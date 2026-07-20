# ADR-016 — Production Deployment Topology

**Status:** ✅ **FINAL — U-REBASELINE-1 (founder-authorized, 2026-07-20).**
**Supersedes:** any implicit assumption that the local single-process, SQLite-backed engine is
the production shape.
**Preserves:** the modular monolith (target-system-specification); ships-dark discipline;
"code exists" never equals "production ready."

---

## 1. Decision — shape

**A modular monolith on managed infrastructure.** No Kubernetes, microservice sprawl or
distributed-systems apparatus adopted for sophistication's sake; components split only when an
operational fact (isolation, blast radius, scaling) forces it. The browser-automation workers
are the first such fact: they run **isolated** from the core service.

**PostgreSQL is the production transactional store.** SQLite remains for local development and
deterministic testing only — it is **not** the assumed multi-tenant production database. The
persistence layer keeps a single schema/migration discipline across both.

## 2. Required production architecture

| Concern | Requirement |
|---|---|
| **Services** | public API + webhook service · internal operational control plane (ADR-017 surfaces) · background worker processes · communications workers · **isolated** browser-automation workers |
| **Persistence** | PostgreSQL (transactional, tenant-first keys) · schema migrations · transactional outbox and durable inbox · durable timers and scheduler |
| **Evidence** | S3-compatible object storage · content-addressed evidence · malware and attachment handling |
| **Identity & access** | managed secrets · tenant authentication · user identity and roles · tenant authorization · approval and policy administration |
| **Operations** | integration connection health · human-review and exception interfaces · logs, traces, metrics and alerts · feature flags · model routing, budgets and fallbacks · rate limits and backpressure · dead-letter and quarantine handling · idempotency and unknown-outcome resolution |
| **Environments** | environment separation · development, staging and production · customer sandbox and pilot posture |
| **Resilience** | backups · point-in-time database recovery · object-store recovery · disaster recovery · incident response |
| **Lifecycle** | customer onboarding and offboarding (ADR-017) · retention and deletion policies · cost and usage controls |

## 3. Readiness vocabulary

> ⚠️ **Reconciled by U-REBASELINE-1:** the **canonical** readiness tiers are the seven in
> [`PROGRESS-PROTOCOL.md §5`](../../implementation/PROGRESS-PROTOCOL.md) — SPECIFIED · LOCALLY
> IMPLEMENTED · INTEGRATION TESTED · STAGING READY · SHADOW-PILOT READY · SUPERVISED-PRODUCTION
> READY · GENERALLY PRODUCTION READY. The six-tier draft below is superseded; it maps 1:1 into the
> canonical seven (INTEGRATION TESTED was inserted; `SPECIFICATION_ONLY`→SPECIFIED,
> `PILOT_READY`→SHADOW-PILOT READY). IMPLEMENTATION-SURFACE may still record the underscore
> spellings; `scripts/progress_status.py` aliases them to the canonical tiers.

Draft (superseded): `SPECIFICATION_ONLY` → `LOCALLY_IMPLEMENTED` → `STAGING_READY` → `PILOT_READY`
→ `SUPERVISED_PRODUCTION_READY` → `GENERALLY_PRODUCTION_READY`.

**"Code exists" means `LOCALLY_IMPLEMENTED`, nothing more.** Promotion between levels requires
the evidence named in the phase acceptance contracts (deployed where, verified how, operated by
whom). The registry and IMPLEMENTATION-SURFACE record the level per capability.

## 4. Consequences

- The revised P3–P14 program (implementation-roadmap, registry) distributes these obligations:
  P5 carries PostgreSQL + outbox/inbox/timers; P11 carries deployment, environments, onboarding
  and the control plane; P12 carries supervised production operation.
- Nothing here is implemented by U-REBASELINE-1. As of this ADR, **every** item in §2 is
  `SPECIFICATION_ONLY` except where IMPLEMENTATION-SURFACE already records a local
  implementation (which is `LOCALLY_IMPLEMENTED`, never higher).
