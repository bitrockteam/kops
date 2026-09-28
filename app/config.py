from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _read_secret(name: str, default: str = "") -> str:
    direct = os.getenv(name)
    if direct:
        return direct
    secret_file = os.getenv(f"{name}_FILE")
    if secret_file and Path(secret_file).is_file():
        return Path(secret_file).read_text(encoding="utf-8").strip()
    return default


@dataclass(frozen=True)
class Settings:
    service: str
    database_url: str
    content_root: Path
    session_secret: str
    internal_token: str
    audit_token: str
    audit_url: str
    publisher_url: str
    content_url: str
    demo_mode: bool
    allowed_model_hosts: frozenset[str]
    audit_timeout_seconds: float

    @classmethod
    def load(cls, service: str | None = None) -> "Settings":
        selected_service = service or os.getenv("KOPS_SERVICE", "api")
        role = os.getenv("KOPS_DB_ROLE", f"kops_{selected_service}")
        password = _read_secret("KOPS_DB_PASSWORD")
        host = os.getenv("KOPS_DB_HOST", "db")
        port = os.getenv("KOPS_DB_PORT", "5432")
        database = os.getenv("KOPS_DB_NAME", "kops")
        database_url = os.getenv(
            "KOPS_DATABASE_URL",
            f"postgresql://{role}:{password}@{host}:{port}/{database}",
        )
        return cls(
            service=selected_service,
            database_url=database_url,
            content_root=Path(os.getenv("KOPS_CONTENT_ROOT", "/var/lib/kops/content")),
            session_secret=_read_secret("KOPS_SESSION_SECRET", "unsafe-development-only"),
            internal_token=_read_secret("KOPS_INTERNAL_TOKEN", "unsafe-development-only"),
            audit_token=_read_secret("KOPS_AUDIT_TOKEN", "unsafe-development-only"),
            audit_url=os.getenv("KOPS_AUDIT_URL", "http://audit:8083"),
            publisher_url=os.getenv("KOPS_PUBLISHER_URL", "http://publisher:8082"),
            content_url=os.getenv("KOPS_CONTENT_URL", "http://content:8084"),
            demo_mode=os.getenv("KOPS_DEMO_MODE", "true").lower() == "true",
            allowed_model_hosts=frozenset(
                item.strip().lower()
                for item in os.getenv("KOPS_ALLOWED_MODEL_HOSTS", "host.docker.internal").split(",")
                if item.strip()
            ),
            audit_timeout_seconds=float(os.getenv("KOPS_AUDIT_TIMEOUT_SECONDS", "2")),
        )
