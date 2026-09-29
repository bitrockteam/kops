"""Deterministic fetchers over fixtures/meridian, one function per collector name."""

from __future__ import annotations

import glob
import json
import re
from datetime import UTC, datetime
from pathlib import Path

FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n\n(.*)$", re.S)
WEB_LOG_TS_RE = re.compile(r'^\{"ts": "([^"]+)"')
DB_LOG_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}):\d{2}")


def _frontmatter_space(text: str) -> str | None:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    for line in match.group(1).splitlines():
        key, _, value = line.partition(":")
        if key.strip() == "space":
            return value.strip()
    return None


def collect_wiki(scope: dict) -> list[dict]:
    items = []
    for path in sorted(glob.glob(scope["path"])):
        text = Path(path).read_text(encoding="utf-8")
        items.append({
            "item_id": f"wiki/{Path(path).name}",
            "content": text,
            "space": _frontmatter_space(text),
        })
    for path in sorted(glob.glob(scope.get("adr", ""))) if scope.get("adr") else []:
        text = Path(path).read_text(encoding="utf-8")
        items.append({"item_id": f"adr/{Path(path).name}", "content": text, "space": None})
    return items


def collect_tickets(scope: dict) -> list[dict]:
    tickets = json.loads(Path(scope["path"]).read_text(encoding="utf-8"))
    return [
        {
            "item_id": f"tickets/{ticket['id']}",
            "content": json.dumps(ticket, sort_keys=True, ensure_ascii=False),
            "space": None,
        }
        for ticket in tickets
    ]


def collect_repo(scope: dict) -> list[dict]:
    commits = json.loads(Path(scope["path"]).read_text(encoding="utf-8"))
    batch_size = int(scope.get("batch", 20))
    items = []
    for start in range(0, len(commits), batch_size):
        batch = commits[start:start + batch_size]
        items.append({
            "item_id": f"repo/batch-{start // batch_size:04d}",
            "content": json.dumps(batch, sort_keys=True, ensure_ascii=False),
            "space": None,
        })
    return items


def _parse_window_minutes(window: str) -> int:
    if window.endswith("m"):
        return int(window[:-1])
    return int(window)


def _line_timestamp(line: str) -> datetime | None:
    match = WEB_LOG_TS_RE.match(line)
    if match:
        return datetime.fromisoformat(match.group(1).replace("Z", "+00:00"))
    match = DB_LOG_TS_RE.match(line)
    if match:
        return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M").replace(tzinfo=UTC)
    return None


def _bucket_key(ts: datetime, window_minutes: int) -> str:
    epoch_minutes = int(ts.timestamp() // 60)
    bucket_start_minutes = (epoch_minutes // window_minutes) * window_minutes
    bucket_dt = datetime.fromtimestamp(bucket_start_minutes * 60, tz=UTC)
    return bucket_dt.strftime("%Y-%m-%dT%H:%M")


def collect_logs(scope: dict) -> list[dict]:
    window_minutes = _parse_window_minutes(scope.get("window", "15m"))
    items = []
    for path in sorted(glob.glob(scope["path"])):
        stream = Path(path).stem
        buckets: dict[str, list[str]] = {}
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            ts = _line_timestamp(line)
            key = _bucket_key(ts, window_minutes) if ts else "unparsed"
            buckets.setdefault(key, []).append(line)
        for key in sorted(buckets):
            items.append({
                "item_id": f"logs/{stream}/{key}",
                "content": "\n".join(buckets[key]),
                "space": None,
            })
    return items


COLLECTORS = {
    "wiki": collect_wiki,
    "tickets": collect_tickets,
    "repo": collect_repo,
    "logs": collect_logs,
}
