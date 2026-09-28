# Local demo implementation evidence

## Evidence identity

| Field | Value |
| --- | --- |
| Initial tested implementation commit | `1b79f82dc762180ea4202a1aa94a2b2fd1aa1a28` |
| Current tested application commit | `934d6636a5935784ef4d5adeeede15c1e028f306` |
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
| Current application checks | `make test` on exact commit `934d663` passed 12 tests in 19.20 seconds, database privilege assertions, worker-interruption recovery, and PostgreSQL job and query-manifest reads after Compose container recreation. The disposable `kops-test` project and volumes were removed on exit. |
| Prior CI check | [GitHub Actions `kops-test`](https://github.com/bitrockteam/kops/actions/runs/36481721801/job/109128716190) passed on prior commit `30ccfb0`. A check for the new pull-request head must be observed separately after push. |
| `python3 -m compileall -q app tests` | Passed. |
| `sh -n scripts/*.sh docker/db/init.sh` | Passed. |
| `docker compose config --quiet` | Passed. |
| `git diff --check` and tracked-file credential-pattern scan | The diff check passed before commit `934d663`; a scan of that commit returned no matching filenames. No runtime secrets or private content were staged. |
| Runtime image dependency probe | Passed; the normal `runtime` target did not contain `pytest`. |

The automated HTTP workflow exercised signed persona selection, local-model endpoint checks, fixture loading, source visibility, admission refusal without the hidden Finance canary, Engineering compilation, exact-hash verification, separate publication authorization, atomic publication, idempotent replay, joint-audience conjunction, current and historical reads, supported, contradictory and unsupported questions, answer promotion to a private candidate, source-revision staleness, membership revocation, durable-audit failure and recovery, and an unreachable local model.

The hardened tests additionally checked direct HTML title escaping, disabled compile and question controls when the model is unreachable, a branded 404 denial view, complete query input pages despite a single model citation, promoted source dependencies, response and audit metadata after membership revocation, blocked historical reads and candidate delivery after source-policy revision, dashboard and alternate denial-route fail-closed behavior when audit is unavailable, trickling and oversized model responses, cancellation during receive, and rejection of mixed source versions during answer promotion. The restart check injected an interrupted `running` record into the disposable test database, restarted the worker, and observed a bounded `worker_interrupted` state before recreating all Compose containers without removing named volumes.

## Manual operational observations

The normal six-service stack started successfully with `make up`; the API health endpoint and server-rendered GUI responded on `127.0.0.1:8080`. `make down` stopped the processes while preserving state. A confirmed `make demo-reset` removed only the `kops-local-demo` volumes.

`make backup` created a checksummed PostgreSQL archive plus source, candidate, page and answer archives. A confirmed `make restore BACKUP=<directory>` verified all checksums, restored seven personas and one run, and returned the API to healthy state. These manual observations were made on the converged implementation worktree before commit `1b79f82`. They were not repeated after the PostgreSQL mount and restore-migration changes in `934d663`, so they remain historical evidence rather than verification of the current backup/restore path.

The current startup preflight refused a deliberately created empty `kops-local-demo_postgres_data` volume with the full warning that an old anonymous volume might contain the real database. That empty probe volume was removed. This proves the refusal path for an empty named volume, not successful migration of prior data or detection of every legacy state.

## Acceptance status

| Result | Scenarios | Evidence and limitation |
| --- | --- | --- |
| Verified for tested paths | A01, A02, A04, A05, A06, A11, A12, A13, A20, A21 | Repeatable tests against real processes, PostgreSQL, private volumes and service roles. Generation used the labeled test fixture. |
| Historically observed, not retested on current commit | A23 | Earlier checksummed restore recovered all four content classes. The changed current restore path was not rerun. |
| Partial | A03, A07, A08, A09, A10, A14, A15, A16, A17, A18, A19, A22, A23, A24, A25, A26 | Additional negative and process-restart variants passed, but the complete metadata/fault matrix, current restore and normal reset path, or live-model result remains open. |
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

GitHub reported `main` as unprotected before this work. The repository administrator enabled branch protection with one required approval, dismissal of stale approvals, approval by someone other than the last pusher, resolved conversations, strict `kops-test` status from GitHub Actions app ID 15368, linear history, administrator enforcement, and force-push/deletion denial. A follow-up GitHub API read reported `protected: true` and the configured fields. Pull request 1 reported `BLOCKED` and `REVIEW_REQUIRED` while the check on `30ccfb0` succeeded. No merge or deliberately rejected push was attempted, so this is observed configuration and pull-request gating, not a proof that every possible privileged bypass is impossible. Repository administrators can still edit protection settings. The new pull-request head needs its own check and independent human approval.

## Baseline conformity

Profile C applies to the implementation workflow. The product demonstrates a local L-to-D transition for compilation and publication; no profile A autonomous loop is present.

| Control | State | Evidence and boundary |
| --- | --- | --- |
| C01 complexity and measure | Verified for demo scope | One bounded worker and one bounded publisher; bytes, latency, states and timestamps are persisted. No production load claim. |
| C02 one accountable writer | Verified | Source, candidate, page, answer and audit writes have distinct process and volume ownership. PostgreSQL privilege assertions passed. |
| C03 independent verification | Partial | Verification is a distinct exact-hash record and persona; a single presenter switching mock personas does not prove independent human review. |
| C04 authority | Verified for covered local contract | Current action grants, memberships, audiences, source compatibility and dependency policy revisions are checked server-side. The identity provider is mocked; concurrent read/revocation linearizability was not fault-injected. |
| C05 proposal and commit separation | Partial overall | Product verification, expiring authorization and bounded publication are tested. `main` protection is active and pull request 1 is blocked pending independent approval; the required human review has not occurred. Repository administrators can edit protection settings. |
| C06 bounded execution and destinations | Verified for configured paths | Local/private destination validation, redirect refusal, streamed byte ceiling, total request deadline, bounded retry and one active compilation were exercised. DNS rebinding and host-administrator control remain outside this demo boundary. |
| C07 identity and delegation | Partial | Initiator, workload principal and authorization references are explicit; real Keycloak and enterprise delegation are absent. |
| C08 token recipients | Partial | Signed sessions include a recipient and internal paths use distinct tokens. MCP and A2A are not applicable because those adapters are absent. |
| C09 credential isolation | Partial | Generated ignored secrets are mounted only into intended services. The trusted local Docker administrator remains able to inspect containers. |
| C10 content boundaries | Verified for covered demo paths | Worker receives only the admitted manifest through the content broker; tested unauthorized titles, bodies, history, response metadata and query context are hidden. |
| C11 limits and stop | Verified for covered paths | Full prompts, streamed responses, total inference deadline, cancellation, source freshness before retries, version checks and restart recovery were tested. No production resource-isolation claim. |
| C12 protected audit | Verified for covered demo paths | Collector is insert-only, actor tokens are service-specific, attempt and committed effect are distinct, tested direct and alternate reads fail closed, and publication reconciles through an outbox. Host administration remains trusted. |

## Remaining delivery gates

1. Select an operator-controlled local model in Model Setup and run the live compilation, question and quality scenarios.
2. Obtain independent review of the exact pull request result. Do not merge automatically.
