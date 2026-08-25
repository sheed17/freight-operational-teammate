> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This is evidence of a past moment, not status.** It is an INDEPENDENT REVIEW: it set no
> acceptance criterion, marked no phase complete, closed no risk, enabled nothing and authorized no
> external effect. It reviewed the `P6-CP-5` candidate (machine **M5 — the Observation**) at content
> commit `221c4b19ae15b4543586b0f3f82a89715a8a30f9` (tree
> `a2714a002f02b0a9df669394808e3be5d8c2be2b`, branch `p5/u5-1-g2-spec-correction`, working tree
> clean) and returned **SUPPORTED, confidence 0.90**.
>
> ### **IT DID NOT REVIEW THE COMMIT THAT CARRIES IT.** The landing commit that brought this file
> in-tree did not exist when the review was performed. Nothing here may be cited as an independent
> review of that commit.
>
> ### **P6-CP-5 IS A CHECKPOINT, NOT A PHASE ACCEPTANCE.** P6 is **NOT COMPLETE**, no P6 acceptance
> criterion is scored, and P7 is not unlocked. M5 continues to **ship dark**.
>
> ### **NO ADJUDICATION FOLLOWED THIS REVIEW, AND NONE IS OWED.** M5 is tier-1 under
> [`CLAUDE.md`](../../CLAUDE.md) §7 — it lands a migration, it is load-bearing for tenant isolation,
> and it is where untrusted counterparty content enters the system — which requires builder + **one
> focused independent review by someone who did not write it**, mutation proof that the guard can
> fail, and CI. The adjudication chains and finalizer rituals cited by the `P6-CP-1` and `P6-CP-2`
> records were retired in the 2026-08 engineering-process simplification and must not be revived on
> the strength of those older artifacts.
>
> ### **CI DID NOT CONCLUDE `SUCCESS` ON THIS COMMIT, AND THIS RECORD DOES NOT PRETEND OTHERWISE.**
> See §7. Read that section before citing this document as evidence of a green repository.

# P6-CP-5 — FOCUSED INDEPENDENT REVIEW — candidate `221c4b1`

**Verdict: `SUPPORTED` · confidence `0.90` · findings `0` · adjudications `0` · criteria `12/12 PASS`**

| | |
|---|---|
| **Reviewed tree** | commit `221c4b19ae15b4543586b0f3f82a89715a8a30f9`, tree `a2714a002f02b0a9df669394808e3be5d8c2be2b`, branch `p5/u5-1-g2-spec-correction`. The review record's `reviewed_fingerprint` reads **`tracked_dirty: 0`, `untracked: 0`** |
| **Reviewer lineage** | A session that did not build M5. The review record states `inherited_builder_context: false` and the run's review ledger states `independent: true`; reviewer session `0f3c581e-1de9-46c1-93a7-aba52aac75ab`, builder session `d02bbb5a-b33f-486f-87cf-3db585386402` |
| **Performed** | `2026-08-25T06:49:42+00:00` |
| **Source artifact** | Product Driver run `20260825-045311`, `iteration-03/independent-review.json` (separate repository, `neyma-product-driver`), sha256 `2dfbabc4fbf63451bc785a05b6122969d0609def5f878705d548b2f85936d1ff` — byte-identical to `accepted/independent-review.json` in the same run. Its prose is quoted verbatim below; nothing is upgraded, softened or summarised into a stronger claim |
| **Adjudications recorded** | **none** (`adjudications: []`) |
| **Findings** | **none** (`findings: []`). §6 records the nonblocking items this landing identified from the run's own evidence — they are **not** reviewer findings and are not presented as such |
| **Scope declared by the run** | `P6/M5`, `level: TASK`, parent phase `P6` (`READY` / `IN_PROGRESS`), `claims_phase_completion: false` |
| **Reviewer executed the product** | **Yes.** `evidence_reproduced: true` and `claimed_evidence_reproduced: true` — see §4 |
| **Reviewer blocked on anything** | **No.** `blocked_on.kind: NONE` — *"All bearing verification was runnable within the read-only boundary and reproduced green."* |

---

## 1. The verdict, verbatim

> "At HEAD 221c4b19ae15 / tree a2714a002f02 (clean working tree), the P6/M5 correction is confined
> to scripts/probe_phase6_observation.py (52 insertions / 8 deletions) and is a probe-observability
> STRENGTHENING: it adds a genuine before/after full-row read-back and two new OK conjuncts (as_of
> advanced; every fact/status column byte-identical) so the as_of-only invariant is surfaced exactly
> at the duplicate path. No machine, schema, migration, or event file changed; git log -L confirms
> the confirmation-updates-as-of-only case last changed at 58852a6, not HEAD. I reproduced the
> product evidence myself: the full probe exits 0 with 'behaviours as specified, 0 wrong'; the
> duplicate case (including --inject duplicate-ingest --repeat 5) prints 'A CONFIRMATION UPDATES
> as_of AND NOTHING ELSE'; both negative controls exit 2; pytest 51 passed; mutation battery 11/11
> caught; ship-dark posture holds (zero production importers, only the probe reaches the module).
> The change weakens no guard and stays within P6/M5 scope."

## 2. What M5 is, in one line

**One `observations` row, seven states, eight transitions, and a natural key the database enforces
— an immutable record that a source SAID something, at a time, which is not the same as it being
true.** `raw_value` and `content_digest` are immutable by trigger, so a wrong reading is never
edited: it is *superseded* by a new observation, and supersession requires a deterministic rule or a
human — never a re-run of the inferrer. The natural key
`(tenant, source_system, external_id, content_digest)` is a `UNIQUE` index, so **the same email
twice is one row, one `ObservationConfirmed`, and zero downstream work** — no duplicate Work Item,
no duplicate approval card, no duplicate invoice. A scanned POD that will not parse is
`UNPARSEABLE` owned by a named human through a foreign key into `tenant_humans`, never a silent
drop; a reference matching two loads is `UNBOUND`, never a guess. Provenance is runtime-assigned:
inbound content cannot set its own `provenance_class`, and a `MODEL_INFERRED` observation is
`CHECK`-forbidden — structurally impossible, because an observation is what a source said, not what
a model believes.

The transition table is the specification's: `OB-1`, `OB-1c`, `OB-2`, `OB-2f`, `OB-3`, `OB-3u`,
`OB-4`, `OB-5` — **eight rows, an exact set match with §14 of**
[`05-observation.machine.md`](../specifications/state-machines/05-observation.machine.md). The
seven canonical F5 events are `ObservationReceived`, `ObservationConfirmed`, `ObservationParsed`,
`ObservationUnparseable`, `ObservationBound`, `ObservationUnbound`, `ObservationSuperseded` —
**and no eighth**. F5 is **order-tolerant** by
[`events/registry.md`](../specifications/events/registry.md) §8, so unlike M3 and M4 this machine
declares **no** `previous_aggregate_version`: the natural key is what makes ingestion commutative,
and a reference to a not-yet-received observation is parked (M-26) and drained when it arrives.

**There is no expiry, no sweep and no deletion.** A stale observation is still a fact.

## 3. What the reviewer established ITSELF, and how

The reviewer ran the product in its own session. Its harness records **17** command outcomes, and
they are reported here by the harness's own status vocabulary rather than collapsed into a single
number:

| Harness status | Count | What it means here |
|---|---|---|
| **`RUNTIME_REPRODUCED`** | **7** | The reviewer executed the product and the output satisfied a named, deterministic expectation |
| **`STRUCTURAL_VERIFIED`** | **4** | The reviewer read structure and it satisfied a named, deterministic expectation |
| `REFUSED` | 2 | The reviewer's command boundary rejected shell composition outside quotes (`&`, `|`). **A limit on the review, never a defect in the product** — and in both cases the reviewer re-issued the same check as a single-command form that ran and satisfied its expectation |
| `COMMAND_ERRORED` | 2 | **Both are the negative controls, exiting 2 exactly as designed.** See §3.1 — this is a harness classification artifact, not a failure |
| `EXPECTATION_FAILED` | 1 | `git status --porcelain=v1` produced **no output**, and the harness cannot assert a substring against an empty capture. See §3.1 |
| `REVIEWER_INSPECTED` | 1 | `git show HEAD -- scripts/probe_phase6_observation.py` — read, but **no expectation was named, so it establishes nothing by machine** and is not counted as evidence here |

**Reproduced by the reviewer, by execution** (the seven `RUNTIME_REPRODUCED`):

| # | What ran | Expectation it satisfied |
|---|---|---|
| 1 | `scripts/probe_phase6_observation.py` (full) | exit 0, *"behaviours as specified, 0 wrong"* — *drive the Observation machine through a brokerage narrative, and attack it* |
| 2 | `--case duplicate-is-one-row-one-confirmation-zero-work` | prints `THE SAME EMAIL TWICE IS ONE OBSERVATION` / `ONE ROW, ONE CONFIRMATION, ZERO WORK` / `A CONFIRMATION UPDATES as_of AND NOTHING ELSE` |
| 3 | the same case with `--inject duplicate-ingest --repeat 5` | the same three lines under five identical re-ingests |
| 4 | `pytest -q -p no:cacheprovider eval/tests/test_phase6_observation.py` | **51 passed** |
| 5 | `scripts/mutate_phase6_observation.py` | **11/11 mutants caught** |
| 6 | an AST sweep over `src/freight_recon` | `production importers of observation: []` |
| 7 | an AST sweep over `scripts` | `scripts reaching observation: ['probe_phase6_observation.py']` |

**Verified structurally by the reviewer** (the four `STRUCTURAL_VERIFIED`): `git rev-parse HEAD` →
`221c4b19ae15…`; `git rev-parse HEAD^{tree}` → `a2714a002f02…`; `git show --stat HEAD` → exactly
`scripts/probe_phase6_observation.py`, `1 file changed`, with `phase6_observations.py` **absent**
from the stat; and
`git log -1 --format=%H -L :case_confirmation_updates_as_of_only:scripts/probe_phase6_observation.py`
→ `58852a6…`, **not** `221c4b1` — proving the pre-existing as-of-only case was untouched by the
reviewed commit rather than rewritten to make a new assertion pass.

### 3.1 Two harness statuses that read like failures and are not — recorded, not tidied

Anyone reading the raw `independent-review.json` will see one `EXPECTATION_FAILED` and two
`COMMAND_ERRORED` rows. **None of the three is a product failure, and none is being quietly dropped here.**

- **`git status --porcelain=v1` → `EXPECTATION_FAILED`.** The declared expectation was
  `expect_absent: ['M ', '??']` against the command's output. The command exited 0 and produced
  **no output at all** — which is precisely what a clean tree produces — and the harness's own
  detail reads *"no output was captured, so no substring assertion could hold"*. The reviewer's
  `reviewed_fingerprint` independently records `tracked_dirty: 0` and `untracked: 0`. **A guard that
  cannot pass over an empty capture is the vacuous-negative failure mode**
  [`CLAUDE.md`](../../CLAUDE.md) §6 names; it is recorded here rather than presented as a clean-tree
  proof, and the clean-tree claim rests on the fingerprint instead.
- **The two negative controls → `COMMAND_ERRORED`.** Both
  `--inject not-a-real-fault` and `--inject expire-observation` exited **2** with a readable
  `unknown fault` message naming the closed vocabulary — *which is the intended behaviour and the
  whole point of the control*. The harness classifies any non-zero exit as `COMMAND_ERRORED`, and
  for the second the scenario-derived expectation was `expect_exit_code: 0`, so it could not have
  been satisfied by correct behaviour. **The product did the right thing; the harness's expectation
  vocabulary could not say so.** Tracked as `P6-D39`.

## 4. What Product Driver independently exercised

M5 was **operated as a running unit, not merely tested**. This is the run's structured evidence, not
its prose.

### 4.1 Scenario evidence — 14/14, 333 assertions, 0 failed

`suite-result.json` records a **full** run (`full_run: true`, *"full required regression set before
acceptance"*), 14 required scenarios, **every one `PASSED`**, `assembly_problems: []`, and every
scenario's evidence independently verified (`evidence_verified: true`, `evidence_problem: ''`):

| Scenario | Origin | Risk category | Outcome | Assertions |
|---|---|---|---|---|
| `p6_m5_observation` | permanent | *(the permanent regression)* | **PASSED** | 208 |
| `m5-w2-01-no-eighth-f5-event` | generated | `safety_invariant` | **PASSED** | 6 |
| `m5-w2-02-no-m9-m6-contract` | generated | `safety_invariant` | **PASSED** | 6 |
| `m5-w2-03-no-invented-expiry-transition` | generated | `unexpected_state_transition` | **PASSED** | 14 |
| `m5-w2-04-ship-dark-no-importer` | generated | `authorization` | **PASSED** | 7 |
| `m5-w2-05-ship-dark-no-channel-join` | generated | `authorization` | **PASSED** | 4 |
| `m5-w2-06-negative-control-faults-refused` | generated | `malformed_input` | **PASSED** | 8 |
| `m5-w2-07-duplicate-idempotency-reestablish` | generated | `idempotency` | **PASSED** | 12 |
| `m5-w3-01-duplicate-as-of-surfaced-refix` | generated | `repeated_request` | **PASSED** | 15 |
| `m5-w3-02-as-of-only-dedicated-case` | generated | `idempotency` | **PASSED** | 12 |
| `m5-w3-03-confirmation-flood-advanced-row` | generated | `repeated_request` | **PASSED** | 12 |
| `S1` | generated | `concurrency` | **PASSED** | 11 |
| `m5-w3-04-as-of-surfaced-different-seed` | generated | `idempotency` | **PASSED** | 13 |
| `m5-w3-06-mutation-battery-guards-can-fail` | generated | `safety_invariant` | **PASSED** | 5 |
| | | | **14 PASSED, 0 failed** | **333, 0 failed** |

Two of these scenarios exist because **earlier iterations of this run failed**. `m5-w2-07` failed at
iteration 2 and `m5-w3-01` was generated to re-establish the same property from a different angle:
the duplicate re-ingest path did not *surface* the as_of-only invariant where the duplicate is
applied, only in a separate case. That is an **observability** defect in the probe, not a behavioural
defect in the machine, and the run's evaluator says so explicitly — *"the earlier generated failures
were a mis-stated/over-specific expectation and an observability gap, both now closed — no meaningful
behavioural defect was exposed"*. The correction commit `221c4b1` closed it by grounding the printed
sentence in a **real before/after full-row read-back**, so the line is now evidence rather than a
bare string. **There are no unresolved material Product Driver scenario failures.**

### 4.2 Mutation evidence — 11/11, each guard proven able to fail

`scripts/mutate_phase6_observation.py`, executed by Product Driver and re-executed by the reviewer:

| # | The guard, and the defect its removal reintroduces |
|---|---|
| 1 | the natural-key index loses `UNIQUE` — the same email twice inserts as two rows, a duplicate Work Item and eventually a duplicate invoice |
| 2 | the `raw_value` immutability trigger is defanged — a wrong reading is EDITED in place instead of superseded |
| 3 | the `content_digest` immutability trigger is defanged — the fact can be re-keyed, so the same email twice stops being one fact |
| 4 | the duplicate short-circuit is disabled — an identical re-ingest is no longer recognized as a confirmation |
| 5 | the `MODEL_INFERRED` refusal is removed from BOTH the machine and the database — a guess gets filed as an observed fact |
| 6 | the guess/ambiguity guard is removed — a `MODEL_INFERRED` binding offered as "confirmed" auto-binds instead of failing closed to `UNBOUND` |
| 7 | the supersession guard is removed — a re-run of the inferrer supersedes an observation |
| 8 | the provenance-from-content refusal is removed — inbound content sets its own provenance |
| 9 | the tenant predicate is dropped from the observation read — one tenant reads another's observation |
| 10 | the transition commits the state without emitting its event — a processing status with no event (GR-2 co-commit broken) |
| 11 | the OCC predicate is dropped from the processing-status transition — a lost update silently wins instead of raising |
| | **11/11 mutants caught** |

The battery's own output carries the honest note *"written by the session that implemented the unit —
evidence, not adjudication."* **That is why the independent reviewer re-ran it**, and did:
`11/11 caught`, `RUNTIME_REPRODUCED`.

### 4.3 The M5 acceptance suite — 51 tests

`eval/tests/test_phase6_observation.py`: **51 passed** — 49 test functions, 51 collected cases — run
by Product Driver in the permanent scenario and re-run by the independent reviewer in its own
session. This file **is** inside `pytest eval` and therefore inside CI's `suite` job — see §7 for
what CI actually concluded.

### 4.4 Negative controls, and the closed fault vocabulary

The probe's fault vocabulary is **closed**: 27 named faults, and anything else is a refusal with
exit 2, never a silent fallback to `none`. Both controls were exercised by Product Driver and
re-run by the reviewer:

- `--inject not-a-real-fault` → **exit 2**, `unknown fault 'not-a-real-fault'`.
- `--inject expire-observation` → **exit 2**, and the refusal states why in the product's own words:
  *"there is no 'expire-observation': observation expiry is the mechanism entity §26 and machine
  §12/§23/§37 say does NOT exist, and accepting it would manufacture evidence for a transition
  nobody authorized."*

### 4.5 Regressions actually available, and what they measured

Executed on the reviewed tree inside the permanent scenario, **with M5's table present in the
schema** — so these are regressions *against M5's migration*, not merely a prior green:

| Surface | Result |
|---|---|
| **P3** — witness, claim CAS, step order, checkpoint matrix, brake, fingerprint | **216 passed** |
| **P4** — import gate, adapter boundary, governed write route, no-mock-effect | **99 passed** |
| **P5** — event transport, replay/audit, durable timers, event contracts, canonical mint | **561 passed** |
| **M1 + M2 + M3 + M4** — work item, pipeline instance, external effect, approval | **432 passed** |
| **M3's own deterministic probe** | `behaviours as specified, 0 wrong` |
| **M4's own deterministic probe** | `behaviours as specified, 0 wrong` |

The M3 and M4 probes are the important ones: they are the two landed machines whose behaviour a new
migration could most plausibly disturb, and both still report **0 wrong** with `observations` in the
schema.

### 4.6 Ship-dark posture — measured, not asserted

Three AST sweeps, two of them re-executed by the reviewer:

- `production importers of observation: []` — **zero** modules under `src/freight_recon` import the
  machine (reviewer-reproduced).
- `scripts reaching observation: ['probe_phase6_observation.py']` — the **only** thing outside the
  package that reaches M5 is its own verification probe (reviewer-reproduced).
- No module joins `observation` to any outbound channel; `checkpoint.py` remains the **sole** gate
  minter; **M3 remains the single effect authority**; no `M6` or `M9` table is created.

### 4.7 No production enablement, and no smuggled successor

M5 **enables nothing**. No production importer, no live external effect, no registered policy gate,
no outbound channel, and no autonomy. The M6 binding seam is **inert** — `bind`/`resolve_unbound`
*apply* a typed binding decision, they never *compute* one; they rank no candidates, build no
`identity_binding_claims` table and implement no `IB-*`. The exception seam mints **no M9 event** and
builds no `exceptions` table; the durable, human-owned record is the row itself sitting in
`UNPARSEABLE`/`UNBOUND` with an FK-backed accountable human. The provenance-laundering **refusal** is
present and mandatory; the F14 audit-event emission half is deferred to Phase 7, where P5's `IR-R9`
already places it. **No M6 or M9 implementation was smuggled into M5**, and two generated scenarios
(`m5-w2-01`, `m5-w2-02`) assert exactly that.

### 4.8 The run's own audit

| Record | Value |
|---|---|
| `scoped-completion.json` | `task_result: VERIFIED`, `task_outstanding: []`, `parent_phase: P6` `READY`/`IN_PROGRESS`, **`parent_phase_accepted: false`** |
| `completion-audit.json` | `decision: VERIFIED`, `implementation_present: true`, `missing_evidence: []`, `contradictions: []`, confidence `0.85` |
| observed state | head `221c4b19ae15…`, tree `a2714a002f02…`, `dirty_file_count: 0`, `untracked_count: 0`, `active_unit_id: P6`, `active_unit_status: READY` |
| receipts | `SUITE-RESULT.json`, `GATE-RESULT.json`, `BUILD-STATUS.yaml` all recorded **absent** — correct, and **required**: [`CLAUDE.md`](../../CLAUDE.md) §0 forbids committed receipts and none may be manufactured |
| `does_not_imply` (the run's own words) | P6 is COMPLETE · any P6 acceptance criterion is scored · the units P6 still owes are built · the next phase is unblocked · phase acceptance has occurred · anything is enabled in production or on live traffic |
| evaluator decision | `ACCEPT`, confidence `0.86`, `problems: []`, `additional_verification_needed: false` |

## 5. Canonical / specification inconsistencies Product Driver surfaced — recorded EXACTLY as found

**The corpus disagrees with itself on three points about M5.** The build reported all three and
implemented **only what every reading agrees on**; the reviewer confirmed the reading taken on the
one it examined. **None of the three is resolved here, and this landing resolves no authority
conflict.** They are stated in `src/freight_recon/observation.py`'s own module docstring so a reader
of the code meets them where the decision would be made. Tracked collectively as `P6-D35`.

| | The conflict | What EVERY reading agrees on | What the code does |
|---|---|---|---|
| **`M5-AQ-1`** | Is `BOUND` terminal? The machine registry §4, entity §12, machine §8 and the target spec §12.5 **all** mark `BOUND (T)` — yet the **same** documents carry `OB-5: {BOUND,PARSED} → SUPERSEDED`, which gives `BOUND` an outgoing edge | supersession requires a deterministic rule or a human, never an inferrer re-run; the superseded row is RETAINED; `raw_value`/`content_digest` never mutate | Implements `OB-5` **exactly as written** and "fixes" the classification in neither direction. The only states with no outgoing edge — absolutely final — are `SUPERSEDED` and `UNPARSEABLE` |
| **`M5-AQ-2`** | Is `UNPARSEABLE` terminal, or non-terminal human-owned? Entity §12, machine §8 and the target spec §12.5 say terminal; machine registry §4 (`UNPARSEABLE (NH)`) and machine §9 say non-terminal human-owned. **Machine §8 and §9 contradict each other inside one file** | `UNPARSEABLE` is never a silent drop, feeds the Exception path, and is HUMAN-OWNED | Builds it human-owned: an FK-backed `owner_id`, no outgoing transition, and nothing sweeps or drops it |
| **`M5-AQ-3`** | What does a duplicate do to a row that has already advanced? `OB-1c`'s From→To reads *(re-ingest) → `CONFIRMED`*, but its Writes column reads *`as_of` updated only*, F5 calls the event *"a FRESHNESS update, NOT a new business fact"*, and machine §16 says `CONFIRMED` short-circuits before any parse/bind re-work | one row, one `ObservationConfirmed`, zero downstream work, `raw_value`/`content_digest` unchanged, the immutable CONTENT untouched | Implements the **`as_of`-only** reading: a re-ingest advances `as_of` (never backwards) and emits `ObservationConfirmed`, and **never rewrites `state`** — because the required-observable sentence *"A CONFIRMATION UPDATES as_of AND NOTHING ELSE"* is decisive, and discarding a processing status the machine already established (a `BOUND` row reverting to `CONFIRMED`) is the loss the build task's §3.1 warns against (not this report's §3.1). `CONFIRMED` stays in the seven-state vocabulary; the confirmation is carried by the EVENT, not by a state rewrite |

**`M5-AQ-3` is the one the reviewer examined directly**, and it is the reading the reviewed commit
exists to make observable. The run also left two **scenario requests** against it, which are
requests for future coverage and not findings: exercise a duplicate arriving against a row already
advanced to `PARSED`/`BOUND`/`SUPERSEDED` to confirm the `as_of`-only reading under state pressure;
and a seeded high-concurrency natural-key race with mixed tenants and multiple `source_system`s
sharing one `external_id`.

## 6. Minor and nonblocking items — recorded, not actioned

### **THE INDEPENDENT REVIEW RETURNED ZERO FINDINGS AND ZERO ADJUDICATIONS.** Nothing below is a
reviewer finding and nothing below may be cited as one. Each was identified **at this landing** from
the run's own structured evidence, the M5 source, the specification corpus, the CI record and this
landing's own mutation battery against the status guards. Each is **RECORDED, NOT ACTIONED** ([`CLAUDE.md`](../../CLAUDE.md) §13 — the debt row is the complete
deliverable). None can produce a wrong customer outcome, violate an invariant, or make a later phase
unsafe, and the machine ships dark.

### `P6-D35` — the three §3.9 M5 authority questions are REPORTED, not resolved · `minor` · specification seam

`M5-AQ-1`, `M5-AQ-2` and `M5-AQ-3`, in full in §5. The code implements only what every reading
agrees on, **invents no reconciliation**, and says so in its own module docstring. These are
specification questions owed to a founder/architect decision, not M5 defects, and they close when
that decision is made — **not by a session choosing a reading**
([`CLAUDE.md`](../../CLAUDE.md) §5: a plausible guess here becomes a permanent, invisible decision).

### `P6-D36` — this commit has NO GREEN CI CONCLUSION · `minor` · CI

Run `32819208290` on head `221c4b1` concluded **`cancelled`**. Full detail, and the honest bound, in
§7. It closes only by a CI run on this branch that concludes `SUCCESS`.

### `P6-D37` — CI does not execute M5's probe or mutation battery · `minor` · CI coverage

Verified mechanically at this landing: `.github/workflows/ci.yml` contains **no** occurrence of
`phase6_observation`. The `effect-grant` job runs **M3's** probe and battery on every push precisely
because `pytest eval` does not invoke them; there is no equivalent job for M4 (`P6-D33`) and none for
M5. `eval/tests/test_phase6_observation.py` **is** inside `pytest eval` and did run in the suite jobs.
Closing this is a change to CI wiring, which a status/evidence landing deliberately does not make.

### `P6-D38` — the run's gate snapshot reads `independent_review: NOT_RUN` · `minor` · evidentiary

`record.json`'s `protocol_resolution.gates.independent_review` reads `NOT_RUN` with detail *"no
independent review recorded for this state"*. **That snapshot was taken before the review executed**
at `2026-08-25T06:49:42+00:00`. The run's `independent-review-ledger.json` records the review at
iteration 3 with `independent: true`, a reviewer session distinct from the builder's,
`inherited_builder_context: false`, verdict `SUPPORTED`, `invalidations: []` and `superseded_by: ''`.
**The structured ledger and the review record are authoritative; the gate snapshot is stale.**
Recorded so a later session reading only the gate block does not conclude a review is still owed.
(This is the M5 analogue of `P6-D34`. Unlike M4's run, this run's *evaluator prose* does **not**
contradict the record — it says the review is *"part of this run"*.)

### `P6-D39` — the reviewer harness's status vocabulary mis-labels correct behaviour · `minor` · evidentiary

Three of the reviewer's 17 command rows carry failure-shaped statuses for reasons that are not
failures: two `COMMAND_ERRORED` rows are the negative controls exiting **2 exactly as designed**, and
one `EXPECTATION_FAILED` row is `git status --porcelain=v1` on a **clean** tree, where an empty
capture makes any substring assertion vacuous. Full detail in §3.1. Recorded so nobody reading the
raw JSON mistakes a correct refusal for a defect — and, in the other direction, so nobody cites the
`git status` row as a clean-tree proof it cannot be.

### `P6-D40` — no guard enforces two of this landing's own prohibitions · `minor` · guard coverage

**Surfaced by this landing's own mutation battery, over a denominator of five mutants each verified
to apply *and* to misbehave** ([`CLAUDE.md`](../../CLAUDE.md) §6 — a mutation that does not
reintroduce the real defect proves nothing). Run against the status/control guard set
(`test_bootstrap_hermeticity`, `test_false_green_defenses`, `test_p5_canonical_event_mint`,
`test_phase0_identifiers`, `test_phase0_errata_guards`, `test_phase2_guard_registry`):

| Mutant | Result |
|---|---|
| `CURRENT.md` stops naming the `observations` tenant table | **CAUGHT** |
| P7 flipped `BLOCKED` → `READY` | **CAUGHT** |
| P6 flipped `READY` → `COMPLETE` | **CAUGHT** |
| **`P6-CP-5` scores a P6 acceptance criterion** (`criteria_scored: [independent_review]`) | ### **MISSED** |
| **`P6-CP-5` cites an `independent_review_report` that is not on disk** | ### **MISSED** |
| | **3 of 5 caught** |

**Both misses are pre-existing guard gaps, not defects this landing introduced**, and both are about
**P6's** landed checkpoints specifically:

- `test_p5_canonical_event_mint.py` asserts `criteria_scored` empty and evidence-plus-review present
  for **P5's** landed checkpoints. **There is no P6 equivalent.** So `criteria_scored: []` on all five
  P6 checkpoints — the single most repeated prohibition in this record — currently rests on
  discipline, not on a guard.
- The registry's own `meta.status_model.invariants` states *"checkpoint_state INDEPENDENTLY_REVIEWED
  or ACCEPTED_FOR_CONTINUATION => the cited independent review report exists on disk"*. The guard
  that enforced it, `test_roadmap_completeness_control.py::test_a_claimed_independent_checkpoint_review_must_cite_a_report_that_exists`
  — named by the `P6-CP-2` re-adjudication as the reason it overturned a review finding — **no longer
  exists in the tree.** It was removed in the 2026-08 simplification, and nothing replaced it.

A **first** round of this battery reported 3 misses; two of those were the battery's own defects, not
the guards' — one mutant deleted the partition row while the word `observations` still appeared
elsewhere in the whole-file substring check, and one run named the removed
`test_roadmap_completeness_control.py`, so its non-zero exit was a **pytest collection error being
mistaken for a caught mutant**. Both were corrected before any result here was believed. That
correction is recorded because it is the exact failure mode §6 exists to catch.

**Closing this means writing guards, which a status/evidence landing deliberately does not do.**
Recorded, not actioned.

### Standing items, carried and unchanged — not new debt

- **`V4` (registered identity rules)** remains **OPEN VALIDATION** per machine spec §43, with the
  fail-closed default the specification states (exact ID match, else `UNBOUND`/human) and explicitly
  *"not a block"*. It requires design-partner evidence and may never be guessed.
- **The exhaustive `(state × trigger)` illegal sweep** is exercised at **representative** points for
  M5 as it is for M3 (`P6-D30`) and M4. Structurally mitigated: `apply()` derives legality **solely**
  from `legal_transitions()`, which returns empty for any non-enumerated pair, and `GR-1` then refuses
  uniformly. It is a **gate G1 phase-acceptance** item, not an M5 defect.
- **The F14 `ProvenanceStrengtheningAttempted` emission half** stays deferred to Phase 7 where P5's
  `IR-R9` places it. The laundering **refusal** is mandatory and present now.
- **`G2-D15`**, `V2`, `V3`, `P6-D31`–`P6-D34` and the P5/P6 residual sets are unchanged by this
  landing.
- **The build session's own suite caveat, unchanged and environmental:** on the builder's sandbox,
  `test_action_callback.py` and `test_p4_deployed_governed_route.py` failures are
  `Operation not permitted` on `socketserver.server_bind` — the sandbox refusing to bind a socket,
  not M5. Those files ran green in CI's Python 3.12 suite job on this commit.

## 7. ### CI — the honest record. The workflow did NOT conclude `SUCCESS`

**Pushed CI run `32819208290`**, head SHA `221c4b19ae15b4543586b0f3f82a89715a8a30f9`. The branch
`p5/u5-1-g2-spec-correction` on `origin` was confirmed at this landing to point at exactly that
commit.

### **OVERALL WORKFLOW CONCLUSION: `CANCELLED`. NOT `SUCCESS`. NOT GREEN.**

| Job | Conclusion |
|---|---|
| **Safety invariants (fast)** | ### **`success`** |
| **Full test suite (py3.12)** | ### **`success`** |
| **P6/M3 effect-grant probe + mutation** | ### **`success`** |
| **Risk radar** | `skipped` (pull-request-only job) |
| **Full test suite (py3.11)** | ### **`cancelled` — by the workflow/runtime ceiling WHILE STILL EXECUTING, at approximately 60%. No pytest failure was emitted before the cancellation.** |

### **THE PROVENANCE OF THIS TABLE IS DISCLOSED RATHER THAN IMPLIED.** These job conclusions were
**supplied by the founder**, not re-read by the session that wrote this record: `api.github.com` is
not reachable from this session's sandbox (TLS interception; both `gh` and a direct API call were
refused), so the run could not be independently re-read here. **They are re-readable at the run
itself, and a later session with network access should read them there rather than trusting this
transcription.** No receipt is committed for any of it —
[`CLAUDE.md`](../../CLAUDE.md) §0 forbids committed suite receipts and none may be manufactured.

**What is a true bound, and what is NOT one.** `eval/tests/test_phase6_observation.py` — M5's whole
51-test acceptance and hostile battery — is inside `pytest eval`, which is exactly what the
*Full test suite* job runs, **and that job passed on Python 3.12 on this commit**. The
*Safety invariants (fast)* job's 26 files are all under `eval/tests/` and are therefore a strict
subset of `pytest eval`; it passed too. ### **THAT IS NOT A CLAIM THAT PYTHON 3.11 WOULD HAVE
PASSED.** A different interpreter is a different execution, and the 3.11 job was cancelled *while
running*, not after finishing. A passing 3.12 suite is evidence about 3.12, and the honest statement
is that **the repository has no Python 3.11 result for this commit at all** — not a failing one, and
not a passing one. The workflow conclusion is `cancelled` and stays `cancelled` until a fresh run
says otherwise.

**The founder has explicitly chosen to continue**, treating the cancellation as a **non-product CI
runtime limitation** rather than as evidence of an M5 defect, on the grounds that the safety
invariants passed, the Python 3.12 full suite passed, Product Driver's behavioural verification
passed, the mutation proof passed, and the independent review supported M5. ### **THAT IS A FOUNDER
DECISION, AND IT IS RECORDED AS A DECISION — NOT AS A VERIFICATION, AND NOT AS A GREEN CI RESULT.**
It is tracked as `P6-D36`.

## 8. What this review and this landing are not

- **Not a phase acceptance.** No P6 acceptance criterion is scored, and none may be from any lineage
  that built M5. P6 remains `READY` / `IN_PROGRESS`, `criteria_scored` is `[]` on all five
  checkpoints, and P7 stays `BLOCKED`.
- **Not an adjudication**, and none is owed. A single independent review is a review, not a chain.
- **Not CI evidence.** See §7. The workflow concluded `cancelled`.
- **Not an enablement.** M5 ships dark: zero production importers, only the probe reaches it, nothing
  joins it to an outbound channel, no external effect is enabled on live traffic, the deployed
  governed route still answers `ROUTE_NOT_CONFIGURED`, and the production `GateRegistry` stays EMPTY.
- **Not a resolution of the three §3.9 authority questions.** `P6-D35` reports them; it does not
  settle them, and no session may settle them by choosing a reading.
- **Not the start of M6.** The M6 binding seam is inert and stays inert.
- **Not a finalizer, a suite receipt, a preserve ref, a clean-clone ceremony or a special Git
  topology.** None is owed for this landing and **a session must not run one.**
- **Not a review of the commit that carries it** — see the banner.
