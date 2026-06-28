"""Tests for the agent-discovered, system-agnostic invoice ledger."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.discovered_write import DiscoveredInvoiceLedger  # noqa: E402
from freight_recon.screen_discovery import DiscoveredInvoiceForm  # noqa: E402
from freight_recon.tms_write import PayableWriteStatus  # noqa: E402


def _form(**over) -> DiscoveredInvoiceForm:
    base = dict(
        url="https://any-tms.test/invoice/new",
        submit_label="Save",
        bill_to_selector="[name=cust]",
        amount_selector="[name=amt]",
        invoice_number_selector="[name=num]",
        description_selector="[name=desc]",
    )
    base.update(over)
    return DiscoveredInvoiceForm(**base)


class FakeSession:
    def __init__(self, error_flash=""):
        self.error_flash = error_flash
        self.navigated = []
        self.evals = []

    def navigate(self, url):
        self.navigated.append(url)

    def evaluate(self, expression):
        if "alert-danger" in expression:
            return self.error_flash
        self.evals.append(expression)
        return None


def _ledger(session, form=None, resolve=lambda n: "99", error=None):
    return DiscoveredInvoiceLedger(
        session=session,
        form=form or _form(),
        resolve_customer=resolve,
        apply_customer=lambda s, cid: s.evaluate(f"APPLY_CUSTOMER:{cid}"),
        readback_fn=lambda lid: {"amount": "100.00"},
        invoice_number_transform=lambda lid: "".join(c for c in lid if c.isdigit()) or None,
        base_url="http://localhost",  # localhost: gate is satisfied without acknowledgement
    )


def test_write_drives_only_discovered_selectors():
    s = FakeSession(error_flash="")
    res = _ledger(s).write_payable(run_id=1, load_id="LD-560005", carrier="Prairie Line", amount="4147.00", charges=None, key="k")
    assert res.status == PayableWriteStatus.WRITTEN
    blob = " ".join(s.evals)
    # The approved amount went into the DISCOVERED amount selector (no hardcoded TMS field name).
    assert "[name=amt]" in blob and "4147.00" in blob
    assert "[name=num]" in blob and "560005" in blob  # invoice number transformed (numeric) into discovered selector
    assert "[name=cust]" in blob and "Prairie Line" in blob  # bill-to text into discovered selector
    assert "APPLY_CUSTOMER:99" in blob  # the injected system-specific customer binding ran


def test_write_fails_closed_on_error_flash():
    s = FakeSession(error_flash="Charge description can not be blank")
    res = _ledger(s).write_payable(run_id=1, load_id="LD-1", carrier="X", amount="1.00", charges=None, key="k")
    assert res.status == PayableWriteStatus.ADAPTER_FAILED
    assert "Charge description" in res.note


def test_write_refuses_without_resolved_customer():
    s = FakeSession()
    res = _ledger(s, resolve=lambda n: None).write_payable(run_id=1, load_id="LD-1", carrier="X", amount="1.00", charges=None, key="k")
    assert res.status == PayableWriteStatus.ADAPTER_FAILED
    assert not s.navigated  # never opened the form without a bill-to


def test_not_writable_form_refused():
    s = FakeSession()
    bad = _form(amount_selector=None)  # discovery couldn't find the money field
    res = _ledger(s, form=bad).write_payable(run_id=1, load_id="LD-1", carrier="X", amount="1.00", charges=None, key="k")
    assert res.status == PayableWriteStatus.ADAPTER_FAILED


def test_get_payable_delegates_to_readback():
    assert _ledger(FakeSession()).get_payable("LD-1") == {"amount": "100.00"}
