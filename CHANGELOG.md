# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

Nothing yet.

## [0.1.0-dev] — unreleased

The first public baseline: Module 1, Core Platform. There are no earlier
versions; this project has not been released before.

### Added

- Django 5 + Django REST Framework backend with PostgreSQL, Redis, Celery and
  Celery Beat, deployed via Docker Compose on a private `ansible-network`.
- `audit` — `AuditEvent` model, request-ID middleware propagating
  `X-Request-ID` across responses and logs, and automatic redaction of
  credential-bearing fields before anything reaches the database.
- `security` — `SecurityEvent` model with typed events and severities.
- `ipintel` — `IPIntelligence` model behind a provider abstraction; the default
  provider classifies addresses offline and requires no commercial API.
- `settings_platform` — `PlatformSetting` with an enforced `is_secret` mask.
- `commun` — shared `UUIDModel`, `TimeStampedModel` and `BaseModel`.
- `GET /api/v1/health/` reporting database and Redis state, plus the platform
  version, and returning 503 when degraded.
- Idempotent `scripts/bootstrap.sh` that generates every secret.
- Test suite (103 tests) running against real PostgreSQL.
- Apache 2.0 licence, open-source governance, contribution, security and
  support documentation, architecture decision records, issue forms, pull
  request template, Dependabot configuration and CI/CD workflows.

### Changed

- Canonical project language is now English: settings default to `en-us`/`UTC`,
  and templates and documentation were translated from Portuguese.
- `AuditEvent`, `SecurityEvent`, `IPIntelligence` and `PlatformSetting` gained
  `__str__`, deterministic ordering, verbose names and database indexes.
- Baseline migrations were regenerated as a single clean `0001_initial` per app.
  Nothing had been released or deployed, so no upgrade path was broken.
- `requirements.txt` now holds runtime dependencies only; development and CI
  tooling moved to `requirements-dev.txt`.
- Locale-independent single source of version truth in `VERSION`.

### Fixed

- `ipintel` no longer misreports RFC 5737 documentation ranges. `is_private`
  now means "not globally routable", and genuine RFC 1918 / RFC 4193 space is
  reported separately as `site_local`.

### Security

- **Removed `BUILD-MANIFEST.json`, which contained the initial administrator
  password in plaintext and was not gitignored.**
- Added `.dockerignore` — `.env` was previously copied into every image layer
  by `COPY . .`.
- Containers now run as an unprivileged user (uid 10001) and declare a
  `HEALTHCHECK`.
- Added session, CSRF, HSTS, referrer-policy, content-type-nosniff and
  clickjacking protections, with secure cookies enabled outside `DEBUG`.
- DRF now requires authentication and applies throttling by default; previously
  it had no configuration at all.
- CORS denies all origins by default.
- Minimum password length raised to 12 characters.
- The health endpoint no longer risks leaking connection details; failures are
  logged server-side and reported to callers as booleans only.
- Django Admin exposes the audit trail read-only, and masks values flagged
  secret in `PlatformSetting`.
- Hardened `.gitignore` against `.env`, private keys, database dumps and
  coverage artefacts.

[Unreleased]: https://github.com/cosmeaf/ansible-devops-platform/compare/v0.1.0...HEAD
[0.1.0-dev]: https://github.com/cosmeaf/ansible-devops-platform/releases/tag/v0.1.0
