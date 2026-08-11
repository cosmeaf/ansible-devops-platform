# Development

The full setup guide lives in [DEVELOPMENT.md](../DEVELOPMENT.md). This page
covers day-to-day working details.

## Quick reference

```bash
make help          # every target
make dev-services  # PostgreSQL + Redis on loopback
make check         # django check + migration drift
make lint          # ruff check + format check
make format        # apply fixes
make test          # pytest
make test-cov      # pytest with coverage
```

## Layout of a change

Most changes touch some subset of:

```text
<app>/models.py          the data
<app>/migrations/        the schema change (generated, then reviewed)
<app>/admin.py           how operators see it
tests/test_<app>.py      proof it works
docs/                    how a user learns about it
CHANGELOG.md             what changed
```

## Adding a model

1. Define it in `<app>/models.py`, inheriting `BaseModel`.
2. Give it `__str__`, `Meta.ordering`, verbose names and any indexes the queries
   will need.
3. `python manage.py makemigrations` — then **read the generated file**.
4. Register it in `<app>/admin.py`. Mark anything sensitive `readonly` or mask
   it.
5. Write tests for the behaviour, not the field list.
6. `python manage.py migrate`.

## Adding an endpoint

DRF defaults to `IsAuthenticated`. An endpoint that should be public has to say
so explicitly — and should have a test asserting it, so that "public" is a
decision rather than an accident.

## Writing tests

- Test behaviour, not lines. A test written to move a coverage number implies a
  confidence that is not there.
- A bug fix comes with a test that fails before the fix.
- Never delete or skip a failing test to make CI green. If a test is genuinely
  wrong, fix it — and say so in the pull request.
- Fixtures live in `tests/conftest.py`.

Useful invocations:

```bash
pytest tests/test_audit.py::test_audit_event_redacts_passwords_on_save
pytest -k redact
pytest -x --ff          # stop at first failure, failures first
pytest --cov --cov-report=term-missing
```

## Debugging across processes

Work that crosses the API and a Celery worker is hard to follow. The request id
is there to make it tractable:

```bash
curl -si -H 'X-Request-ID: my-trace' http://localhost:47420/api/v1/health/
docker compose logs | grep my-trace
```

## Style

Ruff enforces formatting and lint; `pyproject.toml` holds the configuration.
Beyond what it can check:

- English identifiers, comments and docstrings;
- explicit over clever;
- no abstraction without a second implementation in sight — with the documented
  exception of the ipintel provider, whose reasoning is in
  [ADR 0009](adr/0009-ipintel-provider-abstraction.md);
- never log or persist a credential.

## Before opening a pull request

```bash
make check && make lint && make test
```

CI runs the same three. If they pass locally they will pass there, unless the
difference is environmental — in which case that is worth knowing about.
