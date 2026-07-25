"""P3 x P2 ledger compatibility — the regression battery for independent-review finding F-C.

THE DEFECT, STATED ONCE. Phase 2's `effect_grants` consumers were written against
`UNIQUE (tenant, commit_key)` STRICT: "the reservation for this Commit Key" was a total function
returning one row or none. Phase 3 REPLACED that index with the LIVE-HOLD partial form so a
provably-dead grant frees its key for the safe re-checkpoint the crash semantics require. Correct
— and it silently invalidated the assumption under `operation_commit_claim`,
`release_operation_commit`, `update_operation_commit_payload` and `legacy_commit_rows`.

The independent reviewer reproduced two failures. Both are reproduced here, by construction:

  1. a dead P3 grant row plus a live legacy reservation on the same (tenant, commit_key) —
     `operation_commit_claim` returned the DEAD row, and the operation router chooses DONE vs
     ESCALATED from that row's payload status;
  2. `release_operation_commit` — idempotent by contract, called on failure paths — raised
     `sqlite3.IntegrityError: FOREIGN KEY constraint failed`, because its unqualified DELETE
     reached a checkpoint-bound grant that `checkpoint_witnesses` references.

These are not P4 concerns. The schema change is in the tree now, and so are both defects.

Every test below builds its state through the REAL kernel and the REAL store — no hand-inserted
rows standing in for the thing under test — so a future change to either writer is caught here.
"""

from __future__ import annotations

import sqlite3
from dataclasses import replace
from datetime import timedelta

import pytest

from phase3_kit import (
    T_A,
    T_B,
    checkpoint_and_claim,
    green_scenario,
    make_store,
)

from freight_recon.checkpoint import (
    CheckpointInputs,
    expire_unclaimed,
    revoke_unclaimed,
    run_checkpoint,
)
from freight_recon.workflow import WorkflowError


LIVE = ("GRANTED", "CLAIMED", "ATTEMPTED", "VERIFIED", "UNKNOWN_OUTCOME")
DEAD = ("EXPIRED_UNCLAIMED", "REVOKED", "FAILED")


def _rows(store, commit_key):
    return store.conn.execute(
        "SELECT * FROM effect_grants WHERE tenant = ? AND commit_key = ? ORDER BY grant_id",
        (store.tenant, commit_key),
    ).fetchall()


def _legacy_reserve(store, commit_key, *, status="RESERVED", load_ref="load:4471"):
    return store.claim_operation_commit(
        commit_key=commit_key, target_system="tms:truckingoffice", lane="raise_invoice",
        load_ref=load_ref, party="Acme Logistics", approved_amount="2850.00",
        payload={"status": status, "summary": "raise invoice"},
    )


def _dead_p3_grant(tmp_path, *, how: str):
    """A real, provably-dead P3 grant produced by the real kernel, plus its live witness row.

    Returns (store, kernel, commit_key). `how` selects the death: expiry (the crash-after-commit
    shape) or revocation (the deliberate-withdrawal shape). Both free the Commit Key.
    """
    store, kernel, clock, effect, _facts, _versions, _approval, _world, inputs, request = (
        green_scenario(tmp_path))
    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized, f"setup failed: {getattr(outcome, 'reason', '')}"
    if how == "expired":
        clock.advance(seconds=120)
        assert expire_unclaimed(kernel) == 1
    else:
        assert revoke_unclaimed(
            kernel, grant_id=outcome.handle.grant_id, cause="brake engaged", actor="owner:rasheed")
    commit_key = effect.key()
    states = [r["state"] for r in _rows(store, commit_key)]
    assert states and all(s in DEAD for s in states), f"setup did not produce a dead grant: {states}"
    return store, kernel, commit_key


# ============================================================ reviewer failure 1: wrong row


@pytest.mark.parametrize("how", ["expired", "revoked"])
def test_dead_p3_history_beside_a_live_legacy_reservation_returns_the_reservation(tmp_path, how):
    """REVIEWER FAILURE 1, verbatim shape: dead P3 row + live legacy reservation.

    The pre-fix `SELECT ... fetchone()` returned whichever row SQLite reached first. Asserting on
    the STATE and the PAYLOAD (not merely on non-None) is what makes this test discriminate: a
    dead row is also a row, and the old code returned one.
    """
    store, _kernel, commit_key = _dead_p3_grant(tmp_path, how=how)

    assert _legacy_reserve(store, commit_key) is True, (
        "the dead grant must not block a new legacy reservation - freeing the key is the entire "
        "reason the live-hold index replaced the strict one"
    )

    seen = [r["state"] for r in _rows(store, commit_key)]
    assert sorted(seen) == sorted([*(s for s in seen if s in DEAD), "GRANTED"]), seen
    assert len(seen) == 2, f"the test needs BOTH rows present to be meaningful: {seen}"

    claim = store.operation_commit_claim(commit_key=commit_key)
    assert claim is not None, "the live reservation reads as absent - dead history masked it"
    assert claim["payload"]["status"] == "RESERVED", (
        f"operation_commit_claim returned the WRONG ROW: {claim!r}. The caller chooses DONE vs "
        "ESCALATED from this payload, so a dead row here is a false receipt or a false repeat."
    )


def test_dead_history_alone_is_not_a_reservation(tmp_path):
    """Dead history is evidence, never a reservation. `None` is the honest answer."""
    store, _kernel, commit_key = _dead_p3_grant(tmp_path, how="expired")
    assert _rows(store, commit_key), "population empty - this test would pass vacuously"
    assert store.operation_commit_claim(commit_key=commit_key) is None, (
        "a provably-dead grant was reported as a live reservation"
    )


def test_a_live_p3_grant_is_visible_as_the_one_live_reservation(tmp_path):
    """The complement: a LIVE checkpoint-bound grant holds the key, so it must not read as absent.

    This is the fail-closed direction. The router escalates when it cannot confirm a reservation,
    and a live P3 grant holding the key is exactly a thing it must not blindly write over.
    """
    store, kernel, _clock, effect, _facts, _versions, _approval, _world, inputs, request = (
        green_scenario(tmp_path))
    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized
    commit_key = effect.key()

    assert _legacy_reserve(store, commit_key) is False, (
        "a live grant already holds this Commit Key; a second live reservation must be refused"
    )
    claim = store.operation_commit_claim(commit_key=commit_key)
    assert claim is not None and claim["commit_key"] == commit_key


def test_legacy_commit_rows_never_reports_a_checkpoint_bound_grant(tmp_path):
    """`legacy_commit_rows` is the pre-Phase-1 compatibility bridge. A P3 grant is not one.

    Its caller ESCALATES on any row returned, so a P3 grant leaking in would report a historical
    double-commit that never happened.
    """
    store, _kernel, _ck = _dead_p3_grant(tmp_path, how="expired")
    p3_states = [r["state"] for r in store.conn.execute(
        "SELECT state FROM effect_grants WHERE tenant = ? AND checkpoint_id IS NOT NULL",
        (store.tenant,)).fetchall()]
    assert p3_states, "no checkpoint-bound row exists - this guard would prove nothing"

    rows = store.legacy_commit_rows(
        lane="raise_invoice", load_ref="load:4471", party="Acme Logistics",
        canonical_commit_key="some-other-canonical-key")
    assert rows == [], f"a checkpoint-bound P3 grant was reported as pre-migration evidence: {rows}"


# ============================================================ reviewer failure 2: the FK error


@pytest.mark.parametrize("how", ["expired", "revoked"])
def test_release_operation_commit_is_idempotent_and_does_not_raise_the_foreign_key_error(
    tmp_path, how
):
    """REVIEWER FAILURE 2, verbatim shape.

    Pre-fix, the unqualified DELETE reached the checkpoint-bound grant, which
    `checkpoint_witnesses` references, and raised `sqlite3.IntegrityError: FOREIGN KEY constraint
    failed` out of a method contractually required to be safe on a repeated failure path.

    Three properties, all asserted: it does not raise; it is idempotent; and it deletes only what
    it owns - the witness and its grant must both survive.
    """
    store, _kernel, commit_key = _dead_p3_grant(tmp_path, how=how)
    assert _legacy_reserve(store, commit_key) is True

    witness_before = store.conn.execute(
        "SELECT COUNT(*) FROM checkpoint_witnesses WHERE tenant = ?", (store.tenant,)
    ).fetchone()[0]
    assert witness_before == 1, "no witness row exists - the FK could not fire and this proves nothing"

    try:
        store.release_operation_commit(commit_key=commit_key)
        store.release_operation_commit(commit_key=commit_key)   # idempotent: the second is a no-op
    except sqlite3.IntegrityError as exc:  # pragma: no cover - this IS the reported defect
        pytest.fail(f"release_operation_commit raised the reviewer's foreign-key error: {exc}")
    except WorkflowError as exc:  # pragma: no cover
        pytest.fail(f"release_operation_commit refused a legitimate release: {exc}")

    after = _rows(store, commit_key)
    assert [r["state"] for r in after] and all(r["state"] in DEAD for r in after), (
        f"release deleted P3 dead-state history instead of only its own reservation: "
        f"{[(r['state'], r['checkpoint_id']) for r in after]}"
    )
    assert all(r["checkpoint_id"] is not None for r in after), "a legacy row survived the release"
    assert store.conn.execute(
        "SELECT COUNT(*) FROM checkpoint_witnesses WHERE tenant = ?", (store.tenant,)
    ).fetchone()[0] == witness_before, "the append-only witness was destroyed by a legacy release"


def test_release_never_deletes_a_live_checkpoint_bound_grant(tmp_path):
    """The dangerous variant: a LIVE P3 grant beside a legacy release call.

    Deleting it would erase an outstanding authorization while the world may already have been
    touched — the launderable state the ledger exists to prevent.
    """
    store, kernel, _clock, effect, _facts, _versions, _approval, _world, inputs, request = (
        green_scenario(tmp_path))
    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized
    commit_key = effect.key()

    store.release_operation_commit(commit_key=commit_key)   # must be a no-op, not a deletion

    rows = _rows(store, commit_key)
    assert len(rows) == 1 and rows[0]["state"] == "GRANTED", (
        f"a live checkpoint-bound grant was released by the legacy path: {[r['state'] for r in rows]}"
    )


def test_foreign_key_enforcement_is_actually_on(tmp_path):
    """The FK must be REAL, or every assertion above about it is decoration.

    Proven by observing the constraint fire on a direct delete, not by reading the pragma.
    """
    store, _kernel, _ck = _dead_p3_grant(tmp_path, how="expired")
    grant_id = store.conn.execute(
        "SELECT grant_id FROM checkpoint_witnesses WHERE tenant = ?", (store.tenant,)
    ).fetchone()["grant_id"]
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute("DELETE FROM effect_grants WHERE tenant = ? AND grant_id = ?",
                           (store.tenant, grant_id))
    store.conn.rollback()


# ============================================================ the invariants F-C must preserve


def test_update_payload_still_targets_exactly_one_row_beside_dead_history(tmp_path):
    """`update_operation_commit_payload`'s strict rowcount==1 must remain TRUE, not merely strict.

    With dead P3 history sharing the key, the unscoped UPDATE matched 2 rows and the method raised
    on a correct call — turning a safety assertion into a false alarm on the crash path.
    """
    store, _kernel, commit_key = _dead_p3_grant(tmp_path, how="expired")
    assert _legacy_reserve(store, commit_key) is True

    store.update_operation_commit_payload(
        commit_key=commit_key, payload={"status": "NEEDS_VERIFICATION", "summary": "crashed"})

    claim = store.operation_commit_claim(commit_key=commit_key)
    assert claim["payload"]["status"] == "NEEDS_VERIFICATION"
    dead_payloads = [r["payload_json"] for r in _rows(store, commit_key)
                     if r["checkpoint_id"] is not None]
    assert dead_payloads and all("NEEDS_VERIFICATION" not in p for p in dead_payloads), (
        "the legacy payload update overwrote a checkpoint-bound grant's payload"
    )


def test_one_live_reservation_per_tenant_and_commit_key_still_holds(tmp_path):
    """The P2 invariant F-C must not trade away: a second live reservation is refused."""
    store = make_store(tmp_path, T_A)
    assert _legacy_reserve(store, "ck-1") is True
    assert _legacy_reserve(store, "ck-1") is False, "two live reservations for one Commit Key"
    rows = _rows(store, "ck-1")
    assert len([r for r in rows if r["state"] in LIVE]) == 1


def test_the_same_commit_key_in_another_tenant_is_a_different_effect(tmp_path):
    """Tenant-first, unchanged by F-C: the scoping added is state/ownership, never cross-tenant."""
    a = make_store(tmp_path, T_A, name="multi.db")
    b = make_store(tmp_path, T_B, name="multi.db")
    assert _legacy_reserve(a, "ck-shared") is True
    assert _legacy_reserve(b, "ck-shared") is True, "tenant B was blocked by tenant A's reservation"
    assert a.operation_commit_claim(commit_key="ck-shared") is not None
    b.release_operation_commit(commit_key="ck-shared")
    assert a.operation_commit_claim(commit_key="ck-shared") is not None, (
        "tenant B's release destroyed tenant A's reservation"
    )


def test_the_live_hold_state_set_is_imported_from_the_migration_that_defines_the_index(tmp_path):
    """A second, drifting copy of the live set is how this class of defect returns.

    The consumers must read the SAME tuple the index is built from — proven by identity of value
    against the migration module, and by the index's own SQL text.
    """
    from freight_recon.migrations.phase3_checkpoint import LIVE_HOLD_STATES, P3_INDEXES
    from freight_recon.workflow import _LIVE_HOLD_STATES

    assert _LIVE_HOLD_STATES == LIVE_HOLD_STATES == LIVE, (
        f"the ledger consumers' live set drifted from the index's: {_LIVE_HOLD_STATES}"
    )
    sql = P3_INDEXES["ix_effect_grants_live_hold"]
    for state in LIVE_HOLD_STATES:
        assert f"'{state}'" in sql, f"{state} is in the consumers' live set but not in the index"


def test_a_re_checkpoint_after_death_still_mints_and_claims(tmp_path):
    """End to end: the crash semantics P3 bought must survive the F-C scoping.

    dead grant -> re-checkpoint -> new grant -> claim, with the dead row retained as evidence.
    """
    store, kernel, clock, effect, facts, versions, approval, world, inputs, request = (
        green_scenario(tmp_path))
    first = run_checkpoint(kernel, request, inputs)
    assert first.authorized
    clock.advance(seconds=120)
    assert expire_unclaimed(kernel) == 1

    approval2 = replace(approval, granted_at=clock.now, expires_at=clock.now + timedelta(hours=1))
    inputs2 = CheckpointInputs(
        material_facts_reader=inputs.material_facts_reader,
        projection_assertion=inputs.projection_assertion,
        projected_state_reader=inputs.projected_state_reader,
        entity_version_reader=inputs.entity_version_reader,
        approval=approval2,
    )
    second, claim = checkpoint_and_claim(kernel, request, inputs2, effect)
    assert second.authorized, f"re-checkpoint refused: {getattr(second, 'reason', '')}"
    assert claim.claimed, f"re-claim refused: {claim.cause}"

    states = sorted(r["state"] for r in _rows(store, effect.key()))
    assert states == ["CLAIMED", "EXPIRED_UNCLAIMED"], states
