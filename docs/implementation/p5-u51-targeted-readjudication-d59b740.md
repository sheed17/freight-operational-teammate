# P5 U5.1 — SEPARATE TARGETED RE-ADJUDICATION of candidate `d59b740`

Transcribed by the campaign controller from the adjudicator's return. The adjudicator could not
write this file itself. It is a **further session**: it did not build any candidate, did not review
any candidate, and wrote no prior adjudication. It **fixed nothing**. It reproduced every finding
before ruling on it.

## VERDICT: UPHOLD ACCEPT WITH RECORDED RESIDUALS

The reviewer's ACCEPT is upheld. All four findings independently reproduced and confirmed. The
adjudicator **disagrees with the reviewer's reasoning** on Findings 2 and 3 — in Finding 2 the
defect is materially *worse* than reported; in Finding 3 the reviewer both under-credited its own
candidate's guard and gave the wrong mechanical reason for non-blocking. Neither disagreement
reaches the rejection threshold the `38b4bda` / `1ae365a` adjudications applied.

## The deciding test

The prior two candidates were rejected on one fact: **a founder-gated obligation could actually be
discharged with the suite green.**

| Candidate | Exploit | Suite | Obligation |
|---|---|---|---|
| `38b4bda` | AP-9 → `CONSUMES:BrakeReleased` | **GREEN** | discharged 7→6 |
| `1ae365a` | PL-7a → `CONSUMES:EffectExecuted` | **GREEN** (53/0) | discharged 7→6 |
| `d59b740` | PL-7a → `DELEGATES_TO:CHECKPOINT=PL-7b`, **fully coordinated** | **RED** | **NOT discharged; the seven hold** |

The adjudicator built the *complete* coordinated laundering — not the one-token version: spec
Event-cell token, PL-7a moved into `DELEGATES_TO.members` with a resolution block, its
`G2-OB-PL-7A` obligation record deleted, `open_founder_gated_obligations` 7→6,
`computed_classification` updated to DELEGATES_TO 3 / EVENT_REQUIRED 6, and a
`frozen_event_required_set.discharges` entry with route `PRE_EXISTING_STRUCTURAL_PROOF` and a cited
authority. Result:

```
FAILED test_the_event_required_set_is_frozen_by_identity_and_never_by_count
E  AssertionError: three-way set identity broke:
E    computed=['04-approval:AP-9','07-conflict:CF-7','09-exception:EC-7',
E              '11-policy:PO-2','11-policy:PO-3','12-rule:RU-8']
E    Extra items in the right set: '02-pipeline-instance:PL-7a'
```

This is the §I.3 invariant the `1ae365a` re-adjudication mandated, and **it fires**. That is the
difference between a defect and a residual.

## Per-finding rulings

**Finding 1 — CONFIRMED · NON-BLOCKING · agrees with the reviewer.** Reproduced against
`_retired_24_offenders`. Not a regression of F-03: F-03's actual exploit string is now CAUGHT. The
surviving carve-out is a different, sentence-scoped one, positively asserted by the candidate's own
hostile node. It is the already-adjudicated residual R-04 ("UPHELD, NARROWED — non-blocking,
governance-attributable, NOT OWED BY U5.1") and R-05 ("narrowing is optional, not required").

**Finding 2 — CONFIRMED · NON-BLOCKING · disagrees: the defect is worse than reported.** Confirmed
no guard compares anything against the certified parent. Going further, the adjudicator counted
rows carrying `co-commit` declarations:

- at certified parent `6e8127d`: **5** — EF-2, EF-4, PL-8, PL-9, PL-12
- at candidate `d59b740`: **20** — adding EF-3, EF-3f, EF-3u, EF-4c, EF-4u, EF-5, AP-1, CM-5, PL-6, PL-10, PL-10f, PL-10u, PL-11, PL-11c, PL-15

**Fifteen of the twenty reverse legs were authored by the same commit that makes the CONSUMES
claims they justify.** The audit sentence therefore states a property that is false of this unit's
own corpus — an inaccurate statement in an IMPLEMENTATION_CONTROL artifact, the same class of
defect as the F-02 falsehood this unit was required to remediate.

Still non-blocking because: the *operative* clause ("a token it added to its **own** cell") is
mechanically true and verified; the fifteen additions are substantively true architecture filling
real documentation gaps; the audit's own `machine_source_of_truth` truthfully discloses the
addition, so the file contradicts itself rather than concealing; the full exploit runs 9 nodes red;
and enforcing literal pre-existence needs a parent-commit comparison outside §N's authorized
surfaces.

> **RECORDED RESIDUAL R2-A.** The 5a rule text's "PRE-EXISTS the claim" clause is an overclaim and
> **must be corrected** by the next G2-adjacent unit — struck, or restated as "is authored on a
> different row of a different machine", which is what the guard actually proves. Record it with the
> adjudicator's measurement (5→20).

**Finding 3 — CONFIRMED · NON-BLOCKING · disagrees with the reviewer's reasoning in both
directions.** Reproduced exactly; and at the discharge layer under full coordinated laundering,
`_event_required_set_errors` returns `[]` — **the §I.3 discharge machinery IS fooled** — while the
hard anchor (7 vs computed 6) refuses anyway.

Is DELEGATES_TO the same defect as the CONSUMES rejection in a different class? **Decisively not.**
At 38b4bda and 1ae365a the laundering *succeeded* (suite green, obligation gone). Here it *fails*,
on the mandated invariant. At 38b4bda there was **no effective backstop at all**; this is not a
backstop "elsewhere", it is §I.3 set identity doing exactly its mandated job.

The reviewer *under-credited its own candidate* by describing the catch as "audit drift plus two
hard-coded anchors" — the audit-drift node is defeatable, and the adjudicator defeated it; the node
that stops it is the §I.3-mandated invariant.

The reviewer is *mechanically wrong* that closure "needs the `From` state":

| | delegating `From` | targets' `From` |
|---|---|---|
| WI-14 (legitimate) | `ESCALATED` | `IN_PROGRESS`, `{OPEN,IN_PROGRESS}`, … |
| CF-6 (legitimate) | `ESCALATED` | `OPEN` |
| PL-7a (false) | `VALIDATED` | `AWAITING_APPROVAL` |

A From-*difference* rule admits all three; a From-*equality* rule rejects both legitimate rows. The
correct, stronger reason: **no datum in the structured columns separates PL-7a→PL-7b from
WI-14→WI-5.** The only separating datum is the `Guard` column, and *"prose is never a predicate, in
any class"* (§I.2(5)). Closure is genuinely unavailable within U5.1's authorized surfaces.

> **RECORDED RESIDUAL R3-A** (new; neither prior review raised it). `_resolve_delegation` proves
> only *(exists · is a §3 producer · shares the target state)*. It admits a semantically false
> delegation authored entirely in the delegating row's own Event cell, and `_discharge_route_errors`
> re-proves DELEGATES_TO discharges through this predicate — so a false DELEGATES_TO discharge
> record passes the §I.3 discharge machinery.
>
> **RECORDED RESIDUAL R3-B** (new, and why R3-A matters). Because the three-way assertion
> `computed == ADJUDICATED_EVENT_REQUIRED == registered` is **unconditional**, both discharge routes
> (`MINTED_CANONICAL_EVENT`, `PRE_EXISTING_STRUCTURAL_PROOF`) are currently **unreachable dead
> code** — no discharge of any kind can pass. Fail-safe, and stronger than §I.3 required, but the
> discharge machinery has **never been exercised against a real departure**. The first
> founder-authorized unit to discharge one of the seven must amend the hard-coded anchor, and **at
> that moment R3-A becomes load-bearing**. R3-A is owed by that unit, before it amends the anchor.

**Finding 5 — CONFIRMED as a disclosure · NON-BLOCKING · DISCHARGED, not carried.** The adjudicator
did not accept the reviewer's inference; it **produced the missing independent clean-clone
measurement itself**, without running the forbidden `scripts/clean_clone_gate.py`: its own
`git clone` into `/private/tmp`, fresh venv, `pip install -e ".[dev]"`, canonical config.

```
2104 passed, 1 skipped, 5 warnings in 404.97s
SKIPPED [1] eval/tests/test_phase0_guard_integrity.py:109
```

Clone verified at HEAD `d59b740`, tree `a88921c`, 0 dirty entries. `test_status_reality.py -rs` in
the clone: 7 passed, 0 skipped. An independent pre-finalizer clean-clone measurement now exists and
matches the primary-worktree counts exactly.

## Ruling on the controller's worktree cleanup

**LEGITIMATE. THE CANDIDATE IS NOT TAINTED.** Both files untracked at both refs (`git ls-tree`
count 0 at each); removing them changed no committed byte. Tree still `a88921c…`; `git status
--porcelain -uall` empty; reflog head is the content commit — no commit was created. Blobs
byte-identical across both preserve refs, the on-disk copy and the recorded checksum, all four
digests `3a660afe…f6f1`. Same disposition `1ae365a` §L gave F-04. The cleanup also made the
clean-tree-gated `test_status_reality.py` nodes actually **run** rather than skip, strengthening the
evidence base rather than laundering it.

## FINALIZATION RULING: **YES**

`d59b740` is eligible for exactly ONE finalizer-generated metadata commit. The `owed_next` chain is
satisfied. Constraints stated on that commit:

1. Exactly one finalizer-generated metadata commit, first-parent on `d59b740`; no merge commit above
   the content commit; `main` advances fast-forward only, at the push, a separate founder-authorized act.
2. The finalizer runs the gate itself and regenerates `GATE-RESULT.json` (currently stale at `a31a94a`).
3. **No criterion may be scored.** All 14 P5 criteria stay PENDING; `independent_review` and
   `final_adjudication` are structurally un-self-suppliable and are **not** discharged by this
   document — this is the *unit's* re-adjudication, not P5's phase adjudication.
4. The frozen 98, the seven EVENT_REQUIRED obligations, and P5's READY/NOT_STARTED/NO_CHECKPOINT
   triple must be unchanged.
5. Residuals R2-A, R3-A, R3-B must be recorded, R3-A explicitly owned by the first unit that amends
   `ADJUDICATED_EVENT_REQUIRED`.

## Not verified

`clean_clone_gate.py` not run (forbidden), so the clean-clone measurement omits the gate's extra
steps (`check_env.py` floors, config/manifest sha binding, deselect/`-k` sub-runs); no line-by-line
audit of the full 1892-line guard diff; the 9×111 relation matrix not re-run; DELEGATES_TO laundering
not individually attempted on the other six (the blocking mechanism is class- and row-independent);
P4/R-07 not reopened; the finalizer's percentage arithmetic not verified. **No mutation touched the
primary worktree** — all mutation work in `git archive` extracts and a throwaway clone.
