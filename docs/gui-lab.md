# Guided GUI contract: the lab stage

The first delivery's GUI contract is `docs/gui-walkthrough.md`: ten stages, a persona
selector, an evidence panel, a status timeline, admin-only failure scenarios. That contract
stays. This file says what the lab stage adds or changes, so that Franco can configure the
model and follow every step of the demo from the browser without a terminal. Every screen shows
backend state; every action goes through the protected API; nothing here is a frontend-only
simulation.

## Layout changes

- Persistent header adds: provider, System Two model, System One model, reasoning effort, and
  the run in progress. Empty provider shows a red "no model configured" chip and a link to
  Settings.
- Persona selector becomes a person selector: the 15 people of Meridian Ferries plus the
  `ops-agent` service account, each with their roles from the directory import. Picking a person
  sets rights (roles), need (audience briefs of those roles) and form (that person's rendering
  profile). A separate "operator" toggle keeps the admin-only controls of the first delivery.
- Left navigation, in demo order: Settings, Collect, Classify, Admission, Compile, Review,
  Publish, Ask, Live, Maintain, Access, Audit, Lineage.
- Evidence panel adds, where relevant: run manifest, quarantine record, classification record
  (answers, confidences, `k`, thresholds, model), gate trace of an answer, gateway call records.

## Stages

| Stage | Actions | Visible proof |
|---|---|---|
| 0. Settings | Choose provider (`anthropic`, `openai`), System Two model, System One model, reasoning; paste the API key (written to the secret file, never echoed); test the connection; save. Same variables as `.env`; the panel shows which source set each value. | Sanitized connectivity result naming provider and model; saved configuration pinned to later jobs; refusal to compile while empty. |
| 1. Collect | Run one or all four collectors over `fixtures/meridian/`; open a run manifest; open a quarantine record; try to run an unregistered collector (operator only). | Item counts per source, the three quarantined items with the rule that caught them, the ntfy event, the roster marked restricted, the refusal of the unregistered collector, the manifest with hashes. |
| 2. Classify | Run the classifier on a run; open an item to see answers and confidences; open the owner queue and decide an item as its owner; open the eval report; change a threshold (operator) and see which items move. | Per-item typed answers with confidence and `decided_by`; the uncertain band and its self-consistency samples; the owner's label stored; precision and recall per tag against `expected_tags.json`; model, reasoning, `k` and thresholds on every record. |
| 3. Admission | As in the first delivery, plus: the split of a mixed item into one item per domain, shown as a tree; the domain and tag rule refusing an item for a role. | Included items per role, the split tree, refusals with the rule name, no title leakage across roles. |
| 4. Compile | Start compilation of one role wiki or all; the audience brief of the role is shown next to the job. | Job events, provider and model, budget, candidate per role with its full manifest. |
| 5. Review | As in the first delivery, per role wiki. | Candidate hash, manifest, findings, reviewer decision. |
| 6. Publish | As in the first delivery, per role wiki. | Authorization record, expected versions, committed pages, audit receipt. |
| 7. Ask | Pick a person, pick a request context (desk, on-call, functional, review), ask one of the five questions or a free one; open the gate trace of the answer; edit the person's rendering profile and ask again. | The answer as rendered for that person; the trace with three rows: rights (pages allowed and refused, with the rule), need (audience brief applied, pages selected inside the allowed set), form (profile applied); a 404 for a person without rights; the same question for two people of the same role side by side. |
| 8. Live | Pick a ticket; start the ops agent; watch its calls; try a hand-crafted mutating operation (operator only). | The closed operation list with the classifier's confidence per operation; each gateway call with attempt and result; both refusals of the mutating operation; the agent's reading as a private candidate next to the compiled runbook; calls and time consumed against the budget. |
| 9. Maintain | As in the first delivery, plus: change a tag on an item, move a tag between domains, change a role's domains; see what goes stale. | Stale pages per role, regeneration candidates; adding a person to a role stales nothing. |
| 10. Access | As in the first delivery, at the person and role level. | Denials on pages, history and saved answers after a membership change. |
| 11. Audit | As in the first delivery, plus filters by run, item, person, agent. | Durable events with correlation IDs; classification decisions as values; gateway attempts and results. |
| 12. Lineage | Pick a raw item; read the three answers. | Who could have seen it and when (roles, domains, people, agents, with dates), who did (reads from the audit), where it could have gone (pages, answers, live views that used it). |

## Rendering profile editor

One form per person under Ask: length, leads with, format, tone, avoid, own words, notes.
Every save is versioned and audited. The chat may propose a change to the profile from what
the person wrote (for example a term they use); the proposal is shown as a diff and applied
only when the person accepts it. The profile never adds pages: the trace of the next answer
proves it.

## Gate trace

Every answer stores and shows its trace, in this order and with these words:

1. Rights: roles of the person, domains and tags granted, pages allowed, pages refused and
   why. The only row that can say "refused".
2. Need: the audience briefs applied, the request context, the pages selected among the
   allowed ones and the ones left out as not useful for this job.
3. Form: the rendering profile version applied.

The trace is the demo's proof of D5 and D6. It is a record, not a rendering: the same trace
is available through the API for the evidence files.

## Acceptance

The whole demo story of `README.md` is completable from the browser, in order, without a
terminal, with a fresh `.env` and a key. Screenshots come from the running application and
name the commit, provider and model. A failure states what happened and what remains
unpublished. Refreshing the browser preserves the run state.
