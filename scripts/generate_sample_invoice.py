"""Generate a realistic sample carrier freight invoice PDF (with a known-answer JSON).

Used to exercise the extraction pipeline without needing a real scanned invoice,
and as the seed of the golden set: the emitted ``*.expected.json`` is the ground
truth to score field-by-field extraction against.

Usage:
    python scripts/generate_sample_invoice.py [output_dir]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

# --- Known answer (ground truth) for this invoice ---------------------------
INVOICE = {
    "invoice_number": "TRK-2024-88913",
    "carrier_name": "Sunbelt Freight Carriers LLC",
    "load_or_pro": "LD-559210",
    "linehaul_amount": "1250.00",
    "fuel_surcharge": "187.50",
    "accessorials": [
        {"name": "detention", "amount": "120.00"},
        {"name": "lumper", "amount": "85.00"},
    ],
    "total_amount": "1642.50",
    "invoice_date": "2024-11-18",
}


def _draw(c: canvas.Canvas) -> None:
    w, h = LETTER
    left = 0.75 * inch
    y = h - 0.9 * inch

    c.setFont("Helvetica-Bold", 18)
    c.drawString(left, y, INVOICE["carrier_name"])
    y -= 0.24 * inch
    c.setFont("Helvetica", 10)
    c.drawString(left, y, "4820 Interstate Commerce Dr, Memphis, TN 38118")
    y -= 0.16 * inch
    c.drawString(left, y, "MC# 778413   DOT# 2991045   billing@sunbeltfreight.example")

    c.setFont("Helvetica-Bold", 22)
    c.drawRightString(w - 0.75 * inch, h - 0.95 * inch, "FREIGHT INVOICE")

    y -= 0.5 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, f"Invoice #: {INVOICE['invoice_number']}")
    c.drawRightString(w - 0.75 * inch, y, f"Invoice Date: {INVOICE['invoice_date']}")
    y -= 0.22 * inch
    c.setFont("Helvetica", 11)
    c.drawString(left, y, f"Load / PRO #: {INVOICE['load_or_pro']}")
    c.drawRightString(w - 0.75 * inch, y, "Terms: Net 30")

    y -= 0.3 * inch
    c.setFont("Helvetica", 10)
    c.drawString(left, y, "Bill To: Apex Logistics Brokerage   |   Origin: Dallas, TX   ->   Dest: Atlanta, GA")

    # Charges table
    y -= 0.45 * inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(left, y, "Description")
    c.drawRightString(w - 0.75 * inch, y, "Amount (USD)")
    y -= 0.08 * inch
    c.line(left, y, w - 0.75 * inch, y)
    y -= 0.26 * inch

    rows = [
        ("Linehaul - Dry Van 53'", INVOICE["linehaul_amount"]),
        ("Fuel Surcharge (15%)", INVOICE["fuel_surcharge"]),
    ]
    for acc in INVOICE["accessorials"]:
        rows.append((f"Accessorial - {acc['name'].title()}", acc["amount"]))

    c.setFont("Helvetica", 11)
    for desc, amt in rows:
        c.drawString(left, y, desc)
        c.drawRightString(w - 0.75 * inch, y, f"${float(amt):,.2f}")
        y -= 0.26 * inch

    y -= 0.05 * inch
    c.line(left, y, w - 0.75 * inch, y)
    y -= 0.3 * inch
    c.setFont("Helvetica-Bold", 13)
    c.drawString(left, y, "TOTAL DUE")
    c.drawRightString(w - 0.75 * inch, y, f"${float(INVOICE['total_amount']):,.2f}")

    y -= 0.7 * inch
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(left, y, "Remit payment within 30 days. Reference Load/PRO # on all correspondence.")
    c.showPage()
    c.save()


def main(out_dir: str = "data/samples") -> None:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pdf_path = out / "carrier_invoice_sample.pdf"
    json_path = out / "carrier_invoice_sample.expected.json"

    _draw(canvas.Canvas(str(pdf_path), pagesize=LETTER))
    json_path.write_text(json.dumps(INVOICE, indent=2), encoding="utf-8")

    print(f"Wrote sample invoice PDF:  {pdf_path}")
    print(f"Wrote known-answer JSON:   {json_path}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "data/samples")
