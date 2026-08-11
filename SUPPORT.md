# Support

Where to take what, so questions reach the right place and issues stay useful.

## Choose a channel

| You have… | Use | Why |
|---|---|---|
| A question about how to use the platform | **Discussions → Q&A** | Questions are conversations, not defects |
| An idea or feature suggestion | **Discussions → Ideas** | Gets shaped before becoming an issue |
| A confirmed, reproducible bug | **Issues → Bug report** | Tracked to a fix |
| A scoped feature request with a clear use case | **Issues → Feature request** | Tracked to a decision |
| A documentation error | **Issues → Documentation** | Small, actionable, great first contribution |
| A security vulnerability | **Private advisory — see [SECURITY.md](SECURITY.md)** | Public disclosure endangers every deployment |
| Something to show off | **Discussions → Show and Tell** | We'd like to see it |

**Issues are for confirmed bugs and scoped requests.** If you are not sure
whether the behaviour you're seeing is a bug, start in Discussions. Nobody will
mind, and it is much better than an issue that turns out to be a typo in a
`.env` file.

Please do not use a pull request to ask a support question.

## Before you ask

Most reports get answered fastest when the asker has already:

1. Read [docs/troubleshooting.md](docs/troubleshooting.md).
2. Checked `docker compose ps` and `docker compose logs`.
3. Checked `GET /api/v1/health/`.
4. Searched existing issues and discussions.

## Making a good report

Include:

- what you expected to happen, and what happened instead;
- the version or commit;
- deployment method and host OS;
- Docker and Docker Compose versions;
- the relevant log output.

**Redact secrets before pasting anything.** Logs and `.env` dumps routinely
contain passwords, tokens and keys. Remove them first — once it is in a public
issue, it is public.

## Response expectations

This is an open-source project maintained by volunteers. There is no support
contract and no guaranteed response time. Clear, reproducible reports get
answered first, simply because they can be.

## Commercial support

None is offered today.
