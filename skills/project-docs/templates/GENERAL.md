# GENERAL — <project name>

<!-- For a business analyst, not a programmer.
Use business language: "the manager confirms the order", not "PATCH /orders/{id}".
Technical details only as a link in the "Related" line. -->

## Problem → solution

**Problem:**
> <!-- ONLY in the user's words. No answer → ask, do not invent.
Write their answer almost verbatim; light cleanup is fine. -->
> <problem>

**Solution:**
<!-- 1–3 sentences: what the system does so the problem goes away. -->
<solution>

**How we know it's solved:**
<!-- A measurable result, if the user named one. E.g. "a request is handled in 10 minutes instead of a day". If not named — ❓. -->
- <criterion>

**Out of scope:**
<!-- What we explicitly do NOT do. Saves arguments later. -->
- <...>

---

## Actors and roles

<!-- Everyone who interacts with the system: people, departments, external companies, other systems. -->

| Role | Who it is | What they do in the system |
|---|---|---|
| <Client> | <who> | <what> |

---

## Business processes

<!-- One process = one card. Order: most important first.
"If it goes wrong" is mandatory: that is where the forgotten rules hide. -->

### <Process name>

- **Why:** <which part of the problem it solves>
- **Trigger:** <what starts it: a person's action, time, an event>
- **Actors:** <roles from the table above>
- **Steps:**
  1. <who> <does what>
  2. <...>
- **Result:** <what exists at the end>
- **If it goes wrong:**
  - <situation> → <what happens>
- **Related:** <other processes>; tech → `API.md#<...>`, `ENTITY.md#<...>`

---

## Glossary

<!-- Business terms and their names in code. This is the bridge between GENERAL and ENTITY.
Only words that are actually used and can be understood in different ways. -->

| Term | Meaning in this business | In code |
|---|---|---|
| <Order> | <definition> | `<Order>` |
