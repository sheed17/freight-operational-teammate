"""Portfolio demo — a disputed delivery, settled by a human, and still watched afterwards.

    .venv/bin/python docs/portfolio/demo/disputed_delivery.py            # the story, moment by moment
    .venv/bin/python docs/portfolio/demo/disputed_delivery.py --detail   # every moment in full

A driver texts "delivered" before the receiver's window has even opened. Five minutes later the
tracking provider puts the truck on the interstate. Neyma does not pick a winner: it raises a
Conflict and asks a named human. Dana calls the receiver and says the load is still IN TRANSIT.

What has to be true afterwards is the point of the demo. The driver's claim had already answered
the delivery appointment's arrival watch, so overruling him must make that watch OWED AGAIN - or
the load reads "quiet, nothing to do" while a truck misses its appointment. Here the window closes
in silence, the missed delivery becomes work, and when the truck really arrives the load closes out.

THIS FILE ADDS NO PRODUCT BEHAVIOUR. It composes the existing synthetic-corpus builders
(`eval/freight_corpus`) with the existing loop runner (`freight_domain/load_loop.py`), exactly as
`eval/tests/test_p9_load_loop.py::test_an_overruled_delivery_claim_stops_answering_the_delivery_watch`
does, and prints what the runner already renders. It reads no network, calls no model, sends
nothing, and writes only to a throwaway SQLite file in a temporary directory.

SYNTHETIC. Every company, person, load number and sentence here is invented development input.
"""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for entry in (str(ROOT / "src"), str(ROOT / "eval")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_corpus.builders import says  # noqa: E402
from freight_corpus.loop_histories import Load, _builder  # noqa: E402
from freight_corpus.parties import NORTHLINE, SETUPS  # noqa: E402
from freight_corpus.work_attack import audit_state  # noqa: E402
from freight_recon.freight_domain.load_loop import (  # noqa: E402
    render_moment,
    render_trace,
    run_load_loop,
)
from freight_recon.workflow import WorkflowStore  # noqa: E402

LOAD_NUMBER = "LD-59001"
#: The moments worth reading in full, in the order they happen.
KEY_MOMENTS = ("driver-says-delivered", "provider-says-moving", "dana-says-moving", "pod")


def build_history():
    """One load at a brokerage with an arrival watch and NO tracking cadence, so nothing but the
    delivery appointment itself stands between this load and silence."""
    h = _builder("DEMO", "Bloomington to Toledo: delivered, says the driver", "2026-09-01",
                 "contradictory_tracking")
    load = Load(h, LOAD_NUMBER, customer="great_lakes_bev", carrier="summit", sell=172000,
                buy=141000, serial="79001", pickup="Great Lakes Beverage Bloomington",
                delivery="Maumee Distributing", delivery_zone="America/New_York")
    load.book()
    load.track("at-pickup", h.t("10:10"), "AT_PICKUP", "S1")
    load.track("loaded", h.t("11:00"), "LOADED", "S1")
    load.pings(("14:30", 0), ("18:00", 0), ("21:30", 0), ("01:00", 1), ("04:30", 1))
    # 07:30 Central: the receiver's 09:00-11:00 Eastern window has not opened yet.
    load.sms("driver-says-delivered", h.t("07:30", 1), "delivered, empty", says("DELIVERED", "S2"))
    load.track("provider-says-moving", h.t("07:35", 1), "IN_TRANSIT", position="I-75 N")
    h.human("dana-says-moving", h.t("08:00", 1), "dana.ortiz", "confirm_movement_status",
            refs=load.refs, status="IN_TRANSIT", note="receiver has not seen him")
    # Nothing arrives while the delivery window closes. The loop looks again on its own.
    load.track("at-delivery", h.t("13:30", 1), "AT_DELIVERY", "S2")
    load.delivered("delivered", h.t("14:00", 1))
    load.pod("pod", h.t("14:30", 1))
    h.clock("end", h.t("18:00", 1))
    return h.build({})


def main() -> int:
    parser = argparse.ArgumentParser(
        description="A disputed delivery, settled by a human, and still watched afterwards.")
    parser.add_argument("--detail", action="store_true", help="print every moment in full")
    args = parser.parse_args()

    history = build_history()
    with tempfile.TemporaryDirectory(prefix="neyma-portfolio-demo-") as scratch:
        store = WorkflowStore(Path(scratch) / "demo.db", tenant=history.tenant)
        try:
            result = run_load_loop(
                store.conn, SETUPS, [history],
                audit=lambda state, view, tenant: audit_state(state, view, tenant=tenant))
            story = result.story(NORTHLINE, LOAD_NUMBER)
            view = result.intakes[NORTHLINE].projection().loads[story.load_id]
        finally:
            store.close()

    print("THE LOAD THROUGH TIME  (one line per moment; a `tick` is a deadline passing in silence)")
    print(render_trace(story))
    print()
    for moment in story.moments:
        if args.detail or moment.trigger in KEY_MOMENTS or moment.trigger_kind == "tick":
            print(render_moment(moment, detail=True))
            print()

    watches = [e for e in view.expectations if e["expected_type"] == "arrival:S2"]
    overruled = [t for t in view.tracking if t.overruled_by]
    disputes = [c for c in view.conflicts if c["field"] == "tracking_status"]
    # THE PROPERTY THE DEMO IS ABOUT: from the human's decision until a truck is really at the
    # dock, the delivery is owed - so no moment in between may call the load quiet.
    decided, arrived = story.at("dana-says-moving"), story.at("at-delivery")
    falsely_quiet = [m.trigger for m in story.moments
                     if m.quiet and decided.index <= m.index < arrived.index]
    metrics = result.report["metrics"]
    print("WHAT THE CANONICAL RECORD HOLDS AT THE END")
    print(f"  delivery-arrival watches on this stop   {[e['state'] for e in watches]}"
          "   (the first was answered by the driver's claim; the second was owed again)")
    print(f"  claims a human overruled, still on file {[(t.value('signal'), t.value('status')) for t in overruled]}")
    print(f"  tracking disputes                       {[(c['state'], len(c['parties'])) for c in disputes]}"
          "   (state, parties kept)")
    print(f"  quiet while the delivery was still owed {falsely_quiet}"
          "   (must be empty: this is the false QUIET)")
    print(f"  external-effect rows written            {metrics['external_effect_rows']}")
    print(f"  cross-tenant mapping violations         {metrics['wrong_cross_tenant_mappings']}")
    print(f"  audit findings (independent oracle)     {len(result.findings)}")
    failed = bool(result.findings or falsely_quiet or metrics["external_effect_rows"]
                  or metrics["wrong_cross_tenant_mappings"])
    print("\nRESULT: " + ("FAILED - the run broke one of the properties above" if failed
                          else "OK - the delivery stayed watched and nothing left the building"))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
