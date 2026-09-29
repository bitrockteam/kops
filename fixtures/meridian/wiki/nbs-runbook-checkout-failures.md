---
title: Runbook: NBS checkout failures
owner: sara.conti
space: Operations
updated: 2026-09-17
---

# Runbook: NBS checkout failures

## Symptoms
Customers report "payment failed" at the last step. HelpHub tickets mention `PAY-502` or `PAY-431`.
The `nbs-payments` dashboard shows authorize error rate above 5%.

## Triage
1. Adapter health: `kubectl -n nbs get pods -l app=paygate-adapter` and
   `kubectl -n nbs logs deploy/paygate-adapter --since=15m | grep upstream`.
2. CardinalPay status page. If they declare an incident, go to step 4.
3. If `PAY-502` stays above 5% for 10 minutes and CardinalPay is green: set the config map key
   `nbs.paygate.retry=true` (ADR-007) and restart the adapter: `kubectl -n nbs rollout restart deploy/paygate-adapter`.
4. If CardinalPay is down: enable deferred checkout, `nbs.checkout.deferred=true` (ADR-005). Customers
   get a 24 hour hold and a payment link by mail. Tell the Customer Care lead so that L1 gets the script.
5. `PAY-431` is never an outage: the issuer declined 3DS. The customer retries with another card. Do not escalate.

## Escalation
On-call L3 if two adapter restarts do not clear the error rate within 15 minutes.

## Afterwards
Open a post-mortem page, link the HelpHub tickets, reset the two flags to `false`.
