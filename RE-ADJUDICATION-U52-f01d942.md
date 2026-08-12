# P5 U5.2 — SEPARATE TARGETED ADJUDICATION of candidate `f01d942b54b74658d51ba77cb831334cad7bd993`

Transcribed by the campaign controller from the adjudicator's return; it could not write files. It is
a further session: it built nothing, reviewed nothing, wrote no prior adjudication, and remediated
nothing. It reproduced every finding with its own instruments before ruling. Primary worktree at
finish: `git status --porcelain -uall` 0 lines, HEAD `f01d942`, tree `ade05901`. All mutation in
throwaway clones under `/private/tmp`.

## VERDICT: UPHOLD REJECT — TARGETED REMEDIATION REQUIRED

Reached by different reasoning than the reviewer's, on corrected arithmetic, and with **one blocking
route the reviewer missed entirely** — which makes the reviewer's proposed remediation scope
insufficient.

## The deciding test

The U5.1 re-adjudication drew the line at *"a founder-gated obligation could actually be discharged
with the suite green"*, and accepted `d59b740` because the equivalent laundering ran the §I.3
frozen-set node RED. The adjudicator built the fully coordinated laundering at `f01d942` — RU-8's
mint undone, Event cell → `DELEGATES_TO:EXPIRED=PO-7`, discharge record, obligation record,
`discharged_members` mirror, `computed_classification` and the `DELEGATES_TO.members` resolution
block all updated consistently — and ran the whole delegation/discharge layer:

```
6 passed, 5 warnings in 0.19s
```

**The single deciding fact: the general invariant that carried the last adjudication no longer
fires.** `f01d942` necessarily retired the unconditional three-way equality — it had to, or no mint
could land, and R3-B is correct in direction — and routed all of its refusal power through
`_discharge_route_errors` → `_resolve_delegation`. Under coordinated laundering that predicate
returns `[]` and every node of the discharge machinery is green. What refuses instead is a
seven-name literal `MINTED` dict in `test_p5_canonical_event_mint.py` — the class of defense the U5.1
re-adjudication explicitly discounted.

Aggravating: this unit was under a named per-unit obligation to prevent exactly this. The U5.1
re-adjudication states *"R3-A is owed by that unit, before it amends the anchor."* `f01d942` is that
unit; its subject line asserts it "close[d] the false-delegation route"; and R3-A's literal
statement — *"a false DELEGATES_TO discharge record passes the §I.3 discharge machinery"* — is
**verbatim still true**.

This is **not** the `38b4bda`/`1ae365a` case (suite fully green, obligation gone) — the adjudicator
says so plainly and declines the reviewer's implication that it is. It is a third case, and it falls
on the defect side of the repository's own principle: *"A COUNT IS NOT THE INVARIANT; THE COUNT IS A
CONSEQUENCE."*

## Per-finding rulings

**F-01 — CONFIRMED · BLOCKING · reviewer's arithmetic wrong in three places, all understating the
defect.** Driving the *real* `_resolve_delegation` over every expressible triple: 250 triples, 157
admitted, 93 rejected, **106 admitted cross-machine**.

1. **Nine adj7-sourced admits, not eight.** The reviewer missed `AP-9 → GRANTED=EF-2f`, owner
   **`ClaimRefused`** — an M3 idempotent claim refusal standing as the record of an M4 approval
   freeze, more flagrant than the `AP-9 → PL-8` case it did name. Root cause: EF-2f's From→To cell
   contains no `→`, so `_states_in(cell.split("→",1)[-1])` reads the entire cell and yields
   `{GRANTED}` — the parser degrades silently on an arrow-less row.
2. **The trigger invariant closes 4 of 13 adj7 routes, not "the route."** Counterfactual over the
   same 250 triples: base 250 admits / 13 adj7; trigger-only 167 / 9; same-machine 102 / 2;
   From-intersect 33 / 1 but **false-rejects all 7 declared branches**; trigger AND same-machine
   **53 / 0 / 0 false rejects**.
3. **`166/83` is not the predicate's verdict.** A trigger-only sweep reproduces the builder's figure
   exactly; the *full* predicate admits 157. The commit message's sweep numbers describe the inline
   trigger clause, not the predicate they are offered as evidence for — F-03's signature in the
   commit record.

`RU-8 → EXPIRED=PO-7` remains the worst of the nine: the row's own committed prose says the other
aggregate's fact *"does not record that THIS rule expired"*.

**F-02 — CONFIRMED · BLOCKING · the reviewer's central empirical claim is materially wrong, and the
truth is worse.** Per-row probe: **four** of the seven accept a false DELEGATES_TO discharge, not
five — AP-9 (3 of 4 expressible), PO-2 (2 of 4), PO-3 (1 of 1), RU-8 (3 of 3); CF-7 and EC-7 have
empty To-sets and no expressible route; PL-7a is the lone refusal. The end-to-end's `14 failed`
is **10**: four are CLI subprocess smoke tests that fail identically on a pristine unlaundered clone,
a control the reviewer never ran. The reviewer's decisive claim — every failure a name/count literal,
every discharge-machinery node green — is nonetheless **TRUE**, verified the hard way: one general
cross-record consistency guard did fire, but only because the first laundering was incomplete; both
records are the launderer's to edit, and completing them turns that node green, leaving only count
literals and the seven-name `MINTED` dict.

Severity weighed honestly: the `MINTED` dict lives in a *guard* file, so the seven cannot be
laundered away today without editing a guard, and this is not the `38b4bda`/`1ae365a` case. It blocks
anyway, on three grounds already ruled on by this repository: the mint-name anchor pins *this mint's
identity*, not the *discharge predicate*, and has zero force over any future obligation or any
delegation elsewhere in the corpus; the general invariant that carried the last adjudication was
retired in this same commit and its replacement admits 9 of 13 adj7-sourced routes; and R3-A was owed
by this unit by name and is asserted closed in an immutable commit record while measurably open.

**N-01 (NEW — the reviewer missed this entirely) — CONFIRMED · BLOCKING.** The reviewer's negative
battery covered CONSUMES, forged records, invented routes, blank authority, shrunk registers and
silent deletion. It never tested the **`NON_PRODUCING` discharge route**, whose entire re-proof is
`_durable_write(rec["row"], states)` — **a re-reading of the row's own `Writes` cell, which the
discharging edit is free to empty.** Textbook self-certification, the exact thing the `38b4bda`
adjudication forbade. Three of the seven — AP-9, CF-7, EC-7, precisely those whose durable write is a
*field* write rather than a state change — fall to a **two-cell specification edit**, including
**AP-9, the row of the `38b4bda` rejection**. End-to-end with AP-9's mint undone, Event cell →
`NON_PRODUCING:ENUMERATED_NO_OP`, Writes cell emptied, all audit records coordinated:
`3 passed`. The obligation register already holds the authoritative datum
(`durable_write: "frozen=true"` for AP-9); `_discharge_route_errors` simply does not consult it.
**The reviewer's remediation item 1 does not touch this route**, so its scope would ship a candidate
with an equally trivial hole in a sibling route. Independently blocking.

**F-03 — CONFIRMED exactly · BLOCKING (it is what let F-01 ship).** AST scan:
`test_the_trigger_intersection_invariant_is_verified_over_the_whole_corpus` calls
`_resolve_delegation`: **False**. Neutering the trigger conjunct inside the predicate while leaving
the sweep untouched: `1 failed, 88 passed` — only the single hostile node on the one hand-picked
pair. The sweep asserts zero false *rejects* only, the inverse of the selection-bias correction the
CONSUMES re-adjudication demanded. Had it called the predicate and asserted the admitted set, the 106
cross-machine admits would have been in the builder's own output.

**F-04 — CONFIRMED · BLOCKING · agrees with the reviewer; the property really is true.** No
`monkeypatch` anywhere in the two guard files. `not frozenset() & <anything>` is constant `True`;
`empty_anchor` is a byte-identical recomputation of `got` with the same five arguments. The docstring
claiming it "re-runs the whole delegation resolution with `ADJUDICATED_EVENT_REQUIRED` emptied" is
false of the code beneath it. The adjudicator performed both claimed verifications itself — real AST
scan (`references ADJUDICATED_EVENT_REQUIRED: False`) and real monkeypatch (anchor emptied → PL-7a
still refused, WI-14 still resolves) — and **the property is TRUE**. A false proof of a true claim,
in a control guard, with a misdescribing docstring and a commit message asserting two verification
artifacts that do not exist in the tree. In a program whose governance history is about false green,
a guard that reports work it did not do blocks on its own.

**F-05 — CONFIRMED · BLOCKING (contradicts the mutation evidence).** Striking `PolicyApproved` from
§5's CONSEQUENTIAL list on a pristine clone: `4 failed, 2117 passed` — **identical to the pristine
baseline**, zero additional nodes. No guard in `eval/` reads §5's CONSEQUENTIAL list. The commit
calls that promotion *"the 'no admin path' evidence"* and separately claims twenty mutations each
neutering a rule or a fact the guard reads. This is such a fact, unmutated and unguarded; the
mutation-evidence claim is **overstated, not merely incomplete**.

**F-06 — CONFIRMED (location corrected) · NONBLOCKING · disagrees with the reviewer's reasoning.**
The sentence is in `events/04-approval-events.md`, not the machine file. Reconstructing the current
value does **not** require an absence — `ApprovalFrozen` sets it, `RealityEstablished` clears it, both
positive edges; ER-16 is not self-undermining. The real defect is the reviewer's second point: **the
clearing of `frozen` is a durable write on M4 with no transition row, no event and no registered
obligation** — a fresh GR-2 obligation created by this commit's own sentence. Nonblocking because it
fails closed, but it must not ship as an unrecorded assertion.

**F-07 — CONFIRMED in part · NONBLOCKING.** ER-16's core *is* guarded (the mint test pins
`"POSITIVE"`, `"never from an absence"`, `"OutcomeUnknown"`, `"RealityEstablished"`); the scoping
parenthetical is not among the pinned phrases. The new §8 "order-tolerant" bullet is wholly
unguarded.

**F-08 — CONFIRMED · NONBLOCKING, correct decision.** Record as a residual.
**F-09** — pre-existing, not introduced here. **F-10** — not verified by the adjudicator.

## Ruling: is the same-machine conjunct principled, or over-fitting?

**Principled — on firmer ground than the reviewer gave, and its remedy is necessary but NOT
sufficient.** §1's universal ordering key is `(tenant_id, aggregate_id, aggregate_version)`. A target
on a different machine is a different aggregate, so its event carries a different `aggregate_id` and
cannot, under the repository's own envelope, be the record of *this* aggregate's state change. It is
the exact structural **dual** of the already-adjudicated CONSUMES-5c, which requires **CROSS**-machine
on the authority of `state-machines/registry.md:182`. Both derive from one line of specification,
neither from an exploit list. Against the complete declared population:
`declared branches a same-machine conjunct would FALSE-REJECT: []`.

Three corrections to the reviewer's remedy:

1. **Additive, not a replacement.** Same-machine alone still admits `PL-7a → PL-7b` and `AP-9 → AP-2`.
   The trigger conjunct must be **kept**; only `trigger AND same-machine` reaches 53 admits / 0 adj7 /
   0 false rejects. "The trigger invariant is over-fitted, add same-machine instead" would be a wrong
   and dangerous reading.
2. **It does not close N-01**, which no change to `_resolve_delegation` touches.
3. **It is a necessary-conditions filter, not a semantic proof, and must be recorded as such** — in
   the existing `ADJUDICATED_UNDECLARED_ACCEPTS` style. The surviving 53 include
   `EF-1 → GRANTED=EF-2f` and `IB-1 → PROPOSED=IB-3`. That is acceptable under this repository's own
   standard; what is not acceptable is announcing an invariant closing 4 of 13 as having "close[d]
   the false-delegation route" in a commit subject line.

**The additional invariant the adjudicator holds is right, and generalizes past both routes:** *a
discharge may never be admitted on a re-reading of a cell the discharging edit is itself permitted to
change.* Concretely, for any row in `ADJUDICATED_EVENT_REQUIRED` the registered obligation's own
`durable_write` field is authoritative, so the NON_PRODUCING route is structurally unavailable to it.
Zero false rejects, no new populations, and it is the direct application of the `38b4bda`
anti-self-certification ruling to the one route that never received it.

## What the reviewer got wrong in the candidate's favour

**R2-A: the builder is right and the reviewer's doubt is unfounded.** Measured across three commits
with the adjudicator's own parser: `6e8127d` → **5** rows (PL-12, PL-8, PL-9, EF-2, EF-4); `d59b740`
→ **20**, reproducing the U5.1 re-adjudication's arithmetic *and its exact named row identity*. The
candidate's correction is landed correctly, records the mandated 5→20 measurement, restates the
property as different-row authorship, and declines the out-of-scope widening. **R2-A is fully
discharged and must not be reopened.**

**The mint itself holds.** §3 F1–F13 = 105 (removing one drives the guard to `104, not 105`), all
seven present, `len(corpus − minted) = 98` by set difference, each minted event exactly one producer.
Baseline suite on the clean worktree: `2123 passed, 1 skipped in 392.32s`.

**Did the reviewer over-reject?** No. No finding is a residual by the `d59b740` standard.

## Remediation scope (minimal, ordered)

1. `_resolve_delegation`: **keep** the trigger conjunct; **add** a same-machine conjunct. Both
   positionally required, both fail-closed on undecidable. (F-01, F-02)
2. `_discharge_route_errors`: bar the `NON_PRODUCING` route for any row whose registered obligation
   records a `durable_write`; the register, not the row's own Writes cell, is the authority. (**N-01**)
3. Make the corpus sweep **call `_resolve_delegation`** and assert the **exact admitted set**, not
   only zero false rejects. Deleting either conjunct must turn it red. (F-03)
4. Replace the tautological anchor-independence assertion with a real `monkeypatch.setattr`; correct
   the docstring. **The replacement's commit message must not repeat the AST-scan/monkeypatch claim,
   and should record that `f01d942` made it falsely.** (F-04)
5. Guard §5 CONSEQUENTIAL membership: at minimum `PolicyApproved ∈ §5` and every §5 member ∈ §3.
   Correct the mutation-evidence claim. (F-05)
6. Either delete the unfreeze sentence or register the `frozen`-clearing durable write as a new OPEN
   GR-2 obligation. Do not assert an unmodelled mechanism. (F-06)
7. Record the surviving structural imprecision as a named residual in the existing
   `ADJUDICATED_UNDECLARED_ACCEPTS` style. Guard ER-16's scoping parenthetical and the §8 bullet, or
   record them as unguarded. (F-07)

**Must NOT be reopened.** The mint (seven names, schemas, §3/§5/family contracts, the seven
reclassified rows with Writes preserved); counts 105 / 117-9-6-2-0 = 134 and digest
`1485bd6f0f6dd02b`; **R2-A's correction, fully discharged**; R4-A; the **direction** of R3-B (making
both routes reachable was necessary and correct); the legitimate document truth-maintenance; ER-16
and D2's EMIT decision; PO-1's `PolicyProposed`; `src/`, `PROGRAM-WEIGHTS.yaml`, the R-07 record, P4
COMPLETE, the Phase-8 deferral; P5's `READY / NOT_STARTED / NO_CHECKPOINT` with all 14 criteria
PENDING and nothing scored.

## Topology — verified, not assumed

```
38b4bda   parents: 6e8127d    P5 U5.1
1ae365a   parents: 6e8127d    P5 U5.1 replacement
d59b740   parents: 6e8127d    P5 U5.1 second replacement
f01d942   parents: eda3a6d    P5 U5.2
```

All three U5.1 candidates are **siblings** on the certified predecessor's status-metadata commit,
never descendants of the rejected one. Option A applies unchanged: the replacement's **sole parent is
`eda3a6d`**, not a descendant of `f01d942`; `f01d942` is preserved permanently and unmodified, and
needs its **own** preserve ref before any branch pointer moves.

## What the adjudicator did NOT verify

`finalize_status.py` and `clean_clone_gate.py` not run (forbidden), so no clean-clone measurement
exists from it. No commit, amend, push, or forbidden git command. **The builder's 20-mutation log** —
none of the twenty reproduced directly; F-05 and N-01 established as uncovered rule classes by its own
mutations, which contradicts the log's completeness claim without auditing its entries. F-10 not
measured. The `1485bd6f0f6dd02b` digest **construction** not verified (the 105/98 set arithmetic and
per-event producer uniqueness were). The 9×111 CONSUMES matrix and the carried
`PL-11c → OutcomeUnknown` residual — inherited from U5.1, not re-cut. `PROGRAM-WEIGHTS.yaml`, `src/`
and the R-07 record — relied on the reviewer's byte-comparison, not repeated. No runtime behaviour
(none exists). The four CLI smoke failures are clone artifacts, not diagnosed further. Its sweep
drives the repository's real guard functions and is not an independent corpus parser, so a defect in
`_transition_rows`/`_states_in` would be invisible to it — one such degradation was noted (EF-2f's
arrow-less cell) but the parser was not systematically audited.

## CONTROLLER'S INDEPENDENT REPRODUCTION

Before commissioning remediation the controller confirmed N-01's structural basis on the primary
worktree at `f01d942`: `_discharge_route_errors`'s NON_PRODUCING branch is
`return ([...] if _durable_write(rec["row"], states) else [])` — a re-reading of the row's own cell —
while `TRANSITION-EVENT-AUDIT.yaml` carries an authoritative `durable_write:` field per obligation
that the branch never consults.
