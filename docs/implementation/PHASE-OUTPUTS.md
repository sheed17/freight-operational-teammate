# Phase Output Map

> **What each phase actually buys, and what stays forbidden afterwards.**
>
> ### **REBASELINED by U-REBASELINE-1 (ADR-012..017):** the P0–P14 identifiers and safety
> sequencing are preserved; outputs were revised so the program produces a **deployable
> product** — PostgreSQL persistence (P5), communications ingestion (P9) and supervised sends
> (P12), the **Delivered Load Closure** shadow slice (P10, superseding the W6→W8 description),
> production deployment + onboarding + the web control plane (P11), and workflow-authority
> migration (P13). Readiness vocabulary: ADR-016 §3 — "code exists" = `LOCALLY_IMPLEMENTED` only.
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

## The state token in each heading is RESTATED, never established here

Every `## PN — …` heading below opens with one of exactly three tokens — **✅ COMPLETE**,
**🔄 IN PROGRESS — NOT COMPLETE**, **⛔ NOT STARTED** — optionally qualified after it (P4 reads
**✅ COMPLETE — ADJUDICATED**). They mirror the `execution_state` field of
[`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml), which is the machine authority for
unit state, and
[`eval/tests/test_roadmap_completeness_control.py`](../../eval/tests/test_roadmap_completeness_control.py)
fails the build when a heading here disagrees with it. **This file establishes no status.** Its
checkpoint-kernel heading was still asserting the un-started token long after that phase had been
adjudicated complete, and nothing noticed — which is precisely why the tokens are now guarded
rather than hand-maintained.

> ### **`execution_state` is not the same question as `status`.** `status` answers *may this unit
> be worked on, and is it the approved next one* (BLOCKED / READY / IN_PROGRESS / COMPLETE);
> `execution_state` answers *has work actually landed inside it* (NOT_STARTED / IN_PROGRESS /
> COMPLETE). **P5 is `READY` and `NOT_STARTED` at the same time, and both are true**: it is the
> selected unit AND no work has landed in it. `READY` is a selection, never a claim of progress.
> P4 is `COMPLETE` on both axes. See `meta.status_model` in the registry.

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

## U-DOC-1 / U-HANDOFF-1 — Durable control and rehearsal ✅ COMPLETE *(gate closed by U-HANDOFF-1D; the current unit is **U-REBASELINE-1** — see [`CURRENT.md`](CURRENT.md))*

| | |
|---|---|
| **Purpose** | Make the repository able to replace conversation memory, then **prove it empirically** |
| **System capability after** | A zero-context agent can identify the product, the status, the legacy, and the next unit |
| **User-visible capability** | **None** |
| **Safety guarantees after** | Stale guidance can no longer outrank canonical documents; every subsystem has a disposition; every unresolved rule has a safe interim behaviour |
| **Still prohibited** | ### **All of Phase 3.** No checkpoint, no witness, no CAS, no adapter containment |
| **Acceptance gates** | The documentation acceptance suite; the rehearsal's own criteria |
| **Next unlocked** | **P3** — but only after the rehearsal passes *and* an independent inspection agrees |

## P3 — Checkpoint, Witness and claim CAS ✅ COMPLETE

| | |
|---|---|
| **Purpose** | Make the two-key rule real |
| **System capability after** | ### **Commit-once becomes a database constraint at the effect boundary.** Replay becomes structurally inert |
| **User-visible capability** | ### **None.** A customer sees nothing until P4 routes effects through it. **A checkpoint with unconstrained bypass routes around it is theatre** — which is exactly why P4 must follow |
| **Safety guarantees after** | Seven checks in ONE atomic transaction; an unconstructable `CheckpointPassed`; a grant is **necessary but not sufficient** — a fresh matching witness is also required; confusion check at the adapter; `EffectAttempted` emitted **before** the call so orphans are detectable |
| **Still prohibited** | *(HISTORICAL — this row states the state AFTER P3; R-07 was recorded CONTAINED at P4, see below)* ### **R-07 stays OPEN through P3**. The six live-write paths still bypassed all of this |
| **Legacy contained** | None yet — P3 builds the wall, P4 routes traffic through it |
| **Acceptance gates** | The AC-SAFE checkpoint cases |
| **Next unlocked** | P4 |

## P4 — Adapter containment ✅ COMPLETE — ADJUDICATED — **THIS IS WHERE R-07 CLOSED**

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
>
> ### **THAT CONDITION IS NOW MET, AND THE RECORD IS WRITTEN.** P4 is adjudicated COMPLETE at 14/14
> weighted criteria, both finalization passes ran, and a separate content commit afterwards recorded
> `status: CONTAINED` in [`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml) with the
> mechanism named. The guard did not go away — it was **re-pointed**: it now fails the build if the
> CONTAINED record stands while any of its mechanical conditions stops holding (a live or recorded
> violation edge, the two surfaces disagreeing, a production `GateRegistry` populated before Phase 8,
> the deployed callback regaining a direct actuator route, or missing evidence).
>
> ### **CONTAINED IS NOT "ENABLED".** External-effect paths are structurally forced through the
> governed boundary or they fail closed. No production write is enabled, the production
> `GateRegistry` population is EMPTY until U8.1 / P8, and no autonomy of any kind was granted.

## P5 — Canonical events, outbox/inbox, replay isolation + production persistence ⛔ NOT STARTED

| | |
|---|---|
| **Purpose** | Make history a first-class, replayable, inert fact stream |
| **System capability after** | State rebuildable from history; a `GC-1` rebuild digest compared against the pinned one; ### **PostgreSQL as the production transactional store with schema migrations, durable timers and scheduler (ADR-016 — SQLite stays dev/test-only)** |
| **User-visible capability** | None |
| **Safety guarantees after** | ### **Replay cannot mint authority, mint witnesses or grants, or call adapters.** Events are facts, never commands |
| **Still prohibited** | Entities and machines (P6); policy (P8) |
| **Legacy contained** | Legacy state management begins to be displaced |
| **Acceptance gates** | **G2**; `event-and-replay-acceptance.md` |
| **Blocked on** | ### **NOTHING IN THE SPECIFICATION. G2 IS ADJUDICATED AND ITS SEVEN EVENT OBLIGATIONS ARE DISCHARGED.** The predicate is settled and mechanised (interpretation C, HYBRID), all 134 rows carry structured classification, and the 7 transitions that performed durable writes with no canonical event — `PL-7a`, `AP-9`, `CF-7`, `EC-7`, `PO-2`, `PO-3`, `RU-8` — were given 7 **minted** canonical events under founder/architect authority on 2026-08-12 (registry 98 → 105), each discharge re-proven mechanically and each obligation retained in [`TRANSITION-EVENT-AUDIT.yaml`](TRANSITION-EVENT-AUDIT.yaml). ### **P5 IS STILL NOT_STARTED — the block that remains is that no P5 work has been done**, and the G2 residuals `G2-D4`/`D6`/`D8`/`D9`/`D10` stay recorded OPEN |
| **Next unlocked** | P6 |

## P6 — Foundational entities and state machines 🔨 IN PROGRESS — `P6-CP-1` landed, the phase is NOT COMPLETE

| | |
|---|---|
| **Purpose** | Work Item, Pipeline Instance, the 13 machines, 134 transitions |
| **Landed checkpoint** | ### **`P6-CP-1` — machine M1, the Work Item, and ownership as a RECORDED AUTHORITY.** 14 of the 134 transitions as declarative data, `AC-MACH-000`'s bijection by EXACT SET EQUALITY, the 64-pair illegal sweep recorded to audit **and** security, K-1 `decision_ref` resolution, `owner_id` as a FOREIGN KEY into `tenant_humans`. Ships dark. ### **Its FIRST candidate `2ed750e` was REJECTED by a fresh independent review** — the ownership model, transition table, closure, timer, OCC, tenant isolation and P5 reuse were upheld SOUND; the rejection was one material defect class, evidence of a refusal keyed on the identity of a transition that did not happen (F-01 repeated illegal-transition evidence; F-02 an ownerless park). ### **The accepted candidate is `ca8c070`:** a fresh targeted INDEPENDENT re-review by a session that neither implemented nor remediated it returned ACCEPT ([report](p6-cp1-independent-rereview-report-ca8c070.md)), and a SEPARATE third session returned ADJUDICATE PASS ([report](p6-cp1-targeted-adjudication-report-ca8c070.md)); 41/41 mutants caught. ### **A CHECKPOINT IS NOT AN ACCEPTANCE: NO P6 criterion is scored and the phase is not complete** ([record](p6-u1-work-item-ownership-implementation-record.md)) |
| **Still owed for the phase** | the **Pipeline Instance** (M2, 25 transitions), **M3–M13** (95 transitions), and with them `AC-EVT-003` — which discharges only when all 134 land |
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

## P9 — Freight-domain projections, mappings and communications ingestion ⛔ NOT STARTED

| | |
|---|---|
| **Purpose** | The 40 domain entities and External Entity Mapping with field-level authority |
| **System capability after** | Freight concepts modelled canonically; per-field authoritative sources; ### **inbound email/SMS ingested as evidence (ADR-015) — correlated to tenants/loads/Work Items, commitments extracted with provenance, expected responses as Expectations** |
| **User-visible capability** | None yet |
| **Safety guarantees after** | A disagreement with an external system is an observation to reconcile, never a silent overwrite |
| **Still prohibited** | The vertical slice (P10) |
| **Blocked on** | ### **V-21 — the order/load/movement/leg/stop cardinality question blocks any schema** |
| **Acceptance gates** | **G1**; `domain-model-acceptance.md` |
| **Next unlocked** | P10 |

## P10 — Delivered Load Closure: shadow slice ⛔ NOT STARTED

| | |
|---|---|
| **Purpose** | The wedge outcome (PRODUCT.md §15, spanning parts of W5/W6/W7/W8/W10): delivery detection → required documents → reconciliation → billing readiness, with communications **drafted, never sent** |
| **System capability after** | One complete canonical loop chain end-to-end |
| **User-visible capability** | ### **FIRST REAL USER VALUE.** A brokerage sees delivered loads carried to billing-ready with documents, evidence and drafted follow-ups attached |
| **Safety guarantees after** | ### **NO WRITES, NO SENDS.** Read-only by construction |
| **Still prohibited** | Any external write |
| **Blocked on** | ### **V-W1 — whether Delivered Load Closure is the right wedge is UNVALIDATED** ([`DESIGN-PARTNER-EVIDENCE-PROGRAM.md`](../product/DESIGN-PARTNER-EVIDENCE-PROGRAM.md)) |
| **Acceptance gates** | **G5** |
| **Next unlocked** | P11 |

## P11 — Production foundation, onboarding, control plane + shadow operation ⛔ NOT STARTED

| | |
|---|---|
| **Purpose** | ### **Deployed staging/pilot environments (ADR-016), tenant + integration onboarding and the thin web control plane (ADR-017)**; live reads, zero effects; the human executes and Neyma captures evidence |
| **System capability after** | Shadow-vs-human diff rate measured — in a deployed environment, with onboarding, credential lifecycle (ADR-014) and connection health real |
| **User-visible capability** | Neyma proposes; the human executes; the human sees whether it would have been right |
| **Safety guarantees after** | Zero effects by construction |
| **Still prohibited** | Any write by Neyma |
| **Acceptance gates** | **G6 → G7** |
| **Next unlocked** | P12 |

## P12 — Supervised external effects and communications ⛔ NOT STARTED

| | |
|---|---|
| **Purpose** | The first live gated writes AND ### **outbound email/SMS sends (ADR-015)** through the full kernel, in production under supervision |
| **System capability after** | Grant-backed, witness-gated, verified-by-readback external effects |
| **User-visible capability** | ### **Neyma writes to approved systems and sends real communications** — verifiably, under a human's authority, with delivery states verified |
| **Safety guarantees after** | The `UNKNOWN_OUTCOME` rate is instrumented; ### **a rising rate is automatic demotion**; wrong actions target **ZERO**, and any occurrence demotes |
| **Still prohibited** | Unattended operation; multi-loop expansion |
| **Acceptance gates** | **G8**; ### **G4 re-run LIVE** |
| **Next unlocked** | P13 |

## P13 — Multi-loop expansion and workflow-authority migration ⛔ NOT STARTED

| | |
|---|---|
| **Purpose** | Additional loops plus the 10 atomic cross-loop handoffs; ### **the ADR-013 authority-migration model implemented — a customer may deliberately migrate a workflow's authority to Neyma, with all 13 recorded fields** |
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
