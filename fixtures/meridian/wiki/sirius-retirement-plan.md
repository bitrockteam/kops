---
title: Sirius retirement plan
owner: paolo.ricci
space: Product
updated: 2026-09-15
---

# Sirius retirement plan

Sirius stopped taking new bookings on 2026-05-04. Bookings made before that date keep their `S-` PNR
and stay readable through `sirius-bridge` (ADR-008).

- 2026-05-04: NBS live on all routes. Sirius read-only.
- 2026-11-30: last `S-` departure.
- 2027-03-31: `sirius-bridge` switched off; remaining `S-` records archived.

## What Customer Care needs to know
A customer with a PNR starting with `S-` is looked up in the NBS back office with the "legacy" toggle.
Changes to an `S-` booking are not possible; the operator rebooks in NBS and refunds Sirius through
the refund script.
