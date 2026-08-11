# ADR 0007 — Apache License 2.0

## Status

Accepted

## Context

The project is open source and wants contributors, including from companies.
The licence choice determines who can adopt it, who can contribute, and what
protection either side has.

Three things matter here: corporate adoption should not require a legal review
that ends in "no"; contributors should be protected from patent claims; and the
project should not restrict commercial use, because restricting it would rule
out most of the organisations that manage infrastructure at the scale this
targets.

## Decision

We will license the project under the **Apache License 2.0**, using the official
text verbatim in `LICENSE`, with a `NOTICE` file.

## Consequences

### Positive

- Permits use, modification, distribution and commercial use, so companies can
  adopt it without a licensing conversation.
- **Includes an express patent grant** — contributors grant patent rights for
  their contributions, and the licence terminates for anyone who initiates
  patent litigation over the work. Permissive licences without this clause leave
  both sides exposed.
- Requires attribution and a statement of changes, so provenance is preserved.
- Explicit trademark and warranty disclaimers.
- Widely recognised; corporate legal teams have pre-approved it.
- Compatible with GPLv3, so GPLv3 projects can incorporate this work.

### Negative

- Being permissive, it allows a proprietary derivative: someone may take this,
  extend it and never publish the changes. That is an accepted cost of the
  adoption we want.
- Slightly more ceremony than MIT — a `NOTICE` file and change statements.

### Neutral

- Contributors license their contributions under the same terms.
- Every source file may carry a licence header, though the repository-level
  `LICENSE` is what governs.

## Alternatives considered

### MIT

Shorter and simpler, and very widely used. Rejected because it has **no patent
grant**. For an infrastructure automation platform that companies would run in
production, that omission is a real risk for contributors and adopters alike.

### GPLv3

Would guarantee that improvements come back to the project. Rejected because its
copyleft obligations make many companies refuse to adopt or contribute, and
because network-adjacent deployment scenarios raise questions we do not want
users to have to answer.

### AGPLv3

Closes the SaaS loophole GPLv3 leaves open. Rejected for the same adoption
reason, more strongly — many organisations forbid AGPL software outright, which
would exclude much of the intended audience.

### BSD-3-Clause

Essentially equivalent to MIT for our purposes, with the same missing patent
grant. Rejected on the same ground.

## Date

2026-08-11
