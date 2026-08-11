# ADR 0004 — Next.js as a separate frontend module

## Status

**Proposed** — planned for Module 2. Not implemented.

## Context

Module 1 ships Django Admin and two minimal server-rendered pages. That is
enough to operate the platform, and nowhere near enough to be a product: no
dashboards, no playbook editor, no live execution logs, no role-aware
navigation.

The question is whether the interface should be Django templates or a separate
application.

## Decision

We will build the web interface as **`ansible-web`, a separate Next.js +
TypeScript application** consuming the platform's REST API, delivered as its own
module.

The backend stays API-first. The interface is a client, not a layer inside
Django.

## Consequences

### Positive

- The API is forced to be complete and usable, because the UI has no privileged
  access to Django internals. Anything the UI can do, a script can do.
- Live execution logs and an embedded editor (Monaco) are natural in a rich
  client and awkward in server-rendered templates.
- Frontend and backend can be developed, tested, versioned and deployed
  independently.
- TypeScript against a generated client catches API contract drift at compile
  time.

### Negative

- Two applications, two toolchains, two dependency trees, two CI pipelines.
- Cross-origin authentication needs deliberate design — CSRF, cookies and
  origins do not solve themselves. This is why `CORS_ALLOWED_ORIGINS` is empty
  by default rather than permissive.
- A contributor who wants to change one screen may need to run both.
- More total code than templates would require.

### Neutral

- Django Admin remains available as an operator fallback.
- Module 1 is fully usable before any of this exists.

## Alternatives considered

### Django templates + HTMX

Far less machinery, one deployment, no CORS problem, and genuinely capable. The
strongest alternative. Rejected because the target interface — live streaming
logs, a code editor, an inventory graph — is where server-rendered fragments
stop being the simpler option, and because keeping the UI in Django makes it too
easy to let the API rot.

### Django REST + React SPA (no framework)

Similar benefits without Next.js's conventions. Rejected mainly for the lack of
built-in routing, data-fetching and rendering conventions, which a small team
would end up reinventing.

### No web UI, API only

Honest and cheap. Rejected because the project's stated goal is to be
approachable and self-hosted, and "write your own client" is neither.

## Date

2026-08-11
