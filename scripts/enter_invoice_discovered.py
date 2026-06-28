"""Gated invoice write driven ONLY by the agent-discovered field map — no hardcoded TMS selectors.

End-to-end agnostic proof: the discovery agent authors the field map from the live DOM, then the
generic DiscoveredInvoiceLedger drives the same gated enter_approved_payable path through those
discovered selectors. The TMS-specific seams (customer resolution, the hidden-id bind, the readback)
are injected and clearly separated from the generic form driving.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

from enter_truckingoffice_invoice import seed_approved_run  # noqa: E402
from freight_recon.cdp_session import CdpBrowserSession  # noqa: E402
from freight_recon.discovered_write import DiscoveredInvoiceLedger  # noqa: E402
from freight_recon.screen_discovery import discover_invoice_form, extract_form_schema, openai_completer  # noqa: E402
from freight_recon.tms_write import ExecutionStatusUpdate, approved_amount_for_run, enter_approved_payable  # noqa: E402
from freight_recon.truckingoffice_write import (  # noqa: E402
    DEFAULT_BASE_URL,
    _extract_invoice_rows_js,
    find_or_create_customer,
    numeric_invoice_number,
    parse_invoice_readback,
)
from freight_recon.workflow import WorkflowState, WorkflowStore  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "data" / "active_workspace" / "truckingoffice_discovered.sqlite3"))
    parser.add_argument("--seed-load", default="LD-560004")
    parser.add_argument("--corpus", default=str(ROOT / "data" / "synthetic_corpus"))
    parser.add_argument("--cdp-url", default="http://localhost:9222")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--invoice-form-url", default=DEFAULT_BASE_URL + "/no_load_invoice/new")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--acknowledge-real-write", action="store_true")
    args = parser.parse_args()

    Path(args.db).unlink(missing_ok=True)
    store = WorkflowStore(args.db)
    run_id = seed_approved_run(store, Path(args.corpus), args.seed_load)
    run = store.get_run(run_id)
    approved = approved_amount_for_run(store, run_id)
    print(f"run {run_id}: load={run.load_id} carrier={run.carrier!r} approved_amount={approved}")

    base = args.base_url.rstrip("/")

    def on_status(u: ExecutionStatusUpdate) -> None:
        print(f"  [{u.phase.value}] {u.message}")

    with CdpBrowserSession(cdp_url=args.cdp_url, url_filter="truckingoffice") as session:
        # 1) The agent reads the screen and AUTHORS the field map (no hand-written JSON).
        schema = extract_form_schema(session, args.invoice_form_url)
        form = discover_invoice_form(schema, complete=openai_completer(model=args.model))
        print("\nAgent-discovered map driving this write:")
        print(json.dumps({"amount": form.amount_selector, "invoice_number": form.invoice_number_selector,
                          "description": form.description_selector, "bill_to": form.bill_to_selector,
                          "submit": form.submit_label, "writable": form.is_writable()}, indent=2))

        # 2) TMS-specific seams (injected): resolve the customer, bind the hidden id, read back /invoices.
        def apply_customer(s, cid):
            s.evaluate("(function(id){var a=document.getElementById('invoice_customer_id');if(a)a.value=id;"
                       "var b=document.getElementById('customer');if(b)b.value=id;})(" + json.dumps(cid) + ")")

        def readback(load_id):
            inv = numeric_invoice_number(load_id)
            session.navigate(f"{base}/invoices")
            rows = session.evaluate(_extract_invoice_rows_js()) or []
            amt = parse_invoice_readback(rows, inv) if inv else None
            return None if amt is None else {"amount": amt, "carrier": None, "external_ref": load_id, "idempotency_key": load_id}

        ledger = DiscoveredInvoiceLedger(
            session=session,
            form=form,
            resolve_customer=lambda name: find_or_create_customer(session, name, base_url=base),
            apply_customer=apply_customer,
            readback_fn=readback,
            invoice_number_transform=numeric_invoice_number,
            base_url=base,
            approved_write_hosts=["secure.truckingoffice.com"],
            real_write_acknowledged=args.acknowledge_real_write,
        )
        print()
        outcome = enter_approved_payable(store, ledger, run_id, amount=approved, on_status=on_status)
    store.close()
    print(json.dumps(outcome.model_dump(mode="json"), indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
