from __future__ import annotations

import hmac
import uuid
from datetime import UTC, datetime
from typing import Any

import httpx

from app.config import Settings


class AuditUnavailable(RuntimeError):
    pass


class AuditClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def append(self, event: dict[str, Any]) -> str:
        event_id = event.get("event_id") or str(uuid.uuid4())
        payload = {
            "event_id": event_id,
            "occurred_at": event.get("occurred_at") or datetime.now(UTC).isoformat(),
            **event,
        }
        try:
            response = httpx.post(
                f"{self.settings.audit_url}/internal/events",
                json=payload,
                headers={"Authorization": f"Bearer {self.settings.audit_token}"},
                timeout=self.settings.audit_timeout_seconds,
                follow_redirects=False,
            )
            response.raise_for_status()
        except (httpx.HTTPError, ValueError) as error:
            raise AuditUnavailable("durable audit recording is unavailable") from error
        return event_id


def internal_token_valid(provided: str | None, expected: str) -> bool:
    if not provided or not provided.startswith("Bearer "):
        return False
    return hmac.compare_digest(provided[7:], expected)
