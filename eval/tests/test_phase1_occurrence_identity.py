"""Phase-1 Closure Correction — occurrence identity comes from a canonical business occurrence.

Phase 1 correctly made `record_payment`, `adjust_invoice` and `check_call` fail closed: repetition is
legitimate for each, and the only thing distinguishing two of them was the AMOUNT, which may not
carry identity. Then it handed callers `params["occurrence_key"]` to unblock them.

That was the same defect with a new name. A free-form caller string is not an identity: vary it
between retries and every attempt mints a new logical effect, so commit-once is defeated through an
arbitrary field instead of through the amount. The escape hatch is gone.

    Occurrence identity comes from a real business occurrence that already exists, is bound to the
    right entity, and belongs to this tenant — or the operation does not run.

Canonical sources, taken from the frozen specs (not invented here):

    record_payment  -> Payment Application  `payment_application_id`   (domain E34) -> P9
    adjust_invoice  -> Compensation         `compensation_id`          (entity 13)  -> P8
    check_call      -> Expectation          `expectation_id`           (entity 11)  -> P8

None of those entities exist yet, so all three stay fail closed. Where the entity is absent, these
tests assert the FAIL-CLOSED behaviour rather than faking a business entity in production code.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.commit_key import (
    CANONICAL_OCCURRENCE_SOURCES,
    CanonicalOccurrence,
    UnidentifiableEffect,
    UnresolvedCanonicalOccurrence,
    occurrence_key_for,
)
from freight_recon.operation_router import OperationRouter, _commit_reservation, freight_lanes
from freight_recon.operator_agent import OperatorAgent
from freight_recon.slack_delegate import CommandIntent, CommandKind
from freight_recon.workflow import WorkflowStore

REPEATABLE = ("record_payment", "adjust_invoice", "check_call")


class _Actuator:
    def __init__(self):
        self.calls = []

    def observe(self):
        return {"url": "https://tms.test/x", "interactive": [], "errors": []}

    def navigate(self, u): self.calls.append(("navigate", u)); return True
    def click(self, t): self.calls.append(("click", t)); return True
    def type(self, t, v): self.calls.append(("type", t, v)); return True
    def select(self, t, o): self.calls.append(("select", t, o)); return True
    def read(self, t): self.calls.append(("read", t)); return "X"


def _agent(actuator):
    def complete(_p):
        return json.dumps({"action": "CLICK", "target": "Save"})

    def build(*, approved_amount=None, approve=None, prepare_only=False):
        return OperatorAgent(actuator=actuator, complete=complete, approved_amount=approved_amount,
                             approve=approve, prepare_only=prepare_only)

    build.actuator = actuator
    return build


def _operate(summary, params):
    return CommandIntent(kind=CommandKind.OPERATE, summary=summary, params=params)


def _lane(name):
    return next(l for l in freight_lanes() if l.name == name)


def _payment_params(**extra):
    p = {"load_ref": "INV-9", "customer": "ACME"}
    p.update(extra)
    return p


# ------------------------------------------------------- 1-3: free-form cannot unblock any of them

@pytest.mark.parametrize("lane_name", REPEATABLE)
def test_1_to_3_a_free_form_occurrence_key_cannot_unblock_a_repeatable_operation(lane_name):
    """The closure. `occurrence_key` is not a field any more; supplying it changes nothing."""
    intent = _operate("do it", _payment_params(occurrence_key="anything-i-like"))
    with pytest.raises(UnresolvedCanonicalOccurrence):
        _commit_reservation("acme", "tms", _lane(lane_name), intent, "500.00")


@pytest.mark.parametrize("lane_name", REPEATABLE)
def test_1_to_3b_the_error_names_the_canonical_entity_and_the_phase_that_brings_it(lane_name):
    """Fail closed, but never mutely: say what is missing and who will build it."""
    src = CANONICAL_OCCURRENCE_SOURCES[lane_name]
    with pytest.raises(UnresolvedCanonicalOccurrence) as exc:
        occurrence_key_for(lane_name)
    msg = str(exc.value)
    assert src.entity in msg and src.field in msg and src.phase in msg


# ------------------------------------------------- 4: varying the free-form value proves nothing

def test_4_changing_the_free_form_value_between_retries_cannot_produce_a_second_effect(tmp_path):
    """THE attack the escape hatch enabled: a caller minting a fresh identity per attempt.

    Under the old code these three payloads produced three different Commit Keys and three
    reservations for one logical payment. Now all three are refused identically.
    """
    store = WorkflowStore(tmp_path / "w.sqlite3", tenant="tenant-fixture-a")
    try:
        actuator = _Actuator()
        for attempt in ("attempt-1", "attempt-2", "attempt-3"):
            result = OperationRouter(
                lanes=freight_lanes(), build_agent=_agent(actuator),
                approved_amount_for=lambda _i: "500.00", tenant="acme", commit_store=store,
            ).run(_operate("record a payment on INV-9",
                           _payment_params(occurrence_key=attempt, commit=True)),
                  approve=lambda a: True)
            assert result.status == "ESCALATED"
        rows = store.conn.execute("SELECT COUNT(*) c FROM operation_commit_claims").fetchone()["c"]
        assert rows == 0, "a caller-authored string created a reservation"
        assert actuator.calls == [], "a caller-authored string reached the TMS"
    finally:
        store.close()


# --------------------------------------------------- 5-7: payment occurrences are Payment Applications

def test_5_payment_amount_cannot_distinguish_two_payment_occurrences():
    """The amount is a material fact. Two partial payments are two Payment Applications, not two sums."""
    for amount in ("500.00", "700.00", "500.00"):
        with pytest.raises(UnresolvedCanonicalOccurrence):
            _commit_reservation("acme", "tms", _lane("record_payment"),
                                _operate("payment", _payment_params()), amount)


def test_6_two_canonical_payment_application_identities_are_two_legitimate_partial_payments():
    """The contract, at the derivation: distinct Payment Applications => distinct logical effects.

    Asserted against the canonical type rather than a lane, because Payment Application persistence
    does not exist (P9) and faking it in production to make a test pass would be the fake-oracle
    failure the acceptance rules forbid.
    """
    first = occurrence_key_for(
        "record_payment", resolved=CanonicalOccurrence("Payment Application", "pa-0001"))
    second = occurrence_key_for(
        "record_payment", resolved=CanonicalOccurrence("Payment Application", "pa-0002"))
    assert first != second, "two Payment Applications collapsed into one occurrence"
    # And the SAME Payment Application is the SAME occurrence, whatever the amount says.
    again = occurrence_key_for(
        "record_payment", resolved=CanonicalOccurrence("Payment Application", "pa-0001"))
    assert again == first


def test_7_an_external_payment_id_is_unusable_until_deterministically_bound():
    """An authoritative external transaction id only counts once it is BOUND to a Payment Application.

    Binding is an Identity Binding Claim (P7); the Payment Application itself is P9. Neither exists,
    so an external id is not an occurrence identity today - it is a string someone typed.
    """
    src = CANONICAL_OCCURRENCE_SOURCES["record_payment"]
    assert src.entity == "Payment Application"
    # An unbound external transaction, however authoritative-looking, is the WRONG entity.
    with pytest.raises(UnidentifiableEffect, match="wrong entity|needs a Payment Application"):
        occurrence_key_for("record_payment",
                           resolved=CanonicalOccurrence("External Payment Transaction", "ACH-77421"))


# --------------------------------------------------------- 8-9: adjustments are Compensations

def test_8_an_invoice_adjustment_requires_its_canonical_adjustment_identity():
    """The invoice's own identity is not enough: one invoice may take several distinct adjustments."""
    with pytest.raises(UnresolvedCanonicalOccurrence):
        _commit_reservation("acme", "tms", _lane("adjust_invoice"),
                            _operate("credit INV-9", _payment_params()), "-100.00")
    assert CANONICAL_OCCURRENCE_SOURCES["adjust_invoice"].entity == "Compensation"


def test_9_two_legitimate_adjustments_to_one_invoice_stay_distinguishable():
    first = occurrence_key_for("adjust_invoice", resolved=CanonicalOccurrence("Compensation", "cm-1"))
    second = occurrence_key_for("adjust_invoice", resolved=CanonicalOccurrence("Compensation", "cm-2"))
    assert first != second


# ------------------------------------------------------ 10-11: check calls fulfil Expectations

def test_10_a_check_call_requires_the_relevant_expectation_occurrence():
    with pytest.raises(UnresolvedCanonicalOccurrence):
        _commit_reservation("acme", "tms", _lane("check_call"),
                            _operate("log a note on LD-1", {"load_ref": "LD-1", "carrier": "C"}), None)
    assert CANONICAL_OCCURRENCE_SOURCES["check_call"].entity == "Expectation"


def test_11_a_runtime_timestamp_cannot_distinguish_check_call_effects():
    """A timestamp taken at call time is attempt-scoped: it makes every retry a new effect."""
    for stamp in ("2026-07-16T10:00:00Z", "2026-07-16T10:00:01Z"):
        with pytest.raises(UnresolvedCanonicalOccurrence):
            _commit_reservation("acme", "tms", _lane("check_call"),
                                _operate("note", {"load_ref": "LD-1", "carrier": "C",
                                                  "timestamp": stamp, "occurrence_key": stamp}), None)


# ------------------------------------------------- 12-13: wrong tenant / wrong entity fail closed

def test_12_wrong_tenant_occurrence_identity_fails_closed():
    """An occurrence belonging to another tenant is not this tenant's identity.

    Today no resolver exists, so tenant checking has nothing to resolve AGAINST and the operation
    fails closed for that reason - which is the safe outcome, and is asserted rather than assumed.
    The tenant check itself becomes real when the resolver arrives (P8/P9), and it is recorded in the
    review as that resolver's obligation. The Commit Key is already tenant-scoped regardless.
    """
    with pytest.raises(UnresolvedCanonicalOccurrence):
        _commit_reservation("tenant_b", "tms", _lane("record_payment"),
                            _operate("payment", _payment_params()), "500.00")
    # The key's own tenant scoping is intact and independent of the occurrence.
    a = occurrence_key_for("record_payment", resolved=CanonicalOccurrence("Payment Application", "pa-1"))
    assert a == occurrence_key_for("record_payment",
                                   resolved=CanonicalOccurrence("Payment Application", "pa-1"))
    from freight_recon.commit_key import LogicalEffect
    k1 = LogicalEffect("tenant_a", "record_payment", "tms", "INV-9|ACME", "record_payment", a).key()
    k2 = LogicalEffect("tenant_b", "record_payment", "tms", "INV-9|ACME", "record_payment", a).key()
    assert k1 != k2, "the same occurrence in two tenants collided"


def test_13_wrong_entity_occurrence_identity_fails_closed():
    """An Expectation is not a Payment Application. An occurrence bound to the wrong entity is noise."""
    with pytest.raises(UnidentifiableEffect, match="needs a Payment Application"):
        occurrence_key_for("record_payment", resolved=CanonicalOccurrence("Expectation", "ex-1"))
    with pytest.raises(UnidentifiableEffect, match="needs a Compensation"):
        occurrence_key_for("adjust_invoice", resolved=CanonicalOccurrence("Payment Application", "pa-1"))
    with pytest.raises(UnidentifiableEffect, match="needs an Expectation|needs a Expectation"):
        occurrence_key_for("check_call", resolved=CanonicalOccurrence("Compensation", "cm-1"))


def test_13b_an_occurrence_with_no_identifier_fails_closed():
    with pytest.raises(UnidentifiableEffect, match="carries no identifier"):
        occurrence_key_for("record_payment", resolved=CanonicalOccurrence("Payment Application", "   "))


# ------------------------------------------- 14-15: nothing reaches the TMS, nothing is reserved

@pytest.mark.parametrize("lane_name,params,amount", [
    ("record_payment", {"load_ref": "INV-9", "customer": "ACME", "commit": True}, "500.00"),
    ("adjust_invoice", {"load_ref": "INV-9", "customer": "ACME", "commit": True}, "-100.00"),
    ("check_call", {"load_ref": "LD-1", "carrier": "C", "commit": True}, None),
])
def test_14_and_15_missing_canonical_occurrence_means_zero_actuator_calls_and_no_reservation(
    tmp_path, lane_name, params, amount
):
    """The two negatives that matter: nothing happened outside, and nothing was written inside."""
    store = WorkflowStore(tmp_path / f"{lane_name}.sqlite3", tenant="tenant-fixture-a")
    try:
        actuator = _Actuator()
        result = OperationRouter(
            lanes=freight_lanes(), build_agent=_agent(actuator),
            approved_amount_for=lambda _i: amount, tenant="acme", commit_store=store,
        ).run(_operate({"record_payment": "record a payment on INV-9",
                        "adjust_invoice": "credit invoice INV-9",
                        "check_call": "log a check call on LD-1"}[lane_name], params),
              approve=lambda a: True)

        assert result.status == "ESCALATED"
        assert actuator.calls == [], f"{lane_name} reached the TMS with no canonical occurrence"
        rows = store.conn.execute("SELECT COUNT(*) c FROM operation_commit_claims").fetchone()["c"]
        assert rows == 0, f"{lane_name} reserved with no canonical occurrence"
    finally:
        store.close()


# ------------------------------------------------------------- 16-17: Phase 1 must not regress

def test_16_ac_safe_012_remains_green():
    """The amount still does not touch identity."""
    intent = _operate("invoice LD-1", {"load_ref": "LD-1", "customer": "ACME"})
    keys = {_commit_reservation("acme", "tms", _lane("raise_invoice"), intent, a)["commit_key"]
            for a in ("2850.00", "3100.00", None)}
    assert len(keys) == 1


def test_17_ac_safe_013_remains_green(tmp_path):
    """Non-money effects still get a Commit Key."""
    pod = tmp_path / "pod.pdf"
    pod.write_bytes(b"POD")
    res = _commit_reservation("acme", "tms", _lane("file_document"),
                              _operate("file the pod", {"load_ref": "LD-1", "carrier": "C"}), None,
                              document_path=str(pod))
    assert res["commit_key"] and res["approved_amount"] == ""


def test_the_lanes_that_worked_before_still_work():
    """The correction touches only the three that were already fail closed. Nothing else moved."""
    intent = _operate("invoice LD-1", {"load_ref": "LD-1", "customer": "ACME"})
    assert _commit_reservation("acme", "tms", _lane("raise_invoice"), intent, "100.00")["commit_key"]
    assert _commit_reservation("acme", "tms", _lane("record_payable"), intent, "100.00")["commit_key"]
    assert _commit_reservation("acme", "tms", _lane("create_load"), intent, None)["commit_key"]
    status = _operate("mark delivered", {"load_ref": "LD-1", "customer": "C", "status_value": "DELIVERED"})
    assert _commit_reservation("acme", "tms", _lane("update_status"), status, None)["commit_key"]
