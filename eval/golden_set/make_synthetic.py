"""Generate synthetic carrier-invoice fixtures to test the eval harness itself.

Produces 3 simple text PDFs (via PyMuPDF — no extra deps), their ground truth, and
two mock-extraction files (v1 with deliberate errors, v2 with two of them fixed) so
the scoring, calibration, failure-mode, and --compare paths can all be exercised
WITHOUT any API key. This is the "test the harness before trusting it" step.

Run:  python eval/golden_set/make_synthetic.py
"""

from __future__ import annotations

import json
from pathlib import Path

import fitz  # PyMuPDF

HERE = Path(__file__).resolve().parent
DOCS = HERE / "documents"
GROUND_TRUTH = HERE / "ground_truth.json"
MOCK_V1 = HERE / "mock_v1.json"
MOCK_V2 = HERE / "mock_v2.json"


# (filename, lines-to-draw, ground-truth dict)
FIXTURES = [
    (
        "invoice_001.pdf",
        [
            "Swift Transport LLC",
            "Invoice #: INV-2024-8847        Date: 2024-03-15",
            "Load #: L-449821",
            "",
            "Linehaul .................. $1,150.00",
            "Fuel Surcharge ............ $87.50",
            "Detention ................. $150.00",
            "TOTAL DUE ................. $1,387.50",
        ],
        {
            "invoice_number": "INV-2024-8847",
            "carrier_name": "Swift Transport LLC",
            "load_or_pro_number": "L-449821",
            "linehaul_amount": 1150.00,
            "fuel_surcharge": 87.50,
            "accessorials": [{"name": "detention", "amount": 150.00}],
            "total_amount": 1387.50,
            "invoice_date": "2024-03-15",
        },
    ),
    (
        "invoice_002.pdf",
        [
            "Midwest Freight Inc",
            "Bill #: 84729-A     Invoice Date: 2024-03-18",
            "PRO: PRO-9921044",
            "",
            "Base Rate ................. $2,200.00",
            "FSC ....................... $330.00",
            "Amount Due ................ $2,530.00",
        ],
        {
            "invoice_number": "84729-A",
            "carrier_name": "Midwest Freight Inc",
            "load_or_pro_number": "PRO-9921044",
            "linehaul_amount": 2200.00,
            "fuel_surcharge": 330.00,
            "accessorials": [],
            "total_amount": 2530.00,
            "invoice_date": "2024-03-18",
        },
    ),
    (
        "invoice_003.pdf",
        [
            "Lone Star Carriers",
            "Ref #: RB-7781      2024-03-20",
            "Shipment ID: L-44982",
            "",
            "Freight Charge ............ $1,875.00",
            "Fuel Adj .................. $281.25",
            "Lumper .................... $95.00",
            "Detention ................. $120.00",
            "Balance Due ............... $2,371.25",
        ],
        {
            "invoice_number": "RB-7781",
            "carrier_name": "Lone Star Carriers",
            "load_or_pro_number": "L-44982",
            "linehaul_amount": 1875.00,
            "fuel_surcharge": 281.25,
            "accessorials": [
                {"name": "lumper", "amount": 95.00},
                {"name": "detention", "amount": 120.00},
            ],
            "total_amount": 2371.25,
            "invoice_date": "2024-03-20",
        },
    ),
]


def _draw(path: Path, lines: list[str]) -> None:
    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for i, line in enumerate(lines):
        size = 16 if i == 0 else 11
        page.insert_text((72, y), line, fontsize=size, fontname="helv")
        y += 26 if i == 0 else 20
    doc.save(path)
    doc.close()


def _f(value, conf, note=None):
    d = {"value": value, "confidence": conf}
    if note:
        d["extraction_note"] = note
    return d


def build_mock_v1() -> dict:
    """What the model 'produced' on the first prompt — with deliberate, varied errors."""
    return {
        # Clean doc — all correct, honest high confidence.
        "invoice_001.pdf": {
            "invoice_number": _f("INV-2024-8847", 0.97),
            "carrier_name": _f("Swift Transport LLC", 0.96),
            "load_or_pro_number": _f("L-449821", 0.95),
            "linehaul_amount": _f(1150.00, 0.96),
            "fuel_surcharge": _f(87.50, 0.93),
            "accessorials": [{"name": "detention", "amount": 150.00, "confidence": 0.90}],
            "total_amount": _f(1387.50, 0.95),
            "invoice_date": _f("2024-03-15", 0.97),
        },
        # Overconfident WRONG linehaul (required) + missed fuel surcharge + near-match carrier.
        "invoice_002.pdf": {
            "invoice_number": _f("84729-A", 0.96),
            "carrier_name": _f("Midwest Freight", 0.92),  # near-match -> CORRECT
            "load_or_pro_number": _f("PRO-9921044", 0.93),
            "linehaul_amount": _f(2350.00, 0.91, "read the base rate line"),  # WRONG, overconfident
            "fuel_surcharge": _f(None, 0.30, "could not locate FSC reliably"),  # NOT_FOUND
            "accessorials": [],
            "total_amount": _f(2530.00, 0.94),
            "invoice_date": _f("2024-03-18", 0.97),
        },
        # Overconfident truncated PRO (required) + one accessorial missed.
        "invoice_003.pdf": {
            "invoice_number": _f("RB-7781", 0.95),
            "carrier_name": _f("Lone Star Carriers", 0.94),
            "load_or_pro_number": _f("L-449", 0.88, "shipment id label was non-standard"),  # WRONG truncation
            "linehaul_amount": _f(1875.00, 0.90),
            "fuel_surcharge": _f(281.25, 0.80),
            "accessorials": [{"name": "lumper", "amount": 95.00, "confidence": 0.85}],  # missed detention
            "total_amount": _f(2371.25, 0.93),
            "invoice_date": _f("2024-03-20", 0.96),
        },
    }


def build_mock_v2() -> dict:
    """A 'tuned prompt' run — fixes the two required-field errors; fuel still missed."""
    v2 = json.loads(json.dumps(build_mock_v1()))
    v2["invoice_002.pdf"]["linehaul_amount"] = _f(2200.00, 0.94)  # fixed
    v2["invoice_003.pdf"]["load_or_pro_number"] = _f("L-44982", 0.92)  # fixed truncation
    v2["invoice_003.pdf"]["accessorials"] = [
        {"name": "lumper", "amount": 95.00, "confidence": 0.88},
        {"name": "detention", "amount": 120.00, "confidence": 0.86},
    ]
    return v2


def main() -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    ground_truth = {}
    for name, lines, truth in FIXTURES:
        _draw(DOCS / name, lines)
        ground_truth[name] = truth
    GROUND_TRUTH.write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")
    MOCK_V1.write_text(json.dumps(build_mock_v1(), indent=2), encoding="utf-8")
    MOCK_V2.write_text(json.dumps(build_mock_v2(), indent=2), encoding="utf-8")
    print(f"Wrote {len(FIXTURES)} synthetic PDFs to {DOCS}")
    print(f"Wrote ground truth: {GROUND_TRUTH}")
    print(f"Wrote mock runs: {MOCK_V1.name}, {MOCK_V2.name}")


if __name__ == "__main__":
    main()
