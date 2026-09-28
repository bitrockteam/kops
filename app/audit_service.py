from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from psycopg.errors import UniqueViolation

from app.audit import internal_token_valid
from app.config import Settings, _read_secret
from app.db import Database


settings = Settings.load("audit")
database = Database(settings)
AUDIT_ACTORS = {
    _read_secret("KOPS_AUDIT_API_TOKEN"): {"kops-api"},
    _read_secret("KOPS_AUDIT_WORKER_TOKEN"): {"compilation-worker"},
    _read_secret("KOPS_AUDIT_PUBLISHER_TOKEN"): {"bounded-publication-executor", "publication-service"},
}


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.open()
    try:
        yield
    finally:
        database.close()


app = FastAPI(title="kops protected audit collector", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/events", status_code=201)
def append_event(event: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, str]:
    matched_actors = next(
        (actors for token, actors in AUDIT_ACTORS.items() if token and internal_token_valid(authorization, token)),
        None,
    )
    if not matched_actors:
        raise HTTPException(status_code=401, detail="internal authentication required")
    if event.get("actor") not in matched_actors:
        raise HTTPException(status_code=403, detail="audit actor does not match the authenticated service")
    with database.connection() as connection:
        available = connection.execute(
            "SELECT enabled FROM kops.demo_controls WHERE control_name = 'audit_available'"
        ).fetchone()
        if not available or not available["enabled"]:
            raise HTTPException(status_code=503, detail="audit collector deliberately unavailable")
        try:
            connection.execute(
                """
                INSERT INTO kops.audit_events (
                    event_id, correlation_id, occurred_at, initiator, actor, delegation_ref,
                    action, resource_type, resource_id, audience_id, decision, reason_code,
                    policy_revision, outcome, authorization_ref, operation_ref, details
                ) VALUES (
                    %(event_id)s, %(correlation_id)s, %(occurred_at)s, %(initiator)s, %(actor)s,
                    %(delegation_ref)s, %(action)s, %(resource_type)s, %(resource_id)s,
                    %(audience_id)s, %(decision)s, %(reason_code)s, %(policy_revision)s,
                    %(outcome)s, %(authorization_ref)s, %(operation_ref)s, %(details)s
                )
                """,
                {
                    "event_id": event["event_id"],
                    "correlation_id": event["correlation_id"],
                    "occurred_at": event["occurred_at"],
                    "initiator": event.get("initiator"),
                    "actor": event["actor"],
                    "delegation_ref": event.get("delegation_ref"),
                    "action": event["action"],
                    "resource_type": event["resource_type"],
                    "resource_id": event.get("resource_id"),
                    "audience_id": event.get("audience_id"),
                    "decision": event["decision"],
                    "reason_code": event["reason_code"],
                    "policy_revision": event.get("policy_revision"),
                    "outcome": event["outcome"],
                    "authorization_ref": event.get("authorization_ref"),
                    "operation_ref": event.get("operation_ref"),
                    "details": json.dumps(event.get("details", {})),
                },
            )
            connection.commit()
        except UniqueViolation:
            connection.rollback()
    return {"event_id": event["event_id"]}


@app.delete("/internal/events/{event_id}", status_code=405)
@app.patch("/internal/events/{event_id}", status_code=405)
def immutable_audit(event_id: str) -> None:
    raise HTTPException(status_code=405, detail=f"audit event {event_id} is append-only")
