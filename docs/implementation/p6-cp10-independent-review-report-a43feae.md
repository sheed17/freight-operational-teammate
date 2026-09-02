> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This is evidence of a past moment, not status.** It is an INDEPENDENT REVIEW: it set no
> acceptance criterion, marked no phase complete, closed no risk, enabled nothing and authorized no
> external effect. It reviewed the M10 implementation tree (machine **M10 — the Compensation**) at
> commit `a43feae7496a7a9dddc363b98eed0345482f0890` (tree
> `3b85cea8997e3e2e0cbea460fe77ee3239ed4611`, branch `p5/u5-1-g2-spec-correction`, working tree
> clean) and returned **SUPPORTED, confidence 0.90**.
>
> ### **THE LANDING CANDIDATE IS `a833074`, AND THE REVIEWER DID NOT SEE IT.** `a833074` is a
> post-push CI correction made **after** this review. §9 proves mechanically what it did and did not
> change — `src/` is **byte-identical**, so no reviewed runtime moved — but nothing here may be cited
> as an independent review of `a833074`. Two different claims are kept apart throughout this
> document: *"an independent review of the M10 implementation tree"* and *"a post-review candidate
> correction verified by targeted tests and by CI."*
>
> ### **IT DID NOT REVIEW THE COMMIT THAT CARRIES IT.** The landing commit that brought this file
> in-tree did not exist when the review was performed.
>
> ### **P6-CP-10 IS A CHECKPOINT, NOT A PHASE ACCEPTANCE.** P6 is **NOT COMPLETE**, no P6 acceptance
> criterion is scored, and P7 is not unlocked. M10 continues to **ship dark**.
>
> ### **NO ADJUDICATION FOLLOWED THIS REVIEW, AND NONE IS OWED.** M10 is tier-1 under
> [`CLAUDE.md`](../../CLAUDE.md) §7 — it lands a migration, it is load-bearing for tenant isolation,
> and it is a **money-affecting** surface — which requires builder + **one focused independent review
> by someone who did not write it**, mutation proof that the guard can fail, and CI. The adjudication
> chains and finalizer rituals cited by the `P6-CP-1` and `P6-CP-2` records were retired in the
> 2026-08 engineering-process simplification and must not be revived.
>
> ### **CI DID NOT CONCLUDE `SUCCESS` ON THE LANDING CANDIDATE, AND THIS RECORD DOES NOT PRETEND
> OTHERWISE.** Run `33594219060` concluded **`cancelled`**. §8 states both halves exactly — including
> that Python 3.11 and *Safety invariants (fast)* have **no result**. Read it before citing this
> document as evidence of a green repository.

# P6-CP-10 — FOCUSED INDEPENDENT REVIEW — M10 implementation tree `a43feae`

**Verdict: `SUPPORTED` · confidence `0.90` · findings `0` · adjudications `0` · criteria `11/11 PASS`**

| | |
|---|---|
| **Reviewed tree** | commit `a43feae7496a7a9dddc363b98eed0345482f0890`, tree `3b85cea8997e3e2e0cbea460fe77ee3239ed4611`, branch `p5/u5-1-g2-spec-correction`. The review record's `reviewed_fingerprint` reads **`tracked_dirty: 0`, `untracked: 0`**, identity `a43feae7496a/3b85cea8997e/-` |
| **Landing candidate** | `a83307410746520ab084d028c98e1e23288755fb` — **two commits later, and NOT reviewed.** §9 measures the delta |
| **Reviewer lineage** | A session that did not build M10. The review record states `inherited_builder_context: false`; reviewer session `28c38089-a152-42c2-b440-52eba32987b9`, builder session `a4661cfd-8251-41f1-b94c-20f8472578be` |
| **Performed** | `2026-09-01T23:50:30+00:00` |
| **Source artifact** | Product Driver run `20260901-082602`, `accepted/independent-review.json` (separate repository, `neyma-product-driver`) — `iteration-01` promoted to `accepted`. Its prose is quoted verbatim below; nothing is upgraded, softened or summarised into a stronger claim |
| **Adjudications recorded** | **none** (`adjudications: []`) |
| **Findings** | **none** (`findings: []`). §7 records the nonblocking items THIS LANDING identified from the run's own evidence — they are **not** reviewer findings and are not presented as such |
| **Scope declared by the run** | `P6/M10`, parent phase `P6` (`READY` / `IN_PROGRESS`), `parent_phase_accepted: false`, `task_result: VERIFIED`, `task_outstanding: []`, `criteria_scored` unmoved |
| **Review requirement** | `required: true`, triggered from `CLAUDE.md` §7. **SATISFIED for the reviewed tree** |
| **Reviewer executed the product** | **Yes.** `evidence_reproduced: true` and `claimed_evidence_reproduced: true` — see §4 |
| **Reviewer blocked on anything** | **No.** `blocked_on.kind: NONE` — though its harness refused three commands; see §4.1 and §7 |

---

## 1. The verdict, verbatim

> "Independently reproduced M10's product behaviour against HEAD a43feae / tree 3b85cea (confirmed
> clean, working tree empty): the compensation acceptance suite (63 passed), the probe --all
> (behaviours as specified, 0 wrong), and the 33-mutation battery (33/33 caught, 0 escaped,
> anti-vacuity re-export control included) all pass. M10 ships dark (zero production importers of
> compensation.py), mints no gate decision (only checkpoint.py does), engages no brake, imports M1's
> single K-1 resolver rather than a second one, carries exactly the seven registered F10 contracts
> plus the shared F3 RealityEstablished, has nine CM transitions and six states enforced by CHECK,
> and M11/M12/M13 are unbuilt. M-33 unknown-outcome refusal, model-cannot-approve/own,
> canonical-money, no-timer/no-auto-retry and per-effect uniqueness are each exercised live by the
> probe and each protected by a caught mutant. The correction commit a43feae — the safety-guard
> surface this review exists for — widens three neighbour dark-surface guards to tolerate
> compensation_shadow.py; I verified that file is a transient byte-copy of the already-dark M10
> machine (not git-tracked, absent from the working tree, purged at battery start and in
> finally/BaseException), the guards still reject any other production importer and still inspect >20
> modules, and the FIXED-SPECIFICATION change is docstring-only with the assertion body unchanged.
> The ten M1-M9+checkpoint machine files are byte-identical to HEAD. No live-traffic path is opened
> and no safety guarantee is weakened. Scope respected: no P6 criterion scored, P6 stays IN_PROGRESS."

---

## 2. What M10 is, in one line

**M10 is the machine whose whole job is to prove that an UNDO gets no privileged path.**

A carrier's POD was bound to the wrong load. An invoice for GBP 2,850 went out to the customer on the
strength of it. A human corrects the binding, and that invoice now rests on a fact known to be wrong.
The money left the building; something has to credit it back.

The tempting implementation is a rollback: find the effect, call the adapter's void endpoint, mark the
row undone. ### **THAT IS A SECOND, UNGATED WRITE ROUTE INTO A CUSTOMER'S ACCOUNTING SYSTEM**, reached
precisely when the system is already known to be wrong about something. M10 does the opposite: the
credit note is a **NEW external effect** — its own M2 Pipeline Instance, its own policy evaluation, its
own brake check, its own M4 human approval, its own P3 checkpoint witness, its own single-use M3 Effect
Grant, its own commit key, its own verified readback. The `compensations` row is only the
**obligation** to do that, with a named human owner and the amount at stake written on it from the
moment it exists.

### **AN "UNDO" THAT BYPASSES THE GATES IS AN UNGATED WRITE WITH A GOOD EXCUSE.**

### **AND YOU CANNOT UNDO WHAT YOU CANNOT PROVE YOU DID.** When the original effect's outcome is
`UNKNOWN_OUTCOME` — the TMS timed out and nobody can say whether the invoice was issued — M10
**refuses to compensate at all** (M-33). "Cancel invoice #560010" against a system where no such
invoice exists can **create a credit note out of nothing**. A human resolves the unknown to `VERIFIED`
or `FAILED` first, through M3's `EF-5`. Only then may compensation be considered. Eligibility is read
from the persisted grant ledger, never from a caller flag.

Six canonical states (`REQUIRED`, `APPROVED`, `EXECUTING`, `COMPLETED`, `COMPENSATION_FAILED`,
`NOT_POSSIBLE`) as a database `CHECK` with **no seventh** — no `CANCELLED`, no `EXPIRED`, no
`TIMED_OUT`, no `STALE`, no `ROLLED_BACK` — and **no expiry column at all**. Nine transitions
`CM-1`, `CM-1r`, `CM-2`, `CM-2n`, `CM-3`, `CM-4`, `CM-4f`, `CM-5`, `CM-5x`, an exact set match with
§14 of [`10-compensation.machine.md`](../specifications/state-machines/10-compensation.machine.md).

**`COMPENSATION_FAILED` and `NOT_POSSIBLE` are the most dangerous states the system can be in** —
reality and the projection are KNOWN to diverge. No timer moves them, no retry loop moves them, no
sweep, no reaper, no model, at any confidence. They stay loud, keep their named human owner and
**carry the exposure** until a human establishes reality through `CM-5`.

**M10 does not write a second K-1 resolver.** It imports M1's landed `resolve_decision_ref` — measured
at this landing: `names imported from work_item: ['DecisionRefUnresolvable', 'resolve_decision_ref']`,
and `modules DEFINING resolve_decision_ref: ['work_item.py:689']`, one and only one.

---

## 3. One tenant-first table enters the canonical partition

`compensations` is the single table M10's migration creates. **Unlike M9, this landing's candidate
needed a REG-1 adjudication** — the build commit `715ddc0` did not classify the table in
[`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml), CI caught it, and `a833074`
supplied it. §8 and §9 record that as CI doing its job, not as an M10 runtime defect.

### 3.1 The load-bearing DDL was introspected LIVE at this landing, not read

A **fresh canonical database, built the way production builds one** (`create_canonical_schema`), then
introspected. All read-only; **no runtime file changed.**

| What was measured | What came back |
|---|---|
| the table exists in a fresh canonical database | 33 tables, `compensations` present |
| `PRAGMA table_info` — primary key order | `['tenant', 'compensation_id']` — **tenant-first**, 15 columns |
| `PRAGMA index_list`/`index_info` — every index | 4 indexes, **4 of 4 lead with `tenant`**: `sqlite_autoindex`, `ix_compensations_commit_key`, `ix_compensations_owner`, `ix_compensations_one_active_per_effect` |
| the AC-RACE-013 predicate, verbatim | `CREATE UNIQUE INDEX ix_compensations_one_active_per_effect ON compensations (tenant, original_effect_id) WHERE state != 'NOT_POSSIBLE'` — built exactly as §17 writes it |
| `PRAGMA foreign_key_list` | 4 composite FKs, **every one leading with `tenant`**: into `approvals`, `pipeline_instances`, `effect_grants` (`original_effect_id → grant_id`) and `tenant_humans` (`owner_id → human_id`) |
| the state vocabulary in the live DDL | exactly **6** literals; **no seventh**; **no expiry/TTL column** (`[]`) |
| triggers | `trg_compensations_no_delete`, `trg_compensations_identity_immutable`, `trg_compensations_version_advances_on_state_change` |

### 3.2 The invariants were proven by ATTEMPTING THE VIOLATION — with the population proved first

### **TWO POSITIVE CONTROLS RAN FIRST, AND BOTH WERE ACCEPTED.** Without them every refusal below
would be indistinguishable from a fixture that could not insert anything at all — the vacuous-negative
failure [`CLAUDE.md`](../../CLAUDE.md) §6 exists to catch. The population is real: `tenant_humans`
seeded in two tenants, `effect_grants` seeded with 18 rows.

| Control | Outcome |
|---|---|
| a legal `REQUIRED` compensation in tenant `acme` | **ACCEPTED** |
| the same original effect compensated in tenant `beta` | **ACCEPTED** — tenants are isolated, not colliding |

Then **nine illegal inserts, nine refusals**:

| Attempt | Refused by |
|---|---|
| a seventh state `'ROLLED_BACK'` | `CHECK constraint failed: state IN ('REQUIRED','APPROVED','EXECUTING','COMPLETED','COMPENSATION_FAILED','NOT_POSSIBLE')` |
| a seventh state `'CANCELLED'` | the same `CHECK` |
| an **ownerless** compensation | `NOT NULL constraint failed: compensations.owner_id` |
| an owner from **another tenant** | `FOREIGN KEY constraint failed` |
| an owner who is **not a recorded human** | `FOREIGN KEY constraint failed` |
| a **second active** compensation for the same original effect | `UNIQUE constraint failed: compensations.tenant, compensations.original_effect_id` |
| a compensation with **no exposure amount** | `NOT NULL constraint failed: compensations.exposure_amount_minor` |
| a compensation with **no reason** | `NOT NULL constraint failed: compensations.reason` |
| `version = 0` | `CHECK constraint failed: version >= 1` |

**The no-delete trigger refuses the `DELETE` outright**, with the entity's own prose: *"a compensation
is never deleted … retention is permanent, and an exposure NEVER expires and is never swept away by a
reaper. A row that quietly stops being visible is the EXACT failure this entity exists to prevent —
the money left the building and nobody is accountable for it."*

**`M10-AQ-9`'s consequence was MEASURED, not asserted.** Moving the first compensation to
`NOT_POSSIBLE` (advancing its OCC version) and inserting a second for the same original effect is
**ACCEPTED** — leaving `[('cmp-1','NOT_POSSIBLE'), ('cmp-2','REQUIRED')]`. That is what the canonical
predicate requires, and it is **reported as an authority question rather than silently corrected**.

### 3.3 The event contracts, measured

118 registered contracts. The F10 family has **exactly seven** members and no eighth —
`CompensationRequired` (CM-1), `CompensationRefused` (CM-1r), `CompensationApproved` (CM-2),
`CompensationImpossible` (CM-2n), `CompensationStarted` (CM-3), `CompensationCompleted` (CM-4),
`CompensationFailed` (CM-4f). `CM-5` emits the **already-registered shared F3 `RealityEstablished`**,
whose producers are `['EF-5', 'CM-5']` with `coordination: true` — ### **M10 minted no duplicate
coordination contract** (CLAUDE.md rule 17). `CorrectionInvalidatedAnEffect` and
`NoCompensatingActionExists` are confirmed **not registered**, and M10 mints neither.

### 3.4 The transition arithmetic, re-derived rather than carried

Parsing §14 of **all thirteen** machine files and **counting rows** discovered 13 files and **134**
rows, matching P6's own `expected_production_outputs`. Written and landed as of `P6-CP-10`:
14 + 25 + 13 + 11 + 8 + 11 + 7 + 8 + 7 + **9** = **113**, so **21 remain** — exactly M11's 7, M12's 9
and M13's 5. No prior figure was carried.

---

## 4. What the reviewer established ITSELF, and how

`evidence_reproduced: true` and `claimed_evidence_reproduced: true`. Its harness logged **21 command
attempts**, of which **18 ran** and 3 were refused by its own layers (§4.1). The load-bearing results
it produced with its own hands:

| What it ran | What it showed |
|---|---|
| `git rev-parse HEAD` | `a43feae7496a…` — the tree under review is the declared target |
| `git rev-parse HEAD^{tree}` | `3b85cea8997e…` |
| `git status --porcelain` | empty — the working tree was clean |
| `git ls-files` over the M10 artifacts | machine, migration, probe, mutation battery and suite all tracked on the reviewed tree |
| `.venv/bin/python -m pytest -q -p no:cacheprovider eval/tests/test_phase6_compensation.py` | **63 passed** |
| `.venv/bin/python scripts/probe_phase6_compensation.py --all` | exit 0, **`behaviours as specified, 0 wrong`** |
| `.venv/bin/python scripts/mutate_phase6_compensation.py` | **33/33 mutants caught, 0 escaped**, anti-vacuity re-export control included |
| AST scan of `src/freight_recon` | **`production importers of compensation: []`** |
| AST scan for gate minters | **`modules that MINT a gate decision: ['checkpoint.py']`**; `GateRegistry` constructed by M10: **False** |
| registry scan of `event_contracts_data.json` | seven F10 contracts, the shared F3 `RealityEstablished`, no unregistered name emitted |
| `pytest … work_item / pipeline_instance / external_effect / approval` | **432 passed** — M1, M2, M3, M4 unbroken with M10's table present |
| `pytest … test_phase6_exception.py` | **58 passed** — M9 unbroken |
| `pytest … test_false_green_defenses.py` | **8 passed** |
| `git show a43feae` + `git ls-files "*compensation_shadow*"` + `find . -name compensation_shadow.py` | the correction's tolerated file is a **transient byte-copy** of the already-dark machine: **not tracked, absent from the working tree**, purged at battery start and in `finally`/`BaseException` |
| `test_m1_through_m9_machines_are_unchanged` | the ten named M1–M9 + checkpoint files are **byte-identical to HEAD** |

### 4.1 Harness statuses that read like failures and are not — recorded, not tidied

**Three of the 21 attempts were refused by the harness rather than by the product**, at two layers:

| Layer | Command | Re-issued and run? |
|---|---|---|
| `composition` | `git rev-parse HEAD && git write-tree …; git status …` | **Yes** — split into three single commands, all ran |
| `composition` | `ls -la …five artifacts… 2>&1` | **Yes** — the same facts were re-established with `git ls-files` |
| `reviewer-floor` | `sed -n '855,930p' eval/tests/test_phase6_compensation.py` | **No** — `sed` is refused as *"a stream editor that can write through its own syntax"*, though this invocation only read |

The reviewer's `blocked_on.kind` is **`NONE`**, and its own note records the one remaining
over-broad refusal — a declared F10-registry one-liner rejected by *"an over-broad 'at' token
heuristic"* — with the observation that *"every fact it asserts was fully reproduced by
`scripts/probe_phase6_compensation.py --all`, so no evidence was lost."* §3.3 re-runs that registry
oracle directly at this landing rather than carrying it as debt. This is the harness
status-vocabulary defect already recorded as `P6-D39` (M5), `P6-D45` (M6), `P6-D51` (M7), `P6-D56`
(M8) and `P6-D61` (M9), in a new shape. Recorded as `P6-D69`.

---

## 5. What Product Driver independently exercised

**Thirteen scenarios, all `PASSED`, 667 assertions, 0 failed, 0 blocked, 0 skipped** — the permanent
`p6_m10_compensation` plus **twelve generated**, the largest generated contribution of any P6 landing.

| Scenario | Origin | Risk category | Priority | Assertions | Outcome |
|---|---|---|---|---|---|
| `p6_m10_compensation` | permanent | — | P0 | 540 | **PASSED** |
| `CM-HP-01` | generated | `happy_path` | P1 | 9 | **PASSED** |
| `CM-ELIG-02` | generated | `boundary` | P1 | 6 | **PASSED** |
| `CM-TO-04` | generated | `timeout_before_effect` | P1 | 8 | **PASSED** |
| `CM-RACE-05` | generated | `concurrency` | P0 | 8 | **PASSED** |
| `CM-FAIL-R3-01` | generated | `partial_failure` | P1 | 13 | **PASSED** |
| `CM-NP-AQ4-01` | generated | `safety_invariant` | P0 | 13 | **PASSED** |
| `CM-STORM-01` | generated | `safety_invariant` | P0 | 12 | **PASSED** |
| `CM-W3-TO-01` | generated | `timeout_after_effect` | P1 | 10 | **PASSED** |
| `CM-W3-CFAIL-02` | generated | `retry_safety` | P1 | 15 | **PASSED** |
| `CM-W3-NP-03` | generated | `safety_invariant` | P1 | 13 | **PASSED** |
| `CM-W3-UNIQ-04` | generated | `concurrency` | P1 | 11 | **PASSED** |
| `CM-W3-CRASH-06` | generated | `crash_mid_workflow` | P2 | 9 | **PASSED** |

`coverage_summary` records **16 proposed, 12 accepted, 4 filtered, 0 invalid**, with
`uncovered_risks: []`. See `P6-D70` for the four that were filtered.

The run's `scoped_completion` reads `task_result: VERIFIED`, `task_outstanding: []`,
`parent_phase_accepted: false`, and its `does_not_imply` list names exactly what this landing also
refuses to claim: **P6 is not COMPLETE, no P6 acceptance criterion is scored, the units P6 still owes
are not built, the next phase is not unblocked, phase acceptance has not occurred, and nothing is
enabled in production or on live traffic.**

### 5.1 The run's first iteration blocked on the harness, not on M10

`state.json` records five iterations; `accepted/` is `iteration-01` of the final wave. The blockers
that drove the corrections were **environment artifacts, each diagnosed and disproved**: a scenario
step naming `test_phase3_checkpoint.py`, a file that does not exist (the real files are
`test_phase3_checkpoint_matrix.py`, `test_phase3_claim_cas.py`, `test_phase3_step_order.py` → **154
passed**); and twelve `test_phase6_pipeline_instance.py` failures that reproduced only without
`-p no:cacheprovider` — pytest **cache/order pollution in the `import_probe` guards**
(`from eval.phase0 import import_probe`), not an M10 regression. With the corrected command list the
neighbour matrix is **432 passed**. `git-diff-stat.txt` shows no repository file was edited to make
any of this pass.

---

## 6. The eleven criteria the reviewer assessed

All **PASS**, none `CANNOT_DETERMINE`. Bases are the reviewer's own, quoted from
`criteria_assessment`.

| # | Criterion | Basis the reviewer recorded |
|---|---|---|
| 1 | **M10 acceptance battery passes** (AC-REC-001…005, AC-RACE-013, AC-MACH-1001…1009) | "Reproduced: `pytest eval/tests/test_phase6_compensation.py` → 63 passed, exit 0." |
| 2 | **M-33** — compensation forbidden on `UNKNOWN_OUTCOME`; eligibility from the persisted ledger, not a caller flag | probe printed `COMPENSATION IS FORBIDDEN ON AN UNKNOWN OUTCOME`, `READ FROM THE LEDGER, NEVER A CALLER FLAG`, refusal cause `unknown_outcome`, zero pipelines/grants/effects; **mutants 1 and 3 CAUGHT** |
| 3 | **A compensation is itself a separately gated external effect** — no rollback, no privileged undo, no bulk undo, no adapter fast path | probe: new M2 pipeline, own commit key, own grant, readback required, `NO FAST PATH FOR UNDO`, `NO BULK UNDO`; **mutants 19–24, 26 CAUGHT** |
| 4 | **Authority is never laundered** — a model cannot own/approve/establish reality; K-1 resolver imported from M1; mints no gate, engages no brake | probe: model cannot own/approve/establish reality; K-1 imported from M1, no second resolver; `gate minters=['checkpoint.py']`, `GateRegistry False`, `brake False`; **mutants 4, 16, 25 CAUGHT** |
| 5 | **`COMPENSATION_FAILED`/`NOT_POSSIBLE` are loud, sticky, human-owned** — no timer, sweep or retry auto-resolves; the row is never deleted | probe: `NO TIMER MOVES ANY COMPENSATION STATE`, `NO AUTOMATIC RETRY`, `ROW CANNOT BE DELETED`, `TimerFired` has no legal row; **mutants 10, 13, 14, 15 CAUGHT** |
| 6 | **Canonical money and the six-state lifecycle enforced by DB `CHECK`** — no seventh state, no expiry | probe: canonical six, count 6, `CHECK True`, float/Decimal/bool/lowercase-currency refused; **mutants 8, 9, 11, 12 CAUGHT** |
| 7 | **F10 event conformance** — seven registered contracts, no eighth, no second `RealityEstablished` | probe: F10 count 7, code carries the seven, unregistered `[]`; declared set = seven F10 + `RealityEstablished` (single F3 coordination, producers CM-5/EF-5); **mutants 30, 31 CAUGHT** |
| 8 | **Ship-dark** — zero production importers; only test/probe/mutate reach M10; joins no channel; M11/M12/M13 unbuilt | `production importers of compensation: []`; probe: three expected external files, `channel modules []`, M11/M12/M13 tables/modules/migrations all `[]` |
| 9 | **M1–M9 + the checkpoint kernel unchanged** (no safety guard weakened in the machines) | `test_m1_through_m9_machines_are_unchanged` (a `git diff --name-only HEAD` over 10 named files) passes; probe `landed machines modified since the M9 head: []` |
| 10 | **The correction commit does not weaken a safety guard** (the review trigger) | `git show a43feae`: the `compensation_shadow.py` tolerance is a transient byte-copy of the dark M10 machine (`git ls-files` and `find` both empty), purged at start/`finally`/`BaseException`; guards still reject other importers and still inspect >20 modules; the `FIXED-SPECIFICATION` edit is docstring-only. `false_green` suite 8 passed |
| 11 | **Scope discipline** — no P6 acceptance criterion scored; P6 remains `IN_PROGRESS` | Registry P6 `READY`/`IN_PROGRESS`, verified weighted progress 0%; correction message *"Scores no P6 criterion"*; builder `criteria_scored []` |

---

## 7. Minor and nonblocking items — recorded, not actioned

### **THE INDEPENDENT REVIEW RETURNED ZERO FINDINGS.** Everything below was identified **at this landing** from the run's own structured evidence, the M10 source, the specification corpus and the CI record. **None is a reviewer finding and none may be cited as one.** Each is recorded, not actioned ([`CLAUDE.md`](../../CLAUDE.md) §13). None can produce a wrong customer outcome, violate an invariant, or make a later phase unsafe, and the machine ships dark.

They are carried in [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) as **`P6-D65`
through `P6-D70`**: the thirteen M10 authority questions, REPORTED and unresolved (`P6-D65`); the
`cancelled` CI workflow and what Python 3.11 and *Safety invariants* do **not** establish (`P6-D66`);
the absence of any CI job running M10's probe or mutation battery (`P6-D67`); the review being bound
to `a43feae` rather than to the landing candidate `a833074` (`P6-D68`); the reviewer harness's refusal
vocabulary (`P6-D69`); and the four generated scenarios filtered at assembly (`P6-D70`).

### **THE THIRTEEN AUTHORITY QUESTIONS ARE REPORTED, NOT RESOLVED.** The corpus numbers them
`M10-AQ-1` … `M10-AQ-13` (thirteen headings; the run's own prose calls them "twelve" — the count is
stated here as measured, not as the run summarised it). Each is built **fail-closed**:

- **`M10-AQ-1`/`M10-AQ-2`** — `CorrectionInvalidatedAnEffect`, `HumanApproved`,
  `NoCompensatingActionExists`, `PipelineFailed` and `HumanEstablishedReality` are **not registered
  contracts**. M10 mints none of them. It owns a callable `raise_from_correction(…)` seam
  (`compensation.py:510`) that takes already-registered correction facts plus a resolved
  `decision_ref`. `CM-4f`'s trigger is its executing pipeline **reaching** `FAILED` or
  `NEEDS_VERIFICATION`, read from the M2 row — not the delivery of an event that does not exist.
- **`M10-AQ-3`** — there is **no `invalidating_decision_ref` column**; the fact rides the immutable
  `CompensationRequired` event in the transactional outbox. The persistence asymmetry is reported.
- **`M10-AQ-4`/`M10-AQ-5`** — the `COMPENSATION_FAILED` branch coordinates with M2's landed `PL-15`;
  the `NOT_POSSIBLE` branch records `reality_decision_ref` with **no fabricated pipeline**.
  `RealityEstablished` keeps `aggregate_type: "effect_grant"` and is discriminated by
  `subject="compensation"`; the enum was not widened and `outcome="COMPLETED"` is never emitted.
- **`M10-AQ-6`** — M10 reads M4 and consumes no approval at `CM-2`; `Compensation.APPROVED` is not
  collapsed with `Approval.GRANTED`/`CONSUMED`.
- **`M10-AQ-7`** — M10 reuses M2's `propose`; the caller supplies the Work Item. No second pipeline,
  no edit to M2's state machine.
- **`M10-AQ-8`** — M10 uses the checkpoint/brake substrate and builds **no part of M11, M12 or M13**.
- **`M10-AQ-9`** — the predicate is built verbatim; the consequence is measured in §3.2 and reported.
- **`M10-AQ-10`** — the other six M3 states create nothing and mint no refusal-cause variant.
- **`M10-AQ-11`** — a deterministic-evidence token, **no capability registry**, and the `S`-trigger
  versus human-authority tension is reported rather than settled.
- **`M10-AQ-12`** — the F10 → M9 escalation seam is **named and left UNWIRED**. M10 creates no
  Exception row, wires no oversight queue, dashboard or notifier, and does not edit M9. This is the
  precedent M9's own landing set for `M9-AQ-4`: wiring a seam is precisely what shipping dark forbids.
- **`M10-AQ-13`** — `original_effect_id` is the K-4 provenance reference for the required, money-
  affecting `exposure`, which is persisted as `exposure_amount_minor` + `exposure_currency`. No money
  value is persisted without provenance and no reference the corpus does not support was invented.

### **ONE CARRIED RESIDUAL NAMES `closes_at: M10`, AND M10 DOES NOT CLOSE IT — STATED RATHER THAN LET
PASS.** `P6-D2` (`CorrectionInvalidatedAnEffect` is listed in M1 §33 "Events consumed" but has no §14
row; §27 routes it out of band to M10) is **not closed here**. That is `M10-AQ-1`: M10 uses the
established correction seam and **mints no unregistered event name**, which is the safe direction the
disposition already named — but it is not the determination the row is waiting for. The row stays
open with its `closes_at` marker unchanged. **A landing that quietly moved it would be the
claim-outliving-its-warrant failure this repository keeps catching.**

**`V1` stays open validation** — machine §43, *"reopening may raise a compensation"* — fail-closed,
each human-approved, and not a block. **`M9-AQ-1` … `M9-AQ-6`, `M7-AQ-1` … `M7-AQ-3`, `M6-AQ-*`,
`M5-AQ-*`, `P6-D1`, `P6-D3`, `P6-D4` and `V10` are untouched.** **`P6-D40` is carried forward
unchanged and was not re-verified here.**

---

## 8. ### CI — the honest record. The workflow did NOT conclude `SUCCESS`

**Run `33594219060`, on the landing candidate `a833074`, concluded `cancelled` — and `cancelled` is
not `success`.** Nothing in this document says otherwise.

| Job | Conclusion |
|---|---|
| *Full test suite (py3.12)* | **SUCCESS** — **3165 passed, 1 skipped**, the entire suite completed |
| *P6/M3 effect-grant probe + mutation* | **SUCCESS** |
| *Full test suite (py3.11)* | **CANCELLED** at the workflow/runtime ceiling, ~54%, **no pytest `F` emitted before cancellation** |
| *Safety invariants (fast)* | **CANCELLED** at its runtime ceiling, **no pytest `F` emitted before cancellation** |
| *Risk radar* | **skipped** (pull-request-only) |

### **THIS IS THE STRONGEST CI POSITION OF ANY P6 LANDING, AND IT IS STILL NOT GREEN.** For the first
time since `P6-CP-6` a **complete interpreter suite ran the whole way through**, and for the first
time at any P6 landing that completed suite **executed the landing machine's own tests**.

**Measured at this landing, not assumed.** `pytest eval --collect-only -q` on this exact tree collects
**3166** tests — matching py3.12's `3165 passed + 1 skipped` **exactly** — and
`eval/tests/test_phase6_compensation.py` occupies positions **2061–2123**, **65.1%–67.1%** of the run.
So the py3.12 job **ran all 63 of M10's tests and they passed**.

### **WHAT PYTHON 3.11 DOES NOT ESTABLISH.** Cancelled at ~54%, it stopped **before** 65.1%. The
honest statement is not "no verdict" but **NO EXECUTION**: the repository has **no Python 3.11 run of
M10's 63 tests on this commit, neither failing nor passing.** *Safety invariants (fast)* likewise has
**no result** — and its 26 named files do **not** include `test_phase6_compensation.py`, so what its
cancellation costs is a second execution of guards the completed py3.12 suite already ran, not
coverage of M10 itself.

### **THE SIX REAL FAILURES FROM THE PRIOR RUN ARE GONE, AND A COMPLETED JOB ESTABLISHES IT.** Run
`33575760180`, on the pushed pre-correction head `a43feae`, reported **6 failed, 3156 passed, 1
skipped** on py3.12. They were reproduced **exactly, all six and only six**, at this landing on a
throwaway worktree of `a43feae`:

| Test | Position (of 3166) | On `a43feae` | On `a833074` |
|---|---|---|---|
| `test_bootstrap_hermeticity.py::test_the_canonical_table_partition_is_exact_and_disjoint` | 179 — 5.7% | **FAILED** | **passed** |
| `test_phase0_baseline_manifest.py::test_r07_containment_record_holds_only_while_its_mechanical_conditions_hold` | 1429 — 45.1% | **FAILED** | **passed** |
| `test_phase0_errata_guards.py::test_typed_policy_runtime_exists_only_with_its_canonical_authority` | 1460 — 46.1% | **FAILED** | **passed** |
| `test_phase0_null_gate.py::test_the_typed_gate_population_is_now_non_empty_and_confined_to_the_checkpoint_kernel` | 1496 — 47.3% | **FAILED** | **passed** |
| `test_phase0_tenant_posture.py::test_no_new_tenantless_table_appeared` | 1522 — 48.1% | **FAILED** | **passed** |
| `test_phase3_schema.py::test_a_phase2_only_database_is_refused_until_the_phase3_migration_runs` | 1840 — 58.1% | **FAILED** | **passed** |

All six are inside the completed py3.12 suite that concluded **SUCCESS** on `a833074`. **Five of the
six sit below 54%**, so the cancelled py3.11 job passed *through* their positions without emitting a
failure marker — corroboration, not the basis. The basis is the completed py3.12 run.

**None of the six was an M10 runtime defect.** Three were canonical bookkeeping — `compensations` was
a real canonical table that the partition guard, the REG-1 manifest and the migration walk could not
see — and three were **stale guard subjects**: P0 guards that defended the ADR-010 boundary by reading
**raw file text**, which cannot tell `if gate is FORBIDDEN:` apart from a docstring saying *"this
machine mints NO gate decision."* M10's docstring says exactly that. AST proof recorded in the
correction: `compensation.py` and `phase6_compensations.py` hold six gate-token occurrences and
**zero are executable** — five Python docstrings/comments and one SQL `--` comment inside a DDL
string. ### **The guards were catching M10 for DESCRIBING the authority it defers to.** What narrowed
is what the guards **read**; who is permitted is untouched, the kernel allowlist is unchanged,
`compensation.py` is **not** in it, and production `GateRegistry` registration remains **EMPTY**.

### **AND THE NARROWED GUARDS WERE PROVEN NOT TO BE DECORATIONS.** Three new mutants make
`compensation.py` commit the real forbidden acts — deciding `AUTONOMOUS_WITHIN_CAPS` for small
compensations in code, carrying an uncited `DEFAULT_GATE` literal, and registering a production gate
for `adjust_invoice` — and all three turn the respective guard **RED**. The battery is **36/36 caught,
0 escaped** at this landing, re-run on the committed tree.

### **THE JOB CONCLUSIONS ABOVE WERE SUPPLIED BY THE FOUNDER AND WERE NOT RE-READ BY THE LANDING SESSION.** `gh run view` has failed from this sandbox with a TLS interception error at every landing since `P6-CP-5`. A later session with network access should read run `33594219060` itself rather than trust this transcription. The founder chose to land M10 on the evidence that exists, treating the py3.11 and *Safety* cancellations as **non-product CI runtime limitations** rather than as evidence of an M10 defect; that is recorded as a **DECISION, not a verification** (`P6-D66`). It closes only by a CI run on this branch that concludes `SUCCESS`.

---

## 9. What the post-review correction changed — measured, not asserted

The reviewer saw `a43feae`. The landing candidate is `a833074`. **The delta was measured
mechanically at this landing:**

| Surface | Result |
|---|---|
| the whole `src/` tree | **byte-identical** — `bef554e379492b2c2dba494c65db3545ce45b750` at `715ddc0`, at `a43feae` **and** at `a833074` |
| `compensation.py`, `phase6_compensations.py`, `schema.py`, `phase2_tenant_first.py` | **byte-identical** across `a43feae → a833074` |
| migration runtime semantics | **unchanged** — no file under `src/freight_recon/migrations/` differs |
| checkpoint semantics | **unchanged** — `checkpoint.py` byte-identical across the entire M10 range `715ddc0~1..a833074` |
| M1–M9 machine semantics | **unchanged** — `work_item.py`, `pipeline_instance.py`, `external_effect.py`, `approval.py`, `observation.py`, `identity_binding_claim.py`, `conflict.py`, `expectation.py`, `exception.py`, `brake.py` all byte-identical across `715ddc0~1..a833074` |
| `.github/` | **byte-identical** across the entire M10 range — `41f76934b715f253da6e7f6a261c351186a7447b` |

What `a833074` **did** touch, and nothing else: `docs/implementation/CURRENT.md` (one line — the
`compensations` partition row), `docs/implementation/phase-0-baseline-manifest.yaml` (the REG-1
classification), a new `eval/phase0/gate_scan.py` (one shared statement of the ADR-010 boundary, so
three guards stop restating it and drifting), five guard test files, and
`scripts/mutate_phase6_compensation.py` (three added mutants and a scanner-level control).

### **SO THE HONEST SPLIT IS THIS.** The M10 **implementation** — machine, migration, wiring, and the
whole of `src/` — received a focused independent review by a session that did not build it, and that
review returned SUPPORTED. The **candidate correction** on top received targeted tests (§8's six, plus
the 63-test acceptance suite, the probe and the 36/36 battery) and a completed py3.12 CI suite. It did
**not** receive an independent review, and this document does not claim one for it.

---

## 10. What did NOT change

- **No runtime code.** The landing commit that carries this file changes three documents and nothing
  under `src/`, `eval/`, `scripts/` or `.github/`.
- **No P6 acceptance criterion is scored.** `criteria_scored` is `[]` on all **ten** checkpoints.
- **P6 is not COMPLETE.** `status: READY`, `execution_state: IN_PROGRESS`.
- **P7 is not unlocked.** `status: BLOCKED`, `execution_state: NOT_STARTED`.
- **Nothing is enabled in production.** M10 has **zero** production importers across **121** modules,
  and **no** production module's import closure reaches it. **Twenty** channel-capable modules were
  discovered and **none** reaches it. `modules that MINT a gate decision: ['checkpoint.py']`. No
  production module constructs a `GateRegistry` at all, so the registered-action-class population is
  structurally **EMPTY** — the sole `GateEntry` construction anywhere in the package is the kernel's
  own `GateRegistry._DEFAULT` fallback at `checkpoint.py:242`, which resolves an unregistered class to
  `HUMAN_APPROVAL_REQUIRED`. M10 imports no `checkpoint`, no `brake` and no timer service. The only
  things outside the package that reach it are its own suite, kit, probe and mutation battery. There
  is **no oversight queue, no dashboard, no notifier and no MTTR surface**, and `policy`, `rule` and
  `brake_lifecycle` modules do not exist — **M11, M12 and M13 are unbuilt.**
