"""Phase 1 demo: render a carrier invoice PDF, run vision extraction, print results.

Usage:
    python scripts/run_extraction.py [path/to/invoice.pdf]
    python scripts/run_extraction.py --render-only [path/to/invoice.pdf]

Reads provider + API key from the environment (.env supported via python-dotenv).
With --render-only it rasterizes the PDF and reports page sizes without calling
any LLM — useful to validate the pipeline before an API key is configured.
"""

from __future__ import annotations

import argparse
import os
import sys
from decimal import Decimal
from pathlib import Path

# Make src/ importable when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # python-dotenv optional at runtime
    pass

from freight_recon.config import load_config  # noqa: E402
from freight_recon.extraction import extract_from_pages  # noqa: E402
from freight_recon.render import render_pdf  # noqa: E402

DEFAULT_PDF = "data/samples/carrier_invoice_sample.pdf"


def _fmt_money(value) -> str:
    if value is None:
        return "—"
    try:
        return f"${Decimal(str(value)):,.2f}"
    except Exception:
        return str(value)


def _print_extraction(result) -> None:
    obj = result.extraction
    print("\n" + "=" * 64)
    print(f"  EXTRACTION — {result.doc_type}  via {result.provider}/{result.model}")
    print("=" * 64)

    for name, field_value in obj:
        # List fields (accessorials) render differently from Confident[...] scalars.
        if isinstance(field_value, list):
            print(f"\n  {name}:")
            if not field_value:
                print("      (none)")
            for item in field_value:
                conf = getattr(item, "confidence", 0.0)
                print(f"      - {item.name:<16} {_fmt_money(item.amount):>12}   conf={conf:.2f}")
            continue

        value = getattr(field_value, "value", field_value)
        conf = getattr(field_value, "confidence", None)
        money_like = name in {"linehaul_amount", "fuel_surcharge", "total_amount"}
        shown = _fmt_money(value) if money_like else (value if value is not None else "—")
        flag = "  ⚠ LOW" if name in result.low_confidence_fields else ""
        conf_str = f"conf={conf:.2f}" if conf is not None else ""
        print(f"  {name:<18} {str(shown):<28} {conf_str}{flag}")

    if result.low_confidence_fields:
        print(
            f"\n  ⚠ {len(result.low_confidence_fields)} field(s) below confidence threshold "
            f"-> would route to NEEDS_REVIEW: {', '.join(result.low_confidence_fields)}"
        )
    else:
        print("\n  ✓ All fields at/above confidence threshold.")
    print("=" * 64 + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", nargs="?", default=DEFAULT_PDF, help="Path to invoice PDF")
    parser.add_argument("--render-only", action="store_true", help="Rasterize only; no LLM call")
    parser.add_argument("--client", default=None, help="Apply a per-client config overlay")
    parser.add_argument("--dpi", type=int, default=200)
    args = parser.parse_args()

    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"PDF not found: {pdf_path}")
        print("Generate the sample first:  python scripts/generate_sample_invoice.py")
        return 2

    config = load_config("carrier_invoice", client=args.client)
    print(f"Loaded config: doc_type={config.doc_type}  "
          f"fields={len(config.fields)}  confidence_threshold={config.confidence_threshold}")

    pages = render_pdf(pdf_path, dpi=args.dpi)
    sizes = ", ".join(f"p{p.page_number}={len(p.png_bytes)//1024}KB" for p in pages)
    print(f"Rendered {len(pages)} page(s) @ {args.dpi} DPI: {sizes}")

    if args.render_only:
        print("\n--render-only: skipping LLM extraction. Pipeline up to extraction verified.")
        return 0

    provider = (os.getenv("EXTRACTION_PROVIDER") or "anthropic").lower()
    key_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
    if not os.getenv(key_var):
        print(f"\n{key_var} is not set. Set it (or use a .env file) to run extraction.")
        print("To validate the rest of the pipeline now:  "
              "python scripts/run_extraction.py --render-only")
        return 3

    result = extract_from_pages(pages, config)
    if not result.ok:
        print(f"\nEXTRACTION FAILED: {result.error}")
        return 1

    _print_extraction(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
