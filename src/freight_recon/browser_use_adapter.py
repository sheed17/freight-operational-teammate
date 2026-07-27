"""EP-14 — THE STRUCTURALLY READ-ONLY BROWSER-USE SURFACE (P4 adapter containment, R-07 scope).

This module used to be read-only by NAMING. Its class docstring said "Read-only Browser Use TMS
adapter", and in the same file sat `BrowserUseWriteLedger` (a payable write) and
`NativeBrowserUseRunner` (a driver that runs an ARBITRARY natural-language task). The repository's
own import gate did not believe the docstring: `BrowserUseTmsAdapter` was listed in
`test_import_gate._LIVE_WRITE_DRIVERS` alongside `CdpActuator`, because a read caller holding it
could reach a generic browser agent and a write ledger. That is the same defect F2 found in
`cdp_session`, and the same answer applies — a mechanism, not a promise.

The write half now lives in `browser_use_write` [[browser_use_write]], the effect-capable slot the
frozen phase-0 inventory had already reserved. What is left here can express a READ and nothing else.

THREE BARRIERS, mirroring the F2 CDP split:

  1. NO WRITE API EXISTS HERE. There is no `write_payable`, no `get_payable`, no `submit`, no
     `enter_*`, and no generic `run`. A caller holding a `BrowserUseTmsAdapter` cannot express a
     write — not "must not", CANNOT. The module imports no effect-capable adapter at all, so there
     is nothing here to hand one out either.

  2. THE TASK IS NEVER CALLER-AUTHORED. This is the browser-agent analogue of "caller data is never
     code". A browser-use agent does whatever its TASK STRING says, so the task string is the
     actuation primitive. `ReadOnlyBrowserUseRunner` does not accept one. It accepts a TASK ID from
     the frozen `VETTED_READ_TASKS` registry plus DATA, renders the task from the registry itself,
     and validates the data (`load_id` against `LOAD_ID_RE`, the base URL against the domain
     allowlist). Nothing in this module concatenates caller input into a task the caller chose.

  3. THE RUNNER REFUSES ANYTHING ELSE. `ReadOnlyBrowserUseRunner.run_vetted` rejects an unknown task
     id before a browser is launched, and the browser profile is pinned to the configured domain
     allowlist. A caller that reaches the runner directly still cannot issue an arbitrary task.

HONEST SCOPE — this claim is deliberately narrower than F2's. CDP containment is protocol-level: the
read channel allowlists CDP METHODS, so `Input.dispatchMouseEvent` is refused by the transport and
the browser never sees it. A browser-use agent has no such chokepoint: it is an LLM driving a real
browser, and an LLM handed a read task could in principle still click something. The read tasks below
therefore also SAY "do not click submit, approve, send, upload, or write anything" — and a sentence
in a prompt is not a mechanism, which is exactly why it is not what this module rests on.

What IS mechanically true here, and is what the P4 containment claim relies on:
  * a read-side caller cannot express a write on this surface (no method exists),
  * a read-side caller cannot author the agent's task (barrier 2),
  * a read-side caller cannot reach `BrowserUseWriteLedger` or `NativeBrowserUseRunner` through this
    module (barrier 1 — proved by the import graph, not by inspection), and
  * the agent is confined to the configured domain allowlist.
The residual risk — an LLM misbehaving inside a read task on an allowlisted domain — is real,
belongs to the browser-agent execution class rather than to the import boundary, and is contained by
the effect boundary at the point where a write is ATTEMPTED, not by this module pretending otherwise.
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

#: Method names that would make this surface effect-capable again. Named so a guard can assert they
#: never appear here, the way `cdp_readonly.FORBIDDEN_PRIMITIVES` does for the CDP surface.
FORBIDDEN_WRITE_PRIMITIVES: tuple[str, ...] = (
    "write_payable", "get_payable", "submit", "enter_payable", "run", "click", "type", "upload",
)


class BrowserUseTaskTransport(Protocol):
    """What the read adapter needs from a transport: run a VETTED task id with DATA.

    Deliberately NOT `run(task: str)`. A transport that accepts a task string is an actuation
    primitive, and typing the seam this way means an effect-capable runner is not even
    substitutable here.
    """

    async def run_vetted(
        self, task_id: str, *, base_url: str, load_id: str,
        allowed_domains: list[str] | None = None, headless: bool = False,
    ) -> str:
        ...


@dataclass(frozen=True)
class BrowserUseConfig:
    base_url: str = "http://localhost:8000/tms"
    allowed_domains: tuple[str, ...] = ("localhost", "127.0.0.1")
    headless: bool = False


# ---------------------------------------------------------------------------------------------
# The vetted read tasks. Each is a FIXED template rendered by this module from validated data —
# never a string a caller supplied. Membership is by TASK ID, and the registry is the only source
# of task text, so a caller cannot pass a lookalike, a superset, or a task with an appended payload.
# ---------------------------------------------------------------------------------------------

READ_LOAD_TASK = "read_tms_load"
READ_PAYABLE_TASK = "read_tms_payable"


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


#: Exactly the tasks this surface may ever issue. A task id outside this map is refused before a
#: browser is launched.
VETTED_READ_TASKS: dict[str, Any] = {
    READ_LOAD_TASK: _read_load_task,
    READ_PAYABLE_TASK: _read_payable_task,
}


def render_vetted_task(task_id: str, *, base_url: str, load_id: str) -> str:
    """Render a vetted read task from validated DATA, or refuse.

    Pure and total, so every refusal is unit-testable without a browser. This is the ONLY function
    in the read half that produces a task string, and it can only produce one of the vetted two.
    """
    template = VETTED_READ_TASKS.get(str(task_id))
    if template is None:
        raise TmsAdapterError(
            f"refused: {task_id!r} is not a vetted read task. This surface issues only "
            f"{sorted(VETTED_READ_TASKS)}. Caller-authored browser-agent tasks cannot be run here; "
            "the write path is browser_use_write, behind the effect boundary."
        )
    if not LOAD_ID_RE.match(str(load_id)):
        raise TmsAdapterError(f"invalid load id for browser-use TMS adapter: {load_id}")
    return template(str(base_url).rstrip("/"), str(load_id))


class ReadOnlyBrowserUseRunner:
    """The read transport — barrier 3.

    It launches browser-use with a task RENDERED HERE from the vetted registry. It has no method
    that accepts a task string, so even a caller that reaches this object cannot issue an arbitrary
    task: the refusal happens before a browser exists.

    It deliberately does NOT import or wrap `browser_use_write.NativeBrowserUseRunner`. Reusing the
    unrestricted driver would put an effect-capable object one attribute access away from every read
    caller, and would create an import edge from the read module to the effect-capable module —
    the exact reachability EP-14 exists to remove.
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

        return ChatOpenAI(model=self.model or os.getenv("NEYMA_BROWSER_USE_MODEL", "gpt-4.1-mini"))

    async def run_vetted(
        self, task_id: str, *, base_url: str, load_id: str,
        allowed_domains: list[str] | None = None, headless: bool = False,
    ) -> str:
        task = render_vetted_task(task_id, base_url=base_url, load_id=load_id)
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
                allowed_domains=list(allowed_domains or []),
            ),
        )
        history = await agent.run(max_steps=self.max_steps)
        result = history.final_result()
        if result is None:
            raise TmsAdapterError("browser-use returned no final result")
        return str(result)


class BrowserUseTmsAdapter:
    """A browser-use TMS surface that can READ a load or a payable, and nothing else.

    Every method here is a read. There is no write method to call, no way to hand a caller a write
    ledger, and no path by which caller input becomes the agent's task.
    """

    def __init__(
        self,
        *,
        runner: BrowserUseTaskTransport | None = None,
        config: BrowserUseConfig | None = None,
        tool_context: ToolContext,
        store: WorkflowStore | None = None,
        run_id: int | None = None,
    ) -> None:
        self.config = config or BrowserUseConfig()
        self.runner = runner or ReadOnlyBrowserUseRunner()
        self.tool_context = tool_context
        self.store = store
        self.run_id = run_id
        self._validate_base_url()

    async def read_load(self, load_id: str) -> TmsLoadReadback:
        self._validate_load_id(load_id)
        self._require_tool("read_tms_load")
        payload = await self._observe(READ_LOAD_TASK, load_id)
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
        payload = await self._observe(READ_PAYABLE_TASK, load_id)
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

    async def _observe(self, task_id: str, load_id: str) -> str:
        """The ONLY way anything runs here: a vetted task id plus validated data.

        There is no string in this method into which caller input is spliced, and no branch that
        forwards a caller-supplied task.
        """
        return await self.runner.run_vetted(
            task_id,
            base_url=self.config.base_url.rstrip("/"),
            load_id=load_id,
            allowed_domains=list(self.config.allowed_domains),
            headless=self.config.headless,
        )

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


def read_load_sync(adapter: BrowserUseTmsAdapter, load_id: str) -> TmsLoadReadback:
    return asyncio.run(adapter.read_load(load_id))


def read_payable_sync(adapter: BrowserUseTmsAdapter, load_id: str) -> TmsPayableReadback:
    return asyncio.run(adapter.read_payable(load_id))


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
