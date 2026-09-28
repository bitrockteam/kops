from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from app.content import LocalContentStore
from app.db import Database


PERSONAS = [
    ("eng_reader", "Evelyn Engineer", ["source_import", "compile", "read", "query", "save_answer"], False, ["engineering"]),
    ("finance_reader", "Finn Finance", ["source_import", "compile", "read", "query", "save_answer"], False, ["finance"]),
    ("dual_compiler", "Drew Dual-access Compiler", ["source_import", "compile", "read", "query", "save_answer", "maintain"], False, ["engineering", "finance"]),
    ("reviewer", "Riley Reviewer", ["review", "read"], False, ["engineering", "finance"]),
    ("publisher", "Parker Publisher", ["authorize", "publish", "read", "query"], False, ["engineering", "finance"]),
    ("auditor", "Avery Auditor", ["audit", "read"], False, ["engineering", "finance"]),
    ("operator_admin", "Olivia Local Operator", ["*"], True, ["engineering", "finance"]),
]

AUDIENCES = [
    ("engineering", "Engineering", ["engineering"]),
    ("finance", "Finance", ["finance"]),
    ("joint", "Engineering AND Finance", ["engineering", "finance"]),
]


def seed_reference_data(database: Database) -> None:
    with database.connection() as connection:
        for subject_id, display_name, grants, is_operator, groups in PERSONAS:
            connection.execute(
                """
                INSERT INTO kops.personas(subject_id, display_name, action_grants, is_operator)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (subject_id) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    action_grants = EXCLUDED.action_grants,
                    is_operator = EXCLUDED.is_operator,
                    active = true
                """,
                (subject_id, display_name, json.dumps(grants), is_operator),
            )
            for group_id in groups:
                connection.execute(
                    """
                    INSERT INTO kops.memberships(subject_id, group_id, active)
                    VALUES (%s, %s, true)
                    ON CONFLICT (subject_id, group_id) DO NOTHING
                    """,
                    (subject_id, group_id),
                )
        for audience_id, display_name, groups in AUDIENCES:
            connection.execute(
                """
                INSERT INTO kops.audiences(audience_id, display_name, required_groups)
                VALUES (%s, %s, %s)
                ON CONFLICT (audience_id) DO NOTHING
                """,
                (audience_id, display_name, json.dumps(groups)),
            )
        exists = connection.execute("SELECT run_id FROM kops.runs ORDER BY created_at LIMIT 1").fetchone()
        if not exists:
            connection.execute(
                "INSERT INTO kops.runs(label, created_by) VALUES ('Synthetic governed compilation run', 'operator_admin')"
            )
        connection.commit()


def load_synthetic_corpus(
    database: Database,
    store: LocalContentStore,
    fixture_root: Path,
    subject_id: str,
) -> list[str]:
    manifest = json.loads((fixture_root / "corpus.json").read_text(encoding="utf-8"))
    loaded: list[str] = []
    with database.connection() as connection:
        for item in manifest:
            existing = connection.execute(
                "SELECT source_id FROM kops.sources WHERE title = %s AND synthetic",
                (item["title"],),
            ).fetchone()
            if existing:
                loaded.append(str(existing["source_id"]))
                continue
            source_id = str(uuid.uuid4())
            body = (fixture_root / item["file"]).read_text(encoding="utf-8")
            object_key, digest = store.put_immutable("sources", source_id, "1", body)
            connection.execute(
                """
                INSERT INTO kops.sources(
                    source_id, title, audience_id, current_revision, synthetic, created_by
                ) VALUES (%s, %s, %s, 1, true, %s)
                """,
                (source_id, item["title"], item["audience_id"], subject_id),
            )
            connection.execute(
                """
                INSERT INTO kops.source_versions(
                    source_id, revision, object_key, content_hash, origin, created_by
                ) VALUES (%s, 1, %s, %s, %s, %s)
                """,
                (source_id, object_key, digest, f"synthetic:{item['key']}", subject_id),
            )
            loaded.append(source_id)
        connection.commit()
    return loaded
