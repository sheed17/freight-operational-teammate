# Implementation Planning Registry

*The index of the implementation-planning layer. ### **Planning artifacts only — NO production code, NO migration files, NO schema changes, NO symbol renames have been performed.***

## Documents
| Doc | Contents |
|---|---|
| [current-state-inventory.md](current-state-inventory.md) | the mechanical recon @ `6057dfe` — 208 py files, 73 src, 50 scripts, 78 tests, ~20.7k LOC; the 8 tables; the deprecated-term surface |
| [current-to-target-gap-matrix.md](current-to-target-gap-matrix.md) | 34 components × {class, target, acceptance, unit, deps, ### **earliest gate blocked**} |
| [implementation-roadmap.md](implementation-roadmap.md) | Phases 0–14 · the 16 principles · ordering · ### **flags · observability · rollback** |
| [migration-plan.md](migration-plan.md) | ### **Safety Task #1** · ledger · checkpoint · containment · ### **semantic code migration** · ### **the first vertical slice** |
| [data-migration-plan.md](data-migration-plan.md) | every persisted concept classified · ### **the ambiguous-effect rule** |
| [effect-entry-point-cutover-plan.md](effect-entry-point-cutover-plan.md) | EP-1…EP-13 · ### **6 production-reachable live-write paths** · cutover mechanisms |
| [pr-sequence.md](pr-sequence.md) | PR-sized units U0.\*–U9.\* + P10–P14 · ### **the dependency spine** |
| [red-to-green-acceptance-plan.md](red-to-green-acceptance-plan.md) | case → status → blocking unit → green phase → gate |
| [release-gate-plan.md](release-gate-plan.md) | phases→G0–G10 · ### **the G4 correction** |
| [implementation-risk-register.md](implementation-risk-register.md) | R-01…R-20 |
| [implementation-planning-review.md](implementation-planning-review.md) | ### **the hostile planning review + the verdict** |
| [phase-0-baseline-manifest.yaml](phase-0-baseline-manifest.yaml) | ### **the adjudicated current-state facts** — every allowance carries a reason, a phase, an owner and a deletion condition |
| [phase-0-implementation-review.md](phase-0-implementation-review.md) | ### **Phase 0 delivered + its findings + the verdict** |
| [phase-1-implementation-review.md](phase-1-implementation-review.md) | ### **Phase 1 delivered — the Commit Key correction + its findings + the verdict** |
| [canonical-corpus-errata-review.md](canonical-corpus-errata-review.md) | ### **the bounded errata pass — 141→134, 92→98, 6→7 tables, U0.3→P8 + the 3 findings in its own work** |

## Phases → gates → units
| Phase | Units | Gate |
|---|---|---|
| ### **0** Baseline & guards | ### **U0.1, U0.2, U0.4 + U0.5–U0.13** *(U0.3 deferred to P8 — see P0-F1)* | ### **G0 — DONE** |
| ### **1** ⛔ **SAFETY TASK #1** | ### **U1.1–U1.6 — DONE** | ### **G0 — AC-SAFE-012/013 GREEN ✔** |
| **2** Tenant-safe ledger | U2.1–U2.5 | → G4 |
| **3** Checkpoint + witness | U3.1–U3.5 | → G4 |
| **4** Adapter containment | U4.1–U4.11 | → G4 · **G3** |
| **5** Outbox + replay | U5.1–U5.6 | **G2** |
| **6** Entities + machines | U6.1–U6.4 | **G1** · → G4 |
| **7** Provenance + binding | U7.1–U7.5 | G1 · → G4 |
| ### **8** Policy, brake, M7–M10 | U8.1–U8.6 | ### **G4 QUALIFIES** |
| **9** Domain projections | U9.1–U9.13 | **G1** |
| **10** ### First slice (W6→W8) | — | **G5** |
| **11** Shadow → human-executed | — | **G6→G7** |
| ### **12** Supervised effects | — | ### **G8 (G4 re-run LIVE)** |
| **13** Multi-loop | — | **G9** |
| **14** Bounded autonomy | — | **G10** |

## The dependency spine *(nothing may jump it)*
### **U0.2 → U1.2/U1.3 → U2.1 → U2.3 → U3.1 → U3.2 → U3.3 → U4.9 → U4.6 → P12**

## Migrations (planned, NOT written)
| ID | Phase | Kind | Dry-run first |
|---|---|---|---|
| **M-1** commit-key backfill | P1 | TRANSFORM | ### **yes — collisions ⇒ MANUAL_REVIEW_REQUIRED** |
| **M-2** tenant-first keys ### **(7 tables — errata: was 6)** | P2 | TRANSFORM | yes |
| **M-3** ledger backfill | P2 | TRANSFORM | yes |
| **M-4** event upcast `v0→v1` | P5 | TRANSFORM | yes |
| **M-5** `workflow_runs` SPLIT | P6 | ### **SPLIT — MERGE_FORBIDDEN** | yes |
| **M-6** evidence content-addressing | P7 | TRANSFORM | yes |
| **M-7** ### historical ambiguous effects | ### **P1/P2** | ### **⇒ `UNKNOWN_OUTCOME` + owner — NEVER inferred success** | yes |

## Cutovers
| ID | Capability | Mechanism | At |
|---|---|---|---|
| **C-1** TMS invoice write | ### **the shared ledger's unique index** | P12 |
| **C-2** TMS payable write | shared ledger | P12+ |
| **C-3** document file | shared ledger | P12 |
| ### **C-4** terminal direct writes (EP-6,7,9,10) | ### **PHYSICAL DELETION** | ### **P4** |
| **C-5** `orient_tms` actuator import (EP-8) | import removed + CI gate | P4 |
| **C-6** mock ledger paths | the existing prod guard | done |

## Risks: **R-01…R-20** · ### **the standing one is R-07** (the 6 live paths are reachable until P4, mitigated only by operator discipline).

## Status
| Layer | Status |
|---|---|
| Architecture (ADR-001…011 + A1–A4) | **FROZEN** |
| Semantic Model · Target Spec Rev 2 | **FROZEN** |
| Specifications (entities, machines, events, domain, adapters, workflows, acceptance) | **FROZEN** |
| ### **Implementation & migration planning** | ### **FROZEN at `9f20b25`** |
| ### **Phase 0 — baseline & migration guards** | ### **COMPLETE (`d33f251`) — the guard suite + adjudicated manifest. Its 3 findings are now CORRECTED by the errata pass.** |
| ### **Canonical Corpus Errata Pass** | ### **COMPLETE — DEF-4/5/6 + P0-F1 corrected; ERRATA 5 made the Phase-0 tree green (it was RED). Corpus only; no code, schema, or behaviour touched.** |
| ### **Phase 1 — Migration Safety Task #1** | ### **COMPLETE — the Commit Key identifies the EFFECT, not the decision. AC-SAFE-012/013 GREEN. FORWARD-ONLY: the amount-keyed derivation is deleted, not deprecated.** |
| ### **Phase 2 — Tenant-safe ledger** | ### **NOT STARTED — by instruction. Unblocked; U2.1 scope corrected to all 7 tables.** |
