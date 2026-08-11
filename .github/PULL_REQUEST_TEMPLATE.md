## Description

<!-- What does this change, and why? The "why" matters more than the "what" —
     the diff already shows the what. -->

## Related issue

<!-- Fixes #123 / Closes #123 / Relates to #123 -->

Fixes #

## Type of change

- [ ] Bug fix — a non-breaking change that fixes a defect
- [ ] Feature — a non-breaking change that adds capability
- [ ] Refactor — no change in behaviour
- [ ] Documentation
- [ ] Security
- [ ] Tests
- [ ] Build / CI

## Component

- [ ] Backend / API
- [ ] Frontend
- [ ] Ansible
- [ ] Agent
- [ ] Docker / deployment
- [ ] Database / migrations
- [ ] Documentation
- [ ] Security

## Testing

<!-- What did you actually run, and what did it show? "Tests pass" is less
     useful than "added 4 tests covering X; verified Y manually against a
     fresh bootstrap". -->

## Security impact

<!-- Does this touch authentication, authorisation, secrets, audit, network
     exposure or dependencies? If not, say "None". If yes, explain. -->

## Breaking changes

<!-- Does this change an API, a setting name, a database schema or a default in
     a way that would break an existing installation? If yes, describe the
     upgrade path. -->

## Screenshots

<!-- For anything visible. Delete this section if not applicable. -->

## Checklist

- [ ] Tests pass locally (`make test`)
- [ ] `python manage.py check` passes
- [ ] `makemigrations --check --dry-run` reports no drift
- [ ] Lint and formatting pass (`make lint`)
- [ ] **No secrets committed** — no `.env`, keys, tokens or passwords
- [ ] Documentation updated where behaviour changed
- [ ] Migrations reviewed by hand, not just generated
- [ ] Security implications considered
- [ ] Backwards compatibility considered
- [ ] `CHANGELOG.md` updated under `Unreleased`
- [ ] Commits follow [Conventional Commits](https://www.conventionalcommits.org/)
