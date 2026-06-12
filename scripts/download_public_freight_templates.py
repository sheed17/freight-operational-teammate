"""Download approved public freight template/sample PDFs for layout reference.

These files are used as layout references only. Do not use any incidental real business data
from downloaded files. Synthetic corpus generation should supply its own fake data.

Downloads are written under data/template_sources/downloaded/, which is gitignored.
The registry JSON is written under data/template_sources/template_registry.json for audit.

Usage:
    .venv/bin/python scripts/download_public_freight_templates.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "data" / "template_sources"
DOWNLOADS = OUT_ROOT / "downloaded"
REGISTRY = OUT_ROOT / "template_registry.json"


@dataclass(frozen=True)
class TemplateSource:
    id: str
    doc_type: str
    title: str
    url: str
    usage: str
    notes: str


SOURCES = [
    TemplateSource(
        id="montana_short_form_bol",
        doc_type="bill_of_lading",
        title="Bill of Lading Short Form Template",
        url="https://agr.mt.gov/_docs/marketing-docs/sellingtoretail/Bill_of_Lading_Template.pdf",
        usage="blank/template layout reference",
        notes="Public government-hosted short-form BOL template.",
    ),
    TemplateSource(
        id="smartroutes_basic_pod",
        doc_type="proof_of_delivery",
        title="Basic Proof of Delivery Template",
        url="https://smartroutes.io/docs/basic-proof-of-delivery-template.pdf",
        usage="blank/template layout reference",
        notes="Public proof-of-delivery sample/template.",
    ),
    TemplateSource(
        id="first_choice_blank_bol",
        doc_type="bill_of_lading",
        title="Blank Bill of Lading",
        url="https://firstchoicetransportation.net/wp-content/uploads/2021/10/Blank-BOL.pdf",
        usage="blank/template layout reference",
        notes="Public blank GS1-style BOL form.",
    ),
    TemplateSource(
        id="cocodoc_load_confirmation_template",
        doc_type="rate_confirmation",
        title="Load Confirmation Sheet Template",
        url="https://cdn.cocodoc.com/cocodoc-form-pdf/pdf/328217501--load-confirmation-template-excel-.pdf",
        usage="sample/template layout reference",
        notes="Public rate-confirmation/load-tender style template; use layout only.",
    ),
    TemplateSource(
        id="load1_lumper_instructions",
        doc_type="lumper_receipt_context",
        title="Lumper Receipt Instructions",
        url="https://load1.com/wp-content/uploads/2023/03/Lumper-Receipt-Instructions-.pdf",
        usage="process/context reference",
        notes="Public driver instructions showing lumper receipt workflow expectations.",
    ),
]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download(source: TemplateSource) -> dict:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    filename = f"{source.id}.pdf"
    path = DOWNLOADS / filename
    request = urllib.request.Request(
        source.url,
        headers={"User-Agent": "NeymaSyntheticCorpus/0.1 (+layout-reference)"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        data = response.read()
    if not data.startswith(b"%PDF"):
        raise ValueError(f"{source.id}: downloaded file does not look like a PDF")
    path.write_bytes(data)
    return {
        **asdict(source),
        "local_path": str(path.relative_to(ROOT)),
        "bytes": len(data),
        "sha256": sha256(path),
    }


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    records = []
    failures = []
    for source in SOURCES:
        try:
            record = download(source)
            records.append(record)
            print(f"downloaded {source.id}: {record['bytes']} bytes")
        except Exception as exc:  # noqa: BLE001 - report and continue so one bad URL doesn't block all
            failures.append({"id": source.id, "url": source.url, "error": f"{type(exc).__name__}: {exc}"})
            print(f"failed {source.id}: {failures[-1]['error']}", file=sys.stderr)

    REGISTRY.write_text(
        json.dumps(
            {
                "policy": (
                    "Use public blank/sample/template PDFs for layout reference only. "
                    "Replace all business data with synthetic data."
                ),
                "downloaded": records,
                "failures": failures,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"wrote registry: {REGISTRY}")
    return 1 if failures and not records else 0


if __name__ == "__main__":
    raise SystemExit(main())
