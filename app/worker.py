from __future__ import annotations

import hashlib
import json
import re
import signal
import time
import uuid
from typing import Any

import httpx

from app.audit import AuditClient, AuditUnavailable
from app.config import Settings
from app.content import LocalContentStore
from app.db import Database
from app.model import LocalModelClient, ModelError
from app.security import canonical_json


SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,79}$")
stopping = False


def _stop(_: int, __: object) -> None:
    global stopping
    stopping = True


def _event(database: Database, job_id: str, state: str, detail: str) -> None:
    with database.connection() as connection:
        connection.execute(
            "INSERT INTO kops.job_events(job_id, state, detail) VALUES (%s, %s, %s)",
            (job_id, state, detail),
        )
        connection.commit()


def _claim_job(database: Database) -> dict[str, Any] | None:
    with database.connection() as connection:
        job = connection.execute(
            """
            SELECT * FROM kops.jobs
            WHERE status = 'queued'
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED LIMIT 1
            """
        ).fetchone()
        if not job:
            connection.rollback()
            return None
        if job["cancel_requested"]:
            connection.execute(
                "UPDATE kops.jobs SET status = 'cancelled', completed_at = now() WHERE job_id = %s",
                (job["job_id"],),
            )
            connection.execute(
                "INSERT INTO kops.job_events(job_id, state, detail) VALUES (%s, 'cancelled', 'Cancelled before model execution')",
                (job["job_id"],),
            )
            connection.commit()
            return None
        connection.execute(
            "UPDATE kops.jobs SET status = 'running', started_at = now() WHERE job_id = %s",
            (job["job_id"],),
        )
        connection.execute(
            "INSERT INTO kops.job_events(job_id, state, detail) VALUES (%s, 'running', 'Restricted worker claimed the job')",
            (job["job_id"],),
        )
        connection.commit()
        return dict(job)


def _load_inputs(database: Database, settings: Settings, job: dict[str, Any]) -> tuple[list[dict[str, Any]], str, int]:
    with database.connection() as connection:
        rows = connection.execute(
            """
            SELECT ji.*, s.title, s.audience_id, s.policy_revision AS current_policy_revision,
                   s.current_revision
            FROM kops.job_inputs ji
            JOIN kops.sources s ON s.source_id = ji.source_id
            WHERE ji.job_id = %s ORDER BY s.title
            """,
            (job["job_id"],),
        ).fetchall()
        audience = connection.execute(
            "SELECT required_groups, policy_revision FROM kops.audiences WHERE audience_id = %s AND active",
            (job["audience_id"],),
        ).fetchone()
        memberships = connection.execute(
            "SELECT group_id FROM kops.memberships WHERE subject_id = %s AND active",
            (job["requested_by"],),
        ).fetchall()
    if not audience or not set(audience["required_groups"]).issubset({row["group_id"] for row in memberships}):
        raise PermissionError("requester audience membership changed before execution")
    for row in rows:
        if row["source_policy_revision"] != row["current_policy_revision"] or row["source_revision"] != row["current_revision"]:
            raise PermissionError("source revision or policy changed before execution")
    try:
        response = httpx.get(
            f"{settings.content_url}/internal/jobs/{job['job_id']}/inputs",
            headers={"Authorization": f"Bearer {settings.internal_token}"},
            timeout=10.0,
            follow_redirects=False,
        )
        response.raise_for_status()
        inputs = response.json()["inputs"]
    except (httpx.HTTPError, KeyError, TypeError, ValueError) as error:
        raise ValueError("admitted-content broker is unavailable or returned an invalid contract") from error
    total_bytes = sum(len(item["content"].encode()) for item in inputs)
    if not inputs:
        raise ValueError("job has no admitted inputs")
    if total_bytes > int(job["limits"]["max_input_bytes"]):
        raise ValueError("admitted input exceeds the configured byte limit")
    manifest = [
        {"source_id": item["source_id"], "revision": item["revision"]}
        for item in inputs
    ]
    return inputs, hashlib.sha256(canonical_json(manifest).encode()).hexdigest(), total_bytes


def _prompt(job: dict[str, Any], inputs: list[dict[str, Any]]) -> str:
    evidence = "\n\n".join(
        f"<source id=\"{item['source_id']}\" revision=\"{item['revision']}\" title=\"{item['title']}\">\n"
        f"{item['content']}\n</source>"
        for item in inputs
    )
    return (
        f"Task: {job['task_text']}\nTarget audience: {job['audience_id']}\n"
        "Create a concise overview plus useful concept, entity, or comparison pages when evidence supports them. "
        "Identify contradictions explicitly. Use only exact supplied source identifiers in citations.\n\n"
        f"{evidence}"
    )


def _validate_candidate(
    raw: dict[str, Any], admitted: set[tuple[str, int]], store: LocalContentStore, job_id: str
) -> tuple[dict[str, Any], list[dict[str, str]], int]:
    pages = raw.get("pages")
    if not isinstance(pages, list) or not pages or len(pages) > 8:
        raise ValueError("model output must contain one to eight pages")
    normalized_pages: list[dict[str, Any]] = []
    findings: list[dict[str, str]] = []
    output_bytes = 0
    seen_slugs: set[str] = set()
    for index, page in enumerate(pages, start=1):
        if not isinstance(page, dict):
            raise ValueError("page entry must be an object")
        slug = str(page.get("slug", ""))
        title = str(page.get("title", "")).strip()
        markdown = str(page.get("markdown", ""))
        citations = page.get("citations", [])
        if not SLUG.fullmatch(slug) or slug in seen_slugs:
            raise ValueError("page slug is invalid or duplicated")
        if not title or len(title) > 160 or not markdown:
            raise ValueError("page title or Markdown body is invalid")
        if not isinstance(citations, list):
            raise ValueError("page citations must be a list")
        normalized_citations: list[dict[str, Any]] = []
        for citation in citations:
            try:
                key = (str(citation["source_id"]), int(citation["revision"]))
            except (KeyError, TypeError, ValueError) as error:
                raise ValueError("citation shape is invalid") from error
            if key not in admitted:
                raise ValueError("model cited a source outside the admitted manifest")
            normalized_citations.append({"source_id": key[0], "revision": key[1]})
        if not normalized_citations:
            findings.append({"severity": "warning", "code": "page_without_citation", "page": slug})
        object_key, body_hash = store.put_immutable("candidates", job_id, f"page-{index}", markdown)
        output_bytes += len(markdown.encode())
        normalized_pages.append(
            {
                "slug": slug,
                "title": title,
                "object_key": object_key,
                "content_hash": body_hash,
                "citations": normalized_citations,
            }
        )
        seen_slugs.add(slug)
    payload = {
        "pages": normalized_pages,
        "contradictions": raw.get("contradictions", []),
        "quality_notes": raw.get("quality_notes", []),
    }
    return payload, findings, output_bytes


def _finish_failure(database: Database, job_id: str, status: str, code: str, detail: str) -> None:
    with database.connection() as connection:
        connection.execute(
            """
            UPDATE kops.jobs SET status = %s, error_code = %s, error_sanitized = %s,
                completed_at = now() WHERE job_id = %s
            """,
            (status, code, detail, job_id),
        )
        connection.execute(
            "INSERT INTO kops.job_events(job_id, state, detail) VALUES (%s, %s, %s)",
            (job_id, status, detail),
        )
        connection.commit()


def process_job(database: Database, store: LocalContentStore, model: LocalModelClient, audit: AuditClient, settings: Settings, job: dict[str, Any]) -> None:
    job_id = str(job["job_id"])
    correlation_id = f"job:{job_id}"
    try:
        audit.append(
            {
                "correlation_id": correlation_id,
                "initiator": job["requested_by"],
                "actor": "compilation-worker",
                "delegation_ref": job_id,
                "action": "compile.start",
                "resource_type": "job",
                "resource_id": job_id,
                "audience_id": job["audience_id"],
                "decision": "allowed",
                "reason_code": "admitted_job",
                "outcome": "attempt",
                "details": {"model_config_revision": job["model_config_revision"]},
            }
        )
        inputs, manifest_hash, input_bytes = _load_inputs(database, settings, job)
        config = job["model_config_snapshot"]
        if not config:
            raise ModelError("no usable local model configuration is pinned to this job")
        attempts = 1 + min(int(job["limits"].get("max_retries", 0)), 1)
        raw: dict[str, Any] | None = None
        last_error: Exception | None = None
        for attempt in range(attempts):
            try:
                raw = model.compile(config, _prompt(job, inputs))
                break
            except ModelError as error:
                last_error = error
                if attempt + 1 < attempts:
                    _event(database, job_id, "running", "Transient local-model failure; using the single permitted retry")
        if raw is None:
            raise last_error or ModelError("local model failed")
        with database.connection() as connection:
            current = connection.execute(
                "SELECT cancel_requested FROM kops.jobs WHERE job_id = %s", (job_id,)
            ).fetchone()
        if current["cancel_requested"]:
            _finish_failure(database, job_id, "cancelled", "cancelled", "Output discarded after cancellation")
            return
        admitted = {(item["source_id"], item["revision"]) for item in inputs}
        payload, findings, output_bytes = _validate_candidate(raw, admitted, store, job_id)
        if output_bytes > int(job["limits"]["max_output_bytes"]):
            raise ValueError("model output exceeds the configured byte limit")
        candidate_hash = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
        audit.append(
            {
                "correlation_id": correlation_id,
                "initiator": job["requested_by"],
                "actor": "compilation-worker",
                "delegation_ref": job_id,
                "action": "candidate.create",
                "resource_type": "candidate",
                "resource_id": candidate_hash,
                "audience_id": job["audience_id"],
                "decision": "allowed",
                "reason_code": "validated_model_output",
                "outcome": "attempt",
                "details": {"manifest_hash": manifest_hash, "page_count": len(payload["pages"])},
            }
        )
        candidate_id = str(uuid.uuid4())
        with database.connection() as connection:
            connection.execute(
                """
                INSERT INTO kops.candidates(
                    candidate_id, job_id, audience_id, candidate_hash, manifest_hash,
                    payload, validation_findings, state, created_by
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'draft', 'compilation-worker')
                """,
                (candidate_id, job_id, job["audience_id"], candidate_hash, manifest_hash, json.dumps(payload), json.dumps(findings)),
            )
            connection.execute(
                """
                UPDATE kops.jobs SET status = 'ready', input_bytes = %s, output_bytes = %s,
                    model_latency_ms = %s, completed_at = now() WHERE job_id = %s
                """,
                (input_bytes, output_bytes, raw.get("_latency_ms"), job_id),
            )
            connection.execute(
                "INSERT INTO kops.job_events(job_id, state, detail) VALUES (%s, 'ready', 'Private candidate is ready for independent verification')",
                (job_id,),
            )
            connection.commit()
        audit.append(
            {
                "correlation_id": correlation_id,
                "initiator": job["requested_by"],
                "actor": "compilation-worker",
                "delegation_ref": job_id,
                "action": "candidate.create",
                "resource_type": "candidate",
                "resource_id": candidate_id,
                "audience_id": job["audience_id"],
                "decision": "allowed",
                "reason_code": "candidate_persisted",
                "outcome": "committed",
                "details": {"candidate_hash": candidate_hash},
            }
        )
    except AuditUnavailable:
        _finish_failure(database, job_id, "blocked", "audit_unavailable", "Compilation blocked because durable audit is unavailable")
    except PermissionError as error:
        _finish_failure(database, job_id, "blocked", "policy_changed", str(error))
    except (ModelError, ValueError) as error:
        _finish_failure(database, job_id, "failed", "compilation_failed", str(error))
    except Exception:
        _finish_failure(database, job_id, "failed", "internal_error", "Compilation failed with a sanitized internal error")


def main() -> None:
    settings = Settings.load("worker")
    database = Database(settings, min_size=1, max_size=2)
    store = LocalContentStore(settings.content_root)
    model = LocalModelClient(settings.allowed_model_hosts)
    audit = AuditClient(settings)
    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)
    database.open()
    try:
        while not stopping:
            job = _claim_job(database)
            if job:
                process_job(database, store, model, audit, settings, job)
            else:
                time.sleep(1)
    finally:
        database.close()


if __name__ == "__main__":
    main()
