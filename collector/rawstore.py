"""The raw store: content-addressed, immutable, file based. No model, standard library only."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class RawStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        (self.root / "raw").mkdir(parents=True, exist_ok=True)
        (self.root / "quarantine").mkdir(parents=True, exist_ok=True)
        (self.root / "runs").mkdir(parents=True, exist_ok=True)

    def write_raw(
        self, collector: str, item_id: str, content: str, *, prefilter_version: int, restricted: bool = False
    ) -> str:
        sha = content_hash(content)
        directory = self.root / "raw" / collector
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{sha}.json"
        if not path.exists():
            path.write_text(
                canonical_json({
                    "item_id": item_id,
                    "collector": collector,
                    "sha256": sha,
                    "content": content,
                    "captured_at": datetime.now(UTC).isoformat(),
                    "prefilter_version": prefilter_version,
                    "restricted": restricted,
                }) + "\n",
                encoding="utf-8",
            )
        return sha

    def write_quarantine(
        self, collector: str, item_id: str, content: str, hits: list[dict], *, prefilter_version: int
    ) -> str:
        sha = content_hash(content)
        directory = self.root / "quarantine" / collector
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{sha}.json"
        path.write_text(
            canonical_json({
                "item_id": item_id,
                "collector": collector,
                "sha256": sha,
                "rules": sorted({hit["rule"] for hit in hits}),
                "hits": hits,
                "captured_at": datetime.now(UTC).isoformat(),
                "prefilter_version": prefilter_version,
            }) + "\n",
            encoding="utf-8",
        )
        return sha

    def write_run(self, run_id: str, manifest: dict) -> None:
        (self.root / "runs" / f"{run_id}.json").write_text(canonical_json(manifest) + "\n", encoding="utf-8")
