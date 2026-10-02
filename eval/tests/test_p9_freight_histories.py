"""P9 deep-end 1 — the freight-domain spine, tested with freight.

Every test here runs whole load histories through the real spine: the P6-P8 machines on a real
database, the External Entity Mapping, the projection, the detectors and the timeline. Nothing is
mocked, nothing calls a model, and nothing leaves the process.

### THE CORPUS IS SYNTHETIC DEVELOPMENT INPUT. Twenty invented load histories across three invented
brokerages. A passing test here says the spine behaves as specified on that input. It is not evidence
of customer validation and it validates no freight rule.

### WHAT COULD FAIL, AND WOULD. Each behavioural claim below is checked against a population proven
non-empty, and `scripts/mutate_p9_freight_domain.py` reintroduces the real defect behind each one and
confirms the named test turns RED.
"""

from __future__ import annotations

import sqlite3
import sys
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_corpus.builders import HistoryBuilder  # noqa: E402
from freight_corpus.histories import build_corpus  # noqa: E402
from freight_corpus.parties import CEDAR, HARBOR, NORTHLINE, SETUPS  # noqa: E402
from freight_recon.freight_domain.corpus_run import (  # noqa: E402
    cross_tenant_violations,
    run_corpus,
    shared_reference_population,
)
from freight_recon.freight_domain.entity_mapping import (  # noqa: E402
    ExternalEntityMappings,
    ExternalReference,
)
from freight_recon.freight_domain.financial import blocking_discrepancies  # noqa: E402
from freight_recon.freight_domain.history import (  # noqa: E402
    FreightHistory,
    InboundRecord,
    MalformedHistory,
    UnparseableRecord,
    parse_record,
)
from freight_recon.freight_domain.intake import FreightIntake, HistoryClock  # noqa: E402
from freight_recon.freight_domain.model import (  # noqa: E402
    AccessorialAuthorization,
    DirectedMoney,
    DomainModelError,
    carrier_owed,
)
from freight_recon.workflow import WorkflowStore  # noqa: E402

#: Every table the spine writes canonical rows to. Used to measure "nothing new was written".
CANONICAL_ROW_TABLES = (
    "observations", "identity_binding_claims", "external_entity_mappings", "conflicts",
    "conflict_parties", "expectations", "exceptions", "evidence", "evidence_spans", "work_items",
)


def _store(tmp_path: Path, name: str = "p9.db") -> WorkflowStore:
    return WorkflowStore(tmp_path / name, tenant=NORTHLINE)


def _row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {t: int(conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0])
            for t in CANONICAL_ROW_TABLES}


def _history(history_id: str) -> FreightHistory:
    return next(h for h in build_corpus() if h.history_id == history_id)


def _truncate(history: FreightHistory, *, after: str) -> FreightHistory:
    """The same history, stopped just after the record labeled `after`."""
    labels = [r.label for r in history.records]
    assert after in labels, f"{history.history_id} has no record labeled {after!r}"
    return FreightHistory(history_id=history.history_id, title=history.title,
                          tenant=history.tenant, hostile=history.hostile,
                          records=history.records[: labels.index(after) + 1], expected={})


@pytest.fixture(scope="module")
def corpus(tmp_path_factory):
    store = _store(tmp_path_factory.mktemp("p9-corpus"))
    result = run_corpus(store.conn, SETUPS, build_corpus())
    yield result, store.conn
    store.close()


# ============================================================ the corpus, whole

def test_all_twenty_histories_run_and_every_labeled_outcome_holds(corpus):
    """The finish line: twenty hostile histories go through the spine and every outcome a history
    LABELS is what Neyma concluded. Counted, not assumed — a history with no checks proves nothing."""
    result, _ = corpus
    assert len(result.histories) == 20
    assert {h.history.tenant for h in result.histories} == {NORTHLINE, CEDAR, HARBOR}
    for item in result.histories:
        assert item.checks >= 3, f"{item.history.history_id} asserts only {item.checks} outcome(s)"
        assert item.mismatches == [], item.mismatches
    metrics = result.report["metrics"]
    assert metrics["histories_processed"] == 20
    assert metrics["labeled_expectations_checked"] >= 200
    assert metrics["labeled_expectations_failed"] == 0
    assert metrics["canonical_loads_produced"] == sum(
        len(p.loads) for p in result.projections.values()) >= 20
    views = [v for p in result.projections.values() for v in p.loads.values()]
    assert any(v.attention for v in views), "no load needs a human: the corpus is not hostile"
    assert any(not v.attention for v in views), "no load runs clean: nothing is being operated"


def test_the_corpus_is_hostile_in_the_ways_it_claims(corpus):
    """The corpus must actually contain what the hostility list names; a clean corpus that passes is
    a green check that parsed nothing."""
    result, _ = corpus
    tags = {tag for h in result.histories for tag in h.history.hostile}
    for required in (
            "duplicate_messages", "late_arriving_information", "stale_information",
            "contradictory_appointment_times", "tms_delivered_pod_absent",
            "pod_before_tms_delivered", "rate_con_differs_from_invoice",
            "wrong_load_document_candidate", "same_external_id_under_two_tenants",
            "two_plausible_loads", "carrier_silence", "promise_never_arrives",
            "corrected_load_number", "forwarded_repeated_email", "duplicate_invoice",
            "incomplete_documents", "accessorial_not_authorized", "conflicting_tracking_sources"):
        assert required in tags, f"no history is tagged {required}"
    metrics = result.report["metrics"]
    for name in ("duplicate_inputs_suppressed", "ambiguous_mappings", "conflicts_raised",
                 "unresolved_document_requirements", "overdue_expectations",
                 "indeterminate_expectations", "reconciliation_discrepancies",
                 "human_attention_required", "references_shared_across_tenants",
                 "late_bindings_after_mapping_arrived", "refused_records", "unparseable_records"):
        assert metrics[name] > 0, f"the corpus exercises no {name}"


# ============================================================ binding and identity

def test_a_pod_cannot_silently_bind_to_the_wrong_load(tmp_path):
    """A POD carrying one load's number and another load's BOL is bound to NEITHER. It is held, both
    loads are named as candidates, a human owns it, and neither load gains a document."""
    store = _store(tmp_path)
    history = _truncate(_history("N07"), after="pod")
    result = run_corpus(store.conn, SETUPS, [history])
    outcome = result.outcome("N07", "pod")
    projection = result.projections[NORTHLINE]
    first, second = result.view(NORTHLINE, "LD-48301"), result.view(NORTHLINE, "LD-48302")

    assert outcome.disposition == "AMBIGUOUS"
    assert sorted(outcome.candidate_load_ids) == sorted([first.load_id, second.load_id])
    assert outcome.ambiguity == "references_name_different_loads"
    assert first.documents == {} and second.documents == {}
    held = [u for u in projection.unbound if u.observation_id == outcome.observation_id]
    assert len(held) == 1 and held[0].state == "UNBOUND" and held[0].owner_id == "priya.nair"
    claims = store.conn.execute(
        "SELECT state, owner_id, provenance_class FROM identity_binding_claims "
        "WHERE tenant = ? AND subject_ref = ?", (NORTHLINE, outcome.observation_id)).fetchall()
    assert len(claims) == 2, "one candidate claim per plausible load"
    assert {c["state"] for c in claims} == {"AMBIGUOUS"}
    assert all(c["owner_id"] == "priya.nair" for c in claims)
    # Both loads were delivered, and neither is eligible to invoice on a POD nobody has placed.
    assert first.invoice.lifecycle_state == second.invoice.lifecycle_state == "NOT_ELIGIBLE"
    store.close()


def test_the_same_load_number_in_two_tenants_cannot_cross_bind(corpus):
    """Northline and Cedar Ridge each have a load numbered LD-48219, the same PO, the same carrier and
    the same PRO, in the same database. They are two canonical loads and nothing crosses."""
    result, conn = corpus
    north, cedar = result.view(NORTHLINE, "LD-48219"), result.view(CEDAR, "LD-48219")
    assert north.load_id != cedar.load_id
    assert north.load.tenant_id == NORTHLINE and cedar.load.tenant_id == CEDAR

    # The population the negative assertion rests on: the same references DO exist under both.
    assert shared_reference_population(conn) >= 4
    reference = ExternalReference("tms:loadmaster", "load_ref", "LD-48219")
    clock = HistoryClock()
    clock.set("2026-06-01T00:00:00.000Z")
    by_tenant = {
        tenant: ExternalEntityMappings(conn, tenant=tenant, clock=clock).resolve(reference)
        for tenant in (NORTHLINE, CEDAR)}
    assert by_tenant[NORTHLINE].status == by_tenant[CEDAR].status == "EXACT"
    assert by_tenant[NORTHLINE].entity_refs == (north.ref,)
    assert by_tenant[CEDAR].entity_refs == (cedar.ref,)

    # Every record of each brokerage's history is bound to its own load.
    for tenant, view, history_id in ((NORTHLINE, north, "N01"), (CEDAR, cedar, "C01")):
        bound = [o for o in result.history(history_id).outcomes if o.load_id]
        assert len(bound) >= 5
        assert {o.load_id for o in bound} == {view.load_id}
        assert all(o["tenant"] == tenant for o in view.observations)
    assert north.documents.keys().isdisjoint(cedar.documents.keys())
    # Same rate-con number, same carrier, two different agreements: neither leaked into the other.
    north_buy = next(iter(north.rate_confirmations.values())).value("linehaul")
    cedar_buy = next(iter(cedar.rate_confirmations.values())).value("linehaul")
    assert north_buy.amount_minor == 240000 and cedar_buy.amount_minor == 230000

    assert cross_tenant_violations(conn) == []
    assert result.report["metrics"]["wrong_cross_tenant_mappings"] == 0
    # A brokerage that has never seen a reference does not find it in a neighbour's data.
    only_northline = ExternalReference("tms:loadmaster", "load_ref", "LD-48233")
    assert ExternalEntityMappings(conn, tenant=NORTHLINE, clock=clock).resolve(
        only_northline).status == "EXACT"
    assert ExternalEntityMappings(conn, tenant=CEDAR, clock=clock).resolve(
        only_northline).status == "UNMAPPED"


def test_the_cross_tenant_audit_fires_on_a_real_cross_tenant_binding(tmp_path):
    """`wrong_cross_tenant_mappings == 0` is a negative assertion, so the audit that produces it is
    shown to FIRE. The composite foreign keys make a cross-tenant SUBJECT unrepresentable, but a
    claim's `entity_ref` is text: a Cedar Ridge claim naming Northline's load is exactly the defect,
    it can be written, and the audit must report it."""
    store = _store(tmp_path)
    result = run_corpus(store.conn, SETUPS, [_history("N01"), _history("C01")])
    conn = store.conn
    assert cross_tenant_violations(conn) == []
    north, cedar = result.view(NORTHLINE, "LD-48219"), result.view(CEDAR, "LD-48219")
    victim = conn.execute(
        "SELECT binding_claim_id FROM identity_binding_claims WHERE tenant = ? "
        "AND state = 'CONFIRMED' AND entity_ref = ? ORDER BY binding_claim_id LIMIT 1",
        (CEDAR, cedar.ref)).fetchone()["binding_claim_id"]
    # The claim's own immutability triggers are dropped ON THIS THROWAWAY DATABASE so the forbidden
    # state can be written at all; that it takes this much is the point.
    triggers = [r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type = 'trigger' "
        "AND tbl_name = 'identity_binding_claims'")]
    for name in triggers:
        conn.execute(f"DROP TRIGGER {name}")
    conn.execute("UPDATE identity_binding_claims SET entity_ref = ? WHERE tenant = ? "
                 "AND binding_claim_id = ?", (north.ref, CEDAR, victim))
    conn.commit()
    violations = cross_tenant_violations(conn)
    assert len(violations) == 1 and victim in violations[0] and NORTHLINE in violations[0], violations
    store.close()


def test_an_ambiguous_load_reference_stays_ambiguous(corpus):
    """A PO that covers two loads does not get resolved to the nearer one — not at intake, and not by
    the end of the corpus. A bare number with no system named does not resolve at all."""
    result, conn = corpus
    po_only = result.outcome("N08", "customer-po-only")
    bare = result.outcome("N08", "text-bare-number")
    both = result.outcome("N08", "customer-po-and-load")
    first, second = result.view(NORTHLINE, "LD-48410"), result.view(NORTHLINE, "LD-48411")

    assert po_only.disposition == "AMBIGUOUS"
    assert sorted(po_only.candidate_load_ids) == sorted([first.load_id, second.load_id])
    assert bare.disposition == "UNBOUND" and bare.candidate_load_ids == ()
    # The same PO PLUS a load number is consistent with exactly one load, and binds.
    assert both.disposition == "BOUND" and both.load_id == second.load_id

    still_held = {u.observation_id: u for u in result.projections[NORTHLINE].unbound}
    assert po_only.observation_id in still_held and bare.observation_id in still_held
    assert still_held[po_only.observation_id].owner_id == "priya.nair"
    confirmed = conn.execute(
        "SELECT COUNT(*) FROM identity_binding_claims WHERE tenant = ? AND subject_ref IN (?, ?) "
        "AND state = 'CONFIRMED'",
        (NORTHLINE, po_only.observation_id, bare.observation_id)).fetchone()[0]
    assert confirmed == 0


def test_a_late_record_binds_when_its_load_arrives_and_stale_news_does_not_regress(corpus):
    """A rate confirmation that arrived before the TMS row existed is held, then bound when the load
    appears. A stale TMS snapshot arriving after a newer one changes nothing about what is believed."""
    result, _ = corpus
    assert result.outcome("N14", "rate-con-early").disposition == "UNBOUND"
    view = result.view(NORTHLINE, "LD-48801")
    assert [d.value("doc_type") for d in view.documents.values()] == ["RATE_CON"]
    assert len(view.rate_confirmations) == 1
    assert next(iter(view.rate_confirmations.values())).movement_id == \
        view.movements["M1"].entity_id, "the early rate con was not attributed to its movement"
    status = view.load.field_of("reported_status")
    assert status.value == "IN_TRANSIT"
    assert [f.value for f in status.stale_facts()] == ["COVERED", "DISPATCHED"]
    late = [t for t in view.timeline if "arrived_out_of_order" in t.flags]
    assert len(late) == 2
    assert [t.at for t in view.timeline] == sorted(t.at for t in view.timeline)
    # The stale snapshot is told where it BELONGS in business time, not as the latest news: the load
    # went COVERED -> DISPATCHED -> IN_TRANSIT, and never "back" from IN_TRANSIT to DISPATCHED.
    assert [t.summary for t in view.timeline if t.kind == "tms_status"] == [
        "TMS status COVERED -> DISPATCHED", "TMS status DISPATCHED -> IN_TRANSIT"]


def test_the_cardinalities_are_not_collapsed(corpus):
    """One load moved by two carriers; one customer order covering two loads. Neither is forced into
    a 1:1 shape (V-21 is OPEN — the model keeps the entities distinct and the relationship additive).
    """
    result, _ = corpus
    repowered = result.view(NORTHLINE, "LD-48890")
    assert len(repowered.movements) == 2
    assert {m.load_id for m in repowered.movements.values()} == {repowered.load_id}
    assert len({m.carrier_id for m in repowered.movements.values()}) == 2
    assert sorted(m.value("reported_status") for m in repowered.movements.values()) == [
        "DELIVERED", "FELL_OFF"]
    assert len(repowered.rate_confirmations) == 2
    assert sorted(r.status for r in repowered.reconciliations) == ["COMPUTED", "RECONCILED"]

    first, second = result.view(NORTHLINE, "LD-48410"), result.view(NORTHLINE, "LD-48411")
    assert first.load_id != second.load_id
    assert first.load.order_id == second.load.order_id is not None
    assert first.order.entity_id != first.load_id, "an order is not its load"


# ============================================================ documents and delivery

def test_delivered_does_not_imply_pod_received(corpus):
    """The TMS says delivered. No POD exists. The requirement is OUTSTANDING, the POD is an overdue
    Expectation owned by a human, and the load is not eligible to invoice."""
    result, _ = corpus
    view = result.view(NORTHLINE, "LD-48260")
    assert view.load.value("reported_status") == "DELIVERED" and view.delivered_claims()
    assert not [d for d in view.documents.values() if d.value("doc_type") == "POD"]
    assert [(r.required_doc_type, r.state) for r in view.requirements] == [("POD", "OUTSTANDING")]
    pod = [e for e in view.expectations if e["expected_type"] == "document:POD"]
    assert len(pod) == 1 and pod[0]["state"] == "OVERDUE" and pod[0]["owner_id"] == "dana.ortiz"
    assert pod[0]["coverage_health"] == "HEALTHY", "OVERDUE requires proven coverage"
    assert view.invoice.lifecycle_state == "NOT_ELIGIBLE"
    # The carrier side reconciled cleanly: AP being right does not make AR ready.
    assert [r.status for r in view.reconciliations] == ["RECONCILED"]


def test_pod_received_does_not_imply_billing_ready(tmp_path, corpus):
    """A signed POD on file is necessary and not sufficient. Before any source reports delivery the
    load is not eligible; where the brokerage has configured no requirement, what the load needs is
    unknown and it is not eligible either."""
    store = _store(tmp_path)
    early = run_corpus(store.conn, SETUPS, [_truncate(_history("N04"), after="pod")])
    view = early.view(NORTHLINE, "LD-48277")
    assert [d.value("doc_type") for d in view.documents.values()] == ["RATE_CON", "POD"]
    assert view.delivered_claims() == [], "a POD arriving does not set the load delivered"
    assert view.load.value("reported_status") == "IN_TRANSIT"
    assert view.invoice.lifecycle_state == "NOT_ELIGIBLE"
    assert any("delivery has not been reported" in b for b in view.invoice.blockers)
    store.close()

    result, _ = corpus
    settled = result.view(NORTHLINE, "LD-48277")
    assert settled.invoice.lifecycle_state == "ELIGIBLE", "once delivery is reported it is eligible"
    assert not [e for e in settled.expectations if e["expected_type"] == "document:POD"], (
        "a POD already on file is not expected again")

    unknown = result.view(HARBOR, "HP-1107")
    assert [d.value("doc_type") for d in unknown.documents.values()].count("POD") == 1
    assert [r.state for r in unknown.requirements] == ["UNKNOWN"]
    assert unknown.invoice.lifecycle_state == "NOT_ELIGIBLE"


def test_an_unusable_document_does_not_satisfy_a_requirement(corpus):
    """Half a POD, an illegible POD and an unsigned BOL arrive. None of them is a POD."""
    result, _ = corpus
    view = result.view(NORTHLINE, "LD-48620")
    kinds = sorted(str(d.value("doc_type")) for d in view.documents.values())
    assert kinds == ["BOL", "POD", "POD"]
    assert [r.state for r in view.requirements] == ["OUTSTANDING"]
    unusable = [x for x in view.exceptions if x["type"] == "document_unusable"]
    assert len(unusable) == 2 and all(x["owner_id"] == "dana.ortiz" for x in unusable)
    assert view.invoice.lifecycle_state == "NOT_ELIGIBLE"


def test_duplicate_inbound_evidence_does_not_create_duplicate_canonical_work(tmp_path):
    """Re-delivered records, a forwarded copy of the same POD and a re-sent invoice produce one
    Observation, one Document and one payable each — and running the whole history AGAIN writes
    nothing at all."""
    store = _store(tmp_path)
    history = _history("N02")
    result = run_corpus(store.conn, SETUPS, [history])
    view = result.view(NORTHLINE, "LD-48233")
    assert result.outcome("N02", "tender-redelivered").disposition == "DUPLICATE"
    assert result.outcome("N02", "rate-con-redelivered").disposition == "DUPLICATE"
    assert len([d for d in view.documents.values() if d.value("doc_type") == "POD"]) == 1
    assert len(view.duplicate_evidence_arrivals) == 1
    assert len(view.payables) == 1
    assert sum(len(p.duplicate_observation_ids) for p in view.payables.values()) == 1
    assert len([e for e in view.expectations if e["expected_type"] == "counterparty_update"]) == 1, (
        "a promise quoted in a forwarded email is not a second promise")

    before, digest = _row_counts(store.conn), result.projections[NORTHLINE].digest()
    assert before["observations"] > 10 and before["identity_binding_claims"] > 10
    intake = result.intakes[NORTHLINE]
    # The same records arriving again, a week later: same source, same id, same content.
    replayed = [intake.ingest(replace(r, received_at="2026-03-20T12:00:00+00:00"))
                for r in history.records if r.is_observation]
    assert len(replayed) > 10
    assert {o.disposition for o in replayed} == {"DUPLICATE"}
    assert _row_counts(store.conn) == before
    assert intake.projection().digest() == digest
    store.close()


# ============================================================ conflicts and expectations

def test_conflicting_appointment_facts_do_not_flatten_into_one_guessed_value(corpus):
    """The TMS, the facility portal and the carrier give two different delivery windows. The window
    has NO value, the Conflict names every party and its own provenance, a human owns it, and no
    arrival deadline is asserted from a disputed time."""
    result, _ = corpus
    view = result.view(NORTHLINE, "LD-48305")
    window = view.appointments["S2"].field_of("window")
    assert window.condition == "conflicting"
    assert window.value is None and window.current is None
    assert len(window.latest_by_source()) == 3, "every source's statement is retained"
    assert len(window.facts) >= 3
    conflicts = [c for c in view.conflicts if c["field"] == "window"]
    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict["state"] in ("RAISED", "OPEN") and conflict["owner_id"] == "dana.ortiz"
    stated = {p["stated_value"] for p in conflict["parties"]}
    assert len(conflict["parties"]) == 3 and len(stated) == 2
    assert {p["provenance_class"] for p in conflict["parties"]} == {
        "SYSTEM_IMPORTED", "MODEL_EXTRACTED"}
    assert not [e for e in view.expectations if e["expected_type"] == "arrival:S2"]
    # The undisputed pickup window is unaffected.
    assert view.appointments["S1"].condition("window") == "consistent"


def test_tracking_unavailable_does_not_mean_late(corpus):
    """Two deadlines pass on one load. The carrier's promised text never came over a line we can
    prove was up: OVERDUE. The arrival was never seen over a tracking feed that was DOWN:
    INDETERMINATE — and the human is told we were blind, not that the carrier failed."""
    result, _ = corpus
    view = result.view(NORTHLINE, "LD-48455")
    by_type = {e["expected_type"]: e for e in view.expectations}
    assert by_type["counterparty_update"]["state"] == "OVERDUE"
    assert by_type["counterparty_update"]["coverage_health"] == "HEALTHY"
    arrival = by_type["arrival:S1"]
    assert arrival["state"] == "INDETERMINATE" and arrival["state"] != "OVERDUE"
    assert arrival["coverage_gap"] and "DOWN" in arrival["coverage_gap"]
    questions = {x["source_ref"]: x["specific_question"] for x in view.exceptions
                 if x["source_kind"] == "expectation"}
    assert len(questions) == 2
    assert "blind" in questions[arrival["expectation_id"]].lower()
    assert "blind" not in questions[by_type["counterparty_update"]["expectation_id"]].lower()
    assert not view.delivered_claims()


def test_an_outage_inside_a_healthy_window_is_blindness_not_lateness(tmp_path):
    """The tracking feed was recorded HEALTHY for the whole period — and DOWN for the hours that
    mattered. Both records span the appointment. The arrival that was never seen is INDETERMINATE:
    a narrower outage is not outvoted by a broader all-clear. (Found at P9: M8 took the first
    covering row and ruled this OVERDUE.)"""
    store = _store(tmp_path)
    source = _history("N09")
    outage_first = [r for r in source.records if r.label != "coverage-tracking:macropoint"]
    builder = HistoryBuilder("N09", source.title, NORTHLINE, day="2026-04-10",
                             zone="America/Chicago", hostile=source.hostile)
    builder.coverage("coverage-tracking-all-clear", builder.t("04:00"), "tracking:macropoint",
                     builder.t("00:00", -9), builder.t("23:59", 20))
    builder.coverage("coverage-tracking-outage", builder.t("04:30"), "tracking:macropoint",
                     builder.t("06:00"), builder.t("18:00"), health="DOWN")
    history = FreightHistory(history_id="N09", title=source.title, tenant=NORTHLINE,
                             hostile=source.hostile,
                             records=(*builder.records, *outage_first), expected={})
    result = run_corpus(store.conn, SETUPS, [history])
    rows = store.conn.execute(
        "SELECT health FROM observation_coverage WHERE tenant = ? AND channel = ? "
        "ORDER BY window_start", (NORTHLINE, "tracking:macropoint")).fetchall()
    assert [r["health"] for r in rows] == ["HEALTHY", "DOWN"], "both readings must be on file"
    arrival = next(e for e in result.view(NORTHLINE, "LD-48455").expectations
                   if e["expected_type"] == "arrival:S1")
    assert arrival["state"] == "INDETERMINATE"
    assert arrival["coverage_health"] == "DOWN"
    store.close()


def test_a_facility_appointment_deadline_is_evaluated_in_the_facilitys_timezone(corpus):
    """A Detroit delivery window ending 11:00 is 11:00 EASTERN — an hour before 11:00 in the Chicago
    office that booked it — and the Expectation's deadline says so."""
    result, _ = corpus
    view = result.view(NORTHLINE, "LD-48219")
    window = view.appointments["S2"].value("window")
    assert window["timezone"] == "America/Detroit" and window["end_local"].endswith("T11:00")
    arrival = next(e for e in view.expectations if e["expected_type"] == "arrival:S2")
    assert arrival["deadline_utc"] == "2026-03-10T15:00:00.000Z"
    assert arrival["originating_timezone"] == "America/Detroit"


def test_conflicting_tracking_sources_raise_a_conflict_not_a_verdict(corpus):
    """The driver says delivered; the tracking provider then places the truck 38 miles out. Neither
    is believed over the other, and a load whose delivery is disputed is not eligible to invoice."""
    result, _ = corpus
    view = result.view(NORTHLINE, "LD-48760")
    conflict = next(c for c in view.conflicts if c["field"] == "tracking_status")
    assert conflict["state"] in ("RAISED", "OPEN")
    assert sorted(p["stated_value"] for p in conflict["parties"]) == ["DELIVERED", "IN_TRANSIT"]
    assert view.invoice.lifecycle_state == "NOT_ELIGIBLE"
    assert any("tracking_status" in b for b in view.invoice.blockers)


# ============================================================ money

def test_an_invoice_discrepancy_remains_visible(corpus):
    """The carrier bills the number from a phone call instead of the rate confirmation. Nothing is
    adjusted: both figures stand as stated, the mismatch is a Conflict a human owns, the payable is
    held, and re-projecting does not make it go away."""
    result, _ = corpus
    view = result.view(NORTHLINE, "LD-48340")
    payable = next(iter(view.payables.values()))
    ratecon = next(iter(view.rate_confirmations.values()))
    assert ratecon.value("linehaul") == carrier_owed(195000, "USD")
    assert payable.value("linehaul") == carrier_owed(215000, "USD")
    assert payable.lifecycle_state == "HELD"
    assert [r.status for r in view.reconciliations] == ["DISCREPANT"]
    codes = [d.code for d in blocking_discrepancies(view.reconciliations[0])]
    assert codes == ["LINEHAUL_MISMATCH"]
    conflict = next(c for c in view.conflicts if c["field"] == "owed_to_carrier.linehaul")
    assert conflict["state"] in ("RAISED", "OPEN") and conflict["owner_id"] == "dana.ortiz"

    again = result.intakes[NORTHLINE].projection().view_by_load_ref("LD-48340")
    assert [r.status for r in again.reconciliations] == ["DISCREPANT"]
    assert view.reconciliations[0].source_observation_ids, "the evidence chain is pinned (CD-18)"


def test_a_conversational_rate_never_becomes_the_buy_rate(corpus):
    """V-14 (OPEN): the rate confirmation is the only authoritative buy rate. A number agreed in an
    email, and a carrier-pay figure sitting in the TMS, are retained as MODEL_INFERRED observations
    that no consequential read can see — and with no rate confirmation there is no expected buy."""
    result, _ = corpus
    talked = result.view(NORTHLINE, "LD-48340").movements["M1"].field_of("pre_ratecon_buy")
    assert [f.provenance_class for f in talked.facts] == ["MODEL_INFERRED"]
    assert talked.facts[0].value == carrier_owed(215000, "USD")
    assert talked.gating_facts() == [] and talked.current is None
    assert talked.condition == "unknown"

    view = result.view(CEDAR, "LD-50033")
    guesses = view.movements["M1"].field_of("pre_ratecon_buy")
    assert len(guesses.facts) >= 2 and {f.provenance_class for f in guesses.facts} == {
        "MODEL_INFERRED"}
    reconciliation = view.reconciliations[0]
    assert reconciliation.expected is None and reconciliation.expected_condition == "absent"
    assert reconciliation.status == "COMPUTED"
    assert [d.code for d in blocking_discrepancies(reconciliation)] == [
        "EXPECTED_BUY_UNESTABLISHED"]
    assert [x["type"] for x in view.exceptions] == ["buy_rate_unestablished"]


def test_an_accessorial_mention_does_not_become_a_human_authorization(corpus):
    """A carrier says a lumper charge "was already approved". That is a claim and a fraud signal. The
    ONLY thing that authorizes it is a recorded human's own act; the detention nobody authorized
    stays unresolved, and a forged or model-originated authorization cannot be constructed."""
    result, conn = corpus
    view = result.view(NORTHLINE, "LD-48702")
    lumper, detention = view.accessorials["LUMPER"], view.accessorials["DETENTION"]
    assert lumper.counterparty_asserted_authorization is True
    assert len(view.authorizations) == 1
    authorization = view.authorizations[0]
    assert authorization.authorized_by == "marcus.reid"
    assert authorization.provenance_class == "OWNER_ASSERTED"
    assert authorization.charge_type == "LUMPER" and lumper.lifecycle_state == "AUTHORIZED"
    assert detention.lifecycle_state == "CLAIMED" and detention.authorization_id is None
    by_line = {d.line: d.authorization for d in view.reconciliations[0].discrepancies}
    assert by_line == {"LUMPER": "AUTHORIZED", "DETENTION": "UNRESOLVED"}
    assert "counterparty_self_authorization" in {x["type"] for x in view.exceptions}

    # Cedar Ridge: the carrier asserts approval, an email declares its own provenance, and someone
    # types an authorization in the carrier dispatcher's name. No authorization results.
    hostile = result.view(CEDAR, "LD-50090")
    assert hostile.authorizations == []
    assert hostile.accessorials["DETENTION"].lifecycle_state == "CLAIMED"
    assert result.outcome("C03", "email-declares-provenance").disposition == "REFUSED"
    assert result.outcome("C03", "forged-authorization").disposition == "REFUSED"
    refused = conn.execute(
        "SELECT type, severity, owner_id FROM exceptions WHERE tenant = ? AND type IN "
        "('inbound_content_claimed_provenance', 'unauthenticated_human_assertion')",
        (CEDAR,)).fetchall()
    assert sorted(r["type"] for r in refused) == [
        "inbound_content_claimed_provenance", "unauthenticated_human_assertion"]
    assert all(r["severity"] == "SEV1" and r["owner_id"] == "lee.tran" for r in refused)

    for provenance in ("MODEL_INFERRED", "MODEL_EXTRACTED", "LINKER_INFERRED", "SYSTEM_IMPORTED"):
        with pytest.raises(DomainModelError):
            AccessorialAuthorization(
                authorization_id="a", tenant_id=NORTHLINE, load_id="l", charge_type="DETENTION",
                amount_cap=carrier_owed(17500, "USD"), authorized_by="carla.mendez",
                decision_ref="per our call", provenance_class=provenance, observation_id="o")


def test_money_always_carries_its_direction_and_never_floats(corpus):
    """Sell is IN, buy is OUT, on every monetary fact in the corpus; a float amount is unparseable."""
    result, _ = corpus
    seen = {"IN": 0, "OUT": 0}
    for projection in result.projections.values():
        for view in projection.loads.values():
            for entity in view.entities():
                for field in entity.fields.values():
                    for fact in field.facts:
                        if isinstance(fact.value, DirectedMoney):
                            seen[fact.value.direction] += 1
                            assert isinstance(fact.value.amount_minor, int)
                            expected = "IN" if entity.ENTITY_TYPE == "brokerage_load" else "OUT"
                            assert fact.value.direction == expected, (entity.ENTITY_TYPE, field.name)
    assert seen["IN"] >= 20 and seen["OUT"] >= 30
    with pytest.raises(DomainModelError):
        DirectedMoney(100, "USD", "SIDEWAYS", "owed_to_carrier")
    record = InboundRecord(
        label="x", channel="email", kind="document", source_system="email:x", external_id="1",
        received_at="2026-03-09T08:00:00-05:00", as_of="2026-03-09T08:00:00-05:00",
        timezone="America/Chicago", refs=(),
        payload={"doc_type": "RATE_CON", "content": "x",
                 "extracted": {"ratecon_number": "R", "currency": "USD", "linehaul_minor": 2400.0}})
    with pytest.raises(UnparseableRecord):
        parse_record(record)


# ============================================================ provenance and ownership

def test_binding_an_artifact_does_not_strengthen_what_it_says(corpus):
    """A driver's text bound to a load by exact id is still a driver's text. M5 overwrites the
    Observation ROW's provenance with the binding's (LINKER_INFERRED, or OWNER_ASSERTED when a human
    bound it); every FACT the spine reads from that record keeps the provenance of how it was
    acquired."""
    result, conn = corpus
    view = result.view(NORTHLINE, "LD-48219")
    claim = next(t for t in view.tracking if t.value("signal") == "driver_assertion")
    fact = claim.field_of("status").facts[0]
    row = conn.execute("SELECT provenance_class, match_method FROM observations WHERE tenant = ? "
                       "AND observation_id = ?", (NORTHLINE, fact.observation_id)).fetchone()
    assert row["match_method"] == "EXACT_ID" and row["provenance_class"] == "LINKER_INFERRED"
    assert fact.provenance_class == "MODEL_EXTRACTED"

    human_bound = result.view(NORTHLINE, "LD-48302")
    pod = next(d for d in human_bound.documents.values() if d.value("doc_type") == "POD")
    pod_fact = pod.field_of("doc_type").facts[0]
    pod_row = conn.execute("SELECT provenance_class, match_method FROM observations WHERE "
                           "tenant = ? AND observation_id = ?",
                           (NORTHLINE, pod_fact.observation_id)).fetchone()
    assert pod_row["match_method"] == "HUMAN" and pod_row["provenance_class"] == "OWNER_ASSERTED"
    assert pod_fact.provenance_class == "MODEL_EXTRACTED", (
        "a human saying WHERE a document belongs does not make its contents owner-asserted")

    classes = {f.provenance_class for p in result.projections.values() for v in p.loads.values()
               for e in v.entities() for fld in e.fields.values() for f in fld.facts}
    assert classes == {"SYSTEM_IMPORTED", "MODEL_EXTRACTED", "MODEL_INFERRED"}


def test_every_open_obligation_has_one_accountable_active_human(corpus):
    """Every Conflict, Exception, late Expectation, held record and Work Item in the corpus names one
    recorded ACTIVE human of its own brokerage."""
    result, conn = corpus
    checked = 0
    for tenant, projection in result.projections.items():
        humans = {r["human_id"] for r in conn.execute(
            "SELECT human_id FROM tenant_humans WHERE tenant = ? AND state = 'ACTIVE'", (tenant,))}
        assert humans
        owners: list[str | None] = [u.owner_id for u in projection.unbound]
        for view in projection.loads.values():
            assert view.work_item is not None, "a load with no Work Item has no accountable owner"
            owners.append(view.work_item["owner_id"])
            owners.extend(c["owner_id"] for c in view.conflicts)
            owners.extend(x["owner_id"] for x in view.exceptions)
            owners.extend(e["owner_id"] for e in view.late_expectations())
        for owner in owners:
            checked += 1
            assert owner in humans, f"{tenant}: {owner!r} is not an ACTIVE human of this brokerage"
    assert checked >= 40, f"only {checked} owned obligations were checked"


# ============================================================ history and correction

def test_a_correction_supersedes_without_deleting_history(corpus):
    """A POD bound by its number to the wrong load is corrected by a human. The wrong binding is
    retained as CORRECTED with its propagation obligation; the document moves; the load it left owes
    a POD again. A renumbered load and a mis-keyed PO keep their old mappings, and the database
    itself refuses to edit or delete one."""
    result, conn = corpus
    wrong, right = result.view(NORTHLINE, "LD-48720"), result.view(NORTHLINE, "LD-48721")
    pod = result.outcome("N16", "pod")
    assert pod.load_id == wrong.load_id, "it bound exactly, to the load it named"
    assert [d.value("doc_type") for d in right.documents.values()] == ["POD"]
    assert wrong.documents == {}
    claims = conn.execute(
        "SELECT state, entity_ref, provenance_class, corrected_from, propagation_obligation "
        "FROM identity_binding_claims WHERE tenant = ? AND subject_ref = ? ORDER BY created_at",
        (NORTHLINE, pod.observation_id)).fetchall()
    assert [c["state"] for c in claims] == ["CORRECTED", "CONFIRMED"]
    assert claims[0]["entity_ref"] == wrong.ref and claims[0]["propagation_obligation"]
    assert claims[1]["entity_ref"] == right.ref
    assert claims[1]["provenance_class"] == "OWNER_ASSERTED" and claims[1]["corrected_from"]
    # What rested on the wrong binding is re-derived: the load it left owes its POD again.
    history = [e["state"] for e in wrong.expectations if e["expected_type"] == "document:POD"]
    assert history == ["DISCHARGED", "OVERDUE"]
    assert [r.state for r in wrong.requirements] == ["OUTSTANDING"]
    assert [r.state for r in right.requirements] == ["SATISFIED"]

    renumbered = result.view(NORTHLINE, "LD-48591")
    states = {(m.external_id, m.state) for m in renumbered.mappings}
    assert {("LD-48519", "SUPERSEDED"), ("LD-48591", "ACTIVE"), ("PO-4504", "CORRECTED"),
            ("PO-4540", "ACTIVE")} <= states
    corrected = next(m for m in renumbered.mappings if m.external_id == "PO-4540")
    assert corrected.provenance_class == "OWNER_ASSERTED" and corrected.decision_human_id == \
        "dana.ortiz" and corrected.replaces_mapping_id is not None
    assert result.outcome("N10", "carrier-stale-number").disposition == "AMBIGUOUS", (
        "a retired number is a weak candidate, never an exact match")

    retired = next(m for m in renumbered.mappings if m.state == "SUPERSEDED")
    # A LEAF mapping — no other row names it — so the only thing that can refuse its deletion is the
    # no-delete trigger. Deleting the retired row below is ALSO refused by a foreign key (its
    # replacement points at it), which would hold with the trigger gone and prove nothing about it.
    replaced = {m.replaces_mapping_id for m in renumbered.mappings}
    leaf = next(m for m in renumbered.mappings
                if m.state == "ACTIVE" and m.mapping_id not in replaced
                and m.external_id_kind == "bol_number")
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        conn.execute("DELETE FROM external_entity_mappings WHERE tenant = ? AND mapping_id = ?",
                     (NORTHLINE, leaf.mapping_id))
    conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM external_entity_mappings WHERE mapping_id = ?",
                        (leaf.mapping_id,)).fetchone()[0] == 1
    for statement in (
            "UPDATE external_entity_mappings SET neyma_entity_id = 'elsewhere' WHERE mapping_id = ?",
            "UPDATE external_entity_mappings SET state = 'ACTIVE', retired_at = NULL, "
            "retired_reason = NULL WHERE mapping_id = ?",
            "DELETE FROM external_entity_mappings WHERE mapping_id = ?"):
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(statement, (retired.mapping_id,))
        conn.rollback()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO external_entity_mappings (tenant, mapping_id, neyma_entity_type, "
            "neyma_entity_id, external_system, external_id_kind, external_id, provenance_class, "
            "state, source_observation_id, created_at) VALUES (?, 'guess', 'brokerage_load', 'x', "
            "'tms:loadmaster', 'load_ref', 'LD-1', 'MODEL_INFERRED', 'ACTIVE', ?, 'now')",
            (NORTHLINE, retired.source_observation_id))
    conn.rollback()


def test_a_history_must_be_in_arrival_order_and_must_belong_to_its_tenant(tmp_path):
    builder = HistoryBuilder("X1", "out of order", NORTHLINE, day="2026-07-01",
                             zone="America/Chicago", hostile=())
    builder.clock("later", builder.t("10:00"))
    builder.clock("earlier", builder.t("09:00"))
    with pytest.raises(MalformedHistory):
        builder.build({})
    store = _store(tmp_path)
    with pytest.raises(MalformedHistory):
        FreightIntake(store.conn, SETUPS[CEDAR]).run(_history("N01"))
    store.close()


# ============================================================ replay

def test_replaying_the_corpus_produces_the_same_projection_and_no_external_effects(tmp_path, corpus):
    """Two independent runs agree byte for byte; rebuilding the projection from durable records
    writes nothing; and every ledger that would record an external effect or a minted authority is
    empty — measured over tables proven to exist, beside tables proven to have been written."""
    result, conn = corpus
    second_store = _store(tmp_path, "replay.db")
    second = run_corpus(second_store.conn, SETUPS, build_corpus())
    assert set(second.projections) == set(result.projections) and len(result.projections) == 3
    for tenant, projection in result.projections.items():
        assert projection.digest() == second.projections[tenant].digest(), tenant
    assert second.report == result.report
    second_store.close()

    before_counts, before_changes = _row_counts(conn), conn.total_changes
    assert before_counts["observations"] >= 130 and before_counts["expectations"] >= 20
    for tenant, intake in result.intakes.items():
        assert intake.projection().digest() == result.projections[tenant].digest()
    assert conn.total_changes == before_changes, "rebuilding the projection wrote to the database"
    assert _row_counts(conn) == before_counts

    present = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    effects = result.report["effect_surface_rows"]
    assert set(effects) == {NORTHLINE, CEDAR, HARBOR}
    for tenant, tables in effects.items():
        assert set(tables) <= present and len(tables) == 5
        assert all(count == 0 for count in tables.values()), (tenant, tables)
    assert result.report["metrics"]["external_effect_rows"] == 0


def test_the_settled_picture_owes_nothing_new(corpus):
    """Detection is a fixed point: over the finished corpus the detectors ask for nothing the
    machines have not already recorded, so re-running them raises nothing."""
    result, conn = corpus
    before = _row_counts(conn)
    for intake in result.intakes.values():
        raised = (intake.stats.conflicts_raised, intake.stats.expectations_raised,
                  intake.stats.exceptions_raised, intake.stats.expectations_discharged)
        intake._settle()
        assert raised == (intake.stats.conflicts_raised, intake.stats.expectations_raised,
                          intake.stats.exceptions_raised, intake.stats.expectations_discharged)
        assert intake.stats.writes_after_settle == 0
    assert _row_counts(conn) == before


# ============================================================ the timeline

def test_the_operational_timeline_is_derived_ordered_and_pinned(corpus):
    """The baseline load reads, in order, the way a dispatcher would tell it — and every entry names
    the canonical record it came from."""
    result, _ = corpus
    view = result.view(NORTHLINE, "LD-48219")
    kinds = [t.kind for t in view.timeline]
    order = ["load_data", "carrier_assignment", "document", "communication", "tracking",
             "expectation_overdue", "expectation_discharged", "financial_reconciliation"]
    positions = [kinds.index(k) for k in order]
    assert positions == sorted(positions), list(zip(order, positions))
    assert [t.at for t in view.timeline] == sorted(t.at for t in view.timeline)
    assert all(t.source_refs for t in view.timeline)
    assert all(t.tenant_id == NORTHLINE and t.load_id == view.load_id for t in view.timeline)
    overdue = next(t for t in view.timeline if t.kind == "expectation_overdue")
    assert overdue.at == "2026-03-10T01:00:00.000Z", "20:00 Chicago, told at the deadline"
    final = view.timeline[-1]
    assert final.kind == "financial_reconciliation" and "detention" in final.summary
    assert "UNRESOLVED" in final.summary and "needs_human" in final.flags

    for projection in result.projections.values():
        for load in projection.loads.values():
            assert load.timeline, f"{load.load.value('load_ref')} has no timeline"
            assert [t.at for t in load.timeline] == sorted(t.at for t in load.timeline)


def test_the_report_is_machine_readable_and_carries_no_money(corpus):
    result, _ = corpus
    report = result.report
    for name in ("histories_processed", "canonical_loads_produced",
                 "exact_external_mappings_resolved", "ambiguous_mappings",
                 "wrong_cross_tenant_mappings", "duplicate_inputs_suppressed", "conflicts_raised",
                 "unresolved_document_requirements", "overdue_expectations",
                 "reconciliation_discrepancies", "human_attention_required"):
        assert isinstance(report["metrics"][name], int), name
    assert len(report["histories"]) == 20

    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                assert "amount" not in str(key) and "minor" not in str(key), key
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
        else:
            assert "USD" not in str(value), value
    walk(report)
    assert not any("percent" in key or "accuracy" in key for key in report["metrics"])
