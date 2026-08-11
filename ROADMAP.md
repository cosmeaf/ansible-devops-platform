# Roadmap

What is built, what comes next, and in what order.

**No dates.** This is a volunteer-maintained project in early development;
publishing dates we cannot commit to would be worse than publishing none.
Order is a plan, not a promise — it will change as we learn.

Milestones are conceptual releases, each roughly a module.

---

## 0.1.0 — Core Platform ← current

**Status: implemented, pending release validation.**

- [x] Django 5 + Django REST Framework
- [x] PostgreSQL as primary database
- [x] Redis broker and cache
- [x] Celery worker and Celery Beat
- [x] `authentication` — session authentication, role-based access control
- [x] Platform management interface, independent of Django Admin
- [x] `commun` — shared abstract base models
- [x] `security` — security event model
- [x] `ipintel` — provider abstraction, offline classifier
- [x] `audit` — audit trail, request-ID correlation, secret redaction
- [x] `settings_platform` — database-backed operational settings
- [x] `GET /api/v1/health/`
- [x] Docker Compose deployment, private service network
- [x] Idempotent bootstrap with automatic secret generation
- [x] Test suite against real PostgreSQL
- [x] Open-source foundation: licence, governance, CI/CD, documentation

## 0.2.0 — Web Foundation

The `ansible-web` module. A backend with no interface is only half a product.

- [ ] Next.js + TypeScript application
- [ ] Authentication UI against the platform API
- [ ] Dashboard and navigation
- [ ] Typed API client
- [ ] RBAC-aware interface
- [ ] Token or session strategy for a separate-origin frontend

## 0.3.0 — Infrastructure

Before you can automate infrastructure, the platform has to know it exists.

- [ ] `InfrastructureAsset` base model
- [ ] `Server` (Linux, Windows)
- [ ] Environments (production, staging, development)
- [ ] Groups and tagging
- [ ] Credential storage with envelope encryption
- [ ] Connection testing

## 0.4.0 — Ansible Automation

The point of the whole project. Ansible remains the engine; nothing here
becomes a proprietary format.

- [x] Inventory generation, compatible with standard Ansible inventories
- [ ] Playbook management (standard Ansible YAML)
- [ ] Role management
- [ ] Variable management
- [ ] Monaco-based editor
- [ ] Ansible Runner integration
- [ ] Check mode (dry run)
- [ ] Execution

## 0.5.0 — Operations

- [ ] Job model and lifecycle
- [ ] Scheduler
- [ ] WebSocket transport
- [ ] Live execution logs
- [ ] Run history and diffing
- [ ] Notifications

## 0.6.0 — Git Integration

- [ ] Playbook repositories backed by Git
- [ ] Diff view
- [ ] Change history
- [ ] Controlled rollback

## 0.7.0 — Go Agent (optional)

**The agent will never be required.** The rule is:

> **Ansible changes. The agent observes.**

Ansible handles automation, configuration, deployment and patching. The agent
handles heartbeat, inventory, telemetry and status. You can use the platform
with Ansible alone, forever.

- [ ] Linux agent
- [ ] Windows agent
- [ ] Enrollment and identity
- [ ] Heartbeat
- [ ] Inventory collection

## 0.8.x and beyond — Infrastructure breadth

Today the model is a server. It will not stay that way. Planned
`InfrastructureAsset` types include network devices, hypervisors, virtual
machines, container hosts, Kubernetes clusters, databases, storage and cloud
resources.

- [ ] Network device automation
- [ ] VMware
- [ ] Docker hosts
- [ ] Kubernetes
- [ ] Cloud providers
- [ ] Databases
- [ ] Storage
- [ ] AIX

## 1.0.0 — Stable Core Platform

`1.0.0` means a stable, documented API, a supported upgrade path, and a
security process that has been exercised in practice. It is not a marketing
milestone and will not be declared early.

---

## Out of scope

Permanently, by design:

- replacing Ansible with a proprietary automation format;
- vendor lock-in;
- a hosted SaaS offering;
- requiring the Go agent.

## Influencing this roadmap

Open a Discussion under **Ideas**. Scope changes go through an
[ADR](docs/adr/) — see [GOVERNANCE.md](GOVERNANCE.md).
