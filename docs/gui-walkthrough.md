# Guided GUI contract

The GUI is a primary deliverable. A visitor should be able to follow the current run without reconstructing terminal logs. Every stage must show actual backend state, and every mutation must use the protected API.

## Layout

- Persistent header: kops, selected synthetic persona, audience, run ID, local model and an explicit mocked-identity indicator.
- Left navigation: Model Setup, Sources, Admission, Compile, Review, Publish, Read and Ask, Maintain, Access Changes, Audit.
- Main panel: current inputs, available actions and results.
- Evidence panel: authorized source revisions, decisions, dependencies, candidate/page versions and audit correlation IDs.
- Status timeline: queued, running, blocked, failed, verified, authorized and published states from server events. Preserve the last confirmed state after a connection loss.

Use plain language and consistent action labels. Keep credentials, raw authorization tokens and internal exception details out of normal product views. A restricted diagnostic view may expose sanitized error details needed to reproduce failures. Do not conceal a failed job behind a generic success badge.

## Stages and required actions

| Stage | User actions | Visible proof |
| --- | --- | --- |
| 0. Model Setup | Select local adapter, endpoint and model, test the connection, set finite execution limits. | Sanitized reachability/capability result and saved configuration; no automatic download or hosted fallback. |
| 1. Sources | Load synthetic corpus, inspect permitted documents, import text, select intended audience. | Source revision/hash, policy, source-use eligibility and provenance origin. |
| 2. Admission | Preview allowed inputs, attempt a forbidden source, confirm compile request. | Included inputs and policy decisions; generic refusal for hidden resources without title leakage. |
| 3. Compile | Start local inference, observe progress, cancel a run. | Actual job events, current model, budget consumption and resulting private change set or failure. |
| 4. Review | Compare old/new pages, inspect citations, reject or record verification. | Candidate hash, full permitted manifest, validation findings, reviewer identity and decision. |
| 5. Publish | Authorize concrete content/audience; publish through the bounded writer. | Separate authorization record, expected versions, committed page versions and audit receipt. |
| 6. Read and Ask | Browse links/history, search pages, ask questions, propose saving an answer. | Authorized content and citations; unsupported/conflicting answers labeled; saved answers become candidates. |
| 7. Maintain | Introduce a revised source, run checks, inspect findings, request regeneration. | Stale dependencies, proposed changes, broken-link/citation findings and a new reviewable candidate. |
| 8. Access Changes | Under admin persona, revoke membership or change a source policy; switch back to affected persona. | Denied current/history/query access and blocked stale authorizations. |
| 9. Audit | Under authorized persona, filter attempts, decisions and effects by run/document. | Actual durable events, versions, timestamps, outcomes and correlation IDs. |

Links, catalogs, audit details and historical pages must honor access policy. The persona selector is an explicit local presentation control, not a real identity verification feature. Changing persona clears incompatible query context.

## Controlled failure demonstrations

Provide a local, admin-only scenario panel for stale approval, conflicting edit, duplicate publication, audit unavailability, source-policy change during a job and job cancellation. These controls must invoke the actual failure paths, not display prerecorded explanations. Protect them from ordinary user requests and disable them outside demo mode.

The demo can be reset to its synthetic fixture state through an explicit, scoped confirmation. A reset must never delete unrelated files or real external resources. Record the reset as a demo operation and make clear which previous run data is being removed. Independent acceptance evidence must remain available outside the resettable runtime dataset.

## GUI acceptance

The default walkthrough is completable without manual API calls. A failure clearly states what happened and what remains unpublished. Refreshing the browser preserves authoritative run state. Screenshots must come from the running application, and evidence must reference the tested commit. Capture both a normal publication and a permission-denial/revocation scenario.

Model configuration is a local operator function. Changing personas does not grant ordinary readers permission to choose network destinations. Missing or failed inference leaves compile/query actions visibly blocked while source and audit inspection remain available.
