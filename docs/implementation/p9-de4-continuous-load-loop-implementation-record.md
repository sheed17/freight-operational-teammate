# P9-CP-4 — the continuous load loop: complete loads, booked to customer billing-ready, in shadow

> **This is a builder's record, not a status.** Status is [`CURRENT.md`](CURRENT.md) and the registry.
> **Founder direction, 2026-10-06:** the formal P9 acceptance exercise is stopped, `c4376b9` is the P9
> product baseline, and the first continuous shadow freight operating loop is built on the freight
> spine now — pulling an entity, a rule or an act into the system only when the loop needs it.
> **P9 is not accepted, nothing is scored, and P10 is still `BLOCKED`.** This work accepted nothing,
> opened nothing and enabled nothing.
> **The corpus is synthetic development input.** Nothing here is a design-partner observation, no
> freight rule is validated by it, and no labor time was measured.
> **Three focused independent reviews have been performed, and each BLOCKED this checkpoint.** The
> first (2026-10-06) found the false quiet repaired in §10. The second (2026-10-07) found the §10
> repair sound on every criterion it was given, and blocked the tree on a rescheduled-appointment
> false quiet that repair had neither introduced nor closed (§11). The third (2026-10-07) found the
> §11 repair sound, and blocked the tree on three older defects on the same seam (§12).
> **The repair in §12 was written by the session that performed that third review, so it is a
> builder's work and has not been independently reviewed.** Tier-1 and tier-2 surfaces were touched
> (§5, §10, §11, §12); one focused independent review of the §12 repair is still owed before merge
> ([`CLAUDE.md`](../../CLAUDE.md) §7).

## 1. What a broker can now do that they could not before

Watch a load run. From the moment it is booked until customer billing is ready, Neyma keeps one
operating picture of the load and can be asked, at any moment in its life:

| | |
|---|---|
| 1 | What is happening? |
| 2 | What evidence supports that? |
| 3 | What changed since the previous moment? |
| 4 | What work remains? |
| 5 | What is overdue? |
| 6 | What are we waiting for? |
| 7 | What would Neyma do next? |
| 8 | What requires a human? |
| 9 | Why does it require a human? |
| 10 | Is customer billing ready? |
| 11 | Is there unresolved carrier-side work? |
| 12 | Is the load genuinely quiet? |
| 13 | How many human touches has this load required? |

```
.venv/bin/python scripts/run_freight_corpus.py --loop                                  # every load, now
.venv/bin/python scripts/run_freight_corpus.py --loop --load LD-50007                  # one load's life
.venv/bin/python scripts/run_freight_corpus.py --loop --load LD-50007 --detail         # the thirteen answers
.venv/bin/python scripts/run_freight_corpus.py --loop --load LD-50002 --after loaded   # one moment
```

Twenty-one complete loads run side by side in one inbox, in the order their records arrived. The
picture changes when something arrives — and when a deadline passes with nothing arriving at all.

**It is shadow only.** What Neyma "would do" is a sentence with a draft nobody sends. What needs a
human is a question, with the reason and the evidence, laid before a named person. Nothing executes.

## 2. What was built

| Piece | What it is |
|---|---|
| `freight_domain/load_loop.py` | The picture (`LoadMoment`), what changed (`Change`), what Neyma would do (`Proposal`, with a `draft`), what a human is asked (`Escalation`), the cost in people (`HumanTouches`), the runner and three renderings: the board, a load's life in one line per moment, and a moment as the thirteen answers. A read model: it writes nothing. |
| Deadline-driven evaluation | Before each record, the runner lets the clock pass to every `due_by` the open work already holds and looks again. No deadline is invented; a history carries no `clock` record merely to make one fire. |
| One inbox | Histories are merged by arrival time, so loads are in flight together and one load's record is the moment another's deadline is noticed. |
| `confirm_movement_status` | A new human act (§4). |
| `eval/freight_corpus/loop_histories.py` | Twenty-one complete loads with labeled moments (§3). |
| `scripts/run_freight_corpus.py --loop` | The one command. It audits every evaluation and fails if a load is quiet while anything is owed, waited for or disputed. |
| `eval/tests/test_p9_load_loop.py` | Thirty tests. |

**Three definitions the loop had to make, and made conservatively:**

- **Quiet** is "no needs" — on a load that is *booked*. A tendered load with no carrier has no needs
  only because covering it is outside this loop; it is reported not quiet, next step `NOT_BOOKED`.
- **A human touch** is a decision a human recorded on the load, or one still owed. Both are read from
  the canonical record, so a restart or a replay counts the same.
- **Carrier-side work** is an unplaced invoice, an invoice discrepancy, an unauthorized accessorial or
  a blocked reconciliation. It never gates customer billing readiness and always prevents quiet.

## 3. The loads

| | Load | Trouble | How it ends | Touches |
|---|---|---|---|---|
| L01 | LD-50001 | none | quiet, billing-ready | 0 |
| L02 | LD-50002 | late to the shipper; the window closes in silence | quiet, billing-ready | 0 |
| L03 | LD-50003 | late to the receiver; the driver explains after the window | quiet, billing-ready | 0 |
| L04 | LD-50004 | the driver goes dark for a day | quiet, billing-ready | 0 |
| L05 | LD-50005 | "I'll update you by 12:30" — and nothing | quiet, billing-ready | 0 |
| L06 | LD-50006 | three ETAs, each later | quiet, billing-ready | 0 |
| L07 | LD-50007 | driver says delivered, tracking says moving | quiet, billing-ready | 1 |
| L08 | LD-50008 | picked up on the driver's word alone | quiet, billing-ready | 0 |
| L09 | LD-50009 | delivered, no POD; the invoice arrives first | quiet, billing-ready | 0 |
| L10 | LD-50010 | unsigned POD, then the signed one three times | quiet, billing-ready | 0 |
| L11 | LD-50011 | page one of two, then the whole POD | quiet, billing-ready | 0 |
| L12 | LD-50012, LD-50013 | one POD, the other load's number on it | both quiet, billing-ready | 0 and 1 |
| L13 | LD-50014 at Cedar Ridge | the same number next door | quiet, billing-ready | 0 |
| L14 | LD-50014 at Northline | the twin whose POD never came | POD overdue; Neyma would ask | 0 |
| L15 | LD-50015 | the receiver moved the appointment | quiet, billing-ready | 1 |
| L16 | LD-50016 | appointments requested, never confirmed | quiet, billing-ready | 0 |
| L17 | LD-50017 | the invoice is for more than the rate confirmation | billing-ready, **not quiet**: a human's question, open | 1 |
| L18 | LD-50018 | an invoice that names no carrier | quiet, billing-ready | 1 |
| L19 | LD-50019 | detention nobody agreed to, "per approval from Mike" | billing-ready, **not quiet**: denied, still billed | 2 |
| L20 | LD-50020 | the TMS named the wrong carrier, then was corrected | quiet, billing-ready | 0 |
| L21 | LD-50021 | everything out of order, some of it twice | quiet, billing-ready | 0 |

Restart, replay, duplication, reordering, late arrival and dropped records are not separate loads:
they are done to every Northline load by the hostile layer (§6).

## 4. What the loop found in the spine, and what was done

| | Finding | Disposition |
|---|---|---|
| F-22 | **A load whose movement sources contradicted each other was disputed forever.** The driver texts "delivered"; the tracking provider then shows the truck moving. That raises a Conflict only a human may settle — and there was no act by which a human could. The provider later reporting arrival, the TMS saying delivered and a signed POD arriving changed nothing: the load stayed `DISPUTED`, never billing-ready, never quiet, with nobody able to close it. | **Fixed.** `confirm_movement_status`: a recorded human says where the load is. Her act resolves the Conflict through M7's own resolve-by-human transition; a claim of a later stage made before her decision is overruled (retained, and no longer counted); a contradiction made after it is a NEW Conflict with its own row. Nothing auto-resolves: sources agreeing later is not a human deciding. |
| F-23 | A tendered load with unconfirmed appointments and no carrier was reported `QUIET`. | **Fixed in the loop's picture:** an unbooked load is never called quiet. The work engine's own `routine_work_is_zero` is unchanged; covering a load is not modeled (`P9-D33`). |
| F-24 | An assertion made in the name of nobody the brokerage has recorded produced TWO human items: the held record, and the Exception about it. | **Fixed:** one need, with the held record as its evidence. |
| F-25 | Work that is on no load — a refused assertion, an unplaceable record — appeared on no load's picture, so a board on which every load was quiet could hide it. | **Fixed:** the loop carries it beside the loads, on the board and in the metrics. |
| F-26 | The mapping store, the registry's review fields and the P9 mutation batteries' absence from CI were examined the same day in the acceptance-contract work. | **Not in this tree.** Parked on local branch `p9/adr-020-closure`. |

## 5. Safety surfaces touched — tier 1 and tier 2, independent review owed before merge

| Surface | Change | What makes it safe |
|---|---|---|
| Human authority over a disputed fact | A new human act reaches M7's resolve-by-human transition through the one composition module. | Only a recorded, active human of the brokerage can make it: an unrecorded name is refused and put before a human; a status that is not a movement status is not an act. The decider and the act are retained on the Conflict; every party's statement is retained. |
| The meaning of a claim | A movement-status claim a human overruled no longer counts as that stage. | It stays on the record. Only a claim made *before* her decision, of a *later* stage than she confirmed, is overruled. |
| Who may speak as the owner | A new tracking signal, `owner_confirmation`. | It is not in the vocabulary a tracking record may carry: a provider or driver that names itself the owner is unparseable. Mutant in place. |
| Tracking Conflict detection | A settled dispute is not re-detected; a later contradiction gets a new Conflict id. | Both directions carry a test and a mutant: a settled dispute raised again, and a later contradiction silently lost. |
| Work on no load | A refused record and its Exception are one need. | The Exception is the need; the held record is its evidence and one of its origins. |

Nothing here sends, writes outside Neyma's own state, calls an adapter or calls a model. The
ships-dark guards are unchanged and pass: exactly two harness scripts reach the spine.

**Rollback:** revert the commit. Nothing on a live path reaches any of it.

## 6. What proves it, and what could have failed

Each figure is what the command printed on the committed tree.

| Check | Result | What it could have caught |
|---|---|---|
| `run_freight_corpus.py --loop` | 21 histories, 22 loads, 425 records, 10 deadlines passed in silence, 331 moments; 513 labeled checks, 0 failed | Any labeled moment a broker would expect that the loop did not say |
| The audit, on every evaluation | 4,802 evaluations, 0 findings | A load quiet while a Conflict, an owed Expectation, a standing Exception, an unmet requirement or unplaced paper was live; stale work; a need with no owner. It is seen to fire when a load's work is stripped. |
| `run_freight_corpus.py --loop --attack` — the hostile layer over the 20 Northline loads | 393 mutants, 8,153 audited evaluations, 0 findings | Every record twice; the first record again at the end; a restart in the middle; the same load already at another brokerage; neighbours swapped; a message delayed to the end; a promise repeated; each record never arriving |
| Replay | Every picture of every load identical on a second run | Anything that depended on run order or wall-clock time |
| Restart in the middle of every history | Every picture identical to the uninterrupted run | Anything that lived only in memory |
| Two brokerages, one load number | Cedar Ridge's POD satisfies nothing at Northline; 0 wrong cross-tenant mappings | A reference resolved next door |
| Effect and authority ledgers | 0 rows | Any grant, witness, approval, compensation or pipeline instance minted |
| Money in a picture | 0 of 331 moments | An amount quoted from the timeline |
| Mutation | thirteen mutants added to `scripts/mutate_p9_load_work.py`, each turning its named guard RED | A guard that cannot fail |

No model was called and nothing was spent.

## 7. Measured

On twenty-two synthetic loads: 21 reach customer billing-ready; 19 end quiet; 2 are billing-ready
with carrier-side work still open; 16 cost zero human touches; 7 touches in all (5 decisions
recorded, 2 still owed), at most 2 on one load; Neyma would have made 29 distinct proposals. **These
are counts on invented freight. They are not a forecast about a brokerage.**

## 8. Knowingly incomplete

| ID | Debt | Why it does not block this checkpoint |
|---|---|---|
| `P9-D49` | **Every deadline Neyma handled by itself still leaves an Exception a human must close.** 16 cured Exceptions across 13 of 22 loads. They are counted, shown on the board, and NOT counted as touches. | M9 closes only by a human's decision (`P9-D30`). Who or what may close a cured Exception is a product decision. |
| `P9-D50` | A wrong-amount invoice, or a denied accessorial that is still billed, is a human's question with **no act that closes it**. L17 and L19 never go quiet. | A financial resolution is an approval (`P9-D37`, `P9-D39`). Truthful, owned, never quiet. |
| `P9-D51` | After a carrier explains a delay, the overdue arrival still proposes asking the carrier for status — and nothing prompts anyone to tell the receiver or the customer. | The lateness is real and stays visible. There is no customer or facility follow-up in the vocabulary (`P9-D33`). Whether a delay notice answers the follow-up is **NEEDS VALIDATION** (V-29). |
| `P9-D52` | A signed POD on file with no delivery report leaves the load "in transit", and when the cadence passes Neyma would chase the carrier (L21, briefly). | Whether a usable POD is itself a delivery report is **NEEDS VALIDATION** (V-30) — and a POD can be on the wrong load (L12). |
| `P9-D53` | A carrier's stated new arrival time has nowhere to live. Three later ETAs (L06) create no work until the window has already closed. | An ETA is a forecast, and the spine keeps no forecast as a fact. What an ETA past the window should trigger is **NEEDS VALIDATION** (V-31). |
| ~~`P9-D54`~~ | ~~An arrival watch discharged by a claim a human later overrules is not restored.~~ **CLOSED by the review repair (§10).** | The reason recorded here was wrong: the tracking cadence is optional tenant policy, and at a brokerage without one the load went quiet. This was the blocking finding. |
| `P9-D55` | What changed is said against the previous picture, which the runner holds in memory. A real restart would report its first picture of each load with no changes. | The picture itself is a pure function of the canonical record and survives a restart identically. |
| `P9-D56` | The loop re-projects the whole brokerage at every record: 22 loads and 425 records take about 25 seconds. | Development scale (`P9-D38`). |
| `P9-D57` | An uncovered load is outside the loop: reported not quiet, and nothing says who should cover it. | The loop begins at booked, by direction. |
| `P9-D58` | The acceptance-contract work is parked, unmerged: the mapping store's lost-race fix, the three P9 batteries in CI, the reconciled review fields, the validation items raised by P9. | None is needed by a single-writer, ships-dark loop. Merging it will conflict here in the registry, `CURRENT.md` and the status guard. |

## 9. What is next

The three product failures to attack first are `P9-D49` (humans closing what Neyma already handled),
`P9-D50` (a carrier-side question nobody can close) and `P9-D51`/`P9-D53` together (a late load on
which Neyma asks the wrong party the wrong question, and nobody tells the receiver).

## 10. Independent review — 2026-10-06 — and its repair

### What the review found

**BLOCKED**, on one reachable failure, in class "false quiet":

> The driver says delivered. The tracking provider contradicts him. A recorded human settles it with
> `confirm_movement_status IN_TRANSIT`. His claim is correctly overruled - but it had already
> discharged the delivery appointment's arrival watch, M8's `DISCHARGED` is terminal, and the watch
> could not be raised again under an id that already existed. The POD watch was cancelled, the
> Conflict was resolved, and **nothing was left on the load: it read `QUIET`, next step `NOTHING`,
> through a delivery window the truck then missed.** `audit_state` passed it, because it reads what
> the record still owes and a watch that was wrongly answered owes nothing.

This is `P9-D54`, which §8 had recorded as non-blocking because "the tracking cadence still catches
silence". The cadence is optional: Northline as the freight corpus ships it has none.

A second, lesser finding on the same seam: a human act could carry an `as_of` later than the instant
it was received. A decision settles what was said before it, so a future-dated decision settled
everything said until then - including a contradiction made, and received, after she acted.

### What was repaired

**The rule.** An overruled claim is no longer evidence of where the truck has been. It stays on the
load as what its source said (`LoadView.tracking`); everything that CONCLUDES something reads
`LoadView.standing_tracking()` instead:

| Conclusion | Before | Now |
|---|---|---|
| The truck arrived at a stop (`detectors.arrival_evidence`, used to discharge an arrival watch) | Any claim at the stop, overruled or not | Standing claims only |
| A watch that was answered stays answered | Forever: `DISCHARGED` is terminal and the id exists | A watch M8 holds `DISCHARGED` while **nothing standing** answers it is raised again, as the next generation of the same id (`detectors._owed_again_id`) - the pattern `_document_expectations` already uses for a required document. The first generation keeps its id; a generation that is owed, cancelled or expired is returned as itself, so nothing is raised twice and nothing is resurrected. |
| The tracking-cadence watch a delivery report answered | Left answered | Owed again when that report no longer stands (same helper) |
| A stop has been reached (`load_work._stop_reached`, which decides whether an unconfirmed appointment is still work) | The stop's reported arrival/departure, from any claim | Standing claims only - **a second false quiet on the unrepaired tree**: an unconfirmed delivery appointment stopped being work because of a "delivered" a human had overruled |
| The load's stage, and whether it is under way | Any claim | Standing claims only |
| What the picture says SATISFIED a watch (`load_work._settlements`) | The overruled claim | `SUPERSEDED`, by her decision |

Nothing is rewritten. The watch his claim answered is still `DISCHARGED`, by his record; the watch
that is owed is a second row; his claim and her decision are both on the load. M8 is untouched.

The rule is written against the view, not against the word "overruled", so it also holds for the
other human act that invalidates evidence: a tracking record a human **moves to another load**
(`correct_binding`) no longer answers the watch on the load it was moved off. That was a false quiet
on the unrepaired tree too, older than this checkpoint; it is closed and pinned by a test.

**A human act cannot know the future.** `parse_record` refuses a `human_assertion` whose `as_of` is
later than its `received_at`: it is unparseable, held for the intake owner on the board as work on no
load, and never applied. An act about an EARLIER moment is legal and is still applied; an act dated
at the instant it arrived is ordinary. The rule is the console path's alone - a tracking provider
whose clock runs ahead is not judged by it, and no general time framework was added.

### What proves it

| Check | Result | What it could have caught |
|---|---|---|
| The review's reproduction, no cadence | **Before:** `IN_TRANSIT`, quiet, next `NOTHING`, 0 moments overdue. **After:** not quiet from the moment she acts; `ARRIVAL_PENDING` due at the window's close; `CARRIER_STATUS_OVERDUE` (`ARRIVAL:S2_OVERDUE`) one minute after it; the same work a truck that is simply late owes | The defect |
| The same with a cadence, pinged inside it all day | The missed delivery is overdue under its own reason while the cadence need stays `PENDING` | The cadence being the only thing between the load and silence |
| A real delivery after the overrule | The re-owed watch is discharged by that record, on time; two rows, never three; quiet and billing-ready with the POD | Duplicate watches; a watch that cannot be answered again |
| Other standing evidence | Overruling "delivered" while the provider and the human both put the truck AT the dock reopens nothing | Over-reopening |
| Thirteen new tests and one strengthened, in `test_p9_load_loop.py` | all pass; twelve of the fourteen FAIL on the unrepaired tree. The two that pass there are the two that should: one asserts what must not change (a watch other evidence answers is not reopened), one proves the second oracle can fire | - |
| A second oracle, `_unwatched_stops`, on every evaluation of every loop test | 0 findings; seen to fire | A stop with a confirmed appointment that has neither a standing arrival nor a live watch. Written without the detectors. |
| Replay; restart before her act, after it, after the window closed; every record twice | Identical pictures, identical watches | A watch re-raised twice, or lost, across a restart |
| Two brokerages, one load number | Northline's watch is owed again; Cedar Ridge's claim stands, its watch stays answered, its dispute is open | A decision reaching next door |
| `run_freight_corpus.py --loop` | Every figure in §6 unchanged: 425 records, 4,802 evaluations, 331 moments, 513 labeled checks, 0 failed, 0 audit findings | The repair changing a load that has no overruled claim |
| The hostile layers | `--loop --attack` 393 mutants, 8,153 evaluations, 0 findings; `--attack` 164 mutants, 1,719 evaluations, 0 findings | - |
| Mutation | eleven mutants added to `scripts/mutate_p9_load_work.py`, and two whose anchors the repair moved re-pointed at the same defects; each turns its named guard RED | A guard that cannot fail |
| Effect and authority ledgers | 0 rows in every run | - |

**Rollback:** revert the repair commit. Nothing on a live path reaches any of it.

### Debt recorded by the review and the repair

| ID | Debt | Why it does not block |
|---|---|---|
| ~~`P9-D59`~~ | ~~An appointment whose watch was AMENDED to a new window and then went overdue gets a second owed watch for the same stop and deadline (W07 / LD-49006, two `OVERDUE` rows). Present, identically, on the unrepaired tree.~~ **CLOSED by the second review's repair (§11).** | The reason recorded here was wrong: "not silence" held only until the appointment was put back, one record later (`P9-D65`). |
| `P9-D60` | Only a human's LATEST status decision overrules anything. If she says "in transit" and later "delivered", the claim her first decision overruled counts again. | Her later decision is itself a delivery report, so no conclusion rests on the revived claim alone. Whether an earlier decision should outlive a later one is a product question. |
| `P9-D61` | A record moved to another load does not answer the watch on the load it was moved TO: M5 has no re-bind and M8 refuses a discharging observation bound elsewhere. | The watch stays owed and goes overdue: over-asking, never silence. |
| `P9-D62` | A human's "at pickup" / "at delivery" with no stop named is not arrival evidence at the only such stop, so a watch can be owed again after she said the truck is there. | Over-asking, and avoidable by naming the stop. The same gap exists for a bare `AT_PICKUP` from any source. |
| `P9-D63` | `run_load_loop(restart_after=...)` raises if the restart follows a brokerage's last record. | Harness only; no canonical state is involved. |
| `P9-D64` | A human's decision settles a statement ABOUT an earlier moment even when it ARRIVES after she decided - a late batch of provider pings, say - so she never saw it. | It is more of the evidence she already weighed, and the rule is stated ("what was said before it"). Whether "before" should mean said or received is a product question. |

## 11. Second independent review — 2026-10-07 — and its repair

### What the review found

The §10 repair held on every criterion it was reviewed against: the original false quiet closed with
and without a tracking cadence, a valid later delivery, ten orderings of several claims, repeated
and stale human decisions, future-dated acts, forged authority, later contradiction, replay and
restart, two brokerages, and no effect row. The review reproduced §10's defect on `ee9f6b8` and its
absence on `9359798` with histories and an oracle of its own.

**BLOCKED** all the same, on one reachable failure in class "false quiet" that §10 neither
introduced nor closed. It is older than this checkpoint (the code path dates from `50f3334`,
`P9-CP-3`) and is recorded as **`P9-D65`**:

> A CONFIRMED appointment is moved to an earlier window - by a recorded human, or by an edit to the
> TMS row - that window lapses, and the appointment is put back where it was. The watch had followed
> the appointment by amendment, so it still carried the id of the window it was FIRST raised for;
> it went overdue against the earlier window and was cancelled when the appointment left. The
> window the appointment returned to mapped to that cancelled row's id, an id M8 holds in any state
> is never raised again, and **the restored appointment had no watch at all: `QUIET`, next step
> `NOTHING`, through a window the truck then missed.** With a tracking cadence the load was not
> quiet, and the missed appointment was still never late. Its smallest form is one wrong entry - a
> window already past - corrected five minutes later.

`audit_state` passed it. §10's own second oracle, `_unwatched_stops`, fires on it; no history in the
corpus reached it.

The review classified `P9-D59` as blocking with it. They share one root cause - a row's identity
named a window, and the appointment had moved - and §10's reason for carrying `P9-D59` ("not
duplicate work and not silence") stopped being true one record later.

### What was repaired

**The rule.** A truck's arrival at a stop is ONE obligation however often its appointment moves; an
M8 row is one GENERATION of the watch for it. `detectors._arrival_expectations` now asks what is
owed of the obligation, and never of an id:

| Question | Before | Now |
|---|---|---|
| Is the appointment that stands already watched? | By id: is there a row under the id of the window it now has | By obligation: a live watch at this stop on the deadline that now stands IS the watch, whichever row it is. A watch that followed the appointment there by amendment counts, so a moved appointment that is then missed no longer gets a second watch beside it (`P9-D59`) |
| Has the truck already answered it? | By id | A watch at this stop that a STANDING record discharged answers the obligation, whatever window that row was raised for. Nothing is raised to be discharged again - which, when the arrival was late, used to leave a second Exception for a human to close |
| Under which id is a watch raised when neither holds? | The first generation M8 does not hold `DISCHARGED`. A `CANCELLED` generation was returned as itself, could not be raised, and nothing watched (`P9-D65`) | The first generation that is not HISTORY (`detectors._owed_again_id`): `DISCHARGED`, `CANCELLED` and `EXPIRED` are all terminal and all skipped. A generation still owed is returned as itself, so a watch already owed is not raised twice |

Nothing is rewritten, reused or reopened. The cancelled watch is still `CANCELLED`, with the
deadline it was late against; the watch that is owed is a row of its own, with a generation id that
is a pure function of the load, the stop, the window and how many generations are already history -
so a replay or a restart arrives at the same ids. M8 and `foundation.raise_expectation` are
untouched: an id present in any state is still never raised again, and should not be. A moved
appointment still AMENDS its watch in place ("a moved appointment is the same watch"), and a watch
left overdue on a window the appointment has left is still cancelled.

This extends §10's generation mechanism; it adds no second one. The tracking-cadence watch uses the
same helper and is unchanged: none of its rows is ever cancelled.

### What proves it

| Check | Result | What it could have caught |
|---|---|---|
| The review's reproduction, no cadence: 13:00-15:00 confirmed; at 11:20 entered as 09:00-11:00; at 11:25 put back | **Before:** `IN_TRANSIT`, quiet, next `NOTHING`, both rows `CANCELLED`, never late. **After:** not quiet from the correction on; `ARRIVAL_PENDING` due 19:00Z; `CARRIER_STATUS_OVERDUE` (`ARRIVAL:S2_OVERDUE`) at 19:01Z; rows `CANCELLED`, `OVERDUE`; the same work a truck late for an untouched appointment owes | The defect |
| The same through the system of record: the TMS row edited earlier, missed, edited back | Watched and called late; no human act involved | A repair that only covers the human's act |
| The same with a tracking cadence, pinged inside it all day | The restored appointment's miss is overdue under its own reason while the cadence need stays `PENDING` | The cadence being what keeps a moved appointment visible |
| Moved to a window never used; put back before anything lapsed; three moves and home; put back twice | One live watch after every move, the expected rows, and no moment late for a window nobody holds | Two watches, none, or a stale one left live |
| `P9-D59` as it was found: moved earlier, missed, arrives an hour late | One watch, answered late; one cured Exception - exactly what a load whose appointment never moved leaves. Before: two of each | Duplicate canonical state and duplicate housekeeping |
| A real arrival inside the restored window, then delivery and the POD | The restored watch is discharged by that record, on time; quiet and billing-ready | A watch that cannot be answered |
| The clock read five more times with nothing arriving | The same three rows, the same raise/cancel/amend counts, the same pictures as a run that never looked again | A generation raised on every look |
| Replay; restart before the first change, after it, after the correction, after the restored window closed; every record twice | Identical pictures and identical rows, ids included | A generation that depends on when the process started |
| Two brokerages, one load number | Northline's moves and restores; Cedar Ridge's one watch is never touched, and Dana's reschedule in its inbox is refused | A reschedule reaching next door |
| Nine new regression tests and one oracle test in `test_p9_load_loop.py` | all pass; all nine regression tests FAIL on `9359798`. The oracle test passes there, as it should: it proves the new oracle can fire | - |
| A third oracle, `_doubly_watched_stops`, beside `_unwatched_stops` on every evaluation of every loop test | 0 findings; seen to fire | Two live arrival watches at one stop |
| Eighteen hostile histories outside the suite, each judged at every evaluation: never unwatched, never two live watches, no cancellable watch left live on a window the appointment has left | 18 of 18 clean - one of them only by that letter: over a blind channel the stop stays under an unverified follow-up on the old deadline (`P9-D66`). They include: the same window restored three times; a human's wrong entry answered by the TMS row and then by her; the TMS's wrong edit corrected by a human; every update redelivered and replayed late; the truck arriving between the wrong entry and its correction, and after the restored window closed; a false "delivered" overruled and THEN the appointment moved and restored; the pickup stop; both brokerages rescheduling differently | - |
| `run_freight_corpus.py --loop` and the work corpus | Every figure in §6 unchanged: 425 records, 4,802 evaluations, 331 moments, 513 labeled checks, 0 failed, 0 audit findings; work corpus 183 records, 1,284 evaluations, 278 checks. Every load's final picture is identical to `9359798`, and LD-49006 no longer carries two owed watches | The repair changing a load whose appointment never came back |
| The hostile layers | `--loop --attack` 393 mutants, 8,153 evaluations, 0 findings; `--attack` 164 mutants, 1,719 evaluations, 0 findings | - |
| Mutation | four mutants added to `scripts/mutate_p9_load_work.py`, and three whose anchors the repair moved re-pointed at the same defects; all 82 mutants of the battery turn their named guard RED. Run on a copy of the working tree, never in it | A guard that cannot fail |
| The seven P9 and ships-dark test files | 250 passed (240 before this repair, and the ten new tests) | - |
| Effect and authority ledgers | 0 rows in every run | - |

**Rollback:** revert the repair commit. Nothing on a live path reaches any of it.

### Debt recorded by the review and the repair

| ID | Debt | Why it does not block |
|---|---|---|
| ~~`P9-D65`~~ | ~~An appointment put back to a window whose watch had been cancelled is not watched.~~ **CLOSED by this repair.** | It was the blocking finding. |
| ~~`P9-D66`~~ | **CLOSED by the third review's repair (§12).** ~~Over a tracking channel with no health reading, the watch that followed an appointment to a lapsed window is `INDETERMINATE`, which M8 can neither amend nor cancel.~~ Put BACK, the appointment keeps that watch as the stop's one live watch, on the deadline it was judged against: the restored window is not timed separately. Moved on to a window never used, it is watched there by a second live watch beside the first - the one case left where a stop has two. | Never quiet either way: the unverified follow-up stays on the stop until the truck arrives, and both collapse into the one carrier follow-up. Neither is new: the unrepaired tree timed the restored window no better and left one more such watch in each case. Whether a watch M8 has judged blind should be closable when its appointment moves is M8's question, not this spine's. |
| `P9-D67` | **STILL OPEN - explicitly not repaired in §12.** A truck checked in at the delivery stop with no delivery report is `QUIET` at a brokerage with no tracking cadence - including when a human overrules "delivered" by saying "at delivery". Nothing waits for the delivery to be reported. Older than this checkpoint. | The arrival obligation is met by standing evidence. How long a truck may sit at a dock before someone is asked is a tenant rule nobody has stated: **NEEDS VALIDATION**. With a cadence the tracking watch covers it. |
| ~~`P9-D68`~~ | **CLOSED by the third review's repair (§12).** ~~A source that restates, AFTER a human's decision, the status she overruled is fresh evidence:~~ a TMS row re-sent still saying `DELIVERED` makes the load delivered again and replaces the late-truck follow-up with a POD request, with no new dispute unless a current-state source contradicts it. Older than this checkpoint. | Not quiet and not billing-ready without a signed POD. It is the stated rule ("what was said before it, and only that"); whether a restatement by the same source is new evidence is a product question. |

## 12. Third independent review — 2026-10-07 — and its repair

### What the review found

The §11 repair held on everything it was reviewed against: the reproduction, ten generation
attacks and 1,914 randomized reschedule histories written by the reviewer, the original over-rule
path, `P9-D59`, replay and restart, two brokerages, authority, and no effect row. No defect was
found in it.

**BLOCKED** all the same, on three defects on the same seam. All three are older than `e1a84f5`
and behave identically on `9359798`:

> 1. **`P9-D68` - a restated claim undoes a human's decision.** 08:30 the system of record says
>    DELIVERED; 08:35 the provider says IN_TRANSIT; 09:00 Dana confirms IN_TRANSIT; 15:00 the
>    delivery window is missed and the late-truck follow-up opens; 16:00 the same row arrives as a
>    new version, still DELIVERED, with nothing new in it. The load read DELIVERED again, the
>    re-owed arrival watch was discharged, the follow-up was replaced by a POD request, and no
>    Conflict was raised. A driver texting "delivered" a second time did the same.
> 2. **New, unrecorded (`P9-D69`) - an appointment reported RESCHEDULED or CANCELLED keeps the
>    window it left.** The record says `RESCHEDULED 16:00-18:00`; the watch stayed on 13:00-15:00,
>    the truck was called provably late at 15:01 against a window nobody held, and 16:00-18:00 was
>    never timed. A CANCELLED appointment was still called late.
> 3. **`P9-D66` - a blind channel's judgment sets the deadline.** Over a tracking channel with no
>    health reading, the watch M8 had judged `INDETERMINATE` against a window the appointment then
>    left went on driving the work: an unverified chase due at the old time, and - when the
>    appointment was put back - no watch on the window that stood at all.

`P9-D67` (a truck at the receiver is quiet with no cadence) was classified safe debt. It is **not
repaired here** and is still open: how long a truck may sit at a dock before somebody is asked is a
rule nobody has stated, and it belongs to the delay/delivery iteration.

### The rule

**Current operational behaviour follows current freight reality.** Historical evidence and
historical Expectation generations stay on the record, exactly as they were. They do not go on
controlling the stage, the deadline, the work, quiet or billing readiness once the freight fact they
stood for has been rejected, superseded, moved or cancelled. The semantics below were stated by the
founder in the repair brief; the choices the brief left to the builder are listed under "Decisions".

### What was repaired

**1. A human's answer is not undone by a word** (`projection._apply_status_decisions`,
`detectors._tracking_conflicts`). A recorded human's decision still overrules every claim, about a
moment up to hers, of a later stage than she confirmed. What is said of a later stage AFTER she
decided is now treated by what it is:

| What arrives after her decision | Before | Now |
|---|---|---|
| The source she overruled says the same thing again, having said nothing else in between - a re-sent row, a new version with no new freight fact, the same text typed twice - **while the brokerage is still waiting for the truck at the stop the claim is about** | Stood. The load was DELIVERED again and the late work was discharged | **Overruled by the same decision**, silently: it was answered when she answered the first one. It is still on the record (`overruled_by`). Nothing owed changes, and the watch that is still owed will find the truth out |
| The same repeat **where nothing is waiting** - the truck is already at that stop by standing evidence, or this brokerage watches no arrivals at all | Stood | **Contests her decision**, like any other bare claim: a question, never silence. Dropped unasked it would have been a delivery report on a QUIET load |
| A bare claim that is NEW - another source, or the same one after it had said something different | Stood, silently | **Contests her decision** (`TrackingEvent.contests`): it does not stand, and a new Conflict is raised with her own decision as a party. The load is DISPUTED and hers to decide; until she does, the delivery is still watched and still called late |
| The tracking provider's own reading puts the truck past where she said it was | Stood | Stands - and every claim made from that reading on is believed as it always was. Nobody is asked to approve a real delivery because the truck was moving earlier |
| The same record again (same id), or the same statement under a new id about the same moment | Inert / overruled | Unchanged |

A claim that does not stand also answers no tracking watch and starts no tracking clock
(`detectors._tracking_expectations`, `_discharges`): the row she overruled, sent again, is not the
truck being heard from.

**2. The appointment that stands sets the deadline** (`LoadView.arrival_deadline`,
`detectors._arrival_expectations`, `load_work._appointment_needs`).

| The appointment record says | Before | Now |
|---|---|---|
| `RESCHEDULED`, with a new window | Treated as "not confirmed": the watch stayed on the window it left | The new window is the time the truck is held to. The watch moves to it by amendment (or, if the old one was already missed, the missed watch is cancelled and a new one raised). Verifying the unconfirmed window is still work, and says what it is: `APPOINTMENT_RESCHEDULED` |
| `CANCELLED` | The watch stayed live and went overdue | The watch is withdrawn (`CANCELLED` in M8, retained). Nothing is raised in its place. The stop has no appointment anyone holds: `APPOINTMENT_CANCELLED`, the existing verify-appointment work. Never quiet |
| `REQUESTED` | Raises nothing, moves nothing | **Unchanged**, as the brief required (`P9-D70`) |

**3. A blind channel does not set the deadline** (`LoadView.superseded_expectations`,
`operative_expectations`, `detectors._owed_again_id`, `load_work._expectation_needs`). M8 is
untouched: it still will not amend or cancel an `INDETERMINATE` Expectation, and nothing here makes
it. That row stays exactly as M8 ruled it - owned, with its Exception - until the truck arrives.
What changed is what reads it:

| Question | Before | Now |
|---|---|---|
| Is a watch M8 judged blind, on a window the appointment has left, the stop's watch? | Yes: put back, it stood in for the watch that was owed | No. It is history about a window. The appointment that stands is watched by a row whose deadline is its own (the next generation of the same id) |
| Does it drive the work? | Yes: an unverified chase, due at the old time | No. Current work is read from `operative_expectations`. Its Exception is listed with the others whose cause is gone - housekeeping, exactly as the Exception of a cancelled overdue watch is over a healthy channel |
| What does channel health still decide? | - | Whether a missed appointment is `OVERDUE` or `UNVERIFIED`. Only that |

### A safety surface was touched

The audit oracle (`eval/freight_corpus/work_attack.py::audit_state`) used to require every owed
Expectation to be behind some need - that is its silent-stall check. It now leaves out one kind of
row: an arrival watch M8 judged `INDETERMINATE` against a window the appointment has left
(`watches_a_window_that_is_gone`, read from the appointment itself, not from the code under test).
**That narrows a guard.** In its place the oracle fails any need that DOES rest on such a row, and
`_doubly_watched_stops` fails any movable watch left live on a window that is gone. Both are seen to
fire in anti-vacuity tests, and the mutants that put the stale row back behind the work are caught.
Taken as tier 1 for that reason: one focused independent review, before merge.

### Decisions made in this repair

Each of these is a choice. None is a design-partner observation.

| Decision | Why |
|---|---|
| **Only the tracking provider's own position reading shows that the truck moved on.** A driver's text, a carrier's email and a system-of-record status are bare claims | The brief names "valid AT_DELIVERY tracking" as real later evidence, and it is the one signal that is a reading rather than somebody's word. One such reading is taken at face value (`P9-D74`) |
| **A signed POD is not evidence that the truck moved on** | A POD satisfies the document requirement and reports no delivery (CD-8); nothing in the spine treats it otherwise, and the brief limited this to "existing POD semantics". A POD beside a restated or contested claim advances nothing until a human confirms or the provider reads the truck there (`P9-D72`) |
| **A restatement is the same source, the same status, and nothing else said in between** | The narrowest reading. A restatement is defeated SILENTLY, so anything wider would drop real information unasked; a source that changed its statement and then says it again is asking anew |
| **A restatement is dropped silently only where the truck is still being asked about** | Found by attacking the first version of this repair, which dropped every repeat. With the truck at the receiver by her own word and no cadence, nothing is owed (`P9-D67`); the same driver's second "delivered" was then discarded onto a quiet load, and the unrepaired tree would at least have asked for a POD. So does a brokerage that watches no arrivals. Silence is safe only while an owed watch will expose the truth; elsewhere the repeat is a dispute. It costs a human touch there, and it is never a false quiet |
| **A reading lifts her decision for claims made at or after it, never before** | Otherwise a truck that reached the receiver at 13:30 would make a 10:00 restatement true, and a dispute that never was would be put to a human |
| **A RESCHEDULED window that nobody confirmed is watched AND still to be verified** | The brief: the new window "must be watched", and an existing "not yet confirmed" distinction is preserved. Two reason codes were added on the existing need kind; no new kind, action or state |
| **A superseded blind watch is not a need, and its Exception is housekeeping** | Parity with the healthy channel, where the missed watch is cancelled and its Exception awaits a human's closure. No M8 row is changed |

### What proves it

| Check | Result | What it could have caught |
|---|---|---|
| The review's three reproductions, as tests | **Before:** DELIVERED and `REQUEST_POD`; late at 15:01 against 13:00-15:00; an unverified chase due 11:00 with no watch on 13:00-15:00. **After:** `IN_TRANSIT`, the late-truck follow-up unchanged, one resolved Conflict; nothing late at 15:01, the miss called at 18:01; `ARRIVAL_PENDING` due 15:00 and the miss shown `UNVERIFIED` at 15:01 | The three defects |
| `P9-D68`, the eight required cases and more | Restated after the window was missed and before it; the same record again; the same statement under a new id; the same source three times; another source's bare claim (a dispute, answered either way); a source that changed its mind and says it again; a repeat with the truck already at the receiver, and at a brokerage that watches no arrivals (a dispute, not silence); a real delivery after a provider reading, from three source combinations; a restatement made BEFORE the truck moved on; a POD alone; a contradiction after real progress; with a tracking cadence | A fix that ignores everything after her decision, or that trusts arrival order |
| The appointment record | RESCHEDULED later, earlier, three times, after each window was missed, to a window already closed, then CONFIRMED; CANCELLED while ahead and after it was missed; a truck that had already arrived; every record twice; a brokerage that watches no arrivals | A stale window timing the truck, a second watch, or a watch on nothing |
| A blind channel, in every state the vocabulary has | No reading, `DOWN`, `UNKNOWN`, `PARTIAL` - discovered from `COVERAGE_HEALTH`, not listed. Put back; moved on; three times; moved on and back onto the window the blind row is on; arrival inside the new window and after it; cancelled; looked at five more times; replayed, restarted, every record twice | A stale deadline behind any need; a missed current appointment that cannot surface |
| Two brokerages, one load number | The same records at both; Northline's Dana decides and its appointment is rescheduled, nobody at Cedar Ridge decides anything. Northline's claims are overruled and its watch moves; Cedar Ridge's stand, its pictures and rows are those of running alone, and no id is shared | A decision or a reschedule reaching next door |
| Parity with a healthy channel | A blind reschedule followed by an arrival ends quiet and billing-ready with exactly the housekeeping the same load leaves over a healthy channel, one carrier follow-up at most, and no human question | Duplicate operator or human work |
| Thirty-nine new tests in `test_p9_load_loop.py` | all pass. Run against the unrepaired logic (`projection`, `detectors`, `load_work`, `load_loop` as of `e1a84f5`), 33 FAIL: 32 because the behaviour is wrong, 1 because it asks a method the repair added. The other 6 pin what already held and must keep holding: the same record again, the same statement under a new id, a real later delivery, a contradiction after it, a truck that had already arrived, and the blind population. None of the 53 tests that were already there fails on the unrepaired logic under the tightened oracles | - |
| Three checks added to `audit_state`, run on EVERY evaluation of every loop test, corpus load and hostile mutant | **current deadline** - no need rests on an arrival watch for a window the appointment has left; **human decision** - no bare claim stands beyond a recorded human's answer without a provider reading, and no claim made after her answer is dropped unasked onto a quiet load. 0 findings; each seen to fire in an anti-vacuity test | A stale deadline or a resurrected claim in any history, not only the ones written for it |
| The oracles `_unwatched_stops` and `_doubly_watched_stops` | Kept, and tightened: a stop is watched only by a live watch on the window that STANDS; a movable watch left live on a window the appointment has left is a finding | The repair hiding behind an oracle that counts any live row |
| Attacks outside the suite, each judged at every evaluation by the reviewer's own oracle and by `audit_state` | 2,184 seeded randomized histories on the final code (36,236 evaluations): a recorded human and the system of record moving the appointment among four windows as CONFIRMED, RESCHEDULED, CANCELLED or REQUESTED; redelivered records; arrivals; delivery reports made and made again by the system of record and the driver; human status decisions; PODs. A third of the mixed run over a blind channel in each of its four states and a quarter with a tracking cadence, plus 729 blind-only. 0 findings. The reviewer's scripted histories for all three defects re-run on the repaired tree: 0 findings. Replay, restart after every record, every record twice and the whole inbox again: 116 comparisons, all identical | - |
| `run_freight_corpus.py --loop`, the work corpus, the base corpus | Every figure unchanged: 425 records, 4,802 evaluations, 331 moments, 513 labeled checks, 0 failed, 0 audit findings; work corpus 278 checks, 1,227 evaluations (the 1,284 in §11 was a misstatement of the same figure); base corpus 262 labeled expectations, 0 failed | The repair changing a load it had no business changing |
| The hostile layers | `--loop --attack` 393 mutants, 8,153 evaluations, 0 findings; `--attack` 164 mutants, 1,719 evaluations, 0 findings - now including the three new checks | - |
| Mutation | twenty mutants added to `scripts/mutate_p9_load_work.py`, and six whose anchors the repair moved re-pointed at the same defects; all 102 mutants of the battery turn their named guard RED. Run on a complete copy of the working tree, never in it; the copy differs from what was committed only by a two-line comment in `model.py` and by this record | A guard that cannot fail |
| The seven P9 and ships-dark test files | 289 passed (250 before this repair, and the thirty-nine new tests) | - |
| Effect and authority ledgers | 0 rows in every run | - |

**Rollback:** revert the repair commit. Nothing on a live path reaches any of it.

### Debt recorded by the review and the repair

| ID | Debt | Why it does not block |
|---|---|---|
| ~~`P9-D66`~~ | **CLOSED by this repair.** | - |
| `P9-D67` | **STILL OPEN.** A truck with a standing arrival at the receiver and no delivery report is `QUIET` at a brokerage with no tracking cadence. One way in is worth naming, because §12 leaves it exactly where it was: the system of record said DELIVERED early, a human overruled it, the truck then really arrives - and the row, which already says DELIVERED, is never sent again. | Not part of this repair, by the founder's direction. The arrival obligation is met; the missing decision is how long ARRIVED-but-not-DELIVERED is tolerated before a dwell follow-up starts. **NEEDS VALIDATION.** |
| ~~`P9-D68`~~ | **CLOSED by this repair.** | - |
| ~~`P9-D69`~~ | **CLOSED by this repair.** An appointment reported RESCHEDULED or CANCELLED kept the watch of the window it left. | It was a blocking finding. |
| `P9-D70` | An appointment that goes from CONFIRMED to `REQUESTED` (with or without a new window) keeps the watch of the last confirmed window, which can then go overdue. | Unchanged on purpose: the brief excluded REQUESTED semantics. Whether a requested change withdraws the confirmed time is a freight rule nobody has stated. **NEEDS VALIDATION.** Never quiet: the unconfirmed appointment is work. |
| `P9-D71` | After a recorded human has confirmed an appointment, a later system record that says `CANCELLED` (or `RESCHEDULED`) with the SAME window is not applied and nobody is asked: her confirmation stands (`OWNER_ASSERTED` is not overwritten) and an appointment's status is not a field two sources can dispute. A different window IS a Conflict. | Over-asking, never silence: the watch she confirmed runs on. Making an appointment's status disputable changes how every status disagreement is read; it is a product decision, not this repair. |
| `P9-D72` | A signed POD is not evidence that the truck moved on. Beside a restated claim it advances nothing; beside a new bare claim the dispute stays hers. | Not quiet and not billing-ready in either case, and a human's confirmation or a provider reading closes it. Whether a POD should itself advance a load a human held in transit is a product question. |
| `P9-D73` | While two systems dispute an appointment's window (no human has decided), the watch stays on the window it had and can go overdue against it. | The dispute is a human's open question, first in the picture. What a disputed window should do to its watch is undecided. |
| `P9-D74` | One provider reading past where she said the truck was lifts her decision for everything said after it. A false reading would let a restatement stand. | The brief names a valid provider reading as real evidence. A later reading of an earlier stage against another source's claim is already a new dispute. |
| `P9-D75` | After a human's status decision, at a brokerage with no provider readings, every later bare claim of progress is a dispute and costs a human touch - and so is a repeat by the source she overruled, once nothing else is asking about that stop. | It is the stated rule: a bare word does not replace her answer. Over-asking, never silence. Whether some bare claims should be believed after a time is tenant policy. |
| `P9-D76` | When the claim that answered an arrival watch is overruled, other evidence still stands, and the appointment is then moved to a window never used that has already closed, one extra cured Exception is left. Found by the third review; older than this checkpoint. | Housekeeping only: no need, no proposal, no question. |
