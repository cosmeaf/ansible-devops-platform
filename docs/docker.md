# Docker

## The stack

| Container | Image | Role | Published |
|---|---|---|---|
| `ansible-api` | built here | Django + gunicorn | `47420` |
| `ansible-postgres` | `postgres:16` | Database | no |
| `ansible-redis` | `redis:7` | Broker, results, cache | no |
| `ansible-celery` | built here | Task worker | no |
| `ansible-celery-beat` | built here | Scheduler | no |

All five share the `ansible-network` bridge. Only the API is reachable from the
host.

Volumes: `ansible-postgres-data`, `ansible-redis-data`.

## Everyday commands

```bash
docker compose up -d                 # start
docker compose ps                    # status
docker compose logs -f               # follow all logs
docker compose logs -f ansible-api   # follow one service
docker compose restart ansible-api   # restart one service
docker compose down                  # stop, keeping data
```

## ⚠️ `docker compose down -v`

```bash
docker compose down -v    # DELETES ansible-postgres-data
```

This removes the volumes. Your database — every audit event, every setting,
every user — is gone, and there is no undo.

It is **not** a normal operation. It is not how you restart, free space, or fix
a problem. Use it only when you deliberately want an empty installation, and
only after checking your backups.

To stop the stack, `docker compose down` is what you want.

## Rebuilding after a code change

```bash
docker compose build ansible-api
docker compose up -d ansible-api
```

The worker and beat use the same image, so rebuild them together when the code
changes:

```bash
docker compose build
docker compose up -d
```

## Running commands inside the container

```bash
docker compose exec ansible-api python manage.py migrate
docker compose exec ansible-api python manage.py createsuperuser
docker compose exec ansible-api python manage.py shell
docker compose exec ansible-postgres psql -U ansible_platform -d ansible_platform
```

## Health

Every service declares a healthcheck, so `docker compose ps` reports real state
rather than just "running":

```bash
docker compose ps
curl -s http://localhost:47420/api/v1/health/
docker inspect --format '{{json .State.Health}}' ansible-api | python3 -m json.tool
```

## Backup and restore

Backup:

```bash
docker compose exec -T ansible-postgres \
  pg_dump -U ansible_platform ansible_platform > backup-$(date +%F).sql
```

Restore:

```bash
docker compose exec -T ansible-postgres \
  psql -U ansible_platform -d ansible_platform < backup-2026-08-11.sql
```

Test your restore on a throwaway installation before you need it. A backup you
have never restored is a hope, not a backup.

## The image

`docker/django/Dockerfile`:

- `python:3.12-slim` base;
- dependencies installed before the source copy, so editing code does not
  invalidate the pip layer;
- runs as uid 10001, not root;
- `HEALTHCHECK` against `/api/v1/health/`;
- gunicorn logging to stdout/stderr, with graceful shutdown on `SIGTERM`.

`.dockerignore` keeps `.env`, `.git/`, virtualenvs, caches and test artefacts
out of the build context — without it, `COPY . .` would bake your secrets into a
layer.

## Development override

`docker-compose.dev.yml` publishes PostgreSQL and Redis on **loopback only**, so
a Django process on the host can reach them:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
    up -d ansible-postgres ansible-redis
```

Never apply this file to a deployed environment.

## Troubleshooting

| Symptom | Check |
|---|---|
| Container restarting | `docker compose logs <service>` |
| `port is already allocated` | Change `ANSIBLE_API_PORT` in `.env` |
| API cannot reach the database | `docker compose ps` — is postgres healthy? |
| `failed to resolve host 'ansible-postgres'` | You are running on the host, not in the network. Use the dev override. |
| Build fails | `docker compose build --no-cache ansible-api` |
| Out of disk | `docker system prune` — **check first**, it removes unused images and networks |

More in [troubleshooting.md](troubleshooting.md).
