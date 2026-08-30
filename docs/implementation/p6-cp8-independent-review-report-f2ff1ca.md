> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This is evidence of a past moment, not status.** It is an INDEPENDENT REVIEW: it set no
> acceptance criterion, marked no phase complete, closed no risk, enabled nothing and authorized no
> external effect. It reviewed the `P6-CP-8` candidate (machine **M8 — the Expectation**) at commit
> `f2ff1ca459de5859b675a1e72af7be43ce70ace2` (tree `fdf478f63b35cb62ddd99a656247bf44cc431d04`,
> branch `p5/u5-1-g2-spec-correction`, working tree clean) and returned **SUPPORTED, confidence
> 0.90**.
>
> ### **IT DID NOT REVIEW THE COMMIT THAT CARRIES IT.** The landing commit that brought this file
> in-tree did not exist when the review was performed. Nothing here may be cited as an independent
> review of that commit.
>
> ### **P6-CP-8 IS A CHECKPOINT, NOT A PHASE ACCEPTANCE.** P6 is **NOT COMPLETE**, no P6 acceptance
> criterion is scored, and P7 is not unlocked. M8 continues to **ship dark**.
>
> ### **NO ADJUDICATION FOLLOWED THIS REVIEW, AND NONE IS OWED.** M8 is tier-1 under
> [`CLAUDE.md`](../../CLAUDE.md) §7 — it lands a migration and it is load-bearing for tenant
> isolation — which requires builder + **one focused independent review by someone who did not write
> it**, mutation proof that the guard can fail, and CI. The adjudication chains and finalizer rituals
> cited by the `P6-CP-1` and `P6-CP-2` records were retired in the 2026-08 engineering-process
> simplification and must not be revived on the strength of those older artifacts.
>
> ### **CI DID NOT CONCLUDE `SUCCESS` ON THIS COMMIT, AND THIS RECORD DOES NOT PRETEND OTHERWISE.**
> The workflow concluded `cancelled`. It is nonetheless the **strongest CI position of any P6
> landing since `P6-CP-6`** — one full suite completed and executed M8's own tests — and §8 states
> both halves of that exactly. Read it before citing this document as evidence of a green
> repository.

# P6-CP-8 — FOCUSED INDEPENDENT REVIEW — candidate `f2ff1ca`

**Verdict: `SUPPORTED` · confidence `0.90` · findings `0` · adjudications `0` · criteria `9/9 PASS`**

| | |
|---|---|
| **Reviewed tree** | commit `f2ff1ca459de5859b675a1e72af7be43ce70ace2`, tree `fdf478f63b35cb62ddd99a656247bf44cc431d04`, branch `p5/u5-1-g2-spec-correction`. The review record's `reviewed_fingerprint` reads **`tracked_dirty: 0`, `untracked: 0`**, identity `f2ff1ca459de/fdf478f63b35/-` |
| **Reviewer lineage** | A session that did not build M8. The review record states `inherited_builder_context: false` and the run's review ledger states `independent: true`, `superseded_by: ""`; reviewer session `1329e155-cde7-4f24-b213-ec1eb291f31a`, builder session `908d199e-b93d-4b81-a6dd-8faa989255fe` |
| **Performed** | `2026-08-29T09:16:10+00:00` |
| **Source artifact** | Product Driver run `20260829-084631`, `accepted/independent-review.json` (separate repository, `neyma-product-driver`) — the run's only iteration, `iteration-01` promoted to `accepted`. Its prose is quoted verbatim below; nothing is upgraded, softened or summarised into a stronger claim |
| **Adjudications recorded** | **none** (`adjudications: []`) |
| **Findings** | **none** (`findings: []`). §7 records the nonblocking items this landing identified from the run's own evidence — they are **not** reviewer findings and are not presented as such |
| **Scope declared by the run** | `P6/M8`, parent phase `P6` (`READY` / `IN_PROGRESS`), `parent_phase_accepted: false`, `task_result: VERIFIED`, `task_outstanding: []` |
| **Review requirement** | `required: true`, triggered from `CLAUDE.md` §7 and `AGENTS.md` read at run time. **SATISFIED** by this review |
| **Reviewer executed the product** | **Yes.** `evidence_reproduced: true` and `claimed_evidence_reproduced: true` — see §4 |
| **Reviewer blocked on anything** | **No.** `blocked_on.kind: NONE` — *"The review concluded on reproduced runtime and structural evidence against the declared tree; nothing blocked it."* |

---

## 1. The verdict, verbatim

> "Reviewing P6/M8 (the Expectation) at HEAD f2ff1ca / tree fdf478f, clean working tree — the exact
> declared state. M8 is fully implemented and committed (commits 96b7cb3, c950a83, f2ff1ca); the
> task's correct posture was verification, not rebuild. I reproduced the load-bearing evidence myself
> against the real tree: the deterministic probe reports 'behaviours as specified, 0 wrong' (exit 0);
> the mutation battery catches 21/21 mutants including honesty-split removal,
> OVERDUE-without-healthy-coverage, absent/partial coverage read as health, dropped uniqueness,
> weakened OCC, UTC-instead-of-local evaluation, dropped owner CHECK, confidence-as-guard, an
> introduced sweep/reaper, an M9 exceptions table, and a gate-mint import (exit 0); the pytest suite
> passes 72/72 (exit 0); and three malformed-input negative controls (unknown/reopen/supersede
> faults) fail closed with readable messages and no traceback (exit 2). Structurally I read the
> migration DDL and confirmed the two load-bearing guards are real database constraints, not Python
> branches: the honesty-split CHECK (state <> 'OVERDUE' OR (coverage_ref IS NOT NULL AND
> coverage_health = 'HEALTHY')) reinforced by a composite FK (tenant, coverage_ref, coverage_health)
> into observation_coverage(tenant, coverage_id, health), plus the partial unique index ON
> expectations (tenant, expectation_key) WHERE state IN ('RAISED') and the owner CHECK (state NOT IN
> human-owned OR owner_id IS NOT NULL). Ship-dark is confirmed: zero production importers of
> expectation.py, only probe_phase6_expectation.py reaches it, no channel join, no health probe, and
> only checkpoint.py mints a gate decision. The two tests commit c950a83 de-vacuumed
> (expiry-never-silence, forcing-overdue-illegal) assert over proven non-empty populations with
> positive, negative, and security-event checks. Scope is P6/M8 only: this scores no P6 phase
> criterion and P6 remains IN_PROGRESS, consistent with the registry's 0-of-0 weighted progress."

---

## 2. What M8 is, in one line

**M8 tells "the POD never came" apart from "we were not watching."** A load delivers and a POD is
owed by 17:00 at the Denver facility. The deadline passes. If the mailbox was demonstrably **HEALTHY**
across the whole window, the Expectation is `OVERDUE` and **a named human owns it**. If the channel
was `DOWN`, `UNKNOWN`, only `PARTIAL`, or there is **no coverage record at all**, it is
`INDETERMINATE` instead — because **accusing a counterparty of a failure that was ours is the one
thing this machine may never do**. That difference is a database `CHECK` reinforced by a composite
foreign key, **not a branch and not a matter of tone**.

### 2.1 The transition table — re-derived mechanically, not carried

The `Still owed` figure in [`CURRENT.md`](CURRENT.md) is **derived at each landing by parsing §14
of all thirteen machine files under `docs/specifications/state-machines/` and counting table rows**,
never by carrying the previous number. At this landing that parse **discovered 13 machine files and
counted 134 rows** — matching the registry's `expected_production_outputs` of "134 transitions" —
distributed as:

| Machine | §14 rows |
|---|---|
| M1 work item | 14 |
| M2 pipeline instance | 25 |
| M3 external effect grant | 13 |
| M4 approval | 11 |
| M5 observation | 8 |
| M6 identity binding claim | 11 |
| M7 conflict | 7 |
| **M8 expectation** | **8** |
| M9 exception | 7 |
| M10 compensation | 9 |
| M11 policy | 7 |
| M12 rule | 9 |
| M13 brake | 5 |
| **total** | **134** |

M8 contributes exactly `EX-1`, `EX-2`, `EX-3`, `EX-3i`, `EX-4`, `EX-5`, `EX-6`, `EX-7` — an **exact
set match** with §14 of `08-expectation.machine.md`, verified at this landing by parsing the ids out
of `src/freight_recon/expectation.py` and comparing sets. The only other `EX-*` token in the module
is `EX-6i`, and it appears **twice, both times as a negation** — *"there is no `EX-6i`"* — which is
how the module refuses to widen `EX-6`'s from-set rather than inventing a transition. Written after
M8: 14 + 25 + 13 + 11 + 8 + 11 + 7 + 8 = **97 of 134**, so **37 remain**.

### 2.2 The shape the database enforces — introspected LIVE at this landing

The reviewer verified these by **reading** the migration DDL (§7, `P6-D56`). At this landing they
were re-verified with the stronger instrument the reviewer's own command vocabulary had refused it:
a **fresh canonical database built the way production builds one**, introspected, with the
load-bearing violation **attempted rather than read**.

- **31 canonical tables discovered**; `expectations` and `observation_coverage` both present.
- **Six canonical states**, inline `CHECK`ed: `RAISED`, `DISCHARGED`, `OVERDUE`, `INDETERMINATE`,
  `CANCELLED`, `EXPIRED`. **There is no seventh** — no `TIMED_OUT`, no `STALE`, no bare `RESOLVED`
  imported from M9, no `SUPERSEDED`.
- **The honesty split is a database constraint**: `CHECK (state <> 'OVERDUE' OR (coverage_ref IS NOT
  NULL AND coverage_health = 'HEALTHY'))`, reinforced by `FOREIGN KEY (tenant, coverage_ref,
  coverage_health) REFERENCES observation_coverage (tenant, coverage_id, health)` so
  `coverage_health` **cannot lie about the row it names**. ### **PROVEN BY ATTEMPTING THE VIOLATION,
  NOT BY READING IT**: inserting `state='OVERDUE'` with `coverage_ref IS NULL` and
  `coverage_health='DOWN'` is **refused by the live database** with `IntegrityError`.
- **The coverage health vocabulary is closed and has four members** — `HEALTHY`, `DOWN`, `UNKNOWN`,
  `PARTIAL`. ### **`ABSENT` IS NOT AMONG THEM, AND `health` CARRIES NO `DEFAULT`.** That is the
  structural form of M-32: **absence is NO ROW, never a health value**, so blindness can never be
  silently recorded as a positive assertion that we were watching.
- **`expected_source` is `NOT NULL`** — there is no Expectation without a declared channel.
- **The human-owner requirement is a `CHECK`**: a human-owned state without `owner_id` is
  structurally impossible, and `owner_id` is FK-backed into `tenant_humans`.
- **Tenant-first**: the `PRIMARY KEY` leads with `tenant`, and of the **5 explicitly-declared
  indexes** across the two tables (auto-indexes excluded from the denominator), **zero fail to lead
  with `tenant`**.
- **The concurrency invariant** is `CREATE UNIQUE INDEX ix_expectations_one_live_per_key ON
  expectations (tenant, expectation_key) WHERE state IN ('RAISED')` — **tenant-first and partial**:
  at most one live Expectation per owed observation, while discharged and expired history accumulates
  freely.

**Seven F8 contracts are registered and only those**, verified at this landing against
`event_contracts_data.json` (**118 registered contracts scanned**): `ExpectationRaised` (`EX-1`),
`ExpectationDischarged` (`EX-2`, `EX-4`), `ExpectationOverdue` (`EX-3`), `ExpectationIndeterminate`
(`EX-3i`), `ExpectationReVersioned` (`EX-5`), `ExpectationCancelled` (`EX-6`), `ExpectationExpired`
(`EX-7`). **All eight transitions are covered by seven events and no eighth event is minted** —
`EX-2` and `EX-4` are the two discharge paths and share one contract.

---

## 3. Two tenant-first tables enter the canonical partition

The M8 build commit `96b7cb3` registered `expectations` and `observation_coverage` in
[`CURRENT.md`](CURRENT.md)'s tenant-first partition, and `f2ff1ca` adjudicated them into
[`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml) under `tables_tenant_first` —
**never** `tables_tenant_exempt`. That partition is asserted mechanically on every CI run by
`eval/tests/test_bootstrap_hermeticity.py::test_the_canonical_table_partition_is_exact_and_disjoint`
(which now pins `p6_expectations_tenant: 2`) and by
`eval/tests/test_phase0_tenant_posture.py::test_no_new_tenantless_table_appeared`.

### **THAT SECOND GUARD WENT RED FIRST, AND IT WAS RIGHT TO.** CI run `33240868415` failed it on
Python 3.12 with *"NEW table(s) not in the baseline manifest: ['expectations',
'observation_coverage']"*. That was not a timeout, not flake and not an M8 runtime defect: `REG-1`
requires every new persisted table to be **deliberately classified**, and `96b7cb3` landed two tables
without the adjudication row. `f2ff1ca` is the repository-control correction — **no guard weakened,
skipped, xfailed or taught M8's names, and no allowance created**. **P6/M8 declares no tenant-exempt
table.**

---

## 4. What the reviewer established ITSELF, and how

The reviewer declared **11 commands with named, checkable expectations** and its harness records
**21 command attempts**. `evidence_reproduced: true` and `claimed_evidence_reproduced: true`. The
load-bearing results it produced with its own hands:

| What it ran | What it showed |
|---|---|
| `git rev-parse HEAD` / `HEAD^{tree}` / `git status --porcelain` / `git log --oneline -8` | `f2ff1ca459de…` / `fdf478f63b35…`, status **empty** — the tree under review is the declared target and is clean |
| `.venv/bin/python scripts/probe_phase6_expectation.py` | exit 0, 82 cases, **`behaviours as specified, 0 wrong`**, every required capability literal printed and **zero** forbidden `### … ###` collapse banners |
| `.venv/bin/python scripts/mutate_phase6_expectation.py` | **21/21 mutants caught** |
| `.venv/bin/python -m pytest eval/tests/test_phase6_expectation.py -q` | **72 passed** |
| `pytest … --collect-only -q` | the 72-case denominator, collected rather than asserted |
| `probe … --inject not-a-real-fault` | exit 2 — *"unknown fault … The fault vocabulary is CLOSED and BOUNDED"*, then the full vocabulary printed |
| `probe … --inject reopen-expectation` | exit 2 — refused: *"entity §27 and machine §24 say 'Reopening rules. N/A'. A probe that accepted it would produce passing evidence for a transition the corpus states does not exist."* |
| `probe … --inject supersede-expectation` | exit 2 — refused: *"a re-versioned deadline is NOT a supersession; there is no SUPERSEDED state in registry §4's M8 row and no ExpectationSuperseded event is registered anywhere"* |
| AST scan of `src/freight_recon` | **117 production modules scanned**, **`production importers of expectation: []`** |
| AST scan of `scripts` | **`scripts reaching expectation: ['probe_phase6_expectation.py']`** |
| Channel-join scan | **`modules joining the expectation machine to a channel: []`**; **`production coverage health probes: []`** |
| Gate-mint scan | **`modules that MINT a gate decision: ['checkpoint.py']`** — M8 is not a second gate |
| `ls -la` of the three M8 artifacts | the machine, the probe and the mutation battery all present on the reviewed tree |

**The probe's fault vocabulary declares four negative controls; the reviewer ran three of them.**
The fourth (`correct-expectation`) is exercised by the run's permanent scenario, not by the
reviewer's own hands — stated here rather than rounded up to four.

### 4.1 Harness statuses that read like failures and are not — recorded, not tidied

**Four** outcomes are recorded in `executed_commands` with `execution_failed: true` and
`exit_code: null` **while every one of them behaved correctly**: the three exit-2 negative controls
(whose captured stderr **is** the correct refusal) and `probe … --help`, which argparse exits
non-zero on for this script. This is the same harness status-vocabulary defect already recorded as
`P6-D39` (M5), `P6-D45` (M6) and `P6-D51` (M7): the harness has no status for *"the command was
supposed to fail, and it failed correctly."* **The refusals are right; the labels are wrong.**
Recorded as `P6-D56`, not tidied away.

**Three of the 21 attempts were refused by the harness rather than by the product** — two at the
`composition` layer (`&&`/`;`-joined command chains, **re-issued as separate commands, all of which
ran**) and one at the `vocabulary` layer (the production-importer AST scan, **re-issued in approved
form and ran**). ### **UNLIKE `P6-D51`, EVERY REFUSED COMMAND WAS RE-ISSUED AND EXECUTED.** No
oracle was abandoned. The one instrument the reviewer did **not** obtain was a live-database DDL
introspection; it read `src/freight_recon/migrations/phase6_expectations.py` instead, and its own
criteria basis says so ("Structural: DDL … lines 261/267"). **That gap is closed at this landing
rather than carried**: §2.2 records a fresh canonical database introspected with the honesty-split
violation attempted and refused.

---

## 5. What Product Driver independently exercised

**Two scenarios, both `PASSED`, 408 assertions, 0 failed, 0 blocked, 0 skipped.**

| Scenario | Origin | Assertions | Outcome |
|---|---|---|---|
| `p6_m8_expectation` | permanent | 396 | **PASSED** |
| `S1-owed-observation-happy-lifecycle` | generated | 12 | **PASSED** |

The acceptance gate reads **`VERIFIED` — 2/2 required scenarios passed with resolvable evidence**,
and every acceptance-blocking risk the run named has a passing scenario behind it: the `P0`
safety-invariant risk (that M8's natural product form — a live tracking / SLA / "what is late"
surface — must **not** arrive with it), the `P0` missing-data risk (that `health` must carry no
`ABSENT` member and no `DEFAULT`, or blindness reads as a positive health assertion), the `P0`
restart-recovery risk (that the deadline must ride P5's `durable_timers` rather than an in-memory
sleep or a background scan), the `P0` regression risk (that M8 must FK only into tables that exist
and must build no M9–M12 table), the `P1` unexpected-state-transition risk (an invented eighth event
or a leaked M9 contract name), and the `P1` happy-path risk. ### **§7 `P6-D57` records what this
coverage cost**: the generated half of it is the **thinnest of any P6 landing except M6's zero**.

### 5.1 Mutation evidence — 21/21, each guard proven able to fail

### **A GUARD NEVER SEEN TO FAIL IS A DECORATION** ([`CLAUDE.md`](../../CLAUDE.md) §6). Each mutant
reintroduces a specific real defect and is caught:

1. `INDETERMINATE` removed from the honesty split — a **blind window routed to `OVERDUE`**
2. `OVERDUE` allowed without a healthy `coverage_ref` — the entity §16 `CHECK` widened
3. **absent** coverage treated as healthy — the M-32 fail-closed default flipped
4. **partial** coverage treated as healthy — the "throughout the window" span check dropped
5. the declared `expected_source` requirement dropped — an Expectation with no channel
6. the one-live-per-key index loses `UNIQUE` — two live `RAISED` for one owed observation
7. the partial index loses its `WHERE` clause — history collides with live rows
8. the **tenant** dropped from the uniqueness boundary — one key in two tenants coalesces
9. an **unbound** observation allowed to discharge — the entity §13 `BOUND` guard dropped
10. a **late arrival rejected** because the deadline passed — a late POD is still a POD
11. the terminal-age timer fires **silently** — `EX-7` expiry skipped
12. the deadline **history dropped** — `EX-5` re-versions and forgets
13. the **OCC predicate weakened** — a stale version accepted, a lost update
14. a facility appointment evaluated **in UTC** instead of facility-local — the DST defect
15. the **owner requirement dropped** from the human-owned states — the `AC-SAFE-028` `CHECK` widened
16. **confidence becomes a guard input** — `1.0` forces the `OVERDUE` branch
17. **replay recomputes from the current channel** rather than the recorded coverage
18. a **sweep/reaper** introduced beside the durable timer
19. an **M9 `exceptions` table** created — an unauthorized neighbouring machine's storage
20. M8 made a **gate-decision minter** — crossing `CLAUDE.md` rule 17
21. the **ship-dark posture weakened** — a production module imports the machine

### 5.2 Regressions — run WITH M8's tables present in the schema

P3 **216**, P4 **99**, P5 **561**, M1–M7 **591**, all passed, and the **M5, M6 and M7 probes each
still report `behaviours as specified, 0 wrong`** with `expectations` and `observation_coverage` in
the schema. Fresh and migrated canonical databases both report `schema_readiness_problems == []`,
with both M8 tables present, tenant-first, and no foreign key pointing at a table that does not
exist.

### 5.3 Ship-dark posture — measured, not asserted

Re-measured by this landing session independently of the run, over **discovered** populations with
the denominator printed (`CLAUDE.md` §6 — never enumerate filenames in a guard): **117** production
modules scanned → `production importers of expectation: []`; **74** scripts scanned →
`['probe_phase6_expectation.py']`; **165** eval modules scanned →
`['test_phase6_expectation.py']`; channel-join scan → `[]`; gate-mint scan → `['checkpoint.py']`.
No production module imports the machine, nothing joins it to an inbound or outbound channel, there
is no coverage-health probe or poller, and `checkpoint.py` remains the sole minter of a gate
decision. The production `GateRegistry` stays **EMPTY**.

---

## 6. The seams M8 preserved, and the landed units it did not touch

**M8 builds no neighbour to satisfy prose about one.** `EX-3` (`OVERDUE`) and `EX-3i`
(`INDETERMINATE`) are the seam an **Exception (M9)** will one day consume, and M8 leaves it as what
it is: a **durable, retained, human-owned row and its own F8 event**. It mints no `ExceptionRaised`,
creates no `exceptions` table, and an overdue Expectation **does not quietly become a Conflict**.

Verified at this landing by `git diff --stat 96b7cb3~1 f2ff1ca` restricted to the protected machines,
which returns **empty**: `checkpoint.py`, `external_effect.py`, `identity_binding_claim.py`,
`conflict.py` and `observation.py` are **byte-identical** across the entire M8 commit range. **No
authority question was answered by editing a landed unit.**

**Two M7 artifacts were edited inside the M8 build range, and it is not a rebuild of M7.**
`test_phase6_conflict.py` and `probe_phase6_conflict.py` each carried a forward-looking assertion
that `expectations` is **not** built — true at the `P6-CP-7` landing, false the moment M8's migration
exists. `96b7cb3` narrows both forbidden sets to `{exceptions, compensations, policies, rules}` and
says why at the site — the same correction M6's forbidden set received when M7 landed. **`conflict.py`
itself is untouched** (see above). §7 `P6-D58` records the one honesty defect in how that was
written.

---

## 7. Minor and nonblocking items — recorded, not actioned

### **THE INDEPENDENT REVIEW RETURNED ZERO FINDINGS AND ZERO ADJUDICATIONS.** Nothing below is a
reviewer finding and none may be cited as one. Each was identified at this landing from the run's
own structured evidence, the M8 source, the specification corpus and the CI record. Each is
**RECORDED, NOT ACTIONED** ([`CLAUDE.md`](../../CLAUDE.md) §13 — the debt row is the complete
deliverable). **None can produce a wrong customer outcome, violate an invariant, or make a later
phase unsafe**, and the machine ships dark.

### `P6-D53` — the workflow concluded `cancelled`, and py3.12 has no result · `minor` · CI

GitHub Actions run `33245212866` on this commit concluded **`cancelled`**, so **this commit has no
green CI conclusion** and this record does not claim one. See §8 for the job-by-job detail and for
the measured statement of exactly which interpreter did and did not execute M8's tests. It closes
only by a CI run on this branch that concludes `SUCCESS`.

### `P6-D54` — CI does not execute M8's probe or mutation battery · `minor` · CI coverage

The `effect-grant` job runs M3's probe and battery on every push precisely because `pytest eval` does
not invoke them. There is no equivalent job for M4 (`P6-D33`), M5 (`P6-D37`), M6 (`P6-D43`), M7
(`P6-D49`) or M8 — verified mechanically at this landing by the **absence of any `phase6_expectation`
occurrence in `.github/workflows/ci.yml` (count 0)**. Closing this is a change to CI wiring, which a
status/evidence landing deliberately does not make. Unlike `P6-D49`, the usual mitigating sentence
**is** available here: M8's 72 tests are inside `pytest eval`, and that job completed on Python 3.11.

### `P6-D55` — the run's gate and topology snapshots are stale and read as blockers · `minor` · evidentiary

`accepted/protocol-resolution.json` reads `gates.independent_review: NOT_RUN` — *"no independent
review recorded for this state"* — which the run's **own** review ledger contradicts (one review,
verdict `SUPPORTED`, `independent: true`). Its `topology.state` reads `ILLEGAL` because it evaluates
HEAD against a recorded status commit `d59b7400a472` under the **retired** two-commit
content+metadata convention, which was removed in the 2026-08 simplification and **must not be
revived**. The same snapshot's own `status` is `CONSISTENT` with `violations: []`, `deadlocks: []`,
`environment_blockers: []` and `next_safe_action: "proceed: topology and authority are consistent"`.
This is the identical condition recorded as `P6-D38` (M5), `P6-D44` (M6) and `P6-D50` (M7).

### `P6-D56` — reviewer-harness status vocabulary · `minor` · evidentiary

Four correct outcomes are labelled `execution_failed` / `COMMAND_ERRORED` — the three exit-2 negative
controls and `probe … --help`. Same defect as `P6-D39`, `P6-D45` and `P6-D51`. **Materially better
than `P6-D51` in one respect**: all three harness-refused commands were re-issued in approved form
and executed, so no oracle was abandoned. The one weaker instrument — the migration invariants
verified by reading the DDL rather than introspecting a live database — **is repaired at this landing
rather than carried forward** (§2.2), which is the first time that `P6-D51`-class gap has been closed
in the same commit that records it.

### `P6-D57` — the generated half of the scenario coverage is the thinnest since M6's zero · `minor` · coverage disclosure

`scenario-generation/wave-01.json` records **6 proposed, 0 accepted, 6 rejected**; every rejection
reason is the same and is about the **harness, not about M8** — an unapproved command vocabulary (a
`create_canonical_schema` or AST-scan command outside the approved set). `wave-02.json` then proposed
**1** and accepted it, so the run's generated contribution is **one scenario, 12 assertions**, against
M7's four (`P6-D52`) and M5's fourteen. ### **WHAT IT COSTS, STATED EXACTLY**: the permanent scenario
carries **396 of the 408 assertions**, and the five themes wave-01 lost — the state-vocabulary
introspection, the ship-dark AST sweep, and their siblings — **all have a named permanent-probe case
or a named test that passed**, several of them re-measured independently at this landing (§2.2,
§5.3). What was lost is the generated scenarios' **composed dimension pressure** (varied
`--concurrency`, `--repeat`, `--tenants`, `--seed`), not the behaviours themselves. This is disclosed
rather than glossed.

### `P6-D58` — a build commit wrote "LANDED" prose before the landing existed · `minor` · evidentiary

`96b7cb3` narrowed M7's two forbidden-table sets (§6) and justified both edits in-line with the
sentence *"M8 (the Expectation) LANDED as the build checkpoint after M7"*. **That sentence was false
when it was written** — M8 was an unreviewed content candidate, `c950a83` corrected the surrounding
status surfaces to say exactly that, and only this commit makes it true. The **code** those comments
sit beside was correct in both worlds (the tables genuinely exist, so asserting their absence would
have been wrong either way); it is the **tense** that ran ahead of the evidence. Recorded because
this repository's characteristic failure is a claim that outlives its warrant, not actioned because
the sentence is now true and rewriting landed comments to re-stage a corrected history would be a
worse defect than the one it fixes.

### Standing items, carried and unchanged — not new debt

`P6-D40` (no status guard enforces that a P6 checkpoint scores no acceptance criterion, and none
enforces that its cited review report exists on disk; the partition guard matches table names as
whole-file substrings) is **carried forward unchanged**. It was **not** re-verified against the
committed guards at this landing; what was run instead is an in-memory landing-posture battery over
this commit's own status surfaces, which is a different instrument and is not a claim that `P6-D40`
moved. `P6-D24`–`P6-D27`, `P6-D47`–`P6-D52`, the G2 residuals, `V2`/`V3`/`V4` and every earlier P6
residual are carried unchanged. The three M7 authority questions `M7-AQ-1`, `M7-AQ-2` and `M7-AQ-3`
remain **REPORTED and unresolved**; M8 answers none of them and touches neither protected machine.

---

## 8. ### CI — the honest record. The workflow did NOT conclude `SUCCESS`

**GitHub Actions run `33245212866` on `f2ff1ca` concluded `cancelled`.** Job by job:

| Job | Conclusion |
|---|---|
| `Safety invariants (fast)` | **SUCCESS** |
| `P6/M3 effect-grant probe + mutation` | **SUCCESS** |
| `Full test suite (py3.11)` | **SUCCESS** — **3041 passed, 1 skipped** |
| `Full test suite (py3.12)` | **CANCELLED** at the 60-minute runtime ceiling having reached ~56%, **with no test-failure marker observed before cancellation** |
| `Risk radar` | **SKIPPED** (pull-request-only) |

### **THE WORKFLOW IS NOT GREEN AND THIS DOCUMENT DOES NOT SAY IT IS.** One job was cancelled, so the
workflow's overall conclusion is `cancelled`, and **`cancelled` is not `success`**. Anyone citing
this landing as "CI green" is citing it wrongly.

### **AND — STATED WITH EQUAL PRECISION — THIS IS THE STRONGEST CI POSITION OF ANY P6 LANDING SINCE
`P6-CP-6`, AND M8'S OWN TESTS DID EXECUTE.** At `P6-CP-7` not one full suite completed and the
safety job did not complete either; the only success was M3's job, which executes no M7 code. Here
**three jobs concluded `SUCCESS`, including a full suite that ran to completion.** Measured rather
than assumed: `pytest eval -q -p no:cacheprovider --collect-only` on this exact tree collects
**3042** tests, which **matches py3.11's `3041 passed, 1 skipped` exactly**, and
`eval/tests/test_phase6_expectation.py` occupies **positions 2107–2178** of that collection. So the
py3.11 job executed **all 72 of M8's tests and they passed** — the first P6 machine since M6 with a
completed CI execution of its own suite.

### **PYTHON 3.12 HAS NO RESULT FOR THIS COMMIT — NEITHER FAILING NOR PASSING.** M8's tests sit at
**69.3%–71.6%** of the run and that job was cancelled at **~56%**, so it **stopped before them**. A
different interpreter is a different execution, so the honest statement is not "no verdict" but **"no
execution": the repository has no Python 3.12 run of M8's 72 tests on this commit.** (Denominator and
caveat both stated: the collection was taken locally on this tree with the repository's own command,
while CI's percentage is pytest's own progress display over its own collection under its own
interpreter, so this is strong evidence of ordering rather than a byte-exact reproduction of CI's
run — though the 3042/3042 agreement with py3.11 is unusually direct corroboration that the two
collections are the same.)

### **THE PRIOR REG-1 FAILURE IS FIXED, AND THAT IS ESTABLISHED BY A COMPLETED JOB RATHER THAN BY
INFERENCE.** Run `33240868415` failed `test_phase0_tenant_posture.py::test_no_new_tenantless_table_appeared`
on Python 3.12. That file **is** among the 26 the `Safety invariants (fast)` job names, and that job
concluded **SUCCESS** on this run — so the guard that was red has been executed to completion and is
green. It sits at positions **1511–1520** (49.7%–50.0%) of the full collection, so the cancelled
py3.12 suite also passed through it without failing before reaching ~56%; that second observation is
corroboration, not the basis.

### **THE JOB CONCLUSIONS ABOVE WERE SUPPLIED BY THE FOUNDER AND WERE NOT RE-READ BY THIS SESSION.**
`gh run view` has failed from this sandbox with a TLS interception error at every P6 landing since
`P6-CP-5`. A later session with network access should read run `33245212866` itself rather than trust
this transcription.

The founder has chosen to land M8 on the evidence that exists — a reviewer that reproduced the probe,
the mutation battery, the targeted suite and three negative controls against this exact tree; two
passing Product Driver scenarios; a completed py3.11 suite that ran M8's tests; and a completed
safety job that ran the previously-red REG-1 guard — treating the py3.12 cancellation as a
**non-product CI runtime limitation** rather than as evidence of an M8 defect. **That is recorded as
a founder DECISION, not as a verification** (`P6-D53`).

---

## 9. What did NOT change

- **No P6 acceptance criterion is scored.** `criteria_scored` is `[]` on all eight checkpoints.
- **P6 is not COMPLETE.** Registry `status: READY`, `execution_state: IN_PROGRESS`. **P7 stays
  `BLOCKED` / `NOT_STARTED`.**
- **M8 ships dark.** Zero production importers, no channel join, no coverage-health probe or poller,
  no live tracking or SLA surface, no gate mint, and the production `GateRegistry` stays EMPTY until
  U8.1/P8.
- **The kernel is untouched.** `checkpoint.py`, `external_effect.py`, `identity_binding_claim.py`,
  `conflict.py` and `observation.py` are byte-identical across the entire M8 commit range
  `96b7cb3~1..f2ff1ca`.
- **`R-07` remains CONTAINED, and CONTAINED is not ENABLED.** No production write is enabled and no
  autonomy was granted.
- **M1–M7 are not rebuilt or polished.** Their residuals remain debt rows.
- **No retired process was revived**: no finalizer, no adjudication chain, no committed suite
  receipt, no clean-clone ceremony, no preserve ref, no two-commit topology.
- **The next build checkpoint is M9 — the Exception.** Nothing here starts it.
