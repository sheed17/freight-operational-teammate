> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This is evidence of a past moment, not status.** It is an INDEPENDENT REVIEW: it set no
> acceptance criterion, marked no phase complete, closed no risk, enabled nothing and authorized no
> external effect. It reviewed the `P6-CP-4` candidate (machine **M4 — the Approval**) at content
> commit `1524fc3a32243c86d3c5fb510659e8a6282caf04` (tree
> `542fbe447c521540d227e8e6b6b9c1d5a493a06b`, branch `p5/u5-1-g2-spec-correction`, working tree
> clean) and returned **SUPPORTED, confidence 0.86**.
>
> ### **IT DID NOT REVIEW THE COMMIT THAT CARRIES IT.** The landing commit that brought this file
> in-tree did not exist when the review was performed. Nothing here may be cited as an independent
> review of that commit.
>
> ### **P6-CP-4 IS A CHECKPOINT, NOT A PHASE ACCEPTANCE.** P6 is **NOT COMPLETE**, no P6 acceptance
> criterion is scored, and P7 is not unlocked. M4 continues to **ship dark**.
>
> ### **NO ADJUDICATION FOLLOWED THIS REVIEW, AND NONE IS OWED.** M4 is tier-1 under
> [`CLAUDE.md`](../../CLAUDE.md) §7 — the approval/grant lifecycle — which requires builder + **one
> focused independent review by someone who did not write it**, mutation proof that the guard can
> fail, and CI. The adjudication chains and finalizer rituals cited by the `P6-CP-1` and `P6-CP-2`
> records were retired in the 2026-08 engineering-process simplification and must not be revived on
> the strength of those older artifacts.
>
> ### **CI DID NOT CONCLUDE `SUCCESS` ON THIS COMMIT, AND THIS RECORD DOES NOT PRETEND OTHERWISE.**
> See §6. Read that section before citing this document as evidence of a green repository.

# P6-CP-4 — FOCUSED INDEPENDENT REVIEW — candidate `1524fc3`

**Verdict: `SUPPORTED` · confidence `0.86` · findings `0` · adjudications `0`**

| | |
|---|---|
| **Reviewed tree** | commit `1524fc3a32243c86d3c5fb510659e8a6282caf04`, tree `542fbe447c521540d227e8e6b6b9c1d5a493a06b`, branch `p5/u5-1-g2-spec-correction`, **0 tracked-dirty files, 0 untracked** |
| **Reviewer lineage** | A session that did not build M4. The review record states `inherited_builder_context: false` and the ledger `independent: true`; reviewer session `3111f388-90d8-41f9-810a-2a6804651335`, builder session `05011ca5-b7e9-40d0-97cb-b264fe4d6c99` |
| **Performed** | `2026-08-25T02:11:01+00:00` |
| **Source artifact** | Product Driver run `20260825-000934`, `iteration-03/independent-review.json` (separate repository, `neyma-product-driver`), sha256 `61f7ea725bb789273154204ffc28b21feeb44404b07ad83c91dac46c94977909`. Its prose is quoted verbatim below; nothing is upgraded, softened or summarised into a stronger claim |
| **Adjudications recorded** | **none** (`adjudications: []`) |
| **Findings** | **none** (`findings: []`). §5 records the nonblocking items this landing identified from the run's own evidence — they are **not** reviewer findings and are not presented as such |
| **Scope declared by the run** | `P6/M4`, checkpoint `P6-CP-4`, `claims_phase_completion: false` |
| **Reviewer executed the product** | **Yes.** `evidence_reproduced: true`. This is the material difference from the `P6-CP-3` review, which was read-only — see §3 |

---

## 1. The verdict, verbatim

> "Reviewed P6/M4 (the Approval machine) at HEAD 1524fc3 / tree 542fbe44, working tree clean — I
> confirmed the exact state myself. The flagged concern (independent review of a 'safety guard'
> change) resolves cleanly: the two corrections weaken no guard. Correction 1 relocates the
> eight-state enumeration from a table-level CHECK to an inline column CHECK without changing the
> vocabulary (I confirmed the inline CHECK yields exactly the eight canonical states, no SUPERSEDED,
> no ninth). Correction 2 (the HEAD commit) is a probe-only change that STRENGTHENS the
> database-invariants case: it inserts a second live approval for the same (tenant, commit_key) and
> prints 'AT MOST ONE LIVE APPROVAL PER COMMIT KEY' only on a genuine DB refusal, failing with a MISS
> marker otherwise. I reproduced the load-bearing runtime evidence: the full probe ('behaviours as
> specified, 0 wrong', exit 0), the mutation battery (10/10 caught), the test suite (35 passed), the
> corrected focused case (prints the invariant lines), and the M3 probe (0 wrong — no regression). I
> structurally confirmed the dark posture (zero production importers of approval; only
> probe_phase6_approval.py reaches it; nothing joins approval to an outbound channel), the
> live-unique partial index, the granted_by CHECK, the approvals FKs (tenant_humans, effect_grants),
> schema readiness problems: [], the kernel gate-mint still confined to checkpoint.py, and no
> invented unfreeze surfaces (G2-D15 preserved). fp_v1 is consumed from fingerprint.py, not
> reimplemented. The builder correctly claims M4 ships dark, scores no P6 criterion, and leaves P6
> IN_PROGRESS; the registry confirms READY/IN_PROGRESS."

## 2. What M4 is, in one line

**One `approvals` row, one machine, eleven transitions, and the `fp_v1` fingerprint that makes "the
human agreed to THIS" a fact a database can `CHECK`.** At re-check every material fact is re-read
**live** and re-fingerprinted under the approval's **stored** version, so a drifted fact is not a
weaker approval — it is `VOID_ON_DRIFT` with a field-level diff, no grant, no effect. Provenance
class and evidence condition are **inside** the fingerprint, so the same number believed for a
different reason voids too. `GRANTED → CONSUMED` co-commits with M3's claim CAS through P3's kernel,
so **M3 remains the single effect authority** and M4 mints no gate decision and constructs no second
CAS ([`CLAUDE.md`](../../CLAUDE.md) rule 17).

The transition table is the specification's: `AP-1`, `AP-2`, `AP-2d`, `AP-3`, `AP-4`, `AP-4p`,
`AP-5`, `AP-6`, `AP-7`, `AP-8`, `AP-9` — **eleven rows, an exact set match with §14 of**
[`04-approval.machine.md`](../specifications/state-machines/04-approval.machine.md).

## 3. What the reviewer established ITSELF, and how

**The `P6-CP-3` review was read-only and could only corroborate behaviour from harness-captured
output. This one was not.** The reviewer ran the product in its own session: **16 commands executed
the product and satisfied a named expectation** (`RUNTIME_REPRODUCED`), **1** verified structure
against a named expectation (`STRUCTURAL_VERIFIED`), and **7** further commands were inspections
with no expectation attached — *those establish nothing by machine, and are not counted as evidence
here.* The reviewer's command boundary **refused 3 commands** for shell composition outside quotes;
a refusal is a limit on the review, never a defect in the product.

| Class | What it covers | Standing |
|---|---|---|
| **REPRODUCED by the reviewer, by execution** | The full M4 probe (`behaviours as specified, 0 wrong`, exit 0); the mutation battery (`10/10 mutants caught`); `eval/tests/test_phase6_approval.py` (`35 passed`); the corrected `--case database-invariants`; the M3 regression probe (`0 wrong`); the inline eight-state `CHECK` vocabulary; the `approvals` foreign keys and the `granted_by` `CHECK`; the live-approval partial `UNIQUE` index; schema readiness `problems: []`; the three dark-posture AST scans; the gate-mint confinement and the absent unfreeze surfaces | **The reviewer's own execution** |
| **VERIFIED structurally by the reviewer** | That the HEAD change (`1524fc3`) is confined to `scripts/probe_phase6_approval.py` and touches no DDL, `CHECK`, index or guard | The reviewer's own read |
| **CORROBORATED from the run's records** | Everything in the verdict not named above — read out of this run's evidence rather than re-measured by the reviewer | Product Driver run records |

**The reviewer confirmed the reviewed state itself** with three separate commands: `git rev-parse
HEAD` → `1524fc3a3224…`, `git rev-parse HEAD^{tree}` → `542fbe447c52…`, `git status --porcelain=v1`
→ empty.

## 4. What Product Driver independently exercised

M4 was **operated as a running unit, not merely tested**. This is the run's structured evidence, not
its prose.

### 4.1 Scenario evidence — 14/14, 406 assertions, 0 failed

`suite-result.json` records a **full** run (`full_run: true`, "full required regression set before
acceptance"), 14 required scenarios, **every one `PASSED`**, `assembly_problems: []`:

| Scenario | Origin | Outcome | Assertions |
|---|---|---|---|
| `p6_m4_approval` | permanent | PASSED | 198 / 0 failed |
| `S-C01-2` · `S-C01-3` · `S-C01-4` · `S-C01-5` · `S-C01-6` | generated | PASSED | 14 · 11 · 14 · 9 · 15 |
| `S-COH-AUTH` · `S-COH-DRIFT` · `S-COH-VOID` | generated | PASSED | 30 · 23 · 25 |
| `S-UNIQ-CASE` | generated | PASSED | 14 |
| `S1-dark-ship-single-authority` | generated | PASSED | 12 |
| `S2-unfreeze-does-not-exist` | generated | PASSED | 9 |
| `S3-probe-interface-closed-vocabulary` | generated | PASSED | 20 |
| `S4-db-enforced-authority-invariants` | generated | PASSED | 12 |
| **Total** | | **14 PASSED / 0 failed** | **406 / 0 failed** |

### 4.2 Mutation evidence — 10/10

`scripts/mutate_phase6_approval.py`: **10 of 10 load-bearing guards proven to fail when mutated** —
drift comparison, provenance-in-fingerprint (laundering), evidence-condition degradation,
unreadable-source-as-no-drift, the `granted_by` `CHECK`, the live-approval unique index, the
double-tap short-circuit, the consume co-commit, transport-token single-use, and the tenant
predicate. **A guard never seen to fail is a decoration** ([`CLAUDE.md`](../../CLAUDE.md) §6); these
were seen to fail.

### 4.3 Negative controls, and the closed fault vocabulary

`--inject not-a-real-fault` and `--inject unfreeze` **both exit 2** with `unknown fault`. The second
is load-bearing: the probe refuses to simulate an unfreeze because **no unfreeze exists**.

### 4.4 Behaviours observed, and regressions

Probe exit 0, `behaviours as specified, 0 wrong`; every required invariant sentence present and every
forbidden marker (`### DRIFTED APPROVAL EXECUTED ###`, `### APPROVAL CONSUMED TWICE ###`, …) absent.
`replay: 0 grants, 0 approvals granted, 0 approvals consumed, 0 external effects`. Regressions green:
**P3 205 · P4 99 · P5 209 · M1/M2/M3 397**; the M3 probe still reports `0 wrong` with M4's seam
present; `eval/tests/test_phase6_approval.py` **35 passed**; schema readiness `problems: []`.

### 4.5 The fourteen criteria, all `PASS`

`approval_required` · `authorization` · `stale_state`/drift · `conflicting_evidence` ·
`safety_invariant` · `concurrency` · `idempotency` · `repeated_request` ·
`retry_safety`/replay-inertness · `cross_tenant` · `unexpected_state_transition` · strict-order F4
aggregate · dark posture · scope discipline. Plus the reviewed change itself: *"correction 2 does not
weaken a safety guard"* — **PASS**. **No criterion returned `CANNOT_DETERMINE`.**

### 4.6 The harness's own audit

`scoped-completion.json`: `task_result: VERIFIED`, `task_outstanding: []`, `parent_phase_accepted:
false`. `completion-audit.json`: `decision: VERIFIED`, `implementation_present: true`,
`missing_evidence: []`, `contradictions: []`. The run's `does_not_imply` list is explicit and is
honoured by this landing: **P6 is not COMPLETE, no P6 acceptance criterion is scored, the units P6
still owes are not built, the next phase is not unblocked, and nothing is enabled in production or on
live traffic.**

### 4.7 No production enablement

Reproduced by the reviewer, by execution: `production importers of approval: []`; `scripts reaching
approval: ['probe_phase6_approval.py']`; `modules joining approval to an outbound channel: []`;
`modules that MINT a gate decision: ['checkpoint.py']`; `invented unfreeze surfaces: []`. M4 does not
import M3 — the consume seam runs through P3's kernel. No external effect was performed by this run.
The deployed governed route still answers `ROUTE_NOT_CONFIGURED` and the production `GateRegistry`
stays EMPTY until U8.1/P8.

## 5. Minor and nonblocking items — recorded, not actioned

**The independent review returned ZERO findings.** The following are **not** reviewer findings. They
were identified by this landing from the run's own evidence, the M4 source, the specification and the
CI record, and each is recorded here so it is legible later
([`CLAUDE.md`](../../CLAUDE.md) §13 — the debt row is the complete deliverable). **None can produce a
wrong customer outcome, violate an invariant, or make a later phase unsafe, and the machine ships
dark.**

### `P6-D31` — the §3.9 authority-seam conflict is REPORTED, not resolved · `minor`

Three authorities put `GRANTED → CONSUMED` **inside the claim transaction** (entity §15, machine §14
`AP-7`, `EF-2`). Two rows are written from `GRANTED` on triggers that can only arrive **after** that
transaction committed (`AP-8` on `AttemptFailedProvably` = `EF-3f` from `CLAIMED`; `AP-9` on
`AttemptOutcomeUnknown` = `EF-3u` from `CLAIMED`). Under the claim-time reading `AP-8`/`AP-9` are
unreachable; under the commit-time reading `AP-7`'s "same txn as the claim" is false. **The code
implements `AP-7` exactly as the three claim-transaction clauses state it and `AP-8`/`AP-9` exactly
as written, and invents no reconciliation** — no state, no flag, no un-consume path. It therefore
cannot prove which reading is canonical, and says so in its own module docstring. What every reading
agrees on, and what the code guarantees: **no second effect, no second grant of authority, nothing
reusable.** This is a specification question owed to a founder/architect decision, not an M4 defect.
**Evidence:** `src/freight_recon/approval.py` module docstring; `docs/specifications/entities/06-approval.md`;
`docs/specifications/state-machines/04-approval.machine.md` §4/§14/§15.

### `P6-D32` — this commit has no green CI conclusion · `minor`

See §6. The workflow concluded `cancelled`. Recorded so no later session reads this report as CI
evidence. **It closes only by a CI run on this branch that concludes `SUCCESS`.**

### `P6-D33` — CI does not execute M4's probe or mutation battery · `minor`

`.github/workflows/ci.yml` has an `effect-grant` job that runs **M3's** probe and mutation battery on
every push, precisely because `pytest eval` does not invoke them. **There is no equivalent job for
M4.** M4's `scripts/probe_phase6_approval.py` and `scripts/mutate_phase6_approval.py` are therefore
executed by the Product Driver run and by the independent reviewer, but **not by the source-of-truth
authority on every push**. `eval/tests/test_phase6_approval.py` **is** inside `pytest eval` and did
run in both full-suite jobs. **Verified mechanically:** no occurrence of `phase6_approval` in
`.github/workflows/ci.yml`. This is a CI-coverage gap, not an M4 defect, and closing it is a change
to CI wiring that this status landing deliberately does not make.

### `P6-D34` — the run's free-form evaluator prose contradicts the run's own structured record · `minor`

The evaluator's `final_decision.summary` closes with *"a focused independent review by a session that
did not build it remains a REQUIRED separate run step; this ACCEPT is a judgement that the observed
builder behaviour matches the M4 contract, not a substitute for that review."* **The run's structured
records say that review then ran, inside the same run, and satisfied the requirement**:
`independent-review-ledger.json` records it at iteration 3 with `independent: true`, a reviewer
session distinct from the builder's, `inherited_builder_context: false` and verdict `SUPPORTED`; the
run's own founder summary answers *"Did it satisfy what this task owed?"* with *"Yes — a supported
review of this exact implementation."* Related: `record.json`'s
`protocol_resolution.gates.independent_review` reads `NOT_RUN`, a gate snapshot taken **before** the
review executed at `02:11:01`. **The structured evidence is authoritative here and the prose is
stale**; recorded so a later session reading only the prose does not conclude a review is still owed.

### Standing items, carried and unchanged

- **`G2-D15` — the unfreeze direction** remains an open residual, and M4 **preserves** it: `AP-9`
  sets `frozen=true`, a frozen approval accepts no trigger, there is no un-freeze event, no
  un-freeze transition and no side-effect that clears the flag. A full-history rebuild reconstructs a
  frozen approval as **still frozen** — strictly safer than the original, which is why the residual is
  nonblocking. `ER-16`: `frozen` is reconstructed from the **presence** of `ApprovalFrozen`, never
  from an absence.
- **`V2` and `V3` open validation** (machine spec §43): approval TTLs, and dual-control classes and
  thresholds. **Fail-closed defaults; the mechanism is complete.** Explicitly *"not blocks"* in the
  specification, and they require design-partner evidence, never inference.
- **The exhaustive `(state × trigger)` illegal sweep** — `foundational-machine-acceptance.md`'s
  per-machine mandatory assertion #2 — is exercised at **representative** points for M4 (terminal
  states final by trigger, parametrized; frozen reuse; a replayed transport token), not as an
  enumerated cartesian sweep. This is the **same shape** as `P6-D30`, recorded at the M3 landing, and
  it is structurally mitigated the same way: `apply()` derives legality **solely** from
  `legal_transitions()`, which returns empty for any non-enumerated pair, and `GR-1` then refuses
  uniformly. ### **IT IS A PHASE-ACCEPTANCE ITEM AND CLOSES AT GATE G1**, where the per-machine
  mandatory assertions are scored — not a blocker on M4 as a landed increment. Stated here as this
  landing's own mechanical observation; **the reviewer did not raise it.**

## 6. ### CI — the honest record. The workflow did NOT conclude `SUCCESS`

**Pushed CI run `32801579476`**, head SHA `1524fc3a32243c86d3c5fb510659e8a6282caf04`.

### **OVERALL WORKFLOW CONCLUSION: `CANCELLED`. NOT `SUCCESS`. NOT GREEN.**

| Job | Conclusion | Window |
|---|---|---|
| **Full test suite (py3.11)** | ### **`success`** | 02:29:19 → 02:41:32 |
| **Full test suite (py3.12)** | ### **`success`** | 02:29:19 → 02:42:09 |
| **P6/M3 effect-grant probe + mutation** | ### **`success`** | 02:29:19 → 02:30:13 |
| **Safety invariants (fast)** | ### **`cancelled`** | 02:29:19 → 02:59:33 |
| **Risk radar** | `skipped` (pull-request-only job) | — |

**What the cancelled job's log actually shows**, read end to end: the step *"Effect boundary,
checkpoint kernel, authority, tenancy, idempotency"* started at `02:29:36`, emitted only its command
echo, produced **no pytest output and no failure line of any kind**, and ended at `02:59:32` with
`##[error]The operation was canceled.` — **exactly 30 minutes after the job started**, against the
job's declared `timeout-minutes: 30`. **The cancellation is the job timeout expiring, not a test
failure and not a manual cancel.** No test in that job was observed to fail.

**A bound that is true and is NOT a claim of green.** The safety job's 26 test files are **all** under
`eval/tests/` and are therefore a **strict subset** of `pytest eval` — which is exactly what the
`suite` job runs, and which **passed on both Python 3.11 and Python 3.12 on this same commit**. So
the cancelled job covered no test file that a passing job did not also execute. ### **THAT IS A
SUBSET ARGUMENT, NOT A CI RECEIPT.** It does not make the workflow green, it does not substitute for
a `SUCCESS` conclusion, and it must not be quoted as one. The workflow conclusion is `cancelled` and
stays `cancelled` until a fresh run says otherwise.

**No receipt is committed for any of this** — [`CLAUDE.md`](../../CLAUDE.md) §0 forbids committed
suite receipts, and none may be manufactured. The facts above are read from the CI run itself and are
re-readable there.

**The founder has explicitly chosen to continue**, treating the cancellation as a **non-product CI
runtime limitation** rather than as evidence of an M4 defect. That is a recorded founder decision,
and it is recorded as a decision — **not** as a verification, and **not** as a green CI result. It is
tracked as `P6-D32`.

## 7. What this review and this landing are not

- **Not a phase acceptance.** No P6 acceptance criterion is scored, and none may be from any lineage
  that built M4. P6 remains `READY` / `IN_PROGRESS`, `criteria_scored` is `[]`, and P7 stays
  `BLOCKED`.
- **Not an adjudication**, and none is owed. M4 is tier-1 (`CLAUDE.md` §7): builder + **one** focused
  independent review + mutation proof + CI. A single independent review is a review, not a chain.
- **Not CI evidence.** See §6. The workflow concluded `cancelled`.
- **Not an enablement.** M4 ships dark: zero production importers, only the probe reaches it, nothing
  joins it to an outbound channel. No external effect is enabled on live traffic.
- **Not a resolution of the §3.9 authority seam.** `P6-D31` reports it; it does not settle it.
- **Not a finalizer, a suite receipt, a preserve ref or a special Git topology.** None is owed for
  this landing and **a session must not run one.**
- **Not a review of the commit that carries it** — see the banner.
