#!/bin/sh
set -eu

api_password=$(cat /run/secrets/db_api_password)
worker_password=$(cat /run/secrets/db_worker_password)
publisher_password=$(cat /run/secrets/db_publisher_password)
audit_password=$(cat /run/secrets/db_audit_password)
content_password=$(cat /run/secrets/db_content_password)

psql --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" \
  --set=api_password="$api_password" \
  --set=worker_password="$worker_password" \
  --set=publisher_password="$publisher_password" \
  --set=audit_password="$audit_password" \
  --set=content_password="$content_password" <<'SQL'
SELECT format('CREATE ROLE kops_owner NOLOGIN') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kops_owner') \gexec
SELECT format('CREATE ROLE kops_api LOGIN PASSWORD %L', :'api_password') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kops_api') \gexec
SELECT format('CREATE ROLE kops_worker LOGIN PASSWORD %L', :'worker_password') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kops_worker') \gexec
SELECT format('CREATE ROLE kops_publisher LOGIN PASSWORD %L', :'publisher_password') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kops_publisher') \gexec
SELECT format('CREATE ROLE kops_audit LOGIN PASSWORD %L', :'audit_password') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kops_audit') \gexec
SELECT format('CREATE ROLE kops_content LOGIN PASSWORD %L', :'content_password') WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'kops_content') \gexec
SQL
