# ADR 0012 — Django Admin is not product surface

## Status

Accepted

## Context

Django Admin is excellent, and it made Module 1 usable before any interface
existed. That convenience is also a trap.

If the product's interface links into the admin, the admin becomes the product
by default. That has consequences that are hard to reverse:

- the admin is generated from the models, so it exposes every field, every
  relation and every delete button, ignoring the platform's own authorisation
  rules;
- it has no concept of the platform's roles beyond the single `is_staff` bit;
- the Next.js module cannot reuse any of it, so any workflow that grows inside
  the admin has to be rebuilt later;
- users learn an interface that is scheduled to be taken away from them.

## Decision

**Django Admin is an operator backdoor for running the platform. It is never
product surface.**

Concretely:

- No page in the platform interface links to `/admin/`. Enforced by tests
  asserting that neither `href="/admin/` nor "Django Admin" appears in any
  rendered management page, the landing page, or the sign-in page.
- The platform ships its own management interface at `/manage/`, gated by
  role-derived permissions ([ADR 0011](0011-role-based-access-control.md)).
- Admin access is granted only by a role with `grants_admin_access`. The
  default platform account does not have it and is redirected away from
  `/admin/`.
- Any capability an operator genuinely needs belongs in `/manage/` and in the
  API — not in the admin.

The admin is retained, because removing it would leave a deployment with no way
to recover from a broken role configuration.

## Consequences

### Positive

- Every user-facing capability has to exist in the platform's own interface and
  therefore in its API, which is what keeps the API honest.
- Users only ever see screens that respect the role model.
- The Next.js module replaces a defined surface, rather than an accumulation of
  admin workflows.
- A compromised platform account does not reach the admin unless its role says
  so.

### Negative

- Management screens must be built that the admin would have given for free.
  Module 1 pays this cost immediately, in views and templates.
- Two interfaces exist over the same models, which is duplication.
- Operators used to reaching the admin for everything have to learn where the
  supported path is.

### Neutral

- The admin stays registered and useful for recovery and for low-level
  inspection by an administrator.

## Alternatives considered

### Use Django Admin as the interface

Free, immediate, and the reason it was tempting. Rejected: it cannot express
the role model, it exposes destructive operations indiscriminately, and every
workflow built there is thrown away when Module 2 lands.

### Remove Django Admin entirely

Cleanest boundary. Rejected because it removes the recovery path — if role
assignment breaks, an administrator needs a way in that does not depend on the
role system working.

### Theme the admin to look like the product

Cheap to start. Rejected as the worst option: it makes the admin *look*
supported while keeping all its behaviour, which encourages exactly the
dependence this decision exists to prevent.

## Date

2026-08-11
