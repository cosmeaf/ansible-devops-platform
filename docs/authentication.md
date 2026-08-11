# Authentication

What exists today, stated precisely, and what is planned.

> Django having a `User` model does not mean this platform has an
> authentication system. Most of what a platform needs here is **not yet
> built**, and this page says so rather than implying otherwise.

---

## What works today

### Session authentication

Django's session authentication, backed by the database.

- `POST /accounts/login/` — sign in
- `POST /accounts/logout/` — sign out
- `/admin/` — Django Admin, staff only

Sessions are eight hours by default (`SESSION_COOKIE_AGE`) and expire when the
browser closes. Cookies are `HttpOnly`, `SameSite=Lax`, and `Secure` whenever
`DEBUG` is off.

### Password policy

Enforced by Django's validators:

- at least 12 characters;
- not too similar to the username or email;
- not in the common-password list;
- not entirely numeric.

Hashed with PBKDF2-SHA256. Never stored or logged in clear — there is a test
asserting exactly that.

### API authentication

DRF is configured with `SessionAuthentication` and `IsAuthenticated` as
defaults. An endpoint that should be public opts out explicitly; the health
endpoint is the only one that does.

Requests are throttled: 60/min anonymous, 1000/hour authenticated.

### Authorisation

Django's model permissions and the `is_staff` / `is_superuser` flags. That is
all — see below.

---

## What is NOT implemented

| Capability | Status | Planned |
|---|---|---|
| **RBAC** | Not implemented. No `Role` model, no per-resource permissions. Access is staff/superuser only. | 0.2.0 |
| **Password reset by email** | Django's URLs are routed, but **no email backend is configured**, so no message is ever sent. Reset must be done in the admin. | 0.2.0 |
| **Forced password change on first login** | Not implemented. The generated admin password remains valid until changed by hand. | 0.2.0 |
| **MFA / TOTP** | Not implemented. | Not scheduled |
| **Account lockout** | Not implemented. `SecurityEvent` can record a failed login; nothing acts on it. Brute-force defence is rate limiting only. | 0.2.0 |
| **Token / JWT authentication** | Not implemented. Needed for the Next.js module and for API clients. | 0.2.0 |
| **SSO (OIDC, SAML, LDAP)** | Not implemented. | Not scheduled |
| **Session invalidation on password change** | Not implemented. Existing sessions survive. | 0.2.0 |
| **Login audit events** | The model supports `LOGIN` / `LOGOUT` actions; **nothing writes them yet**. | 0.2.0 |

The last one is worth restating: the audit *model* is ready for login events,
but authentication does not currently emit them. Do not assume sign-ins are
being recorded.

---

## Planned RBAC design

Sketch only, not implemented. Recorded so the direction is visible:

```text
User → Role → Permissions → Resources
```

Anticipated roles: Administrator, Operator, Developer, Auditor (read-only),
Viewer. Permissions scoped per environment and per asset group.

This will go through an ADR before implementation, per
[GOVERNANCE.md](../GOVERNANCE.md).

---

## Practical guidance now

Given the gaps above:

1. **Change the generated admin password immediately.**
2. Create individual accounts — never share one. Without per-user accounts the
   audit trail cannot attribute anything.
3. Grant `is_staff` sparingly; there is no finer-grained control yet.
4. Do not expose the platform to the internet. Rate limiting is not a substitute
   for lockout and MFA.
5. Put it behind a VPN or an authenticating reverse proxy if you need stronger
   access control today.

## Related

- [security.md](security.md) — the full security posture
- [audit.md](audit.md) — the audit trail
- [ROADMAP.md](../ROADMAP.md) — when the gaps close
