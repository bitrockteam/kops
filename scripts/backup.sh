#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
timestamp=$(date -u +%Y%m%dT%H%M%SZ)
destination=".runtime/backups/$timestamp"
umask 077
mkdir -p "$destination"

docker compose exec -T db pg_dump -U postgres -d kops --format=custom >"$destination/database.dump"
docker compose exec -T api tar -C /var/lib/kops/content/sources -cf - . >"$destination/sources.tar"
docker compose exec -T worker tar -C /var/lib/kops/content/candidates -cf - . >"$destination/candidates.tar"
docker compose exec -T publisher tar -C /var/lib/kops/content/pages -cf - . >"$destination/pages.tar"
docker compose exec -T api tar -C /var/lib/kops/content/answers -cf - . >"$destination/answers.tar"

(
  cd "$destination"
  sha256sum database.dump sources.tar candidates.tar pages.tar answers.tar >SHA256SUMS
)
printf '%s\n' "Backup created at $destination"
