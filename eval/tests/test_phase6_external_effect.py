"""M3 — the External Effect / Effect Grant — acceptance and hostile battery.

Organised by RISK, not by transition id, because what matters is not that the happy path works but
what the machine REFUSES: whether a broker can be billed twice, whether a forged handle can act,
whether "we do not know" is ever quietly allowed to become "it failed".

    A  the transition table is the specification's, not a story about it   (AC-MACH-301..313)
    B  mint requires REAL checkpoint authority                             (EF-1)
    C  the claim CAS admits exactly one winner                             (EF-2 / EF-2f)
    D  EffectAttempted exists before the world, exactly once               (EF-2 / EF-3)
    E  FAILED requires proof; timeout / crash / lost is UNKNOWN            (EF-3f / EF-3u)
    F  VERIFIED requires a healthy match; blind is not failed              (EF-4 / EF-4c / EF-4u)
    G  UNKNOWN_OUTCOME is human-owned and no timer moves it                (EF-3u / EF-5 / EF-5x)
    H  REVOKED is not EXPIRED_UNCLAIMED                                    (EF-2r / EF-2x)
    I  a brake between mint and claim makes the CAS match zero rows        (§30)
    J  the strict-order consumer: idempotency, park, drain, predecessor    (P6-D24 / P6-D11)
    K  replay produces zero effects; tenant isolation; it ships dark       (GR-11 / [C-1])
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "eval" / "tests"))

import phase3_kit as p3  # noqa: E402
import phase6_effect_kit as kit  # noqa: E402

from freight_recon.brake import BrakeStore  # noqa: E402
from freight_recon.checkpoint import ClaimParams, EffectGrantHandle  # noqa: E402
from freight_recon.event_contracts import CONTRACTS  # noqa: E402
from freight_recon.external_effect import (  # noqa: E402
    PRODUCED_CONTRACTS,
    TRANSITIONS,
    EffectGrantState,
    ExternalEffectMachine,
    GuardNotSatisfied,
    IllegalTransition,
    OwnershipRefused,
    StateConflict,
    Trigger,
)
from freight_recon.migrations.phase6_external_effects import (  # noqa: E402
    EF_STATES,
    EF_TERMINAL_STATES,
)

MACHINE_SPEC = ROOT / "docs/specifications/state-machines/03-external-effect-grant.machine.md"
T_A, T_B = kit.T_A, kit.T_B
OWNER = kit.OWNER


# ============================================================ A. the table IS the specification's

def _spec_transition_ids() -> set[str]:
    """The EF-* identifiers of §14, parsed out of the machine file's transition table."""
    text = MACHINE_SPEC.read_text(encoding="utf-8")
    section = text.split("## 14.")[1].split("## 15.")[0]
    ids = set(re.findall(r"\*\*(EF-[0-9]+[a-z]*)\*\*", section))
    return ids


def test_the_spec_parser_is_not_vacuous():
    ids = _spec_transition_ids()
    assert len(ids) >= 13, f"the §14 parser found only {ids}; it proves nothing"
    assert "EF-1" in ids and "EF-5x" in ids


def test_the_transition_identifiers_are_a_bijection_with_the_specification():
    assert {row.id for row in TRANSITIONS} == _spec_transition_ids(), (
        "the implemented transition ids differ from §14 — a renamed or dropped row is a machine that "
        "is not the one the specification describes")


def test_the_state_set_is_exactly_the_registrys_eight():
    assert {s.value for s in EffectGrantState} == set(EF_STATES)
    assert len(EF_STATES) == 8


def test_the_terminal_set_is_exactly_the_four_and_unknown_is_not_among_them():
    assert set(EF_TERMINAL_STATES) == {"VERIFIED", "FAILED", "EXPIRED_UNCLAIMED", "REVOKED"}
    assert "UNKNOWN_OUTCOME" not in EF_TERMINAL_STATES, (
        "UNKNOWN_OUTCOME is non-terminal and human-owned; reading it as terminal is how 'we do not "
        "know' gets laundered into a closed ledger")


def test_every_produced_contract_names_its_transition_as_a_producer():
    for row in TRANSITIONS:
        for event_name in row.events:
            contract = CONTRACTS[event_name]
            assert row.id in contract.producers, (
                f"{row.id} emits {event_name} but the canonical contract does not name it a "
                f"producer — the contract gate would refuse the envelope")


def test_the_produced_set_matches_the_table():
    assert PRODUCED_CONTRACTS == {ev for row in TRANSITIONS for ev in row.events}
    # The five capability/lifecycle events plus the outcome events; VerificationDeferred is PL-11d's
    # (M2), not M3's, and is correctly absent.
    assert "VerificationDeferred" not in PRODUCED_CONTRACTS


# ============================================================ B. mint requires real authority (EF-1)

def test_a_green_mint_produces_a_grant_and_one_EffectGranted(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint = scn.mint()
    assert mint.authorized and mint.grant_id
    assert scn.m3.require(mint.grant_id).state is EffectGrantState.GRANTED
    assert kit.count_event(scn.store, "EffectGranted") == 1
    granted = kit.effect_grant_events(scn.store)[0]
    assert granted["event_name"] == "EffectGranted" and granted["producer"] == "EF-1"
    # EF-1 is CONSEQUENTIAL: it pins the decision context from the witness, not from today's state.
    assert granted["payload"]["checkpoint_id"] == scn.m3.require(mint.grant_id).checkpoint_id
    assert granted["payload"]["policy_version"]


def test_mint_requires_the_kernel(tmp_path):
    scn = kit.Scenario(tmp_path)
    naked = ExternalEffectMachine(scn.store.conn, tenant=scn.store.tenant, clock=scn.clock)
    with pytest.raises(GuardNotSatisfied, match="kernel"):
        naked.mint(scn.request, scn.inputs, actor_id="x")


def test_a_refused_checkpoint_mints_no_grant_and_emits_no_EffectGranted(tmp_path):
    # A brake engaged before the checkpoint makes step 7 refuse: nothing is minted, all-or-nothing.
    scn = kit.Scenario(tmp_path)
    BrakeStore(scn.store.conn).engage(
        tenant=scn.store.tenant, action_class=scn.effect.action_class, actor="ops-lead",
        actor_kind="HUMAN", reason="pause all outbound while we investigate")
    mint = scn.mint()
    assert not mint.authorized and mint.refusal is not None
    assert kit.count_event(scn.store, "EffectGranted") == 0
    assert kit.ledger(scn.store) == [], "a refused checkpoint left a grant row behind"


def test_a_grant_cannot_be_minted_across_a_tenant(tmp_path):
    scn = kit.Scenario(tmp_path, tenant=T_A)
    # A machine bound to tenant B cannot mint tenant A's effect.
    other = ExternalEffectMachine(scn.store.conn, tenant=T_B, kernel=scn.kernel, clock=scn.clock)
    with pytest.raises(Exception):
        other.mint(scn.request, scn.inputs, actor_id="x")


# ============================================================ C. the claim CAS — exactly one winner

def test_two_claims_on_one_grant_leave_exactly_one_CLAIMED(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint = scn.mint()
    c1 = scn.m3.claim(mint.handle, scn.params, actor_id="w1", attempt_id="a1")
    c2 = scn.m3.claim(mint.handle, scn.params, actor_id="w2", attempt_id="a2")
    assert c1.claimed and not c2.claimed
    assert c2.cause == "ALREADY_CLAIMED"
    rows = scn.store.conn.execute(
        "SELECT COUNT(*) FROM effect_grants WHERE state = 'CLAIMED'").fetchone()[0]
    assert rows == 1, "ONE WINNER, NEVER TWO — a second claim created a second CLAIMED row"
    # EF-2f recorded the loser's refusal as ClaimRefused, mapped to the CAS cause.
    refused = [e for e in kit.effect_grant_events(scn.store) if e["event_name"] == "ClaimRefused"]
    assert len(refused) == 1 and refused[0]["payload"]["cause"] == "already_claimed"


def test_a_replayed_handle_second_claim_matches_zero_rows(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint = scn.mint()
    scn.m3.claim(mint.handle, scn.params, actor_id="w1")
    # The SAME signed handle presented again: the CAS finds the row not-GRANTED and does nothing.
    replayed = scn.m3.claim(mint.handle, scn.params, actor_id="w2")
    assert not replayed.claimed
    assert scn.m3.require(mint.grant_id).state is EffectGrantState.CLAIMED


def test_a_forged_handle_names_no_row_and_is_a_sev0_not_a_ClaimRefused(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint = scn.mint()
    forged = EffectGrantHandle(
        tenant=scn.store.tenant, grant_id="not-a-real-grant", token="deadbeef",
        signature=scn.kernel.sign("deadbeef"))
    result = scn.m3.claim(forged, scn.params, actor_id="attacker")
    assert not result.claimed
    # A forged/no-row handle is a Sev-0 the KERNEL records; EF-2f does NOT mint a ClaimRefused for it
    # — laundering an attack into an ordinary refusal is exactly what the distinct records prevent.
    assert result.claim_refused_event_id is None
    assert kit.count_event(scn.store, "ClaimRefused") == 0
    assert scn.m3.require(mint.grant_id).state is EffectGrantState.GRANTED


def test_a_wrong_target_claim_is_a_confused_deputy_sev0(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint = scn.mint()
    wrong = ClaimParams(
        tenant=scn.store.tenant, action_class=scn.effect.action_class,
        target_system=scn.effect.target_system, target_resource_id="load:OTHER",
        target_operation=scn.effect.target_operation)
    result = scn.m3.claim(mint.handle, wrong, actor_id="deputy")
    assert not result.claimed and result.cause == "CONFUSED_DEPUTY"
    assert result.claim_refused_event_id is None, "a confused-deputy claim minted an ordinary refusal"
    assert scn.m3.require(mint.grant_id).state is EffectGrantState.GRANTED


def test_a_retry_is_a_new_grant_never_a_re_claim(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint = scn.mint()
    scn.m3.claim(mint.handle, scn.params, actor_id="w1")
    # The claimed grant holds the commit key (Layer-2 live-hold): a second mint of the SAME logical
    # effect is refused at the ledger, so a retry cannot re-claim — it must be a NEW grant from a NEW
    # checkpoint, which is impossible while the first still holds the key.
    retry = scn.mint()
    assert not retry.authorized, "a second grant was minted for a commit key already held"
    assert retry.refusal is not None and retry.refusal.reason == "COMMIT_KEY_HELD"


# ============================================================ D. EffectAttempted — before, and once

def test_EffectAttempted_is_emitted_exactly_once_across_the_whole_lifecycle(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    fp = scn.approved_fingerprint(mint.grant_id)
    scn.m3.apply(mint.grant_id, Trigger.ADAPTER_RETURNED, actor_id="adapter")
    scn.m3.apply(mint.grant_id, Trigger.READBACK_MATCHED, actor_id="readback",
                 health_signal="HEALTHY", matched_fingerprint=fp)
    assert kit.count_event(scn.store, "EffectAttempted") == 1, (
        "EF-3 must NOT emit a second EffectAttempted (§19/§38)")
    # And it rode the CLAIM commit — before EF-3's EffectExecuted — so a lost response is detectable.
    names = kit.event_names(scn.store)
    assert names.index("EffectAttempted") < names.index("EffectExecuted")


def test_the_claim_co_commits_GrantClaimed_and_EffectAttempted_at_one_version(tmp_path):
    scn = kit.Scenario(tmp_path)
    scn.claimed()
    events = kit.effect_grant_events(scn.store)
    claimed = [e for e in events if e["event_name"] in ("GrantClaimed", "EffectAttempted")]
    assert {e["event_name"] for e in claimed} == {"GrantClaimed", "EffectAttempted"}
    assert len({e["version"] for e in claimed}) == 1, (
        "GrantClaimed and EffectAttempted are one transition (EF-2) and share one version")


def test_the_claim_is_atomic_never_both_never_neither(tmp_path):
    """The ledger CLAIMED state and the EffectAttempted event are one commit. If either could exist
    without the other, a crash between them is a claimed grant whose attempt was never recorded, or a
    recorded attempt with no claim (the orphan §35 auto-brakes)."""
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    assert scn.m3.require(mint.grant_id).state is EffectGrantState.CLAIMED
    assert kit.count_event(scn.store, "EffectAttempted") == 1


def test_a_restart_after_the_claim_re_executes_nothing_exactly_one_EffectAttempted(tmp_path):
    """restart_recovery (P0, §36): a process restart AFTER the CAS re-presents the winner's handle.
    Recovery must NOT re-drive the adapter — the row is already CLAIMED, a second claim matches zero
    rows, EffectAttempted stays at one, and a retry can only be a NEW grant, which the live-hold ledger
    refuses while the effect is held. Never act twice when the world only wanted it once."""
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    assert kit.count_event(scn.store, "EffectAttempted") == 1
    replay = scn.m3.claim(mint.handle, scn.params, actor_id="restarted-worker")
    assert not replay.claimed, "a restart re-claimed an already-CLAIMED grant"
    claimed_rows = [g for g in kit.ledger(scn.store) if g["state"] == "CLAIMED"]
    assert len(claimed_rows) == 1
    assert kit.count_event(scn.store, "EffectAttempted") == 1, (
        "a restart past the CAS re-drove the effect — a second EffectAttempted is a double effect")
    retry = scn.mint()
    assert not retry.authorized and retry.refusal is not None, (
        "a retry after the claim must be refused — the live-hold ledger holds the commit key")
    assert retry.refusal.reason == "COMMIT_KEY_HELD"


# ============================================================ E. FAILED needs proof; unknown is unknown

def test_a_pre_flight_rejection_with_proof_is_FAILED(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    r = scn.m3.apply(mint.grant_id, Trigger.ADAPTER_REJECTED_PRE_FLIGHT, actor_id="adapter",
                     failure_proof="TMS 422: invoice number already retired, no record created")
    assert r.to_state is EffectGrantState.FAILED
    g = scn.m3.require(mint.grant_id)
    assert g.failure_proof and "422" in g.failure_proof
    assert [e["payload"].get("failure_proof") for e in kit.effect_grant_events(scn.store)
            if e["event_name"] == "EffectFailed"] == [g.failure_proof]


def test_FAILED_without_proof_is_refused_not_persisted(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    with pytest.raises(GuardNotSatisfied, match="proof"):
        scn.m3.apply(mint.grant_id, Trigger.ADAPTER_REJECTED_PRE_FLIGHT, actor_id="adapter")
    assert scn.m3.require(mint.grant_id).state is EffectGrantState.CLAIMED, (
        "a FAILED with no proof is an UNKNOWN OUTCOME wearing a resolution — the state must not move")
    assert kit.count_event(scn.store, "EffectFailed") == 0


@pytest.mark.parametrize("trigger", [
    Trigger.ADAPTER_TIMED_OUT, Trigger.PROCESS_CRASHED, Trigger.LOST_RESPONSE])
def test_a_timeout_crash_or_lost_response_is_UNKNOWN_never_FAILED(tmp_path, trigger):
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    r = scn.m3.apply(mint.grant_id, trigger, actor_id="sys", exposure="invoice load:4471 ~$2,850",
                     accountable_owner_id=OWNER)
    assert r.to_state is EffectGrantState.UNKNOWN_OUTCOME, (
        f"{trigger.value} yielded {r.to_state.value}; a timeout alone NEVER proves failure (GR-5)")
    g = scn.m3.require(mint.grant_id)
    assert g.unknown_reason == "UNKNOWN_OUTCOME" and g.failure_proof is None
    assert kit.count_event(scn.store, "EffectFailed") == 0


@pytest.mark.parametrize("trigger", [Trigger.ADAPTER_TIMED_OUT, Trigger.LOST_RESPONSE])
def test_an_ambiguous_outcome_is_UNKNOWN_named_human_and_one_EffectAttempted(tmp_path, trigger):
    """timeout_after_effect (P0, rule 12 / GR-5): a timed-out or lost response resolves to
    UNKNOWN_OUTCOME — NEVER FAILED — owned by a NAMED human, and it still carries EXACTLY ONE
    EffectAttempted, so "we do not know" can never mask a second attempt or an orphan. This is the
    load-bearing distinction between "attempted" and "failed" that stops a broker being billed twice."""
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    assert kit.count_event(scn.store, "EffectAttempted") == 1
    r = scn.m3.apply(mint.grant_id, trigger, actor_id="sys", exposure="invoice load:4471 ~$2,850",
                     accountable_owner_id=OWNER)
    assert r.to_state is EffectGrantState.UNKNOWN_OUTCOME
    g = scn.m3.require(mint.grant_id)
    assert g.failure_proof is None
    assert kit.count_event(scn.store, "EffectFailed") == 0, "an ambiguous outcome became FAILED"
    assert kit.count_event(scn.store, "EffectAttempted") == 1, (
        "the ambiguous outcome moved EffectAttempted off exactly one — a hidden double effect")
    unknown = [e for e in kit.effect_grant_events(scn.store) if e["event_name"] == "OutcomeUnknown"]
    assert unknown and unknown[0]["accountable_owner_id"] == OWNER, (
        "an UNKNOWN_OUTCOME with no named accountable human is the one obligation nobody owes (rule 13)")


# ============================================================ F. verify — healthy match, or unknown

def test_a_positive_control_readback_matching_the_fingerprint_is_VERIFIED(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    scn.m3.apply(mint.grant_id, Trigger.ADAPTER_RETURNED, actor_id="adapter")
    fp = scn.approved_fingerprint(mint.grant_id)
    r = scn.m3.apply(mint.grant_id, Trigger.READBACK_MATCHED, actor_id="readback",
                     health_signal="TMS session live, record read", matched_fingerprint=fp)
    assert r.to_state is EffectGrantState.VERIFIED
    g = scn.m3.require(mint.grant_id)
    assert g.verification_outcome == "VERIFIED_SUCCESS" and g.health_signal and g.verified_at


def test_a_verified_requires_a_matching_fingerprint(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    scn.m3.apply(mint.grant_id, Trigger.ADAPTER_RETURNED, actor_id="adapter")
    with pytest.raises(GuardNotSatisfied, match="fingerprint"):
        scn.m3.apply(mint.grant_id, Trigger.READBACK_MATCHED, actor_id="readback",
                     health_signal="HEALTHY", matched_fingerprint="not-the-approved-one")
    assert scn.m3.require(mint.grant_id).state is EffectGrantState.ATTEMPTED
    assert kit.count_event(scn.store, "EffectVerified") == 0


def test_a_conflicting_readback_is_UNKNOWN_with_OBSERVATION_CONFLICTING(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    scn.m3.apply(mint.grant_id, Trigger.ADAPTER_RETURNED, actor_id="adapter")
    r = scn.m3.apply(mint.grant_id, Trigger.READBACK_CONFLICTING, actor_id="readback",
                     accountable_owner_id=OWNER)
    assert r.to_state is EffectGrantState.UNKNOWN_OUTCOME
    assert scn.m3.require(mint.grant_id).unknown_reason == "OBSERVATION_CONFLICTING"
    assert kit.count_event(scn.store, "VerificationConflict") == 1


def test_a_blind_readback_is_OBSERVATION_UNAVAILABLE_never_FAILED(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    scn.m3.apply(mint.grant_id, Trigger.ADAPTER_RETURNED, actor_id="adapter")
    r = scn.m3.apply(mint.grant_id, Trigger.READBACK_UNAVAILABLE, actor_id="readback",
                     channel="tms-portal", accountable_owner_id=OWNER)
    assert r.to_state is EffectGrantState.UNKNOWN_OUTCOME, "BLIND IS NOT FAILED"
    assert scn.m3.require(mint.grant_id).unknown_reason == "OBSERVATION_UNAVAILABLE"
    assert kit.count_event(scn.store, "EffectFailed") == 0
    unavailable = [e for e in kit.effect_grant_events(scn.store)
                   if e["event_name"] == "VerificationUnavailable"]
    assert len(unavailable) == 1 and unavailable[0]["payload"]["channel"] == "tms-portal"


# ============================================================ G. UNKNOWN_OUTCOME — owned, and frozen

def test_UNKNOWN_OUTCOME_cannot_be_created_without_a_named_active_human(tmp_path):
    scn = kit.Scenario(tmp_path, with_owner=False)  # no recorded human
    mint, _ = scn.claimed()
    with pytest.raises(OwnershipRefused):
        scn.m3.apply(mint.grant_id, Trigger.LOST_RESPONSE, actor_id="sys", exposure="x",
                     accountable_owner_id="ghost")
    assert scn.m3.require(mint.grant_id).state is EffectGrantState.CLAIMED


def test_UNKNOWN_OUTCOME_is_owned_by_the_named_human_on_the_event(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    scn.m3.apply(mint.grant_id, Trigger.LOST_RESPONSE, actor_id="sys", exposure="~$2,850",
                 accountable_owner_id=OWNER)
    unknowns = scn.m3.unknown_outcomes()
    assert [g.grant_id for g in unknowns] == [mint.grant_id], "the Sev-1 queue is empty or wrong"
    outcome_event = [e for e in kit.effect_grant_events(scn.store)
                     if e["event_name"] == "OutcomeUnknown"][0]
    assert outcome_event["accountable_owner_id"] == OWNER


def test_no_timer_moves_an_UNKNOWN_OUTCOME(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    scn.m3.apply(mint.grant_id, Trigger.LOST_RESPONSE, actor_id="sys", exposure="x",
                 accountable_owner_id=OWNER)
    with pytest.raises(IllegalTransition):
        scn.m3.apply(mint.grant_id, Trigger.TIMER_FIRED, actor_id="timer")
    assert scn.m3.require(mint.grant_id).state is EffectGrantState.UNKNOWN_OUTCOME
    # EF-5x is ILLEGAL (GR-6) and records IllegalTransitionAttempted on both surfaces.
    assert kit.count_event(scn.store, "IllegalTransitionAttempted") == 1
    assert any(r["event_type"] == "IllegalTransitionAttempted"
               for r in kit.security_rows(scn.store))


def test_an_UNKNOWN_OUTCOME_resolves_only_by_an_authenticated_human_decision(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    scn.m3.apply(mint.grant_id, Trigger.LOST_RESPONSE, actor_id="sys", exposure="x",
                 accountable_owner_id=OWNER)
    # A human established that the invoice DID go out — resolves to VERIFIED, with the decision ref.
    decision = p3_human_decision(scn)
    r = scn.m3.apply(mint.grant_id, Trigger.HUMAN_ESTABLISHED_REALITY, actor_type="human",
                     actor_id=OWNER, outcome="VERIFIED", decision_ref=decision,
                     decision_ref_kind="AUDIT_EVENT")
    assert r.to_state is EffectGrantState.VERIFIED
    g = scn.m3.require(mint.grant_id)
    assert g.reality_decision_ref == decision
    established = [e for e in kit.effect_grant_events(scn.store)
                  if e["event_name"] == "RealityEstablished"][0]
    assert established["payload"]["outcome"] == "VERIFIED"
    assert established["payload"]["subject"] == "effect"


def test_an_UNKNOWN_OUTCOME_resolution_to_FAILED_still_requires_proof(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    scn.m3.apply(mint.grant_id, Trigger.LOST_RESPONSE, actor_id="sys", exposure="x",
                 accountable_owner_id=OWNER)
    decision = p3_human_decision(scn)
    with pytest.raises(GuardNotSatisfied, match="proof"):
        scn.m3.apply(mint.grant_id, Trigger.HUMAN_ESTABLISHED_REALITY, actor_type="human",
                     actor_id=OWNER, outcome="FAILED", decision_ref=decision,
                     decision_ref_kind="AUDIT_EVENT")
    assert scn.m3.require(mint.grant_id).state is EffectGrantState.UNKNOWN_OUTCOME


def test_EF5_refuses_an_unreadable_outcome(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    scn.m3.apply(mint.grant_id, Trigger.LOST_RESPONSE, actor_id="sys", exposure="x",
                 accountable_owner_id=OWNER)
    decision = p3_human_decision(scn)
    with pytest.raises(GuardNotSatisfied):
        scn.m3.apply(mint.grant_id, Trigger.HUMAN_ESTABLISHED_REALITY, actor_type="human",
                     actor_id=OWNER, outcome="MAYBE", decision_ref=decision,
                     decision_ref_kind="AUDIT_EVENT")
    assert scn.m3.require(mint.grant_id).state is EffectGrantState.UNKNOWN_OUTCOME


# ============================================================ H. REVOKED is not EXPIRED_UNCLAIMED

def test_a_revocation_is_REVOKED_and_not_an_expiry(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint = scn.mint()
    r = scn.m3.revoke(mint.grant_id, cause="brake engaged mid-flight", actor_id="ops")
    assert r.to_state is EffectGrantState.REVOKED
    assert kit.count_event(scn.store, "GrantRevoked") == 1
    assert kit.count_event(scn.store, "GrantExpired") == 0, "REVOKED IS NOT EXPIRED_UNCLAIMED"


def test_an_expiry_is_EXPIRED_UNCLAIMED_and_not_a_revocation(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint = scn.mint()
    scn.clock.advance(seconds=120)  # past the grant TTL
    r = scn.m3.expire(mint.grant_id)
    assert r.to_state is EffectGrantState.EXPIRED_UNCLAIMED
    assert kit.count_event(scn.store, "GrantExpired") == 1
    assert kit.count_event(scn.store, "GrantRevoked") == 0, "an expiry masqueraded as a revocation"


def test_revoking_a_claimed_grant_does_nothing(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    with pytest.raises((GuardNotSatisfied, StateConflict)):
        scn.m3.revoke(mint.grant_id, cause="too late", actor_id="ops")
    assert scn.m3.require(mint.grant_id).state is EffectGrantState.CLAIMED, (
        "revoking a CLAIMED grant moved it — the effect may already exist; that is UNKNOWN territory")


# ============================================================ I. a brake between mint and claim

def test_a_brake_between_mint_and_claim_makes_the_cas_match_zero_rows(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint = scn.mint()
    # Ops engages the brake in the seconds between mint and claim.
    BrakeStore(scn.store.conn).engage(
        tenant=scn.store.tenant, action_class=scn.effect.action_class, actor="ops-lead",
        actor_kind="HUMAN", reason="pause all outbound while we investigate a duplicate")
    result = scn.m3.claim(mint.handle, scn.params, actor_id="w")
    assert not result.claimed, "the brake did not stop the claim"
    assert result.cause == "BRAKE_CHANGED"
    assert scn.m3.require(mint.grant_id).state is EffectGrantState.GRANTED, (
        "A BRAKE BETWEEN MINT AND CLAIM MAKES THE CAS MATCH ZERO ROWS — the adapter did nothing")
    assert kit.count_event(scn.store, "EffectAttempted") == 0, "an attempt fired under a brake"


# ============================================================ J. the strict-order consumer

def test_redelivery_of_a_consumed_event_is_idempotent(tmp_path):
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    box = scn.inbox()
    kit.replay_produced_stream(scn, box, mint.grant_id)  # cursor catches up to v2
    executed = kit.canonical_effect_envelope(
        tenant=scn.store.tenant, grant_id=mint.grant_id, event_name="EffectExecuted",
        producer_transition_id="EF-3", aggregate_version=3, previous_aggregate_version=2,
        seed="exec-1", pins=kit.grant_pins(scn, mint.grant_id))
    first = scn.m3.consume(executed, inbox=box)
    assert first.consume.applied and scn.m3.require(mint.grant_id).state is EffectGrantState.ATTEMPTED
    # Redeliver the SAME event: the inbox says duplicate, the handler never runs, no second effect.
    second = scn.m3.consume(executed, inbox=box)
    assert second.consume.is_noop
    assert scn.m3.require(mint.grant_id).state is EffectGrantState.ATTEMPTED


def test_an_event_for_a_grant_that_does_not_exist_parks(tmp_path):
    scn = kit.Scenario(tmp_path)
    scn.claimed()
    box = scn.inbox()
    ghost = kit.canonical_effect_envelope(
        tenant=scn.store.tenant, grant_id="ghost-4471", event_name="EffectExecuted",
        producer_transition_id="EF-3", aggregate_version=1, previous_aggregate_version=0,
        seed="ghost")
    result = scn.m3.consume(ghost, grant_id="ghost-4471", inbox=box)
    assert result.consume.outcome.value == "PARKED_MISSING_AGGREGATE"


def test_a_verification_parks_on_its_unapplied_predecessor_and_drains_when_it_lands(tmp_path):
    """P6-D11: strict order is ORDER not CONTIGUITY — the readback blocks on the UNAPPLIED
    predecessor (the adapter return), not on an absent version, and P6-D24's drain releases it the
    moment that predecessor applies, rather than leaving it to M-26 expiry."""
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    box = scn.inbox()
    kit.replay_produced_stream(scn, box, mint.grant_id)
    fp = scn.approved_fingerprint(mint.grant_id)
    pins = kit.grant_pins(scn, mint.grant_id)
    executed = kit.canonical_effect_envelope(
        tenant=scn.store.tenant, grant_id=mint.grant_id, event_name="EffectExecuted",
        producer_transition_id="EF-3", aggregate_version=3, previous_aggregate_version=2,
        seed="exec-1", pins=pins)
    verified = kit.canonical_effect_envelope(
        tenant=scn.store.tenant, grant_id=mint.grant_id, event_name="EffectVerified",
        producer_transition_id="EF-4", aggregate_version=4, previous_aggregate_version=3,
        payload={"verification_outcome": "VERIFIED_SUCCESS", "health_signal": "HEALTHY",
                 "matched_fingerprint": fp}, seed="ver-1", pins=pins)
    # The readback arrives FIRST — its predecessor (the adapter return) has not applied. It parks.
    parked = scn.m3.consume(verified, inbox=box)
    assert parked.consume.outcome.value == "PARKED_VERSION_GAP"
    assert scn.m3.require(mint.grant_id).state is EffectGrantState.CLAIMED
    # The adapter return lands — and drains the readback, which applies as ITSELF.
    landed = scn.m3.consume(executed, inbox=box)
    assert landed.consume.applied
    assert scn.m3.require(mint.grant_id).state is EffectGrantState.VERIFIED, (
        "the parked verification did not drain when its predecessor applied")


def test_an_illegal_transition_marker_riding_the_stream_is_consumed_not_skipped(tmp_path):
    """P6-D11 / F14: an IllegalTransitionAttempted riding the strict aggregate is a legible member of
    the stream. A consumer that reached it as a declared predecessor advances over it rather than
    parking forever — consuming the COMPLETE stream, never a family subset."""
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    # Produce a real F14 marker on the stream by attempting an illegal transition.
    with pytest.raises(IllegalTransition):
        scn.m3.apply(mint.grant_id, Trigger.TIMER_FIRED, actor_id="attacker")
    box = scn.inbox()
    outcomes = kit.replay_produced_stream(scn, box, mint.grant_id)
    # Every produced event — including the F14 marker — was consumed (none left the cursor stuck).
    assert all(o in ("APPLIED", "DUPLICATE_NOOP", "STALE_NOOP") for o in outcomes), outcomes
    assert any(e["event_name"] == "IllegalTransitionAttempted"
               for e in kit.effect_grant_events(scn.store))


def test_the_consumer_supplies_a_drain_handler(tmp_path):
    """P6-D24 closes here: the drain path is exercised (the readback above drains), and without a
    factory a parked cohort would leave the park only by M-26 expiry. Asserted structurally so the
    obligation cannot regress to 'off by default'."""
    src = (ROOT / "src" / "freight_recon" / "external_effect.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    consume = next(n for n in ast.walk(tree)
                   if isinstance(n, ast.FunctionDef) and n.name == "consume")
    calls = [n for n in ast.walk(consume)
             if isinstance(n, ast.Call) and any(
                 isinstance(kw, ast.keyword) and kw.arg == "drain_handler_for" for kw in n.keywords)]
    assert calls, "consume() does not pass drain_handler_for — P6-D24 is unmet"


# ============================================================ K. replay, tenant isolation, dark

def test_replay_of_the_whole_corpus_produces_zero_grants_claims_and_effects(tmp_path):
    """GR-11: replay reconstructs the outcome record and performs no adapter call. The kernel makes a
    grant impossible to mint under replay (a CheckpointPassed cannot be constructed), and M3 mints and
    claims only through it — so replaying the emitted corpus mints nothing, claims nothing and emits
    no EffectAttempted."""
    scn = kit.Scenario(tmp_path)
    mint, _ = scn.claimed()
    scn.m3.apply(mint.grant_id, Trigger.ADAPTER_RETURNED, actor_id="adapter")
    grants_before = len(kit.ledger(scn.store))
    attempts_before = kit.count_event(scn.store, "EffectAttempted")

    # Replay every effect_grant event back through the consumer: it advances a projection cursor and
    # touches the world zero times. No new grant row, no new claim, no new EffectAttempted.
    box = scn.inbox()
    kit.replay_produced_stream(scn, box, mint.grant_id)
    assert len(kit.ledger(scn.store)) == grants_before, "replay created a grant"
    assert kit.count_event(scn.store, "EffectAttempted") == attempts_before, (
        "replay emitted a second EffectAttempted — it touched the world")


def test_a_claim_never_transitions_another_tenants_grant(tmp_path):
    scn_a = kit.Scenario(tmp_path, tenant=T_A, resource="load:shared")
    mint_a = scn_a.mint()
    # Tenant B, its own store/kernel, cannot see or claim tenant A's grant.
    scn_b = p3.make_store(tmp_path, tenant=T_B, name="tenantb.db")
    m3_b = ExternalEffectMachine(scn_b.conn, tenant=T_B, kernel=scn_a.kernel, clock=scn_a.clock)
    assert m3_b.get(mint_a.grant_id) is None, "[C-1]: tenant B read tenant A's grant"
    with pytest.raises(Exception):
        m3_b.require(mint_a.grant_id)
    assert scn_a.m3.require(mint_a.grant_id).state is EffectGrantState.GRANTED


def test_it_ships_dark(tmp_path):
    """Nothing under src/freight_recon/ imports external_effect, and the only script that may is the
    probe. Discovered by scanning, never by an enumerated file list."""
    importers: list[str] = []
    inspected = 0
    for path in sorted((ROOT / "src" / "freight_recon").rglob("*.py")) + \
            sorted((ROOT / "scripts").rglob("*.py")):
        if path.name == "external_effect.py":
            continue
        inspected += 1
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and \
                    node.module.split(".")[-1] == "external_effect":
                importers.append(path.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[-1] == "external_effect":
                        importers.append(path.name)
    assert inspected > 20, f"the sweep inspected {inspected} modules; it proves nothing"
    assert set(importers) <= {"probe_phase6_external_effect.py"}, (
        f"M3 has importers outside the permitted probe: {sorted(set(importers))}. M3 ships dark.")


def test_the_ledger_is_the_only_effect_authority(tmp_path):
    """external_effect.py mints and claims ONLY through the P3 kernel — it constructs no GateRegistry
    and no second CAS. Asserted by AST: no GateRegistry/GateEntry is built here (rule 17)."""
    src = (ROOT / "src" / "freight_recon" / "external_effect.py").read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("GateRegistry", "GateEntry"), (
                "M3 constructs a gate — the checkpoint is the only thing that mints a gate decision")


# --- a real committed human-decision reference for the EF-5 resolution tests -------------------

def p3_human_decision(scn) -> str:
    """One committed `HumanDecided` event id, resolvable by K-1 — an authenticated human decision."""
    from freight_recon.event_envelope import EventEnvelope
    from freight_recon.event_outbox import TransactionalOutbox

    now = "2026-08-20T10:00:00.000Z"
    env = EventEnvelope(
        event_id=kit._seeded_uuid(f"decision-{scn.store.tenant}"),
        event_name="HumanDecided", event_version=CONTRACTS["HumanDecided"].current_version,
        occurred_at=now, recorded_at=now, tenant_id=scn.store.tenant,
        aggregate_type="work_item", aggregate_id="wi-reality-1", aggregate_version=1,
        causation_id=None, correlation_id="wi-reality-1", producer_component="work_service",
        producer_transition_id="WI-9", actor_type="human", actor_id=OWNER,
        trace_id="trace-reality", payload={"decision_ref": "human-said-it-went-out"})
    scn.store.conn.execute("BEGIN IMMEDIATE")
    TransactionalOutbox(scn.store.conn, tenant=scn.store.tenant).emit(env)
    scn.store.conn.commit()
    return env.event_id
