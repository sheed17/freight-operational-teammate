"""P6 / M10 — the Compensation — acceptance and hostile battery.

Machine §14 names nine transitions (CM-1…CM-5x); AC-MACH-000 asserts an EXACT SET match against them.
The recovery-and-compensation acceptance (AC-REC-001…005, AC-RACE-013) and the platform-safety mandate
M-33 are exercised by name. The rest of the battery covers the six states, the owner and exposure
invariants, the one-active-per-effect predicate (### M10-AQ-9, verbatim), the compensating effect's own
commit key, the human-approval gate, readback-or-nothing completion, the loud human-owned states, the
shared RealityEstablished (### M10-AQ-5), replay isolation and the ship-dark posture.

### EVERY CORPUS-SCANNING NEGATIVE ASSERTION PROVES ITS POPULATION FIRST (CLAUDE.md §6): an assertion
that "no module does X" first asserts it FOUND the modules it scanned, or it passes over an empty set.
"""

from __future__ import annotations

import ast
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval" / "tests")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_recon.event_contracts import CONTRACTS  # noqa: E402
from freight_recon.fingerprint import Money, MoneyMustNotFloat  # noqa: E402
from freight_recon.schema import (  # noqa: E402
    create_canonical_schema,
    enable_and_verify_foreign_keys,
    schema_readiness_problems,
)
from freight_recon.migrations.phase6_compensations import (  # noqa: E402
    COMPENSATION_STATES,
    phase6_compensations_readiness_problems,
)
from freight_recon.compensation import (  # noqa: E402
    F10_CONTRACTS,
    PRODUCED_CONTRACTS,
    TRANSITIONS,
    CmState,
    MalformedCompensation,
    GuardNotSatisfied,
    IllegalTransition,
    M10Machine,
    OriginalNotCompensable,
    Trigger,
    legal_transitions,
)

import phase6_compensation_kit as ck  # noqa: E402

TENANT = ck.T_A
HUMAN = "owner:sam"
M10_SRC = (ROOT / "src" / "freight_recon" / "compensation.py").read_text(encoding="utf-8")

# The nine canonical transition ids, from machine §14 — the AC-MACH-000 population.
CANONICAL_CM_IDS = ("CM-1", "CM-1r", "CM-2", "CM-2n", "CM-3", "CM-4", "CM-4f", "CM-5", "CM-5x")


class Clock:
    def __init__(self, base: datetime | None = None) -> None:
        self._t = base or datetime(2026, 8, 28, 8, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        from datetime import timedelta
        self._t += timedelta(milliseconds=1)
        return self._t


def _fresh_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(conn)
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    return conn


def _store(tmp_path: Path, tenant: str = TENANT):
    clk = ck.Clock()
    store = ck.make_store(tmp_path, tenant)
    enable_and_verify_foreign_keys(store.conn)
    ck.a_human(store, HUMAN, tenant=tenant, clock=clk)
    return store, clk


def _machine(store, clk, tenant: str = TENANT) -> M10Machine:
    return M10Machine(store.conn, tenant=tenant, clock=clk)


def _required(store, clk, *, grant_state: str = "VERIFIED", tenant: str = TENANT, owner: str = HUMAN,
              exposure: Money | None = None, grant_id: str | None = None):
    """A compensation raised from an original effect in `grant_state`. Returns (machine, TransitionResult,
    original grant id)."""
    gid = ck.an_original_effect_in(store, grant_state, tenant=tenant, grant_id=grant_id, clock=clk)
    dref = ck.a_human_decision(store, tenant=tenant, actor_id=owner, seed=f"d-{gid}", clock=clk)
    m = _machine(store, clk, tenant)
    r = m.raise_from_correction(
        original_effect_id=gid, owner_id=owner, exposure=exposure or Money(285000, "GBP"),
        reason="POD rebound to load 4471", decision_ref=dref)
    return m, r, gid


def _drive_to(store, clk, m, r, gid, *, target: str, pid: str = "pi-cmp", ap: str = "ap-cmp",
              wi: str = "wi-cmp"):
    """Raise → CM-2 → CM-3 → drive the compensating pipeline to `target` → observe. Returns the machine."""
    cid = r.compensation.compensation_id
    original = m._require_original_effect(gid)
    effect = m.compensating_effect(original, cid)
    world = ck.a_world(resource=original.target_resource_id)
    ck.a_granted_m4_approval(store, effect, world, approval_id=ap, tenant=m.tenant, granter=HUMAN, clock=clk)
    m.approve(cid, approval_id=ap, actor_id=HUMAN)
    ck.a_work_item(store, tenant=m.tenant, work_item_id=wi, owner_id=HUMAN, clock=clk)
    m.start_execution(cid, work_item_id=wi, pipeline_instance_id=pid, actor_id="compensation")
    ck.drive_compensating_pipeline(store, effect, world, pipeline_instance_id=pid, tenant=m.tenant,
                                   approval_id=ap, granter=HUMAN, target=target, clock=clk)
    return m


# ============================================================ AC-MACH-000 — the exact set match

def test_ac_mach_000_transition_table_is_the_nine_canonical_rows():
    """### THE ORACLE IS EXACT SET EQUALITY of transition identifiers, not a count (AC-MACH-000). A row
    in §14 with no case, or a case with no §14 row, fails the build. Enumerated from the machine's OWN
    declarative data (TRANSITIONS), never an if/elif."""
    declared = tuple(r.id for r in TRANSITIONS)
    assert set(declared) == set(CANONICAL_CM_IDS)
    assert len(declared) == len(CANONICAL_CM_IDS) == 9
    # CM-5x is the one ILLEGAL row, CM-1r the one refusal-only row.
    by_id = {r.id: r for r in TRANSITIONS}
    assert by_id["CM-5x"].illegal and by_id["CM-5x"].kind.value == "NON_PRODUCING"
    assert by_id["CM-1r"].refusal_only
    # The six canonical states, exactly.
    states = {s.value for row in TRANSITIONS for s in (*row.from_states, *( (row.to_state,) if row.to_state else () ))}
    assert states <= set(COMPENSATION_STATES)
    assert set(COMPENSATION_STATES) == {s.value for s in CmState}


def test_ac_mach_000_timer_fired_has_no_legal_row_at_any_state():
    """### CM-5x: TimerFired is a trigger with no legal row anywhere, so GR-1 refuses it uniformly."""
    for state in CmState:
        assert legal_transitions(state, Trigger.TIMER_FIRED) == ()


# ============================================================ AC-MACH-1001..1009 — per transition

def test_ac_mach_1001_cm_required_from_verified_effect(tmp_path):
    store, clk = _store(tmp_path)
    m, r, _ = _required(store, clk)
    c = m.get(r.compensation.compensation_id)
    assert r.transition_id == "CM-1" and c.state is CmState.REQUIRED
    assert r.event_names == ("CompensationRequired",)
    assert c.owner_id == HUMAN and c.exposure.canonical() == "285000|GBP"


def test_ac_mach_1002_cm_cannot_compensate_unknown(tmp_path):
    """### M-33 / AC-REC-001. UNKNOWN_OUTCOME ⇒ CM-1r: CompensationRefused{unknown}, ZERO rows."""
    store, clk = _store(tmp_path)
    m, r, _ = _required(store, clk, grant_state="UNKNOWN_OUTCOME")
    assert r.transition_id == "CM-1r" and r.refused and r.refusal_cause == "unknown_outcome"
    assert r.event_names == ("CompensationRefused",)
    assert store.conn.execute("SELECT COUNT(*) FROM compensations WHERE tenant=?", (TENANT,)).fetchone()[0] == 0


def test_ac_mach_1003_cm_money_comp_requires_human_approval(tmp_path):
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk)
    cid = r.compensation.compensation_id
    effect = m.compensating_effect(m._require_original_effect(gid), cid)
    world = ck.a_world(resource=m._require_original_effect(gid).target_resource_id)
    ck.a_granted_m4_approval(store, effect, world, approval_id="ap-1", tenant=TENANT, granter=HUMAN, clock=clk)
    r2 = m.approve(cid, approval_id="ap-1", actor_id=HUMAN)
    assert r2.transition_id == "CM-2" and m.get(cid).state is CmState.APPROVED
    assert r2.event_names == ("CompensationApproved",)


def test_ac_mach_1004_cm_not_possible_escalates_honestly(tmp_path):
    store, clk = _store(tmp_path)
    m, r, _ = _required(store, clk, exposure=Money(500000, "GBP"))
    cid = r.compensation.compensation_id
    r2 = m.mark_not_possible(cid, impossibility_evidence="a completed ACH wire has no reversal endpoint")
    assert r2.transition_id == "CM-2n" and m.get(cid).state is CmState.NOT_POSSIBLE
    assert r2.event_names == ("CompensationImpossible",)
    assert m.get(cid).exposure.canonical() == "500000|GBP"  # exposure kept


def test_ac_mach_1005_cm_execution_is_a_full_pipeline(tmp_path):
    """### AC-REC-002 — the compensating effect uses the ORDINARY pipeline: its own witness+grant+
    approval+readback. CM-3 starts a NEW M2 pipeline distinct from the original effect's."""
    store, clk = _store(tmp_path)
    m = _drive_to(store, clk, *_required(store, clk), target="VERIFIED")
    cid = m.owner_queue()[0].compensation_id if m.owner_queue() else None
    # a witness and a grant exist for the compensating pipeline, and it is not the original's.
    assert store.conn.execute("SELECT COUNT(*) FROM checkpoint_witnesses WHERE tenant=?", (TENANT,)).fetchone()[0] >= 1
    grants = [row["grant_id"] for row in store.conn.execute(
        "SELECT grant_id FROM effect_grants WHERE tenant=?", (TENANT,))]
    assert any(g.startswith("grant-") for g in grants)  # the direct-inserted original
    assert any(not g.startswith("grant-") for g in grants)  # the pipeline-minted compensating grant


def test_ac_mach_1006_cm_complete_on_verified(tmp_path):
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk)
    m = _drive_to(store, clk, m, r, gid, target="VERIFIED")
    r4 = m.observe_pipeline(r.compensation.compensation_id, actor_id="compensation")
    assert r4.transition_id == "CM-4" and m.get(r.compensation.compensation_id).state is CmState.COMPLETED
    assert r4.event_names == ("CompensationCompleted",)


def test_ac_mach_1007_cm_failed_non_terminal(tmp_path):
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk, exposure=Money(285000, "GBP"))
    m = _drive_to(store, clk, m, r, gid, target="FAILED")
    r4 = m.observe_pipeline(r.compensation.compensation_id, actor_id="compensation")
    c = m.get(r.compensation.compensation_id)
    assert r4.transition_id == "CM-4f" and c.state is CmState.COMPENSATION_FAILED
    assert not c.is_terminal and c.is_human_owned and c.exposure.canonical() == "285000|GBP"


def test_ac_mach_1008_cm_failed_resolved_only_by_human(tmp_path):
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk)
    m = _drive_to(store, clk, m, r, gid, target="NEEDS_VERIFICATION")
    cid = r.compensation.compensation_id
    m.observe_pipeline(cid, actor_id="compensation")
    assert m.get(cid).state is CmState.COMPENSATION_FAILED
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=HUMAN, seed="r5", clock=clk)
    r5 = m.establish_reality(cid, decision_ref=dref, outcome="VERIFIED", actor_id=HUMAN)
    assert r5.transition_id == "CM-5" and m.get(cid).state is CmState.COMPLETED
    assert r5.event_names == ("RealityEstablished",)


def test_ac_mach_1009_cm_no_timer_moves_failed(tmp_path):
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk)
    m = _drive_to(store, clk, m, r, gid, target="NEEDS_VERIFICATION")
    cid = r.compensation.compensation_id
    m.observe_pipeline(cid, actor_id="compensation")
    with pytest.raises(IllegalTransition):
        m.handle_timer_fired(cid, timer_kind="age")
    assert m.get(cid).state is CmState.COMPENSATION_FAILED  # unmoved
    assert "IllegalTransitionAttempted" in _security(store)


# ============================================================ AC-REC / AC-RACE

def test_ac_rec_001_zero_compensating_calls_on_unknown(tmp_path):
    """### assert ZERO compensating calls — you cannot undo what you cannot prove you did (M-33)."""
    store, clk = _store(tmp_path)
    m, r, _ = _required(store, clk, grant_state="UNKNOWN_OUTCOME")
    assert store.conn.execute("SELECT COUNT(*) FROM compensations WHERE tenant=?", (TENANT,)).fetchone()[0] == 0
    assert store.conn.execute("SELECT COUNT(*) FROM pipeline_instances WHERE tenant=?", (TENANT,)).fetchone()[0] == 0
    assert store.conn.execute("SELECT COUNT(*) FROM checkpoint_witnesses WHERE tenant=?", (TENANT,)).fetchone()[0] == 0
    # exactly one grant — the original UNKNOWN one; no compensating grant was minted.
    assert store.conn.execute("SELECT COUNT(*) FROM effect_grants WHERE tenant=?", (TENANT,)).fetchone()[0] == 1


def test_ac_rec_001_cm1_reads_the_ledger_not_a_flag():
    """### Eligibility is read from the effect_grants row, never a caller flag. `raise_from_correction`
    takes no boolean eligibility parameter — the ONLY signal is the persisted ledger state."""
    tree = ast.parse(M10_SRC)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "raise_from_correction")
    params = {a.arg for a in fn.args.args} | {a.arg for a in fn.args.kwonlyargs}
    assert "original_effect_id" in params  # it takes the id and reads the row
    assert not any("verified" in p.lower() or "eligib" in p.lower() for p in params)
    assert "SELECT grant_id, state" in M10_SRC  # it reads the ledger, not a flag


def test_ac_rec_001_other_six_original_states_create_no_compensation_and_no_variant(tmp_path):
    """### The other six M3 states satisfy no CM-1 guard and mint NO refusal variant (### M10-AQ-10)."""
    store, clk = _store(tmp_path)
    for state in ("FAILED", "REVOKED", "EXPIRED_UNCLAIMED", "GRANTED", "CLAIMED", "ATTEMPTED"):
        with pytest.raises(OriginalNotCompensable):
            _required(store, clk, grant_state=state, grant_id=f"g-{state.lower()}")
    assert store.conn.execute("SELECT COUNT(*) FROM compensations WHERE tenant=?", (TENANT,)).fetchone()[0] == 0
    # exactly ONE refusal cause exists in the corpus, and it is unknown_outcome.
    assert CONTRACTS["CompensationRefused"].fields[1].fixed == "unknown_outcome"


def test_ac_rec_002_compensation_uses_the_ordinary_pipeline(tmp_path):
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk)
    cid = r.compensation.compensation_id
    m = _drive_to(store, clk, m, r, gid, target="VERIFIED")
    comp = m.get(cid)
    # the executing pipeline is a real M2 row, distinct from any original pipeline, with its own grant.
    prow = store.conn.execute(
        "SELECT grant_id, commit_key FROM pipeline_instances WHERE tenant=? AND pipeline_instance_id=?",
        (TENANT, comp.pipeline_instance_id)).fetchone()
    assert prow is not None and prow["grant_id"] is not None
    assert prow["commit_key"] == comp.commit_key  # the compensating effect's own key


def test_ac_rec_003_no_bulk_undo_n_individually_gated(tmp_path):
    """### A correction storm invalidating N effects raises N Compensations, each individually gated —
    its own owner, exposure, approval, pipeline, grant, commit key. No bulk grant, no shared approval."""
    store, clk = _store(tmp_path)
    m = _machine(store, clk)
    cids = []
    for i in range(3):
        gid = ck.a_verified_original_effect(store, tenant=TENANT, grant_id=f"g-storm-{i}",
                                            resource=f"inv-{i}", clock=clk)
        dref = ck.a_human_decision(store, tenant=TENANT, actor_id=HUMAN, seed=f"storm-{i}", clock=clk)
        rr = m.raise_from_correction(original_effect_id=gid, owner_id=HUMAN,
                                     exposure=Money(1000 * (i + 1), "GBP"), reason="storm", decision_ref=dref)
        cids.append(rr.compensation.compensation_id)
    assert len(set(cids)) == 3
    keys = {m.get(c).commit_key for c in cids}
    assert len(keys) == 3  # three distinct commit keys — no shared reservation
    # aggregate exposure may be COMPUTED and shown before approval (entity §43(d)); we compute it.
    total = sum(m.get(c).exposure.amount_minor for c in cids)
    assert total == 1000 + 2000 + 3000


def test_ac_rec_004_compensation_failed_never_auto_resolves(tmp_path):
    """### No timer, no retry loop, no sweep, no reaper, no model moves COMPENSATION_FAILED. There is no
    automatic best-effort retry method on the machine."""
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk)
    m = _drive_to(store, clk, m, r, gid, target="FAILED")
    cid = r.compensation.compensation_id
    m.observe_pipeline(cid, actor_id="compensation")
    with pytest.raises(IllegalTransition):
        m.handle_timer_fired(cid)
    assert m.get(cid).state is CmState.COMPENSATION_FAILED
    for banned in ("def retry", "def sweep", "def reap", "def scan_stale", "def auto_resolve",
                   "def auto_close"):
        assert banned not in M10_SRC


def test_ac_rec_005_and_ac_race_013_crash_and_timeout_reach_compensation_failed(tmp_path):
    """### AC-REC-005 / AC-RACE-013 — a timed-out compensating write (NEEDS_VERIFICATION) routes to
    COMPENSATION_FAILED. A TIMEOUT IS NOT A FAILURE and it is not COMPLETED — it is the loud, owned,
    non-terminal state that carries the exposure."""
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk, exposure=Money(285000, "GBP"))
    m = _drive_to(store, clk, m, r, gid, target="NEEDS_VERIFICATION")
    cid = r.compensation.compensation_id
    r4 = m.observe_pipeline(cid, actor_id="compensation")
    c = m.get(cid)
    assert r4.transition_id == "CM-4f" and c.state is CmState.COMPENSATION_FAILED
    assert c.exposure.canonical() == "285000|GBP" and not c.is_terminal


def test_post_readback_pipeline_states_exclude_pre_readback():
    """### CM-4 keys on the pipeline reaching a POST-READBACK state. EXECUTED (adapter returned success)
    and CLAIMED/GRANTED are BEFORE the readback, so completing on them is completion without readback."""
    from freight_recon.compensation import POST_READBACK_PIPELINE_STATES
    assert "VERIFIED" in POST_READBACK_PIPELINE_STATES
    for pre in ("EXECUTED", "CLAIMED", "GRANTED", "NEEDS_VERIFICATION", "CHECKPOINT"):
        assert pre not in POST_READBACK_PIPELINE_STATES, f"{pre} is pre-readback and must not complete a compensation"


# ============================================================ owner

def test_owner_required_from_creation_and_ownerless_is_impossible():
    conn = _fresh_conn()
    _seed_fk_targets(conn)  # a real original effect + human, so ONLY the NULL owner can fail
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO compensations (tenant, compensation_id, original_effect_id, commit_key, state, "
            "version, exposure_amount_minor, exposure_currency, owner_id, reason, created_at, updated_at) "
            "VALUES (?, 'c', 'grant-fk', 'ck', 'REQUIRED', 1, 1, 'GBP', NULL, 'r', 't', 't')", (TENANT,))


def test_a_model_cannot_own_a_compensation(tmp_path):
    store, clk = _store(tmp_path)
    gid = ck.a_verified_original_effect(store, tenant=TENANT, clock=clk)
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=HUMAN, seed="mo", clock=clk)
    m = _machine(store, clk)
    with pytest.raises(GuardNotSatisfied):
        m.raise_from_correction(original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"),
                                reason="x", decision_ref=dref, actor_kind="model")


def test_cross_tenant_owner_fails_closed(tmp_path):
    store, clk = _store(tmp_path, tenant=ck.T_A)
    ck.a_human(store, "owner:bob", tenant=ck.T_B, clock=clk)
    gid = ck.a_verified_original_effect(store, tenant=ck.T_A, clock=clk)
    dref = ck.a_human_decision(store, tenant=ck.T_A, actor_id=HUMAN, seed="xt", clock=clk)
    m = _machine(store, clk, ck.T_A)
    with pytest.raises(GuardNotSatisfied):
        m.raise_from_correction(original_effect_id=gid, owner_id="owner:bob", exposure=Money(1, "GBP"),
                                reason="x", decision_ref=dref)


def test_an_offboarded_human_cannot_own_a_new_compensation(tmp_path):
    store, clk = _store(tmp_path)
    store.conn.execute(
        "UPDATE tenant_humans SET state='OFFBOARDED', offboarded_at='t' WHERE tenant=? AND human_id=?",
        (TENANT, HUMAN))
    store.conn.commit()
    gid = ck.a_verified_original_effect(store, tenant=TENANT, clock=clk)
    m = _machine(store, clk)
    with pytest.raises(GuardNotSatisfied):
        m.raise_from_correction(original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"),
                                reason="x", decision_ref="anything")


# ============================================================ exposure

def test_db_exposure_columns_are_not_null():
    conn = _fresh_conn()
    _seed_fk_targets(conn)  # a real original effect + human, so ONLY the NULL exposure can fail
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO compensations (tenant, compensation_id, original_effect_id, commit_key, state, "
            "version, exposure_amount_minor, exposure_currency, owner_id, reason, created_at, updated_at) "
            "VALUES (?, 'c', 'grant-fk', 'ck', 'REQUIRED', 1, NULL, 'GBP', ?, 'r', 't', 't')", (TENANT, HUMAN))


def test_a_float_exposure_is_refused(tmp_path):
    store, clk = _store(tmp_path)
    gid = ck.a_verified_original_effect(store, tenant=TENANT, clock=clk)
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=HUMAN, seed="f", clock=clk)
    m = _machine(store, clk)
    with pytest.raises(MoneyMustNotFloat):
        Money(2850.0, "GBP")  # refused at construction
    with pytest.raises(MalformedCompensation):
        m.raise_from_correction(original_effect_id=gid, owner_id=HUMAN, exposure=2850.0,  # type: ignore[arg-type]
                                reason="x", decision_ref=dref)


def test_a_decimal_exposure_is_refused():
    from decimal import Decimal
    with pytest.raises(MoneyMustNotFloat):
        Money(Decimal("2850"), "GBP")  # type: ignore[arg-type]


def test_db_refuses_a_non_integer_minor_unit():
    """The DB CHECK typeof(exposure_amount_minor)='integer' refuses a real that survived past Money."""
    conn = _fresh_conn()
    _seed_fk_targets(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO compensations (tenant, compensation_id, original_effect_id, commit_key, state, "
            "version, exposure_amount_minor, exposure_currency, owner_id, reason, created_at, updated_at) "
            "VALUES (?, 'c', 'grant-fk', 'ck', 'REQUIRED', 1, 2850.5, 'GBP', ?, 'r', 't', 't')",
            (TENANT, HUMAN))


def test_exposure_survives_into_compensation_failed_and_not_possible(tmp_path):
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk, exposure=Money(285000, "GBP"))
    m = _drive_to(store, clk, m, r, gid, target="FAILED")
    m.observe_pipeline(r.compensation.compensation_id, actor_id="compensation")
    assert m.get(r.compensation.compensation_id).exposure.canonical() == "285000|GBP"
    # not_possible
    m2, r2, _ = _required(store, clk, exposure=Money(500000, "GBP"), grant_id="g-np")
    m2.mark_not_possible(r2.compensation.compensation_id, impossibility_evidence="wire, no reversal")
    assert m2.get(r2.compensation.compensation_id).exposure.canonical() == "500000|GBP"


# ============================================================ lifecycle & schema

def test_the_six_canonical_states_and_no_seventh():
    conn = _fresh_conn()
    ddl = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='compensations'").fetchone()[0].upper()
    for s in COMPENSATION_STATES:
        assert f"'{s}'" in ddl
    for forbidden in ("CANCELLED", "EXPIRED", "RETRYING", "RESOLVED", "REVERSED", "UNDONE", "ABANDONED"):
        assert f"'{forbidden}'" not in ddl
    _seed_fk_targets(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO compensations (tenant, compensation_id, original_effect_id, commit_key, state, "
            "version, exposure_amount_minor, exposure_currency, owner_id, reason, created_at, updated_at) "
            "VALUES (?, 'c', 'grant-fk', 'ck', 'CANCELLED', 1, 1, 'GBP', ?, 'r', 't', 't')", (TENANT, HUMAN))


def test_no_expiry_column():
    conn = _fresh_conn()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(compensations)")}
    for banned in ("expires_at", "ttl", "deleted_at", "expiry", "expire_at"):
        assert banned not in cols


def test_a_compensation_row_cannot_be_deleted(tmp_path):
    store, clk = _store(tmp_path)
    m, r, _ = _required(store, clk)
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute("DELETE FROM compensations WHERE tenant=? AND compensation_id=?",
                           (TENANT, r.compensation.compensation_id))


def test_executing_requires_a_bound_pipeline_instance_id():
    conn = _fresh_conn()
    _seed_fk_targets(conn)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO compensations (tenant, compensation_id, original_effect_id, commit_key, state, "
            "version, exposure_amount_minor, exposure_currency, owner_id, reason, created_at, updated_at) "
            "VALUES (?, 'c', 'grant-fk', 'ck', 'EXECUTING', 1, 1, 'GBP', ?, 'r', 't', 't')",
            (TENANT, HUMAN))


def test_completed_is_the_only_terminal_state():
    from freight_recon.compensation import TERMINAL_STATES
    assert {s.value for s in TERMINAL_STATES} == {"COMPLETED"}


# ============================================================ uniqueness — M10-AQ-9 verbatim

def test_the_uniqueness_predicate_excludes_not_possible_exactly_as_written():
    conn = _fresh_conn()
    idx = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='index' AND name='ix_compensations_one_active_per_effect'"
    ).fetchone()[0]
    compact = " ".join(idx.split()).upper()
    assert "UNIQUE" in compact
    assert "TENANT" in compact and "ORIGINAL_EFFECT_ID" in compact
    assert "WHERE STATE != 'NOT_POSSIBLE'" in compact


def test_one_active_compensation_per_invalidated_effect(tmp_path):
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk)
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=HUMAN, seed="dup", clock=clk)
    # a second raise for the same original effect coalesces onto the first active one.
    r2 = m.raise_from_correction(original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"),
                                 reason="again", decision_ref=dref, compensation_id="cmp-second")
    assert r2.compensation.compensation_id == r.compensation.compensation_id
    assert store.conn.execute("SELECT COUNT(*) FROM compensations WHERE tenant=? AND original_effect_id=?",
                              (TENANT, gid)).fetchone()[0] == 1


def test_a_second_compensation_after_not_possible_is_insertable_m10_aq_9(tmp_path):
    """### M10-AQ-9, the surprising consequence, PRESERVED: NOT_POSSIBLE is excluded from the predicate,
    so a second compensation for the same original effect IS insertable while a NOT_POSSIBLE one is open."""
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk, grant_id="g-aq9")
    m.mark_not_possible(r.compensation.compensation_id, impossibility_evidence="no reversal endpoint")
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=HUMAN, seed="aq9b", clock=clk)
    r2 = m.raise_from_correction(original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"),
                                 reason="second attempt", decision_ref=dref, compensation_id="cmp-aq9-2")
    assert r2.transition_id == "CM-1" and r2.compensation.compensation_id == "cmp-aq9-2"
    assert store.conn.execute("SELECT COUNT(*) FROM compensations WHERE tenant=? AND original_effect_id=?",
                              (TENANT, gid)).fetchone()[0] == 2


# ============================================================ CM-2 approval

def test_a_stale_or_wrong_commit_key_approval_is_refused(tmp_path):
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk)
    cid = r.compensation.compensation_id
    # an approval for a DIFFERENT effect (wrong commit key)
    other = ck.an_original_effect_in(store, "VERIFIED", tenant=TENANT, grant_id="g-other", clock=clk)
    wrong_effect = m.compensating_effect(m._require_original_effect(other), "cmp-other")
    ck.a_granted_m4_approval(store, wrong_effect, ck.a_world(resource="invoice-g-other"),
                             approval_id="ap-wrong", tenant=TENANT, granter=HUMAN, clock=clk)
    with pytest.raises(GuardNotSatisfied):
        m.approve(cid, approval_id="ap-wrong", actor_id=HUMAN)


def test_a_model_cannot_approve_a_compensation(tmp_path):
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk)
    cid = r.compensation.compensation_id
    effect = m.compensating_effect(m._require_original_effect(gid), cid)
    ck.a_granted_m4_approval(store, effect, ck.a_world(resource=m._require_original_effect(gid).target_resource_id),
                             approval_id="ap-1", tenant=TENANT, granter=HUMAN, clock=clk)
    with pytest.raises(IllegalTransition):
        m.approve(cid, approval_id="ap-1", actor_id="a-model", actor_kind="model")
    assert m.get(cid).state is CmState.REQUIRED


def test_a_cross_tenant_approval_is_refused(tmp_path):
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk)
    # an approval that does not exist in this tenant
    with pytest.raises(GuardNotSatisfied):
        m.approve(r.compensation.compensation_id, approval_id="ap-nonexistent", actor_id=HUMAN)


def test_m10_builds_no_second_approval_system():
    """M10 reads M4's approvals row; it defines no approval state machine of its own."""
    assert "class M10Machine" in M10_SRC
    assert "def request" not in M10_SRC and "def grant" not in M10_SRC
    assert "ApprovalMachine" not in M10_SRC  # it reads the row directly, does not drive M4


# ============================================================ commit key

def test_the_compensating_effect_has_its_own_commit_key(tmp_path):
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk)
    comp = m.get(r.compensation.compensation_id)
    original = m._require_original_effect(gid)
    # the compensating commit key is the canonical Compensation occurrence, NOT derived from the original.
    assert comp.commit_key != "ck-orig-" + gid
    assert "ck-orig" not in comp.commit_key  # not the original's, not a substring of it
    # a retry of the SAME compensation converges on one key.
    eff = m.compensating_effect(original, comp.compensation_id)
    assert eff.key() == comp.commit_key
    # a DIFFERENT compensation of the same invoice is a distinct effect.
    eff2 = m.compensating_effect(original, "cmp-different")
    assert eff2.key() != comp.commit_key


def test_the_commit_key_is_the_canonical_compensation_occurrence():
    from freight_recon.commit_key import (CANONICAL_OCCURRENCE_SOURCES, OCCURRENCE_RULES,
                                          CANONICAL_OCCURRENCE_REQUIRED, occurrence_key_for,
                                          UnresolvedCanonicalOccurrence)
    src = CANONICAL_OCCURRENCE_SOURCES["adjust_invoice"]
    assert src.field == "compensation_id" and src.entity == "Compensation"
    assert OCCURRENCE_RULES["adjust_invoice"] == CANONICAL_OCCURRENCE_REQUIRED
    # an unresolved Compensation occurrence still fails closed.
    with pytest.raises(UnresolvedCanonicalOccurrence):
        occurrence_key_for("adjust_invoice", resolved=None)


# ============================================================ CM-5 / RealityEstablished

def test_cm5_emits_the_shared_f3_realityestablished_with_subject_compensation(tmp_path):
    store, clk = _store(tmp_path)
    m, r, _ = _required(store, clk, grant_id="g-cm5")
    cid = r.compensation.compensation_id
    m.mark_not_possible(cid, impossibility_evidence="no reversal endpoint")
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=HUMAN, seed="cm5", clock=clk)
    m.establish_reality(cid, decision_ref=dref, outcome="FAILED", actor_id=HUMAN)
    row = store.conn.execute(
        "SELECT aggregate_type, producer_transition_id, envelope_json FROM event_outbox "
        "WHERE tenant=? AND event_name='RealityEstablished' ORDER BY sequence DESC LIMIT 1", (TENANT,)).fetchone()
    assert row["aggregate_type"] == "effect_grant" and row["producer_transition_id"] == "CM-5"
    assert '"subject": "compensation"' in row["envelope_json"] or '"subject":"compensation"' in row["envelope_json"].replace(" ", "")


def test_m10_mints_no_second_realityestablished_contract():
    """There is exactly one RealityEstablished contract (F3), with CM-5 and EF-5 as its producers."""
    reality = [n for n in CONTRACTS if n == "RealityEstablished"]
    assert reality == ["RealityEstablished"]
    c = CONTRACTS["RealityEstablished"]
    assert c.family == "F3" and set(c.producers) == {"EF-5", "CM-5"}
    # M10 declares only the seven F10 names + the shared RealityEstablished; no eighth Compensation event.
    assert PRODUCED_CONTRACTS == F10_CONTRACTS | {"RealityEstablished"}
    assert F10_CONTRACTS == {"CompensationRequired", "CompensationRefused", "CompensationApproved",
                             "CompensationImpossible", "CompensationStarted", "CompensationCompleted",
                             "CompensationFailed"}


def test_a_model_cannot_establish_reality(tmp_path):
    store, clk = _store(tmp_path)
    m, r, _ = _required(store, clk, grant_id="g-mr")
    cid = r.compensation.compensation_id
    m.mark_not_possible(cid, impossibility_evidence="no reversal endpoint")
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=HUMAN, seed="mr", clock=clk)
    with pytest.raises(IllegalTransition):
        m.establish_reality(cid, decision_ref=dref, outcome="FAILED", actor_kind="model")
    assert m.get(cid).state is CmState.NOT_POSSIBLE


def test_reality_establishment_from_not_possible_fabricates_no_pipeline(tmp_path):
    store, clk = _store(tmp_path)
    m, r, _ = _required(store, clk, grant_id="g-np2")
    cid = r.compensation.compensation_id
    m.mark_not_possible(cid, impossibility_evidence="no reversal endpoint")
    before = store.conn.execute("SELECT COUNT(*) FROM pipeline_instances WHERE tenant=?", (TENANT,)).fetchone()[0]
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=HUMAN, seed="np2", clock=clk)
    m.establish_reality(cid, decision_ref=dref, outcome="FAILED", actor_id=HUMAN)
    after = store.conn.execute("SELECT COUNT(*) FROM pipeline_instances WHERE tenant=?", (TENANT,)).fetchone()[0]
    assert before == after == 0 and m.get(cid).reality_decision_ref is not None


# ============================================================ invalidating authority

def test_the_invalidating_decision_ref_must_resolve(tmp_path):
    store, clk = _store(tmp_path)
    gid = ck.a_verified_original_effect(store, tenant=TENANT, clock=clk)
    m = _machine(store, clk)
    # a bare string that references nothing
    with pytest.raises(GuardNotSatisfied):
        m.raise_from_correction(original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"),
                                reason="x", decision_ref=str(uuid.uuid4()))


def test_an_automation_emitted_human_decision_event_is_refused(tmp_path):
    store, clk = _store(tmp_path)
    gid = ck.a_verified_original_effect(store, tenant=TENANT, clock=clk)
    # a HumanDecided event recorded by automation (actor_type=system) — ER-11 laundering
    from phase6_pipeline_kit import canonical_event
    automated = canonical_event(store, event_name="HumanDecided", producer_transition_id="WI-9",
                                aggregate_type="work_item", aggregate_id="wi-auto", aggregate_version=1,
                                seed="auto", tenant=TENANT, actor_type="system", actor_id="automation",
                                clock=clk, payload={"decision_ref": "x"}, emit=True).event_id
    m = _machine(store, clk)
    with pytest.raises(GuardNotSatisfied):
        m.raise_from_correction(original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"),
                                reason="x", decision_ref=automated)


def test_m10_imports_the_k1_resolver_and_defines_no_second():
    assert "from .work_item import DecisionRefUnresolvable, resolve_decision_ref" in M10_SRC
    # it calls it and does not define its own resolver
    assert "resolve_decision_ref(" in M10_SRC
    assert "def resolve_decision_ref" not in M10_SRC


# ============================================================ brake & gate

def test_an_active_brake_blocks_a_compensating_write(tmp_path):
    """### Under an active brake, the compensating pipeline's checkpoint refuses (BRAKE_ENGAGED) — the
    compensation cannot execute. An urgent compensation does not bypass it; a human narrows first."""
    from freight_recon.brake import BrakeStore
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk)
    cid = r.compensation.compensation_id
    original = m._require_original_effect(gid)
    effect = m.compensating_effect(original, cid)
    world = ck.a_world(resource=original.target_resource_id)
    ck.a_granted_m4_approval(store, effect, world, approval_id="ap-b", tenant=TENANT, granter=HUMAN, clock=clk)
    m.approve(cid, approval_id="ap-b", actor_id=HUMAN)
    ck.a_work_item(store, tenant=TENANT, work_item_id="wi-b", owner_id=HUMAN, clock=clk)
    m.start_execution(cid, work_item_id="wi-b", pipeline_instance_id="pi-b", actor_id="compensation")
    # engage a tenant-wide brake, then try to drive the compensating pipeline's checkpoint.
    BrakeStore(store.conn).engage(tenant=TENANT, actor=HUMAN, actor_kind="HUMAN", reason="halt all effects")
    with pytest.raises(Exception):
        ck.drive_compensating_pipeline(store, effect, world, pipeline_instance_id="pi-b", tenant=TENANT,
                                       approval_id="ap-b", granter=HUMAN, target="VERIFIED", clock=clk)
    # the compensating effect never verified; the compensation is still EXECUTING (blocked), never COMPLETED.
    assert m.get(cid).state is CmState.EXECUTING


def test_m10_engages_no_brake_and_mints_no_gate():
    """### AST scan (not a substring one — the docstrings legitimately discuss the brake and the gate).
    M10 imports neither the brake nor the checkpoint, so it constructs no GateRegistry and calls no
    engage/narrow/mint_grant."""
    tree = ast.parse(M10_SRC)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[-1])
        if isinstance(node, ast.Import):
            for a in node.names:
                imported.add(a.name.split(".")[-1])
    assert "brake" not in imported and "checkpoint" not in imported, f"M10 imports: {sorted(imported)}"


# ============================================================ replay isolation

def test_replay_reconstructs_state_only_and_mints_nothing(tmp_path):
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk)
    m = _drive_to(store, clk, m, r, gid, target="VERIFIED")
    cid = r.compensation.compensation_id
    m.observe_pipeline(cid, actor_id="compensation")
    rebuilt = m.rebuild(cid)
    assert rebuilt.state is CmState.COMPLETED
    assert (rebuilt.pipelines_minted, rebuilt.grants_minted, rebuilt.claims,
            rebuilt.external_effects, rebuilt.approvals_minted, rebuilt.new_authority) == (0, 0, 0, 0, 0, 0)


# ============================================================ transactionality

def test_state_and_event_co_commit(tmp_path):
    store, clk = _store(tmp_path)
    m, r, gid = _required(store, clk)
    cid = r.compensation.compensation_id
    # one CompensationRequired event on the compensation aggregate, and the row is REQUIRED.
    n = store.conn.execute(
        "SELECT COUNT(*) FROM event_outbox WHERE tenant=? AND aggregate_type='compensation' "
        "AND aggregate_id=? AND event_name='CompensationRequired'", (TENANT, cid)).fetchone()[0]
    assert n == 1 and m.get(cid).state is CmState.REQUIRED


def test_concurrent_creation_yields_exactly_one_compensation(tmp_path):
    """Two raises against one invalidated effect — the partial unique index serializes to one row."""
    import threading
    store, clk = _store(tmp_path)
    gid = ck.a_verified_original_effect(store, tenant=TENANT, grant_id="g-conc", clock=clk)
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=HUMAN, seed="conc", clock=clk)
    # each thread its own connection on the same file (P3/P4 per-thread-connection discipline)
    dbpath = [r[2] for r in store.conn.execute("PRAGMA database_list")][0]
    results = []
    def worker(i):
        conn = sqlite3.connect(dbpath)
        conn.row_factory = sqlite3.Row
        enable_and_verify_foreign_keys(conn)
        mm = M10Machine(conn, tenant=TENANT, clock=Clock())
        try:
            rr = mm.raise_from_correction(original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"),
                                          reason="race", decision_ref=dref, compensation_id=f"cmp-{i}")
            results.append(rr.compensation.compensation_id)
        except Exception:
            pass
        conn.close()
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert store.conn.execute("SELECT COUNT(*) FROM compensations WHERE tenant=? AND original_effect_id=?",
                              (TENANT, gid)).fetchone()[0] == 1


# ============================================================ ship dark & neighbours

def test_readiness_is_clean_on_a_fresh_canonical_database():
    conn = _fresh_conn()
    assert phase6_compensations_readiness_problems(conn) == []
    assert schema_readiness_problems(conn) == []


def test_the_produced_contracts_are_the_seven_f10_plus_the_shared_reality():
    assert F10_CONTRACTS == frozenset(
        n for n, c in CONTRACTS.items() if c.family == "F10")
    for name in F10_CONTRACTS:
        assert CONTRACTS[name].aggregate_type == "compensation"


def test_no_unregistered_compensation_event_name_in_the_machine():
    """### A canonical scan: every `Compensation[A-Z]` identifier in the machine is one of the seven
    registered F10 event names. `CompensationCancelled` is what an invented eighth would be called."""
    import re
    found = set(re.findall(r"\bCompensation[A-Z][A-Za-z]*", M10_SRC))
    assert found, "population proof: the scan found Compensation* identifiers"  # not vacuous
    assert found <= F10_CONTRACTS, f"unregistered Compensation* name(s): {found - F10_CONTRACTS}"


def test_m10_ships_dark_no_production_importer():
    """Nothing under src/freight_recon/ imports the compensation machine (only the probe may)."""
    pkg = ROOT / "src" / "freight_recon"
    scanned = 0
    offenders = []
    for py in pkg.rglob("*.py"):
        if py.name == "compensation.py":
            continue
        scanned += 1
        tree = ast.parse(py.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[-1] == "compensation":
                offenders.append(str(py.relative_to(ROOT)))
            if isinstance(node, ast.ImportFrom) and not node.module and any(a.name == "compensation" for a in node.names):
                offenders.append(str(py.relative_to(ROOT)))
            if isinstance(node, ast.Import):
                for a in node.names:
                    if a.name.split(".")[-1] == "compensation":
                        offenders.append(str(py.relative_to(ROOT)))
    assert scanned > 50, f"population proof: scanned only {scanned} production modules"
    assert offenders == [], f"production importer(s) of the compensation machine: {offenders}"


def test_the_neighbouring_machines_m12_m13_are_not_built():
    """### NARROWED WHEN M11 LANDED, NOT A REBUILD OF M10 (CLAUDE.md §5 rule 20; the M6/M7/M8 precedent).
    This M10 test artifact carried a forward-looking assertion that the `policies` table is not built —
    TRUE at the `P6-CP-10` landing and FALSE the moment M11's migration exists. It is corrected to assert
    only what is still true: M12's `rules` and M13's brake lifecycle are not built. M10's machine source
    (`compensation.py`) is byte-unchanged and still names no policy/rule/brake transition id."""
    conn = _fresh_conn()
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "rules" not in tables, "M12's rules table must not be built by M10/M11"
    # no M11/M12/M13 transition ids in the M10 machine source, and no F13 BrakeNarrowed emission.
    import re
    assert not re.findall(r"\b(?:PO|RU|BR)-\d+", M10_SRC)
    assert "BrakeNarrowed" not in M10_SRC


def test_m10_arms_no_timer():
    assert "class M10Machine" in M10_SRC
    for banned in ("from .event_timers import", "DurableTimers", ".schedule(", "TIMER_KIND_"):
        assert banned not in M10_SRC


def test_m1_through_m9_machines_are_unchanged():
    """The landed machines stay byte-identical unless a canonical authority forced a seam change.

    FIXED-SPECIFICATION: this set is NOT a discovered population — it is the exact list the M10 unit
    brief names as must-stay-byte-identical (the nine landed P6 machines M1..M9 plus the P3 checkpoint
    kernel). Discovering "machine modules" by glob would silently admit a NEW machine to the frozen set
    or drop one that was renamed; the guard's value is precisely that adding or removing a name here is
    a deliberate, reviewed edit. The checkpoint kernel and the claim CAS are named because CLAUDE.md §10
    forbids weakening them.
    """
    unchanged = (
        "src/freight_recon/work_item.py", "src/freight_recon/pipeline_instance.py",
        "src/freight_recon/external_effect.py", "src/freight_recon/approval.py",
        "src/freight_recon/observation.py", "src/freight_recon/identity_binding_claim.py",
        "src/freight_recon/conflict.py", "src/freight_recon/expectation.py",
        "src/freight_recon/exception.py", "src/freight_recon/checkpoint.py",
    )
    r = subprocess.run(["git", "diff", "--name-only", "HEAD", "--", *unchanged], cwd=ROOT,
                       capture_output=True, text=True)
    assert r.returncode == 0 and r.stdout.strip() == "", f"landed machines changed: {r.stdout}"


# ============================================================ DDL introspection with positive controls

def _seed_fk_targets(conn: sqlite3.Connection) -> None:
    """A recorded human and a VERIFIED effect grant so a WELL-FORMED insert has its FK referents."""
    conn.execute(
        "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, authority_role, state, "
        "recorded_at, recorded_by, recorded_by_kind) VALUES (?,?,?,?,?,?,?,'human')",
        (TENANT, HUMAN, "Sam", "AUTHORIZED_HUMAN", "ACTIVE", "t", "founder"))
    conn.execute(
        "INSERT OR IGNORE INTO effect_grants (tenant, grant_id, commit_key, action_class, target_system, "
        "target_resource_id, target_operation, state, issued_at, created_at) "
        "VALUES (?, 'grant-fk', 'ck', 'raise_invoice', 'tms', 'inv', 'op', 'VERIFIED', 't', 't')", (TENANT,))
    conn.commit()


def test_ddl_positive_control_a_wellformed_required_row_is_accepted():
    conn = _fresh_conn()
    _seed_fk_targets(conn)
    conn.execute(
        "INSERT INTO compensations (tenant, compensation_id, original_effect_id, commit_key, state, "
        "version, exposure_amount_minor, exposure_currency, owner_id, reason, created_at, updated_at) "
        "VALUES (?, 'c1', 'grant-fk', 'ck-cmp', 'REQUIRED', 1, 285000, 'GBP', ?, 'POD rebound', 't', 't')",
        (TENANT, HUMAN))
    conn.commit()
    assert conn.execute("SELECT state FROM compensations WHERE compensation_id='c1'").fetchone()[0] == "REQUIRED"


def test_ddl_cross_tenant_owner_effect_and_approval_fail_closed():
    conn = _fresh_conn()
    _seed_fk_targets(conn)
    # owner from another tenant
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO compensations (tenant, compensation_id, original_effect_id, commit_key, state, "
            "version, exposure_amount_minor, exposure_currency, owner_id, reason, created_at, updated_at) "
            "VALUES (?, 'c', 'grant-fk', 'ck', 'REQUIRED', 1, 1, 'GBP', 'ghost', 'r', 't', 't')", (TENANT,))
    # original effect that no row backs
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO compensations (tenant, compensation_id, original_effect_id, commit_key, state, "
            "version, exposure_amount_minor, exposure_currency, owner_id, reason, created_at, updated_at) "
            "VALUES (?, 'c', 'no-such-grant', 'ck', 'REQUIRED', 1, 1, 'GBP', ?, 'r', 't', 't')", (TENANT, HUMAN))


def _security(store) -> list[str]:
    return [r[0] for r in store.conn.execute(
        "SELECT event_type FROM security_events WHERE tenant=?", (TENANT,))]
