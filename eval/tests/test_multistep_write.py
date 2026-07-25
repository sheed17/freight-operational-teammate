"""Tests for the multi-step gated write (wizard-shaped TMS flows), money bound at one sub-step."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.multistep_write import MultiStepInvoiceLedger, WriteSubStep  # noqa: E402
from freight_recon.tms_write import PayableWriteStatus  # noqa: E402


class FakeSession:
    """Records navigations and field sets; the error-flash check returns `error` (default none)."""

    def __init__(self, error=""):
        self.error = error
        self.nav = []
        self.sets = []      # (selector, value)
        self.clicks = []

    def navigate(self, url):
        self.nav.append(url)

    def evaluate(self, expression):
        if "alert-danger" in expression:
            return self.error
        if expression.startswith("(function(sel,val)"):
            # crude extraction of the json args for assertions
            import json
            args = expression[expression.index(")(") + 2: -1]
            sel, val = json.loads("[" + args + "]")
            self.sets.append((sel, val))
            return True
        if expression.startswith("(function(label)"):
            self.clicks.append(expression)
            return True
        return None


def _transporters_substeps():
    # order details -> line-item (amount here) -> raise invoice (the shape mapped on transporters.io)
    return [
        WriteSubStep(name="order details", url="https://t.test/orders/new",
                     set_values={"[name=customer]": "Acme Brokerage"}, submit_label="Save and continue"),
        WriteSubStep(name="line item", set_values={"[name=desc]": "Linehaul"},
                     amount_selector="[name=line_amount]", submit_label="Add"),
        WriteSubStep(name="raise invoice", url="https://t.test/finance/uninvoiced", submit_label="Raise"),
    ]


def _ledger(session, substeps=None, readback=lambda lid: {"amount": "4172.00"}):
    return MultiStepInvoiceLedger(
        session=session, substeps=substeps or _transporters_substeps(), readback_fn=readback,
        base_url="http://localhost",  # localhost: gate satisfied without acknowledgement
        settle_seconds=0,
    )


def test_multistep_runs_all_steps_in_order_and_binds_amount_once():
    s = FakeSession()
    res = _ledger(s).write_payable(run_id=1, load_id="LD-9", carrier="Acme", amount="4172.00", charges=None, key="k")
    assert res.status == PayableWriteStatus.WRITTEN
    assert s.nav == ["https://t.test/orders/new", "https://t.test/finance/uninvoiced"]  # 2 navs (middle step stays)
    # The approved amount was entered exactly once, at the line-item money selector.
    amount_sets = [(sel, val) for sel, val in s.sets if val == "4172.00"]
    assert amount_sets == [("[name=line_amount]", "4172.00")]
    assert len(s.clicks) == 3  # each sub-step submitted


def test_multistep_fails_closed_without_exactly_one_money_step():
    s = FakeSession()
    # zero money steps
    no_money = [WriteSubStep(name="a", set_values={"[name=x]": "1"})]
    r0 = _ledger(s, substeps=no_money).write_payable(run_id=1, load_id="L", carrier="C", amount="1", charges=None, key="k")
    assert r0.status == PayableWriteStatus.ADAPTER_FAILED and "exactly one money sub-step" in r0.note
    # two money steps
    two_money = [WriteSubStep(name="a", amount_selector="[name=a]"), WriteSubStep(name="b", amount_selector="[name=b]")]
    r2 = _ledger(s, substeps=two_money).write_payable(run_id=1, load_id="L", carrier="C", amount="1", charges=None, key="k")
    assert r2.status == PayableWriteStatus.ADAPTER_FAILED and "found 2" in r2.note


def test_multistep_fails_closed_on_a_sub_step_error():
    s = FakeSession(error="Customer can't be blank")
    res = _ledger(s).write_payable(run_id=1, load_id="L", carrier="C", amount="4172.00", charges=None, key="k")
    assert res.status == PayableWriteStatus.ADAPTER_FAILED
    assert "order details" in res.note and "Customer can't be blank" in res.note


def test_multistep_runs_per_substep_apply_hook():
    s = FakeSession()
    applied = {}
    steps = _transporters_substeps()
    steps[0].apply = lambda sess, ctx: applied.update({"carrier": ctx["carrier"], "amount": ctx["amount"]})
    res = _ledger(s, substeps=steps).write_payable(run_id=1, load_id="L", carrier="Acme", amount="4172.00", charges=None, key="k")
    assert res.status == PayableWriteStatus.WRITTEN
    assert applied == {"carrier": "Acme", "amount": "4172.00"}  # system-specific binding got run-time context


def test_get_payable_delegates_to_readback():
    assert _ledger(FakeSession()).get_payable("L") == {"amount": "4172.00"}
