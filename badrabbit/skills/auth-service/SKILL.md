---
name: auth-service
description: Use when building or changing authentication - the separate auth service on FastAPI + AuthX, ES256 keys and JWKS, claims and TTLs, refresh rotation, passwords, login protection, token verification in consumer services (Python and Go), browser cookies and CSRF, service tokens, and running it in compose.
---

# Auth service

Implementation guide for Alexey's auth model (source: `06-auth`, checked against AuthX 1.7.1 — verify the API against the installed version, not memory). Writer rules: `auth.md` (R-AUTH-*). Security review of auth: `security-review` → `references/auth-jwt.md`.

**Priority.** The user's request > the project's `AGENTS.md`/`CLAUDE.md` > this skill. An existing project with another login scheme is not rebuilt silently: report the difference and offer a migration as a separate task.

## The ten rules

1. Auth is always a separate service with its own code, PostgreSQL, and migrations — also next to a modular monolith.
2. Python + FastAPI + AuthX; passwords argon2id via pwdlib.
3. Client ↔ service authorisation is always JWT.
4. Asymmetric signatures only: ES256 by default, RS256 allowed. Never HS256 or any shared secret.
5. Only auth has the private key; others verify locally with the public key from JWKS, never calling auth per request.
6. Every token has `exp`; access TTL from config, 15 min by default, never infinite.
7. Refresh rotates on every use; its `jti` is stored in PostgreSQL; reuse revokes the whole chain.
8. Browsers keep tokens in httpOnly + Secure + SameSite cookies with CSRF protection, never `localStorage`.
9. The role is checked by a route dependency in each service; the right to an object by the service layer.
10. External IdPs (Keycloak, Authentik, SSO, "log in with …") only on the user's explicit requirement; even then auth stays the only issuer of the product's JWTs.

## References

| File | Read when |
|---|---|
| `references/structure.md` | creating the service: ownership, stack, folder layout, layers, endpoints, code skeleton |
| `references/keys-tokens.md` | keys, JWKS, rotation, claims, TTL table, AuthX config, error mapping, AuthX pitfalls |
| `references/passwords-sessions.md` | password hashing, registration, refresh sessions and rotation, logout and revocation, login protection |
| `references/consumers.md` | verifying tokens in other services (Python and Go code), roles and object rights, browsers and mobile clients, service-to-service tokens, external IdPs |
| `references/run.md` | horizontal scaling, compose (dev and prod), `.env.example`, image rules |
| `references/checklist.md` | anti-patterns and the final checklist |
