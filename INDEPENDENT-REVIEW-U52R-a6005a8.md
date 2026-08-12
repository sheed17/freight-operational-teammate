# P5 U5.2 — FRESH INDEPENDENT REVIEW of replacement candidate `a6005a81e234956bb837c0bdc9d3b6cd4febfc53`

Transcribed by the campaign controller from the reviewer's return; it could not write files. It built
nothing, reviewed nothing, adjudicated nothing, remediated nothing. Primary worktree at finish:
`git status --porcelain -uall` 0 lines, HEAD `a6005a81`, tree `9021fff2`. All mutation work in
`git archive` extracts and throwaway clones under `/private/tmp/u52rev/`. `finalize_status.py` and
`clean_clone_gate.py` never run.

## VERDICT: REJECT — TARGETED REMEDIATION REQUIRED

On the decisive question, unchanged from three prior rejections. **A founder-gated obligation can
still be discharged through a semantically false route with the general machinery green** — not
through the two routes the builder hardened, but through the third it did not:
`PRE_EXISTING_STRUCTURAL_PROOF` + `CONSUMES`. The exploit is `CONSUMES:BrakeReleased`, literally the
exploit that rejected `38b4bda`, landing on CF-7 and EC-7 with **all thirteen delegation/discharge
nodes passing** and, on a full clean-clone suite run, **not one general guard red**.

Everything else in the remediation is real and holds. Items (1)–(7) each do what the commit says;
N-01 is genuinely closed and survived four separate bypasses; the mint, counts, digest, R2-A, R4-A
and every forbidden surface are intact. The rejection is on one thing.

## BLOCKING

### R-01 — N-01's own rule is not applied to the CONSUMES route. A two-cell edit discharges AP-9, CF-7 or EC-7 with the whole layer green.

`_discharge_route_errors` (`test_bootstrap_hermeticity.py:1114`) routes a
`PRE_EXISTING_STRUCTURAL_PROOF` discharge of a CONSUMES-classified row into
`_consumes_relationship_errors`, whose first act is `durable = _durable_write(row, states)` followed
by `if not durable: continue  # rule 3 — GR-2 does not bind`. That is a re-reading of the row's own
`Writes` cell — **the cell the discharging edit is free to empty**. With it empty, every relational
conjunct (4b mutual exclusion, 4c cross-machine, 5a bidirectional row-bound co-commit, 5d replay
coverage) is skipped and the function returns `[]`. An empty list is an accepted discharge.

This is character-for-character the defect N-01 was created for, one route along. The adjudication
stated the rule generally — *"a discharge may never be admitted on a re-reading of a cell the
discharging edit is itself permitted to change"* — and the candidate applied it to `NON_PRODUCING`
only. Rule 4's text ("the marker is DESCRIPTIVE and carries NO EXEMPTING FORCE") was written as a
**classification** rule; used as a **discharge** predicate it inverts into "carries full exempting
force".

The three rows that fall are exactly the N-01 three — those whose durable write is a field write:

```
04-approval:AP-9    Writes emptied -> durable=False  CONSUMES:BrakeReleased errors=NONE  *** ACCEPTED ***
07-conflict:CF-7    Writes emptied -> durable=False  CONSUMES:BrakeReleased errors=NONE  *** ACCEPTED ***
09-exception:EC-7   Writes emptied -> durable=False  CONSUMES:BrakeReleased errors=NONE  *** ACCEPTED ***
02-pipeline:PL-7a / 11-policy:PO-2 / PO-3 / 12-rule:RU-8   durable=True -> refused (2 errors each)

registered durable_write the guard declines to consult on this route:
   AP-9 'frozen=true'   CF-7 'append parties[]'   EC-7 'severity'
```

Control, identical row state, NON_PRODUCING route: `### 04-approval:AP-9: NON_PRODUCING IS NOT AN
AVAILABLE DISCHARGE ROUTE FOR AN ADJUDICATED FOUNDER-GATED ROW…`. AP-9 is caught, but only by two
AP-9-name-pinned regression nodes inherited from U5.1. **CF-7 and EC-7 have no such node.**

Fully coordinated CF-7 laundering, six specification/audit files, **no guard file touched**: the
CF-7 row's `Writes` → `—` and `Event` → `` `CONSUMES:BrakeReleased` ``; the §3 entry, the family
contract row, the §5 payload row and `canonical_expected.yaml` entry all dropped; and in
`TRANSITION-EVENT-AUDIT.yaml` the counts moved to 104 / PRODUCER 116 / CONSUMES 10 / producer 116 /
non-producer 18, CF-7 added to `classes[CONSUMES].members` with `owner: [BR-4]`,
`owner_machine: [M13]`, `durable_write: false`, and `discharged_members`,
`frozen_event_required_set.discharges` and the `G2-OB-CF-7-…` register entry all re-pointed to
`event: BrakeReleased`, `route: PRE_EXISTING_STRUCTURAL_PROOF`.

```
classifier errors: []
_event_required_set_errors: NONE   *** the founder-gated set is 'intact' ***
EVENT_REQUIRED computed: set()

the 13-node delegation/discharge layer:   13 passed, 5 warnings in 0.51s
```

Full canonical suite, pristine clone at `a6005a8` with only those six files changed:

```
19 failed, 2105 passed, 3 skipped in 384.07s
```

Four of the nineteen are CLI clone artifacts that fail identically on a pristine unlaundered clone
(`4 failed` control). **All fifteen remaining are literal counts or names written for this specific
mint** — 10 `MINTED_2026_08_12` name literals, 3 acceptance-bijection count literals, and the
104-vs-105 / 116-vs-117 assertions. Green throughout:
`test_the_event_required_set_is_frozen_by_identity_and_never_by_count`,
`test_the_founder_gated_event_obligations_are_explicit_and_cannot_be_silently_discharged`,
`test_every_durable_write_is_recorded_by_an_event_or_a_registered_open_obligation`,
`test_consuming_rows_prove_an_authoritative_co_transition_relationship`,
`test_the_relation_matrix_over_every_consumer_and_every_canonical_event_is_exact`,
`test_the_delegation_predicate_is_swept_over_the_whole_corpus_and_its_admitted_set_is_exact`,
`test_hostile_an_open_obligation_may_not_annex_another_rows_co_commit_declaration`,
`test_non_producing_rows_are_structurally_declared_and_perform_zero_durable_writes`,
`test_the_producer_map_and_the_transition_corpus_are_bijective`.

That is the `f01d942` condition verbatim.

**Not inherited from the certified predecessor.** At `d59b740` the machinery existed but the frozen-
set assertion was unconditional, so no discharge of any kind could land and the CONSUMES route was
dead code. R3-B opened the route; the adjudication ruled its *direction* correct and did not measure
this consequence, and the prior reviewer's negative battery tested CONSUMES laundering only with the
row's `Writes` cell **intact**.

**Aggravating.** `TRANSITION-EVENT-AUDIT.yaml:771` (`authorized_discharge_routes`) already states the
correct rule: `PRE_EXISTING_STRUCTURAL_PROOF` requires *"for CONSUMES … consumes_valid rules
1,2,3,5a–5d and 7 in full, with the 5a REVERSE leg row-bound."* Rules 5a–5d are not applied at all
when the row's own `Writes` cell is empty. The recorded authorization and the implemented predicate
diverge, and the divergence is the hole.

**Minimal remediation direction** (stated for the adjudicator, not applied): apply N-01's own rule to
the CONSUMES branch — for a member of `ADJUDICATED_EVENT_REQUIRED` the register's `durable_write` is
authoritative, so rule 4's non-binding short-circuit is unavailable and 5a–5d must be proven in full.

## NONBLOCKING

**R-02 — a second, undisclosed single point of failure on the DELEGATES_TO route.**
`_resolve_delegation`'s conjuncts read the delegating row's `Trig` cell — the same row, same table,
same file as the `Event` cell the launderer is already editing. Widening it defeats the trigger
conjunct outright. `AP-9 → DELEGATES_TO:GRANTED=AP-2` plus `Trig S → S\|H`: the whole discharge
machinery accepts *"M4's approval freeze is recorded by `ApprovalGranted`"*; the frozen-set node,
the resolution node, the obligation node, the durable-write node and the annex node all pass.
**Nonblocking** because the corpus sweep refuses twice independently, the second assertion being a
general corpus-wide property keyed on `ADJUDICATED_EVENT_REQUIRED` — the governance anchor the U5.1
re-adjudication mandated, not this mint's names — so the laundering does run RED on a general guard,
which is the `d59b740` standard. But it is the same self-certification shape as N-01, needs **no
guard mutation at all**, and the commit message discloses only one single point (M1 + RU-8→PO-7).

**R-03 — the guard file states false measurements of its own predicate, three times, with the two
conjuncts swapped.** Real figures, by deleting each conjunct from the real function and sweeping all
250 triples: both conjuncts **51** admits / 0 adj7 / 0 cross-machine; trigger deleted **96** / 2 / 0;
same-machine deleted **157** / 9 / 106; both deleted **235** / 13 / 139. Against the tree:
`:398-400` cites 167 / 102 / 53 (the adjudication's re-implementation figures, presented without
attribution as measurements of this predicate); `:406` says "THE 53 SURVIVORS … asserted EXACTLY by
`ADJUDICATED_DELEGATION_ADMITS`" which holds **51**; `:488` says 53 in the predicate's own docstring;
`:617-618` and `:2212` have trigger-deleted and same-machine-deleted **transposed**. The commit
message discloses the 51-vs-53 discrepancy honestly and the audit and registry all correctly say 51 —
the stale figures are confined to the guard file, which is precisely where F-04 established that a
guard reporting something other than what it does blocks on its own. Documentary, not mechanical.

**R-04 — the two new residuals collide with existing G2 identifiers.** `G2-D11` and `G2-D12` are
already taken in the same namespace for different, closed defects (`G2-D11` the producer-map
bijection, `G2-D12` the retired 121/13 split), still live in guard comments at `:218`, `:220`,
`:1336`, `:1815`, `:1978` and in the audit at `:21`, `:312`. `G2-D13`/`G2-D14` are also taken; the
next free ids are `G2-D15`/`G2-D16`. The collision now propagates to `BUILD-STATUS.yaml:46` and
`CURRENT.md:546`.

**R-05 — ruling on the schema inconsistency the builder flagged: yes, it needs a recorded residual.**
`authorized_discharge_routes` advertises `NON_PRODUCING` as a sub-route of
`PRE_EXISTING_STRUCTURAL_PROOF`. N-01 makes it structurally unreachable for every row that record
governs, and the register guard separately requires a canonical `discharging_event` a NON_PRODUCING
discharge cannot truthfully supply. The record advertises a route that is unavailable and, if
available, unsatisfiable — a live false claim in a control record, the F-02 failure mode. "Moot" is
not "true". The same sentence's CONSUMES clause is false in the other direction (R-01).

**R-06 — fixture-premise assertions read as defences.** Four nodes carry premise assertions that fire
on any edit to AP-9 or PL-7a and can be miscounted as rule guards. The commit message correctly
discounts this class for `f01d942`; some of its own `remediated: N failed` counts include members of
it.

## WHAT WAS ATTACKED AND HELD

**N-01 is genuinely closed and survived four bypasses**, each fully coordinated: two-cell laundering
on all three field-write rows (each RED on the discharge machinery itself); emptying the register's
`durable_write` (two independent errors); deleting the register entry outright with `meta` counts
coordinated (fail-closed, "the register may not shrink"); and register shadowing with a duplicate
`04-approval:AP-9` key carrying `durable_write: ""` (caught twice).

**The plain delegation launderings run red on general guards, as claimed.** `RU-8 → EXPIRED=PO-7`
fully coordinated fails the frozen-set node with `claims a DELEGATES_TO proof that does not resolve:
EXPIRED: delegation target PO-7 is CROSS-MACHINE…`, plus the resolution node, the sweep and the annex
node. Same for `PO-3 → APPROVED=CM-2`.

**All thirteen adj7-sourced expressible routes are refused and both conjuncts are load-bearing.**
PL-7a has one expressible target (refused on trigger); AP-9 four (AP-2 on trigger, EF-1/EF-2f/PL-8 on
machine); CF-7 and EC-7 none; PO-2 four, PO-3 one, RU-8 three, all on machine. Deleting trigger
readmits PL-7a→PL-7b and AP-9→AP-2; deleting same-machine readmits the other nine.

**No over-rejection.** All seven declared branches resolve. All four fail-closed branches present and
positional; the sweep separately asserts no corpus row is undecidable on either.

**The sweep drives the real predicate and the pinned set is correct.** An independent five-conjunct
re-implementation reproduces `ADJUDICATED_DELEGATION_ADMITS` exactly — 51 members, zero either way.
Deleting either conjunct turns the sweep red. The exact-set assertion is genuinely two-directional.

**Item (4) is real** — planting `_ = ADJUDICATED_EVENT_REQUIRED` inside `_resolve_delegation` turns
the AST-scan node red; the `monkeypatch.setattr` is real and carries a took-effect check.
**Item (5) is real** — striking `PolicyApproved` from the list line: `2 failed` against `f01d942`'s
zero; the amendment note cannot rescue it; an undecidable list also fails closed.
**Item (7)/F-07** — deleting ER-16's parenthetical: `1 failed`; deleting the §8 bullet: `1 failed`.

**The builder's three reported MISSes are honest**, each `76 passed` on the clean corpus, and two are
load-bearing under laundering: M6 + the CF-7 NON_PRODUCING laundering leaves the whole discharge layer
green (the N-01 bar is the sole defence, exactly as stated); M17 is defence-in-depth in both
directions. M4 is judged genuinely unreachable — making a machine undecidable renames every row key
on that machine and breaks the frozen anchor. **The disclosed single point is real and correctly
described** (M1 + RU-8→PO-7: only the sweep is a general guard).

**51 is right**, both by independent parser and by deleting conjuncts from the real function; the
adjudication's 53/167/102 are re-implementation artifacts.

**Re-attribution routes are closed.** Cross-machine re-attribution is caught by a genuine general
guard (`non-coordination event(s) whose producers span more than one machine`). Same-machine
re-attribution evades every count and general guard but is caught by `MINTED_2026_08_12` — ruled a
**correct** defence rather than a name-literal accident, because the MINTED route's premise *is*
founder authorization over seven specific (row, event) pairs, and an authorization list is the only
faithful mechanization of it. No residual.

**Item 8a** — the pre-existing partial defence is real: blanking a DISCHARGED obligation's
`discharging_event` is refused, so a launderer must supply a cover name to reach the route predicate.

**Item 9 — the record is truthful, with the R-03 exceptions.** Sole parent `eda3a6d` verified; the
three U5.1 candidates verified as siblings on `6e8127d`; all three preserve refs exist with the
stated hashes. Manifest 2124 → **2127**, +4 / −1, as claimed. Suite on the clean primary worktree:
**2126 passed, 1 skipped in 393.39s** against the message's 2124/3 — same 2127 total, the difference
being precisely the two dirty-tree NOT-RUN skips the message itself explains. **Unlike `f01d942`,
every verification artifact the message asserts exists in the tree and does what it says.**

**Item 7 — nothing the mint rests on was damaged.** The only specification change between `f01d942`
and `a6005a8` is the F-06 unfreeze-sentence deletion. Independently recomputed: 105 F1–F13 contracts,
F14 13, F15 9, digest `1485bd6f0f6dd02b` reproduced, classification 117/9/6/2/0 = 134 with zero
classifier errors. `src/` 0 files changed `eda3a6d..a6005a8`; `PROGRAM-WEIGHTS.yaml` 0 changed; R-07's
record untouched; no review/adjudication file touched. P4 COMPLETE with 14 PASS; P5
READY/NOT_STARTED/NO_CHECKPOINT with 14 PENDING; Phase-8 deferral intact. R2-A's CONSUMES machinery is
byte-untouched by the remediation.

## WHAT WAS NOT VERIFIED

The full 17-mutation log — six reproduced (M1, M2, M4, M6, M8, M17) plus three laundering
combinations and nine of the reviewer's own; the other eleven are not enumerated in the commit message
and were not reconstructed. Unlike `f01d942`'s, this log's three claimed MISSes and the two checkable
claims all hold, so there is no evidence of overstatement — but it was not audited.
`finalize_status.py` / `clean_clone_gate.py` not run, so no clean-clone measurement exists.
No runtime behaviour (none exists). The CONSUMES relation matrix beyond the AP-9 and `BrakeReleased`
cases, the 5a co-commit corpus, and the carried `PL-11c → OutcomeUnknown` residual — inherited from
U5.1, not re-cut; in particular whether a **bidirectionally forged** co-commit passes `consumes_valid`
for a durable-writing member was not tested, because R-01 needs no such forgery. The seven minted
payloads and family contracts against their obligations — upheld previously, byte-identical here, not
re-derived. `PROGRAM-WEIGHTS.yaml` content (only that it is unchanged). Documents outside `docs/`,
`eval/`, `src/`. The G2-D11/G2-D12 collision's full downstream reach.

## CONTROLLER'S INDEPENDENT REPRODUCTION

Confirmed R-01's structural basis on the primary worktree at `a6005a8` before commissioning any
further work:

- `_discharge_route_errors` line 1088-1091: the `PRE_EXISTING_STRUCTURAL_PROOF` + `CONSUMES` branch
  calls `_consumes_relationship_errors(rec["row"], …)`.
- `_consumes_relationship_errors` lines 912-913: `if not durable: continue  # rule 3 - GR-2 does not
  bind; DESCRIPTIVE marker, no exempting force`, where `durable = _durable_write(row, states)` reads
  the row's own `Writes` cell.
- The same function's docstring asserts the discharge claim "is re-proven here from structured data -
  and never from data the discharging edit authored (N-01)". That statement is false of the CONSUMES
  branch beneath it — the same class of defect as F-04 in the prior candidate.
