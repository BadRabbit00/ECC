---
name: risk-model
description: Use when building or updating a project's risk map - inventory of data and business-process assets, C/I/A/R scores on a 0-10 scale with reasons, exposure from the architecture, and the computed magnitude and risk in docs/RISK.toml and docs/RISK.md. Not a vulnerability review.
---

# Risk model

A method to find **where security matters for the business**, before anyone looks for vulnerabilities. It answers: which data and processes would hurt most if leaked, corrupted, stopped or found non-compliant, and how reachable they are. Vulnerability review (`security-review`) comes later and uses this map to grade its findings.

## Contents

1. [When to use](#when-to-use) · 2. [Assets](#assets) · 3. [Scores](#scores) · 4. [Exposure and scope](#exposure-and-scope) · 5. [The numbers are the script's](#the-numbers-are-the-scripts) · 6. [Procedure](#procedure) · 7. [Output](#output) · 8. [Reference files](#reference-files)

## When to use

- The orchestrator's risk-map step: after the docs (G3), before the plan and any code.
- An existing project without `docs/RISK.toml`, or a change that adds a process, a data group, a store, an integration, or opens something to the internet.
- `db-reviewer`, `security-reviewer`, `architect-critic` read the result; they do not build it.

## Assets

Only **data** and **business processes**. No computers, servers, laptops or people: those are where assets live and who touches them, not the assets.

| Kind | What | From | Id |
|---|---|---|---|
| process | a business process: trigger → steps → result | `docs/GENERAL.md` processes | `P-01` |
| data | a group of data with one meaning and one owner: an entity group, uploaded files, secrets and keys, logs with personal data | `docs/DATABASE.md`, `ENTITY.md`, `SPECIFICATION.md` (secrets, storage) | `D-01` |

Rules:
- **Group, do not list tables.** `customers` + `addresses` + `contacts` = one asset "customer personal data". Split a group only when its parts score differently (password hashes vs profile names).
- **Every data asset is used by at least one process**, and every process uses at least one data asset. A dangling asset means the map is wrong.
- **Secrets are data assets** (`kind = "secret"`): JWT signing keys, API keys of payment providers, database credentials.
- **Logs and backups** are data assets when they hold personal or business data.
- Each asset names its sources (`docs/...#anchor`, `file:line`). A fact you cannot find is a ❓ question, never a guess.

## Scores

Four axes, integers **0–10**, each with a one-line reason. The full anchor tables are in `references/scales.md`: pick the band whose consequence matches, then the number inside it.

| Axis | Question |
|---|---|
| **C** confidentiality | what does it cost if this leaks to someone who should not see it? |
| **I** integrity | what does it cost if it is wrong, tampered with, or silently lost? |
| **A** availability | what does it cost if it is unavailable, and after how long does it hurt? |
| **R** compliance | which law, regulator, partner or contract is broken if C, I or A fails, and how badly? |

Score **consequences, not likelihood**: "a leak means a fine and notifying every customer" is C; "the endpoint has no auth" is exposure, not C.

Consequence kinds, all four count: money (lost revenue, fines, refunds), law and contracts, reputation and customers, stopped operations.

Inheritance is done by the script, not by you. Down: data gets at least the A of every process that uses it, and the I of every process that writes it (`w`, `rw`); when a process depends on that data less than its own score, set `need = { I = n, A = n }` on the link. Up: a process gets at least the C and R of the data it uses, except secrets (`kind = "secret"`), which are scored on their own asset. Score each asset **as it is on its own**; do not pre-raise.

## Exposure and scope

**Exposure (0–10)** comes from the architecture, not from bugs:

| Exposure | Reachable by |
|---|---|
| 0–1 | nothing outside the service: internal job, no inbound path |
| 2–3 | staff only, inside the network or VPN, after login |
| 4–5 | staff over the internet after login and 2FA; or a trusted partner over mTLS |
| 6–7 | customers over the internet after login; or a third-party service that holds or processes the data |
| 8–9 | anyone on the internet without login, or through a public webhook / form |
| 10 | public by design (open API, public bucket) or already copied to third parties outside our control |

**Scope** — how much of the business the asset carries: `one` (one process or a small set of records), `several` (several processes or a large share of customers), `all` (the whole business or every customer).

## The numbers are the script's

You never compute magnitude, risk or level, and never write them anywhere. Fill `docs/RISK.toml` (template: `~/.claude/br/templates/RISK.toml`) and the orchestrator runs:

```bash
~/.claude/br/bin/br-risk docs/RISK.toml          # writes docs/RISK.md and docs/RISK.json
~/.claude/br/bin/br-risk docs/RISK.toml --check  # validation only
```

For reference only: magnitude = min(10, (max + 0.1 × sum of the other three) × scope), scope one 1.0 / several 1.1 / all 1.2; risk = magnitude × exposure / 10; levels critical ≥ 8, high ≥ 6, medium ≥ 4, low ≥ 2. The coefficients live in `[model]` of the project's `RISK.toml`; they change only with the user's agreement.

## Procedure

1. **Read** `docs/GENERAL.md` (processes), `SPECIFICATION.md` (services, stores, integrations, auth, secrets), `DATABASE.md`, `API.md`; in mode B, the researcher cards. Code only to confirm where data lives.
2. **List processes**, then **data groups**, then the `uses` links (with `r`, `w`, `rw`).
3. **Score** C/I/A/R per asset from `references/scales.md`, one reason each, naming the consequence and, where known, a number from the brief ("~4 000 orders/day", "partner contract demands 99.9 %").
4. **Exposure and scope** per asset from the architecture, with the path that makes it reachable.
5. **Questions.** Business values you cannot see (cost of an hour of downtime, which regulator, contract terms) become ❓ with the score you would use if unanswered, marked `provisional`.
6. **Return** the TOML blocks; the orchestrator writes the file, runs the script, and shows the result.

## Output

- `docs/RISK.toml` — source: written by the orchestrator from the assessor's blocks.
- `docs/RISK.md` — generated: summary, asset map (mermaid), register sorted by risk, heat map, reasons, inheritance log, minimum controls per level. Never edited by hand.
- `docs/RISK.json` — generated: for `presenter` (`docs/slides/risks.html`).
- Risk-driven policies (RPO, audit log retention, encryption) go into `docs/POLICY.md` with `Source: RISK <asset id>`.

## Reference files

| File | Covers |
|---|---|
| `references/scales.md` | anchor tables for C, I, A, R on 0–10 with examples per band; exposure and scope details |
| `references/example.md` | a worked map for a small drone-delivery service: assets, scores with reasons, the TOML, and what the script prints |
