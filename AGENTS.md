# kops project instructions

- Read `HANDOFF.md`, `docs/plan.md`, `docs/gui-walkthrough.md`, `docs/acceptance.md` and the relevant sections of `docs/architecture-v4.md` before implementation.
- The latest user-authorized scope in `docs/plan.md` controls demo adaptations: local Compose runtime, synthetic sources, mocked Keycloak, real inference from the runtime-selected hosted provider and a GUI for all stages.
- Implement the workflow completely. Do not replace authorization, persistence, publication, provenance, review, revocation or audit with frontend-only simulations.
- Keep project status, decisions, validation evidence and next steps in this repository. Do not put task state in shared personal memory.
- Use one accountable writer per file or shared state. No subagent delegation is required by this repository.
- Solo exploration: Franco and the agent, nobody else. Two branches only, `dev` and `main`, no feature branches, no pull requests, no branch protection, no external reviewer. Work is committed and pushed on `dev` as it lands; `main` receives it when Franco says so. A Codex review is a tool Franco can ask for, not a gate.
- Getting started must be: clone, copy `.env.example` to `.env`, choose the model, `docker compose up`. Anything that needs `make`, Bash or a host package is a gap to close, not a prerequisite to document.
- The product is the demo. The primary artifact is the Compose stack: it must run unchanged on Linux, Windows and macOS with Docker, with no host-specific assumption in code, scripts or documentation. The model is chosen at runtime through environment: provider (`anthropic` or `openai`, hosted, key from a secret file), model name, classifier model, reasoning effort; selectable per session without a rebuild, never hard-wired, never silently defaulted, and the evidence names the provider actually used. No local inference and no Ollama.
- `docs/lab.md` is the plan for the next stage and `HANDOFF.md` the assignment: raw store and collectors with a rule pre-filter, a schema-based classifier on the selected provider, one wiki per audience, a return through three separate gates (rights, need, form), a read-only gateway and a bounded ops agent, lineage.
- `scripts/generate_meridian.py` is the only source of `fixtures/meridian/`. Edit the generator, regenerate, commit both; never hand-edit the output. Generators, collectors and lint stay deterministic standard-library code with no model call.
- Everything in `fixtures/meridian/` is invented, planted secrets are canonical fake values; keep it that way, because part of the corpus is sent to a hosted classifier.
- Keep the Git remote on SSH. Preserve the configured Franco Geraci/Voloire/Voloirex identity and GitHub noreply address. Do not add coauthor or generation trailers.
- Keep public-facing names and text focused on KnowledgeOps Platform and kops. Preserve any legally required third-party notices if code is reused; do not invent ownership claims.
- Do not commit credentials, real company content, private briefs, runtime data or unreviewed generated artifacts. The repository is public.
- Real provider calls go to the provider, model and reasoning selected for the session. Do not substitute another provider or a fixture response silently; fixture output never satisfies a gate.
- The only author is Franco Geraci. No other person, company, client, call or meeting is named anywhere in the repository, and no attribution other than the configured Git identity appears in commits, files or metadata.
- No OpenSearch, embeddings, live corporate SSO, new cloud services or production deployment. Use v4 components only, with the documented demo adapters.
- Evidence must identify the actual tested commit/configuration and observed result. Mark mocks and unknown controls explicitly. Never claim enterprise security from this demo.
