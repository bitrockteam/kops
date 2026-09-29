from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path


SAFE_COMPONENT = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}$")


class LocalContentStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o750)

    def _component(self, value: str) -> str:
        if not SAFE_COMPONENT.fullmatch(value):
            raise ValueError("invalid content identifier")
        return value

    def put_immutable(self, namespace: str, object_id: str, revision: str, body: str) -> tuple[str, str]:
        safe_namespace = self._component(namespace)
        safe_object_id = self._component(object_id)
        safe_revision = self._component(revision)
        body_bytes = body.encode("utf-8")
        digest = hashlib.sha256(body_bytes).hexdigest()
        relative = Path(safe_namespace) / safe_object_id / f"{safe_revision}-{digest}.md"
        destination = (self.root / relative).resolve()
        if self.root not in destination.parents:
            raise ValueError("content path escaped storage root")
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        if destination.exists():
            if destination.read_bytes() != body_bytes:
                raise ValueError("immutable content collision")
            return relative.as_posix(), digest
        file_descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
        with os.fdopen(file_descriptor, "wb") as stream:
            stream.write(body_bytes)
            stream.flush()
            os.fsync(stream.fileno())
        return relative.as_posix(), digest

    def read(self, object_key: str) -> str:
        relative = Path(object_key)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("invalid content object key")
        source = (self.root / relative).resolve()
        if self.root not in source.parents or not source.is_file():
            raise FileNotFoundError("content object not found")
        return source.read_text(encoding="utf-8")
