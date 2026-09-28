from __future__ import annotations

import hashlib
import json
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import FastAPI, Header, HTTPException

from app.audit import AuditClient, AuditUnavailable, internal_token_valid
from app.config import Settings
from app.content import LocalContentStore
from app.db import PUBLICATION_POLICY_LOCK_KEY, Database


settings = Settings.load("publisher")
database = Database(settings, min_size=1, max_size=3)
store = LocalContentStore(settings.content_root)
audit = AuditClient(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.open()
    try:
        yield
    finally:
        database.close()


app = FastAPI(title="kops bounded publication executor", docs_url=None, redoc_url=None, lifespan=lifespan)


def _require_internal(authorization: str | None) -> None:
    if not internal_token_valid(authorization, settings.internal_token):
        raise HTTPException(status_code=401, detail="internal authentication required")


def _fresh_operation(operation_id: str, connection: Any | None = None) -> dict[str, Any]:
    def fetch(active_connection: Any) -> Any:
        return active_connection.execute(
            """
            SELECT o.*, pa.candidate_id, pa.candidate_hash AS authorized_hash,
                   pa.audience_id, pa.authorized_by, pa.expected_versions,
                   pa.dependency_revisions, pa.policy_revisions, pa.expires_at,
                   pa.status AS authorization_status, c.candidate_hash, c.payload,
                   c.state AS candidate_state, c.job_id, j.cancel_requested, j.status AS job_status
            FROM kops.operations o
            JOIN kops.publication_authorizations pa ON pa.authorization_id = o.authorization_id
            JOIN kops.candidates c ON c.candidate_id = pa.candidate_id
            JOIN kops.jobs j ON j.job_id = c.job_id
            WHERE o.operation_id = %s
            """,
            (operation_id,),
        ).fetchone()
    if connection is None:
        with database.connection() as active_connection:
            row = fetch(active_connection)
    else:
        row = fetch(connection)
    if not row:
        raise HTTPException(status_code=404, detail="operation not found")
    return dict(row)


def _mark_refused(operation_id: str, code: str) -> None:
    with database.connection() as connection:
        connection.execute(
            """
            UPDATE kops.operations SET status = 'refused', error_code = %s, completed_at = now()
            WHERE operation_id = %s AND status NOT IN ('committed', 'uncertain')
            """,
            (code, operation_id),
        )
        connection.commit()


def _validate_freshness(operation: dict[str, Any], connection: Any) -> None:
    if operation["operation_type"] != "publish_document":
        raise ValueError("unsupported typed operation")
    if operation["authorization_status"] != "active":
        raise ValueError("authorization is not active")
    expires = operation["expires_at"]
    if expires <= datetime.now(UTC):
        raise ValueError("authorization expired")
    if operation["candidate_state"] != "authorized":
        raise ValueError("candidate is not authorized")
    if operation["authorized_hash"] != operation["candidate_hash"]:
        raise ValueError("candidate hash changed after authorization")
    if operation["cancel_requested"] or operation["job_status"] == "cancelled":
        raise ValueError("job was stopped")
    persona = connection.execute(
            "SELECT action_grants FROM kops.personas WHERE subject_id = %s AND active",
            (operation["authorized_by"],),
        ).fetchone()
    memberships = connection.execute(
            "SELECT group_id FROM kops.memberships WHERE subject_id = %s AND active",
            (operation["authorized_by"],),
        ).fetchall()
    audience = connection.execute(
            "SELECT required_groups, policy_revision FROM kops.audiences WHERE audience_id = %s AND active",
            (operation["audience_id"],),
        ).fetchone()
    dependencies = connection.execute(
            """
            SELECT ji.source_id, ji.source_revision, ji.source_policy_revision,
                   s.current_revision, s.policy_revision, s.active AS source_active,
                   sa.active AS source_audience_active, sa.required_groups AS source_required_groups
            FROM kops.job_inputs ji JOIN kops.sources s ON s.source_id = ji.source_id
            JOIN kops.audiences sa ON sa.audience_id = s.audience_id
            WHERE ji.job_id = %s
            """,
            (operation["job_id"],),
        ).fetchall()
    if not persona or ("publish" not in persona["action_grants"] and "*" not in persona["action_grants"]):
        raise ValueError("publisher action grant was revoked")
    if not audience or not set(audience["required_groups"]).issubset({row["group_id"] for row in memberships}):
        raise ValueError("publisher audience membership was revoked")
    expected_audience_revision = int(operation["policy_revisions"].get("audience", -1))
    if audience["policy_revision"] != expected_audience_revision:
        raise ValueError("audience policy changed after authorization")
    pinned_dependencies = {
        str(item["source_id"]): {
            "revision": item["source_revision"],
            "policy_revision": item["source_policy_revision"],
        }
        for item in dependencies
    }
    if pinned_dependencies != operation["dependency_revisions"]:
        raise ValueError("authorization dependency manifest does not match the candidate")
    for item in dependencies:
        if item["source_revision"] != item["current_revision"] or item["source_policy_revision"] != item["policy_revision"]:
            raise ValueError("source revision or policy changed after authorization")
        source_groups = set(item["source_required_groups"])
        if not item["source_active"] or not item["source_audience_active"] or not source_groups.issubset(set(audience["required_groups"])) or not source_groups.issubset({row["group_id"] for row in memberships}):
            raise ValueError("source is no longer admissible for publisher and destination")


def _deliver_outbox(operation_id: str) -> dict[str, Any] | None:
    with database.connection() as connection:
        outbox = connection.execute(
            "SELECT * FROM kops.audit_outbox WHERE operation_id = %s",
            (operation_id,),
        ).fetchone()
    if not outbox:
        return None
    audit.append(dict(outbox["event_payload"]))
    with database.connection() as connection:
        connection.execute(
            "UPDATE kops.audit_outbox SET delivery_status = 'delivered', delivered_at = now() WHERE outbox_id = %s",
            (outbox["outbox_id"],),
        )
        connection.execute(
            "UPDATE kops.operations SET status = 'committed' WHERE operation_id = %s",
            (operation_id,),
        )
        connection.commit()
    return dict(outbox["event_payload"])


def publish(operation_id: str) -> dict[str, Any]:
    operation = _fresh_operation(operation_id)
    if operation["status"] == "committed":
        try:
            _deliver_outbox(operation_id)
        except AuditUnavailable as error:
            with database.connection() as connection:
                connection.execute(
                    "UPDATE kops.operations SET status = 'uncertain', error_code = 'post_effect_audit_unavailable' WHERE operation_id = %s",
                    (operation_id,),
                )
                connection.commit()
            raise HTTPException(status_code=503, detail="committed effect remains audit-uncertain; reconcile later") from error
        return {"operation_id": operation_id, "status": "committed", "result": operation["result"], "reconciled": True}
    if operation["status"] == "uncertain":
        try:
            _deliver_outbox(operation_id)
        except AuditUnavailable as error:
            raise HTTPException(status_code=503, detail="committed effect remains audit-uncertain; reconcile later") from error
        refreshed = _fresh_operation(operation_id)
        return {"operation_id": operation_id, "status": "committed", "result": refreshed["result"], "reconciled": True}
    if operation["status"] == "refused":
        raise HTTPException(status_code=409, detail=f"operation refused: {operation['error_code']}")
    try:
        with database.connection() as connection:
            _validate_freshness(operation, connection)
        audit.append(
            {
                "correlation_id": f"operation:{operation_id}",
                "initiator": operation["requested_by"],
                "actor": "bounded-publication-executor",
                "delegation_ref": str(operation["authorization_id"]),
                "action": "publication.execute",
                "resource_type": "operation",
                "resource_id": operation_id,
                "audience_id": operation["audience_id"],
                "decision": "allowed",
                "reason_code": "fresh_authorization_validated",
                "outcome": "attempt",
                "authorization_ref": str(operation["authorization_id"]),
                "operation_ref": operation_id,
                "details": {"candidate_hash": operation["candidate_hash"]},
            }
        )
    except AuditUnavailable as error:
        _mark_refused(operation_id, "audit_unavailable")
        raise HTTPException(status_code=503, detail="publication blocked because durable audit is unavailable") from error
    except ValueError as error:
        _mark_refused(operation_id, "freshness_check_failed")
        raise HTTPException(status_code=409, detail=str(error)) from error

    published: list[dict[str, Any]] = []
    outbox_id = str(uuid.uuid4())
    try:
        with database.connection() as connection:
            connection.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (PUBLICATION_POLICY_LOCK_KEY,))
            locked = connection.execute(
                "UPDATE kops.operations SET status = 'executing' WHERE operation_id = %s AND status = 'pending' RETURNING operation_id",
                (operation_id,),
            ).fetchone()
            if not locked:
                raise ValueError("operation is no longer pending")
            operation = _fresh_operation(operation_id, connection)
            _validate_freshness(operation, connection)
            inputs = connection.execute(
                "SELECT source_id, source_revision, source_policy_revision FROM kops.job_inputs WHERE job_id = %s",
                (operation["job_id"],),
            ).fetchall()
            for page in operation["payload"]["pages"]:
                body = store.read(page["object_key"])
                if hashlib.sha256(body.encode()).hexdigest() != page["content_hash"]:
                    raise ValueError("candidate content integrity check failed")
                lock_key = f"{operation['audience_id']}:{page['slug']}"
                connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (lock_key,))
                document = connection.execute(
                    """
                    SELECT * FROM kops.documents WHERE audience_id = %s AND slug = %s FOR UPDATE
                    """,
                    (operation["audience_id"], page["slug"]),
                ).fetchone()
                current_version = document["current_version"] if document else 0
                expected_version = int(operation["expected_versions"].get(page["slug"], 0))
                if current_version != expected_version:
                    raise ValueError(f"expected-version conflict for {page['slug']}")
                if document:
                    document_id = str(document["document_id"])
                else:
                    document_id = str(uuid.uuid4())
                    connection.execute(
                        """
                        INSERT INTO kops.documents(document_id, slug, title, audience_id, current_version, publication_state)
                        VALUES (%s, %s, %s, %s, 0, 'published')
                        """,
                        (document_id, page["slug"], page["title"], operation["audience_id"]),
                    )
                new_version = current_version + 1
                object_key, body_hash = store.put_immutable("pages", document_id, str(new_version), body)
                connection.execute(
                    """
                    INSERT INTO kops.page_versions(
                        document_id, version, candidate_id, title, object_key, content_hash,
                        published_by, operation_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (document_id, new_version, operation["candidate_id"], page["title"], object_key, body_hash, operation["authorized_by"], operation_id),
                )
                for dependency in inputs:
                    connection.execute(
                        """
                        INSERT INTO kops.dependencies(
                            document_id, document_version, source_id, source_revision, source_policy_revision
                        ) VALUES (%s, %s, %s, %s, %s)
                        """,
                        (document_id, new_version, dependency["source_id"], dependency["source_revision"], dependency["source_policy_revision"]),
                    )
                connection.execute(
                    """
                    UPDATE kops.documents SET title = %s, current_version = %s, publication_state = 'published'
                    WHERE document_id = %s
                    """,
                    (page["title"], new_version, document_id),
                )
                published.append({"document_id": document_id, "slug": page["slug"], "version": new_version})
            result = {"pages": published, "candidate_id": str(operation["candidate_id"])}
            event_payload = {
                "event_id": str(uuid.uuid4()),
                "correlation_id": f"operation:{operation_id}",
                "initiator": operation["requested_by"],
                "actor": "publication-service",
                "delegation_ref": str(operation["authorization_id"]),
                "action": "publication.commit",
                "resource_type": "operation",
                "resource_id": operation_id,
                "audience_id": operation["audience_id"],
                "decision": "allowed",
                "reason_code": "conditional_transaction_committed",
                "outcome": "committed",
                "authorization_ref": str(operation["authorization_id"]),
                "operation_ref": operation_id,
                "details": {"pages": published},
            }
            connection.execute(
                """
                UPDATE kops.operations SET status = 'committed', result = %s, completed_at = now()
                WHERE operation_id = %s
                """,
                (json.dumps(result), operation_id),
            )
            connection.execute(
                "UPDATE kops.publication_authorizations SET status = 'consumed' WHERE authorization_id = %s",
                (operation["authorization_id"],),
            )
            connection.execute(
                "UPDATE kops.candidates SET state = 'published' WHERE candidate_id = %s",
                (operation["candidate_id"],),
            )
            connection.execute(
                """
                INSERT INTO kops.audit_outbox(outbox_id, operation_id, event_payload, delivery_status)
                VALUES (%s, %s, %s, 'pending')
                """,
                (outbox_id, operation_id, json.dumps(event_payload)),
            )
            connection.commit()
    except ValueError as error:
        _mark_refused(operation_id, "conditional_write_refused")
        raise HTTPException(status_code=409, detail=str(error)) from error
    except Exception as error:
        _mark_refused(operation_id, "publication_transaction_failed")
        raise HTTPException(status_code=500, detail="publication transaction failed") from error

    try:
        _deliver_outbox(operation_id)
    except AuditUnavailable as error:
        with database.connection() as connection:
            connection.execute(
                "UPDATE kops.operations SET status = 'uncertain', error_code = 'post_effect_audit_unavailable' WHERE operation_id = %s",
                (operation_id,),
            )
            connection.execute(
                "UPDATE kops.audit_outbox SET delivery_status = 'failed' WHERE operation_id = %s",
                (operation_id,),
            )
            connection.commit()
        raise HTTPException(status_code=503, detail="publication committed but confirmation is uncertain; reconcile by operation ID") from error
    return {"operation_id": operation_id, "status": "committed", "result": {"pages": published}, "reconciled": False}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/operations/{operation_id}/publish")
def publish_operation(operation_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    _require_internal(authorization)
    return publish(operation_id)
