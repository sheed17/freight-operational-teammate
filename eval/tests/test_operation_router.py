"""Tests for the request->agent->result bridge (Version B): bounded lanes, gates, refusal, receipts."""

import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.operation_router import (  # noqa: E402
    OperationLane,
    OperationRouter,
    freight_lanes,
)
from freight_recon.operator_agent import OperatorAgent  # noqa: E402
from freight_recon.slack_delegate import CommandIntent, CommandKind  # noqa: E402
from freight_recon.workflow import WorkflowStore, operation_commit_key  # noqa: E402


class FakeActuator:
    def __init__(self):
        self.calls = []

    def observe(self):
        return {"url": "https://tms.test/x", "interactive": [], "errors": []}

    def navigate(self, url): self.calls.append(("navigate", url)); return True
    def click(self, target): self.calls.append(("click", target)); return True
    def type(self, target, value): self.calls.append(("type", target, value)); return True
    def select(self, target, option): self.calls.append(("select", target, option)); return True
    def read(self, target): self.calls.append(("read", target)); return "INV-4912"


def _scripted_llm(actions):
    seq = list(actions)

    def complete(_prompt):
        return json.dumps(seq.pop(0)) if seq else json.dumps({"action": "DONE", "why": "finished"})

    return complete


def _operate(summary, params=None):
    return CommandIntent(kind=CommandKind.OPERATE, summary=summary, params=params or {})


def _agent_factory(llm, actuator=None):
    act = actuator or FakeActuator()

    def build_agent(*, approved_amount=None, approve=None, prepare_only=False):
        return OperatorAgent(actuator=act, complete=llm, approved_amount=approved_amount,
                             approve=approve, prepare_only=prepare_only)

    build_agent.actuator = act
    return build_agent


def test_known_lane_drives_agent_to_done():
    llm = _scripted_llm([
        {"action": "NAVIGATE", "target": "https://tms.test/invoices/new"},
        {"action": "TYPE", "target": "Total Charge", "value": "0"},
        {"action": "CLICK", "target": "Save invoice"},
        {"action": "READ", "target": "invoice number"},
        {"action": "DONE", "why": "invoice INV-4912 created"},
    ])
    build_agent = _agent_factory(llm)
    router = OperationRouter(
        lanes=freight_lanes(), build_agent=build_agent,
        approved_amount_for=lambda _i: "2850.00",
    )
    res = router.run(_operate("invoice today's delivered load for Acme"), approve=lambda a: True)
    assert res.status == "DONE" and res.lane == "raise_invoice"
    # Money fence: the approved amount reached the form, not a model-chosen number.
    assert ("type", "Total Charge", "2850.00") in build_agent.actuator.calls
    assert "✅ Done" in res.to_slack()


def test_unknown_request_is_refused_not_improvised():
    # The core Version-B boundary: a request with no known lane must NOT free-form a goal.
    build_agent = _agent_factory(_scripted_llm([]))
    router = OperationRouter(lanes=freight_lanes(), build_agent=build_agent, approved_amount_for=lambda _i: "1")
    res = router.run(_operate("reorganize the whole accounting system however you see fit"))
    assert res.status == "REFUSED" and res.lane is None
    assert build_agent.actuator.calls == []  # the agent never ran
    assert "won't improvise" in res.to_slack()


def test_money_lane_without_approved_amount_escalates_at_the_door():
    build_agent = _agent_factory(_scripted_llm([]))
    router = OperationRouter(lanes=freight_lanes(), build_agent=build_agent, approved_amount_for=lambda _i: None)
    res = router.run(_operate("invoice the delivered load for Acme"))
    assert res.status == "ESCALATED" and res.lane == "raise_invoice"
    assert "no human-approved amount" in res.note
    assert build_agent.actuator.calls == []  # never drove without an approved amount


def test_browser_preflight_blocks_operation_before_agent_runs():
    from types import SimpleNamespace

    called = {"build": 0}

    def build_agent(**_kwargs):
        called["build"] += 1
        return OperatorAgent(actuator=FakeActuator(), complete=_scripted_llm([]))

    router = OperationRouter(
        lanes=freight_lanes(),
        build_agent=build_agent,
        approved_amount_for=lambda _i: "2850.00",
        browser_health_check=lambda: SimpleNamespace(
            healthy=False,
            status="SESSION_EXPIRED",
            detail="TMS browser session appears to be on a login/session-expired page; human re-auth is required.",
            active_url="https://secure.truckingoffice.com/login",
        ),
    )
    res = router.run(_operate("invoice the delivered load for Acme"), approve=lambda a: True)
    assert res.status == "ESCALATED" and res.lane == "raise_invoice"
    assert "human re-auth" in res.note
    assert res.steps[0]["browser_preflight"] == "SESSION_EXPIRED"
    assert called["build"] == 0


def test_agent_escalation_propagates_as_result():
    llm = _scripted_llm([{"action": "ESCALATE", "target": "cannot find the customer field"}])
    build_agent = _agent_factory(llm)
    router = OperationRouter(lanes=freight_lanes(), build_agent=build_agent, approved_amount_for=lambda _i: "100.00")
    res = router.run(_operate("invoice the load for Acme"), approve=lambda a: True)
    assert res.status == "ESCALATED" and res.lane == "raise_invoice"
    assert "✋ I need you" in res.to_slack()


def test_payable_lane_matches_and_binds_amount():
    # a money run must read the record back before DONE (verify-before-done)
    llm = _scripted_llm([{"action": "READ", "target": "saved payable"}, {"action": "DONE", "why": "payable recorded"}])
    build_agent = _agent_factory(llm)
    router = OperationRouter(lanes=freight_lanes(), build_agent=build_agent, approved_amount_for=lambda _i: "1200.00")
    res = router.run(_operate("record the carrier payable for load LD-5001"), approve=lambda a: True)
    assert res.status == "DONE" and res.lane == "record_payable"


def test_explicit_lane_param_overrides_keyword_matching():
    llm = _scripted_llm([{"action": "DONE", "why": "ok"}])
    build_agent = _agent_factory(llm)
    router = OperationRouter(lanes=freight_lanes(), build_agent=build_agent, approved_amount_for=lambda _i: "5.00")
    res = router.run(CommandIntent(CommandKind.OPERATE, "handle this", {"lane": "raise_invoice"}),
                     approve=lambda a: True)
    assert res.lane == "raise_invoice"


def test_non_money_lane_runs_without_an_amount():
    lane = OperationLane("status_check", ("check status",), lambda i: "check the load status", requires_amount=False)
    llm = _scripted_llm([{"action": "DONE", "why": "checked"}])
    build_agent = _agent_factory(llm)
    router = OperationRouter(lanes=[lane], build_agent=build_agent, approved_amount_for=lambda _i: None)
    res = router.run(_operate("check status of LD-5001"))
    assert res.status == "DONE" and res.lane == "status_check"


def test_cross_run_commit_claim_prevents_resumed_double_save(tmp_path):
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    try:
        first_llm = _scripted_llm([
            {"action": "CLICK", "target": "Save invoice"},
            {"action": "ESCALATE", "target": "readback was slow"},
        ])
        first_agent = _agent_factory(first_llm)
        router = OperationRouter(
            lanes=freight_lanes(),
            build_agent=first_agent,
            approved_amount_for=lambda _i: "2850.00",
            tenant="acme",
            commit_store=store,
        )
        intent = _operate(
            "invoice the delivered load for Acme",
            {"customer": "Acme", "load_ref": "LD-9001", "commit": True},
        )

        first = router.run(intent, approve=lambda a: True)
        assert first.status == "ESCALATED"
        assert ("click", "Save invoice") in first_agent.actuator.calls
        assert any(step.get("committed") is True for step in first.steps)

        second_llm = _scripted_llm([
            {"action": "CLICK", "target": "Save invoice"},
            {"action": "DONE", "why": "saved again"},
        ])
        second_agent = _agent_factory(second_llm)
        resumed = OperationRouter(
            lanes=freight_lanes(),
            build_agent=second_agent,
            approved_amount_for=lambda _i: "2850.00",
            tenant="acme",
            commit_store=store,
        ).run(intent, approve=lambda a: True)

        assert resumed.status == "DONE"
        assert "already committed" in resumed.note
        assert ("click", "Save invoice") not in second_agent.actuator.calls
    finally:
        store.close()


def test_cross_run_commit_claim_prevents_concurrent_double_save(tmp_path):
    db_path = tmp_path / "workflow.sqlite3"
    WorkflowStore(db_path).close()
    start = threading.Barrier(2)
    lock = threading.Lock()
    saves = []
    results = []

    class SlowSaveActuator(FakeActuator):
        def click(self, target):
            with lock:
                saves.append(target)
            time.sleep(0.05)
            return super().click(target)

    def run_once():
        store = WorkflowStore(db_path)
        try:
            actuator = SlowSaveActuator()
            build_agent = _agent_factory(
                _scripted_llm([
                    {"action": "CLICK", "target": "Save invoice"},
                    {"action": "READ", "target": "Invoice #"},   # verify-before-done: confirm it saved
                    {"action": "DONE", "why": "saved"},
                ]),
                actuator=actuator,
            )
            router = OperationRouter(
                lanes=freight_lanes(),
                build_agent=build_agent,
                approved_amount_for=lambda _i: "2850.00",
                tenant="acme",
                commit_store=store,
            )
            intent = _operate(
                "invoice the delivered load for Acme",
                {"customer": "Acme", "load_ref": "LD-9001", "commit": True},
            )
            start.wait(timeout=5)
            results.append(router.run(intent, approve=lambda a: True).status)
        finally:
            store.close()

    threads = [threading.Thread(target=run_once) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    # Exactly one save happens (no double-write). The winner commits -> DONE; the loser can't tell a
    # live-concurrent winner from a crashed one (both look RESERVED), so it fails SAFE -> ESCALATED
    # ("verify"), rather than silently reporting a done it didn't do. Safety over a tidy double-DONE.
    assert sorted(results) == ["DONE", "ESCALATED"]
    assert saves == ["Save invoice"]


def test_staged_run_with_create_invoice_opener_is_not_read_as_committed():
    # Regression: a PREPARED run clicks the load's "Create Invoice" OPENER link, then stops before the
    # form's Save. The old keyword heuristic saw "create" in the target and stamped the run committed —
    # which poisoned the payload so its 'submit' resume was refused. A commit is real only when the agent
    # tags the actually-executed submit step committed=True.
    from freight_recon.operation_router import _result_committed
    from freight_recon.operator_agent import AgentResult

    staged = AgentResult("goal", "PREPARED", [
        {"action": "CLICK", "target": "101", "ok": True, "why": "open load"},
        {"action": "CLICK", "target": "Create Invoice", "ok": True, "why": "open the invoice form"},
    ], "filled and staged; stopped before Save")
    assert _result_committed(staged) is False           # opener label must not read as a commit

    real = AgentResult("goal", "DONE", [
        {"action": "CLICK", "target": "Create Invoice", "ok": True, "committed": True, "why": "submit"},
    ], "committed and confirmed")
    assert _result_committed(real) is True               # the real tagged commit does count


def test_operation_commit_key_normalizes_equivalent_money_amounts():
    base = {
        "tenant": "acme",
        "lane": "record_payable",
        "load_ref": "LD-1",
        "party": "TQL",
    }
    assert operation_commit_key(**base, approved_amount="$2,850") == operation_commit_key(
        **base,
        approved_amount="2850.00",
    )


def test_expanded_operation_set_routes_each_owner_request_to_its_lane():
    # The back-office operations an owner requests each resolve to a distinct bounded lane. Ordering +
    # keywords keep overlaps ("payment on invoice" vs "invoice ...") from mis-routing.
    router = OperationRouter(lanes=freight_lanes(), build_agent=lambda **_: None)

    def lane(text):
        got = router.lane_for(CommandIntent(kind=CommandKind.OPERATE, summary=text, params={}))
        return got.name if got else None

    assert lane("invoice Great Lakes for load 105") == "raise_invoice"
    assert lane("bill load 105") == "raise_invoice"
    assert lane("record payment on invoice 560003 for 184.50") == "record_payment"
    assert lane("apply the payment to invoice 560009") == "record_payment"
    assert lane("credit invoice 560003 by 200 short pay") == "adjust_invoice"
    assert lane("record payable to Iron Horse for LD-5") == "record_payable"
    assert lane("attach the POD to load 105") == "file_document"
    assert lane("create a new load for Acme from Dallas to Chicago") == "create_load"
    assert lane("book a load for Coyote") == "create_load"
    assert lane("mark load 105 delivered") == "update_status"
    assert lane("update status of 88 to dispatched") == "update_status"
    assert lane("log a check call on load 105 driver is 50 miles out") == "check_call"
    # the invoice lane still wins its own phrasing even though it mentions a delivered load
    assert lane("invoice today's delivered load for Acme") == "raise_invoice"

    # operational lanes create/update/log records without money; the AR/AP lanes require an amount
    lanes = {l.name: l for l in freight_lanes()}
    for op in ("file_document", "create_load", "update_status", "check_call"):
        assert lanes[op].requires_amount is False, op
    for money in ("raise_invoice", "record_payment", "adjust_invoice", "record_payable"):
        assert lanes[money].requires_amount is True, money


def test_crash_after_reservation_escalates_on_retry_not_false_done(tmp_path):
    # BLOCKER regression: a run that crashes AFTER reserving the commit but BEFORE any write must not,
    # on retry, be reported as DONE ("already committed") with nothing written — and must not blindly
    # repeat the write either. It escalates for a human to verify in the TMS.
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    try:
        class BoomActuator(FakeActuator):
            def observe(self):
                raise RuntimeError("CDP disconnected / process killed by supervisor")

        boom = _agent_factory(_scripted_llm([]), actuator=BoomActuator())
        intent = _operate("invoice the delivered load for Acme",
                          {"customer": "Acme", "load_ref": "LD-9001", "commit": True})
        r1 = OperationRouter(lanes=freight_lanes(), build_agent=boom, approved_amount_for=lambda _i: "2850.00",
                             tenant="acme", commit_store=store)
        raised = False
        try:
            r1.run(intent, approve=lambda a: True)
        except RuntimeError:
            raised = True
        assert raised and boom.actuator.calls == []          # crashed, wrote nothing

        good = _agent_factory(_scripted_llm([{"action": "READ", "target": "x"}, {"action": "DONE", "why": "ok"}]))
        retry = OperationRouter(lanes=freight_lanes(), build_agent=good, approved_amount_for=lambda _i: "2850.00",
                                tenant="acme", commit_store=store).run(intent, approve=lambda a: True)
        assert retry.status == "ESCALATED"                   # NOT a false DONE
        assert "not confirmed done" in retry.note.lower()
        assert good.actuator.calls == []                     # did NOT blindly repeat the write
    finally:
        store.close()


def test_leaked_reserved_claim_from_hard_kill_escalates(tmp_path):
    # A hard kill can't run the crash handler, so it leaves a bare RESERVED claim. The duplicate-guard
    # must still escalate (verify), not report DONE.
    store = WorkflowStore(tmp_path / "workflow.sqlite3")
    try:
        store.claim_operation_commit(tenant="acme", lane="raise_invoice", load_ref="LD-9001",
                                     party="Acme", approved_amount="2850.00", payload={"status": "RESERVED"})
        good = _agent_factory(_scripted_llm([{"action": "DONE", "why": "ok"}]))
        res = OperationRouter(lanes=freight_lanes(), build_agent=good, approved_amount_for=lambda _i: "2850.00",
                              tenant="acme", commit_store=store).run(
            _operate("invoice the delivered load for Acme", {"customer": "Acme", "load_ref": "LD-9001", "commit": True}),
            approve=lambda a: True)
        assert res.status == "ESCALATED" and "not confirmed done" in res.note.lower()
        assert good.actuator.calls == []
    finally:
        store.close()
