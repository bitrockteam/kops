---
title: Post-mortem: NBS checkout outage, 12 September 2026
owner: davide.rinaldi
space: Operations
updated: 2026-09-17
---

# Post-mortem: NBS checkout outage, 12 September 2026

## Summary
From 14:09 to 14:41 CEST every payment attempt on NBS failed with `PAY-502`. 1,214 holds expired
without payment. 63 HelpHub tickets. No data lost.

## Timeline (CEST)
- 14:09 CardinalPay authorize endpoint starts returning HTTP 502 for 40% of calls.
- 14:12 `nbs-payments` alert, on-call (Sara Conti) acknowledges.
- 14:15 Adapter restart, no effect. CardinalPay status page green.
- 14:23 Retry flag `nbs.paygate.retry` enabled: error rate drops to 18%.
- 14:31 Deferred checkout enabled; Customer Care lead informed; L1 script sent to the floor.
- 14:41 CardinalPay recovers. Flags left on until 16:00, then reset.

## Root cause
Capacity incident on the CardinalPay side, confirmed by their report on 15 September. The retry
flag was off by default (ADR-007 shipped it opt-in).

## Actions
- Retry on by default from release 2026.38 (commit `nbs-api: enable paygate retry by default`).
- Customer Care keeps the deferred checkout script pinned in HelpHub.
- Ask CardinalPay for the service credit under the SLA.
