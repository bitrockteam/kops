# Implementation handoff: the lab stage

**Status:** the first delivery is merged on `main` at `4050225`. The next stage is planned in
`docs/lab.md`, designed in `docs/lab-design.md` and starts from `dev`. Nothing of it is
implemented yet. This document is the assignment for the session that implements it, and that
session runs unattended: Franco launches it from a terminal and does not answer questions
while it runs.

## Who is here

Franco Geraci and one implementing session. Nobody else commits, reviews or approves. The Git
identity is Franco's (`Franco Geraci`, `Voloire` or `Voloirex`, address
`6276639+Voloire@users.noreply.github.com`); do not change it and do not add any co-author,
generation or attribution trailer. Two branches: `dev` for the work, `main` when Franco says.
No feature branches, no pull requests, no branch protection.

## Before launch (Franco)

The session cannot ask for anything, so these exist before it starts:

1. `.env` copied from `.env.example` with `KOPS_MODEL_PROVIDER`, `KOPS_MODEL_NAME`,
   `KOPS_CLASSIFIER_MODEL` and `KOPS_MODEL_REASONING` filled in.
2. The API key in `.runtime/secrets/<provider>_api_key` (create the directory if missing).
   Never in `.env`, never in Git, never printed.
3. Docker and Compose running on the machine. Nothing else is required on the host.
4. A permission allowlist, so that the run needs no confirmation without disabling
   confirmations altogether (baseline C11). Franco creates `.claude/settings.json` in the
   repository root by hand; the session never writes its own permissions:

```json
{
  "permissions": {
    "allow": [
      "Bash(docker compose:*)", "Bash(docker:*)",
      "Bash(git status:*)", "Bash(git log:*)", "Bash(git diff:*)",
      "Bash(git add:*)", "Bash(git commit:*)", "Bash(git push origin dev:*)",
      "Bash(python:*)", "Bash(pytest:*)", "Bash(curl:*)",
      "Edit", "Write", "Agent"
    ],
    "deny": [
      "Bash(git push --force:*)", "Bash(git checkout main:*)", "Bash(git switch main:*)",
      "Bash(git merge:*)", "Bash(git reset --hard:*)",
      "Read(./.env)", "Read(./.runtime/**)"
    ]
  }
}
```

5. The launch, from the repository root, in non-interactive mode:

```bash
claude --model sonnet -p "Read HANDOFF.md and run the next open phase of docs/lab.md, then the following ones, until a stop condition. Report at the end."
```

The session never asks for a confirmation and never uses an interactive question: a tool call
outside the allowlist is denied, not prompted, and the session treats a denial as a stop
condition to record, never as something to work around.

## Models and orchestration

The session is Sonnet 5 at high effort and is the only accountable writer of the repository:
every file change, commit and push is made by the session itself (baseline C02, one writer per
artifact). Two subagents exist, defined in `~/.claude/agents/`, and are the whole
orchestration:

| Role | Agent | Model, effort | Used for | Never for |
|---|---|---|---|---|
| Implement | the session | Sonnet 5, high | all code, Compose, SQL, GUI, docs, evidence, commits | asking Franco |
| Verify a gate | `verifica` | Haiku 4.5, high | running the gate's command and comparing the observed output with the expected one, from the running stack, without the session's narrative (C03) | fixing anything |
| Isolated piece | `esecutore` | Sonnet 5, high | optional: one specified, self-contained piece with its own files (a generator change, a target container, a test suite), when the session's context is better spent elsewhere | a file the session or another agent is writing |

Rules:

- Declare model and effort in every subagent prompt. Cap the report: 300 words for
  implementation or verification, result first. Give the subagent the whole context in the
  prompt; it does not inherit the session.
- One agent per file at a time. While an `esecutore` runs, the session does not edit its files.
- No Opus, Fable or Astra subagent. If a phase needs the plan redesigned (a gate that turns out
  unreachable, a control that conflicts with the baseline), that is a stop condition, not an
  escalation the session performs on its own.
- Codex is not used in the unattended run. Franco may ask for a `/codex:review` afterwards.
- Each gate is verified by `verifica` before the phase closes; the evidence file quotes its
  verdict and the command it ran. A gate the session declares met without that verdict is not
  met.

The runtime models of the demo are a separate matter and come from `.env`: System Two
(`KOPS_MODEL_NAME`) for compilation, answers and the agent's reading; System One
(`KOPS_CLASSIFIER_MODEL`) for classification and the agent's decisions. The table below says
which phase exercises which, so that the evidence names the model actually used.

## The unattended run

1. `git status -sb` on `dev`, clean tree, remote on SSH, identity as above. Do not touch `main`.
2. Read, in this order: `AGENTS.md`; `docs/lab.md` (D1 to D10, phases and gates);
   `docs/lab-design.md` (Compose, collectors, data model, return, gateway, agent, lineage);
   `docs/gui-lab.md` (the screens; the demo is driven entirely from the GUI, every phase ships
   its screens); `docs/status.md` (which phase is open); `README.md`; `docs/architecture-v4.md`,
   `docs/gui-walkthrough.md` and `docs/evidence/implementation.md` (what the first delivery
   built, so that nothing is rebuilt or weakened); `scripts/generate_meridian.py` and
   `fixtures/meridian/manifest.json`; the agentic baseline in the shared memory
   (`baseline-agenti/SCHEDA.md`), profile C while building, profile A for the ops agent.
3. Check that `.env` and the key file exist and that the provider answers a minimal call
   through the stack. If either is missing or the provider refuses, write the fact in
   `docs/status.md`, commit, push and stop: nothing else can be verified.
4. Run the open phase: implement, bring the stack up, run the gate, have `verifica` confirm
   it, write `docs/evidence/lab-pN.md`, update `docs/status.md` and `README.md` where the
   phase changed what a reader can do, commit and push on `dev`.
5. Continue with the next phase. Stop at P7 unless `docs/status.md` says Franco asked for it.
6. When context compaction is near: finish the current step, commit, push, record the exact
   next action in `docs/status.md`, then stop. Franco relaunches the same command and the new
   session resumes from `docs/status.md`.

At the end, and at every stop, the last message states: phases closed with their commits,
the phase open and its next action, what was not verified.

## Deliverables per phase

Each phase, in order, delivers code, tests, GUI screens as written in `docs/gui-lab.md`, and
one evidence file `docs/evidence/lab-pN.md` with: commit, command, provider, model, reasoning,
expected result, observed result, the `verifica` verdict, a baseline conformity block
(profile, controls touched, state as verified, partial, not met, unknown or not applicable),
limitations and side findings in one line each.

| Phase | Delivers | Runtime model exercised | Gate (from `docs/lab.md`) |
|---|---|---|---|
| P0 | Init service or `scripts/setup.py` for secrets; `anthropic` and `openai` adapters with key from secret file; the four runtime variables in `.env.example`, Compose and the GUI settings panel; allowlist reduced to the two provider hosts; fixture model kept for the test profile | System Two | clone, `.env`, `docker compose up` on a machine with only Docker; one page compiled and published from the configured provider |
| P1 | Raw store tables and volume, collector registry, four collectors over `fixtures/meridian/`, rule pre-filter, quarantine records, ntfy notification, run manifests, Collect screen | none | the three planted items quarantined, ntfy rings, roster restricted, unregistered collector refused, manifest per run |
| P2 | Classifier service: schema call, uncertain-band self-consistency, batching by window and commit batch, thresholds, owner queue, eval report against `expected_tags.json`, Classify screen | System One | every item classified with confidence; report with precision and recall per tag; an item under the threshold waits and the owner's label is stored |
| P3 | Tables source, tag, domain, role, principal and their links; directory import from `org/`; split task for mixed items; one wiki per role through the existing compile, review and publish path; person selector | System Two | supplier rates only in Finance, supplier profile only in Operations; adding a person to a role recompiles nothing |
| P4 | Audience brief per role in the compile prompt; request contexts; rendering profile table and editor; the three gates and the gate trace in the chat; the five questions from `eval/questions.json`; Ask screen | System Two | Q1 returns script, checklist, code path and 404 per role; a context outside the role gets 404; same role, two people, different form |
| P5 | Gateway with typed read-only operations on the demo targets; two-sided refusal of mutating operations; bounded ops agent producing a candidate only; Live screen | both | both refusals in the audit; failing health check reported within budget, not fixed |
| P6 | History tables and the Lineage screen | none | the roster's lineage names every principal and agent that could have seen it, with dates |
| P7 | Only if Franco asks in `docs/status.md`: k3d, Keycloak, graph export | | |

## Rules that do not bend

- The model is never hard-wired and never silently defaulted. No local inference, no Ollama.
- Everything is operated from the GUI. A gate that can be observed only from a terminal, a
  script or an agent session is not met; the screen that shows it is part of the phase.
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
- No question to Franco, no interactive prompt, no listener left running, no polling loop. A
  missing decision is a stop condition, written in `docs/status.md`.

## Stop conditions

Stop, after committing and pushing what is consistent, and write the reason in
`docs/status.md`, when: a gate cannot be observed as written after two attempts; `verifica`
fails a gate twice on the same phase; a provider rejects a documented parameter; a control of
the baseline would have to be weakened; a change would touch `main`; the plan would need a
redesign; a secret would have to be printed or committed to proceed.
