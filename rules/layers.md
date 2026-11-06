---
paths:
  - "src/*/app/**"
  - "src/*/internal/**"
  - "src/*/cmd/**"
  - "src/*/src/**"
  - "src/*/lib/**"
---

# Layering and naming

## Scope

Application code of any service or module under `src/<component>/`. Frontend structure is covered in `design.md` and the React rules.

## Rules

- R-LAYER-DIRECTION: dependencies go one way, router/handler → service → repository → model. `core` (config, db, logging) and `domain` (enums, domain errors, pure rules) may be used by every layer. A lower layer never imports a higher one.
- R-LAYER-ROUTER: a router/handler parses the request, checks the role through a dependency or middleware, calls a service, and returns the response. No SQL, no `commit`, no business conditions.
- R-LAYER-SERVICE: a service holds the rules and the transaction (one scenario = one commit). It never imports the web framework and never raises `HTTPException`; it raises domain errors.
- R-LAYER-REPO: a repository runs ORM queries only: no `commit`, no HTTP errors, no business decisions.
- R-LAYER-NAMING: files bound to an entity are named `<entity>_<layer>` (`order_service.py`, `order_handler.go`, `order_repository.rs`); infrastructure files are named by content (`config.py`, `database.py`). `utils`, `helpers`, `common`, `misc` are forbidden. In Go, never end a file name with `_test`, `_<GOOS>` or `_<GOARCH>`.
- R-LAYER-CLASSES: ORM model = bare entity (`Order`); schemas `OrderCreate/OrderRead/OrderUpdate`; other layers use full words (`OrderRepository`, `OrderService`, `PaymentClient`). No `OrderSchema`, `OrderModel`, `OrderRepo`.
- R-LAYER-CONFIG: one config module reads env (`core/config.py`, `internal/config`); nothing else calls `os.getenv` / `os.Getenv` / `std::env::var`. Variables carry a service prefix (`ORDERS_DATABASE_URL`).
- R-LAYER-ERRORS: domain errors become HTTP responses in one place (`api/errors.py`, error middleware). One format: `{"detail", "code"}`.
- R-LAYER-NO-FANATISM: a layer exists when it has work to do. No pass-through layers, no `BaseRepository[T]` for two CRUD calls, no interface with a single implementation unless it is a boundary that tests must fake.
- R-LAYER-SERVICES-ISOLATED: a service never imports another service's code and never connects to another service's DB. Use its API or events.

## Examples

### R-LAYER-ROUTER — HTTP only in the router

Bad:
```python
@router.post("/orders")
async def create_order(body: OrderCreate, session: SessionDep) -> OrderRead:
    if await session.scalar(select(exists().where(Order.number == body.number))):
        raise HTTPException(409, "exists")
    order = Order(**body.model_dump())
    session.add(order)
    await session.commit()
    return OrderRead.model_validate(order)
```
Why: the rule cannot be reused from a worker or CLI, and it can only be tested through HTTP.

Good:
```python
@router.post("", response_model=OrderRead, status_code=201)
async def create_order(body: OrderCreate, user: ManagerDep, service: OrderServiceDep) -> OrderRead:
    return OrderRead.model_validate(await service.create(body, actor_id=user.id))
```

### R-LAYER-SERVICE — domain errors, not HTTP

Bad:
```python
class OrderService:
    async def cancel(self, order_id: UUID) -> None:
        order = await self.orders.get(order_id)
        if order.status == OrderStatus.PAID:
            raise HTTPException(status_code=409, detail="paid")
```
Why: the service now depends on FastAPI; a Celery task calling it gets an HTTP exception.

Good:
```python
class OrderService:
    async def cancel(self, order_id: UUID) -> None:
        order = await self.orders.get(order_id)
        if order.status == OrderStatus.PAID:
            raise OrderAlreadyPaid(order_id)        # ConflictError subclass, mapped to 409 in api/errors.py
        order.status = OrderStatus.CANCELLED
        await self.session.commit()
```

### R-LAYER-CONFIG — one config module

Bad:
```go
func NewPaymentClient() *PaymentClient {
    return &PaymentClient{url: os.Getenv("PAYMENT_URL")}   // empty string at runtime if unset
}
```
Why: a missing variable surfaces as a failed request in production, not as a startup error.

Good:
```go
// internal/config/config.go
type Config struct {
    PaymentURL string `env:"ORDERS_PAYMENT_URL,required"`
}
func Load() (Config, error) { var c Config; return c, env.Parse(&c) }   // fails at startup

// cmd/api/main.go
cfg := must(config.Load())
payments := client.NewPaymentClient(cfg.PaymentURL)
```

### R-LAYER-NO-FANATISM — no layers without work

Bad:
```python
class OrderManager:
    def __init__(self, service: OrderService) -> None:
        self.service = service
    async def get(self, order_id: UUID) -> Order:
        return await self.service.get(order_id)   # adds nothing
```
Why: one more hop to read and change, and no logic in it.

Good:
```python
# the router calls OrderService directly; a new layer appears only when it carries a rule
```
