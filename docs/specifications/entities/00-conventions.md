# Foundational Entity Specifications — Conventions

**Layer:** Specification. **Derived from (frozen, authoritative):** the canonical Target System Architecture Specification (`7ae1564`), ADR-001…011 (incl. A1–A4), the Semantic Model, the Operating Model, the Engineering Principles.
**Rule:** ### **These specifications DERIVE from the architecture. They invent nothing.** No new primitive, state, event, provenance class, gate decision, verification outcome, evidence condition, or effect path. Where one appears necessary, the file **stops and names the missing architectural concept** — it does not fill the gap.

---

## How to read these files

Every file follows the **same 45-point structure** (the numbered headings). Answers are terse by design: two senior engineers implementing independently must converge, so each answer is a **constraint**, not a discussion.

**Cross-cutting conventions that apply to EVERY entity — stated once here, referenced as `[C-n]`:**

| # | Convention |
|---|---|
| **C-1** | **`tenant_id` is `NOT NULL` and is the FIRST column of every primary key and every unique index** (spec §7, M-8). Cross-tenant access is rejected before any handler; a breach is Sev-0 and engages a GLOBAL brake. |
| **C-2** | **Every state change + its emitted events are written in ONE transaction** (the transactional outbox — spec §11.4, M-23). "Emitted event" below always means "into the outbox, atomically with the transition." |
| **C-3** | **Every transition is keyed by the triggering `event_id` in the consumer inbox** `(consumer_id, tenant_id, event_id)`. A redelivered trigger is a **no-op** (M-24). This is the universal idempotency mechanism; individual files note only *additional* idempotency. |
| **C-4** | **An event not in the transition table for the current state is an ILLEGAL TRANSITION**: it raises, persists no state change, and emits `IllegalTransitionAttempted` (audit **and** security) (M-28). |
| **C-5** | **Replay reconstructs state by applying events through the transition tables. It can NEVER cause an effect** — it cannot construct a `CheckpointPassed`, therefore cannot mint an Effect Grant (M-27). Replaying any entity below produces zero grants and zero `EffectAttempted`. |
| **C-6** | **A model may never author, evaluate, confirm, resolve, or activate any native record below.** Its only output is a `ProposedIntent` — inert data (M-65). |
| **C-7** | **`provenance_class` ∈ {`SYSTEM_IMPORTED`, `OWNER_ASSERTED`, `LINKER_INFERRED`, `MODEL_EXTRACTED`, `MODEL_INFERRED`, `RECONCILED`}**, runtime-assigned (R-P1), weakened-never-strengthened (R-P2), `OWNER_ASSERTED` never machine-recomputed (R-P3). `MODEL_INFERRED` never gates a consequential action, at any confidence (M-13…M-16). |
| **C-8** | **Audit is append-only.** No `UPDATE`, no `DELETE` on `audit_events`, `observations`, `evidence`, `provenance_records`, `outbox`, or any closure/superseded row (spec §25, S8). |
| **C-9** | **Retention is permanent** for observations, evidence, provenance, events, grants, checkpoints, approvals (with full canonical payloads), and audit events (spec §16.2). "Deletion policy" below is therefore almost always **"none."** |
| **C-10** | **Version columns are monotonic per record; a mutation with a stale expected version fails (optimistic concurrency)** (spec §16.1 / ADR-009 §5). Applies to every native mutable entity. |

## Canonical enum registry *(the ONLY legal values — any file using another value is defective)*

- **Gate decisions:** `HUMAN_APPROVAL_REQUIRED` · `AUTONOMOUS_WITHIN_CAPS` · `PERMANENT_HUMAN_ASSERTION_REQUIRED` · `FORBIDDEN` *(NOT NULL — spec §20.1)*
- **Provenance classes:** the six of C-7.
- **Evidence conditions:** `absent` · `unknown` · `consistent` · `conflicting` · `stale` *(spec §6.3)*
- **Verification outcomes:** `VERIFIED_SUCCESS` · `VERIFIED_FAILURE` · `UNKNOWN_OUTCOME` · `VERIFICATION_DEFERRED` · `VERIFICATION_IMPOSSIBLE` · `AWAITING_OBSERVATION` · `OBSERVATION_UNAVAILABLE` · `OBSERVATION_CONFLICTING` *(spec §26.1)*
- **`unknown_reason`** *(on `UNKNOWN_OUTCOME`)*: `UNKNOWN_OUTCOME` · `OBSERVATION_UNAVAILABLE` · `OBSERVATION_CONFLICTING`

## Authority classes *(point 6)*

- **projected** — derived from an authoritative external system; rebuildable; never optimistically updated.
- **Neyma-native** — authored by Neyma or an authenticated human; event-reconstructable; versioned; correctable.
- **immutable record** — written once, never transitions, never edited (e.g. Observation content, Evidence, Checkpoint Witness, Audit Event).
- **materialized projection** — the typed view built from observations + claims.

## SPECIFICATION BLOCKED

If a file cannot proceed without a decision that belongs **above** this layer, it prints:

> ### 🚫 **SPECIFICATION BLOCKED — <the exact missing higher-level decision>**

and stops that section. **No file below is blocked** (verified against the 13 canonical lifecycle tables + the 3 immutable records). The `NEEDS VALIDATION` items (point 45) are **not** blocks — each has a fail-closed default.
