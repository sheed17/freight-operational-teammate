"""Run Rasheed/Neyma Test Freight as the first supervised design partner."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - optional local/runtime convenience
    pass

from freight_recon.cli_tenant import resolve_cli_tenant, tenant_from_client_config
from freight_recon.channels import load_delivery_config  # noqa: E402
from freight_recon.delivery import DeliverySigner, build_delivery_message, record_delivery_message  # noqa: E402
from freight_recon.delivery_dispatch import DispatchMode, dispatch_delivery_message  # noqa: E402
from freight_recon.review import ReviewPayload  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402
from run_dogfood_pilot import DEFAULT_WORKSPACE as DOGFOOD_WORKSPACE, run_pilot  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CLIENT_CONFIG = ROOT / "configs" / "clients" / "rasheed_first_design_partner.yaml"
DEFAULT_WORKSPACE = DOGFOOD_WORKSPACE / "first_design_partner"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default=None, help="Canonical tenant; no default.")
    parser.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    parser.add_argument("--client-config", default=str(DEFAULT_CLIENT_CONFIG))
    parser.add_argument("--loads", type=int, default=18)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--age-hours", type=int, default=48)
    parser.add_argument(
        "--dispatch-mode",
        choices=["DRY_RUN", "LOCAL_OUTBOX", "LIVE_SLACK"],
        default="LOCAL_OUTBOX",
        help="LIVE_SLACK posts only to Slack and requires explicit Slack env vars; email remains unsent",
    )
    parser.add_argument("--text", action="store_true")
    args = parser.parse_args()
    tenant = resolve_cli_tenant(tenant=getattr(args, "tenant", None),
                                client_config=getattr(args, "client_config", None),
                                context="run_first_design_partner")

    workspace = Path(args.workspace)
    client_config_path = Path(args.client_config)
    report = run_first_design_partner(
        workspace=workspace,
        client_config_path=client_config_path,
        loads_count=args.loads,
        seed=args.seed,
        age_hours=args.age_hours,
        dispatch_mode=args.dispatch_mode,
    )
    print(json.dumps(report, indent=2))
    if args.text:
        print()
        print(_render_text(report))
    return 0 if report["ready"] else 1


def run_first_design_partner(
    *,
    workspace: Path,
    client_config_path: Path = DEFAULT_CLIENT_CONFIG,
    loads_count: int = 18,
    seed: int = 42,
    age_hours: int = 48,
    dispatch_mode: str = "LOCAL_OUTBOX",
) -> dict:
    # The canonical tenant for this workspace: the client config we were already given.
    tenant = tenant_from_client_config(client_config_path)

    pilot_report = run_pilot(
        tenant=tenant,
        workspace=workspace,
        loads_count=loads_count,
        seed=seed,
        age_hours=age_hours,
        apply_sample_actions=dispatch_mode != "LIVE_SLACK",
    )
    dispatch_report = _dispatch_review_messages(
        workspace=workspace,
        client_config_path=client_config_path,
        mode=dispatch_mode,
    )
    report = {
        "company": "Neyma Test Freight LLC",
        "operator": "Rasheed",
        "role": "first supervised design partner",
        "dispatch_mode": dispatch_mode,
        "email_ingestion_simulated": True,
        "carrier_sends_enabled": False,
        "real_tms_write_enabled": False,
        "slack_live_posting_enabled": dispatch_mode == "LIVE_SLACK",
        "pilot": {
            "email_ingestion": pilot_report["email_ingestion"],
            "local_callback_action_applied": pilot_report["local_callback_action_applied"],
            "tms_readback_verified": pilot_report["tms_readback_verified"],
            "mock_tms_write_verified": pilot_report["mock_tms_write_verified"],
            "sample_actions_applied": pilot_report["sample_actions_applied"],
            "review_payloads": pilot_report["review_payloads"],
            "delivery_messages": pilot_report["delivery_messages"],
            "artifacts": pilot_report["artifacts"],
        },
        "dispatch": dispatch_report,
        "ready": _ready(pilot_report, dispatch_report, dispatch_mode=dispatch_mode),
        "artifacts": {
            "workspace": str(workspace),
            "operator_report": str(workspace / "first_design_partner_report.json"),
            "dispatch_attempts": dispatch_report["artifacts"]["dispatch_attempts"],
            "dogfood_pilot_report": pilot_report["artifacts"]["pilot_report"],
        },
    }
    (workspace / "first_design_partner_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def _dispatch_review_messages(*, workspace: Path, client_config_path: Path, mode: str) -> dict:
    # The canonical tenant for this workspace: the client config we were already given.
    tenant = tenant_from_client_config(client_config_path)

    config = load_delivery_config(client_config_path)
    if config is None:
        raise SystemExit(f"No delivery config found: {client_config_path}")
    env = dict(os.environ)
    signer = _signer(config.action_token_secret_env, env, require_real_secret=mode == "LIVE_SLACK")
    payloads = [
        ReviewPayload.model_validate(item)
        for item in json.loads((workspace / "review_payloads.json").read_text(encoding="utf-8"))
    ]
    if mode == "LIVE_SLACK":
        _require_live_slack_env(config, env)
        attempts = _live_slack_only_attempts(
        tenant=tenant,
            workspace=workspace,
            client_config_path=client_config_path,
            payloads=payloads,
            signer=signer,
            env=env,
        )
    else:
        dispatch_mode = DispatchMode(mode)
        attempts = []
        store = WorkflowStore(workspace / "neyma_workflow.sqlite3", tenant=tenant)
        try:
            for payload in payloads:
                message = build_delivery_message(payload, signer, actor="Rasheed")
                record_delivery_message(store, message)
                attempts.extend(
                    dispatch_delivery_message(
                        store,
                        message,
                        config,
                        env=env,
                        mode=dispatch_mode,
                        email_outbox_dir=workspace / "email_outbox",
                        actor="Rasheed",
                    )
                )
        finally:
            store.close()
    attempts_path = workspace / "first_design_partner_dispatch_attempts.json"
    attempts_path.write_text(json.dumps([attempt.model_dump(mode="json") for attempt in attempts], indent=2), encoding="utf-8")
    return {
        "attempts": len(attempts),
        "statuses": _status_counts(attempts),
        "channels": _channel_counts(attempts),
        "artifacts": {"dispatch_attempts": str(attempts_path)},
    }


def _live_slack_only_attempts(*, workspace: Path, client_config_path: Path, payloads: list[ReviewPayload], signer, env):
    """Explicitly allow Slack live posting while leaving email unsent.

    The client config remains safe by default. This in-memory override is only reached when the
    operator passes ``--dispatch-mode LIVE_SLACK`` and has provided Slack env vars.
    """
    raw = yaml.safe_load(client_config_path.read_text(encoding="utf-8"))
    raw["delivery"]["slack"]["outbound_enabled"] = True
    raw["delivery"]["email"]["enabled"] = False
    temp_path = workspace / "live_slack_runtime_config.yaml"
    temp_path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    config = load_delivery_config(temp_path)
    attempts = []
    store = WorkflowStore(workspace / "neyma_workflow.sqlite3", tenant=tenant)
    try:
        for payload in payloads:
            message = build_delivery_message(payload, signer, actor="Rasheed")
            record_delivery_message(store, message)
            attempts.extend(
                dispatch_delivery_message(
                    store,
                    message,
                    config,
                    env=env,
                    mode=DispatchMode.LIVE,
                    actor="Rasheed",
                )
            )
    finally:
        store.close()
    return attempts


def _signer(secret_env: str, env: dict[str, str], *, require_real_secret: bool = False) -> DeliverySigner:
    secret = env.get(secret_env)
    if secret:
        return DeliverySigner(secret)
    if require_real_secret:
        raise SystemExit(f"Missing action-token secret for LIVE_SLACK: {secret_env}")
    return DeliverySigner.from_env(allow_local_dev=True)


def _require_live_slack_env(config, env: dict[str, str]) -> None:
    if config.slack is None:
        raise SystemExit("LIVE_SLACK requires a Slack channel config")
    required = [
        config.action_token_secret_env,
        config.slack.signing_secret_env,
        config.slack.bot_token_env,
    ]
    missing = [name for name in required if name and not env.get(name)]
    if missing:
        raise SystemExit(f"LIVE_SLACK missing required env vars: {', '.join(missing)}")


def _status_counts(attempts) -> dict[str, int]:
    counts: dict[str, int] = {}
    for attempt in attempts:
        counts[attempt.status.value] = counts.get(attempt.status.value, 0) + 1
    return counts


def _channel_counts(attempts) -> dict[str, int]:
    counts: dict[str, int] = {}
    for attempt in attempts:
        counts[attempt.channel.value] = counts.get(attempt.channel.value, 0) + 1
    return counts


def _ready(pilot_report: dict, dispatch_report: dict, *, dispatch_mode: str) -> bool:
    if dispatch_mode == "LIVE_SLACK":
        return (
            pilot_report["email_ingestion"]["packet_link_accuracy"] == 1.0
            and pilot_report["email_ingestion"]["doc_type_accuracy"] == 1.0
            and pilot_report["review_payloads"] > 0
            and dispatch_report["attempts"] > 0
            and dispatch_report["statuses"].get("SENT", 0) > 0
            and dispatch_report["channels"] == {"slack": dispatch_report["attempts"]}
        )
    common = (
        pilot_report["email_ingestion"]["packet_link_accuracy"] == 1.0
        and pilot_report["email_ingestion"]["doc_type_accuracy"] == 1.0
        and pilot_report["local_callback_action_applied"] is True
        and pilot_report["tms_readback_verified"] is True
        and pilot_report["mock_tms_write_verified"] is True
        and dispatch_report["attempts"] > 0
    )
    return common and "SENT" not in dispatch_report["statuses"]


def _render_text(report: dict) -> str:
    return "\n".join(
        [
            "Neyma First Design Partner Run",
            f"Company: {report['company']}",
            f"Operator: {report['operator']}",
            f"Dispatch mode: {report['dispatch_mode']}",
            f"Ready: {'yes' if report['ready'] else 'no'}",
            f"Review packets: {report['pilot']['review_payloads']}",
            f"Dispatch statuses: {report['dispatch']['statuses']}",
            f"Live Slack posting enabled: {report['slack_live_posting_enabled']}",
            f"Carrier sends enabled: {report['carrier_sends_enabled']}",
            f"Real TMS write enabled: {report['real_tms_write_enabled']}",
        ]
    )


if __name__ == "__main__":
    raise SystemExit(main())
