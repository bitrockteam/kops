#!/bin/sh
set -eu

cd "$(dirname "$0")/.."
requested=${1:-}
if [ -z "$requested" ]; then
  printf '%s\n' "Usage: make restore BACKUP=.runtime/backups/<timestamp>" >&2
  exit 1
fi

backup_root=$(realpath .runtime/backups)
backup_path=$(realpath "$requested")
case "$backup_path" in
  "$backup_root"/*) ;;
  *) printf '%s\n' "Restore path must be a child of .runtime/backups" >&2; exit 1 ;;
esac

for required in database.dump sources.tar candidates.tar pages.tar answers.tar SHA256SUMS; do
  if [ ! -f "$backup_path/$required" ]; then
    printf '%s\n' "Backup is incomplete: missing $required" >&2
    exit 1
  fi
done
(
  cd "$backup_path"
  sha256sum --check SHA256SUMS
)

printf '%s' "Replace only the kops synthetic database and content volumes from $backup_path? Type RESTORE-KOPS: "
read -r confirmation
if [ "$confirmation" != "RESTORE-KOPS" ]; then
  printf '%s\n' "Restore cancelled."
  exit 1
fi

docker compose stop api worker publisher audit content
docker compose exec -T db dropdb -U postgres --force --if-exists kops
docker compose exec -T db createdb -U postgres kops
docker compose exec -T db pg_restore -U postgres -d kops --exit-on-error <"$backup_path/database.dump"

docker compose run --rm --no-deps --user 0 api sh -c 'find /var/lib/kops/content/sources /var/lib/kops/content/answers -mindepth 1 -delete'
docker compose run --rm --no-deps --user 0 worker sh -c 'find /var/lib/kops/content/candidates -mindepth 1 -delete'
docker compose run --rm --no-deps --user 0 publisher sh -c 'find /var/lib/kops/content/pages -mindepth 1 -delete'
docker compose run --rm --no-deps --user 0 api tar --no-same-owner --no-same-permissions --touch -C /var/lib/kops/content/sources -xf - <"$backup_path/sources.tar"
docker compose run --rm --no-deps --user 0 worker tar --no-same-owner --no-same-permissions --touch -C /var/lib/kops/content/candidates -xf - <"$backup_path/candidates.tar"
docker compose run --rm --no-deps --user 0 publisher tar --no-same-owner --no-same-permissions --touch -C /var/lib/kops/content/pages -xf - <"$backup_path/pages.tar"
docker compose run --rm --no-deps --user 0 api tar --no-same-owner --no-same-permissions --touch -C /var/lib/kops/content/answers -xf - <"$backup_path/answers.tar"
docker compose up -d
printf '%s\n' "Restore completed from $backup_path. The trusted local host operation is outside the in-app audit boundary."
