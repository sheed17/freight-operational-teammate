# Technical case study

**Neyma: keeping an operational obligation alive when the evidence under it turns out to be wrong.**

This is written to be useful in an engineering interview. It covers the problem, why the obvious
AI approach does not survive it, the architecture and its costs, and one bug in depth — found by
review, reproduced on demand, fixed without rewriting history, and now pinned by tests that have
been seen to fail. Figures marked *verified* were reproduced for this document; see
[`METRICS.md`](METRICS.md).

---

## 1. The engineering challenge

A freight brokerage moves a load using a dozen channels that were never designed to agree: a TMS
row, a tracking feed, driver texts, dispatcher emails, PDFs, phone calls. Three properties of that
environment drive every design decision here.

1. **Sources contradict each other, routinely and innocently.** A driver hits "delivered" at the
   wrong stop. A tracking provider lags. The TMS row is edited and reverted. There is no source you
   can simply trust.
2. **The important events are the ones that do not happen.** The POD that never arrives, the check
   call nobody makes, the appointment window that closes with nobody at the dock. An event-driven
   system cannot react to an event that was never emitted.
3. **Mistakes cost money and are hard to undo.** Paying a carrier twice, billing a customer for a
   load that did not deliver, or telling a shipper something false all happen outside the system
   and stay happened.

The target was a system that holds one canonical picture of each load, knows what is owed and by
when, and puts each real decision in front of one accountable person — while being *structurally*
unable to act on the outside world without authority.

## 2. Why simplistic AI automation is insufficient

The obvious design is a loop: an LLM reads the inbox, decides what is going on, and calls tools.
It demos well. Each of these is a way it fails on real freight, and the mechanism this project
used instead:

| Naive approach | Failure | What was built |
|---|---|---|
| The model's reading *is* the state | A plausible misreading becomes a fact nobody can trace | A reading is a typed claim that must quote the words it came from; a grounding pass drops any item whose quote is not literally in the source. It enters the record as `MODEL_EXTRACTED`, never as truth. |
| Ask the model which source is right | It will always pick one, confidently | Disagreement becomes a Conflict that cannot be resolved by recency, confidence, a model or a clock — only by a recorded human act |
| React to messages as they arrive | Silence is invisible; nothing arrives to react *to* | Expectations are durable commitments with deadlines; the loop re-evaluates at every deadline, so a window closing in silence is its own event |
| Let the agent call tools | A retry acts twice; a prompt-injected "this charge is approved" is obeyed | A claimed approval is a fraud signal. Effects need an approval bound to exact facts, a fresh seven-check witness and a one-time grant claimed atomically. None of it is reachable from the model. |
| Keep conversation memory | Replay or restart changes the answer | State is a pure fold over durable records. Work has no row of its own; its identity is its cause, so asking twice creates nothing. |
| One prompt per customer | Two brokerages with the same load number bleed into each other | Tenant is first in every key and enforced by the database; the test corpus deliberately gives two brokerages identical identifiers in one database |

The summary an interviewer usually wants: **the model was confined to the one thing it is good at
— reading language — and everything that decides, schedules, reconciles or acts is deterministic
code with a test that can fail.** In the synthetic evaluation, 176 pieces of work were settled
with no model call at all and 110 were sent to one (*verified, replayed*).

## 3. Architecture and major trade-offs

The layers are described in the [architecture tour](ARCHITECTURE_TOUR.md). The decisions worth
defending, with what each cost:

| Decision | What it buys | What it costs |
|---|---|---|
| **State is a projection, not tables.** A load is recomputed from immutable observations on every read. | Replay is inert by construction. History is honest: a belief that was later corrected stays on the timeline where it was held. | Read cost grows with history and was never measured at volume. No per-entity freight tables to query. |
| **Detectors return intents; machines decide.** Freight logic proposes a Conflict or an Expectation; a separate state machine decides if it is new, a duplicate or illegal. | One conflict system and one expectation system, regardless of how many features want one. | Indirection. The case-study bug lived exactly in the seam between "what freight needs" and "what the machine will allow". |
| **Every threshold is configuration or absent.** No default deadline is invented for a brokerage that did not choose one. | The system never enforces a freight rule nobody decided. | Sparse configuration means sparse coverage. In the demo, a truck at the dock with no unload clock reads as quiet. |
| **Provenance is field-level and assigned by the runtime.** A record cannot state how much it can bear. | A model-inferred value physically cannot be read by a consequential gate. | Every fact drags its history; the model is heavier than a row of columns. |
| **Effect identity excludes the amount.** The Commit Key identifies the effect; the approved values are separate Material Facts. | Two approvals at different amounts for one invoice are one effect, not two payments. | Two concepts that are easy to conflate and must be defended by tests. |
| **Build the authority kernel before any feature that needs it, and ship it dark.** | When effects were eventually wired, the unsafe path would not exist. | Months of work a user cannot see. In hindsight this is the largest trade-off in the project: the safety machinery is far ahead of anything a customer could use, and customer discovery later paused the product. |
| **Process: written acceptance criteria, review by a session that did not build it, mutation proof for guards.** | Reviews caught real defects, including the one below. | Heavy. The repository's own history records a simplification pass that removed ceremony which had grown past its value. |

## 4. A difficult real bug: the false quiet

### What a broker would have seen

A driver texts "delivered". The tracking provider shows the truck still moving. Neyma flags the
contradiction and asks Dana. Dana calls the receiver and records that the load has **not**
delivered.

The load then reads `QUIET` — nothing waited for, nothing overdue, next step `NOTHING` — and stays
that way while the truck misses its delivery appointment. Nobody is told.

For a product whose entire promise is noticing what did not happen, that is the worst available
failure: silent, plausible, and triggered by a human doing exactly the right thing.

### Where it came from

It was introduced by a fix. The load loop had exposed that a tracking dispute stayed disputed
forever, because there was no act by which a human could settle one. Commit `ee9f6b8` added that
act, `confirm_movement_status`. Settling the dispute worked. What it did to the *obligation* did
not.

Three individually reasonable design facts combined:

1. **The driver's claim had already answered the watch.** When he said "delivered", the Expectation
   watching for arrival at the delivery stop was discharged by his record. Correct at the time.
2. **`DISCHARGED` is terminal in the Expectation machine.** It should be: that row is the permanent
   record that the watch was answered, by that record, at that time.
3. **A watch's id is derived from its cause** — this tenant, this load, this stop. That is what
   makes the system idempotent: raise it twice and you get one row.

So after Dana overruled the claim, the detector correctly concluded "a delivery watch is owed",
computed its id, found a row with that id already in a terminal state, and raised nothing. The
obligation was real and the system had no way to express it.

### Why it survived the original author

It was noticed and misjudged. The implementation record logged it as debt item `P9-D54` and
classified it non-blocking, on the reasoning that "the tracking cadence still catches silence". At
a brokerage configured to expect a tracking ping every few hours, that was true: the load was not
quiet, because a ping was owed.

The tracking cadence is optional per-brokerage configuration. The load loop's test corpus ran on a
brokerage setup that had one. At a brokerage without one, nothing stood between the load and
silence.

The review of `ee9f6b8`, performed by a session that had not written it, blocked the change on a
reachable reproduction at a no-cadence brokerage. The lesson is not subtle but it is easy to skip:
**a safety argument that depends on optional configuration is not a safety argument.**

### How it was reproduced

Two ways, both runnable today.

**As a story.** [`demo/disputed_delivery.py`](demo/disputed_delivery.py) builds the scenario from
the existing corpus builders. Run against an isolated export of the pre-fix commit (*verified*):

```text
  09-02T12:35 provider-says-moving    DISPUTED   HUMAN_ATTENTION bill=no  touch=1 HUMAN:EVIDENCE_CONFLICT
  09-02T13:00 dana-says-moving        IN_TRANSIT QUIET           bill=no  touch=1 NOTHING
  09-02T18:30 at-delivery             IN_TRANSIT QUIET           bill=no  touch=1 NOTHING

  delivery-arrival watches on this stop   ['DISCHARGED']
  quiet while the delivery was still owed ['dana-says-moving']
RESULT: FAILED - the run broke one of the properties above
```

And against the current commit:

```text
  09-02T13:00 dana-says-moving        IN_TRANSIT WAIT            bill=no  touch=1 WAIT
 ~09-02T15:01 deadline@...15:01       IN_TRANSIT NEYMA_CAN_ACT   bill=no  touch=1 NEYMA:REQUEST_CARRIER_STATUS

  delivery-arrival watches on this stop   ['DISCHARGED', 'DISCHARGED']
  quiet while the delivery was still owed []
RESULT: OK - the delivery stayed watched and nothing left the building
```

The commands are in [`DEMO.md`](DEMO.md#the-same-script-on-the-code-before-the-fix). They use
`git archive` into a temporary directory, so the checkout is never touched.

**As tests.** Running the fix commit's test file against the pre-fix source, in an isolated
export, gives **12 failed, 31 passed** (*verified*). The twelve are the new regressions; the
thirty-one are the tests that already existed, still green — which is the uncomfortable part.
The suite was passing the whole time.

### How it was fixed

The fix (`9359798`) rests on one distinction: **what a source said** versus **what currently
stands**.

- A claim a recorded human overruled stays on the load as what its source said. It is no longer
  evidence of where the truck has been. Everything that *concludes* something — arrival evidence,
  the load's stage, whether a stop was reached, what satisfied a watch — now reads
  `LoadView.standing_tracking()` rather than the raw list
  ([`projection.py`](../../src/freight_recon/freight_domain/projection.py)).
- A watch that the machine holds `DISCHARGED` while **nothing standing answers it** is owed again,
  raised as the next *generation* of the same id
  ([`detectors._owed_again_id`](../../src/freight_recon/freight_domain/detectors.py)).

What the fix deliberately does **not** do is the tempting thing: reopen the discharged row, or
make `DISCHARGED` non-terminal. The Expectation machine is untouched. At the end of the demo the
record holds two rows for that stop, both discharged — the first by the driver's claim, the second
by the real arrival — plus his claim marked overruled and the dispute with both parties. The
history of what was believed, and when, is intact.

A second defect on the same seam was fixed alongside it: a human act could carry a timestamp later
than the moment it was received, and because a decision settles what was said before it, a
future-dated decision silenced contradictions made after she acted. Such an act is now refused as
unparseable and held for a person.

### It was not one bug

The same shape — *a record that no longer described the freight went on controlling the work* —
surfaced twice more under review of each repair:

| Commit | The variant | The rule that fixed it |
|---|---|---|
| `9359798` | An overruled claim kept answering the delivery watch | Conclusions read standing evidence only; an unanswered watch is owed again as a new generation |
| `e1a84f5` | An appointment moved earlier, missed there and put back had **no** watch: it mapped to a cancelled row's id | The arrival obligation is asked of the *stop*, never of a row id. Terminal generations are skipped; a live watch on the standing deadline *is* the watch |
| `8ee5bf6` | The TMS re-sent an unchanged `DELIVERED` row and undid the human's answer; a rescheduled appointment kept timing the window it had left | A restatement by the overruled source stays overruled; a genuinely new claim contests her decision and is raised to her; the appointment that stands sets the deadline |

Across the three repairs the source change was modest — 6 files, about 460 lines added — while the
loop's test file grew from 30 test functions to 83 (*verified from the diffs*).

The general lesson: **the identity of an obligation is not the identity of the row that once
recorded it.** Stable, cause-derived ids give you idempotency for free and quietly assume a cause
is satisfied at most once. Freight violates that assumption whenever a human corrects the record.

### What protects it now

- **Regression tests** in
  [`eval/tests/test_p9_load_loop.py`](../../eval/tests/test_p9_load_loop.py): 92 collected tests,
  all passing (*verified*), including replay, restart, doubled-inbox and cross-tenant versions of
  the scenario.
- **Independent oracles on every evaluation**, not only at labeled moments. One re-derives "is this
  load falsely quiet?" from the canonical record; another, written without the detectors, asks
  whether any stop is unwatched; a third fails two live watches at one stop.
- **Mutants that put the defect back.** `scripts/mutate_p9_load_work.py` holds 102 hand-written
  mutants, each reintroducing one real defect and naming the test that must go red. **102 of 102
  caught** (*verified*, on an isolated export). Several are exactly this bug: an overruled claim
  that still counts as arrival evidence, a watch never owed again, a watch raised a third time.
- **Hostile input mutation.** 393 rewritten histories — late, never arriving, duplicated,
  reordered, restarted — produce 0 findings (*verified*).

One of those oracles had to be narrowed during the third repair. The commit says so plainly,
treats the change as high-risk, and adds mutants proving the replacement check can fire. That
habit — saying out loud when a guard was weakened, and proving the new one — is worth more than
the guard.

## 5. Remaining limitations

Stated as they are, because a portfolio piece that hides these is not credible.

- **No customer deployment.** Everything described here ran on synthetic data. The product was
  paused after customer discovery.
- **Unvalidated freight rules.** Several domain questions the code had to take a position on are
  recorded as open and were never answered by a real brokerage.
- **The last three repairs lack their separate review.** Each was written by the session that
  reviewed the previous one. The project's own rule says a fresh reviewer is owed; that review was
  not done before the pause.
- **"Independent review" was AI-agent sessions.** Separate sessions with no shared context, which
  did reject work — but not human third parties.
- **Shadow only, and never under load.** No concurrency testing of the loop, no production
  database run of this layer, no latency or volume figures.
- **Model evidence is thin.** A small, self-authored, replayed corpus on one model.
- **Recorded debt remains open**, including a known finding in the effect path (`RR-01`) that
  blocks ever enabling a live writer.
- **No interface.** A person answers questions in this system by way of fixture records.

## 6. Questions this prepares you for

**"Tell me about a hard bug."** Use section 4. The strongest version is ninety seconds: the
symptom in freight terms, the three reasonable facts that combined, why your own tests were green,
how a reviewer's no-cadence reproduction broke the argument, and the fix that kept the terminal
state terminal.

**"How do you make an LLM safe in a system that takes actions?"** Don't let it. Confine it to
typed, quoted interpretation; make provenance a property the runtime assigns; keep every decision
deterministic; and put effect authority behind something a model cannot construct.

**"How do you know your tests are any good?"** Because they have been seen to fail. Mutation
batteries reintroduce each real defect; oracles run on every evaluation; negative assertions prove
their population first. And say what the mutation number is not: targeted mutants, not a coverage
score.

**"What would you do differently?"** Talk to customers before building the safety kernel. The
engineering order was defensible; the product order was not, and discovery arrived after months of
infrastructure no user could see.

**"What is the weakest part?"** Everything about the real world: unvalidated rules, synthetic data,
no load, no users. The architecture is the strong part and it is unproven where it matters.

**"How much of this did you write?"** Answer precisely. See
[`CAREER_NOTES.md`](CAREER_NOTES.md#describing-your-role-accurately).
