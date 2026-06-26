"""Tests for the owner-reachable ops brake (pause/resume TMS writes) and command handler."""

import json
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


def test_handle_command_unresolved_and_load_status(tmp_path):
    oc = OpsControl(tmp_path / "ops.json")
    store = _Store()
    unresolved = handle_ops_command("show unresolved", actor="R", ops_control=oc, store=store)
    assert "LD-1" in unresolved and "LD-2" not in unresolved  # only open items
    one = handle_ops_command("status LD-2", actor="R", ops_control=oc, store=store)
    assert "LD-2" in one and "DONE" in one
