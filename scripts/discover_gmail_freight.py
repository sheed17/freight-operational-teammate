"""Discover likely freight/PDF emails in Gmail and copy candidates into Neyma intake."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

from freight_recon.imap_mailbox import ImapCredentials  # noqa: E402
from freight_recon.inbox_discovery import DEFAULT_GMAIL_QUERY, discover_freight_messages  # noqa: E402
from run_mailbox_intake import DEFAULT_INBOX  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("NEYMA_IMAP_HOST", "imap.gmail.com"))
    parser.add_argument("--port", type=int, default=int(os.getenv("NEYMA_IMAP_PORT", "993")))
    parser.add_argument("--username", default=os.getenv("NEYMA_IMAP_USERNAME") or os.getenv("NEYMA_SMTP_USERNAME"))
    parser.add_argument("--password", default=os.getenv("NEYMA_IMAP_PASSWORD") or os.getenv("NEYMA_SMTP_PASSWORD"))
    parser.add_argument("--mailbox", default=os.getenv("NEYMA_DISCOVERY_MAILBOX", "INBOX"))
    parser.add_argument("--query", default=os.getenv("NEYMA_DISCOVERY_GMAIL_QUERY", DEFAULT_GMAIL_QUERY))
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--min-score", type=float, default=0.45)
    parser.add_argument("--out", default=str(DEFAULT_INBOX))
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--text", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print full discovery metadata")
    args = parser.parse_args()

    if not args.username or not args.password:
        print("Missing IMAP credentials. Set NEYMA_IMAP_USERNAME/PASSWORD or NEYMA_SMTP_USERNAME/PASSWORD.")
        return 2
    result = discover_freight_messages(
        credentials=ImapCredentials(args.host, args.username, args.password, args.port),
        output_dir=Path(args.out),
        mailbox=args.mailbox,
        gmail_query=args.query,
        limit=args.limit,
        min_score=args.min_score,
        dry_run=args.dry_run,
    )
    if args.json:
        print(result.model_dump_json(indent=2))
    if args.text or not args.json:
        print()
        print("Gmail Freight Discovery")
        print(f"Mailbox: {result.mailbox}")
        print(f"Query: {result.gmail_query}")
        print(f"Searched: {result.searched}")
        print(f"Candidates: {result.candidates}")
        print(f"Written: {result.written}")
        print(f"Skipped existing: {result.skipped_existing}")
        for row in result.rows[:10]:
            print(f"- score={row.score:.2f} subject={row.subject!r} attachments={len(row.attachment_names)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
