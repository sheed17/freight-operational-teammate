"""Run the hostile freight corpus through the P9 freight-domain spine and print what Neyma made of it.

    .venv/bin/python scripts/run_freight_corpus.py            # timelines + metrics
    .venv/bin/python scripts/run_freight_corpus.py --json     # the machine-readable report only
    .venv/bin/python scripts/run_freight_corpus.py --only N01 # one history's timeline

Twenty synthetic load histories go into ONE throwaway database shared by three brokerages. For each
history this prints the operational timeline Neyma derived, whether the load is eligible to invoice
and why not, and what is waiting on a human; then the corpus metrics.

It reads fixtures and writes canonical rows to a temporary database. It sends nothing, calls no
outside system and uses no model. The corpus is synthetic development input — not customer evidence.
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT / "src"), str(ROOT / "eval")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_corpus.histories import build_corpus  # noqa: E402
from freight_corpus.parties import SETUPS  # noqa: E402
from freight_recon.freight_domain.corpus_run import render_corpus, run_corpus  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--json", action="store_true", help="print only the JSON report")
    parser.add_argument("--only", metavar="HISTORY_ID",
                        help="print one history's timeline (the whole corpus still runs)")
    parser.add_argument("--report", metavar="PATH", help="also write the JSON report to PATH")
    args = parser.parse_args(argv)

    histories = build_corpus()
    with tempfile.TemporaryDirectory(prefix="neyma-freight-corpus-") as scratch:
        store = WorkflowStore(Path(scratch) / "corpus.db", tenant=histories[0].tenant)
        try:
            result = run_corpus(store.conn, SETUPS, histories)
        finally:
            store.close()

    report = json.dumps(result.report, indent=2, sort_keys=True)
    if args.report:
        Path(args.report).write_text(report + "\n", encoding="utf-8")
    if args.json:
        print(report)
    else:
        text = render_corpus(result)
        if args.only:
            blocks = text.split("=== ")
            text = "".join("=== " + b for b in blocks if b.startswith(f"{args.only} "))
        print(text)
        print("CORPUS METRICS")
        for key, value in result.report["metrics"].items():
            print(f"  {key:48s} {value}")
    failed = result.report["metrics"]["labeled_expectations_failed"]
    violations = result.report["metrics"]["wrong_cross_tenant_mappings"]
    effects = result.report["metrics"]["external_effect_rows"]
    if failed or violations or effects:
        print(f"\nFAILED: {failed} labeled expectation(s), {violations} cross-tenant "
              f"violation(s), {effects} external-effect row(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
