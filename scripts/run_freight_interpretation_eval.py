"""Evaluate model-backed freight interpretation: labeled freight language, scored field by field.

    # REPLAY (the default): answers come from recorded readings. Costs nothing, calls nothing.
    .venv/bin/python scripts/run_freight_interpretation_eval.py --stage labeled

    # LIVE: paid model calls. Opt-in TWICE - the flag AND the environment variable.
    NEYMA_LIVE_INFERENCE=1 .venv/bin/python scripts/run_freight_interpretation_eval.py \
        --live --stage smoke

Stages, smallest first: smoke (5 messages) | labeled (24 messages + 6 correlation cases) |
corpus (the twenty hostile histories, raw) | scenarios (nine raw-language histories) | all

    # LOAD-WORK REASONING: eight operational states where act-or-wait is not settled by the
    # canonical record, plus nine the projection settles alone (counted as NOT sent). Run by name;
    # it is not part of `all`, keeps its own recording, and is capped at 20 calls unless told more.
    .venv/bin/python scripts/run_freight_interpretation_eval.py --stage load_work

A live run records every reading it pays for, so the next run of the same stage replays it for
free. A recorded reading is a development/eval optimization and never business authority: it goes
through exactly the grounding and normalization a live one does.

One run is capped by --max-calls / --max-input-tokens / --max-output-tokens: a bug cannot loop
through real money. The API key is read from OPENAI_API_KEY by the SDK and is never printed, logged
or written anywhere by this script.

The corpus is SYNTHETIC development input. A score here is not customer evidence.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for entry in (str(ROOT / "src"), str(ROOT / "eval")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_corpus.interpretation_eval import (  # noqa: E402
    LOAD_WORK_STAGE,
    STAGES,
    calls_failed,
    run_stage,
)
from freight_recon.inference.contracts import Usage  # noqa: E402
from freight_recon.inference.gateway import ReplayGateway  # noqa: E402
from freight_recon.inference.ledger import InferenceBudget, InferenceLedger  # noqa: E402
from freight_recon.inference.recording import RecordingStore  # noqa: E402
from freight_recon.inference.settings import (  # noqa: E402
    DEFAULT_MODEL,
    InferenceSettings,
    load_price_table,
)

LIVE_ENV = "NEYMA_LIVE_INFERENCE"
RECORDINGS = ROOT / "eval" / "freight_corpus" / "recordings"


def _load_dotenv() -> None:
    """Pick up a local .env when one is readable, and ONLY when the key is not already in the
    process environment: a run handed its credential by the environment reads no file at all. A
    missing or unreadable file is not an error."""
    if os.environ.get("OPENAI_API_KEY"):
        return
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except (ImportError, OSError):
        pass


def _gateway(args: argparse.Namespace, ledger: InferenceLedger, budget: InferenceBudget):
    recording = RecordingStore(Path(args.recording))
    effort = None if args.reasoning_effort == "default" else args.reasoning_effort
    if not args.live:
        return ReplayGateway(provider="openai", model=args.model, recording=recording,
                             reasoning_effort=effort, ledger=ledger), recording
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is not set in the environment. Nothing was called.")
    # The one place in the repository that constructs a live gateway.
    from freight_recon.inference.openai_responses import OpenAIResponsesGateway

    return OpenAIResponsesGateway(
        model=args.model, allow_live=True, recording=recording, reasoning_effort=effort,
        ledger=ledger, budget=budget, max_attempts=args.max_attempts,
        timeout_s=args.timeout, max_output_tokens=args.max_output_tokens_per_call), recording


def _print_load_work(work: dict) -> None:
    print(f"  cases: {work['cases_correct']}/{work['cases']} correct; failed calls "
          f"{work['failed_calls']}")
    print(f"  WAIT correctly selected: {work['wait_correctly_selected']}/{work['wait_expected']}; "
          f"action correctly selected: {work['act_correctly_selected']}/{work['act_expected']}")
    print(f"  human-required preserved: {work['human_required_preserved']}/{work['human_cases']}; "
          f"stated posture agreed with the work: {work['stated_posture_agreement']}/"
          f"{work['cases'] - work['failed_calls']}")
    print(f"  refused parts: {work['refused_parts']} (unknown need/action/evidence id: "
          f"{work['unknown_id_or_action_refusals']})")
    print(f"  controls settled deterministically: "
          f"{work['controls'] - work['unnecessary_model_calls']}/{work['controls']}; "
          f"unnecessary model calls: {work['unnecessary_model_calls']}; external-effect rows: "
          f"{work['external_effect_rows']}")
    for row in work["results"]:
        if row.get("call") != "OK":
            print(f"    {row['case']}: CALL FAILED {row['call']}")
        elif not row["ok"]:
            print(f"    {row['case']} {row['tags']}: expected {row['expected']} "
                  f"{row['expected_posture']} got {row['observed']} {row['observed_posture']} "
                  f"refused {row['refused']}")
    for row in work["control_results"]:
        print(f"    {row['case']} {row['situation']}: {row['route_reason']} "
              f"sent_to_model={row['sent_to_model']}")


def _print_stage(name: str, stage: dict, show: bool) -> None:
    print(f"\n=== {name}")
    if "load_work" in stage:
        _print_load_work(stage["load_work"])
        if show:
            for row in stage["load_work"]["results"]:
                print(f"    {row['case']}: {row.get('observed')} - {row.get('explanation', '')}")
        return
    messages = stage.get("messages")
    if messages:
        print(f"  messages: {messages['cases_fully_correct']}/{messages['cases']} fully correct; "
              f"fields {messages['fields_correct']}/{messages['fields_checked']}; "
              f"failed calls {messages['failed_calls']}; "
              f"items dropped by grounding {messages['items_dropped_by_grounding']}")
        for row in messages["results"]:
            if row["call"] != "OK":
                print(f"    {row['case']}: CALL FAILED {row['call']} {row.get('debug', '')}")
            for field, verdict in row["fields"].items():
                print(f"    {row['case']} {field}: expected {verdict['expected']} "
                      f"got {verdict['observed']}")
            if show and row["call"] == "OK":
                print(f"    {row['case']} [{row['category']}] asserts="
                      f"{json.dumps(row['asserts'], sort_keys=True)}")
                print(f"      mentions={json.dumps(row['mentions'], sort_keys=True)} "
                      f"dropped={row['dropped']}")
    correlation = stage.get("correlation")
    if correlation:
        print(f"  correlation: {correlation['cases_correct']}/{correlation['cases']} correct; "
              f"ids refused (not supplied / unsupported) {correlation['ids_refused']}; "
              f"failed calls {correlation['failed_calls']}")
        for row in correlation["results"]:
            if not row["ok"]:
                print(f"    {row['case']}: expected {row.get('expected')} got "
                      f"{row.get('observed')} refused {row.get('refused')} {row.get('call')}")
    narrow = stage.get("commitments_only_task")
    if narrow:
        print(f"  commitments-only task: {narrow['cases_correct']}/{narrow['cases']} correct")
        for row in narrow["results"]:
            if not row["ok"]:
                print(f"    {row['case']}: expected {row.get('expected')} got "
                      f"{row.get('observed')} {row.get('call')}")
    if "labeled_outcomes_checked" in stage:
        checked, failed = stage["labeled_outcomes_checked"], stage["labeled_outcomes_failed"]
        print(f"  histories {stage['histories']}, loads {stage['loads']}: labeled outcomes "
              f"{checked - failed}/{checked}; readings {stage['model_readings']} "
              f"(failed {stage['model_reading_failures']}); candidate requests "
              f"{stage['model_candidate_requests']} (ids refused "
              f"{stage['model_candidates_refused']}); cross-tenant violations "
              f"{stage['wrong_cross_tenant_mappings']}; external-effect rows "
              f"{stage['external_effect_rows']}")
        for mismatch in stage["mismatches"]:
            print(f"    !! {mismatch}")
        agreement = stage.get("message_agreement")
        if agreement:
            print(f"  per-message agreement with the structured fixtures: "
                  f"{agreement['messages_agreeing']}/{agreement['messages']}")
            for row in agreement["differences"]:
                print(f"    {row['message']}: expected {row['expected']} got {row['observed']} "
                      f"dropped {row['dropped']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--stage", choices=[*STAGES, LOAD_WORK_STAGE, "all"], default="smoke")
    parser.add_argument("--live", action="store_true",
                        help=f"make paid model calls (also requires {LIVE_ENV}=1)")
    parser.add_argument("--model", help="the model to evaluate (default: NEYMA_INFERENCE_MODEL, "
                                        f"then {DEFAULT_MODEL})")
    parser.add_argument("--reasoning-effort",
                        help="reasoning effort sent to the model, or 'default' to send none "
                             "(default: NEYMA_INFERENCE_REASONING_EFFORT, then low)")
    parser.add_argument("--recording", help="recorded readings file (default: per model/effort)")
    parser.add_argument("--max-calls", type=int,
                        help="call budget for the run (default 150; 20 for load_work)")
    parser.add_argument("--max-input-tokens", type=int, default=400_000)
    parser.add_argument("--max-output-tokens", type=int, default=150_000)
    parser.add_argument("--max-output-tokens-per-call", type=int, default=4000)
    parser.add_argument("--max-attempts", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=45.0)
    parser.add_argument("--ledger", help="append call telemetry (JSONL) to this path")
    parser.add_argument("--report", help="write the JSON report to this path")
    parser.add_argument("--show-readings", action="store_true",
                        help="print each message's converted reading")
    args = parser.parse_args(argv)
    if args.live:
        if os.environ.get(LIVE_ENV) != "1":
            raise SystemExit(
                f"--live makes PAID model calls and needs {LIVE_ENV}=1 in the environment as "
                f"well. Nothing was called.")
        # Only a run that is allowed to spend reads the local .env, and only for the credential.
        _load_dotenv()
    settings = InferenceSettings.from_env()
    model_source = "--model" if args.model else settings.model_source
    args.model = args.model or settings.model
    args.reasoning_effort = (args.reasoning_effort or settings.reasoning_effort or "default")
    load_work = args.stage == LOAD_WORK_STAGE
    if args.max_calls is None:
        args.max_calls = 20 if load_work else 150
    if not args.recording:
        suffix = ".load-work" if load_work else ""
        args.recording = str(
            RECORDINGS / f"{args.model}.effort-{args.reasoning_effort}{suffix}.json")

    ledger = InferenceLedger(sink=Path(args.ledger) if args.ledger else None)
    budget = InferenceBudget(max_calls=args.max_calls, max_input_tokens=args.max_input_tokens,
                             max_output_tokens=args.max_output_tokens)
    gateway, recording = _gateway(args, ledger, budget)
    print(f"provider={gateway.provider} model={gateway.model} (from {model_source}) "
          f"reasoning_effort={args.reasoning_effort} mode={'LIVE' if args.live else 'replay'} "
          f"recorded_readings={len(recording)}")

    stages = list(STAGES) if args.stage == "all" else [args.stage]
    report: dict = {"provider": gateway.provider, "model": gateway.model,
                    "reasoning_effort": args.reasoning_effort,
                    "mode": "live" if args.live else "replay", "stages": {},
                    "note": "Synthetic development corpus. Not customer evidence."}
    for name in stages:
        if budget.exhausted:
            print(f"\n=== {name}: SKIPPED - the run budget is exhausted")
            report["stages"][name] = {"skipped": "run_budget_exhausted"}
            continue
        stage = run_stage(name, gateway, ledger)
        report["stages"][name] = stage
        _print_stage(name, stage, args.show_readings)

    summary = ledger.summary()
    live = Usage(**summary["live_tokens"])
    total = Usage(**summary["tokens"])
    prices = load_price_table()
    report["inference"] = summary
    report["budget"] = budget.as_document()
    report["estimated_api_cost_usd"] = {
        "price_table": prices.version, "this_run_live": prices.estimate_usd(gateway.model, live),
        "all_readings_at_list_price": prices.estimate_usd(gateway.model, total)}
    print("\nINFERENCE")
    print(f"  calls {summary['calls']} by task "
          f"{ {k: v['calls'] for k, v in summary['calls_by_task'].items()} }")
    print(f"  served from {summary['served_from']}; outcomes {summary['outcomes']}; "
          f"retries {summary['retries']}")
    print(f"  tokens this run, LIVE: input {live.input_tokens} (cached "
          f"{live.cached_input_tokens}) output {live.output_tokens} (reasoning "
          f"{live.reasoning_tokens})")
    print(f"  tokens for every reading used, live or replayed: input {total.input_tokens} "
          f"output {total.output_tokens}")
    print(f"  estimated API cost ({prices.version}): this run live "
          f"${report['estimated_api_cost_usd']['this_run_live']}, all readings "
          f"${report['estimated_api_cost_usd']['all_readings_at_list_price']}")
    print(f"  routing: {summary['routing']['settled_deterministically']} settled "
          f"deterministically, {summary['routing']['sent_to_model']} sent to a model")
    print(f"  budget: {budget.as_document()}")
    failures = calls_failed(ledger)
    if failures:
        print(f"  FAILED CALLS: {failures}")
    if args.report:
        Path(args.report).parent.mkdir(parents=True, exist_ok=True)
        Path(args.report).write_text(json.dumps(report, indent=1, sort_keys=True, default=str)
                                     + "\n", encoding="utf-8")
        print(f"  report written to {args.report}")
    return 1 if failures.get("REPLAY_MISS") or budget.exhausted else 0


if __name__ == "__main__":
    raise SystemExit(main())
