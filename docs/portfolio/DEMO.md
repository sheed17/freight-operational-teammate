# Demonstration

Two reproducible demonstrations, both on synthetic data, both offline. Neither calls a model, opens
a socket, sends a message or writes anything except a throwaway SQLite file in a temporary
directory.

| | Demo 1 — the disputed delivery | Demo 2 — the appointment that moved |
|---|---|---|
| Command | `.venv/bin/python docs/portfolio/demo/disputed_delivery.py` | `.venv/bin/python scripts/run_freight_corpus.py --loop --load LD-50015 --detail` |
| Runtime | under a second | a few seconds (runs all 21 corpus loads, prints one) |
| Shows | conflict, human authority, an obligation that survives being overruled, a missed deadline detected in silence | a carrier's claim cannot move an appointment; a human's can; the deadline follows the window that stands |

Setup is the [quick start](../../README.md#quick-start) in the README: a virtualenv and
`pip install -e ".[dev]"`. No API key is needed.

---

## Demo 1 — a driver says DELIVERED, tracking disagrees, a human settles it

```bash
.venv/bin/python docs/portfolio/demo/disputed_delivery.py            # the story, moment by moment
.venv/bin/python docs/portfolio/demo/disputed_delivery.py --detail   # every moment in full
```

[`disputed_delivery.py`](demo/disputed_delivery.py) adds no product behaviour. It builds one
synthetic load with the existing corpus builders and hands it to the existing loop runner
(`freight_domain/load_loop.py`) — the same composition the regression test
`test_an_overruled_delivery_claim_stops_answering_the_delivery_watch` uses — then prints what the
runner already renders. The full captured output is in
[`demo/expected_output.txt`](demo/expected_output.txt); two runs are byte-identical.

### The situation

Load `LD-59001`, Bloomington to Toledo, for a brokerage that watches delivery appointments but has
**no tracking cadence configured**. That matters: nothing except the appointment itself stands
between this load and silence. The receiver's window is 09:00–11:00 Eastern (13:00–15:00 UTC).

### Expected output, and what each moment means

One line per moment. Columns: time (UTC), what arrived, stage, posture, customer-billing-ready,
human touches so far, next step. The excerpts in this document condense column spacing, shorten
the deadline label and trim the trailing list of open needs; the detail blocks are verbatim apart
from line wrapping. The unedited capture is [`demo/expected_output.txt`](demo/expected_output.txt).

```text
  09-02T09:30 ping-1-0430             IN_TRANSIT WAIT            bill=no  touch=0 WAIT
  09-02T12:30 driver-says-delivered   DELIVERED  NEYMA_CAN_ACT   bill=no  touch=0 NEYMA:REQUEST_POD
  09-02T12:35 provider-says-moving    DISPUTED   HUMAN_ATTENTION bill=no  touch=1 HUMAN:EVIDENCE_CONFLICT
  09-02T13:00 dana-says-moving        IN_TRANSIT WAIT            bill=no  touch=1 WAIT
 ~09-02T15:01 deadline@...15:01       IN_TRANSIT NEYMA_CAN_ACT   bill=no  touch=1 NEYMA:REQUEST_CARRIER_STATUS
  09-02T18:30 at-delivery             IN_TRANSIT QUIET           bill=no  touch=1 NOTHING
  09-02T19:00 delivered               DELIVERED  NEYMA_CAN_ACT   bill=no  touch=1 NEYMA:REQUEST_POD
  09-02T19:30 pod                     DELIVERED  QUIET           bill=yes touch=1 NOTHING
```

**12:30 — the driver texts "delivered, empty".** One source, uncontradicted, so the stage becomes
`DELIVERED`, the arrival watch on the delivery stop is discharged by his record, and a POD is now
owed. Neyma *would* ask the carrier for it:

```text
 7 Neyma would   REQUEST_POD -> carrier (Summit Line Freight)
                 DRAFT, NOT SENT: Load LD-59001 is reported delivered at Maumee Distributing. Please send
                 the signed proof of delivery, all pages, so the load can be closed out.
```

**12:35 — the tracking provider reports the truck moving.** Two sources now disagree about one
field. Neyma does not prefer the newer one, the "more reliable" one or the more confident one. It
raises a Conflict and puts a question in front of the load's accountable human, with the evidence:

```text
 3 changed       STAGE DISPUTED (DELIVERED -> DISPUTED); OPENED EVIDENCE_CONFLICT (OPEN/HUMAN_REQUIRED)
 8 needs a human EVIDENCE_CONFLICT -> dana.ortiz
 9 why           EVIDENCE_CONFLICT: Movement sources contradict each other about where the freight is.
                 asks dana.ortiz: Which statement is right?
                 evidence ev-2c05da36ae5a conflict: CLAIM_VS_OBSERVATION on brokerage_load.tracking_status
                 evidence ev-131e7f65de22 observation: MODEL_EXTRACTED says DELIVERED
                 evidence ev-769a2722a56a observation: SYSTEM_IMPORTED says IN_TRANSIT
```

Note the provenance tags: the driver's text was *read* (`MODEL_EXTRACTED`), the provider's ping was
*imported* (`SYSTEM_IMPORTED`). Neither can settle the dispute.

**13:00 — Dana records that the load is in transit.** Her act is `OWNER_ASSERTED` and resolves the
Conflict through the Conflict machine's own resolve-by-human transition. Four things follow in one
step:

```text
 3 changed       STAGE IN_TRANSIT (DISPUTED -> IN_TRANSIT);
                 OPENED ARRIVAL_PENDING (PENDING/DETERMINISTIC due 2026-09-02T15:00:00.000Z);
                 CLOSED EVIDENCE_CONFLICT (RESOLVED); CLOSED DOCUMENT_REQUIRED (SUPERSEDED);
                 HUMAN_ACT human (0 -> 1)
 6 waiting for   ARRIVAL_PENDING until 2026-09-02T15:00:00.000Z
12 quiet         no
```

The premature POD request is withdrawn, and — the point of the demo — **the delivery is watched
again**, against the appointment's real deadline.

**15:01 — the window closes and nothing arrives.** No record triggered this line. The loop looked
again because a deadline it was holding had passed:

```text
--- 2026-09-02T15:01:00.000Z  after deadline@2026-09-02T15:01:00.000Z  (a deadline passed; nothing arrived)
 3 changed       OPENED CARRIER_STATUS_OVERDUE (OVERDUE/NEYMA_ACTION_CANDIDATE due 2026-09-02T15:00:00.000Z);
                 CLOSED ARRIVAL_PENDING (SUPERSEDED)
 7 Neyma would   REQUEST_CARRIER_STATUS -> carrier (Summit Line Freight)
                 DRAFT, NOT SENT: Load LD-59001: we have not had the update we expected. Where is the truck
                 now, and what is the current ETA to the next stop?
```

**18:30–19:30 — the truck really arrives, late; the TMS says delivered; the POD comes in.** The
second watch is discharged by the *real* arrival, the load becomes billing-ready and quiet. One
human touch, total.

### What the canonical record holds at the end

```text
  delivery-arrival watches on this stop   ['DISCHARGED', 'DISCHARGED']
  claims a human overruled, still on file [('driver_assertion', 'DELIVERED')]
  tracking disputes                       [('RESOLVED_BY_HUMAN', 2)]
  quiet while the delivery was still owed []
  external-effect rows written            0
  cross-tenant mapping violations         0
  audit findings (independent oracle)     0

RESULT: OK - the delivery stayed watched and nothing left the building
```

Nothing was rewritten to get there. The driver's claim is still on the load, marked overruled. The
watch it answered is still discharged by his record. The watch that was owed is a second row. The
dispute keeps both parties. The script exits non-zero if any of these properties breaks.

### The same script, on the code before the fix

This scenario is a real defect the project shipped and then repaired
([case study](CASE_STUDY.md)). To see the broken behaviour without touching your checkout, export
the earlier commit to a temporary directory and run the same script there:

```bash
mkdir -p "$TMPDIR/neyma-before" && git archive ee9f6b8 | tar -x -C "$TMPDIR/neyma-before"
mkdir -p "$TMPDIR/neyma-before/docs/portfolio/demo"
cp docs/portfolio/demo/disputed_delivery.py "$TMPDIR/neyma-before/docs/portfolio/demo/"
(cd "$TMPDIR/neyma-before" && "$OLDPWD/.venv/bin/python" docs/portfolio/demo/disputed_delivery.py)
```

Actual output on `ee9f6b8` (exit status 1):

```text
  09-02T12:35 provider-says-moving    DISPUTED   HUMAN_ATTENTION bill=no  touch=1 HUMAN:EVIDENCE_CONFLICT
  09-02T13:00 dana-says-moving        IN_TRANSIT QUIET           bill=no  touch=1 NOTHING
  09-02T18:30 at-delivery             IN_TRANSIT QUIET           bill=no  touch=1 NOTHING

  delivery-arrival watches on this stop   ['DISCHARGED']
  quiet while the delivery was still owed ['dana-says-moving']

RESULT: FAILED - the run broke one of the properties above
```

At 13:00 the load is `QUIET`, next step `NOTHING`. There is no 15:01 line at all: the appointment
is missed and nobody is told.

### An honest edge in the "after" output

At 18:30 the truck is at the dock, the delivery has not been reported, and the load reads `QUIET`.
That is by design rather than an oversight: this brokerage configured no unload or dwell clock,
and Neyma never invents a deadline nobody chose. It is also exactly the kind of rule that would
need validating with a real brokerage before anyone relied on it.

---

## Demo 2 — the receiver pushed the appointment

```bash
.venv/bin/python scripts/run_freight_corpus.py --loop --load LD-50015            # one line per moment
.venv/bin/python scripts/run_freight_corpus.py --loop --load LD-50015 --detail   # in full
```

Load `LD-50015` is confirmed for 09:00–11:00. The carrier emails *"Receiver pushed us to 2
tomorrow."*

```text
  08-16T20:00 receiver-pushed         IN_TRANSIT HUMAN_ATTENTION bill=no  touch=1 HUMAN:EVIDENCE_CONFLICT
  08-16T20:40 dana-confirms-window    IN_TRANSIT WAIT            bill=no  touch=1 WAIT
  ...
  08-17T16:30 ping-1-1130             IN_TRANSIT WAIT            bill=no  touch=1 WAIT
  08-17T18:20 at-delivery             IN_TRANSIT WAIT            bill=no  touch=1 WAIT
  08-17T19:10 delivered               DELIVERED  NEYMA_CAN_ACT   bill=no  touch=1 NEYMA:REQUEST_POD
  08-17T19:40 pod                     DELIVERED  QUIET           bill=yes touch=1 NOTHING
```

- A carrier's sentence does not move an appointment. It conflicts with the confirmed window, and
  the question goes to a human.
- Dana confirms 14:00–16:00 with the receiver. The arrival watch **moves with the appointment**.
- The original 11:00 deadline passes with the truck still rolling, and nothing fires. The truck
  arrives at 14:20 local and is on time.

The harder variants — an appointment moved earlier, missed there and put back; rescheduled while
the tracking channel was blind; edited in the TMS and reverted — were each a real false-quiet
defect. They are pinned by regression tests rather than by a CLI story:

```bash
.venv/bin/python -m pytest eval/tests/test_p9_load_loop.py -q -k "appointment or resched or window"   # 30 tests
.venv/bin/python -m pytest eval/tests/test_p9_load_loop.py -q -k "overrul or says_it_has_not_delivered" # 10 tests
```

## The whole corpus at once

```bash
.venv/bin/python scripts/run_freight_corpus.py --loop
```

Twenty-one complete synthetic loads across two brokerages — one clean, the rest late, silent,
contradicted, mis-papered, mis-billed or out of order — run side by side in one database. The
board shows where each stands, whether it is billing-ready, whether it is genuinely quiet and how
many human touches it has cost. On commit `8ee5bf6`: 425 records, 4,802 evaluations, 513 labeled
checks with 0 failed, 0 audit findings, 0 external-effect rows.

---

## Recording storyboard (about 90 seconds)

A terminal recording is the honest medium: there is no web UI for this layer, and none should be
implied.

| # | Time | On screen | Say or caption |
|---|---|---|---|
| 1 | 0:00 | README title and the one-sentence description | "Freight runs on messages that contradict each other. This is what happens when one of them is wrong." |
| 2 | 0:08 | Run `disputed_delivery.py`; pause on the trace | "One load, moment by moment. Synthetic data, no network, no model call." |
| 3 | 0:18 | Highlight the 12:30 and 12:35 lines | "The driver says delivered. Tracking says he is still on the interstate. The stage becomes DISPUTED." |
| 4 | 0:30 | Scroll to block 8–9 of the 12:35 moment | "It does not pick a winner. It asks a named person, and shows her both pieces of evidence and where each came from." |
| 5 | 0:42 | The 13:00 moment, line 3 `changed` | "She says in transit. The POD request is withdrawn and the delivery is watched again." |
| 6 | 0:54 | The `~15:01` line and the draft | "The window closes and nothing arrives. That silence is the event. The follow-up is a draft; nothing is sent." |
| 7 | 1:06 | The end-of-run summary | "Nothing was rewritten. His claim is still on file, overruled. Zero external effects." |
| 8 | 1:16 | Split: the pre-fix run printing `QUIET … NOTHING` at 13:00 | "On the earlier commit the same load went quiet here. That bug is the case study." |
| 9 | 1:26 | `pytest … -k overrul` passing, then the mutation battery summary | "It is pinned by regression tests, and by mutants that put the defect back and must be caught." |

## Captures worth making

- **Terminal recording** of Demo 1 with [asciinema](https://asciinema.org) or
  [vhs](https://github.com/charmbracelet/vhs). Use a wide terminal (about 170 columns) so trace
  lines do not wrap, or pipe through `cut -c1-110` for a narrow one.
- **Side-by-side still** of the 13:00 moment before and after the fix. Both outputs are real;
  the commands are above.
- **The board**, from `scripts/run_freight_corpus.py --loop`: 22 rows and the loop metrics fit one
  screen.
- **The architecture diagram** in the README renders on GitHub as-is; export it from there.
- **The earlier surface.** [`packet-page-ld560003.png`](../../packet-page-ld560003.png) is a real
  capture of the legacy review-packet page on synthetic data. Label it as the earlier surface, not
  as the UI of the load loop.

Do not mock up a dashboard for the load loop. It does not have one.
