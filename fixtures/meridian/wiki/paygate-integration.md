---
title: PayGate: CardinalPay integration
owner: elena.moretti
space: Platform
updated: 2026-09-22
---

# PayGate: CardinalPay integration

`paygate-adapter` wraps the CardinalPay REST API. Operations: `authorize`, `capture`, `refund`,
`3ds-callback`. Every call carries an idempotency key derived from the booking id and the attempt number.

- Authorize is called at "pay"; capture is called at "confirm". A hold that expires (BK-409) voids
  the authorization.
- CardinalPay returns HTTP 502 when their gateway is saturated. Since ADR-007 the adapter retries
  three times with exponential backoff (200 ms, 800 ms, 3200 ms) when `nbs.paygate.retry` is on.
- 3DS challenges come back through the callback; a declined challenge is `PAY-431`.
- Credentials: sandbox and production API keys live in the platform vault under `paygate/`. They are
  never in the repository, the config maps or this page.
- Webhooks for refunds land on `/webhooks/cardinalpay` and are verified by signature.

Code: `services/paygate_adapter/client.py`, `services/paygate_adapter/retry.py`,
tests in `tests/paygate/test_retry.py`.
