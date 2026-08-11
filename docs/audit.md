# Audit

The audit trail records who did what, to what, from where, and with what result.

## The model

`audit.models.AuditEvent`:

| Field | Purpose |
|---|---|
| `uuid` | External identifier |
| `user` | Actor. `NULL` after the account is deleted. |
| `username_snapshot` | The actor's name, preserved independently of the FK |
| `request_id` | Correlates the event with logs and the HTTP response |
| `session_id` | Session the action came from |
| `source_ip` | Origin address |
| `country`, `asn` | Enrichment, populated by `ipintel` when available |
| `module` | Which part of the platform |
| `resource_type`, `resource_id` | What was acted on |
| `action` | `CREATE` `READ` `UPDATE` `DELETE` `EXECUTE` `CHECK` `LOGIN` `LOGOUT` `DENIED` `EXPORT` `DOWNLOAD` |
| `previous_value`, `new_value` | Before and after, as JSON |
| `result` | `SUCCESS` `FAILED` `DENIED` |
| `user_agent` | Client string |
| `metadata` | Anything else, as JSON |
| `created_at` | When |

### Why `username_snapshot` exists

`user` is `on_delete=SET_NULL`, so deleting an account nulls the reference
rather than cascading and erasing the trail. But that alone would leave an event
that records an action with no actor.

`username_snapshot` is written on save and never cleared. Delete the user and
the trail still says `admin` did it. An audit log that forgets its subject when
the subject is removed is exactly the log an attacker wants.

## Secret redaction

**Nothing credential-shaped is ever written to the audit table.**

`previous_value`, `new_value` and `metadata` all pass through
`audit.sanitizers.sanitize` inside `AuditEvent.save()`.

```python
AuditEvent.objects.create(
    module="authentication",
    action="UPDATE",
    new_value={"username": "admin", "password": "hunter2"},
)
# stored: {"username": "admin", "password": "[REDACTED]"}
```

Matching is on the **key name**: case-insensitive, substring-based, applied
recursively through nested dicts and lists.

Recognised: `password` `passwd` `secret` `token` `api_key` `apikey`
`private_key` `privatekey` `cookie` `authorization` `auth_header` `session_key`
`sessionid` `csrfmiddlewaretoken` `credential` `passphrase` `salt` `signature`
`encryption_key`.

Because matching is substring-based, `new_password`, `smtp_password` and
`X-Api-Key` are all caught without being listed.

### Why redaction lives in `save()`

So a caller cannot forget. Any code path that writes an audit event is covered —
including code written by someone who never read this page. See
[ADR 0010](adr/0010-audit-secret-redaction.md).

### Known limits

Two, both deliberate and both worth knowing:

1. **Key-based, not value-based.** A secret under an innocuous key —
   `{"note": "the password is hunter2"}` — is not caught. Value-based detection
   was rejected because its false positives create false confidence.
2. **`bulk_create` bypasses `save()`, and therefore bypasses redaction.** Do not
   use it for audit events. If bulk writes are ever needed, redaction must move
   to a pre-save signal first.

## Request correlation

`RequestAuditContextMiddleware` accepts an inbound `X-Request-ID` or generates a
UUID, publishes it to a `ContextVar`, and echoes it on the response.

```bash
curl -si http://localhost:47420/api/v1/health/ | grep -i x-request-id
```

```text
X-Request-ID: 3f2b1c8e-...
```

Every log record emitted during that request carries the same id:

```text
2026-08-11 12:00:00 INFO [3f2b1c8e-...] audit: ...
```

Outside a request — a management command, a Celery task — the id is `-`.

The `ContextVar` is reset in a `finally` block, so a pooled worker thread never
inherits a stale id from the request before it.

## Querying

Django Admin exposes the trail read-only, filterable by action, result, module
and date, and searchable by username, request id, resource and source IP.

Programmatically:

```python
from audit.models import AuditEvent

AuditEvent.objects.filter(username_snapshot="admin")
AuditEvent.objects.filter(result="DENIED")
AuditEvent.objects.filter(request_id="3f2b1c8e-...")
AuditEvent.objects.filter(resource_type="Server", resource_id="42")
```

Indexes exist for `(-created_at, module)`, `(user, -created_at)`,
`(action, result)` and `(resource_type, resource_id)`.

## Immutability

Django Admin blocks add, change and delete on audit events. That is an
application-level guarantee — it stops an operator, not an attacker with
database access.

There is **no cryptographic integrity protection**. Hash chaining or signed
append-only storage would provide it; neither is implemented. If you need
tamper-evidence today, ship the logs off-host to storage the platform cannot
write to.

## Retention

None. Events accumulate indefinitely. A retention policy is a roadmap item; for
now, if you generate a lot of events, plan for the table to grow.
