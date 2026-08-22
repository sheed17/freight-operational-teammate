> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **This is evidence of a past moment, not status.** It is an INDEPENDENT REVIEW: it set no
> acceptance criterion, marked no phase complete, closed no risk, enabled nothing and authorized no
> external effect. It reviewed the `P6-CP-3` candidate (machine **M3 — the External Effect / Effect
> Grant**) at content commit `5f9779f5b3339ed8c7af54aecd0772994eedbb1a` (tree
> `e0aff5f5c9bf2ec90d2e3e1f5ed644ae14392458`, branch `p5/u5-1-g2-spec-correction`, working tree
> clean) and returned **SUPPORTED, confidence 0.82**.
>
> ### **IT DID NOT REVIEW THE COMMIT THAT CARRIES IT.** The landing commit that brought this file
> in-tree did not exist when the review was performed. Nothing here may be cited as an independent
> review of that commit.
>
> ### **P6-CP-3 IS A CHECKPOINT, NOT A PHASE ACCEPTANCE.** P6 is **NOT COMPLETE**, no P6 acceptance
> criterion is scored, and P7 is not unlocked. M3 continues to **ship dark**.
>
> ### **NO ADJUDICATION FOLLOWED THIS REVIEW, AND NONE IS OWED.** M3 is tier-2 under
> [`CLAUDE.md`](../../CLAUDE.md) §7 — builder + **one focused independent review by a session that
> did not build it**, plus CI. The adjudication chains and finalizer rituals cited by the `P6-CP-1`
> and `P6-CP-2` records were retired in the 2026-08 engineering-process simplification and must not
> be revived on the strength of those older artifacts.

# P6-CP-3 — FOCUSED INDEPENDENT REVIEW — candidate `5f9779f`

**Verdict: `SUPPORTED` · confidence `0.82`**

| | |
|---|---|
| **Reviewed tree** | commit `5f9779f5b3339ed8c7af54aecd0772994eedbb1a`, tree `e0aff5f5c9bf2ec90d2e3e1f5ed644ae14392458`, branch `p5/u5-1-g2-spec-correction`, **0 dirty files** |
| **Reviewer lineage** | A session that did not build M3. The review record states `inherited_builder_context: false`; reviewer session `d6f0bdae-d61c-414d-baff-dbf65af67590` |
| **Performed** | `2026-08-22T08:03:02+00:00` |
| **Source artifact** | Product Driver run `20260822-070832`, `iteration-01/independent-review.json` (separate repository, `neyma-product-driver`), sha256 `bc410ff7a04e5574f676d31ccd7c4f8631196a42adc08015c0b140f4ba00d7a6`. Its prose is quoted verbatim below; nothing is upgraded, softened or summarised into a stronger claim |
| **Adjudications recorded** | **none** (`adjudications: []`) |
| **Findings** | **2, both `minor`, neither blocking** |
| **Scope declared by the run** | `P6/M3`, repository unit `P6-CP-3`, `claims_phase_completion: false` |

---

## 1. The verdict, verbatim

> "P6/M3 (the External Effect / Effect Grant machine, P6-CP-3) is supported by evidence. I
> independently verified, by reading, that the implementation's 13-row transition table is an exact
> bijection with the spec's §14 (EF-1, EF-2, EF-2r, EF-2x, EF-2f, EF-3, EF-3f, EF-3u, EF-4, EF-4c,
> EF-4u, EF-5, EF-5x); that the safety invariants the unit exists to guarantee are enforced as
> machine guards (FAILED requires affirmative proof of non-occurrence; a timeout/crash/lost-response
> is UNKNOWN_OUTCOME not FAILED; blind readback is OBSERVATION_UNAVAILABLE not VERIFIED; VERIFIED
> requires a healthy readback matching the approved fingerprint; UNKNOWN_OUTCOME is human-owned and
> no timer moves it via the ILLEGAL EF-5x; mint and the claim CAS route only through P3's kernel and
> no second gate is constructed); that the migration adds the six outcome columns and the two
> tenant-first FKs (checkpoint_witnesses deferrable, pipeline_instances) with a structural readiness
> oracle; that the machine ships dark (no src/freight_recon module imports it — only the migration is
> imported, which is expected); and that P6-D24 (drain_handler_for) and P6-D11 (F14 predecessor /
> complete-stream) are implemented in consume(). Behavioural correctness is corroborated by
> harness-captured command execution (commands.log, suite-result.json, decision.json) captured against
> the exact current tree (HEAD 5f9779f, branch p5/u5-1-g2-spec-correction, 0 dirty files, confirmed in
> context-provenance.json): probe exit 0 'behaviours as specified, 0 wrong'; M3 pytest 49 passed;
> regressions P3 82 / P4 99 / P5 182 / M1+M2 348; mutation 9/9 caught; negative control exit 2; schema
> readiness []; FKs to both referents; commit-once UNIQUE index intact. Crucially, nothing is
> overclaimed on the status surfaces: M3 is deliberately absent from the registry's
> landed_checkpoints, no P6 criterion is scored, and P6 remains READY / IN_PROGRESS — exactly what
> this task's scope requires."

## 2. The evidentiary boundary the reviewer drew, and this record keeps

The review distinguishes two classes of claim, and that distinction is load-bearing. It is preserved
here rather than flattened into a single word.

| Class | What it covers | Standing |
|---|---|---|
| **VERIFIED by the reviewer, directly** | Structural conformance read off the tree: the §14 bijection, the guards that enforce the safety invariants, the migration's columns and the two tenant-first foreign keys, the ship-dark posture (its own `Grep` over `src/`), and that `P6-D24` and `P6-D11` are implemented in `consume()`. | The reviewer's own work |
| **CORROBORATED, not reviewer-reproduced** | The pass/fail behaviour: 49 M3 tests passing, the probe's `behaviours as specified, 0 wrong`, the 9/9 mutation battery, the P3/P4/P5/M1+M2 regression counts, the schema readiness `[]`, the FK and UNIQUE-index introspection. | Harness-captured stdout and exit codes, bound to a tree hash matching this HEAD |

**This review observed no CI result.** CI's own result on this branch is not observable from the
repository, and no committed receipt exists or may exist ([`CLAUDE.md`](../../CLAUDE.md) §0 forbids
them). Nothing in this record may be read as CI evidence.

## 3. Criteria assessment, as recorded

| # | Criterion | Assessment | Basis, as the reviewer stated it |
|---|---|---|---|
| 1 | Transition table is the specification's: the 13 `EF-*` identifiers of §14 implemented exactly (bijection, exact set equality) | **PASS** | Read `docs/specifications/state-machines/03-external-effect-grant.machine.md` §14 (13 rows) and `src/freight_recon/external_effect.py`'s `TRANSITIONS` tuple; the id sets are identical. `test_the_transition_identifiers_are_a_bijection_with_the_specification` parses §14 and asserts equality, and it executed green (49 passed, `commands.log`) |
| 2 | Eight canonical states with `UNKNOWN_OUTCOME` non-terminal and human-owned; `REVOKED` distinct from `EXPIRED_UNCLAIMED` | **PASS** | `migrations/phase6_external_effects.py` defines `EF_STATES` (8), `EF_TERMINAL_STATES` (4, excluding `UNKNOWN_OUTCOME`), `EF_HUMAN_OWNED_STATES=('UNKNOWN_OUTCOME',)`. CHECK vocabulary confirmed as the 8 states via `commands.log` DB introspection; probe printed `REVOKED IS NOT EXPIRED_UNCLAIMED` |
| 3 | `FAILED` requires affirmative proof of non-occurrence; timeout/crash/lost-response is `UNKNOWN_OUTCOME`, never `FAILED` (GR-5/GR-6) | **PASS** | `external_effect.py` `_writes_and_payload` EF-3f raises `GuardNotSatisfied` without `failure_proof`; EF-3u routes to `UNKNOWN_OUTCOME`. The mutation battery caught the "EF-3f accepts FAILED with NO proof" mutant (`commands.log` 9/9) |
| 4 | `VERIFIED` requires a healthy readback matching the approved fingerprint; blind is `OBSERVATION_UNAVAILABLE`, not failure (M-70/71) | **PASS** | EF-4's guard requires `health_signal` and `matched_fingerprint == grant.material_facts_fingerprint`, else EF-4u/EF-4c. Mutant "EF-4 stops requiring the readback to MATCH" was caught |
| 5 | `UNKNOWN_OUTCOME` has a named ACTIVE human owner and no timer resolves it (rule 13, EF-5x ILLEGAL) | **PASS** | `_require_active_human` checks `tenant_humans state='ACTIVE'` before any `HUMAN_OWNED_STATES` write; EF-5x is `illegal=True` and excluded from `legal_transitions`. `test_no_timer_moves_an_UNKNOWN_OUTCOME` and `test_UNKNOWN_OUTCOME_cannot_be_created_without_a_named_active_human` present and executed green |
| 6 | Mint and the claim CAS reuse P3's kernel only; no second effect authority / gate is constructed (`CLAUDE.md` rule 17) | **PASS** | `mint()` calls `run_checkpoint_locked` and `claim()` calls `claim_grant_cas_locked`; `test_the_ledger_is_the_only_effect_authority` AST-asserts no `GateRegistry`/`GateEntry` construction. `commands.log` AST scan: only `checkpoint.py` mints a gate decision |
| 7 | Migration delivers the outcome-aspect columns and two tenant-first FKs; fresh canonical DB reports readiness `[]` | **PASS** | `phase6_external_effects.py` adds `EF_OUTCOME_COLUMNS` and `EF_REQUIRED_REFERENTS` (`checkpoint_witnesses`, `pipeline_instances`); the readiness oracle checks both. `commands.log`: `problems: []`, columns present, `foreign keys -> [checkpoint_witnesses, pipeline_instances]` |
| 8 | M3 ships dark: no production importer of the machine; only the probe may import it | **PASS** | The reviewer's own `Grep` over `src/` found no import of the `external_effect` module (only its migration `phase6_external_effects` is imported by `schema.py`/phase2). Corroborated by `test_it_ships_dark` (AST, denominator inspected > 20) and the `commands.log` AST scan: `production importers: []`, `scripts reaching external_effect: [probe_phase6_external_effect.py]` |
| 9 | `P6-D24` (strict consumer supplies `drain_handler_for`) and `P6-D11` (§8 complete-stream / F14 predecessor, ORDER not CONTIGUITY) discharged | **PASS** | `consume()` passes `drain_handler_for` and `requires`/`requires_existing` to `DedupInbox`; the reference resolver parks a missing grant; `_envelope` stamps `previous_aggregate_version` on every event. Tests for park/drain and the F14 marker riding the stream present and executed green; the probe printed the corresponding markers |
| 10 | No overclaim: M3 not recorded as landed, no P6 criterion scored, P6 remains READY / IN_PROGRESS | **PASS** | At the reviewed tree, `landed_checkpoints` contained only `P6-CP-1` and `P6-CP-2`, with a comment keeping `P6-CP-3` deliberately absent and `criteria_scored` empty; `CURRENT.md` marked M3 a CANDIDATE, NOT landed / NOT scored. Matches `task-scope.json`'s `claims_phase_completion: false` |
| 11 | Exhaustive (state × trigger) illegal sweep per `foundational-machine-acceptance.md` per-machine assertion #2 | ### **CANNOT_DETERMINE** | "No explicit cartesian sweep test found in `eval/tests/test_phase6_external_effect.py`; illegality is exercised only at representative points. Exhaustiveness is structurally guaranteed by the table-driven `legal_transitions()`/GR-1 refusal, but I cannot confirm an enumerated exhaustive assertion exists. This is a G1 phase-acceptance item, explicitly not this run's scoring bar." |

**Criterion 10 was true of the reviewed tree and is deliberately superseded by the landing commit
that carries this report** — which records `P6-CP-3` as a landed *checkpoint*. Its three other
clauses are prohibitions and **remain in force**: no P6 acceptance criterion is scored, `P6` stays
`READY` / `IN_PROGRESS`, and P6 has not reached phase acceptance.

## 4. Findings — two, both `minor`, neither blocking

### F-1 — read-only reviewer: behaviour is corroborated, not reviewer-reproduced

> **Finding.** "This review session is read-only and could not itself execute the suite, probe or
> mutation battery; the behavioural claims (49 M3 tests pass, probe 0-wrong, 9/9 mutants, regressions
> green) rest on the Product Driver harness's captured command outputs (commands.log /
> suite-result.json) rather than reviewer re-execution. Those receipts bind to the exact tree under
> review (HEAD 5f9779f, clean, per context-provenance.json), so they are admissible, but they are a
> harness capture, not a committed CI receipt (none exists — CLAUDE.md §0 forbids committed
> receipts), and CI's own result on this branch is not observable from the repository. Structural
> conformance was verified by the reviewer directly; behaviour is corroborated, not
> reviewer-reproduced."
>
> **Reasoning.** "Discipline requires distinguishing VERIFIED from corroborated. The code/spec
> conformance and ship-dark posture I verified by reading; the pass/fail behaviour I confirmed only
> from harness-captured stdout+exit codes on a tree hash matching the current HEAD. This does not
> weaken the verdict because the captured evidence matches the tree and my structural read
> independently confirms the code implements the invariants the log reports, but it is the honest
> boundary of what a read-only session can certify."

**Evidence path:** `runs/20260822-070832/iteration-01/commands.log` (Product Driver repository).
**Severity:** `minor`. **Not actioned** — it is a statement of the review's own reach, not a defect
in M3. It is recorded here so no later session mistakes this report for execution evidence.

### F-2 — illegal transitions are tested at representative points, not by an exhaustive sweep

> **Finding.** "The test module covers illegal transitions only at representative points (EF-5x timer
> on UNKNOWN_OUTCOME, terminal-state protection, an F14 marker riding the strict stream) rather than
> an explicit exhaustive (state × trigger) cartesian sweep asserting every non-enumerated pair is
> ILLEGAL — the phase acceptance contract's per-machine mandatory assertion #2. The risk is mitigated
> structurally: apply() derives legality solely from legal_transitions(), which returns empty for any
> non-enumerated pair, and GR-1 then refuses uniformly (raise, persist nothing, record
> IllegalTransitionAttempted on both surfaces), so exhaustiveness is a property of the table-driven
> design, not of enumerated test cases."
>
> **Reasoning.** "The exhaustive-sweep requirement is part of foundational-machine-acceptance.md
> (AC-MACH, gate G1), which is a PHASE acceptance concern; the task scope explicitly states this run
> does not score a P6 acceptance criterion and phase acceptance is not this run's bar. It is recorded
> as a debt observation for the eventual G1 review, not a blocker on M3 as a landed-increment
> candidate."

**Evidence path:** `eval/tests/test_phase6_external_effect.py`. **Severity:** `minor`.
**Recorded, not actioned** ([`CLAUDE.md`](../../CLAUDE.md) §13) — it is **owed at gate G1**, where
the per-machine mandatory assertions are scored, and it is the same observation as criterion 11's
`CANNOT_DETERMINE`. It cannot produce a wrong customer outcome on this tree: the machine ships dark
and refuses every non-enumerated pair by construction.

## 5. What this review is not

- **Not a phase acceptance.** No P6 acceptance criterion is scored, and none may be from any lineage
  that built M3. P6 remains `READY` / `IN_PROGRESS`.
- **Not an adjudication**, and none is owed — M3 is tier-2 (`CLAUDE.md` §7).
- **Not CI evidence.** The reviewer observed no CI run; see F-1.
- **Not an enablement.** M3 ships dark: zero production importers, only the probe reaches it. No
  external effect is enabled on live traffic, the deployed governed route still answers
  `ROUTE_NOT_CONFIGURED`, and the production `GateRegistry` stays EMPTY until U8.1/P8.
- **Not a review of the commit that carries it** — see the banner.
