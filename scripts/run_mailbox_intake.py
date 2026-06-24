"""Poll a controlled inbound mailbox directory and feed Neyma packet ingestion.

This is Phase A of owner-operator readiness: the agent sits where work arrives. The first transport
is a local directory of real ``.eml`` files so dogfood and tests can run without mailbox secrets.
Gmail/IMAP/API watchers should feed the same mailbox-intake contract later.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from freight_recon.mailbox_intake import run_mailbox_intake  # noqa: E402
from run_workflow import DEFAULT_CORPUS, load_synthetic_loads  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INBOX = ROOT / "data" / "active_workspace" / "mailbox" / "inbound"
DEFAULT_PRESERVE = ROOT / "data" / "active_workspace" / "mailbox"
DEFAULT_STATE = DEFAULT_PRESERVE / "mailbox_state.json"
DEFAULT_OUT = DEFAULT_PRESERVE / "mailbox_intake_report.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS), help="Synthetic/load corpus root")
    parser.add_argument("--inbox", default=str(DEFAULT_INBOX), help="Directory containing inbound .eml files")
    parser.add_argument("--preserve-dir", default=str(DEFAULT_PRESERVE), help="Where raw messages/state are preserved")
    parser.add_argument("--state", default=str(DEFAULT_STATE), help="Mailbox state JSON path")
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Report JSON path")
    parser.add_argument("--text", action="store_true", help="Print a short operator summary")
    args = parser.parse_args()

    loads = load_synthetic_loads(Path(args.corpus))
    result = run_mailbox_intake(
        inbox_dir=Path(args.inbox),
        preserve_dir=Path(args.preserve_dir),
        state_path=Path(args.state),
        loads=loads,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result.model_dump(mode="json"), indent=2), encoding="utf-8")
    print(json.dumps(result.model_dump(mode="json"), indent=2))
    if args.text:
        print()
        print("Mailbox Intake")
        print(f"Scanned: {result.scanned}")
        print(f"New messages: {len(result.new_messages)}")
        print(f"Duplicates: {len(result.duplicates)}")
        print(f"Packet runs: {len(result.packet_runs)}")
        for packet in result.packet_runs:
            flags = ",".join(packet.packet.flags) if packet.packet.flags else "clean"
            print(
                f"- {packet.load_id}: messages={packet.source_message_count} "
                f"docs={packet.packet.delivered_doc_types} missing={packet.packet.missing_required} "
                f"needs_human={packet.packet.needs_human} flags={flags}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
