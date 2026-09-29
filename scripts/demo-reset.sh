#!/bin/sh
set -eu

cd "$(dirname "$0")/.."

if [ "${1:-}" != "--yes" ]; then
  printf '%s' "Reset only kops synthetic PostgreSQL and content volumes? Type RESET-KOPS: "
  read -r confirmation
  if [ "$confirmation" != "RESET-KOPS" ]; then
    printf '%s\n' "Reset cancelled."
    exit 1
  fi
fi

docker compose down --volumes --remove-orphans
printf '%s\n' "Removed only Docker volumes owned by the kops-local-demo Compose project. Evidence files in docs/evidence were preserved."
