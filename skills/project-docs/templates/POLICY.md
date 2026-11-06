# POLICY — <project name>

<!-- All project rules: what is mandatory, recommended, forbidden. A plain observation "we do it this way" → PATTERN.md.
Start from ~/.claude/br/templates/POLICY.defaults.md: copy the policies that apply, keep their P-… ids as headings.
A project-only rule gets a new id in the same style (P-<AREA>-<NAME>). Heading = id only, so links stay short:
POLICY.md#p-http-retries.
Source: `default (P-…)` = taken from defaults, not confirmed; `confirmed YYYY-MM-DD` = the user said yes;
`project` = found in this project's code, CI or linters.
Delete empty areas. -->

## Levels

| Level | Meaning |
|---|---|
| **MUST** | Breaking it = a bug or a rejected review |
| **SHOULD** | You may deviate, with a reason in a comment or PR |
| **MUST NOT** | Never do this, except for the listed exceptions |

---

## Code

### P-CODE-METHOD-JOBS

- **Topic:** method size
- **Level:** MUST
- **Rule:** a method or function does at most two jobs (definition → project-docs skill, section «Jobs»).
- **Why:** big methods are hard to test and change; LLMs tend to bloat them.
- **Exceptions:** orchestrator methods that only glue calls together, each listed in `METHOD.md` with «✅ Justified».
- **How to check:** review; a new method with 3+ jobs goes into `METHOD.md`.
- **Source:** default (P-CODE-METHOD-JOBS)

---

## HTTP clients

### P-HTTP-RETRIES

- **Topic:** retries
- **Level:** <MUST>
- **Rule:** <at most 3 attempts; backoff 0.5 s → 1 s → 2 s ±20% jitter; honour `Retry-After`; only idempotent requests, only on network errors, 429, 502, 503, 504; after the last attempt a domain error>
- **Why:** <a failing neighbour must not get a retry storm or a duplicated side effect>
- **Exceptions:** <payments: <n> attempts — confirmed …>
- **How to check:** <the shared client `<src/shared/http_client.py>` does it; review>
- **Source:** <default (P-HTTP-RETRIES) / confirmed YYYY-MM-DD>

---

## API

### <P-API-IDEMPOTENCY>

- **Topic:** <creating requests>
- **Level:** <...>
- **Rule:** <...>
- **Why:** <...>
- **Exceptions:** <none>
- **How to check:** <...>
- **Source:** <...>

---

## Data

### <P-DB-MIGRATIONS>

### <P-DB-CRITICALITY>

<!-- Data classes (critical / important / disposable) per table live here; DATABASE.md links to it. -->

---

## Security

### <P-SEC-…>

---

## Git

### <P-GIT-FLOW>

### <P-GIT-COMMITS>
