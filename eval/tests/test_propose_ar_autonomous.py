"""The autonomous AR runner: graduated loads run unattended (fenced + capped), the rest get a button."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from freight_recon.lane_graduation import LaneGraduation  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402
from propose_ar_from_tms import _run_autonomous, autonomy_split  # noqa: E402


def test_autonomy_split_routes_within_caps_autonomous_over_caps_supervised(tmp_path):
    grad = LaneGraduation(tmp_path / "grad.json")
    grad.graduate("default", "raise_invoice", actor="owner", max_amount="3000.00")
    rows = [
        {"load_ref": "101", "customer": "Echo", "amount": "2500.00"},   # within ceiling -> autonomous
        {"load_ref": "102", "customer": "Acme", "amount": "5000.00"},   # over ceiling  -> supervised
    ]
    auto, supervised = autonomy_split(rows, graduation=grad)
    assert [r["load_ref"] for r in auto] == ["101"]
    assert [r["load_ref"] for r in supervised] == ["102"]


def test_autonomy_split_respects_the_party_allowlist(tmp_path):
    grad = LaneGraduation(tmp_path / "grad.json")
    grad.graduate("default", "raise_invoice", actor="owner", allowed_parties=["echo"])
    rows = [
        {"load_ref": "101", "customer": "Echo", "amount": "2500.00"},   # on the allowlist -> autonomous
        {"load_ref": "102", "customer": "Acme", "amount": "2500.00"},   # off it          -> supervised
    ]
    auto, supervised = autonomy_split(rows, graduation=grad)
    assert [r["load_ref"] for r in auto] == ["101"]
    assert [r["load_ref"] for r in supervised] == ["102"]


def test_autonomy_split_all_supervised_when_lane_not_graduated(tmp_path):
    grad = LaneGraduation(tmp_path / "grad.json")  # nothing graduated
    rows = [{"load_ref": "101", "customer": "Echo", "amount": "2500.00"}]
    auto, supervised = autonomy_split(rows, graduation=grad)
    assert auto == [] and [r["load_ref"] for r in supervised] == ["101"]


def test_autonomy_split_none_graduation_is_all_supervised():
    rows = [{"load_ref": "101", "customer": "Echo", "amount": "2500.00"}]
    auto, supervised = autonomy_split(rows, graduation=None)
    assert auto == [] and len(supervised) == 1


class _FakeResult:
    lane = "raise_invoice"
    status = "DONE"
    note = "Invoice #999 created and saved"
    steps = [
        {"action": "CLICK", "target": "Create Invoice", "committed": True, "ok": True},
        {"action": "READ", "target": "invoice", "observed": "Invoice #999", "ok": True},
    ]


class _FakeRouter:
    def __init__(self):
        self.calls = []

    def run(self, intent, approve=None):
        # autonomous entry point MUST pass approve=None (never a per-run approver)
        assert approve is None
        self.calls.append(intent.params)
        return _FakeResult()


class _FakePoster:
    def __init__(self):
        self.posted = []

    def post_message(self, *, channel, payload):
        self.posted.append(payload["text"])
        return type("R", (), {"ok": True})()


def test_run_autonomous_commits_receipts_with_trace_and_dedups(tmp_path):
    store = WorkflowStore(str(tmp_path / "w.sqlite3"))
    router, poster = _FakeRouter(), _FakePoster()
    rows = [{"load_ref": "101", "customer": "Echo", "amount": "2500.00"}]

    n = _run_autonomous(rows, router=router, store=store, live=True, poster=poster, channel="C")
    assert n == 1
    assert router.calls[0]["approved_amount"] == "2500.00"     # deterministic amount, not model-chosen
    assert router.calls[0]["lane"] == "raise_invoice"
    assert "Done" in poster.posted[0] and "Committed: Create Invoice" in poster.posted[0]  # receipt + trace

    # dedup: the same load isn't auto-invoiced twice in the window before the TMS flips to Invoiced
    n2 = _run_autonomous(rows, router=router, store=store, live=True, poster=poster, channel="C")
    assert n2 == 0 and len(router.calls) == 1
    store.close()


def test_run_autonomous_dry_run_does_not_call_the_router(tmp_path):
    router, poster = _FakeRouter(), _FakePoster()
    rows = [{"load_ref": "101", "customer": "Echo", "amount": "2500.00"}]
    n = _run_autonomous(rows, router=router, store=None, live=False, poster=poster, channel="C")
    assert n == 0 and router.calls == [] and poster.posted == []
