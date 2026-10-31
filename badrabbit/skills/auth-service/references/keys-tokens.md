# Keys and tokens

## Algorithm
ES256 (ECDSA P-256) by default: short keys and signatures, fast, supported by AuthX, PyJWT, golang-jwt, JWKS clients. RS256 (≥ 2048 bits) only if a consumer cannot do ES256 or the project is already on it. EdDSA: not supported by AuthX 1.7.1. HS256/384/512: never.

```bash
openssl genpkey -algorithm EC -pkeyopt ec_paramgen_curve:P-256 -out jwt.key   # private, auth only
openssl pkey -in jwt.key -pubout -out jwt.pub                                 # public
```

## Storage
- Private key never in git, images (`COPY`/`ARG`/`ENV`), compose, logs, docs, or agent replies; never printed. Prod: platform secret or docker secret mounted as a file (`AUTH_JWT_PRIVATE_KEY_FILE=/run/secrets/jwt_private_key`); PEM in env only if the platform cannot mount files.
- Locally a one-shot `auth-keygen` service creates the pair in a named volume if absent. Never generated at app start (each replica would get its own key; restarts would log everyone out).
- Auth refuses to start without a key; the public key is derived from the private one.
- `kid` = first 16 hex chars of SHA-256 of the public PEM; every token carries it.
- A key or signing secret found in git (history included) is compromised: tell the user, propose rotation; never rewrite history yourself.

## JWKS
`GET /.well-known/jwks.json` serves the current and (during rotation) previous public keys with `kid`, `use: "sig"`, `alg`; `Cache-Control: public, max-age=300`. Simplification allowed for 2–3 services where redeploy-on-rotation is fine: public PEMs in the consumer's env (`ORDERS_AUTH_PUBLIC_KEYS`).

```python
# core/keys.py
def public_jwk(public_key: EllipticCurvePublicKey, kid: str) -> dict[str, Any]:
    jwk = ECAlgorithm.to_jwk(public_key, as_dict=True)      # from jwt.algorithms import ECAlgorithm
    return {**jwk, "kid": kid, "use": "sig", "alg": "ES256"}
```

## Rotation without downtime
AuthX verifies with the current key and one previous (`JWT_PREVIOUS_PUBLIC_KEY`): at most two keys live at once.
1. Generate a new pair; publish the new public key in JWKS next to the current one, without signing with it; wait the consumers' JWKS cache time (≥ 10 min).
2. Switch signing to the new key; move the old public key to `JWT_PREVIOUS_PUBLIC_KEY`, keep it in JWKS.
3. After the refresh TTL (the longest token signed by the old key), remove the old key everywhere.
4. Compromise: remove the key from JWKS immediately, revoke all refresh sessions, everyone logs in again — the user decides.

## Claims

| Claim | Rule |
|---|---|
| `sub` | user UUID as a string; not email or login |
| `exp`, `iat` | always (AuthX sets them from the TTL) |
| `jti` | unique id; for refresh set it yourself and store it |
| `iss` | auth's id (`JWT_ENCODE_ISSUER`); consumers check it |
| `aud` | access: the product API id (`shop-api`); refresh: `auth`; service token: the target service |
| `type` | `access` or `refresh` (AuthX); consumers accept only `access` |
| `roles` / `scopes` | the minimum needed for checks |
| `sid` | refresh family id, for revocation and audit |

AuthX also adds `fresh` and `csrf`. Never personal data, secrets, internal flags, or long permission lists: a JWT is signed, not encrypted, and large tokens hit header limits.

## TTL
Configured in `.env` (`AUTH_ACCESS_TTL_MINUTES`, `AUTH_REFRESH_TTL_DAYS`, `AUTH_SESSION_MAX_DAYS`), validated at startup by range (out of range → no start, also in dev).

| Token | Default | Range | Depends on |
|---|---|---|---|
| access | 15 min | 5–30, hard cap 60 | it cannot be revoked in other services before `exp`: TTL = damage window. Money, personal data, admin: 5–10 min; low-risk internal tools: up to 30 |
| refresh | 14 days | 1–30 (mobile up to 90) | client type: admin a working day (8–24 h), web 7–14 days, mobile 30–90 |
| whole session | 30 days | ≥ refresh | absolute limit: rotation never extends a login forever |
| service | 10 min | 5–15 | no refresh; the client fetches a new one early |

Never `JWT_ACCESS_TOKEN_EXPIRES=None` (AuthX then issues tokens without `exp`), day-long access, year-long TTLs, "eternal" integration tokens.

## AuthX configuration

```python
# core/config.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="AUTH_")
    env: Literal["dev", "prod"] = "prod"               # strict by default
    database_url: str
    redis_url: str
    jwt_private_key_file: Path
    jwt_previous_public_key_file: Path | None = None   # only during rotation
    jwt_issuer: str = "auth"
    jwt_audience: str
    access_ttl_minutes: int = Field(15, ge=5, le=60)
    refresh_ttl_days: int = Field(14, ge=1, le=90)
    session_max_days: int = Field(30, ge=1, le=180)
    cookie_secure: bool = True
    # model_validator: prod forbids cookie_secure=False, an env-seeded admin, CORS "*"

# core/security.py
REFRESH_AUDIENCE = "auth"
auth = AuthX(config=AuthXConfig(          # every value explicit: AuthXConfig is a BaseSettings and reads JWT_* env itself
    JWT_ALGORITHM="ES256",
    JWT_PRIVATE_KEY=keys.private_pem, JWT_PUBLIC_KEY=keys.public_pem,
    JWT_PREVIOUS_PUBLIC_KEY=keys.previous_public_pem,
    JWT_ENCODE_ISSUER=settings.jwt_issuer, JWT_DECODE_ISSUER=settings.jwt_issuer,
    JWT_ENCODE_AUDIENCE=settings.jwt_audience,
    JWT_DECODE_AUDIENCE=[settings.jwt_audience, REFRESH_AUDIENCE],
    JWT_ACCESS_TOKEN_EXPIRES=timedelta(minutes=settings.access_ttl_minutes),
    JWT_REFRESH_TOKEN_EXPIRES=timedelta(days=settings.refresh_ttl_days),
    JWT_TOKEN_LOCATION=["cookies", "headers"],
    JWT_COOKIE_SECURE=settings.cookie_secure, JWT_COOKIE_SAMESITE="lax", JWT_COOKIE_CSRF_PROTECT=True,
    JWT_REFRESH_COOKIE_PATH="/api/auth",   # refresh cookie goes only to auth; keep the CSRF cookie on "/"
))
auth.set_callback_token_blocklist(is_access_revoked)

# services/token_service.py
access = auth.create_access_token(
    uid=str(user.id), fresh=is_login, headers={"kid": keys.kid},
    data={"roles": sorted(r.value for r in user.roles), "sid": str(session.family_id)},
)
refresh = auth.create_refresh_token(
    uid=str(user.id), headers={"kid": keys.kid}, audience=REFRESH_AUDIENCE, expiry=session.expires_at,
    data={"jti": str(session.jti), "sid": str(session.family_id)},   # own jti, stored in the DB
)
```

## Errors

```python
# api/errors.py — the only place errors become HTTP; do NOT call auth.handle_errors(app)
STATUS_BY_ERROR = {InvalidCredentials: 401, SessionRevoked: 401, AccountLocked: 429, EmailTaken: 409}

def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error(_: Request, exc: DomainError) -> JSONResponse:
        status = next((s for cls, s in STATUS_BY_ERROR.items() if isinstance(exc, cls)), 400)
        return JSONResponse({"detail": str(exc), "code": exc.code}, status_code=status)

    @app.exception_handler(AuthXException)
    async def authx_error(_: Request, exc: AuthXException) -> JSONResponse:
        if isinstance(exc, InsufficientScopeError):
            return JSONResponse({"detail": "Недостаточно прав", "code": "FORBIDDEN"}, status_code=403)
        return JSONResponse({"detail": "Требуется вход", "code": "UNAUTHORIZED"}, status_code=401)
```

(`EmailTaken` is for internal flows such as an admin creating a user; public registration must not reveal a taken address — see `passwords-sessions.md`.)

## AuthX facts (1.7.1)
- Protect routes with `Depends(auth.access_token_required)` / `auth.refresh_token_required` (signature, `exp`, `iss`, `aud`, `type`, CSRF for cookies, the revocation callback). `auth.fresh_token_required` for password/email change and account deletion. `auth.scopes_required("orders:write")` → 403.
- `auth.verify_token(...)` called directly does NOT run the revocation callback: verify through the dependencies.
- Custom claims: `payload.model_extra["roles"]` (`payload.extra_dict` is empty in this version).
- `auth.handle_errors(app)` answers 422 with `{"message","error_type"}`: use the handler above instead.
- Cookies: `set_access_cookies`, `set_refresh_cookies`, `unset_cookies`; JS-readable `csrf_access_token` / `csrf_refresh_token` are set too.
- Not in AuthX (do it yourself): JWKS and key selection by `kid`; requiring `exp` on verification; refresh session storage and reuse detection.
- Built-in `RateLimiter` and session storage are in-process by default: in prod only with a Redis/PostgreSQL backend.
- Never use `implicit_refresh_middleware`: it extends access without checking the refresh session.
