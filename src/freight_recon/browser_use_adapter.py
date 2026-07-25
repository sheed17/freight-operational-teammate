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
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

from .tms_adapter import TmsAdapterError, TmsLoadReadback, TmsPayableReadback
from .tms_write import PayableWriteResult, PayableWriteStatus
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

    Kept out of tests unless the optional dependency is installed and explicitly used. The agent LLM
    is browser-use's hosted model when ``BROWSER_USE_API_KEY`` is set, otherwise OpenAI (`ChatOpenAI`)
    using ``OPENAI_API_KEY`` — so the execution agent runs without a separate browser-use account.
    """

    def __init__(self, *, model: str | None = None, max_steps: int = 12) -> None:
        self.model = model
        self.max_steps = max_steps

    def _llm(self):
        import os

        if os.getenv("BROWSER_USE_API_KEY"):
            from browser_use.beta import ChatBrowserUse

            return ChatBrowserUse()
        from browser_use import ChatOpenAI

        # gpt-4.1-mini is the validated default for the native browser-use wrapper here. Keep it
        # configurable so live evals can route known-screen runs cheaper without touching code.
        return ChatOpenAI(model=self.model or os.getenv("NEYMA_BROWSER_USE_MODEL", "gpt-4.1-mini"))

    async def run(self, task: str, *, allowed_domains: list[str], headless: bool) -> str:
        try:
            from browser_use.beta import Agent, BrowserProfile
        except ModuleNotFoundError as exc:
            raise TmsAdapterError(
                "browser-use is not installed. Install with: "
                ".venv/bin/python -m pip install '.[browser-agent]'"
            ) from exc

        agent = Agent(
            task=task,
            llm=self._llm(),
            browser_profile=BrowserProfile(
                headless=headless,
                allowed_domains=allowed_domains,
            ),
        )
        history = await agent.run(max_steps=self.max_steps)
        result = history.final_result()
        if result is None:
            raise TmsAdapterError("browser-use returned no final result")
        return str(result)


class BrowserUseWriteLedger:
    """Drive browser-use to ENTER a payable in the writable mock TMS and read it back.

    This is the execution layer realized through the real browser. It implements the same
    ``write_payable`` / ``get_payable`` seam as :class:`~freight_recon.tms_write.MockTmsWriteLedger`,
    so the gated ``enter_approved_payable`` path (confirm-before-submit → submit → verify-by-readback
    → idempotency) drives a real browser **unchanged**. The TMS server owns idempotency/duplicate
    logic; this ledger only operates the screen and reports back what the TMS displays. It never
    decides an amount.
    """

    def __init__(
        self,
        *,
        runner: BrowserUseRunner,
        base_url: str,
        allowed_domains: tuple[str, ...] = ("localhost", "127.0.0.1"),
        headless: bool = True,
        readback_fn: "Callable[[str], dict | None] | None" = None,
    ) -> None:
        self.runner = runner
        self.base_url = base_url.rstrip("/")
        self.allowed_domains = list(allowed_domains)
        self.headless = headless
        self._validate_write_target()
        # Verify-by-readback is a SAFETY gate, so it should be deterministic — not an LLM reading a
        # screen. When a readback_fn is supplied (e.g. an HTTP/API/DOM-scrape read of the system of
        # record), get_payable uses it; otherwise it falls back to the agent (used by unit tests).
        self.readback_fn = readback_fn

    def write_payable(
        self, *, run_id: int, load_id: str, carrier: str, amount: str, charges, key: str
    ) -> PayableWriteResult:
        from urllib.parse import quote

        url = (
            f"{self.base_url}/payables/new?load_id={quote(load_id)}&run_id={run_id}"
            f"&carrier={quote(carrier)}&key={quote(key)}"
        )
        data = _parse_json_result(self._run(_enter_payable_task(url, amount)))
        raw_status = str(data.get("status", "")).upper()
        external_ref = data.get("external_ref") or None
        note = str(data.get("note") or "entered via browser-use")
        try:
            status = PayableWriteStatus(raw_status)
        except ValueError:
            # The agent's free-text status read was fuzzy. Fall back to the deterministic table
            # readback — but only call it WRITTEN if the row carries THIS submit's idempotency key.
            # A row with a different key means a prior/duplicate payable, NOT that our write landed,
            # so it must fail closed (never mask a DUPLICATE_BLOCKED as WRITTEN). verify-by-readback
            # still independently re-checks the amount before the run can reach DONE.
            readback = self.get_payable(load_id)
            if readback is not None and readback.get("idempotency_key") == key:
                status = PayableWriteStatus.WRITTEN
                external_ref = external_ref or readback.get("external_ref")
                note = f"submit confirmed by readback key match (agent status text was {raw_status!r})"
            else:
                raise TmsAdapterError(
                    f"browser-use returned an unrecognized TMS write status {raw_status!r} and the "
                    f"readback row for {load_id} did not carry this submit's idempotency key"
                )
        return PayableWriteResult(
            run_id=run_id,
            load_id=load_id,
            idempotency_key=key,
            status=status,
            external_ref=external_ref,
            note=note,
        )

    def get_payable(self, load_id: str) -> dict | None:
        # Deterministic verify path (preferred): an independent, non-LLM read of the system of record.
        if self.readback_fn is not None:
            return self.readback_fn(load_id)
        try:
            data = _parse_json_result(self._run(_read_payables_task(f"{self.base_url}/payables.html", load_id)))
        except TmsAdapterError:
            return None  # unreadable readback fails closed → verify mismatch → FAILED, never DONE
        amount = data.get("amount")
        if amount in (None, "", "null"):
            return None
        # Defensive: only trust a row the agent confirms is for THIS load (it must not return a
        # neighbouring row from a multi-row table). If the read-back load id disagrees, treat as absent.
        read_load = data.get("load_id")
        if read_load not in (None, "", "null") and str(read_load).strip().upper() != str(load_id).strip().upper():
            return None
        return {
            "amount": str(amount),
            "carrier": data.get("carrier"),
            "external_ref": data.get("external_ref"),
            "idempotency_key": data.get("idempotency_key"),
        }

    def _run(self, task: str) -> str:
        return asyncio.run(self.runner.run(task, allowed_domains=self.allowed_domains, headless=self.headless))

    def _validate_write_target(self) -> None:
        host = (urlparse(self.base_url).hostname or "").lower()
        allowed = {"localhost", "127.0.0.1"}
        if host not in allowed:
            raise TmsAdapterError(
                "browser-use write ledger is mock/local only; real TMS hosts require a separate approved sandbox gate"
            )


def _enter_payable_task(form_url: str, amount: str) -> str:
    return f"""
Open {form_url}
This is a TMS carrier-payable entry form. Type exactly {amount} into the amount input (element id "amount").
Then click the button with id "submit-payable" (labeled "Enter payable").
On the resulting confirmation page, read the text of elements id "write-status", id "external-ref",
id "idempotency-key", and id "note".
Return ONLY valid JSON with keys: status, external_ref, idempotency_key, note.
Do not navigate anywhere else and do not change any other field.
"""


def http_payable_readback(base_url: str, load_id: str) -> dict | None:
    """Deterministic verify-by-readback for the mock TMS: read the payables page over HTTP and parse
    the exact row. The verify gate must not depend on an LLM interpreting a screen.

    For a real, authenticated TMS the deterministic read would instead use the TMS API or a precise
    in-session DOM extraction (selector-based), not an LLM free-read — same principle, same contract.
    """
    import urllib.request

    try:
        raw = urllib.request.urlopen(f"{base_url.rstrip('/')}/payables.html", timeout=10).read().decode("utf-8")
    except Exception:  # noqa: BLE001 - unreadable readback fails closed → verify mismatch → FAILED
        return None
    return parse_payables_row(raw, load_id)


def parse_payables_row(html_text: str, load_id: str) -> dict | None:
    """Deterministically parse the exact payables-table row for ``load_id`` from rendered HTML."""
    import re

    target = str(load_id).strip().upper()
    matches = [
        chunk
        for chunk in html_text.split('<tr class="payable-row"')[1:]
        if (m := re.search(r'data-load-id="([^"]*)"', chunk)) and m.group(1).strip().upper() == target
    ]
    # Absent OR ambiguous (more than one row for this load) → fail closed: verify-by-readback must
    # never guess which duplicate row is authoritative; mismatch → FAILED, never DONE.
    if len(matches) != 1:
        return None
    chunk = matches[0]

    def _cell(cls: str) -> str | None:
        cell = re.search(rf'class="{cls}">([^<]*)<', chunk)
        return cell.group(1).strip() if cell else None

    amount = _cell("amount")
    if not amount:
        return None
    return {
        "amount": amount,
        "carrier": _cell("carrier"),
        "external_ref": _cell("external-ref"),
        "idempotency_key": _cell("idempotency-key"),
    }


def _read_payables_task(url: str, load_id: str) -> str:
    return f"""
Open {url}
The payables table has columns: Load, Carrier, Amount, Reference, Key.
Find the EXACT row whose Load cell equals {load_id} (not any other load).
Return ONLY valid JSON with keys read from THAT row's cells: load_id, amount, carrier, external_ref, idempotency_key.
If there is no row whose Load equals {load_id}, return {{"load_id": null, "amount": null}}.
Money values must not include dollar signs.
"""


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
