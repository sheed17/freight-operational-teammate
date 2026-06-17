"""Run inbound email ingestion over the synthetic email corpus and score it against hidden truth.

Measures the Stage 2 "are we extracting the right documents?" question:
- packet-link accuracy: did we link the packet to the correct load?
- doc-type accuracy: did we classify each real attachment correctly?
- noise rejection: did we refuse to attribute noise attachments to the packet?
- missing-doc detection: did we flag exactly the missing required documents?
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from freight_recon.ingestion import ingest_eml_paths  # noqa: E402
from run_workflow import DEFAULT_CORPUS, load_synthetic_loads  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_EMAIL_CORPUS = ROOT / "data" / "synthetic_corpus" / "email_packets"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--email-corpus", default=str(DEFAULT_EMAIL_CORPUS))
    parser.add_argument("--text", action="store_true")
    args = parser.parse_args()

    loads = load_synthetic_loads(Path(args.corpus))
    truth = json.loads((Path(args.email_corpus) / "ground_truth" / "email_packets.json").read_text())

    link_correct = 0
    doc_total = doc_correct = 0
    noise_total = noise_rejected = 0
    missing_correct = 0
    per_packet = []

    for packet in truth:
        eml_paths = [e["eml_path"] for e in packet["emails"]]
        ingested = ingest_eml_paths(eml_paths, loads)

        linked_ok = ingested.packet_load_id == packet["load_id"]
        link_correct += int(linked_ok)

        truth_by_name = {a["filename"]: a for a in (a for e in packet["emails"] for a in e["attachments"])}
        for assessment in ingested.attachments:
            t = truth_by_name.get(assessment.filename)
            if t is None:
                continue
            if t["is_noise"]:
                noise_total += 1
                noise_rejected += int(not assessment.belongs_to_packet)
            else:
                doc_total += 1
                doc_correct += int(assessment.classification.doc_type == t["doc_type"])

        missing_ok = set(ingested.missing_required) == set(packet["missing_doc_types"])
        missing_correct += int(missing_ok)

        per_packet.append(
            {
                "load_id": packet["load_id"],
                "scenario": packet["scenario"],
                "linked_to": ingested.packet_load_id,
                "link_ok": linked_ok,
                "delivered": ingested.delivered_doc_types,
                "missing": ingested.missing_required,
                "extraneous": ingested.extraneous_attachments,
                "needs_human": ingested.needs_human,
                "flags": ingested.flags,
            }
        )

    n = len(truth)
    summary = {
        "packets": n,
        "packet_link_accuracy": _ratio(link_correct, n),
        "doc_type_accuracy": _ratio(doc_correct, doc_total),
        "noise_rejection_rate": _ratio(noise_rejected, noise_total),
        "missing_doc_detection_accuracy": _ratio(missing_correct, n),
        "needs_human_packets": sum(1 for p in per_packet if p["needs_human"]),
    }
    print(json.dumps(summary, indent=2))
    if args.text:
        print()
        for p in per_packet:
            mark = "OK " if p["link_ok"] else "XX "
            print(f"[{mark}] {p['load_id']:<10} {p['scenario']:<28} → {p['linked_to']}  "
                  f"missing={p['missing']} extraneous={p['extraneous']} flags={p['flags']}")
    return 0


def _ratio(num: int, den: int) -> float:
    return round(num / den, 3) if den else 1.0


if __name__ == "__main__":
    raise SystemExit(main())
