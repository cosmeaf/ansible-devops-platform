# ADR 0005 — Ansible as the execution engine

## Status

Accepted (principle) — runner integration planned for Module 4.

## Context

The platform automates infrastructure. It could define its own automation
format, or it could drive an existing engine.

Every platform that invents its own format asks users to rewrite what they
already have, and to accept that leaving means rewriting it again.

## Decision

We will use **Ansible as the execution engine**, and the platform will **not**
replace it.

Concretely, and permanently:

- playbooks stay standard Ansible YAML;
- inventories stay compatible with standard Ansible inventories;
- roles stay standard Ansible roles;
- there is **no proprietary automation format**.

The platform supplies what Ansible does not: multi-user access control, audit,
scheduling, history, a shared inventory and an API.

## Consequences

### Positive

- Existing Ansible content works without modification. Adoption costs a `git
  clone`, not a migration project.
- No lock-in: if you stop using this platform, your playbooks still run under
  `ansible-playbook`. This is a feature, stated deliberately.
- The enormous Ansible Galaxy ecosystem is available unchanged.
- Contributors bring Ansible knowledge with them.
- Agentless by default — target hosts need SSH or WinRM, nothing installed.

### Negative

- The platform inherits Ansible's constraints: its performance characteristics,
  its error messages, its YAML.
- Breaking changes in Ansible become our compatibility problem.
- We cannot offer capabilities Ansible does not have without either extending
  Ansible or breaking the no-proprietary-format promise. We will not break it.

### Neutral

- Ansible Runner becomes a dependency of the execution module.
- Execution isolation (containers per run) is a platform concern, not Ansible's.

## Alternatives considered

### A proprietary automation format

Would allow exactly the semantics we want. Rejected because it is the single
most effective way to trap users, and because it discards the ecosystem that
makes Ansible worth building on.

### Supporting several engines (Ansible, Salt, Puppet, Chef)

Broader appeal. Rejected as premature and as a quality trap: an abstraction over
four engines serves none of them well, and the project has not yet served one.

### Direct SSH execution without Ansible

Fewer dependencies. Rejected because it means reimplementing idempotency,
modules, facts, inventory and error handling — badly, and forever.

## Date

2026-08-11
