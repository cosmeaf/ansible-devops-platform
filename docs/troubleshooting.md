# Troubleshooting

## Start here

```bash
docker compose ps                                  # is everything up and healthy?
curl -s http://localhost:47420/api/v1/health/      # what does the platform say?
docker compose logs --tail=50                      # what went wrong?
```

The health endpoint tells you which dependency is unhappy:

```json
{"status": "degraded", "version": "0.1.0-dev", "database": false, "redis": true}
```

---

## Startup

### `decouple.UndefinedValueError: DJANGO_SECRET_KEY not found`

No `.env`.

```bash
./scripts/bootstrap.sh
```

### `bind: address already in use`

Something already holds port 47420.

```bash
lsof -i :47420
```

Either stop it, or pick another port in `.env`:

```bash
ANSIBLE_API_PORT=48420
```

Then `docker compose up -d`.

### `Cannot connect to the Docker daemon`

Docker is not running. Start Docker Desktop, or `sudo systemctl start docker`.

---

## Database

### `failed to resolve host 'ansible-postgres'`

`ansible-postgres` is a Docker network name. You are running Django on the host,
where it does not resolve.

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
    up -d ansible-postgres ansible-redis

export POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=47432
export REDIS_HOST=127.0.0.1   REDIS_PORT=47379
```

### `connection refused` on 47432

The dev override was not applied. The base compose file does not publish
PostgreSQL — that is deliberate. Start the services with both `-f` flags, as
above.

### `password authentication failed`

`POSTGRES_PASSWORD` in `.env` no longer matches what the database was
initialised with. The volume keeps the original password.

Either restore the original value in `.env`, or change it inside PostgreSQL:

```bash
docker compose exec ansible-postgres \
  psql -U ansible_platform -c "ALTER USER ansible_platform WITH PASSWORD 'new';"
```

Do **not** delete the volume to fix this unless you are willing to lose the
data.

### `relation does not exist`

Migrations have not run.

```bash
docker compose exec ansible-api python manage.py migrate
```

---

## Redis and Celery

### Health reports `"redis": false`

```bash
docker compose ps ansible-redis
docker compose exec ansible-redis redis-cli ping     # expect: PONG
```

### The worker is not picking up tasks

```bash
docker compose logs ansible-celery
docker compose exec ansible-celery celery -A core inspect ping
docker compose exec ansible-celery celery -A core inspect active
```

Usually the broker is unreachable — check `REDIS_HOST` and `REDIS_PORT`.

### Beat cannot write its schedule

The schedule file must go somewhere writable; `/app` is not, because the
container runs unprivileged. The compose command already passes
`--schedule /var/run/ansible/celerybeat-schedule`. If you changed the command,
put it back.

---

## HTTP

### 400 Bad Request on every request

The `Host` header is not in `DJANGO_ALLOWED_HOSTS`.

```bash
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,platform.example.com
```

### CSRF verification failed

You are on a different origin from the one Django expects.

```bash
DJANGO_CSRF_TRUSTED_ORIGINS=https://platform.example.com
```

Behind a TLS-terminating proxy, also set `DJANGO_BEHIND_PROXY=True`.

### 403 on API requests

DRF requires authentication by default. Sign in, or use an endpoint that opts
out. There is no token authentication yet — see
[authentication.md](authentication.md).

### 429 Too Many Requests

Throttling. Adjust `THROTTLE_ANON` / `THROTTLE_USER` if the limits are wrong for
your use.

---

## Tests

### `django.db.utils.OperationalError` during pytest

PostgreSQL is not reachable. Tests do not fall back to SQLite — deliberately.

```bash
make dev-services
export POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=47432
export REDIS_HOST=127.0.0.1   REDIS_PORT=47379
pytest
```

### `permission denied to create database`

The test runner creates `test_<dbname>`. Grant `CREATEDB`:

```sql
ALTER USER ansible_platform CREATEDB;
```

---

## Sign-in

### The admin password does not work

```bash
grep INITIAL_ADMIN_PASSWORD .env
```

If the account existed before that value was written, the password in `.env` is
not the live one — bootstrap never resets an existing password. Reset it:

```bash
docker compose exec ansible-api python manage.py changepassword admin
```

### Locked out entirely

```bash
docker compose exec ansible-api python manage.py createsuperuser
```

---

## Still stuck

Open a Discussion under Q&A with:

- what you did and what happened;
- `docker compose ps` output;
- the relevant logs;
- your Docker and Compose versions;
- your OS.

**Redact secrets before pasting.** Logs and `.env` contents routinely contain
passwords and keys.

See [SUPPORT.md](../SUPPORT.md).
