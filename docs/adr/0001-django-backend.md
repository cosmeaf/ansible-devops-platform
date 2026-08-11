# ADR 0001 — Django as the backend framework

## Status

Accepted

## Context

The platform needs a backend that can deliver, quickly and without being
assembled from parts: an admin interface for early operation, a mature ORM with
real migrations, session and permission primitives to build RBAC on, and an
ecosystem that a contributor is likely to already know.

The audit and security requirements mean the framework's own security posture
matters as much as its features. The project is maintained by a small team, so
"batteries included" is worth more than maximum flexibility.

## Decision

We will build the backend on **Django 5** with **Django REST Framework**.

## Consequences

### Positive

- Django Admin gives a usable operator interface on day one, before any custom
  UI exists — this is why Module 1 is usable at all.
- The ORM's migration system handles schema evolution without a separate tool.
- `django.contrib.auth` provides users, groups and permissions, which is the
  foundation the planned RBAC extends rather than replaces.
- Django's security defaults (CSRF, XSS escaping, SQL parameterisation,
  clickjacking protection) are on by default and are actively maintained.
- Large contributor pool: Django and DRF are widely known.

### Negative

- Django's synchronous core makes long-running Ansible executions unsuitable for
  the request cycle. This forces the Celery dependency (see [ADR 0003](0003-redis-celery.md))
  rather than making it optional.
- DRF is heavier than a minimal API layer, and its class hierarchy has a
  learning curve.
- Django's conventions are opinionated; fighting them is expensive, so the
  project largely does not.

### Neutral

- Python 3.12 becomes the minimum runtime.
- Ansible is also Python, so the future runner integration shares an ecosystem.

## Alternatives considered

### FastAPI

Faster and natively asynchronous, with better OpenAPI generation. Rejected
because it ships no admin interface, no ORM, no migrations and no auth system.
Each would have to be chosen, integrated and maintained separately — for a small
team that is a large recurring cost, and it would have delayed a usable Module 1
substantially.

### Flask

Maximum flexibility, minimum structure. Rejected for the same reason as FastAPI,
more so: nearly every component would be a separate decision.

### Go

Excellent for the planned agent, and it is what the agent will use. Rejected for
the platform because the automation ecosystem here is Python — Ansible itself is
Python — and the productivity gap for CRUD-heavy, admin-heavy work is real.

## Date

2026-08-11
