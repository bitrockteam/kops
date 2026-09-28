# Local demo implementation evidence

## Evidence identity

| Field | Value |
| --- | --- |
| Tested implementation commit | `1b79f82c67b36a261bfebf6683a905653de07a7b` |
| Date and host | 28 September 2026, `voloire-XPS`, Ubuntu 26.04 LTS |
| Automated configuration | Docker Compose project `kops-test`, Python 3.13 runtime image, PostgreSQL 18.0 Alpine, fresh disposable volumes |
| Identity boundary | Labeled mock identity with signed server-issued sessions and seven synthetic personas |
| Inference boundary | Labeled test-only deterministic local HTTP fixture; it is not a live-model result or runtime fallback |
| External services | None |

## Reproducible checks

| Check | Observed result |
| --- | --- |
| `make setup` | Passed; validated Docker and Compose and prepared ignored per-service secrets without installing a model or identity provider. |
| `make test` at the tested commit | Passed: 10 tests in 9.75 seconds, followed by `database privilege boundaries verified`. The target created fresh volumes and removed its containers, networks and volumes on exit. |
| `python3 -m compileall -q app tests` | Passed. |
| `sh -n scripts/*.sh docker/db/init.sh` | Passed. |
| `docker compose config --quiet` | Passed. |
| `git diff --check` and credential-pattern scan | Passed before the implementation commit. No runtime secrets or private content were staged. |
| Runtime image dependency probe | Passed; the normal `runtime` target did not contain `pytest`. |

The automated HTTP workflow exercised signed persona selection, local-model endpoint checks, fixture loading, source visibility, admission refusal without the hidden Finance canary, Engineering compilation, exact-hash verification, separate publication authorization, atomic publication, idempotent replay, joint-audience conjunction, current and historical reads, supported, contradictory and unsupported questions, answer promotion to a private candidate, source-revision staleness, membership revocation, durable-audit failure and recovery, and an unreachable local model.

## Manual operational observations

The normal six-service stack started successfully with `make up`; the API health endpoint and server-rendered GUI responded on `127.0.0.1:8080`. `make down` stopped the processes while preserving state. A confirmed `make demo-reset` removed only the `kops-local-demo` volumes.

`make backup` created a checksummed PostgreSQL archive plus source, candidate, page and answer archives. A confirmed `make restore BACKUP=<directory>` verified all checksums, restored seven personas and one run, and returned the API to healthy state. These manual observations were made on the converged implementation worktree before commit `1b79f82`; the exact commit received the automated clean-volume test above, but the manual backup and restore sequence was not repeated after the commit object was created.

## Acceptance status

| Result | Scenarios | Evidence and limitation |
| --- | --- | --- |
| Verified | A01, A02, A04, A05, A06, A09, A11, A12, A13, A20, A21, A24 | Repeatable tests against real processes, PostgreSQL, private volumes and service roles. Generation used the labeled test fixture. |
| Verified by scoped manual operation | A23 | Checksummed database and all four content classes were restored; record counts and health matched. |
| Partial | A03, A07, A08, A10, A14, A15, A16, A17, A18, A19, A22, A25, A26 | At least one applicable success, refusal or static boundary passed, but the complete fault matrix, process probe, live-model result or screenshot evidence remains open. |
| Not verified with live inference | A03, A10, A12, A25 | No operator-supplied Ollama, llama.cpp or LM Studio endpoint was available. Fixture output is deliberately excluded from live evidence. |

Actual GUI screenshots are not included. Browser use was not authorized during implementation, and the repository policy requires authorization before opening one. `screenshots/README.md` names the required views without substituting mock images.

## Baseline conformity

Profile C applies to the implementation workflow. The product demonstrates a local L-to-D transition for compilation and publication; no profile A autonomous loop is present.

| Control | State | Evidence and boundary |
| --- | --- | --- |
| C01 complexity and measure | Verified for demo scope | One bounded worker and one bounded publisher; bytes, latency, states and timestamps are persisted. No production load claim. |
| C02 one accountable writer | Verified | Source, candidate, page, answer and audit writes have distinct process and volume ownership. PostgreSQL privilege assertions passed. |
| C03 independent verification | Partial | Verification is a distinct exact-hash record and persona; a single presenter switching mock personas does not prove independent human review. |
| C04 authority | Verified for local contract | Current action grants, memberships, audiences and policy revisions are checked server-side. The identity provider is mocked. |
| C05 proposal and commit separation | Verified | Worker creates private candidates only. Verification, expiring authorization and the bounded publication transaction are separate records and effects. |
| C06 bounded execution and destinations | Verified for configured paths | Local/private destination validation, redirect refusal, byte/token/time/retry limits and one active compilation are enforced. DNS rebinding and host-administrator control remain outside this demo boundary. |
| C07 identity and delegation | Partial | Initiator, workload principal and authorization references are explicit; real Keycloak and enterprise delegation are absent. |
| C08 token recipients | Partial | Signed sessions include a recipient and internal paths use distinct tokens. MCP and A2A are not applicable because those adapters are absent. |
| C09 credential isolation | Partial | Generated ignored secrets are mounted only into intended services. The trusted local Docker administrator remains able to inspect containers. |
| C10 content boundaries | Verified for demo scope | Worker receives only the admitted manifest through the content broker; unauthorized titles, bodies, history and query context are hidden. |
| C11 limits and stop | Verified for covered paths | Finite limits, cancellation checks, version checks and denial tests passed. No production resource-isolation claim. |
| C12 protected audit | Verified for demo scope | Collector is insert-only, actor tokens are service-specific, attempt and committed effect are distinct, reads fail closed, and publication reconciles through an outbox. Host administration remains trusted. |

## Remaining delivery gates

1. Select an operator-controlled local model in Model Setup and run the live compilation, question and quality scenarios.
2. Obtain browser authorization and capture the actual GUI views listed in `screenshots/README.md`.
3. Obtain independent review of the exact pull request result. Do not merge automatically.
