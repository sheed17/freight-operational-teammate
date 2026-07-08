"""Tests for the owner-reachable ops brake (pause/resume TMS writes) and command handler."""

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.ops_control import OpsControl, handle_ops_command  # noqa: E402


def test_pause_resume_round_trip_and_audit(tmp_path):
    oc = OpsControl(tmp_path / "ops.json")
    assert oc.is_tms_writes_paused() is False
    oc.pause_tms_writes(actor="Rasheed", reason="looks off")
    assert oc.is_tms_writes_paused() is True
    assert oc.status()["paused_by"] == "Rasheed"
    oc.resume_tms_writes(actor="Rasheed")
    assert oc.is_tms_writes_paused() is False
    log = json.loads((tmp_path / "ops.json").read_text())["log"]
    assert [e["action"] for e in log] == ["pause", "resume"]
    assert log[0]["actor"] == "Rasheed" and log[0]["reason"] == "looks off"


def test_handle_command_pause_resume_status(tmp_path):
    oc = OpsControl(tmp_path / "ops.json")
    assert "PAUSED" in handle_ops_command("pause tms writes", actor="R", ops_control=oc)
    assert oc.is_tms_writes_paused() is True
    assert "PAUSED" in handle_ops_command("status", actor="R", ops_control=oc)
    assert "RESUMED" in handle_ops_command("resume", actor="R", ops_control=oc)
    assert oc.is_tms_writes_paused() is False
    assert "ACTIVE" in handle_ops_command("status", actor="R", ops_control=oc)
    assert "Commands" in handle_ops_command("frobnicate", actor="R", ops_control=oc)


class _Run:
    def __init__(self, load_id, state, reason=None):
        self.load_id = load_id
        self.state = state
        self.reason = reason


class _Store:
    def list_runs(self):
        return [_Run("LD-1", "NEEDS_REVIEW", "variance $300"), _Run("LD-2", "DONE")]


def test_handle_command_roi_reports_what_neyma_did(tmp_path):
    from freight_recon.workflow import WorkflowStore

    oc = OpsControl(tmp_path / "ops.json")
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        store.add_security_event(
            "slack_operation_applied", actor="R",
            payload={"lane": "raise_invoice", "status": "DONE", "approved_amount": "2850.00",
                     "note": "invoice INV-4912 verified", "steps": []},
        )
        out = handle_ops_command("roi", actor="R", ops_control=oc, store=store)
        assert "Raised 1 customer invoice" in out and "$2850.00" in out
        # No store -> falls through to help rather than erroring.
        assert "Commands" in handle_ops_command("roi", actor="R", ops_control=oc)
    finally:
        store.close()


def test_empty_and_bare_commands_do_not_crash(tmp_path):
    # Regression: "/neyma" with no text (empty cmd) must return HELP, never IndexError (broke Slack).
    from freight_recon.workflow import WorkflowStore

    oc = OpsControl(tmp_path / "ops.json")
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        for text in ("", "   ", "graduate", "supervise", "unknown thing"):
            out = handle_ops_command(text, actor="R", ops_control=oc, store=store)
            assert isinstance(out, str) and out  # a reply, no exception
        assert "Commands" in handle_ops_command("", actor="R", ops_control=oc, store=store)
    finally:
        store.close()


def test_handle_command_knowledge_learn_inspect_forget(tmp_path):
    from freight_recon.workflow import WorkflowStore

    oc = OpsControl(tmp_path / "ops.json")
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        assert "haven't learned" in handle_ops_command("know", actor="R", ops_control=oc, store=store)
        out = handle_ops_command("learn Northbound Freight Brokers is order #1002",
                                 actor="R", ops_control=oc, store=store)
        assert "I'll remember" in out
        know = handle_ops_command("know", actor="R", ops_control=oc, store=store)
        assert "Northbound" in know and "order #1002" in know
        assert "Northbound" in handle_ops_command("know about Northbound", actor="R", ops_control=oc, store=store)
        # SOP onboarding: a task-scoped procedure
        sop = handle_ops_command("sop raise_invoice: always include the load reference",
                                 actor="R", ops_control=oc, store=store)
        assert "procedure" in sop and "raise_invoice" in sop
        assert "load reference" in handle_ops_command("know", actor="R", ops_control=oc, store=store)
        gone = handle_ops_command("forget Northbound", actor="R", ops_control=oc, store=store)
        assert "Forgot 1" in gone
        # Northbound is gone, but the SOP procedure remains.
        after = handle_ops_command("know", actor="R", ops_control=oc, store=store)
        assert "Northbound" not in after and "load reference" in after
        handle_ops_command("forget load reference", actor="R", ops_control=oc, store=store)
        assert "haven't learned" in handle_ops_command("know", actor="R", ops_control=oc, store=store)
    finally:
        store.close()


def test_handle_command_graduation_flips_lane_autonomy(tmp_path):
    from freight_recon.workflow import WorkflowStore

    oc = OpsControl(tmp_path / "ops.json")
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        assert "supervised" in handle_ops_command("autonomy", actor="R", ops_control=oc, store=store)
        out = handle_ops_command("graduate raise_invoice", actor="R", ops_control=oc, store=store)
        assert "AUTONOMOUS" in out
        assert "raise_invoice" in handle_ops_command("autonomy", actor="R", ops_control=oc, store=store)
        assert "SUPERVISED" in handle_ops_command("supervise raise_invoice", actor="R", ops_control=oc, store=store)
        # Unknown lane is refused, not created.
        assert "Unknown lane" in handle_ops_command("graduate frobnicate", actor="R", ops_control=oc, store=store)
    finally:
        store.close()


def test_handle_command_unresolved_and_load_status(tmp_path):
    oc = OpsControl(tmp_path / "ops.json")
    store = _Store()
    unresolved = handle_ops_command("show unresolved", actor="R", ops_control=oc, store=store)
    assert "LD-1" in unresolved and "LD-2" not in unresolved  # only open items
    one = handle_ops_command("status LD-2", actor="R", ops_control=oc, store=store)
    assert "LD-2" in one and "DONE" in one


def test_status_command_answers_what_is_neyma_doing(tmp_path):
    import json

    oc = OpsControl(tmp_path / "ops.json")
    status_file = tmp_path / "status.json"
    status_file.write_text(json.dumps({"state": "IDLE", "iteration": 2, "consecutive_failures": 0}))
    out = handle_ops_command("what is neyma doing", actor="R", ops_control=oc, store=_Store(), status_file=str(status_file))
    assert "Gmail polling" in out  # service health line
    assert "TMS writes are *ACTIVE*" in out  # brake state
    assert "waiting on you" in out  # how much needs the owner


def test_status_command_prefers_pilot_readiness_when_workspace_is_known(tmp_path):
    import json
    import sqlite3

    oc = OpsControl(tmp_path / "ops.json")
    (tmp_path / "teammate_status.json").write_text(
        json.dumps({"state": "IDLE", "iteration": 2, "consecutive_failures": 0}),
        encoding="utf-8",
    )
    (tmp_path / "teammate_supervisor.json").write_text(
        json.dumps({"degraded": False, "children": {"callback": {"pid": os.getpid(), "running": True}, "loop": {"pid": os.getpid(), "running": True}}}),
        encoding="utf-8",
    )
    conn = sqlite3.connect(tmp_path / "workflow.sqlite3")
    conn.execute("CREATE TABLE ok (id INTEGER)")
    conn.close()

    out = handle_ops_command("status", actor="R", ops_control=oc, store=_Store(), workspace=tmp_path)
    assert "Pilot readiness" in out
    assert "Workflow DB is readable" in out
    assert "TMS writes are *ACTIVE*" in out


def test_status_command_uses_explicit_db_path_for_readiness(tmp_path):
    import json
    import sqlite3

    oc = OpsControl(tmp_path / "ops.json")
    (tmp_path / "teammate_status.json").write_text(
        json.dumps({"state": "IDLE", "iteration": 2, "consecutive_failures": 0}),
        encoding="utf-8",
    )
    (tmp_path / "teammate_supervisor.json").write_text(
        json.dumps({"degraded": False, "children": {"callback": {"pid": os.getpid(), "running": True}, "loop": {"pid": os.getpid(), "running": True}}}),
        encoding="utf-8",
    )
    real_db = tmp_path / "custom_callback.sqlite3"
    conn = sqlite3.connect(real_db)
    conn.execute("CREATE TABLE ok (id INTEGER)")
    conn.close()

    out = handle_ops_command("status", actor="R", ops_control=oc, workspace=tmp_path, db_path=real_db)
    assert "Workflow DB is readable" in out
    assert "Workflow DB has not been created" not in out
