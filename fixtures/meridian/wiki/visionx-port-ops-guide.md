---
title: Vision X: port operations guide
owner: federica.bruni
space: Fleet Operations
updated: 2026-09-05
---

# Vision X: port operations guide

Vision X receives the manifest of every departure from NBS (`nbs-worker`, PNR sync) and shows it to
the gate with vehicle lanes and boarding status.

- A manifest is final 45 minutes before departure. Later bookings appear as "late" and need a gate override.
- A missing vehicle on the manifest usually means the PNR sync failed: check the departure in the
  Vision X "sync" tab; a red clock means NBS did not send the update. Call the ops desk, do not retype the vehicle.
- Boarding delays over 20 minutes are announced by the gate and reported in HelpHub as a P3 so that
  Customer Care can answer the phone with the same information.
