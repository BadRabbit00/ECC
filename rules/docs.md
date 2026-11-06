---
paths:
  - "docs/**"
---

# Project docs

## Scope

`docs/` of a project: the 10 files (`GENERAL`, `API`, `DATABASE` + `<db>.dbml`, `STRUCTURE`, `ENTITY`, `METHOD`, `SPECIFICATION`, `PATTERN`, `POLICY`, `OVERVIEW`) and `docs/slides/`. The full standard is in the `project-docs` skill. Only the orchestrator writes here.

## Rules

- R-DOCS-ENGLISH: docs are in English. `docs/slides/*.html` are in Russian.
- R-DOCS-ONE-HOME: every fact is written in full in exactly one file; other files link to it as `FILE.md#anchor`. Never retell what you link to.
- R-DOCS-NO-INVENTION: a fact that is not in the code, the materials, or the user's words becomes `❓ <question>`. Before hand-off, every `❓` is collected in `OVERVIEW.md#open-questions`.
- R-DOCS-MARKERS: `🆕` at the end of a heading means planned, not implemented; `🗑️` means it exists and will be removed. A card without a marker describes what is in the code now. Remove the marker when the task is done.
- R-DOCS-HOMES: field types live only in `.dbml`; API contracts only in `API.md`; rules only in `POLICY.md`; method details only in `METHOD.md` (methods with 3+ jobs, each with a verdict).
- R-DOCS-POLICY-SOURCE: every policy in `POLICY.md` has `Source: default (P-…) | confirmed YYYY-MM-DD | project`.
- R-DOCS-NO-HINTS: no template hints (`<!-- -->`, `<…>`) and no empty sections remain after filling.

## Examples

### R-DOCS-ONE-HOME — link, do not repeat

Bad:
```markdown
<!-- API.md -->
#### `POST /v1/orders`
- **Retries:** 3 attempts, exponential backoff 0.5s→1s→2s, only on 429/502/503/504.
```
Why: the same rule now lives in API.md and POLICY.md, and one of them will go stale.

Good:
```markdown
<!-- API.md -->
#### `POST /v1/orders`
- **Retries:** → `POLICY.md#p-http-retries`
```

### R-DOCS-MARKERS — planned vs existing

Bad:
```markdown
#### `GET /v1/orders/{id}/invoice`
- **Purpose:** returns the invoice PDF link
```
Why: an agent reading this assumes the endpoint exists and calls it.

Good:
```markdown
#### `GET /v1/orders/{id}/invoice` 🆕
- **Purpose:** returns the invoice PDF link
```
