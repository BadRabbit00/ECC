# METHOD — <project name>

<!-- Only methods and functions with MORE THAN TWO jobs.
What counts as a job → project-docs skill, section «Jobs» (short: input check, DB read, DB write,
external call, sending an event, data transformation, side effect; logging and return are not jobs;
identical actions in a row are one job).

Purpose: catch bloated methods. Rule → POLICY.md#p-code-method-jobs.
Group by class. Free functions go under a module heading.
If there are no such methods, keep only the summary with the line "No fat methods". -->

## Summary

| Method | Jobs | Verdict |
|---|---|---|
| `<OrderService.create_order>` | <4> | ✂️ Split |
| `<CheckoutFlow.run>` | <5> | ✅ Justified |

---

## `<OrderService>`

### `<create_order(cart, user) -> Order>`

- **Description:** <creates an order from the cart; process step → GENERAL.md#<checkout>>
- **Returns:** `<Order>` — <created order in status `new`>
- **Jobs:**
  1. <checks the cart is not empty and items are in stock>
  2. <writes the order and items to the DB>
  3. <calls billing to create an invoice>
  4. <publishes `order.created`>
- **Verdict:** ✂️ Split — <move 3 and 4 into an `order.created` handler; the method keeps the check and the write>

---

## `<CheckoutFlow>`

### `<run(cart_id) -> CheckoutResult>`

- **Description:** <...>
- **Returns:** `<CheckoutResult>` — <...>
- **Jobs:**
  1. <...>
  2. <...>
  3. <...>
- **Verdict:** ✅ Justified — <orchestrator: each step calls a separate service, no own logic inside>

---

## Module `<utils/export.py>`

### `<export_report(params) -> Path>`

- **Description:** <...>
- **Returns:** <...>
- **Jobs:**
  1. <...>
- **Verdict:** <...>
