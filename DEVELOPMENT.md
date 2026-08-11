# Development

Setting up a working environment on macOS or Linux.

> Windows is not covered. It may work via WSL2 — untested, so it is not
> documented as supported.

---

## Prerequisites

| Tool | Version | Check |
|---|---|---|
| Git | any recent | `git --version` |
| Python | 3.12 | `python3.12 --version` |
| Docker | 24+ | `docker --version` |
| Docker Compose | v2+ | `docker compose version` |

### macOS

```bash
brew install python@3.12 git
brew install --cask docker      # then launch Docker Desktop
```

### Linux (Debian/Ubuntu)

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv git
# Docker Engine + Compose plugin: https://docs.docker.com/engine/install/
```

---

## Option A — everything in Docker

The shortest path to a running system.

```bash
git clone https://github.com/cosmeaf/ansible-devops-platform.git
cd ansible-devops-platform
./scripts/bootstrap.sh
```

Open <http://localhost:47420>. The bootstrap script generates `.env` with every
secret filled in and is safe to run again.

Code changes require a rebuild:

```bash
docker compose up -d --build ansible-api
```

## Option B — Django on the host, services in Docker

Better for day-to-day development: instant reloads and a usable debugger.

The main `docker-compose.yml` deliberately does **not** publish PostgreSQL or
Redis to the host. `docker-compose.dev.yml` adds loopback-only port bindings so
a host process can reach them.

```bash
# 1. Generate .env (creates secrets; safe to re-run)
./scripts/bootstrap.sh

# 2. Virtual environment
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt

# 3. Backing services, published to loopback only
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
    up -d ansible-postgres ansible-redis

# 4. Point Django at them (env vars override .env)
export POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=47432
export REDIS_HOST=127.0.0.1   REDIS_PORT=47379

# 5. Migrate and run
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Django is now on <http://127.0.0.1:8000>.

`make dev-services` wraps steps 3 and 4.

### Celery on the host

```bash
celery -A core worker -l INFO
celery -A core beat -l INFO --schedule /tmp/celerybeat-schedule
```

---

## Everyday commands

```bash
make help          # list every target
make up            # start the full stack
make down          # stop, keeping data
make logs          # follow logs
make check         # django check + migration check
make lint          # ruff check + format check
make format        # apply formatting
make test          # pytest
make migrate       # apply migrations
make shell         # Django shell
make clean         # remove caches (never touches volumes)
```

---

## Ports

| Service | Port | Exposure |
|---|---|---|
| `ansible-api` | 47420 | published |
| `runserver` | 8000 | host only |
| PostgreSQL | 47432 | loopback, dev override only |
| Redis | 47379 | loopback, dev override only |

High ports are used deliberately, to avoid colliding with anything already on
the machine.

---

## Tests

```bash
pytest                                     # everything
pytest tests/test_audit.py                 # one file
pytest -k redact                           # by name
pytest --cov --cov-report=term-missing     # with coverage
```

Tests need PostgreSQL running and reachable. They will **not** fall back to
SQLite — the project runs on PostgreSQL, and testing against a different engine
would hide exactly the problems the suite exists to find.

---

## Migrations

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py makemigrations --check --dry-run   # what CI enforces
```

Read the generated migration before committing it. CI fails when a model change
has no matching migration.

---

## Project conventions

- English for identifiers, comments, docstrings, commits and documentation.
- Ruff for linting and formatting; configuration lives in `pyproject.toml`.
- Settings stay in a single readable `core/settings.py` — see
  [ADR 0008](docs/adr/0008-single-settings-module.md).
- Never log or persist a credential.

Optional pre-commit hooks:

```bash
pre-commit install
```

---

## Troubleshooting

See [docs/troubleshooting.md](docs/troubleshooting.md). The most common causes:

| Symptom | Cause |
|---|---|
| `decouple.UndefinedValueError` | No `.env` — run `./scripts/bootstrap.sh` |
| `failed to resolve host 'ansible-postgres'` | Running on the host without the `POSTGRES_HOST` override |
| `connection refused` on 47432 | Dev override not applied when starting the services |
| Port 47420 in use | Set `ANSIBLE_API_PORT` in `.env` |
