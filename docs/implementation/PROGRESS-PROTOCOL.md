# PROGRESS PROTOCOL — The Founder Build-Status System

> **CANONICAL — IMPLEMENTATION_CONTROL.** Created by U-REBASELINE-1 (founder-authorized,
> 2026-07-20). This protocol is **part of the project control system, not optional conversational
> behavior.** Every future Claude Code session must follow it.
>
> **It does not compete with [`CURRENT.md`](CURRENT.md).** `CURRENT.md` remains the single
> short-form status authority for commit/tree/suite and phase state; this protocol adds the
> **founder-facing progress view** — mechanically-derived percentages, readiness tiers and a
> plain-language expectation — computed from evidence, never estimated.

---

## 1. Why this exists

The founder needs to understand a multi-phase build **without reading code, test logs or
implementation detail** — and needs the numbers to be honest, so a high "foundational" percentage
can never be mistaken for a usable product. This protocol makes progress **evidence-based and
mechanical**: the finalizer computes the percentages and refuses to record inflated ones.

## 2. The standard report — `NEYMA BUILD STATUS`

Every meaningful implementation unit, correction unit, review, adjudication or phase completion
ends by printing this block. The percentages are **read from
[`BUILD-STATUS.yaml`](BUILD-STATUS.yaml)**, which the finalizer derives — they are never typed by
hand.

```
NEYMA BUILD STATUS

CLI switch readiness: __%
Overall implementation program: __%
Current phase: <phase> — __%
User-visible product maturity: __%
Production readiness: __%

Current readiness tier:
<one of the seven tiers in §5>

Active work unit:
<unit identifier and title>

Completed in this unit:
• ...
Verified evidence:
• ...
What Neyma can do now:
• ...
What Neyma still cannot do:
• ...
Why the current work matters:
• ...
Remaining in the current phase:
• ...
Blockers:
• ...
Expected founder experience right now:
<plain language — why the product may or may not yet look usable>
Next approved unit:
<identifier and title>
Verdict:
<ON TRACK | AT RISK | BLOCKED | REQUIRES FOUNDER DECISION>
```

## 3. Percentage integrity — the rules the finalizer enforces

Percentages are **evidence-based only**. They may **never** be estimated from time spent, tokens,
lines of code, changed files, commits, how hard the work felt, conversational confidence, or
unverified implementation claims.

**Current-phase completion** is computed from the phase's **approved weighted acceptance contract**
(the criterion weights in [`PROGRAM-WEIGHTS.yaml`](PROGRAM-WEIGHTS.yaml), which total exactly 100).
A criterion contributes to progress **only when its required evidence exists**:

| Criterion state | Contribution |
|---|---|
| `PENDING` | **0%** |
| `IN_PROGRESS` | **0%** — unless the contract defines independently verifiable partial milestones |
| `PASS` | its **full approved weight** |
| `FAIL` | **0%** |
| `BLOCKED` | **0%** |

**Code written is not completion.** No partial credit is awarded merely because code exists.

**Weights are frozen once a phase begins.** A material weight change requires an explicit
explanation, repository evidence, founder approval, and a committed acceptance-contract revision —
silent re-weighting to improve a number is forbidden and the finalizer rejects an unsupported
percentage increase.

## 4. Overall program & the two other headline numbers

**Overall implementation program** = Σ over the implementation phases of
`(program weight ÷ 100) × verified phase completion %`, using the **program weights** in
`PROGRAM-WEIGHTS.yaml` (which total exactly 100). Weights are **not** equal — they reflect
implementation scope, safety importance, production complexity, user value, integration
complexity, validation requirements, and rollout/operational requirements.

**Completed historical foundation work (P0–P2 and the control units) is reported separately** from
the post-rebaseline implementation program. **Architecture documentation is never represented as
implemented product functionality.**

**User-visible product maturity** measures what a freight owner or daily operator can actually
use. It does **not** rise because backend infrastructure exists. It is derived from the
evidence-gated `user_visible_checklist` in `PROGRAM-WEIGHTS.yaml` (onboarding, system mapping, load
ingestion, work-item visibility, sourcing, documents, communications, approvals, exceptions,
sync, accounting prep, operator surfaces, owner reporting, end-to-end workflows). The report must
state plainly when foundational progress is high but user-visible maturity is low.

**Production readiness** measures whether Neyma can safely and continuously serve real customers. It
is derived from the evidence-gated `production_readiness_checklist` (production DB, migrations,
object storage, workers/scheduling, queues/inbox/outbox, tenant isolation, auth, secrets,
credential lifecycle, email/SMS delivery, environments, CI/CD, monitoring, backup/restore,
disaster recovery, incident response, provider-outage handling, security testing, load/concurrency
testing, support tooling, onboarding/offboarding, retention/deletion, cost/model controls,
shadow-pilot evidence, supervised-production evidence, rollback exercises). **Local tests passing
never produce a high production-readiness percentage.**

## 5. Readiness tiers (canonical — supersedes the ADR-016 draft vocabulary)

Exactly these seven tiers, in order. A tier is not skipped without explicit evidence and
adjudication.

| Tier | Meaning |
|---|---|
| **SPECIFIED** | The behavior and acceptance contract exist; the capability is not implemented. |
| **LOCALLY IMPLEMENTED** | Works in a local dev environment with required unit/component tests. |
| **INTEGRATION TESTED** | Passed tests against realistic adapters, provider sandboxes or controlled test infrastructure. |
| **STAGING READY** | Deployed in a production-like staging environment with migrations, secrets, monitoring and operational controls. |
| **SHADOW-PILOT READY** | Can observe real customer work and generate proposed outcomes with **no** consequential external effects. |
| **SUPERVISED-PRODUCTION READY** | Can serve a real customer while consequential actions stay reviewed, bounded and reversible. |
| **GENERALLY PRODUCTION READY** | Sufficient reliability, security, observability, recovery, support and customer evidence for its approved production scope. |

Mapping from the ADR-016 draft: `SPECIFICATION_ONLY`→SPECIFIED, `LOCALLY_IMPLEMENTED`→LOCALLY
IMPLEMENTED (INTEGRATION TESTED inserted), `STAGING_READY`→STAGING READY, `PILOT_READY`→SHADOW-PILOT
READY, `SUPERVISED_PRODUCTION_READY`→SUPERVISED-PRODUCTION READY,
`GENERALLY_PRODUCTION_READY`→GENERALLY PRODUCTION READY.

## 6. Per-phase founder expectations

Each phase in `PROGRAM-WEIGHTS.yaml` carries a plain-language `founder_expectation`: what becomes
possible, what stays impossible, what should be visible, what may still look incomplete, why the
phase is necessary, what drift/failure would look like, and what evidence proves it on track. The
guidance by phase family:

- **Safety phases (P3–P5):** the product may have no usable interface yet; progress shows in
  authorization, idempotency, concurrency safety, verified effect handling and durable execution.
- **Domain/model phases (P6–P9):** the system understands freight state and obligations, but may
  still lack production integrations and customer-facing polish.
- **Platform phase (P11):** tenant onboarding, PostgreSQL, object storage, workers, credentials,
  communications and control surfaces become visible.
- **Workflow phases (P10, P12):** a real operational outcome runs end-to-end in shadow, then under
  supervision.
- **Production phases (P11–P14):** deployment, monitoring, recovery, support and real pilot
  evidence become the primary proof of progress.

The repository helps the founder **stay patient during foundational phases without hiding real
delays or architectural drift.**

## 7. Canonical progress artifacts

| Artifact | Role |
|---|---|
| [`PROGRESS-PROTOCOL.md`](PROGRESS-PROTOCOL.md) | this protocol |
| [`PROGRAM-WEIGHTS.yaml`](PROGRAM-WEIGHTS.yaml) | phase program weights (Σ=100), the weighted acceptance template (Σ=100), and the CLI-switch / production / user-visible checklists |
| [`BUILD-STATUS.yaml`](BUILD-STATUS.yaml) | the finalizer-derived snapshot: HEAD, tree, active phase/unit, single READY unit, all five percentages, tier, criteria, blockers, last test evidence, finalizer + clean-clone results, independent-review status, last updated commit |

These do **not** create competing status authorities. `BUILD-STATUS.yaml` is **derived and
finalizer-written** (like `CURRENT.md`'s status block); its `content_commit`/`content_tree` follow
the two-commit convention and must equal `CURRENT.md`'s.

## 8. What the finalizer rejects

[`scripts/finalize_status.py`](../../scripts/finalize_status.py), via
[`scripts/progress_status.py`](../../scripts/progress_status.py), refuses to record status when:

- any percentage is outside 0–100;
- phase program weights do not total 100;
- acceptance-template weights do not total 100;
- a reported percentage exceeds what the evidence supports (an unsupported increase);
- a phase is at 100% before its required independent review and adjudication;
- a production-ready claim lacks the required evidence;
- the READY unit is inconsistent with the registry;
- a progress file references the wrong HEAD or tree;
- a user-visible claim is unsupported by implemented capabilities;
- a progress file is stale after a completed work unit.

## 9. Session-end requirement

Every future coding session ends by: (1) running the required tests; (2) updating the canonical
progress artifacts; (3) reporting evidence honestly; (4) running the canonical finalizer;
(5) committing implementation and status truthfully; (6) printing the complete `NEYMA BUILD STATUS`
block; (7) **stopping at the next approved control boundary.** A session must **never** roll into
the next implementation unit merely because the current one finished — the next unit must be
`READY` in the canonical registry.
