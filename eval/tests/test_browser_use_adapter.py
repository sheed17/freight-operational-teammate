"""Tests for the Browser Use production adapter boundary."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.browser_use_adapter import BrowserUseConfig, BrowserUseTmsAdapter  # noqa: E402
from freight_recon.tms_adapter import TmsAdapterError  # noqa: E402
from freight_recon.tool_permissions import ToolContext  # noqa: E402
from freight_recon.workflow import WorkflowState  # noqa: E402


class FakeBrowserUseRunner:
    def __init__(self, result: str) -> None:
        self.result = result
        self.calls: list[dict] = []

    async def run(self, task: str, *, allowed_domains: list[str], headless: bool) -> str:
        self.calls.append(
            {
                "task": task,
                "allowed_domains": allowed_domains,
                "headless": headless,
            }
        )
        return self.result


def test_browser_use_adapter_reads_load_from_json_result():
    runner = FakeBrowserUseRunner(
        """
        {
          "pro_number": "PRO-9200411",
          "invoice_number": "INV-2026003",
          "carrier": "Summit Valley Trucking",
          "customer": "Harbor Appliance Group",
          "pickup_date": "2026-05-05",
          "delivery_date": "2026-05-07",
          "equipment": "26' Box Truck",
          "commodity": "retail dry goods",
          "rate_total": "3334.50",
          "invoice_total": "3634.50",
          "payable_status": "NEEDS_REVIEW",
          "workflow_state": "NEEDS_REVIEW",
          "workflow_reason": "unauthorized detention",
          "charges": [{"name": "detention", "rate_amount": null, "invoice_amount": "300.00", "authorized": false, "backup_document": null}],
          "documents": [{"doc_type": "carrier_invoice", "label": "Carrier Invoice", "href": "/invoice.pdf"}]
        }
        """
    )
    adapter = BrowserUseTmsAdapter(
        runner=runner,
        tool_context=ToolContext(workflow_state=WorkflowState.NEEDS_REVIEW),
    )

    result = read_async(adapter.read_load("LD-560003"))

    assert result.source == "browser_use_tms"
    assert result.rate_total == "3334.50"
    assert result.invoice_total == "3634.50"
    assert result.charges[0].name == "detention"
    assert runner.calls[0]["allowed_domains"] == ["localhost", "127.0.0.1"]
    assert "Do not click submit" in runner.calls[0]["task"]


def test_browser_use_adapter_reads_payable_from_json_result():
    runner = FakeBrowserUseRunner(
        """
        {
          "invoice_number": "INV-2026003",
          "carrier": "Summit Valley Trucking",
          "expected_amount": "3334.50",
          "billed_amount": "3634.50",
          "payable_status": "NEEDS_REVIEW"
        }
        """
    )
    adapter = BrowserUseTmsAdapter(
        runner=runner,
        tool_context=ToolContext(workflow_state=WorkflowState.NEEDS_REVIEW),
    )

    result = read_async(adapter.read_payable("LD-560003"))

    assert result.source == "browser_use_tms_payables"
    assert result.billed_amount == "3634.50"
    assert "payables.html" in runner.calls[0]["task"]


def test_browser_use_adapter_respects_tool_permissions():
    adapter = BrowserUseTmsAdapter(
        runner=FakeBrowserUseRunner("{}"),
        tool_context=ToolContext(workflow_state=WorkflowState.RECEIVED),
    )

    with pytest.raises(TmsAdapterError, match="tool blocked"):
        read_async(adapter.read_load("LD-560003"))


def test_browser_use_adapter_blocks_unallowlisted_base_url():
    with pytest.raises(TmsAdapterError):
        BrowserUseTmsAdapter(
            runner=FakeBrowserUseRunner("{}"),
            config=BrowserUseConfig(base_url="https://real-tms.example.com"),
            tool_context=ToolContext(workflow_state=WorkflowState.NEEDS_REVIEW),
        )


def test_browser_use_adapter_rejects_non_json_agent_output():
    adapter = BrowserUseTmsAdapter(
        runner=FakeBrowserUseRunner("I found it!"),
        tool_context=ToolContext(workflow_state=WorkflowState.NEEDS_REVIEW),
    )

    with pytest.raises(TmsAdapterError, match="not valid JSON"):
        read_async(adapter.read_payable("LD-560003"))


def read_async(awaitable):
    import asyncio

    return asyncio.run(awaitable)
