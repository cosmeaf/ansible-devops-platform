# Ansible DevOps Platform — developer shortcuts.
# Every target wraps a command you could run by hand; nothing here is magic.

COMPOSE     := docker compose
COMPOSE_DEV := docker compose -f docker-compose.yml -f docker-compose.dev.yml
PYTHON      := python

.DEFAULT_GOAL := help
.PHONY: help setup up down restart logs ps build check lint format test test-cov \
        migrate makemigrations shell superuser dev-services clean

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

setup: ## Bootstrap: generate .env and start the full stack
	./scripts/bootstrap.sh

up: ## Start the stack
	$(COMPOSE) up -d

down: ## Stop the stack, keeping data (never passes -v)
	$(COMPOSE) down

restart: ## Restart the stack
	$(COMPOSE) restart

logs: ## Follow logs
	$(COMPOSE) logs -f

ps: ## Show container status
	$(COMPOSE) ps

build: ## Rebuild images
	$(COMPOSE) build

dev-services: ## Start PostgreSQL and Redis published on loopback for host-side dev
	$(COMPOSE_DEV) up -d ansible-postgres ansible-redis
	@echo
	@echo "Export these before running Django on the host:"
	@echo "  export POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=47432"
	@echo "  export REDIS_HOST=127.0.0.1 REDIS_PORT=47379"

check: ## Django system checks and migration drift check
	$(PYTHON) manage.py check
	$(PYTHON) manage.py makemigrations --check --dry-run

lint: ## Lint and verify formatting
	ruff check .
	ruff format --check .

format: ## Apply formatting and safe lint fixes
	ruff check --fix .
	ruff format .

test: ## Run the test suite
	pytest

test-cov: ## Run the test suite with a coverage report
	pytest --cov --cov-report=term-missing

migrate: ## Apply migrations
	$(PYTHON) manage.py migrate

makemigrations: ## Generate migrations
	$(PYTHON) manage.py makemigrations

shell: ## Django shell
	$(PYTHON) manage.py shell

superuser: ## Create a superuser
	$(PYTHON) manage.py createsuperuser

clean: ## Remove caches and build artefacts (never touches volumes)
	find . -type d -name __pycache__ -not -path './.venv/*' -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov coverage.xml
	@echo "Caches removed. Docker volumes were not touched."
