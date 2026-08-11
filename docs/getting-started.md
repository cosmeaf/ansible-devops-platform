# Getting started

From nothing to a running platform.

## What you need

Docker and Docker Compose. That is the whole list.

```bash
docker --version
docker compose version
```

## Install

```bash
git clone https://github.com/cosmeaf/ansible-devops-platform.git
cd ansible-devops-platform
chmod +x scripts/bootstrap.sh
./scripts/bootstrap.sh
```

You will not be asked to invent a password, generate a key, or fill in a config
file. The script does all of it.

## What the script does

```text
[CHECK] Docker ................................. OK
[CHECK] OpenSSL ................................ OK
[CHECK] Docker Compose ......................... OK
[CHECK] Docker daemon .......................... OK
[BOOT] Environment file ........................ OK
[BOOT] Building images ......................... OK
[BOOT] PostgreSQL .............................. OK
[BOOT] Redis ................................... OK
[BOOT] Django API .............................. OK
[BOOT] Migrations .............................. OK
[BOOT] Administrator ........................... OK
[BOOT] Celery worker ........................... OK
[BOOT] Celery Beat ............................. OK
[TEST] Django check ............................ PASS
[TEST] Health endpoint ......................... PASS
```

1. Verifies prerequisites.
2. Generates `.env` with a random `DJANGO_SECRET_KEY`, `POSTGRES_PASSWORD`,
   `INITIAL_ADMIN_PASSWORD` and `PLATFORM_ENCRYPTION_KEY`, then `chmod 600`s it.
3. Builds the image and starts PostgreSQL, Redis, the API, the Celery worker and
   Celery Beat.
4. Applies migrations.
5. Creates the `admin` account.
6. Verifies Django's checks and the health endpoint.

## Sign in

| | |
|---|---|
| Platform | <http://localhost:47420> |
| Admin | <http://localhost:47420/admin/> |
| Health | <http://localhost:47420/api/v1/health/> |

Username `admin`. For the password:

```bash
grep INITIAL_ADMIN_PASSWORD .env
```

**Change it after your first sign-in**, in Django Admin under Users. Forced
password change on first login is on the roadmap, not implemented.

## Verify

```bash
curl -s http://localhost:47420/api/v1/health/
```

```json
{"status": "healthy", "version": "0.1.0-dev", "database": true, "redis": true}
```

`503` with `"status": "degraded"` means a dependency is down. Check
`docker compose ps` and `docker compose logs`.

## Running it again

The bootstrap script is idempotent. Running it a second time will **not**:

- overwrite your `.env`;
- reset the admin password;
- destroy the database;
- recreate volumes.

So it is safe to use to bring the stack back up after a reboot, though
`docker compose up -d` is the usual way.

## Everyday operation

```bash
docker compose ps           # what is running
docker compose logs -f      # follow logs
docker compose down         # stop, keeping data
docker compose up -d        # start again
```

> Never run `docker compose down -v` unless you intend to **delete your
> database**. See [docker.md](docker.md).

## What you can do now

Module 1 is the foundation. Today you get:

- Django Admin over the audit trail, security events, IP intelligence and
  platform settings;
- a health endpoint;
- request-ID correlation across logs;
- a working Celery worker and scheduler.

You cannot yet run playbooks or manage inventory — those are Modules 3 and 4.
See [ROADMAP.md](../ROADMAP.md).

## Next

- [Configuration](configuration.md) — every variable you can set
- [Security](security.md) — what is protected and what is not
- [Troubleshooting](troubleshooting.md) — when it does not work
