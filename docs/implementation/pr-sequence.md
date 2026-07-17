# PR-Sized Implementation Units

> ### **NO CALENDAR ESTIMATES.** A unit is sized by **one reviewable idea**, not by hours. ### **Every unit leaves the repo deployable and coherent** (principle 12) and ### **names the acceptance case that proves it done — a unit whose completion oracle is "the code is written" is not a unit.**

**Legend — Flag:** the capability flag gating the unit (`OFF` until its gate). **Rollback:** what disabling the flag reverts to. ### **A rollback NEVER restores a removed unsafe path** (principle 11).

## Phase 0 — Baseline & migration guards *(G0)*
| Unit | Changes | Green when | Stays RED | Flag | Rollback | ### Completion oracle |
|---|---|---|---|---|---|---|
| **U0.1** | acceptance harness skeleton, registry loader | `AC-TRACE-000` runs | — | n/a | n/a | the harness enumerates the frozen registry and reports |
| **U0.2** | ### **the two MIGRATION_GUARD cases** | ### **they RUN and FAIL** | ### **AC-SAFE-012/013 — RED BY DESIGN** | n/a | n/a | ### **CI shows two named expected-failures, not zero tests. A guard that does not fail today is not a guard.** |
| ### **U0.3** | ### **the null-gate startup check — `DEFERRED_BY_DEPENDENCY — REQUIRED AT PHASE 8`** | ### **`AC-CKPT-6-missing`** | ### **the RUNTIME invariant — see U8.1** | n/a | n/a | ### **Phase-0 obligation (below), NOT the runtime check** |

> ### **⛔ U0.3 — DEFERRED_BY_DEPENDENCY — REQUIRED AT PHASE 8** *(Errata 2026-07-16)*
> ### **This is a planned dependency, NOT a waiver.** The requirement is preserved in full; only its phase semantics are corrected.
> **Why:** `AC-CKPT-6-missing` asserts that an Action Class with a **null gate** makes the system **FAIL TO START**. Typed Policy and Action Class gate registration do not exist until **P8**. ### **Running the intended checker now would enumerate ZERO gate registrations and report green — a false pass on an empty population (M-9), and the same error as PL-6: a gate enabled before the thing it gates exists.** The roadmap already names the rule: ### **a gate with nothing behind it is theatre.**
> ### **A fail-safe DEFAULT (today's `lane_graduation`) is NOT a NOT-NULL gate.** A default says *"nobody decided, so we picked the safe answer."* The canonical rule says *"nobody decided, so REFUSE TO START."*
>
> ### **THE PHASE-0 OBLIGATION** *(complete — `test_phase0_null_gate.py`)*: verify the canonical gate-decision requirement **exists** · verify its implementation unit (**U8.1**) is **registered** · verify it is **assigned to Phase 8** · verify its acceptance case and release-gate dependencies (**G4**) **resolve** · ### **verify NO earlier phase may claim the runtime invariant is implemented** · ### **FAIL if a zero-row runtime checker reports success.**
> ### **THE PHASE-8 COMPLETION OBLIGATION** *(U8.1)*: enumerate **every registered Action Class** · require **exactly ONE positive gate decision** each · ### **reject null · reject default · reject unregistered action classes** · ### **FAIL STARTUP on incomplete registration** · ### **prove a NON-ZERO evaluated registration count.**
> ### **U0.3 may NOT be marked implemented before P8. No placeholder Policy or gate runtime may be added to satisfy it earlier.**
| **U0.4** | `AC-SEC-001` tenant-first structural probe | ### **it RUNS and FAILS (7/8 tables)** | ### **AC-SEC-001** | n/a | n/a | ### **the probe names all 7 offending tables by EXACT SET** *(errata: was 6/8)* |
| **U0.5** | the evaluation contract — no probe may report green on zero rows | `AC-TRACE-000` | — | n/a | n/a | the M-9 defect is reproduced in a test and fails loudly |
| **U0.6** | canonical identifier resolution | `AC-TRACE-000` | — | n/a | n/a | every cited id resolves to the frozen corpus or a declared scheme |
| **U0.7** | planning-graph consistency | `AC-TRACE-000` | — | n/a | n/a | ### **G4 mechanically resolves through P8** |
| **U0.8** | acceptance bijection probes (exact-set) | `AC-MACH-000`, `AC-EVT-000` | — | n/a | n/a | ### **enumerated == registered, by SET not count** |
| **U0.9** | direct adapter import guard *(DETECTION ONLY — not U4.9's gate)* | `AC-SEC-013` | ### **AC-SEC-013 stays red until P4** | n/a | n/a | the allowlist is shrinking-only |
| **U0.10** | live-effect entry-point guard | `AC-SEC-013` | ### **R-07 stays OPEN** | n/a | n/a | ### **every effect-capable entry point is classified; NONE is contained** |
| **U0.11** | deprecated-semantics baseline | — | — | n/a | n/a | counts recorded, ratcheted downward-only, nothing renamed |
| **U0.12** | the baseline manifest + its integrity | — | — | n/a | n/a | every allowance has a reason, phase, owner, deletion condition |
| **U0.13** | ### **guard integrity — the guards guard themselves** | — | — | n/a | n/a | ### **no guard may be skipped, non-strict-xfailed, or assert vacuously over an empty set** |

> ### **ERRATA 5 (2026-07-16):** U0.5–U0.13 were **delivered in Phase 0 but never declared here**, so every normative reference to them was an unresolvable identifier — the exact defect class U0.6 exists to catch, and ### **the Phase-0 commit `d33f251` was RED against its own guard because of it.** The Phase-0 review reported the scope delta in prose and left the declaration as an owner decision; ### **prose could not satisfy a mechanical resolver.** Declaring them here is the smallest change that makes the plan match its own contents.

## Phase 1 — ⛔ MIGRATION SAFETY TASK #1 *(G0 → the first green)*
| Unit | Changes | Green when | Flag | Rollback | ### Completion oracle |
|---|---|---|---|---|---|
| **U1.1** | the canonical key derivation, **new symbol, unused** | key unit tests | n/a | delete | the derivation is amount-free by signature — ### **the amount is not a parameter, so it cannot be passed** |
| ### **U1.2** | ### **`_commit_identity` drops `approved_amount`; the amount moves to the fingerprint** (`operation_router.py:335`, consumers at 14 sites, `workflow.py:543,582`) | ### **AC-SAFE-012 GREEN** | n/a | ### **NONE — this is a defect fix, not a capability** | ### **`AC-SAFE-012` flips red→green + a grep proves no amount reaches any key derivation** |
| ### **U1.3** | ### **delete `if not amount: return None` — EVERY consequential effect gets a key** | ### **AC-SAFE-013 GREEN** | n/a | NONE | ### **AC-SAFE-013 green + a non-money effect (document file) mints a key** |
| ### **U1.4** | ### **invert `eval/tests/test_lane_graduation.py:206`** *(it currently asserts the defect)* | the inverted test | n/a | NONE | ### **the test that encoded the defect now forbids it — the old assertion CANNOT be restored without failing AC-SAFE-012** |
| **U1.5** | ### **the historical backfill (report-only first)** | the dry-run report | n/a | re-run | ### **the report lists every collision; each collision is routed to MANUAL_REVIEW_REQUIRED, NOT merged** |
| **U1.6** | rename `commit_identity` → **Commit Key** *(mechanical, behavior-free)* | suite unchanged | n/a | rename back | ### **a diff-shape review: rename-only, zero logic** |

## Phase 2 — Tenant-safe ledger *(G4-prep)*
### **U2.1** tenant-first keys across ### **ALL SEVEN offending tables — enumerated by exact set in [migration-plan.md PART 7](migration-plan.md), not by count** ⇒ ### **`AC-SEC-001` GREEN.** *(Errata 2026-07-16: this unit previously said "the 6 offending tables". Executed literally it would have migrated six, left `operation_token_amounts` behind, and left AC-SEC-001 red with the phase marked done. ### **U2.1 is NOT complete while any of the seven remains non-tenant-first.**)* · **U2.2** the one `effect_grants` table, 8 states · **U2.3** ### **the two partial unique indexes (reservation + commit-once)** ⇒ `AC-SAFE-014`, `AC-RACE-001` · **U2.4** the ledger backfill from `operation_commit_claims` (dry-run first) · **U2.5** rename to `effect_grants`.
> ### **U2.3 is the load-bearing unit of the whole plan: it is the mechanism that makes coexistence safe (principle 5). Until it exists, EVERY cutover strategy in the entry-point plan is unbacked.**

## Phase 3 — Checkpoint + witness *(G4)*
**U3.1** ### **`CheckpointPassed` with no public constructor** ⇒ `AC-SAFE-002` (a **negative control**: a synthesized witness must **fail to compile**) · **U3.2** the 7 steps in one transaction, ### **no async work before the claim CAS** ⇒ the 105 `AC-CKPT-*` · **U3.3** grant mint + claim CAS ⇒ `AC-RACE-001..017` (10k interleavings) · **U3.4** ### **brake as admission control — refuses to mint/claim, NEVER kills a worker** ⇒ `AC-SAFE-006/007/027` · **U3.5** the spec-derived contract simulators (replacing `MockTmsWriteLedger`).

## Phase 4 — Adapter containment *(G4)*
### **U4.11** the verification taxonomy (8 outcomes + positive health detection) ⇒ `AC-SAFE-021/023`, `AC-ADPT-012/015` · **U4.1** the pipeline client · **U4.2–U4.5** convert the 4 src sites (`multistep_write`, `discovered_write`, `truckingoffice_write`, `brain_runtime`) · ### **U4.6 DELETE EP-6, EP-7, EP-9, EP-10** · ### **U4.7 remove the `cdp_actuator` import from `orient_tms.py` (EP-8)** · **U4.8** convert EP-1/EP-3 to pipeline clients · ### **U4.9 the CI import gate ON** ⇒ `AC-SEC-013`, `AC-ADPT-002` · **U4.10** orphan detection.
> ### **U4.6 is irreversible by design. Its rollback is NOT "restore the scripts" — it is "the capability stays off." (principle 11)**

## Phases 5–9 *(kernel completion)*
**P5:** U5.1 transactional outbox ⇒ `AC-RACE-006/007`; U5.2 dedup inbox ⇒ `AC-ADPT-010`; U5.3 ### **the 98 event contracts** + upcaster *(errata: was 92)*; U5.4 ### **the `GC-1` golden corpus + pinned digest** ⇒ `AC-EVT-007/008`; U5.5 ### **sandboxed replay — effects structurally unreachable in replay** ⇒ `AC-EVT-011`; ### **U5.6 audit reconstruction (18-field explainability, beliefs-of-that-day)** ⇒ `AC-AUD-*`.
**P6:** U6.1 ### **Work Item (+ the accountable owner)** ⇒ `AC-SAFE-028`; U6.2 Pipeline Instance; U6.3 the 13 machines / ### **134 transitions** ⇒ `AC-MACH-*` *(errata: was 141)*; U6.4 ### **the `workflow_runs` SPLIT + the `done` rename**.
**P7:** U7.1 ### **`provenance_class` + R-P1/2/3** ⇒ `AC-SAFE-015/016`, `AC-ADPT-008`; U7.2 content-addressed Evidence; U7.3 Observation; U7.4 ### **the deterministic linker (`AMBIGUOUS` ⇒ human, never a guess)**; U7.5 the `claim` verb rename.
**P8:** ### **U8.1 typed policy + Action Class gate registration ⇒ `AC-CKPT-6-*` — and it CLOSES U0.3 (`DEFERRED_BY_DEPENDENCY`): enumerate every registered Action Class, require exactly one positive gate decision, reject null/default/unregistered, FAIL STARTUP on incomplete registration, and prove a non-zero evaluated count**; U8.2 ### **compile-or-refuse Rules** ⇒ `AC-WF10-005`; U8.3 the real brake + `BrakeEngaged`; U8.4 Conflict/Expectation/Exception/Compensation ⇒ M7–M10; ### **U8.5 THE `lane` MIGRATION (310 sites → action_class ∪ workflow_id ∪ policy scope)** — mechanical, behavior-free, last; U8.6 `CommandIntent` → Proposal.
**P9:** U9.1–U9.11 the 40 domain entities by family ⇒ `AC-DOM-*`; U9.12 External Entity Mapping; U9.13 field-level authority.

## Phases 10–14 *(the slice — NEEDS DESIGN-PARTNER VALIDATION)*
**P10** W6→W8 no-writes ⇒ `AC-WF6-*`, `AC-FC-005/006/013` (**G5**) · **P11** shadow ⇒ **zero-effect assertion** (**G6**) then human-executed ⇒ ### **`AC-DEG` assertion 5: NEVER claim Neyma executed** (**G7**) · ### **P12 the first supervised live write — gated on G4 RE-RUN LIVE + the physical deletion of EP-6,7,9,10** (**G8**) · **P13** handoffs ⇒ `AC-FC-016` (**G9**) · **P14** bounded autonomy ⇒ the graduation dossier (**G10**).

## Dependency spine *(the only strictly-ordered chain)*
### **U0.2 → U1.2/U1.3 → U2.1 → U2.3 → U3.1 → U3.2 → U3.3 → U4.9 → U4.6 → P12.**
### **Everything else may parallelize. Nothing may jump this chain — every link is a safety precondition of the next, and P12 (the first live write) sits behind ALL of them.**
