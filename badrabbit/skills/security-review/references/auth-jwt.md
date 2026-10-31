# Auth and JWT (from `06-auth`)

The project's model: one separate `auth` service issues tokens; every other service verifies them locally.

## Issuing (auth service)
- ES256 (RS256 only with a reason); never HS256 or a shared secret. The private key exists only in auth, from a secret or the `auth-keygen` volume; auth refuses to start without it; all replicas share one key; every token has `kid`.
- Claims: `sub` (UUID), `roles`/`scopes`, `sid`, `exp`, `iat`, `jti`, `iss`, `aud`, `type`. No email, name, phone.
- Access 15 min by default (5–60, validated at startup); refresh rotates on every use with `jti` stored in PostgreSQL; reuse revokes the family; an absolute session limit exists. Concurrent refresh is closed by `FOR UPDATE` or a conditional `UPDATE`.
- Logout is `POST`, revokes the session, and blocklists the access `jti` in Redis until its `exp`.
- Passwords: pwdlib + argon2id in a thread pool; the password used as given (no strip/lower); a dummy hash equalises timing for unknown users.
- Registration takes the minimal role; roles change only by an admin.
- Rate limits in Redis: login 5/min per IP+email and 20/min per IP; refresh 30/min per session; registration/reset/codes 3 per 15 min per address. After 10 failures in a row, a 15-minute lock with `429` + `Retry-After` (never a permanent lock). Client IP only from trusted proxy headers.
- AuthX errors are mapped to 401/403 `{"detail","code"}`, not 422.

## Verifying (every consumer)
- Own 30–80-line verifier (`core/security.py` + `api/deps.py`, or `internal/middleware/auth_middleware.go`), not a shared package. Python uses PyJWT, not AuthX.
- Signature by JWKS key with matching `kid`; algorithm from a whitelist in code; ignore `jku`, `x5u`, `jwk` headers; JWKS URL only from config.
- Require `exp`, `iat`, `sub`, `jti`, `iss`, `aud`; `aud` = this API; `type == "access"`; leeway ≤ 30 s.
- JWKS cached in process, refreshed every 10 min and on unknown `kid` (at most every 30 s). Auth down → cached keys keep working; no dependency on auth in `depends_on` or `/ready`.
- Roles by a route dependency; object rights in the service with an explicit actor, raising `PermissionDenied`.
- Never read the users table; never call auth per request.

## Browsers and clients
- Browsers: `HttpOnly; Secure; SameSite=Lax` cookies; same origin through the proxy; CSRF double submit: `X-CSRF-TOKEN` on POST/PUT/PATCH/DELETE compared in constant time. `GET /api/auth/me` instead of decoding the JWT in JS. 401 handling only in `http.ts` (single-flight refresh, retry once, then login).
- `Authorization: Bearer` for mobile, server clients, CLI, integrations; a separate login endpoint returns tokens in the body; the browser login never does. Mobile stores tokens in Keychain/Keystore.
- Never `localStorage`/`sessionStorage`/IndexedDB, never tokens in URLs.

## Service-to-service
- Client credentials at `POST /internal/token`; secret in the caller's env, argon2 hash in `service_clients` with allowed `aud` and scopes. Service token: no user roles, no refresh, TTL ≤ 15 min, `aud` = target. User tokens are refused on `/internal/*`, service tokens on public routes.
- No static shared API keys; if one exists: `compare_digest`, ≥ 32 bytes, no default in code, replacement proposed as a task.

## Red flags (grade at least HIGH)
HS256 with a shared secret · algorithm taken from the token · `verify_signature: False` or missing `aud`/`iss`/`exp` checks · refresh accepted as access · tokens without `exp` or with day-long TTL · trust in `X-User-Id` / `AUTH_DISABLED` without the dev double guard · role from the registration body · tokens in `localStorage` or URLs · rate limiters in process memory · different answers for "no user" and "wrong password".
