# P9-CP-4 — the continuous load loop: complete loads, booked to customer billing-ready, in shadow

> **This is a builder's record, not a status.** Status is [`CURRENT.md`](CURRENT.md) and the registry.
> **Founder direction, 2026-10-06:** the formal P9 acceptance exercise is stopped, `c4376b9` is the P9
> product baseline, and the first continuous shadow freight operating loop is built on the freight
> spine now — pulling an entity, a rule or an act into the system only when the loop needs it.
> **P9 is not accepted, nothing is scored, and P10 is still `BLOCKED`.** This work accepted nothing,
> opened nothing and enabled nothing.
> **The corpus is synthetic development input.** Nothing here is a design-partner observation, no
> freight rule is validated by it, and no labor time was measured.
> **No independent review has been performed.** Tier-1 and tier-2 surfaces were touched (§5); one
> focused independent review is owed before merge ([`CLAUDE.md`](../../CLAUDE.md) §7).

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
| `P9-D54` | An arrival watch discharged by a claim a human later overrules is not restored. | The tracking cadence still catches silence, so the load is not quiet. A missed window on that stop would not be called late. |
| `P9-D55` | What changed is said against the previous picture, which the runner holds in memory. A real restart would report its first picture of each load with no changes. | The picture itself is a pure function of the canonical record and survives a restart identically. |
| `P9-D56` | The loop re-projects the whole brokerage at every record: 22 loads and 425 records take about 25 seconds. | Development scale (`P9-D38`). |
| `P9-D57` | An uncovered load is outside the loop: reported not quiet, and nothing says who should cover it. | The loop begins at booked, by direction. |
| `P9-D58` | The acceptance-contract work is parked, unmerged: the mapping store's lost-race fix, the three P9 batteries in CI, the reconciled review fields, the validation items raised by P9. | None is needed by a single-writer, ships-dark loop. Merging it will conflict here in the registry, `CURRENT.md` and the status guard. |

## 9. What is next

The three product failures to attack first are `P9-D49` (humans closing what Neyma already handled),
`P9-D50` (a carrier-side question nobody can close) and `P9-D51`/`P9-D53` together (a late load on
which Neyma asks the wrong party the wrong question, and nobody tells the receiver).
