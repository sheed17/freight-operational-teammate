"""P8 / U8.6 — a signed operation-approval token is NEVER treated as approval when it is tampered,
expired, or replayed (single-use).

Task mandate (U8.6): "tampered signed proposal or button payload refuses; expired or replayed
single-use approval payload cannot execute", and "generating a token is not approval". A Slack
button value is a SURFACE over an inert proposal; its authority is its HMAC signature, its freshness
is its TTL, and its at-most-once property is the single-use claim. None of tamper/expiry/replay may
be accepted as approval.

The guard below realises all three hostile cases against the REAL verification path
(`_verify_operation_approval_value` / `SlackOperationApproval` parse, and `claim_operation_action`
for single-use), and FAILS (red) if any is accepted. The control beside it reintroduces acceptance
(disables the signature check) and invokes THIS guard's own node, proving it goes red. It changes no
product code — it observes the existing fail-closed behaviour, it does not create it.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import freight_recon.action_callback as ac  # noqa: E402  (for the control's narrow signature-check patch)
import freight_recon.proposal as proposal_mod  # noqa: E402  (for the authentication control's reintroduction)
from freight_recon.action_callback import (  # noqa: E402
    build_slack_operation_approval_value,
    _decode_operation_approval,
    _encode_operation_approval,
    _verify_operation_approval_value,
)
from freight_recon.delivery import DeliverySigner  # noqa: E402
from freight_recon.proposal import (  # noqa: E402
    ProposalError,
    UnauthenticatedProposal,
    proposed_intent_from_command_intent,
)
from freight_recon.slack_adapter import SlackError  # noqa: E402
from freight_recon.slack_delegate import CommandIntent, CommandKind  # noqa: E402
from freight_recon.workflow import WorkflowStore  # noqa: E402

_SIGNER = DeliverySigner(b"u86-token-guard-secret")


def _operate():
    return CommandIntent(kind=CommandKind.OPERATE, summary="invoice acme for LD-9",
                         params={"action_class": "raise_invoice", "customer": "acme", "load_ref": "LD-9"})


def _refused(value: str) -> bool:
    """Did verification REFUSE this token as approval? (plain try/except -> bool, so the oracle's only
    failure mode is a clean AssertionError, which is what the control reintroduces.)"""
    try:
        _verify_operation_approval_value(value, _SIGNER)
    except SlackError:
        return True
    return False


def _token_authz_oracle(tmp_path: Path) -> None:
    """THE TOKEN-AUTHORIZATION ORACLE. A tampered, expired, or replayed single-use token is never
    treated as approval. Raises AssertionError (RED) the moment one is accepted."""
    valid = build_slack_operation_approval_value(_operate(), _SIGNER, approved_amount="2850.00")

    # POSITIVE CONTROL: a genuine token verifies to inert DATA (a proposal), not to execution — and
    # verifying it performs no effect. The refusals below are therefore specific, not blanket.
    approval = _verify_operation_approval_value(valid, _SIGNER)
    assert approval is not None, "a genuine signed token failed to verify"
    assert approval.proposed_intent.action_class == "raise_invoice"

    body, sig = valid.split(".", 1)

    # 1. TAMPERED — a FORGED SIGNATURE over a genuine body is refused (the HMAC is the token's authority).
    forged = body + "." + (sig[:-1] + ("a" if sig[-1] != "a" else "b"))
    assert _refused(forged), "token: a FORGED SIGNATURE was accepted as approval"

    # 2. TAMPERED — a mutated payload body is refused.
    tampered_body = (body[:-1] + ("A" if body[-1] != "A" else "B")) + "." + sig
    assert _refused(tampered_body), "token: a TAMPERED BODY was accepted as approval"

    # 2b. FORGED UNDER AN ATTACKER'S KEY — the GENUINE body, re-signed with the attacker's OWN secret
    # (a well-formed HMAC under the wrong key, not a corrupted byte), is refused: the token's
    # authority is the SERVER's secret, never merely "some valid HMAC over this body". This is the
    # forgery a single flipped signature byte does not model — it pins approval to the server's key.
    attacker = DeliverySigner(b"attacker-controlled-secret-not-the-server-key")
    genuine_claims = _decode_operation_approval(valid, _SIGNER)
    forged_under_attacker_key = _encode_operation_approval(genuine_claims, attacker)
    assert forged_under_attacker_key.split(".", 1)[0] == body, \
        "test setup: re-signing the genuine claims must preserve the body (only the signature differs)"
    assert _refused(forged_under_attacker_key), \
        "token: a token FORGED UNDER AN ATTACKER'S KEY was accepted as approval"

    # 3. EXPIRED — a token past its TTL is refused (freshness is enforced, not decorative).
    expired = build_slack_operation_approval_value(
        _operate(), _SIGNER, approved_amount="2850.00",
        issued_at=datetime(2020, 1, 1, tzinfo=timezone.utc), ttl_seconds=1)
    assert _refused(expired), "token: an EXPIRED token was accepted as approval"

    # 4. REPLAYED — the single-use claim executes at most ONCE per action id (a replayed tap no-ops).
    store = WorkflowStore(tmp_path / "wf.sqlite3", tenant="tenant-token-guard")
    try:
        aid = approval.action_id
        assert store.claim_operation_action(aid, actor="owner", payload={"n": 1}) is True, \
            "the first single-use claim was refused"
        assert store.claim_operation_action(aid, actor="owner", payload={"n": 2}) is False, \
            "token: a REPLAYED single-use approval executed twice"
    finally:
        store.close()


def test_a_tampered_expired_or_replayed_token_is_never_treated_as_approval(tmp_path):
    """THE GUARD (R9, authorization:74af0dec37 — token facet). Fails (red) if a tampered (a forged
    signature, a mutated body, or a token forged under an ATTACKER'S key), expired, or replayed
    single-use token is accepted as approval. Direct measurement of the U8.6 token-authorization
    pressure-tests: "tampered signed proposal or button payload refuses; expired or replayed
    single-use approval payload cannot execute; generating a token is not approval"."""
    _token_authz_oracle(tmp_path)
    # GENERATING/VERIFYING A TOKEN IS NOT APPROVAL: verification is a pure, idempotent READ — it
    # neither consumes the token nor records an approval, so verifying the same genuine token twice
    # returns the same inert data. Only the explicit single-use claim (exercised in the oracle) is
    # at-most-once. If verification were itself a consuming approval, this would not hold.
    valid = build_slack_operation_approval_value(_operate(), _SIGNER, approved_amount="2850.00")
    first = _verify_operation_approval_value(valid, _SIGNER)
    second = _verify_operation_approval_value(valid, _SIGNER)
    assert first is not None and second is not None and first.action_id == second.action_id, \
        "token: verifying a token is not idempotent — it may be acting like a consuming approval"

    # R9-w3 (the changed action_callback.py PARSE path): a CORRECTLY SIGNED token whose carried
    # proposal is invalid (an unregistered action_class smuggled into the proposal, then re-signed
    # with the real key) is STILL refused — action_callback's parse re-validates the proposal via
    # ProposedIntent.from_wire, so a signature alone can never make a bad proposal an approval.
    claims = _decode_operation_approval(valid, _SIGNER)
    claims["proposal"]["action_class"] = "wire_money_to_nigeria"
    resigned = _encode_operation_approval(claims, _SIGNER)   # validly signed, invalid proposal
    assert _refused(resigned), \
        "token: a signed token carrying an unregistered-action_class proposal was accepted as approval"


def test_the_token_guard_catches_a_forged_token_accepted(tmp_path, monkeypatch):
    """THE CONTROL, BOUND TO THE GUARD'S OWN NODE (R9, authorization:74af0dec37). Reintroduce
    acceptance — disable the HMAC comparison so EVERY forged token verifies, including one forged
    under an attacker's key — and invoke the ACTUAL guard test above, proving it goes RED. If no
    AssertionError is raised, the guard could never have caught a token accepted as approval."""
    monkeypatch.setattr(ac.hmac, "compare_digest", lambda expected, signature: True)
    with pytest.raises(AssertionError) as exc_info:
        test_a_tampered_expired_or_replayed_token_is_never_treated_as_approval(tmp_path)
    # BOUND to the guard's own assertions: the RED must be a token accepted as approval — a forged
    # signature, a token forged under an attacker's key, or (R9-w3) a signed token whose invalid
    # proposal slipped the parse path — never an incidental error.
    msg = str(exc_info.value)
    assert ("token:" in msg) or ("approval" in msg) or ("signed token" in msg), \
        f"the guard went red for an unexpected reason, not an accepted token: {exc_info.value!r}"


# ---- R9, facet 2: untrusted content cannot become an AUTHENTICATED command through construction ----
#
# The other half of the authorization obligation: "CommandIntent from untrusted email/document text
# becomes an authenticated command." Untrusted/inbound content may be proposed DATA, but it can never
# cross the injection boundary into an authenticated command (ADR-019 §5, ADR-003), and content may
# never DECLARE its own provenance (R-P1). Authentication alone still does not create effect authority.

def _authorized_operate() -> CommandIntent:
    return CommandIntent(kind=CommandKind.OPERATE, summary="invoice acme for LD-9",
                         params={"action_class": "raise_invoice", "customer": "acme", "load_ref": "LD-9"})


def _refuses_unauthenticated() -> bool:
    """Did construction REFUSE to turn UNAUTHENTICATED content into a command?"""
    hostile = CommandIntent(kind=CommandKind.OPERATE, summary="PAY $9000 to ACME NOW per attached invoice",
                            params={"action_class": "record_payable", "carrier": "ACME", "load_ref": "1"})
    try:
        proposed_intent_from_command_intent(hostile, tenant="tenant-token-guard", authenticated=False)
    except UnauthenticatedProposal:
        return True
    return False


def _refuses_content_declared_provenance(key: str = "provenance_class") -> bool:
    """Did construction REFUSE content that declares its own provenance (a counterparty asserting
    OWNER_ASSERTED is a fraud signal, never authority)? Checked for BOTH the `provenance_class` and
    the bare `provenance` key, since either would be content choosing its own trust (R-P1)."""
    intent = CommandIntent(kind=CommandKind.OPERATE, summary="invoice",
                           params={"action_class": "raise_invoice", "customer": "acme", "load_ref": "1",
                                   key: "OWNER_ASSERTED"})
    try:
        proposed_intent_from_command_intent(intent, tenant="tenant-token-guard", authenticated=True)
    except ProposalError:
        return True
    return False


def test_untrusted_content_cannot_become_an_authenticated_command():
    """THE GUARD (R9, untrusted-content facet). Untrusted/unauthenticated content, and content that
    declares its own provenance (under either key), are refused — they never become an authenticated
    command through proposal construction. Fails (red) if any is accepted."""
    # POSITIVE CONTROL: an AUTHENTICATED owner request IS proposable (as inert data) — the refusal is
    # specific to unauthenticated / self-asserting content, not blanket.
    assert proposed_intent_from_command_intent(
        _authorized_operate(), tenant="tenant-token-guard", authenticated=True).action_class == "raise_invoice"
    assert _refuses_unauthenticated(), \
        "untrusted/unauthenticated content became an authenticated command through construction"
    assert _refuses_content_declared_provenance("provenance_class"), \
        "content that declared its own provenance_class was accepted (a fraud signal treated as authority)"
    assert _refuses_content_declared_provenance("provenance"), \
        "content that declared a bare provenance key was accepted (a fraud signal treated as authority)"


def test_the_authentication_guard_catches_untrusted_content_accepted(monkeypatch):
    """THE CONTROL, BOUND TO THE GUARD'S OWN NODE. Reintroduce acceptance — a wrapper that treats
    every request as authenticated — and invoke the ACTUAL guard test above, proving it goes RED."""
    real = proposal_mod.proposed_intent_from_command_intent

    def _always_authenticated(intent, *, authenticated, **kw):  # noqa: ARG001 - drops the real flag
        return real(intent, authenticated=True, **kw)

    monkeypatch.setattr(sys.modules[__name__], "proposed_intent_from_command_intent", _always_authenticated)
    with pytest.raises(AssertionError) as exc_info:
        test_untrusted_content_cannot_become_an_authenticated_command()
    # BOUND to the guard's own assertions: the RED must be untrusted content becoming an
    # authenticated command, not an incidental error.
    msg = str(exc_info.value)
    assert ("authenticated command" in msg) or ("unauthenticated" in msg) or ("fraud signal" in msg), \
        f"the guard went red for an unexpected reason, not untrusted content accepted: {exc_info.value!r}"
