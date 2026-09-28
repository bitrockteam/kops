#!/bin/sh
set -eu

project=$(docker compose config --format json | jq -r '.name')
container=$(docker compose ps -a -q db)
if [ -n "$container" ] && docker inspect --format '{{range .Mounts}}{{println .Destination}}{{end}}' "$container" | grep -Fxq /var/lib/postgresql/data; then
    printf '%s\n' \
        'Refusing to recreate the previous PostgreSQL 18 container: its database may be in an anonymous volume.' \
        'While the previous version still runs, create and verify a kops backup. Then use the documented confirmed reset and restore procedure.' >&2
    exit 1
fi

volume="${project}_postgres_data"
if docker volume inspect "$volume" >/dev/null 2>&1; then
    if ! docker run --rm --pull=never --mount "type=volume,src=$volume,dst=/check,readonly" \
        --entrypoint sh postgres:18.0-alpine -c 'test -f /check/18/docker/PG_VERSION' >/dev/null 2>&1; then
        printf '%s\n' \
            'Refusing to initialize PostgreSQL on a pre-existing volume without the PostgreSQL 18 data directory.' \
            'This may be an old empty named volume while the actual database remains in an anonymous volume. Back up with the previous version, then follow the confirmed reset and restore procedure.' >&2
        exit 1
    fi
fi
