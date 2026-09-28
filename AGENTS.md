# kops project instructions

- Read `HANDOFF.md`, `docs/plan.md`, `docs/gui-walkthrough.md`, `docs/acceptance.md` and the relevant sections of `docs/architecture-v4.md` before implementation.
- The latest user-authorized scope in `docs/plan.md` controls demo adaptations: local runtime, synthetic sources, mocked Keycloak, real local inference and a GUI for all stages.
- Implement the workflow completely. Do not replace authorization, persistence, publication, provenance, review, revocation or audit with frontend-only simulations.
- Keep project status, decisions, validation evidence and next steps in this repository. Do not put task state in shared personal memory.
- Use one accountable writer per file or shared state. No subagent delegation is required by this repository.
- Create an implementation branch, commit and push the completed work, and open a PR. Shared-branch integration requires independent review and Franco's approval; never merge automatically.
- Keep the Git remote on SSH. Preserve the configured Franco Geraci/Voloire/Voloirex identity and GitHub noreply address. Do not add coauthor or generation trailers.
- Keep public-facing names and text focused on KnowledgeOps Platform and kops. Preserve any legally required third-party notices if code is reused; do not invent ownership claims.
- Do not commit credentials, real company content, private briefs, runtime data or unreviewed generated artifacts. The repository is public.
- Real provider calls require the selected local endpoint/model. Do not substitute a paid hosted service or a fixture response silently.
- No OpenSearch, embeddings, live corporate SSO, new cloud services or production deployment. Use v4 components only, with the documented demo adapters.
- Evidence must identify the actual tested commit/configuration and observed result. Mark mocks and unknown controls explicitly. Never claim enterprise security from this demo.
