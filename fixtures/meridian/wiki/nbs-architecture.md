---
title: New Booking System: architecture
owner: elena.moretti
space: Platform
updated: 2026-09-13
---

# New Booking System: architecture

NBS replaced Sirius for all four routes in May 2026. It runs in the `nbs` namespace of the
production Kubernetes cluster and is deployed by Argo CD from `main`.

## Components
- `nbs-web`: React single page app, served by nginx, 3 replicas.
- `nbs-api`: Python, FastAPI, 6 replicas, horizontal autoscaling on CPU.
- `nbs-worker`: async jobs: confirmation mail, PNR sync to Vision X manifests, refund batches.
- `nbs-db`: PostgreSQL 16, one primary and one streaming replica, managed by Platform. `pgbouncer`
  in transaction pooling mode sits in front of it (ADR-006).
- `paygate-adapter`: the only component that talks to CardinalPay (ADR-003). Holds the provider
  credentials from the platform vault. Implements authorize, capture, refund and the 3DS callback.
- `sirius-bridge`: read-only lookups of legacy bookings, PNR prefix `S-`, until March 2027 (ADR-008).

## Booking flow
search, quote, hold (10 minutes, BK-409 when expired), pay (authorize then capture), confirm
(PNR issued, mail sent, manifest updated in Vision X).

## Error codes as the customer sees them
- `PAY-431`: 3DS declined by the issuer. Not an outage.
- `PAY-502`: payment provider unreachable. Outage or degradation on the CardinalPay side or in the adapter.
- `BK-409`: hold expired before payment.
- `BK-404`: PNR not found.
- `CHK-001`: check-in window closed.

## Data
Tables `bookings`, `passengers`, `vehicles`, `payments`, `manifests`. `passengers` holds names and
document numbers: personal data, retention 24 months after departure.

## Observability
Grafana dashboards `nbs-overview` and `nbs-payments`. Alerts route to the ops-desk on-call through
the paging tool. Logs are shipped as JSON lines with `request_id`.
