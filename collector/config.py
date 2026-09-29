from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def read_secret(name: str, default: str = "") -> str:
    direct = os.getenv(name)
    if direct:
        return direct
    secret_file = os.getenv(f"{name}_FILE")
    if secret_file and Path(secret_file).is_file():
        return Path(secret_file).read_text(encoding="utf-8").strip()
    return default


@dataclass(frozen=True)
class CollectorSettings:
    registry_path: Path
    raw_root: Path
    audit_url: str
    audit_token: str
    notify_url: str
    notify_topic: str
    internal_token: str
    port: int

    @classmethod
    def load(cls) -> "CollectorSettings":
        return cls(
            registry_path=Path(os.getenv("KOPS_COLLECTOR_REGISTRY", "/etc/kops/collectors.yaml")),
            raw_root=Path(os.getenv("KOPS_RAW_ROOT", "/var/lib/kops/raw")),
            audit_url=os.getenv("KOPS_AUDIT_URL", "http://audit:8083"),
            audit_token=read_secret("KOPS_AUDIT_TOKEN", "unsafe-development-only"),
            notify_url=os.getenv("KOPS_NOTIFY_URL", "http://notify:8085"),
            notify_topic=os.getenv("KOPS_NOTIFY_TOPIC", "kops-quarantine"),
            internal_token=read_secret("KOPS_INTERNAL_TOKEN", "unsafe-development-only"),
            port=int(os.getenv("KOPS_COLLECTOR_PORT", "8091")),
        )
