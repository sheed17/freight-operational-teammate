"""U2.6BC Blocker 1 — a migration owner assertion is a tenant identity, validated like any other.

PHASE_GUARD

The hole this closes was real and it was mine: `migrate(db, assert_tenant="default")` was accepted,
and it assigned every historical row to a sentinel. Proven against a copy of the live workspace —
18 real `workflow_runs` rows came out owned by `"default"`.

    `default` is not ownership. It is missing ownership, spelled so that it compiles.

A migration is the worst possible place for that mistake. Production writes one bad tenant onto one
row and someone notices; a migration writes it onto every historical row at once and calls the job
done. So the assertion goes through the SAME `require_tenant()` boundary production construction
uses — there is no second, looser path for migrations.
"""

import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.migrations.phase2_tenant_first import migrate
from freight_recon.tenant import FORBIDDEN_TENANTS, InvalidTenant, MissingTenant

REAL = Path(__file__).resolve().parents[2] / "data" / "active_workspace" / "neyma_workflow.sqlite3"


def _legacy_copy() -> str:
    """A copy of the real pre-migration workspace. The original is never touched."""
    d = tempfile.mkdtemp()
    dst = Path(d) / "w.sqlite3"
    shutil.copy(REAL, dst)
    return str(dst)


def _tables(db: str) -> set[str]:
    import sqlite3
    c = sqlite3.connect(db)
    try:
        return {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        c.close()


def _count(db: str, table: str) -> int:
    import sqlite3
    c = sqlite3.connect(db)
    try:
        if table not in _tables(db):
            return 0
        return c.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    finally:
        c.close()


@pytest.mark.parametrize("bad", ["default", "DEFAULT", "Default", "  default  ", "global",
                                 "unknown", "test", "none", "system", "shared"])
def test_1_2_6_every_sentinel_is_rejected_case_insensitively(bad):
    with pytest.raises(InvalidTenant):
        migrate(_legacy_copy(), assert_tenant=bad, dry_run=False)


def test_3_4_blank_and_whitespace_are_rejected():
    for bad in ("", "   ", "\t\n"):
        with pytest.raises(MissingTenant):
            migrate(_legacy_copy(), assert_tenant=bad, dry_run=False)


def test_5_non_string_is_rejected():
    for bad in (123, 0, [], {}, object()):
        with pytest.raises(InvalidTenant):
            migrate(_legacy_copy(), assert_tenant=bad, dry_run=False)   # type: ignore[arg-type]


def test_every_canonical_sentinel_is_covered_not_just_the_ones_i_thought_of():
    """The list is the contract: iterate it, so a new sentinel is protected the day it is added."""
    assert len(FORBIDDEN_TENANTS) >= 15
    for sentinel in FORBIDDEN_TENANTS:
        with pytest.raises(InvalidTenant):
            migrate(_legacy_copy(), assert_tenant=sentinel, dry_run=False)


def test_8_9_10_an_invalid_assertion_costs_zero_rows_zero_ledger_and_zero_quarantine():
    """The refusal must land BEFORE anything is written — including under the bad value itself.

    Quarantining rows under `tenant="default"` would be the same defect wearing a safety label.
    """
    db = _legacy_copy()
    before = _count(db, "workflow_runs")
    assert before == 18, "the fixture is not the real legacy workspace"

    with pytest.raises(InvalidTenant):
        migrate(db, assert_tenant="default", dry_run=False)

    tables = _tables(db)
    assert "migration_quarantine" not in tables, "a refused migration created quarantine rows"
    assert "effect_grants" not in tables, "a refused migration created canonical ledger rows"
    assert "schema_migrations" not in tables, "a refused migration recorded migration steps"
    assert _count(db, "workflow_runs") == before, "a refused migration touched the data"


def test_7_a_valid_explicit_tenant_succeeds():
    db = _legacy_copy()
    rep = migrate(db, assert_tenant="acme-brokerage", dry_run=False)
    assert rep.tenant_assertion == "acme-brokerage"
    assert sum(rep.rows_migrated.values()) > 0
    assert sum(rep.rows_quarantined.values()) == 0


def test_a_valid_tenant_is_normalised_the_same_way_production_normalises_it():
    db = _legacy_copy()
    rep = migrate(db, assert_tenant="  Acme-Brokerage  ", dry_run=False)
    assert rep.tenant_assertion == "Acme-Brokerage", "migration normalisation drifted from production"


def test_no_assertion_still_quarantines_rather_than_guessing():
    """The frozen rule survives the fix: ownership cannot be inferred."""
    db = _legacy_copy()
    rep = migrate(db, dry_run=False)
    assert sum(rep.rows_quarantined.values()) == 120
    assert sum(rep.rows_migrated.values()) == 0
    assert _count(db, "workflow_runs") == 0, "a row was guessed into a tenant"


def test_the_dry_run_also_refuses_an_invalid_assertion():
    """A dry run that accepts `default` teaches an operator the value is fine."""
    with pytest.raises(InvalidTenant):
        migrate(_legacy_copy(), assert_tenant="default", dry_run=True)


def test_there_is_no_second_looser_assertion_path():
    """One boundary. A migration-only validator would drift from production the first time either moved."""
    import inspect

    from freight_recon.migrations import phase2_tenant_first as m

    src = inspect.getsource(m)
    assert "from ..tenant import require_tenant" in src, "the migration validates tenants its own way"
    assert "require_tenant(" in inspect.getsource(m.migrate)
