# Architecture

This page covers the practical layout. For the diagrams, the target
architecture and the reasoning, see [ARCHITECTURE.md](../ARCHITECTURE.md) and
the [decision records](adr/).

## Runtime topology

```text
                    host
                     │  :47420
        ┌────────────┴─────────────┐
        │      ansible-api         │   Django 5 + DRF, gunicorn
        └────────────┬─────────────┘
                     │  ansible-network (bridge, not published)
    ┌────────────┬───┴────┬──────────────────┐
    │            │        │                  │
ansible-     ansible-  ansible-       ansible-celery-beat
postgres      redis     celery
```

## Modules

| Package | Contains |
|---|---|
| `core` | Settings, URL configuration, WSGI/ASGI entry points, the Celery app, the health view, and the version source |
| `commun` | `UUIDModel`, `TimeStampedModel`, `BaseModel` — abstract only |
| `authentication` | App configuration; session auth is Django's. RBAC is planned. |
| `audit` | `AuditEvent`, request-ID middleware, log filter, sanitizers |
| `security` | `SecurityEvent` and its taxonomy |
| `ipintel` | `IPIntelligence`, provider protocol, local provider |
| `settings_platform` | `PlatformSetting` with secret masking |

`commun` holds shared *base models* and nothing else. It is not a utilities
package, and turning it into one would be a regression.

## Data model

Everything inherits `BaseModel`:

```text
BaseModel
├── uuid        UUID, unique, non-editable
├── created_at  indexed
└── updated_at
```

The UUID is the identifier meant for external use. Sequential integer primary
keys leak record counts and invite enumeration; the UUID does neither.

## Middleware order

```text
SecurityMiddleware              transport headers
CorsMiddleware                  origin check (empty allow-list by default)
SessionMiddleware               session load
CommonMiddleware
CsrfViewMiddleware
AuthenticationMiddleware        request.user
RequestAuditContextMiddleware   request id in, request id out
MessageMiddleware
XFrameOptionsMiddleware
```

`RequestAuditContextMiddleware` sits after authentication so an audit context
can see `request.user`, and before the view so the id covers the whole handler.

## Configuration flow

```text
environment variables  ──┐
                         ├──> python-decouple ──> core/settings.py
.env file              ──┘
```

Real environment variables win over `.env`. That is what makes CI overrides and
per-container configuration work without editing files.

## Version

`VERSION` at the repository root is the single source of truth. `core/version.py`
reads it; `core.settings.VERSION` re-exports it; the health endpoint reports it.
One file to change at release time.

## Testing

```text
tests/
├── conftest.py               shared fixtures
├── test_audit.py             model behaviour + redaction
├── test_authentication.py    login, logout, admin access
├── test_commun.py            base model behaviour
├── test_health.py            health endpoint contract
├── test_ipintel.py           model + provider classification
├── test_middleware.py        request-id propagation
├── test_security.py          security model + hardening settings
└── test_settings_platform.py settings model + secret masking
```

Tests run against real PostgreSQL. See
[ADR 0002](adr/0002-postgresql-primary-database.md) for why SQLite is not an
option, even for tests.
