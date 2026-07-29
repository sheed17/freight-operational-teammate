"""EP-14 — THE EFFECT-CAPABLE BROWSER-USE SURFACE (P4 adapter containment, R-07 scope).

This module is the write half of the browser-use split. It holds everything that can touch an
external system through a browser agent:

  * `NativeBrowserUseRunner` — the generic browser-agent driver. It runs an ARBITRARY natural-
    language task, so the task string decides what happens to the page. That is an actuation
    primitive in the same sense `cdp_session.evaluate()` is: whoever can hand it a task can make it
    do anything the browser can do. It lives HERE, on the effect-capable side, for exactly that
    reason.
  * `BrowserUseWriteLedger` — the authorized payable write, with verify-by-readback.

WHY THIS FILE EXISTS (the EP-14 relocation, not a new module). `browser_use_write` was ALREADY a
registered effect-capable adapter name in the frozen phase-0 inventory — in
`import_probe.ADAPTER_MODULES`, in `import_probe.EFFECT_CAPABLE_ADAPTERS`, in `entrypoint_probe`,
and in the baseline manifest — with no file behind it. The write ledger previously sat in
`browser_use_adapter`, which is why an ordinary read caller
(`scripts/read_tms_browser_use.py`) had a violation-capable edge: it imported a module that
co-located a write ledger and a generic browser-agent driver. Moving the write half into the slot
canonical authority had already reserved for it OCCUPIES A PRE-REGISTERED DESTINATION rather than
adding a module, and SWAPS one intra-adapter composition edge for another:

    before:  browser_use_adapter -> tms_write        (and read_tms_browser_use -> browser_use_adapter
                                                      was an EFFECT-CAPABLE violation)
    after:   browser_use_write   -> tms_write        (and read_tms_browser_use -> browser_use_adapter
                                                      is ordinary detection residue, not a violation)

Detection edges are unchanged at 14. The unauthorized violation set shrinks 2 -> 1.

WHAT MAY REACH THIS MODULE. `effect_boundary` is the only permitted application route. Nothing here
mints authority: `BrowserUseWriteLedger` cannot create or extend a grant, a witness, an approval or
a claim, and it cannot construct an `ExecutionCapability` — that class has no public constructor and
this module does not import it. The ledger operates a screen and reports what the TMS displays; the
decision that a write may happen at all is made before it is ever called.

THIS MODULE DELIBERATELY DOES NOT IMPORT `browser_use_adapter`. It carries its own JSON parsing and
its own readback task rather than reaching across to the read module, for two reasons: an edge from
the effect-capable module to the read module would GROW the authorized composition surface (14 ->
15), which the EP-14 relocation rules forbid; and the dependency direction that matters for
containment is that the read surface can never reach the write surface. The cost is a small amount
of duplicated text, which is the same trade `cdp_readonly` makes by owning its own transport rather
than reusing `cdp_session`'s.
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any, Callable, Protocol
from urllib.parse import urlparse

from .tms_adapter import TmsAdapterError
from .tms_write import PayableWriteResult, PayableWriteStatus


class BrowserUseRunner(Protocol):
    async def run(self, task: str, *, allowed_domains: list[str], headless: bool) -> str:
        ...


class NativeBrowserUseRunner:
    """Thin lazy wrapper around `browser-use[core]` — THE EFFECT-CAPABLE SUBSTRATE.

    It runs whatever task it is given. There is no vetting here and there is deliberately none: this
    is the unrestricted driver, and its containment is that only the effect-capable side of the
    split can reach it. The read adapter has its own runner that can express nothing but a vetted
    read (`browser_use_adapter.ReadOnlyBrowserUseRunner`).

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
    ``write_payable`` / ``get_payable`` seam as the mock ledger in :mod:`freight_recon.tms_write`,
    so the gated ``enter_approved_payable`` path (confirm-before-submit → submit → verify-by-readback
    → idempotency) drives a real browser **unchanged**. The TMS server owns idempotency/duplicate
    logic; this ledger only operates the screen and reports back what the TMS displays. It never
    decides an amount, and it never decides whether it is allowed to run.

    RETAINED FOR ITS DOCUMENTED FUTURE (P12). EP-14 relocated this class; it did not delete or
    weaken it. Removing a legitimate future write capability to make a P4 gate green would be
    exactly the false-green the containment work exists to prevent.
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


def _read_payables_task(url: str, load_id: str) -> str:
    return f"""
Open {url}
The payables table has columns: Load, Carrier, Amount, Reference, Key.
Find the EXACT row whose Load cell equals {load_id} (not any other load).
Return ONLY valid JSON with keys read from THAT row's cells: load_id, amount, carrier, external_ref, idempotency_key.
If there is no row whose Load equals {load_id}, return {{"load_id": null, "amount": null}}.
Money values must not include dollar signs.
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


# =============================================================================================
# THE BOUNDED, TYPED INVOICE WRITE (P4 EP-1 write-half, R-07 scope).
#
# This is the adapter side of the typed freight operation. It maps an already-validated
# `freight_operations.InvoiceWriteOperation` — identity and approved DATA, never behaviour — to a
# BOUNDED browser write. It is NOT `NativeBrowserUseRunner`: no method here accepts a task string, a
# selector, a URL, JavaScript or an adapter method from the caller. The task the browser runs is
# RENDERED HERE from the typed fields; the caller supplies only data.
#
# IT IMPORTS NO EFFECT MACHINERY. It does not know about capabilities, grants, witnesses or the
# checkpoint. It cannot mint or alter authority because it cannot reach any of it. The effect
# boundary is what validates the capability and decides the outcome; this returns plain evidence.
#
# IT SHIPS DARK. `write`/`readback` refuse a real (non-sandbox, non-loopback) target and refuse to
# run at all without an explicitly injected sandbox runner. So no real external write is performed:
# the bounded implementation EXISTS and is typed, but the live supervised write is P12, not P4.
# =============================================================================================

from dataclasses import dataclass as _dataclass


class SandboxOnlyWriteRefused(TmsAdapterError):
    """The bounded invoice write refused because the operation is not sandbox/loopback, or no
    sandbox runner is wired. The capability is dark; a real write is P12, not here. Fail closed."""


@_dataclass(frozen=True, slots=True)
class BoundedWriteResult:
    """Plain evidence of a bounded write attempt. The effect boundary translates it into its own
    outcome types; this carries no authority and no decision."""

    outcome: str                 # "ATTEMPTED" | "PREFLIGHT_REJECTED" | "OUTCOME_UNKNOWN"
    external_ref: str = ""
    detail: str = ""
    proof: str = ""              # for PREFLIGHT_REJECTED: the proof of non-occurrence
    exposure: str = ""           # for OUTCOME_UNKNOWN: the rendered exposure string (never a number)


@_dataclass(frozen=True, slots=True)
class BoundedReadback:
    """Plain readback evidence. `health_signal` is the POSITIVE control; `observed_fingerprint` is
    the material-facts fingerprint the boundary compares to the approval (None = unread)."""

    health_signal: bool
    observed_fingerprint: str | None
    detail: str = ""


def _is_loopback_base_url(base_url: str) -> bool:
    host = (urlparse(str(base_url or "")).hostname or "").lower()
    return host in {"localhost", "127.0.0.1", "::1"}


class SandboxInvoiceWriteAdapter:
    """The bounded invoice-write adapter behind the effect boundary (default for EP-1).

    `runner` is an optional sandbox browser-agent runner. It is NEVER handed a caller-authored task:
    `write`/`readback` render a FIXED task from the typed operation's data. With no runner wired the
    adapter still refuses to perform a real write — the capability is dark.

    A production sandbox would inject a runner AND a deterministic readback function; both are out of
    scope for P4 (they land with the P12 supervised-write integration).
    """

    def __init__(self, *, runner: "BrowserUseRunner | None" = None,
                 readback_fn: "Callable[[object], BoundedReadback] | None" = None) -> None:
        self.runner = runner
        self.readback_fn = readback_fn

    def _refuse_if_not_dark(self, op: object) -> None:
        if not getattr(op, "sandbox", False):
            raise SandboxOnlyWriteRefused(
                "the invoice write adapter is dark: it performs no write for a non-sandbox "
                "operation. Live supervised writes are enabled and validated at P12, not P4.")
        base_url = str(getattr(op, "base_url", "") or "")
        if base_url and not _is_loopback_base_url(base_url):
            raise SandboxOnlyWriteRefused(
                f"refused: {base_url!r} is not a loopback sandbox host. A real TMS host requires the "
                "P12 approved-sandbox gate, which does not exist yet.")

    def write(self, op: object) -> BoundedWriteResult:
        """Perform the bounded write from typed data. Dark: refuses non-sandbox, and refuses to run
        without an injected sandbox runner (so no real external write occurs at P4)."""
        self._refuse_if_not_dark(op)
        if self.runner is None:
            raise SandboxOnlyWriteRefused(
                "no sandbox runner is wired, so no browser write is performed. The bounded task is "
                "defined and typed; executing it is the P12 supervised-write integration.")
        task = _render_invoice_write_task(op)      # FIXED task rendered from typed DATA only
        data = _parse_json_result(asyncio.run(
            self.runner.run(task, allowed_domains=["localhost", "127.0.0.1"], headless=True)))
        return BoundedWriteResult(
            outcome="ATTEMPTED",
            external_ref=str(data.get("external_ref") or ""),
            detail=str(data.get("note") or "bounded invoice write attempted"))

    def readback(self, op: object) -> BoundedReadback:
        if self.readback_fn is not None:
            return self.readback_fn(op)
        return BoundedReadback(health_signal=False, observed_fingerprint=None,
                               detail="no deterministic readback wired (dark)")


def _render_invoice_write_task(op: object) -> str:
    """Render the FIXED browser task for a typed invoice write. The ONLY caller inputs are DATA
    (the approved amount, the load and invoice references, the target account) interpolated as
    literal text into a fixed instruction — never a task the caller authored, never a selector, URL
    or script the caller chose."""
    fields = dict(getattr(op, "approved_fields", {}) or {})
    amount = str(fields.get("amount", "") or "")
    customer = str(fields.get("customer", "") or "")
    base_url = str(getattr(op, "base_url", "") or "").rstrip("/")
    load_id = str(getattr(op, "load_id", "") or "")
    invoice_ref = str(getattr(op, "invoice_ref", "") or "")
    return (
        f"Open {base_url}/invoices/new?load_id={load_id}&invoice_ref={invoice_ref}\n"
        f"This is a TMS customer-invoice entry form. Type exactly {amount} into the amount input "
        f"(element id \"amount\") for customer {customer}.\n"
        f"Then click the button with id \"submit-invoice\".\n"
        "On the resulting confirmation page, read the text of elements id \"write-status\", id "
        "\"external-ref\", id \"note\".\n"
        "Return ONLY valid JSON with keys: status, external_ref, note.\n"
        "Do not navigate anywhere else and do not change any other field."
    )
