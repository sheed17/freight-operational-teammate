"""P6 / M6 — the Identity Binding Claim — acceptance and hostile battery.

Entity §44 names nine adversarial tests by name; they are here by those names. The rest of the
battery covers the transition table (IB-1…IB-8), the SD-6 derivation the database enforces, the
mixed-order transport (proposals order-tolerant, correction/supersession strict), the M7/M10/Evidence
inert seams, the checkpoint seam, and the ship-dark posture. Several node ids are the guards
`scripts/mutate_phase6_identity_binding_claim.py` turns RED — a guard never seen to fail is a
decoration.

The suite protects M6's actual behaviour: a human's decision can never be quietly recomputed,
overwritten, duplicated, laundered, guessed at, or rebuilt away by a replay.
"""

from __future__ import annotations

import ast
import json
import sqlite3
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

from freight_recon.identity_binding_claim import (  # noqa: E402
    AGGREGATE_TYPE,
    PRODUCED_CONTRACTS,
    TRANSITIONS,
    TRANSITIONS_BY_ID,
    BindingState,
    ContentSetProvenance,
    FailClosed,
    ForgedEvidence,
    GuardNotSatisfied,
    IllegalTransition,
    M6Machine,
    MatchAttempt,
    MatchMethod,
    OrdinalTarget,
    OwnerAssertedOverwrite,
    StateConflict,
    UnknownClaim,
)
from freight_recon.migrations.phase6_identity_binding_claims import (  # noqa: E402
    CLAIM_STATES,
    phase6_identity_binding_claims_readiness_problems,
)
from freight_recon.schema import (  # noqa: E402
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)

TENANT = "acme-brokerage"
HUMAN = "owner:dana"


def _conn() -> sqlite3.Connection:
    tmp = Path(tempfile.mkdtemp(prefix="p6m6-test-"))
    conn = sqlite3.connect(str(tmp / "ibc.db"))
    conn.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(conn)
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    return conn


def _human(conn: sqlite3.Connection, tenant: str = TENANT, human_id: str = HUMAN,
           state: str = "ACTIVE") -> str:
    conn.execute(
        "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, authority_role, "
        "state, recorded_at, recorded_by, recorded_by_kind) VALUES (?,?,?,?, ?, ?, ?, 'human')",
        (tenant, human_id, human_id, "AUTHORIZED_HUMAN", state, "2026-08-20T09:00:00.000Z",
         "founder"))
    conn.commit()
    return human_id


_SUBJECT_N = [0]


def _subject(conn: sqlite3.Connection, tenant: str = TENANT, obs_id: str | None = None) -> str:
    _SUBJECT_N[0] += 1
    oid = obs_id or f"obs-{_SUBJECT_N[0]}"
    conn.execute(
        "INSERT OR IGNORE INTO observations (tenant, observation_id, source_system, external_id, "
        "content_digest, raw_value, as_of, received_at, state, version, provenance_class, "
        "created_at, updated_at) VALUES (?,?, 'pod:scan', ?, ?, 'v', 't', 't', 'RECEIVED', 1, "
        "'SYSTEM_IMPORTED', 't', 't')",
        (tenant, oid, oid, oid))
    conn.commit()
    return oid


@pytest.fixture()
def conn() -> sqlite3.Connection:
    return _conn()


@pytest.fixture()
def m6(conn) -> M6Machine:
    _human(conn)
    return M6Machine(conn, tenant=TENANT)


def _exact(conn, entity="load:4471", **kw) -> MatchAttempt:
    kw.setdefault("open_entity_count", 1)
    return MatchAttempt(subject_ref=_subject(conn), entity_ref=entity,
                        match_method=MatchMethod.EXACT_ID, **kw)


# ---- structure ---------------------------------------------------------------------------------

def test_the_seven_states_are_exactly_the_registry_set():
    assert set(CLAIM_STATES) == {"PROPOSED", "CONFIRMED", "AMBIGUOUS", "REJECTED", "SUPERSEDED",
                                 "CORRECTED", "CONFLICTING"}
    assert len(CLAIM_STATES) == 7
    assert {s.value for s in BindingState} == set(CLAIM_STATES)


def test_no_eighth_state_exists_anywhere():
    for forbidden in ("RESOLVED", "EXPIRED", "ARCHIVED", "DELETED"):
        assert forbidden not in CLAIM_STATES


def test_the_transition_ids_are_the_canonical_ib_set():
    assert set(TRANSITIONS_BY_ID) == {"IB-1", "IB-2", "IB-2r", "IB-2h", "IB-3", "IB-4", "IB-5",
                                      "IB-6", "IB-7", "IB-8"}
    assert len(TRANSITIONS) == 10


def test_the_six_f6_contracts_are_produced_and_no_seventh():
    assert PRODUCED_CONTRACTS == {"ClaimProposed", "ClaimConfirmed", "ClaimEvidenced",
                                  "ClaimAmbiguous", "ClaimSuperseded", "ClaimCorrected"}
    assert "ClaimRejected" not in PRODUCED_CONTRACTS
    assert "ClaimConflicted" not in PRODUCED_CONTRACTS


def test_fresh_canonical_database_is_ready():
    conn = _conn()
    assert schema_readiness_problems(conn) == []
    assert phase6_identity_binding_claims_readiness_problems(conn) == []


# ---- IB-1..IB-4: proposal, the deterministic ladder --------------------------------------------

def test_ib_propose_sets_derived_provenance(m6, conn):
    r = m6.propose(_exact(conn))
    c = m6.get(r.claim.binding_claim_id)
    assert r.transition_id == "IB-1" and c.state is BindingState.PROPOSED
    assert c.provenance_class == "LINKER_INFERRED"


@pytest.mark.parametrize("method,prov,kw", [
    (MatchMethod.EXACT_ID, "LINKER_INFERRED", {}),
    (MatchMethod.RULE, "LINKER_INFERRED", {"rule_id": "r-1"}),
    (MatchMethod.RECONCILIATION, "RECONCILED", {}),
    (MatchMethod.MODEL_EXTRACT, "MODEL_EXTRACTED", {"evidence_id": "e", "span": "page:1"}),
    (MatchMethod.MODEL_INFER, "MODEL_INFERRED", {}),
])
def test_provenance_is_the_derived_function_of_match_method(m6, conn, method, prov, kw):
    r = m6.propose(MatchAttempt(subject_ref=_subject(conn), entity_ref="load:1",
                                match_method=method, **kw))
    assert m6.get(r.claim.binding_claim_id).provenance_class == prov


def test_ib_exact_id_confirms(m6, conn):
    r = m6.link(_exact(conn, open_entity_count=1))
    assert m6.get(r.claim.binding_claim_id).state is BindingState.CONFIRMED
    assert r.transition_id == "IB-2"


def test_exact_id_with_two_open_entities_is_ambiguous(m6, conn):
    r = m6.link(_exact(conn, open_entity_count=2), owner_id=_human(conn))
    assert m6.get(r.claim.binding_claim_id).state is BindingState.AMBIGUOUS


def test_ib_rule_or_reconcile_confirms(m6, conn):
    r = m6.link(MatchAttempt(subject_ref=_subject(conn), entity_ref="l", match_method=MatchMethod.RULE,
                             rule_id="r", rule_registered=True))
    assert m6.get(r.claim.binding_claim_id).state is BindingState.CONFIRMED
    u = m6.link(MatchAttempt(subject_ref=_subject(conn), entity_ref="l", match_method=MatchMethod.RULE,
                             rule_id="r", rule_registered=False), owner_id=_human(conn))
    assert m6.get(u.claim.binding_claim_id).state is BindingState.AMBIGUOUS


def test_reconciliation_requires_two_sources(m6, conn):
    two = m6.link(MatchAttempt(subject_ref=_subject(conn), entity_ref="l",
                               match_method=MatchMethod.RECONCILIATION, source_count=2))
    assert m6.get(two.claim.binding_claim_id).state is BindingState.CONFIRMED
    one = m6.link(MatchAttempt(subject_ref=_subject(conn), entity_ref="l",
                               match_method=MatchMethod.RECONCILIATION, source_count=1),
                  owner_id=_human(conn))
    assert m6.get(one.claim.binding_claim_id).state is BindingState.AMBIGUOUS


def test_ib_model_extract_is_evidence_not_confirmation(m6, conn):
    r = m6.link(MatchAttempt(subject_ref=_subject(conn), entity_ref="load:4471",
                             match_method=MatchMethod.MODEL_EXTRACT, evidence_id="pod.pdf",
                             span="page:1"))
    c = m6.get(r.claim.binding_claim_id)
    assert c.state is BindingState.PROPOSED and r.event_names == ("ClaimEvidenced",)


def test_guess_never_confirms_at_confidence_1_0(m6, conn):
    """§44 / GR-8: a MODEL_INFERRED guess NEVER confirms, at confidence 1.0 exactly as at 0.4."""
    for confidence in (1.0, 0.99, 0.5, 0.0):
        r = m6.link(MatchAttempt(subject_ref=_subject(conn), entity_ref="load:4471",
                                 match_method=MatchMethod.MODEL_INFER, confidence=confidence),
                    owner_id=_human(conn))
        c = m6.get(r.claim.binding_claim_id)
        assert c.state is BindingState.AMBIGUOUS, f"confidence {confidence} confirmed a guess"
        assert c.provenance_class == "MODEL_INFERRED"
        assert c.ambiguous_reason == "model_inferred"


def test_single_weak_candidate_is_still_ambiguous(m6, conn):
    """§44 / M-17: a single WEAK candidate is AMBIGUOUS, never auto-confirmed."""
    r = m6.link(MatchAttempt(subject_ref=_subject(conn), entity_ref="load:1",
                             match_method=MatchMethod.EXACT_ID, open_entity_count=1,
                             candidate_count=1, weak=True), owner_id=_human(conn))
    c = m6.get(r.claim.binding_claim_id)
    assert c.state is BindingState.AMBIGUOUS and c.ambiguous_reason == "single_weak"


def test_multiple_candidates_are_ambiguous(m6, conn):
    r = m6.link(_exact(conn, open_entity_count=3, candidate_count=3), owner_id=_human(conn))
    assert m6.get(r.claim.binding_claim_id).ambiguous_reason == "multiple"


def test_ambiguous_names_an_active_recorded_human(m6, conn):
    with pytest.raises(GuardNotSatisfied):
        m6.link(MatchAttempt(subject_ref=_subject(conn), entity_ref="l",
                             match_method=MatchMethod.MODEL_INFER))
    with pytest.raises(GuardNotSatisfied):
        m6.link(MatchAttempt(subject_ref=_subject(conn), entity_ref="l",
                             match_method=MatchMethod.MODEL_INFER), owner_id="ghost")


# ---- the human assertion (IB-2h) ---------------------------------------------------------------

def test_ib_human_assert_binds_immutable_id(m6, conn):
    h = _human(conn)
    r = m6.assert_human(subject_ref=_subject(conn), entity_ref="load:4471", decision_ref="dec-1",
                        decision_human_id=h, actor_id=h)
    c = m6.get(r.claim.binding_claim_id)
    assert c.state is BindingState.CONFIRMED and c.provenance_class == "OWNER_ASSERTED"
    assert c.decision_ref == "dec-1" and c.match_method == "HUMAN"


def test_human_assertion_requires_a_decision_ref(m6, conn):
    h = _human(conn)
    with pytest.raises(GuardNotSatisfied):
        m6.assert_human(subject_ref=_subject(conn), entity_ref="l", decision_ref="",
                        decision_human_id=h, actor_id=h)


def test_a_model_actor_cannot_confirm(m6, conn):
    h = _human(conn)
    with pytest.raises(IllegalTransition):
        m6.assert_human(subject_ref=_subject(conn), entity_ref="l", decision_ref="d",
                        decision_human_id=h, actor_id="gpt", actor_kind="model")


def test_counterparty_cannot_become_owner_asserted(m6, conn):
    h = _human(conn)
    with pytest.raises(IllegalTransition):
        m6.assert_human(subject_ref=_subject(conn), entity_ref="l", decision_ref="per our call",
                        decision_human_id=h, actor_id="rival", actor_kind="counterparty")
    sec = [r["event_type"] for r in conn.execute(
        "SELECT event_type FROM security_events WHERE tenant = ?", (TENANT,))]
    assert "CounterpartySelfAuthorizationDetected" in sec


def test_a_forged_or_inactive_human_fails_closed(m6, conn):
    with pytest.raises(GuardNotSatisfied):
        m6.assert_human(subject_ref=_subject(conn), entity_ref="l", decision_ref="d",
                        decision_human_id="imposter", actor_id="imposter")
    off = _human(conn, human_id="owner:gone", state="OFFBOARDED")
    with pytest.raises(GuardNotSatisfied):
        m6.assert_human(subject_ref=_subject(conn), entity_ref="l", decision_ref="d",
                        decision_human_id=off, actor_id=off)


def test_ordinal_binding_resolves_to_immutable_id_or_fails_closed(m6, conn):
    """§44 / L-B: an ordinal resolves to the immutable id it was shown, or FAILS CLOSED. It NEVER
    falls back to the new occupant of the slot."""
    h = _human(conn)
    s1, s2, s3 = _subject(conn), _subject(conn), _subject(conn)
    # Happy path: slot 2 = s2 -> binds the immutable id s2.
    r = m6.assert_human(entity_ref="load:4471", decision_ref="d", decision_human_id=h, actor_id=h,
                        ordinal_target=OrdinalTarget(2, s2), current_unlinked=[s1, s2, s3])
    assert m6.get(r.claim.binding_claim_id).subject_ref == s2
    # The slot moved: a new message pushes s2 to slot 3. The action FAILS CLOSED — never slot 2's new
    # occupant.
    with pytest.raises(FailClosed):
        m6.assert_human(entity_ref="load:1", decision_ref="d", decision_human_id=h, actor_id=h,
                        ordinal_target=OrdinalTarget(2, s2), current_unlinked=[_subject(conn), s1, s2])
    # The resolved id is gone entirely: also fail closed.
    with pytest.raises(FailClosed):
        m6.assert_human(entity_ref="load:1", decision_ref="d", decision_human_id=h, actor_id=h,
                        ordinal_target=OrdinalTarget(1, "vanished"), current_unlinked=[s1, s3])


# ---- evidence (IB-3) ---------------------------------------------------------------------------

def test_model_extracted_requires_evidence_span(m6, conn):
    """§44 / §16/§37: a MODEL_EXTRACTED claim with no evidence span is structurally impossible."""
    # The machine refuses (a forged / missing span fails closed).
    with pytest.raises(ForgedEvidence):
        m6.propose(MatchAttempt(subject_ref=_subject(conn), entity_ref="l",
                                match_method=MatchMethod.MODEL_EXTRACT, evidence_id="e", span=None))
    with pytest.raises(ForgedEvidence):
        m6.propose(MatchAttempt(subject_ref=_subject(conn), entity_ref="l",
                                match_method=MatchMethod.MODEL_EXTRACT, evidence_id="e",
                                span="not-a-region"))
    # ### AND THE DATABASE REFUSES IT (defense in depth): a direct MODEL_EXTRACTED row with no span.
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO identity_binding_claims (tenant, binding_claim_id, subject_ref, entity_ref, "
            "provenance_class, state, version, match_method, created_at, updated_at) VALUES "
            "(?, 'x', ?, 'e', 'MODEL_EXTRACTED', 'PROPOSED', 1, 'MODEL_EXTRACT', 't', 't')",
            (TENANT, _subject(conn)))
        conn.commit()
    conn.rollback()


def test_extracted_identifier_re_enters_deterministic_matching(m6, conn):
    subject = _subject(conn)
    ev = m6.link(MatchAttempt(subject_ref=subject, entity_ref="load:4471",
                              match_method=MatchMethod.MODEL_EXTRACT, evidence_id="pod.pdf",
                              span="0:4"))
    assert m6.get(ev.claim.binding_claim_id).state is BindingState.PROPOSED
    det = m6.link(MatchAttempt(subject_ref=subject, entity_ref="load:4471",
                               match_method=MatchMethod.EXACT_ID, open_entity_count=1))
    assert m6.get(det.claim.binding_claim_id).state is BindingState.CONFIRMED
    assert det.claim.binding_claim_id != ev.claim.binding_claim_id


# ---- SD-6 / laundering / immutability -----------------------------------------------------------

def test_no_provenance_laundering(m6, conn):
    """§44 / M-14 / R-P2: a MODEL_INFERRED claim cannot become LINKER_INFERRED by any edit — a change
    of belief is a NEW claim with a new match_method."""
    r = m6.link(MatchAttempt(subject_ref=_subject(conn), entity_ref="l",
                             match_method=MatchMethod.MODEL_INFER), owner_id=_human(conn))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE identity_binding_claims SET provenance_class = 'LINKER_INFERRED' "
                     "WHERE tenant = ? AND binding_claim_id = ?", (TENANT, r.claim.binding_claim_id))
        conn.commit()
    conn.rollback()
    assert m6.get(r.claim.binding_claim_id).provenance_class == "MODEL_INFERRED"


def test_provenance_class_cannot_be_edited(m6, conn):
    """The immutability TRIGGER refuses any UPDATE of provenance_class — even to the same value —
    which is what makes SD-6 true against a connection, not only against the Python."""
    r = m6.propose(_exact(conn))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("UPDATE identity_binding_claims SET provenance_class = 'LINKER_INFERRED' "
                     "WHERE tenant = ? AND binding_claim_id = ?", (TENANT, r.claim.binding_claim_id))
        conn.commit()
    conn.rollback()


def test_sd6_mismatched_insert_is_refused(m6, conn):
    """The SD-6 mapping CHECK refuses any (match_method, provenance_class) pair off the function —
    a caller cannot choose provenance independently of match_method."""
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO identity_binding_claims (tenant, binding_claim_id, subject_ref, entity_ref, "
            "provenance_class, state, version, match_method, rule_id, created_at, updated_at) VALUES "
            "(?, 'sd6', ?, 'e', 'OWNER_ASSERTED', 'PROPOSED', 1, 'EXACT_ID', 'r', 't', 't')",
            (TENANT, _subject(conn)))
        conn.commit()
    conn.rollback()


def test_content_cannot_set_its_own_provenance(m6, conn):
    with pytest.raises(ContentSetProvenance):
        m6.propose(MatchAttempt(subject_ref=_subject(conn), entity_ref="l",
                                match_method=MatchMethod.EXACT_ID,
                                content={"provenance_class": "OWNER_ASSERTED"}))


# ---- the relinker (IB-5 / IB-5x) — the B3 regression -------------------------------------------

def test_owner_binding_survives_relinker(m6, conn):
    """§44 / B3 / GR-9 / R-P3: an OWNER_ASSERTED binding + an inferrer re-run is an ILLEGAL
    TRANSITION — state unchanged, TWO F14 security events emitted, and a retry storm changes
    nothing."""
    h = _human(conn)
    r = m6.assert_human(subject_ref=_subject(conn), entity_ref="load:4471", decision_ref="d",
                        decision_human_id=h, actor_id=h)
    before = dict(conn.execute(
        "SELECT * FROM identity_binding_claims WHERE tenant = ? AND binding_claim_id = ?",
        (TENANT, r.claim.binding_claim_id)).fetchone())
    for _ in range(5):
        with pytest.raises(OwnerAssertedOverwrite):
            m6.recompute(r.claim.binding_claim_id)
    after = dict(conn.execute(
        "SELECT * FROM identity_binding_claims WHERE tenant = ? AND binding_claim_id = ?",
        (TENANT, r.claim.binding_claim_id)).fetchone())
    assert after == before and after["state"] == "CONFIRMED"
    sec = [row["event_type"] for row in conn.execute(
        "SELECT event_type FROM security_events WHERE tenant = ?", (TENANT,))]
    assert "IllegalTransitionAttempted" in sec and "OwnerAssertedOverwriteAttempted" in sec


def test_linker_inferred_may_be_recomputed_and_the_old_row_is_retained(m6, conn):
    r = m6.link(_exact(conn, entity="load:4471"))
    m6.recompute(r.claim.binding_claim_id)
    old = m6.get(r.claim.binding_claim_id)
    assert old.state is BindingState.SUPERSEDED and old.entity_ref == "load:4471"


# ---- inferrer-vs-owner (IB-6) ------------------------------------------------------------------

def test_inferrer_vs_owner_raises_conflict_not_a_winner(m6, conn):
    """§44: the inferrer disagreeing with the owner raises a CONFLICT (ConflictRaised, F7), preserves
    the owner binding intact, and picks no winner."""
    h = _human(conn)
    r = m6.assert_human(subject_ref=_subject(conn), entity_ref="load:4471", decision_ref="d",
                        decision_human_id=h, actor_id=h)
    c = m6.inferrer_disagrees(r.claim.binding_claim_id, disagreeing_entity_ref="load:9999",
                              owner_id=h)
    binding = m6.get(r.claim.binding_claim_id)
    assert c.to_state is BindingState.CONFLICTING
    # ### THE CLAIM'S DURABLE STATE IS CONFLICTING, NOT SUPERSEDED — the inferrer did not win.
    assert binding.state is BindingState.CONFLICTING
    assert binding.entity_ref == "load:4471" and binding.provenance_class == "OWNER_ASSERTED"
    assert conn.execute(
        "SELECT COUNT(*) FROM event_outbox WHERE tenant = ? AND event_name = 'ConflictRaised'",
        (TENANT,)).fetchone()[0] == 1


# ---- correction (IB-7) — append-only, propagating ----------------------------------------------

def test_correction_propagates_a_compensation(m6, conn):
    """§44 / M-20 / ADR-007 §6: correction records a durable M6-OWNED propagation obligation that
    NAMES the completed effects needing a Compensation. It asserts the OBLIGATION — never a
    fabricated `compensations` row, and no Compensation is fabricated as completed (task §3.8)."""
    h = _human(conn)
    r = m6.link(_exact(conn, entity="load:4471"))
    m6.correct(r.claim.binding_claim_id, new_entity_ref="load:44718", decision_ref="fix",
               decision_human_id=h, actor_id=h, dependent_refs=["load:4471.documented"],
               completed_effects=["invoice#560010"])
    old = m6.get(r.claim.binding_claim_id)
    assert old.state is BindingState.CORRECTED and old.propagation_obligation is not None
    obligation = json.loads(old.propagation_obligation)
    assert "invoice#560010" in obligation["completed_effects_needing_compensation"]
    # ### M6 FABRICATES NO COMPENSATION. `compensations` is now a canonical table (M10 LANDED after
    # M9 — rule 20, corrected from the pre-M10 "table absent" assertion), but IB-7 writes NO row into
    # it: the correction records a durable propagation_obligation NAMING the completed effects, and
    # fabricates none as discharged.
    assert conn.execute("SELECT COUNT(*) FROM compensations").fetchone()[0] == 0


def test_correction_is_append_only_and_correction_of_correction_is_supported(m6, conn):
    h = _human(conn)
    r = m6.link(_exact(conn, entity="load:4471"))
    c1 = m6.correct(r.claim.binding_claim_id, new_entity_ref="load:44718", decision_ref="f1",
                    decision_human_id=h, actor_id=h)
    # The prior claim is retained.
    assert m6.get(r.claim.binding_claim_id) is not None
    new = m6.get(c1.corrected_claim_id)
    assert new.corrected_from == r.claim.binding_claim_id and new.state is BindingState.CONFIRMED
    # Correction-of-correction.
    c2 = m6.correct(c1.corrected_claim_id, new_entity_ref="load:44719", decision_ref="f2",
                    decision_human_id=h, actor_id=h)
    assert m6.get(c1.corrected_claim_id).state is BindingState.CORRECTED
    assert m6.get(c2.corrected_claim_id).entity_ref == "load:44719"


def test_two_confirmed_bindings_impossible(m6, conn):
    """§44 / §17: at most one CONFIRMED binding per subject — a partial unique index, exercised with
    real competing confirmations."""
    subject = _subject(conn)
    m6.link(MatchAttempt(subject_ref=subject, entity_ref="load:1", match_method=MatchMethod.EXACT_ID,
                         open_entity_count=1))
    p2 = m6.propose(MatchAttempt(subject_ref=subject, entity_ref="load:2",
                                 match_method=MatchMethod.EXACT_ID))
    with pytest.raises(GuardNotSatisfied):
        m6.resolve(p2.claim.binding_claim_id, MatchAttempt(subject_ref=subject, entity_ref="load:2",
                                                           match_method=MatchMethod.EXACT_ID))
    assert conn.execute(
        "SELECT COUNT(*) FROM identity_binding_claims WHERE tenant = ? AND subject_ref = ? "
        "AND state = 'CONFIRMED'", (TENANT, subject)).fetchone()[0] == 1


def test_a_direct_second_confirmed_insert_is_refused_by_the_partial_index(m6, conn):
    subject = _subject(conn)
    conn.execute(
        "INSERT INTO identity_binding_claims (tenant, binding_claim_id, subject_ref, entity_ref, "
        "provenance_class, state, version, match_method, rule_id, created_at, updated_at) VALUES "
        "(?, 'c1', ?, 'l', 'LINKER_INFERRED', 'CONFIRMED', 1, 'EXACT_ID', 'r', 't', 't')",
        (TENANT, subject))
    conn.commit()
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO identity_binding_claims (tenant, binding_claim_id, subject_ref, entity_ref, "
            "provenance_class, state, version, match_method, rule_id, created_at, updated_at) VALUES "
            "(?, 'c2', ?, 'l', 'LINKER_INFERRED', 'CONFIRMED', 1, 'EXACT_ID', 'r', 't', 't')",
            (TENANT, subject))
        conn.commit()
    conn.rollback()


# ---- rejection / cancellation / OCC ------------------------------------------------------------

def test_proposed_or_ambiguous_may_be_rejected(m6, conn):
    p = m6.propose(_exact(conn))
    assert m6.reject(p.claim.binding_claim_id).to_state is BindingState.REJECTED


def test_cancelled_entity_supersedes_the_confirmed_binding(m6, conn):
    h = _human(conn)
    r = m6.link(_exact(conn, entity="load:4471"))
    m6.cancel_entity(r.claim.binding_claim_id, owner_id=h)
    c = m6.get(r.claim.binding_claim_id)
    assert c.state is BindingState.SUPERSEDED and c.owner_id == h


def test_occ_on_claim_version_refuses_a_lost_update(m6, conn):
    p = m6.propose(_exact(conn))
    snap = m6.get(p.claim.binding_claim_id)
    m6.reject(p.claim.binding_claim_id)
    with pytest.raises((StateConflict, GuardNotSatisfied)):
        m6.resolve(p.claim.binding_claim_id, _exact_for(snap.subject_ref), expected=snap)


def _exact_for(subject):
    return MatchAttempt(subject_ref=subject, entity_ref="load:1", match_method=MatchMethod.EXACT_ID,
                        open_entity_count=1)


# ---- tenancy -----------------------------------------------------------------------------------

def test_cross_tenant_read_is_isolated(conn):
    _human(conn, "tenant-a")
    _human(conn, "tenant-b")
    a = M6Machine(conn, tenant="tenant-a")
    b = M6Machine(conn, tenant="tenant-b")
    ra = a.link(MatchAttempt(subject_ref=_subject(conn, "tenant-a"), entity_ref="load:1",
                             match_method=MatchMethod.EXACT_ID, open_entity_count=1))
    rb = b.link(MatchAttempt(subject_ref=_subject(conn, "tenant-b"), entity_ref="load:1",
                             match_method=MatchMethod.EXACT_ID, open_entity_count=1))
    assert a.get(rb.claim.binding_claim_id) is None
    assert b.get(ra.claim.binding_claim_id) is None
    with pytest.raises(UnknownClaim):
        a.require(rb.claim.binding_claim_id)


def test_same_subject_ref_in_two_tenants_is_two_isolated_claims(conn):
    _human(conn, "tenant-a")
    _human(conn, "tenant-b")
    a = M6Machine(conn, tenant="tenant-a")
    b = M6Machine(conn, tenant="tenant-b")
    sa = _subject(conn, "tenant-a", obs_id="shared")
    sb = _subject(conn, "tenant-b", obs_id="shared")
    ra = a.link(MatchAttempt(subject_ref=sa, entity_ref="load:1", match_method=MatchMethod.EXACT_ID,
                             open_entity_count=1))
    rb = b.link(MatchAttempt(subject_ref=sb, entity_ref="load:1", match_method=MatchMethod.EXACT_ID,
                             open_entity_count=1))
    assert ra.claim.binding_claim_id != rb.claim.binding_claim_id
    assert a.get(rb.claim.binding_claim_id) is None


def test_wrong_tenant_human_assertion_fails_closed(conn):
    _human(conn, "tenant-a")
    hb = _human(conn, "tenant-b", "owner:b")
    a = M6Machine(conn, tenant="tenant-a")
    with pytest.raises(GuardNotSatisfied):
        a.assert_human(subject_ref=_subject(conn, "tenant-a"), entity_ref="l", decision_ref="d",
                       decision_human_id=hb, actor_id=hb)


# ---- transport: co-commit, idempotency, replay, parking ----------------------------------------

def test_state_and_event_co_commit(m6, conn):
    r = m6.propose(_exact(conn))
    assert m6.get(r.claim.binding_claim_id) is not None
    assert conn.execute(
        "SELECT COUNT(*) FROM event_outbox WHERE tenant = ? AND event_name = 'ClaimProposed'",
        (TENANT,)).fetchone()[0] == 1


def test_f6_proposals_declare_no_strict_predecessor(m6, conn):
    from freight_recon.event_envelope import EventEnvelope
    r = m6.link(_exact(conn))
    rows = conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = ? "
        "AND aggregate_id = ?", (TENANT, AGGREGATE_TYPE, r.claim.binding_claim_id)).fetchall()
    for row in rows:
        assert EventEnvelope.from_json(row["envelope_json"]).previous_aggregate_version is None


def test_replay_preserves_owner_asserted_byte_identical(m6, conn):
    """§34 / ADR-007 §7: every OWNER_ASSERTED binding replays byte-identical — the fold reproduces
    the owner's provenance from the event, it never re-derives it."""
    h = _human(conn)
    r = m6.assert_human(subject_ref=_subject(conn), entity_ref="load:4471", decision_ref="d",
                        decision_human_id=h, actor_id=h)
    before = dict(conn.execute(
        "SELECT * FROM identity_binding_claims WHERE tenant = ? AND binding_claim_id = ?",
        (TENANT, r.claim.binding_claim_id)).fetchone())
    rebuilt = m6.rebuild(r.claim.binding_claim_id)
    after = dict(conn.execute(
        "SELECT * FROM identity_binding_claims WHERE tenant = ? AND binding_claim_id = ?",
        (TENANT, r.claim.binding_claim_id)).fetchone())
    assert rebuilt.provenance_class == "OWNER_ASSERTED" and rebuilt.state is BindingState.CONFIRMED
    assert after == before


def test_replay_creates_no_new_claims_or_authority(m6, conn):
    r = m6.link(_exact(conn))
    claims_before = conn.execute(
        "SELECT COUNT(*) FROM identity_binding_claims WHERE tenant = ?", (TENANT,)).fetchone()[0]
    rebuilt = m6.rebuild(r.claim.binding_claim_id)
    assert (rebuilt.new_claims == 0 and rebuilt.rewritten_provenance == 0
            and rebuilt.new_authority == 0 and rebuilt.external_effects == 0)
    assert conn.execute(
        "SELECT COUNT(*) FROM identity_binding_claims WHERE tenant = ?",
        (TENANT,)).fetchone()[0] == claims_before


def test_redelivered_proposal_is_a_no_op(m6, conn):
    from freight_recon.event_envelope import EventEnvelope
    from freight_recon.event_inbox import DedupInbox
    r = m6.link(_exact(conn))
    rows = conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = ? "
        "AND aggregate_id = ? ORDER BY aggregate_version", (TENANT, AGGREGATE_TYPE,
                                                            r.claim.binding_claim_id)).fetchall()
    stream = [EventEnvelope.from_json(row["envelope_json"]) for row in rows]
    box = DedupInbox(conn, tenant=TENANT, consumer_id="m6-t", reference_resolver=m6.reference_resolver)
    for e in stream:
        m6.consume_event(e, inbox=box)
    for e in stream:
        assert m6.consume_event(e, inbox=box).consume.is_noop


def test_correction_before_confirmation_is_parked(m6, conn):
    import uuid

    from freight_recon.event_contracts import CONTRACTS
    from freight_recon.event_envelope import EventEnvelope
    from freight_recon.event_inbox import DedupInbox
    h = _human(conn)
    p = m6.propose(_exact(conn, entity="load:4471"))
    ts = "2026-08-25T10:00:00.000Z"
    corrected = EventEnvelope(
        event_id=str(uuid.uuid4()), event_name="ClaimCorrected",
        event_version=CONTRACTS["ClaimCorrected"].current_version, occurred_at=ts, recorded_at=ts,
        tenant_id=TENANT, aggregate_type=AGGREGATE_TYPE, aggregate_id=p.claim.binding_claim_id,
        aggregate_version=9, previous_aggregate_version=None, causation_id=None,
        correlation_id=p.claim.binding_claim_id, producer_component="identity_service",
        producer_transition_id="IB-7", actor_type="human", actor_id=h,
        trace_id="t-park", payload={"decision_ref": "d", "prior": "load:4471", "new": "load:44718",
                                    "provenance_class": "OWNER_ASSERTED"})
    box = DedupInbox(conn, tenant=TENANT, consumer_id="m6-park",
                     reference_resolver=m6.reference_resolver)
    parked = m6.consume_event(corrected, inbox=box)
    assert parked.consume.outcome.value == "PARKED_MISSING_AGGREGATE"
    # The confirmation lands, then the parked correction drains — never dropped.
    m6.resolve(p.claim.binding_claim_id, _exact_for(p.claim.subject_ref))
    drained = m6.consume_event(corrected, inbox=box)
    assert drained.consume.outcome.value == "APPLIED"
    assert m6.get(p.claim.binding_claim_id).state is BindingState.CORRECTED


# ---- GR-1: illegal transitions ------------------------------------------------------------------

def test_illegal_transition_is_recorded_to_audit_and_security(m6, conn):
    r = m6.link(_exact(conn))       # CONFIRMED
    # Rejecting a CONFIRMED claim is not enumerated (IB-8 is {PROPOSED,AMBIGUOUS} -> REJECTED).
    with pytest.raises(IllegalTransition):
        m6.reject(r.claim.binding_claim_id)
    sec = [row["event_type"] for row in conn.execute(
        "SELECT event_type FROM security_events WHERE tenant = ?", (TENANT,))]
    assert "IllegalTransitionAttempted" in sec


# ---- the migration & the seams ------------------------------------------------------------------

def test_a_legacy_database_migrates_to_the_canonical_claim_shape():
    from fixtures.legacy_workspace import build_legacy_workspace
    from freight_recon.migrations.phase2_tenant_first import OwnerAssertion, migrate
    tmp = Path(tempfile.mkdtemp(prefix="p6m6-mig-"))
    legacy = tmp / "legacy.db"
    build_legacy_workspace(legacy)
    migrate(str(legacy), assertion=OwnerAssertion(
        actor_id="rasheed@neyma", tenant="acme-brokerage", scope="all legacy rows",
        operational_basis="sole workspace onboarded for Acme; verified against record",
        evidence_reference="docs/onboarding/acme.md"), dry_run=False)
    migrated = sqlite3.connect(legacy)
    migrated.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(migrated)
    tables = {r[0] for r in migrated.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "identity_binding_claims" in tables
    assert schema_readiness_problems(migrated) == []
    assert phase6_identity_binding_claims_readiness_problems(migrated) == []


def test_m6_builds_no_m7_conflict_machine():
    """M6 does not itself build the M7 Conflict machine: neither its migration nor its module creates
    the `conflicts` / `conflict_parties` tables, and it mints none of the CF-owned Conflict* events.

    ### UPDATED AT THE M7 LANDING. The canonical schema now DOES carry `conflicts` and
    `conflict_parties` — M7 (a separate unit) built them, and `identity_binding_claim.py` is BYTE-
    UNCHANGED (task §3.6). The property this node protects is unchanged: M6 owns none of that shape.
    Asserting the tables were absent from the whole database was the M6-era spelling of that property;
    the durable spelling is that M6's OWN migration and module create nothing of M7's."""
    from freight_recon.migrations.phase6_identity_binding_claims import P6IBC_TENANT_TABLES
    assert "conflicts" not in P6IBC_TENANT_TABLES and "conflict_parties" not in P6IBC_TENANT_TABLES
    m6_src = (ROOT / "src" / "freight_recon" / "identity_binding_claim.py").read_text(encoding="utf-8")
    m6_mig = (ROOT / "src" / "freight_recon" / "migrations"
              / "phase6_identity_binding_claims.py").read_text(encoding="utf-8")
    for text in (m6_src, m6_mig):
        assert "CREATE TABLE conflicts" not in text
        assert "CREATE TABLE conflict_parties" not in text
    minted = _emitted_event_names()
    for forbidden in ("ConflictOpened", "ConflictEscalated", "ConflictResolved",
                      "ConflictPartyAttached"):
        assert forbidden not in minted
    # But ConflictRaised IS minted — IB-6 is a registered producer (task §3.7).
    assert "ConflictRaised" in minted


def test_m6_builds_no_m10_compensation_machine_and_fabricates_no_compensation():
    conn = _conn()
    # M10 (the Compensation) LANDED after M9, so `compensations` is now canonical (rule 20). M6 still
    # builds no compensation machine and fabricates no compensation: the table is EMPTY after M6's
    # correction, and M6 mints none of M10's F10 events.
    assert conn.execute("SELECT COUNT(*) FROM compensations").fetchone()[0] == 0
    minted = _emitted_event_names()
    for forbidden in ("CompensationRequired", "CompensationCompleted", "CompensationApproved",
                      "CorrectionInvalidatedAnEffect"):
        assert forbidden not in minted


def test_m6_does_not_emit_the_f14_provenance_strengthening_event():
    """§3.10: the laundering REFUSAL is mandatory and present, but the F14 emission
    (ProvenanceStrengtheningAttempted) is Implementation Phase 7's, not M6's."""
    assert "ProvenanceStrengtheningAttempted" not in _emitted_event_names()


def _emitted_event_names() -> set[str]:
    src = (ROOT / "src" / "freight_recon" / "identity_binding_claim.py").read_text(encoding="utf-8")
    names: set[str] = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Call):
            for kw in node.keywords:
                if kw.arg == "event_name" and isinstance(kw.value, ast.Constant):
                    names.add(str(kw.value.value))
    return names | set(PRODUCED_CONTRACTS)


def test_m6_ships_dark():
    """Nothing under src/freight_recon/ imports identity_binding_claim, and the only script that may
    is the probe. Discovered by scanning, never by an enumerated file list."""
    importers: list[str] = []
    inspected = 0
    for path in sorted((ROOT / "src" / "freight_recon").rglob("*.py")) + \
            sorted((ROOT / "scripts").rglob("*.py")):
        if path.name == "identity_binding_claim.py":
            continue
        inspected += 1
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and \
                    node.module.split(".")[-1] == "identity_binding_claim":
                importers.append(path.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.split(".")[-1] == "identity_binding_claim":
                        importers.append(path.name)
    assert inspected > 20, f"the sweep inspected {inspected} modules; it proves nothing"
    assert set(importers) <= {"probe_phase6_identity_binding_claim.py"}, (
        f"M6 has importers outside the permitted probe: {sorted(set(importers))}. M6 ships dark.")


def test_m6_mints_no_gate_and_imports_no_effect_authority():
    src = (ROOT / "src" / "freight_recon" / "identity_binding_claim.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id not in ("GateRegistry", "GateEntry"), "M6 built a gate (rule 17)"
        if isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[-1] not in (
                "checkpoint", "external_effect", "approval"), (
                "M6 imports an effect/approval/checkpoint authority — it authorizes nothing")


def test_m6_does_not_rename_m5_reconcile_constant():
    """§3.5: M6 uses the canonical `RECONCILIATION`; M5's `RECONCILE` constant is unchanged."""
    from freight_recon.migrations.phase6_observations import DETERMINISTIC_MATCH_METHODS
    from freight_recon.migrations.phase6_identity_binding_claims import MATCH_METHODS
    assert "RECONCILE" in DETERMINISTIC_MATCH_METHODS      # M5, byte-unchanged
    assert "RECONCILIATION" in MATCH_METHODS               # M6, canonical
    assert "RECONCILIATION" not in DETERMINISTIC_MATCH_METHODS
