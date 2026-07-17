"""Phase 1 — Migration Safety Task #1. The canonical Commit Key contract.

The eighteen merge-gating oracles required of this phase, plus the concurrency schedules for the
defect that motivated all of it: two workers reading ONE logical money effect at two different
amounts, and both committing.

The rule under test, stated once:

    The Commit Key answers "is this the SAME logical effect?"
    Material decision content answers "are the approved values still identical?"

They are different questions. The defect answered the first with the second.
"""

import json
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.commit_key import (
    KEY_VERSION,
    CanonicalOccurrence,
    LogicalEffect,
    UnidentifiableEffect,
    UnresolvedCanonicalOccurrence,
    commit_key,
    occurrence_key_for,
)
from freight_recon.operation_router import (
    OperationRouter,
    _commit_reservation,
    _logical_effect,
    freight_lanes,
)
from freight_recon.operator_agent import OperatorAgent
from freight_recon.slack_delegate import CommandIntent, CommandKind
from freight_recon.workflow import WorkflowStore


def _operate(summary, params=None):
    return CommandIntent(kind=CommandKind.OPERATE, summary=summary, params=params or {})


def _lane(name):
    return next(l for l in freight_lanes() if l.name == name)


def _key(**over):
    base = dict(tenant="acme", action_class="raise_invoice", target_system="tms",
                target_resource_id="LD-1|CUST", target_operation="raise_invoice", occurrence_key="")
    base.update(over)
    return commit_key(LogicalEffect(**base))


class _Actuator:
    def __init__(self):
        self.calls = []

    def observe(self):
        return {"url": "https://tms.test/x", "interactive": [], "errors": []}

    def navigate(self, url): self.calls.append(("navigate", url)); return True
    def click(self, t): self.calls.append(("click", t)); return True
    def type(self, t, v): self.calls.append(("type", t, v)); return True
    def select(self, t, o): self.calls.append(("select", t, o)); return True
    def read(self, t): self.calls.append(("read", t)); return "INV-1"

    @property
    def commits(self):
        return [c for c in self.calls if c[0] == "click" and "save" in str(c[1]).lower()]


def _agent(actuator):
    def complete(_p):
        return json.dumps({"action": "CLICK", "target": "Save invoice"}) if not actuator.commits \
            else json.dumps({"action": "DONE", "why": "saved"})

    def build(*, approved_amount=None, approve=None, prepare_only=False):
        return OperatorAgent(actuator=actuator, complete=complete, approved_amount=approved_amount,
                             approve=approve, prepare_only=prepare_only)

    build.actuator = actuator
    return build


# ============================================================ THE EIGHTEEN MERGE-GATING ORACLES

def test_01_approved_amount_does_not_affect_the_commit_key():
    intent = _operate("invoice", {"load_ref": "LD-1", "customer": "CUST"})
    keys = {
        _commit_reservation("acme", "tms", _lane("raise_invoice"), intent, amount)["commit_key"]
        for amount in ("2850.00", "3100.00", "0.01", "999999.99", None)
    }
    assert len(keys) == 1, "the approved amount changed the identity of the effect"


def test_02_different_readings_of_one_logical_effect_produce_the_same_key():
    """Two workers, two readings, one invoice. Casing/whitespace/ordering must not fork identity."""
    a = _operate("invoice", {"load_ref": "LD-1", "customer": "CUST"})
    b = _operate("please invoice it", {"customer": "cust", "load_ref": " ld-1 "})
    ka = _commit_reservation("acme", "tms", _lane("raise_invoice"), a, "2850.00")["commit_key"]
    kb = _commit_reservation("ACME", "TMS", _lane("raise_invoice"), b, "3100.00")["commit_key"]
    assert ka == kb


def test_03_changed_mutable_values_remain_separately_detectable():
    """The amount must leave the identity WITHOUT being thrown away - drift must still be visible."""
    intent = _operate("invoice", {"load_ref": "LD-1", "customer": "CUST"})
    at_2850 = _commit_reservation("acme", "tms", _lane("raise_invoice"), intent, "2850.00")
    at_3100 = _commit_reservation("acme", "tms", _lane("raise_invoice"), intent, "3100.00")
    assert at_2850["commit_key"] == at_3100["commit_key"]      # same effect
    assert at_2850["approved_amount"] != at_3100["approved_amount"]   # different facts, still visible
    assert at_2850["approved_amount"] == "2850.00"


def test_04_every_consequential_non_money_effect_has_a_commit_key(tmp_path):
    doc = tmp_path / "pod.pdf"
    doc.write_bytes(b"pod")
    cases = [
        ("file_document", {"load_ref": "LD-1", "carrier": "C"}, str(doc)),
        ("create_load", {"load_ref": "LD-1", "customer": "C"}, None),
        ("update_status", {"load_ref": "LD-1", "customer": "C", "status_value": "DELIVERED"}, None),
    ]
    for lane_name, params, path in cases:
        res = _commit_reservation("acme", "tms", _lane(lane_name), _operate("x", params), None,
                                  document_path=path)
        assert res["commit_key"], f"{lane_name} received no commit key"
        assert res["approved_amount"] == ""


def test_05_missing_logical_effect_identity_fails_closed():
    for params in ({"customer": "C"}, {"load_ref": "LD-1"}, {}):
        with pytest.raises(UnidentifiableEffect):
            _commit_reservation("acme", "tms", _lane("raise_invoice"), _operate("x", params), "100.00")


def test_06_same_logical_effect_claimed_twice_converges_on_one_reservation(tmp_path):
    store = WorkflowStore(tmp_path / "w.sqlite3", tenant="tenant-fixture-a")
    try:
        intent = _operate("invoice", {"load_ref": "LD-1", "customer": "CUST"})
        first = _commit_reservation("acme", "tms", _lane("raise_invoice"), intent, "2850.00")
        second = _commit_reservation("acme", "tms", _lane("raise_invoice"), intent, "3100.00")
        assert store.claim_operation_commit(**first, payload={"status": "RESERVED"}) is True
        assert store.claim_operation_commit(**second, payload={"status": "RESERVED"}) is False
        rows = store.conn.execute("SELECT COUNT(*) c FROM operation_commit_claims").fetchone()["c"]
        assert rows == 1
    finally:
        store.close()


def test_07_two_legitimate_repeats_can_use_distinct_occurrence_discriminators(tmp_path):
    """Commit-once must not become commit-never: legitimate repetition stays possible."""
    doc_a, doc_b = tmp_path / "a.pdf", tmp_path / "b.pdf"
    doc_a.write_bytes(b"POD")
    doc_b.write_bytes(b"BOL")
    intent = _operate("file", {"load_ref": "LD-1", "carrier": "C"})
    ka = _commit_reservation("acme", "tms", _lane("file_document"), intent, None,
                             document_path=str(doc_a))["commit_key"]
    kb = _commit_reservation("acme", "tms", _lane("file_document"), intent, None,
                             document_path=str(doc_b))["commit_key"]
    assert ka != kb

    # This test used to continue:
    #
    #   p1 = _operate("payment", {..., "occurrence_key": "remit-001"})
    #   p2 = _operate("payment", {..., "occurrence_key": "remit-002"})
    #   assert k1 != k2
    #
    # It asserted that a FREE-FORM caller string discriminates two payments - i.e. it encoded the
    # escape hatch as expected behaviour, exactly as test_operation_router.py:282 once encoded the
    # amount-in-key defect (DEF-3). A test that asserts the defect fights the fix, so the closure
    # inverts it: identity comes from a resolved canonical occurrence, and a caller-authored string
    # is not one.
    for occurrence in ("remit-001", "remit-002"):
        payment = _operate("payment", {"load_ref": "INV-9", "customer": "C",
                                       "occurrence_key": occurrence})
        with pytest.raises(UnresolvedCanonicalOccurrence):
            _commit_reservation("acme", "tms", _lane("record_payment"), payment, "500.00")

    # Two distinct payments ARE two effects - discriminated by their Payment Application occurrences.
    k1 = occurrence_key_for("record_payment",
                            resolved=CanonicalOccurrence("Payment Application", "pa-0001"))
    k2 = occurrence_key_for("record_payment",
                            resolved=CanonicalOccurrence("Payment Application", "pa-0002"))
    assert k1 != k2, "two Payment Applications collapsed into one occurrence"


def test_08_same_external_identifier_in_two_tenants_does_not_collide(tmp_path):
    store = WorkflowStore(tmp_path / "w.sqlite3", tenant="tenant-fixture-a")
    try:
        intent = _operate("invoice", {"load_ref": "LD-1", "customer": "CUST"})
        a = _commit_reservation("tenant_a", "tms", _lane("raise_invoice"), intent, "100.00")
        b = _commit_reservation("tenant_b", "tms", _lane("raise_invoice"), intent, "100.00")
        assert a["commit_key"] != b["commit_key"]
        assert store.claim_operation_commit(**a, payload={"status": "RESERVED"}) is True
        assert store.claim_operation_commit(**b, payload={"status": "RESERVED"}) is True, (
            "tenant B was blocked by tenant A's identical load reference"
        )
    finally:
        store.close()


@pytest.mark.parametrize("noise_field,values", [
    ("retry", ["1", "2", "17"]),                      # 09 retry number
    ("request_id", ["req-a", "req-b"]),               # 10 request id
    ("approval_id", ["ap-1", "ap-2"]),                # 11 approval id
    ("timestamp", ["2026-07-16T10:00:00Z", "2026-07-16T11:30:00Z"]),   # 12 timestamp
    ("confidence", ["0.7", "0.99"]),
    ("attempt", ["1", "2"]),
])
def test_09_to_12_attempt_scoped_noise_never_alters_identity(noise_field, values):
    """An attempt-scoped identity makes every retry a NEW effect. That IS the double-commit bug."""
    keys = set()
    for v in values:
        intent = _operate("invoice", {"load_ref": "LD-1", "customer": "CUST", noise_field: v})
        keys.add(_commit_reservation("acme", "tms", _lane("raise_invoice"), intent, "100.00")["commit_key"])
    assert len(keys) == 1, f"{noise_field} leaked into the commit key"


def test_13_payload_field_ordering_does_not_alter_identity():
    a = _operate("x", {"load_ref": "LD-1", "customer": "CUST", "note": "n", "extra": "e"})
    b = _operate("x", {"extra": "e", "note": "n", "customer": "CUST", "load_ref": "LD-1"})
    ka = _commit_reservation("acme", "tms", _lane("raise_invoice"), a, "100.00")["commit_key"]
    kb = _commit_reservation("acme", "tms", _lane("raise_invoice"), b, "100.00")["commit_key"]
    assert ka == kb


def test_14_a_historical_old_format_identity_cannot_permit_recommitment(tmp_path):
    """THE MIGRATION HAZARD. A committed invoice under the old amount-keyed identity must not be
    raised again merely because its canonical key is now different."""
    store = WorkflowStore(tmp_path / "w.sqlite3", tenant="tenant-fixture-a")
    try:
        # A legacy row exactly as the deleted algorithm would have written it: key derived WITH the
        # amount, so it does not match any canonical key.
        store.claim_operation_commit(
            commit_key="legacy_sha_of_acme_raise_invoice_LD-1_CUST_2850.00",
            tenant="acme", lane="raise_invoice", load_ref="LD-1", party="CUST",
            approved_amount="2850.00", payload={"status": "COMMITTED", "committed": True},
        )
        actuator = _Actuator()
        result = OperationRouter(
            lanes=freight_lanes(), build_agent=_agent(actuator),
            approved_amount_for=lambda _i: "2850.00", tenant="acme", commit_store=store,
        ).run(_operate("invoice LD-1", {"load_ref": "LD-1", "customer": "CUST", "commit": True}),
              approve=lambda a: True)

        assert result.status == "ESCALATED"
        assert "pre-migration" in result.note
        assert actuator.commits == [], "a historical effect was RE-COMMITTED after the key changed"
    finally:
        store.close()


def test_14b_two_legacy_rows_for_one_logical_effect_are_manual_review_not_a_merge(tmp_path):
    """Two legacy rows differing only by amount ARE a historical double-commit. Do not merge them.
    Do not pick one. Do not infer success. A human settles it."""
    store = WorkflowStore(tmp_path / "w.sqlite3", tenant="tenant-fixture-a")
    try:
        for amount in ("2850.00", "3100.00"):
            store.claim_operation_commit(
                commit_key=f"legacy_{amount}", tenant="acme", lane="raise_invoice",
                load_ref="LD-1", party="CUST", approved_amount=amount,
                payload={"status": "COMMITTED"},
            )
        actuator = _Actuator()
        result = OperationRouter(
            lanes=freight_lanes(), build_agent=_agent(actuator),
            approved_amount_for=lambda _i: "2850.00", tenant="acme", commit_store=store,
        ).run(_operate("invoice LD-1", {"load_ref": "LD-1", "customer": "CUST", "commit": True}),
              approve=lambda a: True)
        assert result.status == "ESCALATED"
        assert result.steps[0]["disposition"] == "MANUAL_REVIEW_REQUIRED"
        assert result.steps[0]["legacy_rows"] == 2
        assert actuator.commits == []
        # The legacy rows are untouched: no merge, no deletion, no manufactured success.
        rows = store.conn.execute("SELECT COUNT(*) c FROM operation_commit_claims").fetchone()["c"]
        assert rows == 2
    finally:
        store.close()


def test_15_a_non_money_effect_cannot_silently_fall_back_to_none(tmp_path):
    """No None, no UUID, no request id, no timestamp, no payload hash."""
    intent = _operate("file the pod", {"load_ref": "LD-1", "carrier": "C"})
    with pytest.raises(UnidentifiableEffect, match="could not be read"):
        _commit_reservation("acme", "tms", _lane("file_document"), intent, None,
                            document_path="/nonexistent/pod.pdf")


def test_16_a_new_consequential_operation_without_commit_key_construction_fails_a_guard():
    with pytest.raises(UnidentifiableEffect, match="declares no occurrence rule"):
        occurrence_key_for("a_brand_new_consequential_lane")


def test_17_restoring_approved_amount_to_the_commit_key_fails():
    with pytest.raises(TypeError):
        LogicalEffect(tenant="a", action_class="b", target_system="c", target_resource_id="d",
                      target_operation="e", occurrence_key="", approved_amount="1")  # type: ignore
    with pytest.raises(ImportError):
        from freight_recon.workflow import operation_commit_key  # noqa: F401


def test_18_restoring_nullable_non_money_identity_fails(tmp_path):
    doc = tmp_path / "p.pdf"
    doc.write_bytes(b"x")
    res = _commit_reservation("acme", "tms", _lane("file_document"),
                              _operate("file", {"load_ref": "LD-1", "carrier": "C"}), None,
                              document_path=str(doc))
    assert res is not None and res["commit_key"]


# ================================================================== CONCURRENCY SCHEDULES

def test_race_two_workers_two_amounts_one_logical_effect(tmp_path):
    """THE defect, as a race. Worker A reads GBP 2,850; Worker B reads GBP 3,100. Same invoice.

    Under the old algorithm both keys differed, both reservations succeeded, and both invoiced.
    """
    store = WorkflowStore(tmp_path / "w.sqlite3", tenant="tenant-fixture-a")
    try:
        intent = _operate("invoice", {"load_ref": "LD-1", "customer": "CUST"})
        results, keys, barrier = [], [], threading.Barrier(2)

        def worker(amount):
            # A separate connection per worker: the arbiter is the table's PRIMARY KEY, not a shared
            # Python object. Sharing one connection would test nothing but the GIL.
            own = WorkflowStore(tmp_path / "w.sqlite3", tenant="tenant-fixture-a")
            try:
                res = _commit_reservation("acme", "tms", _lane("raise_invoice"), intent, amount)
                keys.append(res["commit_key"])
                barrier.wait()
                results.append(own.claim_operation_commit(**res, payload={"status": "RESERVED"}))
            finally:
                own.close()

        threads = [threading.Thread(target=worker, args=(a,)) for a in ("2850.00", "3100.00")]
        for t in threads: t.start()
        for t in threads: t.join()

        assert len(set(keys)) == 1, "the two workers minted DIFFERENT identities for one invoice"
        assert sorted(results) == [False, True], f"exactly one reservation must win; got {results}"
        rows = store.conn.execute("SELECT COUNT(*) c FROM operation_commit_claims").fetchone()["c"]
        assert rows == 1
        # The losing amount is not lost: the winner's material fact is recorded and can be compared
        # against the approval later (Phase 3's fingerprint). Identity converged; facts did not.
        stored = store.conn.execute("SELECT approved_amount FROM operation_commit_claims").fetchone()
        assert stored["approved_amount"] in ("2850.00", "3100.00")
    finally:
        store.close()


def test_race_same_non_money_effect_from_two_entry_points(tmp_path):
    store = WorkflowStore(tmp_path / "w.sqlite3", tenant="tenant-fixture-a")
    try:
        doc = tmp_path / "pod.pdf"
        doc.write_bytes(b"POD")
        intent = _operate("file", {"load_ref": "LD-1", "carrier": "C"})
        res = _commit_reservation("acme", "tms", _lane("file_document"), intent, None,
                                  document_path=str(doc))
        out, barrier = [], threading.Barrier(2)

        def worker():
            own = WorkflowStore(tmp_path / "w.sqlite3", tenant="tenant-fixture-a")
            try:
                barrier.wait()
                out.append(own.claim_operation_commit(**res, payload={"status": "RESERVED"}))
            finally:
                own.close()

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads: t.start()
        for t in threads: t.join()
        assert sorted(out) == [False, True]
    finally:
        store.close()


def test_race_same_logical_effect_with_different_retry_ids(tmp_path):
    store = WorkflowStore(tmp_path / "w.sqlite3", tenant="tenant-fixture-a")
    try:
        out = []
        for retry in ("1", "2", "3"):
            intent = _operate("invoice", {"load_ref": "LD-1", "customer": "CUST", "retry": retry})
            res = _commit_reservation("acme", "tms", _lane("raise_invoice"), intent, "100.00")
            out.append(store.claim_operation_commit(**res, payload={"status": "RESERVED"}))
        assert out == [True, False, False], "a retry minted a new logical effect"
    finally:
        store.close()


def test_crash_after_identity_before_reservation_is_safe_to_rerun(tmp_path):
    """Nothing happened: no row, no effect. Re-deriving the key must reproduce it exactly."""
    store = WorkflowStore(tmp_path / "w.sqlite3", tenant="tenant-fixture-a")
    try:
        intent = _operate("invoice", {"load_ref": "LD-1", "customer": "CUST"})
        first = _commit_reservation("acme", "tms", _lane("raise_invoice"), intent, "100.00")
        # crash here - the process dies before claiming
        rows = store.conn.execute("SELECT COUNT(*) c FROM operation_commit_claims").fetchone()["c"]
        assert rows == 0
        again = _commit_reservation("acme", "tms", _lane("raise_invoice"), intent, "100.00")
        assert again["commit_key"] == first["commit_key"], "the key is not reproducible after a crash"
        assert store.claim_operation_commit(**again, payload={"status": "RESERVED"}) is True
    finally:
        store.close()


def test_crash_after_reservation_blocks_a_blind_retry_across_a_restart(tmp_path):
    """The reservation survives the process. A leaked RESERVED claim must NOT report success."""
    db = tmp_path / "w.sqlite3"
    intent = _operate("invoice", {"load_ref": "LD-1", "customer": "CUST"})
    res = _commit_reservation("acme", "tms", _lane("raise_invoice"), intent, "100.00")

    store = WorkflowStore(db, tenant="tenant-fixture-a")
    store.claim_operation_commit(**res, payload={"status": "RESERVED"})
    store.close()                                  # crash / restart

    store = WorkflowStore(db, tenant="tenant-fixture-a")                      # a fresh process
    try:
        actuator = _Actuator()
        result = OperationRouter(
            lanes=freight_lanes(), build_agent=_agent(actuator),
            approved_amount_for=lambda _i: "100.00", tenant="acme", commit_store=store,
        ).run(_operate("invoice LD-1", {"load_ref": "LD-1", "customer": "CUST", "commit": True}),
              approve=lambda a: True)
        assert result.status == "ESCALATED"
        assert "not confirmed done" in result.note.lower()
        assert actuator.commits == [], "a blind retry committed after a crash"
    finally:
        store.close()


# ================================================================== the key's own shape

def test_the_key_is_versioned_so_a_future_derivation_is_distinguishable():
    assert KEY_VERSION == "ck_v1"
    a = _key()
    assert len(a) == 64 and a != _key(occurrence_key="x")


def test_every_identity_field_is_required_and_empty_fails_closed():
    for field in ("tenant", "action_class", "target_system", "target_resource_id", "target_operation"):
        with pytest.raises(UnidentifiableEffect, match=field):
            _key(**{field: ""})
    assert _key(occurrence_key="")      # the ONE legitimately-empty field


def test_distinct_logical_effects_do_not_collide_merely_by_sharing_an_entity():
    """Raising an invoice and filing a POD on ONE load are two effects, not one."""
    keys = {
        _key(action_class=a, target_operation=a)
        for a in ("raise_invoice", "record_payable", "file_document", "update_status", "create_load")
    }
    assert len(keys) == 5


def test_a_different_target_system_is_a_different_effect():
    assert _key(target_system="truckingoffice") != _key(target_system="transporters_io")


def test_logical_effect_is_frozen_so_identity_cannot_be_mutated_after_construction():
    import dataclasses
    e = LogicalEffect(tenant="a", action_class="b", target_system="c", target_resource_id="d",
                      target_operation="e", occurrence_key="")
    with pytest.raises(dataclasses.FrozenInstanceError):
        e.tenant = "other"   # type: ignore[misc]


# ============================================================ U1.5 — the historical dry-run report

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))


def _seed_legacy(store, load_ref, amounts, status="COMMITTED", lane="raise_invoice"):
    for i, amt in enumerate(amounts):
        store.claim_operation_commit(
            commit_key=f"legacy_{load_ref}_{i}", tenant="acme", lane=lane, load_ref=load_ref,
            party="CUST", approved_amount=amt, payload={"status": status},
        )


def test_the_backfill_report_never_infers_success(tmp_path):
    """A reservation that never confirmed is UNRESOLVED. It is not success, and never becomes it."""
    from report_legacy_commit_identities import report

    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant="tenant-fixture-a")
    _seed_legacy(store, "LD-COMMITTED", ["2850.00"], status="COMMITTED")
    _seed_legacy(store, "LD-RESERVED", ["2850.00"], status="RESERVED")
    _seed_legacy(store, "LD-UNKNOWN", ["2850.00"], status="NEEDS_VERIFICATION")
    store.close()

    out = report(str(db), tenant="tenant-fixture-a")
    by_ref = {f["logical_effect"]["load_ref"]: f["disposition"] for f in out["findings"]}
    assert by_ref["LD-COMMITTED"] == "RESOLVED_COMMITTED"
    assert by_ref["LD-RESERVED"] == "UNRESOLVED"
    assert by_ref["LD-UNKNOWN"] == "UNRESOLVED"
    assert out["write_performed"] is False


def test_two_legacy_rows_for_one_effect_are_reported_as_a_historical_double_commit(tmp_path):
    from report_legacy_commit_identities import report

    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant="tenant-fixture-a")
    _seed_legacy(store, "LD-DOUBLE", ["2850.00", "3100.00"])   # the defect's fingerprint
    store.close()

    out = report(str(db), tenant="tenant-fixture-a")
    finding = out["findings"][0]
    assert finding["disposition"] == "MANUAL_REVIEW_REQUIRED"
    assert finding["legacy_rows"] == 2
    assert sorted(finding["amounts"]) == ["2850.00", "3100.00"]


def test_the_report_is_read_only(tmp_path):
    """It classifies. It does not repair. Repair is Phase 2's backfill, with a human in the loop."""
    import hashlib

    from report_legacy_commit_identities import report

    db = tmp_path / "w.sqlite3"
    store = WorkflowStore(db, tenant="tenant-fixture-a")
    _seed_legacy(store, "LD-1", ["2850.00", "3100.00"])
    store.close()

    before = hashlib.sha256(db.read_bytes()).hexdigest()
    report(str(db), tenant="tenant-fixture-a")
    assert hashlib.sha256(db.read_bytes()).hexdigest() == before, "the dry-run report mutated the database"

    # Match SQL SHAPE, not prose. A first version searched for the bare word "DELETE" and tripped
    # over the docstring's "the DELETED amount-keyed algorithm" - a substring in a comment is not a
    # write path, and a guard that cannot tell the difference gets switched off.
    import re as _re

    source = (Path(__file__).resolve().parents[2] / "scripts"
              / "report_legacy_commit_identities.py").read_text()
    writes = _re.findall(r"\b(INSERT\s+INTO|UPDATE\s+\w+\s+SET|DELETE\s+FROM)\b", source, _re.I)
    assert not writes, f"the report has a SQL write path: {writes}"
    assert "claim_operation_commit" not in source, "the report can take a reservation"


def test_an_empty_database_reports_nothing_to_do_without_pretending_otherwise(tmp_path):
    from report_legacy_commit_identities import report

    db = tmp_path / "w.sqlite3"
    WorkflowStore(db, tenant="tenant-fixture-a").close()
    out = report(str(db), tenant="tenant-fixture-a")
    assert out["total_rows"] == 0 and out["findings"] == []
    assert out["dispositions"] == {}
