# Contributing

The full guide is [CONTRIBUTING.md](../CONTRIBUTING.md) at the repository root.
This page is a short orientation.

## In one minute

```bash
# fork on GitHub, then
git clone https://github.com/<you>/ansible-devops-platform.git
cd ansible-devops-platform
git checkout -b feature/my-change

python3.12 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
./scripts/bootstrap.sh
make dev-services

# ... make your change, with tests ...

make check && make lint && make test
git commit -m "feat(scope): describe the change"
git push origin feature/my-change
```

Then open a pull request and fill in the template.

## Where things go

| You want to | Go to |
|---|---|
| Report a bug | Issues → Bug report |
| Suggest a feature | Discussions → Ideas, then Issues |
| Ask a question | Discussions → Q&A |
| Report a vulnerability | [SECURITY.md](../SECURITY.md) — privately |
| Fix a typo in the docs | Straight to a pull request |

## Conventions in brief

- **Branches:** `feature/` `fix/` `docs/` `refactor/` `test/` `security/`
  `chore/`
- **Commits:** [Conventional Commits](https://www.conventionalcommits.org/) —
  `feat(auth): add role model`
- **Language:** English, everywhere
- **Tests:** required for behaviour changes
- **CI:** must pass; never make it pass by deleting a test

## First contribution

Look for `good-first-issue`. Documentation improvements and additional tests are
genuinely valuable and are the easiest way to get familiar with the codebase.

## Bigger changes

Anything architectural needs a decision record before the code — see
[adr/](adr/) and [GOVERNANCE.md](../GOVERNANCE.md). This is not bureaucracy; it
is so that you do not spend a weekend on a direction the project cannot take.
