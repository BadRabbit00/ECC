# Passwords, sessions, login protection

## Passwords and registration
- `PasswordHash.recommended()` (pwdlib): argon2id with safe parameters. Only the hash in the DB.
- Old bcrypt hashes: `PasswordHash((Argon2Hasher(), BcryptHasher()))` and `verify_and_update` at login rehash them to argon2id silently.
- `hash` and `verify` run through `run_in_threadpool` (tens of ms of CPU).
- Unknown user → still `verify` against a dummy hash computed once at start: response time must not reveal whether the email exists.

```python
# services/password_service.py — the only place hashes are touched
_hasher = PasswordHash.recommended()
_DUMMY_HASH = _hasher.hash("timing-equalizer")

async def hash_password(password: str) -> str:
    return await run_in_threadpool(_hasher.hash, password)

async def verify_password(password: str, password_hash: str | None) -> bool:
    return await run_in_threadpool(_hasher.verify, password, password_hash or _DUMMY_HASH)
```

- The password is used as given: no `.strip()`, no case changes. Emails are normalised (strip, lower case) and `UNIQUE`.
- Length: min 8 (admins 12), max 128; no composition rules.
- The role at registration never comes from the request: new users get the minimal role. Roles change only through a route under `require_roles(Role.ADMIN)`, with an audit record and a `user.roles_changed` event.
- Password change or reset revokes all of the user's refresh sessions except the current one.

## Refresh sessions
Table `refresh_sessions`: `id`, `user_id`, `family_id` (one chain per login), `jti` (UNIQUE), `expires_at`, `family_expires_at` (absolute limit), `revoked_at`, `replaced_by_jti`, `created_at`, `user_agent`, `ip`. Storing `jti` is enough for a signed refresh JWT; an opaque random refresh is stored only as SHA-256.

**Refresh (`POST /api/auth/refresh`)**, one transaction in the service:
1. `auth.refresh_token_required` checks signature, `exp`, `type`, `aud=auth`, CSRF. Looking up "by hash in the DB" without verifying the JWT is not enough.
2. Load the session by `jti` with `with_for_update()` (or a conditional `update(...).where(RefreshSession.jti == jti, RefreshSession.revoked_at.is_(None)).returning(...)`; 0 rows → check whether the session exists at all). No session → 401.
3. Already revoked or replaced → **reuse**: revoke the whole `family_id`, commit, log `auth.refresh_reuse` with `user_id`, answer 401.
4. `family_expires_at` passed or the user is deactivated → 401.
5. Mark the old session (`revoked_at`, `replaced_by_jti`), create a new one in the same family with `expires_at = min(now + refresh TTL, family_expires_at)`, re-read roles, commit, issue a new pair. Role changes apply at the next refresh, i.e. within the access TTL.

Several tabs refreshing at once look like reuse: the frontend must refresh with one shared request. A server-side tolerance window ≤ 30 s (the repeat gets 401 without revoking the family) is acceptable.

## Logout and revocation
- `logout` finds the session by the refresh token (works with an expired access), revokes its family, puts the current access `jti` (if any) into Redis `auth:revoked:{jti}` with TTL until its `exp`, clears cookies. `logout-all` revokes all families of the user. Logout is `POST` only.

```python
async def is_access_revoked(token: str) -> bool:
    # AuthX passes the raw token BEFORE verifying the signature; the signature is checked right after,
    # so only read jti here. An unreadable token is rejected by that check.
    try:
        jti = jwt.decode(token, options={"verify_signature": False}).get("jti")
    except jwt.PyJWTError:
        return False
    return bool(jti) and await redis.exists(f"auth:revoked:{jti}") == 1
```

- Only auth sees its Redis blocklist; other services learn about revocation through `exp` (hence short access). If instant revocation everywhere is required: auth publishes `auth.sessions_revoked` (`sub`, `jti` or `revoked_before`, `exp`) through the outbox, consumers keep it in their Redis until `exp` and check it in their dependency. Never a "check the token in auth" call per request.

## Login protection
- Rate limits only in Redis (`INCR` + `EXPIRE`, key `auth:rl:{policy}:{key}`): login 5/min per IP+email and 20/min per IP; refresh 30/min per session; registration, password reset, codes 3 per 15 min per address. AuthX `RateLimiter` gets a Redis `backend=` (`increment(key, window)`, `reset(key)`). Login limits are critical: Redis down → login answers 503, never unlimited.
- Per-account brute force: after 10 failures in a row, a 15-minute login lock (Redis counter), `429` + `Retry-After`. Never a permanent lock (a ready-made DoS on someone else's account).
- Uniform answers: «Неверный email или пароль», 401, for an unknown user, a wrong password, and an inactive account. Registration and reset answer the same for taken and free addresses («Проверьте почту»); the email says the address is taken. Timing equalised with the dummy hash.
- Client IP behind a proxy only from trusted headers (`uvicorn --proxy-headers --forwarded-allow-ips=<proxy>`), otherwise everyone shares the proxy's IP.
- Log failed logins, refresh reuse, locks with `user_id` and IP; never passwords, tokens, cookies, or their prefixes.
- First admin: `python -m app.cli.create_admin`, or a seed with a password from env in dev only; in prod that setting blocks startup. No default passwords or secrets in code.
