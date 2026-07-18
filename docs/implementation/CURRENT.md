# CURRENT — The Repository Status Authority

> ### **This is the ONLY short-form current-status authority in this repository.**
> Every phase review, blocker review and planning document is **historical evidence**. Do not
> reconstruct status by reading them — that is the failure this file exists to prevent.
>
> **Last updated:** durable CLI-control documentation task, on top of commit `7d72498`.

---

## Position

| | |
|---|---|
| **Branch** | `recovery/u2-6bc-atomic-cutover` |
| **Baseline commit** | `7d72498` — *Complete final Phase 2 tenant qualification* |
| **Latest validated tree** | `f2b22f037c814b99b29bc24012f3ddc612ade921` |
| **Suite** | ### **1073 passed · 0 failed · 1 skipped** |
| **The one skip** | Conditional and self-describing: *"no red-by-design cases remain: AC-SAFE-012/013 went green at Phase 1"* |
| **Working tree** | clean |

## Completed phases

| Phase | Status | Evidence |
|---|---|---|
| **P0** — baseline & anti-false-green infrastructure | ### **COMPLETE** | [`phase-0-implementation-review.md`](phase-0-implementation-review.md) · `d33f251` |
| **P1** — correct effect identity (Commit Key) | ### **COMPLETE** | [`phase-1-implementation-review.md`](phase-1-implementation-review.md) · `149c02a`, `da07936` |
| **P2** — tenant-safe persistence | ### **COMPLETE** | [`u2-6bc-blocker-6-final-phase-2-review.md`](u2-6bc-blocker-6-final-phase-2-review.md) · `7d72498` |
| **P3** — checkpoint, witness, claim CAS | ### **NOT STARTED** | — |
| **P4–P14** | **NOT STARTED** | [`PHASE-OUTPUTS.md`](PHASE-OUTPUTS.md) |

## Completed acceptance gates

| Case | Status |
|---|---|
| **AC-SAFE-012** | ### **GREEN** |
| **AC-SAFE-013** | ### **GREEN** |
| **AC-SEC-001** | ### **GREEN at the Phase-2 surfaces** (records, grants, api). Seven surfaces deferred by phase: events (P5), witnesses (P3), leases (P3), mappings (P9), credentials (P4), cache keys (P4), adapter calls (P4). |
| **G0** | passed |
| **G1–G10** | not reached |

## Exact counts *(recomputed mechanically, not transcribed)*

| Quantity | Count |
|---|---|
| Canonical tenant-owned tables | **7** |
| Canonical tables total | **11** |
| Tenant-exempt bookkeeping tables | **3** — `schema_migrations`, `migration_quarantine`, `owner_assertions` |
| `WorkflowStore` methods, tenant-scoped + readiness-gated | **22 / 22** |
| `WorkflowStore` construction sites, all with an explicit tenant | **154** *(plus 8 refusal probes, exempted structurally)* |
| Guard files / guard tests | **25 / 367** |
| Canonical transitions | **134** |
| Canonical emitted events | **98** |
| Canonical loops | **11** |
| Domain entities | **40** · adapters **18** · safety invariants **28** |

## ⛔ Open risks and findings — ALL STILL OPEN

| ID | Finding | Status | Closes at |
|---|---|---|---|
| **R-07** | Ungated live-write paths | ### **OPEN — NOT CONTAINED** | **P4** |
| — | **6 production-reachable live-write paths** — EP-1, EP-3, EP-6, EP-7, EP-9, EP-10 | OPEN | P4 |
| — | **31 direct adapter-import edges** across 18 importer modules | OPEN | P4 |
| — | **24 of 134 transitions cite no event** — a G2 question, unsettled | OPEN | before **P5** |
| — | Hardcoded knowledge-base `tenant="default"` — `ops_control.py` ×5, `action_callback.py:1639` | OPEN | the phase that makes the KB tenant-safe |
| — | Checkpoint Witness + seven-step checkpoint + claim CAS unimplemented | OPEN | **P3** |
| — | Adapter containment unimplemented | OPEN | **P4** |
| — | **No firsthand design-partner observation recorded by any agent** | OPEN | [`design-partner-observations.md`](../product/design-partner-observations.md) |
| — | Repository legacy reduction unfinished | OPEN | [`LEGACY-DISPOSITION.md`](LEGACY-DISPOSITION.md) |

> ### **The only mitigation for R-07 is the operator's one-writer-at-a-time discipline.**
> ### **That is discipline, not a mechanism, and it may NEVER be recorded as containment.**
>
> ### **Phase 2 made tenant ownership real at persistence boundaries.**
> ### **Phase 2 did NOT make external effects safe.**

## Current documentation milestone

**DURABLE CLI-CONTROL DOCUMENTATION** — converting the repository into a self-contained product,
architecture and implementation control system for zero-context agents.
Review: [`durable-cli-control-documentation-review.md`](durable-cli-control-documentation-review.md).

## ✅ The exact next approved work program

### **ZERO-CONTEXT CLI HANDOFF REHEARSAL AND HOSTILE READINESS REVIEW**

Unit `U-HANDOFF-1` in [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml).

It tests whether a clean-session agent, given only this repository, can:

1. identify the product correctly (and **reject** the invoice-processor interpretation)
2. identify the current implementation state correctly
3. identify legacy code correctly
4. identify the next work unit correctly
5. explain that unit's expected outputs correctly
6. **refuse to invent missing product rules**
7. follow acceptance and commit discipline

**This is a rehearsal and review unit. It writes no runtime code.**

## ⛔ What must NOT begin yet

| Not yet | Why |
|---|---|
| ### **Implementation Phase 3** | Requires `U-HANDOFF-1` to pass **and** an independent repository inspection |
| Checkpoint Witness / seven-step checkpoint / claim CAS | P3 content |
| Adapter containment | P4 content |
| Closing R-07 | Only reaching P4 closes it |
| Freight workflow implementation | Requires P6–P9 foundations |
| Deleting legacy production code | Requires the deletion conditions in [`LEGACY-DISPOSITION.md`](LEGACY-DISPOSITION.md) |
| Promoting the W6→W8 slice to validated | It is **provisional** and marked **NEEDS DESIGN-PARTNER VALIDATION**; requires recorded evidence |
| The final formal CLI bootstrap prompt | Requires `U-HANDOFF-1` |

## Blocked future units

Every unit from `U3.1` onward is **BLOCKED** on `U-HANDOFF-1`. See the registry for the full
dependency graph.

## Documents required before proceeding

A session picking up `U-HANDOFF-1` must have read, in order:
[`CLAUDE.md`](../../CLAUDE.md) → [`PRODUCT.md`](../../PRODUCT.md) →
[`ARCHITECTURE.md`](../../ARCHITECTURE.md) → [`CANONICAL-DOCUMENTS.md`](../CANONICAL-DOCUMENTS.md) →
this file → [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml).
