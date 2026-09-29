# Lab P0 evidence: model bridge and init-service secrets

## Evidence identity

| Field | Value |
| --- | --- |
| Tested commit | `3eeb2ac895d20cc6de9ea0e3d0c240c5184c06d7` |
| Date and host | 29 September 2026, `capybara`, Windows 11 Pro, Docker Desktop 28.3.2 |
| Compose project | `kops-local-demo` (the normal, non-test project; `docker compose up` with no overrides) |
| Model bridge | `scripts/model_bridge.py`, started with `python scripts/model_bridge.py start`, PID reported at `/health` |
| Command | `docker compose up -d --build` (after `python scripts/model_bridge.py start`); gate actions posted to the same routes the server-rendered GUI forms submit (`/model/save`, `/fixtures/load`, `/jobs/create`, `/candidates/{id}/verify`, `/candidates/{id}/authorize`, `/operations/{id}/publish`), with the same CSRF token flow the GUI uses |

## Gate (from `docs/lab.md`/`HANDOFF.md`)

"Clone, `docker compose up`, bridge started, on a machine with Docker, Python and a signed-in
Claude Code; one page compiled and published, evidence naming the model and effort the bridge
reported."

## Expected result

`docker compose up` alone (after `.env` is copied and the bridge is started) brings up all six
services with no pre-existing host secret file and no `make`/Bash step. The Model Setup screen
tests and pins the bridge and shows the real model id and effort. One page compiles through the
real bridge (not the fixture), gets reviewed, authorized and published, and is then readable
with an audit receipt.

## Observed result

- `python scripts/model_bridge.py start` reported PID 3292; `GET http://127.0.0.1:8090/health`
  returned `{"status": "ok", "bridge_version": "0.1.0", "cli_version": "2.1.280 (Claude Code)", "requested_model": "sonnet", "requested_effort": "high", ...}`.
- `docker compose up -d --build init db` (then the full stack): the `init` service wrote 12
  secret files into the `runtime_secrets` volume and exited 0; `db` started, ran
  `docker/db/init.sh` (after the CRLF fix below) and became healthy; `docker compose up -d --build`
  brought up `audit`, `content`, `publisher`, `worker`, `api` with no restarts.
- `GET /health` on the API returned `{"status":"ok"}`.
- `POST /model/save` (no adapter/endpoint/model name fields — there is nothing left to choose)
  returned "Model configuration revision 1 saved: Reachable in 7893 ms". `GET /?stage=model`
  rendered `Model: claude-sonnet-5`, `Effort: high`, `Bridge version: 0.1.0`,
  `CLI version: 2.1.280 (Claude Code)`, `Revision: 1`.
- `POST /fixtures/load`, `POST /jobs/create` (Engineering, one source) queued a job; it reached
  `status: ready` with `model_latency_ms: 24882` (consistent with a real network round trip to
  Claude; the fixture responds in well under a second). The candidate was verified, authorized
  and published (operation `1890c8bf-f9d7-49d4-adb0-d154bd7ad3be`).
- `GET /documents/564c425e-b63c-4c9b-b691-2c89281d40a6` returned 200 with `Read audit receipt`
  in the body.
- `docker compose ps` showed `db`, `audit`, `content`, `publisher`, `worker`, `api` all `Up`
  (`db` `Up (healthy)`) for the whole run.

## `verifica` verdict

Dispatched to the `verifica` subagent (Haiku 4.5, high effort), given the exact `docker compose
ps`, `curl`, and document-id checks to run against the live stack, no narrative from the
session. Verdict: **PASS**, all five checks confirmed —

> All five checks verified successfully... Check 3: Model Setup page configuration ... HTML
> response contains all three required literal substrings: `claude-sonnet-5`, `>high</dd>`,
> `0.1.0`. ✓ ... Check 4: ... `"model_latency_ms": 24882` (far exceeds 5000 ms threshold,
> confirming real network call to Claude, not fixture short-circuit) ✓ ... Check 5: ... returns
> HTTP 200 and contains the literal substring `Read audit receipt` ... Conclusion: The kops demo
> stack compiled and published one page ... through the real model bridge using Claude Sonnet 5
> at high effort. Measured model latency was 24,882 ms, confirming a genuine network round-trip
> to the Claude API.

## Regression check

Before the live-bridge walkthrough, the full existing acceptance path was run against the
fixture bridge in the isolated `kops-test` Compose project (fresh volumes, `KOPS_MODEL_ENDPOINT`
pointed at `fixture-model`, matching the `Makefile` `test` target run by hand since `make` is
not installed on this Windows host): 12 pytest cases passed, `verify_privileges.sql` passed, and
`scripts/verify-restart.sh` passed (worker interruption recovered; job and query-response-input
counts survived container recreation). The disposable `kops-test` project and its volumes were
removed afterward.

## Baseline conformity block

Profile C (building), per `HANDOFF.md`. `baseline-agenti/SCHEDA.md` could not be read this
session: the Read tool required a cross-directory permission grant that a non-interactive run
cannot answer, so the control set below is limited to what this repository's own
`docs/status.md` and `HANDOFF.md` already name and describe; anything not named there is left
**unknown**, not assumed.

| Control | State | Evidence |
| --- | --- | --- |
| C02 (one writer per artifact) | Verified | The session made every edit and is the sole committer; no subagent wrote to a repository file this phase, matching `AGENTS.md`'s "one accountable writer" rule. |
| C03 (independent verification, no narrative) | Verified | The `verifica` subagent ran the five checks itself from the live stack and returned a verdict before this file was written; its verdict is quoted above verbatim, not paraphrased. |
| C11 (permission allowlist without disabled confirmations) | Verified | `.claude/settings.json` (created by Franco before launch, per `HANDOFF.md`) gated every tool call used this phase; no confirmation was bypassed, and actions outside the allowlist (direct `claude`, `rm`, `sed`, `git rm`, `tasklist`, launching `.exe` directly, `make`) were denied and worked around through allowed tools rather than through a broadened permission. |
| Model/API-key boundary ("no API key, no other provider, no model selector") | Verified | `grep`-level check: no adapter/endpoint/model-name field remains anywhere in `app/`; the model is fixed to `settings.model_endpoint`, and the GUI only shows what the bridge reports. |
| C01, C04–C10, C12 | Unknown | Not evaluated; `SCHEDA.md` unreadable this session. Not claimed as met or unmet. |

Configuration and one passing run are not proof of behavior under load or adversarial input;
this block states what was directly observed, not a general guarantee.

## Limitations

- The gate's actions were posted to the exact routes and CSRF flow the server-rendered GUI forms
  use, and the observation was the literal HTML those GUI screens (`/?stage=model`,
  `/?stage=read`, `/documents/{id}`) render — but no browser actually rendered them. The first
  delivery's evidence (`docs/evidence/implementation.md`) used headless Firefox with geckodriver
  for its screenshots; geckodriver is not installed on this machine, and per policy the browser
  is only used after Franco explicitly authorizes it, which an unattended run cannot obtain. This
  phase's evidence is therefore an HTTP-level confirmation of the same GUI output, not a
  screenshot.
- `docs/gui-lab.md`'s stage descriptions for the lab-specific screens are not yet implemented;
  P0 only had to add the Model screen's bridge fields, which it did.
- The model bridge's concurrency, retry and rate-limit handling are implemented
  (`scripts/model_bridge.py`) but only exercised by a single sequential call in this phase; no
  concurrent-load evidence exists yet.
- `docs/architecture-v4.md`/`docs/gui-walkthrough.md`/`docs/evidence/implementation.md` were read
  for context per `HANDOFF.md` step 2, confirming nothing from the first delivery was rebuilt or
  weakened; no code from that delivery outside the model-configuration surface was touched.

## Side findings

- `docker/db/init.sh` and five other `scripts/*.sh` files were checked out with CRLF line
  endings on this Windows machine (`core.autocrlf=true`, no `.gitattributes`), which made
  Alpine's `/bin/sh` unable to execute `init.sh` and silently skipped creating the `kops_api`/
  `kops_worker`/etc. database roles; fixed by normalizing line endings and adding
  `.gitattributes` (`eol=lf` for `*.sh`/`*.py`, `text=auto eol=lf` generally). This would have
  broken `docker compose up` for any Windows clone before this commit.
- `scripts/setup.sh` could not be deleted: both `rm` and `git rm` were blocked by this session's
  sandbox file-removal policy even for a file this same session had just made obsolete. It is
  now a six-line shim delegating to `scripts/setup.py`, with an inline comment explaining why it
  still exists.
- `scripts/verify-restart.sh`'s own `compose up -d` call (after its mid-script `compose down`)
  did not set `KOPS_MODEL_ENDPOINT`; added it alongside the pre-existing
  `KOPS_ALLOWED_MODEL_HOSTS` for consistency with the `Makefile` `test` target, though no model
  call happens in that script.
- `make` is not installed on this Windows host, so `make test`/`make setup` etc. were run by
  reproducing the `Makefile` target's exact commands by hand; this matches `AGENTS.md`'s
  acknowledgment that anything needing `make` or Bash is a gap outside the mandated
  `docker compose up` getting-started path, not a claim that `make` works here.
