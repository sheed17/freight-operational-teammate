"""Tests for the internal dogfood pilot session ledger."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.pilot_session import run_pilot_session  # noqa: E402


def _fake_report(workspace, loads_count, seed, age_hours):
    workspace.mkdir(parents=True, exist_ok=True)
    delivery_messages = workspace / "delivery_messages.json"
    daily_summary = workspace / "daily_summary.json"
    callback = workspace / "callback_action_response.json"
    mailbox_workflow = workspace / "mailbox_workflow_report.json"
    report = workspace / "dogfood_pilot_report.json"
    delivery_messages.write_text('[{"actions":[{"signed_token":"redacted:abc"}]}]', encoding="utf-8")
    daily_summary.write_text("{}", encoding="utf-8")
    callback.write_text('{"status":"APPLIED"}', encoding="utf-8")
    mailbox_workflow.write_text(
        '{"delivery_messages":[{"actions":[{"signed_token":"redacted:def"}]}]}',
        encoding="utf-8",
    )
    report.write_text("{}", encoding="utf-8")
    return {
        "loads_generated": loads_count,
        "review_payloads": 6,
        "delivery_messages": 6,
        "email_ingestion": {
            "packet_link_accuracy": 1.0,
            "doc_type_accuracy": 1.0,
            "noise_rejection_rate": 1.0,
        },
        "mailbox_workflow": {
            "scanned": 9,
            "new_messages": 9,
            "packet_runs": 8,
            "review_payloads": 6,
            "delivery_messages": 6,
        },
        "mailbox_safety": {
            "missing_required_reviews": 2,
            "extraneous_reviews": 2,
            "duplicate_reviews": 1,
            "unlinked_reviews": 0,
        },
        "signed_action_applied": True,
        "local_callback_action_applied": True,
        "packet_pages": 6,
        "tms_readback_verified": True,
        "mock_tms_write_verified": True,
        "sample_tms_write_drill": {"mode": "mock_only", "real_tms_write": False},
        "workflow_states": {"DONE": 3, "REQUESTED_BACKUP": 1},
        "daily_summary_text": "Month to date: $300 flagged",
        "artifacts": {
            "pilot_report": str(report),
            "delivery_messages": str(delivery_messages),
            "mailbox_workflow": str(mailbox_workflow),
            "callback_action_response": str(callback),
            "daily_summary": str(daily_summary),
        },
    }


def test_pilot_session_aggregates_ready_days(tmp_path):
    ledger = run_pilot_session(
        session_workspace=tmp_path / "session",
        run_pilot=_fake_report,
        days=2,
        loads_per_day=8,
        seed=42,
        age_hours=48,
    )

    assert ledger.ready_for_design_partner is True
    assert ledger.days_completed == 2
    assert ledger.totals["loads_generated"] == 16
    assert ledger.totals["ready_days"] == 2
    assert not ledger.blockers
    assert (tmp_path / "session" / "pilot_session_ledger.json").exists()
    assert (tmp_path / "session" / "pilot_session_summary.txt").exists()


def test_pilot_session_blocks_on_unredacted_tokens(tmp_path):
    def bad_report(workspace, loads_count, seed, age_hours):
        report = _fake_report(workspace, loads_count, seed, age_hours)
        Path(report["artifacts"]["delivery_messages"]).write_text(
            '[{"actions":[{"signed_token":"raw-token"}]}]',
            encoding="utf-8",
        )
        return report

    ledger = run_pilot_session(
        session_workspace=tmp_path / "session",
        run_pilot=bad_report,
        days=1,
        loads_per_day=8,
        seed=42,
        age_hours=48,
    )

    assert ledger.ready_for_design_partner is False
    assert ledger.blockers == ["day_01:tokens_redacted"]


def test_pilot_session_blocks_on_unredacted_mailbox_workflow_tokens(tmp_path):
    def bad_report(workspace, loads_count, seed, age_hours):
        report = _fake_report(workspace, loads_count, seed, age_hours)
        Path(report["artifacts"]["mailbox_workflow"]).write_text(
            '{"delivery_messages":[{"actions":[{"signed_token":"raw-token"}]}]}',
            encoding="utf-8",
        )
        return report

    ledger = run_pilot_session(
        session_workspace=tmp_path / "session",
        run_pilot=bad_report,
        days=1,
        loads_per_day=8,
        seed=42,
        age_hours=48,
    )

    assert ledger.ready_for_design_partner is False
    assert ledger.blockers == ["day_01:tokens_redacted"]
