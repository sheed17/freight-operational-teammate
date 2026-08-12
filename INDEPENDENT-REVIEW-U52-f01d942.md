# P5 U5.2 — FRESH INDEPENDENT REVIEW of candidate `f01d942b54b74658d51ba77cb831334cad7bd993`

Transcribed by the campaign controller from the reviewer's return; the reviewer could not write files.
It built nothing, reviewed no prior candidate, and remediated nothing. Primary worktree untouched
throughout (`git status --porcelain` empty, HEAD `f01d942`); all mutation work in `git clone` /
`git archive` copies under `/private/tmp`.

## VERDICT: REJECT — TARGETED REMEDIATION REQUIRED

The mint itself is sound: counts are real, the seven names and payloads are truthful, the ten
properties hold, nothing was re-attributed, no forbidden surface moved. The rejection is on **R3-A
and R3-B taken together**. R3-A closes one instance of the false-delegation route and leaves 113
cross-machine instances open, eight of them aimed at the seven founder-gated rows. R3-B then unlocks
the discharge machinery those routes feed. A founder-gated obligation can again be discharged through
a semantically false route with the general machinery green — the failure that rejected `38b4bda` and
`1ae365a`.

## BLOCKING FINDINGS

**F-01 — R3-A closes ONE false delegation, not the route.** The trigger-intersection invariant carries
no machine, aggregate or family constraint, unlike CONSUMES-VALID which requires a different machine
in both rows' cells. A row may delegate its GR-2 obligation to a producer on an unrelated machine if
they share a target-state name and one trigger letter. Sweep over the complete structurally-
expressible population: 227 triples, 148 admitted, 79 rejected; 249 row→target pairs, 166 admitted,
of which **113 are cross-machine**. Eight admitted pairs have one of the adjudicated seven as source:
`AP-9→PL-8`, `AP-9→EF-1`, `PO-2→PL-1`, `PO-2→RU-1`, `PO-3→CM-2`, `RU-8→AP-3`, `RU-8→EX-7`,
`RU-8→PO-7`. `AP-9 → GRANTED=PL-8` means an M4 approval freeze would be "recorded by" M2's
`CheckpointPassed` — architecturally the same falsity as the `AP-9 CONSUMES:BrakeReleased` exploit
that rejected `38b4bda`. `RU-8 → EXPIRED=PO-7` is worse: the row's own prose already says the other
aggregate's fact "does not record that THIS rule expired". No over-rejection: all seven declared
branches pass, and a same-machine conjunct would also have zero false rejects (148 → 47 admitted)
while killing every exploit above.

**F-02 — a founder-gated obligation is discharge-able again, discharge machinery green.** R3-B's
`PRE_EXISTING_STRUCTURAL_PROOF` route re-proves a DELEGATES_TO claim through the predicate F-01 shows
to be permissive. Fed directly, five of the seven rows accept a false discharge; PL-7a→PL-7b is the
lone refusal (control). End-to-end in a throwaway clone, replacing RU-8's mint with
`DELEGATES_TO:EXPIRED=PO-7`: `14 failed, 2107 passed` — but **every one of the 14 is a name/count
literal written for this specific mint**, and all five nodes of the discharge machinery PASSED. The
guard meant to refuse a false discharge does not; only this unit's hard-coded event names do, and the
next unit will not have them. Separately,
`test_every_durable_write_is_recorded_by_an_event_or_a_registered_open_obligation` treats class
`DELEGATES_TO` as discharged with no relationship proof at all, where CONSUMES gets a full
re-derivation.

**F-03 — the "corpus-wide sweep" does not exercise the predicate it verifies.**
`test_the_trigger_intersection_invariant_is_verified_over_the_whole_corpus` recomputes `disjoint`
inline and never calls `_resolve_delegation`. Deleting the invariant from the guard leaves it green;
only the single hostile node on one hand-picked pair fails. The sweep asserts zero false *rejects*
only — the selection-bias correction the CONSUMES re-adjudication demanded was applied to the half
that could not fail.

**F-04 — the anchor-independence proof is a tautology, and the commit message describes work not in
the tree.** The commit claims an AST scan and a monkeypatch of `ADJUDICATED_EVENT_REQUIRED`. Neither
exists in the suite. What is committed is
`assert empty_anchor["errors"] and not frozenset() & ADJUDICATED_EVENT_REQUIRED`, where
`empty_anchor` is a verbatim recomputation of `got` three lines above and the second conjunct is
constant True for any anchor value. The docstring asserting it "re-runs the whole delegation
resolution with `ADJUDICATED_EVENT_REQUIRED` emptied" is false of the code beneath it. **The property
is TRUE** — the reviewer performed the real AST scan and the real monkeypatch and both hold — so this
is a false proof of a true claim, in a control guard, restated as fact in the commit record.

**F-05 — `PolicyApproved`'s CONSEQUENTIAL status is entirely unguarded, and is a rule the builder did
not mutate.** The commit calls PO-3's promotion into §5's CONSEQUENTIAL list "the 'no admin path'
evidence". Striking `PolicyApproved` from that list and running the full canonical suite:
`2121 passed, 3 skipped` — zero nodes fail. This contradicts "20 mutations, 20 CAUGHT, each neutering
a rule or a fact in the specification the guard reads": this is exactly such a fact, unmutated.

## NONBLOCKING FINDINGS

**F-06 — the unfreeze path is asserted but not modelled.** The new `ApprovalFrozen` row adds
"Unfreezing … happens through `RealityEstablished` on the bound chain." `04-approval.machine.md` §14
contains no transition clearing `frozen`, and there is no `ApprovalUnfrozen` event; that sentence is
the only mention of unfreezing in the corpus. Reconstructing the *current* value of `frozen`
therefore still needs another aggregate's event plus an absence — the shape ER-16 forbids for the
freeze itself. Fail-closed, hence downgraded, but the sentence asserts a mechanism the repository has
not established and the clearing of `frozen` is an unrecorded durable write on M4 with no transition
row.

**F-07 — two more added rules with no guard.** Deleting ER-16's scoping parenthetical, and deleting
the new §8 "order-tolerant does NOT mean order-free" bullet, each leave `2121 passed`.

**F-08 — `PolicySubmitted` / `PolicyProposed` is a permanent readability hazard.** The event named
"Proposed" is not the one that reaches `PROPOSED`. D3 forced this; the candidate documents and guards
it. Correct decision, residual cost, worth recording as a residual.

**F-09 (informational)** — `test_the_corrected_totals_are_recorded_with_exact_set_digests` asserts
only truthiness of the digest, never a recomputation. Pre-existing, not introduced here.

**F-10 (informational)** — the non-guard-forced document count is **14, not 15**;
`IMPLEMENTATION-SURFACE.yaml` is guard-forced, paired with the `REQUIRED_CONCEPTS` edit.

## WHAT WAS ATTACKED AND HELD

Counts recomputed with the reviewer's own parser: 105 F1–F13 names, 0 duplicates, F14 13, F15 9, 134
rows, split `117/9/6/2/0` summing to 134, no unclassified rows. Digest `1485bd6f0f6dd02b` reproduces;
parent digest `6deb2ccecdfa8b3f` reproduces; set difference against the parent tree is exactly the
seven added with **nothing removed**. Baseline suite on the clean worktree: `2123 passed, 1 skipped`.

R3-B negative controls — **all seven REFUSED**: discharge re-pointed at `BrakeReleased`; invented
third route; blank authority; shrunk frozen-members record; row silently deleted with its discharge;
row returned to EVENT_REQUIRED with the discharge kept; a new obligation joining without amending the
anchor. CONSUMES laundering remains dead: the `38b4bda` exploit and two variants all refused.

Five of the builder's mutations spot-checked (AP-9 payload rename, `unknown_outcome_ref` removal, §3
re-attribution of `PolicyApproved`, PL-7a `caps_evaluated`, EC-7 `previous_severity`) — all genuinely
CAUGHT. The ten founder-required properties verified mechanically: no zero-owner event, no duplicate
declaration, exactly one producer for each of the seven, none `‡`-marked, no minted event omits a
field its row persists, no existing event changed meaning, no obligation hidden through CONSUMES or
DELEGATES_TO, `EVENT_REQUIRED` empty with all seven retained and marked discharged.

AP-9 / ER-16: the reconstruction of `frozen=true` genuinely rests on positive evidence — the fold
reads only AP-9's own producer events, `producers_of["AP-9"] == {"ApprovalFrozen"}`, and AP-9 is not
a producer of `OutcomeUnknown`. Runtime fail-closed default retained and guarded. The only crack is
the unfreeze direction (F-06), which is fail-closed.

Test-node renames: both **replaced and strengthened**, nothing dropped — the replacement keeps all
four original assertions and adds per-name producer pinning plus `len(owned − minted) == 98`; the
second replaces a hand-typed `98/98` with a corpus-derived value and keeps the `(92/92)` regression
assertion. Manifest honest: 2124 collected, 2124 in the manifest, sorted, zero difference either way.

Forbidden surfaces all clean: `src/` byte-unchanged (so the production `GateRegistry` is untouched),
`PROGRAM-WEIGHTS.yaml` untouched, the R-07 `expected_legacy_paths` record untouched, no
review/adjudication report touched, Phase-8 deferral unchanged. P5 stays `READY / NOT_STARTED /
NO_CHECKPOINT` with 14 PENDING criteria and nothing scored; P4 stays COMPLETE. U5.1's R4-A evidence
refs both resolve and their subjects match the recorded verdicts.

Document scope ruling: every added line read. **Legitimate truth-maintenance, not scope creep** — the
acceptance surfaces had to move or `AC-TRACE-000`/G2 would state a false requirement, and every
document reporting the discharge also states that P5 is NOT_STARTED, nothing was built, all criteria
PENDING, and G2-D4/D6/D8/D9/D10 open. Sole exception: F-06's unfreeze sentence.

## WHAT WAS NOT VERIFIED

No runtime behaviour (there is none; `src/` untouched — every replay claim checked is a
specification-level fold, as the candidate itself states). The builder's 20-mutation log in full —
five spot-checked, one uncovered rule class found (F-05); the other fifteen and the discarded
self-mutation not reproduced. R2-A's exact 5→20 arithmetic — a cruder measure gives 11→26, a
different quantity; the substance of the corrected text is correct on inspection. `PROGRAM-WEIGHTS.yaml`
content (only that it is unchanged). The CONSUMES relation matrix beyond the AP-9 cases, and the
carried `PL-11c → OutcomeUnknown` residual, both inherited from U5.1 and not re-cut here. Anything
outside `eval/`, `docs/` and `src/`. `scripts/finalize_status.py` and `scripts/clean_clone_gate.py`
were not run; no commit, amend or push was made.

## REMEDIATION SCOPE PROPOSED BY THE REVIEWER (minimal)

1. Add a same-machine conjunct to `_resolve_delegation` — zero false rejects, closes all eight routes
   at the seven and 101 of 148 overall. (F-01, F-02)
2. Make the corpus sweep call `_resolve_delegation` and assert the false-**accept** set exactly, not
   only zero false rejects. (F-03)
3. Replace the tautological anchor-independence assertion with a real `monkeypatch.setattr` of
   `ADJUDICATED_EVENT_REQUIRED`, and correct the docstring and the commit record. (F-04)
4. Guard §5's CONSEQUENTIAL membership — at minimum that `PolicyApproved` is in it and that every §5
   member exists in §3. (F-05)
5. Record the unfreeze path as an open residual, or remove the sentence asserting it. (F-06)

## CONTROLLER'S INDEPENDENT REPRODUCTION

The controller reproduced three findings before relaying them, on the primary worktree at `f01d942`:

- **F-02** — `_discharge_route_errors` admits `RU-8 → EXPIRED=PO-7` ("M11 PolicyExpired — a POLICY
  expiry, not a rule"), `RU-8 → AP-3`, `RU-8 → EX-7`, `PO-3 → CM-2`, each with `errors: NONE`, while
  the `PL-7a → PL-7b` control is correctly refused with the trigger-disjointness message.
- **F-04** — `not frozenset() & ADJUDICATED_EVENT_REQUIRED` and `not frozenset() & frozenset()` both
  evaluate `True`; the conjunct is constant for any anchor value.
- **F-05** — no node under `eval/tests/` references the events registry §5 CONSEQUENTIAL list.
