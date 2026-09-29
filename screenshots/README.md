# GUI evidence

After the synthetic workflow has a committed publication and the dual-access persona has
had Finance membership revoked, run `make screenshots` with `geckodriver` and Firefox
installed. Set `KOPS_SCREENSHOT_URL` to the local GUI URL if it is not port 8080. The
script opens a temporary headless Firefox session and captures publication, the authorized
catalog, access administration, protected audit, the restricted catalog, and a real denied
page read. It does not reset the runtime or create fixture data.

The screenshots in this directory were taken from the running application at the commit
identified in `../docs/evidence/implementation.md`. The inference service used to prepare
the synthetic story is a labeled deterministic test fixture. The images show GUI behavior,
not live-model quality or independent human review.

| File | View |
| --- | --- |
| [01-publication.png](01-publication.png) | Committed Engineering and joint publication operations. |
| [02-authorized-catalog.png](02-authorized-catalog.png) | Operator's authorized catalog. |
| [03-access-changes.png](03-access-changes.png) | Finance membership revocation controls for the dual-access persona. |
| [04-protected-audit.png](04-protected-audit.png) | Durable audit outcomes. |
| [05-revoked-catalog.png](05-revoked-catalog.png) | Revoked persona's Engineering-only catalog. |
| [06-revoked-page-denial.png](06-revoked-page-denial.png) | Guided 404 response for a former joint page. |
