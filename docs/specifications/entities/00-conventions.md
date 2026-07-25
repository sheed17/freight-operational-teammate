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

---

# CLARIFICATION ADDENDUM (Wave 4.5)

*Resolves specification defects SD-1, SD-5, SD-8, SD-9, SD-11, and hidden assumption HA-1 from `specification-constitution-review.md`. **No new primitive, state, event, or enum is introduced.** Each rule is already implied by the frozen architecture; it is merely made precise so two engineers cannot diverge.*

### K-1 — `decision_ref` is a resolvable reference, never free text *(SD-1)*

> **`decision_ref` MUST reference one of exactly two things, and MUST resolve:**
> **(a) an `audit_events` row of a human-decision type** — `HumanDecided`, `HumanResolved`, `ApprovalGranted`, `RealityEstablished`, `CompensationApproved`, `BrakeReleased` — recording an **authenticated human** actor; **or**
> **(b) a `rule_id`** of an `ACTIVE` Rule (a registered deterministic decision procedure).

**Deterministic rule.** A transition that requires a `decision_ref` MUST reject a value that does not resolve to (a) or (b). A string that references nothing is **not** a `decision_ref` and the transition is illegal `[C-4]`. *(This closes the "closed with the string `done`" hole: the CHECK is not "non-null" but "resolves to an authenticated human decision event or an active rule id".)*
**Why already implied.** ADR-008 defines closure/resolution as requiring *"a human decision id or a deterministic rule id."* Audit Events are the append-only record of human decisions (`17`); Rules carry `rule_id` (`15`). This names the two referents the architecture already has — **no new entity.**
**Enforcement.** A referential-integrity check: `decision_ref` FK → `audit_events(tenant_id, event_id)` **or** `rules(tenant_id, rule_id) WHERE state='ACTIVE'` (a polymorphic reference discriminated by a `decision_ref_kind ∈ {AUDIT_EVENT, RULE}` column). **Test:** `test_decision_ref_must_resolve_to_a_human_decision_event_or_active_rule`.

### K-2 — The three "about" references are distinct, with fixed meanings *(SD-5)*

> | Name | Means | Appears on | Points to |
> |---|---|---|---|
> | **`target_resource_id`** | the **external resource** an effect acts upon | Pipeline Instance, Effect Grant, Checkpoint Witness | an identifier **in an authoritative system** (e.g. `load:4471` in TMS-A) |
> | **`entity_ref`** | the **projected/native business entity** a record concerns | Work Item, Conflict, Exception; **on Observation the same-semantics field is named `bound_entity_ref`** (the entity a bound observation resolved to) | a **canonical projection** row (a `Load`, `Customer Invoice`, …) |
> | **`subject_ref`** | the **artifact/observation** being bound or awaited | Identity Binding Claim, Expectation | an `observation_id` or `evidence_id` |

**Deterministic rule.** These are **three distinct references and MUST NOT be conflated.** An Identity Binding Claim carries **both** `subject_ref` (the artifact — one end) **and** `entity_ref` (the entity it is bound to — the other end); the claim IS the asserted relation between them. A Work Item's `entity_ref` and its Pipeline Instance's `target_resource_id` are **related but not equal**: `entity_ref` is the *projection*; `target_resource_id` is the *external handle* the projection was built from. A join between them goes **through the projection's provenance** (`entity_ref` → its source observations → their `source_system`+`external_id` = the `target_resource_id`), never by string equality.
**Why already implied.** Spec §6 distinguishes projected state, native records, external resources, and artifacts as different kinds of thing (§6.1, eight kinds). These three references are just the identifiers of three of those kinds. **No new concept.**

### K-3 — Replay is read-only, sandboxed, and emits nothing to real consumers *(SD-8, extends `[C-5]`)*

> **`[C-5]` addendum:** replay reconstructs state **into an isolated sandbox**. It **emits ZERO events to the real outbox/consumers, writes ZERO real projections (only sandbox projections for the rebuild-divergence comparison), mints ZERO Effect Grants, and produces ZERO External Effects.** *Wherever an entity file says "replay reconstructs state," read: "in a sandbox, with no real-world or real-consumer side effect."*

**Deterministic rule.** A replay run has no write access to the real outbox, the real `effect_grants` ledger, or real projections; its only output is the sandbox projection compared nightly to the live one (spec §25 — divergence is a Sev-0 that auto-engages a brake).
**Why already implied.** Spec §25 already states *"replay runs against a projection sandbox and cannot construct a witness."* This propagates that single statement uniformly to every entity file. **No new concept.**

### K-4 — The money-in-memory prohibition is scoped to the knowledge base *(SD-9)*

> *"Memory MUST NEVER store a money value"* (spec §22) governs the **knowledge/organizational-memory store only.** It does **NOT** forbid `exposure` (or any money field) on **operational records** (Work Item, Exception, Compensation, Approval, External Effect), **provided the value is sourced from a live or verified authoritative read — never recalled from memory.**

**Deterministic rule.** A money field on an operational record MUST carry the `observation_id` (or effect/approval) it was read from; a money field MUST NOT be populated from a knowledge-base recall. **Why already implied.** Spec §22 places the prohibition under "Knowledge, Context, Rules & Learning"; the money fence (§21) requires amounts to be runtime-read, not remembered. **No new concept.**

### K-5 — An Action Class is a registered descriptor with declared properties *(SD-11)*

> Each **action class** is registered once, and its registration **declares** (additively, so a new class changes no existing semantics): **`gate_decision`** (NOT NULL — the system fails to start otherwise), **`verification_mode`** (`READBACK_VERIFIABLE` · `RECEIPT_VERIFIABLE` · `UNVERIFIABLE`), **`money_direction`** (`IN` · `OUT` · `n/a`), and **`occurrence_key_rule`** (how a legitimate repeat is distinguished — §19.7).

**Deterministic rule.** `occurrence_key` derivation is a **property of the action class**, resolved from its registration — **never a central switch statement.** Adding an action class is purely additive: register the descriptor. **Why already implied.** Spec §19.7 already gives `occurrence_key` per action class by example; §20.1 already makes `gate_decision` a mandatory per-class property; §18/§26.1 already declare `verification_mode` per operation. This states that they live together in one additive registration. **No new concept** — it names where four already-required per-class properties are declared.

### C-11 — Every "one transaction" guarantee depends on the single transactional store *(HA-1)*

> The atomic-checkpoint, verify+record, outbox, inbox, and claim-CAS guarantees **all require the single transactional relational store (A1).** A future process-separation (A3) MUST preserve them **via the shared Effect Grant Ledger and shared store**, not by weakening them — *authority lives in the ledger, not in a process (ADR-004 §4.4).* **This is a documented architectural assumption, not a new decision.**
