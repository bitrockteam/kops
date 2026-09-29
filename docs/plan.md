# Final implementation plan: local kops demo

**Status: first delivery, merged on `main` at `4050225`. This document is kept as the record of that scope. The next stage is `docs/lab.md`, assigned in `HANDOFF.md`; where the two differ (the account's Claude through a host bridge instead of local inference, `dev` and `main` only instead of feature branches and pull requests), the lab plan wins.**

## Objective and authority

Build Governed Knowledge Compilation and Publishing as a local component of KnowledgeOps Platform. The deliverable is a working backend and GUI with synthetic data. The GUI must let Franco execute and inspect each stage from source intake through maintenance and revocation.

The user explicitly requested the local `kops` repository and public `bitrockteam/kops` remote, followed by a final plan and handoff for another implementing session. The original planning session prepared the repository and did not implement the application. Implementation was authorized to commit and push completed work on a feature branch and prepare a PR. No automatic shared-branch merge or deployment is authorized.

## Latest decisions and precedence

| Item | Decision |
| --- | --- |
| Architecture | Follow `architecture-v4.md` for lifecycle, policy, provenance, publication and audit. |
| Delivery | Local runnable demo with synthetic data and a guided GUI. |
| Identity | Mock Keycloak through a replaceable identity adapter; do not run or deploy real Keycloak. |
| Knowledge processing | Real local inference for compilation, questions and model-assisted maintenance. |
| Endpoint/model | No runtime is currently configured. The operator chooses the local endpoint and model through the GUI at runtime. |
| Search | Authorized catalog and lexical search only. No OpenSearch or embeddings. |
| Scope | No corporate connectors, real SSO, unattended refresh, MCP/A2A or production deployment. |
| Branding | KnowledgeOps Platform and kops in the public application and documentation. |
| Baseline | Preserve v4's C01-C12 requirements. Mocked identity changes evidence scope, not backend authorization requirements. |

The archived v4 source document describes real identity integration as the eventual architecture. The user-approved mock in this plan replaces it for the demo. Other v4 safeguards and lifecycle phases stay in scope. Do not add infrastructure because it was discussed in earlier exploratory conversations.

## Product workflow

1. Import synthetic Markdown or plain-text sources into an explicitly selected audience.
2. Preview admission: display permitted sources and refusal reasons without exposing unauthorized source metadata.
3. Compile private candidates containing summaries, concepts, entities, comparisons and linked overviews.
4. Inspect the complete input manifest, page changes, source passages, contradictions and validation findings.
5. Verify the exact candidate under the reviewer role and separately authorize the intended publication.
6. Publish through a bounded executor and a sole conditional writer.
7. Browse authorized published pages, their history and citations; ask questions grounded in those pages.
8. Run maintenance explicitly, update sources and propose regenerated pages.
9. Change memberships or source policies and demonstrate access revocation, stale-state handling and blocked publication.
10. Inspect actual audit attempts, decisions and outcomes, including failure and stop scenarios.

Persistent compilation is central. Importing a source must update the maintained knowledge collection, not merely index raw chunks for question-time synthesis. Query answers can become candidates, but never become published knowledge automatically. Maintenance proposes findings or changes without granting itself authority to write.

## Architecture and implementation choices

Use one Python codebase with a FastAPI API and a server-rendered GUI with small JavaScript enhancements for step navigation, live job events and comparisons. Use PostgreSQL for policy and lifecycle metadata and a durable job table. Store immutable Markdown/source content in private storage behind an adapter, initially a private local volume. Keep publication references and their metadata transactional. A Compose setup may package these v4 responsibilities; do not introduce Kubernetes, a vector database or an external queue service.

Keep runtime boundaries for the restricted compilation worker, model access, bounded publication executor and protected audit collector. One codebase may have several narrowly privileged process entry points. The worker receives admitted inputs and may submit candidates; it cannot write published records, alter policy or administer storage. The executor accepts protected operation references and revalidates actual arguments and authority before effects.

Expose interfaces for `IdentityProvider`, `PolicyService`, `ContentStore`, `ModelClient`, `JobService`, `PublicationService` and `AuditSink`. Real platform adapters can replace local implementations later. They are not part of this task.

### Mocked Keycloak

Implement `MockIdentityProvider` with stable subject IDs and seeded personas. Use a demo session selector that the server resolves against trusted fixtures. The normal API must not accept arbitrary user-provided role or group claims. Include a visible mocked-identity banner and bind the demo to loopback by default.

Current application audience memberships in PostgreSQL are authoritative for the demo. Check them on each protected operation and before content release. A policy-admin demo control can change memberships and source policies, with real audit events and real invalidation. Existing sessions must observe those changes.

Tests can exercise signed fixture tokens, expiry and wrong-recipient rejection where the adapter models tokens. These tests cover only the mock contract. They do not prove Keycloak federation, real token issuance, directory synchronization, MFA or enterprise offboarding.

The presenter may switch seeded personas to demonstrate a complete story. This is a role simulation, not independent human review. Keep the final real acceptance review separate.

### Local inference

Provide a Model Setup screen before compilation: adapter type, endpoint URL, model selection/name, connection test and finite execution limits. Support a local OpenAI-compatible chat endpoint and a native Ollama adapter behind the same model interface. The operator supplies a running local inference service; the demo must not install runtimes or download models automatically. Allow GUI source inspection and deterministic lifecycle tests before model setup; block real compilation/questions with a clear setup action until the selected endpoint is usable. Persist model configuration locally, allow it to be changed between runs, and snapshot the model configuration on each job. Model changes invalidate jobs or approvals that depend on changed generated content. Do not silently use a hosted provider or return fixture text on errors. If the model is unreachable, show the actual error and keep the job unpublished.

Only the local demo operator may configure the model destination. Validate endpoint schemes and destinations server-side; default to loopback and deliberately configured local-network addresses, deny cloud metadata/link-local destinations, and disable unapproved redirects. Browser-supplied endpoint fields must never bypass that control. Resolve container-to-host connectivity through explicit configuration. Broker inference through a typed interface tied to the authenticated workload, protected job record, admitted content and configured limits. Model prompts and source documents cannot choose network destinations or obtain storage credentials. No worker gets a Docker socket, unrestricted shell tool, host home directory or infrastructure credentials.

Offline inference fixtures are acceptable for repeatable tests but do not satisfy the working-demo gate. Record the actual model identity, configuration, input/output sizes, latency and quality findings for live runs. Limit concurrent compilation to one job initially, allow at most one transient inference retry, cap automatic repair attempts and configure finite per-job input, output and wall-time limits before live execution. Never retry an uncertain publication without reconciling its operation ID.

### Policies, content and provenance

Separate action roles from audiences. Seed Engineering, Finance and a joint audience requiring Engineering AND Finance. The first policy language supports bounded conjunctions of stable group IDs and explicit action grants; reject unsupported expressions. A dual-access initiator does not authorize Finance information in an Engineering destination.

Record tenants, subjects, audience memberships, policy revisions, source versions, page versions, dependency edges, jobs, change sets, verification results, publication authorizations, operations and audit outbox events. Full provenance includes every admitted input: sources, existing page versions, task text, schema revision and tool results. Source citations identify evidence; they do not establish that uncited input had no influence.

The model proposes text, links and citations. The backend assigns IDs, policies, hashes, identity and lifecycle metadata. Descriptive Markdown frontmatter cannot grant access. Render Markdown safely, disable active content and remote asset fetching, and protect paths, previews, backlinks, titles, exports and history under the same policy contract.

Build an audience-filtered catalog from authorized published records. Maintain source summaries, entity/concept pages, comparisons and overviews as useful outputs. Generate chronological activity views from persisted events rather than trusting model-written statements that an operation occurred.

### Review, publication and audit

Use `draft -> independently_verified -> authorized -> published -> stale/blocked -> superseded`. Verification checks the exact candidate, complete manifest and acceptance criteria. An authorization record binds the candidate hash, operation, audience, expected versions, policy revisions and expiry. Material changes invalidate prior authorization.

Only the publication service commits visible page revisions. Multi-page changes publish atomically through database references; content may be staged privately first. Record expected-version preconditions, idempotency keys and outcomes. Human edits use the same writer.

Use a protected audit boundary with append authority and no update/delete privileges for the worker and executor. Logs must distinguish attempt, committed effect and uncertain result. Persist intent before effects and correlate outbox events with publication. If durable read-audit recording is unavailable, apply v4's fail-closed behavior. A read receipt proves server delivery, not human consumption. The trusted local host administrator remains outside the demo isolation claim.

## Synthetic scenario

Use a fictional company and clearly labeled fabricated documents. Include an engineering expansion plan, a finance budget, a revised budget, conflicting estimates and an injected instruction attempting to bypass audience controls. Include a Finance-only canary value for leakage tests.

Seed Engineering-only, Finance-only, dual-access, reviewer/publisher and policy-admin personas. Action roles must not imply content access; make content membership explicit for each fixture persona. No real company content or personal credentials enter the public repository.

The walkthrough must prove that a dual-access user compiling for Engineering cannot admit the Finance budget, while a joint-audience job can combine both sources. Revoking Finance membership must then block joint pages, dependent answers and historical versions for that user.

## Milestones

| Milestone | Deliverable | Exit condition |
| --- | --- | --- |
| M0: scaffold and contracts | Feature branch, local configuration, storage schema, fixtures, mock identity, runtime model setup and GUI shell. | The access matrix and finite job limits are explicit; runtime can start locally. |
| M1: deterministic lifecycle | Real protected storage, candidate review, authorization, bounded publication and audit using fixed candidates. | Positive/negative backend checks pass; GUI reflects persisted state. |
| M2: live compilation | Source intake, admission, local inference, structured candidates, evidence and linked pages. | A live source produces a useful candidate; forbidden inputs never reach its context. |
| M3: complete GUI walkthrough | All stages in `gui-walkthrough.md`, including questions and explicit answer-to-candidate promotion. | The normal story can be completed through the GUI without shell-only shortcuts. |
| M4: maintenance and fault scenarios | Source updates, lint, regeneration, policy changes, revoke, stop, retries and outage controls. | `acceptance.md` scenarios execute against real state with observable outcomes. |
| M5: reproducible delivery | Setup/run/stop/reset docs, meaningful tests, live-model evidence and screenshots. | A clean local run reproduces the story; branch committed/pushed and PR ready for review. |

Build the GUI with each milestone. Do not postpone it until backend completion or substitute a terminal trace for the requested product workflow.

## Baseline conformity and limits

The current bootstrap is a profile D documentation publication to the exact public repository requested by Franco. Implementation uses profile C and human-reviewed PR integration. Synthetic publication exercises a supervised D workflow. Autonomous A execution is not enabled.

C01-C12 are design requirements, not current runtime achievements. The source architecture and user-authorized scope are verified as read. Coverage is partial at the design level. Runtime controls are unknown until tested. No implementation failure has yet been observed. Real Keycloak behavior and independent human review cannot be verified through the mock. MCP/A2A-specific controls are not applicable until those surfaces are introduced; ordinary API authorization and credential checks remain required.

The application must display its demonstration limits. A user-visible green stage means that stage's recorded checks passed, not that the entire platform is enterprise-certified.

## Required run interface

Implement and verify the run contract described in `../README.md`: `make setup`, `make up`, `make down`, `make test`, `make demo-reset`, and `make logs`. Setup must not download model weights, install an identity server, or call an external provider. The GUI defaults to `http://127.0.0.1:8080`, configurable if occupied. `make up` keeps start behavior explicit and reports the actual URL; `make down` stops all demo-managed processes. Reset requires confirmation and affects only synthetic runtime state. Container-to-host model networking must be documented and tested.

No model endpoint or model name is hardcoded into the acceptance contract. The local model must be supplied at runtime. If no model is available in the implementation environment, deliver and test the adapter contract, report the live-model acceptance gap accurately, and do not declare the full working demo accepted. Do not silently substitute a fixture model.

## Delivery and repository workflow

Maintain `docs/status.md` and `docs/decisions.md` during implementation. Add an evidence report with tested commit/configuration, expected result, observed result, artifact, limitation and owner/action for each material check. Test code must verify outcomes and refusal paths, not merely mirror implementation helpers.

Commit and push completed implementation work to `feat/local-demo`; open a PR and leave merging to authorized human review. Report local startup instructions, model requirements, validation results and material limitations. Before claiming delivery, verify a clean working tree and zero unpushed commits. Do not deploy, add hosted services, change organizational permissions or send messages to others.
