# CURRENT — Where the program stands

> ### **This is the short-form status authority.** Every phase review, blocker review and planning
> document under `docs/implementation/` is **historical evidence**, not status. Do not reconstruct
> status by reading them.
>
> **CI is the authority on whether the repository is green** — `.github/workflows/ci.yml`, run from
> a fresh checkout. This file carries no suite counts, no commit/tree receipts and no finalizer
> state; those were hand-maintained bookkeeping and were removed in the 2026-08 engineering-process
> simplification. The pre-simplification version of this document, with its full narrative history,
> is in git history at `cff82d5`.

**Last updated:** 2026-08-19, at the engineering-process simplification.

---

## Program position

| Phase | Status | Evidence |
|---|---|---|
| **P0** — baseline & anti-false-green infrastructure | **COMPLETE** | [`phase-0-implementation-review.md`](phase-0-implementation-review.md) |
| **P1** — correct effect identity (the Commit Key; the amount is not in it) | **COMPLETE** | [`phase-1-implementation-review.md`](phase-1-implementation-review.md) |
| **P2** — tenant-safe persistence | **COMPLETE** | [`u2-6bc-blocker-6-final-phase-2-review.md`](u2-6bc-blocker-6-final-phase-2-review.md) |
| **P3** — the checkpoint kernel: seven-step atomic checkpoint, unconstructable witness, grant mint + claim CAS, brake admission | **COMPLETE** — 14/14 | [`p3-final-adjudication-review.md`](p3-final-adjudication-review.md) |
| **P4** — adapter containment: the governed write route, the two-key rule at the effect boundary, the CI import gate | **COMPLETE** — 13/14 | [`p4-final-adjudication-report-0891d1a.md`](p4-final-adjudication-report-0891d1a.md) |
| **P5** — canonical events, outbox/inbox, replay isolation, durable timers, production PostgreSQL | **COMPLETE** — 14/14 | [`p5-final-adjudication-report-91ba4e6.md`](p5-final-adjudication-report-91ba4e6.md) |
| **P6** — foundational entities and state machines | **IN PROGRESS** | two landed checkpoints; see below |
| **P7–P14** | **BLOCKED** behind P6 | [`PHASE-OUTPUTS.md`](PHASE-OUTPUTS.md) |

Gates **G0** and **G1**… **G2 is adjudicated** and its seven event obligations are discharged; the
G2 residuals `G2-D4`, `G2-D6`, `G2-D8`, `G2-D9`, `G2-D10` stay open and block nothing. Exact
members and proofs: [`TRANSITION-EVENT-AUDIT.yaml`](TRANSITION-EVENT-AUDIT.yaml).

## P6 — what has landed, and what is owed

**Capability, in one line: every unit of work has an accountable owner — structurally, not by
documentation.** That turns engineering rule 13 from a written rule into a mechanism.

| | |
|---|---|
| **M1 — the Work Item** (`P6-CP-1`, LANDED) | `owner_id` is a FOREIGN KEY into `tenant_humans` (a recorded, attributed authority that must be ACTIVE at assignment), 14 transitions, terminal states final by trigger, OCC versioning, tenant-first. [review](p6-cp1-independent-rereview-report-ca8c070.md) · [adjudication](p6-cp1-targeted-adjudication-report-ca8c070.md) |
| **M2 — the Pipeline Instance** (`P6-CP-2`, LANDED) | One durable attempt per logical effect and the reservation that makes it exclusive; 25 transitions; `UNIQUE(tenant, commit_key) WHERE state NOT IN (terminal)`; `GRANTED`/`CLAIMED` unreachable without a real witness row, a real grant row and P3's untouched claim CAS. **A billing sweep that proposes the same invoice three times bills the customer once, and a TMS write that times out lands in `NEEDS_VERIFICATION` — non-terminal, holding its reservation, moved by no timer — rather than decaying into "it failed" and being billed twice.** [review](p6-cp2-independent-review-report-1aaf943.md) · [re-adjudication](p6-cp2-targeted-readjudication-report-1aaf943.md) |
| **`P6-D11` — the strict-order F2 ordering contract** | **RESOLVED, reviewed, adjudicated, landed.** `events/registry.md` §8 states that strict per-aggregate ordering means **ORDER, never CONTIGUITY**, and every strict-order producer declares `previous_aggregate_version`, so a consumer blocks on an **unapplied predecessor** rather than on an absent version. No canonical event minted; no transition moved. [record](p6-d11-f2-ordering-contract-record.md) · [review](p6-d11-independent-review-report-021a9a2.md) · [adjudication](p6-d11-targeted-adjudication-report-021a9a2.md) |
| **Still owed** | **M3–M13**, 95 of the 134 transitions, gate **G1**, `AC-SAFE-028`. |
| **Not scored** | `criteria_scored` is `[]` on both checkpoints. **A checkpoint is a landed increment, never a phase acceptance.** No P6 criterion is scored and P6 is not COMPLETE. |
| **Posture** | M1 and M2 both **ship dark**: zero production importers, and M2's import closure reaches no effect-capable adapter. |

**`M3` is the next build unit.** It inherits two recorded obligations: **`P6-D24`** — its strict
consumer must supply `drain_handler_for`, or a parked event leaves the park only by M-26 expiry —
and **§8's complete-stream rule**: a strict-order consumer must consume the whole aggregate stream,
never a family subset, because an `IllegalTransitionAttempted` (F14) riding on the strict F2
aggregate can be the declared predecessor of the next F2 event.

M3 is a **tier-2** change under [`CLAUDE.md`](../../CLAUDE.md) §7: builder + one focused
independent review, and CI. It does not need an adjudication chain or a finalizer.

## Risks and standing constraints

| | |
|---|---|
| **R-07 — ungated live-write paths** | **CONTAINED.** The record is in [`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml) (`expected_legacy_paths.status: CONTAINED`). External-effect paths are structurally forced through the governed boundary or fail closed. ### **CONTAINED IS NOT ENABLED:** no production write is enabled, the deployed governed route answers a recorded `ROUTE_NOT_CONFIGURED` refusal, the production `GateRegistry` population stays EMPTY until U8.1/P8, and no autonomy was granted. |
| **Live-write paths** | P0's six production-reachable paths are all cut: EP-6/7/9/10 physically DELETED; EP-3/EP-8/EP-14 cut to structurally read-only surfaces; EP-1's write half routed through the governed write route and the checkpoint kernel. |
| **Adapter imports** | P0's 31 direct adapter-import edges are gone: the boundary-aware gate's effect-capable violation surface is **EMPTY**, positively anchored by inspected sources and authorized detection edges. Enforced by `eval/tests/test_import_gate.py` on every CI run. |
| **Knowledge base** | Hardcoded `tenant="default"` remains at `ops_control.py` (×5) and `action_callback.py::_learn_correction`. Tracked by symbol, never by line number; verified by guard. |
| **Nonblocking debt** | P5: `IR-R5`–`IR-R12`, `ADJ-P5-01`–`ADJ-P5-03`. P6/M1: R-01/R-02/R-03, A-01/A-02/A-03, `P6-D6`, `P6-D8`. P6/M2: `P6-D17`–`P6-D23`, `P6-D9`, `P6-D12`, `P6-D13`. Plus `P6-D24`–`P6-D27` and the G2 residuals. **These are debt rows, and a debt row is a complete deliverable.** Do not open a remediation campaign against them. |

## Tenant-first table partition

Every canonical table is accounted for, and the partition is asserted mechanically against the
migrations on every CI run (`test_bootstrap_hermeticity.py::test_the_canonical_table_partition_is_exact_and_disjoint`).
It is recorded here because the rehearsal's "7 + 3 vs 11" finding was exactly a table quietly
missing from the written account.

| Class | Tables |
|---|---|
| **migrated to tenant-first at P2** (7) | `audit_events`, `delivery_action_claims`, `effect_grants`, `operation_action_claims`, `operation_token_amounts`, `security_events`, `workflow_runs` |
| **already tenant-first** (1) | `autonomous_run_counters` |
| **tenant-exempt, with a stated reason** (3) | `migration_quarantine`, `owner_assertions`, `schema_migrations` |
| **P3 tenant** (2) | `brakes`, `checkpoint_witnesses` |
| **P3 exempt** (1) | `platform_brake` |
| **P5 tenant** (4) | `event_inbox`, `event_outbox`, `inbox_aggregate_cursor`, `pending_references` |
| **P6 tenant — M1** (2) | `tenant_humans`, `work_items` |
| **P6 tenant — M2** (1) | `pipeline_instances` |

P5, P6/M1 and P6/M2 declare **no** tenant-exempt table, and the guard asserts that emptiness rather
than omitting it: an event nobody owns is an event that will eventually be read by the wrong
brokerage.

## ⛔ What must NOT begin

| Not yet | Why |
|---|---|
| **Enabling any external effect on live traffic** | The capability ships dark. Enabling it is a separate, founder-authorized decision, and live supervised writes are P12 behind the undischarged **RR-01**. |
| **Weakening the checkpoint kernel** | `CheckpointPassed` stays unconstructable, the witness table append-only, and the claim CAS's WHERE-clause revalidation may never lose a predicate. |
| **Rebuilding or polishing M1 or M2** | Both are landed and no further code is owed. Their residuals are debt rows. |
| **Marking P6 COMPLETE, or scoring a P6 criterion from a build lineage** | A phase acceptance needs a reviewer who did not build it. That is the one place the independent-review requirement is about a phase rather than a diff. |
| **Implementation Phase 7** (provenance, evidence, observation, claims, identity binding) | Requires P6 COMPLETE. P5's `IR-R9` (`AC-EVT-011` and the `ProvenanceStrengtheningAttempted` F14 emission half) lands there, not earlier. |
| **Freight workflow implementation** | Requires the P6–P9 foundations. |
| **Deleting legacy production code** | Only under the deletion conditions in [`LEGACY-DISPOSITION.md`](LEGACY-DISPOSITION.md). |
| **Promoting the Delivered Load Closure wedge to validated** | It is `NEEDS VALIDATION` and requires design-partner evidence, never inference. |

## How work lands here now

```
implement  →  targeted tests  →  git diff review  →  commit  →  push  →  CI  →  merge
```

No finalizer, no committed suite receipt, no two-commit metadata convention, no preserve refs, no
special Git topology. Review scales with risk — [`CLAUDE.md`](../../CLAUDE.md) §7. Product Driver
(a separate repository) supplies dynamic and adversarial behavioural validation for tier-1 and
tier-2 work.
