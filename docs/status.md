# Project status

## Completed

- Local Git repository initialized for kops.
- Public `bitrockteam/kops` repository created with an SSH Git remote.
- Architecture v4 captured as the source requirements document.
- Latest demo scope recorded: GUI, synthetic data, mocked Keycloak and real local inference.
- Implementation plan, GUI contract, acceptance matrix and handoff prepared.

## Documentation validation

Checked all local Markdown links and fenced blocks, preserved the v4 architecture snapshot byte-for-byte, confirmed runtime model selection throughout the plan, and scanned the public files for private origin references and obvious credential material. No application or runtime test has been executed.

## Not started

Application implementation, dependency installation, runtime startup, model calls and acceptance tests.

## Runtime choice

No local model endpoint is currently configured. The operator will choose the endpoint and model through the GUI at runtime. This is a product requirement, not a pending planning question. No hosted-provider fallback or automatic model download is authorized.

## Next action

Read `HANDOFF.md`, create the implementation branch and begin M0. Implement Model Setup and inference adapters; a live-model acceptance run needs an operator-supplied endpoint. Update this file with actual evidence and remaining work as implementation proceeds.
