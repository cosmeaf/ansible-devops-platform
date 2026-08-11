# ADR 0008 — A single settings module

## Status

Accepted

## Context

Django projects commonly split settings into a package:

```text
settings/
├── base.py
├── development.py
├── production.py
└── local.py
```

The alternative is one `settings.py` reading everything environment-specific
from the environment.

The split exists to solve a problem: settings that genuinely differ in structure
between environments. This project does not have that problem. Every difference
between development and deployment here is a *value* — a hostname, a debug flag,
a cookie policy — not a different arrangement of settings.

## Decision

We will keep configuration in a **single `core/settings.py`**, with all
environment-specific values read from the environment via `python-decouple`.

## Consequences

### Positive

- One file to read to know how the platform is configured. A contributor does
  not have to trace an inheritance chain to answer "is this on in production?".
- No possibility of a setting defined in `base.py`, overridden in
  `production.py`, and re-overridden in a `local.py` that is not in version
  control — a class of bug that is genuinely hard to debug.
- Aligns with twelve-factor configuration: the same artefact runs everywhere,
  differing only by environment.
- The same image is used in development and deployment, so what you test is what
  you run.

### Negative

- The file is long, and grows as the platform does. Mitigated with clear section
  banners, and revisited if it stops being readable.
- Conditional blocks (`if DEBUG:`) appear inline rather than being separated by
  file. This is a visible trade, and the visibility is part of the point.
- Environment-specific defaults must be expressed as `config(...)` defaults,
  which is slightly more verbose than a plain assignment.

### Neutral

- `.env` is the local mechanism; real environment variables take precedence over
  it, which is what makes CI and container overrides work.

## Alternatives considered

### Settings package with per-environment modules

The conventional choice. Rejected because it solves a structural-difference
problem this project does not have, while introducing an override chain that is
easy to get wrong and hard to audit.

### `django-configurations` or similar

Class-based settings with inheritance. Rejected as a dependency and a layer of
indirection bought for no benefit at this size.

## Date

2026-08-11
