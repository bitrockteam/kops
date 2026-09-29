# Lab design: the components behind the plan

`docs/lab.md` says what the lab stage demonstrates and in which phases. This file holds the
design that the phases implement: Compose additions, the collector registry, the data model,
the return, the gateway, the ops agent and lineage. It is the reference for the implementing
session; where a phase finds a better shape, `docs/decisions.md` records the change and this
file is updated in the same commit.

## Compose additions

The Compose stack stays the artifact. The new services join `compose.yaml` with the same
hardening as the existing ones: read-only filesystem, all capabilities dropped, own PostgreSQL
role, own secrets, internal network. No service on the host, no Bash on the host.

```yaml
services:
  collector:
    build: ./collector
    command: ["python", "-m", "collector.run", "--registry", "/etc/kops/collectors.yaml"]
    volumes:
      - raw_data:/var/lib/kops/raw                     # the only service that writes raw
      - ./collectors.yaml:/etc/kops/collectors.yaml:ro
      - ./fixtures/meridian:/srv/meridian:ro
    environment:
      KOPS_AUDIT_URL: http://audit:8083
      KOPS_NOTIFY_URL: http://notify:8085
      KOPS_PREFILTER_VERSION: "1"
    networks: [backend]
  classifier:
    build: ./classifier
    volumes:
      - raw_data:/var/lib/kops/raw:ro
    environment:
      KOPS_MODEL_ENDPOINT: http://host.docker.internal:8090      # the model bridge on the host
      KOPS_CLASSIFIER_K: ${KOPS_CLASSIFIER_K:-3}                  # self-consistency samples, uncertain band
      KOPS_AUDIT_URL: http://audit:8083
      KOPS_CONTENT_URL: http://content:8084
    networks: [backend, model-egress]
  gateway:
    build: ./gateway
    secrets: [gateway_ssh_key, gateway_observer_dsn, gateway_agent_token]
    environment:
      KOPS_AUDIT_URL: http://audit:8083
    networks: [backend, targets]
  opsagent:
    build: ./opsagent
    secrets: [gateway_agent_token]
    environment:
      KOPS_GATEWAY_URL: http://gateway:8086
      KOPS_MODEL_ENDPOINT: http://host.docker.internal:8090
      KOPS_AGENT_MAX_CALLS: "12"
      KOPS_AGENT_DEADLINE_SECONDS: "180"
    networks: [backend, model-egress]
  notify:
    image: binwiederhier/ntfy:v2.11.0
    command: serve
    networks: [backend]
    ports: ["127.0.0.1:8085:80"]
  demo-web:                                            # the system whose truth the lab tells
    build: ./targets/web
    networks: [targets]
  demo-db:
    image: postgres:18.0-alpine
    volumes: [./targets/db/init:/docker-entrypoint-initdb.d:ro]
    networks: [targets]
  target-ssh:
    build: ./targets/ssh                               # sshd with a ForceCommand wrapper
    networks: [targets]
networks:
  targets:
    internal: true
```

No service holds a model credential. `model-egress` allows exactly `host.docker.internal`,
where the model bridge listens; cloud metadata, link-local addresses and redirects stay
denied as in the first delivery.

## Model bridge

`scripts/model_bridge.py` is a Python standard-library HTTP server on the host, bound to
`127.0.0.1:8090`. It exists because the demo's model is the Claude of the account that runs
it, reached through the signed-in Claude Code CLI, and containers cannot run that CLI.

- Request: `POST /v1/complete` with `system`, `prompt`, optional `schema` (JSON Schema) and
  `max_tokens`. Response: `text` or `object`, plus `model` (the id the CLI reports in its JSON
  result), `effort`, `usage`, `duration_ms`, `bridge_version`. `GET /health` returns model,
  effort and CLI version, which the Model screen shows.
- Each request runs one process: `claude -p --model sonnet --effort high --output-format json
  --tools "" --no-session-persistence`, with `--json-schema` when a schema is given, the prompt
  on standard input. The bridge validates the object against the schema and retries once on a
  mismatch; a second mismatch is a failed call with the raw output attached. Flags verified on
  Claude Code 2.1.280.
- The bridge strips `CLAUDECODE` and `CLAUDE_CODE_*` from the child environment so that it
  can be started from inside an agent session; `start` and `stop` subcommands keep a pid file
  under `.runtime/`, and the unattended run stops it before it ends.
- A `--model` and `--effort` on the bridge's own command line exist for Franco's experiments;
  the GUI never selects a model and the evidence records what the bridge reported.
- Concurrency: at most four child processes at a time; requests beyond that queue. A rate
  limit answer from the CLI is returned as a failed call with `retry_after`, never retried
  silently.

## Collectors and the raw store

Deterministic Python, standard library, no model. A registry file lists each collector with
its kind, scope, owner and the pre-filter version it must run. A run reads the registry,
fetches, pre-filters, writes content-addressed items to `raw/<collector>/<sha256>.json`, writes
one manifest per run and reports counts and quarantines to the audit.

```yaml
# collectors.yaml
collectors:
  - name: wiki
    kind: file
    scope: {path: /srv/meridian/wiki/*.md, adr: /srv/meridian/adr/*.md}
    owner: franco
  - name: tickets
    kind: file
    scope: {path: /srv/meridian/tickets/tickets.json}
    owner: franco
  - name: repo
    kind: file
    scope: {path: /srv/meridian/repo/commits.json, batch: 20}
    owner: franco
  - name: logs
    kind: file
    scope: {path: /srv/meridian/logs/*, window: 15m}
    owner: franco
prefilter:
  version: 1
  rules: [cloud-key, card-luhn, iban, private-key, password-line, unknown-space]
  on_hit: quarantine-and-notify                        # never written to raw
```

Two rules make this the authorized view: a collector not in the registry cannot write, and a
collector whose scope changed since registration is refused until the owner re-registers it.
Raw items are never edited in place; a new run revises them and dependency tracking marks
what goes stale. The `repo` and `logs` collectors produce batched items (commits per batch,
log lines per window) so that the classifier never runs per line.

## Data model

The chain source, tag, domain, role, principal as tables, plus the request context and the
rendering profile. The existing audience becomes the role. The existing admission rule
(readers of a page contained in the intersection of the readers of its sources) stays and
gets one more input: an item is admissible for a role only if every tag on it belongs to a
domain granted to that role.

```sql
-- db/lab/20-domains.sql
create table tags        (tag text primary key, description text);
create table domains     (domain text primary key, description text);
create table domain_tags (domain text references domains, tag text references tags,
                          primary key (domain, tag));
create table roles       (role text primary key, description text, audience_brief jsonb);
create table role_domains(role text references roles, domain text references domains,
                          granted_by text not null, granted_at timestamptz default now(),
                          primary key (role, domain));
create table principals  (principal text primary key,
                          kind text check (kind in ('person','agent','service')));
create table principal_roles(principal text references principals, role text references roles,
                          source text not null,            -- 'directory' | 'manual'
                          primary key (principal, role));
create table item_tags   (item_id text, tag text references tags, probability numeric,
                          decided_by text not null,        -- 'model:<model id>' | 'rule' | 'owner:<name>'
                          question_set text not null,
                          primary key (item_id, tag));
create table classifications (item_id text, run_id text, answers jsonb not null,
                          model text, effort text, k int, thresholds jsonb,
                          at timestamptz default now(), primary key (item_id, run_id));
create table request_contexts (context text primary key, description text);
                          -- 'desk', 'on-call', 'functional', 'review'
create table rendering_profiles (principal text references principals, version int,
                          profile jsonb not null,          -- length, leads_with, format, tone, avoid, own_words
                          changed_by text not null, at timestamptz default now(),
                          primary key (principal, version)); -- read by the renderer only, never by admission
create table role_domains_history    (like role_domains, op text, at timestamptz default now());
create table principal_roles_history (like principal_roles, op text, at timestamptz default now());
```

Directory import: `fixtures/meridian/org/` (people, roles, domains, rendering profiles) is
imported by a Python script into the tables above with `source = 'directory'`; manual rows
survive a re-import; every change lands in the history tables and the audit.

| Change | Effect |
|---|---|
| `domain_tags` or `role_domains` | Role wikis that depend on the tag or domain go stale; the worker recompiles through the existing review gate |
| A raw item revised by a new collector run | Dependent items and pages go stale, existing dependency tracking |
| `principal_roles` | No regeneration; reads are re-evaluated immediately, history and saved answers included |
| Directory re-import | Directory rows rewritten, manual rows kept, history and audit updated |
| `rendering_profiles` | Nothing recompiles; only the rendering of the next answer changes |

Distillation: an item whose tags span more than one domain is never admitted as is. The worker
runs a split task with a fixed output schema: one derived item per domain, each carrying only
that domain's facts, each with the mixed item as provenance. The supplier rate card becomes a
supplier item for Operations and a rates item for Finance.

## The return

Authentication says who is asking. Authorization says what they may see. Neither says what is
useful to them, nor how they read. Three gates, in this order; only the first can refuse.

| Gate | Question | Mechanism | Example: an L1 operator with a customer on the line and a failed payment |
|---|---|---|---|
| 1. Rights | May this principal see this at all? | Role to domain to tag: the existing admission at compile time, re-checked at every read. Directory import sets roles; history keeps every change | Role helpdesk-l1, domain customer-support. The architecture page is not hers. A person entitled to everything passes this gate for every page: that is why the next two exist |
| 2. Need | Of what they may see, what does this reader need for this job, now? | An audience brief per role (who they are, what they need, what they must not get, the form) goes into the compile prompt: the role wiki is written for the audience, not filtered from the whole. A request context (desk, on-call, functional, review) selects inside the role wiki | Her wiki holds a short script split out of the runbook by the compiler: what to say, one check in the back office, when to open a P2. No cluster names, no commands, no supplier terms. Granting her another domain tomorrow would not change her L1 page |
| 3. Form | How does this person read best? | A rendering profile per principal: length, what comes first, format, tone, words to avoid, the person's own words mapped to canonical terms. Proposed by the chat from the conversation, applied only when the person accepts, stored in its own versioned table, read by the renderer only | She says "the booking code" and "the payment thing"; the answer uses her words, puts the customer-facing sentence first and the escalation condition in bold. The on-call engineer at night gets the same substance starting with "you may open a P1 now" |

Substance is decided by gates 1 and 2, form by gate 3. The invariant: rights decide the set of
pages; need and form select and shape within that set and can never add to it. A context or a
profile that names a page outside the role gets a 404, not a page. Every answer stores its
gate trace as written in `docs/gui-lab.md`.

The demonstration is `fixtures/meridian/eval/questions.json`: five questions, each with the
expected return per role, and for two of them per person. Same store, several returns, one
authorization model.

## Live truth: the gateway

A FastAPI service with a fixed list of operations. There is no generic "run this" endpoint.
An operation names a target, takes typed parameters, validates them, executes with a
credential only the gateway holds, and returns structured output. The caller is a service
account identified by a bearer token; the token maps to an allowed set of operations.

```yaml
# gateway/operations.yaml
operations:
  web.health:          {target: http, params: [],               cmd: "GET http://demo-web:8000/health"}
  web.metrics:         {target: http, params: [],               cmd: "GET http://demo-web:8000/metrics"}
  ssh.uptime:          {target: ssh,  params: [],               cmd: "uptime"}
  ssh.disk:            {target: ssh,  params: [],               cmd: "df -h"}
  ssh.ports:           {target: ssh,  params: [],               cmd: "ss -tlnp"}
  ssh.log_tail:        {target: ssh,  params: [unit, lines],    cmd: "tail -n {lines} /var/log/{unit}.log"}
  db.table_counts:     {target: db,   params: [],               sql: "select relname, n_live_tup from pg_stat_user_tables"}
  db.recent_failures:  {target: db,   params: [minutes],        sql: "select * from bookings where status='failed' and at > now() - interval '{minutes} minutes' limit 50"}
params:
  unit:    {pattern: "^[a-z0-9-]{1,40}$"}
  lines:   {int: [1, 500]}
  minutes: {int: [1, 1440]}
```

- Two checks per SSH call. The gateway renders the command from the template and the validated
  parameters. The target's `ForceCommand` wrapper matches it again against the same allowlist
  file, logs it and exits 126 on mismatch. A mutating command never runs even if the gateway
  is wrong.
- Database: only the listed statements, through an observer role with
  `default_transaction_read_only = on` and a 5 second statement timeout.
- Audit: before, `gateway_call_attempt` with actor, operation, parameters, correlation id;
  after, `gateway_call_result` with status, bytes and duration. A blocked call is a third
  event and a ntfy post.
- Limits: per-token rate limit, 10 second timeout per call, 256 KB output cap, two concurrent
  calls per token.

Targets: `demo-web` and `demo-db` are a small booking-style service with a health endpoint, a
few tables and a log with request ids, latencies and occasional failures; its runbook is in the
synthetic wiki, its incidents in the synthetic tickets, its logs among the fixtures, its live
state behind the gateway. `target-ssh` is Alpine with openssh-server, user `observer`,
key-only, `ForceCommand /usr/local/bin/observe`.

## The ops agent

- Identity: service account `opsagent`, principal kind `agent`, role `ops-desk`, a gateway
  token from a secret file. It is one of the principals of the person selector, so lineage
  and audit name it like a person.
- Loop: input is a ticket and its context. The model, with the same schema call as the
  classifier, says which operations of the closed list are relevant, one confidence
  per operation. The gateway runs those above 0.7, in order. A second schema call says whether any result
  is anomalous. A prose call writes the reading with the raw results
  quoted. Budget: `KOPS_AGENT_MAX_CALLS` and `KOPS_AGENT_DEADLINE_SECONDS`; reaching either
  ends the loop with a partial reading that says so. Every tool result enters the context as
  quoted data, never as an instruction.
- Output: a live-view item with question, decisions with probabilities, calls, raw results,
  reading, timestamps, model and effort. It enters kops as a private candidate for the
  ops-desk wiki, never a published page. The GUI shows it next to the compiled runbook.
- No shell, no key other than the gateway token, no network beyond the gateway and the
  model bridge.

## Lineage

One GUI page per raw item, three answers computed from tables the lab already keeps.

| Question | Computed from |
|---|---|
| Who could have seen it, and when | `item_tags` joined to `domain_tags`, `role_domains_history` and `principal_roles_history` over the interval since ingest: the principals, people and agents, whose roles covered the item's tags at each moment |
| Who did see it | Audit read events on pages and answers whose input manifest contains the item; existing provenance |
| Where it could have gone | Pages, answers, promoted candidates, live views and exports that depend on it, each with its own reader set, each a link to the same page |

The check is the personal roster after a full run of the demo: if the page answers all three
questions from stored records, D8 holds. If an answer needs a log that was not kept, that is
the finding to record in `docs/evidence/lab-p6.md`, not something to patch around.
