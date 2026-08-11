# ADR 0006 — Optional Go agent for observation

## Status

**Proposed** — planned for Module 7. Not implemented.

## Context

Ansible is agentless and connects on demand. That is a strength, and it leaves a
gap: between runs the platform knows nothing. It cannot tell whether a host is
alive, whether its inventory drifted, or what its current state is, without
connecting and asking.

Continuous visibility needs something resident. The risk is that adding an agent
quietly makes it mandatory, which would discard the agentless advantage that
made Ansible the right engine in the first place.

## Decision

We will offer an **optional agent written in Go**, governed by one rule:

> **Ansible changes. The agent observes.**

| | Responsibility |
|---|---|
| **Ansible** | automation, configuration, deployment, patching |
| **Agent** | heartbeat, inventory, telemetry, status |

The agent will **never** be required. Every automation capability must work with
Ansible alone, forever. If a feature can only work with the agent installed, it
is designed wrong.

## Consequences

### Positive

- Continuous heartbeat and inventory without polling every host over SSH.
- Go compiles to a single static binary with no runtime dependency — deployable
  on Linux and Windows without installing Python on the target.
- Low resource footprint, appropriate for something resident on every host.
- Users who reject agents lose visibility features and nothing else.

### Negative

- A third language in the project (Python, TypeScript, Go), with its own
  toolchain, CI and reviewer expertise.
- Agents must be built, signed, distributed and upgraded across platforms —
  a substantial ongoing cost.
- An agent is an attack surface on every managed host. Enrollment, identity and
  transport security must be designed before a line of it is written.
- Two sources of inventory truth (agent-reported and Ansible-gathered) that can
  disagree. Reconciliation is a real design problem, not a detail.

### Neutral

- Requires a dedicated agent API on the platform, with its own authentication
  model distinct from user sessions.

## Alternatives considered

### No agent, Ansible polling only

Simplest, and preserves agentless purity completely. Rejected because polling
thousands of hosts over SSH for a heartbeat is expensive and slow, and gives
stale data between polls.

### A mandatory agent

Would make inventory and telemetry far simpler and more reliable. Rejected
outright: it contradicts [ADR 0005](0005-ansible-execution-engine.md), removes
Ansible's agentless advantage, and makes adoption dramatically harder.

### Reusing an existing agent (osquery, Telegraf, node_exporter)

Mature and battle-tested. Genuinely worth reconsidering at implementation time
— possibly as an integration rather than a replacement. Not selected now
because enrollment and platform identity are the parts we most need to control.

### Python agent

Shares the platform's language. Rejected because it requires a Python runtime on
every managed host, which is exactly the imposition the agentless model avoids.

## Date

2026-08-11
