# Consumers, clients, service tokens

## Verifying tokens in other services
- Each service keeps its own 30–80-line verifier: Python `core/security.py` + `api/deps.py`, Go `internal/middleware/auth_middleware.go`. No shared package (small duplication is cheaper than releasing all services together).
- Always check: signature with the JWKS key by `kid`; algorithm from a whitelist in code (`["ES256"]`), never from the token header or JWK; presence of `exp`, `iat`, `sub`, `jti`; `iss`; `aud` = this API; `type == "access"`; clock leeway ≤ 30 s.
- JWKS URL only from config; ignore `jku`, `x5u`, `jwk` headers.
- JWKS loaded lazily and cached in the process, re-read every 10 min and on an unknown `kid` (at most every 30 s). Auth down → cached keys keep working. No dependency on auth in `depends_on` or `/ready`.
- Python consumers use PyJWT, not AuthX (no JWKS, does not require `exp`).

```python
# core/security.py (consumer)
class JwtVerifier:
    def __init__(self, jwks_url: str, issuer: str, audience: str) -> None:
        self.jwks_url, self.issuer, self.audience = jwks_url, issuer, audience
        self.keys: dict[str, jwt.PyJWK] = {}
        self.fetched_at = 0.0

    async def _load_keys(self) -> None:
        if time.monotonic() - self.fetched_at < 30:
            return
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(self.jwks_url)
            resp.raise_for_status()
        self.keys = {k.key_id: k for k in jwt.PyJWKSet.from_dict(resp.json()).keys if k.key_id}
        self.fetched_at = time.monotonic()

    async def verify(self, token: str) -> dict[str, Any]:
        kid = jwt.get_unverified_header(token).get("kid")
        if kid not in self.keys or time.monotonic() - self.fetched_at > 600:
            await self._load_keys()
        if kid not in self.keys:
            raise jwt.InvalidKeyError("unknown kid")
        claims = jwt.decode(token, self.keys[kid].key, algorithms=["ES256"], issuer=self.issuer,
                            audience=self.audience, leeway=30,
                            options={"require": ["exp", "iat", "sub", "jti", "iss", "aud"]})
        if claims.get("type") != "access":
            raise jwt.InvalidTokenError("access token required")
        return claims
```

```python
# api/deps.py (consumer) — rights through dependencies, not ifs spread through the code
async def get_current_user(request: Request) -> CurrentUser:
    header = request.headers.get("Authorization", "")
    token = header.removeprefix("Bearer ") if header.startswith("Bearer ") else request.cookies.get("access_token_cookie")
    if not token:
        raise HTTPException(401, "Требуется вход")
    try:
        claims = await verifier.verify(token)
    except jwt.PyJWTError:
        raise HTTPException(401, "Требуется вход") from None
    except httpx.HTTPError:
        raise HTTPException(503, "Проверка входа временно недоступна") from None
    if not header and request.method not in {"GET", "HEAD", "OPTIONS"}:   # cookie token → CSRF
        csrf = claims.get("csrf") or ""
        if not csrf or not hmac.compare_digest(request.headers.get("X-CSRF-TOKEN", ""), csrf):
            raise HTTPException(401, "CSRF-проверка не пройдена")
    return CurrentUser(id=UUID(claims["sub"]), roles=frozenset(claims.get("roles", [])))

CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]

def require_roles(*roles: Role) -> Callable[[CurrentUser], CurrentUser]:
    def checker(user: CurrentUserDep) -> CurrentUser:
        if user.roles.isdisjoint(r.value for r in roles):
            raise HTTPException(403, "Недостаточно прав")
        return user
    return checker

ManagerDep = Annotated[CurrentUser, Depends(require_roles(Role.MANAGER, Role.ADMIN))]
```

```go
// Go: golang-jwt/jwt/v5 + MicahParks/keyfunc/v3
jwks, err := keyfunc.NewDefaultCtx(ctx, []string{cfg.JWKSURL}) // background refresh, re-read on unknown kid

type Claims struct {
	Type  string   `json:"type"`
	Roles []string `json:"roles"`
	CSRF  string   `json:"csrf"`
	jwt.RegisteredClaims
}

claims := &Claims{}
_, err = jwt.ParseWithClaims(raw, claims, jwks.Keyfunc,
	jwt.WithValidMethods([]string{"ES256"}), jwt.WithIssuer(cfg.Issuer), jwt.WithAudience(cfg.Audience),
	jwt.WithExpirationRequired(), jwt.WithIssuedAt(), jwt.WithLeeway(30*time.Second))
if err != nil || claims.Type != "access" {
	c.AbortWithStatusJSON(http.StatusUnauthorized, gin.H{"detail": "Требуется вход", "code": "UNAUTHORIZED"})
	return
}
// cookie token + mutating method → X-CSRF-TOKEN must equal claims.CSRF (subtle.ConstantTimeCompare)
// roles: a RequireRole(...) middleware on the route group; object rights: in the service
```

- **Role** = a route dependency (`user: ManagerDep`). **Object right** (own order, own org) = the service layer: it receives the actor explicitly, reads the object, raises domain `PermissionDenied`. A hidden button is not protection.
- Never read the users table: `sub` and roles come from claims, the rest from auth's API or a local projection.
- No "auth off" mode (`AUTH_DISABLED`, trusting `X-User-Id`/`X-Dev-User`) in shared code. If the user explicitly wants one for local dev: refuse to start when `env != dev`, and check `env` in the dependency on every request.
- Consumer tests: role × endpoint matrix, expired token, refresh used as access, foreign `aud`, token without `exp`, cookie mutation without the CSRF header.

## Browsers and clients
- **Browser = cookies only.** Auth sets access and refresh as `HttpOnly; Secure; SameSite=Lax`; JS never sees tokens. Frontend and APIs share one origin through the reverse proxy (`/api/auth/*`, `/.well-known/*` → auth; `/api/orders/*` → orders), so cookies reach every service without CORS.
- **CSRF double submit** (built into AuthX): `http.ts` reads `csrf_access_token` (on `/api/auth/refresh` and `/api/auth/logout`: `csrf_refresh_token`) and sends it as `X-CSRF-TOKEN` on POST/PUT/PATCH/DELETE.
- Who is logged in: `GET /api/auth/me`, never decoding the JWT in the browser. UI rights are display only.
- **401 handling** only in `http.ts`: one shared `POST /api/auth/refresh` (single flight), retry the original request once, then the login page.
- `SameSite=None` only for a frontend on another site; then the CSRF header is mandatory and CORS has `allow_credentials` with an explicit origin list, never `*`.
- `Authorization: Bearer` for mobile apps, server clients, CLIs, integrations: a separate login endpoint returns the pair in the body (`TokenResponse`); the browser login never does. Mobile apps keep tokens in Keychain/Keystore.
- Never `localStorage`, `sessionStorage`, IndexedDB, or tokens in URLs (`?token=`, `#access_token=`).

## Service to service
- A service calling another's `/internal/...` gets a service token from auth by client credentials: `POST /internal/token` with `client_id` and `client_secret`. The secret is in the caller's env; `service_clients` stores only its argon2 hash, allowed `aud`, and scopes.
- Service token = access JWT without user roles or refresh: `auth.create_access_token(uid=f"service:{client.name}", audience=target, scopes=client.scopes, expiry=timedelta(minutes=10), headers={"kid": keys.kid})`. The client caches it in memory and refreshes a minute before `exp`.
- The target verifies it with the same verifier, its own name in `aud`, and the required scopes. User tokens are refused on `/internal/...`; service tokens on public routes.
- Acting for a user in a neighbour's public API: forward the user's own access token.
- No static shared API keys; an existing one is compared with `hmac.compare_digest`, ≥ 32 bytes, no default in code, replacement proposed as a task.
- Every outgoing call has a timeout (2–10 s) and bounded retries; an unavailable neighbour becomes a domain error, not a 500 with a stack trace.

## External IdPs
- None by default. Keycloak, Authentik, corporate SSO, "log in with Google/GitHub" only on the user's explicit requirement; never proposed as a replacement.
- Even then auth remains the only issuer of the product's JWTs: it acts as an OAuth/OIDC client (Authorization Code + PKCE), verifies the IdP's `id_token` by its JWKS (algorithm whitelist, `iss`, `aud` = own `client_id`), links accounts in `user_identities` (`provider`, `provider_subject`), maps IdP groups to roles, and issues its own tokens.
- Services trusting the IdP's tokens directly only if the user explicitly requires it; then the verification rules apply to the IdP's JWKS, `iss`, `aud`, each app has its own IdP client, and the decision is recorded in the project docs.
- The OAuth client library is agreed with the user; the protocol is never hand-written.
