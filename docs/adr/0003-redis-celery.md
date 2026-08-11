# ADR 0003 — Redis and Celery for asynchronous work

## Status

Accepted

## Context

Ansible playbook runs take minutes to hours. They cannot happen inside an HTTP
request. The platform also needs scheduled work (periodic runs, inventory
refresh, retention) and, later, live log streaming from a running job.

Django's request cycle is synchronous, so the work has to leave the web process.

## Decision

We will use **Celery 5** for asynchronous execution and scheduling, with
**Redis 7** as broker, result backend and cache.

## Consequences

### Positive

- Long-running executions leave the request cycle entirely, so a playbook run
  cannot hold a web worker.
- Celery Beat provides scheduling without a separate cron server, and without
  cron's opacity.
- Redis serves three roles — broker, result backend and Django cache — so the
  stack carries one dependency instead of three.
- Celery's retry, time-limit and acknowledgement semantics are mature; the
  configuration uses `acks_late` with `reject_on_worker_lost` so a task is not
  silently lost when a worker dies.

### Negative

- Two more containers to run and monitor (`ansible-celery`, `ansible-celery-beat`).
- Redis as a broker does not persist messages as durably as a dedicated message
  queue; a Redis loss can lose queued tasks. Acceptable now, and a reason to
  revisit if job durability becomes a stated guarantee.
- Debugging spans two processes, which is harder than one. The request-ID
  correlation exists partly to make this tractable.

### Neutral

- Beat's schedule file needs a writable path, which the container provides at
  `/var/run/ansible/` since `/app` is not writable by the unprivileged user.

## Alternatives considered

### RabbitMQ as broker

More durable and feature-complete for message queuing. Rejected for now because
it adds a second infrastructure service where Redis already earns its place as
cache, and the durability gap does not yet matter. Worth revisiting when the
platform makes promises about job delivery.

### Django-Q / Huey

Lighter than Celery. Rejected because Celery's ecosystem, documentation and
operational track record matter more than a smaller dependency, and because
later modules will want features (chords, canvas, routing) these do not have.

### Cron in a container

Simplest possible scheduler. Rejected: no visibility into runs, no retry
semantics, no result tracking, and no way for the platform to report what
happened — which is most of the point.

## Date

2026-08-11
