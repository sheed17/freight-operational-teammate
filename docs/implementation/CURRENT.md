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

**Last updated:** 2026-08-25, at the `P6-CP-4` (M4) landing.

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
| **P6** — foundational entities and state machines | **IN PROGRESS** | four landed checkpoints; see below |
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
| **M3 — the External Effect / Effect Grant** (`P6-CP-3`, LANDED) | One `effect_grants` row, eight states, one machine; the single atomic CAS that is the only serialization point between a decision and the outside world. Reuses P3's kernel for mint (EF-1) and the claim CAS (EF-2) — the checkpoint stays the one effect authority — and owns the outcome aspect (EF-3…EF-5) and the canonical `EF-*` event stream the kernel only observes. Discharges its two inherited obligations: **P6-D24** (its strict consumer supplies `drain_handler_for`) and **§8's complete-stream rule** (blocks on an unapplied F14 predecessor). Ships dark: zero production importers; only the probe imports it. **Behavioural checks are executed by CI (`.github/workflows/ci.yml`) on every push — not a committed receipt (CLAUDE.md §0 forbids those)**: `eval/tests/test_phase6_external_effect.py` (46 test functions, 49 parametrized cases) via `pytest eval`; the deterministic `scripts/probe_phase6_external_effect.py` (`behaviours as specified, 0 wrong`) and the `scripts/mutate_phase6_external_effect.py` battery (9/9 caught) via the `effect-grant` job. The machine (`external_effect.py`) and migration (`phase6_external_effects.py`) are unchanged since the build commit `4b87557`; the later commits are probe-only observability corrections and this CI wiring, none touching the machine or the migration. ### **A LANDED INCREMENT, NEVER A PHASE ACCEPTANCE.** It cites the on-disk **focused independent review by a session that did not build it** (CLAUDE.md §7, tier-2), which returned **SUPPORTED, confidence 0.82** against this exact tree with two `minor`, nonblocking findings: [review](p6-cp3-independent-review-report-5f9779f.md). That reviewer was read-only, so it verified the structural conformance and the ship-dark posture itself and **corroborated** the behavioural results from evidence captured against the same tree rather than re-executing them; it observed **no CI result**, and none is claimed here. |
| **M4 — the Approval** (`P6-CP-4`, LANDED) | One `approvals` row, eight states, one machine, eleven transitions (`AP-1`…`AP-9`, an exact set match with §14), and the `fp_v1` fingerprint that makes "the human agreed to THIS" a fact a database can `CHECK`. **A broker approves £2,850 and the TMS says £3,100 at claim time: the approval is not weaker, it is `VOID_ON_DRIFT` with a field-level diff, no grant, no effect** — and because `provenance_class` and `evidence_condition` are INSIDE the fingerprint, the same amount believed for a different reason voids too. `granted_by` is a FOREIGN KEY into `tenant_humans` plus a `CHECK`: a model cannot grant, a counterparty cannot grant. `GRANTED → CONSUMED` is one CAS co-committed with M3's claim through P3's kernel, so **M3 stays the single effect authority** and M4 mints no gate decision (CLAUDE.md rule 17). `UNIQUE(tenant, commit_key) WHERE state IN ('REQUESTED','GRANTED')` — at most one live approval per commit key. A frozen approval (`AP-9`) is quarantined and **no timer unfreezes it**; `G2-D15` is preserved, not closed. Ships dark: zero production importers, only the probe imports it, nothing joins it to an outbound channel. ### **A LANDED INCREMENT, NEVER A PHASE ACCEPTANCE.** It cites the on-disk **focused independent review by a session that did not build it** (CLAUDE.md §7, **tier-1** — the approval lifecycle), which returned **SUPPORTED, confidence 0.86** against this exact tree with **zero findings** and zero adjudications: [review](p6-cp4-independent-review-report-1524fc3.md). Unlike M3's read-only reviewer, **this one executed the product**: 16 commands it ran itself reproduced the probe (`behaviours as specified, 0 wrong`), the mutation battery (**10/10 caught**), the 35-test M4 suite, the DDL introspection and the dark-posture scans. Product Driver independently exercised 14/14 scenarios (406 assertions, 0 failed). ### **CI DID NOT CONCLUDE `SUCCESS` ON THIS COMMIT** — run `32801579476` concluded **`cancelled`**: both full suites (py3.11, py3.12) and the M3 effect-grant job passed, and the *Safety invariants (fast)* job hit its declared 30-minute job timeout with no test failure in its log. **That is not green, and nothing here claims it is** — see §6 of the review report and residual `P6-D32`. |
| **Still owed** | **M5–M13**, 71 of the 134 transitions, gate **G1**, `AC-SAFE-028`. **M5 is the next build checkpoint.** (The transition figure is derived, not carried: M1's 14 + M2's 25 + M3's 13 + M4's 11 = 63 of 134 written, so 71 remain. The `95` this cell read until the `P6-CP-4` landing was the post-M2 figure and went stale at the M3 landing.) |
| **Not scored** | `criteria_scored` is `[]` on all four landed checkpoints. **A checkpoint is a landed increment, never a phase acceptance.** No P6 criterion is scored, and P6 has not reached phase acceptance (registry `status: READY`, `execution_state: IN_PROGRESS`). |
| **Posture** | M1, M2, M3 and M4 all **ship dark**: zero production importers; M2's/M3's import closure reaches no effect-capable adapter, and nothing joins M4 to an outbound channel. **No production effect is enabled by any of them.** |

**`M3` has received its one focused independent review and is LANDED.** It discharged the two
obligations it inherited: **`P6-D24`** — its strict consumer supplies `drain_handler_for`, so a
parked event no longer leaves the park only by M-26 expiry — and **§8's complete-stream rule**: the
consumer blocks on an unapplied predecessor, so an `IllegalTransitionAttempted` (F14) riding the
strict aggregate is a legible member of the stream rather than a phantom gap. The build session's
own evidence (targeted tests, the probe, and the 9/9 mutation battery) never certified the unit; the
review that did is [`p6-cp3-independent-review-report-5f9779f.md`](p6-cp3-independent-review-report-5f9779f.md),
by a session that did not build M3, against commit `5f9779f` / tree `e0aff5f5`.

M3 is a **tier-2** change under [`CLAUDE.md`](../../CLAUDE.md) §7: builder + **one focused
independent review** (by a session that did not build it), and CI. That is satisfied. It needs no
adjudication chain and no finalizer, and none may be run for it. Two `minor` findings are
**recorded, not actioned**: the reviewer was read-only, so the behavioural results are
corroborated rather than reviewer-reproduced; and the illegal
`(state × trigger)` sweep is exercised at representative points rather than exhaustively enumerated
— a **gate G1** phase-acceptance item, not an M3 defect. Landing M3 scores no P6 criterion.

**`M4` has received its one focused independent review and is LANDED as `P6-CP-4`.** The review is
[`p6-cp4-independent-review-report-1524fc3.md`](p6-cp4-independent-review-report-1524fc3.md), by a
session that did not build M4, against commit `1524fc3` / tree `542fbe44` on a clean tree it
confirmed itself: **SUPPORTED, confidence 0.86, zero findings, zero adjudications, fourteen criteria
PASS and none `CANNOT_DETERMINE`.** M4 is **tier-1** under [`CLAUDE.md`](../../CLAUDE.md) §7 — the
approval lifecycle — so it owes builder evidence, **one** focused independent review by someone who
did not write it, mutation proof that the guard can fail, and CI. The first three are discharged:
that reviewer **executed the product** rather than only reading it, and the 10/10 mutation battery
proves each load-bearing guard can actually fail. ### **THE CI CLAUSE IS NOT DISCHARGED, AND IS
RECORDED AS UNDISCHARGED RATHER THAN ASSERTED.** Run `32801579476` on this commit concluded
**`cancelled`** — the *Safety invariants (fast)* job expired against its declared `timeout-minutes:
30` with no test failure in its log, while both full suites and the M3 effect-grant job passed. **The
workflow is not green and this document does not say it is.** The founder chose to land on the
evidence that exists, treating the cancellation as a non-product CI runtime limitation; that is
recorded as a decision, not as a verification (`P6-D32`). Four `minor` items are **recorded, not
actioned** — `P6-D31` (the §3.9 authority seam, reported and unresolved), `P6-D32` (no green CI
conclusion), `P6-D33` (CI runs no M4 probe or mutation job), `P6-D34` (the run's evaluator prose
contradicts its own structured review record) — and **none is a reviewer finding**; the review
returned none. Landing M4 scores no P6 criterion. **The next build checkpoint is M5.**

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
| **P6 tenant — M4** (2) | `approvals`, `approval_signatures` |

P5, P6/M1, P6/M2 and P6/M4 declare **no** tenant-exempt table, and the guard asserts that emptiness
rather than omitting it: an event nobody owns is an event that will eventually be read by the wrong
brokerage, an approval scoped to no brokerage is a consent nobody gave.

## ⛔ What must NOT begin

| Not yet | Why |
|---|---|
| **Enabling any external effect on live traffic** | The capability ships dark. Enabling it is a separate, founder-authorized decision, and live supervised writes are P12 behind the undischarged **RR-01**. |
| **Weakening the checkpoint kernel** | `CheckpointPassed` stays unconstructable, the witness table append-only, and the claim CAS's WHERE-clause revalidation may never lose a predicate. |
| **Rebuilding or polishing M1, M2, M3 or M4** | All four are landed and no further code is owed. Their residuals are debt rows. |
| **Declaring P6's phase acceptance, or scoring a P6 criterion, from a build lineage** | A phase acceptance needs a reviewer who did not build it. That is the one place the independent-review requirement is about a phase rather than a diff — and P6 has not reached it. |
| **Implementation Phase 7** (provenance, evidence, observation, claims, identity binding) | Requires P6's phase acceptance first. P5's `IR-R9` (`AC-EVT-011` and the `ProvenanceStrengtheningAttempted` F14 emission half) lands there, not earlier. |
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
