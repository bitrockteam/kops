"""Minimal stdlib client for the protected audit collector's /internal/events route."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import uuid
from datetime import UTC, datetime
from typing import Any


class AuditUnavailable(RuntimeError):
    pass


def append_event(audit_url: str, token: str, event: dict[str, Any]) -> str:
    event_id = event.get("event_id") or str(uuid.uuid4())
    payload = {
        "event_id": event_id,
        "occurred_at": event.get("occurred_at") or datetime.now(UTC).isoformat(),
        **event,
    }
    request = urllib.request.Request(
        f"{audit_url}/internal/events",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            response.read()
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise AuditUnavailable("durable audit recording is unavailable") from error
    return event_id
