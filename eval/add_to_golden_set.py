"""Interactively add a real document to the golden set.

Renders each page to a PNG you can open, prompts for the human-verified value of
each config field, validates the input, copies the PDF into golden_set/documents/,
and appends the entry to ground_truth.json.

Usage:
    python eval/add_to_golden_set.py path/to/real_invoice.pdf
    python eval/add_to_golden_set.py path/to/real_invoice.pdf --name invoice_021.pdf
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from extraction import load_config, render_pdf_to_pngs  # noqa: E402

EVAL_DIR = Path(__file__).resolve().parent
CONFIG_PATH = EVAL_DIR / "configs" / "carrier_invoice.yaml"
DOCS_DIR = EVAL_DIR / "golden_set" / "documents"
GROUND_TRUTH_PATH = EVAL_DIR / "golden_set" / "ground_truth.json"
PREVIEW_DIR = EVAL_DIR / "golden_set" / ".previews"


def _prompt_value(spec) -> object:
    label = f"  {spec.name} ({spec.type}{', required' if spec.required else ''})"
    while True:
        raw = input(f"{label}\n    > ").strip()
        if raw == "":
            if spec.required:
                print("    This field is required. Please enter a value.")
                continue
            return 0.0 if spec.name == "fuel_surcharge" else None
        if spec.type in ("decimal", "integer"):
            try:
                return float(raw) if spec.type == "decimal" else int(raw)
            except ValueError:
                print("    Not a number — try again.")
                continue
        if spec.type == "date":
            import datetime as dt
            try:
                dt.date.fromisoformat(raw)
                return raw
            except ValueError:
                print("    Use ISO format YYYY-MM-DD.")
                continue
        return raw


def _prompt_accessorials() -> list[dict]:
    print("  accessorials (enter 'name amount' per line, e.g. 'detention 150'; blank line to finish)")
    items: list[dict] = []
    while True:
        raw = input("    > ").strip()
        if raw == "":
            break
        parts = raw.rsplit(maxsplit=1)
        if len(parts) != 2:
            print("    Format: <name> <amount>")
            continue
        name, amount = parts
        try:
            items.append({"name": name.strip().lower(), "amount": float(amount.replace("$", "").replace(",", ""))})
        except ValueError:
            print("    Amount must be a number.")
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", help="Path to the PDF to add")
    parser.add_argument("--name", help="Filename to store it under (default: source filename)")
    args = parser.parse_args()

    src = Path(args.pdf)
    if not src.exists():
        print(f"PDF not found: {src}")
        return 2

    stored_name = args.name or src.name
    config = load_config(CONFIG_PATH)

    # Render previews so the human can read the actual document.
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    pngs = render_pdf_to_pngs(src)
    preview_paths = []
    for i, png in enumerate(pngs, 1):
        p = PREVIEW_DIR / f"{Path(stored_name).stem}_p{i}.png"
        p.write_bytes(png)
        preview_paths.append(p)
    print(f"\nRendered {len(pngs)} page(s). Open these to read the invoice while entering values:")
    for p in preview_paths:
        print(f"  {p}")
    print("\nEnter the correct (human-verified) value for each field. Blank = not present.\n")

    entry: dict = {}
    for spec in config.fields:
        if spec.type == "list":
            entry[spec.name] = _prompt_accessorials()
        else:
            entry[spec.name] = _prompt_value(spec)

    # Persist: copy PDF, append ground truth.
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, DOCS_DIR / stored_name)

    ground_truth = {}
    if GROUND_TRUTH_PATH.exists():
        ground_truth = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))
    ground_truth[stored_name] = entry
    GROUND_TRUTH_PATH.parent.mkdir(parents=True, exist_ok=True)
    GROUND_TRUTH_PATH.write_text(json.dumps(ground_truth, indent=2), encoding="utf-8")

    print(f"\nAdded {stored_name} to golden set. Now contains {len(ground_truth)} document(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
