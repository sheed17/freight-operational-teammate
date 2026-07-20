# ADR-017 — Tenant and Integration Lifecycle, and the Web Control Plane

**Status:** ✅ **FINAL — U-REBASELINE-1 (founder-authorized, 2026-07-20).**
**Preserves:** tenant isolation (P2, AC-SEC-001); Slack/email/SMS as operator surfaces;
"the accountable human stays in the operating seat."

---

## 1. Decision — lifecycle

**Tenant lifecycle** is a first-class governed sequence: prospect → pilot → supervised
production → general production → offboarded. Each transition is an explicit, recorded decision
with its evidence (pilot success criteria, supervision results). **Offboarding is a product
capability, not an afterthought**: data export, credential destruction (ADR-014 §3), retention
and deletion execution, and a verifiable end state.

**Integration lifecycle** per tenant per external system: proposed → authorized (customer
authorization recorded) → connected → healthy/degraded (continuously measured) → suspended →
revoked. Connection health is observable; a degraded integration raises operational work, not
silent staleness.

## 2. Decision — the web control plane

Slack, email and SMS remain important operator surfaces, but **they cannot be the only
administration and oversight interface.** A **thin web control plane** exists to configure,
supervise, understand and govern the work Neyma carries across operational channels.

It supports: open Work Items · exception queues · approval packets · operational history ·
effect history · unknown outcomes · tenant configuration · users and roles · integration
onboarding · connection health · credential lifecycle · policy configuration · approval limits ·
brake status · audit search · metrics and operational value · pilot administration · support
diagnostics · customer onboarding and offboarding.

**The product is not dashboard-first.** The control plane governs; the work continues to meet
people in the channels they already use. A teammate you have to keep visiting hasn't done its
job — the control plane is where you *check on* the teammate, not where the work lives.

## 3. Consequences

- P11 carries the control plane and onboarding implementation; P12 operates them under
  supervision.
- The brake (ADR-011) gains its administrative surface here — engageable from the control plane,
  never dependent on it (the brake must work when the web tier is down).
- Nothing here is implemented by U-REBASELINE-1.
