"""Generate the synthetic inbound-email corpus (Stage 2 ingestion proving ground)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from freight_recon.email_corpus import build_email_corpus  # noqa: E402
from run_workflow import DEFAULT_CORPUS, load_synthetic_loads  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "data" / "synthetic_corpus" / "email_packets"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    loads = load_synthetic_loads(Path(args.corpus))
    corpus = build_email_corpus(
        loads,
        corpus_dir=Path(args.corpus),
        output_dir=Path(args.output),
        seed=args.seed,
    )
    by_scenario: dict[str, int] = {}
    for packet in corpus.packets:
        by_scenario[packet.scenario] = by_scenario.get(packet.scenario, 0) + 1
    summary = {
        "output_dir": corpus.output_dir,
        "packets": len(corpus.packets),
        "emails": sum(len(p.emails) for p in corpus.packets),
        "scenarios": by_scenario,
        "with_noise": sum(1 for p in corpus.packets if p.has_noise),
        "with_missing_docs": sum(1 for p in corpus.packets if p.missing_doc_types),
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
