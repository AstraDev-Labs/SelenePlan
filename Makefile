COMPOSE = docker compose -f infra/docker-compose.yml --env-file infra/.env

.PHONY: env up down logs ps test lint fmt typecheck sbom

env:
	@test -f infra/.env || cp infra/.env.example infra/.env

up: env
	$(COMPOSE) up -d

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

lint:
	@for d in libs/*/ services/*/; do \
	  if [ -f $$d/pyproject.toml ]; then echo "== lint $$d"; (cd $$d && ruff check . && ruff format --check .) || exit 1; fi; \
	done

fmt:
	@for d in libs/*/ services/*/; do \
	  if [ -f $$d/pyproject.toml ]; then (cd $$d && ruff check --fix . && ruff format .); fi; \
	done

typecheck:
	@for d in libs/*/ services/*/; do \
	  if [ -f $$d/pyproject.toml ]; then echo "== mypy $$d"; (cd $$d && mypy src) || exit 1; fi; \
	done

test:
	@for d in libs/*/ services/*/; do \
	  if [ -f $$d/pyproject.toml ]; then echo "== test $$d"; (cd $$d && pytest -q) || exit 1; fi; \
	done


sbom:
	syft dir:. -o spdx-json > sbom.spdx.json
