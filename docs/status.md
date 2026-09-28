# Project status

## Implemented

- FastAPI component API and server-rendered guided GUI for all ten stages.
- PostgreSQL lifecycle, policy, provenance, job, review, authorization, operation, publication and audit records.
- Mock identity with server-issued signed sessions and stable synthetic personas; client-supplied roles are not accepted.
- Engineering, Finance and Engineering AND Finance audiences with bounded conjunction semantics.
- Immutable source, candidate, published-page and answer content volumes behind an adapter.
- Separate API, admitted-content broker, restricted worker, bounded publisher and protected audit collector processes and database roles.
- Operator-selected Ollama and local OpenAI-compatible model adapters with local destination validation, redirect refusal, finite limits and pinned job configuration.
- Exact-candidate verification, expiring effect authorization, expected-version publication, idempotency, audit outbox and uncertain-result reconciliation.
- Authorized catalog, current and historical reads, questions, answer promotion, source revision maintenance, membership revocation and source-policy invalidation.
- Admin-only controls for stale approval, conflicting versions, duplicate publication, audit outage, mid-job policy change and cancellation.
- Confirmed setup, up, down, reset, test, logs, backup and restore commands.
- Pull-request acceptance workflow and `main` protection requiring its check and independent approval.
- Actual Firefox screenshots of publication, authorized and revoked catalogs, access administration, audit, and a denied direct read.
- Post-review hardening: PostgreSQL 18 mount and upgrade preflight, complete query input manifests, current dependency checks on candidate/page/answer/catalog delivery, audience-scoped audit views, bounded streaming model responses, serialized publication, and interrupted-worker recovery.

## Validation observed on 28 September 2026

- `make setup`: passed after Docker was started; no model or identity server was installed.
- `make test` on the hardened worktree: 12 tests passed from fresh isolated volumes, followed by PostgreSQL privilege assertions, worker-interruption recovery, and successful PostgreSQL job and query-manifest reads after container recreation. The exact tested commit is recorded in the implementation evidence report after commit.
- Full deterministic HTTP path: Engineering and joint compilation, review, authorization, atomic publication, idempotent replay, query, saved-answer candidate, maintenance staleness, membership revocation and audit outage recovery passed.
- `make up`: all six normal services started; `GET /health` and the GUI returned successfully on `127.0.0.1:8080`.
- `make backup` and confirmed `make restore`: all archive checksums passed; seven personas and one run were recovered; the API became healthy.
- `make down` and confirmed `make demo-reset`: normal processes stopped and only `kops-local-demo` volumes were removed.
- GitHub Actions `kops-test` passed on application commit `30ccfb0`; pull request 1 is blocked pending review as required by `main` protection.
- Headless Firefox captured six actual GUI views from a disposable fixture-backed stack at `30ccfb0`; that stack and its synthetic volumes were removed after capture.
- The PostgreSQL upgrade preflight refused a deliberately created empty named volume, instead of initializing a replacement database. The empty probe volume was removed immediately. This is not a migration test of real prior data.

The deterministic inference service is a test double and does not satisfy live-model acceptance. No local Ollama, llama.cpp server or LM Studio endpoint was available on this machine, so live compilation, live questions and model-quality assessment remain unverified.

## Baseline status

Implementation and repeatable evidence verify covered local-demo behavior for C01, C02, C04, C06, C10, C11 and C12. C05 product separation is tested, while its shared-branch gate remains partial until independent human approval. C03 is partial for the same review gap. C07-C09 are partial because identity is mocked and the trusted local administrator remains outside the container boundary. MCP/A2A-specific C08 requirements are not applicable because those adapters are absent; mock session recipient checks and per-service internal tokens are implemented. Configuration and source review are not substitutes for runtime fault evidence. No enterprise or production assurance is claimed.

## Next action

Run a user-selected local model through Model Setup, complete the live-model quality set, and obtain independent pull request review. Do not merge automatically.
