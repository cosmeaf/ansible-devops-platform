# ADR 0011 — Roles are the only source of authorisation

## Status

Accepted

## Context

Django ships `is_staff` and `is_superuser` as boolean columns on the user. They
are easy to reach for, and they are a poor authorisation model for a platform
that several people share:

- they are binary — there is no "may read the audit trail but may not manage
  users";
- they are set by hand, so access drifts and nobody can reconstruct why a given
  account has the access it has;
- `is_staff` conflates two unrelated questions: "may this person use the
  platform?" and "may this person open Django Admin?".

The platform needs to answer "who may do what" for an operator, a developer, an
auditor and a viewer, and to answer it the same way for the server-rendered
interface today and the Next.js client tomorrow.

## Decision

We will make **roles the only source of authorisation**.

- `Role` carries a set of Django `Permission` objects plus two explicit
  capability flags: `grants_admin_access` and `grants_superuser`.
- `UserRole` assigns a role to a user, recording who assigned it and when.
- `is_staff` and `is_superuser` are **derived** from a user's roles and
  resynchronised by signal whenever an assignment changes. They are never
  authoritative and are never set by hand.
- `RolePermissionBackend` resolves `has_perm()` through role membership,
  composed alongside Django's `ModelBackend`, which continues to handle
  authentication.

Five system roles ship with the platform: Administrator, Operator, Developer,
Auditor, Viewer. Only Administrator grants admin access.

## Consequences

### Positive

- Access is explainable. "Why can this person see that?" is answered by naming
  a role, not by reading a boolean.
- Granting and revoking is one operation and cannot leave the flags
  inconsistent, because the flags are recomputed from the roles.
- The permission model is the same one the API and the future Next.js client
  will consume, so the interface cannot drift from the rules.
- Platform access and Django Admin access are now separate questions, which is
  what makes [ADR 0012](0012-admin-is-not-product-surface.md) enforceable
  rather than merely a convention.
- Custom roles need no code change.

### Negative

- Two extra tables and a signal on the write path of role assignment.
- The derived flags can be edited directly in the database or in Django Admin,
  which would put them out of step until the next assignment change. Making
  them fully immutable would mean overriding the user model, which is a larger
  change than this earns today.
- Permission checks now hit role membership. Cached per request object, but it
  is more work than reading a boolean column.
- `bulk_create` on `UserRole` bypasses `post_save` and so bypasses flag
  synchronisation. Documented; use ordinary saves.

### Neutral

- Django's group permissions still work; roles are additive, not a replacement
  for the built-in machinery.

## Alternatives considered

### Django groups with a naming convention

Groups already carry permissions, and a convention could mark which group means
"admin". Rejected because a convention is not enforcement: nothing stops the
flags and the groups disagreeing, and groups have no place to record who
granted access or when.

### `is_staff` / `is_superuser` as the model

The status quo. Rejected for the reasons in Context — chiefly that it cannot
express an auditor, which is a role this project specifically needs.

### A full policy engine (Casbin, OPA)

Expressive, and genuinely better at scale. Rejected as far beyond what a
five-role platform needs; it would add a dependency and a language for rules
nobody has yet had to write.

## Date

2026-08-11
