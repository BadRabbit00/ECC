# API — <project name>

<!-- Contracts live here: paths, methods, bodies, response codes, events, webhooks.
Rules (retries, idempotency, general anti-patterns) live in POLICY.md — here only one line with a link.
Delete empty sections entirely. -->

## Common

- **Base URL:** `<https://api.example.com>` <!-- per environment → SPECIFICATION.md#environments -->
- **Format:** <JSON / protobuf / ...>
- **Versioning:** <`/v1/` in path / header / none>
- **Auth:** → `SPECIFICATION.md#external-auth`
- **Common headers:**
  - `<Authorization: Bearer <token>>` — <why>
  - `<X-Request-Id>` — <why>
- **Retries:** → `POLICY.md#p-http-retries`
- **Idempotency:** → `POLICY.md#p-api-idempotency`

### Error format

<!-- One format for the whole project. Several formats is a problem — write ❓. -->

```json
{
  "error": {
    "code": "<machine_readable_code>",
    "message": "<human readable text>",
    "details": {}
  }
}
```

| HTTP code | When |
|---|---|
| `400` | <...> |
| `401` | <...> |

---

## 1. External API

<!-- Endpoints the outside world uses: clients, partners, frontend.
Group by resource. One endpoint = one card. -->

### <Resource: Orders>

#### `<POST /v1/orders>`

- **Purpose:** <one line; business process → GENERAL.md#<...>>
- **Called by:** <frontend / partner / mobile>
- **Permissions:** <required role>
- **Headers:** <only endpoint-specific; common ones are above>
- **Params / body:**
  ```json
  { "<field>": "<type> — <meaning>" }
  ```
- **Response:** `<201>` + <what it returns>
- **Errors:** `<409>` — <when>
- **Idempotent:** <yes, by `Idempotency-Key` / no>
- **Anti-patterns:** <how NOT to call it, one line; general rules → POLICY.md>

### Webhooks

#### Incoming

<!-- Someone outside calls us. -->

##### `<POST /webhooks/payment>`

- **From:** <sender service>
- **When it arrives:** <event>
- **Authenticity check:** <HMAC signature in header `...` / IP allowlist>
- **Body:** <key fields>
- **What we do:** <system reaction>
- **Reply to sender:** <`200` immediately, processed async>

#### Outgoing

<!-- We call someone outside. -->

##### `<order.paid>`

- **To:** <URL / subscribers>
- **When we send:** <event>
- **Body:** <key fields>
- **Signature:** <how we sign>
- **Retries:** → `POLICY.md#p-http-retries`

---

## 2. Internal API

### Service map

<!-- Who calls whom. One line = one link. Reasons "why like this" → SPECIFICATION.md. -->

```
<svc-orders>   → <svc-billing>        : HTTP   : create invoice
<svc-billing>  ⇢ <svc-notify>         : events : <invoice.paid>
<svc-orders>   → <postgres:orders_db> : SQL    : <...>
```

`→` synchronous call, `⇢` asynchronous event.

### <svc-orders>

- **Why this service:** → `SPECIFICATION.md#<svc-orders>`

#### Endpoints / RPC

##### `<GET /internal/orders/{id}>`

- **Called by:** <svc-...>
- **Purpose:** <...>
- **Response:** <...>
- **Auth:** → `SPECIFICATION.md#internal-auth`

#### Events

| Event / topic | Publishes or consumes | Key fields | Why |
|---|---|---|---|
| `<order.created>` | publishes | `<order_id, user_id>` | <...> |

---

## 3. Frontend API

<!-- Only if the frontend has its own server side: BFF, server routes, server actions, SSR proxy.
Plain frontend → backend calls are already in "External API". No server side — delete this section. -->

### `<GET /api/session>`

- **Location:** `<frontend/app/api/session/route.ts>`
- **Purpose:** <...>
- **Calls further:** `<POST /v1/auth/refresh>`
- **Response:** <...>
