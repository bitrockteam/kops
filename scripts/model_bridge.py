"""Model bridge: turns the signed-in Claude Code CLI on this host into an HTTP endpoint.

Standard library only. Binds the loopback interface and runs one ``claude -p`` process per
request; there is no API key anywhere and no model choice here beyond the fixed defaults
below, which match what ``docs/lab-design.md`` documents. Containers reach this bridge as
``host.docker.internal``, the only host the model-egress allowlist admits.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import signal
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

BRIDGE_VERSION = "0.1.0"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8090
DEFAULT_MODEL = "sonnet"
DEFAULT_EFFORT = "high"
DEFAULT_MAX_CONCURRENCY = 4
REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = REPO_ROOT / ".runtime"
PID_FILE = RUNTIME_DIR / "model_bridge.pid"

_CHILD_ENV_PREFIXES = ("CLAUDE_CODE_", "CLAUDECODE")


class BridgeError(RuntimeError):
    def __init__(self, message: str, *, raw: str | None = None, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.raw = raw
        self.retry_after = retry_after


def _child_environment() -> dict[str, str]:
    return {
        key: value
        for key, value in os.environ.items()
        if not any(key == prefix or key.startswith(prefix) for prefix in _CHILD_ENV_PREFIXES)
    }


def _validate_shape(schema: dict[str, Any], value: Any) -> bool:
    """Best-effort structural check: required keys and top-level type, standard library only."""
    if schema.get("type") == "object":
        if not isinstance(value, dict):
            return False
        for key in schema.get("required", []):
            if key not in value:
                return False
    return True


def cli_version() -> str:
    try:
        result = subprocess.run(
            ["claude", "--version"], capture_output=True, text=True, timeout=15,
            env=_child_environment(),
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        return f"unavailable: {type(error).__name__}"
    if result.returncode != 0:
        return f"unavailable: exit {result.returncode}"
    return result.stdout.strip()


class ModelBridge:
    def __init__(self, model: str, effort: str, max_concurrency: int) -> None:
        self.model = model
        self.effort = effort
        self.semaphore = threading.Semaphore(max_concurrency)
        self.lock = threading.Lock()
        self.last_model_id: str | None = None
        self.last_effort: str | None = None
        self.last_completed_at: float | None = None

    def health(self) -> dict[str, Any]:
        with self.lock:
            last_model_id = self.last_model_id
            last_effort = self.last_effort
            last_completed_at = self.last_completed_at
        return {
            "status": "ok",
            "bridge_version": BRIDGE_VERSION,
            "cli_version": cli_version(),
            "requested_model": self.model,
            "requested_effort": self.effort,
            "last_model_id": last_model_id,
            "last_effort": last_effort,
            "last_completed_at": last_completed_at,
            "pid": os.getpid(),
        }

    def _run_once(self, system: str, prompt: str, schema: dict[str, Any] | None) -> dict[str, Any]:
        argv = [
            "claude", "-p",
            "--model", self.model,
            "--effort", self.effort,
            "--output-format", "json",
            "--tools", "",
            "--no-session-persistence",
            "--permission-prompts", "none",
        ]
        if system:
            argv += ["--system-prompt", system]
        if schema is not None:
            argv += ["--json-schema", json.dumps(schema)]
        started = time.monotonic()
        try:
            result = subprocess.run(
                argv, input=prompt, capture_output=True, text=True, timeout=280,
                cwd=str(REPO_ROOT), env=_child_environment(),
            )
        except subprocess.TimeoutExpired as error:
            raise BridgeError("claude -p exceeded the bridge's wall-time budget") from error
        duration_ms = round((time.monotonic() - started) * 1000)
        if result.returncode != 0:
            lowered = (result.stderr or "").lower()
            retry_after = 30.0 if ("rate limit" in lowered or "429" in lowered) else None
            raise BridgeError(
                f"claude -p exited with status {result.returncode}",
                raw=(result.stderr or result.stdout)[:4000], retry_after=retry_after,
            )
        try:
            envelope = json.loads(result.stdout)
        except json.JSONDecodeError as error:
            raise BridgeError("claude -p did not return a parseable JSON envelope", raw=result.stdout[:4000]) from error
        if envelope.get("is_error"):
            raise BridgeError("claude -p reported an error result", raw=json.dumps(envelope)[:4000])
        model_usage = envelope.get("modelUsage") or {}
        model_id = next(iter(model_usage), None) or envelope.get("model") or "unknown"
        text = envelope.get("result", "")
        structured = envelope.get("structured_output")
        return {
            "text": text,
            "object": structured,
            "model": model_id,
            "effort": self.effort,
            "usage": envelope.get("usage", {}),
            "duration_ms": duration_ms,
            "bridge_version": BRIDGE_VERSION,
        }

    def complete(self, system: str, prompt: str, schema: dict[str, Any] | None) -> dict[str, Any]:
        self.semaphore.acquire()
        try:
            response = self._run_once(system, prompt, schema)
            if schema is not None and not _validate_shape(schema, response["object"]):
                response = self._run_once(system, prompt, schema)
                if not _validate_shape(schema, response["object"]):
                    raise BridgeError(
                        "model output did not match the requested schema after one retry",
                        raw=json.dumps(response.get("object")),
                    )
        finally:
            self.semaphore.release()
        with self.lock:
            self.last_model_id = response["model"]
            self.last_effort = response["effort"]
            self.last_completed_at = time.time()
        return response


def _make_handler(bridge: ModelBridge) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = f"kops-model-bridge/{BRIDGE_VERSION}"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            sys.stderr.write(f"{self.address_string()} - {format % args}\n")

        def _send_json(self, status: int, payload: dict[str, Any]) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/health":
                self._send_json(200, bridge.health())
            else:
                self._send_json(404, {"error": "not found"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/v1/complete":
                self._send_json(404, {"error": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            try:
                request = json.loads(self.rfile.read(length) or b"{}")
            except json.JSONDecodeError:
                self._send_json(400, {"error": "request body must be JSON"})
                return
            prompt = request.get("prompt")
            if not isinstance(prompt, str) or not prompt.strip():
                self._send_json(400, {"error": "prompt is required"})
                return
            system = request.get("system", "") or ""
            schema = request.get("schema")
            try:
                self._send_json(200, bridge.complete(system, prompt, schema))
            except BridgeError as error:
                self._send_json(502, {"error": str(error), "raw": error.raw, "retry_after": error.retry_after})

    return Handler


def serve(host: str, port: int, model: str, effort: str, max_concurrency: int) -> None:
    bridge = ModelBridge(model=model, effort=effort, max_concurrency=max_concurrency)
    server = ThreadingHTTPServer((host, port), _make_handler(bridge))
    print(f"kops model bridge listening on http://{host}:{port} (model={model}, effort={effort})")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def _start(host: str, port: int, model: str, effort: str, max_concurrency: int) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    if PID_FILE.is_file():
        existing = PID_FILE.read_text(encoding="utf-8").strip()
        if existing and _process_alive(int(existing)):
            print(f"model bridge already running with pid {existing}")
            return
    argv = [
        sys.executable, str(Path(__file__).resolve()), "serve",
        "--host", host, "--port", str(port),
        "--model", model, "--effort", effort,
        "--max-concurrency", str(max_concurrency),
    ]
    creationflags = 0
    start_new_session = False
    if os.name == "nt":
        creationflags = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        start_new_session = True
    log_path = RUNTIME_DIR / "model_bridge.log"
    with open(log_path, "ab") as log_file:
        process = subprocess.Popen(
            argv, stdout=log_file, stderr=log_file, stdin=subprocess.DEVNULL,
            creationflags=creationflags, start_new_session=start_new_session,
            cwd=str(REPO_ROOT),
        )
    PID_FILE.write_text(str(process.pid), encoding="utf-8")
    print(f"model bridge starting in the background with pid {process.pid}; log at {log_path}")
    for _ in range(30):
        time.sleep(0.5)
        if _health_reachable(host, port):
            print(f"model bridge is healthy at http://{host}:{port}/health")
            return
    print("model bridge did not answer /health within 15 seconds; check the log file", file=sys.stderr)
    sys.exit(1)


def _health_reachable(host: str, port: int) -> bool:
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, OSError):
        return False


def _process_alive(pid: int) -> bool:
    if os.name == "nt":
        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def _stop() -> None:
    if not PID_FILE.is_file():
        print("no model bridge pid file found; nothing to stop")
        return
    pid = int(PID_FILE.read_text(encoding="utf-8").strip())
    if _process_alive(pid):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as error:
            print(f"could not stop pid {pid}: {error}", file=sys.stderr)
    PID_FILE.unlink(missing_ok=True)
    print(f"model bridge (pid {pid}) stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=["serve", "start", "stop"], default="serve")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--effort", default=DEFAULT_EFFORT)
    parser.add_argument("--max-concurrency", type=int, default=DEFAULT_MAX_CONCURRENCY)
    args = parser.parse_args()

    if args.command == "stop":
        _stop()
    elif args.command == "start":
        _start(args.host, args.port, args.model, args.effort, args.max_concurrency)
    else:
        serve(args.host, args.port, args.model, args.effort, args.max_concurrency)


if __name__ == "__main__":
    main()
