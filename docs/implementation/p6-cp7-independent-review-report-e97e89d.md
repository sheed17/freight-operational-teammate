> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This is evidence of a past moment, not status.** It is an INDEPENDENT REVIEW: it set no
> acceptance criterion, marked no phase complete, closed no risk, enabled nothing and authorized no
> external effect. It reviewed the `P6-CP-7` candidate (machine **M7 — the Conflict**) at commit
> `e97e89d12b31b77d0b964c456df44cc069256cae` (tree `a73dd12a1e4e31716f9d7bac3d72c98acb323b8e`,
> branch `p5/u5-1-g2-spec-correction`, working tree clean) and returned **SUPPORTED, confidence
> 0.90**.
>
> ### **IT DID NOT REVIEW THE COMMIT THAT CARRIES IT.** The landing commit that brought this file
> in-tree did not exist when the review was performed. Nothing here may be cited as an independent
> review of that commit.
>
> ### **P6-CP-7 IS A CHECKPOINT, NOT A PHASE ACCEPTANCE.** P6 is **NOT COMPLETE**, no P6 acceptance
> criterion is scored, and P7 is not unlocked. M7 continues to **ship dark**.
>
> ### **NO ADJUDICATION FOLLOWED THIS REVIEW, AND NONE IS OWED.** M7 is tier-1 under
> [`CLAUDE.md`](../../CLAUDE.md) §7 — it lands a migration, it is load-bearing for tenant isolation,
> and it is the mechanism that BLOCKS consequential action on a disputed field — which requires
> builder + **one focused independent review by someone who did not write it**, mutation proof that
> the guard can fail, and CI. The adjudication chains and finalizer rituals cited by the `P6-CP-1`
> and `P6-CP-2` records were retired in the 2026-08 engineering-process simplification and must not
> be revived on the strength of those older artifacts.
>
> ### **CI DID NOT CONCLUDE `SUCCESS` ON THIS COMMIT, AND THIS RECORD DOES NOT PRETEND OTHERWISE.**
> This landing has **strictly less CI evidence than any previous P6 landing**: not one full suite
> completed, and the M7 tests were never reached. See §8. Read that section before citing this
> document as evidence of a green repository.

# P6-CP-7 — FOCUSED INDEPENDENT REVIEW — candidate `e97e89d`

**Verdict: `SUPPORTED` · confidence `0.90` · findings `0` · adjudications `0` · criteria `9/9 PASS`**

| | |
|---|---|
| **Reviewed tree** | commit `e97e89d12b31b77d0b964c456df44cc069256cae`, tree `a73dd12a1e4e31716f9d7bac3d72c98acb323b8e`, branch `p5/u5-1-g2-spec-correction`. The review record's `reviewed_fingerprint` reads **`tracked_dirty: 0`, `untracked: 0`**, identity `e97e89d12b31/a73dd12a1e4e/-` |
| **Reviewer lineage** | A session that did not build M7. The review record states `inherited_builder_context: false` and the run's review ledger states `independent: true`, `invalidations: []`, `superseded_by: ""`; reviewer session `9e41328a-fcbd-4f4a-af29-23226f74a31d`, builder session `b6b2a9fa-17c3-4553-8ae4-a1ce469ef893` |
| **Performed** | `2026-08-28T03:42:58+00:00` |
| **Source artifact** | Product Driver run `20260828-031404`, `accepted/independent-review.json` (separate repository, `neyma-product-driver`) — byte-identical by `sha256` to `iteration-01/independent-review.json` in the same run, the run's only iteration. Its prose is quoted verbatim below; nothing is upgraded, softened or summarised into a stronger claim |
| **Adjudications recorded** | **none** (`adjudications: []`) |
| **Findings** | **none** (`findings: []`). §7 records the nonblocking items this landing identified from the run's own evidence — they are **not** reviewer findings and are not presented as such |
| **Scope declared by the run** | `P6/M7`, `level: TASK`, parent phase `P6` (`READY` / `IN_PROGRESS`), `claims_phase_completion: false`, `phase_completion_requested: false` |
| **Review requirement** | `required: true`, triggers `REPOSITORY_AUTHORITY` and `COMPLETION_AUDIT`. **SATISFIED** by this review |
| **Reviewer executed the product** | **Yes.** `evidence_reproduced: true` and `claimed_evidence_reproduced: true` — see §4 |
| **Reviewer blocked on anything** | **No.** `blocked_on.kind: NONE` — *"All verification needed for the P6/M7 scope was runnable within the read-only + declared-command boundary and was executed in this session."* |

---

## 1. The verdict, verbatim

> "P6/M7 (the Conflict) at HEAD e97e89d / tree a73dd12a (clean working tree, matching the declared
> review target) is supported by evidence I reproduced this session. I re-ran the product's own
> verification surfaces rather than trusting the harness capture: the deterministic probe (exit 0,
> 'behaviours as specified, 0 wrong', all 70 case lines), the mutation battery (16/16 mutants caught
> — every named safety guard demonstrably fails when inverted), the targeted pytest suite (49
> passed), and the three negative controls (invented fault, expire-conflict, cancel-conflict each
> exit 2 with correct fail-closed refusal prose, keeping M7-AQ-3 held open). Structural
> re-verification confirmed the ship-dark posture (0 production importers; only the probe reaches
> the machine; no channel join), F7 registry conformance (5 registered contracts, no synonyms,
> ConflictResolved requires exactly one of {rule_id, decision_ref}, no unregistered names in the
> machine), no sixth state and no expiry/cancellation surfaces or columns, that only checkpoint.py
> mints a gate decision (M7 is not a second gate), and that the M7 commit range touched none of the
> protected machines (checkpoint.py, external_effect.py, identity_binding_claim.py). The migration
> DDL independently confirms five states inline-CHECKed, owner_id NOT NULL + FK (ownerless
> structurally impossible), the resolution-basis CHECKs, and the tenant-first partial unique index
> over the three OPEN states. Scope respected: this is a P6/M7 increment review; P6 remains
> IN_PROGRESS and no phase acceptance criterion is scored."

---

## 2. What M7 is, in one line

**Two systems disagreeing about one field is a DECISION A HUMAN OWNS, not a winner a machine
picked.** The TMS says load 4471 is delivered and the carrier portal says it is still in transit:
the disputed field **freezes** (`conflicting`), a **named ACTIVE human owns it from creation**, and
**no consequential action proceeds on that field while the conflict stands** — no invoice, no
payment, no carrier assignment. Nothing closes it except a **registered versioned rule carrying a
`rule_id`** or an **authenticated human carrying a `decision_ref`**. Not recency. Not confidence.
Not a model. Not a counterparty. Not a clock — the timer **escalates** and can never resolve, and a
Conflict **never expires**.

### 2.1 The transition table — re-derived mechanically, not carried

The `Still owed` figure in [`CURRENT.md`](CURRENT.md) is **derived at each landing by parsing §14
of all thirteen machine files under `docs/specifications/state-machines/` and counting table rows**,
never by carrying the previous number. At this landing that parse discovered **13** machine files
and counted **134** rows in total — matching the registry's `expected_production_outputs` of "134
transitions" — distributed as:

| Machine | §14 rows |
|---|---|
| M1 work item | 14 |
| M2 pipeline instance | 25 |
| M3 external effect grant | 13 |
| M4 approval | 11 |
| M5 observation | 8 |
| M6 identity binding claim | 11 |
| **M7 conflict** | **7** |
| M8 expectation | 8 |
| M9 exception | 7 |
| M10 compensation | 9 |
| M11 policy | 7 |
| M12 rule | 9 |
| M13 brake | 5 |
| **total** | **134** |

M7 contributes exactly `CF-1`, `CF-2`, `CF-3`, `CF-4`, `CF-5`, `CF-6`, `CF-7` — an **exact set
match** with §14 of `07-conflict.machine.md`. Written after M7: 14 + 25 + 13 + 11 + 8 + 11 + 7 =
**89 of 134**, so **45 remain**.

### 2.2 The shape the database enforces

Five canonical states — `RAISED`, `OPEN`, `ESCALATED`, `RESOLVED_BY_RULE`, `RESOLVED_BY_HUMAN` —
inline `CHECK`ed in the DDL. **There is no sixth**: no `CANCELLED` (M7-AQ-3 is held open, not
answered), no `EXPIRED` (entity §26: a Conflict NEVER expires), no bare `RESOLVED` (that is M9's).
Six canonical kinds — `SYSTEM_VS_SYSTEM`, `CLAIM_VS_CLAIM`, `CLAIM_VS_OBSERVATION`,
`INFERRER_VS_OWNER`, `READBACK_VS_APPROVED`, `RULE_VS_RULE` — also inline `CHECK`ed. `owner_id` is
`NOT NULL` **and** a `FOREIGN KEY (tenant, owner_id) REFERENCES tenant_humans (tenant, human_id)`,
so an ownerless Conflict is **structurally impossible**, not merely discouraged. Resolution `CHECK`s
enforce exactly one basis: `RESOLVED_BY_RULE` requires `rule_id`, `RESOLVED_BY_HUMAN` requires
`decision_ref`, and a resolved row with neither is rejected by the database. The concurrency
invariant is `CREATE UNIQUE INDEX ix_conflicts_one_open_per_field ON conflicts (tenant, entity_ref,
field) WHERE state IN ('RAISED','OPEN','ESCALATED')` — **tenant-first, partial**: one open conflict
per field, and a second detection **attaches a party (CF-7)** rather than raising a second conflict.

Five F7 contracts are registered and only those: `ConflictRaised`, `ConflictOpened`,
`ConflictEscalated`, `ConflictPartyAttached`, `ConflictResolved`. `ConflictRaised`'s registered
producers are `['CF-1', 'IB-6', 'EF-4c']`; `ConflictResolved`'s are `CF-3`/`CF-4` with an
exactly-one-of `{rule_id, decision_ref}` requirement.

---

## 3. Two tenant-first tables enter the canonical partition

The M7 build commit `8bb3207` registered `conflicts` and `conflict_parties` in
[`CURRENT.md`](CURRENT.md)'s tenant-first partition and in
[`phase-0-baseline-manifest.yaml`](phase-0-baseline-manifest.yaml). That partition is asserted
mechanically on every CI run by
`eval/tests/test_bootstrap_hermeticity.py::test_the_canonical_table_partition_is_exact_and_disjoint`
— it is recorded there because the rehearsal's "7 + 3 vs 11" finding was exactly a table quietly
missing from the written account. **P6/M7 declares no tenant-exempt table.**

---

## 4. What the reviewer established ITSELF, and how

The reviewer declared **14 commands with named, checkable expectations** and its harness records
**25 command attempts**. `evidence_reproduced: true` and `claimed_evidence_reproduced: true`. The
load-bearing results it produced with its own hands:

| What it ran | What it showed |
|---|---|
| `git rev-parse HEAD` / `HEAD^{tree}` / `git status --short` | `e97e89d12b31…` / `a73dd12a1e4e…`, status empty — the tree under review is the declared target and is clean |
| `.venv/bin/python scripts/probe_phase6_conflict.py` | exit 0, 70 behaviour lines, **`behaviours as specified, 0 wrong`**, including `WHILE A CONFLICT IS OPEN THE FIELD IS conflicting AND BLOCKS EVERY CONSEQUENTIAL ACTION` and `M7 MINTS NO GATE DECISION` |
| `.venv/bin/python scripts/mutate_phase6_conflict.py` | **16/16 mutants caught** |
| `.venv/bin/python -m pytest eval/tests/test_phase6_conflict.py -q` | **49 passed** |
| `probe … --inject not-a-real-fault` | exit 2 — *"unknown fault … The fault vocabulary is CLOSED and BOUNDED"* |
| `probe … --inject expire-conflict` | exit 2 — refused *"because a Conflict NEVER expires (entity §26, machine §12/§23)"* |
| `probe … --inject cancel-conflict` | exit 2 — refused: *"no CANCELLED state and no conflict-cancellation event is registered anywhere"*, **M7-AQ-3 held open** |
| AST scan of `src/freight_recon` | 115 production modules scanned, **`production importers of conflict: []`** |
| AST scan of `scripts` | **`scripts reaching conflict: ['probe_phase6_conflict.py']`** |
| Channel-join scan | 115 modules scanned, **`modules joining the conflict machine to a channel: []`** |
| F7 introspection of `event_contracts_data.json` | five registered contracts; `ConflictResolved requires exactly one of: [(['decision_ref', 'rule_id'], True)]`; `synonym events registered: []`; `unregistered names in the machine: []` |
| Expiry/cancellation scan + `PRAGMA table_info(conflicts)` | `invented expiry/cancellation surfaces: []`, `invented expiry/extra transition rows: []`, `expiry columns on conflicts: []`, 16 columns |
| Gate-mint scan | **`modules that MINT a gate decision: ['checkpoint.py']`** — M7 is not a second gate |
| `git diff --stat 8bb3207~1 e97e89d -- checkpoint.py external_effect.py identity_binding_claim.py` | **empty** — the five M7 commits touched none of the three protected machines |

### 4.1 Harness statuses that read like failures and are not — recorded, not tidied

The three negative controls are recorded in `executed_commands` with `execution_failed: true` and
`exit_code: null` **while their captured stderr is the correct exit-2 refusal**. This is the same
harness status-vocabulary defect already recorded as `P6-D39` (M5) and `P6-D45` (M6): the harness
has no status for *"the command was supposed to fail, and it failed correctly."* The refusals are
right; the labels are wrong. Recorded as `P6-D51`, not tidied away.

Four of the 25 attempts were refused by the harness rather than by the product — one at the
`composition` layer (a `;`-joined git triple, re-issued as three separate commands, all three ran)
and three at the `vocabulary` layer. **Two of the three were re-issued in approved form and ran.**
The third — a `create_canonical_schema` introspection against a fresh temporary database — was
**not** re-issued; the reviewer instead verified the DDL invariants by `grep`-reading
`src/freight_recon/migrations/phase6_conflicts.py`. Its own criteria basis says so explicitly
("Migration DDL (read)"). **That is a weaker instrument than the live-DDL introspection the M4, M5
and M6 reviewers used**, and it is recorded as part of `P6-D51` rather than described as
equivalent. The fresh-and-migrated schema-readiness result quoted in §5 comes from the run's
scenario evidence, not from the reviewer's own hands.

---

## 5. What Product Driver independently exercised

**Five scenarios, all `PASSED`, 380 assertions, 0 failed, 0 blocked, 0 skipped, 0 assembly
problems.**

| Scenario | Origin | Risk family | Assertions | Outcome |
|---|---|---|---|---|
| `p6_m7_conflict` | permanent | — | 338 | **PASSED** |
| `cf-concurrent-cross-tenant-race` | generated | concurrency | 12 | **PASSED** |
| `cf-duplicate-and-concurrent-detection-idempotent` | generated | idempotency | 10 | **PASSED** |
| `cf-replay-heavy-redelivery` | generated | retry_safety | 10 | **PASSED** |
| `cf-ships-dark` | generated | safety_invariant | 10 | **PASSED** |

Each generated scenario names the failure it was built to provoke: a concurrent detection race
defeating an application-level check-then-insert (two open conflicts for one field, or two tenants'
conflicts coalescing into one); a redelivered detection treated as fresh; a heavy-redelivery replay
rebuilding a stale party set or triggering a downstream effect; and a production module importing
`conflict`, minting a gate decision, or wiring into a channel.

### 5.1 Mutation evidence — 16/16, each guard proven able to fail

### **A GUARD NEVER SEEN TO FAIL IS A DECORATION** ([`CLAUDE.md`](../../CLAUDE.md) §6). Each mutant
reintroduces a specific real defect and is caught:

1. `AutoResolve` accepted — the neither-basis branch silently resolves the conflict
2. a `TimerFired` transition to a resolved state — a clock closes a freight dispute
3. a confidence threshold resolves — a `confidence:` pseudo-rule accepted off the registry
4. the newest source wins — a `recency:` pseudo-rule accepted off the registry
5. an unregistered rule resolves — the CF-3 registry lookup dropped
6. a resolved conflict with **no** basis is insertable — the §16 `CHECK` widened
7. an **ownerless** conflict is insertable — `owner_id NOT NULL` dropped
8. the raise and the freeze split into two commits
9. the one-open-conflict-per-field index loses `UNIQUE`
10. the partial index loses its `WHERE` clause
11. a second detection is not coalesced into an attach
12. `ConflictPartyAttached` is never emitted — replay rebuilds a **stale party set**
13. an attached party's provenance is **strengthened** (`MODEL_INFERRED` stored as `RECONCILED`)
14. the **tenant predicate** is dropped from the open-conflict lookup
15. a CF-6 human resolution is attributed **by position** (emits CF-3 instead of CF-4)
16. an open conflict **stops blocking** — the native projection reports `conflicting=False`

### 5.2 Regressions — run WITH M7's tables present in the schema

P3 **216**, P4 **99**, P5 **561**, M1–M6 **542**, all passed, and the M4, M5 and M6 probes each
still report `behaviours as specified, 0 wrong` with `conflicts` and `conflict_parties` in the
schema. Fresh and migrated canonical databases both report `schema_readiness_problems == []`, with
both M7 tables present and tenant-first.

### 5.3 Ship-dark posture — measured, not asserted

Re-measured by this landing session independently of the run, over discovered populations with the
denominator printed: **115** production modules scanned → `production importers of conflict: []`;
**72** scripts scanned → `['probe_phase6_conflict.py']`; **164** eval modules scanned →
`['test_phase6_conflict.py']`; gate-mint scan → `['checkpoint.py']`. No production module imports
the machine, nothing joins it to an inbound or outbound channel, and `checkpoint.py` remains the
sole minter of a gate decision.

---

## 6. The authority questions M7 preserved — REPORTED, NOT RESOLVED

### **NO SESSION MAY CLOSE `M7-AQ-1`, `M7-AQ-2` OR `M7-AQ-3` BY CHOOSING A READING.** These are
specification questions owed to a founder/architect decision ([`CLAUDE.md`](../../CLAUDE.md) §5),
not M7 defects. The code implements **only what every reading agrees on**, invents no
reconciliation, and says so at the site in `src/freight_recon/conflict.py`.

| | |
|---|---|
| **`M7-AQ-1` — the IB-6 / M6 seam** | `IB-6` (M6) already emits a registered `ConflictRaised` for its `INFERRER_VS_OWNER` disagreement, **minting its own conflict id and writing no M7 row** — there was no `conflicts` table when M6 shipped. M7 **does not rewrite M6**, does not mint a second `ConflictRaised` for a disagreement M6 already announced, and does not silently swallow the seam: it records it as an M7-owned obligation (`M7_AQ1_SEAM`, read straight off the canonical contract so the record cannot drift from the registry) and REPORTS it. Verified at this landing: `identity_binding_claim.py` is byte-unchanged across the M7 commit range. |
| **`M7-AQ-2` — the EF-4c / `UNKNOWN_OUTCOME` seam** | `EF-4c` (a readback contradicting the approved fingerprint) is a **registered producer** of `ConflictRaised`, but the shipped M3 emits `VerificationConflict` alone and moves `ATTEMPTED → UNKNOWN_OUTCOME`. M7 **does not edit `external_effect.py`**, does not rewrite, shorten or route around `UNKNOWN_OUTCOME`, and never launders a readback contradiction into an ordinary failure. A `READBACK_VS_APPROVED` conflict M7 raises blocks like any other, and the block is **additive**. Verified at this landing: `external_effect.py` is byte-unchanged across the M7 commit range. |
| **`M7-AQ-3` — cancellation vocabulary / lifecycle** | There is **no cancellation transition, no `CANCELLED` state and no `ConflictCancelled` event**, anywhere. A party retraction **never silently closes** a conflict. The probe **refuses** `--inject cancel-conflict` with exit 2 and a corpus-grounded reason rather than inventing a state — the question is held open by refusal, which is the only way to hold it open without answering it. |

**`Unknown Outcome` never auto-resolves, and M7 did not give it a back door.** M3 remains the single
effect authority; M7 writes no `effect_grants` and no `identity_binding_claims` row.

---

## 7. Minor and nonblocking items — recorded, not actioned

### **THE INDEPENDENT REVIEW RETURNED ZERO FINDINGS AND ZERO ADJUDICATIONS.** Nothing below is a
reviewer finding and none may be cited as one. Each was identified at this landing from the run's
own structured evidence, the M7 source, the specification corpus and the CI record. Each is
**RECORDED, NOT ACTIONED** ([`CLAUDE.md`](../../CLAUDE.md) §13 — the debt row is the complete
deliverable). None can produce a wrong customer outcome, violate an invariant, or make a later
phase unsafe, and the machine ships dark.

### `P6-D47` — the three M7 authority questions are REPORTED, not resolved · `minor` · specification seam

`M7-AQ-1`, `M7-AQ-2` and `M7-AQ-3` as set out in §6. The code implements only what every reading
agrees on. They close by a founder/architect decision, **not** by a session choosing a reading.

### `P6-D48` — this commit has NO GREEN CI CONCLUSION, and CI never reached M7's tests · `minor` · CI

See §8. **This is the weakest CI position of any P6 landing so far** and it is stated as such.

### `P6-D49` — CI does not execute M7's probe or mutation battery · `minor` · CI coverage

The `effect-grant` job runs M3's probe and battery on every push precisely because `pytest eval`
does not invoke them. There is no equivalent job for M4 (`P6-D33`), M5 (`P6-D37`), M6 (`P6-D43`) or
M7 — verified mechanically at this landing by the absence of **any** `phase6_conflict` occurrence in
`.github/workflows/ci.yml` (count: 0). `eval/tests/test_phase6_conflict.py` **is** inside `pytest
eval`, which is what the suite jobs run — but see §8 for why that did not help on this commit.
Closing this is a change to CI wiring, which a status/evidence landing deliberately does not make.

### `P6-D50` — the run's gate and topology snapshots are stale and read as blockers · `minor` · evidentiary

`accepted/protocol-resolution.json` was written at `03:35:09Z`; the review completed at `03:42:58Z`.
Its `gates.independent_review` therefore reads **`NOT_RUN`** — *"no independent review recorded for
this state"* — which the run's own review ledger contradicts (`reviews: [1]`, `verdict: SUPPORTED`,
`independent: true`). Its `topology.state` reads **`ILLEGAL`**, because it evaluates HEAD against a
recorded status commit `d59b7400a472` under the **retired two-commit content+metadata convention**;
that convention was removed in the 2026-08 simplification and must not be revived. The same
snapshot's own `status` is **`CONSISTENT`** with `violations: []`, `deadlocks: []`,
`environment_blockers: []` and `next_safe_action: "proceed: topology and authority are consistent"`.
This is the identical stale-snapshot condition recorded as `P6-D38` (M5) and `P6-D44` (M6).

### `P6-D51` — reviewer-harness status vocabulary, and one instrument substitution · `minor` · evidentiary

Two parts, both described in §4.1. (a) The three correct exit-2 negative controls are labelled
`execution_failed: true` with `exit_code: null` — the recurring harness defect (`P6-D39`, `P6-D45`).
(b) Four of 25 command attempts were refused by the harness's own composition/vocabulary layers; two
were re-issued in approved form, but the fresh-schema DDL introspection was **not**, so the reviewer
verified the migration invariants by **reading the migration source** rather than introspecting a
live database — a weaker instrument than the one the M4/M5/M6 reviewers used. The live fresh-and-
migrated readiness result exists in the run's scenario evidence, not in the reviewer's own commands.

### `P6-D52` — five of nine generated scenarios were rejected at assembly · `minor` · coverage disclosure

Nine adversarial scenarios were proposed in `scenario-generation/wave-01.json`; **four were accepted
and all four PASSED**; **five were REJECTED at assembly** — `cf-competing-resolutions-serialize`,
`cf-escalated-resolves-by-target-state`, `cf-confidence-negative-control-zero`,
`cf-retraction-never-closes` and `cf-crossfamily-producers-recorded` — each for the same reason: an
unapproved command vocabulary (a `create_canonical_schema` / `event_contracts_data.json`
introspection outside the approved set), **not** for anything about M7. This is materially better
than `P6-D46`, where the M6 run accepted **zero** generated scenarios; but it is still a reduction
in generated adversarial pressure, and it is disclosed rather than glossed.

**What that costs, stated exactly.** Verified mechanically at this landing against
`probe_phase6_conflict.py --list-cases`, all five rejected themes have a **named permanent-probe
case** that passed: `competing-resolutions-serialize-at-most-one-wins`,
`escalated-resolution-is-by-target-state-never-by-position`, `confidence-cannot-resolve-a-conflict`,
`a-party-retraction-never-silently-closes-the-conflict`, and
`the-cross-family-conflict-raised-producers-are-recorded`. **What was lost is the generated
scenarios' composed dimension pressure** (varied `--concurrency`, `--parties`, `--seed`,
`--delay-ms`), not the behaviours themselves. The run's own `scenario_requests` ask for exactly that
pressure next: CF-7 party attach at `--concurrency 6-8` with `--parties 6-8`, and a
`READBACK_VS_APPROVED` conflict composed alongside a live M3 `UNKNOWN_OUTCOME`.

### Standing items, carried and unchanged — not new debt

`P6-D40` (no status guard enforces that a P6 checkpoint scores no acceptance criterion, and none
enforces that its cited review report exists on disk; the partition guard matches table names as
whole-file substrings) is **carried forward unchanged and was NOT re-verified at this landing** — no
mutation battery was run against the status guards here, and none is claimed. `P6-D24`–`P6-D27`, the
G2 residuals, and every earlier P6 residual are carried unchanged.

---

## 8. ### CI — the honest record. The workflow did NOT conclude `SUCCESS`

**GitHub Actions run `33142496300` on `e97e89d` concluded `cancelled`.** Job by job:

| Job | Conclusion |
|---|---|
| `P6/M3 effect-grant probe + mutation` | **SUCCESS** |
| `Full test suite (py3.11)` | **CANCELLED** at the declared 60-minute ceiling, having reached ~58%, **with no pytest failure observed before cancellation** |
| `Full test suite (py3.12)` | **CANCELLED** at the declared 60-minute ceiling, having reached ~58%, **with no pytest failure observed before cancellation** |
| `Safety invariants (fast)` | **CANCELLED** at its declared 30-minute ceiling, having reached ~23%, **with no pytest failure observed before cancellation** |
| `Risk radar` | **SKIPPED** (pull-request-only) |

### **THIS IS THE WEAKEST CI POSITION OF ANY P6 LANDING.** At `P6-CP-4`, `P6-CP-5` and `P6-CP-6` at
least one full suite and the safety job completed. **Here not one full suite completed and the
safety job did not complete either.** The only job that concluded `SUCCESS` is M3's effect-grant
job, which does not execute a single line of M7.

### **AND CI ALMOST CERTAINLY NEVER REACHED M7'S TESTS AT ALL.** Measured at this landing rather
than assumed: `pytest eval -q -p no:cacheprovider --collect-only` on this exact tree collects
**2970** tests, and `eval/tests/test_phase6_conflict.py` occupies **positions 2058–2106**, i.e.
**69.3%–70.9%** of the run. Both suite jobs were cancelled at **~58%** — before that range. So the
honest statement is not merely "no verdict": **the repository has no CI execution of `M7`'s 49 tests
on this commit, on either interpreter.** (Denominator and caveat both stated: the collection was
taken locally on this tree with the repository's own command; CI's percentage is pytest's own
progress display over its own collection under its own interpreter, so the figure is strong evidence
of ordering, not a byte-exact reproduction of CI's run.) `test_phase6_conflict.py` is **not** among
the 26 files the `Safety invariants (fast)` job names, so that job's cancellation is irrelevant to
M7 either way.

### **THE JOB CONCLUSIONS ABOVE WERE SUPPLIED BY THE FOUNDER AND WERE NOT RE-READ BY THIS SESSION.**
`gh run view 33142496300` was attempted from this sandbox and failed with
`tls: failed to verify certificate: x509: OSStatus -26276` — the identical failure recorded at the
`P6-CP-6` landing. A later session with network access should read the run itself rather than trust
this transcription.

**The workflow is not green and this document does not say it is.** The founder has explicitly
chosen to land M7 on the evidence that exists — the reviewer-reproduced probe, mutation battery,
targeted suite and negative controls, plus five passing Product Driver scenarios, all executed
against this exact tree — treating the cancellations as a **non-product CI runtime limitation**
rather than as evidence of an M7 defect. **That is recorded as a founder DECISION, not as a
verification** (`P6-D48`). It closes only by a CI run on this branch that concludes `SUCCESS`.

---

## 9. What did NOT change

- **No P6 acceptance criterion is scored.** `criteria_scored` is `[]` on all seven checkpoints.
- **P6 is not COMPLETE.** Registry `status: READY`, `execution_state: IN_PROGRESS`. **P7 stays
  `BLOCKED`.**
- **M7 ships dark.** Zero production importers, no channel join, no gate mint, and the production
  `GateRegistry` stays EMPTY until U8.1/P8.
- **The kernel is untouched.** `checkpoint.py`, `external_effect.py` and `identity_binding_claim.py`
  are byte-identical across the entire M7 commit range `8bb3207~1..e97e89d`.
- **`R-07` remains CONTAINED, and CONTAINED is not ENABLED.** No production write is enabled and no
  autonomy was granted.
- **M1–M6 are not rebuilt or polished.** Their residuals remain debt rows.
- **The next build checkpoint is M8 — the Expectation.** Nothing here starts it.
