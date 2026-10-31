---
paths:
  - "src/auth/**"
  - "**/security.py"
  - "**/deps.py"
  - "**/middleware/auth*"
  - "**/auth_middleware.*"
---

# Authentication and authorization

## Scope

The `auth` service and the token checks in every consumer service. The full implementation guide (AuthX config, refresh rotation, JWKS, rate limits, compose) is the `auth-service` skill. Read it before you build or change auth.

## Rules

- R-AUTH-SEPARATE: auth is always a separate service with its own PostgreSQL, migrations, and Redis, written in Python + FastAPI + AuthX. No auth module inside a monolith. No external IdP unless the user explicitly requires one.
- R-AUTH-ES256: tokens are signed with ES256 (RS256 only with a reason). Never HS256 or a shared secret. Only auth holds the private key.
- R-AUTH-VERIFY-LOCAL: consumers verify tokens locally from JWKS, by `kid`. The algorithm comes from a whitelist in code, never from the token header. Require `exp`, `iat`, `sub`, `jti`, `iss`, `aud`, and `type == "access"`; allow 30 s leeway. Never call auth per request. Never depend on auth in `depends_on` or `/ready`.
- R-AUTH-CLAIMS: claims are `sub` (UUID), `roles`/`scopes`, `sid`. No email, name, phone, or other personal data in the payload.
- R-AUTH-TTL: access is 15 min by default (5–60 min, validated at startup); refresh rotates on every use, its `jti` is stored in PostgreSQL, and reuse revokes the whole family. Never a token without `exp`.
- R-AUTH-BROWSER: browsers get httpOnly + Secure + SameSite cookies plus a CSRF header on every mutating request. Never `localStorage`, never a token in a URL.
- R-AUTH-ROLES: the role is checked by a dependency/middleware on the route; the right to a specific object (own order, own org) is checked in the service, which raises a domain `PermissionDenied`.
- R-AUTH-PASSWORDS: argon2id through pwdlib, called via `run_in_threadpool`. Unknown users are checked against a dummy hash. One error message for every login failure.
- R-AUTH-INTERNAL: service-to-service calls use short-lived service tokens (client credentials, `aud` = target service), never a static shared API key.

## Examples

### R-AUTH-VERIFY-LOCAL — whitelist the algorithm, require claims

Bad:
```python
header = jwt.get_unverified_header(token)
claims = jwt.decode(token, public_key, algorithms=[header["alg"]])   # attacker picks the algorithm
```
Why: algorithm confusion. `exp`, `aud` and `type` are not required, so refresh tokens and foreign tokens pass.

Good:
```python
claims = jwt.decode(
    token, self.keys[kid].key, algorithms=["ES256"],
    issuer=self.issuer, audience=self.audience, leeway=30,
    options={"require": ["exp", "iat", "sub", "jti", "iss", "aud"]},
)
if claims.get("type") != "access":
    raise jwt.InvalidTokenError("access token required")
```

### R-AUTH-ROLES — role on the route, object right in the service

Bad:
```python
@router.get("/orders/{order_id}")
async def get_order(order_id: UUID, user: CurrentUserDep, service: OrderServiceDep) -> OrderRead:
    order = await service.get(order_id)
    if user.role != "admin" and order.owner_id != user.id:     # string role, check in the router
        raise HTTPException(403)
    return OrderRead.model_validate(order)
```
Why: a magic string role, and the object check lives only in this route; the next route forgets it.

Good:
```python
@router.get("/orders/{order_id}")
async def get_order(order_id: UUID, user: CustomerDep, service: OrderServiceDep) -> OrderRead:
    return OrderRead.model_validate(await service.get_for(order_id, actor=user))

# service
async def get_for(self, order_id: UUID, *, actor: CurrentUser) -> Order:
    order = await self.orders.get(order_id) or raise_not_found(order_id)
    if Role.ADMIN not in actor.roles and order.owner_id != actor.id:
        raise PermissionDenied("order", order_id)
    return order
```
