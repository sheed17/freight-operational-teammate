"""Tests for the local internal dogfood pilot runner."""

import json
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from run_dogfood_pilot import run_pilot  # noqa: E402


def test_dogfood_pilot_runner_writes_core_artifacts(tmp_path):
    workspace = tmp_path / "workspace"
    report = run_pilot(workspace=workspace, loads_count=8, seed=42, age_hours=48)

    assert report["company"] == "Neyma Test Freight LLC"
    assert report["role"] == "owner/operator"
    assert report["workflow_runs"] == 8
    assert report["review_payloads"] == 6
    assert report["delivery_messages"] == 6
    assert report["email_ingestion"]["packet_link_accuracy"] == 1.0
    assert report["email_ingestion"]["doc_type_accuracy"] == 1.0
    assert report["email_ingestion"]["noise_rejection_rate"] == 1.0
    assert report["mailbox_workflow"]["scanned"] >= 8
    assert report["mailbox_workflow"]["new_messages"] >= 8
    assert report["mailbox_workflow"]["packet_runs"] == 8
    assert report["mailbox_workflow"]["workflow_runs_touched"] == 8
    assert report["mailbox_workflow"]["review_payloads"] == report["review_payloads"]
    assert report["mailbox_workflow"]["delivery_messages"] == report["delivery_messages"]
    assert report["mailbox_safety"]["missing_required_reviews"] >= 1
    assert report["mailbox_safety"]["extraneous_reviews"] >= 1
    assert report["mailbox_safety"]["duplicate_reviews"] >= 1
    assert report["signed_action_applied"] is True
    assert report["secondary_signed_action_applied"] is True
    assert report["local_callback_action_applied"] is True
    assert report["packet_pages"] == 6
    assert report["mock_tms_records"] == 8
    assert report["tms_readback_verified"] is True
    assert report["mock_tms_write_verified"] is True
    assert report["sample_tms_readback"]["payable"]["billed_amount"] == "3634.50"
    assert report["sample_tms_readback"]["expected_workflow_state"] == "APPROVED"
    assert report["sample_tms_readback"]["load"]["workflow_state"] == "APPROVED"
    assert report["sample_tms_readback"]["payable"]["payable_status"] == "APPROVED_FOR_ENTRY"
    assert report["permission_snapshot"]["read_tms_load_during_review"]["allowed"] is True
    assert report["permission_snapshot"]["submit_tms_payable_during_review"]["allowed"] is False
    assert report["workflow_states"]["DONE"] == 3
    assert report["workflow_states"]["REQUESTED_BACKUP"] == 1
    assert report["sample_tms_write_drill"]["mode"] == "mock_only"
    assert report["sample_tms_write_drill"]["real_tms_write"] is False
    assert report["sample_tms_write_drill"]["confirmation_mode"] == "local_dogfood_auto_confirmed_after_signed_action"
    assert report["sample_tms_write_drill"]["verification_source"] == "mock_tms_ledger_readback"
    assert report["sample_tms_write_drill"]["outcome"]["final_state"] == "DONE"
    assert report["sample_tms_write_drill"]["outcome"]["verified"] is True
    assert report["sample_tms_write_drill"]["ledger_readback"]["amount"] == "3334.50"
    assert report["sample_tms_write_drill"]["post_entry_readback"]["payable"] is None
    assert Path(report["artifacts"]["email_ingestion"]).is_relative_to(workspace)
    assert Path(report["artifacts"]["mailbox_workflow"]).is_relative_to(workspace)
    assert Path(report["artifacts"]["mailbox_state"]).is_relative_to(workspace)
    assert Path(report["artifacts"]["operator_console"]).is_relative_to(workspace)
    assert Path(report["artifacts"]["packet_site"]).is_relative_to(workspace)
    assert (workspace / "synthetic_corpus" / "ground_truth" / "carrier_invoice_extraction.json").exists()
    assert "Approved expected carrier payable $3334.50 by Rasheed" in report["signed_action_mutation"]
    assert "Backup requested by Rasheed" in report["secondary_signed_action_mutation"]
    callback = json.loads(Path(report["artifacts"]["callback_action_response"]).read_text(encoding="utf-8"))
    assert callback["status"] == "APPLIED"
    assert "Backup requested by Rasheed" in callback["message"]
    assert "Month to date:" in report["daily_summary_text"]
    messages = json.loads(Path(report["artifacts"]["delivery_messages"]).read_text(encoding="utf-8"))
    assert messages[0]["actions"][0]["signed_token"].startswith("redacted:")
    mailbox_report = json.loads(Path(report["artifacts"]["mailbox_workflow"]).read_text(encoding="utf-8"))
    assert mailbox_report["delivery_messages"][0]["actions"][0]["signed_token"].startswith("redacted:")
    operator_html = Path(report["artifacts"]["operator_console"]).read_text(encoding="utf-8")
    assert "Dogfood Operator Console" in operator_html
    assert "Mailbox Workflow" in operator_html
    assert "Safety Cases" in operator_html
    assert "Open packet" in operator_html
    assert "signed_token" not in operator_html
    assert "token=" not in operator_html
    assert "eyJ" not in operator_html
    operator_path = Path(report["artifacts"]["operator_console"])
    for href in re.findall(r'href="([^"]+)"', operator_html):
        if href.startswith(("http://", "https://", "mailto:", "#")):
            continue
        target = (operator_path.parent / href).resolve()
        assert target.exists(), f"operator console link does not resolve: {href}"
    for artifact in report["artifacts"].values():
        if artifact is not None:
            assert Path(artifact).exists()
