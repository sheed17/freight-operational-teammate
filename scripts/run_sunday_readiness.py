"""Run the Sunday systems-readiness check for the Neyma freight ops loop.

This is intentionally a coordinator, not a second implementation of the product loop. It invokes
the existing entrypoints and then verifies that the pieces needed for a design-partner walkthrough
are present:

    email/Gmail intake -> extraction/reconciliation -> Slack-shaped or live Slack review ->
    packet evidence pages -> signed action loop -> safe TMS execution/readback artifacts

Use ``--source synthetic`` for a fast, fully local rehearsal. Use ``--source gmail`` when the
controlled Gmail label is seeded and live credentials are available.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SYNTHETIC_WORKSPACE = ROOT / "data" / "active_workspace" / "sunday_readiness"
DEFAULT_GMAIL_WORKSPACE = ROOT / "data" / "active_workspace" / "gmail_to_slack"
DEFAULT_CLIENT_CONFIG = ROOT / "configs" / "clients" / "rasheed_first_design_partner.yaml"
DEFAULT_GMAIL_MAILBOX = "Neyma-Test-Inbox"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", choices=["synthetic", "gmail"], default="synthetic")
    parser.add_argument("--workspace", default=None)
    parser.add_argument("--client-config", default=str(DEFAULT_CLIENT_CONFIG))
    parser.add_argument("--mailbox", default=os.getenv("NEYMA_IMAP_MAILBOX", DEFAULT_GMAIL_MAILBOX))
    parser.add_argument("--query", default=os.getenv("NEYMA_IMAP_QUERY", "ALL"))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--dispatch-mode", choices=["DRY_RUN", "LOCAL_OUTBOX", "LIVE"], default="DRY_RUN")
    parser.add_argument("--real-extraction", action="store_true")
    parser.add_argument("--vision-linking", action="store_true")
    parser.add_argument("--provider", choices=["anthropic", "openai"], default=os.getenv("EXTRACTION_PROVIDER"))
    parser.add_argument("--model", default=os.getenv("OPENAI_MODEL") or os.getenv("ANTHROPIC_MODEL"))
    parser.add_argument("--loads", type=int, default=18)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--text", action="store_true")
    args = parser.parse_args()

    workspace = Path(args.workspace) if args.workspace else (
        DEFAULT_GMAIL_WORKSPACE if args.source == "gmail" else DEFAULT_SYNTHETIC_WORKSPACE
    )
    report_path = workspace / "sunday_readiness_report.json"
    workspace.mkdir(parents=True, exist_ok=True)

    checks: list[dict[str, Any]] = []
    commands: list[dict[str, Any]] = []

    if not args.skip_tests:
        checks.append(_run_check("focused_tests", [py(), "-m", "pytest", *focused_tests(), "-q"], commands))

    checks.append(
        _run_check(
            "slack_channel_preflight",
            [py(), "scripts/verify_first_design_partner_slack.py", "--client-config", args.client_config, "--json"],
            commands,
            required=args.dispatch_mode == "LIVE",
        )
    )
    if args.dispatch_mode == "LIVE":
        checks.extend(_live_secret_checks(args.client_config))

    if args.source == "gmail":
        loop_check = _run_gmail_loop(args, workspace, commands)
        loop_report_path = workspace / "gmail_to_slack_report.json"
    else:
        loop_check = _run_synthetic_loop(args, workspace, commands)
        loop_report_path = workspace / "first_design_partner_report.json"
    checks.append(loop_check)

    loop_report = _load_json(loop_report_path)
    artifacts = _artifact_summary(args.source, workspace, loop_report)
    operator_coverage = _operator_coverage(args.source, workspace, loop_report, artifacts)
    checks.extend(_artifact_checks(args.source, loop_report, artifacts))
    checks.extend(_coverage_checks(args.source, operator_coverage))

    report = {
        "ready": all(check["ok"] or not check.get("required", True) for check in checks),
        "source": args.source,
        "dispatch_mode": args.dispatch_mode,
        "workspace": str(workspace),
        "checks": checks,
        "commands_ran": commands,
        "artifacts": artifacts,
        "operator_coverage": operator_coverage,
        "sunday_runbook": _runbook(args.source, workspace, artifacts, args.client_config),
        "demo_story": [
            "1. Agent lives in the controlled inbox and ingests freight document packets.",
            "2. Neyma classifies/links docs to a load and reconciles carrier invoice money deterministically.",
            "3. Slack is the human control surface: exact-money buttons plus evidence links.",
            "4. Packet page is the evidence canvas for invoice, rate con, POD, BOL, and audit trail.",
            "5. Approved work moves to the TMS execution layer only after approval and readback verification.",
        ],
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.text:
        _print_text(report)
    else:
        print(json.dumps(report, indent=2))
    return 0 if report["ready"] else 1


def py() -> str:
    return str(ROOT / ".venv" / "bin" / "python")


def focused_tests() -> list[str]:
    return [
        "eval/tests/test_mailbox_workflow.py",
        "eval/tests/test_delivery_dispatch.py",
        "eval/tests/test_slack_adapter.py",
        "eval/tests/test_action_callback.py",
        "eval/tests/test_tms_write.py",
        "eval/tests/test_browser_use_write.py",
        "eval/tests/test_packet_page.py",
    ]


def _run_synthetic_loop(args, workspace: Path, commands: list[dict[str, Any]]) -> dict[str, Any]:
    dispatch_mode = "LIVE_SLACK" if args.dispatch_mode == "LIVE" else args.dispatch_mode
    cmd = [
        py(),
        "scripts/run_first_design_partner.py",
        "--workspace",
        str(workspace),
        "--client-config",
        args.client_config,
        "--loads",
        str(args.loads),
        "--seed",
        str(args.seed),
        "--dispatch-mode",
        dispatch_mode,
        "--text",
    ]
    return _run_check("synthetic_full_loop", cmd, commands, required=True)


def _run_gmail_loop(args, workspace: Path, commands: list[dict[str, Any]]) -> dict[str, Any]:
    cmd = [
        py(),
        "scripts/run_gmail_to_slack_dogfood.py",
        "--workspace",
        str(workspace),
        "--client-config",
        args.client_config,
        "--mailbox",
        args.mailbox,
        "--query",
        args.query,
        "--limit",
        str(args.limit),
        "--dispatch-mode",
        args.dispatch_mode,
        "--text",
    ]
    if args.dispatch_mode != "LIVE":
        cmd.append("--allow-local-dev-secret")
    if args.real_extraction:
        cmd.append("--real-extraction")
    if args.vision_linking:
        cmd.append("--vision-linking")
    if args.provider:
        cmd.extend(["--provider", args.provider])
    if args.model:
        cmd.extend(["--model", args.model])
    return _run_check("gmail_to_slack_loop", cmd, commands, required=True)


def _live_secret_checks(client_config_path: str) -> list[dict[str, Any]]:
    raw = yaml.safe_load(Path(client_config_path).read_text(encoding="utf-8")) or {}
    delivery = raw.get("delivery") or {}
    slack = delivery.get("slack") or {}
    required = [
        delivery.get("action_token_secret_env"),
        slack.get("signing_secret_env"),
        slack.get("bot_token_env"),
    ]
    checks = []
    for env_name in [name for name in required if name]:
        checks.append(
            _bool_check(
                f"live_secret_present:{env_name}",
                bool(os.environ.get(env_name)),
                required=True,
                detail=f"{env_name} is set" if os.environ.get(env_name) else f"{env_name} is missing",
            )
        )
    return checks


def _run_check(
    name: str,
    cmd: list[str],
    commands: list[dict[str, Any]],
    *,
    required: bool = True,
) -> dict[str, Any]:
    env = os.environ.copy()
    proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True, capture_output=True)
    record = {
        "name": name,
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "stdout_tail": _tail(proc.stdout),
        "stderr_tail": _tail(proc.stderr),
    }
    commands.append(record)
    return {
        "name": name,
        "ok": proc.returncode == 0,
        "required": required,
        "detail": "passed" if proc.returncode == 0 else f"exit {proc.returncode}",
    }


def _artifact_summary(source: str, workspace: Path, loop_report: dict[str, Any]) -> dict[str, Any]:
    if source == "gmail":
        return {
            "operator_report": str(workspace / "gmail_to_slack_report.json"),
            "workflow_db": loop_report.get("artifacts", {}).get("workflow_db", str(workspace / "workflow.sqlite3")),
            "packet_site": loop_report.get("artifacts", {}).get("site", str(workspace / "site")),
            "dispatch_attempts": loop_report.get("artifacts", {}).get(
                "dispatch_attempts", str(workspace / "slack_dispatch_attempts.json")
            ),
            "review_payloads": loop_report.get("artifacts", {}).get("review_payloads", str(workspace / "review_payloads.json")),
            "serve_packet_site": loop_report.get(
                "serve_command", f"{py()} -m http.server 8000 --directory {workspace / 'site'}"
            ),
        }
    pilot_artifacts = loop_report.get("pilot", {}).get("artifacts", {})
    return {
        "operator_report": str(workspace / "first_design_partner_report.json"),
        "workflow_db": pilot_artifacts.get("workflow_db", str(workspace / "neyma_workflow.sqlite3")),
        "packet_site": pilot_artifacts.get("packet_site", str(workspace / "site")),
        "operator_console": pilot_artifacts.get("operator_console", str(workspace / "site" / "operator" / "index.html")),
        "mock_tms": pilot_artifacts.get("mock_tms", str(workspace / "site" / "tms")),
        "tms_write_drill": pilot_artifacts.get("tms_write_drill"),
        "dispatch_attempts": loop_report.get("artifacts", {}).get(
            "dispatch_attempts", str(workspace / "first_design_partner_dispatch_attempts.json")
        ),
        "serve_packet_site": f"{py()} -m http.server 8000 --directory {workspace / 'site'}",
    }


def _artifact_checks(source: str, loop_report: dict[str, Any], artifacts: dict[str, Any]) -> list[dict[str, Any]]:
    checks = []
    if source == "gmail":
        dispatch = loop_report.get("dispatch", {})
        workflow = loop_report.get("workflow", {})
        checks.extend(
            [
                _bool_check("gmail_packets_created", workflow.get("packet_runs", 0) > 0),
                _bool_check("gmail_review_messages_created", workflow.get("review_payloads", 0) > 0),
                _bool_check("packet_pages_created", len(loop_report.get("packet_pages", [])) > 0),
                _bool_check("dispatch_attempted", dispatch.get("attempts", 0) > 0),
            ]
        )
    else:
        pilot = loop_report.get("pilot", {})
        email_ingestion = pilot.get("email_ingestion", {})
        checks.extend(
            [
                _bool_check("email_ingestion_ready", email_ingestion.get("packet_link_accuracy") == 1.0),
                _bool_check("doc_type_accuracy_ready", email_ingestion.get("doc_type_accuracy") == 1.0),
                _bool_check("noise_rejection_ready", email_ingestion.get("noise_rejection_rate") == 1.0),
                _bool_check(
                    "missing_doc_detection_ready",
                    email_ingestion.get("missing_doc_detection_accuracy") == 1.0,
                ),
                _bool_check("human_review_cases_present", email_ingestion.get("needs_human_packets", 0) > 0),
                _bool_check("review_messages_created", pilot.get("review_payloads", 0) > 0),
                _bool_check("signed_action_loop_applied", pilot.get("local_callback_action_applied") is True),
                _bool_check("mock_tms_readback_verified", pilot.get("tms_readback_verified") is True),
                _bool_check("mock_tms_write_verified", pilot.get("mock_tms_write_verified") is True),
            ]
        )
    checks.append(_bool_check("packet_site_exists", Path(artifacts["packet_site"]).exists()))
    checks.append(_bool_check("workflow_db_exists", Path(artifacts["workflow_db"]).exists()))
    return checks


def _coverage_checks(source: str, coverage: dict[str, Any]) -> list[dict[str, Any]]:
    if source != "synthetic":
        return []
    return [
        _bool_check("coverage_variance_case", coverage["counts"].get("variance", 0) > 0),
        _bool_check("coverage_unauthorized_accessorial", coverage["counts"].get("unauthorized_accessorial", 0) > 0),
        _bool_check("coverage_wrong_load_attachment", coverage["counts"].get("wrong_load_or_extraneous", 0) > 0),
        _bool_check("coverage_missing_pod_or_backup", coverage["counts"].get("missing_pod_or_backup", 0) > 0),
        _bool_check("coverage_duplicate_invoice", coverage["counts"].get("duplicate_invoice", 0) > 0),
        _bool_check("coverage_follow_up_draft", coverage["follow_up_draft_created"] is True),
        _bool_check("coverage_mock_tms_write_readback", coverage["mock_tms_write_verified"] is True),
    ]


def _operator_coverage(
    source: str,
    workspace: Path,
    loop_report: dict[str, Any],
    artifacts: dict[str, Any],
) -> dict[str, Any]:
    payloads = _load_json_list(Path(artifacts.get("review_payloads") or workspace / "review_payloads.json"))
    counts = {
        "variance": 0,
        "unauthorized_accessorial": 0,
        "wrong_load_or_extraneous": 0,
        "missing_pod_or_backup": 0,
        "duplicate_invoice": 0,
    }
    examples: dict[str, dict[str, Any]] = {}
    for payload in payloads:
        load_id = payload.get("load_id")
        outcome = str(payload.get("outcome") or "")
        summary = str(payload.get("summary") or "")
        fields_text = json.dumps(payload.get("fields") or [], sort_keys=True).lower()
        evidence_text = json.dumps(payload.get("evidence_links") or [], sort_keys=True).lower()
        actions_text = json.dumps(payload.get("actions") or [], sort_keys=True).lower()
        card = {
            "load_id": load_id,
            "run_id": payload.get("run_id"),
            "title": payload.get("title"),
            "packet_detail_url": payload.get("packet_detail_url"),
        }
        if outcome == "VARIANCE":
            counts["variance"] += 1
            examples.setdefault("variance", card)
        if "unauthorized" in fields_text or "unauthorized" in summary.lower():
            counts["unauthorized_accessorial"] += 1
            examples.setdefault("unauthorized_accessorial", card)
        if "does_not_belong_to_packet" in evidence_text or "extraneous" in evidence_text:
            counts["wrong_load_or_extraneous"] += 1
            examples.setdefault("wrong_load_or_extraneous", card)
        if "missing" in summary.lower() or "request_backup" in actions_text:
            counts["missing_pod_or_backup"] += 1
            examples.setdefault("missing_pod_or_backup", card)
        if outcome == "DUPLICATE":
            counts["duplicate_invoice"] += 1
            examples.setdefault("duplicate_invoice", card)

    pilot = loop_report.get("pilot", {}) if source == "synthetic" else {}
    tms_write_drill = artifacts.get("tms_write_drill")
    return {
        "role_helped": "owner/operator, controller, AP clerk, back-office generalist",
        "counts": counts,
        "examples": examples,
        "email_ingestion": pilot.get("email_ingestion", loop_report.get("workflow", {})),
        "review_messages": pilot.get("review_payloads", loop_report.get("workflow", {}).get("review_payloads")),
        "dispatch": loop_report.get("dispatch", {}),
        "follow_up_draft_created": bool(pilot.get("artifacts", {}).get("follow_up_draft")),
        "mock_tms_readback_verified": bool(pilot.get("tms_readback_verified")),
        "mock_tms_write_verified": bool(pilot.get("mock_tms_write_verified")),
        "real_tms_write_enabled": False,
        "tms_write_drill": tms_write_drill,
    }


def _bool_check(name: str, ok: bool, *, required: bool = True, detail: str | None = None) -> dict[str, Any]:
    return {"name": name, "ok": bool(ok), "required": required, "detail": detail or ("passed" if ok else "missing")}


def _runbook(source: str, workspace: Path, artifacts: dict[str, Any], client_config: str) -> dict[str, str]:
    db = artifacts["workflow_db"]
    packet_site = artifacts["packet_site"]
    mock_tms = artifacts.get("mock_tms") or f"{packet_site}/tms"
    return {
        "serve_packet_evidence": f"{py()} -m http.server 8000 --directory {packet_site}",
        "start_action_callback": (
            f"{py()} scripts/run_action_callback_server.py --workspace {workspace} --db {db} "
            f"--client-config {client_config} --port 8001"
        ),
        "start_writable_mock_tms": (
            f"{py()} -m freight_recon.mock_tms_write_server --site {mock_tms} "
            f"--ledger {workspace / 'browser_tms_payable_ledger.json'} --port 8012"
        ),
        "live_slack_note": "For live Slack button clicks, tunnel port 8001 and set Slack Interactivity URL to <tunnel>/slack/actions.",
        "source_note": (
            "Gmail source uses the controlled label only; never run against the full inbox for a demo."
            if source == "gmail"
            else "Synthetic source proves the full loop without touching real inbox state."
        ),
    }


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _load_json_list(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _tail(text: str, limit: int = 4000) -> str:
    return text[-limit:] if len(text) > limit else text


def _print_text(report: dict[str, Any]) -> None:
    print("Sunday Readiness")
    print(f"Ready: {'yes' if report['ready'] else 'no'}")
    print(f"Source: {report['source']}")
    print(f"Dispatch mode: {report['dispatch_mode']}")
    print(f"Workspace: {report['workspace']}")
    print()
    print("Checks")
    for check in report["checks"]:
        status = "PASS" if check["ok"] else ("WARN" if not check.get("required", True) else "FAIL")
        print(f"- {status} {check['name']}: {check['detail']}")
    print()
    print("Operator Coverage")
    coverage = report.get("operator_coverage", {})
    counts = coverage.get("counts", {})
    print(f"- Review messages: {coverage.get('review_messages')}")
    print(f"- Variance cases: {counts.get('variance', 0)}")
    print(f"- Unauthorized accessorials: {counts.get('unauthorized_accessorial', 0)}")
    print(f"- Wrong-load/extraneous docs: {counts.get('wrong_load_or_extraneous', 0)}")
    print(f"- Missing POD/backup cases: {counts.get('missing_pod_or_backup', 0)}")
    print(f"- Duplicate invoices: {counts.get('duplicate_invoice', 0)}")
    print(f"- Follow-up draft created: {coverage.get('follow_up_draft_created')}")
    print(f"- Mock TMS write/readback verified: {coverage.get('mock_tms_write_verified')}")
    print(f"- Real TMS write enabled: {coverage.get('real_tms_write_enabled')}")
    examples = coverage.get("examples", {})
    if examples:
        print("Examples")
        for name, item in examples.items():
            print(f"- {name}: {item.get('load_id')} run {item.get('run_id')} -> {item.get('packet_detail_url')}")
    print()
    print("Demo Commands")
    for name, cmd in report["sunday_runbook"].items():
        print(f"- {name}: {cmd}")
    print()
    print(f"Report: {Path(report['workspace']) / 'sunday_readiness_report.json'}")


if __name__ == "__main__":
    raise SystemExit(main())
