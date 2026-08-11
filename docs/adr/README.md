# Architecture Decision Records

An ADR captures a decision that shapes the system's structure: the context, the
decision itself, its consequences, and what was rejected.

The reason to keep them is simple. Code shows *what* the system does. Git shows
*when* it changed. Neither shows *why* someone chose PostgreSQL over MongoDB, or
why the agent is optional. Without that, a future contributor either repeats a
settled argument or reverses a decision without knowing what it cost.

## Index

| ADR | Title | Status |
|---|---|---|
| [0001](0001-django-backend.md) | Django as the backend framework | Accepted |
| [0002](0002-postgresql-primary-database.md) | PostgreSQL as the primary database | Accepted |
| [0003](0003-redis-celery.md) | Redis and Celery for asynchronous work | Accepted |
| [0004](0004-nextjs-frontend-planned.md) | Next.js as a separate frontend module | Proposed |
| [0005](0005-ansible-execution-engine.md) | Ansible as the execution engine | Accepted |
| [0006](0006-go-agent-planned.md) | Optional Go agent for observation | Proposed |
| [0007](0007-apache-2-license.md) | Apache License 2.0 | Accepted |
| [0008](0008-single-settings-module.md) | A single settings module | Accepted |
| [0009](0009-ipintel-provider-abstraction.md) | Provider abstraction for IP intelligence | Accepted |
| [0010](0010-audit-secret-redaction.md) | Redact secrets in the model layer | Accepted |
| [0011](0011-role-based-access-control.md) | Roles are the only source of authorisation | Accepted |
| [0012](0012-admin-is-not-product-surface.md) | Django Admin is not product surface | Accepted |

## Status meanings

- **Proposed** — decided in principle, not yet implemented.
- **Accepted** — decided and implemented.
- **Superseded** — replaced by a later ADR, which is linked.
- **Deprecated** — no longer applies, and nothing replaced it.

## Writing one

Copy [0000-template.md](0000-template.md), take the next number, and open a pull
request. Architectural changes need the ADR *before* the implementation — see
[GOVERNANCE.md](../../GOVERNANCE.md).
