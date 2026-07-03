"""Point the discovery agent at a TMS invoice form it was never told about and let it author the map.

Deterministic DOM extraction over CDP + LLM reasoning (which field means what, from labels alone).
Proves system-agnostic navigation: the agent re-derives the TruckingOffice field map with no
hand-written screen-map JSON in the loop.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

from freight_recon.cdp_session import CdpBrowserSession  # noqa: E402
from freight_recon.screen_discovery import discover_invoice_form, extract_form_schema, openai_completer  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="https://secure.truckingoffice.com/no_load_invoice/new")
    parser.add_argument("--cdp-url", default="http://localhost:9222")
    parser.add_argument("--model", default=os.getenv("NEYMA_SCREEN_DISCOVERY_MODEL", "gpt-4.1-mini"))
    args = parser.parse_args()

    with CdpBrowserSession(cdp_url=args.cdp_url, url_filter="truckingoffice") as session:
        schema = extract_form_schema(session, args.url)
    print(f"Agent saw {len(schema.fields)} fields on {schema.url}")
    print("  labels:", ", ".join(f.label for f in schema.fields if f.label))

    disc = discover_invoice_form(schema, complete=openai_completer(model=args.model))
    print("\nAgent-authored invoice map (no hand-written JSON):")
    print(json.dumps({
        "bill_to": disc.bill_to_selector,
        "amount": disc.amount_selector,
        "invoice_number": disc.invoice_number_selector,
        "description": disc.description_selector,
        "invoice_date": disc.date_selector,
        "submit": disc.submit_label,
        "notes": disc.notes,
        "writable": disc.is_writable(),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
