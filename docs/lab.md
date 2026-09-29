# Lab: the demo beyond the first delivery

The demo is the product. This file is the plan for the next stage of it, worked on `dev` and
merged to `main` by Franco. The full argument, diagram and tables are in the page "kops Lab
Architecture" (Claude artifact, 29 September 2026); this file holds what a session needs to
pick up the work.

## Frame

- Behind kops sits an LLM wiki in Karpathy's pattern: one immutable raw store filled by
  deterministic collectors (repositories, helpdesk tickets, production logs, wiki pages).
  Collectors never call a model. A collector not in the registry cannot write raw.
- A System One model (Jev, TypeSafe AI) sits between raw and the role wikis and answers typed
  questions per item with a probability: which tags, personal, mixed domains, sensitivity. A
  `local` backend on Ollama answers the same question set for comparison and offline work.
- kops compiles one wiki per role through the existing review gate, with an audience brief per
  role in the compile prompt. Mixed items are split into one item per domain first.
- The return passes three separate gates, in order: rights (role, domain, tag: the only gate
  that refuses), need (audience brief and request context), form (rendering profile per person,
  learned by the chat). Need and form never widen the set of pages.
- Live truth: a gateway with typed read-only operations on a demo app, a bounded ops agent
  (Jev picks the checks, the local model writes the reading), output as a candidate only.
- Lineage per raw item: who could have seen it and when, who did, where it could have gone.

## Synthetic world

`scripts/generate_meridian.py` writes `fixtures/meridian/`: Meridian Ferries, 15 people with
rendering profiles, 8 roles with audience briefs, 6 domains, 35 tags, 19 wiki pages, 8 ADRs,
120 tickets, 201 commits, 2,000 log lines. Planted: a credentials page and two tickets that
must be quarantined, a personal roster that must be ingested restricted and traced, three
mixed pages that must split. Ground truth in `fixtures/meridian/eval/`. Edit the generator,
regenerate, commit both; never hand-edit the output.

## Phases and gates

| Phase | Work | Gate |
|---|---|---|
| P0 | Live model on the existing stack | one page compiled and published from Ollama |
| P1 | Raw store, collector registry, four collectors, pre-filter, ntfy | the three planted items are quarantined and ntfy rings; the roster is in raw; an unregistered collector cannot write; every run has a manifest |
| P2 | Classifier with `jev` and `local` backends, label gate | every raw item has tags with probabilities from both backends; a 0.7 item waits for the owner |
| P3 | Domain chain tables, directory import, split task, role wikis | supplier rates in Finance, supplier profile in Operations, neither elsewhere; adding a person to a role recompiles nothing |
| P4 | Audience briefs, request contexts, rendering profiles, the five questions | Q1 returns a script to L1, a checklist to ops, a code path to a developer, 404 to finance; a context naming a page outside the role gets 404 |
| P5 | Gateway, targets, ops agent | a mutating command is refused twice and both refusals are in the audit; the agent reports a failing health check within budget without trying to fix it |
| P6 | History tables and the lineage page | the roster's lineage names every principal who could have seen it, including the agent, with dates |
| P7 | Optional: k3d, Keycloak, knowledge graph export | |

Each phase ends with an entry in `docs/evidence/` naming the commit, the command and the
observed result.

## Runtime

- The Compose stack is the artifact. It runs the same on Linux, Windows and macOS with Docker;
  no step, script or document assumes a host. Scripts that must run on the host are Python,
  standard library, so that they run wherever `docker compose` runs.
- The model is a runtime choice, not a build choice. `KOPS_MODEL_PROVIDER` selects the
  System Two model: `ollama` (default, `KOPS_MODEL_URL` and `KOPS_MODEL_NAME`), `anthropic`
  (Claude, key in a secret file) or `openai` (Codex models, key in a secret file).
  `KOPS_MODEL_NAME` picks the model and `KOPS_MODEL_REASONING` the effort (`low`, `medium`,
  `high`; mapped to each provider's own parameter, ignored where the model has none). The
  same prompt, schema and gate run against every combination; provider, model and reasoning
  are recorded on every compiled page and answer, and the GUI shows them. Franco selects them
  per session from wherever he is: `.env` on the machine, or the settings panel of the GUI
  with the same variables, without rebuilding anything. `KOPS_CLASSIFIER_BACKEND` selects the System One model: `local`
  (the selected provider with a JSON schema and self-consistency) or `jev`. Ollama on the host
  is reached as `host.docker.internal`, declared with
  `extra_hosts: host.docker.internal:host-gateway` so that the name resolves on Linux as it
  already does on Docker Desktop. A hosted provider is never the silent default: it is a
  value someone put in `.env`, and the evidence names it.
- The stack must come up on a machine that has only Docker: fresh volumes, seed from
  `fixtures/`, a model reachable at the configured URL. Nothing else is installed on the host.

## Baseline

Profile C while building, profile A for the ops agent in P5. Conformity block before agentic
effects. With own and synthetic data the hosted classifier needs no derogation; pointing it at
data that must not leave the perimeter would.
