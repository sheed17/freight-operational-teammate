"""Phase 3 — the human brake: admission control, the one-way ratchet, no TTL, fail-closed reads.

Machine M13 and ADR-011, adversarially: automation trying to release or narrow, timers trying to
expire, the store becoming unreadable at the worst moment, and the mint/claim interleavings whose
answer must be "never both, never neither".
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase3_kit import (  # noqa: E402
    T_A,
    T_B,
    green_scenario,
    make_kernel,
    make_store,
    params_for,
)

from freight_recon.brake import (  # noqa: E402
    BrakeError,
    BrakeStore,
    BrakeStoreUnreachable,
)
from freight_recon.checkpoint import claim_grant_cas, run_checkpoint  # noqa: E402


# ------------------------------------------------------------------ engagement (BR-1)

def test_any_human_engages_instantly_and_a_detector_may_too(tmp_path):
    store = make_store(tmp_path)
    brakes = BrakeStore(store.conn)
    human = brakes.engage(tenant=T_A, actor="clerk:dana", actor_kind="HUMAN",
                          reason="something looks wrong")
    assert human.state == "ACTIVE" and human.brake_version == 1
    detector = brakes.engage(tenant=T_A, action_class="raise_invoice",
                             actor="detector:unknown-outcomes", actor_kind="DETECTOR",
                             reason="2 unknown outcomes in one hour")
    assert detector.state == "ACTIVE" and detector.brake_version == 2
    store.close()


def test_engagement_is_idempotent_on_scope_a_flapping_detector_is_one_brake(tmp_path):
    store = make_store(tmp_path)
    brakes = BrakeStore(store.conn)
    first = brakes.engage(tenant=T_A, actor="detector:d1", actor_kind="DETECTOR", reason="flap")
    for _ in range(5):
        again = brakes.engage(tenant=T_A, actor="detector:d1", actor_kind="DETECTOR", reason="flap")
        assert again.brake_id == first.brake_id and again.brake_version == first.brake_version
    count = store.conn.execute(
        "SELECT COUNT(*) FROM brakes WHERE tenant = ? AND state = 'ACTIVE'", (T_A,)).fetchone()[0]
    assert count == 1
    store.close()


def test_a_model_is_neither_a_human_nor_a_detector(tmp_path):
    store = make_store(tmp_path)
    brakes = BrakeStore(store.conn)
    with pytest.raises(BrakeError, match="model"):
        brakes.engage(tenant=T_A, actor="agent:gpt", actor_kind="MODEL", reason="I decided")
    with pytest.raises(BrakeError):
        brakes.engage(tenant=T_A, actor="", actor_kind="HUMAN", reason="anonymous")
    with pytest.raises(BrakeError):
        brakes.engage(tenant=T_A, actor="clerk:dana", actor_kind="HUMAN", reason="  ")
    store.close()


def test_the_platform_brake_is_one_row_and_global(tmp_path):
    store = make_store(tmp_path)
    brakes = BrakeStore(store.conn)
    status = brakes.engage_platform(actor="detector:isolation", actor_kind="DETECTOR",
                                    reason="tenant isolation breach signal")
    assert status.tenant is None and status.scope == "GLOBAL" and status.brake_version == 1
    rows = store.conn.execute("SELECT COUNT(*) FROM platform_brake").fetchone()[0]
    assert rows == 1
    # global denies every tenant's admission
    assert brakes.admission_denied(tenant=T_A, action_class="raise_invoice") is not None
    assert brakes.admission_denied(tenant=T_B, action_class="file_document") is not None
    store.close()


# ------------------------------------------------------------------ the ratchet

def test_automation_may_widen_but_never_narrow_or_release(tmp_path):
    store = make_store(tmp_path)
    brakes = BrakeStore(store.conn)
    status = brakes.engage(tenant=T_A, action_class="raise_invoice",
                           actor="detector:d1", actor_kind="DETECTOR", reason="signal")
    widened = brakes.widen(tenant=T_A, brake_id=status.brake_id,
                           actor="detector:d1", actor_kind="DETECTOR")
    assert widened.scope == "tenant" and widened.brake_version == 2
    with pytest.raises(BrakeError, match="narrow"):
        brakes.narrow(tenant=T_A, brake_id=status.brake_id, actor="detector:d1",
                      actor_kind="DETECTOR", to_action_class="raise_invoice",
                      decision_ref="detector-says-so")
    with pytest.raises(BrakeError, match="release"):
        brakes.release(tenant=T_A, brake_id=status.brake_id, actor="detector:d1",
                       actor_kind="DETECTOR", decision_ref="detector-says-so")
    still = brakes.status(tenant=T_A, brake_id=status.brake_id)
    assert still.state == "ACTIVE" and still.scope == "tenant"
    store.close()


def test_release_requires_a_human_and_a_decision_ref(tmp_path):
    store = make_store(tmp_path)
    brakes = BrakeStore(store.conn)
    status = brakes.engage(tenant=T_A, actor="owner:rasheed", actor_kind="HUMAN", reason="incident")
    with pytest.raises(BrakeError, match="decision_ref"):
        brakes.release(tenant=T_A, brake_id=status.brake_id, actor="owner:rasheed",
                       actor_kind="HUMAN", decision_ref="")
    released = brakes.release(tenant=T_A, brake_id=status.brake_id, actor="owner:rasheed",
                              actor_kind="HUMAN", decision_ref="decision:incident-7-closed")
    assert released.state == "RELEASED" and released.brake_version == 2
    assert brakes.admission_denied(tenant=T_A, action_class="raise_invoice") is None
    store.close()


def test_a_released_row_without_decision_ref_is_not_even_insertable(tmp_path):
    """The database enforces the release contract, not just the API."""
    import sqlite3
    store = make_store(tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            "INSERT INTO brakes (tenant, brake_id, scope, state, actor, actor_kind, "
            "engaged_reason, engaged_at, brake_version) "
            "VALUES (?, 'b-x', 'tenant', 'RELEASED', 'x', 'HUMAN', 'r', 'now', 1)", (T_A,))
    store.conn.rollback()
    store.close()


def test_no_code_path_expires_a_brake(tmp_path):
    """M13 BR-5: a timer releasing a brake is ILLEGAL. Structurally, by AST — not substrings,
    which fire on their own docstrings: the brakes schema carries no TTL/expiry column, no
    function in brake.py is named like an expiry, and no SQL statement in brake.py writes an
    expiry or compares a deadline."""
    import ast
    store = make_store(tmp_path)
    for table in ("brakes", "platform_brake"):
        columns = {r[1] for r in store.conn.execute(f"PRAGMA table_info({table})").fetchall()}
        shaped = {c for c in columns if "expir" in c.lower() or "ttl" in c.lower()
                  or "deadline" in c.lower()}
        assert not shaped, f"{table} carries an expiry-shaped column: {shaped}"
    tree = ast.parse((ROOT / "src" / "freight_recon" / "brake.py").read_text(encoding="utf-8"))
    functions = [n.name for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    assert functions, "brake.py parsed to no functions - the population collapsed"
    expiry_named = [f for f in functions if "expire" in f.lower() or "ttl" in f.lower()]
    assert expiry_named == [], f"brake.py defines expiry-shaped functions: {expiry_named}"
    sql_literals = [
        n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)
        and any(kw in n.value.upper() for kw in ("UPDATE ", "INSERT ", "DELETE "))
    ]
    assert sql_literals, "brake.py contains no SQL - the population collapsed"
    offending = [s for s in sql_literals if "EXPIR" in s.upper() or "TTL" in s.upper()]
    assert offending == [], f"brake SQL touches expiry: {offending}"
    store.close()


def test_brake_versions_are_monotonic_across_all_operations(tmp_path):
    store = make_store(tmp_path)
    brakes = BrakeStore(store.conn)
    seen: list[int] = []
    s1 = brakes.engage(tenant=T_A, action_class="raise_invoice", actor="h:1",
                       actor_kind="HUMAN", reason="one")
    seen.append(s1.brake_version)
    s2 = brakes.widen(tenant=T_A, brake_id=s1.brake_id, actor="h:1", actor_kind="HUMAN")
    seen.append(s2.brake_version)
    s3 = brakes.narrow(tenant=T_A, brake_id=s1.brake_id, actor="h:1", actor_kind="HUMAN",
                       to_action_class="file_document", decision_ref="d:1")
    seen.append(s3.brake_version)
    s4 = brakes.release(tenant=T_A, brake_id=s1.brake_id, actor="h:1", actor_kind="HUMAN",
                        decision_ref="d:2")
    seen.append(s4.brake_version)
    assert seen == sorted(seen) and len(set(seen)) == len(seen), f"not monotonic: {seen}"
    store.close()


def test_tenant_brakes_are_tenant_isolated(tmp_path):
    store = make_store(tmp_path)
    brakes = BrakeStore(store.conn)
    brakes.engage(tenant=T_A, actor="owner:a", actor_kind="HUMAN", reason="alpha incident")
    assert brakes.admission_denied(tenant=T_A, action_class="raise_invoice") is not None
    assert brakes.admission_denied(tenant=T_B, action_class="raise_invoice") is None, (
        "tenant A's brake stopped tenant B")
    token_a = brakes.version_token(tenant=T_A)
    token_b = brakes.version_token(tenant=T_B)
    assert token_a != token_b
    assert token_b.endswith("tenant:0")
    store.close()


# ------------------------------------------------------------------ fail-closed reads

def test_an_unreadable_brake_store_refuses_the_checkpoint(tmp_path):
    """'Cannot read the brake' NEVER means 'off': drop the platform row and the checkpoint's
    step 7 refuses; the claim refuses too."""
    store, kernel, clock, effect, facts, versions, approval, world, inputs, request = (
        green_scenario(tmp_path))
    ok = run_checkpoint(kernel, request, inputs)
    assert ok.authorized
    store.conn.execute("DELETE FROM platform_brake")
    store.conn.commit()
    refused_claim = claim_grant_cas(kernel, ok.handle, params_for(effect))
    assert refused_claim.claimed is False and refused_claim.cause == "BRAKE_UNREADABLE"
    # Re-checkpoint the SAME effect (same approval, same inputs): steps 1-6 pass again exactly
    # as before, and step 7 now refuses — proving the brake read happens inside the checkpoint,
    # before any mint could hold the commit key.
    refused_checkpoint = run_checkpoint(kernel, request, inputs)
    assert refused_checkpoint.authorized is False
    assert refused_checkpoint.step == 7 and refused_checkpoint.reason == "BRAKE_UNREADABLE"
    store.close()


def test_admission_denied_reports_the_widest_applicable_brake(tmp_path):
    store = make_store(tmp_path)
    brakes = BrakeStore(store.conn)
    brakes.engage(tenant=T_A, action_class="raise_invoice", actor="h:1", actor_kind="HUMAN",
                  reason="narrow")
    narrow = brakes.admission_denied(tenant=T_A, action_class="raise_invoice")
    assert narrow is not None and narrow.scope == "action:raise_invoice"
    assert brakes.admission_denied(tenant=T_A, action_class="file_document") is None
    brakes.engage(tenant=T_A, actor="h:1", actor_kind="HUMAN", reason="wide")
    wide = brakes.admission_denied(tenant=T_A, action_class="raise_invoice")
    assert wide is not None and wide.scope == "tenant"
    store.close()


def test_the_operator_report_lists_platform_first_then_tenant_brakes(tmp_path):
    store = make_store(tmp_path)
    brakes = BrakeStore(store.conn)
    brakes.engage(tenant=T_A, actor="h:1", actor_kind="HUMAN", reason="tenant stop")
    brakes.engage_platform(actor="detector:iso", actor_kind="DETECTOR", reason="global stop")
    report = brakes.active_report(tenant=T_A)
    assert [b.scope for b in report] == ["GLOBAL", "tenant"]
    assert all(b.engaged_reason for b in report), "a brake report without reasons hides the why"
    store.close()


# ------------------------------------------------------------------ mint/claim interleavings

def test_interleaved_brake_and_claim_never_both_never_neither(tmp_path):
    """M13 §41(b), at proportionate depth: across engage-before-claim and engage-after-claim
    interleavings, the pair (claimed, brake-blocked-the-claim) is always exactly one true."""
    from phase3_kit import (
        CheckpointInputs, CheckpointRequest, live_reader, make_approval, make_effect, make_facts,
    )
    store = make_store(tmp_path)
    kernel, clock = make_kernel(store)
    brakes = BrakeStore(store.conn)
    outcomes = []
    for i in range(40):
        resource = f"load:il-{i}"
        effect = make_effect(resource=resource)
        facts = make_facts(entity_ref=resource)
        versions = {resource: 1}
        approval = make_approval(effect, facts, versions, clock)
        inputs = CheckpointInputs(
            material_facts_reader=live_reader(lambda f=facts: dict(f)),
            projection_assertion={},
            projected_state_reader=live_reader({}),
            entity_version_reader=live_reader({resource: 1}),
            approval=approval)
        request = CheckpointRequest(effect=effect, actor="pipeline",
                                    accountable_owner="owner:rasheed",
                                    target_entity_ref=resource)
        authorized = run_checkpoint(kernel, request, inputs)
        assert authorized.authorized, f"iteration {i}: {authorized}"
        engage_before_claim = i % 2 == 0
        brake_id = None
        if engage_before_claim:
            brake_id = brakes.engage(tenant=T_A, actor="owner:rasheed", actor_kind="HUMAN",
                                     reason=f"interleave {i}").brake_id
        claim = claim_grant_cas(kernel, authorized.handle, params_for(effect))
        if not engage_before_claim:
            brake_id = brakes.engage(tenant=T_A, actor="owner:rasheed", actor_kind="HUMAN",
                                     reason=f"interleave {i}").brake_id
        blocked = claim.claimed is False and claim.cause == "BRAKE_CHANGED"
        assert claim.claimed != blocked, f"iteration {i}: both or neither ({claim})"
        assert claim.claimed is (not engage_before_claim), (
            f"iteration {i}: engage-before-claim={engage_before_claim} but claimed={claim.claimed}")
        if claim.claimed:
            # the brake engaged AFTER the claim never un-claims it (positions 3-5 run on)
            state = store.conn.execute(
                "SELECT state FROM effect_grants WHERE grant_id = ?",
                (authorized.handle.grant_id,)).fetchone()["state"]
            assert state == "CLAIMED"
        brakes.release(tenant=T_A, brake_id=brake_id, actor="owner:rasheed",
                       actor_kind="HUMAN", decision_ref=f"decision:interleave-{i}")
        outcomes.append(claim.claimed)
    assert len(outcomes) == 40 and any(outcomes) and not all(outcomes), (
        "the interleave population collapsed to one branch")
    store.close()


# ============================================================ F-E: SD-12 amendment A1
#
# The implementation ships the ONE global brake as a separate tenant-EXEMPT `platform_brake`
# table, while 16-brake.md point 7 had resolved SD-12 with the words `tenant_id = <platform
# sentinel>`. The independent review raised this as F-1; it is adjudicated ACCEPTED, and the spec
# is formally amended (amendment A1) so the canonical authority now agrees with the code rather
# than the code quietly diverging from the canonical authority.
#
# An amendment is only worth anything if what it PRESERVED is still enforced. These guards read
# the amended spec and then prove each preserved requirement against the running implementation,
# so "we amended the spec" can never become "we relaxed the rule".


def _brake_spec() -> str:
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    return (root / "docs/specifications/entities/16-brake.md").read_text(encoding="utf-8")


def test_the_sd12_amendment_is_recorded_in_the_canonical_entity_spec():
    """The amendment must be IN the canonical spec, name itself, and keep the cardinality rule."""
    import re

    spec = _brake_spec()
    point7 = re.search(r"^7\. \*\*Tenant ownership.*$", spec, re.M)
    assert point7, "16-brake.md has no point 7"
    text = point7.group(0)
    assert "AMENDED at P3" in text and "amendment A1" in text, (
        "point 7 does not record the SD-12 amendment; the spec and the implementation disagree "
        "again, which is the condition F-1 reported"
    )
    assert "platform_brake" in text, "the amendment does not name the canonical representation"
    assert re.search(r"EXACTLY ONE platform-level row", text), (
        "the amendment lost SD-12's actual rule: ONE row, not N per-tenant rows"
    )
    assert "sentinel" in text and "superseded" in text, (
        "the superseded wording must be named and disarmed in place, not silently deleted"
    )


def test_the_amendment_preserved_every_substantive_sd12_requirement_in_writing():
    """Membership, not prose: each preserved requirement must still be stated."""
    import re

    text = re.search(r"^7\. \*\*Tenant ownership.*$", _brake_spec(), re.M).group(0)
    required = {
        "exactly one platform row": r"EXACTLY ONE platform-level row|exactly ONE platform row",
        "atomic engagement": r"single atomic row write",
        "fail-closed on absence/read failure": r"absent or unreadable.*REFUSAL",
        "admission consults platform AND tenant": r"both\*\*.*platform.*\*\*and\*\*.*tenant|"
                                                  r"platform-`GLOBAL` row \*\*and\*\* the acting tenant",
        "either ACTIVE denies": r"`ACTIVE` result on \*\*either\*\* denies",
        "witnesses/grants bind BOTH versions": r"bind BOTH the platform `global_brake_version` AND",
        "claim CAS revalidates BOTH": r"claim CAS re-validates \*\*both\*\*",
    }
    missing = [name for name, pat in required.items() if not re.search(pat, text, re.I | re.S)]
    assert not missing, f"amendment A1 dropped substantive SD-12 requirements: {missing}"


def test_exactly_one_platform_row_is_structurally_enforced(tmp_path):
    """Preserved requirement 1, against the database rather than the prose."""
    import sqlite3

    store = make_store(tmp_path, T_A)
    assert store.conn.execute("SELECT COUNT(*) FROM platform_brake").fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            "INSERT INTO platform_brake (id, state, brake_version) VALUES (2, 'RELEASED', 0)")
    store.conn.rollback()
    assert store.conn.execute("SELECT COUNT(*) FROM platform_brake").fetchone()[0] == 1
    store.close()


def test_the_platform_brake_table_has_no_tenant_column_at_all(tmp_path):
    """Preserved requirement, in the amendment's own direction: there is no tenant value to be
    wrong. A sentinel column would be the `tenant="default"` defect class returning."""
    store = make_store(tmp_path, T_A)
    cols = {r[1] for r in store.conn.execute("PRAGMA table_info(platform_brake)").fetchall()}
    assert not (cols & {"tenant", "tenant_id"}), (
        f"platform_brake grew a tenant column: {sorted(cols)}. The platform stop is nobody's "
        "tenant data; a sentinel there makes it look like one tenant's fact."
    )


def test_an_absent_platform_row_refuses_rather_than_reading_as_released(tmp_path):
    """Preserved requirement: fail-closed on absence. 'Cannot read the brake' never means 'off'."""
    store = make_store(tmp_path, T_A)
    brakes = BrakeStore(store.conn)
    store.conn.execute("DELETE FROM platform_brake")
    store.conn.commit()
    with pytest.raises(BrakeStoreUnreachable):
        brakes.admission_denied(tenant=T_A, action_class="raise_invoice")
    with pytest.raises(BrakeStoreUnreachable):
        brakes.version_token(tenant=T_A)
    store.close()
