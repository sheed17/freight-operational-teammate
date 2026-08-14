# Canonical Document Authority Map

> **Purpose: to make it impossible for a stale invoice-processing roadmap to outrank the current
> product definition.** This repository's documentation spans two eras. Roughly a quarter
> of them describe an earlier, narrower product. They are kept as evidence — they record real work
> and real lessons — but **they may not direct current implementation.**

**How to use this file:** before treating any document as authority for a decision, find it here.
If it is not `CANONICAL`, `CURRENT_STATUS`, `IMPLEMENTATION_CONTROL` or `ACCEPTANCE_ORACLE`,
**it cannot authorise an implementation decision.**

---

## Authority levels

| Level | May authorise decisions? | Meaning |
|---|---|---|
| **CANONICAL** | ✅ **Yes** | Binding truth. Product, architecture and specification. |
| **CURRENT_STATUS** | ✅ Yes (for status only) | What is true about the repository right now. |
| **IMPLEMENTATION_CONTROL** | ✅ Yes (for sequencing) | What may be built next, and in what order. |
| **ACCEPTANCE_ORACLE** | ✅ Yes (for correctness) | The executable contract a unit must satisfy. |
| **EVIDENCE** | ⚠️ Supporting only | Records observations. Cannot decide. |
| **HISTORICAL** | ❌ **No** | Accurate when written. Superseded now. Read for context. |
| **SUPERSEDED** | ❌ **No** | Actively wrong. Replaced by a named successor. |
| **NEEDS_VALIDATION** | ❌ **No** | Contains open questions. Cannot be built on. |
| **QUARANTINED_GUIDANCE** | ❌ **No** | Would actively misdirect an agent. Retained, disarmed, labelled. |

> **The ordering rule:** `CANONICAL` beats everything. Within CANONICAL, the layer chain in §1
> decides: a lower layer may refine a higher one, never contradict it.
>
> ### **No HISTORICAL document ever outranks a CANONICAL one** — regardless of how detailed,
> confident or recent it looks.

---

## 1. The canonical authority chain

```
docs/architecture/engineering-principles.md                    the constitution
  └─ docs/product/{freight-discovery, operating-model}.md      domain truth
      └─ PRODUCT.md                                            ← the root product authority
          └─ docs/architecture/semantic-model.md               the language
              └─ docs/architecture/decisions/ADR-001…019       binding decisions
                  └─ docs/architecture/target-system-specification.md
                      └─ docs/specifications/{entities, state-machines, events,
                                              domain-entities, adapters, workflows}/
                          └─ docs/specifications/acceptance/   contracts + gates
                              └─ docs/implementation/          the phased build
```

`ARCHITECTURE.md` and `PRODUCT.md` are **entry points into this chain**, not replacements for it.
Where a root file and a detailed spec disagree on detail, **the detailed spec wins**; where they
disagree on *product identity*, **`PRODUCT.md` wins.**

---

## 2. Root control documents

| Path | Purpose | Authority | Supersedes | When to read |
|---|---|---|---|---|
| [`CLAUDE.md`](../CLAUDE.md) | How agents work here | **CANONICAL** | agent status blocks in `AGENTS.md`, `.claude/agents/*` | **First, always** |
| [`PRODUCT.md`](../PRODUCT.md) | What Neyma is | **CANONICAL** | `docs/NEYMA_VISION.md`, `docs/PRODUCT_ROADMAP.md` | Before any product-shaped decision |
| [`ARCHITECTURE.md`](../ARCHITECTURE.md) | Architecture entry point | **CANONICAL** | `docs/AGENTIC_ARCHITECTURE.md` | Before any design decision |
| [`docs/CANONICAL-DOCUMENTS.md`](CANONICAL-DOCUMENTS.md) | This map | **CANONICAL** | — | When unsure whether a doc is authority |
| [`README.md`](../README.md) | Repo orientation | **EVIDENCE** | — | For setup and navigation only |
| [`AGENTS.md`](../AGENTS.md) | Codex compatibility entry | **EVIDENCE** | — | Defers to `CLAUDE.md` |

## 3. Product layer

| Path | Purpose | Authority | Notes |
|---|---|---|---|
| [`product/operating-model.md`](product/operating-model.md) | How a brokerage operates; the eleven loops | **CANONICAL** | "Every future architecture must faithfully implement this model" |
| [`product/freight-discovery.md`](product/freight-discovery.md) | Domain research, every claim labelled | **CANONICAL (evidence)** | Claims inherit their epistemic labels |
| [`product/OPEN-VALIDATION-ITEMS.md`](product/OPEN-VALIDATION-ITEMS.md) | Unresolved rules + safe interim behaviour | **CANONICAL** | **Consult before implementing any freight rule** |
| [`product/design-partner-observations.md`](product/design-partner-observations.md) | What is actually known, by source class | **EVIDENCE** | May not be upgraded to fact by an agent |
| [`product/DESIGN-PARTNER-EVIDENCE-PROGRAM.md`](product/DESIGN-PARTNER-EVIDENCE-PROGRAM.md) | The evidence the wedge requires, accountable sources, fail-closed behavior (U-REBASELINE-1) | **CANONICAL** | Specifies required evidence; is not itself evidence, and never a READY coding unit |
| [`product/OPERATIONAL-USE-CASE-COVERAGE.yaml`](product/OPERATIONAL-USE-CASE-COVERAGE.yaml) | The one operational use-case coverage matrix — every major use case classified, with role/loop/authority/evidence/closure/phase/tier (U-REBASELINE-1A) | **CANONICAL** | Scope, not proof; freight rules stay NEEDS VALIDATION; no mode claimed validated |
| [`product/FREIGHT-OPERATING-VISION.md`](product/FREIGHT-OPERATING-VISION.md) | The complete quote-to-cash product vision, expansion path, one-shared-system principle, product boundaries and reusable narrative | **CANONICAL (navigation)** | Consolidation/entry-point; **holds no authority independent of `PRODUCT.md` and its cited sources; creates no new product decision.** On conflict the source wins |
| [`product/FREIGHT-CAPABILITY-MAP.md`](product/FREIGHT-CAPABILITY-MAP.md) | The 18 freight capability areas (objective/triggers/inputs/work/outputs/systems/evidence/exceptions/approval/phase/loop/autonomy) | **CANONICAL (navigation)** | Defers classification/phase/tier to `OPERATIONAL-USE-CASE-COVERAGE.yaml`; states nothing as implemented |
| [`product/QUOTE-TO-CASH-LIFECYCLE.md`](product/QUOTE-TO-CASH-LIFECYCLE.md) | The end-to-end load lifecycle across the eleven loops, with work-items/evidence/policy/effects per stage | **CANONICAL (navigation)** | Defers loop boundaries/closure/handoffs to the workflow registry |
| [`product/OPERATIONAL-LOOPS.md`](product/OPERATIONAL-LOOPS.md) | Capability→loop coverage for W1–W11 + the recorded loop-gap analysis | **CANONICAL (navigation)** | **Proposes no new loop, rename, split or merge**; records gaps as owning-phase debt |
| [`product/AUTONOMY-MATRIX.md`](product/AUTONOMY-MATRIX.md) | Per-capability autonomy ceilings + high-risk classes, mapped onto the ADR-010 gate decisions | **CANONICAL (navigation)** | Defers enforcement to `ADR-010`/`ADR-003`; nothing is autonomous today |
| [`product/NEYMA-OPERATOR.md`](product/NEYMA-OPERATOR.md) | The Neyma Operator (top-level coordinating + conversational + implementation-learning role), the four operator modes, the customer-discovery lifecycle, the workflow/policy-learning & change process, and the Operator→P5–P14 phase mapping | **CANONICAL (navigation)** | Consolidation/entry-point; **holds no authority independent of `PRODUCT.md`, `ADR-019`/`017`/`018`/`013`/`010` and its cited sources; creates no new product decision, no new loop, no new source of truth, no new effect authority.** States nothing as implemented; on conflict the source wins |

## 4. Architecture layer

| Path | Purpose | Authority |
|---|---|---|
| [`architecture/engineering-principles.md`](architecture/engineering-principles.md) | The constitution | **CANONICAL** |
| [`architecture/semantic-model.md`](architecture/semantic-model.md) | Canonical language | **CANONICAL** |
| [`architecture/decisions/ADR-001…ADR-011`](architecture/decisions/) | The 11 core binding decisions | **CANONICAL** |
| [`architecture/decisions/ADR-012…ADR-019`](architecture/decisions/) | The 8 U-REBASELINE-1 decisions: identity/strategy, workflow-authority migration, credential/machine-identity, communications, production topology, tenant & integration lifecycle, customer operational graph / TMS-agnostic domain model, and the persistent conversational operations layer | **CANONICAL** |
| [`architecture/target-system-specification.md`](architecture/target-system-specification.md) | Target architecture, Rev 2 | **CANONICAL** |
| [`architecture/stream-b-architectural-lessons.md`](architecture/stream-b-architectural-lessons.md) | Lessons L-A…L-D, self-marked **BINDING** | **CANONICAL** |
| [`architecture/live-effect-entrypoint-inventory.md`](architecture/live-effect-entrypoint-inventory.md) | Entry points reaching the live TMS | **CURRENT_STATUS** |
| `architecture/architecture-review.md` · `architecture-correction-plan.md` · `target-spec-revision-report.md` · `wave-2-review.md` · `wave-4-review.md` · `current-state-reconciliation.md` · `repository-baseline-audit.md` · `tms-read-cache-safety-review.md` · `working-tree-separation-plan.md` · `stream-b-review.md` | The hostile reviews that gated each layer | **HISTORICAL** |

> **ADR-003 is marked PERMANENT PRODUCT TRUTH**: an authorization assertion requires human
> confirmation and cannot be graduated away by any autonomy level. It is not revisable by
> implementation convenience.

## 5. Specification layer

All of these are **CANONICAL**. Each family has a registry that is the *sole* canonical index for
its names.

| Family | Files | Registry | Contains |
|---|---|---|---|
| [`specifications/entities/`](specifications/entities/) | 18 | `00-conventions.md` | 17 platform primitives |
| [`specifications/domain-entities/`](specifications/domain-entities/) | 12 | `registry.md` | 40 freight entities in families |
| [`specifications/state-machines/`](specifications/state-machines/) | 14 | `registry.md` | 13 machines, **134 transitions** |
| [`specifications/events/`](specifications/events/) | 16 | `registry.md` | **105 event contracts**, F1–F13 |
| [`specifications/adapters/`](specifications/adapters/) | 14 | `registry.md` | 18 adapter boundary contracts |
| [`specifications/workflows/`](specifications/workflows/) | 12 | `registry.md` | **the eleven loops W1–W11** |
| [`specifications/acceptance/`](specifications/acceptance/) | 24 | `registry.md` | **ACCEPTANCE_ORACLE** — the contracts + `release-gates.md` + `traceability.md` |
| [`specifications/operational-system-map.md`](specifications/operational-system-map.md) | 1 | — | **CANONICAL** — the per-tenant operational graph / system map (ADR-018, U-REBASELINE-1) |
| `specifications/*-review.md` | 9 | — | **HISTORICAL** — the hostile review of each layer |

## 6. Implementation control layer

| Path | Purpose | Authority |
|---|---|---|
| [`implementation/CURRENT.md`](implementation/CURRENT.md) | ### **THE single short-form status authority** | **CURRENT_STATUS** |
| [`implementation/PROGRESS-PROTOCOL.md`](implementation/PROGRESS-PROTOCOL.md) | The founder build-status protocol: report format, evidence-based %, readiness tiers, session-end rule (U-REBASELINE-1) | **IMPLEMENTATION_CONTROL** |
| [`implementation/PROGRAM-WEIGHTS.yaml`](implementation/PROGRAM-WEIGHTS.yaml) | Approved phase program weights + weighted acceptance template + readiness checklists | **IMPLEMENTATION_CONTROL** |
| [`implementation/BUILD-STATUS.yaml`](implementation/BUILD-STATUS.yaml) | The finalizer-derived progress snapshot (percentages, tier, blockers) — defers to CURRENT.md for commit/tree/suite | **CURRENT_STATUS** |
| [`implementation/IMPLEMENTATION-REGISTRY.yaml`](implementation/IMPLEMENTATION-REGISTRY.yaml) | Work units, their three state fields (`status` selection · `execution_state` execution · `checkpoint_state` review), dependencies, acceptance, and the P13 sub-unit decomposition | **IMPLEMENTATION_CONTROL** |
| [`implementation/CAPABILITY-TRACEABILITY.yaml`](implementation/CAPABILITY-TRACEABILITY.yaml) | ### **The promise-to-implementation-to-evidence spine** — every promised capability traced to its owning loop/surface, phase, implementation unit, acceptance contracts and release gate, plus the mechanical full-roadmap completeness rule | **IMPLEMENTATION_CONTROL** — traceability and sequencing only; it creates no product decision and states nothing as implemented |
| [`implementation/PHASE-OUTPUTS.md`](implementation/PHASE-OUTPUTS.md) | What each phase produces and unlocks | **IMPLEMENTATION_CONTROL** |
| [`implementation/LEGACY-DISPOSITION.md`](implementation/LEGACY-DISPOSITION.md) | One disposition per subsystem | **IMPLEMENTATION_CONTROL** |
| [`implementation/implementation-roadmap.md`](implementation/implementation-roadmap.md) | Phases P0–P14, principles, ordering | **IMPLEMENTATION_CONTROL** |
| [`implementation/phase-0-baseline-manifest.yaml`](implementation/phase-0-baseline-manifest.yaml) | Adjudicated current-state facts (machine-checked) | **CURRENT_STATUS** |
| [`implementation/registry.md`](implementation/registry.md) | Human-readable INDEX of the implementation layer — ### **no independent status authority** (H-3); the YAML registry and `CURRENT.md` are authoritative | **EVIDENCE (index)** |
| [`implementation/AUTO-LOADED-GUIDANCE-REVIEW.md`](implementation/AUTO-LOADED-GUIDANCE-REVIEW.md) | The auto-loaded guidance audit — a review of its moment; its live obligations are enforced by guards, not by the document | **HISTORICAL (evidence)** — demoted by U-HANDOFF-1C after its "Reality" row was found carrying a stale suite figure while claiming control authority |
| [`implementation/TOOL-ACCESS-POLICY.md`](implementation/TOOL-ACCESS-POLICY.md) | Broad tool access for formal sessions; research vs authority boundary | **IMPLEMENTATION_CONTROL** |
| [`implementation/U-HANDOFF-1-ACCEPTANCE.yaml`](implementation/U-HANDOFF-1-ACCEPTANCE.yaml) | The executable rehearsal acceptance checklist — **adjudicated 13/13 PASS by U-HANDOFF-1D** from the preserved independent U-HANDOFF-2B evidence | **ACCEPTANCE_ORACLE** |
| [`implementation/U-REBASELINE-1-ACCEPTANCE.yaml`](implementation/U-REBASELINE-1-ACCEPTANCE.yaml) | The executable rebaseline acceptance contract — **RB-01..RB-24 ALL PASS**; RB-24 awarded by U-REBASELINE-1A from the INDEPENDENT review; the unit is COMPLETE | **ACCEPTANCE_ORACLE** |
| [`implementation/IMPLEMENTATION-SURFACE.yaml`](implementation/IMPLEMENTATION-SURFACE.yaml) | Which architecture concepts are implemented vs specification-only | **CURRENT_STATUS** |
| [`implementation/SUITE-RESULT.json`](implementation/SUITE-RESULT.json) | The machine-readable suite-result artifact backing the status record | **CURRENT_STATUS** |
| [`implementation/TRANSITION-EVENT-AUDIT.yaml`](implementation/TRANSITION-EVENT-AUDIT.yaml) | The G2 event contract, the mechanically-proven classification of all 134 transitions, and the seven founder/architect-gated event obligations; G2 PARTIALLY DISCHARGED | **CURRENT_STATUS** |
| [`implementation/EFFECT-PATH-INVENTORY.yaml`](implementation/EFFECT-PATH-INVENTORY.yaml) | The exact live-write adjudication (the six, the exclusions, EP-14) | **CURRENT_STATUS** |
| `implementation/release-gate-plan.md` · `pr-sequence.md` · `red-to-green-acceptance-plan.md` · `migration-plan.md` · `data-migration-plan.md` · `effect-entry-point-cutover-plan.md` · `implementation-risk-register.md` · `current-to-target-gap-matrix.md` | Planning detail | **IMPLEMENTATION_CONTROL** |
| [`implementation/integration-topology-procedure.md`](implementation/integration-topology-procedure.md) | R-21 — the STANDING OBLIGATION on how a finalized pair reaches `main`: fast-forward only, no merge commit above a certified content commit. Binding at integration, enforced by `test_integration_topology.py` | **IMPLEMENTATION_CONTROL** |
| `implementation/u5-7-8-event-transport-evidence.md` | `P5-CP-1`'s implementer evidence: the transactional outbox and dedup inbox as built — design, the strict-ordering defect found and fixed during the build (a UNIQUE index would have made EF-2's `GrantClaimed` + `EffectAttempted` co-emission uninsertable at P6), the crash/duplicate/ordering/tenant scenarios exercised, and what was deliberately NOT built. True as of its own commit; scores nothing | **HISTORICAL (evidence)** |
| `implementation/u5-3-event-contracts-evidence.md` | `U5.3`'s implementer evidence: the 118 canonical event contracts (105 machine-emitted F1–F13 + 13 audit/security F14) DERIVED mechanically from `events/registry.md` §3/§5/§8 and the F1–F14 family files rather than transcribed; the validator, its two §6 modes, and the honest account of why the canonical corpus registers zero upcasters (every contract is at `v1`); the three defects found during the build — including that the pre-existing U5.7/U5.8 transport battery was green against a `CheckpointPassed` payload the specification never declared; the independent review that REJECTED the first candidate on five blocking defects (three derivation errors that made canonical contracts unsatisfiable, two authority holes) and the remediation that followed — including holding the corpus as JSON so that NO safety guard needed amending. True as of its own commit; **scores nothing** | **HISTORICAL (evidence)** |
| `implementation/u5-4-5-6-replay-and-audit-evidence.md` | `U5.4+U5.5+U5.6`'s implementer evidence, as ONE increment because the acceptance spec couples them (`AC-EVT-007`'s oracle IS the corpus, `AC-EVT-008`'s IS a replay): the deterministic per-aggregate fold and its pinned `GC-1` digest, replay proven side-effect free by IMPORT CLOSURE rather than by counting zeros, `explain()` reconstructing the eighteen audit fields from beliefs-of-that-day, and `AC-EVT-009`'s v1→v2→v3 chain proven through the real replay path with a TEST-ONLY contract — no production version was minted, and GC-1 stays purely canonical. Records four defects this build shipped and its own battery caught, including an arrival-ordered fold that would have made the pinned digest a property of one delivery. True as of its own commit; **scores nothing** | **HISTORICAL (evidence)** |
| `implementation/current-state-inventory.md` | The mechanical recon at reset time | **HISTORICAL** |
| `implementation/p4-remediation-handoff.md` | The P4 remediation builder's handoff for a fresh independent re-review: what was changed, what was measured, what remains blocked. It certifies nothing, records no status, and is superseded by the review it hands off to. Its §6 gate-result numbers are WRONG — recorded as finding RR-02; the artifact is right and the handoff is stale | **HISTORICAL (evidence)** |
| `implementation/p4-final-adjudication-report-0891d1a.md` | The SEPARATE FINAL ADJUDICATION of P4 implementation candidate `0891d1a`, by a session that did not implement, remediate or review it. Verdict ACCEPT P4 FOR FINALIZATION; its §F is the verbatim source of the fourteen weighted results now in the registry. `.sha256` sidecar alongside; preserved at `refs/preserve/p4-final-adjudication-0891d1a`. It adjudicated `0891d1a` — **not** the closure commit that carries it | **HISTORICAL (evidence)** |
| `implementation/p4-first-finalization-pass-report-86306d5.md` | The execution record of the ONE canonical finalizer run on `0891d1a`: exit 0, one lock owner, clean-clone PASS, metadata commit `86306d5` touching exactly the five authorized status files. The sole evidence behind the `canonical_finalizer` criterion. `.sha256` sidecar alongside. It records **no** receipt for any later commit | **HISTORICAL (evidence)** |
| `implementation/p4-closure-content-topology-determination.md` | The legal-topology determination that fixed WHERE each remaining P4 act may land under the two-commit convention — and the record of a builder that correctly created NO candidate rather than an illegal one. Its forward-looking §4/§9 guidance was partly overtaken by the finalizer pass that followed it | **HISTORICAL (evidence)** |
| `implementation/p4-closure-candidate-targeted-adjudication-report-42ea24c.md` | The SEPARATE TARGETED ADJUDICATION of the P4 acceptance-closure content commit `42ea24c`, by a session that did not implement, remediate, review or finalize it. Verdict ACCEPT CLOSURE CANDIDATE FOR SECOND FINALIZATION. It is the source of findings **F-TR-01…F-TR-07**, **ADJ-01** and **ADJ-02**, and it ratified the `canonical_finalizer` transcription. `.sha256` sidecar alongside; preserved at `refs/preserve/p4-closure-targeted-adjudication-42ea24c`. It adjudicated `42ea24c` — **not** the R-07 closure commit that carries it | **HISTORICAL (evidence)** |
| `implementation/p4-second-finalization-pass-report-06ebfdb3.md` | ### **A RECONSTRUCTION, NOT AN EXECUTION RECORD.** The evidence report for the SECOND canonical finalizer run (metadata commit `06ebfdb3`), authored **after** the run by an independent attestation session that did **not** execute `finalize_status.py`. Every fact carries an explicit evidence class (`[GIT]`, `[RECEIPT]`, `[RUN-ARTIFACT]`, `[SCRATCHPAD]`, `[UNAVAILABLE]`). It may be cited **only** for facts independently established by Git objects, canonical receipts, lock/run artifacts and preserved scratchpad evidence — **never as contemporaneous finalizer testimony**. The original process PID and the Product Driver run/session IDs are marked `[UNAVAILABLE]`: documented limitations, **not** blanks to be filled in. `.sha256` sidecar alongside; preserved at `refs/preserve/p4-second-finalization-report-06ebfdb3` | **HISTORICAL (evidence)** |
| `implementation/p4-r07-closure-handoff.md` | The R-07 closure builder's handoff for a fresh TARGETED INDEPENDENT REVIEW of the R-07 containment + documentation-consistency content commit. It certifies nothing, adjudicates nothing, runs no finalizer, and is superseded by the review it hands off to | **HISTORICAL (evidence)** |
| [`implementation/u-rebaseline-review-1-independent-report.md`](implementation/u-rebaseline-review-1-independent-report.md) | The preserved INDEPENDENT product/production rebaseline review — the evidence RB-24 required | **HISTORICAL (evidence)** |
| **FAMILY RULE — every review document**: any `docs/implementation/*.md` matching `*review*.md` (phase reviews `phase-*-review`, blocker reviews `u2-6*`, control-correction reviews `durable-cli-*`, `u-handoff-*review`, errata and planning reviews) | Evidence of what was done and found, true as of its own commit | **HISTORICAL (evidence)** — automatically, by family; a review needs no individual row here, and a guard verifies every implementation doc is either individually classified or covered by this rule |
| `implementation/u26-construction-site-inventory.md` · `u26b-method-inventory.md` | Mechanical inventories | **HISTORICAL (evidence)** |

> **Phase reviews are evidence, not status.** They were true when written. **Do not reconstruct
> current status by reading them** — that is what `CURRENT.md` exists to prevent.

## 7. ⛔ The pre-reset `docs/` root

**Every file directly in `docs/` predates the architectural reset (2026-07-09 onward) and sits
entirely outside the canonical chain.** They contain real operational knowledge and real proof of
live work, and they also contain the product definition this program exists to replace.

| Path | Authority | Why |
|---|---|---|
| `NEYMA_VISION.md` | ### **SUPERSEDED** by [`PRODUCT.md`](../PRODUCT.md) | Defines the first teammate family as *Document & Data Entry* and the first workflow as *carrier invoice reconciliation* |
| `PRODUCT_ROADMAP.md` | ### **SUPERSEDED** by [`PHASE-OUTPUTS.md`](implementation/PHASE-OUTPUTS.md) | The 8-stage roadmap. **The single largest source of agent misdirection in the repository.** |
| `AGENTIC_ARCHITECTURE.md` | ### **SUPERSEDED** by [`ARCHITECTURE.md`](../ARCHITECTURE.md) | Core loop is `classify → extract → link`; predates all 11 ADRs |
| `DESIGN_PARTNER_PILOT.md` | ### **QUARANTINED_GUIDANCE** | *"Neyma should prove it can read documents… before it is allowed to write into a TMS"* — the clearest stale product definition |
| `INTERNAL_DOGFOOD_PILOT.md` | **QUARANTINED_GUIDANCE** | Scopes the product to *supervised carrier-payables document review* |
| `CODEX_HANDOFF.md` · `CODEX_FIX_HANDOFF.md` | **QUARANTINED_GUIDANCE** | Defines the product as AP/AR document ops + TMS automation |
| `TMS_ONBOARDING.md` | **HISTORICAL** | TMS-automation framing; names AscendTMS, since replaced by TruckingOffice |
| `stages.txt` | ### **SUPERSEDED** by [`PHASE-OUTPUTS.md`](implementation/PHASE-OUTPUTS.md) | The original 8-stage prose roadmap. **Sat unclassified at the repository ROOT until U-HANDOFF-1B (H-4)** — moved here and bannered |
| `OWNER_OPERATOR_ROADMAP.md` | ### **SUPERSEDED** | Claims to be *"the canonical 'where are we' doc"* — **dated 2026-07-06, before the reset.** A stale authority claim, now void. |
| `OWNER_OPERATOR_READINESS.md` · `OWNER_DEMAND_CATALOG.md` | **HISTORICAL** | Owner-readiness ladder — a *third* phase vocabulary. Not current. |
| `BUILD_SUPERVISION_PROTOCOL.md` | **HISTORICAL** | Superseded by §6 of `CLAUDE.md` |
| `LIVE_WRITE_PROOF.md` | **EVIDENCE** | Genuine record of a proven live write. Valuable; not authority. |
| `FIRST_DESIGN_PARTNER_RASHEED.md` · `WHEN_DESIGN_PARTNER_DATA_ARRIVES.md` · `DESIGN_PARTNER_DEPLOYMENT_PACKAGE.md` | **EVIDENCE** | Inputs to [`design-partner-observations.md`](product/design-partner-observations.md) |
| `DEPLOYMENT.md` · `PRODUCTION_HANDOFF.md` · `PRODUCTION_PILOT.md` · `CLIENT_1_RUNBOOK.md` · `CHANNEL_ONBOARDING.md` · `SESSION_RUNTIME_MIGRATION.md` · `SYNTHETIC_CORPUS.md` | **HISTORICAL** | Operational runbooks for the pre-reset runtime |

> ### **None of these 23 files may authorise an implementation decision.**
> They are preserved because deleting them would destroy the record of what was built, what was
> proven live, and what was learned. **Preserved ≠ authoritative.**

## 8. Circular-authority and duplicate-authority rules

- **There is exactly ONE current-status authority:** `docs/implementation/CURRENT.md`.
  `phase-0-baseline-manifest.yaml` is the machine-checked *fact* record beneath it, not a rival.
  Any other file claiming to be "the where-are-we doc" is stale by definition.
- **There is exactly ONE implementation registry:** `IMPLEMENTATION-REGISTRY.yaml`, indexed by
  `implementation/registry.md` and sequenced by `implementation-roadmap.md`. It is also the
  **machine authority for unit state** — `CURRENT.md` remains the short-form human status
  authority, and the two are guarded against each other. `CAPABILITY-TRACEABILITY.yaml` traces
  capabilities onto those units and is **not** a third status authority: every row names the
  `current_truth_source` it defers to.
- **There is exactly ONE product authority:** `PRODUCT.md`.
- **The chain has a root:** `engineering-principles.md`. It is authorised by nothing above it, which
  is what makes it the constitution rather than a link in a cycle.

## 9. When a document is not listed here

Treat it as **HISTORICAL** and **report it**. A load-bearing document that nobody classified is
exactly the gap this map exists to close, and
[`eval/tests/test_docs_control_system.py`](../eval/tests/test_docs_control_system.py) fails the
build when a root or control document is missing from this map.
