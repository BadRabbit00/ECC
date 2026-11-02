# Worked example: SkyDrop, drone delivery

A small service: customers order in a mobile app, operators dispatch drones, a bank partner takes payments. Two processes, four data groups. Use it to calibrate scores, not to copy them.

## What the assessor read

- `docs/GENERAL.md`: processes "Order placement" and "Flight dispatch"; operating hours 08:00–22:00; ~4 000 orders a day.
- `docs/SPECIFICATION.md`: `svc-orders`, `svc-dispatch`, PostgreSQL `orders_db` and `flight_db`, JWT signing key and bank API key in sops; operators log in with 2FA.
- `docs/DATABASE.md`: `customers`, `addresses`, `orders`, `flight_plans`, `geofences`.

## Decisions worth noting

- `customers` + `addresses` are one asset (D-01): they score the same.
- Keys are one secret asset (D-04). As a secret it does not push C 10 up into every process that reads it.
- P-01 has C 3 on its own: the process handles personal data but the leak cost is scored on D-01; the script raises P-01 to C 8.
- D-02 gets A 9 from P-02 (dispatch reads orders). If dispatch could fly from a cached copy for an hour, the link would say `need = { A = 6 }`.
- Nothing about vulnerabilities: "the admin panel has no rate limit" is not here.

## docs/RISK.toml

```toml
[project]
name = "SkyDrop — drone delivery"

[[process]]
id = "P-01"
name = "Order placement"
owner = "svc-orders"
scope = "all"
C = 3
I = 6
A = 6
R = 2
exposure = 7
exposure_why = "customers in the mobile app after login; payment page of the bank partner"
sources = ["docs/GENERAL.md#order-placement"]
uses = [{ data = "D-01", access = "rw" }, { data = "D-02", access = "rw" }, { data = "D-04", access = "r" }]
[process.why]
C = "handles customer contacts and the order; the data itself is scored on D-01"
I = "a wrong address or item means a failed delivery and a refund"
A = "no orders while it is down; customers switch to couriers after ~1 h"
R = "consumer protection rules on order confirmation"

[[process]]
id = "P-02"
name = "Flight dispatch"
owner = "svc-dispatch"
scope = "all"
C = 2
I = 10
A = 9
R = 7
exposure = 4
exposure_why = "operators over the internet with 2FA; drones over the operator's LTE link"
sources = ["docs/GENERAL.md#flight-dispatch"]
uses = [{ data = "D-03", access = "rw" }, { data = "D-02", access = "r" }, { data = "D-04", access = "r" }]
[process.why]
C = "routes are internal but not secret on their own"
I = "a tampered route or geofence can put a drone over a crowd or an airport zone"
A = "drones in flight need reroutes; no downtime allowed in operating hours"
R = "drone-operation rules of the aviation authority require flight records and geofencing"

[[data]]
id = "D-01"
name = "Customer personal data"
kind = "data"
stores = ["orders_db.customers", "orders_db.addresses"]
volume = "~40 000 customers"
scope = "all"
C = 8
I = 5
A = 4
R = 6
exposure = 7
exposure_why = "read by the app after login and copied into the bank partner's payment page"
sources = ["docs/DATABASE.md#customers"]
[data.why]
C = "names, phones, home addresses of all customers; a leak means notification under the personal data law"
I = "a wrong address sends the drone to the wrong place; fixed by support"
A = "orders can still be read from cache for a while"
R = "Law of RK on personal data: consent, storage in-country, breach notification"

[[data]]
id = "D-02"
name = "Orders"
kind = "data"
stores = ["orders_db.orders"]
volume = "~1 500 orders/day"
scope = "several"
C = 4
I = 6
A = 5
R = 3
exposure = 6
exposure_why = "customers see their own orders after login; operators see all"
sources = ["docs/DATABASE.md#orders"]
[data.why]
C = "order history shows habits but holds no addresses (those are D-01)"
I = "wrong status leads to double delivery or a refund dispute"
A = "status pages stop; operations continue from dispatch"
R = "B2B SLA with two shops on delivery reporting"

[[data]]
id = "D-03"
name = "Flight plans and geofences"
kind = "data"
stores = ["dispatch_db.flight_plans", "dispatch_db.geofences"]
volume = "~300 flights/day"
scope = "several"
C = 3
I = 9
A = 7
R = 7
exposure = 3
exposure_why = "operators inside the dispatch console behind VPN; drones pull plans over mTLS"
sources = ["docs/DATABASE.md#flight_plans"]
[data.why]
C = "routes reveal depots and delivery times"
I = "a changed geofence lets a drone enter a no-fly zone"
A = "new flights cannot start without plans"
R = "flight records must be kept and shown to the aviation authority"

[[data]]
id = "D-04"
name = "Signing and provider keys"
kind = "secret"
stores = ["sops: secrets/prod.yaml"]
volume = "6 keys"
scope = "all"
C = 10
I = 8
A = 6
R = 5
exposure = 2
exposure_why = "only the auth and dispatch services read them at start-up; decrypted by sops-nix on the host"
sources = ["docs/SPECIFICATION.md#secrets"]
[data.why]
C = "the JWT signing key lets anyone act as any user or operator"
I = "a swapped key breaks every login or lets an attacker sign tokens"
A = "services cannot start without them"
R = "bank partner requires key rotation and access logs"
```

## What the script prints

```text
$ ~/.claude/br/bin/br-risk docs/RISK.toml
risk_score: 6 assets → docs/RISK.md and docs/RISK.json
  P-01 Order placement: M 10.0 × E 7 → risk 7.0 (high)
  D-01 Customer personal data: M 10.0 × E 7 → risk 7.0 (high)
  D-02 Orders: M 10.0 × E 6 → risk 6.0 (high)
  P-02 Flight dispatch: M 10.0 × E 4 → risk 4.0 (medium)
  D-03 Flight plans and geofences: M 10.0 × E 3 → risk 3.0 (low)
  D-04 Signing and provider keys: M 10.0 × E 2 → risk 2.0 (low)
```

## Register from docs/RISK.md

| Asset | Type | C | I | A | R | Scope | Magnitude | Exposure | Risk | Level |
|---|---|---|---|---|---|---|---|---|---|---|
| D-01 Customer personal data | data | 8 | 6↑ | 6↑ | 6 | all | 10.0 | 7 | **7.0** | high |
| P-01 Order placement | process | 8↑ | 6 | 6 | 6↑ | all | 10.0 | 7 | **7.0** | high |
| D-02 Orders | data | 4 | 6 | 9↑ | 3 | several | 10.0 | 6 | **6.0** | high |
| P-02 Flight dispatch | process | 4↑ | 10 | 9 | 7 | all | 10.0 | 4 | **4.0** | medium |
| D-03 Flight plans and geofences | data | 3 | 10↑ | 9↑ | 7 | several | 10.0 | 3 | **3.0** | low |
| D-04 Signing and provider keys | data | 10 | 8 | 9↑ | 5 | all | 10.0 | 2 | **2.0** | low |

↑ = raised by inheritance (see below).

## Inheritance log

- P-01: C 3 → 8 from D-01 (Customer personal data)
- P-01: R 2 → 6 from D-01 (Customer personal data)
- P-02: C 2 → 3 from D-03 (Flight plans and geofences)
- P-02: C 3 → 4 from D-02 (Orders)
- D-01: I 5 → 6 from P-01 (Order placement)
- D-01: A 4 → 6 from P-01 (Order placement)
- D-02: A 5 → 6 from P-01 (Order placement)
- D-02: A 6 → 9 from P-02 (Flight dispatch)
- D-03: I 9 → 10 from P-02 (Flight dispatch)
- D-03: A 7 → 9 from P-02 (Flight dispatch)
- D-04: A 6 → 9 from P-02 (Flight dispatch)

## Reading it

- Every magnitude is 10: each asset has one axis at 9–10, or 8 with a wide scope. With these coefficients magnitude saturates on a high-stakes project, and the ranking comes from exposure. That is expected; tuning `[model]` is the user's call.
- D-03 and D-04 are the worst things that can happen (a tampered geofence, leaked keys) but sit low because they are hard to reach. They stay critical for the reviewers anyway: `security-reviewer` grades a finding by the asset's magnitude, so a finding that opens D-03 to the internet is graded as critical.
