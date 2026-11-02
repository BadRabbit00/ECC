# Scales (0–10)

Pick the band whose consequence matches, then the number inside it: the lower number when the consequence is limited to some records, a short time, or one customer group; the higher when it is all of them. Write the reason as the consequence, not the band name.

Consequence kinds, in every axis: **money** (revenue, fines, refunds, compensation), **law and contracts**, **reputation and customers**, **operations** (people or machines stop working).

## C — confidentiality (it leaks)

| Band | Consequence | Typical assets |
|---|---|---|
| 0 | none: already public | catalog, prices on the site, public docs |
| 1–2 | awkward, no harm | internal reference lists, non-sensitive settings, aggregated statistics |
| 3–4 | noticeable harm to the business: competitors learn something, small loss | supplier prices, internal reports, order history without personal data |
| 5–6 | harm to people or real money: personal data of a limited group, business secrets | employee contacts, B2B contract terms, contact data of some customers |
| 7–8 | serious: personal data of many customers, data that enables fraud, regulator involved | customer personal data, addresses with delivery times, ID document scans, routes and schedules |
| 9–10 | threatens the business: payment data, credentials, keys that open everything | card or bank data, password hashes + emails, JWT signing keys, provider API keys, encryption keys |

## I — integrity (it is wrong, tampered with, or silently lost)

| Band | Consequence | Typical assets |
|---|---|---|
| 0 | none: regenerated or not relied on | caches, derived views |
| 1–2 | cosmetic, fixed by hand | UI texts, preferences |
| 3–4 | rework, small money, annoyed customers | catalog descriptions, reports for internal use |
| 5–6 | wrong business decisions, refunds, disputes | stock levels, order statuses, CRM pipeline |
| 7–8 | direct money loss or harm: wrong payouts, wrong prices charged, wrong delivery target | balances, prices, payout amounts, delivery coordinates, access rights |
| 9–10 | physical danger or unbounded loss; cannot be detected or reversed | flight plans and geofences, safety parameters, ledger entries, signing keys |

## A — availability (it is not there)

Tie it to the tolerable downtime the business states; ask when unknown.

| Band | Tolerable downtime | Consequence |
|---|---|---|
| 0 | not needed | nothing waits on it |
| 1–2 | days | someone waits, no money lost |
| 3–4 | about a day | work is delayed, small loss |
| 5–6 | hours | customers notice, orders or work stop for a while |
| 7–8 | under an hour | revenue stops, SLA or partner penalties |
| 9–10 | minutes or none | safety or the whole business stops: live operations, payments, dispatch, flight control |

## R — compliance (a law, regulator, partner or contract is broken)

Score what applies **to this asset** if it fails on C, I or A. Name the source in the reason; when unsure, ask (❓) and mark `provisional`.

| Band | Consequence | Examples |
|---|---|---|
| 0 | no obligations | public data, internal tools |
| 1–2 | internal policy only | company rules, internal SLA |
| 3–4 | contract terms with penalties | B2B SLA, NDA with a client |
| 5–6 | law with notification or fines; partner audit | personal data of employees or customers under the Law of the Republic of Kazakhstan "On personal data and its protection"; consumer protection |
| 7–8 | regulator inspection, licence conditions, bank-partner requirements | payment flows with a bank partner, data that must stay in-country, aviation or drone-operation rules |
| 9–10 | licence loss, criminal liability, or a regulator can stop the business | regulated payment data, critical-infrastructure rules, flight-safety records required by the aviation authority |

## Exposure (0–10)

How reachable the asset is through the architecture as designed. Not vulnerabilities.

| Exposure | Reachable by | Raise by 1 when |
|---|---|---|
| 0–1 | nothing outside its service | — |
| 2–3 | staff inside the network or VPN, after login | many staff roles can read it |
| 4–5 | staff over the internet with 2FA; trusted partner over mTLS | an admin panel is internet-facing |
| 6–7 | customers after login; a third party processes or holds it | it is in exports, emails, or messengers |
| 8–9 | anyone on the internet without login; public forms and webhooks | inputs from it reach other assets |
| 10 | public by design, or copied to parties outside our control | — |

## Scope

| Scope | Meaning |
|---|---|
| `one` | one process, or a small share of records / customers |
| `several` | several processes, or a large share of customers |
| `all` | the whole business stands on it, or every customer is in it |

## Bad and good reasons

Bad:
```toml
C = 8
why = { C = "sensitive data" }
```
Why: no consequence, no group, nothing to check.

Good:
```toml
C = 8
why = { C = "names, phones and home addresses of ~40 000 customers; a leak means notifying them under the personal data law and losing B2C trust" }
```

Bad:
```toml
A = 9
why = { A = "the service has no health check and can go down" }
```
Why: that is a weakness (exposure / later review), not the consequence of downtime.

Good:
```toml
A = 9
why = { A = "dispatch stops: drones in flight cannot get reroutes; the brief allows no downtime during operating hours" }
```
