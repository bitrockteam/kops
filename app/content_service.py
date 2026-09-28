from __future__ import annotations

import hashlib
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Header, HTTPException

from app.audit import internal_token_valid
from app.config import Settings
from app.content import LocalContentStore
from app.db import Database


settings = Settings.load("content")
database = Database(settings, min_size=1, max_size=3)
store = LocalContentStore(settings.content_root)


@asynccontextmanager
async def lifespan(_: FastAPI):
    database.open()
    try:
        yield
    finally:
        database.close()


app = FastAPI(title="kops admitted-content broker", docs_url=None, redoc_url=None, lifespan=lifespan)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/internal/jobs/{job_id}/inputs")
def admitted_inputs(job_id: str, authorization: str | None = Header(default=None)) -> dict[str, Any]:
    if not internal_token_valid(authorization, settings.internal_token):
        raise HTTPException(status_code=401, detail="internal authentication required")
    with database.connection() as connection:
        job = connection.execute(
            "SELECT status, workload_principal FROM kops.jobs WHERE job_id = %s",
            (job_id,),
        ).fetchone()
        if not job or job["status"] != "running" or job["workload_principal"] != "compilation-worker":
            raise HTTPException(status_code=409, detail="job is not an active compilation workload")
        rows = connection.execute(
            """
            SELECT ji.source_id, ji.source_revision, ji.source_policy_revision,
                   ji.object_key, ji.content_hash, s.title
            FROM kops.job_inputs ji JOIN kops.sources s ON s.source_id = ji.source_id
            WHERE ji.job_id = %s ORDER BY s.title
            """,
            (job_id,),
        ).fetchall()
    inputs: list[dict[str, Any]] = []
    for row in rows:
        body = store.read(row["object_key"])
        if hashlib.sha256(body.encode()).hexdigest() != row["content_hash"]:
            raise HTTPException(status_code=500, detail="admitted content integrity check failed")
        inputs.append(
            {
                "source_id": str(row["source_id"]),
                "revision": row["source_revision"],
                "policy_revision": row["source_policy_revision"],
                "title": row["title"],
                "content": body,
                "content_hash": row["content_hash"],
            }
        )
    return {"job_id": job_id, "inputs": inputs}
