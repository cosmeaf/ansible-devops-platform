# ADR 0010 — Redact secrets in the model layer

## Status

Accepted

## Context

`AuditEvent` stores `previous_value`, `new_value` and `metadata` as JSON. These
fields exist to record what changed — and what changed is frequently a
credential: a user changing their password, an administrator rotating an API
key, a failed login carrying the attempted password in the request body.

An audit trail that stores the password it was recording an attempt against has
converted a security control into a credential database. Worse, it is a
credential database that everyone with audit-read permission can query, and that
gets included in every backup.

The question is *where* redaction happens.

## Decision

We will redact in **`AuditEvent.save()`**, not at the call sites.

Every JSON payload passes through `audit.sanitizers.sanitize`, which walks the
structure recursively and replaces the value of any key whose name matches a
credential pattern with `[REDACTED]`.

## Consequences

### Positive

- **A caller cannot forget.** This is the entire reason for the placement. Any
  code path that writes an audit event — existing, future, or written by a
  contributor who never read this ADR — is covered.
- Redaction is enforced at the last point before persistence, so it also covers
  events created by the ORM directly, in a shell, or in a data migration.
- Matching is on the key name, case-insensitive and substring-based, so
  `new_password`, `X-Api-Key` and `smtp_password` are all caught without
  enumerating them.
- Depth-limited traversal, so a pathological or cyclic payload cannot hang the
  save.

### Negative

- A save-time transformation means the object in memory differs from what the
  caller passed. Surprising if you are not expecting it — hence this ADR and the
  docstring.
- Redaction is **key-based, not value-based**. A secret stored under an
  innocuous key (`{"note": "the password is hunter2"}`) is not caught. Value
  based detection was considered and rejected: it produces false positives on
  legitimate data, and false confidence is more dangerous than a known limit.
- `bulk_create` bypasses `save()` and therefore bypasses redaction. This is a
  real gap. It is documented in `docs/audit.md`; if bulk audit writes are ever
  needed, redaction must move to a pre-save signal or a manager method.
- A small per-save cost proportional to payload size.

### Neutral

- The sensitive-key list is a module constant, so a deployment with unusual
  field names can extend it.

## Alternatives considered

### Redact at each call site

Explicit and visible at the point of use. Rejected because it is guaranteed to
be forgotten eventually, and the failure is silent — a credential is written and
nobody notices until it is discovered in a backup.

### Redact on read/display

Keeps the raw data for forensics. Rejected outright: the secret is still in the
database, still in every backup, and still one query or one misconfigured
permission away from exposure. Storing it is the problem.

### Value-based detection (entropy, regexes for key formats)

Would catch secrets under innocuous key names. Rejected as a primary mechanism
because it misclassifies legitimate data — hashes, UUIDs, base64 payloads — and
because a detector that is right most of the time invites trusting it. Possible
future addition *alongside* key matching, never instead of it.

## Date

2026-08-11
