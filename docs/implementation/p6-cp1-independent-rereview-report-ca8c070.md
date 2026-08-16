> # ⛔ HISTORICAL REVIEW — NOT CURRENT AUTHORITY
> **Preserved as received; the body below this banner is byte-identical to the artifact on
> `refs/preserve/p6-cp1-independent-rereview-ca8c070` (commit `7dff7f1`, blob
> `52c2efea58e89aed3704748e110a4c0d09353260`).** This is evidence of a past moment, not status.
> It is an INDEPENDENT REVIEW, **not** an adjudication: it set no acceptance criterion, marked no
> phase complete, closed no risk and authorized no finalization. It reviewed the P6-CP-1 candidate
> at content commit `ca8c070646f2a5f84fc6cafd926d78d1530ebeff` (tree
> `29ad9c25e75619effd4fa2675af320031aea9e6b`) and returned **ACCEPT FOR P6-CP-1 ADJUDICATION**.
>
> ### **IT DID NOT REVIEW THE COMMIT THAT CARRIES IT.** The landing commit that brought this file
> in-tree did not exist when this was written. Nothing here may be cited as an independent review of
> that commit. The separate targeted adjudication that followed it is
> [`p6-cp1-targeted-adjudication-report-ca8c070.md`](p6-cp1-targeted-adjudication-report-ca8c070.md).
>
> ### **P6-CP-1 IS A CHECKPOINT, NOT A PHASE ACCEPTANCE.** P6 is NOT COMPLETE and no P6 acceptance
> criterion is scored.

# P6-CP-1 — FRESH TARGETED INDEPENDENT RE-REVIEW

**Reviewed candidate: content commit `ca8c070646f2a5f84fc6cafd926d78d1530ebeff`**
**(tree `29ad9c25e75619effd4fa2675af320031aea9e6b`; metadata commit `64f6f6c62a785c6f4377b8c96a6000acc1e18f35`)**

**VERDICT: ACCEPT FOR P6-CP-1 ADJUDICATION**

Reviewer: a fresh independent session. It did not implement M1, did not remediate M1 at any
candidate, did not review any earlier P6-CP-1 candidate, did not author `ca8c070`, did not author
`64f6f6c`, and resumed no prior session. Review date: 2026-08-15.

> This is an independent-review **source artifact**. It is **not** an adjudication. It scores no
> acceptance criterion, marks no phase or unit complete, closes no risk, and authorizes no
> finalization. It does not begin M2. It reviews `ca8c070` — not the rejected `f5af910`, and not the
> commit that will eventually carry this report.

---

## 1. Scope, and what this review refused to do

Targeted re-review after remediation of two material defects the previous fresh targeted independent
review raised against `f5af910`:

- **F-04** — heterogeneous parked events could be drained through another event's handler/context.
- **F-05** — partial prerequisite resolution could return `PARKED` while the durable row remained
  `DRAINED`, making the event undiscoverable and unexpirable.

`F-01`, `F-02` and `F-03` were re-attacked as preservation surfaces. M1 was not redesigned, P5 was
not re-certified, M2 was not begun, no unrelated debt was actioned, and **no finding of this review
was remediated by this review**.

Builder test counts were not trusted. Every load-bearing claim below was re-derived by this session
with probes it wrote itself.

## 2. Repository truth, established mechanically

| Claim | How it was checked | Result |
|---|---|---|
| `64f6f6c` is a direct child of `ca8c070` | `git log --format="%H %P"` | CONFIRMED |
| `ca8c070`'s tree is `29ad9c25` | `git rev-parse ca8c070^{tree}` | CONFIRMED |
| `SUITE-RESULT.json` / `GATE-RESULT.json` are bound to that tree | recorded `tree` field vs `rev-parse` | CONFIRMED — both record `29ad9c25` |
| the metadata commit smuggled no content | `git show --stat 64f6f6c` | 5 status docs only; `git diff ca8c070 HEAD -- src eval scripts pytest-canonical.ini` is EMPTY |
| working tree is clean | `git status --porcelain` | clean at entry and at exit |
| the candidate claims nothing | registry `P6` | `execution_state: NOT_STARTED`, `checkpoint_state: NO_CHECKPOINT`, `validation_blockers: []`, `independent_review_report: null`, no criterion scored |
| P6 ships dark | grep for importers of `work_item` under `src/` and `scripts/` | ZERO production importers |

The runtime diff is nine substantive lines in `src/freight_recon/event_inbox.py`.
`src/freight_recon/work_item.py` is byte-identical to its predecessor: M1 was not redesigned,
`requires_existing` was not removed, M-26 was not weakened.

## 3. F-04 — a parked event is executed only under its own semantics

### 3.1 The design shape, verified against the implementation

- The post-apply cross-cohort cascade is **opt-in**. `consume()` returns immediately when
  `drain_handler_for is None` (`event_inbox.py:389`), so the default is OFF.
- What an opting caller supplies is a **factory from a parked envelope to the handler for THAT
  envelope** (`DrainHandlerFactory`). `_drain_for` calls `drain_handler_for(park.envelope)` per event
  (`event_inbox.py:707`) — the handler is derived from the envelope about to be consumed, never from
  the event that seeded the cascade.
- M1 supplies no factory and therefore cascades nothing.
- The `requires_existing` **self-release** path is distinct from the cascade, lives in
  `_consume_validated`, and touches no other event.

The parameter is keyword-only and defaults to `None`; the positional signature
`(self, envelope, handler)` is unchanged, so no existing call site can bind it accidentally.

### 3.2 The same-store hostile case (reviewer-written)

ONE durable store; ONE missing Work Item; TWO canonical M1 trigger shapes with deliberately
distinguishable effects:

| Event | Aggregate | Prerequisite kind | Intended effect |
|---|---|---|---|
| `HumanDecided` | `work_item:wi-hostile` (its own) | explicit `requires_existing` | WI-9: `AWAITING_HUMAN → IN_PROGRESS` |
| `PipelineClosed` | `pipeline_instance:pi-1` | cross-aggregate `requires` | WI-3: `IN_PROGRESS → CLOSED` |

Both parked against the SAME referent — one cohort, not two. Proven:

- `HumanDecided` was interpreted only as `HumanDecided` (WI-9 fired; state `IN_PROGRESS`, not
  `CLOSED`).
- `PipelineClosed` was interpreted only as `PipelineClosed` (WI-3 fired; state `CLOSED`).
- At the moment `HumanDecided` was consumed, `PipelineClosed` had **no inbox receipt** and its park
  was still `PARKED` — it inherited nothing.
- Each legitimate transition occurred exactly once (`WI-9` ×1, `WI-3` ×1, scoped to the aggregate).
- No fabricated `IllegalTransitionAttempted` was produced.
- Neither park became `DRAINED` before its own legitimate terminal handling.
- Redelivery after completion is `DUPLICATE_NOOP` with a byte-identical state digest.
- No event left both populations, over a **proven population of two**.

### 3.3 The old failure shape, recreated

Under mutant **W31** (the cascade restored to the seeding invocation's handler), this reviewer's own
probe reproduced the rejected tree's behaviour exactly:

```
PipelineClosed park           -> DRAINED
PipelineClosed inbox receipt  -> present (silently applied under HUMAN_DECIDED semantics)
WI-3                          -> never fired; Work Item stayed IN_PROGRESS
emissions                     -> ['HumanDecided', 'IllegalTransitionAttempted']   (fabricated)
later genuine retry           -> DUPLICATE_NOOP
```

Ten independent assertions failed. The replacement makes that sequence unreachable, because the
handler is obtained from the envelope rather than from the seeder.

**F-04: CLOSED.**

## 4. The opt-in drain API and caller compatibility

Enumerated mechanically over the whole repository, not inferred from the suite:

- **7 `DedupInbox` construction sites.** Exactly **one is production** — `work_item.py:1238` (M1).
  One is evidence tooling (`scripts/postgres_p5_gate.py`, which passes no resolver, so nothing can
  park). Five are tests.
- **115 `.consume(` call sites. Exactly 5 opt in**, and all five are in
  `eval/tests/test_phase5_event_transport.py`. **ZERO production callers opt in.**
- M1's `consume` call passes no `drain_handler_for`.

The five opt-ins use `phase5_kit.agnostic_drain(handler)`. That helper's justification was checked
rather than accepted: `RecordingHandler.__call__` reads only the envelope it is handed and closes
over a connection and a list — nothing event-specific — so "the handler for THAT envelope" and "this
handler" genuinely are the same function *for that handler*. The helper's docstring says explicitly
that this is a property of that handler and not of handlers generally.

**No caller semantic drift.** The diff to the P5 transport tests removes exactly four lines, each a
`consume(...)` call re-issued with an explicit opt-in. **No assertion was removed, weakened or
rewritten.** The one honest behaviour change is that those five cases previously received the
cascade by default and now request it — capability preserved, default changed, which is the
prescribed remediation.

Reviewer-written probe additionally proved:

- **default OFF**: with no factory, `drained == ()`, neither parked event was executed by anyone, and
  both parks stayed `PARKED` and rediscoverable;
- **opt-in correctness**: each parked event was handled by its own handler and each park closed after
  its own handling;
- **positive control**: a deliberately wrong factory *does* misroute all three events, so the
  correctness assertion is capable of failing.

Under mutant **W31a** (factory consulted with the seeding event), that probe fails — the defect is
detectable one layer down, in the opt-in path M1 does not use.

`requires_existing` semantics (F-03) are unchanged, and the implicit self-aggregate skip is intact:
a required reference equal to the event's own aggregate is still skipped in the `requires`
derivation, while a pair named in `requires_existing` is still checked without a skip.

## 5. F-05 — durable park state tells the truth

### 5.1 The ordering itself, not repair-by-later-UPDATE

`_park_locked`'s `ON CONFLICT ... DO UPDATE` sets **only** `attempts` and `last_attempt_at`. It does
not restore `park_state`. That is precisely why stamping `DRAINED` before eligibility was proven was
unrecoverable, and why the accepted fix is an **ordering** change rather than a repair: the stamp was
moved out of the self-release branch and onto the two paths that have actually finished with the
event — the apply, and the `STALE_NOOP` that means the same thing. `_resolve_park_locked` also
carries `AND park_state = 'PARKED'` in its WHERE clause, so it can only ever move a row out of
`PARKED`.

Every exit path after the self-release flag is set was enumerated and exercised:

| Path | Durable outcome | Verified |
|---|---|---|
| a remaining `requires` blocker | re-parks; row stays `PARKED` | yes |
| strict `VERSION_GAP` | re-parks; row stays `PARKED` | yes (§5.3) |
| `STALE_NOOP` | `DRAINED` — the fact is superseded, i.e. finished with | yes |
| `APPLIED` | `DRAINED`, in the same commit as the consumption | yes |
| handler raises | rollback; row stays `PARKED`, no receipt | yes (§5.3) |

### 5.2 The partial-prerequisite case (reviewer-written)

An event with one `requires_existing` prerequisite and one additional `requires` prerequisite. The
first resolves; the second does not. Proven at the moment of reconsideration:

- API says `PARKED_MISSING_AGGREGATE`;
- the database row says `PARKED`;
- `resolved_at` is `NULL` — not falsely set;
- `parked()` returns it;
- `expire_overdue()` can still reach it, and surfaces it **with its accountable human**;
- the accountable owner is intact;
- no effect occurred, and no inbox receipt exists;
- the outcome detail names the **current** blocker (the still-missing reference), even though the
  immutable park row correctly still records why it was originally parked.

Both branches were then exercised:

- **A — the second prerequisite arrives**: outcome `APPLIED`, the handler ran **exactly once**, the
  park became `DRAINED` **exactly once**, `resolved_at` genuinely set, redelivery `DUPLICATE_NOOP`.
- **B — it never arrives**: six reconsiderations never falsely drained the row, `attempts` were
  counted, `parked()` kept discovering it, and after TTL `expire_overdue()` returned it with its
  owner. M-26's owner-bearing escalation still operates. No effect ever occurred.

Under mutant **W32** this probe fails exactly as the original defect did: row `DRAINED`,
`resolved_at` set, `parked()` empty, `expire_overdue()` empty, while the API answered `PARKED`.

### 5.3 Sibling paths the headline case does not reach

- **strict `VERSION_GAP` after self-release** (on `pipeline_instance`, which is genuinely
  strict-ordered): outcome `PARKED_VERSION_GAP`, row `PARKED`, `resolved_at` NULL, `parked()` finds
  it, expiry reaches it, no effect. The VERSION_GAP sibling of F-05 is genuinely closed, and W32
  reddens this case too.
- **handler raises after self-release**: the exception propagates, the park is **not** stamped, no
  receipt survives, and the event is redelivered and consumed cleanly afterwards — never lost, and
  its park closes only then.
- **an already-EXPIRED park whose prerequisite later arrives**: the event is still consumable and
  consumed exactly once; the row stays `EXPIRED` rather than being rewritten to `DRAINED`. This is
  deliberate and correct — an escalation already handed to a human is not silently retracted, and the
  state is true rather than false. The event is not lost: it carries an `APPLIED` inbox receipt.

**F-05: CLOSED.**

## 6. Preservation of F-01, F-02, F-03

Re-attacked independently, each with a positive control.

**F-01 — refusal evidence keyed on the attempt.** Three DISTINCT hostile `HumanDecided` events
against one `OPEN` Work Item at one unchanged version: each was consumed (`APPLIED`) and classified
`ILLEGAL`, and **three** separate `IllegalTransitionAttempted` records were written. The Work Item's
version and state never moved. Retrying the SAME attempt three times returned `DUPLICATE_NOOP` and
minted no extra evidence. No `DuplicateEmission` escaped; every hostile event carries a receipt, so
the inbox is not poisoned and nothing was left parked. PRESERVED.

**F-02 — ownership cannot be invented.** Eighteen hostile owner candidates were attacked: NULL,
empty, blank, `system`, `SYSTEM`, `Neyma`, `neyma`, `ops-team`, `unassigned`, `model`, `detector`,
`null`, `nobody`, `admin`, `automation`, an unrecorded human, an OFFBOARDED human, and a
foreign-tenant human. **Every one was refused**, the park table stayed EMPTY, and no receipt was
written. Positive control: a recorded ACTIVE human parks normally and the park names that human.
PRESERVED.

**F-03 — the M1 trigger population, re-derived.** The creation/prerequisite split is derived from
§14's `creates` flag, not enumerated: exactly one creation trigger (`WorkItemCreated`), and
`HumanDecided` / `PipelineStarted` / `PipelineClosed` / `ConflictRaised` all require the Work Item to
pre-exist. `WorkItemCreated` does **not** wait for its own product (`APPLIED`, refused as an outcome
`NOT_CONSUMABLE`, no fabricated security record). `HumanDecided` parks on a missing item, converges
under redelivery (`ALREADY_PARKED`, no loop), and **its self-release path still drains correctly** —
`APPLIED` through WI-9, its own semantics, with its park closing exactly then. `PipelineStarted`,
`PipelineClosed` and `ConflictRaised` all park cross-aggregate against the referenced Work Item, with
truthful, owned park rows. **The F-04 cascade change did not break F-03 self-release.** PRESERVED.

## 7. Mutation and the false-green attack

The battery was re-executed by this session: **41/41 caught**.

W31, W31a and W32 were additionally applied by this reviewer against **its own** probes, using an
in-memory save/restore harness (never `git checkout`/`restore`/`stash`/`clean`), with `__pycache__`
purged on both sides and `event_inbox.py` verified byte-for-byte identical after every run:

| Mutant | Recreates | Caught by reviewer probe | Orthogonality |
|---|---|---|---|
| W31 | wrong-handler consumption, fabricated refusal, event loss with a receipt | YES (10 assertions) | leaves F-05 clean |
| W31a | factory consulted with the seeding event | YES (3 assertions) | opt-in path only |
| W32 | API `PARKED` / row `DRAINED`, undiscoverable and unexpirable | YES (F-05 and edge probes) | leaves F-04 clean |

Each mutant restores **only its own** defect, so this is not mutation theatre.

**The new same-store regression is genuinely capable of seeing cross-trigger corruption.** It uses
ONE `make_store`, asserts from `CONTRACTS` that the two members really are the self-aggregate and
cross-aggregate shapes, gives them distinguishable effects, attributes transitions by
`producer_transition_id` scoped to the aggregate, guards its denominators explicitly
(`assert fired`, `assert len(cohort) == 2`), and compares actual enum values
(`is ConsumeOutcome.X`) rather than truthiness. It also delivers a third consumed event
(`WorkItemCreated`) riding on the cohort's referent, because under the defect that seeds the cascade
too. The predecessor sweep gave every trigger a FRESH database, so no two shapes ever shared a
cohort — that is the population shape it structurally could not observe, and it is now covered.

**TEST-NODE-MANIFEST identity:** node set moved 2866 → 2870. Set difference computed directly:
**4 additions, 0 removals, 0 duplicates**, all four new nodes present by exact identity. The guards
compare sets (`missing`/`extra`), so a same-count substitution fails.

## 8. Final gates, reproduced

| Gate | Builder claim | Reproduced by this reviewer |
|---|---|---|
| canonical suite | 2869 passed / 0 failed / 1 justified skip (2870 collected) | **CONFIRMED** — re-ran `scripts/run_canonical_suite.py`: 2869/0/1, exit 0, and `manifest_sha256`, `config_sha256`, `runner_sha256`, `rogue_nodes`, `unexecuted_nodes`, `xfail_nodes` and the skipped-node identity all match the recorded record |
| the one skip | conditional, self-describing | CONFIRMED — `test_the_red_by_design_cases_are_strict_xfails` |
| clean-clone gate | PASS | **CONFIRMED** — re-executed; see §8.1 |
| mutation battery | 41/41 | **CONFIRMED**, plus independent application of W31/W31a/W32 |
| Product Driver | 49/49, 0 wrong | **CONFIRMED** — and it is evidence rather than decoration: under the F-04 mutant it reports **5 wrong behaviours**, naming the wrong-handler consumption, the lost hold, the missing closure, the invented refusal and the transition count |

The composed product narrative was reproduced end to end: a missing Work Item, `HumanDecided` parks,
`PipelineClosed` parks, the Work Item becomes available, each event is processed by its own
semantics, no fabricated refusal, no silent loss — and separately, prerequisite A resolves while B
remains missing, the row stays truthfully `PARKED`, and later B resolves or the TTL expires onto the
accountable human.

The repository's status artifacts were restored byte-for-byte after re-running the gates; the tree is
clean and identical to `HEAD`.

## 9. Findings

### Material blockers

**NONE.** No wrong-event handler execution, no event loss, no false `DRAINED` state, no
undiscoverable or unexpirable park, no duplicate consumption, no ownership loss, no M-26 violation,
no caller semantic drift, no F-01/F-02/F-03 regression, and no false acceptance.

### Nonblocking findings (recorded, not actioned — §13.3)

- **R-01 — the candidate record's prose is stale for this candidate.**
  `IMPLEMENTATION-REGISTRY.yaml` → `units[P6].candidate_awaiting_review.what_is_in_the_tree` still
  describes "186 acceptance and hostile nodes" and "a 32-case mutation battery … at 32/32", which
  described an earlier candidate. The battery is now 41 cases at 41/41 and four regression nodes were
  added. **The error is in the understating direction**, nothing executable asserts either figure
  (verified by grep), and `CURRENT.md` — the status authority — is accurate and machine-maintained.
  Nonblocking: it cannot produce a wrong customer outcome, violate an invariant, or make a later
  phase unsafe.
- **R-02 — `superseded_candidate` records only the first rejection.** It captures `2ed750e` and its
  F-01/F-02 class, but not the later `761fcd7` and `f5af910` rejections that produced F-03 and
  F-04/F-05. Prose-only; the commit chain itself is complete and readable.
- **R-03 — the review that rejected `f5af910` is not preserved.** `refs/preserve` contains
  `p6-cp1-independent-rereview-761fcd7` but has no counterpart for `f5af910`, so the review that
  produced this review's mandate is not in the preserved record. This is a record-keeping gap in the
  process, not a defect in the candidate, and the rejection's content survives in `ca8c070`'s commit
  message. Worth closing before P6 is adjudicated complete, so the candidate's full review lineage is
  reconstructable.

None of R-01/R-02/R-03 is a reason to reject: none can produce a wrong customer outcome, violate an
invariant, or make a later phase unsafe.

## 10. Verdict

**ACCEPT FOR P6-CP-1 ADJUDICATION.**

F-04 and F-05 are closed, mechanically and structurally rather than conditionally. F-01, F-02 and
F-03 remain closed. The amended `DedupInbox` surface — a closed P5 runtime object — was reviewed as
well as M1, and no P5 caller lost, duplicated or misinterpreted an event.

This review adjudicates nothing. P6-CP-1 now owes a **separate targeted adjudication** by a session
that neither implemented, remediated nor reviewed it, and then exactly one finalizer, in that order.
M2 may not begin before that.

---

*Reviewer note on method: every probe in §3–§6 was written by this session against the candidate
tree, and every one was shown to fail under a mutant that restores the corresponding real defect. A
passing check that was never capable of failing is not evidence, and none of the checks reported here
is of that kind.*
