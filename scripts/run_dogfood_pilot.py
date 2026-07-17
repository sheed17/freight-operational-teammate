"""Run the local internal dogfood pilot flow end to end."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.cli_tenant import resolve_cli_tenant
from freight_recon.action_callback import handle_signed_action_callback  # noqa: E402
from freight_recon.config import load_config  # noqa: E402
from freight_recon.delivery import (  # noqa: E402
    DeliverySigner,
    render_delivery_message,
    redact_delivery_message,
    submit_signed_action,
)
from freight_recon.extraction import extract_from_pdf  # noqa: E402
from freight_recon.email_corpus import build_email_corpus  # noqa: E402
from freight_recon.ingestion import ingest_eml_paths  # noqa: E402
from freight_recon.mailbox_workflow import run_mailbox_workflow  # noqa: E402
from freight_recon.mock_tms import build_mock_tms_site  # noqa: E402
from freight_recon.operator_console import build_operator_console  # noqa: E402
from freight_recon.packet_page import build_packet_site  # noqa: E402
from freight_recon.review_actions import ReviewDecision  # noqa: E402
from freight_recon.summary import build_daily_summary, render_daily_summary  # noqa: E402
from freight_recon.tms_adapter import MockTmsReadAdapter, TmsAdapterError  # noqa: E402
from freight_recon.tms_write import ChargeLine, MockTmsWriteLedger, enter_approved_payable  # noqa: E402
from freight_recon.tool_permissions import ToolContext, evaluate_tool_permission  # noqa: E402
from freight_recon.workflow import WorkflowState, WorkflowStore  # noqa: E402
from run_workflow import load_synthetic_loads  # noqa: E402

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover - optional developer convenience
    pass

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKSPACE = ROOT / "data" / "active_workspace"


def run_pilot(
    *,
    tenant: str,
    workspace: Path = DEFAULT_WORKSPACE,
    loads_count: int = 18,
    seed: int = 42,
    age_hours: int = 48,
    extractor=None,
    extraction_mode: str = "synthetic_truth",
    apply_sample_actions: bool = True,
) -> dict:
    workspace.mkdir(parents=True, exist_ok=True)
    corpus = workspace / "synthetic_corpus"
    db_path = workspace / "neyma_workflow.sqlite3"
    site = workspace / "site"
    mock_tms_site = site / "tms"
    review_payloads_path = workspace / "review_payloads.json"
    daily_summary_path = workspace / "daily_summary.json"
    action_result_path = workspace / "dogfood_action_result.json"
    follow_up_path = workspace / "follow_up_draft.json"
    delivery_messages_path = workspace / "delivery_messages.json"
    mailbox_workflow_path = workspace / "mailbox_workflow_report.json"
    mailbox_dir = workspace / "mailbox"
    inbox_dir = mailbox_dir / "inbound"
    mailbox_state_path = mailbox_dir / "mailbox_state.json"
    signed_action_path = workspace / "signed_action_outcome.json"
    callback_action_path = workspace / "callback_action_response.json"
    email_ingestion_path = workspace / "email_ingestion_summary.json"
    tms_write_path = workspace / "tms_write_drill.json"
    tms_write_ledger_path = workspace / "tms_payable_ledger.json"
    report_path = workspace / "dogfood_pilot_report.json"

    _reset_paths(
        files=[
            db_path,
            review_payloads_path,
            daily_summary_path,
            action_result_path,
            follow_up_path,
            delivery_messages_path,
            mailbox_workflow_path,
            mailbox_state_path,
            signed_action_path,
            callback_action_path,
            email_ingestion_path,
            tms_write_path,
            tms_write_ledger_path,
            report_path,
        ],
        directories=[corpus, site, mailbox_dir],
    )

    generate(corpus, loads_count, seed)
    loads = load_synthetic_loads(corpus)
    load_by_id = {load.load_id: load for load in loads}
    email_ingestion = _run_email_ingestion_drill(
        corpus_dir=corpus,
        output_dir=corpus / "email_packets",
        loads=loads,
        seed=seed,
    )
    email_ingestion_path.write_text(json.dumps(email_ingestion, indent=2), encoding="utf-8")
    _copy_email_corpus_to_inbox(Path(email_ingestion["output_dir"]), inbox_dir)
    signer = DeliverySigner.from_env(allow_local_dev=True)
    mailbox_workflow = run_mailbox_workflow(
        tenant=tenant,
        inbox_dir=inbox_dir,
        preserve_dir=mailbox_dir,
        mailbox_state_path=mailbox_state_path,
        workflow_db_path=db_path,
        loads=loads,
        signer=signer,
        actor="Rasheed",
        age_hours=age_hours,
        redact_tokens=False,
        extractor=extractor,
    )
    mailbox_workflow_report = mailbox_workflow.model_copy(
        update={
            "delivery_messages": [
                redact_delivery_message(message) for message in mailbox_workflow.delivery_messages
            ]
        }
    )
    mailbox_workflow_path.write_text(mailbox_workflow_report.model_dump_json(indent=2), encoding="utf-8")

    store = WorkflowStore(db_path, tenant=tenant)
    payloads = mailbox_workflow.review_payloads
    delivery_messages = mailbox_workflow.delivery_messages
    try:
        review_payloads_path.write_text(
            json.dumps([payload.model_dump(mode="json") for payload in payloads], indent=2),
            encoding="utf-8",
        )

        delivery_messages_path.write_text(
            json.dumps(
                [redact_delivery_message(message).model_dump(mode="json") for message in delivery_messages],
                indent=2,
            ),
            encoding="utf-8",
        )
        pages = build_packet_site(
            output_dir=site,
            corpus_dir=corpus,
            store=store,
            loads=load_by_id,
            payloads=payloads,
            mailbox_preserve_dir=mailbox_dir,
        )
        mock_tms = build_mock_tms_site(
            output_dir=mock_tms_site,
            corpus_dir=corpus,
            loads=loads,
            store=store,
        )

        action_result = None
        follow_up_draft = None
        tms_readback = None
        tms_write_drill = None
        signed_action_outcome = None
        first_variance = next((payload for payload in payloads if payload.outcome.value == "VARIANCE"), None)
        if apply_sample_actions and first_variance is not None:
            variance_message = next(message for message in delivery_messages if message.run_id == first_variance.run_id)
            variance_button = next(
                button
                for button in variance_message.actions
                if button.decision == ReviewDecision.APPROVE_EXPECTED_AMOUNT
            )
            signed_action_outcome = submit_signed_action(
                store,
                variance_button.signed_token,
                signer=signer,
                follow_up_loads=load_by_id,
            )
            action_result = signed_action_outcome
            action_result_path.write_text(action_result.model_dump_json(indent=2), encoding="utf-8")
            follow_up_draft = _latest_follow_up_draft(store, first_variance.run_id)
            if follow_up_draft is not None:
                follow_up_path.write_text(json.dumps(follow_up_draft, indent=2), encoding="utf-8")
            mock_tms = build_mock_tms_site(
                output_dir=mock_tms_site,
                corpus_dir=corpus,
                loads=loads,
                store=store,
            )
            tms_adapter = MockTmsReadAdapter(mock_tms_site)
            load_readback = tms_adapter.read_load(first_variance.load_id)
            payable_readback = tms_adapter.read_payable(first_variance.load_id)
            current_run = store.get_run(first_variance.run_id)
            assert current_run is not None
            tms_readback_verified = (
                load_readback.workflow_state == current_run.state.value
                and payable_readback.payable_status == "APPROVED_FOR_ENTRY"
            )
            tms_readback = {
                "verified": tms_readback_verified,
                "expected_workflow_state": current_run.state.value,
                "load": load_readback.model_dump(mode="json"),
                "payable": payable_readback.model_dump(mode="json"),
            }
            if tms_readback_verified:
                approved_amount = variance_button.amount
                if approved_amount is None:
                    raise RuntimeError("approved variance action did not carry an amount")
                ledger = MockTmsWriteLedger(tms_write_ledger_path)
                tms_write_outcome = enter_approved_payable(
                    store,
                    ledger,
                    first_variance.run_id,
                    amount=approved_amount,
                    charges=[ChargeLine(name="Linehaul + authorized charges", amount=approved_amount)],
                    actor="Rasheed",
                    tms_write_enabled=True,
                )
                mock_tms = build_mock_tms_site(
                    output_dir=mock_tms_site,
                    corpus_dir=corpus,
                    loads=loads,
                    store=store,
                )
                post_entry_adapter = MockTmsReadAdapter(mock_tms_site)
                post_entry_payable = None
                post_entry_payable_note = "payable remains visible in active queue"
                try:
                    post_entry_payable = post_entry_adapter.read_payable(first_variance.load_id).model_dump(mode="json")
                except TmsAdapterError as exc:
                    post_entry_payable_note = (
                        "payable no longer appears in active queue after DONE; ledger is the final write readback"
                    )
                tms_write_drill = {
                    "mode": "mock_only",
                    "real_tms_write": False,
                    "confirmation_mode": "local_dogfood_auto_confirmed_after_signed_action",
                    "verification_source": "mock_tms_ledger_readback",
                    "screen_readback_scope": "post-entry load screen only; active payable queue no longer contains DONE items",
                    "ledger": str(tms_write_ledger_path),
                    "outcome": tms_write_outcome.model_dump(mode="json"),
                    "ledger_readback": ledger.get_payable(first_variance.load_id),
                    "post_entry_readback": {
                        "load": post_entry_adapter.read_load(first_variance.load_id).model_dump(mode="json"),
                        "payable": post_entry_payable,
                        "payable_note": post_entry_payable_note,
                    },
                }
                tms_write_path.write_text(json.dumps(tms_write_drill, indent=2), encoding="utf-8")

        # Exercise a second signed delivery round-trip when possible. Prefer a missing-backup card
        # so the pilot proves a non-money follow-up path as well as the variance approval above.
        backup_signed_action_outcome = None
        callback_action_response = None
        round_trip_button = _pick_round_trip_button(
            delivery_messages,
            skip_run_id=first_variance.run_id if first_variance else None,
        )
        if apply_sample_actions and round_trip_button is not None:
            callback_action_response = handle_signed_action_callback(
                store,
                round_trip_button.signed_token,
                signer=signer,
                follow_up_loads=load_by_id,
            )
            backup_signed_action_outcome = callback_action_response.status == "APPLIED"
            signed_action_path.write_text(callback_action_response.model_dump_json(indent=2), encoding="utf-8")
            callback_action_path.write_text(callback_action_response.model_dump_json(indent=2), encoding="utf-8")

        summary = build_daily_summary(store, payloads)
        daily_summary_path.write_text(summary.model_dump_json(indent=2), encoding="utf-8")
        permission_snapshot = _permission_snapshot()

        report = {
            "company": "Neyma Test Freight LLC",
            "operator": "Rasheed",
            "role": "owner/operator",
            "loads_generated": loads_count,
            "extraction_mode": extraction_mode,
            "sample_actions_applied": apply_sample_actions,
            "review_payloads": len(payloads),
            "delivery_messages": len(delivery_messages),
            "email_ingestion": email_ingestion["summary"],
            "mailbox_workflow": {
                "scanned": mailbox_workflow.mailbox.scanned,
                "new_messages": len(mailbox_workflow.mailbox.new_messages),
                "duplicates": len(mailbox_workflow.mailbox.duplicates),
                "packet_runs": len(mailbox_workflow.mailbox.packet_runs),
                "unlinked_messages": len(mailbox_workflow.mailbox.unlinked_messages),
                "workflow_runs_touched": mailbox_workflow.workflow_runs,
                "review_payloads": mailbox_workflow.reviews_created,
                "delivery_messages": mailbox_workflow.deliveries_created,
            },
            "mailbox_safety": _mailbox_safety_summary(mailbox_workflow.packet_results),
            "signed_action_applied": signed_action_outcome is not None,
            "secondary_signed_action_applied": backup_signed_action_outcome is True,
            "local_callback_action_applied": callback_action_response is not None
            and callback_action_response.status == "APPLIED",
            "packet_pages": len(pages),
            "mock_tms_records": len(mock_tms.records),
            "tms_readback_verified": bool(tms_readback and tms_readback.get("verified")),
            "mock_tms_write_verified": bool(
                tms_write_drill
                and tms_write_drill["outcome"]["verified"]
                and tms_write_drill["outcome"]["final_state"] == WorkflowState.DONE.value
                and tms_write_drill["verification_source"] == "mock_tms_ledger_readback"
            ),
            "workflow_runs": len(store.list_runs()),
            "workflow_states": _state_counts(store),
            "artifacts": {
                "workflow_db": str(db_path),
                "email_ingestion": str(email_ingestion_path),
                "mailbox_workflow": str(mailbox_workflow_path),
                "mailbox_state": str(mailbox_state_path),
                "review_payloads": str(review_payloads_path),
                "packet_site": str(site),
                "operator_console": str(site / "operator" / "index.html"),
                "mock_tms": str(mock_tms_site),
                "tms_write_drill": str(tms_write_path) if tms_write_drill else None,
                "daily_summary": str(daily_summary_path),
                "action_result": str(action_result_path) if action_result else None,
                "follow_up_draft": str(follow_up_path) if follow_up_draft else None,
                "delivery_messages": str(delivery_messages_path),
                "signed_action_outcome": str(signed_action_path) if backup_signed_action_outcome else None,
                "callback_action_response": str(callback_action_path) if callback_action_response else None,
            },
            "daily_summary_text": render_daily_summary(summary),
            "sample_delivery_message": (
                render_delivery_message(delivery_messages[0]) if delivery_messages else None
            ),
            "signed_action_mutation": (
                signed_action_outcome.message.status_banner if signed_action_outcome else None
            ),
            "secondary_signed_action_mutation": (
                callback_action_response.mutation_text if callback_action_response else None
            ),
            "sample_tms_readback": tms_readback,
            "sample_tms_write_drill": tms_write_drill,
            "permission_snapshot": permission_snapshot,
            "next_slice": "Customer-system screen mapping and live-channel callback server, still supervised",
        }
        report["artifacts"]["pilot_report"] = str(report_path)
        build_operator_console(
            output_dir=site,
            report=report,
            payloads=payloads,
            delivery_messages=[redact_delivery_message(message) for message in delivery_messages],
            run_states={
                payload.run_id: store.get_run(payload.run_id).state.value
                for payload in payloads
                if store.get_run(payload.run_id) is not None
            },
        )
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        return report
    finally:
        store.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant", default=None, help="Canonical tenant; no default.")
    parser.add_argument("--workspace", default=str(DEFAULT_WORKSPACE))
    parser.add_argument("--loads", type=int, default=18)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--age-hours", type=int, default=48)
    parser.add_argument(
        "--real-extraction",
        action="store_true",
        help="Use configured vision extraction on carrier invoice PDFs instead of synthetic invoice truth",
    )
    parser.add_argument("--provider", default=None, choices=["anthropic", "openai"], help="Override extraction provider")
    parser.add_argument("--model", default=None, help="Override extraction model for this run")
    parser.add_argument("--dpi", type=int, default=200, help="PDF render DPI for real extraction")
    parser.add_argument("--max-pages", type=int, default=3, help="Maximum PDF pages for real extraction")
    parser.add_argument(
        "--skip-sample-actions",
        action="store_true",
        help="Stop after creating review messages; useful before live Slack posting",
    )
    parser.add_argument("--text", action="store_true")
    args = parser.parse_args()

    extractor = _build_real_extractor(
        provider=args.provider,
        model=args.model,
        dpi=args.dpi,
        max_pages=args.max_pages,
    ) if args.real_extraction else None
    report = run_pilot(
        tenant=resolve_cli_tenant(tenant=getattr(args, 'tenant', None), client_config=getattr(args, 'client_config', None), context='run_dogfood_pilot'),
        workspace=Path(args.workspace),
        loads_count=args.loads,
        seed=args.seed,
        age_hours=args.age_hours,
        extractor=extractor,
        extraction_mode="vision_extraction" if args.real_extraction else "synthetic_truth",
        apply_sample_actions=not args.skip_sample_actions,
    )
    print(json.dumps(report, indent=2))
    if args.text:
        print()
        print(report["daily_summary_text"])
    return 0


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


def _pick_round_trip_button(delivery_messages, *, skip_run_id):
    """Pick a signed action button to demonstrate the delivery round-trip.

    Prefer a missing-backup card's REQUEST_BACKUP button (deterministic, non-terminal route);
    otherwise fall back to the first action of the first other reviewable message.
    """
    candidates = [m for m in delivery_messages if m.run_id != skip_run_id]
    for message in candidates:
        for button in message.actions:
            if button.decision == ReviewDecision.REQUEST_BACKUP:
                return button
    for message in candidates:
        if message.actions:
            return message.actions[0]
    return None


def _latest_follow_up_draft(store: WorkflowStore, run_id: int) -> dict | None:
    for event in reversed(store.audit_events(run_id)):
        if event["event_type"] == "follow_up_draft_created":
            return event["payload"]
    return None


def _state_counts(store: WorkflowStore) -> dict[str, int]:
    counts = {state.value: 0 for state in WorkflowState}
    for run in store.list_runs():
        counts[run.state.value] += 1
    return {key: value for key, value in counts.items() if value}


def _permission_snapshot() -> dict[str, dict]:
    checks = {
        "read_tms_load_during_review": ("read_tms_load", ToolContext(workflow_state=WorkflowState.NEEDS_REVIEW)),
        "submit_tms_payable_during_review": (
            "submit_tms_payable",
            ToolContext(
                workflow_state=WorkflowState.NEEDS_REVIEW,
                approval_granted=True,
                tms_write_enabled=True,
            ),
        ),
        "submit_tms_payable_entering_no_write": (
            "submit_tms_payable",
            ToolContext(workflow_state=WorkflowState.ENTERING, approval_granted=True),
        ),
    }
    return {
        name: evaluate_tool_permission(tool, context).model_dump(mode="json")
        for name, (tool, context) in checks.items()
    }


def _reset_paths(*, files: list[Path], directories: list[Path]) -> None:
    for path in files:
        if path.exists():
            path.unlink()
    for path in directories:
        if path.exists():
            shutil.rmtree(path)


def _copy_email_corpus_to_inbox(email_corpus_dir: Path, inbox_dir: Path) -> None:
    inbox_dir.mkdir(parents=True, exist_ok=True)
    for eml_path in sorted(email_corpus_dir.rglob("*.eml")):
        shutil.copy2(eml_path, inbox_dir / eml_path.name)


def _mailbox_safety_summary(packet_results) -> dict:
    return {
        "missing_required_reviews": sum(
            1 for item in packet_results if item.missing_required and item.review_created
        ),
        "extraneous_reviews": sum(
            1 for item in packet_results if item.extraneous_attachments > 0 and item.review_created
        ),
        "duplicate_reviews": sum(
            1 for item in packet_results if item.outcome == "DUPLICATE" and item.review_created
        ),
        "unlinked_reviews": sum(
            1 for item in packet_results if item.load_id == "UNLINKED" and item.review_created
        ),
    }


def _run_email_ingestion_drill(
    *,
    corpus_dir: Path,
    output_dir: Path,
    loads,
    seed: int,
) -> dict:
    email_corpus = build_email_corpus(
        loads,
        corpus_dir=corpus_dir,
        output_dir=output_dir,
        seed=seed,
    )
    link_correct = 0
    doc_total = 0
    doc_correct = 0
    noise_total = 0
    noise_rejected = 0
    missing_correct = 0
    packet_rows = []
    for packet in email_corpus.packets:
        ingested = ingest_eml_paths([email.eml_path for email in packet.emails], loads)
        linked_ok = ingested.packet_load_id == packet.load_id
        link_correct += int(linked_ok)
        truth_by_name = {
            attachment.filename: attachment
            for email in packet.emails
            for attachment in email.attachments
        }
        for assessment in ingested.attachments:
            truth = truth_by_name.get(assessment.filename)
            if truth is None:
                continue
            if truth.is_noise:
                noise_total += 1
                noise_rejected += int(not assessment.belongs_to_packet)
            else:
                doc_total += 1
                doc_correct += int(assessment.classification.doc_type == truth.doc_type)
        missing_ok = set(ingested.missing_required) == set(packet.missing_doc_types)
        missing_correct += int(missing_ok)
        packet_rows.append(
            {
                "load_id": packet.load_id,
                "scenario": packet.scenario,
                "linked_to": ingested.packet_load_id,
                "link_ok": linked_ok,
                "delivered": ingested.delivered_doc_types,
                "missing": ingested.missing_required,
                "extraneous": ingested.extraneous_attachments,
                "needs_human": ingested.needs_human,
                "flags": ingested.flags,
            }
        )
    n = len(email_corpus.packets)
    return {
        "summary": {
            "packets": n,
            "packet_link_accuracy": _ratio(link_correct, n),
            "doc_type_accuracy": _ratio(doc_correct, doc_total),
            "noise_rejection_rate": _ratio(noise_rejected, noise_total),
            "missing_doc_detection_accuracy": _ratio(missing_correct, n),
            "needs_human_packets": sum(1 for row in packet_rows if row["needs_human"]),
        },
        "packets": packet_rows,
        "output_dir": str(output_dir),
    }


def _ratio(num: int, den: int) -> float:
    return round(num / den, 3) if den else 1.0


if __name__ == "__main__":
    raise SystemExit(main())
