"""Multi-step gated write: drive a chain of sub-forms into one financial record.

The single-form ledger (`discovered_write`) assumes one form, one amount field, one submit. Real TMSs
often aren't shaped that way — transporters.io creates an invoice across a wizard (order details ->
line-item amount -> raise invoice), and the amount lives on a line-item sub-step, not a single total.

This ledger generalizes the write to an ordered list of :class:`WriteSubStep`s and plugs into the same
gated `enter_approved_payable` seam (write_payable / get_payable). The Safety Spine is preserved by one
hard rule: **exactly one sub-step is the money sub-step, and the human-approved amount is entered there
and nowhere else.** Zero or multiple money sub-steps fail closed; any sub-step error fails closed;
verify-by-readback still gates DONE. System-specific binding (e.g. a hidden customer id) is an injected
per-sub-step `apply` callable, consistent with the rest of the codebase.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable
from urllib.parse import urlparse

from freight_recon.screen_discovery import BrowserSession
from freight_recon.tms_write import PayableWriteResult, PayableWriteStatus
from freight_recon.truckingoffice_write import authorize_write_host

_SETTLE_SECONDS = 3.5


@dataclass
class WriteSubStep:
    name: str                                  # human label, e.g. "order details" / "line item"
    url: str | None = None                     # navigate here first (None = stay on current page)
    set_values: dict = field(default_factory=dict)   # {selector: value} entered on this sub-step
    amount_selector: str | None = None         # if set, the APPROVED amount is entered here (the binding)
    submit_label: str = "Save"
    apply: Callable[[BrowserSession, dict], None] | None = None  # optional system-specific bind (hidden ids, etc.)


class MultiStepInvoiceLedger:
    def __init__(
        self,
        *,
        session: BrowserSession,
        substeps: list[WriteSubStep],
        readback_fn: Callable[[str], dict | None],
        base_url: str,
        approved_write_hosts=(),
        real_write_acknowledged: bool = False,
        settle_seconds: float = _SETTLE_SECONDS,
    ) -> None:
        authorize_write_host(
            urlparse(base_url).hostname, approved_hosts=approved_write_hosts, acknowledged=real_write_acknowledged
        )
        self.session = session
        self.substeps = substeps
        self.readback_fn = readback_fn
        self.settle_seconds = settle_seconds

    def write_payable(
        self, *, run_id: int, load_id: str, carrier: str, amount: str, charges, key: str
    ) -> PayableWriteResult:
        def _fail(note: str) -> PayableWriteResult:
            return PayableWriteResult(run_id=run_id, load_id=load_id, idempotency_key=key,
                                      status=PayableWriteStatus.ADAPTER_FAILED, external_ref=None, note=note)

        money_steps = [s for s in self.substeps if s.amount_selector]
        if len(money_steps) != 1:
            # Exactly one money sub-step keeps the binding unambiguous — the approved amount goes to
            # one place. Zero or several is a malformed flow; refuse rather than guess where money goes.
            return _fail(f"multi-step write must have exactly one money sub-step, found {len(money_steps)}")

        ctx = {"load_id": load_id, "carrier": carrier, "amount": amount, "key": key}
        for step in self.substeps:
            if step.url:
                self.session.navigate(step.url)
            for selector, value in step.set_values.items():
                if not self._set(selector, value):
                    return _fail(f"{step.name}: could not set field {selector}")
            if step.amount_selector:
                # THE money binding — the human-approved amount, entered only here.
                if not self._set(step.amount_selector, amount):
                    return _fail(f"{step.name}: could not set amount field {step.amount_selector}")
            if step.apply is not None:
                step.apply(self.session, ctx)
            if not self._click(step.submit_label):
                return _fail(f"{step.name}: could not click {step.submit_label!r}")
            time.sleep(self.settle_seconds)
            error = self.session.evaluate(_ERROR_FLASH_JS)
            if error:
                return _fail(f"{step.name}: TMS rejected — {str(error)[:140]}")

        return PayableWriteResult(run_id=run_id, load_id=load_id, idempotency_key=key,
                                  status=PayableWriteStatus.WRITTEN, external_ref=str(load_id),
                                  note=f"invoice created via {len(self.substeps)}-step flow")

    def get_payable(self, load_id: str) -> dict | None:
        return self.readback_fn(load_id)

    def _set(self, selector: str, value: str) -> bool:
        return bool(self.session.evaluate(_set_field_js(selector, value)))

    def _click(self, label: str) -> bool:
        return bool(self.session.evaluate(_click_submit_js(label)))


def _set_field_js(selector: str, value: str) -> str:
    import json
    return (
        "(function(sel,val){var el=document.querySelector(sel);"
        "if(el){el.value=val;el.dispatchEvent(new Event('input',{bubbles:true}));"
        "el.dispatchEvent(new Event('change',{bubbles:true}));return true;}return false;})("
        + json.dumps(selector) + "," + json.dumps(value) + ")"
    )


def _click_submit_js(label: str) -> str:
    import json
    return (
        "(function(label){var b=[...document.querySelectorAll('button,input[type=submit],a.btn')]"
        ".find(e=>((e.innerText||e.value||'').trim().toLowerCase()).indexOf(label.toLowerCase())>=0);"
        "if(b){b.click();return true;}return false;})(" + json.dumps(label) + ")"
    )


_ERROR_FLASH_JS = (
    "(function(){return [...document.querySelectorAll('.alert-danger,.error,.invalid-feedback,"
    ".field_with_errors,.is-invalid')].map(e=>e.innerText.trim()).filter(Boolean).join('; ');})()"
)
