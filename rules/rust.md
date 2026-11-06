---
paths:
  - "**/*.rs"
  - "**/Cargo.toml"
---

# Rust

## Scope

Rust services and libraries (tokio, axum, sqlx/diesel). Layers, DB, and tests have their own rules; this is the language part. `rust-reviewer` checks it in depth.

## Rules

- R-RS-ERRORS: libraries and domain code return typed errors (`thiserror`); `anyhow` only in binaries and top-level glue. Propagate with `?` and context. No `unwrap()` / `expect()` outside tests and startup invariants (with a message that says why it cannot fail).
- R-RS-PANICS: request handlers and workers never panic on input: no slice indexing on untrusted lengths (`get`), no `unwrap` on parsed data, no `unreachable!` for reachable states.
- R-RS-ASYNC: nothing blocking in async code (`std::fs`, `std::thread::sleep`, heavy CPU): use `tokio::fs`, `tokio::time::sleep`, `spawn_blocking`. Never hold a `std::sync::Mutex` guard across `.await`.
- R-RS-OWNERSHIP: take `&str`, `&[T]`, `impl AsRef<…>` in parameters; borrow instead of `clone()`; a `clone()` in a hot loop needs a reason.
- R-RS-TYPES: newtypes for identifiers and validated values (`struct OrderId(Uuid)`); enums for states with data; `match` on your own enums lists every variant (no `_` arm).
- R-RS-UNSAFE: no `unsafe` without a `// SAFETY:` comment proving the invariant, and only where the safe API cannot do it.
- R-RS-LINTS: `cargo clippy --all-targets -- -D warnings` is clean; an `#[allow(...)]` carries a reason (`#[allow(clippy::x, reason = "...")]`).

## Examples

### R-RS-ERRORS — no unwrap on input

Bad:
```rust
async fn get_order(Path(id): Path<String>, State(db): State<Db>) -> Json<Order> {
    let id = Uuid::parse_str(&id).unwrap();
    Json(db.order(id).await.unwrap())
}
```
Why: a malformed id or a DB hiccup panics the task and returns a broken connection instead of 400/404/500.

Good:
```rust
async fn get_order(Path(id): Path<OrderId>, State(svc): State<OrderService>) -> Result<Json<OrderRead>, ApiError> {
    let order = svc.get(id).await?;          // OrderError → ApiError via From
    Ok(Json(order.into()))
}
```

### R-RS-ASYNC — a std mutex across await

Bad:
```rust
let mut cache = state.cache.lock().unwrap();    // std::sync::Mutex
let fresh = fetch(&client, key).await?;         // guard held across await
cache.insert(key, fresh);
```
Why: the guard blocks the executor thread and can deadlock; the future is also not `Send`.

Good:
```rust
let fresh = fetch(&client, key).await?;
state.cache.lock().expect("cache mutex poisoned").insert(key, fresh);   // lock only around the insert
```
