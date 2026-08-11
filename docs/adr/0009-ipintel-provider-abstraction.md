# ADR 0009 — Provider abstraction for IP intelligence

## Status

Accepted

## Context

The platform records the source IP of security-relevant events and wants context
about those addresses: is this internal or external, where does it come from,
is it a known proxy or VPN exit.

Rich answers come from commercial services (MaxMind, IPinfo, AbuseIPDB). Those
services cost money, require an API key, and require sending your traffic
metadata to a third party.

A self-hosted platform that stops working — or degrades — without a commercial
subscription is not really self-hosted. But refusing to integrate those services
would discard genuinely useful data for the users who do want them.

## Decision

We will define a **provider interface** (`ipintel.providers.IPIntelProvider`)
returning a normalised `IPLookupResult`, and ship a **`LocalProvider` that
requires no external service**.

The local provider classifies addresses offline from the address itself. It
returns **no geolocation**, because inventing one would be worse than admitting
we do not know.

External providers may be added later behind the same interface. None will ever
be required.

## Consequences

### Positive

- The platform is fully functional with no API key and no outbound network
  calls. Nothing is sent to a third party by default.
- Adding a provider means writing one class; call sites do not change, because
  they go through `get_provider()`.
- `IPLookupResult` is vendor-neutral, so a provider swap does not ripple into
  the data model or the callers.
- Testable without network access or mocking an HTTP API.

### Negative

- The default provider's answers are thin: scope and address family, nothing
  more. Users wanting geolocation must configure a provider that does not exist
  yet.
- The abstraction has exactly one implementation today, which is the classic
  shape of a premature abstraction. It is justified here because the *reason*
  for it — not depending on a commercial API — is a stated project principle,
  and because the alternative bakes a vendor's response shape into the model.

### Neutral

- `IPIntelligence.provider` records which provider produced a record, so mixed
  data can be reasoned about.

## Notes on the local classifier

`is_private` means **not globally routable**, implemented as
`not ipaddress.ip_address(ip).is_global`. This is deliberately broader than RFC
1918: loopback, link-local, reserved, multicast and the RFC 5737 / RFC 3849
documentation ranges are all reported as private, because the question the
platform is asking is "could this have reached us from the internet?".

Genuine RFC 1918 / RFC 4193 site-local space is reported separately as
`metadata["site_local"]`, since Python's `is_private` is too broad to answer
that question.

## Alternatives considered

### Hardcode MaxMind GeoIP2

Best data quality, simplest code. Rejected because it makes a commercial account
a de facto requirement and sends metadata off-site by default.

### No IP intelligence at all

Cheapest. Rejected because distinguishing internal from external traffic is
basic context for a security event, and it costs nothing to compute locally.

### Bundle a GeoLite database file

Offline geolocation with no API key. Rejected for now on licensing and
data-freshness grounds; it remains a plausible future provider implementation.

## Date

2026-08-11
