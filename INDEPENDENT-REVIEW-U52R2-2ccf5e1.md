# P5 U5.2 — FRESH INDEPENDENT REVIEW of second replacement `2ccf5e1ff88302703834d68706a7e4b221a43d89`

Transcribed by the campaign controller from the reviewer's return; it could not write files. It built
nothing, reviewed nothing prior, adjudicated nothing, remediated nothing. Primary worktree at finish:
0 lines dirty, HEAD `2ccf5e1ff883`, tree `0d8942ac903a`. All mutation in `git archive` extracts and
throwaway clones under `/private/tmp/u52rev3/`. `finalize_status.py` / `clean_clone_gate.py` never
run.

## VERDICT: ACCEPT WITH NONBLOCKING FINDINGS

**The decisive question is closed, for the first time in five candidates.** The reviewer built the
four laundering shapes itself, plus fourteen shapes nobody has tried, and drove every one through the
real `_event_required_set_errors`. **28 of 28 refused, every one by the chokepoint**, and the refusal
is provably the chokepoint's rather than a mint-name literal, a count literal or a fixture premise —
because neutering the chokepoint *alone* puts 19 of the 28 straight back through.

Four findings, all NONBLOCKING, all record/coverage rather than mechanism.

## WHAT WAS ATTACKED AND HELD

**7 rows × 4 shapes, built independently** (the harness constructs R-01, N-02, R-02 and MINT from the
live corpus; it does not call the guard's own `_laundering` helper):

```
TOTAL 28 | accepted 0 | refused-by-chokepoint 28      (every one carries CHOKEPOINT_MARK)
```

**Refusal attributed by inversion** — same harness, `_adjudicated_discharge_authorization_errors`
replaced by `lambda key, entry: []`, nothing else touched:

```
TOTAL 28 | accepted 19 | refused-by-chokepoint 0
```

**Eighteen attacks on the chokepoint itself, all HELD:** lower-cased route; route with trailing space;
`transition` key with trailing space to alias the frozenset; `event` as a list; `event` as a dict;
`route` as a list; duplicate discharges unauthorized-first (green at the set node by last-wins, but
caught by the table/record agreement node, which sees an 8th pair); duplicates authorized-first; the
AP-9 row deleted from the corpus with its authorized discharge kept; MINTED naming another row's
event; **AP-9 MINTED on PO-3's authorized event `PolicyApproved` — refused, the table is read as
PAIRS, not names**; audit `members: []` and `discharges: []`; the `discharges` key removed entirely.

**No bypass exists.** Repo-wide grep: `_discharge_route_errors`, `_event_required_set_errors`,
`_adjudicated_discharge_authorization_errors` and `FOUNDER_AUTHORIZED_DISCHARGES` appear in **no file
other than** the guard. The single caller is the loop over `ADJUDICATED_EVENT_REQUIRED`. Instrumented:
**454 dispatcher calls, 0 with a non-adjudicated key.** `ADJUDICATED_EVENT_REQUIRED` is a guard
literal bound to the audit in both directions; the only early return in `_event_required_set_errors`
is the missing-record path, which returns an error. Fails closed.

**The eighth-obligation claim is TRUE, verified empirically.** Adding `04-approval:AP-2` to the frozen
set with a MINTED discharge on `ApprovalGranted` — an event it *genuinely produces* in §3 — is
refused: `NO FOUNDER AUTHORIZATION EXISTS FOR THE MINTED DISCHARGE 'ApprovalGranted'`. Default-deny
extends automatically. This is the property every prior arrangement lacked.

**The dead-code disclosure is TRUE.** Branch-counter instrumentation over the whole guard:

```
{'dispatcher_calls': 454, 'MINTED_branch': 400, 'PESP_branch': 21,
 'PESP_CONSUMES': 14, 'PESP_DELEGATES_TO': 7}
```

`PESP_NON_PRODUCING`, `PESP_other_class` and `unknown_route_tail` are **zero**. The 21 PESP hits come
entirely from the hostile battery's *neutered* half. Confirmed by mutation: M8 MISS, CONSUMES-branch
MISS, DELEGATES_TO-branch MISS. Keeping them is correct — the adjudication ordered it — and the
unreachability is stated in all three claimed places: guard `:1227-1239`, audit `:817`, registry
`:1702-1705`.

**Zero false rejects.** `_event_required_set_errors(unlaundered)` → `[]`; all seven recorded
discharges are `MINTED_CANONICAL_EVENT` and exactly equal the authorization table. Full canonical
suite on the clean primary worktree: **2135 passed, 1 skipped in 392.33s** = 2136 = the manifest
`node_count`. Control clone `4 failed, 2131 passed, 1 skipped`, the four being the known CLI clone
artifacts. The commit's `2133 / 3` is its own dirty-tree case; totals reconcile at 2136 both ways.

**R-03 re-derived** by deleting each conjunct from the real predicate: 250 expressible; both **51**
(refusals MACH 106 / TRIG 78 / AMBIG 15); trigger deleted **96**; same-machine deleted **157**
(cross-machine 106); both deleted **235**. `ADJUDICATED_DELEGATION_ADMITS` size 51. Guard `:407-410`,
`:419`, `:501`, `:629-632`, `:2398` all correct and **un-transposed**, each label checked against the
measurement. The only surviving `250/167/102/53` strings are explicitly labelled as the rejected
candidate's figures. The audit's `G2-D16 held_by` second instance is corrected.

**Renumbering complete, no collision.** Census across all `.py`/`.yaml`/`.md`: `G2-D15` ×10,
`G2-D16` ×11, both previously zero; every surviving `G2-D11`/`G2-D12` is either the closed defect or
an explicit renumbering note. **R-05** is now true of the implementation in both clauses, and the
`discharges:` comment no longer says "remains available and unused". **R-06**: 12 assertions marked
`FIXTURE PREMISE` under a comment forbidding their use as defences. **Node delta** vs `a6005a8`:
exactly **+9 added, 0 removed**, matching the claim.

**Mutation log: 13 of 14 CAUGHT claims reproduced to the exact node count** — chokepoint call deleted
9; structural proof admitted 9; MINTED without table 8; default-deny tail 1; key-only match 8;
unauthorized pair added 3; authorized pair removed 3; `frozenset()` key 8; refusal ignored 8; trigger
conjunct 2; same-machine conjunct 1; CF-7 discharge re-pointed 5; AP-9 `durable_write` emptied 4; M8
MISS. Not reproduced: the §5 `PolicyApproved` strike.

**The mint is undamaged.** 117/9/6/2/0 = 134; `canonical_events_F1_F13: 105`; digest
`1485bd6f0f6dd02b`. `git diff eda3a6d 2ccf5e1 -- src/` **empty**; `PROGRAM-WEIGHTS.yaml` empty diff.
R2-A, R4-A, ER-16, PO-1's `PolicyProposed` intact. R-07 CONTAINED, P4 COMPLETE, Phase-8 deferral,
GateRegistry EMPTY. P5 **READY / NOT_STARTED / NO_CHECKPOINT**, all **14** criteria PENDING.

## FINDINGS (all NONBLOCKING)

**F-1 — the DECIDING EVIDENCE baseline is wrong: 19, not 21.** The commit states "at a6005a8 **21 of
28 ACCEPTED**" while its own parenthetical sums to 3+7+2+7 = **19**. Measured two independent ways
against a real `a6005a8` extract — the reviewer's own construction (`accepted 19`) and **the
candidate's own `_laundering` fixture transplanted onto `a6005a8`'s module globals**
(`accepted=19 refused=9`). The nine refused are PL-7a/R-01 and, for CF-7·EC-7·PO-2·PO-3·RU-8, the
shapes their own row text refuses. The substantive claim — the defect existed on all seven and is now
closed — is unaffected. The figure appears **only in the commit message**, nowhere in-tree.

**F-2 — "ONE HONEST MISS" is not one: the §3 corroboration is also unfalsifiable, and is not
disclosed.** Both MINTED §3 checks are unfalsifiable by the entire suite:

```
M-A*  delete MINTED sec-3 CORPUS check      ### MISS ###
M-B*  delete MINTED sec-3 PRODUCER check    ### MISS ###
M-AB* delete BOTH                            ### MISS ###
```

Branch counters corroborate: `MINTED_sec3_corpus_FIRED` and `MINTED_sec3_producer_FIRED` are **zero
across the whole guard**, because every forged-mint node is refused earlier by the chokepoint. **This
is not a hole** — the corroboration is load-bearing against a real shape, proven: deleting
`ApprovalFrozen` from AP-9's §3 producer set yields *"claims 'ApprovalFrozen' but sec 3 does not
declare this row a producer of it"*, and deleting it from the corpus yields the corresponding corpus
error. But it is an uncatchable rule of exactly the class the commit undertook to enumerate: the
accurate statement is **four** uncatchable rules on the discharge path, and the disclosure names
three. The remedy is one hostile node and one sentence.

**F-3 — "the registered-`durable_write` requirement IS live and is caught (M12)" is imprecise.** Two
different things are true: the **datum** is caught (emptying AP-9's registered `durable_write` fails
4 nodes), but the **assertion** is not held — removing the requirement itself is a MISS. It is
redundant defence in depth, not an independently load-bearing check, and the sentence reads as
"mutation-proven".

**F-4 — three further caller-side rules are individually uncatchable** (`discharge names X never in
frozen set`, `discharged and no longer classified`, each MISS), though in both cases the laundering
was verified to fail closed on a neighbouring rule. For contrast, the `DISCHARGE_ROUTES` check and the
silent-departure check are each CAUGHT by 1.

**F-5 — trivial count.** The commit says the renumbering touched "the registry (13 sites)"; the count
is **12**. Immaterial.

## RECOMMENDATION

**ACCEPT.** The chokepoint is the right mechanism, installed where the adjudication ordered,
default-deny, reading only the route string and the event name, with one caller and no bypass found
across eighteen attack shapes, extending to an eighth obligation automatically. The zero-false-reject
property is structural, not lucky. Thirteen of fourteen mutation-log entries reproduce to the node
count.

The four nonblocking findings are all in the *record*, not the mechanism. Given this campaign's
standard — that a guard or record stating something other than what it does is itself the defect —
**F-2 in particular should be folded into any follow-on record**, since the commit's credibility rests
specifically on having enumerated its own misses honestly, and it enumerated three of four.

## WHAT WAS NOT VERIFIED

The §5 `PolicyApproved` mutation. The seven minted payloads, schemas, §3/§5/family contracts and
envelope — upheld by two prior adjudications, byte-identical, **not re-derived**; only presence,
`PolicyProposed`'s ownership and the 105/117/9/6/2/0/digest figures were computed.
`_consumes_relationship_errors` and `_resolve_delegation` as classification predicates over the other
127 rows — the delegation predicate was swept for R-03's figures only; the CONSUMES relation matrix,
`ADJUDICATED_UNDECLARED_ACCEPTS` and the carried `PL-11c → OutcomeUnknown` residual were not re-cut.
The renumbering's downstream reach beyond the census. **No clean-clone measurement** — the gate was not
run; "clone" runs are `git clone` + pytest. Documents outside `docs/`/`eval/`/`src/`;
`PROGRAM-WEIGHTS.yaml` content (only that it is byte-untouched); prose edits beyond the 98→105
substitutions. Whether the founder decisions D1/D2 were actually made — nothing in a repository can
establish that. No runtime behaviour (none exists). The four CLI clone-artifact failures were
confirmed present in the unmutated control and absent in the primary worktree, but not diagnosed.

## CONTROLLER'S INDEPENDENT REPRODUCTION

Confirmed F-2's core claim on the primary worktree at `2ccf5e1`: the string
`"sec 3 does not declare this row a producer of it"` occurs **once** in
`eval/tests/test_bootstrap_hermeticity.py` — in the implementation itself — and **zero** times in
`eval/tests/test_p5_canonical_event_mint.py`, so no node asserts that refusal. The chokepoint's
MINTED branch returns its authorization error before the §3 corroboration is reached for any forged
pair, which is why the corroboration cannot be exercised by the current battery.
