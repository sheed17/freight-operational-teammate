"""AC-SAFE-012 and AC-SAFE-013 — THE MIGRATION GUARDS. GREEN as of Phase 1 (Migration Safety Task #1).

These ran and FAILED for the whole of Phase 0, by design, as `strict` xfails named in CI. Phase 1
made the production behaviour satisfy them, so they are now ordinary passing tests. Nothing about
their oracle was softened to get here: the assertions below are the frozen ones, and they are checked
against the REAL router driving a REAL reservation store, counting REAL actuator calls — not against
a stub that agrees with itself.

THE DEFECT THEY EXIST FOR (deleted in Phase 1):

    def _commit_identity(tenant, lane, intent, amount):
        if not amount:
            return None                                    # (B) non-money => NO identity at all
        ...
        return {..., "approved_amount": normalize_money_amount(amount)}   # (A) AMOUNT IN THE IDENTITY

  (A) The amount was part of the effect's identity, so approving GBP 2,850 and then GBP 3,100 for the
      SAME invoice produced two different keys, two reservations, and TWO INVOICES. A re-read of one
      invoice at a corrected figure was indistinguishable from a second invoice.
  (B) A non-money effect — filing a POD — got no identity, and `will_commit` skipped the reservation
      path for it entirely, so filing the same POD twice attached it twice and nothing could notice.

FORWARD-ONLY: `operation_commit_key` is deleted, and `LogicalEffect` has no field an amount could
occupy. Restoring either defect fails this file.
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freight_recon.commit_key import LogicalEffect, UnidentifiableEffect, occurrence_key_for
from freight_recon.operation_router import OperationRouter, _commit_reservation, freight_lanes
from freight_recon.operator_agent import OperatorAgent
from freight_recon.slack_delegate import CommandIntent, CommandKind
from freight_recon.workflow import WorkflowStore
from phase0 import manifest


class _CountingActuator:
    """The negative oracle: every external call is recorded, so 'it did not happen twice' is proved."""

    def __init__(self):
        self.calls = []

    def observe(self):
        return {"url": "https://tms.test/x", "interactive": [], "errors": []}

    def navigate(self, url): self.calls.append(("navigate", url)); return True
    def click(self, target): self.calls.append(("click", target)); return True
    def type(self, target, value): self.calls.append(("type", target, value)); return True
    def select(self, target, option): self.calls.append(("select", target, option)); return True
    def read(self, target): self.calls.append(("read", target)); return "INV-4912"

    @property
    def commits(self):
        return [c for c in self.calls if c[0] == "click" and "save" in str(c[1]).lower()]


def _agent_factory(actuator):
    def complete(_prompt):
        if not actuator.commits:
            return json.dumps({"action": "CLICK", "target": "Save invoice"})
        return json.dumps({"action": "DONE", "why": "saved"})

    def build_agent(*, approved_amount=None, approve=None, prepare_only=False):
        return OperatorAgent(actuator=actuator, complete=complete, approved_amount=approved_amount,
                             approve=approve, prepare_only=prepare_only)

    build_agent.actuator = actuator
    return build_agent


def _operate(summary, params):
    return CommandIntent(kind=CommandKind.OPERATE, summary=summary, params=params)


def _lane(name):
    return next(l for l in freight_lanes() if l.name == name)


# ------------------------------------------------------------------ AC-SAFE-012 (FINANCIAL_CORRECTNESS)

def test_ac_safe_012_commit_key_excludes_mutable_decision_values():
    """AC-SAFE-012, at the derivation: two proposals at GBP 2,850 and GBP 3,100 => IDENTICAL key.

    Frozen oracle (platform-safety-acceptance.md): "two proposals at £2,850 and £3,100 => IDENTICAL
    commit_key => exactly ONE invoice".
    """
    intent = _operate("invoice LD-560010", {"load_ref": "LD-560010", "customer": "ACME"})
    at_2850 = _commit_reservation("tenant_a", "tms", _lane("raise_invoice"), intent, "2850.00")
    at_3100 = _commit_reservation("tenant_a", "tms", _lane("raise_invoice"), intent, "3100.00")

    assert at_2850["commit_key"] == at_3100["commit_key"], (
        "AC-SAFE-012 VIOLATED: changing the approved amount changed the identity of the effect."
    )
    # And the amount is NOT discarded — it is carried as a material fact, where drift can be seen.
    assert at_2850["approved_amount"] == "2850.00"
    assert at_3100["approved_amount"] == "3100.00"


def test_ac_safe_012_end_to_end_two_amounts_raise_exactly_one_invoice(tmp_path):
    """The real oracle, at the real boundary: ONE invoice, proved by the actuator's call log.

    A local write is never an oracle for an external effect — so this asserts on the external calls.
    """
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        actuator = _CountingActuator()
        params = {"load_ref": "LD-560010", "customer": "ACME", "commit": True}

        first = OperationRouter(
            lanes=freight_lanes(), build_agent=_agent_factory(actuator),
            approved_amount_for=lambda _i: "2850.00", tenant="tenant_a", commit_store=store,
        ).run(_operate("invoice LD-560010", params), approve=lambda a: True)

        commits_after_first = len(actuator.commits)

        # The SAME logical invoice, re-read at a different figure. Under the defect this was a
        # different key and committed again. It must now converge and refuse.
        second = OperationRouter(
            lanes=freight_lanes(), build_agent=_agent_factory(actuator),
            approved_amount_for=lambda _i: "3100.00", tenant="tenant_a", commit_store=store,
        ).run(_operate("invoice LD-560010", params), approve=lambda a: True)

        assert first.status in ("DONE", "ESCALATED")
        assert commits_after_first >= 1, "the first attempt never reached a committing click"
        assert len(actuator.commits) == commits_after_first, (
            "AC-SAFE-012 VIOLATED: a second invoice was committed for the same logical effect "
            "because the amount differed"
        )
        assert second.status == "DONE" and "refusing to repeat" in second.note.lower()
        rows = store.conn.execute("SELECT COUNT(*) c FROM operation_commit_claims").fetchone()["c"]
        assert rows == 1, f"exactly one reservation must exist for one logical effect; found {rows}"
    finally:
        store.close()


# ------------------------------------------------------------------------ AC-SAFE-013 (DATA_INTEGRITY)

def test_ac_safe_013_commit_key_exists_for_non_money_effects(tmp_path):
    """AC-SAFE-013: a non-money effect HAS a Commit Key. It used to get None."""
    pod = tmp_path / "pod.pdf"
    pod.write_bytes(b"%PDF-1.4 proof of delivery")
    intent = _operate("file the POD on LD-560010", {"load_ref": "LD-560010", "carrier": "ACME"})

    reservation = _commit_reservation(
        "tenant_a", "tms", _lane("file_document"), intent, None, document_path=str(pod)
    )
    assert reservation is not None
    assert reservation["commit_key"], "AC-SAFE-013 VIOLATED: a non-money effect received no key"
    assert reservation["approved_amount"] == ""      # no money, and that is not an excuse for no key


def test_ac_safe_013_filing_the_same_pod_twice_attaches_it_once(tmp_path):
    """Frozen oracle: "filing the same POD twice => one attachment; no second upload"."""
    store = WorkflowStore(tmp_path / "w.sqlite3")
    try:
        pod = tmp_path / "pod.pdf"
        pod.write_bytes(b"%PDF-1.4 proof of delivery")
        actuator = _CountingActuator()
        params = {"load_ref": "LD-560010", "carrier": "ACME", "commit": True}

        def router():
            return OperationRouter(
                lanes=freight_lanes(), build_agent=_agent_factory(actuator),
                document_for=lambda _i: str(pod), tenant="tenant_a", commit_store=store,
            )

        first = router().run(_operate("file the pod on LD-560010", params), approve=lambda a: True)
        calls_after_first = len(actuator.calls)
        second = router().run(_operate("file the pod on LD-560010", params), approve=lambda a: True)

        assert len(actuator.calls) == calls_after_first, (
            "AC-SAFE-013 VIOLATED: the same POD was uploaded a second time"
        )
        assert second.status == "DONE" and "refusing to repeat" in second.note.lower()
        rows = store.conn.execute("SELECT COUNT(*) c FROM operation_commit_claims").fetchone()["c"]
        assert rows == 1, f"one POD filing = one reservation; found {rows}"
        assert first.status in ("DONE", "ESCALATED")
    finally:
        store.close()


def test_a_different_document_on_the_same_load_is_a_different_effect(tmp_path):
    """The control: commit-once must not become commit-never. A BOL is not the POD."""
    pod, bol = tmp_path / "pod.pdf", tmp_path / "bol.pdf"
    pod.write_bytes(b"POD bytes")
    bol.write_bytes(b"BOL bytes")
    intent = _operate("file", {"load_ref": "LD-1", "carrier": "ACME"})
    a = _commit_reservation("t", "tms", _lane("file_document"), intent, None, document_path=str(pod))
    b = _commit_reservation("t", "tms", _lane("file_document"), intent, None, document_path=str(bol))
    assert a["commit_key"] != b["commit_key"], "two different documents collapsed into one effect"


# ------------------------------------------------------------------------------ forward-only guards

def test_the_defective_derivation_is_deleted_not_deprecated():
    """Forward-only: no second key namespace may exist to authorize anything."""
    with pytest.raises(ImportError):
        from freight_recon.workflow import operation_commit_key  # noqa: F401
    source = (Path(__file__).resolve().parents[2] / "src" / "freight_recon" / "workflow.py").read_text()
    assert "def operation_commit_key(" not in source


def test_the_amount_cannot_be_readded_to_the_key_without_breaking_the_type():
    with pytest.raises(TypeError):
        LogicalEffect(
            tenant="t", action_class="raise_invoice", target_system="tms",
            target_resource_id="LD-1|ACME", target_operation="raise_invoice",
            occurrence_key="", approved_amount="2850.00",   # type: ignore[call-arg]
        )


def test_a_consequential_effect_without_identity_fails_closed_and_never_returns_none():
    """No None, no UUID, no request id, no timestamp. It raises, and the router escalates."""
    intent = _operate("invoice", {"customer": "ACME"})      # no load reference
    with pytest.raises(UnidentifiableEffect):
        _commit_reservation("t", "tms", _lane("raise_invoice"), intent, "100.00")


def test_a_new_consequential_operation_without_an_occurrence_rule_fails_closed():
    """A new lane must declare whether repetition is legitimate before it may ever run."""
    with pytest.raises(UnidentifiableEffect, match="declares no occurrence rule"):
        occurrence_key_for("some_brand_new_lane")


def test_both_guards_are_registered_as_green_with_the_unit_that_fixed_them():
    failures = manifest.expected_failures()
    assert failures["AC-SAFE-012"] == "GREEN_AT_P1"
    assert failures["AC-SAFE-013"] == "GREEN_AT_P1"
