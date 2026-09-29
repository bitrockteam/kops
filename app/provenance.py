from __future__ import annotations

from typing import Any


class MixedSourceVersions(ValueError):
    pass


def inherit_dependency(dependencies: dict[str, dict[str, Any]], item: Any) -> None:
    source_id = str(item["source_id"])
    existing = dependencies.get(source_id)
    if existing and (
        existing["source_revision"] != item["source_revision"]
        or existing["source_policy_revision"] != item["source_policy_revision"]
    ):
        raise MixedSourceVersions(
            "answer inputs contain multiple versions of one source; promotion requires regeneration from one consistent source set"
        )
    dependencies[source_id] = dict(item)
