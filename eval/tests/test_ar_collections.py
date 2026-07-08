"""AR collections: read /invoices -> unpaid receivables -> aged digest. Parsed by content (drift-safe)."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.ar_collections import (  # noqa: E402
    aged_unpaid,
    receivables_from_invoices_table,
    render_aging_digest,
)

# Live-shaped: the 7-col header, but rows carry 6 cells (the empty 'Custom Invoice Number' is dropped,
# shifting everything left) and 'Paid On' is blank for unpaid rows — exactly the drift seen on the TMS.
_OBS = {"tables": [{
    "headers": ["Number", "Custom Invoice Number", "Customer", "Total Amount", "Balance Due",
                "Invoiced On", "Paid On"],
    "rows": [
        {"cells": ["Number", "Custom Invoice Number", "Customer", "Total Amount", "Balance Due",
                   "Invoiced On", "Paid On"]},                                       # header echoed -> skip
        {"cells": ["560011", "Great Lakes Drayage Co", "$2,400.00", "$2,400.00", "07/05/2026",
                   "View Enter Payment"]},                                           # fully unpaid
        {"cells": ["560003", "Maple Leaf Transport", "$3,634.50", "$184.50", "06/28/2026",
                   "View Enter Payment"]},                                           # partially paid
        {"cells": ["560099", "Paid In Full Co", "$1,000.00", "$0.00", "06/01/2026", "View"]},  # paid -> skip
    ],
}]}


def test_receivables_parses_unpaid_by_content_and_excludes_paid():
    recv = {r["invoice"]: r for r in receivables_from_invoices_table(_OBS)}
    assert set(recv) == {"560011", "560003"}                       # paid + header excluded
    # column drift didn't fool the balance: total is first money cell, balance the last
    assert recv["560003"]["total"] == "3634.50" and recv["560003"]["balance_due"] == "184.50"
    assert recv["560003"]["customer"] == "Maple Leaf Transport"
    assert recv["560011"]["balance_due"] == "2400.00"


def test_aged_unpaid_flags_only_past_due_worst_first():
    recv = receivables_from_invoices_table(_OBS)
    aged = aged_unpaid(recv, as_of=date(2026, 7, 6), min_days=7)
    assert [r["invoice"] for r in aged] == ["560003"]              # 8d outstanding; 560011 (1d) is too new
    assert aged[0]["days_outstanding"] == 8
    assert aged[0]["past_due"] is False


def test_aged_unpaid_only_claims_past_due_when_terms_are_configured():
    recv = receivables_from_invoices_table(_OBS)
    aged = aged_unpaid(recv, as_of=date(2026, 7, 6), min_days=1, terms_days=7)
    by_invoice = {r["invoice"]: r for r in aged}
    assert by_invoice["560003"]["past_due"] is True
    assert by_invoice["560011"]["past_due"] is False


def test_aging_digest_totals_the_outstanding_balance():
    aged = aged_unpaid(receivables_from_invoices_table(_OBS), as_of=date(2026, 7, 6), min_days=1)
    digest = render_aging_digest(aged)
    assert "2 unpaid invoices outstanding" in digest
    assert "past due" not in digest
    assert "$2,584.50" in digest                                   # 2400.00 + 184.50 outstanding
    assert "#560003 Maple Leaf Transport" in digest
    assert "draft reminders" in digest.lower()


def test_empty_when_nothing_is_aged():
    assert "No outstanding receivables" in render_aging_digest([])
