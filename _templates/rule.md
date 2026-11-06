---
paths:
  - "**/*.py"
---

<!--
TEMPLATE — copy to badrabbit/rules/<topic>.md, delete every comment.

A path rule loads into ANY session or subagent that touches a file matching `paths:`.
So it must be short and universally true for those files. Budget: ≤ 120 lines.

Put here: conventions every writer of these files needs (layers, naming, ORM-only, config access).
Do NOT put here: review checklists (they belong to the reviewer agent),
long reference tables (they belong to a skill), or anything a hook can enforce.

Defaults that a project may override are marked "(default — project POLICY.md may override)".
-->

# <Topic> rules

## Scope

<!-- One sentence: which files, which situations. -->

## Rules

- R-<AREA>-<NAME>: <rule in one line>
- R-<AREA>-<NAME>: <rule in one line> (default — project POLICY.md may override)

## Examples

### R-<AREA>-<NAME> — <short title>

Bad:
```python
# ...
```
Why: <one line>

Good:
```python
# ...
```
