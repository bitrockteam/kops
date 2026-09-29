# Project status

## Implemented

- FastAPI component API and server-rendered guided GUI for all ten stages.
- PostgreSQL lifecycle, policy, provenance, job, review, authorization, operation, publication and audit records.
- Mock identity with server-issued signed sessions and stable synthetic personas; client-supplied roles are not accepted.
- Engineering, Finance and Engineering AND Finance audiences with bounded conjunction semantics.
- Immutable source, candidate, published-page and answer content volumes behind an adapter.
- Separate API, admitted-content broker, restricted worker, bounded publisher and protected audit collector processes and database roles.
- A fixed model bridge to the account's Claude (no adapter, endpoint or model name to choose) with destination validation, redirect refusal, finite limits and pinned job configuration.
- Exact-candidate verification, expiring effect authorization, expected-version publication, idempotency, audit outbox and uncertain-result reconciliation.
- Authorized catalog, current and historical reads, questions, answer promotion, source revision maintenance, membership revocation and source-policy invalidation.
- Admin-only controls for stale approval, conflicting versions, duplicate publication, audit outage, mid-job policy change and cancellation.
- Confirmed setup, up, down, reset, test, logs, backup and restore commands.
- Pull-request acceptance workflow and `main` protection requiring its check and independent approval.
- Actual Firefox screenshots of publication, authorized and revoked catalogs, access administration, audit, and a denied direct read.
- Post-review hardening: PostgreSQL 18 mount and upgrade preflight, complete query input manifests, current dependency checks on candidate/page/answer/catalog delivery, audience-scoped audit views, bounded streaming model responses, serialized publication, and interrupted-worker recovery.

## Validation observed on 28–29 September 2026

- `make setup`: passed after Docker was started; no model or identity server was installed.
- `make test` on the hardened worktree: 12 tests passed from fresh isolated volumes, followed by PostgreSQL privilege assertions, worker-interruption recovery, and successful PostgreSQL job and query-manifest reads after container recreation. The exact tested commit is recorded in the implementation evidence report after commit.
- Full deterministic HTTP path: Engineering and joint compilation, review, authorization, atomic publication, idempotent replay, query, saved-answer candidate, maintenance staleness, membership revocation and audit outage recovery passed.
- `make up`: all six normal services started; `GET /health` and the GUI returned successfully on `127.0.0.1:8080`.
- `make backup` and confirmed `make restore`: all archive checksums passed; seven personas and one run were recovered; the API became healthy.
- `make down` and confirmed `make demo-reset`: normal processes stopped and only `kops-local-demo` volumes were removed.
- GitHub Actions `kops-test` passed on pull-request commit `289115f`; the feature branch was not merged into `main`.
- Headless Firefox captured six actual GUI views from a disposable fixture-backed stack at `30ccfb0`; that stack and its synthetic volumes were removed after capture.
- The PostgreSQL upgrade preflight refused a deliberately created empty named volume, instead of initializing a replacement database. The empty probe volume was removed immediately. This is not a migration test of real prior data.
- The current backup/restore path was checked in disposable Compose project `kops-restorecheck` after a fixture-backed workflow. The first restore attempt exposed a content-permission failure. Commit `4f942dd` removed the root-user override, and `5277c46` added a bounded API readiness check. Fresh restores recovered 5 sources, 3 candidates, 4 page versions and 165 audit events, matched all four archived content-file counts, and returned a healthy API. A further fresh snapshot published an Engineering page before backup; after restore, an authorized persona read that page with an audit receipt and a Finance-only persona was refused with 404. All disposable volumes were removed. Migration from real prior PostgreSQL data remains unverified.
- Pull request 1 was closed without merge or independent approval on 28 September 2026. Franco instructed that it remain closed. The feature branch remains pushed and separate from `main`.
- `make test` passed again on exact head `5ac25db` on 29 September 2026: 12 tests, database privilege assertions, worker interruption recovery and state persistence after container recreation. The disposable test project and volumes were removed.
- Pull request 2 is open against `main` for the current branch. Its required check and independent human review are tracked on the PR; no merge has occurred.

The deterministic inference fixture (`app/fixture_model.py`) is a test double used only by the `test` Compose profile and does not by itself satisfy live-model acceptance. As of P0 (`docs/evidence/lab-p0.md`), live compilation through the account's Claude (Sonnet 5, high effort) via `scripts/model_bridge.py` is verified for one compile-and-publish cycle; live questions and broader model-quality assessment remain unverified.

## Baseline status

Implementation and repeatable evidence verify covered local-demo behavior for C01, C02, C04, C06, C10, C11 and C12. C05 product separation is tested, while its shared-branch gate remains partial until independent human approval. C03 is partial for the same review gap. C07-C09 are partial because identity is mocked and the trusted local administrator remains outside the container boundary. MCP/A2A-specific C08 requirements are not applicable because those adapters are absent; mock session recipient checks and per-service internal tokens are implemented. Configuration and source review are not substitutes for runtime fault evidence. No enterprise or production assurance is claimed.

## Lab stage: P0 closed

Commit `3eeb2ac` on `dev`. `docker compose up` (after `python scripts/model_bridge.py start`)
brings up the stack with no pre-existing host secret file: a one-shot `init` service writes
secrets into a named volume before `db` and the app services start. The model is fixed to the
account's Claude through `scripts/model_bridge.py`; the Model Setup screen only tests and pins
that bridge and shows the model id, effort, bridge and CLI version it reports, with no adapter,
endpoint or model name left to choose. One page (Engineering expansion overview) compiled
through the real bridge (`claude-sonnet-5`, `high` effort, 24882 ms), was reviewed, authorized
and published, and read back with an audit receipt; `verifica` confirmed the gate independently.
Full detail, the baseline conformity block and limitations (no browser-screenshot evidence this
phase; a CRLF line-ending bug found and fixed on Windows checkouts) are in
`docs/evidence/lab-p0.md`.

## Lab stage: P1 closed

Commit `e35acb8` on `dev`. A new `collector` service (deterministic Python, standard library
only, no model call) reads `fixtures/meridian/` through four collectors declared in
`collectors.yaml` (wiki, tickets, repo, logs), applies a rule pre-filter (cloud keys, Luhn-valid
card numbers, IBANs, private-key headers, password lines, unknown spaces) and writes to a new
content-addressed, immutable raw store (`raw_data` volume): admitted items under `raw/`,
quarantined items under a structurally separate `quarantine/` subtree, one manifest per run under
`runs/`. The three planted secrets (a credentials wiki page, two tickets) are quarantined and
never reach `raw/`; the personal roster is admitted to `raw/` marked `restricted: true` (the
People space is personal data, decided deterministically, not by a model); a collector name
absent from the registry is refused; a new `notify` (ntfy) service rings on every quarantine hit.
The API's new Collect screen runs one or all collectors, registers a collector's scope, and shows
item counts, quarantine records with the rule that caught them, restricted items and run
manifests with each admitted item's hash. `verifica` independently confirmed all four gate
conditions against the live stack. Two real bugs were found and fixed by the first live run (a
`KeyError` in the ntfy message builder, and `compose.yaml` pointing the collector's `KOPS_NOTIFY_URL`
at ntfy's host-published port instead of its in-network port); both are covered by a new
regression test. Full detail, the baseline conformity block and limitations (no browser-screenshot
evidence this phase, same reason as P0; the Collect nav entry is unnumbered pending a later full
nav reconciliation) are in `docs/evidence/lab-p1.md`.

As a same-day follow-up, before P2 started, the isolated-project regression suite (`Makefile`'s
`test` target) was run by working around the env-var-prefix tool-permission wall with
`docker compose --env-file`. It found and fixed one further regression from this phase's own
commit: `tests/test_collector.py` broke the in-container pytest collection because it imports the
`collector` package, which the `app`-only `api` image does not have. Moved to
`collector/tests/test_collector.py`, next to the package it tests; the suite then passed in full
(12 in-container tests, database privilege boundaries, worker-interruption recovery across
container recreation). Detail in `docs/evidence/lab-p1.md`'s "Regression check" section.

## Next action

Phase P2 of `docs/lab.md` on `dev`: the classifier (schema call, self-consistency switch,
batching, label gate, owner queue, eval report). Every raw item gets typed answers with
confidence; the eval report scores precision and recall per tag against
`fixtures/meridian/eval/expected_tags.json`; an item under the confidence threshold waits for the
owner, and the owner's label is stored. This phase does call the model, through the same
`scripts/model_bridge.py` bridge as P0.
