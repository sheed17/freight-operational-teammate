"""Tests for the deterministic, gated TruckingOffice invoice write + readback."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.tms_write import PayableWriteStatus  # noqa: E402
from freight_recon.truckingoffice_write import (  # noqa: E402
    RealTmsWriteNotAuthorized,
    TruckingOfficeInvoiceLedger,
    authorize_write_host,
    build_invoice_form_values,
    normalize_money,
    parse_customer_id,
    parse_invoice_readback,
)


# ----- authorization gate (fail-closed) -----

def test_authorize_localhost_always_allowed():
    authorize_write_host("localhost")
    authorize_write_host("127.0.0.1")


def test_authorize_real_host_refused_without_acknowledgement():
    with pytest.raises(RealTmsWriteNotAuthorized):
        authorize_write_host("secure.truckingoffice.com", approved_hosts=["secure.truckingoffice.com"])


def test_authorize_real_host_refused_when_not_on_approved_list():
    with pytest.raises(RealTmsWriteNotAuthorized):
        authorize_write_host("evil.example.com", approved_hosts=["secure.truckingoffice.com"], acknowledged=True)


def test_authorize_real_host_allowed_only_with_ack_and_approval():
    authorize_write_host("secure.truckingoffice.com", approved_hosts=["secure.truckingoffice.com"], acknowledged=True)


# ----- deterministic parsing -----

def test_normalize_money():
    assert normalize_money("$2,450.00") == "2450.00"
    assert normalize_money("1680.00") == "1680.00"
    assert normalize_money(None) is None
    assert normalize_money("n/a") is None


def test_parse_invoice_readback_matches_single_row():
    rows = [
        {"number": "1000", "customer": "TQL", "total": "$2,450.00"},
        {"number": "1001", "customer": "Echo", "total": "$3,200.00"},
    ]
    assert parse_invoice_readback(rows, "1001") == "3200.00"


def test_parse_invoice_readback_fail_closed_on_missing_or_duplicate():
    rows = [
        {"number": "1000", "customer": "TQL", "total": "$2,450.00"},
        {"number": "1000", "customer": "TQL", "total": "$9,999.00"},  # ambiguous duplicate
    ]
    assert parse_invoice_readback(rows, "1000") is None  # duplicate -> fail closed
    assert parse_invoice_readback(rows, "4242") is None  # absent -> fail closed


def test_parse_customer_id_matches_and_fails_closed():
    rows = [
        {"text": "Total Quality Logistics ap@tql.com (513) Milford OH", "id": "15114781"},
        {"text": "Echo Global Logistics ap@echo.com Chicago IL", "id": "15114782"},
    ]
    assert parse_customer_id(rows, "Total Quality Logistics") == "15114781"
    assert parse_customer_id(rows, "Nonexistent Broker") is None  # absent -> None
    dupes = [{"text": "Acme Freight A", "id": "1"}, {"text": "Acme Freight B", "id": "2"}]
    assert parse_customer_id(dupes, "Acme Freight") is None  # ambiguous -> fail closed


def test_build_form_values_sets_both_customer_id_inputs():
    v = build_invoice_form_values(
        customer_id="15114781", customer_name="Total Quality Logistics",
        invoice_number="1000", total_charge="2450.00", description="Linehaul",
    )
    # The load-bearing quirk: BOTH hidden ids must carry the customer id.
    assert v["by_id"]["invoice_customer_id"] == "15114781"
    assert v["by_id"]["customer"] == "15114781"
    assert v["by_name"]["invoice[total_charge]"] == "2450.00"
    assert v["by_name"]["invoice[invoice_number]"] == "1000"


# ----- ledger over a fake in-session browser -----

class FakeSession:
    def __init__(self, rows=None, error_flash=""):
        self.rows = rows or []
        self.error_flash = error_flash
        self.navigations = []
        self.fills = []

    def navigate(self, url):
        self.navigations.append(url)

    def evaluate(self, expression):
        if "alert-danger" in expression:
            return self.error_flash
        if "table tbody tr" in expression:
            return self.rows
        self.fills.append(expression)  # the fill+save script
        return None


def _ledger(session, resolver=lambda name: "15114781"):
    return TruckingOfficeInvoiceLedger(
        session=session, customer_resolver=resolver,
        approved_write_hosts=["secure.truckingoffice.com"], real_write_acknowledged=True,
    )


def test_ledger_construction_refuses_unauthorized_host():
    with pytest.raises(RealTmsWriteNotAuthorized):
        TruckingOfficeInvoiceLedger(
            session=FakeSession(), customer_resolver=lambda n: "1",
            base_url="https://secure.truckingoffice.com",  # not acknowledged
        )


def test_write_payable_written_when_no_error_flash():
    s = FakeSession(error_flash="")
    res = _ledger(s).write_payable(run_id=1, load_id="1000", carrier="TQL", amount="2450.00", charges=None, key="k1")
    assert res.status == PayableWriteStatus.WRITTEN
    assert any("/no_load_invoice/new" in u for u in s.navigations)
    assert s.fills and "2450.00" in s.fills[0]  # approved amount went into the form


def test_write_payable_fails_closed_on_error_flash():
    s = FakeSession(error_flash="Customer can't be blank")
    res = _ledger(s).write_payable(run_id=1, load_id="1000", carrier="TQL", amount="2450.00", charges=None, key="k1")
    assert res.status == PayableWriteStatus.ADAPTER_FAILED
    assert "Customer can't be blank" in res.note


def test_write_payable_refuses_when_no_customer_resolved():
    s = FakeSession()
    res = _ledger(s, resolver=lambda name: None).write_payable(
        run_id=1, load_id="1000", carrier="Unknown LLC", amount="2450.00", charges=None, key="k1"
    )
    assert res.status == PayableWriteStatus.ADAPTER_FAILED
    assert not s.fills  # never touched the form without a bill-to


def test_get_payable_reads_back_amount():
    s = FakeSession(rows=[{"number": "1000", "customer": "TQL", "total": "$2,450.00"}])
    out = _ledger(s).get_payable("1000")
    assert out["amount"] == "2450.00" and out["idempotency_key"] == "1000"
    assert _ledger(FakeSession(rows=[])).get_payable("1000") is None  # absent -> None
