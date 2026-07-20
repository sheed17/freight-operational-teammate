> ## ⛔ INDEX ONLY — NO INDEPENDENT STATUS AUTHORITY
>
> **Design decision (U-HANDOFF-1B, H-3):** this file is a **human-readable index** of the
> implementation layer's documents. The machine-readable registry is
> [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml); the status authority is
> [`CURRENT.md`](CURRENT.md). **No status statement in this file may direct implementation** —
> the independent rehearsal found this file simultaneously claiming Phase 2 COMPLETE and Phase 2
> IN PROGRESS with instructions to begin U2.6B, which is exactly what an index with status
> authority decays into. Row descriptions summarise what each HISTORICAL document says **as of its
> own moment**; a guard fails the build if this file contradicts the canonical registry.

# Implementation Planning Registry

*The index of the implementation-planning layer, and now of the implementation itself.*

> ### **The "planning artifacts only" banner this file used to carry is no longer true, and leaving it would be a lie by omission.** Phases 0–2 have shipped production code, a migration, canonical schema changes and executable guards. What has NOT happened: no symbol renames, no Phase-3 checkpoint or witness, no adapter containment, and **R-07 remains OPEN — NOT CONTAINED**.

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
| [u-handoff-1c-false-green-and-discovery-correction-review.md](u-handoff-1c-false-green-and-discovery-correction-review.md) | ### **U-HANDOFF-1C — the hostile review's six HIGH findings closed: execution-not-attestation finalizer, isolated pytest config + exact node manifest, whole-suite skip enforcement, transitive safety wall, central dynamic inventory + anti-enumeration meta-guard. 44/44 battery. Next: the SECOND hostile review.** |
| [u-handoff-1b-clean-clone-correction-review.md](u-handoff-1b-clean-clone-correction-review.md) | ### **U-HANDOFF-1B — clean-clone reproducibility: hermetic fixtures (the 46-failure false green closed), fail-fast bootstrap, artifact-backed status, registry.md demoted to index, exact inventories (effect paths, transition/event classes, table partition), graph consistency. Next: the SECOND independent rehearsal.** |
| [u-handoff-1a-control-correction-review.md](u-handoff-1a-control-correction-review.md) | ### **U-HANDOFF-1A — the rehearsal's findings corrected: status-reality guard (two-commit convention), tool-access policy, implemented-vs-specified registry, executable rehearsal checklist. Next: the INDEPENDENT rehearsal.** |
| [durable-cli-control-documentation-review.md](durable-cli-control-documentation-review.md) | ### **DURABLE CLI CONTROL — the repository now replaces conversation memory: PRODUCT/ARCHITECTURE/CLAUDE, the authority map over 198 docs, one status authority, 17 work units, 14 legacy dispositions, 68 documentation guards, 34/34 mutations. Next: zero-context handoff rehearsal.** |
| [CURRENT.md](CURRENT.md) | ### **THE single short-form status authority — read this, not the phase reviews** |
| [TOOL-ACCESS-POLICY.md](TOOL-ACCESS-POLICY.md) | broad tool access for formal CLI sessions — research capability vs consequential authority |
| [u-handoff-1d-final-adjudication-review.md](u-handoff-1d-final-adjudication-review.md) | ### **U-HANDOFF-1D — the handoff gate CLOSED: the independent U-HANDOFF-2B hostile review adjudicated, 13/13 PASS; U-REBASELINE-1 registered as the single READY unit. Next: U-REBASELINE-1.** |
| [u-rebaseline-1-product-production-review.md](u-rebaseline-1-product-production-review.md) | ### **U-REBASELINE-1 — the founder product/integration/production rebaseline: ADR-012..017, Delivered Load Closure wedge (HYPOTHESIS), revised P3–P14, PostgreSQL production topology, communications as a core subsystem. RB-01..23 PASS, RB-24 pending the independent review.** |
| [U-REBASELINE-1-ACCEPTANCE.yaml](U-REBASELINE-1-ACCEPTANCE.yaml) | the 24-criterion rebaseline contract (RB-01..23 PASS, RB-24 PENDING) |
| [../product/DESIGN-PARTNER-EVIDENCE-PROGRAM.md](../product/DESIGN-PARTNER-EVIDENCE-PROGRAM.md) | the wedge's required design-partner evidence, accountable sources, fail-closed |
| [../specifications/operational-system-map.md](../specifications/operational-system-map.md) | the per-tenant operational graph / system map (ADR-018): TMS is one node, not the center; TMS-schema-independent domain model |
| [u-handoff-2b-hostile-review-report.md](u-handoff-2b-hostile-review-report.md) | the preserved independent second hostile review (received portion, truncation disclosed) |
| [U-HANDOFF-1-ACCEPTANCE.yaml](U-HANDOFF-1-ACCEPTANCE.yaml) | the 13-criterion executable rehearsal checklist — adjudicated 13/13 PASS by U-HANDOFF-1D |
| [U-REBASELINE-1-ACCEPTANCE.yaml](U-REBASELINE-1-ACCEPTANCE.yaml) | the 24-criterion rebaseline contract (RB-01..RB-24, all PENDING until the unit executes) |
| [IMPLEMENTATION-SURFACE.yaml](IMPLEMENTATION-SURFACE.yaml) | implemented vs specification-only, machine-checked |
| [IMPLEMENTATION-REGISTRY.yaml](IMPLEMENTATION-REGISTRY.yaml) | the work units, statuses and dependencies |
| [PHASE-OUTPUTS.md](PHASE-OUTPUTS.md) | P0–P14: what each phase buys, and what stays prohibited |
| [LEGACY-DISPOSITION.md](LEGACY-DISPOSITION.md) | one disposition per subsystem; no permanent legacy category |
| [AUTO-LOADED-GUIDANCE-REVIEW.md](AUTO-LOADED-GUIDANCE-REVIEW.md) | every auto-loaded file audited and dispositioned |
| [u2-6bc-blocker-6-final-phase-2-review.md](u2-6bc-blocker-6-final-phase-2-review.md) | ### **Blocker 6 CLOSED — PHASE 2 COMPLETE. Suite GREEN (1073/0/1); AC-SEC-001 satisfied at the Phase-2 surfaces; 20 concurrency schedules; 49/49 mutations detected; every guard classified. R-07 still OPEN.** |
| [u2-6bc-blocker-5-migration-matrix-review.md](u2-6bc-blocker-5-migration-matrix-review.md) | ### **Blocker 5 CLOSED — 20 shapes, 10 classified outcomes; found 3 real migration defects** |
| [u2-6bc-blocker-4-tenant-scope-review.md](u2-6bc-blocker-4-tenant-scope-review.md) | ### **Blocker 4 CLOSED — 22/22 methods tenant-scoped; AC-SAFE-012/013 GREEN again** |
| [u2-6bc-blocker-3-schema-readiness-review.md](u2-6bc-blocker-3-schema-readiness-review.md) | ### **Blocker 3 CLOSED — the complete readiness oracle; found 2 real migration defects** |
| [u2-6bc-blocker-2-owner-assertion-review.md](u2-6bc-blocker-2-owner-assertion-review.md) | ### **Blocker 2 CLOSED — auditable owner assertions (who/what/why), recorded before assignment** |
| [u2-6bc-recovery-and-qualification-review.md](u2-6bc-recovery-and-qualification-review.md) | ### **U2.6BC — the recovered snapshot (`42a87e2`): what it implements, the 16 failures, and why NOT READY** |
| [u2-6b-tenant-method-review.md](u2-6b-tenant-method-review.md) | ### **U2.6B — NOT READY: zero methods scoped, by design. The all-or-nothing reasoning + the plan.** |
| [u26b-method-inventory.md](u26b-method-inventory.md) | the exact 22 methods, each with its target SQL and current cross-tenant risk |
| [u2-6a-tenant-construction-review.md](u2-6a-tenant-construction-review.md) | ### **U2.6A — the tenant construction boundary: 146/146 sites explicit, no default. NOT tenant isolation.** |
| [u26-construction-site-inventory.md](u26-construction-site-inventory.md) | the mechanical 146-site inventory + the 22-method audit |
| [phase-2-implementation-review.md](phase-2-implementation-review.md) | ### **Phase 2 — what is built and proven, what is NOT, and why I stopped (verdict: NOT READY)** |
| [phase-1-occurrence-identity-review.md](phase-1-occurrence-identity-review.md) | ### **the closure correction — the free-form `occurrence_key` escape hatch removed; occurrence identity comes from a canonical business occurrence** |
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

### **Status lives in [`CURRENT.md`](CURRENT.md) — nowhere else, including not here.**
As of the U-HANDOFF-1B correction the canonical record is: **P0, P1, P2 COMPLETE · P3 BLOCKED ·
R-07 OPEN — NOT CONTAINED · next approved work: the independent zero-context rehearsal
(U-HANDOFF-1).** If that sentence and `CURRENT.md` ever disagree, `CURRENT.md` is right.

<details><summary>Historical status table (pre-Blocker snapshot — WRONG about Phase 2; retained as evidence)</summary>

The table below is the U2.6B-era snapshot. Its Phase-2 row ("IN PROGRESS — NOT READY … begin
U2.6B") described a real intermediate moment and was superseded by the six U2.6BC blockers and the
Blocker-6 closure. It is preserved because deleting it would erase the record that the
intermediate state existed.

| Layer | Status |
|---|---|
| Architecture (ADR-001…011 + A1–A4) | **FROZEN** |
| Semantic Model · Target Spec Rev 2 | **FROZEN** |
| Specifications (entities, machines, events, domain, adapters, workflows, acceptance) | **FROZEN** |
| ### **Implementation & migration planning** | ### **FROZEN at `9f20b25`** |
| ### **Phase 0 — baseline & migration guards** | ### **COMPLETE (`d33f251`) — the guard suite + adjudicated manifest. Its 3 findings are now CORRECTED by the errata pass.** |
| ### **Canonical Corpus Errata Pass** | ### **COMPLETE — DEF-4/5/6 + P0-F1 corrected; ERRATA 5 made the Phase-0 tree green (it was RED). Corpus only; no code, schema, or behaviour touched.** |
| ### **Phase 1 — Migration Safety Task #1** | ### **COMPLETE + CLOSED — the Commit Key identifies the EFFECT, not the decision. AC-SAFE-012/013 GREEN. The free-form `occurrence_key` escape hatch is REMOVED: identity comes from a canonical occurrence (Payment Application P9 · Compensation/Expectation P8) or the operation fails closed. FORWARD-ONLY.** |
| ### **Phase 2 — Tenant-safe ledger** | ### **IN PROGRESS — NOT READY.** Migration + canonical `effect_grants` schema built and proven against live data (dry-run byte-identical; 120 ambiguous rows quarantined, none guessed; idempotent rerun). ### **INERT — nothing imports it, live schema unchanged.** ### **U2.6A DONE** (146/146 sites explicit, tenant-bound at construction, no default). Blocking: ### **U2.6B — scope all 22 store methods IN ONE PIECE** *(fully specified in `u26b-method-inventory.md`; zero implemented — a mixed store is worse than an unscoped one)*; then **U2.6C** — activate the migration ⇒ `AC-SEC-001`. See `phase-2-implementation-review.md`. |

</details>
