---
title: Runbook: nbs-db connection exhaustion
owner: davide.rinaldi
space: Operations
updated: 2026-09-10
---

# Runbook: nbs-db connection exhaustion

## Symptoms
`nbs-api` returns 500 on `/api/hold`; logs of `nbs-db` show
`FATAL: remaining connection slots are reserved for non-replication superuser connections`.

## Cause seen so far
A worker deploy with the pool size raised, or a long refund batch holding transactions open.

## Steps
1. `kubectl -n nbs exec deploy/pgbouncer -- psql -p 6432 pgbouncer -c "SHOW POOLS"`.
2. If `cl_waiting` grows: `SHOW SERVERS`, find the client with the oldest `connect_time`.
3. If it is `nbs-worker` refund batch: pause it with `nbs.worker.refunds.paused=true`, let the
   batch resume after the pool drains.
4. Never raise `max_connections` on the primary during an incident.

## Escalation
L3 if `cl_waiting` does not drop within 10 minutes.
