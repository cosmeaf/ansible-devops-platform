# Security Policy

## Supported versions

The project is in early development. Only the latest release line receives
security fixes.

| Version | Supported |
|---|---|
| `0.1.x` (Module 1, alpha) | ✅ |
| Unreleased `main` | ✅ best effort |
| Anything older | ❌ |

There is no long-term-support release yet. That will change at `1.0.0`.

---

## Reporting a vulnerability

**Do not open a public issue, pull request or Discussion for a security
vulnerability.** A public report gives every deployment's attacker the same
information as its maintainer, before a fix exists.

Instead, use **GitHub Private Vulnerability Reporting**:

1. Go to the repository's **Security** tab.
2. Choose **Report a vulnerability**.
3. Fill in the advisory form.

This opens a private channel visible only to maintainers. If private reporting
is unavailable to you, contact the project lead privately on GitHub
([@cosmeaf](https://github.com/cosmeaf)) and ask for a secure channel — do not
include vulnerability details in that first message.

### What to include

The more of this you can provide, the faster the fix:

- affected version or commit;
- deployment method (Docker Compose, manual, other);
- component (API, Celery, database, Docker, bootstrap script, dependency);
- a clear description of the issue and its impact;
- reproduction steps;
- your assessment of severity, and any CVE/CWE reference you think applies.

### What NOT to include

- **No secrets.** Redact passwords, tokens, private keys, session cookies and
  `Authorization` headers from every log, screenshot and paste.
- **No third-party data.** Do not include data belonging to systems you do not
  own.
- **No weaponised exploit in a public place.** Share proof-of-concept code only
  through the private channel.

---

## What to expect

| Stage | Target |
|---|---|
| Acknowledgement of your report | within 5 business days |
| Initial triage and severity assessment | within 10 business days |
| Status update cadence while open | at least every 14 days |
| Fix or documented mitigation | depends on severity and complexity |

These are targets for a project currently maintained by a small team, not a
contractual SLA. If a deadline slips you will be told, not left in silence.

## Disclosure process

1. You report privately.
2. We confirm the issue and assess severity.
3. We develop and test a fix, keeping you informed.
4. We prepare a release and a GitHub Security Advisory.
5. We publish the fix and the advisory together.
6. You are credited by name or handle, unless you prefer otherwise.

We practise **coordinated disclosure**. We will not sit on a confirmed
vulnerability indefinitely, and we ask that you give us a reasonable window to
ship a fix before publishing.

## Safe harbour

We will not pursue or support legal action against anyone who reports a
vulnerability in good faith, follows this policy, avoids privacy violations and
service disruption, and does not access or modify data beyond what is needed to
demonstrate the issue.

## Out of scope

- Findings from automated scanners with no demonstrated impact.
- Missing hardening headers on endpoints that serve no sensitive content.
- Vulnerabilities requiring an already-compromised host or physical access.
- Denial of service through sheer volume of traffic.
- Issues in a deployment's own misconfiguration rather than in this code —
  though if our documentation encouraged that misconfiguration, that *is* in
  scope and worth reporting.

## Security posture of this project

For what the platform currently does and does not protect, see
[docs/security.md](docs/security.md). It is written to be honest about the
alpha state rather than reassuring.
