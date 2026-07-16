# PR-Sized Implementation Units

> ### **NO CALENDAR ESTIMATES.** A unit is sized by **one reviewable idea**, not by hours. ### **Every unit leaves the repo deployable and coherent** (principle 12) and ### **names the acceptance case that proves it done — a unit whose completion oracle is "the code is written" is not a unit.**

**Legend — Flag:** the capability flag gating the unit (`OFF` until its gate). **Rollback:** what disabling the flag reverts to. ### **A rollback NEVER restores a removed unsafe path** (principle 11).

## Phase 0 — Baseline & migration guards *(G0)*
| Unit | Changes | Green when | Stays RED | Flag | Rollback | ### Completion oracle |
|---|---|---|---|---|---|---|
| **U0.1** | acceptance harness skeleton, registry loader | `AC-TRACE-000` runs | — | n/a | n/a | the harness enumerates the frozen registry and reports |
| **U0.2** | ### **the two MIGRATION_GUARD cases** | ### **they RUN and FAIL** | ### **AC-SAFE-012/013 — RED BY DESIGN** | n/a | n/a | ### **CI shows two named expected-failures, not zero tests. A guard that does not fail today is not a guard.** |
| **U0.3** | the null-gate startup check | ### **`AC-CKPT-6-missing`** *(the real frozen ID — see the review's M-2)* | — | n/a | n/a | a null/absent policy gate ⇒ **the process REFUSES TO START** |
| **U0.4** | `AC-SEC-001` tenant-first structural probe | ### **it RUNS and FAILS (6/8 tables)** | ### **AC-SEC-001** | n/a | n/a | the probe names the 6 offending tables |

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
**U2.1** tenant-first keys across the **6 offending tables** ⇒ ### **`AC-SEC-001` GREEN** · **U2.2** the one `effect_grants` table, 8 states · **U2.3** ### **the two partial unique indexes (reservation + commit-once)** ⇒ `AC-SAFE-014`, `AC-RACE-001` · **U2.4** the ledger backfill from `operation_commit_claims` (dry-run first) · **U2.5** rename to `effect_grants`.
> ### **U2.3 is the load-bearing unit of the whole plan: it is the mechanism that makes coexistence safe (principle 5). Until it exists, EVERY cutover strategy in the entry-point plan is unbacked.**

## Phase 3 — Checkpoint + witness *(G4)*
**U3.1** ### **`CheckpointPassed` with no public constructor** ⇒ `AC-SAFE-002` (a **negative control**: a synthesized witness must **fail to compile**) · **U3.2** the 7 steps in one transaction, ### **no async work before the claim CAS** ⇒ the 105 `AC-CKPT-*` · **U3.3** grant mint + claim CAS ⇒ `AC-RACE-001..017` (10k interleavings) · **U3.4** ### **brake as admission control — refuses to mint/claim, NEVER kills a worker** ⇒ `AC-SAFE-006/007/027` · **U3.5** the spec-derived contract simulators (replacing `MockTmsWriteLedger`).

## Phase 4 — Adapter containment *(G4)*
### **U4.11** the verification taxonomy (8 outcomes + positive health detection) ⇒ `AC-SAFE-021/023`, `AC-ADPT-012/015` · **U4.1** the pipeline client · **U4.2–U4.5** convert the 4 src sites (`multistep_write`, `discovered_write`, `truckingoffice_write`, `brain_runtime`) · ### **U4.6 DELETE EP-6, EP-7, EP-9, EP-10** · ### **U4.7 remove the `cdp_actuator` import from `orient_tms.py` (EP-8)** · **U4.8** convert EP-1/EP-3 to pipeline clients · ### **U4.9 the CI import gate ON** ⇒ `AC-SEC-013`, `AC-ADPT-002` · **U4.10** orphan detection.
> ### **U4.6 is irreversible by design. Its rollback is NOT "restore the scripts" — it is "the capability stays off." (principle 11)**

## Phases 5–9 *(kernel completion)*
**P5:** U5.1 transactional outbox ⇒ `AC-RACE-006/007`; U5.2 dedup inbox ⇒ `AC-ADPT-010`; U5.3 the 92 contracts + upcaster; U5.4 ### **the `GC-1` golden corpus + pinned digest** ⇒ `AC-EVT-007/008`; U5.5 ### **sandboxed replay — effects structurally unreachable in replay** ⇒ `AC-EVT-011`; ### **U5.6 audit reconstruction (18-field explainability, beliefs-of-that-day)** ⇒ `AC-AUD-*`.
**P6:** U6.1 ### **Work Item (+ the accountable owner)** ⇒ `AC-SAFE-028`; U6.2 Pipeline Instance; U6.3 the 13 machines / 141 transitions ⇒ `AC-MACH-*`; U6.4 ### **the `workflow_runs` SPLIT + the `done` rename**.
**P7:** U7.1 ### **`provenance_class` + R-P1/2/3** ⇒ `AC-SAFE-015/016`, `AC-ADPT-008`; U7.2 content-addressed Evidence; U7.3 Observation; U7.4 ### **the deterministic linker (`AMBIGUOUS` ⇒ human, never a guess)**; U7.5 the `claim` verb rename.
**P8:** U8.1 typed policy ⇒ `AC-CKPT-6-*`; U8.2 ### **compile-or-refuse Rules** ⇒ `AC-WF10-005`; U8.3 the real brake + `BrakeEngaged`; U8.4 Conflict/Expectation/Exception/Compensation ⇒ M7–M10; ### **U8.5 THE `lane` MIGRATION (310 sites → action_class ∪ workflow_id ∪ policy scope)** — mechanical, behavior-free, last; U8.6 `CommandIntent` → Proposal.
**P9:** U9.1–U9.11 the 40 domain entities by family ⇒ `AC-DOM-*`; U9.12 External Entity Mapping; U9.13 field-level authority.

## Phases 10–14 *(the slice — NEEDS DESIGN-PARTNER VALIDATION)*
**P10** W6→W8 no-writes ⇒ `AC-WF6-*`, `AC-FC-005/006/013` (**G5**) · **P11** shadow ⇒ **zero-effect assertion** (**G6**) then human-executed ⇒ ### **`AC-DEG` assertion 5: NEVER claim Neyma executed** (**G7**) · ### **P12 the first supervised live write — gated on G4 RE-RUN LIVE + the physical deletion of EP-6,7,9,10** (**G8**) · **P13** handoffs ⇒ `AC-FC-016` (**G9**) · **P14** bounded autonomy ⇒ the graduation dossier (**G10**).

## Dependency spine *(the only strictly-ordered chain)*
### **U0.2 → U1.2/U1.3 → U2.1 → U2.3 → U3.1 → U3.2 → U3.3 → U4.9 → U4.6 → P12.**
### **Everything else may parallelize. Nothing may jump this chain — every link is a safety precondition of the next, and P12 (the first live write) sits behind ALL of them.**
