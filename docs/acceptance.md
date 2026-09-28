# Acceptance matrix

**Current result for every scenario: Not run.** Replace this statement with linked evidence as implementation proceeds. Model choice happens at runtime. A live-model acceptance run requires an operator-supplied endpoint and must remain unverified if none is available. The model and GUI must run for real; mocked identity and repeatable test fixtures must be labeled.

| ID | Scenario | Expected outcome |
| --- | --- | --- |
| A01 | Start from a clean local environment and load fixtures. | GUI and required backend processes start reproducibly; no real Keycloak or hosted service is required. |
| A02 | Switch seeded persona and audience. | Server resolves stable identity; client-supplied arbitrary roles cannot grant access. |
| A03 | Ingest a permitted source and compile using local inference. | Immutable source revision, complete input manifest and private linked-page candidate exist. |
| A04 | Dual-access initiator targets Engineering and requests Finance input. | Admission refuses before content reaches that generation context. |
| A05 | Joint Engineering AND Finance compilation. | Only subjects satisfying both policies can retrieve the resulting content. |
| A06 | Review, authorize and publish through GUI. | Exact-candidate verification and effect authorization are distinct; only the bounded writer commits. |
| A07 | Modify candidate content, audience, dependency policy or expected version after authorization. | Old authorization is invalid; no unintended publication occurs. |
| A08 | Concurrent edits and replayed publication. | Conflicts are refused; replay is idempotent; no partial multi-page visibility. |
| A09 | Read pages, history, titles, previews, backlinks, citations and audit as an unauthorized user. | All protected paths deny access without leaking restricted metadata. |
| A10 | Ask answerable, unsupported and contradictory questions. | Answers cite permitted page versions; unsupported claims and conflicts are evaluated independently. |
| A11 | Save an answer. | It becomes a private candidate with complete dependencies, not an automatic publication. |
| A12 | Update source content and run maintenance. | Dependents become stale; regeneration proposes a new version and needs fresh verification/authorization. |
| A13 | Revoke membership while a session is active. | Subsequent protected reads, history and saved answers observe the new local membership state. |
| A14 | Change source policy while a job is queued, running or ready to publish. | Fresh checks prevent outdated admission/publication; dependents block pending re-evaluation. |
| A15 | Inject instructions to widen policy, read hidden sources or call arbitrary URLs. | Model content cannot alter authority, tool scope or output destination. |
| A16 | Attempt worker access to storage administration, publisher writes or broker credentials. | Technical boundaries refuse access; secret values do not appear in evidence. |
| A17 | Exceed job limits or cancel queued/running work. | New model calls and publication stop; the GUI reflects the actual state. |
| A18 | Lose response after a successful publication commit. | Reconcile by operation ID; no blind replay or duplicate visible revision. |
| A19 | Disable durable audit recording; try protected reads and publication. | v4 fail-closed behavior applies; uncertain effects are reconciled explicitly. |
| A20 | Attempt to update/delete audit as worker or publisher. | Refused; attributable events survive within the declared trusted-host boundary. |
| A21 | Render hostile Markdown, paths or remote assets. | No script execution, traversal, unauthorized fetch or direct object bypass. |
| A22 | Restart application and refresh browser mid-run. | Persisted state is recovered; the GUI does not invent completion. |
| A23 | Restore a local backup and run the protected read flow. | Page references, policies, dependencies and audit linkage remain consistent. |
| A25 | Configure local inference through the GUI, change models between jobs and use an unreachable endpoint. | Destination controls apply; each job pins its configuration; real errors are shown with no fixture/cloud fallback. |
| A26 | Try metadata/link-local endpoints, unauthorized redirects and ordinary-user destination changes. | Server rejects disallowed destinations; the worker cannot select a different endpoint. |
| A24 | Complete walkthrough, stop and scoped reset. | Normal operation needs no shell shortcuts; processes stop and reset affects only synthetic demo state. |

## Evidence format

For each material test record: scenario, requirements, commit and configuration, model/adapter version, expected result, observed result, dated evidence, limitations and follow-up. Record negative results, not just happy-path screenshots. Retain a small model-quality set with supported, contradicted and unanswerable questions; source-reference existence is not proof of factual support.

Map acceptance evidence to all v4 controls: C01 complexity and measured resources; C02 writer ownership; C03 independent verification; C04 authority; C05 proposal/commit separation; C06 bounded execution; C07 identity/delegation; C08 token recipients; C09 credential isolation; C10 content boundaries; C11 limits/stop; C12 protected audit.

Mocked identity tests prove local contract behavior only. A single presenter switching reviewer personas does not establish independent human review. Keep those limitations explicit in the final evidence matrix and PR.
