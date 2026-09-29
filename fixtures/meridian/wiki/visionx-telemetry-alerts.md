---
title: Vision X: telemetry alerts
owner: federica.bruni
space: Fleet Operations
updated: 2026-09-14
---

# Vision X: telemetry alerts

Vessels send position, speed and engine status every 30 seconds. Vision X raises:

- `TEL-STALE`: no telemetry for 5 minutes. Usually the satellite link; the vessel calls the port on VHF.
- `TEL-ETA`: ETA drifts more than 30 minutes. Port operations re-plan the berth and the gate.
- `TEL-ENG`: engine status warning. Fleet management only; not for Customer Care.

Dashboard `visionx-fleet`, alert route: fleet-ops pager, copy to the ops desk for `TEL-STALE`.
