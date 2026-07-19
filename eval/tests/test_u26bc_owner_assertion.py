"""U2.6BC Blocker 2 — historical tenant ownership requires an auditable owner assertion.

PHASE_GUARD

Six of the seven legacy tables contain no tenant anywhere: not a column, not a parent, not a payload.
So SOMEONE decides who owns those rows, and the only honest question is whether the record says who,
what they authorised, and on what basis.

    An assertion missing any of that is not a weaker assertion. It is a guess with paperwork.

Every test here runs the REAL migration against a REAL copy of the live workspace. Nothing is mocked:
a mock that bypasses persistence would prove the API is shaped right and nothing about whether rows
actually moved.
"""

import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.migrations.phase2_tenant_first import (
    FORBIDDEN_ACTORS,
    GENERIC_BASIS,
    AssertionIncomplete,
    MigrationRefused,
    OwnerAssertion,
    migrate,
)
from freight_recon.tenant import InvalidTenant, MissingTenant

from fixtures.legacy_workspace import LEGACY_RUNS, build_legacy_workspace

VALID = dict(
    actor_id="rasheed@neyma",
    tenant="acme-brokerage",
    scope="neyma_workflow.sqlite3 — all pre-migration legacy rows",
    operational_basis="sole workspace onboarded for Acme in June 2026; verified against the onboarding record",
    evidence_reference="docs/onboarding/acme-2026-06.md",
)


def _db() -> str:
    d = tempfile.mkdtemp()
    dst = Path(d) / "w.sqlite3"
    build_legacy_workspace(dst)
    return str(dst)


def _tables(db: str) -> set[str]:
    c = sqlite3.connect(db)
    try:
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        c.close()


def _assertions(db: str) -> list[dict]:
    if "owner_assertions" not in _tables(db):
        return []
    c = sqlite3.connect(db)
    c.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in c.execute("SELECT * FROM owner_assertions")]
    finally:
        c.close()


def _rows(db: str, table: str = "workflow_runs") -> int:
    if table not in _tables(db):
        return 0
    c = sqlite3.connect(db)
    try:
        return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        c.close()


# ------------------------------------------------------- 1-5: every required field fails closed

@pytest.mark.parametrize("missing", ["actor_id", "tenant", "scope", "operational_basis",
                                     "evidence_reference"])
def test_1_to_5_missing_any_required_field_fails_before_database_mutation(missing):
    fields = dict(VALID)
    fields[missing] = ""
    with pytest.raises((AssertionIncomplete, MissingTenant)):
        OwnerAssertion(**fields)


def test_1_to_5b_an_incomplete_assertion_never_reaches_the_database():
    """The refusal is at construction, so there is no partially-authorised state to clean up."""
    db = _db()
    before = _rows(db)
    fields = dict(VALID)
    fields["actor_id"] = ""
    with pytest.raises(AssertionIncomplete):
        migrate(db, assertion=OwnerAssertion(**fields), dry_run=False)
    assert _rows(db) == before
    assert "owner_assertions" not in _tables(db)


# --------------------------------------------------------------- 6-8: sentinels and empty reasons

def test_6_sentinel_tenant_remains_rejected():
    """Blocker 1's boundary still applies — there is no second, looser path."""
    for bad in ("default", "DEFAULT", "global", "unknown", "test"):
        with pytest.raises(InvalidTenant):
            OwnerAssertion(**{**VALID, "tenant": bad})


def test_7_sentinel_actor_is_rejected():
    """A machine that names the actor has named nobody."""
    assert len(FORBIDDEN_ACTORS) >= 15
    for bad in FORBIDDEN_ACTORS:
        with pytest.raises(AssertionIncomplete):
            OwnerAssertion(**{**VALID, "actor_id": bad})
        with pytest.raises(AssertionIncomplete):
            OwnerAssertion(**{**VALID, "actor_id": bad.upper()})


def test_8_empty_or_generic_basis_is_rejected():
    for bad in GENERIC_BASIS:
        with pytest.raises(AssertionIncomplete):
            OwnerAssertion(**{**VALID, "operational_basis": bad})
    for too_thin in ("ok fine", "acme's data", "it is acme"):
        with pytest.raises(AssertionIncomplete):
            OwnerAssertion(**{**VALID, "operational_basis": too_thin})


# ------------------------------------------------- 9-16: the durable record and its exact counts

def test_9_10_valid_assertion_creates_one_durable_record_that_precedes_assignment():
    db = _db()
    rep = migrate(db, assertion=OwnerAssertion(**VALID), dry_run=False)
    records = _assertions(db)
    assert len(records) == 1
    r = records[0]
    assert r["actor_id"] == VALID["actor_id"]
    assert r["asserted_tenant"] == VALID["tenant"]
    assert r["operational_basis"] == VALID["operational_basis"]
    assert r["evidence_reference"] == VALID["evidence_reference"]
    assert r["assertion_scope"] == VALID["scope"]
    assert r["status"] == "APPLIED"
    assert r["asserted_at"] and r["completed_at"]
    # asserted BEFORE completed: the authority existed before the rows moved.
    assert r["asserted_at"] <= r["completed_at"]
    assert sum(rep.rows_migrated.values()) > 0


def test_11_12_13_14_counts_in_the_audit_match_what_actually_happened():
    db = _db()
    rep = migrate(db, assertion=OwnerAssertion(**VALID), dry_run=False)
    r = _assertions(db)[0]
    assert r["rows_assigned"] == sum(rep.rows_migrated.values())
    assert r["rows_quarantined"] == sum(rep.rows_quarantined.values())
    assert r["rows_considered"] >= r["rows_assigned"]
    assert r["conflicts_detected"] == 0
    assert r["unresolved_rows"] == r["rows_quarantined"]


def test_15_the_assertion_names_the_exact_table_set():
    db = _db()
    migrate(db, assertion=OwnerAssertion(**VALID), dry_run=False)
    from freight_recon.migrations.phase2_tenant_first import TENANT_FIRST_TABLES
    recorded = set(_assertions(db)[0]["affected_table_set"].split(","))
    assert recorded == set(TENANT_FIRST_TABLES), "the recorded scope drifted from the migrated set"


def test_16_17_assignment_covers_only_the_asserted_tenant():
    db = _db()
    migrate(db, assertion=OwnerAssertion(**VALID), dry_run=False)
    c = sqlite3.connect(db)
    try:
        tenants = {r[0] for r in c.execute("SELECT DISTINCT tenant FROM workflow_runs")}
    finally:
        c.close()
    assert tenants == {VALID["tenant"]}, f"rows landed outside the asserted tenant: {tenants}"


# ------------------------------------------------------------------ 18-21: rerun and conflicts

def test_18_19_rerun_is_idempotent_and_preserves_the_original_actor_and_evidence():
    db = _db()
    a = OwnerAssertion(**VALID)
    migrate(db, assertion=a, dry_run=False)
    first = _assertions(db)[0]
    rep2 = migrate(db, assertion=a, dry_run=False)
    after = _assertions(db)
    assert rep2.already_applied is True
    assert len(after) == 1, "a rerun duplicated the assertion record"
    assert after[0]["actor_id"] == first["actor_id"]
    assert after[0]["evidence_reference"] == first["evidence_reference"]
    assert after[0]["asserted_at"] == first["asserted_at"]


def test_20_a_changed_tenant_is_a_conflict_not_a_reassignment():
    """THE case this record exists for: someone re-runs with a different tenant."""
    db = _db()
    migrate(db, assertion=OwnerAssertion(**VALID), dry_run=False)
    other = OwnerAssertion(**{**VALID, "tenant": "beta-logistics", "actor_id": "someone.else@neyma",
                              "operational_basis": "believed to be Beta's workspace after a later conversation",
                              "evidence_reference": "slack://ops/2026-07-17"})
    with pytest.raises(MigrationRefused, match="CONFLICTING OWNER ASSERTION"):
        migrate(db, assertion=other, dry_run=False)

    c = sqlite3.connect(db)
    try:
        tenants = {r[0] for r in c.execute("SELECT DISTINCT tenant FROM workflow_runs")}
    finally:
        c.close()
    assert tenants == {VALID["tenant"]}, "a conflicting assertion reassigned ownership"
    assert _assertions(db)[0]["conflicts_detected"] == 1, "the conflict was not recorded"


def test_21_a_changed_actor_or_basis_is_a_different_claim():
    """Fingerprint identity is WHAT was asserted — not merely which tenant."""
    a = OwnerAssertion(**VALID)
    b = OwnerAssertion(**{**VALID, "actor_id": "different.person@neyma"})
    c = OwnerAssertion(**{**VALID, "scope": "only rows created before June"})
    assert a.fingerprint() != b.fingerprint()
    assert a.fingerprint() != c.fingerprint()
    assert a.fingerprint() == OwnerAssertion(**VALID).fingerprint()


# --------------------------------------------------------------------- 24-27: dry run and refusal

def test_24_dry_run_validates_everything_and_changes_nothing():
    import hashlib
    db = _db()
    before = hashlib.sha256(Path(db).read_bytes()).hexdigest()
    rep = migrate(db, assertion=OwnerAssertion(**VALID), dry_run=True)
    assert hashlib.sha256(Path(db).read_bytes()).hexdigest() == before, "the dry run wrote to the database"
    assert _assertions(db) == []
    assert "owner_assertions" not in _tables(db)
    assert rep.dry_run is True


def test_25_a_bare_tenant_no_longer_authorises_assignment():
    """`--assert-tenant` alone was enough before Blocker 2. It is not any more."""
    db = _db()
    with pytest.raises(AssertionIncomplete, match="no longer authorises"):
        migrate(db, assert_tenant="acme-brokerage", dry_run=False)
    assert _rows(db) == LEGACY_RUNS, "a bare tenant moved rows"


def test_26_the_cli_refuses_a_partial_assertion_and_accepts_a_complete_one():
    import subprocess
    root = Path(__file__).resolve().parents[2]
    cli = root / "scripts" / "migrate_phase2_tenant_first.py"

    partial = subprocess.run(
        [sys.executable, str(cli), "--db", _db(), "--apply", "--assert-tenant", "acme-brokerage"],
        capture_output=True, text=True, timeout=60)
    assert partial.returncode == 2
    assert "incomplete owner assertion" in partial.stderr

    db = _db()
    full = subprocess.run(
        [sys.executable, str(cli), "--db", db, "--apply", "--assert-tenant", "acme-brokerage",
         "--actor", VALID["actor_id"], "--scope", VALID["scope"],
         "--basis", VALID["operational_basis"], "--evidence", VALID["evidence_reference"]],
        capture_output=True, text=True, timeout=120)
    assert full.returncode == 0, full.stderr[-400:]
    assert "OWNER ASSERTION" in full.stderr and "APPLY" in full.stderr
    assert len(_assertions(db)) == 1


def test_27_no_assertion_still_quarantines_rather_than_guessing():
    """The frozen rule survives Blocker 2: ownership cannot be inferred."""
    db = _db()
    rep = migrate(db, dry_run=False)
    assert sum(rep.rows_quarantined.values()) == 120
    assert sum(rep.rows_migrated.values()) == 0
    assert _rows(db) == 0
    assert _assertions(db) == [], "an assertion record appeared without an assertion"


# ------------------------------------------------------------------------- structural guards

def test_there_is_one_assertion_model_and_no_second_one():
    import inspect

    from freight_recon.migrations import phase2_tenant_first as m

    src = inspect.getsource(m)
    assert src.count("class OwnerAssertion") == 1
    # the tenant still routes through the production boundary
    assert "from ..tenant import require_tenant" in src
    assert "require_tenant(" in inspect.getsource(m.OwnerAssertion.__post_init__)


def test_the_assertion_record_is_append_only_never_rewritten():
    """Rewriting a prior assertion to hide a failed attempt is how audit stops being evidence."""
    import inspect

    from freight_recon.migrations import phase2_tenant_first as m

    src = inspect.getsource(m)
    # the only UPDATEs touch outcome columns, never the asserted facts
    for forbidden in ("SET actor_id", "SET asserted_tenant", "SET operational_basis",
                      "SET evidence_reference", "SET assertion_scope", "DELETE FROM owner_assertions"):
        assert forbidden not in src, f"the assertion record can be rewritten: {forbidden}"


def test_the_assertion_is_frozen_so_a_validated_scope_cannot_widen():
    import dataclasses
    a = OwnerAssertion(**VALID)
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.tenant = "beta-logistics"   # type: ignore[misc]
    with pytest.raises(dataclasses.FrozenInstanceError):
        a.scope = "everything"        # type: ignore[misc]
