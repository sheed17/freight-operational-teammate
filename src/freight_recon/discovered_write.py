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
        repair_fn: Callable[[str, dict], dict] | None = None,
        max_heal_retries: int = 2,
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
        # repair_fn(error, values)->corrected non-money values. None disables self-heal (single attempt).
        self.repair_fn = repair_fn
        self.max_heal_retries = max_heal_retries
        self._written_keys: dict[str, str] = {}
        self._approved_write_hosts = tuple(approved_write_hosts)
        self._real_write_acknowledged = real_write_acknowledged

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
        existing = self.get_payable(load_id)
        if existing is not None:
            return PayableWriteResult(
                run_id=run_id,
                load_id=load_id,
                idempotency_key=key,
                status=PayableWriteStatus.DUPLICATE_BLOCKED,
                external_ref=existing.get("external_ref") if isinstance(existing, dict) else None,
                note="an invoice already exists for this reference; duplicate entry blocked",
            )

        # Concept->value. The agent's discovered selectors map concepts to fields; self-heal may revise
        # these values — except `amount`, which is the human-approved figure and is never repairable.
        values = {
            "amount": amount,
            "invoice_number": self.invoice_number_transform(load_id) or "",
            "description": str(charges) if charges else f"Load {load_id} — {carrier}",
            "bill_to": carrier,
        }
        try:
            error = self._fill_and_submit(values, customer_id)
        except Exception as exc:  # noqa: BLE001 - browser/TMS write errors fail closed through adapter status
            return _fail(str(exc)[:160])
        heals: list[str] = []
        retries = 0
        while error and self.repair_fn is not None and retries < self.max_heal_retries:
            retries += 1
            repair = dict(self.repair_fn(error, dict(values)) or {})
            repair.pop("amount", None)  # MONEY INVARIANT: self-heal can fix navigation, never the amount
            repair = {k: str(v) for k, v in repair.items() if k in values}
            if not repair:
                break
            heals.append(str(error)[:60])
            values.update(repair)
            try:
                error = self._fill_and_submit(values, customer_id)
            except Exception as exc:  # noqa: BLE001
                return _fail(str(exc)[:160])

        if error:
            return _fail(f"TMS rejected the invoice: {str(error)[:160]}")
        note = "invoice saved via agent-discovered field map"
        if heals:
            note += f" (self-healed {len(heals)}x past: {'; '.join(heals)})"
        self._written_keys[load_id] = key
        return PayableWriteResult(
            run_id=run_id, load_id=load_id, idempotency_key=key,
            status=PayableWriteStatus.WRITTEN, external_ref=str(load_id), note=note,
        )

    def _fill_and_submit(self, values: dict, customer_id: str) -> str:
        """Fill the discovered selectors with ``values`` and submit; return the TMS error flash (or '')."""
        authorize_write_host(
            urlparse(self.form.url).hostname,
            approved_hosts=self._approved_write_hosts,
            acknowledged=self._real_write_acknowledged,
        )
        self.session.navigate(self.form.url)
        selectors = {
            "amount": self.form.amount_selector,
            "invoice_number": self.form.invoice_number_selector,
            "description": self.form.description_selector,
            "bill_to": self.form.bill_to_selector,
        }
        for concept, sel in selectors.items():
            if sel and values.get(concept) not in (None, ""):
                if not self._set(sel, values[concept]):
                    return f"Could not set discovered {concept} field ({sel})"
        self.apply_customer(self.session, customer_id)
        if not self._click_submit(self.form.submit_label):
            return f"Could not click submit button labeled {self.form.submit_label!r}"
        time.sleep(_SAVE_SETTLE_SECONDS)
        return self.session.evaluate(_ERROR_FLASH_JS) or ""

    def get_payable(self, load_id: str) -> dict | None:
        record = self.readback_fn(load_id)
        if record is None:
            return None
        return {**record, "idempotency_key": self._written_keys.get(load_id)}

    def _set(self, selector: str | None, value: str) -> bool:
        if selector:
            return bool(self.session.evaluate(_set_field_js(selector, value)))
        return False

    def _click_submit(self, label: str) -> bool:
        return bool(self.session.evaluate(_click_submit_js(label)))


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
