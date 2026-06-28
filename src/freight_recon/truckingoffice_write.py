"""Deterministic, gated invoice write + readback for TruckingOffice (the live design-partner TMS).

This is the real-TMS realization of the same execution seam the mock uses
(:class:`~freight_recon.tms_write.MockTmsWriteLedger`): ``write_payable`` / ``get_payable``. It plugs
into the gated ``enter_approved_payable`` path unchanged, so every safety gate (approved-amount
binding, idempotency, verify-by-readback, pause brake, audit) carries over to the real TMS.

Two deliberate choices keep money-path risk low:

1. **Deterministic, not LLM.** The write fills the mapped form fields by selector and the verify reads
   the ``/invoices`` ledger by selector. An LLM never decides an amount or interprets the
   confirmation — matching the rule that verify-by-readback must not depend on a model reading a screen.
2. **Explicit, audited real-host authorization.** A non-localhost host is refused unless it is on an
   explicit approved list AND a human acknowledged going live. There is no silent default that lets a
   real write happen.

Mapping from the payable seam to TruckingOffice's AR invoice:
``load_id`` -> invoice number (idempotency reference), ``carrier`` -> customer (bill-to),
``amount`` -> Total Charge. See ``configs/tms/truckingoffice_screen_map.json``.
"""

from __future__ import annotations

import re
import time
from typing import Callable, Protocol, Sequence
from urllib.parse import urlparse

# A Save click fires an async form POST that redirects on success. Reading or navigating before it
# lands aborts the write, so we settle after every Save before observing the result.
_SAVE_SETTLE_SECONDS = 3.5

from freight_recon.tms_write import PayableWriteResult, PayableWriteStatus, TmsWriteError

DEFAULT_BASE_URL = "https://secure.truckingoffice.com"
_LOCAL_HOSTS = {"localhost", "127.0.0.1"}


class RealTmsWriteNotAuthorized(TmsWriteError):
    """Raised when a write is aimed at a real (non-local) TMS host without explicit acknowledgement."""


def authorize_write_host(
    host: str | None, *, approved_hosts: Sequence[str] = (), acknowledged: bool = False
) -> None:
    """Fail-closed gate for real-TMS writes.

    Localhost is always allowed (mock). Any other host must be BOTH on ``approved_hosts`` AND
    accompanied by ``acknowledged=True`` (a human turned the live switch on). Otherwise refuse —
    there is no implicit path to writing a real system of record.
    """
    h = (host or "").strip().lower()
    if h in _LOCAL_HOSTS:
        return
    approved = {a.strip().lower() for a in approved_hosts}
    if acknowledged and h in approved:
        return
    raise RealTmsWriteNotAuthorized(
        f"real TMS host {host!r} is not authorized for write — it must be on the approved-hosts list "
        "and accompanied by an explicit human acknowledgement to go live"
    )


def numeric_invoice_number(load_id: str) -> str | None:
    """TruckingOffice requires a numeric invoice number. Derive it from the load/reference id's digits
    (e.g. 'LD-560008' -> '560008'). The full reference is preserved in the Custom Invoice Number field.
    Returns None when there are no digits to use (write then fails closed rather than guess)."""
    m = re.search(r"\d+", str(load_id or ""))
    return m.group(0) if m else None


def normalize_money(text: str | None) -> str | None:
    """'$2,450.00' -> '2450.00'. Returns None when no money value is present (fail-closed for verify)."""
    if text is None:
        return None
    m = re.search(r"(\d[\d,]*\.\d{2})", str(text))
    return m.group(1).replace(",", "") if m else None


def parse_invoice_readback(rows: Sequence[dict], invoice_number: str) -> str | None:
    """Deterministic verify: from the ``/invoices`` table rows, return the normalized Total Amount for
    the row whose Number equals ``invoice_number`` — or None.

    Fail-closed on ambiguity: zero matches OR more than one row with the same number returns None, so a
    duplicate/ambiguous ledger can never be read as a verified write (it routes the run to FAILED).
    """
    target = str(invoice_number).strip()
    matches = [r for r in rows if str(r.get("number", "")).strip() == target]
    if len(matches) != 1:
        return None
    return normalize_money(matches[0].get("total"))


def build_invoice_form_values(
    *,
    customer_id: str,
    customer_name: str,
    invoice_number: str,
    total_charge: str,
    custom_invoice_number: str | None = None,
    description: str | None = None,
    note: str | None = None,
) -> dict:
    """Return the exact form values to set on the No Load Invoice form, split by selector strategy.

    ``by_id`` carries the customer binding to BOTH hidden inputs (ids ``invoice_customer_id`` and
    ``customer``) — Rails reads the last duplicate ``invoice[customer_id]`` input, so setting only one
    yields "Customer can't be blank". This is the single most load-bearing detail of the write.
    """
    return {
        "by_name": {
            "customer_finder_field": customer_name,
            "invoice[invoice_number]": str(invoice_number),
            "invoice[invoice_number_override]": custom_invoice_number or "",
            "invoice[charge_description]": description or "",
            "invoice[total_charge]": str(total_charge),
            "invoice[note]": note or "",
        },
        "by_id": {
            "invoice_customer_id": str(customer_id),
            "customer": str(customer_id),
        },
    }


def parse_customer_id(rows: Sequence[dict], name: str) -> str | None:
    """From /addresses rows ({text, id}), return the customer id whose row text contains ``name``.

    Fail-closed on ambiguity: zero or more than one matching row returns None, so a write never binds
    to the wrong bill-to when names collide.
    """
    target = (name or "").strip().lower()
    if not target:
        return None
    matches = [r for r in rows if target in str(r.get("text", "")).lower()]
    if len(matches) != 1:
        return None
    return str(matches[0].get("id")) or None


def _first_customer_id(rows: Sequence[dict], name: str) -> str | None:
    """Lenient lookup: the FIRST customer row whose text contains ``name``. Used by find-or-create so a
    pre-existing (even duplicated) broker is reused instead of creating yet another stub."""
    target = (name or "").strip().lower()
    if not target:
        return None
    for r in rows:
        if target in str(r.get("text", "")).lower():
            return str(r.get("id")) or None
    return None


def find_or_create_customer(
    session: "BrowserSession", name: str, *, base_url: str = DEFAULT_BASE_URL, city: str = "Dallas", state: str = "Texas"
) -> str | None:
    """Resolve a customer (Address) id by name, creating a stub broker customer if none exists.

    Production-correct: when Neyma invoices a broker not yet on file, it creates the customer rather
    than guessing or failing. Reuse is lenient (first match) so it never creates a duplicate for a
    broker that already exists; creation only happens when there is no match at all.
    """
    base = base_url.rstrip("/")

    def _rows():
        session.navigate(f"{base}/addresses?object=customer")
        return session.evaluate(_addresses_rows_js()) or []

    existing = _first_customer_id(_rows(), name)
    if existing:
        return existing
    session.navigate(f"{base}/addresses/form?address_widget_id=customer&object=customer")
    session.evaluate(_create_customer_js(name, city, state))
    time.sleep(_SAVE_SETTLE_SECONDS)  # let the create POST + redirect land before re-reading
    return _first_customer_id(_rows(), name)  # re-read to confirm + capture the new id


class BrowserSession(Protocol):
    """Minimal in-session browser the ledger drives. The real impl is CDP over a human-logged-in
    Chrome; tests pass a fake. Keeping this tiny keeps the ledger's logic unit-testable."""

    def navigate(self, url: str) -> None: ...
    def evaluate(self, expression: str) -> object: ...


class TruckingOfficeInvoiceLedger:
    """Real-TMS execution ledger implementing the ``write_payable``/``get_payable`` seam over CDP.

    Drops into :func:`freight_recon.tms_write.enter_approved_payable` unchanged. It never decides an
    amount — it writes the approved amount it is handed and reads back what the TMS displays.
    """

    def __init__(
        self,
        *,
        session: BrowserSession,
        customer_resolver: Callable[[str], str | None],
        base_url: str = DEFAULT_BASE_URL,
        approved_write_hosts: Sequence[str] = (),
        real_write_acknowledged: bool = False,
    ) -> None:
        self.session = session
        self.base_url = base_url.rstrip("/")
        self.customer_resolver = customer_resolver
        self._written_keys: dict[str, str] = {}
        # Fail-closed authorization happens at construction: an unauthorized target can't be built.
        authorize_write_host(
            urlparse(self.base_url).hostname,
            approved_hosts=approved_write_hosts,
            acknowledged=real_write_acknowledged,
        )

    def write_payable(
        self, *, run_id: int, load_id: str, carrier: str, amount: str, charges, key: str
    ) -> PayableWriteResult:
        customer_id = self.customer_resolver(carrier)
        if not customer_id:
            # No bill-to means we must not guess — fail closed before touching the form.
            return PayableWriteResult(
                run_id=run_id, load_id=load_id, idempotency_key=key,
                status=PayableWriteStatus.ADAPTER_FAILED,
                external_ref=None,
                note=f"no TruckingOffice customer resolved for {carrier!r}; refusing to write",
            )
        inv_no = numeric_invoice_number(load_id)
        if not inv_no:
            return PayableWriteResult(
                run_id=run_id, load_id=load_id, idempotency_key=key,
                status=PayableWriteStatus.ADAPTER_FAILED, external_ref=None,
                note=f"no numeric invoice number derivable from {load_id!r}; refusing to write",
            )
        existing = self.get_payable(load_id)
        if existing is not None:
            return PayableWriteResult(
                run_id=run_id,
                load_id=load_id,
                idempotency_key=key,
                status=PayableWriteStatus.DUPLICATE_BLOCKED,
                external_ref=existing.get("external_ref") if isinstance(existing, dict) else None,
                note="a TruckingOffice invoice already exists for this invoice number; duplicate entry blocked",
            )
        # TruckingOffice requires a non-blank charge description. Use the charge lines when present,
        # else a clear default tying the invoice to its load/carrier.
        description = str(charges) if charges else f"Load {load_id} — {carrier}"
        values = build_invoice_form_values(
            customer_id=customer_id, customer_name=carrier,
            invoice_number=inv_no, custom_invoice_number=load_id, total_charge=amount,
            description=description,
        )
        self.session.navigate(f"{self.base_url}/no_load_invoice/new")
        submitted = self.session.evaluate(_fill_and_save_js(values))
        if submitted is False:
            return PayableWriteResult(
                run_id=run_id,
                load_id=load_id,
                idempotency_key=key,
                status=PayableWriteStatus.ADAPTER_FAILED,
                external_ref=None,
                note="TruckingOffice form fill/submit failed before save; selector or submit button was not found",
            )
        time.sleep(_SAVE_SETTLE_SECONDS)  # let the invoice POST land (success redirects; failure keeps the error flash)
        error = self.session.evaluate(_error_flash_js())
        if error:
            return PayableWriteResult(
                run_id=run_id, load_id=load_id, idempotency_key=key,
                status=PayableWriteStatus.ADAPTER_FAILED, external_ref=None,
                note=f"TruckingOffice rejected the invoice: {str(error)[:160]}",
            )
        self._written_keys[load_id] = key
        return PayableWriteResult(
            run_id=run_id, load_id=load_id, idempotency_key=key,
            status=PayableWriteStatus.WRITTEN, external_ref=str(load_id),
            note="invoice saved via deterministic CDP fill",
        )

    def get_payable(self, load_id: str) -> dict | None:
        """Deterministic verify-by-readback: read the /invoices ledger and parse this invoice's total."""
        inv_no = numeric_invoice_number(load_id)
        if not inv_no:
            return None
        self.session.navigate(f"{self.base_url}/invoices")
        rows = self.session.evaluate(_extract_invoice_rows_js()) or []
        amount = parse_invoice_readback(rows, inv_no)
        if amount is None:
            return None  # fail-closed: unreadable/ambiguous -> verify mismatch -> FAILED, never DONE
        match = next((r for r in rows if str(r.get("number", "")).strip() == inv_no), {})
        return {
            "amount": amount,
            "carrier": match.get("customer"),
            "external_ref": str(load_id),
            "idempotency_key": self._written_keys.get(load_id),
        }


def _fill_and_save_js(values: dict) -> str:
    import json

    return (
        "(function(v){"
        "var ok=true;"
        "function setn(n,val){var el=document.querySelector('[name=\"'+n+'\"]');"
        "if(el){el.value=val;el.dispatchEvent(new Event('input',{bubbles:true}));"
        "el.dispatchEvent(new Event('change',{bubbles:true}));}else{ok=false;}}"
        "function setid(id,val){var el=document.getElementById(id);"
        "if(el){el.value=val;el.dispatchEvent(new Event('change',{bubbles:true}));}else{ok=false;}}"
        "for(var n in v.by_name){if(v.by_name[n]!==''&&v.by_name[n]!=null){setn(n,v.by_name[n]);}}"
        "for(var i in v.by_id){setid(i,v.by_id[i]);}"
        "var b=[...document.querySelectorAll('form button, form input[type=submit]')]"
        ".find(e=>/save/i.test(e.innerText||e.value||''));if(b){b.click();}else{ok=false;}"
        "return ok;"
        "})(" + json.dumps(values) + ")"
    )


def _error_flash_js() -> str:
    return (
        "(function(){return [...document.querySelectorAll('.alert-danger,.error,.invalid-feedback,"
        ".field_with_errors')].map(e=>e.innerText.trim()).filter(Boolean).join('; ');})()"
    )


def _addresses_rows_js() -> str:
    return (
        "[...document.querySelectorAll('table tbody tr')].map(function(r){"
        "var a=r.querySelector('a[href*=\"/addresses/\"]');"
        "return {text:r.innerText.replace(/\\s+/g,' ').trim(), id:a?a.getAttribute('href').split('/').pop():''};"
        "}).filter(r=>r.id)"
    )


def _create_customer_js(name: str, city: str, state: str) -> str:
    import json

    return (
        "(function(c){"
        "function setn(n,v){var el=document.querySelector('[name=\"'+n+'\"]');"
        "if(el){el.value=v;el.dispatchEvent(new Event('input',{bubbles:true}));"
        "el.dispatchEvent(new Event('change',{bubbles:true}));}}"
        "function sel(n,rx){var s=document.querySelector('[name=\"'+n+'\"]');if(!s)return;"
        "var o=[...s.options].find(o=>rx.test(o.text.trim()));if(o){s.value=o.value;"
        "s.dispatchEvent(new Event('change',{bubbles:true}));}}"
        "setn('address[name]',c.name);sel('address[customer_type_id]',/broker/i);"
        "setn('address[city]',c.city);sel('address[state_id]',new RegExp('^'+c.state+'$','i'));"
        "var b=[...document.querySelectorAll('form button, form input[type=submit]')]"
        ".find(e=>/save/i.test(e.innerText||e.value||''));if(b)b.click();"
        "})(" + json.dumps({"name": name, "city": city, "state": state}) + ")"
    )


def _extract_invoice_rows_js() -> str:
    return (
        "[...document.querySelectorAll('table tbody tr')].map(function(r){"
        "var c=[...r.querySelectorAll('td')].map(x=>x.innerText.trim().replace(/\\s+/g,' '));"
        "return {number:c[1], customer:c[3], total:c[4], invoiced_on:c[6]};"
        "}).filter(r=>r.number)"
    )
