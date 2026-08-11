# ADR 0002 — PostgreSQL as the primary database

## Status

Accepted

## Context

The platform stores audit events, security events, IP intelligence and
operational settings. Several of these use JSON payloads of varying shape
(`metadata`, `previous_value`, `new_value`, setting `value`). The audit trail is
append-heavy and will be queried by time range, user and resource.

Future modules add inventory, job history and execution logs — all of which grow
faster than the tables we have now.

## Decision

We will use **PostgreSQL 16** as the only supported database, in development,
test and deployment alike.

## Consequences

### Positive

- `JSONField` is backed by native `jsonb`, so the JSON columns are indexable and
  queryable rather than opaque text.
- Real constraint support, including the partial and composite constraints the
  data model already uses.
- Strong concurrency (MVCC) suits an append-heavy audit table with concurrent
  readers.
- Mature operational tooling: `pg_dump`, streaming replication, point-in-time
  recovery.

### Negative

- Contributors must run PostgreSQL to run the tests. This is a real barrier to
  entry, and it is accepted deliberately — see below.
- More operational surface than an embedded database: a service to run, back up
  and upgrade.

### Neutral

- The `psycopg` 3 driver is a required dependency.
- The compose stack always includes a database container.

## Alternatives considered

### SQLite for tests, PostgreSQL for deployment

Tempting, and explicitly rejected. It would make the test suite trivially easy
to run and simultaneously worthless for its main purpose: `jsonb` behaviour,
constraint semantics, index behaviour, transaction isolation and type coercion
all differ. Every difference is a bug that passes CI and fails in a user's
deployment. A test suite that cannot fail the way production fails is a false
signal, and a false signal is worse than no signal.

### MySQL / MariaDB

Widely deployed and well understood. Rejected because its JSON support is weaker
than `jsonb`, and Django's PostgreSQL-specific features (which later modules are
likely to want) would be unavailable.

### MongoDB

Attractive for schemaless event payloads. Rejected because the data model is
overwhelmingly relational — users, permissions, assets, jobs, and the
relationships between them — and because giving up transactional integrity in an
*audit* system is not a trade worth making.

## Date

2026-08-11
