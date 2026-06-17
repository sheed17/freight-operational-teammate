"""Production browser-use adapter boundary.

The production browser agent is Browser Use (`browser-use/browser-use`). This module keeps that
optional dependency behind Neyma's adapter contract so the core workflow, tests, and deterministic
mock-TMS reads do not depend on a browser runtime.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from typing import Any, Protocol

from .tms_adapter import TmsAdapterError, TmsLoadReadback, TmsPayableReadback
from .tool_permissions import ToolContext, evaluate_tool_permission, record_tool_permission_decision
from .workflow import WorkflowStore


LOAD_ID_RE = re.compile(r"^[A-Z]{2}-\d{6}$")


class BrowserUseRunner(Protocol):
    async def run(self, task: str, *, allowed_domains: list[str], headless: bool) -> str:
        ...


@dataclass(frozen=True)
class BrowserUseConfig:
    base_url: str = "http://localhost:8000/tms"
    allowed_domains: tuple[str, ...] = ("localhost", "127.0.0.1")
    headless: bool = False


class BrowserUseTmsAdapter:
    """Read-only Browser Use TMS adapter.

    V0 only reads mock TMS. Write/submit paths must be separate methods gated by the tool
    permission registry, explicit approval, and verify-by-readback.
    """

    def __init__(
        self,
        *,
        runner: BrowserUseRunner | None = None,
        config: BrowserUseConfig | None = None,
        tool_context: ToolContext,
        store: WorkflowStore | None = None,
        run_id: int | None = None,
    ) -> None:
        self.config = config or BrowserUseConfig()
        self.runner = runner or NativeBrowserUseRunner()
        self.tool_context = tool_context
        self.store = store
        self.run_id = run_id
        self._validate_base_url()

    async def read_load(self, load_id: str) -> TmsLoadReadback:
        self._validate_load_id(load_id)
        self._require_tool("read_tms_load")
        payload = await self.runner.run(
            _read_load_task(self.config.base_url.rstrip("/"), load_id),
            allowed_domains=list(self.config.allowed_domains),
            headless=self.config.headless,
        )
        data = _parse_json_result(payload)
        readback = TmsLoadReadback.model_validate(
            {
                **data,
                "source": "browser_use_tms",
                "source_url": f"{self.config.base_url.rstrip('/')}/loads/{load_id}.html",
                "load_id": load_id,
            }
        )
        self._audit_readback("browser_use_tms_load_read", readback.model_dump(mode="json"))
        return readback

    async def read_payable(self, load_id: str) -> TmsPayableReadback:
        self._validate_load_id(load_id)
        self._require_tool("read_tms_payable")
        payload = await self.runner.run(
            _read_payable_task(self.config.base_url.rstrip("/"), load_id),
            allowed_domains=list(self.config.allowed_domains),
            headless=self.config.headless,
        )
        data = _parse_json_result(payload)
        readback = TmsPayableReadback.model_validate(
            {
                **data,
                "source": "browser_use_tms_payables",
                "source_url": f"{self.config.base_url.rstrip('/')}/payables.html",
                "load_id": load_id,
            }
        )
        self._audit_readback("browser_use_tms_payable_read", readback.model_dump(mode="json"))
        return readback

    def _require_tool(self, tool_name: str) -> None:
        decision = evaluate_tool_permission(tool_name, self.tool_context)
        if self.store is not None and self.run_id is not None:
            record_tool_permission_decision(self.store, self.run_id, decision=decision, context=self.tool_context)
        if not decision.allowed:
            raise TmsAdapterError(f"tool blocked: {tool_name}: {decision.reason}")

    def _audit_readback(self, event_type: str, payload: dict) -> None:
        if self.store is None or self.run_id is None:
            return
        self.store.add_audit_event(
            self.run_id,
            event_type,
            actor=self.tool_context.actor,
            payload=payload,
        )

    def _validate_load_id(self, load_id: str) -> None:
        if not LOAD_ID_RE.match(load_id):
            raise TmsAdapterError(f"invalid load id for browser-use TMS adapter: {load_id}")

    def _validate_base_url(self) -> None:
        match = re.match(r"^https?://([^/:]+)(?::\d+)?(?:/|$)", self.config.base_url)
        if not match or match.group(1) not in set(self.config.allowed_domains):
            raise TmsAdapterError(f"browser-use base URL is not allowlisted: {self.config.base_url}")


class NativeBrowserUseRunner:
    """Thin lazy wrapper around `browser-use[core]`.

    Kept out of tests unless the optional dependency is installed and explicitly used.
    """

    async def run(self, task: str, *, allowed_domains: list[str], headless: bool) -> str:
        try:
            from browser_use.beta import Agent, BrowserProfile, ChatBrowserUse
        except ModuleNotFoundError as exc:
            raise TmsAdapterError(
                "browser-use is not installed. Install with: "
                ".venv/bin/python -m pip install '.[browser-agent]'"
            ) from exc

        agent = Agent(
            task=task,
            llm=ChatBrowserUse(),
            browser_profile=BrowserProfile(
                headless=headless,
                allowed_domains=allowed_domains,
            ),
        )
        history = await agent.run()
        result = history.final_result()
        if result is None:
            raise TmsAdapterError("browser-use returned no final result")
        return str(result)


def read_load_sync(adapter: BrowserUseTmsAdapter, load_id: str) -> TmsLoadReadback:
    return asyncio.run(adapter.read_load(load_id))


def read_payable_sync(adapter: BrowserUseTmsAdapter, load_id: str) -> TmsPayableReadback:
    return asyncio.run(adapter.read_payable(load_id))


def _read_load_task(base_url: str, load_id: str) -> str:
    return f"""
Open {base_url}/loads/{load_id}.html.
Read the mock TMS load detail page.
Return ONLY valid JSON with these keys:
pro_number, invoice_number, carrier, customer, pickup_date, delivery_date, equipment, commodity,
rate_total, invoice_total, payable_status, workflow_state, workflow_reason, charges, documents.
Money values must not include dollar signs. charges must include name, rate_amount, invoice_amount,
authorized, backup_document. documents must include doc_type, label, href.
Do not click submit, approve, send, upload, or write anything.
"""


def _read_payable_task(base_url: str, load_id: str) -> str:
    return f"""
Open {base_url}/payables.html.
Find the carrier payable row with load id {load_id}.
Return ONLY valid JSON with these keys:
invoice_number, carrier, expected_amount, billed_amount, payable_status.
Money values must not include dollar signs.
Do not click submit, approve, send, upload, or write anything.
"""


def _parse_json_result(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        cleaned = cleaned.removeprefix("json").strip()
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise TmsAdapterError(f"browser-use result was not valid JSON: {raw[:200]}") from exc
    if not isinstance(data, dict):
        raise TmsAdapterError("browser-use result JSON must be an object")
    return data
