# Policy defaults

Base values for a project's `docs/POLICY.md`. Installed at `~/.claude/br/templates/POLICY.defaults.md`.

How the orchestrator uses this file:

1. When a project gets its docs (stage 3 of the flow), copy the policies that apply into `docs/POLICY.md`. Each one gets `Source: default (P-…)`.
2. Policies marked **Ask: yes** go into the question round. Show them as one table in Russian («оставляем так?»), with the default pre-selected.
3. After the user answers, set `Source: confirmed YYYY-MM-DD` or `Source: project`, with the new value.
4. Policies marked **Ask: no** stay default silently. They are listed in the report so the user can object.

Agents treat `Source: default` as "works, but not promised to the business". Reviewers may flag a design that depends on an unconfirmed value.

Contents: [Git](#git) · [Versioning](#versioning) · [HTTP clients](#http-clients) · [API](#api) · [Data](#data) · [Cache](#cache) · [Scaling](#scaling) · [Tests](#tests) · [Code](#code) · [Logging](#logging) · [Dependencies](#dependencies)

---

## Git

### P-GIT-FLOW — branches
- **Default:** `main` = production, `develop` = integration, work in `feature/<task-id>-<slug>` from `develop`. Hotfixes go in `hotfix/<slug>` from `main`, merged into both.
- **Merge into develop:** `git merge --no-ff` after the full test suite is green; the feature branch is deleted after the merge.
- **Agent rights:** anything on `feature/*`; merging into `develop` only when the task is done; nothing on `develop`/`main` beyond that merge (enforced by a hook).
- **Ask: yes** — merge style (`--no-ff` / squash / rebase) and whether `develop` exists at all.

### P-GIT-COMMITS — commit messages
- **Default:** Conventional Commits, English, imperative mood, subject ≤ 72 chars: `type(scope): subject`. Types: `feat fix refactor test docs chore perf ci build`. Scope is the task id or component: `feat(T3): add status filter`. One logical change per commit.
- **Ask: no**

Bad:
```text
fixed stuff + tests + refactor
```
Why: no type, no scope, three changes in one commit; impossible to revert one of them.

Good:
```text
test(T3): cover order status filter
feat(T3): filter orders by status
refactor(T3): extract status parsing into domain
```

---

## Versioning

### P-VER-SEMVER — release versions
- **Default:** SemVer `MAJOR.MINOR.PATCH` per deployable component. The version lives in exactly one place per component (`pyproject.toml`, `Cargo.toml`, `package.json`, a Go `version.go`). Release tag `v<version>` on `main`, set by a human. The changelog is generated from Conventional Commits.
- **Ask: no**

### P-VER-API — API versions
- **Default:** URL prefix `/api/v1/`. A breaking change means a new version (`/api/v2/`); the old one stays for at least one release with a `Deprecation` header. Adding fields is not breaking. Removing or renaming fields or changing types is breaking.
- **Ask: yes** — header versioning instead, if the project already uses it.

---

## HTTP clients

### P-HTTP-TIMEOUTS — timeouts
- **Default:** connect 2 s, total 10 s for internal calls; 30 s for known-slow external APIs (LLM: 120 s, streaming). Never unlimited.
- **Ask: yes** — external APIs with known SLAs.

Bad:
```python
async with httpx.AsyncClient() as client:      # default timeout 5 s for everything, not visible in code
    r = await client.post(url, json=payload)
```
Why: the limit is implicit; one slow neighbour holds a worker forever when someone sets `timeout=None`.

Good:
```python
TIMEOUT = httpx.Timeout(10.0, connect=2.0)      # from settings, see P-HTTP-TIMEOUTS
async with httpx.AsyncClient(timeout=TIMEOUT) as client:
    r = await client.post(url, json=payload)
```

### P-HTTP-RETRIES — retries
- **Default:** at most **3 attempts** total; exponential backoff 0.5 s → 1 s → 2 s with ±20% jitter; honour `Retry-After`. Retry only idempotent requests (GET, PUT, DELETE, POST with `Idempotency-Key`) and only on network errors, `429`, `502`, `503`, `504`. Never retry other `4xx`. After the last attempt, raise a domain error (`PaymentsUnavailable`), not the raw HTTP error.
- **Ask: yes** — the number of attempts for critical integrations (payments).

Bad:
```python
while True:                                   # infinite retry, no backoff
    try:
        return await client.post(url, json=p)  # non-idempotent POST retried → double charge
    except httpx.HTTPError:
        continue
```
Why: a retry storm against a failing neighbour, and a duplicated side effect.

Good:
```python
RETRYABLE = {429, 502, 503, 504}

async def post_idempotent(client: httpx.AsyncClient, url: str, body: dict, key: str, attempts: int = 3) -> httpx.Response:
    for attempt in range(attempts):
        delay = 0.5 * 2**attempt
        try:
            r = await client.post(url, json=body, headers={"Idempotency-Key": key})
            if r.status_code not in RETRYABLE:
                r.raise_for_status()
                return r
            delay = float(r.headers.get("Retry-After", delay))
        except httpx.TransportError:
            pass
        if attempt < attempts - 1:
            await asyncio.sleep(delay * random.uniform(0.8, 1.2))
    raise PaymentsUnavailable()              # domain error, see P-HTTP-CIRCUIT
```

### P-HTTP-CIRCUIT — failing neighbours
- **Default:** when a neighbour fails, degrade instead of returning 500: serve the cache, queue the operation, or switch the feature off. A circuit breaker is used only for high-volume calls (> 10 rps to one neighbour).
- **Ask: no**

---

## API

### P-API-ERRORS — error format
- **Default:** one format for the whole API: `{"detail": "<human text>", "code": "<MACHINE_CODE>"}`, plus `fields` for validation errors. Domain errors map to HTTP codes in one place (`api/errors.py`).
- **Ask: no**

### P-API-PAGINATION — list endpoints
- **Default:** `limit` default 20, max 100. Keyset (`?after=<cursor>`) for feeds, large or growing tables, and anything a public client scrolls. Offset (`?page=`) only for admin tables that stay under ~10k rows. Every list endpoint is paginated, with no exceptions.
- **Ask: yes** — limits for heavy objects.

### P-API-IDEMPOTENCY — creating requests
- **Default:** POST endpoints that create money-, order-, or message-like resources accept `Idempotency-Key` (UUID). The key is stored with the response for 24 h; a repeat returns the stored response.
- **Ask: no**

### P-API-LIMITS — request size and rate
- **Default:** JSON body ≤ 1 MB. File upload through the API ≤ 20 MB; larger files go straight to S3 by presigned URL. Rate limit 60 req/min per user and 600 per IP for the public API; auth endpoints follow the auth rules. Limits are kept in Redis.
- **Ask: yes**

### P-API-METHODS — HTTP semantics
- **Default:** `GET` reads and never changes state; `POST` creates or runs an action; `PUT` replaces; `PATCH` partially updates; `DELETE` deletes. Logout and other state changes are never `GET`.
- **Ask: no**

Bad:
```python
@router.get("/orders/{order_id}/delete")
async def delete_order(order_id: UUID, ...) -> None: ...
```
Why: crawlers, link previews, and prefetch delete data; CSRF protection usually skips GET.

Good:
```python
@router.delete("/orders/{order_id}", status_code=204)
async def delete_order(order_id: UUID, user: ManagerDep, service: OrderServiceDep) -> None:
    await service.delete(order_id, actor=user)
```

---

## Data

### P-DB-MIGRATIONS — schema changes
- **Default:** only through migrations (Alembic / goose / golang-migrate / sqlx / diesel). One logical change per migration, with a working downgrade. Expand → migrate → contract: add first, remove in a later release. Migrations run as a separate step before the app starts.
- **Ask: no**

### P-DB-POOL — connection pool
- **Default:** `pool_size` 5, `max_overflow` 5 per process. The check `(pool_size + max_overflow) × processes × replicas < max_connections − 10` is written in the docs.
- **Ask: yes** — when the replica count is known.

### P-DB-SOFT-DELETE — deletion of business records
- **Default:** business records (orders, payments, users) are soft-deleted with `deleted_at`; technical records (sessions, caches, outbox after delivery) are hard-deleted. Personal-data erasure requests override soft delete.
- **Ask: yes**

### P-DB-CRITICALITY — data classes
- **Default:** every table in `docs/DATABASE.md` has a class:
  - **critical** — money, balances, orders, permissions;
  - **important** — user content, settings;
  - **disposable** — caches, logs, raw API dumps.

  The class decides how strict the db-reviewer is.
- **Ask: yes** — the class of every table, at docs time.

---

## Cache

### P-CACHE-TTL — keys
- **Default:** every key has a TTL (read caches 5 min, reference data 1 h). Key format `<service>:<purpose>:v<N>:<id>`; invalidate by bumping `v<N>`. If Redis is down, the request goes to the DB. Redis is never the only copy of data.
- **Ask: no**

---

## Scaling

### P-SCALE-HORIZONTAL — default scaling model
- **Default:** every service runs as ≥ 2 replicas without code changes. No in-process state that another request needs. Periodic jobs run in exactly one instance (a scheduler service or a leader lock). Vertical scaling only on request or when horizontal is impossible (with the reason written in the docs). A broker is optional; when events must be delivered, use a transactional outbox and idempotent consumers.
- **Ask: no**

---

## Tests

### P-TEST-ORDER — TDD
- **Default:** tests first (written by `test-writer`), then code (`coder`). Code-first only when the user asks for it for a task. Frontend follows the same flow, but UI layout is checked by `ui-verifier` instead of unit tests.
- **Ask: yes** — once per project, then per task only if the user brings it up.

### P-TEST-RUNS — what runs when
- **Default:** during a task, only tests affected by the diff; before merging into `develop`, the full suite of the touched components; CI runs everything on every PR. No fixed coverage percentage; never lower an existing threshold.
- **Ask: no**

---

## Code

### P-CODE-METHOD-JOBS — method size
- **Default:** a method does at most two jobs (definition in the docs standard). Exceptions are recorded in `docs/METHOD.md` with a verdict.
- **Ask: no**

### P-CODE-FILE-SIZE — file size
- **Default:** split a file past ~400 lines or a function past ~50 lines. This is a guideline; a reviewer flags it as MEDIUM, not HIGH.
- **Ask: no**

---

## Logging

### P-LOG-FORMAT — logs
- **Default:** structured JSON to stdout (structlog / slog / tracing). Every request has a `request_id`, which is propagated as `X-Request-ID`. Levels: `error` = someone must act; `warning` = degraded but handled; `info` = business events (`order.created`); `debug` is off in production. Never log secrets, tokens, passwords, or personal data.
- **Ask: no**

---

## Dependencies

### P-DEP-NEW — adding a dependency
- **Default:** a new library, service, or SaaS only with the user's consent and a one-line reason. One tool per job: no second HTTP client, ORM, or queue. Versions are pinned by lock files; updates are a separate task.
- **Ask: no** (the consent is asked at the moment of adding)
