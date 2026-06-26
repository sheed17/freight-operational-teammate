"""Run inbound mailbox intake through workflow, review, and signed delivery artifacts."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from freight_recon.delivery import DeliveryChannel, DeliverySigner, render_delivery_message  # noqa: E402
from freight_recon.config import load_config  # noqa: E402
from freight_recon.document_identifier import extract_pdf_identifiers  # noqa: E402
from freight_recon.extraction import extract_from_pdf  # noqa: E402
from freight_recon.mailbox_workflow import run_mailbox_workflow  # noqa: E402
from run_mailbox_intake import DEFAULT_INBOX, DEFAULT_PRESERVE, DEFAULT_STATE  # noqa: E402
from run_workflow import DEFAULT_CORPUS, DEFAULT_DB, load_synthetic_loads  # noqa: E402

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - optional developer convenience
    pass

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = DEFAULT_PRESERVE / "mailbox_workflow_report.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS), help="Synthetic/load corpus root")
    parser.add_argument("--inbox", default=str(DEFAULT_INBOX), help="Directory containing inbound .eml files")
    parser.add_argument("--preserve-dir", default=str(DEFAULT_PRESERVE), help="Where raw messages/state are preserved")
    parser.add_argument("--mailbox-state", default=str(DEFAULT_STATE), help="Mailbox state JSON path")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Workflow SQLite path")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Report JSON path")
    parser.add_argument("--actor", default="Rasheed")
    parser.add_argument("--age-hours", type=int, default=0)
    parser.add_argument("--channel", default=DeliveryChannel.LOCAL.value, choices=[c.value for c in DeliveryChannel])
    parser.add_argument("--text", action="store_true", help="Print a short operator summary")
    parser.add_argument("--json", action="store_true", help="Print the full JSON report to stdout")
    parser.add_argument(
        "--real-extraction",
        action="store_true",
        help="Use configured vision extraction on carrier invoice PDFs instead of synthetic invoice truth",
    )
    parser.add_argument("--provider", default=None, choices=["anthropic", "openai"], help="Override extraction provider")
    parser.add_argument("--model", default=None, help="Override extraction model for this run")
    parser.add_argument("--dpi", type=int, default=200, help="PDF render DPI for real extraction")
    parser.add_argument("--max-pages", type=int, default=3, help="Maximum PDF pages for real extraction")
    parser.add_argument(
        "--vision-linking",
        action="store_true",
        help="Use vision identifier extraction to link dirty/generic PDF attachments to loads",
    )
    parser.add_argument("--identifier-model", default=None, help="Override model for vision document linking")
    parser.add_argument(
        "--show-tokens",
        action="store_true",
        help="Include raw signed action tokens in stdout/report for explicit local testing only",
    )
    args = parser.parse_args()

    signer = DeliverySigner.from_env(allow_local_dev=True)
    loads = load_synthetic_loads(Path(args.corpus))
    extractor = _build_real_extractor(
        provider=args.provider,
        model=args.model,
        dpi=args.dpi,
        max_pages=args.max_pages,
    ) if args.real_extraction else None
    result = run_mailbox_workflow(
        inbox_dir=Path(args.inbox),
        preserve_dir=Path(args.preserve_dir),
        mailbox_state_path=Path(args.mailbox_state),
        workflow_db_path=Path(args.db),
        loads=loads,
        signer=signer,
        actor=args.actor,
        channel=DeliveryChannel(args.channel),
        age_hours=args.age_hours,
        redact_tokens=not args.show_tokens,
        extractor=extractor,
        attachment_text_extractor=_build_identifier_text_extractor(
            provider=args.provider,
            model=args.identifier_model or args.model,
            dpi=args.dpi,
            max_pages=args.max_pages,
        ) if args.vision_linking else None,
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result.model_dump(mode="json"), indent=2), encoding="utf-8")
    if args.json or not args.text:
        print(json.dumps(result.model_dump(mode="json"), indent=2))
    if args.text:
        print()
        print("Mailbox Workflow")
        print(f"Scanned: {result.mailbox.scanned}")
        print(f"New messages: {len(result.mailbox.new_messages)}")
        print(f"Duplicates: {len(result.mailbox.duplicates)}")
        print(f"Packet runs: {len(result.mailbox.packet_runs)}")
        print(f"Workflow runs touched: {result.workflow_runs}")
        print(f"Review payloads: {result.reviews_created}")
        print(f"Delivery messages: {result.deliveries_created}")
        for packet in result.packet_results:
            status = packet.workflow_state.value if packet.workflow_state else "SKIPPED"
            flags = ",".join(packet.packet_flags) if packet.packet_flags else "clean"
            print(
                f"- {packet.load_id}: state={status} outcome={packet.outcome or 'n/a'} "
                f"review={packet.review_created} delivery={packet.delivery_created} flags={flags}"
            )
        if result.delivery_messages:
            print()
            print("Delivery Preview")
            for message in result.delivery_messages:
                print(render_delivery_message(message))
                print("-" * 80)
    return 0


def _build_real_extractor(*, provider: str | None, model: str | None, dpi: int, max_pages: int):
    resolved_provider = (provider or os.getenv("EXTRACTION_PROVIDER") or "anthropic").lower()
    key_var = "ANTHROPIC_API_KEY" if resolved_provider == "anthropic" else "OPENAI_API_KEY"
    if not os.getenv(key_var):
        raise SystemExit(f"{key_var} is required when --real-extraction uses provider={resolved_provider}")
    config = load_config("carrier_invoice")

    def extractor(pdf_path: str | Path):
        return extract_from_pdf(
            pdf_path,
            config,
            provider=provider,
            model=model,
            dpi=dpi,
            max_pages=max_pages,
        )

    return extractor


def _build_identifier_text_extractor(*, provider: str | None, model: str | None, dpi: int, max_pages: int):
    resolved_provider = (provider or os.getenv("EXTRACTION_PROVIDER") or "openai").lower()
    if resolved_provider != "openai":
        raise SystemExit("--vision-linking currently requires provider=openai")
    if not os.getenv("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required when --vision-linking is enabled")

    def extractor(payload: bytes, filename: str, content_type: str) -> str:
        if content_type != "application/pdf" and not filename.lower().endswith(".pdf"):
            return ""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as tmp:
            tmp.write(payload)
            tmp.flush()
            result = extract_pdf_identifiers(
                tmp.name,
                provider=resolved_provider,
                model=model,
                dpi=dpi,
                max_pages=max_pages,
            )
        return result.as_link_text() if result.ok else ""

    return extractor


if __name__ == "__main__":
    raise SystemExit(main())
