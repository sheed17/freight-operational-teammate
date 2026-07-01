"""Run the Gmail-label-to-Slack dogfood loop end to end.

This is the local proof of the production shape:

    Gmail label -> preserved mailbox -> packet workflow -> packet pages -> Slack review dispatch

Email is inbound only. Slack is the human review surface. Carrier-facing email remains behind the
follow-up send gate and is not sent by this runner.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from decimal import Decimal

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - optional local convenience
    pass

from freight_recon.channels import build_signer, load_delivery_config  # noqa: E402
from freight_recon.delivery import redact_delivery_message  # noqa: E402
from freight_recon.delivery_dispatch import DispatchMode, dispatch_delivery_message  # noqa: E402
from freight_recon.document_identifier import extract_pdf_identifiers  # noqa: E402
from freight_recon.extraction import extract_from_pdf  # noqa: E402
from freight_recon.config import load_config  # noqa: E402
from freight_recon.imap_mailbox import ImapCredentials, pull_imap_messages  # noqa: E402
from freight_recon.mailbox_workflow import run_mailbox_workflow  # noqa: E402
from freight_recon.packet_page import build_packet_site  # noqa: E402
from freight_recon.review import DogfoodClientProfile  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402
from run_mailbox_workflow import _build_identifier_text_extractor  # noqa: E402
from run_workflow import DEFAULT_CORPUS, load_synthetic_loads  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = ROOT / "data" / "active_workspace" / "gmail_to_slack"
DEFAULT_CLIENT_CONFIG = ROOT / "configs" / "clients" / "neyma_test_freight.yaml"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    parser.add_argument("--mailbox", default=os.getenv("NEYMA_IMAP_MAILBOX", "Neyma-Test-Inbox"))
    parser.add_argument("--query", default=os.getenv("NEYMA_IMAP_QUERY", "UNSEEN"))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--host", default=os.getenv("NEYMA_IMAP_HOST", "imap.gmail.com"))
    parser.add_argument("--port", type=int, default=int(os.getenv("NEYMA_IMAP_PORT", "993")))
    parser.add_argument("--username", default=os.getenv("NEYMA_IMAP_USERNAME") or os.getenv("NEYMA_SMTP_USERNAME"))
    parser.add_argument("--password", default=os.getenv("NEYMA_IMAP_PASSWORD") or os.getenv("NEYMA_SMTP_PASSWORD"))
    parser.add_argument("--corpus", default=str(DEFAULT_CORPUS))
    parser.add_argument("--client-config", default=str(DEFAULT_CLIENT_CONFIG))
    parser.add_argument("--dispatch-mode", choices=[mode.value for mode in DispatchMode], default=DispatchMode.DRY_RUN.value)
    parser.add_argument(
        "--enable-live-slack-outbound",
        action="store_true",
        help="Runtime-only gate to post to live Slack when --dispatch-mode LIVE. Keeps committed config off by default.",
    )
    parser.add_argument(
        "--include-local-email-review",
        action="store_true",
        help="Also render legacy local email review artifacts. Default is Slack-only because Slack is the user UI.",
    )
    parser.add_argument(
        "--propose-clean-payables",
        action="store_true",
        help="For each CLEANLY MATCHED carrier invoice, auto-post a signed 'Record payable [Approve & run]' "
        "button to Slack (the agreed rate-con amount). Requires --dispatch-mode LIVE + "
        "--enable-live-slack-outbound, and the teammate running with --enable-operation-router.",
    )
    parser.add_argument("--age-hours", type=int, default=0)
    parser.add_argument("--actor", default="Rasheed")
    parser.add_argument("--real-extraction", action="store_true")
    parser.add_argument("--vision-linking", action="store_true")
    parser.add_argument("--provider", choices=["anthropic", "openai"], default=None)
    parser.add_argument("--model", default=None)
    parser.add_argument("--identifier-model", default=None)
    parser.add_argument("--dpi", type=int, default=200)
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument(
        "--allow-local-dev-secret",
        action="store_true",
        help="Use fixed local action-token secret when the configured secret is absent.",
    )
    parser.add_argument("--reset-state", action="store_true", help="Delete prior workspace state before running.")
    parser.add_argument(
        "--redispatch-existing",
        action="store_true",
        help="Dispatch review cards even if this workflow run already has a dispatch attempt.",
    )
    parser.add_argument("--text", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if not args.username or not args.password:
        raise SystemExit("Missing IMAP credentials. Set NEYMA_IMAP_USERNAME/PASSWORD or NEYMA_SMTP_USERNAME/PASSWORD.")

    workspace = Path(args.workspace)
    inbox_dir = workspace / "inbound"
    preserve_dir = workspace / "mailbox"
    mailbox_state = preserve_dir / "mailbox_state.json"
    db_path = workspace / "workflow.sqlite3"
    report_path = workspace / "gmail_to_slack_report.json"
    workflow_report_path = workspace / "mailbox_workflow_report.json"
    review_payloads_path = workspace / "review_payloads.json"
    delivery_messages_path = workspace / "delivery_messages.json"
    dispatch_attempts_path = workspace / "slack_dispatch_attempts.json"
    site_dir = workspace / "site"

    if args.reset_state and workspace.exists():
        import shutil

        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)

    pull = pull_imap_messages(
        credentials=ImapCredentials(
            host=args.host,
            port=args.port,
            username=args.username,
            password=args.password,
        ),
        output_dir=inbox_dir,
        mailbox=args.mailbox,
        query=args.query,
        limit=args.limit,
    )

    loads = load_synthetic_loads(Path(args.corpus))
    load_by_id = {load.load_id: load for load in loads}
    workflow = run_mailbox_workflow(
        inbox_dir=inbox_dir,
        preserve_dir=preserve_dir,
        mailbox_state_path=mailbox_state,
        workflow_db_path=db_path,
        loads=loads,
        signer=_delivery_signer(args.client_config, args.allow_local_dev_secret),
        client=_client_profile_from_config(Path(args.client_config)),
        actor=args.actor,
        age_hours=args.age_hours,
        redact_tokens=False,
        extractor=_build_real_extractor(
            provider=args.provider,
            model=args.model,
            dpi=args.dpi,
            max_pages=args.max_pages,
        )
        if args.real_extraction
        else None,
        attachment_text_extractor=_build_identifier_text_extractor(
            provider=args.provider,
            model=args.identifier_model or args.model,
            dpi=args.dpi,
            max_pages=args.max_pages,
        )
        if args.vision_linking
        else None,
    )

    workflow_report_path.write_text(_redacted_workflow_json(workflow), encoding="utf-8")
    review_payloads_path.write_text(
        json.dumps([payload.model_dump(mode="json") for payload in workflow.review_payloads], indent=2),
        encoding="utf-8",
    )
    delivery_messages_path.write_text(
        json.dumps([redact_delivery_message(message).model_dump(mode="json") for message in workflow.delivery_messages], indent=2),
        encoding="utf-8",
    )

    store = WorkflowStore(db_path)
    try:
        pages = build_packet_site(
            output_dir=site_dir,
            corpus_dir=Path(args.corpus),
            store=store,
            loads=load_by_id,
            payloads=workflow.review_payloads,
            mailbox_preserve_dir=preserve_dir,
        )
        dispatch_attempts = _dispatch_reviews(
            store=store,
            client_config_path=Path(args.client_config),
            messages=workflow.delivery_messages,
            mode=DispatchMode(args.dispatch_mode),
            actor=args.actor,
            allow_local_dev_secret=args.allow_local_dev_secret,
            slack_only=not args.include_local_email_review,
            redispatch_existing=args.redispatch_existing,
            enable_live_slack_outbound=args.enable_live_slack_outbound,
        )
        proposals_posted = 0
        if args.propose_clean_payables:
            proposals_posted = _post_clean_payable_proposals(
                store=store,
                workflow=workflow,
                load_by_id=load_by_id,
                client_config=args.client_config,
                signer=_delivery_signer(args.client_config, args.allow_local_dev_secret),
                live=DispatchMode(args.dispatch_mode) == DispatchMode.LIVE and args.enable_live_slack_outbound,
            )
    finally:
        store.close()

    dispatch_attempts_path.write_text(
        json.dumps([attempt.model_dump(mode="json") for attempt in dispatch_attempts], indent=2),
        encoding="utf-8",
    )
    report = {
        "mailbox": args.mailbox,
        "query": args.query,
        "pull": pull.model_dump(mode="json"),
        "workflow": {
            "scanned": workflow.mailbox.scanned,
            "new_messages": len(workflow.mailbox.new_messages),
            "duplicates": len(workflow.mailbox.duplicates),
            "packet_runs": len(workflow.mailbox.packet_runs),
            "unlinked_messages": len(workflow.mailbox.unlinked_messages),
            "workflow_runs_touched": workflow.workflow_runs,
            "review_payloads": workflow.reviews_created,
            "delivery_messages": workflow.deliveries_created,
        },
        "packet_pages": [
            {
                "run_id": page.run_id,
                "load_id": page.load_id,
                "url": f"http://localhost:8000{page.url_path}",
                "path": str(page.path),
            }
            for page in pages
        ],
        "dispatch": {
            "mode": args.dispatch_mode,
            "redispatch_existing": args.redispatch_existing,
            "attempts": len(dispatch_attempts),
            "sent": sum(1 for attempt in dispatch_attempts if attempt.status.value == "SENT"),
            "outboxed": sum(1 for attempt in dispatch_attempts if attempt.status.value == "OUTBOXED"),
            "dry_run": sum(1 for attempt in dispatch_attempts if attempt.status.value == "DRY_RUN"),
            "blocked": sum(1 for attempt in dispatch_attempts if attempt.status.value == "BLOCKED"),
            "failed": sum(1 for attempt in dispatch_attempts if attempt.status.value == "FAILED"),
        },
        "artifacts": {
            "workspace": str(workspace),
            "inbox": str(inbox_dir),
            "mailbox": str(preserve_dir),
            "workflow_db": str(db_path),
            "workflow_report": str(workflow_report_path),
            "review_payloads": str(review_payloads_path),
            "delivery_messages": str(delivery_messages_path),
            "dispatch_attempts": str(dispatch_attempts_path),
            "site": str(site_dir),
            "report": str(report_path),
        },
        "serve_command": f".venv/bin/python -m http.server 8000 --directory {site_dir}",
    }
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    if args.json or not args.text:
        print(json.dumps(report, indent=2))
    if args.text:
        _print_text_summary(report, workflow)
    return 0


def _dispatch_reviews(
    *,
    store: WorkflowStore,
    client_config_path: Path,
    messages,
    mode: DispatchMode,
    actor: str,
    allow_local_dev_secret: bool,
    slack_only: bool,
    redispatch_existing: bool,
    enable_live_slack_outbound: bool,
):
    config = load_delivery_config(client_config_path)
    if config is None:
        raise SystemExit(f"No delivery config found: {client_config_path}")
    if slack_only:
        config = config.model_copy(update={"email": None})
    if mode == DispatchMode.LIVE and enable_live_slack_outbound:
        if config.slack is None:
            raise SystemExit("Live Slack outbound requested, but no Slack config is present.")
        config = config.model_copy(
            update={"slack": config.slack.model_copy(update={"outbound_enabled": True})}
        )
    attempts = []
    for message in messages:
        if not redispatch_existing and _has_dispatch_attempt(store, message.run_id):
            continue
        attempts.extend(
            dispatch_delivery_message(
                store,
                message,
                config,
                env=os.environ,
                mode=mode,
                actor=actor,
            )
        )
    return attempts


def _has_dispatch_attempt(store: WorkflowStore, run_id: int) -> bool:
    return any(event["event_type"] == "delivery_dispatch_attempted" for event in store.audit_events(run_id))


def _redacted_workflow_json(workflow) -> str:
    safe = workflow.model_copy(
        update={
            "delivery_messages": [
                redact_delivery_message(message) for message in workflow.delivery_messages
            ]
        }
    )
    return safe.model_dump_json(indent=2)


def _delivery_signer(client_config_path: str | Path, allow_local_dev_secret: bool):
    config = load_delivery_config(client_config_path)
    if config is None:
        raise SystemExit(f"No delivery config found: {client_config_path}")
    if os.environ.get(config.action_token_secret_env):
        return build_signer(config)
    if allow_local_dev_secret:
        from freight_recon.delivery import DeliverySigner

        return DeliverySigner.from_env(allow_local_dev=True)
    raise SystemExit(
        f"Missing action-token secret: {config.action_token_secret_env}. "
        "For local dogfood only, rerun with --allow-local-dev-secret."
    )


_PAYABLE_PROPOSED_EVENT = "payable_proposal_posted"


def _post_clean_payable_proposals(*, store, workflow, load_by_id, client_config, signer, live: bool) -> int:
    """Auto-post a signed 'Record payable [Approve & run]' button for each cleanly matched invoice.

    Fail-safe + idempotent: only clean MATCHED packets, only the deterministic rate-con amount, only
    when the live gate is on, and ONCE per load — a load already proposed (recorded in the audit log) is
    skipped so a still-matched packet doesn't re-post the same button every cycle.
    """
    from freight_recon.channels import slack_channel_for_route
    from freight_recon.delivery_dispatch import SlackApiPoster
    from freight_recon.operation_proposal import post_operation_proposal, proposals_for_clean_matches
    from freight_recon.reconciliation import agreed_rate_total
    from freight_recon.review import ReviewRoute

    config = load_delivery_config(client_config)
    if config is None or config.slack is None:
        print("propose-clean-payables: no Slack config; skipping.")
        return 0
    channel = slack_channel_for_route(config.slack, ReviewRoute.CHANNEL_POST)
    already = {
        e["payload"].get("load_ref")
        for e in store.security_events()
        if e["event_type"] == _PAYABLE_PROPOSED_EVENT
    }
    fresh = [pr for pr in workflow.packet_results if getattr(pr, "load_id", None) not in already]
    proposals = proposals_for_clean_matches(
        fresh, load_by_id, signer=signer, channel_id=channel,
        amount_for_load=lambda load: str(agreed_rate_total(load)),
    )
    if not proposals:
        print("propose-clean-payables: no new cleanly matched invoices to propose.")
        return 0
    if not live:
        print(f"propose-clean-payables: would post {len(proposals)} payable button(s) (live gate off — dry).")
        return 0
    token = os.environ.get(config.slack.bot_token_env or "")
    if not token:
        print("propose-clean-payables: no Slack bot token; skipping.")
        return 0
    poster = SlackApiPoster(token)
    posted = 0
    for message in proposals:
        try:
            result = post_operation_proposal(message, poster=poster)
            if getattr(result, "ok", False):
                posted += 1
                # Record so we never re-post this load's button on a later cycle.
                store.add_security_event(
                    _PAYABLE_PROPOSED_EVENT, actor="system",
                    payload={"load_ref": message.get("load_ref"), "channel_id": channel},
                )
        except Exception as exc:  # noqa: BLE001 - a posting failure must not break the loop
            print(f"propose-clean-payables: post failed: {type(exc).__name__}")
    print(f"propose-clean-payables: posted {posted}/{len(proposals)} payable approval button(s) to {channel}.")
    return posted


def _client_profile_from_config(path: Path) -> DogfoodClientProfile:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    operator = data.get("operator") or {}
    review = data.get("review") or {}
    thresholds = review.get("thresholds") or {}
    return DogfoodClientProfile(
        company_name=data.get("company_name") or "Neyma Test Freight LLC",
        operator_name=operator.get("name") or "Rasheed",
        operator_role=operator.get("role") or "owner/operator",
        follow_up_tone=(review.get("follow_up_tone") or "short and direct").replace("_", " "),
        packet_base_url=review.get("packet_base_url") or "http://localhost:8000/packets",
        evidence_base_url=review.get("evidence_base_url") or "http://localhost:8000/evidence",
        critical_variance_threshold=Decimal(str(thresholds.get("critical_variance_amount", "100.00"))),
        medium_variance_threshold=Decimal(str(thresholds.get("medium_variance_amount", "25.00"))),
    )


def _build_real_extractor(*, provider: str | None, model: str | None, dpi: int, max_pages: int):
    resolved_provider = (provider or os.getenv("EXTRACTION_PROVIDER") or "openai").lower()
    key_var = "ANTHROPIC_API_KEY" if resolved_provider == "anthropic" else "OPENAI_API_KEY"
    if not os.getenv(key_var):
        raise SystemExit(f"{key_var} is required when --real-extraction uses provider={resolved_provider}")
    config = load_config("carrier_invoice")

    def extractor(pdf_path: str | Path):
        return extract_from_pdf(
            pdf_path,
            config,
            provider=provider,
            model=model,
            dpi=dpi,
            max_pages=max_pages,
        )

    return extractor


def _print_text_summary(report: dict, workflow) -> None:
    print()
    print("Gmail -> Slack Dogfood")
    print(f"Mailbox: {report['mailbox']}")
    print(f"Query: {report['query']}")
    print(f"Pulled: {report['pull']['written']} new .eml files ({report['pull']['skipped_existing']} skipped existing)")
    print(f"Packets: {report['workflow']['packet_runs']}")
    print(f"Review messages: {report['workflow']['review_payloads']}")
    print(f"Dispatch: {report['dispatch']}")
    print()
    print("Packet URLs")
    for page in report["packet_pages"]:
        print(f"- {page['load_id']} run {page['run_id']}: {page['url']}")
    print()
    print("Serve locally:")
    print(f"  {report['serve_command']}")
    if workflow.delivery_messages:
        print()
        print("Slack Review Preview")
        for message in workflow.delivery_messages:
            print(f"- {message.title} -> {message.packet_detail_url}")


if __name__ == "__main__":
    raise SystemExit(main())
