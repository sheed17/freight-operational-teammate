"""Tests for the local internal dogfood pilot runner."""

import json
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
    assert Path(report["artifacts"]["packet_site"]).is_relative_to(workspace)
    assert (workspace / "synthetic_corpus" / "ground_truth" / "carrier_invoice_extraction.json").exists()
    assert "Approved expected amount $3334.50 by Rasheed" in report["signed_action_mutation"]
    assert "Backup requested by Rasheed" in report["secondary_signed_action_mutation"]
    callback = json.loads(Path(report["artifacts"]["callback_action_response"]).read_text(encoding="utf-8"))
    assert callback["status"] == "APPLIED"
    assert "Backup requested by Rasheed" in callback["message"]
    assert "Month to date:" in report["daily_summary_text"]
    messages = json.loads(Path(report["artifacts"]["delivery_messages"]).read_text(encoding="utf-8"))
    assert messages[0]["actions"][0]["signed_token"].startswith("redacted:")
    for artifact in report["artifacts"].values():
        if artifact is not None:
            assert Path(artifact).exists()
