"""Pull real IMAP/Gmail messages into Neyma's controlled local .eml inbox."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - optional local/runtime convenience
    pass

from freight_recon.imap_mailbox import ImapCredentials, pull_imap_messages  # noqa: E402
from run_mailbox_intake import DEFAULT_INBOX  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.getenv("NEYMA_IMAP_HOST", "imap.gmail.com"))
    parser.add_argument("--port", type=int, default=int(os.getenv("NEYMA_IMAP_PORT", "993")))
    parser.add_argument("--username", default=os.getenv("NEYMA_IMAP_USERNAME") or os.getenv("NEYMA_SMTP_USERNAME"))
    parser.add_argument("--password", default=os.getenv("NEYMA_IMAP_PASSWORD") or os.getenv("NEYMA_SMTP_PASSWORD"))
    parser.add_argument("--mailbox", default=os.getenv("NEYMA_IMAP_MAILBOX", "INBOX"))
    parser.add_argument("--query", default=os.getenv("NEYMA_IMAP_QUERY", "UNSEEN"))
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--out", default=str(DEFAULT_INBOX))
    parser.add_argument("--dry-run", action="store_true", help="Search only; do not fetch message bytes")
    parser.add_argument("--text", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print full pull metadata")
    args = parser.parse_args()

    if not args.username or not args.password:
        print("Missing IMAP credentials. Set NEYMA_IMAP_USERNAME/PASSWORD or NEYMA_SMTP_USERNAME/PASSWORD.")
        return 2
    result = pull_imap_messages(
        credentials=ImapCredentials(
            host=args.host,
            port=args.port,
            username=args.username,
            password=args.password,
        ),
        output_dir=Path(args.out),
        mailbox=args.mailbox,
        query=args.query,
        limit=args.limit,
        dry_run=args.dry_run,
    )
    if args.json:
        print(result.model_dump_json(indent=2))
    if args.text or not args.json:
        print()
        print("IMAP Mailbox Pull")
        print(f"Host: {result.host}")
        print(f"Mailbox: {result.mailbox}")
        print(f"Query: {result.query}")
        print(f"Matched: {result.matched}")
        print(f"Fetched: {result.fetched}")
        print(f"Written: {result.written}")
        print(f"Skipped existing: {result.skipped_existing}")
        print(f"Output: {result.output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
