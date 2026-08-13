# P5 U5.2 — SEPARATE TARGETED ADJUDICATION of second replacement `2ccf5e1ff88302703834d68706a7e4b221a43d89`

Transcribed by the campaign controller from the adjudicator's return; it could not write files. It
built nothing, reviewed nothing, wrote no prior adjudication, remediated nothing. Primary worktree at
finish: HEAD `2ccf5e1`, tree `0d8942ac`, 0 dirty entries. All mutation in `git archive` extracts and
throwaway clones under `/private/tmp/u52adj2/`. `finalize_status.py` / `clean_clone_gate.py` never
run.

**### THIS DOCUMENT CARRIES THE UNIT'S RESIDUALS.** PROGRESS-PROTOCOL §10 forbids a second content
commit, so they cannot be written in-tree on this unit. They are recorded here, preserved parented to
the candidate — the device commit `08b4d0d` used for U5.1 — and are owed to the next G2-adjacent
content commit.

## VERDICT: UPHOLD ACCEPT, with recorded residuals — and the reviewer UNDER-accepted in one place it did not see

The ACCEPT is correct. **F-2 is a residual, not a blocker** — but the reviewer under-stated it, and the
adjudicator found the shape that shows why the remedy matters. It also found **A-1**, a record defect
created by this candidate's own R-05 remediation, missed by the builder, the reviewer and the
controller.

## The deciding test, as a single fact

Over **5,880 expressible discharge records** — 7 adjudicated rows × 7 route spellings
(`MINTED_CANONICAL_EVENT`, `PRE_EXISTING_STRUCTURAL_PROOF`, `None`, `FOUNDER_WAIVER`, lower-cased,
leading space, trailing space) × 120 events (the whole 118-name §3 corpus, `""`, and a non-canonical
name) — **with §3 forged to corroborate whatever each record claims and the row reclassified to the
most permissive class**, the set `_event_required_set_errors` admits is:

```
ADMITTED: 7
  02-pipeline-instance:PL-7a  MINTED  AutonomousAdmissionRecorded   0 errors
  04-approval:AP-9            MINTED  ApprovalFrozen                0 errors
  07-conflict:CF-7            MINTED  ConflictPartyAttached         0 errors
  09-exception:EC-7           MINTED  ExceptionSeverityChanged      0 errors
  11-policy:PO-2              MINTED  PolicySubmitted               0 errors
  11-policy:PO-3              MINTED  PolicyApproved                0 errors
  12-rule:RU-8                MINTED  RuleExpired                   0 errors
```

**Exactly `FOUNDER_AUTHORIZED_DISCHARGES`, pair for pair, and nothing else.** The admissible-discharge
set for an adjudicated member *is* the whitelist, measured rather than argued. No prior candidate had
a property of this shape.

## Load-bearing claims re-verified

**7 × 4, built independently:** `MODE LIVE — TOTAL 28 | accepted 0 | refused-by-chokepoint 28`.

**The inversion is real, and reproduces the rejected candidate exactly:**

```
MODE NEUTERED (chokepoint -> lambda: [])   accepted 19 | refused-by-chokepoint 0 | refused-by-other 9
MODE LIVE at a real a6005a8 extract        accepted 19 | refused-by-chokepoint 0 | refused-by-other 9
```

The neutered candidate reproduces `a6005a8` **shape-for-shape and row-for-row** — R-01 on
AP-9/CF-7/EC-7, N-02 on all seven, R-02 on PL-7a/AP-9, MINT on all seven. Causal attribution to the
chokepoint is established, not asserted: neutering one function removes all 28 refusals.

**No bypass.** `dispatcher_calls: 454`, `NON-ADJUDICATED KEYS AT DISPATCHER: []`;
`MINTED_sec3_corpus_FIRED`, `MINTED_sec3_producer_FIRED`, `PESP_NON_PRODUCING`, `PESP_other_class`,
`unknown_route_tail` all **zero**. **`FOUNDER_AUTHORIZED_DISCHARGES` is genuinely unshadowable** —
module-level frozenset in the guard, in no other file; `conftest.py` touches nothing of the sort;
pytest core is the only installed plugin; the only two monkeypatches of guard globals are
function-scoped inside the guard's own nodes.

**Zero false rejects, structurally.** Primary worktree, canonical config, clean tree:
**`2135 passed, 1 skipped in 501.46s`, exit 0** = 2136 = manifest `node_count`. Node delta vs
`a6005a8`: **+9 added, 0 removed**. **Eighth-obligation extension TRUE**, verified independently.

**R-03 fully re-derived** by real conjunct deletion: 250 expressible; both **51**; trigger deleted
**96**; same-machine deleted **157** (cross-machine 106); both deleted **235**;
`ADJUDICATED_DELEGATION_ADMITS` 51 — exactly the guard's figures, un-transposed, and exactly the
commit's `Counter({'AMBIG': 15})`. **R-03 is discharged.**

## Per-finding rulings

**F-1 — CONFIRMED · NONBLOCKING · agrees.** The truth is **19**, measured two independent ways; the
commit's own parenthetical sums to 19. `grep -rI "of 28"` across `docs/` and `eval/` returns nothing:
the figure exists **only in the immutable commit message**. *Ruling: an uncorrectable arithmetic error
in a governance record does not block. The remedy for an immutable record is a correcting record, not
a replacement commit — rebuilding a candidate to fix a commit-message subtraction is the exact
disproportion the topology rules guard against.* This adjudication is that correcting record.

**F-2 — RECORDED RESIDUAL, NOT BLOCKING — and worse than the reviewer said.** Deleting **both** MINTED
§3 corroboration checks and running the whole suite: `4 failed, 2129 passed, 3 skipped`, the four
byte-identical to the control's CLI clone artifacts. **### MISS.**

*Beyond the reviewer — the shape nobody tried.* Every prior MINT laundering also re-pointed the audit
record, which is what the chokepoint catches. **A launderer need not touch the audit at all.** Edit §3
alone, re-attributing the gated row to an existing canonical event, and leave the founder-authorized
discharge record exactly as written: the chokepoint sees an authorized pair and is **silent**. All
seven are then refused only by `claims '<event>' but sec 3 does not declare this row a producer of
it`. End-to-end on the real corpus (§3's F4 line edited so AP-9 produces `ApprovalGranted`, audit
untouched): `laundS 11 failed` = control + 7; with the §3 corroboration deleted, `laundK 9 failed` =
control + 5 — **and the five survivors are all mint-name pins**, the class the commit disclaims twice.

*So the eighth obligation was tested.* With `AP-2` adjudicated, an authorized pair added, an honest
discharge recorded, and no mint-name pin because there is none for a future mint:

```
AS SHIPPED                          refused: claims 'ApprovalGranted' but sec 3 does not declare this row a producer of it
SEC-3 CORROBORATION DELETED         *** LAUNDERED: AP-2 left EVENT_REQUIRED on a sec-3 edit alone, machinery GREEN
```

**The two undisclosed rules are not inert corroboration. They are the sole discharge-path defence
against a real laundering shape, and for a future obligation they will be the sole defence full
stop — and no node asserts either of them.**

*Ruling: RESIDUAL, on this campaign's own drawn lines rather than on comfort.* (1) The `f01d942`
adjudication rejected F-05 in the words *"overstated, not merely incomplete"*; here every statement
the commit makes is **true** — fifteen mutations run, fourteen caught (the adjudicator reproduced
**all fourteen**, including the §5 `PolicyApproved` strike the reviewer left open: `mutPA 6 failed` =
control + 2), one missed and named, the three PESP branches correctly identified as uncatchable. What
is absent is a fourth and fifth entry. That is incompleteness. (2) F-04 blocked because a guard
*reported work it did not do*; nothing here is vacuous — the §3 checks are **correct**, merely
**un-asserted**, and the `a6005a8` adjudication itself drew this line: *"a wrong comment beside a
right assertion is a documentation defect; a vacuous assertion beside a docstring claiming a proof is
a false guard."* (3) **Every prior record-accuracy finding in this sub-unit was ruled a residual** —
R-03, R-05, and `d59b740`'s Finding 2 (R2-A). What blocked, every single time, was a **live laundering
route**; there is none here. (4) The exposure is conditional on a future adjudicated act which will
itself be reviewed — the structure `d59b740` used for R3-A. (5) A third replacement would put a
proven-sound chokepoint back on the table for re-editing, against a remedy of one node and one
sentence.

**F-3 — CONFIRMED exactly · NONBLOCKING.** Deleting the *requirement* (not the datum):
`mutF3 4 failed` = control. **### MISS.** The datum is caught (4 nodes); the assertion is not held.
The commit's *"IS live and is caught (M12)"* reads as mutation-proven and is not.

**F-4 — CONFIRMED exactly · NONBLOCKING.** `mutF4a` (never-in-frozen-set) MISS; `mutF4b`
(discharged-and-no-longer-classified) MISS; `mutF4c` (`DISCHARGE_ROUTES`) CAUGHT by 1; `mutM8` MISS.
For `mutF4b` and `mutM8` the determination rests on the two-file subset, argued to be the complete
observable population; their whole-suite runs were terminated at 67% under contention. In both F-4
cases the laundering was confirmed to fail closed on a neighbouring rule.

**F-5 — CONFIRMED · NONBLOCKING.** The registry count is **12**, not 13. Repo-wide `G2-D15` ×10,
`G2-D16` ×11, both previously zero, no collision.

**A-1 — NEW · NONBLOCKING · missed by the builder, the reviewer AND the controller.** Guard
`:1133-1134` reads *"the audit's own note records that `PRE_EXISTING_STRUCTURAL_PROOF` 'remains
available and unused'"*. `grep -c "remains available and unused"
docs/implementation/TRANSITION-EVENT-AUDIT.yaml` → **0**. **This candidate's own R-05 remediation
deleted that sentence**, replacing it with *"UNAVAILABLE to these seven rather than merely unused"*.
The guard now carries a **direct quotation attributed to a document that does not contain it** — a
citation the `a6005a8` controller had independently verified at audit `:782` and which this commit
silently invalidated while correctly claiming to have fixed the surrounding comment. The underlying
argument survives and was verified. Same disposition as R-03 and R-05.

## Did the reviewer over-accept? NO — it UNDER-accepted twice

Every "what held" claim re-cut and true: the 454-call instrumentation, the dead-code branch counters,
the eighth-obligation extension, the 19-not-21 measurement, the duplicate-discharge observation in
both orders (forged-first green at the set node by last-wins, red at the agreement node; it buys the
launderer nothing). `FOUNDER_AUTHORIZED_DISCHARGES` unshadowable. Thirteen of fourteen mutation
reproductions correct, and the fourteenth closed here. **No over-acceptance anywhere.** It
under-accepted twice: it missed the sec-3-only laundering shape — and so described F-2's remedy as
"one hostile node and one sentence" without knowing that node is the only thing standing between a
future eighth obligation and a green laundering — and it missed A-1, created by the very remediation
it was auditing.

## FINALIZATION RULING: YES

`2ccf5e1` is eligible for exactly ONE finalizer-generated metadata commit.

1. **Exactly one finalizer-generated metadata commit, first-parent on `2ccf5e1`.** No merge commit
   above the content commit; `main` advances **fast-forward only**, at the push, a separate
   founder-authorized act (PROGRESS-PROTOCOL §10, R-21).
2. **The finalizer runs the gate itself** and regenerates `GATE-RESULT.json`. **No clean-clone
   measurement exists from the builder, the reviewer or the adjudicator** — the "clone" runs are
   `git clone` + pytest and omit the gate's `check_env.py` floors, config/manifest sha binding and
   deselect sub-runs.
3. **No criterion may be scored.** All **14** P5 criteria stay `PENDING`
   (`Counter({'PENDING': 14})`); P5 stays `READY / NOT_STARTED / NO_CHECKPOINT`. `independent_review`
   and `final_adjudication` are structurally un-self-suppliable and are **not** discharged by this
   document — this is the *unit's* adjudication, not P5's phase adjudication.
4. **Must stay unchanged.** The chokepoint and the order of its call site; `FOUNDER_AUTHORIZED_
   DISCHARGES` and the both-directions agreement node; `ADJUDICATED_EVENT_REQUIRED`; the nine new
   nodes and the manifest at 2136; the mint — 105, `117/9/6/2/0 = 134`, digest `1485bd6f0f6dd02b`;
   `src/` and `PROGRAM-WEIGHTS.yaml` byte-unchanged vs `eda3a6d`; R-07 CONTAINED; P4 COMPLETE; the
   Phase-8 deferral; GateRegistry EMPTY. **N-01's bar, the CONSUMES and DELEGATES_TO branches and the
   two §3 corroboration checks are KEPT** — the last two are load-bearing, as proven.
5. **Residuals go here, not in-tree**, preserved parented to `2ccf5e1`.

| id | residual | owed by |
|---|---|---|
| **A-2 (F-2)** | five uncatchable discharge-path rules, three enumerated; the two MINTED §3 checks are the sole defence against sec-3-only re-attribution and are asserted by no node. Owes (i) one hostile node asserting the §3 producer refusal — the string occurs once in the repository, in the implementation — and (ii) correction of the enumeration in guard `:1229-1239`, registry `:1702-1712` and the commit-equivalent record | **the first unit that amends `ADJUDICATED_EVENT_REQUIRED` or `FOUNDER_AUTHORIZED_DISCHARGES`, BEFORE it amends either** |
| **A-1** | guard `:1133-1134` quotes the audit as saying "remains available and unused"; the audit contains it zero times | next G2-adjacent unit |
| **F-1** | commit message states `21 of 28`; the truth is `19`, twice measured; no in-tree counterpart | corrected by this record; nothing further owed |
| **F-3** | the registered-`durable_write` **requirement** is a MISS; only the datum is caught | next G2-adjacent unit, with A-2 |
| **F-4** | two caller-side rules each a MISS | next G2-adjacent unit, with A-2 |
| **F-5** | "the registry (13 sites)"; the count is 12 | next G2-adjacent unit |

Carried forward unchanged: **R-02** (delegation remains a necessary-conditions filter for the 127
non-adjudicated rows), **G2-D15**, **G2-D16**, **G2-D4/D6/D8/D9/D10**, and the
**PL-11c → OutcomeUnknown** residual.

**Topology** — Option A, verified: sole parent `eda3a6d`, a sibling of both `f01d942` and `a6005a8`
and a descendant of neither. All five cited preserve refs resolve to the stated hashes.

## What the adjudicator did NOT verify

The seven minted payloads, schemas, §3/§5/family contracts and envelope — upheld by two prior
adjudications, byte-identical, **not re-derived**; only presence, the classification and the digest's
presence were computed. `_consumes_relationship_errors` and `_resolve_delegation` as classification
predicates over the other 127 rows — the delegation predicate swept only for R-03's figures; the
CONSUMES relation matrix, `ADJUDICATED_UNDECLARED_ACCEPTS` and the carried `PL-11c → OutcomeUnknown`
residual **not re-cut**. The whole-suite runs for `mutF4b` and `mutM8` were terminated at 67% under
contention; their determination rests on the two-file subset, argued but not proven by exhaustion.
**No clean-clone measurement.** The four CLI failures confirmed as clone artifacts but not diagnosed.
The renumbering's reach beyond the census. Documents outside `docs/`/`eval/`/`src/` beyond four root
files; `PROGRAM-WEIGHTS.yaml` content (only that it is byte-untouched); prose beyond the `98→105` and
`110/24 → 117/17` substitutions. The finalizer's percentage arithmetic. Whether D1/D2/D3 were actually
made — **nothing in a repository can establish that**. No runtime behaviour; none exists.

## CONTROLLER'S INDEPENDENT REPRODUCTION

Both new findings confirmed on the primary worktree at `2ccf5e1` before finalization:

- **A-1** — `remains available and unused` occurs **0** times in
  `docs/implementation/TRANSITION-EVENT-AUDIT.yaml` and **1** time in
  `eval/tests/test_bootstrap_hermeticity.py`, where it is presented as a quotation from the audit.
- **F-2** — `sec 3 does not declare this row a producer of it` occurs exactly **once** in
  `eval/tests/`, in the implementation itself, asserted by no node.
