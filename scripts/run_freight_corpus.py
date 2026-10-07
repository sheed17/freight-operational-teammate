"""Run the hostile freight corpus through the P9 freight-domain spine and print what Neyma made of it.

    .venv/bin/python scripts/run_freight_corpus.py            # timelines + metrics
    .venv/bin/python scripts/run_freight_corpus.py --json     # the machine-readable report only
    .venv/bin/python scripts/run_freight_corpus.py --only N01 # one history's timeline

    .venv/bin/python scripts/run_freight_corpus.py --work                       # work, through time
    .venv/bin/python scripts/run_freight_corpus.py --work --load LD-49015       # one load, now
    .venv/bin/python scripts/run_freight_corpus.py --work --load LD-49015 --after get-back-to-you
    .venv/bin/python scripts/run_freight_corpus.py --attack                     # hostile mutations

    .venv/bin/python scripts/run_freight_corpus.py --loop                       # every load, now
    .venv/bin/python scripts/run_freight_corpus.py --loop --load LD-50007       # one load's life
    .venv/bin/python scripts/run_freight_corpus.py --loop --load LD-50007 --detail
    .venv/bin/python scripts/run_freight_corpus.py --loop --load LD-50007 --after dana-confirms
    .venv/bin/python scripts/run_freight_corpus.py --loop --attack              # hostile, on those

Twenty synthetic load histories go into ONE throwaway database shared by three brokerages. For each
history this prints the operational timeline Neyma derived, whether the load is eligible to invoice
and why not, and what is waiting on a human; then the corpus metrics.

`--work` runs the fifteen through-time histories instead and answers, after every record, WHAT WORK
REMAINS on each load: what is waited for, what Neyma could do, what needs a human. `--load` prints
one load's answer the way an operator would be told it — at the end, or just `--after` a record.
`--attack` runs the deterministic hostile mutation layer over those histories and prints what its
oracle found.

`--loop` runs the CONTINUOUS LOAD LOOP: twenty-one complete loads, booked through customer
billing-ready, in flight side by side in one inbox. It prints the board - where every load stands,
whether it is billing-ready, whether it is quiet, how many human touches it has cost - and the loop
metrics. `--load` prints one load through time, one line per moment; `--detail` prints every moment
as the thirteen answers an operator would want; `--after` prints the one moment just after a record.
Every evaluation is audited against the canonical record: a load that is quiet while anything is
owed, waited for or disputed fails the run. Proposed messages are DRAFTS. Nothing is sent.

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
from freight_corpus.loop_histories import LOOP_SETUPS, build_loop_histories  # noqa: E402
from freight_corpus.parties import NORTHLINE, SETUPS  # noqa: E402
from freight_corpus.work_attack import (  # noqa: E402
    Mutant,
    audit_state,
    build_mutants,
    run_mutant,
)
from freight_corpus.work_histories import WORK_SETUPS, build_work_histories  # noqa: E402
from freight_recon.freight_domain.corpus_run import render_corpus, run_corpus  # noqa: E402
from freight_recon.freight_domain.load_loop import (  # noqa: E402
    render_board,
    render_moment,
    render_story,
    render_trace,
    run_load_loop,
)
from freight_recon.freight_domain.load_work import render_load_work  # noqa: E402
from freight_recon.freight_domain.work_run import (  # noqa: E402
    render_work_run,
    run_work_histories,
)
from freight_recon.workflow import WorkflowStore  # noqa: E402


def _work(args: argparse.Namespace) -> int:
    """The through-time histories: what work remains, after every record."""
    histories = build_work_histories()
    with tempfile.TemporaryDirectory(prefix="neyma-load-work-") as scratch:
        store = WorkflowStore(Path(scratch) / "work.db", tenant=histories[0].tenant)
        try:
            result = run_work_histories(store.conn, WORK_SETUPS, histories)
        finally:
            store.close()
    report = json.dumps(result.report, indent=2, sort_keys=True)
    if args.report:
        Path(args.report).write_text(report + "\n", encoding="utf-8")
    metrics = result.report["metrics"]
    if args.json:
        print(report)
    elif args.load:
        shown = [state for step in result.steps for state in step.states.values()
                 if state.load_number == args.load and (not args.after
                                                        or step.label == args.after)]
        if not shown:
            print(f"no load numbered {args.load!r}"
                  + (f" has a record labeled {args.after!r}" if args.after else ""),
                  file=sys.stderr)
            return 1
        # With no --after, the LAST evaluation: the load as it stands at the end of the corpus.
        for state in (shown if args.after else shown[-1:]):
            print(render_load_work(state))
            print()
    else:
        print(render_work_run(result))
        print("WORK METRICS")
        for key, value in metrics.items():
            print(f"  {key:44s} {value}")
        print(f"  needs by kind: {result.report['needs_by_kind']}")
        print(f"  blocked from billing-ready by: {result.report['billing_blockers']}")
    if metrics["labeled_checks_failed"] or metrics["wrong_cross_tenant_mappings"] \
            or metrics["external_effect_rows"]:
        print(f"\nFAILED: {metrics['labeled_checks_failed']} labeled check(s), "
              f"{metrics['wrong_cross_tenant_mappings']} cross-tenant violation(s), "
              f"{metrics['external_effect_rows']} external-effect row(s)", file=sys.stderr)
        return 1
    return 0


def _loop(args: argparse.Namespace) -> int:
    """The continuous load loop: complete loads, side by side, booked to customer billing-ready."""
    histories = build_loop_histories()
    with tempfile.TemporaryDirectory(prefix="neyma-load-loop-") as scratch:
        store = WorkflowStore(Path(scratch) / "loop.db", tenant=histories[0].tenant)
        try:
            result = run_load_loop(
                store.conn, LOOP_SETUPS, histories,
                audit=lambda state, view, tenant: audit_state(state, view, tenant=tenant))
        finally:
            store.close()
    report = json.dumps(result.report, indent=2, sort_keys=True)
    if args.report:
        Path(args.report).write_text(report + "\n", encoding="utf-8")
    metrics = result.report["metrics"]
    if args.json:
        print(report)
    elif args.load:
        stories = result.find(args.load)
        if not stories:
            print(f"no load numbered {args.load!r}", file=sys.stderr)
            return 1
        for story in stories:
            if args.after:
                try:
                    print(f"LOAD {story.load_number}  [{story.tenant_id}]")
                    print(render_moment(story.at(args.after)))
                except KeyError as exc:
                    print(exc.args[0], file=sys.stderr)
                    return 1
            elif args.detail:
                print(render_story(story, detail=True))
            else:
                print(render_trace(story))
            print()
    else:
        print(render_board(result))
        print("\nLOOP METRICS")
        for key, value in metrics.items():
            print(f"  {key:46s} {value}")
    for item in result.histories:
        for mismatch in item.mismatches:
            print(f"  !! {mismatch}", file=sys.stderr)
    for finding in result.findings:
        print(f"  AUDIT !! {finding}", file=sys.stderr)
    if metrics["labeled_checks_failed"] or metrics["audit_findings"] \
            or metrics["wrong_cross_tenant_mappings"] or metrics["external_effect_rows"]:
        print(f"\nFAILED: {metrics['labeled_checks_failed']} labeled check(s), "
              f"{metrics['audit_findings']} audit finding(s), "
              f"{metrics['wrong_cross_tenant_mappings']} cross-tenant violation(s), "
              f"{metrics['external_effect_rows']} external-effect row(s)", file=sys.stderr)
        return 1
    return 0


def _attack(*, loop: bool = False) -> int:
    """The deterministic hostile mutation layer. No model is called. With `loop`, it is run over
    the complete loads of the continuous loop instead of the through-time work histories."""
    histories = build_loop_histories() if loop else build_work_histories()
    setups = LOOP_SETUPS if loop else WORK_SETUPS

    def one(mutant: Mutant):
        with tempfile.TemporaryDirectory(prefix="neyma-work-attack-") as scratch:
            store = WorkflowStore(Path(scratch) / "attack.db", tenant=NORTHLINE)
            try:
                return run_mutant(store.conn, mutant, setups=setups)
            finally:
                store.close()

    own = [h for h in histories if h.tenant == NORTHLINE]
    bases = {h.history_id: one(Mutant(f"{h.history_id}:base", "base", h.history_id, (h,)))
             for h in own}
    mutants = build_mutants(own)
    operators: dict[str, int] = {}
    findings = [f for r in bases.values() for f in r.findings]
    evaluations = differing = 0
    for mutant in mutants:
        result = one(mutant)
        operators[mutant.operator] = operators.get(mutant.operator, 0) + 1
        evaluations += result.evaluations
        findings.extend(result.findings)
        if mutant.same_final_work_as_base and result.final != bases[mutant.base].final:
            differing += 1
            findings.append(f"{mutant.mutant_id}: the final work differs from the unmutated "
                            f"history's")
    print(f"HOSTILE MUTATION LAYER: {len(mutants)} mutants, {evaluations} audited evaluations")
    for operator, count in sorted(operators.items()):
        print(f"  {operator:36s} {count}")
    print(f"  findings: {len(findings)}")
    for finding in findings:
        print(f"    !! {finding}")
    return 1 if findings else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--json", action="store_true", help="print only the JSON report")
    parser.add_argument("--only", metavar="HISTORY_ID",
                        help="print one history's timeline (the whole corpus still runs)")
    parser.add_argument("--report", metavar="PATH", help="also write the JSON report to PATH")
    parser.add_argument("--work", action="store_true",
                        help="run the through-time histories: what work remains on each load")
    parser.add_argument("--load", metavar="LOAD_NUMBER",
                        help="with --work: print one load's work as an operator would be told it")
    parser.add_argument("--after", metavar="RECORD_LABEL",
                        help="with --work --load: the moment just after this record arrived")
    parser.add_argument("--attack", action="store_true",
                        help="run the deterministic hostile mutation layer over the work engine")
    parser.add_argument("--loop", action="store_true",
                        help="run the continuous load loop: complete loads, booked to "
                             "billing-ready, side by side")
    parser.add_argument("--detail", action="store_true",
                        help="with --loop --load: every moment as the thirteen answers")
    args = parser.parse_args(argv)
    if args.attack:
        return _attack(loop=args.loop)
    if args.loop:
        return _loop(args)
    if args.work:
        return _work(args)

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
