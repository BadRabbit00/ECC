# PATTERN — <project name>

<!-- "How we usually do it". An OBSERVATION, not a law.
Sources: skills and conversation (new project) or repetition in code and comments (existing project).
Record a pattern if it appears in at least 2–3 places or the user/skill names it directly.
If the user says "this is mandatory" — write a rule in POLICY.md and link to it here.
Delete empty categories. -->

## Code

### <A repository per table>

- **Gist:** <a table is accessed only via its `<XxxRepo>` class; services do not write SQL>
- **Source:** <code / skill `<name>` / conversation>
- **Seen in:** `<services/orders/repo.py>`, `<services/billing/repo.py>`
- **Example:**
  ```python
  order = await self.orders.get(order_id)
  ```
- **Not like this:**
  ```python
  await session.execute(text("SELECT * FROM orders ..."))  # inside a service
  ```
- **Mandatory?** → `POLICY.md#<p-…>` / no

---

## Naming

### <...>

- **Gist:** <plural resource paths: `/orders`, not `/order`; service classes end with `Service`>
- **Source:** <...>
- **Seen in:** <...>
- **Mandatory?** <...>

---

## Logging

### <...>

- **Gist:** <...>
- **Source:** <...>
- **Seen in:** <...>
- **Example:** <...>
- **Mandatory?** <...>

---

## Errors

### <...>

---

## Data access

### <...>

---

## Tests

### <...>

---

## Problem solving

<!-- How the project usually solves typical tasks: "need a background job → put it in the queue, not a thread",
"need a new external API → first a client wrapper in libs/clients". -->

### <...>

- **Situation:** <when it applies>
- **How we solve it:** <...>
- **Source:** <...>
- **Example in code:** `<path>`
