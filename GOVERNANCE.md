# Governance

How this project is run and how a change becomes part of it. Deliberately
lightweight — enough structure to be predictable, not so much that contributing
becomes paperwork.

## Roles

### Project Lead

Currently [@cosmeaf](https://github.com/cosmeaf).

Responsible for:

- architectural direction;
- roadmap and scope;
- releases and versioning;
- security response and advisories;
- approving structural changes;
- appointing maintainers.

### Maintainers

Contributors granted commit rights after a sustained track record of good
contributions and review.

Responsible for:

- reviewing and merging pull requests;
- triaging issues and applying labels;
- keeping CI healthy;
- maintaining documentation;
- upholding the [Code of Conduct](CODE_OF_CONDUCT.md).

There are no additional maintainers yet. This section exists so the path is
visible before it is needed.

### Contributors

Anyone who opens an issue, proposes a change, writes a test, improves a
document, or helps someone in Discussions. No formal process, no application.

## Becoming a maintainer

There is no application form. The path is: contribute meaningfully over time,
review other people's work, and act in the project's interest. The Project Lead
extends the invitation.

## Decision making

| Change | Process |
|---|---|
| Bug fix, small feature, docs, tests | Pull request + review |
| Architectural change | Issue or Discussion first, then an [ADR](docs/adr/), then the PR |
| Backwards-incompatible change | ADR **before** implementation, explicit approval from the Project Lead |
| Security fix | Private, coordinated — see [SECURITY.md](SECURITY.md) |
| Release | Project Lead |

Decisions are made in the open by consensus wherever possible. When consensus
is not reached, the Project Lead decides — and records why, so the reasoning
outlives the discussion.

## Architecture Decision Records

Anything that shapes the system's structure gets an ADR in
[docs/adr/](docs/adr/): the context, the decision, the consequences, and the
alternatives that were rejected. The point is that someone arriving in two
years can understand *why*, not just *what*.

Start from [docs/adr/0000-template.md](docs/adr/0000-template.md).

## Code review

- Every change reaches `main` through a pull request.
- CI must pass. Failing tests are not merged, and are never deleted to make CI
  green.
- Review comments are about the code. Disagreement is fine; disrespect is not.
- With a single maintainer, self-merge is permitted for routine changes so the
  project does not deadlock. Anything architectural or security-relevant waits
  for a second opinion where one is available.

## Project scope

The scope is: an open-source, self-hosted platform for DevOps automation and
infrastructure management built around Ansible.

Explicitly **out** of scope:

- replacing Ansible with a proprietary automation format;
- vendor lock-in of any kind;
- a hosted SaaS offering;
- making the optional Go agent a requirement.

A feature request that conflicts with these will be declined with the reason
stated.

## Changing this document

Through a pull request, approved by the Project Lead.
