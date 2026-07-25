"""Tests for the Brain<->money-path wiring: FILL_AND_SUBMIT only succeeds on a verified gated DONE."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.brain_runtime import build_gated_submit  # noqa: E402


class _Outcome:
    def __init__(self, verified, note="", final_state="DONE"):
        self.verified = verified
        self.note = note
        self.final_state = final_state


def _gated(*, approved="4172.00", outcome=None, build_ledger=None, enter_calls=None):
    def enter_fn(store, ledger, run_id, *, amount, on_status=None, ops_control=None):
        if enter_calls is not None:
            enter_calls.append({"amount": amount, "ledger": ledger})
        return outcome or _Outcome(True, "payable entered and verified by readback")
    return build_gated_submit(
        store=object(), run_id=1,
        build_ledger=build_ledger or (lambda ctx: ("LEDGER", ctx.get("form"), ctx.get("customer_id"))),
        enter_fn=enter_fn,
        approved_amount_fn=lambda store, rid: approved,
    )


def test_gated_submit_ok_only_on_verified_done():
    calls = []
    gs = _gated(outcome=_Outcome(True, "verified $4172.00"), enter_calls=calls)
    res = gs({"form": object(), "customer_id": "C1"})
    assert res.ok and "verified" in res.detail
    # The amount came from the approval, not the Brain/context.
    assert calls[0]["amount"] == "4172.00"


def test_gated_submit_fails_when_not_verified():
    gs = _gated(outcome=_Outcome(False, "readback mismatch; routed to review"))
    res = gs({"form": object(), "customer_id": "C1"})
    assert not res.ok and "readback mismatch" in res.detail


def test_gated_submit_refuses_without_approved_amount():
    calls = []
    gs = _gated(approved=None, enter_calls=calls)
    res = gs({"form": object(), "customer_id": "C1"})
    assert not res.ok and "no human-approved amount" in res.detail
    assert calls == []  # never reached the gated executor without an approval


def test_gated_submit_fails_closed_if_ledger_build_raises():
    def boom(ctx):
        raise RuntimeError("no discovered form")
    gs = _gated(build_ledger=boom)
    res = gs({})
    assert not res.ok and "could not build ledger" in res.detail
