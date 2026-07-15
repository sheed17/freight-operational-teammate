# Foundational Entity Specifications — Consistency Review

**Subject:** `docs/specifications/entities/` — 17 foundational entity specifications + `00-conventions.md`.
**Derived from:** the canonical Target System Architecture Specification (`7ae1564`) and the frozen ADR/Semantic/Operating/Principles layers.
**Method:** mechanical grep across all files + manual cross-entity reconciliation.
**Date:** 2026-07-13

---

## 1. SPECIFICATIONS CREATED

All 17, each against the full 45-point structure (mechanically verified: **45/45 points in every file**):

`01` Work Item · `02` Pipeline Instance · `03` External Effect · `04` Effect Grant · `05` Checkpoint Witness · `06` Approval · `07` Observation · `08` Evidence · `09` Identity Binding Claim · `10` Conflict · `11` Expectation · `12` Exception · `13` Compensation · `14` Policy · `15` Rule · `16` Brake · `17` Audit Event · (`00` conventions).

### 1.1 Nothing was invented
**No new architectural primitive, state, event semantic, provenance class, gate decision, verification outcome, evidence condition, or effect path appears in any file.** Mechanical enum sweep (review §9) confirms **only the canonical registries are used**. Every lifecycle references a frozen table (spec §12 / ADR-008/010/011). **No file is SPECIFICATION BLOCKED** (all 13 lifecycle tables exist; the 4 immutable records — Checkpoint Witness, Evidence, Audit Event, and the immutable *content* of Observation — correctly have no lifecycle).

---

## 2. CONTRADICTIONS FOUND

> ### **One, and it is in the CANONICAL SPEC, not in these files. It is resolved at the specification layer without amending the architecture — but it must be recorded.**

### C-1 — Effect Grant vs External Effect: one record or two? **(resolved below the architecture)**

- **Canonical spec §12.3** presents the External Effect as **one state machine** whose states include `GRANTED` and `CLAIMED` (grant states) *and* `ATTEMPTED/VERIFIED/FAILED/UNKNOWN_OUTCOME` (outcome states).
- **Canonical spec §16.1 + §19.6** treat `effect_grants` as the ledger table, with commit-once `WHERE state='CLAIMED'`.
- **ADR-004 §3.2** gives the grant states as `GRANTED → CLAIMED | EXPIRED | REVOKED`.

Taken literally, three texts describe overlapping-but-not-identical state sets for what is arguably one row. **An implementer could reasonably build one table or two, and the two-table build would duplicate the commit-key namespace** — a real divergence.

**Resolution (documented in `03-external-effect.md` and `04-effect-grant.md`):**
> **The Effect Grant and the External Effect are the SAME durable ledger row (`effect_grants`), viewed through two aspects** — *capability* (may this attempt act?) and *outcome* (what happened?). This is faithful to §12.3 (one machine), preserves §16.1's `WHERE state='CLAIMED'` predicate, and honours P36 (fewest concepts). ### **The durable commit-key HOLD through `NEEDS_VERIFICATION` is provided by the Pipeline Instance Layer-1 reservation (non-terminal in `NEEDS_VERIFICATION`), NOT by this row's state** — so §16.1's narrow `WHERE state='CLAIMED'` is correct as the *claim-instant* backstop, and needs no widening.

**This does not require amending the canonical spec** — it interprets it, consistently. **But see §10:** a one-line clarifying note in spec §12.3 / §16.1 would remove the ambiguity permanently and is **recommended, not required.**

**No other contradictions were found.** All state names, event names, identifier names, provenance classes, gate decisions, verification outcomes, and evidence conditions are identical across the 17 files (review §9).

---

## 3. MISSING HIGHER-LEVEL DECISIONS

> ### **NONE that block specification. Every gap is a `NEEDS VALIDATION` with a fail-closed default (review §8), not a missing architectural decision.**

The 13 lifecycle tables, the 4 gate decisions, the 6 provenance classes, the 8 verification outcomes, the 5 evidence conditions, the checkpoint's 7 steps, the commit-key composition, and the two unique indexes were all already decided in the frozen layer. **The entity specs consumed them without needing a new ruling.**

---

## 4. DUPLICATE OR OVERLAPPING CONCEPTS

| Pair | Verdict |
|---|---|
| **Effect Grant / External Effect** | **Overlapping — resolved: one row, two aspects (C-1).** Not a duplicate entity. |
| **Policy / Rule** | **Distinct, sharing compilation/lifecycle machinery.** A Policy sets an action class's posture (gate ceiling, caps, autonomy); a Rule is a registered deterministic procedure with an id. Documented in both files' headers. **Not a duplicate.** |
| **Conflict / Exception** | **Distinct.** A Conflict is *incompatible evidence on a field* (blocks the field); an Exception is *something that needs a human* (owns the human-facing resolution). A Conflict, when it needs a human, **raises** an Exception. Clean 1:0..1. |
| **Expectation / Exception** | **Distinct.** An Expectation owes a future observation; on `OVERDUE`/`INDETERMINATE`/`EXPIRED` it **raises** an Exception. |
| **Identity Binding Claim / Observation** | **Distinct.** An Observation is *what a source said* (projected, immutable); a Binding Claim is *what Neyma inferred about which entity it belongs to* (native, correctable). This distinction is F-04, and keeping it is the whole point. |
| **Checkpoint Witness / Effect Grant** | **Distinct, 1:1.** The witness proves freshness (the seven checks); the grant confers single-use authority. **The two-key rule requires both** precisely because they are different. |
| **Audit Event / Business Event** | **Distinct, both facts, neither a command** (spec §11.3). Business events drive projections; audit events explain Neyma's authority. |

> ### **No entity was created for implementation convenience.** Every one of the 17 corresponds to a canonical Semantic-Model concept with a distinct owner and failure mode.

---

## 5. CARDINALITY CONFLICTS

**None.** The cross-entity cardinalities reconcile:

- **Work Item 1 : N Pipeline Instance** (`01`, `02`, spec §13) — consistent.
- **Pipeline Instance 1 : 0..1 {Approval, Checkpoint Witness, Effect Grant, External Effect}** (`02`) — consistent with each target's inverse.
- **Effect Grant 1 : 1 Checkpoint Witness** (`04`, `05`) — consistent.
- **Pipeline Instance N : 1 commit_key** (the retry family) — consistent with Layer-1 (`WHERE state NOT IN terminal`, one non-terminal) and Layer-2 (`WHERE state='CLAIMED'`, one claimed).
- **Observation N : 0..1 confirmed Binding Claim** and **Binding Claim `UNIQUE ... WHERE state='CONFIRMED'`** — consistent (one canonical binding per subject).
- **Conflict / Exception / Compensation** each 1:1 back to their raising machine — consistent.

---

## 6. TRANSACTION-BOUNDARY CONFLICTS

**None. The boundaries compose, and the one subtle case is explicit:**

- ### **The checkpoint boundary** (`02`, `04`, `05`): the `CHECKPOINT → GRANTED` transition + the Checkpoint Witness insert + the grant mint are **ONE transaction**; the `GRANTED → CLAIMED` transition + `EffectAttempted` + approval `CONSUMED` are **ONE (later) transaction** (the claim CAS). No file contradicts this.
- ### **Verify + record is ONE commit** (`03`) — closing the "verified but not recorded" window.
- **Correction propagation** (`09`, `13`) is **event-driven fan-out, NOT one mega-transaction** — each raised Compensation is its own gated aggregate. Explicitly stated in both files (no bulk-undo).
- **Aggregate independence:** a Work Item does **not** share a transaction with its Pipeline Instances (`01`) — they are separate aggregates coordinated by events. No boundary spans two aggregate roots.

---

## 7. CONSTRAINTS THAT CANNOT CURRENTLY BE ENFORCED

**All specified constraints are enforceable with the frozen architecture (one transactional relational store, A1).** Notes:

| Constraint | Enforceable? |
|---|---|
| `UNIQUE (tenant, commit_key) WHERE state='CLAIMED'` (Layer 2) & `WHERE state NOT IN terminal` (Layer 1) | ✅ partial unique indexes |
| Approval-to-gate (`approval_id NOT NULL` when gate ∈ human) | ✅ DB CHECK |
| `gate_decision NOT NULL` on every action class | ✅ **startup registry check** (not a row constraint — a boot-time gate; enforced as "system fails to start", spec §20.1) |
| `OWNER_ASSERTED` never machine-recomputed | ✅ **illegal-transition guard** (not a column constraint — a transition-table rule) |
| `MODEL_INFERRED` never gates | ✅ **checkpoint input-type raises on read** (a type-level guard) |
| No provenance laundering | ✅ **a total order + an authenticated-only strengthening transition** (application-level, adversarially tested) |
| Content-digest matches stored bytes (Evidence) | ✅ verified on write |
| Append-only (audit, observations, closures) | ✅ enforced by grant (no UPDATE/DELETE) |

> ### **Three of these are NOT relational constraints but TYPE / TRANSITION / STARTUP guards** — and the specs say so explicitly. This is correct: not every invariant is a `CHECK`, and the architecture deliberately spreads enforcement across the type system, CI, the transition tables, and the database (spec §19.9). **None relies on developer discipline.**

---

## 8. REMAINING `NEEDS VALIDATION` ITEMS

**All carried from the canonical spec §32. None blocks specification engineering.** Consolidated by entity:

| Item | Entities | Fail-closed default |
|---|---|---|
| **V1** reopening policy (late POD, short-pay, post-close) | Work Item, Compensation | machinery exists; each reopen needs a human `decision_ref` |
| **V2** approval TTLs | Approval | conservative defaults |
| **V3** dual-control classes/thresholds | Approval | single approval |
| **V4** registered identity rules | Observation, Identity Binding Claim, Rule | exact ID match only ⇒ else `AMBIGUOUS` ⇒ human |
| **V5** registered conflict-resolution rules | Conflict, Rule | no rule ⇒ every conflict to a human |
| **V6** deferred-verification bounds | Pipeline Instance, Expectation | `AWAITING_OBSERVATION` + Expectation |
| **V7** commit-key-in-external-record | External Effect | if not, a human resolves `NEEDS_VERIFICATION` |
| **V11** autonomy graduation thresholds | Policy | **nothing graduates** |
| **V12** per-tenant authorities | Policy | one Policy Owner, one level |
| **V13/V14/V15** brake engage/release/auto-engage | Brake | everyone engages; Policy Owner releases; 2/integration/window |
| Grant TTL length; witness freshness window; audit-query latency; retention tiering | Effect Grant, Checkpoint Witness, Audit Event | implementation tuning |

---

## 9. MECHANICAL CONSISTENCY RESULTS

Run by grep across all 17 files:

| Check | Result |
|---|---|
| **State names** | ✅ Only canonical values. Zero non-registry `UPPER_SNAKE` state tokens after filtering the known registries. |
| **Event names** | ✅ Consistent (`ClaimConfirmed`, `EffectAttempted`, `BrakeEngaged`, `OutcomeUnknown{unknown_reason}`, …); each emitter's list matches its consumers' expectations. |
| **Identifier names** | ✅ `tenant_id`, `commit_key`, `grant_id`, `checkpoint_id`, `pipeline_instance_id`, `work_item_id`, `decision_ref` — one spelling each. |
| **Provenance classes** | ✅ The six, exact, across 10 files that reference them. |
| **Gate decisions** | ✅ The four; **zero `UNGATABLE_PERMANENT` / `HUMAN_REQUIRED`** (the pre-amendment names). |
| **Verification outcomes** | ✅ The eight; `unknown_reason` present as the 3-member sub-enum. |
| **Evidence conditions** | ✅ The five, never collapsed. |
| **Deprecated terms** | ✅ **Zero** `Command`-as-entity, `CommandIntent`, `workflow run`, `commit identity`, `lane`-as-action-class in the body. |
| **`tenant_id` first** | ✅ Every PK/unique index in every file. |
| **No developer-discipline guarantee** | ✅ Every constraint maps to a DB constraint, a type, an illegal transition, a startup check, or a CI gate. |
| **45/45 points** | ✅ Every entity file. |

---

## 10. DOES ANY CANONICAL HIGHER-LEVEL DOCUMENT REQUIRE AMENDMENT?

> ### **NO amendment is REQUIRED. One clarifying note is RECOMMENDED.**

**Recommended (not required) — resolves C-1 permanently:**
Add one sentence to canonical spec **§12.3 / §16.1** stating that *"the External Effect and the Effect Grant are the same `effect_grants` row viewed as outcome and capability; the durable commit-key hold through `NEEDS_VERIFICATION` is the Pipeline Instance Layer-1 reservation, not this row's state."* **The specifications already encode this resolution and are internally consistent without the amendment** — so this is a clarity improvement, not a correctness fix, and it can wait for the next natural revision of the spec. ### **Per the standing rule, I did not modify the frozen document; I surfaced the resolution here and in the two entity files.**

**Nothing else.** The entity specs consumed the frozen architecture without exposing a genuine contradiction that could not be resolved below it.

---

## 11. WHETHER FOUNDATIONAL STATE-MACHINE SPECIFICATION MAY BEGIN

> # ✅ **YES.**

- **All 17 foundational entities are specified**, with attributes, constraints, relationships, transaction boundaries, provenance rules, failure behaviour, events, and adversarial tests.
- **Every lifecycle reference resolves** to a complete canonical table; **nothing is blocked**.
- **The one overlap (Effect Grant / External Effect) is resolved** and documented in three places.
- **No new primitive was introduced; no guarantee rests on discipline; no enum drifted.**

**The next phase — foundational state-machine specifications** (the executable transition tables, guards, and event contracts for the 13 machines) — **may begin.** It should:
1. Encode each transition table from spec §12 as declarative data (not `if` branches), with the guards named in these entity files.
2. Carry forward the **C-1 resolution** (Effect Grant / External Effect = one row, two aspects) into the External Effect / Effect Grant machine.
3. Treat the adversarial test names in these files (points 44) as the **acceptance surface** for the machines.

**Not yet:** freight-domain entities, event-family specs, adapter contracts, workflow specs, API specs, operational-loop acceptance specs, migration plans, or any `*.md` product/architecture/CLAUDE file — per the standing instruction.
