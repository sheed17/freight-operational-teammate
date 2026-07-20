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
              └─ docs/architecture/decisions/ADR-001…018       binding decisions
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

## 4. Architecture layer

| Path | Purpose | Authority |
|---|---|---|
| [`architecture/engineering-principles.md`](architecture/engineering-principles.md) | The constitution | **CANONICAL** |
| [`architecture/semantic-model.md`](architecture/semantic-model.md) | Canonical language | **CANONICAL** |
| [`architecture/decisions/ADR-001…ADR-011`](architecture/decisions/) | The 11 core binding decisions | **CANONICAL** |
| [`architecture/decisions/ADR-012…ADR-018`](architecture/decisions/) | The 7 U-REBASELINE-1 decisions: identity/strategy, workflow-authority migration, credential/machine-identity, communications, production topology, tenant & integration lifecycle, and the customer operational graph / TMS-agnostic domain model | **CANONICAL** |
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
| [`specifications/events/`](specifications/events/) | 16 | `registry.md` | **98 event contracts**, F1–F13 |
| [`specifications/adapters/`](specifications/adapters/) | 14 | `registry.md` | 18 adapter boundary contracts |
| [`specifications/workflows/`](specifications/workflows/) | 12 | `registry.md` | **the eleven loops W1–W11** |
| [`specifications/acceptance/`](specifications/acceptance/) | 24 | `registry.md` | **ACCEPTANCE_ORACLE** — the contracts + `release-gates.md` + `traceability.md` |
| [`specifications/operational-system-map.md`](specifications/operational-system-map.md) | 1 | — | **CANONICAL** — the per-tenant operational graph / system map (ADR-018, U-REBASELINE-1) |
| `specifications/*-review.md` | 9 | — | **HISTORICAL** — the hostile review of each layer |

## 6. Implementation control layer

| Path | Purpose | Authority |
|---|---|---|
| [`implementation/CURRENT.md`](implementation/CURRENT.md) | ### **THE single short-form status authority** | **CURRENT_STATUS** |
| [`implementation/IMPLEMENTATION-REGISTRY.yaml`](implementation/IMPLEMENTATION-REGISTRY.yaml) | Work units, status, dependencies, acceptance | **IMPLEMENTATION_CONTROL** |
| [`implementation/PHASE-OUTPUTS.md`](implementation/PHASE-OUTPUTS.md) | What each phase produces and unlocks | **IMPLEMENTATION_CONTROL** |
| [`implementation/LEGACY-DISPOSITION.md`](implementation/LEGACY-DISPOSITION.md) | One disposition per subsystem | **IMPLEMENTATION_CONTROL** |
| [`implementation/implementation-roadmap.md`](implementation/implementation-roadmap.md) | Phases P0–P14, principles, ordering | **IMPLEMENTATION_CONTROL** |
| [`implementation/phase-0-baseline-manifest.yaml`](implementation/phase-0-baseline-manifest.yaml) | Adjudicated current-state facts (machine-checked) | **CURRENT_STATUS** |
| [`implementation/registry.md`](implementation/registry.md) | Human-readable INDEX of the implementation layer — ### **no independent status authority** (H-3); the YAML registry and `CURRENT.md` are authoritative | **EVIDENCE (index)** |
| [`implementation/AUTO-LOADED-GUIDANCE-REVIEW.md`](implementation/AUTO-LOADED-GUIDANCE-REVIEW.md) | The auto-loaded guidance audit — a review of its moment; its live obligations are enforced by guards, not by the document | **HISTORICAL (evidence)** — demoted by U-HANDOFF-1C after its "Reality" row was found carrying a stale suite figure while claiming control authority |
| [`implementation/TOOL-ACCESS-POLICY.md`](implementation/TOOL-ACCESS-POLICY.md) | Broad tool access for formal sessions; research vs authority boundary | **IMPLEMENTATION_CONTROL** |
| [`implementation/U-HANDOFF-1-ACCEPTANCE.yaml`](implementation/U-HANDOFF-1-ACCEPTANCE.yaml) | The executable rehearsal acceptance checklist — **adjudicated 13/13 PASS by U-HANDOFF-1D** from the preserved independent U-HANDOFF-2B evidence | **ACCEPTANCE_ORACLE** |
| [`implementation/U-REBASELINE-1-ACCEPTANCE.yaml`](implementation/U-REBASELINE-1-ACCEPTANCE.yaml) | The executable rebaseline acceptance contract — RB-01..RB-23 PASS, RB-24 PENDING for the independent review | **ACCEPTANCE_ORACLE** |
| [`implementation/IMPLEMENTATION-SURFACE.yaml`](implementation/IMPLEMENTATION-SURFACE.yaml) | Which architecture concepts are implemented vs specification-only | **CURRENT_STATUS** |
| [`implementation/SUITE-RESULT.json`](implementation/SUITE-RESULT.json) | The machine-readable suite-result artifact backing the status record | **CURRENT_STATUS** |
| [`implementation/TRANSITION-EVENT-AUDIT.yaml`](implementation/TRANSITION-EVENT-AUDIT.yaml) | The mechanically-proven transition/event classes; COUNT NEEDS ADJUDICATION at G2 | **CURRENT_STATUS** |
| [`implementation/EFFECT-PATH-INVENTORY.yaml`](implementation/EFFECT-PATH-INVENTORY.yaml) | The exact live-write adjudication (the six, the exclusions, EP-14) | **CURRENT_STATUS** |
| `implementation/release-gate-plan.md` · `pr-sequence.md` · `red-to-green-acceptance-plan.md` · `migration-plan.md` · `data-migration-plan.md` · `effect-entry-point-cutover-plan.md` · `implementation-risk-register.md` · `current-to-target-gap-matrix.md` | Planning detail | **IMPLEMENTATION_CONTROL** |
| `implementation/current-state-inventory.md` | The mechanical recon at reset time | **HISTORICAL** |
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
  `implementation/registry.md` and sequenced by `implementation-roadmap.md`.
- **There is exactly ONE product authority:** `PRODUCT.md`.
- **The chain has a root:** `engineering-principles.md`. It is authorised by nothing above it, which
  is what makes it the constitution rather than a link in a cycle.

## 9. When a document is not listed here

Treat it as **HISTORICAL** and **report it**. A load-bearing document that nobody classified is
exactly the gap this map exists to close, and
[`eval/tests/test_docs_control_system.py`](../eval/tests/test_docs_control_system.py) fails the
build when a root or control document is missing from this map.
