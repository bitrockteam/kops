# Lab plan: the demo beyond the first delivery

The demo is the product. This file is the plan for its next stage, worked on `dev` and moved to
`main` by Franco. Solo exploration: Franco and the implementing agent, no other committer, no
reviewer, no branch protection. Everything a session needs to pick up the work is here and in
`HANDOFF.md`; the first delivery (merged at `4050225`) is described by `docs/plan.md`,
`docs/architecture-v4.md` and `docs/evidence/implementation.md`.

## What the demo demonstrates

Each claim has an observable proof. A claim without its proof is not demonstrated.

| # | Claim | Proof in the running stack |
|---|---|---|
| D1 | Knowledge is compiled from an immutable raw store filled only by registered, deterministic collectors | A collector not in the registry cannot write; every run leaves a manifest; raw items are never edited in place |
| D2 | Dangerous items never reach a model or a wiki | The planted credentials page and the two tickets with a card number and a password are quarantined by rules before any model call; ntfy rings; the audit shows the quarantine |
| D3 | Every raw item is classified by a System One model with typed answers and a probability, not prose | Each item has tags, domains, personal flag and sensitivity with a confidence; items under the threshold wait in the owner queue; the eval set scores precision and recall per tag |
| D4 | One wiki per audience, compiled through the existing review gate | Supplier rates appear in the Finance wiki, the supplier profile in the Operations wiki, neither elsewhere; every published page carries provider, model and reasoning |
| D5 | The return passes three separate gates: rights, need, form | Q1 returns a phone script to the L1 operator, a checklist to the ops desk, a code path to the developer, and 404 to the finance controller; need and form never widen the set of pages, only rights refuses |
| D6 | The chat adapts the form to the person without changing the substance | The rendering profile is a structured record per principal (length, leads with, format, tone, avoid, own words), visible and editable in the GUI, and the same page returns differently to two people with the same role |
| D7 | Live truth is read through a gateway with typed read-only operations, and an agent stays inside its budget | A mutating command is refused at both ends and both refusals are in the audit; the ops agent reports a failing health check within its call and time budget without trying to fix it |
| D8 | Lineage answers who could have seen an item, who did, where it could have gone | The personal roster's lineage names every principal and agent that could have read it, with dates, including the ops agent |
| D9 | The stack is machine independent and the model is a runtime choice | `git clone`, `.env`, `docker compose up` on Linux, Windows and macOS with only Docker; provider, model and reasoning are chosen per session and recorded on every output |
| D10 | The whole demo is driven from the GUI | Every step, from configuring the model to reading a lineage, is done in the browser; no terminal, no API call by hand, no agent session as the interface. `docs/gui-lab.md` is the screen contract |

Agreed limits, stated once: the personality adaptation is a structured profile, not a learned
model of the person; the human review gate stays because a hosted model's judgment is not
demonstrable as trustworthy from inside the demo; no local inference, no GPU, no Ollama.

## Frame

- Behind kops sits an LLM wiki in Karpathy's pattern: one immutable raw store filled by
  deterministic collectors (repositories, helpdesk tickets, production logs, wiki pages).
  Collectors never call a model. A collector not in the registry cannot write raw.
- A pre-filter of deterministic rules runs inside the collectors: canonical secret patterns
  (card numbers, cloud keys, password lines), personal data markers, unknown spaces. What the
  rules catch is quarantined and never reaches a model.
- A System One classifier sits between raw and the role wikis and answers a fixed question set
  per item with typed values and a confidence (see the next section).
- kops compiles one wiki per role through the existing review gate, with an audience brief per
  role in the compile prompt. Mixed items are split into one item per domain first.
- The return passes three separate gates, in order: rights (role, domain, tag: the only gate
  that refuses), need (audience brief and request context), form (rendering profile per
  person, kept by the chat). Need and form never widen the set of pages.
- Live truth: a gateway with typed read-only operations on a demo app, a bounded ops agent
  that picks checks from a closed list and writes a reading, output as a candidate only.
- Lineage per raw item: who could have seen it and when, who did, where it could have gone.

## System One: the classifier without a dedicated product

The classifier is the runtime-selected hosted provider, called in a dedicated way. Four
techniques stack; the first two are mandatory, the other two are switches.

| Technique | What it does | When it runs |
|---|---|---|
| Rules first | Deterministic pre-filter decides quarantine and obvious facts (space to domain, owner to role) with no model | Always, inside the collector, before any model call |
| Schema call | One call per item to `KOPS_CLASSIFIER_MODEL` with a JSON schema: closed tag list, domains, personal flag, sensitivity, one confidence per answer; reasoning `low`; the model never sees the whole corpus, only the item and the tag catalog | Always, for every item the rules let through |
| Self-consistency | The same call repeated `k` times (default 3) and the agreement ratio replaces the self-reported confidence | Only for items whose first confidence falls in the uncertain band (default 0.4 to 0.8), to bound cost |
| Batching by granularity | Logs are classified per time window and commits per batch, never per line; both providers' batch endpoints are allowed for bulk runs | For the log and repository collectors |

Calibration is part of the phase: `fixtures/meridian/eval/expected_tags.json` scores every
run, and the threshold per question is set from that score, not guessed. Below the threshold
an item waits in the owner queue; the owner's decision is written back as a label and becomes
eval data for the next run. Provider, model, reasoning, `k` and thresholds are recorded on every
classification.

`KOPS_CLASSIFIER_MODEL` defaults to the provider's small model; `KOPS_MODEL_NAME` stays the
System Two model for compilation and answers. Both come from `.env` or the GUI settings panel.

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
| P0 | Machine-independent bootstrap (no `make`, no Bash on the host), hosted providers `anthropic` and `openai` with keys from secret files, provider/model/reasoning from `.env` and the GUI, live model on the existing stack | `git clone`, `.env`, `docker compose up` on a machine with only Docker; one page compiled and published from the configured provider, evidence naming provider, model and reasoning |
| P1 | Raw store, collector registry, four collectors, rule pre-filter, ntfy | the three planted items are quarantined and ntfy rings; the roster is in raw as restricted; an unregistered collector cannot write; every run has a manifest |
| P2 | Classifier: schema call, self-consistency switch, batching, label gate, owner queue, eval report | every raw item has typed answers with confidence; the eval report shows precision and recall per tag against `expected_tags.json`; an item under the threshold waits for the owner and the owner's label is stored |
| P3 | Domain chain tables, directory import, split task, role wikis | supplier rates in Finance, supplier profile in Operations, neither elsewhere; adding a person to a role recompiles nothing |
| P4 | Audience briefs, request contexts, rendering profiles, the five questions | Q1 returns a script to L1, a checklist to ops, a code path to a developer, 404 to finance; a context naming a page outside the role gets 404; two people with the same role get the same pages in different form |
| P5 | Gateway, targets, ops agent | a mutating command is refused twice and both refusals are in the audit; the agent reports a failing health check within budget without trying to fix it |
| P6 | History tables and the lineage page | the roster's lineage names every principal who could have seen it, including the agent, with dates |
| P7 | Optional: k3d, Keycloak, knowledge graph export | |

Each phase ends with an entry in `docs/evidence/` naming the commit, the command, the provider
and model, and the observed result. Phases are committed and pushed on `dev` as they close.
Each phase also delivers its screens as written in `docs/gui-lab.md`: a phase whose gate can be
observed only from a terminal is not closed.

## Run

The target experience on any machine with Docker:

```
git clone git@github.com:bitrockteam/kops.git
cd kops
git checkout dev
cp .env.example .env        # provider, model, reasoning, classifier model
docker compose up --build
```

Today the repository still needs `make setup` (Bash, `scripts/setup.sh`) to generate the
per-service secrets under `.runtime/secrets`, and the model adapters only accept local
endpoints. Those are the two gaps of P0: an init service in Compose (or `python
scripts/setup.py`, standard library) that generates missing secrets into a volume, and provider
adapters for the two hosted APIs with the key read from a secret file, so that the five lines
above are the whole instruction set on Linux, Windows and macOS. `make` stays as a
convenience, never as the only path.

## Runtime

- The Compose stack is the artifact. It runs the same on Linux, Windows and macOS with Docker;
  no step, script or document assumes a host. Scripts that must run on the host are Python,
  standard library, so that they run wherever `docker compose` runs.
- The model is a runtime choice, not a build choice. `KOPS_MODEL_PROVIDER` selects the
  provider: `anthropic` (Claude models) or `openai` (Codex models). `KOPS_MODEL_NAME` picks the
  System Two model, `KOPS_CLASSIFIER_MODEL` the System One model, `KOPS_MODEL_REASONING` the
  effort (`low`, `medium`, `high`, mapped to each provider's own parameter and ignored where a
  model has none). The API key is read from `.runtime/secrets/<provider>_api_key`, never from
  `.env`, never committed. The same prompts, schemas and gates run against every combination.
- The allowlist of model hosts holds exactly the two provider APIs; cloud metadata, link-local
  and redirects stay denied as in the first delivery. There is no default provider: an empty
  `KOPS_MODEL_PROVIDER` makes the GUI show the settings panel and refuse to compile.
- Provider, model, reasoning and, for classifications, `k` and thresholds are recorded on every
  compiled page, answer and classification, and the GUI shows them. Franco selects them per
  session from wherever he is: `.env` on the machine, or the settings panel of the GUI with the
  same variables, without rebuilding anything.
- The test profile keeps a fixture model service that speaks the OpenAI-compatible shape, so
  `docker compose --profile test` runs without a key. Fixture output never satisfies a gate.

## Cost bound

Order of magnitude for one full classification of the synthetic world with the provider's small
model at `low` reasoning: about 400 schema calls (pages, ADRs, tickets, commit batches, log
windows) of one to two thousand tokens each, plus self-consistency on the uncertain band. That
is cents per run, so the eval loop can be repeated freely. Compilation of eight role wikis with
the System Two model is the larger cost and runs only through the review gate.

## Baseline

Profile C while building, profile A for the ops agent in P5. Conformity block before agentic
effects. With own and synthetic data the hosted classifier needs no derogation; pointing it at
data that must not leave the perimeter would.
