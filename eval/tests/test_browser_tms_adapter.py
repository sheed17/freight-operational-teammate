"""Tests for the browser-shaped mock TMS read adapter."""

from pathlib import Path
import sys
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.tms_adapter import BrowserMockTmsReadAdapter, TmsAdapterError  # noqa: E402


class FakeBrowserPage:
    def __init__(self) -> None:
        self.urls: list[str] = []
        self.current_url: str | None = None

    def goto(self, url: str) -> None:
        self.urls.append(url)
        self.current_url = url

    def text(self, selector: str) -> str:
        load_fields = {
            '[data-field="pro_number"]': "PRO-9200411",
            '[data-field="invoice_number"]': "INV-2026003",
            '[data-field="carrier"]': "Summit Valley Trucking",
            '[data-field="customer"]': "Harbor Appliance Group",
            '[data-field="pickup_date"]': "2026-05-05",
            '[data-field="delivery_date"]': "2026-05-07",
            '[data-field="equipment"]': "26' Box Truck",
            '[data-field="commodity"]': "retail dry goods",
            '[data-field="rate_total"]': "$3334.50",
            '[data-field="invoice_total"]': "$3634.50",
            '[data-field="payable_status"]': "NEEDS_REVIEW",
            '[data-field="workflow_state"]': "NEEDS_REVIEW",
            '[data-field="workflow_reason"]': "unauthorized accessorial: detention 300.00 not on rate confirmation",
        }
        return load_fields[selector]

    def attr(self, selector: str, name: str) -> str | None:
        if selector == "main[data-load-id]" and name == "data-load-id":
            return "LD-560003"
        return None

    def table_rows(self, selector: str) -> list[dict[str, Any]]:
        if selector == 'table[aria-label="Charge lines"]':
            return [
                {
                    "name": "linehaul",
                    "rate_amount": "$2925.00",
                    "invoice_amount": "$2925.00",
                    "authorized": "Yes",
                    "backup_document": "",
                },
                {
                    "name": "detention",
                    "rate_amount": "",
                    "invoice_amount": "$300.00",
                    "authorized": "No",
                    "backup_document": "",
                },
            ]
        if selector == 'table[data-tms-table="payables"]':
            return [
                {
                    "load_id": "LD-560003",
                    "invoice_number": "INV-2026003",
                    "carrier": "Summit Valley Trucking",
                    "expected_amount": "$3334.50",
                    "billed_amount": "$3634.50",
                    "payable_status": "NEEDS_REVIEW",
                }
            ]
        return []

    def links(self, selector: str) -> list[dict[str, str]]:
        assert selector == "#documents li[data-doc-type] a"
        return [
            {
                "doc_type": "carrier_invoice",
                "label": "Carrier Invoice",
                "href": "/evidence/LD-560003/carrier_invoice.pdf",
            }
        ]


def test_browser_mock_tms_adapter_reads_load_with_stable_selectors():
    page = FakeBrowserPage()
    adapter = BrowserMockTmsReadAdapter(page)

    load = adapter.read_load("LD-560003")

    assert page.urls == ["http://localhost:8000/tms/loads/LD-560003.html"]
    assert load.source == "mock_tms_browser"
    assert load.rate_total == "3334.50"
    assert load.invoice_total == "3634.50"
    assert load.payable_status == "NEEDS_REVIEW"
    assert any(charge.name == "detention" and charge.authorized is False for charge in load.charges)
    assert any(document.doc_type == "carrier_invoice" for document in load.documents)


def test_browser_mock_tms_adapter_reads_payable_queue():
    page = FakeBrowserPage()
    adapter = BrowserMockTmsReadAdapter(page)

    payable = adapter.read_payable("LD-560003")

    assert page.urls == ["http://localhost:8000/tms/payables.html"]
    assert payable.source == "mock_tms_browser_payables"
    assert payable.expected_amount == "3334.50"
    assert payable.billed_amount == "3634.50"


def test_browser_mock_tms_adapter_blocks_non_allowlisted_base_url():
    with pytest.raises(TmsAdapterError):
        BrowserMockTmsReadAdapter(FakeBrowserPage(), base_url="https://real-tms.example.com")


def test_browser_mock_tms_adapter_blocks_invalid_load_ids():
    adapter = BrowserMockTmsReadAdapter(FakeBrowserPage())

    with pytest.raises(TmsAdapterError):
        adapter.read_load("../LD-560003")
