> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This is evidence of a past moment, not status.** It is an INDEPENDENT REVIEW: it set no
> acceptance criterion, marked no phase complete, closed no risk, enabled nothing and authorized no
> external effect. It reviewed the `P6-CP-9` candidate (machine **M9 — the Exception**) at commit
> `a6e9d3b52a828b3e2094f281a04801222841a26f` (tree `7160f6e365a3eade4c44b33bc40ce159fbce24c7`,
> branch `p5/u5-1-g2-spec-correction`, working tree clean) and returned **SUPPORTED, confidence
> 0.88**.
>
> ### **IT DID NOT REVIEW THE COMMIT THAT CARRIES IT.** The landing commit that brought this file
> in-tree did not exist when the review was performed. Nothing here may be cited as an independent
> review of that commit.
>
> ### **P6-CP-9 IS A CHECKPOINT, NOT A PHASE ACCEPTANCE.** P6 is **NOT COMPLETE**, no P6 acceptance
> criterion is scored, and P7 is not unlocked. M9 continues to **ship dark**.
>
> ### **NO ADJUDICATION FOLLOWED THIS REVIEW, AND NONE IS OWED.** M9 is tier-1 under
> [`CLAUDE.md`](../../CLAUDE.md) §7 — it lands a migration and it is load-bearing for tenant
> isolation — which requires builder + **one focused independent review by someone who did not write
> it**, mutation proof that the guard can fail, and CI. The adjudication chains and finalizer rituals
> cited by the `P6-CP-1` and `P6-CP-2` records were retired in the 2026-08 engineering-process
> simplification and must not be revived on the strength of those older artifacts.
>
> ### **CI DID NOT CONCLUDE `SUCCESS` ON THIS COMMIT, AND THIS RECORD DOES NOT PRETEND OTHERWISE.**
> The workflow concluded `cancelled`. §8 states both halves of that exactly — including that Python
> 3.12 has **no execution** of M9's tests, not merely no verdict. Read it before citing this document
> as evidence of a green repository.

# P6-CP-9 — FOCUSED INDEPENDENT REVIEW — candidate `a6e9d3b`

**Verdict: `SUPPORTED` · confidence `0.88` · findings `0` · adjudications `0` · criteria `11/11 PASS`**

| | |
|---|---|
| **Reviewed tree** | commit `a6e9d3b52a828b3e2094f281a04801222841a26f`, tree `7160f6e365a3eade4c44b33bc40ce159fbce24c7`, branch `p5/u5-1-g2-spec-correction`. The review record's `reviewed_fingerprint` reads **`tracked_dirty: 0`, `untracked: 0`**, identity `a6e9d3b52a82/7160f6e365a3/-` |
| **Reviewer lineage** | A session that did not build M9. The review record states `inherited_builder_context: false` and the run's review ledger states `independent: true`, `superseded_by: ""`; reviewer session `46d5594c-535f-4691-a50f-9e42f3f57a5d`, builder session `f5f7931b-5e86-4b2b-aade-6373094db69b` |
| **Performed** | `2026-09-01T05:04:19+00:00` |
| **Source artifact** | Product Driver run `20260901-040704`, `accepted/independent-review.json` (separate repository, `neyma-product-driver`) — `iteration-03` promoted to `accepted`. Its prose is quoted verbatim below; nothing is upgraded, softened or summarised into a stronger claim |
| **Adjudications recorded** | **none** (`adjudications: []`) |
| **Findings** | **none** (`findings: []`). §7 records the nonblocking items this landing identified from the run's own evidence — they are **not** reviewer findings and are not presented as such |
| **Scope declared by the run** | `P6/M9`, parent phase `P6` (`READY` / `IN_PROGRESS`), `parent_phase_accepted: false`, `task_result: VERIFIED`, `task_outstanding: []`, `repository_unit_id: P6-CP-9` |
| **Review requirement** | `required: true`, triggered from `CLAUDE.md` §7 and `AGENTS.md` read at run time. **SATISFIED** by this review |
| **Reviewer executed the product** | **Yes.** `evidence_reproduced: true` and `claimed_evidence_reproduced: true` — see §4 |
| **Reviewer blocked on anything** | **No.** `blocked_on.kind: NONE` — though it names one oracle its harness refused; see §4.1 and §7 |

---

## 1. The verdict, verbatim

> "Reviewing P6/M9 (Exception) at HEAD a6e9d3b / tree 7160f6e365a3, working tree clean — the exact
> state named. I reproduced the product's own verification: eval/tests/test_phase6_exception.py (58
> passed), scripts/probe_phase6_exception.py (exit 0, 'behaviours as specified, 0 wrong'), and
> scripts/mutate_phase6_exception.py (21/21 mutants caught), plus neighbor regressions M1+M3 (239
> passed). Approved structural oracles hold: M9 imports M1's K-1 resolve_decision_ref with no second
> resolver defined anywhere; production importers of `exception` = [] (ships dark); the only script
> reaching it is its own probe. I read the migration and machine source directly and confirmed the
> guards the mutation battery defends are real, not decorative: the RESOLVED-requires-decision_ref
> CHECK and the named-decision-human CHECK, owner_id NOT NULL + FK into tenant_humans, a five-state
> inline CHECK with no sixth, the SEV0/SEV1/SEV2 CHECK, a BEFORE DELETE no-delete trigger, a
> conditional freeze CHECK, a tenant-first dedup index partial on state!='RESOLVED', and model-actor
> refusals on acknowledge/resolve/change_severity with no checkpoint/brake import. The builder's
> report asserts no phase-level or effect-level outcome, correctly leaves the tier-1 independent
> review PENDING (not self-awarded), and matches the clean tree. The task's scope (P6/M9 only; P6
> stays IN_PROGRESS) is respected. No discrepancies were raised by the auditor and I found none."

---

## 2. What M9 is, in one line

**M9 is the machine whose whole job is that something needing a human reaches a named person and is
never quietly forgotten.** A TMS write times out and the outcome is unknown. An Exception is raised
with a **named human owner from the moment it exists** and a severity beside it. An authenticated
human acknowledges it — which proves they **saw** it and proves nothing else — and it keeps ageing.
Nobody acts, so a durable timer moves it `OPEN → AGEING → ESCALATED`: louder, still owned, and
**never resolved by the clock**. Someone tries to close it with the string `"done"` and the database
refuses, because **closure is an event with a `decision_ref` that RESOLVES** to an authenticated
human decision. A model tries to clear it and is refused at any confidence.

### **AN EXCEPTION CLOSED WITHOUT A DECISION IS NOT CLOSED — IT IS FORGOTTEN.**

Five canonical states (`OPEN`, `ACKNOWLEDGED`, `AGEING`, `ESCALATED`, `RESOLVED`) as an inline
`CHECK` with **no sixth** — no `CANCELLED`, no `EXPIRED`, no `TIMED_OUT`, no `STALE`, no `CLOSED`.
Seven transitions `EC-1`…`EC-7`, an exact set match with §14 of
[`09-exception.machine.md`](../specifications/state-machines/09-exception.machine.md). Six F9
contracts minted and **no seventh** — `EC-3` and `EC-6` both emit `ExceptionResolved`. The finer
operational terms (`triage`, `assigned`, `investigating`, `awaiting_external`, `awaiting_human`,
`resolution_proposed`) are a `sub_status` **field** with a vocabulary disjoint from the state set,
never lifecycle states.

**M9 does not write a second K-1 resolver.** It imports M1's landed `resolve_decision_ref`. That is
the difference between "the `decision_ref` column is not null" and "a real authenticated human
decision exists and it RESOLVES" — the first is satisfied by the string `"done"`.

---

## 3. One tenant-first table enters the canonical partition

`exceptions` is the single table M9's migration creates. It was classified under
`tables_tenant_first` in [`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml) in the
**build** commit `b94f963`, which is why this landing carries no REG-1 adjudication of the kind
`P6-CP-8` needed: `test_phase0_tenant_posture.py::test_no_new_tenantless_table_appeared` was
satisfied before the tree was ever pushed.

### 3.1 The instruments the reviewer lacked, supplied at this landing

The reviewer verified the migration invariants by **reading the DDL** and its harness **refused two
oracles outright** (§4.1). Rather than carry those gaps forward as debt, this landing ran the
missing instruments and records what they returned. All three are read-only measurements over the
same tree; **no runtime file changed.**

**A fresh canonical database, built the way production builds one, then introspected — and every
load-bearing guard proven BY ATTEMPTING THE VIOLATION.** 31 canonical tables discovered, `exceptions`
among them. `PRIMARY KEY (tenant, exception_id)`. Three declared indexes, **zero** of them failing to
lead with `tenant`. 13 `NOT NULL` columns including `owner_id`, `source_ref`, `severity`, `state` and
`summary`. 22 foreign keys, three of them composite `(tenant, …)` pairs into `tenant_humans` for
`owner_id`, `acknowledged_by` and `decision_human_id`. **`severity` and `state` carry no `DEFAULT`**,
so neither can be silently supplied. **Nine attempted violations, nine refusals:**

| Attempted | Refused by |
|---|---|
| an ownerless Exception (`owner_id` NULL) | `NOT NULL constraint failed: exceptions.owner_id` |
| an owner who is not a recorded human of this tenant | `FOREIGN KEY constraint failed` |
| an owner belonging to **another tenant** | `FOREIGN KEY constraint failed` |
| a sixth lifecycle state `'CANCELLED'` | `CHECK constraint failed: state IN ('OPEN','ACKNOWLEDGED','AGEING','ESCALATED','RESOLVED')` |
| a sixth lifecycle state `'EXPIRED'` | the same `CHECK` |
| a fourth severity `'SEV3'` | `CHECK constraint failed: severity IN ('SEV0','SEV1','SEV2')` |
| `RESOLVED` with no `decision_ref` | `CHECK constraint failed: state <> 'RESOLVED' OR decision_ref IS NOT NULL` |
| `RESOLVED` with a `decision_ref` but no named human | `CHECK constraint failed: state <> 'RESOLVED' OR decision_human_id IS NOT NULL` |
| an Exception with no `source_ref` | `NOT NULL constraint failed: exceptions.source_ref` |

**Two positive controls were accepted** — a well-formed `OPEN` row, and a `RESOLVED` row carrying a
`decision_ref`, a `decision_ref_kind` from the two-member vocabulary `('AUDIT_EVENT','RULE')` and a
named human — and exactly **2 rows survive**. Without them the nine refusals would prove only that
the table rejects everything.

**The no-delete trigger and the dedup index, live.** `DELETE FROM exceptions` on an open row is
refused by `trg_exceptions_no_delete` with the machine's own prose — *"an exception is never deleted
… an exception closed without a decision is not closed, it is FORGOTTEN"*. A second open Exception
for the same `(tenant, source_ref, type)` is refused by
`ix_exceptions_one_open_per_cause`. Row count is unchanged at 2 after both attempts.

**The channel-join scan the reviewer's harness hard-blocked** (§4.1). Run here over a **discovered**
population rather than an enumerated one: 119 production modules scanned, **8 channel-capable
modules discovered** by their import of a transport library (`browser_session_health`,
`browser_use_write`, `cdp_readonly`, `cdp_session`, `delivery_dispatch`, `email_adapter`,
`imap_mailbox`, `inbox_discovery`). **Channel-capable modules whose import closure reaches
`exception`: `[]`.** **Transports reachable from `exception`'s own import closure: `[]`.** The
population is non-empty, so the negative is not vacuous.

**The seam-isolation oracle the reviewer cited by token and its harness refused** (`@a81c8e00`).
Reproduced here with docstrings structurally removed, so prose about a forbidden name can neither
pass nor fail it, and with the allowed set **read out of** `events/registry.md` rather than typed in:
6 F9 contracts plus the 1 F14 contract the registry grants to *any machine*. Results — `Exception[A-Z]…`
identifiers in the machine's code: exactly the **6 registered F9 names**; names passed to an emit
site: those 6 plus `IllegalTransitionAttempted`; **foreign machine domain events minted by M9: `[]`**;
**brake-engaging tokens: `[]`**; tables the migration creates: `['exceptions']`; **M10/M11/M12 tables
created: `[]`**.

> **The oracle fired wrongly twice before it was right, and that is recorded rather than hidden.** A
> first cut matched any `…Resolved`/`…Fired` suffix and flagged `Trigger.TIMER_RESOLVE =
> "TimerFiredToResolved"` — the name of an **illegal trigger M9 refuses**, not an event it mints. A
> second cut allowed only F9 and flagged `IllegalTransitionAttempted`, an F14 contract the registry
> grants to any machine and which **eleven** modules in the shipped package emit. Both were defects in the
> instrument, not in M9.

---

## 4. What the reviewer established ITSELF, and how

Its harness records **19 command attempts**: 6 `RUNTIME_REPRODUCED`, 3 `STRUCTURAL_VERIFIED`, 1
`EXPECTATION_FAILED`, 4 `REVIEWER_INSPECTED` (run and read, no deterministic expectation attached, so
nothing there was decided by machine), and 5 `REFUSED` by the harness's own layers.
`evidence_reproduced: true` and `claimed_evidence_reproduced: true`. The load-bearing results it
produced with its own hands:

| What it ran | What it showed |
|---|---|
| `git rev-parse HEAD` | `a6e9d3b52a828b3e…` — the tree under review is the declared target |
| `git rev-parse HEAD^{tree}` (twice, opening and closing the review) | `7160f6e365a3eade…` both times — the tree was **unchanged by the review** |
| `git status --porcelain` | empty output; see §4.1 for why the harness logged this as a failed expectation |
| `.venv/bin/python -m pytest -q -p no:cacheprovider eval/tests/test_phase6_exception.py` | **58 passed** |
| `.venv/bin/python scripts/probe_phase6_exception.py` | exit 0, **`behaviours as specified, 0 wrong`** |
| `.venv/bin/python scripts/mutate_phase6_exception.py` | **21/21 mutants caught** |
| AST scan of `src/freight_recon` | **119 production modules scanned**, **`production importers of exception: []`** |
| AST scan of `scripts` | **`scripts reaching exception: ['probe_phase6_exception.py']`** |
| `pytest … test_phase6_work_item.py test_phase6_external_effect.py` | **239 passed** — M1 and M3 unbroken with M9's table present |
| AST/regex read of the machine | `names imported from M1: ['DecisionRefUnresolvable', 'FailureDisposition', 'resolve_decision_ref']`; **`M9 imports the K-1 resolver: True`**; **`a second resolver defined in the machine: []`**; **`modules defining resolve_decision_ref outside M1: []`** |
| `grep` over `phase6_exceptions.py` | the `RESOLVED`-requires-`decision_ref` CHECK, the named-decision-human CHECK, `owner_id NOT NULL` + FK, the five-state CHECK, the `SEV0/SEV1/SEV2` CHECK, the `BEFORE DELETE` no-delete trigger, the conditional freeze CHECK, the tenant-first partial dedup index |
| `grep` over `exception.py` | model-actor refusals on `acknowledge`, `resolve` and `change_severity`; **no `checkpoint` import, no `brake` import** |
| `ls -la` of the five M9 artifacts | machine, migration, probe, mutation battery and suite all present on the reviewed tree |

**The reviewer ran no negative control of its own.** The probe declares a **66-member closed fault
vocabulary** across 11 composable CLI dimensions, and four out-of-vocabulary refusals (`not-a-real-fault`, `reopen-exception`,
`supersede-exception`, `correct-exception`); all four were exercised by the run's evaluator, not by
the reviewer's own hands. Stated here rather than rounded up. *(Re-run at this landing: all four exit
2 with corpus-grounded prose — e.g. `correct-exception` is refused because "entity §23 and machine
§25 say 'Correction rules. N/A'. Correction is the tidy-looking thing a build session adds; it would
let a wrong severity or a wrong owner be edited out of history.")*

### 4.1 Harness statuses that read like failures and are not — recorded, not tidied

**`git status --porcelain` is logged `EXPECTATION_FAILED`** — *"no output was captured, so no
substring assertion could hold"* — because the reviewer declared `expect_absent: ['exception.py',
'phase6_exceptions.py']` and the harness cannot evaluate an absence assertion against **correctly
empty** output. The working tree was clean; the harness has no status for *"the command was supposed
to print nothing, and it printed nothing."* This is the same status-vocabulary defect already
recorded as `P6-D39` (M5), `P6-D45` (M6), `P6-D51` (M7) and `P6-D56` (M8), in a new shape. Recorded
as `P6-D61`.

**Five of the 19 attempts were refused by the harness rather than by the product**, at three
different layers:

| Layer | Command | Re-issued and run? |
|---|---|---|
| `composition` | `git rev-parse HEAD && git write-tree …; git status …` | **Yes** — split into three single commands, all ran |
| `composition` | `ls -la …five artifacts… 2>&1` | **Yes** — re-issued without the redirect, ran |
| `vocabulary` | a large `python -c` combining an AST parse, a regex sweep and a `sqlite3` build | **Yes, in part** — a narrower `python -c` ran and produced the K-1 resolver result above |
| `vocabulary` | `@a81c8e00` — the seam-isolation oracle, cited by approved-command token | **No** |
| `guard` | the channel-join AST scan | **No** — hard-blocked as *"deploy tooling"*, a false positive on the module-name list it carried |

### **THE TWO ABANDONED ORACLES ARE THE ONE MATERIAL LIMIT ON THIS REVIEW, AND THEY ARE SUPPLIED AT THIS LANDING RATHER THAN CARRIED.** §3.1 reproduces both. The reviewer's own `blocked_on` note anticipated this for the first — *"its content … is independently reproduced by the probe and mutation battery, so nothing is left undetermined"* — and §3.1 goes further by running the oracle itself.

---

## 5. What Product Driver independently exercised

**Eleven scenarios, all `PASSED`, 615 assertions, 0 failed, 0 blocked, 0 skipped.** The acceptance
gate reads **VERIFIED** over the **10 required** scenarios; an eleventh, `S12`, is `required: false`
and also passed.

| Scenario | Origin | Risk category | Priority | Assertions | Outcome |
|---|---|---|---|---|---|
| `p6_m9_exception` | permanent | — | P0 | 478 | **PASSED** |
| `S2-closure-resolves` | generated | `safety_invariant` | P0 | 15 | **PASSED** |
| `S3-no-model-no-laundering` | generated | `authorization` | P0 | 8 | **PASSED** |
| `S4-no-forgetting-durable-timer` | generated | `safety_invariant` | P0 | 19 | **PASSED** |
| `S6-owner-from-creation` | generated | `missing_data` | P0 | 17 | **PASSED** |
| `S1-happy-lifecycle` | generated | `happy_path` | P1 | 11 | **PASSED** |
| `S7-five-states-substatus` | generated | `unexpected_state_transition` | P1 | 17 | **PASSED** |
| `S9-replay-reconstructs` | generated | `stale_state` | P1 | 12 | **PASSED** |
| `S10-ship-dark` | generated | `regression` | P1 | 20 | **PASSED** |
| `S11-migration-readiness` | generated | `regression` | P1 | 9 | **PASSED** |
| `S12-closed-fault-vocabulary` | generated | `malformed_input` | P2 | 9 | **PASSED** |

**This is the strongest generated-scenario contribution of any P6 landing**: `wave-01` proposed 12
and accepted **10** — against M8's one (`P6-D57`), M7's four (`P6-D52`) and M6's zero. See `P6-D62`
for the two that were filtered and why it costs nothing.

The run's `scoped_completion` reads `task_result: VERIFIED`, `task_outstanding: []`,
`parent_phase_accepted: false`, and its `does_not_imply` list names exactly what this landing also
refuses to claim: **P6 is not COMPLETE, no P6 acceptance criterion is scored, the units P6 still owes
are not built, the next phase is not unblocked, phase acceptance has not occurred, and nothing is
enabled in production or on live traffic.**

The run's evaluator additionally drove **live database inserts of its own** and recorded that
ownerless, non-recorded-owner, cross-tenant-owner, cross-tenant-source, `RESOLVED`-without-`decision_ref`,
`CANCELLED`, `EXPIRED` and `SEV3` rows were all refused with `IntegrityError` while two positive
controls were accepted and `rows surviving = 2`. §3.1 reproduces that independently at this landing.

### 5.1 The run took three iterations, and neither of the first two found a product defect

`state.json` records `iteration: 3`. The tree was **byte-identical at `a6e9d3b` with `dirty_file_count: 0`
across all three**. The two problems that drove the corrections were `LIVE_ENABLEMENT` and
`NEXT_PHASE_UNBLOCKED` flags raised by a claim-extractor reading the **builder's report prose** —
every flagged claim is recorded `source: "builder report"` — and the second was seeded by the
builder's own **disclaimer** (*"this does not imply a later phase is unblocked"*), whose negation the
extractor ignored. The evaluator's own decisive argument is recorded verbatim in `decision.json`: *"if
a status document were the source it would have flagged in iteration 1."* The third iteration
withdrew the phase-level and effect-level language in both directions. **No repository file was
edited in any iteration**, and `git-diff-stat.txt` is empty. Recorded as `P6-D63`.

---

## 6. The eleven criteria the reviewer assessed

All **PASS**, none `CANNOT_DETERMINE`.

| # | Criterion | Basis the reviewer recorded |
|---|---|---|
| 1 | **safety invariant** — never closed by silence; closure needs a `decision_ref` that RESOLVES; inactivity/`AutoClose`/expiry/sweep/reaper/timer cannot close one | the `CHECK` + `BEFORE DELETE` trigger (`phase6_exceptions.py:322,404`); `resolve()` calls M1's resolver (`exception.py:651`); mutants *RESOLVED with no decision_ref*, *resolver weakened to non-null*, *AutoClose added*, *no-delete disabled*, *timer resolves* all caught |
| 2 | **authorization** — only an authenticated human may acknowledge/resolve; a model may never own/ack/resolve/re-severity; M9 mints no gate decision and engages no brake | `actor_kind=='model'` guards at `:574`, `:624`, `:787`, `:1025`; no checkpoint/brake import; probe `M9 MINTS NO GATE DECISION`, `M9 ENGAGES NO BRAKE`; mutants *gate-decision minter*, *brake engager*, *model permitted to resolve* caught |
| 3 | **missing data** — ownerless/severity-less/source-less Exception structurally impossible; severity change without previous value or reason refused | `owner_id`/`source_ref`/`severity`/`summary` NOT NULL and the owner FK (`:251,261,266,312`); mutants *owner NOT NULL dropped*, *previous_severity dropped* caught |
| 4 | **unexpected state transition** — five states as a CHECK with no sixth; `sub_status` is a field, not a state | the state CHECK (`:255,120`) and the disjoint `sub_status` CHECK (`:333`); mutants *sixth state added*, *sub_status promoted* caught |
| 5 | **boundary** — severity a closed three-member CHECK, never defaulted; thresholds caller-supplied | `EXCEPTION_SEVERITIES` + inline CHECK (`:134,251`); probe `THE AGEING THRESHOLD IS CALLER-SUPPLIED`, `SEVERITY IS SEV0, SEV1 OR SEV2 AND NOTHING ELSE` |
| 6 | **concurrency** — optimistic version check; a stale version writes zero rows and raises; indexes tenant-first | `version NOT NULL CHECK(version>=1)` (`:256,317`); indexes tenant-first (`:363,370`); probe `A LOST UPDATE … IS REFUSED`, `A STALE VERSION NEVER OVERWRITES` |
| 7 | **cross-tenant** — the same source in two tenants is isolated; no cross-tenant own/resolve/source/read | `PRIMARY KEY (tenant, exception_id)`, tenant-first FKs and indexes (`:309,312-314,363`); mutants *owner from another tenant*, *tenant dropped from dedup* caught; probe printed all four cross-tenant fail-closed lines |
| 8 | **malformed input / permanent-failure classification supplied, not inferred** | probe `CLASSIFICATION IS SUPPLIED, NEVER INFERRED FROM A MESSAGE`, `PERMANENT … RAISES IMMEDIATELY WITH ZERO RETRIES`; mutants *PERMANENT retried*, *permanence inferred from message* caught |
| 9 | **regression** — M1/M3/M5/M7/M8 unchanged; M9 ships dark | `production importers of exception: []` over 119 modules; `scripts reaching exception: ['probe_phase6_exception.py']`; M1+M3 suites 239 passed; probe asserts the neighbours unchanged and M10/M11/M12 not built |
| 10 | **K-1 resolver reuse** — M9 imports M1's resolver rather than defining a second | `M9 imports the K-1 resolver: True`; `a second resolver defined in the machine: []`; `modules defining resolve_decision_ref outside M1: []` |
| 11 | **scope discipline** — the task completes no phase, scores no acceptance criterion, edits no status surface | `git status --porcelain` empty at `a6e9d3b`; the builder's report withdraws all phase/effect claims and leaves the tier-1 review PENDING; the registry still records P6 `READY`/`IN_PROGRESS` |

---

## 7. Minor and nonblocking items — recorded, not actioned

### **THE INDEPENDENT REVIEW RETURNED ZERO FINDINGS.** Everything below was identified **at this landing** from the run's own structured evidence, the M9 source, the specification corpus and the CI record. **None is a reviewer finding and none may be cited as one.** Each is recorded, not actioned ([`CLAUDE.md`](../../CLAUDE.md) §13). None can produce a wrong customer outcome, violate an invariant, or make a later phase unsafe, and the machine ships dark.

They are carried in [`IMPLEMENTATION-REGISTRY.yaml`](IMPLEMENTATION-REGISTRY.yaml) as **`P6-D59`
through `P6-D64`**: the `cancelled` CI workflow and what Python 3.12 does *not* establish (`P6-D59`);
the absence of any CI job running M9's probe or mutation battery (`P6-D60`); the harness status
vocabulary (`P6-D61`); the two filtered generated scenarios (`P6-D62`); the three-iteration
report-prose loop (`P6-D63`); and the pre-existing `W26` `SETUP-FAIL` in M1's mutation battery, which
is **not M9's** and was deliberately not appeased by editing M9 (`P6-D64`).

**`M9-AQ-1` … `M9-AQ-6` remain REPORTED, not resolved** — the human-vs-active-rule closure (`RULE`
refuses today and `P6-D4` stays open at M12), cancellation having no state and no event, the
polymorphic `source_ref` FK, who wires the five landed to-Exception seams, what the freeze is, and
`EC-4`'s from-set. M9 implements only where every canonical reading agrees. **`M7-AQ-1`, `M7-AQ-2`
and `M7-AQ-3` are untouched.** **`P6-D40` is carried forward unchanged and was not re-verified here.**
**`V10` thresholds stay caller-supplied**, with no business default invented.

**Two carried residuals name `closes_at: M9`, and M9 closes neither.** `P6-D1` — whether
`ExceptionResolved` may stand in for K-1's missing `HumanResolved`, whose disposition says *"M9 owns
that determination"* — is **not determined here**; that is `M9-AQ-1`, and M9 builds the human branch,
imports M1's resolver unchanged and leaves the `RULE` branch **refusing**. `P6-D3` — the Sev-0 raise
for an owner retired around `offboard_human` — is **not closed either**; M9 supplies a machine that
can carry a `SEV0` Exception, but nothing wires M1's ownerless detector to it, which is `M9-AQ-4`.
Both rows stay open with their `closes_at` markers unchanged. **A landing that quietly moved them
would be the claim-outliving-its-warrant failure this repository keeps catching.**

---

## 8. ### CI — the honest record. The workflow did NOT conclude `SUCCESS`

**Run `33460644572` concluded `cancelled`, and `cancelled` is not `success`.** Nothing in this
document says otherwise.

| Job | Conclusion |
|---|---|
| *Safety invariants (fast)* | **SUCCESS** |
| *P6/M3 effect-grant probe + mutation* | **SUCCESS** |
| *Full test suite (py3.11)* | **SUCCESS** — **3099 passed, 1 skipped** |
| *Full test suite (py3.12)* | **CANCELLED** at the runtime ceiling, ~55%, **no test-failure marker observed before cancellation** |
| *Risk radar* | **skipped** (pull-request-only) |

**Measured at this landing, not assumed.** `pytest eval --collect-only -q` on this exact tree collects
**3100** tests — matching py3.11's `3099 + 1` **exactly** — and
`eval/tests/test_phase6_exception.py` occupies positions **2107–2164**, **68.0%–69.8%** of the run.
So the py3.11 job **ran all 58 of M9's tests and they passed**.

### **WHAT PYTHON 3.12 DOES NOT ESTABLISH.** Cancelled at ~55%, it stopped **before** that range. The honest statement is not "no verdict" but **NO EXECUTION**: the repository has **no Python 3.12 run of M9's 58 tests on this commit, neither failing nor passing.**

**The `F` that ran 33452247720 exposed is fixed, and a completed job establishes it.** That earlier
run printed a real `F` at ~20% on **both** interpreters:
`test_false_green_defenses.py::test_every_corpus_scanning_negative_assertion_proves_its_population`.
It was M9-caused and the guard was right — M9's build commit added four corpus-scanning negative
assertions and none proved its population, which `a6e9d3b` corrected by anchoring each. Measured
here: that test sits at position **611 of 3100 — 19.7%**, matching the observed failure point, and it
is inside the `Full test suite` job that concluded **SUCCESS** on py3.11. The cancelled py3.12 job
passed **through** 19.7% without emitting a failure marker, which is corroboration rather than the
basis.

*(Denominator and caveat both stated: the collection was taken locally with the repository's own
command, while CI's percentage is pytest's own progress display over its own collection under its own
interpreter — so this is strong evidence of ordering rather than a byte-exact reproduction, though the
3100/3100 agreement with py3.11 is unusually direct corroboration that the two collections are the
same.)*

### **THE JOB CONCLUSIONS ABOVE WERE SUPPLIED BY THE FOUNDER AND WERE NOT RE-READ BY THE LANDING SESSION.** `gh run view` has failed from this sandbox with a TLS interception error at every landing since `P6-CP-5`. A later session with network access should read run `33460644572` itself rather than trust this transcription. The founder chose to land M9 on the evidence that exists, treating the py3.12 cancellation as a **non-product CI runtime limitation** rather than as evidence of an M9 defect; that is recorded as a **DECISION, not a verification** (`P6-D59`). It closes only by a CI run on this branch that concludes `SUCCESS`.

---

## 9. What did NOT change

- **No runtime code.** The landing commit that carries this file changes three documents and nothing
  under `src/`, `eval/`, `scripts/` or `.github/`. `exception.py`, `phase6_exceptions.py`,
  `checkpoint.py`, `external_effect.py`, `identity_binding_claim.py`, `conflict.py`, `observation.py`,
  `expectation.py` and `work_item.py` are byte-identical to the commits that landed them.
- **No P6 acceptance criterion is scored.** `criteria_scored` is `[]` on all **nine** checkpoints.
- **P6 is not COMPLETE.** `status: READY`, `execution_state: IN_PROGRESS`.
- **P7 is not unlocked.** `status: BLOCKED`, `execution_state: NOT_STARTED`.
- **Nothing is enabled in production.** M9 has zero production importers across 119 modules, mints no
  gate decision (`modules that MINT a gate decision: ['checkpoint.py']`), engages no brake, joins no
  channel, and the production `GateRegistry` stays **EMPTY**. There is **no oversight queue, no
  dashboard, no notifier and no MTTR surface** — M9 owes the row and the tenant-first index, and
  builds none of those.
- **M10 is not built.** The next build checkpoint is **M10 — the Compensation**.
