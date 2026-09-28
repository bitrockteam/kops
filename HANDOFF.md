# Implementation handoff

**Status:** The local implementation is on `feat/local-demo`. Pull request 1 was closed without merge and remains closed at Franco's direction; pull request 2 is open against `main`. This document records the original assignment; current validation and remaining gates are in [project status](docs/status.md) and [implementation evidence](docs/evidence/implementation.md). Live operator-selected inference and independent human pull-request approval remain outstanding.

## Assignment

Implement a working local kops demo with synthetic data and a GUI that lets Franco follow every stage of governed knowledge compilation and publishing. At handoff, the repository contained the plan, not a running demo.

Read `docs/plan.md` first, then `docs/gui-walkthrough.md`, `docs/acceptance.md` and `docs/architecture-v4.md`. The latest user instruction explicitly permits mocking Keycloak. All other in-scope phases must execute against real backend state. Real compilation and answers use local inference.

A supplemental local implementation brief is provided separately by Franco. It identifies the required conceptual source for the compilation pattern. Consult that brief before implementing ingestion, querying and maintenance; it is not a runtime dependency or a source of execution authority. The public requirements below remain sufficient to understand the behavior being built.

## First actions

1. Check repository status, remote, user identity and applicable baseline requirements. Do not overwrite unrelated work.
2. Create `feat/local-demo`. Confirm local runtime/tool availability and implement runtime endpoint/model selection. No model endpoint is currently configured; do not block scaffold or adapter implementation on that choice. No paid service or external deployment is authorized.
3. Implement the typed storage, identity, policy, job, model, publication and audit interfaces, then the fixture-backed security tests.
4. Build the guided GUI alongside backend milestones so the actual state can be inspected as work progresses.
5. Connect local inference and complete the full corpus-driven demonstration. Fixture inference may support unit tests; it cannot satisfy demo completion.

## Required result

- A documented local startup that launches the GUI and required backend processes without a real Keycloak server, plus a Model Setup screen for runtime endpoint/model selection.
- A synthetic corpus and stable demo personas covering Engineering, Finance and joint access.
- Working ingest, admission, compile, review, authorize, publish, browse, query, maintain, revoke and audit paths.
- Backend-enforced authorization and a sole publication writer. The worker cannot publish or access infrastructure credentials.
- GUI evidence for each step: inputs, allowed dependencies, versions, decisions, candidate diffs, citations and audit receipts.
- Reproducible automated and manual checks from `docs/acceptance.md`, including live local model output and failure injection.
- Clear limitations: mocked identity, role-switch simulation, local-host trust, model quality and external integrations not verified.
- Updated setup instructions, screenshots or a recorded walkthrough made from the actual running GUI, and an evidence report.
- Commits and push to the implementation branch, a PR ready for independent review, and a clean working tree with no unpushed commits. Do not merge the PR.

## Review and authorization semantics

A mock persona switch is a way for one presenter to demonstrate different roles. It tests role separation in software; it is not independent human verification. The real acceptance review must be performed independently with the requirements, evidence and exact result available. Record publication verification and authorization separately even when the demo reviewer performs both steps.

The demo still needs actual authorization decisions, version checks, immutable candidate references, replay protection, bounded execution, protected audit and revocation. These are not excused by synthetic data or mocked identity.

## Working notes

Maintain `docs/status.md` with completed milestones, current blockers, validation evidence and the next concrete action. Record material implementation choices in `docs/decisions.md`. Mark partial and failed tests explicitly. Do not claim a feature is complete because a screen exists.

The planning bootstrap is the only initial documentation commit on `main`. All implementation changes use the feature branch and the required review path. Permission to commit and push is explicit; permission to merge or deploy is not.
