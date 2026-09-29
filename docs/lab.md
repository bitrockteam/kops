# Lab plan: the demo beyond the first delivery

The demo is the product. This file is the plan for its next stage, worked on `dev` and moved to
`main` by Franco. Solo exploration: Franco and the implementing agent, no other committer, no
reviewer, no branch protection. Everything a session needs to pick up the work is here, in
`docs/lab-design.md` (the components: Compose additions, collectors, data model, return,
gateway, ops agent, lineage) and in `HANDOFF.md` (the unattended run, its models and
orchestration, the stop conditions); the first delivery (merged at `4050225`) is described by `docs/plan.md`,
`docs/architecture-v4.md` and `docs/evidence/implementation.md`.

## What the demo demonstrates

Each claim has an observable proof. A claim without its proof is not demonstrated.

| # | Claim | Proof in the running stack |
|---|---|---|
| D1 | Knowledge is compiled from an immutable raw store filled only by registered, deterministic collectors | A collector not in the registry cannot write; every run leaves a manifest; raw items are never edited in place |
| D2 | Dangerous items never reach a model or a wiki | The planted credentials page and the two tickets with a card number and a password are quarantined by rules before any model call; ntfy rings; the audit shows the quarantine |
| D3 | Every raw item is classified by a System One model with typed answers and a probability, not prose | Each item has tags, domains, personal flag and sensitivity with a confidence; items under the threshold wait in the owner queue; the eval set scores precision and recall per tag |
| D4 | One wiki per audience, compiled through the existing review gate | Supplier rates appear in the Finance wiki, the supplier profile in the Operations wiki, neither elsewhere; every published page carries the model id and effort |
| D5 | The return passes three separate gates: rights, need, form | Q1 returns a phone script to the L1 operator, a checklist to the ops desk, a code path to the developer, and 404 to the finance controller; need and form never widen the set of pages, only rights refuses |
| D6 | The chat adapts the form to the person without changing the substance | The rendering profile is a structured record per principal (length, leads with, format, tone, avoid, own words), visible and editable in the GUI, and the same page returns differently to two people with the same role |
| D7 | Live truth is read through a gateway with typed read-only operations, and an agent stays inside its budget | A mutating command is refused at both ends and both refusals are in the audit; the ops agent reports a failing health check within its call and time budget without trying to fix it |
| D8 | Lineage answers who could have seen an item, who did, where it could have gone | The personal roster's lineage names every principal and agent that could have read it, with dates, including the ops agent |
| D9 | A clone runs the demo, and the model is the account's Claude with nothing to choose | `git clone`, `docker compose up`, `python scripts/model_bridge.py` on a machine with Docker, Python and a signed-in Claude Code; the model and effort reported by the bridge are recorded on every output |
| D10 | The whole demo is driven from the GUI | Every step, from configuring the model to reading a lineage, is done in the browser; no terminal, no API call by hand, no agent session as the interface. `docs/gui-lab.md` is the screen contract |

Agreed limits, stated once: the personality adaptation is a structured profile, not a learned
model of the person; the human review gate stays because a model's judgment is not
demonstrable as trustworthy from inside the demo; no local inference, no GPU, no Ollama, no
API key and no provider choice: the only model is the Claude of the account that runs the
demo, through the signed-in Claude Code CLI on the host, fixed to Sonnet 5 at high effort.

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

The classifier is the same Claude model as everything else, Sonnet 5 at high effort through
the model bridge, called in a dedicated way. Four
techniques stack; the first two are mandatory, the other two are switches.

| Technique | What it does | When it runs |
|---|---|---|
| Rules first | Deterministic pre-filter decides quarantine and obvious facts (space to domain, owner to role) with no model | Always, inside the collector, before any model call |
| Schema call | One call per item through the bridge with a JSON schema: closed tag list, domains, personal flag, sensitivity, one confidence per answer; the model never sees the whole corpus, only the item and the tag catalog | Always, for every item the rules let through |
| Self-consistency | The same call repeated `k` times (default 3) and the agreement ratio replaces the self-reported confidence | Only for items whose first confidence falls in the uncertain band (default 0.4 to 0.8), to bound cost |
| Batching by granularity | Logs are classified per time window and commits per batch, never per line; the bridge runs a few calls in parallel for bulk runs | For the log and repository collectors |

Calibration is part of the phase: `fixtures/meridian/eval/expected_tags.json` scores every
run, and the threshold per question is set from that score, not guessed. Below the threshold
an item waits in the owner queue; the owner's decision is written back as a label and becomes
eval data for the next run. Model, effort, `k` and thresholds are recorded on every
classification.

There is no separate classifier model: the bridge serves one model for classification,
compilation and answers. System One and System Two differ in the schema and the question
set, not in the model.

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
| P0 | Bootstrap without `make` or Bash on the host; the model bridge `scripts/model_bridge.py` (Python, standard library) that runs the signed-in Claude Code CLI with Sonnet 5 at high effort and JSON schema output; the existing broker pointed at the bridge; the Model screen | `git clone`, `docker compose up`, `python scripts/model_bridge.py` on a machine with Docker, Python and a signed-in Claude Code; one page compiled and published, evidence naming the model and effort the bridge reported |
| P1 | Raw store, collector registry, four collectors, rule pre-filter, ntfy | the three planted items are quarantined and ntfy rings; the roster is in raw as restricted; an unregistered collector cannot write; every run has a manifest |
| P2 | Classifier: schema call, self-consistency switch, batching, label gate, owner queue, eval report | every raw item has typed answers with confidence; the eval report shows precision and recall per tag against `expected_tags.json`; an item under the threshold waits for the owner and the owner's label is stored |
| P3 | Domain chain tables, directory import, split task, role wikis | supplier rates in Finance, supplier profile in Operations, neither elsewhere; adding a person to a role recompiles nothing |
| P4 | Audience briefs, request contexts, rendering profiles, the five questions | Q1 returns a script to L1, a checklist to ops, a code path to a developer, 404 to finance; a context naming a page outside the role gets 404; two people with the same role get the same pages in different form |
| P5 | Gateway, targets, ops agent | a mutating command is refused twice and both refusals are in the audit; the agent reports a failing health check within budget without trying to fix it |
| P6 | History tables and the lineage page | the roster's lineage names every principal who could have seen it, including the agent, with dates |
| P7 | Optional: k3d, Keycloak, knowledge graph export | |

Each phase ends with an entry in `docs/evidence/` naming the commit, the command, the model
and effort, and the observed result. Phases are committed and pushed on `dev` as they close.
Each phase also delivers its screens as written in `docs/gui-lab.md`: a phase whose gate can be
observed only from a terminal is not closed. The phases run unattended, one after the other,
in a single Sonnet 5 session that implements and commits, with a Haiku 4.5 verifier that
re-runs every gate independently before the phase closes; `HANDOFF.md` fixes the models, the
launch and the stop conditions.

## Run

The target experience on Franco's machines, each with Docker, Python 3 and a signed-in Claude
Code:

```
git clone git@github.com:bitrockteam/kops.git
cd kops
git checkout dev
cp .env.example .env              # port only
docker compose up --build
python scripts/model_bridge.py    # in a second terminal, on the host
```

Today the repository still needs `make setup` (Bash, `scripts/setup.sh`) to generate the
per-service secrets under `.runtime/secrets`, and the broker only speaks to local
OpenAI-compatible endpoints. Those are the two gaps of P0: an init service in Compose (or
`python scripts/setup.py`, standard library) that generates missing secrets into a volume, and
the model bridge, so that the six lines above are the whole instruction set. `make` stays as
a convenience, never as the only path.

## Runtime

- The Compose stack is the artifact. It runs the same on Linux, Windows and macOS with Docker;
  no step, script or document assumes a host beyond Python 3 and a signed-in Claude Code.
  Scripts that run on the host are Python, standard library.
- The model is the Claude of the account that runs the demo, fixed to Sonnet 5 at high
  effort. `scripts/model_bridge.py` listens on the host (`127.0.0.1:8090`, reached from the
  containers as `host.docker.internal:8090`, the allowlist of the first delivery) and turns
  each request into one `claude -p` invocation with `--model`, `--effort high`,
  `--output-format json`, `--json-schema` when the caller sends a schema, `--tools ""` and
  `--no-session-persistence`. It returns the text or the parsed object plus the model id and
  usage that the CLI reports. No API key exists anywhere; the CLI's own sign-in is the
  credential, and it stays on the host.
- Nothing selects the model by hand: no variable in `.env`, no panel in the GUI. The bridge
  accepts a `--model` argument on its own command line for Franco's experiments; the GUI and
  the evidence show whatever the bridge reports.
- The model id, the effort, and for classifications `k` and thresholds are recorded on every
  compiled page, answer and classification, and the GUI shows them. An unreachable bridge is
  an explicit failed state, never a canned answer.
- The test profile keeps a fixture model service that speaks the same request shape as the
  bridge, so `docker compose --profile test` runs without Claude Code. Fixture output never
  satisfies a gate.

## Cost bound

The cost is usage of the account's Claude seat, not money per call. One full classification of
the synthetic world is about 400 schema calls (pages, ADRs, tickets, commit batches, log
windows), each a separate `claude -p` process of a few seconds, plus self-consistency on the
uncertain band: the bridge runs a small number of them in parallel and the run takes minutes,
not hours. Compilation of eight role wikis is the larger use and runs only through the review
gate. The seat's rate limit is the bound; a limit hit is reported as a failed job, and the
run resumes from the queue.

## Baseline

Profile C while building, profile A for the ops agent in P5. Conformity block before agentic
effects. With own and synthetic data the classifier on the account's Claude needs no
derogation; pointing it at
data that must not leave the perimeter would.
