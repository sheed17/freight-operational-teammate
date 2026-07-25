# Platform Safety Acceptance *(AC-SAFE-*, AC-CKPT-*)*

*Registry: `acceptance/registry.md` (contract defaults, oracle rule, fixtures). ### **EVERY case here is MERGE-GATING. Zero failure tolerance. No individual waiver.***

---
## PART A — THE 28 PERMANENT SAFETY INVARIANTS

*Each: `ID · invariant · source · risk · level · oracle · negative assertion · variants`. Variants: **P**=positive **N**=negative **R**=race **C**=crash **RP**=replay.*

| ID | Invariant proved | Source | Risk | Oracle | Negative assertion | Variants |
|---|---|---|---|---|---|---|
| **AC-SAFE-001** | No external effect without a **claimed** Effect Grant | ADR-004 §2.1 | SAFETY_CRITICAL | adapter refuses; **simulator records ZERO external calls**; `ClaimRefused` | ### **the simulator's call log is empty** | P N R C RP |
| **AC-SAFE-002** | No external effect without a **fresh** Checkpoint Witness | ADR-004 §2.2 | SAFETY_CRITICAL | a valid grant + stale witness ⇒ refuse + `StaleWitnessUsed` | zero external calls | P N |
| **AC-SAFE-003** | Witness+grant bind the **same** tenant, action, target, commit key, fingerprint, policy_version, brake_version, entity-version set | ADR-004 §3.2 | SAFETY_CRITICAL | DB row equality across all 8 fields | any mismatch ⇒ Sev-0 event, no call | P N |
| **AC-SAFE-004** | All **seven** checkpoint steps in ONE atomic transaction | ADR-004 §2.4 | SAFETY_CRITICAL | ### **a txn-boundary probe: exactly one commit contains all 7 reads + the witness insert + the mint** | no partial witness exists at any isolation level | P C |
| **AC-SAFE-005** | ### **NO async work between checkpoint success and claim** | Target §19.2 M-40 | SAFETY_CRITICAL | ### **an instrumentation oracle: no await/IO/scheduling point between the witness insert and the CAS** | — | P |
| **AC-SAFE-006** | Brake before claim ⇒ ### **the claim affects ZERO rows** | ADR-011 | SAFETY_CRITICAL | `UPDATE … rowcount = 0`; zero external calls | the adapter never invoked | P R |
| **AC-SAFE-007** | Brake after claim ⇒ ### **does NOT kill the in-flight worker** | ADR-011 §3 | SAFETY_CRITICAL | the effect proceeds to `VERIFIED`; ### **assert NO `UNKNOWN_OUTCOME` was manufactured by the brake** | no worker termination | P R |
| **AC-SAFE-008** | Material-fact drift **voids** a stale approval | ADR-005 F-01 | FINANCIAL_CORRECTNESS | `VOID_ON_DRIFT` + a field-level `drift_diff` naming amount old→new | ### **zero external calls — the £3,100 invoice never issued** | P N R |
| **AC-SAFE-009** | Entity-version drift **blocks** the claim | ADR-009 | FINANCIAL_CORRECTNESS | `CheckpointFailed{step:5}`; CAS zero rows | no call | P R |
| **AC-SAFE-010** | Policy-version drift **blocks** the claim | ADR-010 | FINANCIAL_CORRECTNESS | claim CAS zero rows; `ApprovalVoided{policy}` | no call | P R |
| **AC-SAFE-011** | An approval authorizes **one committed effect**, not one attempt | ADR-005 §3.7 | FINANCIAL_CORRECTNESS | approval survives a **provable** failure and authorizes a new pipeline; **consumed exactly once** | ### **a frozen (post-unknown) approval is NOT reusable** | P N |
| **AC-SAFE-012** | ### **Commit Key EXCLUDES mutable decision values (the amount)** | ADR-009 §4 | FINANCIAL_CORRECTNESS | ### **two proposals at £2,850 and £3,100 ⇒ IDENTICAL commit_key ⇒ exactly ONE invoice** | the simulator shows one create | P R **MIGRATION_GUARD** |
| **AC-SAFE-013** | ### **Commit Key EXISTS for non-money effects** | ADR-009 §4.3 | DATA_INTEGRITY | filing the same POD twice ⇒ **one attachment** | no second upload | P **MIGRATION_GUARD** |
| **AC-SAFE-014** | Two racing attempts at one logical effect ⇒ **at most one claim** | ADR-009 | SAFETY_CRITICAL | `UNIQUE(tenant,commit_key) WHERE state='CLAIMED'`; 1 winner / N-1 `ClaimRefused` | exactly one external call | P **R** |
| **AC-SAFE-015** | `MODEL_INFERRED` **cannot be read** by a consequential gate | ADR-002 §2.3 | SAFETY_CRITICAL | ### **the checkpoint input type RAISES on read; at confidence 1.0 it still refuses** | no witness | P N |
| **AC-SAFE-016** | `OWNER_ASSERTED` **cannot be overwritten** by machine recomputation | R-P3 / L-A | DATA_INTEGRITY | ILLEGAL TRANSITION; state unchanged; `IllegalTransitionAttempted` | ### **the owner's binding is byte-identical after** | P N RP |
| **AC-SAFE-017** | An open **Conflict blocks** dependent consequential actions | ADR-002 C6 | SAFETY_CRITICAL | field `conflicting` ⇒ checkpoint step-4 fail | no call | P |
| **AC-SAFE-018** | ### **A counterparty assertion cannot self-authorize** | **ADR-003 (permanent)** | SAFETY_CRITICAL | the claim is `MODEL_EXTRACTED`; payable **blocked**; `CounterpartySelfAuthorizationDetected` | ### **no promotion to `OWNER_ASSERTED` at ANY confidence** | P N |
| **AC-SAFE-019** | ### **Replay cannot create a witness, grant, adapter call, or effect** | ADR-004 §4.6 | SAFETY_CRITICAL | replay `GC-1` ⇒ **0 witnesses, 0 grants, 0 calls** | the simulator log is empty | **RP** |
| **AC-SAFE-020** | Compensation uses the **ordinary pipeline** | ADR-008 §3.10 | FINANCIAL_CORRECTNESS | the compensating effect has its own witness+grant+approval+readback | no privileged path | P |
| **AC-SAFE-021** | ### **A timeout alone NEVER produces `FAILED`** | GR-5 | SAFETY_CRITICAL | timeout ⇒ `UNKNOWN_OUTCOME`; `FAILED` requires `failure_proof` | ### **no `EffectFailed` without proof** | P N C |
| **AC-SAFE-022** | `UNKNOWN_OUTCOME` always carries an **owner + reason** | GR-6 | SAFETY_CRITICAL | `unknown_reason` NOT NULL; a named human owner; exposure stated | ### **no timer moves it (illegal)** | P N |
| **AC-SAFE-023** | ### **Local persistence cannot verify an external effect** | M-72 | SAFETY_CRITICAL | ### **the verifier's interface has NO access to local state; a local write ⇒ still `UNKNOWN`** | the R-01 archetype cannot recur | P N |
| **AC-SAFE-024** | An Exception cannot close without a **valid `decision_ref`** | GR-14 / K-1 | AUDITABILITY | ### **the ref must RESOLVE to a human-decision audit row or an ACTIVE rule — a bare string fails** | no close | P N |
| **AC-SAFE-025** | Cross-tenant processing **rejected before business handling** | C-1 | TENANT_ISOLATION | rejected at the inbox; `CrossTenantAccessAttempted`; **GLOBAL brake** | ### **no tenant-A handler ran** | P N |
| **AC-SAFE-026** | Unauthorized adapter invocation **engages the brake** | §19.9 L5 | SECURITY | orphan `EffectAttempted` ⇒ `OrphanAdapterInvocation` ⇒ auto-brake (tenant+action) | — | P |
| **AC-SAFE-027** | ### **Automation cannot broaden policy or release a brake** | ER-11/12 | SAFETY_CRITICAL | a property test over **every** automated path ⇒ engage/narrow only | `UnauthorizedPolicyActivationAttempted` / `UnauthorizedBrakeReleaseAttempted` recorded | P N |
| **AC-SAFE-028** | ### **Every open Work Item has exactly ONE accountable human owner** | I1 | OPERATIONAL_COMPLETENESS | ### **a DB invariant scan: zero open Work Items with null/`system` owner, at any time** | creation without an owner fails | P N C |

---
## PART B — THE ATOMIC CHECKPOINT MATRIX *(AC-CKPT-*)*

### **7 steps × 15 conditions = 105 merge-gating cases.** Steps: **1** approval validity · **2** fingerprint equality · **3** projected freshness · **4** native-state validity · **5** entity-version concurrency · **6** policy/autonomy · **7** brake admission.

**Conditions (per step):** `valid` · `missing input` · `stale input` · `conflicting input` · `wrong tenant` · `wrong target` · `wrong actor` · `changed version` · `changed policy` · `changed brake` · `crash before txn` · `crash during txn` · `crash after commit` · `replay` · `concurrent competing claim`.

**ID:** `AC-CKPT-<step><condition>` (e.g. `AC-CKPT-3-stale`).

> ### **THE UNIVERSAL ORACLE FOR ALL 105:** the outcome is **ALWAYS EXACTLY ONE** of:
> **(a) ONE immutable Checkpoint Witness AND ONE claimed Effect Grant** *(all seven passed, atomically)*
> **(b) NO authorization capability whatsoever** *(no witness row, no grant row, no external call)*
> ### **NO PARTIAL AUTHORIZATION STATE MAY EXIST — asserted at every isolation level and after every crash point.**

**Representative anchors (each expands across the 15 conditions):**
- **Step 1** `AC-CKPT-1-*` — a missing/expired/revoked/wrong-authority approval ⇒ (b). `wrong actor`: a **model**-granted approval ⇒ (b) + Sev-0.
- **Step 2** `AC-CKPT-2-*` — ### **`stale`: approve £2,850, mutate the TMS to £3,100, resume ⇒ (b) + `VOID_ON_DRIFT` + a diff naming the amount. THE F-01 CASE.**
- **Step 3** `AC-CKPT-3-*` — ### **`stale`: a CACHE offered to the money read ⇒ structurally impossible (the reader cannot accept one) ⇒ compile/construction failure, not a runtime pass. `missing`: source unavailable ⇒ (b) — NEVER "no drift".**
- **Step 4** `AC-CKPT-4-*` — `conflicting`: an open Conflict on a material field ⇒ (b). A `MODEL_INFERRED` material fact ⇒ (b).
- **Step 5** `AC-CKPT-5-*` — ### **`changed version`: an entity in the SD-3 set mutates concurrently ⇒ (b). `missing`: an entity referenced by a material fact NOT pinned ⇒ THE SPEC IS VIOLATED — the case FAILS the implementation** *(this is the SD-3 oracle: assert the pinned set equals {every material-fact entity} ∪ {target} ∪ {gate-precondition entities}).* |
- **Step 6** `AC-CKPT-6-*` — `missing`: an action class with a **null gate** ⇒ ### **the system FAILS TO START** (a `STRUCTURAL` case). `changed policy` ⇒ (b).
- **Step 7** `AC-CKPT-7-*` — `changed brake` ⇒ (b) + CAS zero rows. ### **`missing`: the brake store unreachable ⇒ (b) — "cannot read the brake" NEVER means "off".**

**Crash conditions (all 7 steps):** `crash before txn` ⇒ (b), nothing happened. `crash during txn` ⇒ (b), no partial rows. ### **`crash after commit` (witness+grant exist, claim not yet made) ⇒ the grant EXPIRES unclaimed ⇒ (b) — nothing happened; re-checkpoint is safe.**
**Replay (all 7):** ⇒ ### **(b) always — replay constructs no witness (AC-SAFE-019).**
**Concurrent competing claim (all 7):** ⇒ exactly one (a), the rest (b).
