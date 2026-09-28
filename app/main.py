from __future__ import annotations

import hashlib
import json
import os
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
from fastapi import Cookie, FastAPI, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from itsdangerous import BadSignature, URLSafeTimedSerializer

from app.audit import AuditClient, AuditUnavailable
from app.config import Settings
from app.content import LocalContentStore
from app.db import Database
from app.model import LocalModelClient, ModelError
from app.rendering import render_markdown
from app.security import (
    AuthenticationError,
    AuthorizationError,
    DestinationError,
    MockIdentityProvider,
    PostgresPolicyService,
    Principal,
    canonical_json,
    validate_model_endpoint,
)
from app.seed import load_synthetic_corpus, seed_reference_data


settings = Settings.load("api")
database = Database(settings, min_size=1, max_size=8)
store = LocalContentStore(settings.content_root)
identity = MockIdentityProvider(database, settings.session_secret)
policy = PostgresPolicyService(database)
audit = AuditClient(settings)
model_client = LocalModelClient(settings.allowed_model_hosts)
csrf_signer = URLSafeTimedSerializer(settings.session_secret, salt="kops-csrf-v1")
fixture_root = Path(os.getenv("KOPS_FIXTURE_ROOT", "/opt/kops/fixtures"))
if not fixture_root.exists():
    fixture_root = Path(__file__).resolve().parent.parent / "fixtures"


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.open()
    seed_reference_data(database)
    try:
        yield
    finally:
        database.close()


app = FastAPI(title="KnowledgeOps Platform kops", docs_url=None, redoc_url=None, lifespan=lifespan)
app.mount("/static", StaticFiles(directory=Path(__file__).parent / "static"), name="static")
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.exception_handler(DestinationError)
def destination_error_handler(_: Request, error: DestinationError) -> JSONResponse:
    return JSONResponse(status_code=400, content={"detail": str(error)})


def _principal(session: str | None) -> Principal:
    try:
        return identity.resolve_session(session)
    except AuthenticationError as error:
        raise HTTPException(status_code=401, detail=str(error)) from error


def _csrf_for(principal: Principal) -> str:
    return csrf_signer.dumps({"subject_id": principal.subject_id, "purpose": "form"})


def _require_csrf(principal: Principal, token: str) -> None:
    try:
        value = csrf_signer.loads(token, max_age=8 * 60 * 60)
    except BadSignature as error:
        raise HTTPException(status_code=403, detail="invalid form protection token") from error
    if value != {"subject_id": principal.subject_id, "purpose": "form"}:
        raise HTTPException(status_code=403, detail="form protection token does not match the session")


def _redirect(stage: str, message: str, level: str = "ok") -> RedirectResponse:
    from urllib.parse import urlencode

    return RedirectResponse(url=f"/?{urlencode({'stage': stage, 'message': message, 'level': level})}", status_code=303)


def _event(
    principal: Principal,
    action: str,
    resource_type: str,
    resource_id: str | None,
    audience_id: str | None,
    decision: str,
    reason_code: str,
    outcome: str,
    *,
    correlation_id: str | None = None,
    details: dict[str, Any] | None = None,
    authorization_ref: str | None = None,
    operation_ref: str | None = None,
) -> str:
    return audit.append(
        {
            "correlation_id": correlation_id or str(uuid.uuid4()),
            "initiator": principal.subject_id,
            "actor": "kops-api",
            "delegation_ref": f"demo-session:{principal.subject_id}",
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "audience_id": audience_id,
            "decision": decision,
            "reason_code": reason_code,
            "outcome": outcome,
            "authorization_ref": authorization_ref,
            "operation_ref": operation_ref,
            "details": details or {},
        }
    )


def _groups_for_audience(audience_id: str) -> tuple[set[str], int]:
    with database.connection() as connection:
        row = connection.execute(
            "SELECT required_groups, policy_revision FROM kops.audiences WHERE audience_id = %s AND active",
            (audience_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="audience not available")
    return set(row["required_groups"]), row["policy_revision"]


def _require(principal: Principal, action: str, audience_id: str) -> int:
    decision = policy.authorize(principal, action, audience_id)
    if not decision.allowed:
        try:
            _event(principal, action, "audience", None, audience_id, "denied", decision.reason_code, "refused")
        except AuditUnavailable:
            pass
        raise HTTPException(status_code=403, detail="operation is not permitted for this persona and audience")
    return decision.policy_revision


def _is_operator(principal: Principal) -> bool:
    with database.connection() as connection:
        row = connection.execute(
            "SELECT is_operator FROM kops.personas WHERE subject_id = %s", (principal.subject_id,)
        ).fetchone()
    return bool(row and row["is_operator"])


def _visible_sources(principal: Principal) -> list[dict[str, Any]]:
    with database.connection() as connection:
        rows = connection.execute(
            """
            SELECT s.source_id, s.title, s.audience_id, s.current_revision, s.policy_revision,
                   s.synthetic, sv.content_hash, sv.origin, sv.created_at
            FROM kops.sources s JOIN kops.source_versions sv
              ON sv.source_id = s.source_id AND sv.revision = s.current_revision
            WHERE s.active ORDER BY s.title
            """
        ).fetchall()
        audiences = connection.execute("SELECT audience_id, required_groups FROM kops.audiences").fetchall()
    required = {row["audience_id"]: set(row["required_groups"]) for row in audiences}
    return [dict(row) for row in rows if required.get(row["audience_id"], set()).issubset(principal.groups)]


def _source_for_read(principal: Principal, source_id: str) -> dict[str, Any]:
    with database.connection() as connection:
        row = connection.execute(
            """
            SELECT s.*, sv.object_key, sv.content_hash, sv.origin
            FROM kops.sources s JOIN kops.source_versions sv
              ON sv.source_id = s.source_id AND sv.revision = s.current_revision
            WHERE s.source_id = %s AND s.active
            """,
            (source_id,),
        ).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="source not available")
    required, _ = _groups_for_audience(row["audience_id"])
    if not required.issubset(principal.groups):
        try:
            _event(principal, "source.read", "source", None, None, "denied", "source_not_available", "refused")
        except AuditUnavailable:
            pass
        raise HTTPException(status_code=404, detail="source not available")
    return dict(row)


def _candidate_for(principal: Principal, candidate_id: str, action: str = "read") -> dict[str, Any]:
    with database.connection() as connection:
        row = connection.execute(
            """
            SELECT c.*, j.requested_by, j.run_id, j.model_config_snapshot, j.model_config_revision,
                   j.status AS job_status
            FROM kops.candidates c JOIN kops.jobs j ON j.job_id = c.job_id
            WHERE c.candidate_id = %s
            """,
            (candidate_id,),
        ).fetchone()
        if row:
            inputs = connection.execute(
                """
                SELECT ji.source_id, ji.source_revision, ji.source_policy_revision, ji.content_hash,
                       s.title, s.audience_id
                FROM kops.job_inputs ji JOIN kops.sources s ON s.source_id = ji.source_id
                WHERE ji.job_id = %s ORDER BY s.title
                """,
                (row["job_id"],),
            ).fetchall()
    if not row:
        raise HTTPException(status_code=404, detail="candidate not available")
    required, _ = _groups_for_audience(row["audience_id"])
    if not required.issubset(principal.groups):
        raise HTTPException(status_code=404, detail="candidate not available")
    if action != "read" and action not in principal.action_grants and "*" not in principal.action_grants:
        raise HTTPException(status_code=403, detail="action is not granted")
    result = dict(row)
    result["inputs"] = [dict(item) for item in inputs]
    result["rendered_pages"] = [
        {**page, "rendered": render_markdown(store.read(page["object_key"]))}
        for page in row["payload"]["pages"]
    ]
    return result


def _document_for_read(principal: Principal, document_id: str, version: int | None = None) -> dict[str, Any]:
    with database.connection() as connection:
        document = connection.execute(
            "SELECT * FROM kops.documents WHERE document_id = %s", (document_id,)
        ).fetchone()
        if not document:
            raise HTTPException(status_code=404, detail="page not available")
        selected_version = version or document["current_version"]
        page = connection.execute(
            "SELECT * FROM kops.page_versions WHERE document_id = %s AND version = %s",
            (document_id, selected_version),
        ).fetchone()
        dependencies = connection.execute(
            """
            SELECT d.*, s.title, s.policy_revision AS current_policy_revision,
                   s.current_revision
            FROM kops.dependencies d JOIN kops.sources s ON s.source_id = d.source_id
            WHERE d.document_id = %s AND d.document_version = %s
            """,
            (document_id, selected_version),
        ).fetchall()
    if not page:
        raise HTTPException(status_code=404, detail="page version not available")
    decision = policy.authorize(principal, "read", document["audience_id"])
    if not decision.allowed:
        try:
            _event(principal, "page.read", "document", None, None, "denied", "page_not_available", "refused")
        except AuditUnavailable:
            pass
        raise HTTPException(status_code=404, detail="page not available")
    if document["publication_state"] == "blocked":
        raise HTTPException(status_code=409, detail="page is blocked pending policy re-evaluation")
    try:
        receipt = _event(
            principal,
            "page.read",
            "document",
            document_id,
            document["audience_id"],
            "allowed",
            "current_policy_allowed",
            "delivery_attempt",
            details={"version": selected_version},
        )
    except AuditUnavailable as error:
        raise HTTPException(status_code=503, detail="read blocked because durable audit is unavailable") from error
    body = store.read(page["object_key"])
    if hashlib.sha256(body.encode()).hexdigest() != page["content_hash"]:
        raise HTTPException(status_code=500, detail="published content integrity check failed")
    return {
        **dict(document),
        "version": selected_version,
        "page": dict(page),
        "dependencies": [dict(item) for item in dependencies],
        "rendered": render_markdown(body),
        "read_receipt": receipt,
    }


def _active_model_config() -> dict[str, Any] | None:
    with database.connection() as connection:
        row = connection.execute(
            "SELECT * FROM kops.model_configs WHERE active ORDER BY revision DESC LIMIT 1"
        ).fetchone()
    if not row:
        return None
    return {
        "config_id": str(row["config_id"]),
        "revision": row["revision"],
        "adapter": row["adapter"],
        "endpoint": row["endpoint"],
        "model_name": row["model_name"],
        "limits": row["limits"],
        "connection_status": row["connection_status"],
        "diagnostic": row["diagnostic"],
    }


def _dashboard_state(principal: Principal) -> dict[str, Any]:
    with database.connection() as connection:
        personas = connection.execute(
            "SELECT subject_id, display_name, action_grants FROM kops.personas WHERE active ORDER BY display_name"
        ).fetchall()
        audiences = connection.execute(
            "SELECT * FROM kops.audiences WHERE active ORDER BY display_name"
        ).fetchall()
        run = connection.execute("SELECT * FROM kops.runs ORDER BY created_at DESC LIMIT 1").fetchone()
        jobs = connection.execute(
            """
            SELECT j.*, c.candidate_id, c.state AS candidate_state
            FROM kops.jobs j LEFT JOIN kops.candidates c ON c.job_id = j.job_id
            ORDER BY j.created_at DESC LIMIT 25
            """
        ).fetchall()
        documents = connection.execute(
            "SELECT * FROM kops.documents ORDER BY title"
        ).fetchall()
        operations = connection.execute(
            """
            SELECT o.*, pa.candidate_id, pa.audience_id, pa.authorized_by
            FROM kops.operations o JOIN kops.publication_authorizations pa
              ON pa.authorization_id = o.authorization_id
            ORDER BY o.created_at DESC LIMIT 20
            """
        ).fetchall()
        verifications = connection.execute(
            """
            SELECT v.*, c.audience_id FROM kops.verifications v
            JOIN kops.candidates c ON c.candidate_id = v.candidate_id
            ORDER BY v.created_at DESC LIMIT 20
            """
        ).fetchall()
        authorizations = connection.execute(
            "SELECT * FROM kops.publication_authorizations ORDER BY created_at DESC LIMIT 20"
        ).fetchall()
        responses = connection.execute(
            "SELECT * FROM kops.query_responses WHERE subject_id = %s ORDER BY created_at DESC LIMIT 20",
            (principal.subject_id,),
        ).fetchall()
        job_events = connection.execute(
            """
            SELECT je.* FROM kops.job_events je JOIN kops.jobs j ON j.job_id = je.job_id
            ORDER BY je.created_at DESC LIMIT 30
            """
        ).fetchall()
        audit_events: list[Any] = []
        if "audit" in principal.action_grants or "*" in principal.action_grants:
            audit_events = connection.execute(
                "SELECT * FROM kops.audit_events ORDER BY occurred_at DESC LIMIT 100"
            ).fetchall()
    visible_audiences = {
        row["audience_id"]
        for row in audiences
        if set(row["required_groups"]).issubset(principal.groups)
    }
    visible_jobs = [
        dict(row)
        for row in jobs
        if row["audience_id"] in visible_audiences
        and (row["requested_by"] == principal.subject_id or {"review", "authorize", "publish"} & principal.action_grants or "*" in principal.action_grants)
    ]
    visible_documents = [dict(row) for row in documents if row["audience_id"] in visible_audiences]
    visible_operations = [dict(row) for row in operations if row["audience_id"] in visible_audiences]
    visible_job_ids = {row["job_id"] for row in visible_jobs}
    return {
        "personas": [dict(row) for row in personas],
        "audiences": [dict(row) for row in audiences if row["audience_id"] in visible_audiences],
        "sources": _visible_sources(principal),
        "run": dict(run) if run else None,
        "jobs": visible_jobs,
        "documents": visible_documents,
        "operations": visible_operations,
        "verifications": [dict(row) for row in verifications if row["audience_id"] in visible_audiences],
        "authorizations": [dict(row) for row in authorizations if row["audience_id"] in visible_audiences],
        "responses": [dict(row) for row in responses],
        "job_events": [dict(row) for row in job_events if row["job_id"] in visible_job_ids],
        "audit_events": [dict(row) for row in audit_events],
        "model": _active_model_config(),
        "is_operator": _is_operator(principal),
    }


@app.get("/health")
def health() -> dict[str, str]:
    with database.connection() as connection:
        connection.execute("SELECT 1").fetchone()
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
def index(
    request: Request,
    stage: str = Query(default="model"),
    message: str | None = Query(default=None),
    level: str = Query(default="ok"),
    candidate: str | None = Query(default=None),
    document: str | None = Query(default=None),
    version: int | None = Query(default=None),
    kops_session: str | None = Cookie(default=None),
) -> HTMLResponse:
    principal = _principal(kops_session)
    candidate_detail = _candidate_for(principal, candidate) if candidate else None
    document_detail = _document_for_read(principal, document, version) if document else None
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "principal": principal,
            "csrf": _csrf_for(principal),
            "stage": stage,
            "message": message,
            "level": level,
            "state": _dashboard_state(principal),
            "candidate_detail": candidate_detail,
            "document_detail": document_detail,
            "mock_identity": True,
        },
    )


@app.post("/session/persona")
def switch_persona(
    subject_id: str = Form(),
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    current = _principal(kops_session)
    _require_csrf(current, csrf)
    try:
        signed = identity.issue_session(subject_id)
    except AuthenticationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    response = _redirect("model", "Synthetic persona changed; incompatible query context was cleared")
    response.set_cookie("kops_session", signed, httponly=True, samesite="strict", secure=False, max_age=8 * 60 * 60)
    return response


@app.post("/model/test")
def test_model(
    adapter: str = Form(),
    endpoint: str = Form(),
    model_name: str = Form(),
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    if not _is_operator(principal):
        raise HTTPException(status_code=403, detail="only the local operator can choose model destinations")
    config = {
        "adapter": adapter,
        "endpoint": validate_model_endpoint(endpoint, settings.allowed_model_hosts),
        "model_name": model_name.strip(),
        "limits": {"max_output_tokens": 800, "wall_time_seconds": 60},
    }
    try:
        result = model_client.test_connection(config)
        _event(principal, "model.test", "model_configuration", None, None, "allowed", "local_destination_validated", "completed", details=result)
        return _redirect("model", f"Connection succeeded in {result['latency_ms']} ms")
    except (ModelError, ValueError) as error:
        _event(principal, "model.test", "model_configuration", None, None, "allowed", "connection_failed", "failed", details={"error": str(error)})
        return _redirect("model", str(error), "error")


@app.post("/model/save")
def save_model(
    adapter: str = Form(),
    endpoint: str = Form(),
    model_name: str = Form(),
    max_input_bytes: int = Form(default=60000),
    max_output_bytes: int = Form(default=30000),
    max_output_tokens: int = Form(default=1200),
    wall_time_seconds: int = Form(default=90),
    max_retries: int = Form(default=1),
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    if not _is_operator(principal):
        raise HTTPException(status_code=403, detail="only the local operator can choose model destinations")
    normalized = validate_model_endpoint(endpoint, settings.allowed_model_hosts)
    if adapter not in {"openai", "ollama"} or not model_name.strip():
        raise HTTPException(status_code=400, detail="adapter and model name are required")
    limits = {
        "max_input_bytes": min(max(max_input_bytes, 1024), 250000),
        "max_output_bytes": min(max(max_output_bytes, 1024), 100000),
        "max_output_tokens": min(max(max_output_tokens, 64), 4096),
        "wall_time_seconds": min(max(wall_time_seconds, 5), 300),
        "max_retries": min(max(max_retries, 0), 1),
        "max_repairs": 1,
        "concurrency": 1,
    }
    config = {"adapter": adapter, "endpoint": normalized, "model_name": model_name.strip(), "limits": limits}
    connection_status = "untested"
    diagnostic = "Saved; run the connection test before compilation"
    try:
        result = model_client.test_connection(config)
        connection_status = "reachable"
        diagnostic = f"Reachable in {result['latency_ms']} ms"
    except ModelError as error:
        connection_status = "failed"
        diagnostic = str(error)
    with database.connection() as connection:
        connection.execute("UPDATE kops.model_configs SET active = false WHERE active")
        row = connection.execute(
            """
            INSERT INTO kops.model_configs(
                adapter, endpoint, model_name, limits, connection_status, diagnostic, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING revision
            """,
            (adapter, normalized, model_name.strip(), json.dumps(limits), connection_status, diagnostic, principal.subject_id),
        ).fetchone()
        connection.execute(
            """
            UPDATE kops.candidates SET state = 'stale'
            WHERE state IN ('draft', 'independently_verified', 'authorized')
              AND job_id IN (SELECT job_id FROM kops.jobs WHERE model_config_revision IS DISTINCT FROM %s)
            """,
            (row["revision"],),
        )
        connection.execute(
            "UPDATE kops.publication_authorizations SET status = 'invalidated' WHERE status = 'active'"
        )
        connection.commit()
    _event(principal, "model.configure", "model_configuration", str(row["revision"]), None, "allowed", "operator_configuration", "committed", details={"adapter": adapter, "model": model_name.strip(), "status": connection_status})
    return _redirect("model", f"Model configuration revision {row['revision']} saved: {diagnostic}", "ok" if connection_status == "reachable" else "error")


@app.post("/fixtures/load")
def load_fixtures(
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    if not _is_operator(principal):
        raise HTTPException(status_code=403, detail="only the local operator can load the synthetic corpus")
    loaded = load_synthetic_corpus(database, store, fixture_root, principal.subject_id)
    _event(principal, "fixtures.load", "synthetic_corpus", None, None, "allowed", "explicit_demo_action", "committed", details={"source_count": len(loaded)})
    return _redirect("sources", f"Synthetic corpus is ready with {len(loaded)} sources")


@app.get("/sources/{source_id}", response_class=HTMLResponse)
def read_source(source_id: str, kops_session: str | None = Cookie(default=None)) -> HTMLResponse:
    principal = _principal(kops_session)
    source = _source_for_read(principal, source_id)
    try:
        _event(principal, "source.read", "source", source_id, source["audience_id"], "allowed", "source_policy_allowed", "delivery_attempt", details={"revision": source["current_revision"]})
    except AuditUnavailable as error:
        raise HTTPException(status_code=503, detail="source read blocked because durable audit is unavailable") from error
    body = store.read(source["object_key"])
    return HTMLResponse(f"<main><h1>{source['title']}</h1>{render_markdown(body)}<p><a href='/'>Return to kops</a></p></main>")


@app.post("/sources/import")
def import_source(
    title: str = Form(),
    audience_id: str = Form(),
    content: str = Form(),
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    _require(principal, "source_import", audience_id)
    if not title.strip() or not content.strip() or len(content.encode()) > 100000:
        raise HTTPException(status_code=400, detail="title and content are required and content is limited to 100000 bytes")
    source_id = str(uuid.uuid4())
    object_key, digest = store.put_immutable("sources", source_id, "1", content)
    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO kops.sources(source_id, title, audience_id, current_revision, created_by)
            VALUES (%s, %s, %s, 1, %s)
            """,
            (source_id, title.strip(), audience_id, principal.subject_id),
        )
        connection.execute(
            """
            INSERT INTO kops.source_versions(source_id, revision, object_key, content_hash, origin, created_by)
            VALUES (%s, 1, %s, %s, 'manual-local-import', %s)
            """,
            (source_id, object_key, digest, principal.subject_id),
        )
        connection.commit()
    _event(principal, "source.import", "source", source_id, audience_id, "allowed", "source_import_grant", "committed", details={"revision": 1, "content_hash": digest})
    return _redirect("sources", "Source revision 1 imported")


@app.post("/admission/preview")
def admission_preview(
    audience_id: str = Form(),
    source_ids: list[str] = Form(default=[]),
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    _require(principal, "compile", audience_id)
    visible = {str(item["source_id"]): item for item in _visible_sources(principal)}
    included: list[str] = []
    denied = 0
    for source_id in source_ids:
        source = visible.get(source_id)
        if source and policy.source_compatible(source["audience_id"], audience_id):
            included.append(source["title"])
        else:
            denied += 1
    _event(principal, "admission.preview", "compile_request", None, audience_id, "allowed", "preview_completed", "completed", details={"included_count": len(included), "denied_count": denied})
    text = f"Included: {', '.join(included) if included else 'none'}. Refused hidden or incompatible inputs: {denied}."
    return _redirect("admission", text, "error" if denied else "ok")


@app.post("/jobs/create")
def create_job(
    audience_id: str = Form(),
    source_ids: list[str] = Form(default=[]),
    task_text: str = Form(default="Compile maintained knowledge pages from the admitted sources."),
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    audience_policy_revision = _require(principal, "compile", audience_id)
    model = _active_model_config()
    if not model or model["connection_status"] != "reachable":
        return _redirect("model", "Compilation is blocked until a reachable local model configuration is saved", "error")
    if not source_ids:
        raise HTTPException(status_code=400, detail="at least one source must be selected")
    visible = {str(item["source_id"]): item for item in _visible_sources(principal)}
    admitted: list[dict[str, Any]] = []
    for source_id in source_ids:
        source = visible.get(source_id)
        if not source or not policy.source_compatible(source["audience_id"], audience_id):
            _event(principal, "compile.request", "compile_job", None, audience_id, "denied", "source_not_admissible", "refused", details={"requested_count": len(source_ids)})
            raise HTTPException(status_code=403, detail="one or more requested sources are not available for this destination")
        admitted.append(source)
    with database.connection() as connection:
        active = connection.execute(
            "SELECT job_id FROM kops.jobs WHERE status IN ('queued', 'running') LIMIT 1"
        ).fetchone()
        if active:
            raise HTTPException(status_code=409, detail="the single compilation slot is already in use")
        run = connection.execute("SELECT run_id FROM kops.runs ORDER BY created_at DESC LIMIT 1").fetchone()
        job_id = str(uuid.uuid4())
        snapshot = {key: model[key] for key in ("adapter", "endpoint", "model_name", "limits", "revision")}
        connection.execute(
            """
            INSERT INTO kops.jobs(
                job_id, run_id, requested_by, audience_id, task_text, model_config_snapshot,
                model_config_revision, limits, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'queued')
            """,
            (job_id, run["run_id"], principal.subject_id, audience_id, task_text.strip(), json.dumps(snapshot), model["revision"], json.dumps(model["limits"])),
        )
        for source in admitted:
            connection.execute(
                """
                INSERT INTO kops.job_inputs(
                    job_id, source_id, source_revision, source_policy_revision,
                    object_key, content_hash, admission_decision
                )
                SELECT %s, s.source_id, s.current_revision, s.policy_revision,
                       sv.object_key, sv.content_hash, 'allowed'
                FROM kops.sources s JOIN kops.source_versions sv
                  ON sv.source_id = s.source_id AND sv.revision = s.current_revision
                WHERE s.source_id = %s
                """,
                (job_id, source["source_id"]),
            )
        connection.execute(
            "INSERT INTO kops.job_events(job_id, state, detail) VALUES (%s, 'queued', 'Admission completed and the protected job was persisted')",
            (job_id,),
        )
        connection.commit()
    _event(principal, "compile.request", "job", job_id, audience_id, "allowed", "inputs_admitted", "committed", correlation_id=f"job:{job_id}", details={"source_count": len(admitted), "audience_policy_revision": audience_policy_revision, "model_config_revision": model["revision"]})
    return _redirect("compile", f"Compilation job {job_id} queued")


@app.post("/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str,
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    with database.connection() as connection:
        job = connection.execute("SELECT * FROM kops.jobs WHERE job_id = %s", (job_id,)).fetchone()
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        if job["requested_by"] != principal.subject_id and not _is_operator(principal):
            raise HTTPException(status_code=403, detail="only the requester or operator can stop this job")
        if job["status"] not in {"queued", "running"}:
            return _redirect("compile", f"Job is already {job['status']}", "error")
        new_status = "cancelled" if job["status"] == "queued" else job["status"]
        connection.execute(
            "UPDATE kops.jobs SET cancel_requested = true, status = %s, completed_at = CASE WHEN %s = 'cancelled' THEN now() ELSE completed_at END WHERE job_id = %s",
            (new_status, new_status, job_id),
        )
        connection.execute(
            "INSERT INTO kops.job_events(job_id, state, detail) VALUES (%s, 'cancelled', 'Stop requested; no new model call or publication is permitted')",
            (job_id,),
        )
        connection.commit()
    _event(principal, "job.cancel", "job", job_id, job["audience_id"], "allowed", "requester_stop", "committed", correlation_id=f"job:{job_id}")
    return _redirect("compile", "Stop requested and publication is blocked")


@app.post("/candidates/{candidate_id}/verify")
def verify_candidate(
    candidate_id: str,
    decision: str = Form(),
    findings: str = Form(default="Reviewed against the complete manifest and acceptance criteria."),
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    candidate = _candidate_for(principal, candidate_id, "review")
    _require(principal, "review", candidate["audience_id"])
    if decision not in {"verified", "rejected"}:
        raise HTTPException(status_code=400, detail="verification decision is invalid")
    if candidate["state"] not in {"draft", "independently_verified"}:
        raise HTTPException(status_code=409, detail="candidate is not reviewable in its current state")
    correlation_id = f"candidate:{candidate_id}"
    _event(principal, "candidate.verify", "candidate", candidate_id, candidate["audience_id"], "allowed", "review_grant", "attempt", correlation_id=correlation_id, details={"candidate_hash": candidate["candidate_hash"], "decision": decision})
    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO kops.verifications(candidate_id, candidate_hash, reviewer_id, decision, findings)
            VALUES (%s, %s, %s, %s, %s)
            """,
            (candidate_id, candidate["candidate_hash"], principal.subject_id, decision, json.dumps([{"note": findings.strip()}])),
        )
        connection.execute(
            "UPDATE kops.candidates SET state = %s WHERE candidate_id = %s AND candidate_hash = %s",
            ("independently_verified" if decision == "verified" else "rejected", candidate_id, candidate["candidate_hash"]),
        )
        connection.commit()
    _event(principal, "candidate.verify", "candidate", candidate_id, candidate["audience_id"], "allowed", "exact_candidate_recorded", "committed", correlation_id=correlation_id, details={"candidate_hash": candidate["candidate_hash"], "decision": decision})
    return _redirect("review", f"Candidate {decision} with exact hash {candidate['candidate_hash'][:12]}")


@app.post("/candidates/{candidate_id}/authorize")
def authorize_candidate(
    candidate_id: str,
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    candidate = _candidate_for(principal, candidate_id, "authorize")
    audience_revision = _require(principal, "authorize", candidate["audience_id"])
    if candidate["state"] != "independently_verified":
        raise HTTPException(status_code=409, detail="the exact candidate must be independently verified first")
    with database.connection() as connection:
        verification = connection.execute(
            """
            SELECT * FROM kops.verifications
            WHERE candidate_id = %s AND candidate_hash = %s AND decision = 'verified'
            ORDER BY created_at DESC LIMIT 1
            """,
            (candidate_id, candidate["candidate_hash"]),
        ).fetchone()
        if not verification:
            raise HTTPException(status_code=409, detail="matching verification record not found")
        expected_versions: dict[str, int] = {}
        for page in candidate["payload"]["pages"]:
            document = connection.execute(
                "SELECT current_version FROM kops.documents WHERE audience_id = %s AND slug = %s",
                (candidate["audience_id"], page["slug"]),
            ).fetchone()
            expected_versions[page["slug"]] = document["current_version"] if document else 0
        dependencies = {
            str(item["source_id"]): {
                "revision": item["source_revision"],
                "policy_revision": item["source_policy_revision"],
            }
            for item in candidate["inputs"]
        }
        authorization_id = str(uuid.uuid4())
        operation_id = str(uuid.uuid4())
        idempotency_key = hashlib.sha256(
            canonical_json(
                {
                    "candidate_hash": candidate["candidate_hash"],
                    "audience": candidate["audience_id"],
                    "expected_versions": expected_versions,
                    "dependencies": dependencies,
                }
            ).encode()
        ).hexdigest()
        existing = connection.execute(
            "SELECT operation_id FROM kops.operations WHERE idempotency_key = %s",
            (idempotency_key,),
        ).fetchone()
        if existing:
            return _redirect("publish", f"Existing operation {existing['operation_id']} retained for this exact effect")
        _event(principal, "publication.authorize", "candidate", candidate_id, candidate["audience_id"], "allowed", "verified_candidate_and_effect", "attempt", correlation_id=f"operation:{operation_id}", details={"candidate_hash": candidate["candidate_hash"], "expected_versions": expected_versions})
        connection.execute(
            """
            INSERT INTO kops.publication_authorizations(
                authorization_id, candidate_id, candidate_hash, audience_id, authorized_by,
                expected_versions, dependency_revisions, policy_revisions, expires_at, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'active')
            """,
            (
                authorization_id,
                candidate_id,
                candidate["candidate_hash"],
                candidate["audience_id"],
                principal.subject_id,
                json.dumps(expected_versions),
                json.dumps(dependencies),
                json.dumps({"audience": audience_revision}),
                datetime.now(UTC) + timedelta(minutes=30),
            ),
        )
        connection.execute(
            """
            INSERT INTO kops.operations(
                operation_id, authorization_id, operation_type, idempotency_key,
                requested_by, status
            ) VALUES (%s, %s, 'publish_document', %s, %s, 'pending')
            """,
            (operation_id, authorization_id, idempotency_key, principal.subject_id),
        )
        connection.execute(
            "UPDATE kops.candidates SET state = 'authorized' WHERE candidate_id = %s AND candidate_hash = %s",
            (candidate_id, candidate["candidate_hash"]),
        )
        connection.commit()
    _event(principal, "publication.authorize", "operation", operation_id, candidate["audience_id"], "allowed", "immutable_effect_bound", "committed", correlation_id=f"operation:{operation_id}", authorization_ref=authorization_id, operation_ref=operation_id, details={"candidate_hash": candidate["candidate_hash"], "expires_in_minutes": 30})
    return _redirect("publish", f"Authorization and operation {operation_id} created separately from verification")


def _call_publisher(operation_id: str) -> dict[str, Any]:
    try:
        response = httpx.post(
            f"{settings.publisher_url}/internal/operations/{operation_id}/publish",
            headers={"Authorization": f"Bearer {settings.internal_token}"},
            timeout=15.0,
            follow_redirects=False,
        )
    except httpx.HTTPError as error:
        raise HTTPException(status_code=503, detail=f"publication result is uncertain for operation {operation_id}; reconcile using the same operation ID") from error
    if response.status_code >= 400:
        detail = response.json().get("detail", "publication refused") if response.headers.get("content-type", "").startswith("application/json") else "publication refused"
        raise HTTPException(status_code=response.status_code, detail=detail)
    return response.json()


@app.post("/operations/{operation_id}/publish")
def publish_operation(
    operation_id: str,
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    with database.connection() as connection:
        operation = connection.execute(
            """
            SELECT o.*, pa.audience_id FROM kops.operations o
            JOIN kops.publication_authorizations pa ON pa.authorization_id = o.authorization_id
            WHERE o.operation_id = %s
            """,
            (operation_id,),
        ).fetchone()
    if not operation:
        raise HTTPException(status_code=404, detail="operation not found")
    _require(principal, "publish", operation["audience_id"])
    result = _call_publisher(operation_id)
    return _redirect("read", f"Operation {operation_id} is {result['status']}; {len(result.get('result', {}).get('pages', []))} page revisions are visible")


@app.get("/documents/{document_id}", response_class=HTMLResponse)
def document_page(
    document_id: str,
    version: int | None = Query(default=None),
    kops_session: str | None = Cookie(default=None),
) -> HTMLResponse:
    principal = _principal(kops_session)
    document = _document_for_read(principal, document_id, version)
    dependency_rows = "".join(
        f"<li>{item['title']} revision {item['source_revision']} (policy {item['source_policy_revision']})</li>"
        for item in document["dependencies"]
    )
    return HTMLResponse(
        f"<main><h1>{document['title']}</h1><p>Audience: {document['audience_id']} | Version: {document['version']} | State: {document['publication_state']}</p>"
        f"{document['rendered']}<h2>Dependencies</h2><ul>{dependency_rows}</ul>"
        f"<p>Read audit receipt: {document['read_receipt']}</p><p><a href='/?stage=read'>Return to kops</a></p></main>"
    )


@app.post("/query")
def query_pages(
    audience_id: str = Form(),
    question: str = Form(),
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    _require(principal, "query", audience_id)
    model = _active_model_config()
    if not model or model["connection_status"] != "reachable":
        return _redirect("model", "Questions are blocked until a reachable local model is configured", "error")
    with database.connection() as connection:
        pages = connection.execute(
            """
            SELECT d.document_id, d.slug, d.title, d.current_version, d.publication_state,
                   pv.object_key, pv.content_hash
            FROM kops.documents d JOIN kops.page_versions pv
              ON pv.document_id = d.document_id AND pv.version = d.current_version
            WHERE d.audience_id = %s AND d.publication_state IN ('published', 'stale')
            ORDER BY d.title
            """,
            (audience_id,),
        ).fetchall()
        run = connection.execute("SELECT run_id FROM kops.runs ORDER BY created_at DESC LIMIT 1").fetchone()
    if not pages:
        raise HTTPException(status_code=409, detail="no authorized published pages are available for this audience")
    _event(principal, "query.execute", "audience", audience_id, audience_id, "allowed", "authorized_compiled_pages_only", "attempt", details={"page_count": len(pages)})
    allowed_citations: set[tuple[str, int]] = set()
    page_blocks: list[str] = []
    total_bytes = 0
    for page in pages:
        body = store.read(page["object_key"])
        total_bytes += len(body.encode())
        allowed_citations.add((str(page["document_id"]), page["current_version"]))
        page_blocks.append(
            f"<page document_id=\"{page['document_id']}\" version=\"{page['current_version']}\" title=\"{page['title']}\">\n{body}\n</page>"
        )
    if total_bytes > model["limits"]["max_input_bytes"]:
        raise HTTPException(status_code=413, detail="authorized page set exceeds the configured model input limit")
    prompt = f"Question: {question.strip()}\n\n" + "\n\n".join(page_blocks)
    response_id = str(uuid.uuid4())
    try:
        result = model_client.answer(model, prompt)
        answer = str(result.get("answer", "")).strip()
        raw_citations = result.get("citations", [])
        citations: list[dict[str, Any]] = []
        invalid_citation = False
        for citation in raw_citations if isinstance(raw_citations, list) else []:
            try:
                key = (str(citation["document_id"]), int(citation["version"]))
            except (KeyError, TypeError, ValueError):
                invalid_citation = True
                continue
            if key not in allowed_citations:
                invalid_citation = True
                continue
            citations.append({"document_id": key[0], "version": key[1]})
        evaluation = str(result.get("evaluation", "unsupported"))
        if evaluation not in {"supported", "contradictory", "unsupported"} or invalid_citation:
            evaluation = "unsupported"
        if evaluation == "supported" and not citations:
            evaluation = "unsupported"
        object_key, digest = store.put_immutable("answers", response_id, "1", answer)
        with database.connection() as connection:
            connection.execute(
                """
                INSERT INTO kops.query_responses(
                    response_id, run_id, subject_id, audience_id, question, answer_object_key,
                    answer_hash, citations, evaluation, model_config_revision
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (response_id, run["run_id"], principal.subject_id, audience_id, question.strip(), object_key, digest, json.dumps(citations), evaluation, model["revision"]),
            )
            connection.commit()
        _event(principal, "query.execute", "query_response", response_id, audience_id, "allowed", "grounded_answer_recorded", "completed", details={"evaluation": evaluation, "citation_count": len(citations), "model_config_revision": model["revision"]})
        return _redirect("read", f"Answer {response_id} recorded as {evaluation}; inspect it below")
    except ModelError as error:
        with database.connection() as connection:
            connection.execute(
                """
                INSERT INTO kops.query_responses(
                    response_id, run_id, subject_id, audience_id, question, citations,
                    evaluation, model_config_revision, error_sanitized
                ) VALUES (%s, %s, %s, %s, %s, '[]', 'failed', %s, %s)
                """,
                (response_id, run["run_id"], principal.subject_id, audience_id, question.strip(), model["revision"], str(error)),
            )
            connection.commit()
        return _redirect("read", str(error), "error")


@app.get("/responses/{response_id}", response_class=HTMLResponse)
def read_response(response_id: str, kops_session: str | None = Cookie(default=None)) -> HTMLResponse:
    principal = _principal(kops_session)
    with database.connection() as connection:
        response = connection.execute(
            "SELECT * FROM kops.query_responses WHERE response_id = %s", (response_id,)
        ).fetchone()
    if not response or response["subject_id"] != principal.subject_id:
        raise HTTPException(status_code=404, detail="answer not available")
    _require(principal, "read", response["audience_id"])
    _event(principal, "answer.read", "query_response", response_id, response["audience_id"], "allowed", "response_owner_and_audience", "delivery_attempt")
    answer = store.read(response["answer_object_key"]) if response["answer_object_key"] else response["error_sanitized"]
    return HTMLResponse(f"<main><h1>Grounded answer</h1><p>Evaluation: {response['evaluation']}</p>{render_markdown(answer or '')}<pre>{json.dumps(response['citations'], indent=2)}</pre><p><a href='/?stage=read'>Return</a></p></main>")


@app.post("/responses/{response_id}/save-candidate")
def save_answer_candidate(
    response_id: str,
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    with database.connection() as connection:
        response = connection.execute(
            "SELECT * FROM kops.query_responses WHERE response_id = %s", (response_id,)
        ).fetchone()
        if not response or response["subject_id"] != principal.subject_id:
            raise HTTPException(status_code=404, detail="answer not available")
        _require(principal, "save_answer", response["audience_id"])
        if response["evaluation"] == "failed" or not response["answer_object_key"]:
            raise HTTPException(status_code=409, detail="failed answers cannot become candidates")
        run = connection.execute("SELECT run_id FROM kops.runs ORDER BY created_at DESC LIMIT 1").fetchone()
        model = _active_model_config()
        job_id = str(uuid.uuid4())
        limits = model["limits"] if model else {"max_input_bytes": 0, "max_output_bytes": 0, "max_retries": 0}
        snapshot = {key: model[key] for key in ("adapter", "endpoint", "model_name", "limits", "revision")} if model else None
        connection.execute(
            """
            INSERT INTO kops.jobs(
                job_id, run_id, requested_by, workload_principal, audience_id, task_text,
                model_config_snapshot, model_config_revision, limits, status, completed_at
            ) VALUES (%s, %s, %s, 'query-service', %s, %s, %s, %s, %s, 'ready', now())
            """,
            (job_id, run["run_id"], principal.subject_id, response["audience_id"], f"Promote query response {response_id} to a private candidate", json.dumps(snapshot) if snapshot else None, response["model_config_revision"], json.dumps(limits)),
        )
        dependency_rows: dict[str, dict[str, Any]] = {}
        for citation in response["citations"]:
            rows = connection.execute(
                """
                SELECT d.source_id, d.source_revision, d.source_policy_revision,
                       sv.object_key, sv.content_hash
                FROM kops.dependencies d JOIN kops.source_versions sv
                  ON sv.source_id = d.source_id AND sv.revision = d.source_revision
                WHERE d.document_id = %s AND d.document_version = %s
                """,
                (citation["document_id"], citation["version"]),
            ).fetchall()
            for item in rows:
                dependency_rows[str(item["source_id"])] = dict(item)
        for source_id, item in dependency_rows.items():
            connection.execute(
                """
                INSERT INTO kops.job_inputs(
                    job_id, source_id, source_revision, source_policy_revision,
                    object_key, content_hash, admission_decision
                ) VALUES (%s, %s, %s, %s, %s, %s, 'inherited_from_authorized_page')
                """,
                (job_id, source_id, item["source_revision"], item["source_policy_revision"], item["object_key"], item["content_hash"]),
            )
        slug = f"saved-answer-{response_id[:8]}"
        payload = {
            "pages": [{
                "slug": slug,
                "title": f"Saved answer: {response['question'][:80]}",
                "object_key": response["answer_object_key"],
                "content_hash": response["answer_hash"],
                "citations": response["citations"],
            }],
            "contradictions": [],
            "quality_notes": ["Promoted from a query response; publication still requires verification and authorization."],
        }
        manifest = {"page_citations": response["citations"], "source_dependencies": sorted(dependency_rows)}
        candidate_hash = hashlib.sha256(canonical_json(payload).encode()).hexdigest()
        candidate_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO kops.candidates(
                candidate_id, job_id, audience_id, candidate_hash, manifest_hash,
                payload, validation_findings, state, created_by
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, 'draft', 'query-service')
            """,
            (candidate_id, job_id, response["audience_id"], candidate_hash, hashlib.sha256(canonical_json(manifest).encode()).hexdigest(), json.dumps(payload), json.dumps([{"severity": "info", "code": "answer_promotion"}])),
        )
        connection.execute(
            "INSERT INTO kops.job_events(job_id, state, detail) VALUES (%s, 'ready', 'Saved answer became a private candidate; no publication occurred')",
            (job_id,),
        )
        connection.commit()
    _event(principal, "answer.promote", "candidate", candidate_id, response["audience_id"], "allowed", "save_answer_grant", "committed", details={"response_id": response_id, "candidate_hash": candidate_hash})
    return _redirect("review", f"Answer became private candidate {candidate_id}; it is not published")


def _commit_source_revision(
    principal: Principal, source: dict[str, Any], content: str, origin: str
) -> tuple[int, int, str]:
    source_id = str(source["source_id"])
    if not content.strip() or len(content.encode()) > 100000:
        raise HTTPException(status_code=400, detail="revision content is required and limited to 100000 bytes")
    new_revision = source["current_revision"] + 1
    object_key, digest = store.put_immutable("sources", source_id, str(new_revision), content)
    with database.connection() as connection:
        connection.execute(
            """
            INSERT INTO kops.source_versions(source_id, revision, object_key, content_hash, origin, created_by)
            VALUES (%s, %s, %s, %s, %s, %s)
            """,
            (source_id, new_revision, object_key, digest, origin, principal.subject_id),
        )
        connection.execute(
            "UPDATE kops.sources SET current_revision = %s WHERE source_id = %s AND current_revision = %s",
            (new_revision, source_id, source["current_revision"]),
        )
        stale_documents = connection.execute(
            """
            SELECT d.document_id FROM kops.documents d
            WHERE d.publication_state = 'stale' AND EXISTS (
                SELECT 1 FROM kops.dependencies dep
                WHERE dep.document_id = d.document_id AND dep.source_id = %s
                  AND dep.document_version = d.current_version
            )
            """,
            (source_id,),
        ).fetchall()
        connection.commit()
    _event(principal, "source.revise", "source", source_id, source["audience_id"], "allowed", "maintenance_grant", "committed", details={"revision": new_revision, "stale_document_count": len(stale_documents), "content_hash": digest})
    return new_revision, len(stale_documents), digest


@app.post("/sources/{source_id}/revise")
def revise_source(
    source_id: str,
    content: str = Form(),
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    source = _source_for_read(principal, source_id)
    _require(principal, "maintain", source["audience_id"])
    new_revision, stale_count, _ = _commit_source_revision(
        principal, source, content, "explicit-maintenance-update"
    )
    return _redirect("maintain", f"Source revision {new_revision} committed; {stale_count} dependent pages are stale and need regeneration")


@app.post("/fixtures/revise-budget")
def apply_revised_budget(
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    with database.connection() as connection:
        row = connection.execute(
            "SELECT source_id FROM kops.sources WHERE title = 'Finance budget' AND synthetic AND active"
        ).fetchone()
    if not row:
        raise HTTPException(status_code=409, detail="load the synthetic corpus first")
    source = _source_for_read(principal, str(row["source_id"]))
    _require(principal, "maintain", source["audience_id"])
    body = (fixture_root / "revised-finance-budget.md").read_text(encoding="utf-8")
    new_revision, stale_count, _ = _commit_source_revision(
        principal, source, body, "synthetic:revised-finance-budget"
    )
    return _redirect("maintain", f"Synthetic revised budget became source revision {new_revision}; {stale_count} dependent pages are stale")


@app.post("/access/membership")
def change_membership(
    subject_id: str = Form(),
    group_id: str = Form(),
    active: bool = Form(default=False),
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    if not _is_operator(principal) or ("policy_admin" not in principal.action_grants and "*" not in principal.action_grants):
        raise HTTPException(status_code=403, detail="policy administration is required")
    if group_id not in {"engineering", "finance"}:
        raise HTTPException(status_code=400, detail="unsupported fixture group")
    _event(principal, "membership.change", "membership", f"{subject_id}:{group_id}", None, "allowed", "policy_admin_grant", "attempt", details={"active": active})
    with database.connection() as connection:
        updated = connection.execute(
            """
            INSERT INTO kops.memberships(subject_id, group_id, active, revision)
            VALUES (%s, %s, %s, 1)
            ON CONFLICT (subject_id, group_id) DO UPDATE SET
              active = EXCLUDED.active, revision = kops.memberships.revision + 1, updated_at = now()
            RETURNING revision
            """,
            (subject_id, group_id, active),
        ).fetchone()
        connection.execute(
            "UPDATE kops.publication_authorizations SET status = 'invalidated' WHERE authorized_by = %s AND status = 'active'",
            (subject_id,),
        )
        if not active:
            connection.execute(
                "UPDATE kops.jobs SET cancel_requested = true WHERE requested_by = %s AND status IN ('queued', 'running')",
                (subject_id,),
            )
        connection.commit()
    _event(principal, "membership.change", "membership", f"{subject_id}:{group_id}", None, "allowed", "authoritative_membership_updated", "committed", details={"active": active, "revision": updated["revision"]})
    return _redirect("access", f"Membership {subject_id}/{group_id} is now {'active' if active else 'revoked'}; existing sessions observe it immediately")


@app.post("/access/source-policy")
def change_source_policy(
    source_id: str = Form(),
    audience_id: str = Form(),
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    if not _is_operator(principal):
        raise HTTPException(status_code=403, detail="policy administration is required")
    _groups_for_audience(audience_id)
    _event(principal, "source.policy_change", "source", source_id, audience_id, "allowed", "policy_admin_grant", "attempt")
    with database.connection() as connection:
        source = connection.execute(
            "UPDATE kops.sources SET audience_id = %s, policy_revision = policy_revision + 1 WHERE source_id = %s RETURNING policy_revision",
            (audience_id, source_id),
        ).fetchone()
        if not source:
            raise HTTPException(status_code=404, detail="source not found")
        blocked = connection.execute(
            """
            SELECT d.document_id FROM kops.documents d
            WHERE d.publication_state = 'blocked' AND EXISTS (
                SELECT 1 FROM kops.dependencies dep
                WHERE dep.document_id = d.document_id AND dep.source_id = %s
                  AND dep.document_version = d.current_version
            )
            """,
            (source_id,),
        ).fetchall()
        connection.commit()
    _event(principal, "source.policy_change", "source", source_id, audience_id, "allowed", "policy_revision_committed", "committed", details={"policy_revision": source["policy_revision"], "blocked_document_count": len(blocked)})
    return _redirect("access", f"Source policy revision {source['policy_revision']} applied; {len(blocked)} dependent pages are blocked")


@app.post("/demo/audit-availability")
def audit_availability(
    enabled: bool = Form(default=False),
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    if not settings.demo_mode or not _is_operator(principal):
        raise HTTPException(status_code=404, detail="demo failure controls are unavailable")
    if not enabled:
        _event(principal, "demo.audit_availability", "audit_collector", None, None, "allowed", "operator_failure_injection", "attempt", details={"enabled": False})
    with database.connection() as connection:
        connection.execute(
            "UPDATE kops.demo_controls SET enabled = %s, updated_by = %s, updated_at = now() WHERE control_name = 'audit_available'",
            (enabled, principal.subject_id),
        )
        connection.commit()
    if enabled:
        _event(principal, "demo.audit_availability", "audit_collector", None, None, "allowed", "operator_failure_injection", "committed", details={"enabled": True})
    return _redirect("audit", f"Durable audit is now {'available' if enabled else 'deliberately unavailable'}; protected reads and publication {'resume' if enabled else 'fail closed'}", "ok" if enabled else "error")


@app.post("/demo/stale-approval")
def inject_stale_approval(
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    if not settings.demo_mode or not _is_operator(principal):
        raise HTTPException(status_code=404, detail="demo failure controls are unavailable")
    with database.connection() as connection:
        latest = connection.execute(
            """
            SELECT pa.audience_id FROM kops.publication_authorizations pa
            WHERE pa.status = 'active' ORDER BY pa.created_at DESC LIMIT 1
            """
        ).fetchone()
        if not latest:
            raise HTTPException(status_code=409, detail="an active authorization is required")
        connection.execute(
            "UPDATE kops.audiences SET policy_revision = policy_revision + 1 WHERE audience_id = %s",
            (latest["audience_id"],),
        )
        connection.commit()
    _event(principal, "demo.stale_approval", "audience", latest["audience_id"], latest["audience_id"], "allowed", "operator_failure_injection", "committed")
    return _redirect("publish", "Audience policy revision changed after authorization; the bounded publisher will refuse the stale approval", "error")


@app.post("/demo/conflicting-edit")
def inject_conflicting_edit(
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    if not settings.demo_mode or not _is_operator(principal):
        raise HTTPException(status_code=404, detail="demo failure controls are unavailable")
    with database.connection() as connection:
        base = connection.execute(
            """
            SELECT pa.*, c.payload FROM kops.publication_authorizations pa
            JOIN kops.candidates c ON c.candidate_id = pa.candidate_id
            WHERE c.state = 'authorized' ORDER BY pa.created_at DESC LIMIT 1
            """
        ).fetchone()
        if not base:
            raise HTTPException(status_code=409, detail="an authorized candidate is required")
        wrong_expected = dict(base["expected_versions"])
        first_slug = next(iter(wrong_expected))
        wrong_expected[first_slug] = max(0, int(wrong_expected[first_slug]) - 1)
        if wrong_expected[first_slug] == int(base["expected_versions"][first_slug]):
            wrong_expected[first_slug] = int(base["expected_versions"][first_slug]) + 1
        authorization_id = str(uuid.uuid4())
        operation_id = str(uuid.uuid4())
        connection.execute(
            """
            INSERT INTO kops.publication_authorizations(
                authorization_id, candidate_id, candidate_hash, audience_id, authorized_by,
                expected_versions, dependency_revisions, policy_revisions, expires_at, status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now() + interval '10 minutes', 'active')
            """,
            (authorization_id, base["candidate_id"], base["candidate_hash"], base["audience_id"], principal.subject_id, json.dumps(wrong_expected), json.dumps(base["dependency_revisions"]), json.dumps(base["policy_revisions"])),
        )
        connection.execute(
            """
            INSERT INTO kops.operations(operation_id, authorization_id, operation_type, idempotency_key, requested_by, status)
            VALUES (%s, %s, 'publish_document', %s, %s, 'pending')
            """,
            (operation_id, authorization_id, f"conflict-demo:{operation_id}", principal.subject_id),
        )
        connection.commit()
    try:
        _call_publisher(operation_id)
    except HTTPException as error:
        return _redirect("publish", f"Actual conflicting write was refused: {error.detail}", "error")
    return _redirect("publish", "Conflict scenario unexpectedly committed", "error")


@app.post("/demo/replay-publication")
def replay_publication(
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    if not settings.demo_mode or not _is_operator(principal):
        raise HTTPException(status_code=404, detail="demo failure controls are unavailable")
    with database.connection() as connection:
        operation = connection.execute(
            "SELECT operation_id FROM kops.operations WHERE status IN ('committed', 'uncertain') ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
    if not operation:
        raise HTTPException(status_code=409, detail="a committed or uncertain operation is required")
    result = _call_publisher(str(operation["operation_id"]))
    return _redirect("publish", f"Replay reconciled operation {operation['operation_id']} as {result['status']} without a duplicate revision")


@app.post("/demo/policy-change-during-job")
def policy_change_during_job(
    csrf: str = Form(),
    kops_session: str | None = Cookie(default=None),
) -> RedirectResponse:
    principal = _principal(kops_session)
    _require_csrf(principal, csrf)
    if not settings.demo_mode or not _is_operator(principal):
        raise HTTPException(status_code=404, detail="demo failure controls are unavailable")
    with database.connection() as connection:
        item = connection.execute(
            """
            SELECT j.job_id, ji.source_id FROM kops.jobs j JOIN kops.job_inputs ji ON ji.job_id = j.job_id
            WHERE j.status IN ('queued', 'running') ORDER BY j.created_at DESC LIMIT 1
            """
        ).fetchone()
        if not item:
            raise HTTPException(status_code=409, detail="a queued or running job is required")
        connection.execute(
            "UPDATE kops.sources SET policy_revision = policy_revision + 1 WHERE source_id = %s",
            (item["source_id"],),
        )
        connection.commit()
    _event(principal, "demo.mid_job_policy_change", "job", str(item["job_id"]), None, "allowed", "operator_failure_injection", "committed", details={"source_id": str(item["source_id"])})
    return _redirect("compile", "A source policy changed during the job; execution or publication will fail its fresh check", "error")


@app.get("/api/state")
def api_state(kops_session: str | None = Cookie(default=None)) -> dict[str, Any]:
    principal = _principal(kops_session)
    state = _dashboard_state(principal)
    return {
        "run_id": str(state["run"]["run_id"]) if state["run"] else None,
        "jobs": [
            {
                "job_id": str(job["job_id"]),
                "status": job["status"],
                "candidate_id": str(job["candidate_id"]) if job["candidate_id"] else None,
                "input_bytes": job["input_bytes"],
                "output_bytes": job["output_bytes"],
                "model_latency_ms": job["model_latency_ms"],
                "error": job["error_sanitized"],
            }
            for job in state["jobs"]
        ],
        "events": [
            {"job_id": str(item["job_id"]), "state": item["state"], "detail": item["detail"], "created_at": item["created_at"].isoformat()}
            for item in state["job_events"]
        ],
    }
