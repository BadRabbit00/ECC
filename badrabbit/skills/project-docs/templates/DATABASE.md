# DATABASE — <project name>

<!-- The MEANING of data lives here: why a table exists, who owns it, how a record lives.
Field types, keys and indexes live only in <db_name>.dbml — do not copy them here.
To view the schema: open dbdiagram.io and paste the .dbml contents. -->

## Databases

| DB | Engine | Purpose | Schema | Owner service |
|---|---|---|---|---|
| `<orders_db>` | <PostgreSQL 16> | <...> | `<orders_db>.dbml` | `<svc-orders>` |

**Migrations:** <tool (alembic / prisma / goose)>, located in `<path>`.
Schema change rule → `POLICY.md#p-db-migrations`

---

## <orders_db>

### `<orders>`

- **Purpose:** <what it stores in business terms; term → GENERAL.md#glossary>
- **Writes:** `<svc-orders>` — **Reads:** `<svc-billing>`, `<svc-reports>`
- **Entity in code:** → `ENTITY.md#<order>`
- **Non-obvious fields:**
  <!-- Only fields whose meaning is not clear from the name. Do not describe `created_at`. -->
  - `<status>` — <meaning>, values → [enum](#order_status)
  - `<total_minor>` — <amount in minor units to avoid rounding errors>
- **Relations:**
  - `<orders.user_id → users.id>` — <why the relation exists, in words>
- **Record life:**
  - created: <when>
  - changed: <what and when>
  - deleted: <never / soft delete via `deleted_at` / after N days>
- **Indexes, why:** <`(user_id, created_at)` — for a user's order history>

---

## Enums

### `<order_status>`

| Value | Meaning | Can move to |
|---|---|---|
| `<new>` | <...> | `<paid>`, `<cancelled>` |
| `<paid>` | <...> | `<shipped>` |
