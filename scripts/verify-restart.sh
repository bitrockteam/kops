#!/bin/sh
set -eu

project=kops-test
compose() {
    docker compose -p "$project" --profile test "$@"
}
query() {
    compose exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d kops -tAc "$1"
}

job_id=$(query "SELECT job_id FROM kops.jobs WHERE status = 'ready' ORDER BY created_at DESC LIMIT 1")
test -n "$job_id"
before=$(query 'SELECT count(*) FROM kops.jobs')
test "$before" -gt 0

compose stop worker >/dev/null
query "UPDATE kops.jobs SET status = 'running', completed_at = NULL WHERE job_id = '$job_id'" >/dev/null
compose start worker >/dev/null
attempt=0
while [ "$attempt" -lt 20 ]; do
    status=$(query "SELECT status FROM kops.jobs WHERE job_id = '$job_id'")
    if [ "$status" = blocked ]; then
        break
    fi
    attempt=$((attempt + 1))
    sleep 1
done
test "$status" = blocked
test "$(query "SELECT error_code FROM kops.jobs WHERE job_id = '$job_id'")" = worker_interrupted

compose down >/dev/null
KOPS_PORT=18080 KOPS_BUILD_TARGET=test KOPS_ALLOWED_MODEL_HOSTS=host.docker.internal,fixture-model KOPS_MODEL_ENDPOINT=http://fixture-model:8090 compose up -d >/dev/null
after=$(query 'SELECT count(*) FROM kops.jobs')
test "$after" = "$before"
test "$(query 'SELECT count(*) FROM kops.query_response_inputs')" -gt 0
printf '%s\n' "worker interruption recovered; PostgreSQL job and query manifests survived container recreation"
