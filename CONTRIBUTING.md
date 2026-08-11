# Contributing

Thank you for considering a contribution. This document covers everything from
setting up your environment to getting a pull request merged.

By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

---

## Before you start

- **Found a security vulnerability?** Do not open a public issue. Follow
  [SECURITY.md](SECURITY.md).
- **Have a question?** Use Discussions, not an issue. See [SUPPORT.md](SUPPORT.md).
- **Planning something large?** Open a Discussion or issue first. An
  architectural change needs an ADR (see [GOVERNANCE.md](GOVERNANCE.md)) before
  the code, so nobody spends a weekend on a direction the project won't take.
- **New here?** Issues labelled `good-first-issue` are scoped to be approachable.

---

## Development environment

### Prerequisites

| Tool | Version |
|---|---|
| Git | any recent |
| Python | 3.12 |
| Docker | 24+ |
| Docker Compose | v2+ |

### Fork and clone

```bash
# Fork on GitHub first, then:
git clone https://github.com/<your-username>/ansible-devops-platform.git
cd ansible-devops-platform
git remote add upstream https://github.com/cosmeaf/ansible-devops-platform.git
```

### Branch

Branch from an up-to-date `main`:

```bash
git fetch upstream
git checkout -b feature/short-description upstream/main
```

Branch prefixes: `feature/`, `fix/`, `docs/`, `refactor/`, `test/`,
`security/`, `chore/`.

Examples: `feature/server-inventory`, `fix/login-rate-limit`,
`docs/docker-installation`, `security/session-hardening`.

### Virtual environment and dependencies

```bash
python3.12 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
```

### Environment file

```bash
./scripts/bootstrap.sh
```

The script generates a `.env` with every secret filled in. It is idempotent —
it will not overwrite an existing `.env`. Never commit `.env`; it is gitignored
for a reason.

### Backing services

The main compose file deliberately does not publish PostgreSQL or Redis. For
host-side development, add the dev override, which binds them to loopback only:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml \
    up -d ansible-postgres ansible-redis

export POSTGRES_HOST=127.0.0.1 POSTGRES_PORT=47432
export REDIS_HOST=127.0.0.1 REDIS_PORT=47379
```

### Migrations

```bash
python manage.py migrate
```

If you changed a model:

```bash
python manage.py makemigrations
```

Review the generated file before committing it. CI fails if a model change has
no matching migration.

### Run

```bash
python manage.py runserver
```

---

## Quality checks

Run all of these before pushing — CI runs the same ones.

```bash
make check      # python manage.py check + makemigrations --check
make lint       # ruff check + ruff format --check
make test       # pytest
```

Or individually:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
ruff check .
ruff format --check .
pytest
```

Optional but recommended:

```bash
pre-commit install
```

### Testing expectations

- Tests run against **real PostgreSQL**, never SQLite. Substituting SQLite hides
  the incompatibilities the suite exists to catch.
- Test behaviour, not lines. Coverage written to move a percentage is worse than
  no test, because it implies confidence that isn't there.
- A bug fix should come with a test that fails before the fix.
- Never delete or skip a failing test to make CI green. If a test is genuinely
  wrong, fix it and say so in the PR.

---

## Code style

- **English everywhere** — identifiers, comments, docstrings, commit messages,
  documentation. `class Server`, not `class Servidor`.
- Ruff handles formatting and linting; `pyproject.toml` holds the configuration.
- Favour KISS and explicit over clever. Apply DRY and SOLID where they genuinely
  help, not as a ritual.
- Avoid premature abstraction: no service layer for trivial CRUD, no generic
  repository wrapper, no microservice boundaries this project has not earned.
- Never log or persist a credential. Audit payloads pass through
  `audit.sanitizers.sanitize`; keep it that way.

---

## Commits

This project uses [Conventional Commits](https://www.conventionalcommits.org/).

```text
<type>(<optional scope>): <short imperative summary>
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `build`, `ci`, `chore`,
`perf`, `security`.

```text
feat(auth): add initial RBAC structure
fix(audit): preserve request id across the response
docs: add local development guide
ci: add backend test workflow
security(auth): harden session configuration
```

Keep commits focused. Several small, reviewable commits beat one large one.

---

## Pull requests

```bash
git push origin feature/short-description
```

Open the PR against `main` and fill in the template. A good PR:

- does one thing;
- explains **why**, not just what;
- links the issue it closes (`Fixes #123`);
- includes tests;
- updates documentation when behaviour changes;
- notes any security or breaking-change impact.

### Flow

```text
Fork → Clone → Branch → Develop → Test → Commit → Push
     → Pull Request → CI → Review → Merge
```

CI must pass. A maintainer reviews; expect questions — they are about the code,
not about you. Merges are squashed, so your branch history stays yours and
`main` stays readable.

---

## Recognition

Every merged contribution is part of the project's history. Contributors are
credited via Git history and GitHub's contributor list.
