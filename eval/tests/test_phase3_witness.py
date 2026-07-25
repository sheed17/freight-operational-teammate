"""Phase 3 — the Checkpoint Witness: unconstructable, immutable, single-use, 1:1.

The adversarial battery from entities/05-checkpoint-witness.md §44, executed for real: every
forgery route the Python runtime offers is tried, and every one must mint nothing.
"""

from __future__ import annotations

import ast
import copy
import pickle
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase3_kit import (  # noqa: E402
    Clock,
    assert_no_partial_state,
    green_scenario,
    make_kernel,
    make_store,
    params_for,
)

import freight_recon.checkpoint as cp  # noqa: E402
from freight_recon.checkpoint import (  # noqa: E402
    CheckpointError,
    CheckpointPassed,
    claim_grant_cas,
    mint_grant,
    run_checkpoint,
    seven_step_checkpoint,
)


def _authorized(tmp_path):
    store, kernel, clock, effect, facts, versions, approval, world, inputs, request = (
        green_scenario(tmp_path))
    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized, f"green scenario refused: {outcome}"
    return store, kernel, clock, effect, request, outcome


# ------------------------------------------------------------------ unconstructability

def test_witness_has_no_public_constructor():
    with pytest.raises(CheckpointError):
        CheckpointPassed()
    with pytest.raises(CheckpointError):
        CheckpointPassed(object(), checkpoint_id="x", tenant="t", commit_key="k")


def test_a_subclass_of_checkpoint_passed_cannot_exist():
    with pytest.raises(CheckpointError):
        class Impostor(CheckpointPassed):  # noqa: N801
            pass


def test_a_hollow_object_new_shell_mints_nothing(tmp_path):
    store, kernel, clock, effect, request, outcome = _authorized(tmp_path)
    shell = object.__new__(CheckpointPassed)
    with pytest.raises(CheckpointError, match="not produced by the checkpoint function"):
        mint_grant(
            kernel, witness=shell, request=request,
            gate_entry=kernel.gates.gate_for("raise_invoice"), approval=None,
            material_facts_fingerprint="forged", approval_fingerprint=None, entity_versions={},
            brake_token="forged", projected_observations=(), native_claims=(), now=clock.now)
    store.close()


def test_a_pickled_or_copied_pass_cannot_exist(tmp_path):
    """Freshness does not serialize: pickling, copying and deep-copying all raise, so a witness
    cannot be smuggled across a process boundary or duplicated for a second mint."""
    # A genuine pass is only reachable inside the checkpoint; take the refusal from the types.
    shell = object.__new__(CheckpointPassed)
    with pytest.raises(CheckpointError):
        pickle.dumps(shell)
    with pytest.raises(CheckpointError):
        copy.copy(shell)
    with pytest.raises(CheckpointError):
        copy.deepcopy(shell)


def test_a_reconstructed_pass_from_the_stored_witness_row_mints_nothing(tmp_path):
    """THE REPLAY CASE at P3 depth: rebuild a CheckpointPassed from durable history (the witness
    row) and attempt to mint. Replay reconstructs state; it can never construct authority
    (AC-SAFE-019, C-5)."""
    store, kernel, clock, effect, request, outcome = _authorized(tmp_path)
    row = store.conn.execute("SELECT * FROM checkpoint_witnesses").fetchone()
    replayed = object.__new__(CheckpointPassed)
    # the attacker even sets the real attributes from history
    object.__setattr__(replayed, "checkpoint_id", row["checkpoint_id"])
    object.__setattr__(replayed, "tenant", row["tenant"])
    object.__setattr__(replayed, "commit_key", row["commit_key"])
    object.__setattr__(replayed, "_consumed", False)
    grants_before = store.conn.execute("SELECT COUNT(*) FROM effect_grants").fetchone()[0]
    with pytest.raises(CheckpointError):
        mint_grant(
            kernel, witness=replayed, request=request,
            gate_entry=kernel.gates.gate_for("raise_invoice"), approval=None,
            material_facts_fingerprint=row["material_facts_fingerprint"],
            approval_fingerprint=None, entity_versions={}, brake_token=row["brake_version"],
            projected_observations=(), native_claims=(), now=clock.now)
    grants_after = store.conn.execute("SELECT COUNT(*) FROM effect_grants").fetchone()[0]
    assert grants_after == grants_before, "replay minted a grant"
    store.close()


def test_only_the_checkpoint_module_constructs_a_genuine_pass():
    """Structural (AST over the whole src tree): `_mint_checkpoint_passed` is called exactly once,
    inside checkpoint.py's own success path, and `CheckpointPassed(` is never constructed
    positionally anywhere else. The population is every src module, printed."""
    src = ROOT / "src"
    files = sorted(src.rglob("*.py"))
    assert len(files) >= 60, f"src population collapsed: {len(files)} files"
    factory_calls: list[str] = []
    ctor_calls: list[str] = []
    for f in files:
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                name = getattr(node.func, "id", getattr(node.func, "attr", ""))
                if name == "_mint_checkpoint_passed":
                    factory_calls.append(f.name)
                if name == "CheckpointPassed":
                    ctor_calls.append(f.name)
    assert factory_calls == ["checkpoint.py"], (
        f"the genuine-pass factory must be called exactly once, in checkpoint.py: {factory_calls}")
    assert set(ctor_calls) <= {"checkpoint.py"}, (
        f"CheckpointPassed constructed outside the kernel: {ctor_calls}")


# ------------------------------------------------------------------ single-use and 1:1

def test_a_consumed_pass_cannot_mint_twice(tmp_path):
    """Capture the genuine pass a real green checkpoint minted with, then try to mint again
    from it: single-use means the second mint refuses (witness : grant = 1 : 1)."""
    captured: list = []
    original = cp._mint_checkpoint_passed

    def capture(**kwargs):
        passed = original(**kwargs)
        captured.append(passed)
        return passed

    cp._mint_checkpoint_passed = capture
    try:
        store, kernel, clock, effect, request, outcome = _authorized(tmp_path)
    finally:
        cp._mint_checkpoint_passed = original
    assert len(captured) == 1 and captured[0]._consumed is True
    with pytest.raises(CheckpointError, match="already consumed"):
        mint_grant(
            kernel, witness=captured[0], request=request,
            gate_entry=kernel.gates.gate_for("raise_invoice"), approval=None,
            material_facts_fingerprint="x", approval_fingerprint=None, entity_versions={},
            brake_token="b", projected_observations=(), native_claims=(), now=clock.now)
    store.close()


def test_witness_to_grant_is_one_to_one_in_the_database(tmp_path):
    store, kernel, clock, effect, request, outcome = _authorized(tmp_path)
    w = outcome.witness
    with pytest.raises(Exception):  # UNIQUE (tenant, grant_id)
        store.conn.execute(
            """INSERT INTO checkpoint_witnesses (
                tenant, checkpoint_id, grant_id, actor, accountable_owner, action_class,
                target_system, target_resource_id, target_operation, commit_key,
                material_facts_fingerprint, entity_versions_json, approval_id,
                approval_fingerprint, policy_version, gate_decision, autonomy_state,
                brake_version, projected_observations_json, native_claims_json,
                created_at, expires_at)
            VALUES (?, 'cp-second', ?, 'x', 'x', 'a', 't', 'r', 'o', 'ck', 'fp', '{}', 'ap',
                    'apf', 'pv', 'HUMAN_APPROVAL_REQUIRED', 'H', 'bv', '[]', '[]',
                    '2026-01-01T00:00:00+00:00', '2026-01-01T00:01:00+00:00')""",
            (w.tenant, w.grant_id))
    store.conn.rollback()
    store.close()


def test_a_witness_row_cannot_reference_a_nonexistent_grant(tmp_path):
    store = make_store(tmp_path)
    with pytest.raises(Exception):  # tenant-consistent FK
        store.conn.execute(
            """INSERT INTO checkpoint_witnesses (
                tenant, checkpoint_id, grant_id, actor, accountable_owner, action_class,
                target_system, target_resource_id, target_operation, commit_key,
                material_facts_fingerprint, entity_versions_json, approval_id,
                approval_fingerprint, policy_version, gate_decision, autonomy_state,
                brake_version, projected_observations_json, native_claims_json,
                created_at, expires_at)
            VALUES ('tenant-alpha', 'cp-x', 'grant-that-does-not-exist', 'x', 'x', 'a', 't',
                    'r', 'o', 'ck', 'fp', '{}', 'ap', 'apf', 'pv', 'HUMAN_APPROVAL_REQUIRED',
                    'H', 'bv', '[]', '[]', '2026-01-01T00:00:00+00:00',
                    '2026-01-01T00:01:00+00:00')""")
    store.conn.rollback()
    store.close()


# ------------------------------------------------------------------ immutability [C-8]

def test_the_witness_table_refuses_update_and_delete(tmp_path):
    store, kernel, clock, effect, request, outcome = _authorized(tmp_path)
    import sqlite3
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        store.conn.execute("UPDATE checkpoint_witnesses SET actor = 'tampered'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        store.conn.execute("DELETE FROM checkpoint_witnesses")
    store.conn.rollback()
    # the row is byte-identical after both attempts
    row = store.conn.execute("SELECT actor FROM checkpoint_witnesses").fetchone()
    assert row["actor"] == "pipeline"
    store.close()


def test_a_witness_with_a_null_gate_decision_is_not_insertable(tmp_path):
    store, kernel, clock, effect, request, outcome = _authorized(tmp_path)
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            """INSERT INTO checkpoint_witnesses (
                tenant, checkpoint_id, grant_id, actor, accountable_owner, action_class,
                target_system, target_resource_id, target_operation, commit_key,
                material_facts_fingerprint, entity_versions_json, approval_id,
                approval_fingerprint, policy_version, gate_decision, autonomy_state,
                brake_version, projected_observations_json, native_claims_json,
                created_at, expires_at)
            VALUES ('tenant-alpha', 'cp-null', ?, 'x', 'x', 'a', 't', 'r', 'o', 'ck2', 'fp',
                    '{}', 'ap', 'apf', 'pv', NULL, 'H', 'bv', '[]', '[]',
                    '2026-01-01T00:00:00+00:00', '2026-01-01T00:01:00+00:00')""",
            (outcome.witness.grant_id + "-x",))
    store.conn.rollback()
    store.close()


def test_witness_expiry_must_exceed_creation(tmp_path):
    store, kernel, clock, effect, request, outcome = _authorized(tmp_path)
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            """INSERT INTO checkpoint_witnesses (
                tenant, checkpoint_id, grant_id, actor, accountable_owner, action_class,
                target_system, target_resource_id, target_operation, commit_key,
                material_facts_fingerprint, entity_versions_json, approval_id,
                approval_fingerprint, policy_version, gate_decision, autonomy_state,
                brake_version, projected_observations_json, native_claims_json,
                created_at, expires_at)
            VALUES ('tenant-alpha', 'cp-backwards', 'g-x', 'x', 'x', 'a', 't', 'r', 'o', 'ck3',
                    'fp', '{}', 'ap', 'apf', 'pv', 'HUMAN_APPROVAL_REQUIRED', 'H', 'bv', '[]',
                    '[]', '2026-01-01T00:01:00+00:00', '2026-01-01T00:00:00+00:00')""")
    store.conn.rollback()
    store.close()


# ------------------------------------------------------------------ freshness at the claim

def test_a_stale_witness_is_refused_at_the_claim_and_recorded(tmp_path):
    """AC-SAFE-002: a valid grant with a stale witness is refused — the grant alone is
    insufficient. The refusal is a durable StaleWitnessUsed security event."""
    from datetime import timedelta
    store = make_store(tmp_path)
    # witness window shorter than grant TTL: the witness goes stale while the grant still lives
    kernel, clock = make_kernel(
        store, witness_window=timedelta(seconds=30), grant_ttl=timedelta(seconds=300))
    from phase3_kit import (
        CheckpointInputs, CheckpointRequest, live_reader, make_approval, make_effect, make_facts,
    )
    effect = make_effect()
    facts = make_facts()
    versions = {"load:4471": 17}
    approval = make_approval(effect, facts, versions, clock)
    inputs = CheckpointInputs(
        material_facts_reader=live_reader(lambda: dict(facts)),
        projection_assertion={"status": "DELIVERED"},
        projected_state_reader=live_reader({"status": "DELIVERED"}),
        entity_version_reader=live_reader({"load:4471": 17}),
        approval=approval)
    request = CheckpointRequest(
        effect=effect, actor="pipeline", accountable_owner="owner:rasheed",
        target_entity_ref="load:4471")
    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized
    clock.advance(seconds=31)  # the approval wait: witness stale, grant alive
    claim = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    assert claim.claimed is False and claim.cause == "STALE_WITNESS"
    grant = store.conn.execute("SELECT state FROM effect_grants WHERE grant_id = ?",
                               (outcome.handle.grant_id,)).fetchone()
    assert grant["state"] == "GRANTED", "a stale-witness refusal must not consume the grant"
    events = [e["event_type"] for e in store.security_events()]
    assert "StaleWitnessUsed" in events
    assert_no_partial_state(store, effect.key())
    store.close()


def test_the_two_canonical_names_are_the_same_checkpoint():
    assert seven_step_checkpoint is run_checkpoint


# ------------------------------------------------------------------ no async in the kernel

def test_the_kernel_contains_no_asynchronous_work():
    """AC-SAFE-005's P3 share, structurally: no async def, no await, no sleeping, no scheduling
    inside the checkpoint module — the seven reads, the witness insert and the mint are one
    synchronous transaction, and nothing yields between them."""
    tree = ast.parse((ROOT / "src" / "freight_recon" / "checkpoint.py").read_text(encoding="utf-8"))
    offenders = [
        type(node).__name__
        for node in ast.walk(tree)
        if isinstance(node, (ast.AsyncFunctionDef, ast.Await, ast.AsyncFor, ast.AsyncWith))
    ]
    assert offenders == [], f"asynchronous constructs in the checkpoint kernel: {offenders}"
    source = (ROOT / "src" / "freight_recon" / "checkpoint.py").read_text(encoding="utf-8")
    for forbidden in ("time.sleep", "asyncio", "threading.Timer"):
        assert forbidden not in source, f"{forbidden} has no business inside the checkpoint kernel"
