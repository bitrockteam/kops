"""Host preflight and secret generation, standard library only.

``docker compose up`` no longer needs this script: an ``init`` service inside the Compose
stack runs ``generate-secrets`` itself, into the ``runtime_secrets`` volume, before any other
service starts. This script stays for two callers: the init service (inside its container) and
anyone on the host who wants the same secrets or preflight checks without Docker running yet.
"""

from __future__ import annotations

import argparse
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SECRET_NAMES = [
    "db_admin_password", "db_api_password", "db_worker_password", "db_publisher_password",
    "db_audit_password", "db_content_password", "session_secret",
    "internal_api_token", "internal_worker_token",
    "audit_api_token", "audit_worker_token", "audit_publisher_token", "audit_collector_token",
]


def generate_secrets(directory: Path) -> list[str]:
    directory.mkdir(parents=True, exist_ok=True)
    written: list[str] = []
    for name in SECRET_NAMES:
        destination = directory / name
        if destination.is_file() and destination.stat().st_size > 0:
            continue
        destination.write_text(secrets.token_hex(32), encoding="utf-8")
        destination.chmod(0o644)
        written.append(name)
    return written


def preflight() -> None:
    for command_name in ("docker",):
        if shutil.which(command_name) is None:
            print(f"Required command is missing: {command_name}", file=sys.stderr)
            sys.exit(1)
    env_file = REPO_ROOT / ".env"
    env_example = REPO_ROOT / ".env.example"
    if not env_file.is_file():
        env_file.write_text(env_example.read_text(encoding="utf-8"), encoding="utf-8")
    written = generate_secrets(REPO_ROOT / ".runtime" / "secrets")
    (REPO_ROOT / ".runtime" / "backups").mkdir(parents=True, exist_ok=True)
    config_check = subprocess.run(
        ["docker", "compose", "config", "--quiet"], cwd=str(REPO_ROOT), capture_output=True, text=True,
    )
    if config_check.returncode != 0:
        print(config_check.stderr, file=sys.stderr)
        sys.exit(1)
    info = subprocess.run(["docker", "info"], capture_output=True, text=True)
    if info.returncode != 0:
        print(
            "Docker is installed and the Compose configuration is valid, but the daemon is "
            "not available. Start Docker, then run this preflight again.",
            file=sys.stderr,
        )
        sys.exit(1)
    note = f"; generated {len(written)} host-side secret file(s) for local inspection" if written else ""
    print(f"Setup validated. `docker compose up` generates its own secrets in a volume{note}.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command")
    generate = subparsers.add_parser("generate-secrets", help="write missing secret files into a directory")
    generate.add_argument("--dir", required=True, type=Path)
    subparsers.add_parser("preflight", help="host checks, .env, and host-side secret files (default)")
    args = parser.parse_args()

    if args.command == "generate-secrets":
        written = generate_secrets(args.dir)
        print(f"{len(written)} secret file(s) written to {args.dir}")
    else:
        preflight()


if __name__ == "__main__":
    main()
