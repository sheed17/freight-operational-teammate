"""P9 deep-end 3 — the operational work engine, tested with freight, through time.

Every test runs load histories through the REAL spine — the P6-P8 machines on a real database, the
External Entity Mapping, the projection, the detectors — and asks, after records arrive and after
time passes, what work remains. Nothing is mocked below the gateway, nothing leaves the process, and
no test here calls a model: where a model's seat is occupied it is by a scripted reply, including
hostile ones.

### THE CORPUS IS SYNTHETIC DEVELOPMENT INPUT. A passing test says the engine behaves as specified on
invented histories. It validates no freight rule and is not customer evidence.

### WHAT COULD FAIL, AND WOULD. Each claim is checked over a population proven non-empty, and
`scripts/mutate_p9_load_work.py` reintroduces the real defect behind each one and confirms the named
test turns RED.
"""

from __future__ import annotations

import json
import socket
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from dark_surface_kit import callers_of  # noqa: E402
from freight_corpus import raw_histories as scenarios_module  # noqa: E402
from freight_corpus.builders import (  # noqa: E402
    HistoryBuilder,
    charges,
    load_ref,
    movement,
    says,
)
from freight_corpus.histories import _cover, _rate_con, _stops, build_corpus  # noqa: E402
from freight_corpus.parties import (  # noqa: E402
    CARRIERS,
    CEDAR,
    CUSTOMERS,
    HARBOR,
    NORTHLINE,
    NORTHLINE_OPS,
    NORTHLINE_PODS,
    NORTHLINE_SMS,
    SETUPS,
    dispatcher,
)
from freight_corpus.raw_histories import build_raw_histories, raw_history_responder  # noqa: E402
from freight_corpus.work_attack import (  # noqa: E402
    CANONICAL_TABLES,
    Mutant,
    audit_state,
    build_mutants,
    row_counts,
    run_mutant,
)
from freight_corpus.work_histories import (  # noqa: E402
    WORK_SETUPS,
    _covered,
    _delivered,
    _invoice_as,
    build_work_histories,
)
from freight_corpus.work_reasoning_cases import (  # noqa: E402
    CONTROL_STATES,
    REASONING_CASES,
    build_states,
    case_states,
    oracle_reply,
    score_case,
)
from freight_recon.freight_domain.corpus_run import cross_tenant_violations  # noqa: E402
from freight_recon.freight_domain.history import FreightHistory  # noqa: E402
from freight_recon.freight_domain.intake import FreightIntake  # noqa: E402
from freight_recon.freight_domain.interpretation import FreightInterpreter  # noqa: E402
from freight_recon.freight_domain.load_work import (  # noqa: E402
    Handling,
    NeedKind,
    NeedStatus,
    Posture,
    ShadowAction,
    _Build,
    evaluate_load_work,
    evaluate_unplaced_work,
    need_id,
    render_load_work,
)
from freight_recon.freight_domain.work_reasoning import (  # noqa: E402
    ADVISED,
    FAILED,
    NOT_NEEDED,
    REUSED,
    LoadWorkReasoner,
    build_request,
    question_digest,
    route_load_work,
)
from freight_recon.freight_domain.work_run import run_work_histories, work_states  # noqa: E402
from freight_recon.inference.contracts import LoadWorkReasoning, RoutingViolation, Task  # noqa: E402
from freight_recon.inference.gateway import ProviderRejection, TransportFailure  # noqa: E402
from freight_recon.inference.ledger import InferenceBudget, InferenceLedger  # noqa: E402
from freight_recon.inference.prompts import (  # noqa: E402
    PROMPT_VERSION,
    prompt_version_for,
    render,
)
from freight_recon.inference.scripted import ScriptedGateway  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402

REASONER = "src/freight_recon/freight_domain/work_reasoning.py"


@pytest.fixture(autouse=True)
def _no_network(monkeypatch):
    """No test in this module may open a socket. A model call that slipped out would fail here."""
    def refuse(*args, **kwargs):
        raise AssertionError("a test in test_p9_load_work.py tried to open a network connection")
    monkeypatch.setattr(socket.socket, "connect", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)


def _store(directory: Path, name: str = "work.db") -> WorkflowStore:
    return WorkflowStore(directory / name, tenant=NORTHLINE)


def _history(history_id: str) -> FreightHistory:
    return next(h for h in build_work_histories() if h.history_id == history_id)


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    """The fifteen through-time histories, in ONE database for both brokerages, with no model."""
    store = _store(tmp_path_factory.mktemp("p9-work"))
    result = run_work_histories(store.conn, WORK_SETUPS, build_work_histories())
    yield result, store.conn
    store.close()


def _view(result, tenant: str, load: str):
    return result.intakes[tenant].projection().view_by_load_ref(load)


# ============================================================ the corpus, through time

def test_every_labeled_moment_of_every_history_holds(run):
    """The finish line: at 58 labeled moments across fifteen load histories, the work Neyma reports
    is the work the history says remains. Counted, not assumed."""
    result, _ = run
    assert len(result.histories) == 15
    for item in result.histories:
        assert item.checkpoints, f"{item.history.history_id} labels no moment"
        assert item.mismatches == [], item.mismatches
    metrics = result.report["metrics"]
    assert metrics["labeled_checkpoints"] >= 55 and metrics["labeled_checks"] >= 250
    assert metrics["labeled_checks_failed"] == 0
    assert metrics["loads_evaluated"] == 15
    # Work both OPENED and CLOSED: a corpus where nothing ever closes proves no lifecycle.
    for name in ("needs_automatically_satisfied", "needs_resolved_by_a_human",
                 "waits_that_escalated_to_a_follow_up", "duplicate_needs_suppressed", "waits",
                 "neyma_action_candidates", "human_required_needs",
                 "loads_with_zero_routine_work", "loads_reaching_billing_ready",
                 "loads_blocked_from_billing_ready"):
        assert metrics[name] > 0, f"the corpus exercises no {name}"
    assert metrics["raw_operational_signals"] > metrics["unique_operational_needs"]
    assert metrics["external_effect_rows"] == 0 and metrics["wrong_cross_tenant_mappings"] == 0
    assert "usd" not in json.dumps(result.report).lower(), "the report carries money"


def test_a_healthy_billing_ready_load_has_zero_routine_work(run):
    """A load picked up, tracked inside the cadence, delivered, signed for and billed as agreed is
    QUIET — at the end, and it needed no human at any moment on the way. Nothing was manufactured
    so that it would have a next action."""
    result, _ = run
    final = result.state(NORTHLINE, "LD-49002")
    assert final.routine_work_is_zero and final.posture is Posture.QUIET
    assert final.next_action is None and final.billing_ready
    assert final.reconciliation == ("RECONCILED",) and final.requirements == {"POD": "SATISFIED"}
    assert final.housekeeping == ()
    seen = [s.states[final.load_id] for s in result.steps
            if s.history_id == "W02" and final.load_id in s.states]
    assert len(seen) >= 15
    assert not any(state.human_attention for state in seen), "a clean load asked for a human"
    # It was not quiet the whole way: it was WATCHED, and one thing was asked for and received.
    assert {state.posture for state in seen} == {Posture.WAIT, Posture.NEYMA_CAN_ACT,
                                                 Posture.QUIET}


# ============================================================ identity, duplication, replay

def test_evaluating_the_same_state_twice_creates_nothing(run):
    """Same canonical state, same needs, same ids — and not one canonical row written. The
    population is every load of both brokerages, and the tables are proven non-empty first."""
    result, conn = run
    before = row_counts(conn)
    assert all(before[t] > 0 for t in ("observations", "expectations", "exceptions",
                                       "work_items", "conflicts", "event_outbox"))
    first = {tenant: work_states(intake) for tenant, intake in result.intakes.items()}
    second = {tenant: work_states(intake) for tenant, intake in result.intakes.items()}
    assert sum(len(states) for states in first.values()) == 15
    assert sum(len(s.needs) for states in first.values() for s in states.values()) >= 8
    for tenant, states in first.items():
        for load_id, state in states.items():
            assert state.digest() == second[tenant][load_id].digest()
            ids = [n.need_id for n in state.needs]
            assert len(ids) == len(set(ids))
    assert row_counts(conn) == before, "asking what work remains wrote canonical rows"
    assert set(CANONICAL_TABLES) >= {"work_items", "exceptions", "expectations"}


def test_a_duplicate_inbound_event_creates_no_duplicate_work(run, tmp_path):
    """The promise arrives again after it has gone overdue; the signed POD arrives twice more. The
    work is the same work: same need ids, and no second Expectation, Exception or Work Item."""
    result, _ = run
    for history_id, before, duplicate, load in (("W03", "a-minute-late", "check-in-again",
                                                 "LD-49003"),
                                                ("W07", "pod-signed", "pod-signed-again",
                                                 "LD-49007")):
        one, two = result.at(history_id, before, load), result.at(history_id, duplicate, load)
        assert [n.need_id for n in one.needs] == [n.need_id for n in two.needs]
        assert [n.status for n in one.needs] == [n.status for n in two.needs]
    step = next(s for s in result.steps if s.label == "check-in-again")
    assert step.disposition == "DUPLICATE"

    store = _store(tmp_path)
    history = _history("W03")
    labels = [r.label for r in history.records]
    intake = FreightIntake(store.conn, WORK_SETUPS[NORTHLINE])
    for record in history.records[: labels.index("a-minute-late") + 1]:
        intake.ingest(record)
    counted = ("expectations", "exceptions", "work_items", "conflicts")
    before = {t: row_counts(store.conn)[t] for t in counted}
    assert before["expectations"] >= 2 and before["exceptions"] >= 1
    intake.ingest(history.records[labels.index("check-in-again")])
    assert {t: row_counts(store.conn)[t] for t in counted} == before
    store.close()


def test_replay_and_restart_reproduce_the_same_work(run, tmp_path):
    """Run the histories again in a fresh database: the same needs, the same ids, the same lives.
    Then throw the process away mid-history and rebuild it from the database: the same work."""
    result, _ = run
    store = _store(tmp_path, "again.db")
    again = run_work_histories(store.conn, WORK_SETUPS, build_work_histories())
    assert set(again.final) == set(result.final) and len(result.final) == 15
    for key, state in result.final.items():
        assert again.final[key].digest() == state.digest()
    assert {k: (v.closed_how, v.reopened) for k, v in again.lives.items()} == {
        k: (v.closed_how, v.reopened) for k, v in result.lives.items()}

    rebuilt = FreightIntake(store.conn, WORK_SETUPS[NORTHLINE])
    as_of = again.intakes[NORTHLINE].foundation.now()
    for load_id, state in work_states(rebuilt, as_of=as_of).items():
        assert state.digest() == again.final[(NORTHLINE, load_id)].digest()
    store.close()


def test_a_need_is_one_need_however_many_rows_describe_it(run):
    """One missing POD is one piece of work — not a requirement, an Expectation and an Exception
    shown as three. The underlying rows are all still there, underneath."""
    result, _ = run
    late = result.at("W07", "a-day-passes", "LD-49007")
    assert [n.kind for n in late.needs] == [NeedKind.DOCUMENT_REQUIRED]
    kinds = sorted(o.split(":", 1)[0] for o in late.needs[0].origins)
    assert kinds == ["exception", "expectation", "requirement"], kinds
    assert late.raw_signals == 3 and len(late.needs) == 1
    assert late.housekeeping == (), "the Exception of a LIVE cause was filed as housekeeping"

    unusable = result.at("W07", "pod-unsigned", "LD-49007")
    assert [n.kind for n in unusable.needs] == [NeedKind.DOCUMENT_REQUIRED]
    assert unusable.needs[0].need_id == late.needs[0].need_id
    assert sorted({o.split(":", 1)[0] for o in unusable.needs[0].origins}) == [
        "document", "exception", "expectation", "requirement"]
    assert len(unusable.needs[0].origins) == 5, "the unusable POD's own Exception is folded in"
    # Three ways to be late on one load are ONE follow-up to the carrier.
    promised = result.at("W15", "two-passes", "LD-49015")
    assert len([n for n in promised.needs if n.kind is NeedKind.CARRIER_STATUS_OVERDUE]) == 1
    assert promised.together and len(promised.together[0]) == 2


def test_one_cause_reached_by_two_signals_is_one_need_not_two(run):
    """The guarantee itself, at the point it is enforced: a need added for a cause that already has
    one MERGES into it — both signals behind one piece of work — and never becomes a second."""
    result, _ = run
    view = _view(result, NORTHLINE, "LD-49002")
    build = _Build(view=view, setup=WORK_SETUPS[NORTHLINE], as_of="2026-07-30T00:00:00.000Z")
    for origin, reason in (("requirement:r1", "DOCUMENT_NOT_RECEIVED"),
                           ("expectation:e1", "DOCUMENT_CHANNEL_BLIND")):
        build.add(NeedKind.DOCUMENT_REQUIRED, ("POD",), status=NeedStatus.OPEN,
                  handling=Handling.NEYMA_ACTION_CANDIDATE, reason_codes=(reason,), why="x",
                  actions=(ShadowAction.REQUEST_POD,), origins=(origin,))
    assert len(build.needs) == 1, "the same cause became two pieces of work"
    assert build.needs[0].origins == ("requirement:r1", "expectation:e1")
    assert build.needs[0].reason_codes == ("DOCUMENT_NOT_RECEIVED", "DOCUMENT_CHANNEL_BLIND")
    build.add(NeedKind.DOCUMENT_REQUIRED, ("BOL",), status=NeedStatus.OPEN,
              handling=Handling.NEYMA_ACTION_CANDIDATE, reason_codes=("x",), why="x")
    assert len(build.needs) == 2, "a different cause must be a different need"
    with pytest.raises(ValueError):
        build.add(NeedKind.EVIDENCE_CONFLICT, ("c",), status=NeedStatus.OPEN,
                  handling=Handling.WAIT, reason_codes=("x",), why="x", human_required=True)


def test_an_invoice_resent_with_different_charges_is_a_dispute_and_shows_no_money(tmp_path):
    """An invoice reconciles. The same invoice NUMBER then arrives again with a different linehaul.
    It does not stay "good": the payable is disputed, the reconciliation is no longer RECONCILED,
    and one human is asked — shown that the two renditions differ, and neither figure. A human's
    need never offers WAIT."""
    h = HistoryBuilder("WR", "an invoice re-sent with different charges", NORTHLINE,
                       day="2026-08-12", zone="America/Chicago",
                       hostile=("duplicate_invoice_different_charges",))
    load = "LD-49096"
    stops = _stops(h, pickup="Prairie Ag Decatur", delivery="Three Rivers Co-op")
    _cover(h, NORTHLINE_OPS, NORTHLINE_PODS)
    customer, carrier = _covered(h, load=load, customer="prairie_ag", carrier="ironwood",
                                 po="PO-2396", bol="BOL-56096", pro="PRO-60096", sell=188000,
                                 stops=stops, at=("07:30", "08:10"))
    _rate_con(h, "rate-con", h.t("08:30"), load=load, number="RC-49096", carrier="ironwood",
              linehaul=150000, via=NORTHLINE_OPS)
    _delivered(h, "delivered", h.t("15:00"), load=load, customer=customer, carrier=carrier,
               po="PO-2396", bol="BOL-56096", pro="PRO-60096", sell=188000, stops=stops)
    h.document("pod", h.t("15:20"), "POD", f"PROOF OF DELIVERY | load {load}",
               refs=(load_ref(load),), via=NORTHLINE_PODS, signed=True)
    for label, clock, linehaul, rendition in (("invoice", "16:00", 150000, "a"),
                                              ("invoice-revised", "17:00", 163500, "b")):
        _invoice_as(h, label, h.t(clock), load=load, number="IW-9096", carrier="ironwood",
                    linehaul=linehaul, via=NORTHLINE_OPS, mc=CARRIERS["ironwood"]["mc"],
                    rendition=rendition)
    store = _store(tmp_path)
    result = run_work_histories(store.conn, WORK_SETUPS, [h.build({})])
    first = result.at("WR", "invoice", load)
    assert first.routine_work_is_zero and first.reconciliation == ("RECONCILED",)
    state = result.at("WR", "invoice-revised", load)
    assert state.reconciliation == ("COMPUTED",), "a re-billed invoice stayed RECONCILED"
    assert [n.kind for n in state.needs] == [NeedKind.EVIDENCE_CONFLICT]
    need = state.needs[0]
    assert need.human_required and need.reason_codes == ("FINANCIAL:carrier_payable.linehaul",)
    assert need.actions == (ShadowAction.ASK_HUMAN_REVIEW_FINANCIAL_DISCREPANCY,)
    assert ShadowAction.WAIT not in need.actions
    view = result.intakes[NORTHLINE].projection().view_by_load_ref(load)
    stated = [p["stated_value"] for c in view.conflicts for p in c["parties"]]
    assert sorted(stated) == ["USD 1,500.00 OUT", "USD 1,635.00 OUT"], "the figures ARE on record"
    document = json.dumps(state.as_document()) + render_load_work(state)
    for figure in ("1,500", "1,635", "150000", "163500", "USD"):
        assert figure not in document, f"{figure} leaked into the work state"
    assert len([e for e in need.evidence if "states a different figure" in e.note]) == 2
    assert audit_state(state, view, tenant=NORTHLINE) == []
    assert next(iter(view.payables.values())).lifecycle_state == "DISPUTED"
    store.close()


def test_a_conflict_and_the_exception_raised_for_it_are_one_need(tmp_path):
    """An Exception whose SOURCE is a Conflict is that Conflict's paperwork, not a second task."""
    store = _store(tmp_path)
    history = _history("W06")
    labels = [r.label for r in history.records]
    intake = FreightIntake(store.conn, WORK_SETUPS[NORTHLINE])
    for record in history.records[: labels.index("portal-says-morning") + 1]:
        intake.ingest(record)
    view = intake.projection().view_by_load_ref("LD-49006")
    conflict = view.open_conflicts()[0]
    intake.foundation.raise_exception(
        exception_id="exc-for-the-conflict", type="conflict_needs_owner", severity="SEV2",
        source_ref=conflict["conflict_id"], source_kind="conflict", owner_id="dana.ortiz",
        summary="An appointment conflict has not been looked at.", entity_ref=view.ref)
    state = work_states(intake)[view.load_id]
    conflicts = [n for n in state.needs if n.kind is NeedKind.EVIDENCE_CONFLICT]
    assert len(conflicts) == 1 and len(state.human_attention) == 1
    assert sorted(o.split(":", 1)[0] for o in conflicts[0].origins) == ["conflict", "exception"]
    assert not [n for n in state.needs if n.kind is NeedKind.UNCLASSIFIED_EXCEPTION]
    store.close()


# ============================================================ time

def test_work_changes_when_time_passes_and_nothing_arrives(run, tmp_path):
    """10:00 "I'll update you in an hour" is a WAIT. 10:45 is the same wait with less of it left.
    11:01, on a clock that has TICKED, is an overdue promise Neyma could follow up. And 11:01 merely
    ASKED ABOUT, before the deadline machinery has ruled, is not called late by this projection."""
    result, _ = run
    said = result.at("W03", "check-in", "LD-49003")
    promise = said.need(NeedKind.CARRIER_UPDATE_PENDING)
    assert promise.handling is Handling.WAIT and said.posture is Posture.WAIT
    assert promise.due_by == "2026-06-09T16:00:00.000Z"
    assert promise.evidence[-1].excerpt.startswith("checked in at the shipper")

    store = _store(tmp_path)
    history = _history("W03")
    intake = FreightIntake(store.conn, WORK_SETUPS[NORTHLINE])
    for record in history.records:
        intake.ingest(record)
        if record.label == "check-in":
            break
    rows = row_counts(store.conn)
    at = {clock: next(iter(work_states(intake, as_of=f"2026-06-09T{clock}:00.000Z").values()))
          for clock in ("15:00", "15:45", "16:01")}
    assert row_counts(store.conn) == rows, "asking about a later time advanced something"
    assert [at[c].posture for c in ("15:00", "15:45")] == [Posture.WAIT, Posture.WAIT]
    assert at["15:45"].need(NeedKind.CARRIER_UPDATE_PENDING).need_id == promise.need_id
    assert "15m remaining" in render_load_work(at["15:45"])
    due = at["16:01"].need(NeedKind.CARRIER_STATUS_OVERDUE)
    assert due.status.value == "DUE" and due.handling is Handling.DETERMINISTIC
    assert ShadowAction.REQUEST_CARRIER_STATUS not in due.actions, "called late before M8 ruled"
    store.close()

    ticked = result.at("W03", "a-minute-late", "LD-49003").need(NeedKind.CARRIER_STATUS_OVERDUE)
    assert ticked.status.value == "OVERDUE"
    assert ticked.handling is Handling.NEYMA_ACTION_CANDIDATE and not ticked.human_required
    assert ticked.actions == (ShadowAction.REQUEST_CARRIER_STATUS,)
    closed = result.at("W03", "update", "LD-49003")
    assert closed.need(NeedKind.CARRIER_STATUS_OVERDUE) is None
    assert {s.kind for s in closed.settled} >= {NeedKind.CARRIER_STATUS_OVERDUE,
                                                NeedKind.CARRIER_UPDATE_PENDING}


def test_a_blind_channel_is_never_reported_as_a_late_carrier(run):
    """The cadence passed while the tracking feed was DOWN. A follow-up is offered; "overdue" is
    not said, because nobody was watching the channel the silence was on."""
    result, _ = run
    need = result.at("W05", "cadence-passes", "LD-49005").need(NeedKind.CARRIER_STATUS_OVERDUE)
    assert need.status.value == "UNVERIFIED" and "TRACKING_UNVERIFIED" in need.reason_codes
    assert "TRACKING_OVERDUE" not in need.reason_codes
    assert need.actions == (ShadowAction.REQUEST_CARRIER_STATUS,)
    watched = result.at("W04", "first-silence", "LD-49004").need(
        NeedKind.CARRIER_STATUS_OVERDUE)
    assert watched.status.value == "OVERDUE" and "TRACKING_OVERDUE" in watched.reason_codes


def test_a_moved_appointment_moves_the_deadline_being_watched(run):
    """A human confirms a different delivery window. The arrival watch follows it — in the
    receiver's timezone — and the deadline it replaced is retained in M8's own history."""
    result, conn = run
    watch = [n for n in result.at("W06", "dana-decides", "LD-49006").needs
             if n.kind is NeedKind.ARRIVAL_PENDING and "S2" in n.reason_codes[0]]
    assert [n.due_by for n in watch] == ["2026-06-22T15:00:00.000Z"]
    final = [n for n in result.at("W06", "dana-decides-again", "LD-49006").needs
             if n.kind is NeedKind.ARRIVAL_PENDING]
    assert [n.due_by for n in final] == ["2026-06-22T20:00:00.000Z"]
    assert final[0].need_id == watch[0].need_id, "a moved appointment is the same watch"
    history = conn.execute(
        "SELECT deadline_history FROM expectations WHERE tenant = ? AND expectation_id = ?",
        (NORTHLINE, final[0].origins[0].split(":", 1)[1])).fetchone()[0]
    assert json.loads(history) == ["2026-06-22T19:00:00.000Z", "2026-06-22T15:00:00.000Z"]


def test_a_bare_delivered_answers_the_arrival_it_implies(tmp_path):
    """The system of record says DELIVERED and names no stop. On a load with one pickup and one
    delivery that answers both arrivals: a delivered load does not go on asking where the truck is.
    Before this was fixed, every such load kept a carrier follow-up open forever."""
    h = HistoryBuilder("WB", "delivered, with no stop named", NORTHLINE, day="2026-08-10",
                       zone="America/Chicago", hostile=("tms_delivered_names_no_stop",))
    load = "LD-49095"
    stops = _stops(h, pickup="Prairie Ag Decatur", delivery="Three Rivers Co-op",
                   pickup_status="CONFIRMED", delivery_status="CONFIRMED")
    _cover(h, NORTHLINE_OPS, NORTHLINE_PODS, "tracking:macropoint")
    customer, carrier = _covered(h, load=load, customer="prairie_ag", carrier="ironwood",
                                 po="PO-2395", bol="BOL-56095", pro="PRO-60095", sell=188000,
                                 stops=stops, at=("07:30", "08:10"))
    _delivered(h, "delivered", h.t("15:00"), load=load, customer=customer, carrier=carrier,
               po="PO-2395", bol="BOL-56095", pro="PRO-60095", sell=188000, stops=stops)
    h.document("pod", h.t("15:20"), "POD", f"PROOF OF DELIVERY | load {load}",
               refs=(load_ref(load),), via=NORTHLINE_PODS, signed=True)
    h.clock("two-days-later", h.t("12:00", 2))
    store = _store(tmp_path)
    result = run_work_histories(store.conn, WORK_SETUPS, [h.build({})])
    state = result.state(NORTHLINE, load)
    assert state.routine_work_is_zero and state.billing_ready, [n.kind for n in state.needs]
    arrivals = store.conn.execute(
        "SELECT expected_type, state FROM expectations WHERE tenant = ? "
        "AND expected_type LIKE 'arrival:%' ORDER BY expected_type", (NORTHLINE,)).fetchall()
    assert [(r["expected_type"], r["state"]) for r in arrivals] == [
        ("arrival:S1", "DISCHARGED"), ("arrival:S2", "DISCHARGED")]
    store.close()


# ============================================================ conflicts

def test_an_unresolved_conflict_is_human_attention_and_resolving_it_keeps_history(run):
    """Two systems state two delivery windows: a human's, with every party's statement on it. When
    she decides, the need is gone — and the Conflict, its parties and her decision are all still
    there. A statement made AFTER she decided is a new dispute, never a silent overwrite."""
    result, conn = run
    disputed = result.at("W06", "portal-says-morning", "LD-49006")
    need = disputed.need(NeedKind.EVIDENCE_CONFLICT)
    assert need.human_required and disputed.posture is Posture.HUMAN_ATTENTION
    assert need.owner_id == "dana.ortiz" and ShadowAction.WAIT not in need.actions
    stated = [e.note for e in need.evidence if e.kind == "observation"]
    assert len(stated) == 2 and any("T13:00" in s for s in stated) \
        and any("T09:00" in s for s in stated)

    decided = result.at("W06", "dana-decides", "LD-49006")
    assert decided.need(NeedKind.EVIDENCE_CONFLICT) is None and not decided.human_attention
    rows = conn.execute(
        "SELECT conflict_id, state, decision_human_id, decision_ref FROM conflicts "
        "WHERE tenant = ? AND field = 'window' ORDER BY created_at", (NORTHLINE,)).fetchall()
    assert [r["state"] for r in rows] == ["RESOLVED_BY_HUMAN", "RESOLVED_BY_HUMAN"]
    assert {r["decision_human_id"] for r in rows} == {"dana.ortiz"}
    assert all(str(r["decision_ref"]).startswith("observation:") for r in rows)
    assert rows[0]["conflict_id"] != rows[1]["conflict_id"], "the second dispute reused the first"
    parties = conn.execute(
        "SELECT COUNT(*) FROM conflict_parties WHERE tenant = ? AND conflict_id = ?",
        (NORTHLINE, rows[0]["conflict_id"])).fetchone()[0]
    assert parties == 2, "resolving a conflict lost a party's statement"

    again = result.at("W06", "receiver-pushed", "LD-49006").need(NeedKind.EVIDENCE_CONFLICT)
    assert again is not None and again.need_id != need.need_id
    view = _view(result, NORTHLINE, "LD-49006")
    window = view.appointments["S2"].field_of("window")
    assert window.condition == "consistent" and window.current.provenance_class == "OWNER_ASSERTED"
    assert window.value["start_local"].endswith("T14:00"), "the owner's last word did not stand"
    assert len(window.facts) == 6, "a superseded statement was deleted"
    assert len({f.source_system for f in window.facts}) == 4, "TMS, portal, carrier and console"


# ============================================================ documents

def test_delivered_without_a_pod_is_work_and_a_usable_pod_closes_it(run):
    result, _ = run
    open_ = result.at("W07", "delivered", "LD-49007")
    need = open_.need(NeedKind.DOCUMENT_REQUIRED)
    assert need.handling is Handling.NEYMA_ACTION_CANDIDATE and not need.human_required
    assert need.actions == (ShadowAction.REQUEST_POD,) and not open_.billing_ready
    assert need.due_by == "2026-06-26T20:00:00.000Z", "the brokerage's own 24 hours"
    # An unsigned POD is not a POD: the need survives it, and the load is still not billable.
    unsigned = result.at("W07", "pod-unsigned", "LD-49007")
    assert unsigned.need(NeedKind.DOCUMENT_REQUIRED) is not None and not unsigned.billing_ready
    closed = result.at("W07", "pod-signed", "LD-49007")
    assert closed.routine_work_is_zero and closed.billing_ready
    assert [s.how for s in closed.settled if s.kind is NeedKind.DOCUMENT_REQUIRED] == ["SATISFIED"]
    life = [x for x in result.life(NORTHLINE, NeedKind.DOCUMENT_REQUIRED)
            if x.load_id == closed.load_id]
    assert len(life) == 1 and life[0].closed_how == "SATISFIED" and life[0].reopened == 0


# ============================================================ P9-D23

def _unplaced(result, history_id: str, label: str, load: str):
    state = result.at(history_id, label, load)
    return state, state.need(NeedKind.INVOICE_UNATTRIBUTED)


@pytest.mark.parametrize("history_id,label,load,problem", [
    ("W01", "invoice-no-mc", "LD-49001", "CARRIER_NOT_STATED"),
    ("W10", "invoice-other-spelling", "LD-49010", "CARRIER_UNRECOGNIZED"),
    ("W11", "invoice", "LD-49011", "CARRIER_NOT_ON_LOAD"),
    ("W12", "invoice", "LD-49012", "CARRIER_AMBIGUOUS"),
])
def test_an_invoice_no_movement_claims_is_an_owned_human_need_and_never_reconciled(
        run, history_id, label, load, problem):
    """P9-D23. An invoice bound to a load that cannot be placed on a carrier movement — no MC, an MC
    spelled another way, a carrier not on the load, a carrier with two movements — is HELD, is
    reconciled against nothing, makes nothing payable, guesses no carrier, and is a named human's
    with everything needed to place it."""
    result, conn = run
    state, need = _unplaced(result, history_id, label, load)
    assert need is not None, "the invoice is invisible"
    assert need.human_required and need.handling is Handling.HUMAN_REQUIRED
    assert need.reason_codes == (problem,) and need.owner_id == "dana.ortiz"
    assert need.actions == (ShadowAction.ASK_HUMAN_RESOLVE_IDENTITY,)
    assert state.posture is Posture.HUMAN_ATTENTION and not state.routine_work_is_zero
    # It explains itself: the document, what is missing, the evidence, and what would clear it.
    assert "Carrier invoice" in need.why and "Clears when" in need.why
    assert "Attribute it" in need.question
    kinds = {e.kind for e in need.evidence}
    assert {"observation", "document", "carrier_movement"} <= kinds
    assert "RECONCILED" not in state.reconciliation

    step = next(s for s in result.steps if s.history_id == history_id and s.label == label)
    exception = conn.execute(
        "SELECT state, owner_id, summary, specific_question, entity_ref FROM exceptions "
        "WHERE tenant = ? AND type = 'carrier_invoice_unattributed' AND entity_ref = ?",
        (NORTHLINE, f"brokerage_load:{state.load_id}")).fetchall()
    assert len(exception) == 1, "exactly one owned Exception per unplaced invoice"
    assert exception[0]["owner_id"] == "dana.ortiz" and step.disposition == "BOUND"
    summary = exception[0]["summary"]
    assert "has not been reconciled and nothing is payable" in summary
    assert not any(ch.isdigit() and token.replace(",", "").replace(".", "").isdigit()
                   and len(token) > 5 for token in summary.split() for ch in token[:1]), summary
    effects = result.intakes[NORTHLINE].foundation.effect_surface_counts()
    assert sum(effects.values()) == 0, "an unplaced invoice produced payment authority"


def test_an_unplaced_invoice_is_held_and_is_compared_against_nothing(tmp_path):
    """The invoice the independent review used: overbilled by ten thousand dollars against a signed
    rate confirmation, with no MC. Before the fix it produced no Exception and no attention."""
    store = _store(tmp_path)
    history = _history("W01")
    labels = [r.label for r in history.records]
    intake = FreightIntake(store.conn, WORK_SETUPS[NORTHLINE])
    for record in history.records[: labels.index("invoice-no-mc") + 1]:
        intake.ingest(record)
    view = intake.projection().view_by_load_ref("LD-49001")
    payable = next(iter(view.payables.values()))
    assert payable.movement_id is None and payable.attribution_basis is None
    assert payable.attribution_problem == "CARRIER_NOT_STATED"
    assert payable.lifecycle_state == "HELD", "an unplaced invoice is not merely 'received'"
    assert len(view.movements) == 1, "one movement on the load, and it was still not assumed"
    assert all(r.payable_id is None for r in view.reconciliations)
    assert [r.status for r in view.reconciliations] == ["COMPUTED"]
    assert any(a.startswith("invoice_unattributed:") for a in view.attention)
    assert [x["type"] for x in view.open_exceptions()] == ["carrier_invoice_unattributed"]
    store.close()


def test_placing_the_invoice_clears_the_stall_and_keeps_the_history(run):
    """A human places it (W01, W10, W12) or the system of record is corrected (W11). The need is
    gone, how it ended is on the record, the right NEW work appears if the placed invoice does not
    match — and the M9 Exception, which only a human's recorded decision may close, is retained as
    housekeeping rather than left as a task or deleted."""
    result, conn = run
    by_human = result.at("W01", "attributed", "LD-49001")
    assert by_human.need(NeedKind.INVOICE_UNATTRIBUTED) is None
    assert [(s.kind, s.how) for s in by_human.settled
            if s.kind is NeedKind.INVOICE_UNATTRIBUTED] == [
        (NeedKind.INVOICE_UNATTRIBUTED, "RESOLVED")]
    # Placed, it is finally compared — and it is ten thousand dollars over. Not quiet.
    discrepancy = by_human.need(NeedKind.INVOICE_DISCREPANCY)
    assert discrepancy is not None and discrepancy.human_required
    assert by_human.reconciliation == ("DISCREPANT",)
    view = _view(result, NORTHLINE, "LD-49001")
    payable = next(iter(view.payables.values()))
    assert payable.attribution_basis == "HUMAN_ASSERTION" and payable.attributed_by == "marcus.reid"
    assert payable.lifecycle_state == "HELD", "a human placing an invoice does not approve it"

    by_record = result.at("W11", "carrier-corrected", "LD-49011")
    assert by_record.routine_work_is_zero and by_record.reconciliation == ("RECONCILED",)
    assert [s.how for s in by_record.settled
            if s.kind is NeedKind.INVOICE_UNATTRIBUTED] == ["SATISFIED"]
    corrected = next(iter(_view(result, NORTHLINE, "LD-49011").payables.values()))
    assert corrected.attribution_basis == "CARRIER_MC_EXACT" and corrected.attributed_by is None

    for history_id, label, load in (("W01", "attributed", "LD-49001"),
                                    ("W10", "attributed", "LD-49010"),
                                    ("W11", "carrier-corrected", "LD-49011"),
                                    ("W12", "attributed", "LD-49012")):
        state = result.at(history_id, label, load)
        assert not [n for n in state.human_attention
                    if n.kind is NeedKind.INVOICE_UNATTRIBUTED], "a stale human task was left"
        assert len([h for h in state.housekeeping
                    if "carrier_invoice_unattributed" in h]) == 1
        life = [x for x in result.life(NORTHLINE, NeedKind.INVOICE_UNATTRIBUTED)
                if x.load_id == state.load_id]
        assert len(life) == 1 and life[0].closed_how in ("RESOLVED", "SATISFIED")
    rows = conn.execute("SELECT COUNT(*) FROM exceptions WHERE tenant = ? "
                        "AND type = 'carrier_invoice_unattributed'", (NORTHLINE,)).fetchone()[0]
    assert rows == 4, "history was deleted to make the need go away"


def test_an_mc_is_looked_up_never_tidied_and_never_looked_up_next_door(run):
    """ "MC 771203" is not "MC-771203": Neyma does not decide two spellings are one carrier. And an
    MC resolves only through THIS brokerage's own mapping."""
    result, conn = run
    # At the moment the invoice arrives, BEFORE any human acts: it fits no carrier Neyma knows.
    arrived = result.at("W10", "invoice-other-spelling", "LD-49010")
    unplaced = arrived.need(NeedKind.INVOICE_UNATTRIBUTED)
    assert unplaced is not None, "the spelling was normalized and the invoice placed itself"
    assert unplaced.reason_codes == ("CARRIER_UNRECOGNIZED",)
    assert any("'MC 771203'" in e.note for e in unplaced.evidence)
    assert any("MC-771203" in e.note for e in unplaced.evidence), "the candidate is shown too"
    assert "RECONCILED" not in arrived.reconciliation
    view = _view(result, NORTHLINE, "LD-49010")
    payable = next(iter(view.payables.values()))
    assert payable.stated_carrier_mc == "MC 771203"
    assert payable.attribution_basis == "HUMAN_ASSERTION", "the spelling was normalized"
    known = conn.execute(
        "SELECT COUNT(DISTINCT tenant) FROM external_entity_mappings "
        "WHERE external_system = 'fmcsa' AND external_id = 'MC-771203'").fetchone()[0]
    assert known == 2, "the trap needs the same carrier under both brokerages"
    assert conn.execute("SELECT COUNT(*) FROM external_entity_mappings "
                        "WHERE external_id = 'MC 771203'").fetchone()[0] == 0


def test_the_same_invoice_at_another_brokerage_cannot_be_reached(run):
    """Cedar Ridge and Northline each hold load LD-49050 — same PO, BOL, carrier, invoice number and
    message id. Cedar Ridge's invoice is unplaced; Northline's reconciles. A Northline human then
    tries to place "the" invoice by the id Cedar Ridge's carries. It reaches nothing of Cedar's."""
    result, conn = run
    cedar, north = result.state(CEDAR, "LD-49050"), result.state(NORTHLINE, "LD-49050")
    assert cedar.load_id != north.load_id
    need = cedar.need(NeedKind.INVOICE_UNATTRIBUTED)
    assert need is not None and need.tenant_id == CEDAR and need.owner_id == "sam.okafor"
    assert north.need(NeedKind.INVOICE_UNATTRIBUTED) is None
    assert north.reconciliation == ("RECONCILED",)
    cedar_payable = next(iter(_view(result, CEDAR, "LD-49050").payables.values()))
    assert cedar_payable.movement_id is None, "another brokerage's act placed this invoice"
    refused = north.need(NeedKind.IDENTITY_UNRESOLVED)
    assert refused is not None and refused.reason_codes == ("HUMAN_ACT_NAMES_NOTHING",)
    # The tenant is in the identity: the same cause at two brokerages is two needs.
    north_ids = {n.need_id for s in result.final.values() if s.tenant_id == NORTHLINE
                 for n in s.needs}
    cedar_ids = {n.need_id for s in result.final.values() if s.tenant_id == CEDAR
                 for n in s.needs}
    assert cedar_ids and north_ids and cedar_ids.isdisjoint(north_ids)
    assert need_id(CEDAR, NeedKind.INVOICE_UNATTRIBUTED, "x") != need_id(
        NORTHLINE, NeedKind.INVOICE_UNATTRIBUTED, "x")
    with pytest.raises(ValueError):
        need_id("", NeedKind.INVOICE_UNATTRIBUTED, "x")
    for state in result.final.values():
        assert all(n.tenant_id == state.tenant_id for n in state.needs)
    assert cross_tenant_violations(conn) == []
    with pytest.raises(ValueError):
        evaluate_load_work(_view(result, CEDAR, "LD-49050"), setup=WORK_SETUPS[NORTHLINE],
                           as_of="2026-07-21T00:00:00.000Z")


# ============================================================ money

def test_an_invoice_discrepancy_is_never_silently_good(run):
    """A billed line that differs from the rate confirmation is a human's: one need, with the
    Conflict M7 raised for it folded in — never auto-approved, never auto-disputed, never quiet."""
    result, _ = run
    state = result.at("W08", "invoice", "LD-49008")
    need = state.need(NeedKind.INVOICE_DISCREPANCY)
    assert need.human_required and "LINEHAUL_MISMATCH" in need.reason_codes
    assert state.reconciliation == ("DISCREPANT",) and not state.routine_work_is_zero
    assert sorted({o.split(":", 1)[0] for o in need.origins}) == ["conflict", "reconciliation"]
    assert not [n for n in state.needs if n.kind is NeedKind.EVIDENCE_CONFLICT], \
        "the same disagreement was shown twice"
    document = json.dumps(state.as_document())
    assert "2050" not in document and "2,050" not in document, "an amount leaked into the work"
    final = result.state(NORTHLINE, "LD-49008")
    assert final.need(NeedKind.INVOICE_DISCREPANCY) is not None, "it went quiet by itself"


def test_a_claimed_approval_is_not_an_authorization(run):
    """ "Detention is included per approval from Mike." The charge is exactly as unauthorized as it
    was, the claim is recorded as a reason to look harder, and only a recorded human's decision
    ends it — here, a denial, after which the billed charge is a discrepancy."""
    result, _ = run
    before = result.at("W08", "invoice", "LD-49008").need(NeedKind.ACCESSORIAL_UNAUTHORIZED)
    after = result.at("W08", "mike-approved", "LD-49008").need(NeedKind.ACCESSORIAL_UNAUTHORIZED)
    assert after is not None and after.human_required and after.need_id == before.need_id
    assert "COUNTERPARTY_CLAIMS_APPROVAL" in after.reason_codes
    assert after.actions == (ShadowAction.ASK_HUMAN_DECIDE_ACCESSORIAL,)
    view = _view(result, NORTHLINE, "LD-49008")
    assert view.authorizations == [] and view.accessorials["DETENTION"].lifecycle_state == "DENIED"
    denied = result.at("W08", "marcus-denies", "LD-49008")
    assert denied.need(NeedKind.ACCESSORIAL_UNAUTHORIZED) is None
    assert "ACCESSORIAL_DENIED_BUT_BILLED:DETENTION" in denied.need(
        NeedKind.INVOICE_DISCREPANCY).reason_codes
    # The other way out: a named human authorizes it, and a matching invoice is then quiet.
    authorized = result.state(NORTHLINE, "LD-49009")
    assert authorized.routine_work_is_zero and authorized.reconciliation == ("RECONCILED",)
    assert len(_view(result, NORTHLINE, "LD-49009").authorizations) == 1


# ============================================================ the twenty hostile histories

@pytest.fixture(scope="module")
def hostile(tmp_path_factory):
    """The twenty hostile histories of P9-CP-1, through the work engine, with their own setups."""
    store = _store(tmp_path_factory.mktemp("p9-work-hostile"))
    result = run_work_histories(store.conn, SETUPS, build_corpus())
    yield result, store.conn
    store.close()


def test_the_twenty_hostile_histories_end_in_the_work_they_should(hostile):
    """What each hostile load needs at the end, read by the work engine rather than labeled for it."""
    result, conn = hostile
    assert len(result.histories) == 20 and len(result.final) == 23

    def kinds(tenant: str, load: str) -> set[str]:
        return {n.kind.value for n in result.state(tenant, load).needs}

    assert result.state(NORTHLINE, "LD-48233").routine_work_is_zero, "N02 runs clean"
    assert result.state(NORTHLINE, "LD-48233").billing_ready
    assert kinds(NORTHLINE, "LD-48260") == {"DOCUMENT_REQUIRED"}, "N03 delivered, POD never came"
    assert not result.state(NORTHLINE, "LD-48260").billing_ready
    assert "EVIDENCE_CONFLICT" in kinds(NORTHLINE, "LD-48305"), "N05 two delivery appointments"
    assert kinds(NORTHLINE, "LD-48219") == {"ACCESSORIAL_UNAUTHORIZED"}, "N01 detention"
    assert "INVOICE_DISCREPANCY" in kinds(NORTHLINE, "LD-48340"), "N06 invoice vs rate con"
    harbor = next(s for s in result.final.values() if s.tenant_id == HARBOR)
    assert {"BILLING_REQUIREMENTS_UNKNOWN", "RECONCILIATION_BLOCKED"} <= {
        n.kind.value for n in harbor.needs}, "H01 nothing configured, rate con unsigned"
    assert not harbor.billing_ready
    disputed = [s for s in result.final.values() if s.stage.value == "DISPUTED"]
    assert disputed, "N13: sources contradict each other about where the freight is"
    # A held record offered to two loads is ONE need, shown on both.
    held = [n for s in result.final.values() for n in s.needs
            if n.kind is NeedKind.IDENTITY_UNRESOLVED and "AMBIGUOUS_BINDING" in n.reason_codes]
    shown_on: dict[str, set[str]] = {}
    for need in held:
        shown_on.setdefault(need.need_id, set()).add(need.load_id)
    assert len(held) >= 3 and all(n.human_required for n in held)
    assert len(shown_on) < len(held), "a record offered to two loads became two needs"
    assert sorted(len(loads) for loads in shown_on.values())[-1] == 2
    for need in held:
        confirmed = conn.execute(
            "SELECT COUNT(*) FROM identity_binding_claims WHERE state = 'CONFIRMED' "
            "AND subject_ref = ?", (need.origins[0].split(":", 1)[1],)).fetchone()[0]
        assert confirmed == 0, "an ambiguous record was bound"
    # N16: a POD bound by its own number to the WRONG load, then moved by a human. While it sat
    # there the wrong load looked satisfied; once moved, the wrong load owes its POD again and the
    # right one is quiet — and the move is on the record as a superseded binding.
    wrong_before = result.at("N16", "pod", "LD-48720")
    assert wrong_before.need(NeedKind.DOCUMENT_REQUIRED) is None
    assert result.at("N16", "pod", "LD-48721").need(NeedKind.DOCUMENT_REQUIRED) is not None
    wrong, right = result.state(NORTHLINE, "LD-48720"), result.state(NORTHLINE, "LD-48721")
    assert kinds(NORTHLINE, "LD-48720") == {"DOCUMENT_REQUIRED"} and not wrong.billing_ready
    assert right.routine_work_is_zero and right.billing_ready
    assert [s.how for s in wrong.settled if s.kind is NeedKind.IDENTITY_UNRESOLVED] == [
        "SUPERSEDED"]
    # Nothing a load's own view cannot show is lost: the inbox has its own list.
    unplaced = [n for tenant, intake in result.intakes.items() for n in evaluate_unplaced_work(
        intake.projection(), setup=intake.setup, exceptions=intake.foundation.exceptions(),
        as_of=intake.foundation.now())]
    assert len(unplaced) >= 4 and all(n.human_required and n.owner_id for n in unplaced)
    assert result.report["metrics"]["unplaced_work_needing_a_human"] == len(unplaced)
    for state in result.final.values():
        view = result.intakes[state.tenant_id].projection().loads[state.load_id]
        assert audit_state(state, view, tenant=state.tenant_id) == []
    assert result.report["metrics"]["external_effect_rows"] == 0


def test_a_quoted_promise_opens_no_second_wait(hostile):
    """N02: the customer forwards the carrier's promise. It is quoted, and it is not new work."""
    result, _ = hostile
    forwarded = result.at("N02", "customer-forward", "LD-48233")
    promises = [n for n in forwarded.needs if n.kind in (NeedKind.CARRIER_UPDATE_PENDING,
                                                         NeedKind.CARRIER_STATUS_OVERDUE)]
    assert promises == []
    assert [x.kind for x in result.life(NORTHLINE, NeedKind.CARRIER_UPDATE_PENDING)
            if x.load_id == forwarded.load_id] == ["CARRIER_UPDATE_PENDING"]


# ============================================================ a model's reading, and its failure

def test_a_model_proposed_candidate_is_a_humans_need_and_never_a_binding(tmp_path):
    """R04: three messages nothing exact can place. A model PROPOSES loads; the work engine shows
    one human need per held record, marked as model-proposed, and nothing is bound."""
    store = _store(tmp_path)
    ledger = InferenceLedger()
    gateway = ScriptedGateway(raw_history_responder(), ledger=ledger)
    histories = [h for h in build_raw_histories() if h.history_id == "R04"]
    result = run_work_histories(store.conn, SETUPS, histories,
                                interpreter=FreightInterpreter(gateway, ledger))
    proposed = [n for s in result.final.values() for n in s.needs
                if "MODEL_PROPOSED_CANDIDATES" in n.reason_codes]
    assert proposed, "R04 produced no model-proposed candidate"
    assert all(n.human_required and n.kind is NeedKind.IDENTITY_UNRESOLVED for n in proposed)
    assert all(n.actions == (ShadowAction.ASK_HUMAN_RESOLVE_IDENTITY,) for n in proposed)
    for need in proposed:
        claims = store.conn.execute(
            "SELECT state, match_method FROM identity_binding_claims WHERE subject_ref = ?",
            (need.origins[0].split(":", 1)[1],)).fetchall()
        assert claims and {c["state"] for c in claims} == {"AMBIGUOUS"}
        assert {c["match_method"] for c in claims} == {"MODEL_INFER"}
    store.close()


def test_a_reading_that_fails_leaves_a_human_need_and_the_rest_of_the_work_intact(tmp_path):
    """The provider fails on an invoice's text. The invoice is still observed and bound; nothing is
    extracted or assumed; a named human is asked to read it; and the POD the load is also missing
    is still the same deterministic candidate it would have been."""
    h = HistoryBuilder("WX", "an invoice nobody could read", NORTHLINE, day="2026-08-03",
                       zone="America/Chicago", hostile=("model_interpretation_failure",))
    load = "LD-49090"
    stops = _stops(h, pickup="Prairie Ag Decatur", delivery="Three Rivers Co-op")
    _cover(h, NORTHLINE_OPS, NORTHLINE_PODS)
    customer, carrier = _covered(h, load=load, customer="prairie_ag", carrier="ironwood",
                                 po="PO-2390", bol="BOL-56090", pro="PRO-60090", sell=188000,
                                 stops=stops, at=("07:30", "08:10"))
    _delivered(h, "delivered", h.t("15:00"), load=load, customer=customer, carrier=carrier,
               po="PO-2390", bol="BOL-56090", pro="PRO-60090", sell=188000, stops=stops)
    h.raw_document("invoice", h.t("16:00"), "CARRIER_INVOICE",
                   "CARRIER INVOICE\nInvoice number: IW-9090\nLine haul: $1,500.00\n",
                   refs=(load_ref(load),), via=NORTHLINE_OPS)
    store = _store(tmp_path)
    ledger = InferenceLedger()
    gateway = ScriptedGateway(lambda task, request: ProviderRejection("refusal_or_empty_output"),
                              ledger=ledger)
    result = run_work_histories(store.conn, WORK_SETUPS, [h.build({})],
                                interpreter=FreightInterpreter(gateway, ledger))
    state = result.state(NORTHLINE, load)
    reading = state.need(NeedKind.DOCUMENT_NEEDS_READING)
    assert reading is not None and reading.human_required and reading.owner_id == "priya.nair"
    assert reading.actions == (ShadowAction.ASK_HUMAN_REVIEW_DOCUMENT,)
    assert "could not be read" in reading.why
    pod = state.need(NeedKind.DOCUMENT_REQUIRED)
    assert pod is not None and pod.handling is Handling.NEYMA_ACTION_CANDIDATE
    view = _view(result, NORTHLINE, load)
    assert view.payables == {} and view.reconciliations == [], "a failed reading invented a payable"
    assert len(gateway.invocations_of(Task.INTERPRET_DOCUMENT_TEXT)) == 1
    store.close()


def _raw_factory(responder):
    ledger = InferenceLedger()
    gateway = ScriptedGateway(responder, ledger=ledger)
    interpreter = FreightInterpreter(gateway, ledger)
    return lambda conn, setup: FreightIntake(conn, setup, interpreter=interpreter)


def test_the_nine_raw_language_histories_pass_the_oracle_at_every_step(tmp_path):
    """Freight said the way people say it, read by a (scripted) model, audited after every record
    by the same oracle the hostile layer uses. This is where the orphaned POD Expectation was
    found: R03's delivery report was moved to the right load and the wrong one kept owing a POD."""
    store = _store(tmp_path)
    histories = build_raw_histories()
    result = run_mutant(store.conn, Mutant("raw-nine", "base", "R", tuple(histories)),
                        setups=SETUPS, intake_factory=_raw_factory(raw_history_responder()))
    assert len(histories) == 9 and result.steps == sum(len(h.records) for h in histories)
    assert result.steps > 50 and result.evaluations > 100, (result.steps, result.evaluations)
    assert result.findings == [], result.findings[:5]
    store.close()


def test_a_wrong_load_number_is_a_humans_question_and_moving_the_record_moves_the_work(tmp_path):
    """R03: "that was the wrong load number — this is for 51004." A counterparty's claim re-binds
    nothing; a named human is asked. When she moves the delivery report, the POD is owed on the
    load it now belongs to and NOT on the load it left — whose Expectation is cancelled, retained,
    rather than left to go overdue on a load nobody says was delivered. Her question stays open:
    nothing here decides it was answered."""
    store = _store(tmp_path)
    histories = [h for h in build_raw_histories() if h.history_id == "R03"]
    ledger = InferenceLedger()
    gateway = ScriptedGateway(raw_history_responder(), ledger=ledger)
    result = run_work_histories(store.conn, SETUPS, histories,
                                interpreter=FreightInterpreter(gateway, ledger))
    claimed = result.at("R03", "carrier-correction", "LD-51003")
    question = claimed.need(NeedKind.IDENTITY_UNRESOLVED)
    assert question.human_required and question.owner_id == "priya.nair"
    assert question.reason_codes == ("REFERENCE_CORRECTION_CLAIMED",)
    assert claimed.need(NeedKind.DOCUMENT_REQUIRED) is not None, "still (wrongly) owed here"
    assert result.at("R03", "carrier-correction", "LD-51004").need(
        NeedKind.DOCUMENT_REQUIRED) is None

    left, joined = result.state(NORTHLINE, "LD-51003"), result.state(NORTHLINE, "LD-51004")
    assert left.need(NeedKind.DOCUMENT_REQUIRED) is None and left.stage.value == "DISPATCHED"
    assert joined.need(NeedKind.DOCUMENT_REQUIRED) is not None and joined.stage.value == "DELIVERED"
    assert not [n for n in left.needs if n.kind is NeedKind.UNCLASSIFIED_EXCEPTION]
    assert {(s.kind, s.how) for s in left.settled} >= {
        (NeedKind.DOCUMENT_REQUIRED, "SUPERSEDED"), (NeedKind.IDENTITY_UNRESOLVED, "SUPERSEDED")}
    rows = store.conn.execute(
        "SELECT subject_ref, state FROM expectations WHERE tenant = ? "
        "AND expected_type = 'document:POD' ORDER BY created_at", (NORTHLINE,)).fetchall()
    assert [r["state"] for r in rows] == ["CANCELLED", "RAISED"], "history was not retained"
    assert rows[0]["subject_ref"] == f"brokerage_load:{left.load_id}"
    # The human's question is not closed for her: M9 has no closure this spine can perform.
    assert left.need(NeedKind.IDENTITY_UNRESOLVED) is not None
    store.close()


def test_an_expectation_that_outlives_its_cause_is_never_dropped(tmp_path):
    """The one case M8 cannot cancel: the POD deadline passed while the channel was BLIND
    (INDETERMINATE), and then the delivery report was moved off the load. The Expectation is still
    owed in M8 with nothing left to explain it. It is not a request Neyma could make and it is not
    dropped: a named human is shown it."""
    h = HistoryBuilder("WO", "a POD owed on a load nobody says was delivered", NORTHLINE,
                       day="2026-08-17", zone="America/Chicago",
                       hostile=("expectation_outlives_its_cause", "blind_is_not_late"))
    refs_a, refs_b = (load_ref("LD-49097"),), (load_ref("LD-49098"),)
    _cover(h, NORTHLINE_OPS, NORTHLINE_SMS)
    _cover(h, NORTHLINE_PODS, health="DOWN", minute=5)
    for index, load in enumerate(("LD-49097", "LD-49098")):
        stops = _stops(h, pickup="Prairie Ag Peoria", delivery=f"River Bend Co-op {index}")
        h.tms(f"covered-{load}", h.t(f"07:1{index}"), load=load, status="COVERED", version=1,
              customer=CUSTOMERS["prairie_ag"], po=f"PO-239{7 + index}",
              bol=f"BOL-5609{7 + index}", sell=charges(133000), stops=stops,
              movements=(movement("M1", CARRIERS["summit"], pro=f"PRO-6009{7 + index}"),))
    h.message("delivered-wrong-thread", h.t("10:00"), channel="email",
              source_system=NORTHLINE_OPS, sender=dispatcher("summit"), thread="re-49097",
              subject="RE: LD-49097", body="delivered, empty", refs=refs_a,
              asserts=(says("DELIVERED", "S2"),), external_id="<wo-delivered>")
    h.clock("a-day-passes", h.t("10:05", 1))
    h.human("moved", h.t("11:00", 1), "priya.nair", "correct_binding", refs=refs_b,
            target={"source_system": NORTHLINE_OPS, "external_id": "<wo-delivered>"},
            note="that report was for 49098")
    store = _store(tmp_path)
    result = run_work_histories(store.conn, WORK_SETUPS, [h.build({})])
    blind = result.at("WO", "a-day-passes", "LD-49097").need(NeedKind.DOCUMENT_REQUIRED)
    assert blind.status is NeedStatus.UNVERIFIED and "DOCUMENT_CHANNEL_BLIND" in blind.reason_codes
    left = result.state(NORTHLINE, "LD-49097")
    assert left.need(NeedKind.DOCUMENT_REQUIRED) is None, "a POD is requested on an undelivered load"
    orphan = left.need(NeedKind.UNCLASSIFIED_EXCEPTION)
    assert orphan is not None, "an owed Expectation was dropped"
    assert orphan.human_required and orphan.actions == ()
    assert orphan.reason_codes == ("EXPECTATION_OUTLIVED_ITS_CAUSE:document:POD",)
    assert sorted(o.split(":", 1)[0] for o in orphan.origins) == ["exception", "expectation"]
    state = store.conn.execute(
        "SELECT state FROM expectations WHERE tenant = ? AND subject_ref = ? "
        "AND expected_type = 'document:POD'",
        (NORTHLINE, f"brokerage_load:{left.load_id}")).fetchone()["state"]
    assert state == "INDETERMINATE", "M8 has no exit from INDETERMINATE, and none was invented"
    assert left.housekeeping == (), "a live obligation was filed as housekeeping"
    view = result.intakes[NORTHLINE].projection().view_by_load_ref("LD-49097")
    assert audit_state(left, view, tenant=NORTHLINE) == []
    store.close()


# ============================================================ shadow reasoning

def _undecided(run):
    result, _ = run
    return result.at("W15", "get-back-to-you", "LD-49015")


def _reply(state, *, action: str, posture: str = "ACT", **changes):
    need = next(n for n in state.needs if n.handling is Handling.MODEL_REASONING)
    reply = {"posture": posture, "next_need_id": need.need_id, "groups": [],
             "advice": [{"need_id": need.need_id, "recommended_action": action,
                         "evidence_ids": [need.evidence[-1].evidence_id], "reason": "scripted"}],
             "explanation": "scripted"}
    reply.update(changes)
    return reply


def _advise(state, reply, **gateway_kwargs):
    ledger = InferenceLedger()
    gateway = ScriptedGateway(lambda task, request: reply, ledger=ledger, **gateway_kwargs)
    reasoner = LoadWorkReasoner(gateway, ledger)
    return reasoner.advise(state), gateway, reasoner


def test_the_model_is_asked_only_when_the_record_leaves_act_or_wait_open(run):
    """Every evaluation of every load is ROUTED. Across the whole corpus the model's seat is
    reached for one question — a POD owed while a promise of unsettled scope is pending — and for
    nothing the deterministic projection had already answered."""
    result, _ = run
    states = [s for step in result.steps for s in step.states.values()]
    assert len(states) > 1000
    routes = {}
    for state in states:
        route = route_load_work(state)
        routes[route.reason] = routes.get(route.reason, 0) + 1
        wanted = any(n.handling is Handling.MODEL_REASONING for n in state.needs)
        assert route.model_needed == wanted
    assert {"quiet", "only_waiting", "human_attention_only", "deterministic_work_is_sufficient",
            "act_or_wait_not_settled_by_the_record"} == set(routes), routes
    assert routes["act_or_wait_not_settled_by_the_record"] == 1

    calls: list[str] = []
    ledger = InferenceLedger()
    gateway = ScriptedGateway(
        lambda task, request: (calls.append(request.source_id),
                               oracle_reply(request, {}))[1], ledger=ledger)
    reasoner = LoadWorkReasoner(gateway, ledger)
    for state in states:
        reasoner.advise(state)
    summary = reasoner.summary(loads=15)
    assert len(calls) == 1 and summary["model_reasoning_calls"] == 1
    assert summary["model_calls_avoided"] == len(states) - 1
    assert summary["outcomes"] == {ADVISED: 1, NOT_NEEDED: len(states) - 1}
    # A promise recorded as being ABOUT the missing document settles it with no model at all.
    covered = result.at("W15", "pod-by-two", "LD-49015")
    need = covered.need(NeedKind.DOCUMENT_REQUIRED)
    assert need.handling is Handling.WAIT and "COVERED_BY_PENDING_PROMISE" in need.reason_codes
    assert not route_load_work(covered).model_needed
    # And the gateway itself refuses a call the route did not ask for.
    with pytest.raises(RoutingViolation):
        gateway.reason_load_work(build_request(covered, route_load_work(covered)))


def test_the_same_question_is_not_asked_twice(run):
    """Time passing, or another load's record arriving, does not re-ask. A changed need does."""
    state = _undecided(run)
    reply = _reply(state, action="REQUEST_POD")
    ledger = InferenceLedger()
    gateway = ScriptedGateway(lambda task, request: reply, ledger=ledger)
    reasoner = LoadWorkReasoner(gateway, ledger)
    first = reasoner.advise(state)
    later = replace(state, as_of="2026-07-23T15:50:00.000Z")
    assert question_digest(later) == question_digest(state)
    second = reasoner.advise(later)
    assert (first.status, second.status) == (ADVISED, REUSED) and second.picks == first.picks
    assert len(gateway.invocations) == 1
    assert [r.reason for r in ledger.routings] == ["question_unchanged"]
    changed = replace(state, needs=tuple(replace(n, reason_codes=(*n.reason_codes, "X"))
                                         for n in state.needs))
    assert reasoner.advise(changed).status == ADVISED and len(gateway.invocations) == 2


def test_the_model_may_only_select_what_it_was_supplied(run):
    """An invented need, an action outside the closed vocabulary, an action this need does not
    offer, and evidence it was never shown: each is refused, alone, and the rest of the reply
    stands. The request it was shown names only this load's own ids, and no money."""
    state = _undecided(run)
    need = next(n for n in state.needs if n.handling is Handling.MODEL_REASONING)
    other = next(n for n in state.needs if n is not need)
    request = build_request(state, route_load_work(state))
    rendered = render(Task.REASON_LOAD_WORK, request)
    assert {n.need_id for n in request.needs} == {n.need_id for n in state.needs}
    assert "REQUEST_POD, WAIT" in rendered and "USD" not in rendered and "$" not in rendered
    assert "I'll get back to you by 3." in rendered and "untrusted data" in rendered

    good, _, _ = _advise(state, _reply(state, action="WAIT", posture="WAIT", next_need_id=None))
    assert good.status == ADVISED and good.picks == {need.need_id: "WAIT"} and good.refused == ()
    assert good.posture == Posture.WAIT.value

    for label, reply, code in (
            ("an invented need", _reply(state, action="WAIT", advice=[
                {"need_id": "need-0000000000000000", "recommended_action": "WAIT",
                 "evidence_ids": [need.evidence[-1].evidence_id], "reason": "x"}]),
             "need_id_not_supplied"),
            ("an action outside the vocabulary", _reply(state, action="SEND_EMAIL_TO_CARRIER"),
             "action_not_offered_for_need"),
            ("an action another need offers", _reply(state, action="REQUEST_CARRIER_STATUS"),
             "action_not_offered_for_need"),
            ("an invented next need", _reply(state, action="REQUEST_POD",
                                             next_need_id="need-ffffffffffffffffffff"),
             "next_need_id_not_supplied"),
            ("a group naming a need it was not given", _reply(
                state, action="REQUEST_POD",
                groups=[{"need_ids": [need.need_id, "need-ffffffffffffffffffff"]}]),
             "group_names_a_need_not_supplied")):
        advice, _, _ = _advise(state, reply)
        assert code in advice.refused, (label, advice.refused)
        assert advice.status == ADVISED, label

    invented = _reply(state, action="REQUEST_POD")
    invented["advice"][0]["evidence_ids"] = ["ev-000000000000"]
    advice, _, _ = _advise(state, invented)
    assert "evidence_id_not_supplied" in advice.refused and advice.picks == {}
    # One bad part does not take the good part with it.
    mixed = _reply(state, action="REQUEST_POD")
    mixed["advice"].append({"need_id": "need-0000000000000000", "recommended_action": "WAIT",
                            "evidence_ids": [], "reason": "x"})
    advice, _, _ = _advise(state, mixed)
    assert advice.picks == {need.need_id: "REQUEST_POD"}
    assert advice.refused == ("need_id_not_supplied",)
    # A need the record already settled is not re-decided.
    settled = _reply(state, action="REQUEST_POD")
    settled["advice"].append({"need_id": other.need_id, "recommended_action": "WAIT",
                              "evidence_ids": [other.evidence[0].evidence_id], "reason": "x"})
    advice, _, _ = _advise(state, settled)
    assert other.need_id not in advice.picks


def test_the_model_cannot_suppress_a_need_a_human_must_decide(run):
    """W08: an invoice discrepancy and an unauthorized accessorial. A reply that says WAIT for
    both, and calls the posture WAIT, changes nothing: a human's need never offers WAIT, and the
    posture is recomputed from the work rather than taken from the reply."""
    result, _ = run
    state = result.at("W08", "mike-approved", "LD-49008")
    assert len(state.human_attention) == 2
    assert not route_load_work(state).model_needed, "a human-only load is not a model's question"
    request = build_request(state, replace(route_load_work(state), model_needed=True))
    assert all("WAIT" not in option.actions for option in request.needs)
    reply = LoadWorkReasoning.model_validate({
        "posture": "WAIT", "next_need_id": None, "groups": [],
        "advice": [{"need_id": n.need_id, "recommended_action": "WAIT",
                    "evidence_ids": [n.evidence[0].evidence_id], "reason": "it can wait"}
                   for n in state.needs], "explanation": "nothing to do"})
    from freight_recon.freight_domain.work_reasoning import screen_advice
    advice = screen_advice(reply, state, request)
    assert advice.picks == {} and advice.refused.count("action_not_offered_for_need") == 2
    assert "stated_posture_disagrees_with_the_work" in advice.refused
    assert advice.posture == Posture.HUMAN_ATTENTION.value and advice.stated_posture == "WAIT"
    assert len(state.human_attention) == 2 and all(n.human_required for n in state.needs)

    # The same on a load with BOTH an undecided need and a human's: the pick lands, the human stays.
    undecided = _undecided(run)
    human = replace(state.human_attention[0], load_id=undecided.load_id)
    both = replace(undecided, needs=(human, *undecided.needs))
    advice, _, _ = _advise(both, _reply(both, action="WAIT", posture="WAIT", next_need_id=None))
    assert advice.posture == Posture.HUMAN_ATTENTION.value
    assert "stated_posture_disagrees_with_the_work" in advice.refused
    assert list(advice.picks.values()) == ["WAIT"] and human.need_id not in advice.picks


def test_a_model_failure_leaves_the_deterministic_work_standing(run):
    """A timeout, a rejection, a reply that is not the contract, a spent budget: each yields FAILED
    advice and the SAME work — the undecided need still listing both of its answers."""
    state = _undecided(run)
    before = state.digest()
    for reply, kwargs, calls in (
            (TransportFailure("APITimeoutError"), {}, 2),
            (ProviderRejection("refusal_or_empty_output"), {}, 1),
            ({"posture": "MAYBE", "advice": "none"}, {}, 2),
            (_reply(state, action="WAIT"),
             {"budget": InferenceBudget(max_calls=0, max_input_tokens=1, max_output_tokens=1)},
             0)):
        advice, gateway, reasoner = _advise(state, reply, **kwargs)
        assert advice.status == FAILED and advice.picks == {} and advice.failure
        assert len(gateway.invocations) == calls
        assert advice.posture == Posture.NEYMA_CAN_ACT.value, "a failed call assumed a WAIT"
        assert reasoner.summary(loads=1)["outcomes"] == {FAILED: 1}
    assert state.digest() == before
    need = state.need(NeedKind.DOCUMENT_REQUIRED)
    assert need.actions == (ShadowAction.REQUEST_POD, ShadowAction.WAIT)


def test_only_the_work_reasoner_calls_the_load_work_task_and_its_prompt_cannot_drift():
    """One caller in production, and a recording of this task cannot outlive its prompt or its
    schema — the four reading tasks keep the version their committed recordings were made under."""
    assert callers_of("reason_load_work") == {REASONER}
    version = prompt_version_for(Task.REASON_LOAD_WORK)
    assert version.startswith("p9-load-work-1+") and len(version.split("+")[1]) == 12
    for task in Task:
        if task is not Task.REASON_LOAD_WORK:
            assert prompt_version_for(task) == PROMPT_VERSION
    vocabulary = {a.value for a in ShadowAction}
    assert len(vocabulary) == 10 and "WAIT" in vocabulary
    assert not vocabulary & {"SEND", "PAY", "APPROVE", "WRITE"}


def test_the_labeled_reasoning_cases_are_real_states_and_the_scorer_can_fail(tmp_path):
    """The live eval's cases are real projected states, each genuinely routed to a model, each
    labeled. With the oracle's answers every case scores; with a wrong one the scorer says so."""
    assert 10 <= len(REASONING_CASES) <= 15
    store = _store(tmp_path)
    states = case_states(store.conn)
    store.close()
    assert set(states) == {c.case_id for c in REASONING_CASES}
    assert len({question_digest(s) for s, _ in states.values()}) == len(REASONING_CASES)
    expectations = {"WAIT": 0, "ACT": 0, "HUMAN": 0}
    for case in REASONING_CASES:
        state, request = states[case.case_id]
        assert route_load_work(state).model_needed, f"{case.case_id} does not need a model"
        assert bool(state.human_attention) == case.human_need
        assert case.promise_text in render(Task.REASON_LOAD_WORK, request)
        reply = LoadWorkReasoning.model_validate(oracle_reply(request, case.picks))
        verdict = score_case(case, state, request, reply)
        assert verdict["ok"] and verdict["refused"] == [], (case.case_id, verdict)
        expectations[case.posture] += 1
        other = {kind: next(a.value for n in state.needs if n.kind.value == kind
                            for a in n.actions if a.value != action)
                 for kind, action in case.picks.items()}
        bad = LoadWorkReasoning.model_validate(oracle_reply(request, other))
        assert not score_case(case, state, request, bad)["ok"], f"{case.case_id} cannot fail"
    assert all(count >= 2 for count in expectations.values()), expectations


def test_the_control_states_are_settled_without_a_model(tmp_path):
    """Four situations the projection answers alone are in the eval to be counted as NOT sent."""
    store = _store(tmp_path)
    _, controls = build_states(store.conn)
    store.close()
    assert set(controls) == {case_id for case_id, _ in CONTROL_STATES}
    reasons = {case_id: route_load_work(state) for case_id, state in controls.items()}
    assert not any(route.model_needed for route in reasons.values())
    assert sorted(route.reason for route in reasons.values()) == [
        "deterministic_work_is_sufficient", "human_attention_only", "only_waiting", "quiet"] or \
        sorted(route.reason for route in reasons.values()) == [
        "human_attention_only", "only_waiting", "only_waiting", "quiet"]


LUNA_WORK_RECORDING = (ROOT / "eval" / "freight_corpus" / "recordings"
                       / "gpt-6-luna.effort-low.load-work.json")


def test_the_recorded_luna_reasoning_replays_offline_and_reproduces_the_measured_result():
    """The live load-work eval's result, pinned. What gpt-6-luna answered on 2026-10-03 is
    committed; replaying it — every socket call forbidden by this module — through TODAY's
    projection, routing and screening must reproduce what was reported.

    A REPLAY_MISS means the QUESTION changed since it was asked: the prompt, the output schema, a
    case, or the deterministic work the case projects to. That is not a flake. Re-measure:

        NEYMA_LIVE_INFERENCE=1 .venv/bin/python scripts/run_freight_interpretation_eval.py \\
            --live --stage load_work

    ### ONE RUN OF ONE MODEL ON THIRTEEN SYNTHETIC STATES. Not evidence about customers, and the
    recording is a development optimization: nothing consequential reads it."""
    from freight_corpus.interpretation_eval import run_stage
    from freight_recon.inference.gateway import ReplayGateway
    from freight_recon.inference.recording import RecordingStore

    assert LUNA_WORK_RECORDING.is_file(), f"{LUNA_WORK_RECORDING} is not committed"
    ledger = InferenceLedger()
    gateway = ReplayGateway(provider="openai", model="gpt-6-luna", reasoning_effort="low",
                            recording=RecordingStore(LUNA_WORK_RECORDING), ledger=ledger)
    work = run_stage("load_work", gateway, ledger)["load_work"]
    assert work["failed_calls"] == 0, (
        "the committed recording no longer answers the questions the code asks. Re-measure "
        "with the live eval and commit the new recording.")
    assert (work["cases"], work["cases_correct"]) == (13, 13)
    assert (work["wait_expected"], work["wait_correctly_selected"]) == (6, 6)
    assert (work["act_expected"], work["act_correctly_selected"]) == (7, 7)
    assert (work["human_cases"], work["human_required_preserved"]) == (2, 2)
    assert work["refused_parts"] == 0 and work["unknown_id_or_action_refusals"] == 0
    assert work["controls"] == 4 and work["unnecessary_model_calls"] == 0
    assert work["external_effect_rows"] == 0
    summary = ledger.summary()
    assert summary["served_from"] == {"replay": 13}
    assert set(summary["calls_by_task"]) == {"reason_load_work"}
    assert summary["routing"]["settled_deterministically"] == 4
    recorded = LUNA_WORK_RECORDING.read_text(encoding="utf-8")
    assert "USD" not in recorded and "$" not in recorded and "sk-" not in recorded


# ============================================================ the hostile mutation layer

@pytest.fixture(scope="module")
def attack(tmp_path_factory):
    """Every deterministic mutant, each on its own database, audited after every record."""
    directory = tmp_path_factory.mktemp("p9-work-attack")

    def one(mutant: Mutant, index: int):
        store = _store(directory, f"m{index}.db")
        try:
            return run_mutant(store.conn, mutant)
        finally:
            store.close()

    bases = {h.history_id: one(Mutant(f"{h.history_id}:base", "base", h.history_id, (h,)), i)
             for i, h in enumerate(build_work_histories()) if h.tenant == NORTHLINE}
    mutants = build_mutants()
    return bases, [(m, one(m, 100 + i)) for i, m in enumerate(mutants)]


def test_a_hundred_hostile_mutations_expose_no_stall_no_stale_work_and_no_leak(attack):
    """Records arriving twice, late, out of order or never; a repeated promise; a restart in the
    middle; the same load at another brokerage. After EVERY record of every mutant, an oracle that
    reads the canonical view itself finds no silent stall, no stale work, no false quiet, no false
    escalation, no duplicate, no wrong billing readiness and no tenant leak — and evaluating wrote
    nothing."""
    bases, results = attack
    assert len(results) >= 100, f"only {len(results)} mutants"
    operators = {m.operator for m, _ in results}
    assert operators == {"duplicate_arrival", "late_redelivery", "restart",
                         "same_load_at_another_brokerage", "repeated_promise", "never_arrives",
                         "reordered", "arrives_late"}
    assert sum(r.evaluations for _, r in results) > 1500
    findings = [f for _, r in results for f in r.findings] + [
        f for r in bases.values() for f in r.findings]
    assert findings == [], findings[:5]
    compared = 0
    for mutant, result in results:
        if mutant.same_final_work_as_base:
            compared += 1
            assert result.final == bases[mutant.base].final, mutant.mutant_id
    assert compared >= 50
    # The mutants are not all the base in disguise: dropping a record CHANGES the work.
    changed = [m.mutant_id for m, r in results
               if m.operator == "never_arrives" and r.final != bases[m.base].final]
    assert len(changed) >= 20, "removing a record never changed what work remained"


def test_the_oracle_fires_on_a_wrong_answer(run):
    """The attack above is a negative assertion over an oracle. The oracle is shown to FIRE: on a
    dropped need, a human's need downgraded, a human's need that can be waited away, a duplicate, a
    foreign tenant, flipped billing readiness, and work resting on nothing."""
    result, _ = run
    state = result.at("W01", "invoice-no-mc", "LD-49001")
    labels = [r.label for r in _history("W01").records]
    assert "invoice-no-mc" in labels
    view = None
    for step in result.steps:
        if step.history_id == "W01" and step.label == "invoice-no-mc":
            view = True
    assert view

    def audit(wrong, at):
        # The canonical view AT that moment is rebuilt from a truncated run.
        return wrong, at

    import tempfile
    with tempfile.TemporaryDirectory() as scratch:
        store = _store(Path(scratch))
        intake = FreightIntake(store.conn, WORK_SETUPS[NORTHLINE])
        history = _history("W01")
        for record in history.records[: labels.index("invoice-no-mc") + 1]:
            intake.ingest(record)
        moment = intake.projection().view_by_load_ref("LD-49001")
        honest = evaluate_load_work(moment, setup=intake.setup, as_of=intake.foundation.now())
        assert audit_state(honest, moment, tenant=NORTHLINE) == []
        need = honest.needs[0]
        for label, wrong, expected in (
                ("dropped", replace(honest, needs=()), "SILENT STALL"),
                ("dropped", replace(honest, needs=()), "FALSE QUIET"),
                ("downgraded", replace(honest, needs=(replace(
                    need, human_required=False, handling=Handling.NEYMA_ACTION_CANDIDATE),)),
                 "A HUMAN NEED DOWNGRADED"),
                ("waitable", replace(honest, needs=(replace(
                    need, actions=(ShadowAction.WAIT,)),)), "AUTHORITY"),
                ("duplicated", replace(honest, needs=(need, need)), "DUPLICATE WORK"),
                ("foreign", replace(honest, needs=(replace(need, tenant_id=CEDAR),)), "TENANT"),
                ("billing", replace(honest, billing_ready=not honest.billing_ready), "BILLING"),
                ("unowned", replace(honest, needs=(replace(need, owner_id=None),)),
                 "no accountable owner"),
                ("money", replace(honest, billing_blockers=("owes USD 11,620.00",)), "MONEY")):
            found = audit_state(wrong, moment, tenant=NORTHLINE)
            assert any(expected in f for f in found), (label, expected, found)
        store.close()
    assert state.need(NeedKind.INVOICE_UNATTRIBUTED) is not None


# ============================================================ the operator-facing surface

def test_the_development_report_reads_like_an_operators_answer(run):
    result, _ = run
    waiting = render_load_work(result.at("W03", "check-in", "LD-49003"))
    assert "LOAD LD-49003" in waiting and "Stage: AT_PICKUP" in waiting
    assert "CARRIER_UPDATE_PENDING" in waiting and "remaining" in waiting
    assert "Open work:\n- none" in waiting and "Human attention:\n- none" in waiting
    assert "Next posture:\n- WAIT" in waiting

    candidates = render_load_work(result.at("W15", "two-passes", "LD-49015"))
    assert "- REQUEST_POD" in candidates and "- REQUEST_CARRIER_STATUS" in candidates
    assert "one outreach covers 2 of these" in candidates
    assert "Human attention:\n- none" in candidates

    human = render_load_work(result.at("W06", "portal-says-morning", "LD-49006"))
    assert "Human attention:\n- EVIDENCE_CONFLICT [APPOINTMENT_WINDOW]" in human
    assert "asks dana.ortiz: Which statement is right?" in human
    assert "T13:00" in human and "T09:00" in human
    assert "Next posture:\n- ASK_HUMAN_RESOLVE_CONFLICT" in human

    quiet = render_load_work(result.state(NORTHLINE, "LD-49002"))
    assert "Next posture:\n- QUIET" in quiet and "Billing ready: yes" in quiet
    for text in (waiting, candidates, human, quiet):
        assert "USD" not in text and "$" not in text
