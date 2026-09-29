# Implementation handoff: the lab stage

**Status:** the first delivery is merged on `main` at `4050225`. The next stage is planned in
`docs/lab.md` and starts from `dev`. Nothing of it is implemented yet. This document is the
assignment for the session that implements it.

## Who is here

Franco Geraci and one implementing agent. Nobody else commits, reviews or approves. The Git
identity is Franco's (`Franco Geraci`, `Voloire` or `Voloirex`, address
`6276639+Voloire@users.noreply.github.com`); do not change it and do not add any co-author,
generation or attribution trailer. Two branches: `dev` for the work, `main` when Franco says.
No feature branches, no pull requests, no branch protection.

## Which model implements this

A Sonnet 5 session at high effort is sufficient. The plan is specified down to the gate of each
phase, the data model and the runtime variables, and every gate is a deterministic check on
the running stack. Escalate to Opus only if a phase needs the plan redesigned (a gate that turns
out unreachable, a control that conflicts with the baseline), and say so before doing it.

## Read in this order

1. `AGENTS.md`: the rules of this repository.
2. `docs/lab.md`: what the demo demonstrates (D1 to D9), the classifier design, phases P0 to P7
   with their gates, the run and runtime contract.
3. `README.md`: the public description; keep it accurate as phases close.
4. `docs/architecture-v4.md` and `docs/evidence/implementation.md`: what the first delivery
   built and verified, so that nothing is rebuilt or weakened.
5. `scripts/generate_meridian.py` and `fixtures/meridian/manifest.json`: the synthetic world and
   its ground truth.
6. The agentic baseline in the shared memory (`baseline-agenti/SCHEDA.md`), profile C while
   building, profile A for the ops agent in P5.

## First actions

1. `git status -sb` on `dev`, remote on SSH, identity as above. Do not touch `main`.
2. Confirm Docker and Compose on the machine. Nothing else is installed on the host.
3. Ask Franco for the provider to use in this session (`anthropic` or `openai`), the model names
   and the reasoning effort; write them in `.env` (ignored) and the key in
   `.runtime/secrets/<provider>_api_key` (ignored). Never print the key, never commit it.
4. Start with P0. Do not open a later phase before the gate of the current one is observed and
   written in `docs/evidence/`.

## Deliverables per phase

Each phase, in order, delivers code, tests, GUI screens where the plan names them, and one
evidence file `docs/evidence/lab-pN.md` with: commit, command, provider, model, reasoning,
expected result, observed result, limitations. Then commit and push on `dev`.

| Phase | Delivers | Gate (from `docs/lab.md`) |
|---|---|---|
| P0 | Init service or `scripts/setup.py` for secrets; `anthropic` and `openai` adapters with key from secret file; `KOPS_MODEL_PROVIDER`, `KOPS_MODEL_NAME`, `KOPS_CLASSIFIER_MODEL`, `KOPS_MODEL_REASONING` in `.env.example`, Compose and the GUI settings panel; allowlist reduced to the two provider hosts; fixture model kept for the test profile | clone, `.env`, `docker compose up` on a machine with only Docker; one page compiled and published from the configured provider |
| P1 | Raw store tables and volume, collector registry, four collectors over `fixtures/meridian/`, rule pre-filter, quarantine records, ntfy notification, run manifests | the three planted items quarantined, ntfy rings, roster restricted, unregistered collector refused, manifest per run |
| P2 | Classifier service: schema call, uncertain-band self-consistency, batching by window and commit batch, thresholds, owner queue, eval report against `expected_tags.json` | every item classified with confidence; report with precision and recall per tag; an item under the threshold waits and the owner's label is stored |
| P3 | Tables source, tag, domain, role, principal and their links; directory import from `org/`; split task for mixed items; one wiki per role through the existing compile, review and publish path | supplier rates only in Finance, profile only in Operations; adding a person to a role recompiles nothing |
| P4 | Audience brief per role in the compile prompt; request contexts; rendering profile table and GUI; the three gates in the chat; the five questions from `eval/questions.json` | Q1 returns script, checklist, code path and 404 per role; a context outside the role gets 404; same role, two people, different form |
| P5 | Gateway with typed read-only operations on a demo target; two-sided refusal of mutating operations; bounded ops agent (max calls, deadline) producing a candidate only | both refusals in the audit; failing health check reported within budget, not fixed |
| P6 | History tables and the lineage page | the roster's lineage names every principal and agent that could have seen it, with dates |
| P7 | Optional, only if Franco asks: k3d, Keycloak, graph export | |

## Rules that do not bend

- The model is never hard-wired and never silently defaulted. No local inference, no Ollama.
- Collectors, generators, rules and lint are deterministic standard-library Python with no
  model call. `fixtures/meridian/` is regenerated, never hand-edited.
- Authorization, persistence, publication, provenance, review, revocation and audit are backend
  enforced. No frontend-only simulation of any of them.
- Need and form never widen the set of pages that rights allowed.
- Fixture output never satisfies a gate. Evidence names the real provider and model.
- Nothing outside the current phase is touched or improved; side findings go in one line in the
  evidence file.
- The repository is public: synthetic data only, canonical fake secrets only, no real company
  or client content, no third-party names.

## Working notes

Keep `docs/status.md` current: phase in progress, blockers, next concrete action. Record
material choices in `docs/decisions.md`. Keep `README.md` accurate as phases close. Before
declaring a phase done or a session safe to end: clean working tree, zero unpushed commits on
`dev`.

Stop and report, without guessing, when: a gate cannot be observed as written; a provider
rejects a documented parameter; a control of the baseline would have to be weakened; a change
would touch `main`.
