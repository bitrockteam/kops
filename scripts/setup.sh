#!/bin/sh
set -eu

cd "$(dirname "$0")/.."

for command_name in docker make; do
  if ! command -v "$command_name" >/dev/null 2>&1; then
    printf '%s\n' "Required command is missing: $command_name" >&2
    exit 1
  fi
done

umask 077
mkdir -p .runtime/secrets .runtime/backups
for secret_name in db_admin_password db_api_password db_worker_password db_publisher_password db_audit_password db_content_password session_secret internal_api_token internal_worker_token audit_api_token audit_worker_token audit_publisher_token; do
  destination=".runtime/secrets/$secret_name"
  if [ ! -s "$destination" ]; then
    if command -v openssl >/dev/null 2>&1; then
      openssl rand -hex 32 >"$destination"
    else
      python3 -c 'import secrets; print(secrets.token_hex(32))' >"$destination"
    fi
  fi
  chmod 644 "$destination"
done

if [ ! -f .env ]; then
  cp .env.example .env
  chmod 600 .env
fi

docker compose config --quiet
if ! docker info >/dev/null 2>&1; then
  printf '%s\n' "Docker is installed and the Compose configuration is valid, but the daemon is not available. Start Docker, then run make setup again." >&2
  exit 1
fi
printf '%s\n' "Setup validated. No model runtime, model weights, or identity server were installed."
