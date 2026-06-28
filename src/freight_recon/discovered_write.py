"""Drive a gated invoice write from an AGENT-DISCOVERED screen map — no per-TMS field code.

This closes the agnostic loop. The discovery agent authors a :class:`DiscoveredInvoiceForm` from the
live DOM; this ledger fills that form's fields purely by the discovered selectors and plugs into the
same gated ``enter_approved_payable`` path. The same code writes any TMS the agent can read.

What stays generic (driven by discovery): amount, invoice number, description, bill-to text, submit.
What is honestly system-specific and therefore injected (and itself discoverable later):
  - ``resolve_customer``  — map a broker name to the system's internal customer id (entity resolution).
  - ``apply_customer``    — bind that id on the form (e.g. hidden fields an autocomplete sets).
  - ``readback_fn``       — the deterministic verify read of the system of record.
The money rule is unchanged: the ledger writes the approved amount it is handed and never decides one;
verify-by-readback stays deterministic.
"""

from __future__ import annotations

import json
import time
from typing import Callable
from urllib.parse import urlparse

from freight_recon.screen_discovery import BrowserSession, DiscoveredInvoiceForm
from freight_recon.tms_write import PayableWriteResult, PayableWriteStatus
from freight_recon.truckingoffice_write import authorize_write_host

_SAVE_SETTLE_SECONDS = 3.5


class DiscoveredInvoiceLedger:
    def __init__(
        self,
        *,
        session: BrowserSession,
        form: DiscoveredInvoiceForm,
        resolve_customer: Callable[[str], str | None],
        apply_customer: Callable[[BrowserSession, str], None],
        readback_fn: Callable[[str], dict | None],
        invoice_number_transform: Callable[[str], str | None] = lambda x: x,
        base_url: str,
        approved_write_hosts=(),
        real_write_acknowledged: bool = False,
    ) -> None:
        authorize_write_host(
            urlparse(base_url).hostname, approved_hosts=approved_write_hosts, acknowledged=real_write_acknowledged
        )
        self.session = session
        self.form = form
        self.resolve_customer = resolve_customer
        self.apply_customer = apply_customer
        self.readback_fn = readback_fn
        self.invoice_number_transform = invoice_number_transform

    def write_payable(
        self, *, run_id: int, load_id: str, carrier: str, amount: str, charges, key: str
    ) -> PayableWriteResult:
        def _fail(note: str) -> PayableWriteResult:
            return PayableWriteResult(
                run_id=run_id, load_id=load_id, idempotency_key=key,
                status=PayableWriteStatus.ADAPTER_FAILED, external_ref=None, note=note,
            )

        if not self.form.is_writable():
            return _fail("discovered form is not writable (missing bill-to/amount/submit)")
        customer_id = self.resolve_customer(carrier)
        if not customer_id:
            return _fail(f"no customer resolved for {carrier!r}; refusing to write")

        # Everything below uses the agent-discovered selectors — there is no hardcoded TMS field name.
        self.session.navigate(self.form.url)
        self._set(self.form.amount_selector, amount)
        inv_no = self.invoice_number_transform(load_id)
        if self.form.invoice_number_selector and inv_no:
            self._set(self.form.invoice_number_selector, inv_no)
        if self.form.description_selector:
            self._set(self.form.description_selector, str(charges) if charges else f"Load {load_id} — {carrier}")
        if self.form.bill_to_selector:
            self._set(self.form.bill_to_selector, carrier)
        self.apply_customer(self.session, customer_id)

        self._click_submit(self.form.submit_label)
        time.sleep(_SAVE_SETTLE_SECONDS)
        error = self.session.evaluate(_ERROR_FLASH_JS)
        if error:
            return _fail(f"TMS rejected the invoice: {str(error)[:160]}")
        return PayableWriteResult(
            run_id=run_id, load_id=load_id, idempotency_key=key,
            status=PayableWriteStatus.WRITTEN, external_ref=str(load_id),
            note="invoice saved via agent-discovered field map",
        )

    def get_payable(self, load_id: str) -> dict | None:
        return self.readback_fn(load_id)

    def _set(self, selector: str | None, value: str) -> None:
        if selector:
            self.session.evaluate(_set_field_js(selector, value))

    def _click_submit(self, label: str) -> None:
        self.session.evaluate(_click_submit_js(label))


def _set_field_js(selector: str, value: str) -> str:
    return (
        "(function(sel,val){var el=document.querySelector(sel);"
        "if(el){el.value=val;el.dispatchEvent(new Event('input',{bubbles:true}));"
        "el.dispatchEvent(new Event('change',{bubbles:true}));return true;}return false;})("
        + json.dumps(selector) + "," + json.dumps(value) + ")"
    )


def _click_submit_js(label: str) -> str:
    return (
        "(function(label){var b=[...document.querySelectorAll('form button, form input[type=submit]')]"
        ".find(e=>((e.innerText||e.value||'').trim().toLowerCase())===label.toLowerCase());"
        "if(b){b.click();return true;}return false;})(" + json.dumps(label) + ")"
    )


_ERROR_FLASH_JS = (
    "(function(){return [...document.querySelectorAll('.alert-danger,.error,.invalid-feedback,"
    ".field_with_errors')].map(e=>e.innerText.trim()).filter(Boolean).join('; ');})()"
)
