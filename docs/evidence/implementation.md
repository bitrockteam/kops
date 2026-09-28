# Local demo implementation evidence

## Evidence identity

| Field | Value |
| --- | --- |
| Initial tested implementation commit | `1b79f82dc762180ea4202a1aa94a2b2fd1aa1a28` |
| Current tested application commit | `30ccfb0c03027e7c7912e4cf69ef50e58c8eb9d2` |
| Date and host | 28 September 2026, `voloire-XPS`, Ubuntu 26.04 LTS |
| Automated configuration | Docker Compose project `kops-test`, Python 3.13 runtime image, PostgreSQL 18.0 Alpine, fresh disposable volumes |
| Identity boundary | Labeled mock identity with signed server-issued sessions and seven synthetic personas |
| Inference boundary | Labeled test-only deterministic local HTTP fixture; it is not a live-model result or runtime fallback |
| Demo runtime external services | None |

## Reproducible checks

| Check | Observed result |
| --- | --- |
| `make setup` | Passed; validated Docker and Compose and prepared ignored per-service secrets without installing a model or identity provider. |
| `make test` at the initial commit | Passed: 10 tests in 9.75 seconds, followed by `database privilege boundaries verified`. The target created fresh volumes and removed its containers, networks and volumes on exit. |
| Current application checks | The expanded local suite passed: 10 tests in 8.17 seconds plus database privilege assertions. [GitHub Actions `kops-test`](https://github.com/bitrockteam/kops/actions/runs/36481721801/job/109128716190) completed successfully on exact application commit `30ccfb0`. |
| `python3 -m compileall -q app tests` | Passed. |
| `sh -n scripts/*.sh docker/db/init.sh` | Passed. |
| `docker compose config --quiet` | Passed. |
| `git diff --check` and credential-pattern scan | Passed before the implementation commit. No runtime secrets or private content were staged. |
| Runtime image dependency probe | Passed; the normal `runtime` target did not contain `pytest`. |

The automated HTTP workflow exercised signed persona selection, local-model endpoint checks, fixture loading, source visibility, admission refusal without the hidden Finance canary, Engineering compilation, exact-hash verification, separate publication authorization, atomic publication, idempotent replay, joint-audience conjunction, current and historical reads, supported, contradictory and unsupported questions, answer promotion to a private candidate, source-revision staleness, membership revocation, durable-audit failure and recovery, and an unreachable local model.

The expanded test also checked direct HTML title escaping, disabled compile and question controls when the model is unreachable, and a branded 404 denial view that excludes the revoked document from the catalog.

## Manual operational observations

The normal six-service stack started successfully with `make up`; the API health endpoint and server-rendered GUI responded on `127.0.0.1:8080`. `make down` stopped the processes while preserving state. A confirmed `make demo-reset` removed only the `kops-local-demo` volumes.

`make backup` created a checksummed PostgreSQL archive plus source, candidate, page and answer archives. A confirmed `make restore BACKUP=<directory>` verified all checksums, restored seven personas and one run, and returned the API to healthy state. These manual observations were made on the converged implementation worktree before commit `1b79f82`; the exact commit received the automated clean-volume test above, but the manual backup and restore sequence was not repeated after the commit object was created.

## Acceptance status

| Result | Scenarios | Evidence and limitation |
| --- | --- | --- |
| Verified | A01, A02, A04, A05, A06, A09, A11, A12, A13, A20, A21, A24 | Repeatable tests against real processes, PostgreSQL, private volumes and service roles. Generation used the labeled test fixture. |
| Verified by scoped manual operation | A23 | Checksummed database and all four content classes were restored; record counts and health matched. |
| Partial | A03, A07, A08, A10, A14, A15, A16, A17, A18, A19, A22, A25, A26 | At least one applicable success, refusal or static boundary passed, but the complete fault matrix, process probe or live-model result remains open. |
| Not verified with live inference | A03, A10, A12, A25 | No operator-supplied Ollama, llama.cpp or LM Studio endpoint was available. Fixture output is deliberately excluded from live evidence. |

## Actual GUI evidence

Franco authorized Firefox. Headless Firefox 154.0 with geckodriver 0.37.1 captured the running application from commit `30ccfb0` in disposable Compose project `kops-evidence` on loopback port 18081. The synthetic workflow used the labeled test-only inference fixture. Its Finance membership revocation was an actual persisted policy change. The browser used a temporary profile, and the project containers and volumes were removed after capture.

| Image | Observed state |
| --- | --- |
| [Publication](../../screenshots/01-publication.png) | Engineering and joint operations show committed results. |
| [Authorized catalog](../../screenshots/02-authorized-catalog.png) | Operator sees both audiences and stale joint pages. |
| [Access change](../../screenshots/03-access-changes.png) | Admin form identifies the synthetic dual-access persona and Finance membership. |
| [Protected audit](../../screenshots/04-protected-audit.png) | Durable attempts, decisions and outcomes are visible to the operator. |
| [Revoked catalog](../../screenshots/05-revoked-catalog.png) | The same dual-access persona, after Finance revocation, sees Engineering pages only. |
| [Denied page](../../screenshots/06-revoked-page-denial.png) | A direct read of its former joint page returns the guided 404 view with no joint catalog entry. |

These images prove what Firefox rendered in the fixture-backed local demo. They do not establish live-model quality, real single sign-on, or independent human review.

## Shared-branch protection

GitHub reported `main` as unprotected before this work. The repository administrator enabled branch protection with one required approval, dismissal of stale approvals, approval by someone other than the last pusher, resolved conversations, strict `kops-test` status from GitHub Actions app ID 15368, linear history, administrator enforcement, and force-push/deletion denial. A follow-up GitHub API read reported `protected: true` and the configured fields. Pull request 1 reported `BLOCKED` and `REVIEW_REQUIRED` while the check on `30ccfb0` succeeded. No merge or deliberately rejected push was attempted, so this is observed configuration and pull-request gating, not a proof that every possible privileged bypass is impossible. Repository administrators can still edit protection settings.

## Baseline conformity

Profile C applies to the implementation workflow. The product demonstrates a local L-to-D transition for compilation and publication; no profile A autonomous loop is present.

| Control | State | Evidence and boundary |
| --- | --- | --- |
| C01 complexity and measure | Verified for demo scope | One bounded worker and one bounded publisher; bytes, latency, states and timestamps are persisted. No production load claim. |
| C02 one accountable writer | Verified | Source, candidate, page, answer and audit writes have distinct process and volume ownership. PostgreSQL privilege assertions passed. |
| C03 independent verification | Partial | Verification is a distinct exact-hash record and persona; a single presenter switching mock personas does not prove independent human review. |
| C04 authority | Verified for local contract | Current action grants, memberships, audiences and policy revisions are checked server-side. The identity provider is mocked. |
| C05 proposal and commit separation | Partial overall | Product verification, expiring authorization and bounded publication are tested. `main` protection is active and pull request 1 is blocked pending independent approval; the required human review has not occurred. Repository administrators can edit protection settings. |
| C06 bounded execution and destinations | Verified for configured paths | Local/private destination validation, redirect refusal, byte/token/time/retry limits and one active compilation are enforced. DNS rebinding and host-administrator control remain outside this demo boundary. |
| C07 identity and delegation | Partial | Initiator, workload principal and authorization references are explicit; real Keycloak and enterprise delegation are absent. |
| C08 token recipients | Partial | Signed sessions include a recipient and internal paths use distinct tokens. MCP and A2A are not applicable because those adapters are absent. |
| C09 credential isolation | Partial | Generated ignored secrets are mounted only into intended services. The trusted local Docker administrator remains able to inspect containers. |
| C10 content boundaries | Verified for demo scope | Worker receives only the admitted manifest through the content broker; unauthorized titles, bodies, history and query context are hidden. |
| C11 limits and stop | Verified for covered paths | Finite limits, cancellation checks, version checks and denial tests passed. No production resource-isolation claim. |
| C12 protected audit | Verified for demo scope | Collector is insert-only, actor tokens are service-specific, attempt and committed effect are distinct, reads fail closed, and publication reconciles through an outbox. Host administration remains trusted. |

## Remaining delivery gates

1. Select an operator-controlled local model in Model Setup and run the live compilation, question and quality scenarios.
2. Obtain independent review of the exact pull request result. Do not merge automatically.
