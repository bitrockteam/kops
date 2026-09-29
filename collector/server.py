"""The collector service: a stdlib HTTP server triggered by the API, never by the host directly.

Deterministic Python, standard library only, no model call. One request runs one collector or
all four, applies the rule pre-filter, writes content-addressed raw items, quarantines hits,
rings ntfy, reports to the durable audit and returns the run manifest.
"""

from __future__ import annotations

import hmac
import json
import threading
import uuid
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from collector import prefilter, sources
from collector.audit_client import AuditUnavailable, append_event
from collector.config import CollectorSettings
from collector.notify_client import ring
from collector.rawstore import RawStore
from collector.registry import check_registration, load_registrations, parse_registry, save_registrations, scope_fingerprint

settings = CollectorSettings.load()
store = RawStore(settings.raw_root)
registrations_path = settings.raw_root / "registrations.json"
run_lock = threading.Lock()


def _token_valid(authorization: str | None) -> bool:
    if not authorization or not authorization.startswith("Bearer "):
        return False
    return hmac.compare_digest(authorization[7:], settings.internal_token)


def _load_registry() -> dict:
    text = settings.registry_path.read_text(encoding="utf-8")
    return parse_registry(text)


def _bootstrap_registrations(registry: dict) -> dict:
    registrations = load_registrations(registrations_path)
    changed = False
    for entry in registry.get("collectors", []):
        name = entry["name"]
        if name not in registrations:
            registrations[name] = {
                "scope_fingerprint": scope_fingerprint(entry["scope"]),
                "owner": entry["owner"],
                "registered_at": datetime.now(UTC).isoformat(),
            }
            changed = True
    if changed:
        save_registrations(registrations_path, registrations)
    return registrations


def _report(action: str, resource_id: str, decision: str, reason_code: str, outcome: str, details: dict) -> None:
    try:
        append_event(settings.audit_url, settings.audit_token, {
            "correlation_id": str(uuid.uuid4()),
            "initiator": None,
            "actor": "raw-store-collector",
            "action": action,
            "resource_type": "collector_run",
            "resource_id": resource_id,
            "audience_id": None,
            "decision": decision,
            "reason_code": reason_code,
            "outcome": outcome,
            "details": details,
        })
    except AuditUnavailable:
        pass


def _run_one(name: str, entry: dict, prefilter_version: int) -> dict:
    fetch = sources.COLLECTORS[name]
    items = fetch(entry["scope"])
    admitted, quarantined = [], []
    for item in items:
        hits = prefilter.find_hits(item["content"], space=item.get("space"))
        if hits:
            sha = store.write_quarantine(name, item["item_id"], item["content"], hits, prefilter_version=prefilter_version)
            quarantined.append({"item_id": item["item_id"], "sha256": sha, "rules": sorted({h["rule"] for h in hits})})
        else:
            restricted = prefilter.is_restricted(item.get("space"))
            sha = store.write_raw(
                name, item["item_id"], item["content"], prefilter_version=prefilter_version, restricted=restricted
            )
            admitted.append({"item_id": item["item_id"], "sha256": sha, "restricted": restricted})
    return {"collector": name, "seen": len(items), "admitted": admitted, "quarantined": quarantined}


def handle_run(payload: dict) -> tuple[int, dict]:
    requested = str(payload.get("collector") or "all")
    requested_by = payload.get("requested_by")
    registry = _load_registry()
    by_name = {entry["name"]: entry for entry in registry.get("collectors", [])}
    prefilter_version = int(registry.get("prefilter", {}).get("version", 1))
    names = list(by_name) if requested == "all" else [requested]
    run_id = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}-{uuid.uuid4().hex[:8]}"
    started_at = datetime.now(UTC).isoformat()

    with run_lock:
        registrations = _bootstrap_registrations(registry)
        results, refused = [], []
        for name in names:
            entry = by_name.get(name)
            if entry is None:
                refused.append({"collector": name, "reason": "not_registered"})
                _report("collector.run.refused", name, "denied", "collector_not_registered", "refused", {"collector": name})
                continue
            status, detail = check_registration(name, entry["scope"], registrations)
            if status != "ok":
                refused.append({"collector": name, "reason": status, "detail": detail})
                _report("collector.run.refused", name, "denied", status, "refused", {"collector": name, "detail": detail})
                continue
            result = _run_one(name, entry, prefilter_version)
            results.append(result)
            _report(
                "collector.run", name, "allowed", "prefilter_applied", "completed",
                {"seen": result["seen"], "admitted": len(result["admitted"]), "quarantined": len(result["quarantined"])},
            )

        total_quarantined = sum(len(result["quarantined"]) for result in results)
        manifest = {
            "run_id": run_id,
            "requested": requested,
            "requested_by": requested_by,
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "prefilter_version": prefilter_version,
            "results": results,
            "refused": refused,
        }
        store.write_run(run_id, manifest)

    if total_quarantined:
        lines = [
            f"{item['item_id']} ({', '.join(item['rules'])})"
            for r in results for item in r["quarantined"]
        ]
        ring(
            settings.notify_url, settings.notify_topic,
            f"Run {run_id} quarantined {total_quarantined} item(s):\n" + "\n".join(lines),
            title="kops raw store quarantine",
        )
    _report(
        "collector.run.manifest", run_id, "allowed", "run_complete", "committed",
        {"requested": requested, "quarantined": total_quarantined, "refused": [r["collector"] for r in refused]},
    )
    status_code = 200 if results or not refused else 403
    return status_code, manifest


def handle_register(payload: dict) -> tuple[int, dict]:
    name = payload.get("collector")
    registry = _load_registry()
    by_name = {entry["name"]: entry for entry in registry.get("collectors", [])}
    entry = by_name.get(name)
    if entry is None:
        return 404, {"detail": f"collector '{name}' is not declared in the registry file"}
    with run_lock:
        registrations = load_registrations(registrations_path)
        registrations[name] = {
            "scope_fingerprint": scope_fingerprint(entry["scope"]),
            "owner": entry["owner"],
            "registered_at": datetime.now(UTC).isoformat(),
        }
        save_registrations(registrations_path, registrations)
    _report("collector.register", name, "allowed", "owner_registered_scope", "committed", {"collector": name})
    return 200, {"collector": name, "registered": True}


class Handler(BaseHTTPRequestHandler):
    server_version = "kops-collector/1"

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - stdlib signature
        pass

    def _write_json(self, status_code: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - stdlib signature
        if self.path == "/health":
            try:
                registry = _load_registry()
                self._write_json(200, {"status": "ok", "collectors": [c["name"] for c in registry.get("collectors", [])]})
            except OSError as error:
                self._write_json(503, {"status": "error", "detail": str(error)})
            return
        self._write_json(404, {"detail": "not found"})

    def do_POST(self) -> None:  # noqa: N802 - stdlib signature
        if self.path not in ("/run", "/register"):
            self._write_json(404, {"detail": "not found"})
            return
        if not _token_valid(self.headers.get("Authorization")):
            self._write_json(401, {"detail": "internal authentication required"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw_body or b"{}")
        except json.JSONDecodeError:
            self._write_json(400, {"detail": "request body must be JSON"})
            return
        try:
            if self.path == "/run":
                status_code, result = handle_run(payload)
            else:
                status_code, result = handle_register(payload)
        except (OSError, KeyError, ValueError) as error:
            self._write_json(500, {"detail": str(error)})
            return
        self._write_json(status_code, result)


def main() -> None:
    server = ThreadingHTTPServer(("0.0.0.0", settings.port), Handler)
    server.serve_forever()


if __name__ == "__main__":
    main()
