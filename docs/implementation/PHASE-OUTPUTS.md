# Phase Output Map

> **What each phase actually buys, and what stays forbidden afterwards.**
> A phase is not "some work in an area". It is a specific change in what the system can do and what
> it can no longer do wrong.

## ⚠️ Two different roadmaps exist. Do not mix them.

| Roadmap | Status | Where |
|---|---|---|
| ### **Implementation Phases P0–P14, gates G0–G10** | ### **CURRENT — the only one in force** | [`implementation-roadmap.md`](implementation-roadmap.md) |
| The original architecture-to-handoff programme (ADRs → specs → acceptance → implementation plan, each layer hostilely reviewed) | **COMPLETE** — it produced the canonical corpus and ended when implementation began | `docs/architecture/`, `docs/specifications/` |
| The 8-stage roadmap ("Stage 1 … Stage 8") | ### **SUPERSEDED — do not use** | `docs/PRODUCT_ROADMAP.md` |
| The owner-readiness ladder | **HISTORICAL** — a third vocabulary, not current | `docs/OWNER_OPERATOR_READINESS.md` |

> ### **"Phase" is overloaded in this repository.** Legacy files say "Stage 5", the README once said
> "Phase 1 demo", and the owner-readiness docs have their own phases. **When this repository says
> Phase N without qualification, it means Implementation Phase PN below.**

---

## P0 — Baseline and anti-false-green infrastructure ✅ COMPLETE

| | |
|---|---|
| **Purpose** | Know exactly what is true before changing anything, and make a false green detectable |
| **System capability after** | Guards recompute facts and diff them against an adjudicated manifest |
| **User-visible capability** | **None** |
| **Safety guarantees after** | A guard that asserts nothing now fails. Every allowance carries a reason, phase, owner and deletion condition |
| **Still prohibited** | Everything. P0 changes no runtime behaviour |
| **Legacy removed/contained** | None — P0 only *records* |
| **Acceptance gates** | **G0** |
| **Next unlocked** | P1 |

## P1 — Correct effect identity ✅ COMPLETE

| | |
|---|---|
| **Purpose** | Make the Commit Key identify the **effect**, not the decision's contents |
| **System capability after** | A retry of one logical effect is recognised as that same effect |
| **User-visible capability** | **None yet** — but the double-invoice defect is now structurally impossible |
| **Safety guarantees after** | ### **The amount is provably not in the Commit Key.** Occurrence identity comes from a canonical business occurrence, so a caller cannot manufacture a new identity per attempt |
| **Still prohibited** | Multi-tenant operation; any ungated effect |
| **Legacy removed/contained** | `operation_commit_key` deleted; the free-form occurrence escape hatch removed |
| **Acceptance gates** | **AC-SAFE-012, AC-SAFE-013 GREEN** |
| **Next unlocked** | P2 |

## P2 — Tenant-safe persistence ✅ COMPLETE

| | |
|---|---|
| **Purpose** | Make the tenant real at every persistence boundary |
| **System capability after** | Two brokerages can share a database with no cross-tenant read, write or disclosure |
| **User-visible capability** | **None yet.** ### **This is a safety phase, and it is honest to say a customer would notice nothing.** |
| **Safety guarantees after** | Tenant required at construction, validated against sentinels, first in every key, enforced by composite FKs with column order checked; historical ownership only by recorded human assertion; readiness reads what the DB **enforces** |
| **Still prohibited** | ### **Ungated external effects — R-07 is untouched.** No checkpoint, no witness, no grant claim |
| ### **Explicitly** | ### **Phase 2 did NOT make external effects safe.** It made ownership of data real; the effect boundary is P3–P4 |
| **Legacy removed/contained** | Global `document_hash` uniqueness gone; the global Commit Key ledger gone; `tenant` parameters removed from store methods |
| **Acceptance gates** | **AC-SEC-001 GREEN** at the Phase-2 surfaces (7 deferred by phase) |
| **Next unlocked** | U-DOC-1 → U-HANDOFF-1 |

## U-DOC-1 / U-HANDOFF-1 — Durable control and rehearsal ⬅ **CURRENT**

| | |
|---|---|
| **Purpose** | Make the repository able to replace conversation memory, then **prove it empirically** |
| **System capability after** | A zero-context agent can identify the product, the status, the legacy, and the next unit |
| **User-visible capability** | **None** |
| **Safety guarantees after** | Stale guidance can no longer outrank canonical documents; every subsystem has a disposition; every unresolved rule has a safe interim behaviour |
| **Still prohibited** | ### **All of Phase 3.** No checkpoint, no witness, no CAS, no adapter containment |
| **Acceptance gates** | The documentation acceptance suite; the rehearsal's own criteria |
| **Next unlocked** | **P3** — but only after the rehearsal passes *and* an independent inspection agrees |

## P3 — Checkpoint, Witness and claim CAS ⛔ NOT STARTED

| | |
|---|---|
| **Purpose** | Make the two-key rule real |
| **System capability after** | ### **Commit-once becomes a database constraint at the effect boundary.** Replay becomes structurally inert |
| **User-visible capability** | ### **None.** A customer sees nothing until P4 routes effects through it. **A checkpoint with unconstrained bypass routes around it is theatre** — which is exactly why P4 must follow |
| **Safety guarantees after** | Seven checks in ONE atomic transaction; an unconstructable `CheckpointPassed`; a grant is **necessary but not sufficient** — a fresh matching witness is also required; confusion check at the adapter; `EffectAttempted` emitted **before** the call so orphans are detectable |
| **Still prohibited** | ### **R-07 stays OPEN.** The six live-write paths still bypass all of this |
| **Legacy contained** | None yet — P3 builds the wall, P4 routes traffic through it |
| **Acceptance gates** | The AC-SAFE checkpoint cases |
| **Next unlocked** | P4 |

## P4 — Adapter containment ⛔ NOT STARTED — **THIS IS WHERE R-07 CLOSES**

| | |
|---|---|
| **Purpose** | Route every external effect through the boundary, then close the door |
| **System capability after** | ### **An external effect without a grant becomes structurally impossible.** Orphan-adapter detection at Sev-0 |
| **User-visible capability** | None directly — but this is the phase after which supervised live operation becomes conceivable |
| **Safety guarantees after** | ### **R-07 CLOSES.** 31 adapter-import edges converted or removed; the 6 production-reachable live-write paths deleted or de-actuated; the CI import gate ON |
| **Still prohibited** | Freight workflows; autonomy of any kind |
| **Legacy removed** | ### **EP-6, EP-7, EP-9, EP-10 physically DELETED.** EP-8 loses its actuator import. EP-1/EP-3 become pipeline clients |
| **Acceptance gates** | `adapter-boundary-acceptance.md`; the import gate |
| **Next unlocked** | P5 |

> ### **R-07 may not be marked CONTAINED before this phase completes.** Not by a plan, not by a
> policy, not by operator discipline. A guard fails the build if anyone writes `CONTAINED` early.

## P5 — Canonical events, outbox/inbox, replay isolation ⛔ NOT STARTED

| | |
|---|---|
| **Purpose** | Make history a first-class, replayable, inert fact stream |
| **System capability after** | State rebuildable from history; a `GC-1` rebuild digest compared against the pinned one |
| **User-visible capability** | None |
| **Safety guarantees after** | ### **Replay cannot mint authority, mint witnesses or grants, or call adapters.** Events are facts, never commands |
| **Still prohibited** | Entities and machines (P6); policy (P8) |
| **Legacy contained** | Legacy state management begins to be displaced |
| **Acceptance gates** | **G2**; `event-and-replay-acceptance.md` |
| **Blocked on** | ### **The transition/event completeness finding must be adjudicated first** — COUNT NEEDS ADJUDICATION, 4 classes, [`TRANSITION-EVENT-AUDIT.yaml`](TRANSITION-EVENT-AUDIT.yaml) |
| **Next unlocked** | P6 |

## P6 — Foundational entities and state machines ⛔ NOT STARTED

| | |
|---|---|
| **Purpose** | Work Item, Pipeline Instance, the 13 machines, 134 transitions |
| **System capability after** | ### **Every unit of work has an accountable owner — structurally, not by convention** |
| **User-visible capability** | None yet |
| **Safety guarantees after** | A Work Item with no owner is a Sev-0 condition; the Pipeline Instance becomes the reservation |
| **Still prohibited** | Freight projections (P9); policy (P8) |
| **Legacy contained** | ### **The second orchestration system starts being retired** — `action_callback.py` and the routing layer |
| **Acceptance gates** | **G1**; `AC-SAFE-028` |
| **Next unlocked** | P7 |

## P7 — Provenance, Evidence, Observations, Claims, Identity Binding ⛔ NOT STARTED

| | |
|---|---|
| **Purpose** | Make where-a-fact-came-from structural |
| **System capability after** | Content-addressed Evidence; a deterministic linker; first-class Conflicts |
| **User-visible capability** | Escalations arrive with evidence attached, traceably |
| **Safety guarantees after** | ### **`MODEL_INFERRED` cannot authorise a consequential action, and `OWNER_ASSERTED` cannot be silently overwritten — enforced rather than documented** |
| **Still prohibited** | Policy and autonomy (P8) |
| **Legacy contained** | ### **The knowledge-base `tenant="default"` finding CLOSES HERE** |
| **Acceptance gates** | **G1**; `AC-SAFE-015/016` |
| **Next unlocked** | P8 |

## P8 — Policy, Rule, Brake, Conflict, Expectation, Exception, Compensation ⛔ NOT STARTED

| | |
|---|---|
| **Purpose** | Typed policy, compile-or-refuse rules, and a real brake |
| **System capability after** | Admission control per action class with caps and time boxes |
| **User-visible capability** | ### **Exceptions become a managed queue with owners** rather than things discovered late |
| **Safety guarantees after** | The gate decision is never null; ### **the brake becomes admission control instead of a flag checked by convention**; *a prompt string is not a policy* |
| **Still prohibited** | Autonomy (P14); live effects (P12) |
| **Legacy contained** | Review/approval surfaces rewritten; reconciliation rewritten as Expectations/Exceptions |
| **Acceptance gates** | ### **G4 QUALIFIES HERE — not at P4** |
| **Next unlocked** | P9 |

## P9 — Freight-domain projections and mappings ⛔ NOT STARTED

| | |
|---|---|
| **Purpose** | The 40 domain entities and External Entity Mapping with field-level authority |
| **System capability after** | Freight concepts modelled canonically; per-field authoritative sources |
| **User-visible capability** | None yet |
| **Safety guarantees after** | A disagreement with an external system is an observation to reconcile, never a silent overwrite |
| **Still prohibited** | The vertical slice (P10) |
| **Blocked on** | ### **V-21 — the order/load/movement/leg/stop cardinality question blocks any schema** |
| **Acceptance gates** | **G1**; `domain-model-acceptance.md` |
| **Next unlocked** | P10 |

## P10 — First vertical slice: W6 → W8 ⛔ NOT STARTED

| | |
|---|---|
| **Purpose** | Document intake → packet → eligibility → prepared invoice |
| **System capability after** | One complete canonical loop chain end-to-end |
| **User-visible capability** | ### **FIRST REAL USER VALUE.** A brokerage sees a prepared invoice assembled from real documents with evidence attached |
| **Safety guarantees after** | ### **NO WRITES.** Read-only by construction |
| **Still prohibited** | Any external write |
| **Blocked on** | ### **V-W1 — whether W6→W8 is actually the right slice is UNVALIDATED** |
| **Acceptance gates** | **G5** |
| **Next unlocked** | P11 |

## P11 — Shadow mode and human-executed operation ⛔ NOT STARTED

| | |
|---|---|
| **Purpose** | Live reads, zero effects; then the human executes and Neyma captures evidence |
| **System capability after** | Shadow-vs-human diff rate measured |
| **User-visible capability** | Neyma proposes; the human executes; the human sees whether it would have been right |
| **Safety guarantees after** | Zero effects by construction |
| **Still prohibited** | Any write by Neyma |
| **Acceptance gates** | **G6 → G7** |
| **Next unlocked** | P12 |

## P12 — Supervised external effects ⛔ NOT STARTED

| | |
|---|---|
| **Purpose** | The first live gated write through the full kernel |
| **System capability after** | Grant-backed, witness-gated, verified-by-readback external effects |
| **User-visible capability** | ### **Neyma writes to the TMS** — once, verifiably, under a human's authority |
| **Safety guarantees after** | The `UNKNOWN_OUTCOME` rate is instrumented; ### **a rising rate is automatic demotion**; wrong actions target **ZERO**, and any occurrence demotes |
| **Still prohibited** | Unattended operation; multi-loop expansion |
| **Acceptance gates** | **G8**; ### **G4 re-run LIVE** |
| **Next unlocked** | P13 |

## P13 — Multi-loop expansion ⛔ NOT STARTED

| | |
|---|---|
| **Purpose** | Additional loops plus the 10 atomic cross-loop handoffs |
| **System capability after** | More of the back office carried |
| **User-visible capability** | ### **The product starts to feel like an operational teammate rather than one workflow** |
| **Safety guarantees after** | Per-loop capability flags; handoffs are atomic |
| **Still prohibited** | Autonomy |
| **Blocked on** | each loop's freight rules require design-partner validation |
| **Acceptance gates** | **G9** |
| **Next unlocked** | P14 |

## P14 — Bounded autonomy ⛔ NOT STARTED

| | |
|---|---|
| **Purpose** | Per action class, capped, time-boxed, revocable autonomy |
| **System capability after** | Specific action classes proceed without per-action approval |
| **User-visible capability** | ### **The back office runs itself for the classes that have earned it** — and only those |
| **Safety guarantees after** | Revocable by construction; the brake still refuses admission |
| **Still prohibited** | ### **PERMANENTLY: graduating away the authorization assertion.** ADR-003 is PERMANENT PRODUCT TRUTH — an authorization assertion requires human confirmation and **no autonomy level ever removes it** |
| **Acceptance gates** | **G10**; the graduation dossier |
| **Next unlocked** | — this is the destination |

---

## The shape of the whole programme

| Phases | What they are |
|---|---|
| **P0–P2** ✅ | **Foundations** — know the truth, identify effects correctly, own data per tenant |
| **P3–P5** | ### **THE SAFETY WALL** — make effects impossible without authority. **Loop-independent, so no missing customer evidence blocks them** |
| **P6–P9** | **The canonical model** — entities, machines, provenance, policy, freight domain |
| **P10–P11** | **First value, no risk** — a real loop, read-only, then shadow |
| **P12–P14** | **Earned trust** — supervised effects, expansion, then bounded autonomy |

> ### **Every phase ships DARK** — code deployed, capability flag OFF — so that **deploy and enable
> are two separate, separately-reviewed decisions.** The brake is armed in every environment from
> P3 forward, including test.
