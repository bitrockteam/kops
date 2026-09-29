"""Read-only view of the raw store volume for the Collect screen.

The collector service is the only writer; the API only mounts ``raw_data`` read-only and
reads the manifests, quarantine records and per-collector counts it left behind.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def list_runs(raw_root: Path, limit: int = 10) -> list[dict[str, Any]]:
    runs_dir = raw_root / "runs"
    if not runs_dir.is_dir():
        return []
    paths = sorted(runs_dir.glob("*.json"), reverse=True)[:limit]
    return [record for record in (_read_json(path) for path in paths) if record]


def list_quarantine(raw_root: Path) -> list[dict[str, Any]]:
    quarantine_dir = raw_root / "quarantine"
    if not quarantine_dir.is_dir():
        return []
    return [
        record for record in (_read_json(path) for path in sorted(quarantine_dir.rglob("*.json"))) if record
    ]

def raw_counts(raw_root: Path) -> dict[str, int]:
    raw_dir = raw_root / "raw"
    if not raw_dir.is_dir():
        return {}
    return {
        collector_dir.name: len(list(collector_dir.glob("*.json")))
        for collector_dir in sorted(raw_dir.iterdir())
        if collector_dir.is_dir()
    }


def restricted_items(raw_root: Path) -> list[dict[str, Any]]:
    raw_dir = raw_root / "raw"
    if not raw_dir.is_dir():
        return []
    return [
        record
        for record in (_read_json(path) for path in sorted(raw_dir.rglob("*.json")))
        if record and record.get("restricted")
    ]
