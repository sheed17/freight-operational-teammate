# Phase-1 Implementation Review — Migration Safety Task #1

> ### **CORRECTED — 2026-07-16.** This review presented `params['occurrence_key']` as the way to unblock the three fail-closed lanes. ### **That was wrong: a free-form caller string is the amount defect with a new field name.** The escape hatch has been REMOVED; occurrence identity now comes from a canonical business occurrence (Payment Application · Compensation · Expectation) or the operation fails closed. ### **Everything else in this review stands.** See `phase-1-occurrence-identity-review.md`.

> ### **The Commit Key now identifies the EFFECT, never the CONTENT of the decision.**
> ### **FORWARD-ONLY.** The amount-keyed derivation is **deleted, not deprecated**. Rollback may disable a capability; it may never bring this defect back — and the suite fails if anyone tries.
> ### **Phase 1 corrects effect IDENTITY. It does not claim the target effect boundary exists.** No grant ledger, no witness, no checkpoint, no claim CAS, no adapter containment, no tenant-first migration.

---

## ⛔ CONFLICT WITH THE FROZEN PLAN — REPORTED, NOT ABSORBED

### P1-F1 — U1.4 names the wrong test
The frozen `pr-sequence.md` says: *"U1.4 — invert `eval/tests/test_lane_graduation.py:206` (it currently asserts the defect)."* ### **It does not.** That test (`..._when_commit_identity_is_missing`) asserts the **nullable-identity** behaviour (DEF-2's shape): a missing identity escalates without burning the daily cap.

### **The amount-in-key assertion actually lived in `eval/tests/test_operation_router.py:282`** — `test_operation_commit_key_normalizes_equivalent_money_amounts`, which passed `approved_amount=` **into the key derivation** and asserted that two spellings of one amount hash alike. True, reassuring, and beside the point: by passing the amount at all it **enshrined it as identity**.

**Both were inverted.** Had I followed the line reference literally, the real defect-encoding test would have survived U1.4 untouched.

---

## 1. Frozen Phase-1 units completed
| Unit | Status |
|---|---|
| **U1.1** canonical derivation, amount-free **by signature** | ### **DONE** — `LogicalEffect` has no amount field; `commit_key()` takes no amount |
| **U1.2** the amount leaves the identity | ### **DONE — AC-SAFE-012 GREEN** |
| **U1.3** every consequential effect gets a key | ### **DONE — AC-SAFE-013 GREEN** |
| **U1.4** invert the defect-encoding test | ### **DONE — both of them** (see P1-F1) |
| **U1.5** historical backfill, report-only | ### **DONE** — `scripts/report_legacy_commit_identities.py`, proven to write nothing |
| **U1.6** rename `commit_identity` → Commit Key | ### **DONE** — 14 → **0** |

## 2. Production files changed (3)
`src/freight_recon/commit_key.py` **(new)** · `src/freight_recon/operation_router.py` · `src/freight_recon/workflow.py`.
### **No schema change. No migration file. No broad rename.** `approved_amount TEXT NOT NULL` still exists — as a **column**, never a key.

## 3. Test and guard files changed (7)
**New:** `test_phase1_commit_key.py` (35), `test_phase1_structural_guards.py` (12), `scripts/report_legacy_commit_identities.py`.
**Rewritten:** `test_phase0_migration_guards.py` (xfail → green). **Updated:** `test_operation_router.py`, `test_lane_graduation.py`, `test_phase0_deprecated_semantics.py`, `phase-0-baseline-manifest.yaml`.

## 4–5. Commit Key producers and consumers — the full inventory
| Site | Was | Now |
|---|---|---|
| `operation_router.py:335` `_commit_identity` | ### **the defective producer** | ### **DELETED** → `_logical_effect` + `_commit_reservation` |
| `workflow.py:875` `operation_commit_key` | ### **the defective derivation** | ### **DELETED** |
| `workflow.py` `operation_commit_claim` / `claim_operation_commit` / `update_operation_commit_payload` / `release_operation_commit` | each **re-derived** the key from the amount | take `commit_key`; **derive nothing** |
| router lines 147/167/222/228–232/243/287–311 (14 consumers) | splatted the identity dict | pass the canonical key |
| `test_operation_router.py:282`, `test_lane_graduation.py:206` | **asserted the defect** | inverted |

### **The producer inventory is now ONE. `test_the_canonical_derivation_is_the_only_one` walks every module in `src/` and `scripts/` and fails if a second appears.**

## 6. Canonical Commit Key fields
`SHA256("ck_v1" | tenant | action_class | target_system | target_resource_id | target_operation | occurrence_key)` — each component normalised **individually before joining**, and every field required except `occurrence_key` (empty = repetition not legitimate).

## 7. Mutable fields removed
### **`approved_amount`** — the whole point. Also structurally excluded: rate, line items, approval result, confidence, model output, **retry number, request id, approval id, attempt timestamps**, policy result. ### **They are not filtered out — there is nowhere to put them.** `LogicalEffect` is a frozen six-field dataclass; adding one fails a guard that reads the class's AST.
### **The amount is NOT discarded.** It travels as a **material fact** on the reservation, where drift stays visible for Phase 3's fingerprint to invalidate an approval — without ever splitting the effect's identity.

## 8–9. Money and non-money coverage — ### **the occurrence problem, stated honestly**
| Lane | Money | Repetition legitimate? | Occurrence discriminator | Verdict |
|---|---|---|---|---|
| `raise_invoice` | yes | no | `""` (single) | ✔ commit-once |
| `record_payable` | yes | no | `""` | ✔ |
| `create_load` | no | no | `""` | ✔ |
| `file_document` | no | **yes** | ### **content digest** | ✔ same POD once; BOL distinct |
| `update_status` | no | **yes** | ### **target status** | ✔ DELIVERED once; PICKED_UP distinct |
| ### **`record_payment`** | yes | ### **YES** | ### **NONE EXISTS** | ### **FAILS CLOSED** |
| ### **`adjust_invoice`** | yes | ### **YES** | ### **NONE EXISTS** | ### **FAILS CLOSED** |
| ### **`check_call`** | no | ### **YES** | ### **NONE EXISTS** | ### **FAILS CLOSED** |

### ⛔ P1-F2 — THREE LANES NOW FAIL CLOSED. THIS IS A REAL CAPABILITY REGRESSION.
> Partial payments against one invoice are **legitimately repeated**. ### **Today the only thing telling two of them apart was the AMOUNT — which is exactly what may not carry identity.** Remove it and two legitimate payments collapse into one effect (the second wrongly refused); keep it and re-reading ONE payment at a corrected figure looks like two (the double-pay defect).
> ### **There is no third option that is honest, so these lanes ESCALATE to a human until a real occurrence discriminator exists.** The frozen brief sanctions exactly this: *"do not invent one silently… fail closed, and report the unresolved semantic dependency."*
> ~~**A caller may pass `params['occurrence_key']` (a remittance reference, a credit-memo number) and the lane runs normally.**~~
> ### **⛔ SUPERSEDED 2026-07-16 — THIS WAS THE DEFECT.** A free-form caller string is not an identity: vary it between retries and every attempt mints a new logical effect, defeating commit-once through an arbitrary field instead of through the amount. ### **The escape hatch is REMOVED.** Occurrence identity now comes from a resolved canonical occurrence — **Payment Application `payment_application_id`** (P9) · **Compensation `compensation_id`** (P8) · **Expectation `expectation_id`** (P8) — or the operation fails closed. The underlying observation below stands: ### **the dependency is a product decision, not a coding one.** See `phase-1-occurrence-identity-review.md`.
> **`check_call`** had **no** duplicate protection before (non-money effects skipped the reservation path entirely). It now refuses rather than repeats.

### ⛔ The structural half of AC-SAFE-013
`will_commit` was `lane.requires_amount and not prepare_only` — ### **so the entire commit-once path was skipped for every non-money effect.** A key alone would have been a decoration. It is now `not prepare_only`: non-money effects reserve like money ones. ### **Filing the same POD twice now attaches it once — proved by counting actuator calls, not by reading code.**

## 10. Historical compatibility posture
`legacy_commit_rows()` — the bridge. ### **Exact scope:** rows whose descriptive columns identify this logical effect but whose `commit_key` is not the canonical one. ### **Deterministic:** an indexed lookup on stored columns; the old key is never recomputed or guessed. ### **No claim authority — it only ever BLOCKS** (asserted by AST: no INSERT/UPDATE/DELETE). ### **Removal: P2 (U2.4). Deletion condition:** zero legacy rows, proven by the backfill's dry-run.

| Legacy state | Disposition |
|---|---|
| committed | ### **reservation preserved — the effect is NOT repeated** |
| RESERVED / NEEDS_VERIFICATION | ### **UNRESOLVED — an accountable human, never an inferred success** |
| ### **≥2 rows for one logical effect** | ### **MANUAL_REVIEW_REQUIRED — evidence of a historical double-commit. Not merged. Not picked. Not resolved by an algorithm.** |

> ### **Without this bridge the migration itself would have been the double-commit:** a historically-raised invoice computes a different key today, so the canonical claim would succeed and raise it again. ### **No verified success is manufactured from historical data.**

## 11. Concurrency results
| Schedule | Result |
|---|---|
| ### **two workers, GBP 2,850 vs GBP 3,100, one invoice** | ### **identical keys · exactly ONE reservation · one row** |
| same non-money effect from two entry points | one winner |
| same effect, three retry ids | ### **one reservation — a retry is not a new effect** |
| distinct legitimate occurrences | distinct keys ✔ |
| same external id in two tenants | ### **both proceed — no collision** |
| crash after identity, before reservation | nothing happened; key reproducible; rerun safe |
| ### **crash after reservation, then restart** | ### **ESCALATES "not confirmed done" — no blind retry** |

Each worker uses its **own** SQLite connection: the arbiter is the table's PRIMARY KEY, not a Python object. ### **Phase 1 does NOT claim Phase 3's claim-CAS semantics. What it establishes is convergent identity plus the existing single-row reservation — and that is exactly what is tested, no more.**

## 12. Mutation-test results — ### **16/16 DETECTED**
amount back in the type · ### **the APPROVED amount folded back into the hash** · `None` for non-money · a new lane with no occurrence rule · request id as identity · retry id as identity · tenant scope removed · a second constructor · the deleted derivation restored by name · AC-SAFE-012 → xfail · AC-SAFE-013 → skip · non-money reservation disabled · the bridge given claim authority · a historical effect made re-committable · the amount no longer preserved · per-component normalisation removed.

> ### **The harness caught a genuine production bug I had written:** I normalised the *joined* `target_resource_id`, so `" ld-1 "` + `"cust"` kept its inner space — ### **two readings of ONE invoice would have forked into two effects, the exact failure Phase 1 exists to prevent.** Fixed by normalising each component before joining.
> ### **And one of my mutations was a fake:** "amount back in the hash" injected `params["amount"]`, which is always empty here — it changed the source text while changing no behaviour, and the guard was right to stay green. ### **A mutation that does not reintroduce the defect proves nothing about the guard.** Rewritten to fold in the real approved amount; it then failed as it should.

## 13–14. AC-SAFE-012 / AC-SAFE-013 — ### **GREEN**
Not renamed, not weakened, not skipped, not stubbed. Both assert the **frozen oracles** against the **real router** with a **real store**, counting **real actuator calls**:
- **AC-SAFE-012** — GBP 2,850 then GBP 3,100 ⇒ identical key ⇒ ### **exactly ONE invoice** (`len(actuator.commits)` unchanged; one row).
- **AC-SAFE-013** — the same POD twice ⇒ ### **ONE attachment** (`len(actuator.calls)` unchanged; one row).

## 15–19. ### **OPEN FINDINGS — ALL PRESERVED, NONE CLOSED**
| # | Finding | Status |
|---|---|---|
| 15 | seven non-tenant-first tables | ### **OPEN — P2. Untouched.** |
| 16 | ### **`workflow_runs.document_hash` globally unique across tenants** | ### **OPEN — a present cross-tenant defect, P2. Not patched opportunistically.** |
| 17 | 24 canonical transitions with no cited event | ### **OPEN — event-corpus obligation, before P5/G2. No events invented.** |
| 18 | ### **R-07** | ### **OPEN — NOT CONTAINED.** Six live-write paths remain reachable. |
| 19 | 31 direct adapter import edges | ### **OPEN — P4. Untouched.** |

## 20–21. Final suite + final-tree validation evidence
| | |
|---|---|
| **Final suite** | ### **832 passed · 1 skipped · 0 failed** *(the skip is the now-empty red-by-design registry — AC-SAFE-012/013 went green, so nothing is red-by-design any more)* |
| validation start tree | `8fc4c1896e3ba4641aa86ef26cb6a1f857b8a5d6` |
| validation end tree | `8fc4c1896e3ba4641aa86ef26cb6a1f857b8a5d6` |
| commit candidate tree | `8fc4c1896e3ba4641aa86ef26cb6a1f857b8a5d6` |
| ### **all three match** | ### **✔ — the suite ran LAST, against the exact tree committed** |

### ⛔ P1-F3 — the deprecated-term ratchet was measuring the wrong surface
The first final run came back **4 failed**: `lane` 314→327, `CommandIntent` 93→95, **`commit_identity` 0→2**. All of it from Phase 1's own new **test** files naming the terms they test — and 2 of the `commit_identity` hits were inside a guard whose entire job is to assert `"def _commit_identity(" not in source`.
> ### **`commit_identity` in PRODUCTION had reached ZERO — U1.6 complete, the unit's whole point — while the combined count read 2 and called it a regression.** Naming a deleted symbol in order to forbid it is the opposite of a regression, and a rule that scores it as one only teaches people to switch the rule off.
> The ratchet now governs **production** (`src/` + `scripts/`) — the surface P8's rename must migrate and the only one that can entrench the old model. Tests are counted and tracked, never ratcheted: their vocabulary is derivative of the API they exercise, and P8 sweeps them along with the code.
> ### **Narrowed, not weakened — proved by mutation: a new deprecated use in production, deprecated vocabulary reaching a new production file, and `_commit_identity` restored in production are each still DETECTED (3/3).**
> **The honest numbers this exposed, measured against `d33f251`:** ### **production `lane` 257 → 227 (down 30 — deleting the amount-keyed derivation took its lane-shaped parameters with it) · `commit_identity` 14 → 0 · `CommandIntent` 56 → 57 (+1, adjudicated).**

## 22. Rollback posture
### **FORWARD-ONLY.** **Permitted:** disable the consequential capability · preparation-only / read-only mode · **preserve corrected Commit Key data** · require manual execution.
### **FORBIDDEN — and mechanically prevented:** restoring amount-dependent keys (the type has no field; the derivation is deleted; 4 guards + 3 mutations fail) · restoring nullable non-money identity · **two identity algorithms independently authorising execution** (`test_the_canonical_derivation_is_the_only_one` walks every module) · deleting corrected effect-identity history · treating unresolved compatibility cases as safe to retry.

## 23. May Phase 2 begin?
| Condition | Status |
|---|---|
| every consequential effect has a Commit Key | ✔ (or fails closed) |
| identity excludes mutable decision content | ✔ structurally |
| equivalent attempts converge | ✔ incl. the race |
| distinct effects don't collide | ✔ |
| tenant scopes every key | ✔ *(in the KEY; the TABLE is still not tenant-first — P2, not claimed)* |
| AC-SAFE-012 / AC-SAFE-013 | ### **GREEN** |
| historical effects can't be recommitted | ✔ bridge + 16/16 mutations |
| open findings preserved | ### **✔ all five** |

---

# VERDICT

## ### **READY TO BEGIN IMPLEMENTATION PHASE 2**

**Carried forward:**
- ### **P1-F2 — three lanes (`record_payment`, `adjust_invoice`, `check_call`) now ESCALATE.** A real capability regression, taken deliberately: the amount was the only thing distinguishing legitimate repeats, and it may not carry identity. ### **This needs a product decision — what identifies a payment occurrence? — and a caller-supplied `occurrence_key` unblocks it immediately.**
- ### **Tenant isolation is NOT complete.** The key is tenant-scoped; the table is not. `AC-SEC-001` stays red. ### **P2 must migrate all SEVEN tables** — and `workflow_runs.document_hash` is a **live** cross-tenant leak today.
- ### **R-07 remains OPEN — NOT CONTAINED.** Phase 1 made effect identity correct. It did not put a wall in front of the six live-write paths; only P4 does.
