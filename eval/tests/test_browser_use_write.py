"""Tests for browser-use TMS write execution (with an injected fake runner — no live browser/LLM).

These prove the gated write path drives a browser-shaped ledger exactly like the JSON ledger:
confirm-before-submit, verify-by-readback, and fail-closed routing all hold when the "TMS" is a
browser the agent operates. The fake runner stands in for browser-use, returning the JSON the agent
would read off the writable mock TMS confirmation/readback pages.
"""

import json
import re
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.browser_use_adapter import BrowserUseWriteLedger, TmsAdapterError  # noqa: E402
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.review import build_review_payload, record_review_payload  # noqa: E402
from freight_recon.review_actions import ReviewActionRequest, ReviewDecision, apply_review_action  # noqa: E402
from freight_recon.tms_write import ChargeLine, PayableWriteStatus, enter_approved_payable  # noqa: E402
from freight_recon.workflow import WorkflowState, WorkflowStore, process_load_packet  # noqa: E402

_AMOUNT = "3634.50"


class FakeRunner:
    """Stands in for browser-use: simulates operating the writable mock TMS screens.

    On a write task it records the amount it was told to type and reports the server's status; on a
    readback task it reports the recorded amount (or an overridden ``saved_amount`` to force a
    mismatch). No browser, no network, no LLM.
    """

    def __init__(
        self,
        *,
        write_status: str = "WRITTEN",
        saved_amount: str | None = None,
        ref: str = "PV-TEST123",
        saved_key: str | None = None,
    ) -> None:
        self.write_status = write_status
        self.saved_amount = saved_amount
        self.ref = ref
        self.saved_key = saved_key  # override the readback row's key (None = echo this submit's key)
        self.typed_amount: str | None = None
        self.typed_key: str | None = None
        self.tasks: list[str] = []

    async def run(self, task: str, *, allowed_domains, headless) -> str:
        self.tasks.append(task)
        if "payables/new" in task:
            amt = re.search(r"Type exactly ([\d.]+)", task)
            self.typed_amount = amt.group(1) if amt else None
            key = re.search(r"key=([^&\s]+)", task)
            self.typed_key = key.group(1) if key else None
            return json.dumps(
                {"status": self.write_status, "external_ref": self.ref, "idempotency_key": self.typed_key, "note": "entered"}
            )
        if "payables.html" in task:
            req = re.search(r"Load cell equals (\S+)", task)
            amount = self.saved_amount if self.saved_amount is not None else self.typed_amount
            key = self.saved_key if self.saved_key is not None else self.typed_key
            return json.dumps(
                {
                    "load_id": req.group(1) if req else None,
                    "amount": amount,
                    "carrier": "Great Lakes Drayage Co",
                    "external_ref": self.ref,
                    "idempotency_key": key,
                }
            )
        return "{}"


def _ledger(runner) -> BrowserUseWriteLedger:
    return BrowserUseWriteLedger(runner=runner, base_url="http://127.0.0.1:8012", headless=True)


def _approved_run(tmp_path):
    corpus = tmp_path / "corpus"
    generate(corpus, 8, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    store = WorkflowStore(tmp_path / "wf.sqlite3", tenant="tenant-fixture-a")
    seen: set[tuple[str, str]] = set()
    for load in loads:
        process_load_packet(store, load, primary_document_path=corpus / load.documents["carrier_invoice"], seen_invoice_keys=seen)
    run = next(r for r in store.list_runs() if r.load_id == "LD-560003")
    load = next(load for load in loads if load.load_id == "LD-560003")
    record_review_payload(store, build_review_payload(run, load, age_hours=0))
    apply_review_action(store, ReviewActionRequest(run_id=run.id, decision=ReviewDecision.APPROVE_FULL_AMOUNT, amount=_AMOUNT))
    return store, run.id


# ---- BrowserUseWriteLedger unit tests -----------------------------------------

def test_write_payable_parses_browser_confirmation():
    runner = FakeRunner(write_status="WRITTEN")
    result = _ledger(runner).write_payable(
        run_id=1, load_id="LD-560004", carrier="Great Lakes Drayage Co", amount="447.00", charges=[], key="abc123"
    )
    assert result.status == PayableWriteStatus.WRITTEN
    assert result.external_ref == "PV-TEST123"
    assert runner.typed_amount == "447.00"  # the agent typed exactly the approved amount
    assert "payables/new" in runner.tasks[0] and "key=abc123" in runner.tasks[0]


def test_browser_write_ledger_blocks_ascendtms_target():
    try:
        BrowserUseWriteLedger(runner=FakeRunner(), base_url="https://ascendtms.com/accounting/payables")
        raised = False
    except TmsAdapterError:
        raised = True
    assert raised


def test_browser_write_ledger_blocks_nonlocal_real_tms_target():
    try:
        BrowserUseWriteLedger(runner=FakeRunner(), base_url="https://some-tms.example/payables")
        raised = False
    except TmsAdapterError:
        raised = True
    assert raised


def test_get_payable_returns_none_when_absent():
    runner = FakeRunner(saved_amount="null")
    assert _ledger(runner).get_payable("LD-560004") is None


def test_fuzzy_status_resolves_to_written_when_readback_confirms():
    # The agent's free-text status read is unreliable; if the payable is in the table, the submit
    # landed → WRITTEN (verify-by-readback still independently checks the amount before DONE).
    runner = FakeRunner(write_status="Pending-ish nonsense")
    result = _ledger(runner).write_payable(run_id=1, load_id="LD-1", carrier="c", amount="1.00", charges=[], key="k")
    assert result.status == PayableWriteStatus.WRITTEN


def test_unknown_status_and_empty_readback_fails_closed():
    runner = FakeRunner(write_status="Pending-ish nonsense", saved_amount="null")
    try:
        _ledger(runner).write_payable(run_id=1, load_id="LD-1", carrier="c", amount="1.00", charges=[], key="k")
        raised = False
    except Exception:
        raised = True
    assert raised  # unknown status AND no payable on readback → never assume success


# ---- end-to-end through the gated path ----------------------------------------

def test_browser_execution_enters_and_verifies_to_done(tmp_path):
    store, run_id = _approved_run(tmp_path)
    outcome = enter_approved_payable(
        store, _ledger(FakeRunner()), run_id, amount=_AMOUNT, charges=[ChargeLine(name="total", amount=_AMOUNT)]
    )
    assert outcome.final_state == WorkflowState.DONE
    assert outcome.write_status == PayableWriteStatus.WRITTEN
    assert outcome.verified is True
    store.close()


def test_browser_readback_mismatch_blocks_done(tmp_path):
    store, run_id = _approved_run(tmp_path)
    # The TMS "saved" a different amount than the agent typed → verify-by-readback must catch it.
    outcome = enter_approved_payable(store, _ledger(FakeRunner(saved_amount="3634.49")), run_id, amount=_AMOUNT)
    assert outcome.final_state == WorkflowState.FAILED
    assert outcome.verified is False
    store.close()


def test_browser_duplicate_status_routes_to_failed(tmp_path):
    # A real DUPLICATE_BLOCKED status from the TMS must route to FAILED through the browser seam.
    store, run_id = _approved_run(tmp_path)
    outcome = enter_approved_payable(store, _ledger(FakeRunner(write_status="DUPLICATE_BLOCKED")), run_id, amount=_AMOUNT)
    assert outcome.final_state == WorkflowState.FAILED
    assert outcome.write_status == PayableWriteStatus.DUPLICATE_BLOCKED
    store.close()


def test_browser_session_expired_routes_to_waiting(tmp_path):
    store, run_id = _approved_run(tmp_path)
    outcome = enter_approved_payable(store, _ledger(FakeRunner(write_status="SESSION_EXPIRED")), run_id, amount=_AMOUNT)
    assert outcome.final_state == WorkflowState.WAITING_FOR_SESSION
    store.close()


def test_deterministic_readback_parses_exact_row_from_multirow_table(tmp_path):
    # The verify gate must read the RIGHT row deterministically, even with multiple rows present.
    from freight_recon.browser_use_adapter import parse_payables_row
    from freight_recon.mock_tms_write_server import render_payables_table
    from freight_recon.tms_write import MockTmsWriteLedger

    led = MockTmsWriteLedger(tmp_path / "l.json")
    led.write_payable(run_id=2, load_id="LD-560002", carrier="Iron Horse", amount="3569.50", charges=[], key="KEY-2")
    led.write_payable(run_id=4, load_id="LD-560004", carrier="Great Lakes", amount="4172.00", charges=[], key="KEY-4")
    html = render_payables_table(led)

    assert parse_payables_row(html, "LD-560002")["amount"] == "3569.50"
    assert parse_payables_row(html, "LD-560002")["idempotency_key"] == "KEY-2"
    assert parse_payables_row(html, "LD-560004")["amount"] == "4172.00"  # not confused by the other row
    assert parse_payables_row(html, "LD-999999") is None


def test_deterministic_readback_fails_closed_on_duplicate_rows():
    from freight_recon.browser_use_adapter import parse_payables_row

    html = (
        '<table>'
        '<tr class="payable-row" data-load-id="LD-1"><td class="amount">100.00</td>'
        '<td class="idempotency-key">A</td></tr>'
        '<tr class="payable-row" data-load-id="LD-1"><td class="amount">999.00</td>'
        '<td class="idempotency-key">B</td></tr>'
        '</table>'
    )
    # Two rows for the same load → ambiguous → fail closed (never guess which is authoritative).
    assert parse_payables_row(html, "LD-1") is None


def test_deterministic_verify_reaches_done(tmp_path):
    # Agent writes (fuzzy is fine); verify-by-readback is a deterministic independent read → DONE.
    store, run_id = _approved_run(tmp_path)
    runner = FakeRunner()
    ledger = BrowserUseWriteLedger(
        runner=runner,
        base_url="http://localhost:8012",
        readback_fn=lambda lid: {"amount": _AMOUNT, "idempotency_key": runner.typed_key},
    )
    outcome = enter_approved_payable(store, ledger, run_id, amount=_AMOUNT)
    assert outcome.final_state == WorkflowState.DONE
    assert outcome.verified is True
    store.close()


def test_fuzzy_status_with_mismatched_readback_key_fails_closed():
    # Unknown status AND the readback row carries a DIFFERENT idempotency key (a prior/duplicate
    # payable, not our write) → must NOT be reported as WRITTEN. This is the masked-duplicate guard.
    runner = FakeRunner(write_status="garbled nonsense", saved_key="SOMEONE-ELSES-KEY")
    try:
        _ledger(runner).write_payable(run_id=1, load_id="LD-1", carrier="c", amount="1.00", charges=[], key="my-key")
        raised = False
    except Exception:
        raised = True
    assert raised
