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
