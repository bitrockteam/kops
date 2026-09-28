.PHONY: setup up down logs test demo-reset status backup restore

KOPS_PORT ?= 8080

setup:
	@sh scripts/setup.sh

up:
	@docker compose up -d --build
	@printf '%s\n' "kops is starting at http://127.0.0.1:$(KOPS_PORT)"
	@printf '%s\n' "Open Model Setup before compilation. No hosted fallback is configured."

down:
	@docker compose down

logs:
	@docker compose logs --follow --tail=200 api worker publisher audit db

status:
	@docker compose ps

test:
	@set -eu; \
	trap 'docker compose -p kops-test --profile test down --volumes --remove-orphans >/dev/null 2>&1 || true' EXIT INT TERM; \
	KOPS_PORT=18080 KOPS_BUILD_TARGET=test KOPS_ALLOWED_MODEL_HOSTS=host.docker.internal,fixture-model docker compose -p kops-test --profile test up -d --build; \
	docker compose -p kops-test exec -T -e PYTHONDONTWRITEBYTECODE=1 api pytest -p no:cacheprovider -m "not live_model"; \
	docker compose -p kops-test exec -T db psql -v ON_ERROR_STOP=1 -U postgres -d kops -f /checks/verify_privileges.sql

demo-reset:
	@sh scripts/demo-reset.sh

backup:
	@sh scripts/backup.sh

restore:
	@sh scripts/restore.sh "$(BACKUP)"
