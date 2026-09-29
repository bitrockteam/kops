---
title: Runbook: NBS deploy and rollback
owner: davide.rinaldi
space: Operations
updated: 2026-09-24
---

# Runbook: NBS deploy and rollback

Deploys are blue/green through Argo CD (ADR-004). A deploy is a merge to `main`; Argo syncs within
three minutes and shifts traffic when the new ReplicaSet passes the readiness probe on `/health`.

## Rollback
1. `argocd app history nbs-api` and pick the previous revision.
2. `argocd app rollback nbs-api <id>`.
3. Watch `kubectl -n nbs rollout status deploy/nbs-api`.
4. Post in the ops channel: revision, reason, ticket.

## Freeze windows
No deploys on Fridays after 14:00 and on the day before a peak departure (Genoa-Olbia Friday
evenings in July and August).

## What to check after any deploy
Error rate on `nbs-overview`, p95 latency of `/api/quote`, the `paygate-adapter` authorize success rate.
