# Decisions

| Decision | Reason | Scope |
| --- | --- | --- |
| Implement a local component with synthetic data. | Validate the complete knowledge lifecycle without corporate data or deployment. | Initial demo. |
| Mock Keycloak only. | The user wants to verify the other v4 phases without configuring real identity infrastructure. | Identity is simulated; backend policy decisions remain real. |
| Select local inference at runtime. | Explicit user choice; no service is currently configured. | GUI setup for adapter, endpoint, model and finite limits; no automatic model download or hosted fallback. |
| Make the GUI part of every milestone. | The user must follow the steps directly. | All application phases. |
| Preserve v4 authority and provenance boundaries. | A useful demo must exercise the actual lifecycle rather than only display a proposed architecture. | All in-scope operations. |
| Exclude OpenSearch and unrelated infrastructure. | Explicit user constraint. | Catalog and lexical search only. |
| Keep the repository public and use KnowledgeOps Platform branding. | Explicit user request. | Reviewed synthetic/public artifacts only. |
| Use a feature branch and human-reviewed PR for implementation. | Commit/push authorization does not authorize automatic shared-branch integration. | Implementation after the planning bootstrap. |
| Use separate process and PostgreSQL roles for API, admitted-content broker, worker, publisher and audit. | The worker must receive only admitted source bodies, the API must not write page revisions, and the collector must be append-only. | Local Compose demo; the host administrator remains trusted. |
| Use separate content volumes by lifecycle class. | Read-only and read-write mounts make source, candidate, page and answer authority observable and testable. | Local content adapter. |
| Authenticate internal calls with per-path secrets and audit calls with per-service actor tokens. | A worker token must not impersonate the API or publisher in protected audit, and the worker must not invoke publication directly. | Generated ignored runtime secrets. |
| Keep deterministic inference behind a test-only Compose profile. | Repeatable lifecycle tests are valuable but must never become a normal-runtime or live-model fallback. | Automated tests only. |
| Invalidate through database-owned bounded triggers. | Source and audience changes must block or stale dependents even though the API has no write privilege on published records. | Source revisions and policy revisions. |
| Back up database and each private content class together. | Page references, policies, dependencies and audit linkage must restore consistently. | Checksummed local archives below ignored runtime state. |
