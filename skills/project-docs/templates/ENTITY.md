# ENTITY — <project name>

<!-- Entities in code: classes, interfaces/traits/protocols, DTOs, enums, services.
One entity = one card. Contract = method NAMES ONLY; descriptions live in METHOD.md (fat methods only).
Skip small helper classes with 1–2 methods.

Card fields:
- Description — why it exists at all, in applied terms, as part of a business process.
- Type — what construct it is, what data it holds, what you can do with it.
- Contract — methods the type promises to have (interface, trait, protocol, abstract class).
- Parent / Children — inheritance and interface implementation.
- Relations — logical links to other entities and why they exist.
- Invariants — what is ALWAYS true for this entity. A broken invariant = a bug. -->

## Cards

### `<Order>`

- **Description:** <a client's order; created when the client checks out the cart → GENERAL.md#<checkout>>
- **Type:** <dataclass / class / aggregate>. Holds <id, client, items, status, total>.
  You can <add an item, change status, compute the total>.
- **Contract:** `<add_item>`, `<cancel>`, `<mark_paid>`, `<total>`
- **Parent:** `<Entity>`
- **Children:** —
- **Relations:**
  - `<OrderItem>` — <owns: an order consists of items>
  - `<User>` — <references: an order has an owner>
  - `<OrderRepo>` — <persisted through it>
- **Invariants:**
  - <total = sum of items>
  - <items of a paid order cannot change>
  - <status changes only along the transition table → DATABASE.md#order_status>

### `<Notifier>`

- **Description:** <notifies the client when the order status changes>
- **Type:** <interface / protocol>. Holds no data, defines behaviour.
- **Contract:** `<send>`
- **Parent:** —
- **Children:** `<EmailNotifier>`, `<TelegramNotifier>`
- **Relations:**
  - `<OrderService>` — <uses it to inform the client>
- **Invariants:**
  - <a failed send does not break the main process>

---

## Trees

### Inheritance and implementation

<!-- Who inherits from whom / who implements which interface. -->

```
<Entity>
├── <Order>
└── <User>

<Notifier>            (interface)
├── <EmailNotifier>
└── <TelegramNotifier>
```

### Usage

<!-- Who uses whom. Entry points on top, dependencies below.
If an entity appears twice, the second time mark it with an asterisk and no subtree: `<OrderRepo> *` -->

```
<OrderController>
└── <OrderService>
    ├── <OrderRepo>
    │   └── <Order>
    ├── <BillingClient>
    └── <Notifier>
```
