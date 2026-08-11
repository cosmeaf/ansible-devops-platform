# Installation

## Requirements

### Docker install (recommended)

| | Minimum |
|---|---|
| Docker | 24+ |
| Docker Compose | v2 |
| RAM | 2 GB free |
| Disk | 5 GB free |
| OS | Linux or macOS |

Nothing else — no Python, no PostgreSQL, no Redis on the host.

### Manual install

| | Minimum |
|---|---|
| Python | 3.12 |
| PostgreSQL | 16 |
| Redis | 7 |

Windows is not supported. WSL2 may work; it is untested, so it is not documented
as supported.

## Method 1 — Docker Compose

```bash
git clone https://github.com/cosmeaf/ansible-devops-platform.git
cd ansible-devops-platform
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh
```

See [getting-started.md](getting-started.md) for what happens and what to do
next.

## Method 2 — manual

For development, or where Docker is unavailable.

```bash
git clone https://github.com/cosmeaf/ansible-devops-platform.git
cd ansible-devops-platform

python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create the database:

```sql
CREATE DATABASE ansible_platform;
CREATE USER ansible_platform WITH PASSWORD 'choose-a-strong-password';
GRANT ALL PRIVILEGES ON DATABASE ansible_platform TO ansible_platform;
```

Create `.env` from the reference and fill in the values:

```bash
cp .env.example .env
```

Generate the secrets rather than inventing them:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"   # DJANGO_SECRET_KEY
python -c "import secrets; print(secrets.token_hex(32))"       # PLATFORM_ENCRYPTION_KEY
```

Set `POSTGRES_HOST` and `REDIS_HOST` to wherever your services actually are —
the defaults (`ansible-postgres`, `ansible-redis`) are Docker network names and
will not resolve on a host.

Then:

```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic --noinput
gunicorn core.wsgi:application --bind 0.0.0.0:47420
```

Celery, in separate processes:

```bash
celery -A core worker -l INFO
celery -A core beat -l INFO
```

## Ports

| Service | Default | Published |
|---|---|---|
| API | 47420 | yes |
| PostgreSQL | 5432 | **no** — Docker network only |
| Redis | 6379 | **no** — Docker network only |

High ports avoid collisions with whatever else is on the machine. Change the API
port with `ANSIBLE_API_PORT` in `.env`.

Do not publish PostgreSQL or Redis. Neither is configured for exposure — Redis
in particular has no authentication in this stack, because it does not need any
while it is unreachable.

## Upgrading

```bash
git pull
docker compose build
docker compose up -d
docker compose exec ansible-api python manage.py migrate
```

Back up first:

```bash
docker compose exec ansible-postgres \
  pg_dump -U ansible_platform ansible_platform > backup-$(date +%F).sql
```

Your `.env` is not touched by an upgrade.

## Uninstalling

```bash
docker compose down          # stop, keep data
```

To remove the data as well — **this deletes your database permanently**:

```bash
docker compose down -v
```

## Verifying

```bash
curl -s http://localhost:47420/api/v1/health/
docker compose ps
```

If anything is wrong, see [troubleshooting.md](troubleshooting.md).
