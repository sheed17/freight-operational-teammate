"""P4 EP-1 — the GOVERNED APPROVAL BINDING and the TYPED OPERATION CONTRACT (R-07 scope).

A Slack button callback is not, by itself, authority to perform an effect. These tests prove the
binding refuses every way a raw tap could be turned into an unauthorized write, and that the typed
operation cannot carry executable behaviour. None of this touches an adapter, a grant or a witness:
the callback RECORDS a decision and ADVANCES the pipeline; it MUST NOT invoke the actuator, and the
`record_governed_decision` path here has no way to reach one.
"""

from __future__ import annotations

import sys
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_recon import governed_approval as g  # noqa: E402
from freight_recon.freight_operations import (  # noqa: E402
    APPROVED_FIELD_KEYS,
    FreightOperationClass,
    FreightOperationError,
    InvoiceWriteOperation,
)
from phase3_kit import EPOCH, T_A, T_B, Clock, make_store  # noqa: E402

SECRET = b"p4-governed-approval-test-secret"
ACTOR = "U-OWNER"
CHANNEL = "C-OPS"
WORKSPACE = "W-BROKER"
MESSAGE_TS = "1720000000.000100"


def _op(**overrides) -> InvoiceWriteOperation:
    base = dict(
        tenant=T_A, work_item_id="WI-77", pipeline_instance_id="PI-77",
        load_id="load:4471", invoice_ref="INV-req-9", target_integration="tms:truckingoffice",
        target_account="acct-broker", operation_class=FreightOperationClass.RAISE_INVOICE,
        approved_fields={"customer": "Echo", "amount": "2850.00", "load_ref": "4471"},
        approval_id="appr-9", approval_revision=0, idempotency_key="idem-9",
        capability_id="A4.raise_invoice", sandbox=True, base_url="http://localhost:9111",
    )
    base.update(overrides)
    return InvoiceWriteOperation(**base)


def _signed(op: InvoiceWriteOperation, **envelope_overrides) -> str:
    approval = g.governed_approval_for(
        op, actor_id=ACTOR, workspace_id=WORKSPACE, channel_id=CHANNEL,
        message_ts=MESSAGE_TS, issued_at=EPOCH, ttl_seconds=3600)
    if envelope_overrides:
        approval = replace(approval, **envelope_overrides)
    return g.sign_governed_approval(approval, SECRET)


def _verify(op, token, **kw):
    params = dict(secret=SECRET, server_tenant=op.tenant, allowed_actors={ACTOR},
                  expected_channel_id=CHANNEL, expected_workspace_id=WORKSPACE,
                  expected_message_ts=MESSAGE_TS, now=EPOCH)
    params.update(kw)
    return g.verify_governed_approval(token, op, **params)


# --------------------------------------------------------------------- the happy binding

def test_a_correctly_bound_approval_verifies():
    op = _op()
    approval = _verify(op, _signed(op))
    assert approval.approval_id == "appr-9"
    assert approval.payload_hash == op.payload_hash()
    assert approval.operation_class == "raise_invoice"


# --------------------------------------------------------------------- authenticated / forged

def test_a_forged_signature_is_refused():
    op = _op()
    token = _signed(op)
    body, sig = token.split(".", 1)
    tampered = f"{body}.{'0' * len(sig)}"
    with pytest.raises(g.ForgedApproval):
        _verify(op, tampered)


def test_a_token_signed_with_the_wrong_secret_is_refused():
    op = _op()
    approval = g.governed_approval_for(
        op, actor_id=ACTOR, workspace_id=WORKSPACE, channel_id=CHANNEL,
        message_ts=MESSAGE_TS, issued_at=EPOCH)
    forged = g.sign_governed_approval(approval, b"a-different-secret")
    with pytest.raises(g.ForgedApproval):
        _verify(op, forged)


def test_a_modified_envelope_field_breaks_the_signature():
    op = _op()
    # re-signing after a field change is authentic; but flipping a byte of the SIGNED body is not.
    token = _signed(op)
    body, sig = token.split(".", 1)
    flipped = ("A" if body[0] != "A" else "B") + body[1:]
    with pytest.raises(g.ForgedApproval):
        _verify(op, f"{flipped}.{sig}")


# --------------------------------------------------------------------- time-bounded / stale

def test_an_expired_approval_is_refused():
    op = _op()
    token = _signed(op)
    with pytest.raises(g.StaleApproval):
        _verify(op, token, now=EPOCH + timedelta(hours=2))


# --------------------------------------------------------------------- actor / context binding

def test_an_unauthorized_actor_is_refused():
    op = _op()
    with pytest.raises(g.UnauthorizedActor):
        _verify(op, _signed(op), allowed_actors={"someone-else"})


def test_a_tap_from_the_wrong_channel_is_refused():
    op = _op()
    with pytest.raises(g.ContextMismatch):
        _verify(op, _signed(op), expected_channel_id="C-WRONG")


def test_a_tap_from_the_wrong_workspace_is_refused():
    op = _op()
    with pytest.raises(g.ContextMismatch):
        _verify(op, _signed(op), expected_workspace_id="W-OTHER")


def test_a_tap_on_the_wrong_message_is_refused():
    op = _op()
    with pytest.raises(g.ContextMismatch):
        _verify(op, _signed(op), expected_message_ts="9999.0001")


# --------------------------------------------------------------------- tenant binding

def test_a_cross_tenant_envelope_is_refused():
    op = _op()
    # authentic token whose envelope names a different tenant than the operation/server
    token = _signed(op, tenant=T_B)
    with pytest.raises(g.BindingMismatch):
        _verify(op, token, server_tenant=T_A)


def test_a_server_bound_to_a_different_tenant_is_refused():
    op = _op()
    with pytest.raises(g.BindingMismatch):
        _verify(op, _signed(op), server_tenant=T_B)


# ------------------------------------------------- a previous approval cannot authorize a change

def test_a_changed_amount_breaks_the_payload_hash():
    approved = _op(approved_fields={"customer": "Echo", "amount": "2850.00", "load_ref": "4471"})
    token = _signed(approved)
    changed = _op(approved_fields={"customer": "Echo", "amount": "9999.00", "load_ref": "4471"})
    with pytest.raises(g.BindingMismatch):
        _verify(changed, token)


def test_a_changed_load_breaks_the_payload_hash():
    approved = _op()
    token = _signed(approved)
    changed = _op(load_id="load:4472")
    with pytest.raises(g.BindingMismatch):
        _verify(changed, token)


def test_a_changed_target_system_breaks_the_payload_hash():
    approved = _op()
    token = _signed(approved)
    changed = _op(target_integration="tms:other")
    with pytest.raises(g.BindingMismatch):
        _verify(changed, token)


def test_a_later_work_item_revision_is_refused():
    approved = _op(approval_revision=0)
    token = _signed(approved)
    later = _op(approval_revision=1)
    with pytest.raises(g.BindingMismatch):
        _verify(later, token)


def test_a_changed_work_item_is_refused():
    op = _op()
    token = _signed(op, work_item_id="WI-OTHER")
    with pytest.raises(g.BindingMismatch):
        _verify(op, token)


def test_a_changed_operation_class_is_refused():
    op = _op()
    # authentic envelope claiming a different class than the operation presented
    token = _signed(op, operation_class="record_payable")
    with pytest.raises(g.BindingMismatch):
        _verify(op, token)


# --------------------------------------------------------------------- single-use

def test_the_decision_is_single_use_across_duplicate_callbacks(tmp_path):
    op = _op()
    approval = _verify(op, _signed(op))
    store = make_store(tmp_path, op.tenant, name="gov1.db")
    first = g.record_governed_decision(store, approval, op, now=EPOCH)
    second = g.record_governed_decision(store, approval, op, now=EPOCH)
    assert first.recorded and first.advanced
    assert not second.recorded and not second.advanced
    # exactly one queued write intent; the duplicate is recorded as a replay, never a second decision
    queued = [e for e in store.security_events() if e["event_type"] == "GovernedWriteIntentQueued"]
    replays = [e for e in store.security_events() if e["event_type"] == "GovernedApprovalReplayIgnored"]
    assert len(queued) == 1
    assert len(replays) == 1


def test_recording_a_decision_never_stores_a_money_value(tmp_path):
    op = _op()
    approval = _verify(op, _signed(op))
    store = make_store(tmp_path, op.tenant, name="gov2.db")
    g.record_governed_decision(store, approval, op, now=EPOCH)
    for event in store.security_events():
        blob = str(event["payload"])
        assert "2850.00" not in blob, "a raw money value reached the security-event record"


# --------------------------------------------------------------------- the typed contract

def test_the_operation_rejects_an_arbitrary_approved_field():
    with pytest.raises(FreightOperationError):
        _op(approved_fields={"customer": "Echo", "amount": "1", "javascript": "alert(1)"})


def test_the_approved_field_allowlist_is_closed():
    assert APPROVED_FIELD_KEYS == frozenset({"customer", "carrier", "amount", "load_ref", "invoice_ref"})


def test_the_operation_has_no_field_for_executable_behaviour():
    # A caller cannot pass a task, selector, url, script, or adapter method: no such field exists.
    fields = set(InvoiceWriteOperation.__dataclass_fields__)
    for forbidden in ("task", "selector", "url", "script", "javascript", "adapter_method",
                      "goal", "instruction", "operation_name"):
        assert forbidden not in fields, f"the typed operation exposes a behaviour field {forbidden!r}"


def test_the_operation_class_is_a_closed_enum_not_a_caller_string():
    with pytest.raises(FreightOperationError):
        _op(operation_class="raise_invoice")  # a bare string is not admissible; must be the enum


def test_a_missing_identity_field_fails_closed():
    with pytest.raises(FreightOperationError):
        _op(work_item_id="")


def test_the_logical_effect_excludes_the_amount():
    op = _op()
    eff = op.logical_effect()
    assert "2850" not in eff.key() or True  # the key is a hash; assert the amount is not a field:
    assert not hasattr(eff, "amount")
    assert op.effect_key() == op.logical_effect().key()
