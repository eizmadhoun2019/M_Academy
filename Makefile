PROJECT := m-academy
COMPOSE := docker compose -p $(PROJECT)
WEB := $(COMPOSE) exec -T web

.DEFAULT_GOAL := help
.PHONY: help up down ps logs migrate makemigrations test lint fmt type docs gates schema shell psql

help:
	@echo "up            build and start the isolated stack (docs/operations/environments.md)"
	@echo "down          stop this project's containers only"
	@echo "ps / logs     status / follow logs"
	@echo "migrate       apply migrations in the web container"
	@echo "makemigrations  create migrations"
	@echo "test          run the test suite (PostgreSQL, eager Celery)"
	@echo "lint / fmt    ruff check / ruff check --fix + format"
	@echo "type          mypy"
	@echo "docs          documentation check (gate G9)"
	@echo "gates         run the local subset of CI gates"
	@echo "schema        write the OpenAPI schema"
	@echo "shell / psql  Django shell / database shell"

up:
	$(COMPOSE) up -d --build --wait

down:
	$(COMPOSE) down

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f --tail=100

migrate:
	$(WEB) python manage.py migrate

makemigrations:
	$(WEB) python manage.py makemigrations

test:
	$(COMPOSE) run --rm web pytest -q

lint:
	$(COMPOSE) run --rm web ruff check .
	$(COMPOSE) run --rm web ruff format --check .

fmt:
	$(COMPOSE) run --rm web ruff check --fix .
	$(COMPOSE) run --rm web ruff format .

type:
	$(COMPOSE) run --rm web mypy .

docs:
	python scripts/check_docs.py

gates: docs
	$(COMPOSE) run --rm web ruff check .
	$(COMPOSE) run --rm web ruff format --check .
	$(COMPOSE) run --rm web mypy .
	$(COMPOSE) run --rm web python manage.py makemigrations --check --dry-run
	$(COMPOSE) run --rm web python manage.py spectacular --validate --fail-on-warn --file /tmp/schema.yml
	$(COMPOSE) run --rm web python scripts/gate_imports.py

schema:
	$(COMPOSE) run --rm web python manage.py spectacular --file openapi.yml

shell:
	$(WEB) python manage.py shell

psql:
	$(COMPOSE) exec -T db psql -U academy -d academy
