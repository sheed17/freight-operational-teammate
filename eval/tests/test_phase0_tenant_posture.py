"""U0.4 — the tenant-first structural probe (AC-SEC-001), and the no-new-tenantless-table guard.

AC-SEC-001 WAS RED BY DESIGN, AND IS NOW GREEN BY PROOF.

Phase 0 recorded the posture and stopped it getting worse; it deliberately migrated nothing. U2.6BC
migrated it. So the assertions here INVERT — and that inversion is the single most dangerous edit in
this file, because "make the red test green" is also exactly what someone does to hide a defect.

What protects it is that the oracle got STRICTER rather than weaker:

  * Phase 0 asked source text one question: is tenant first in the key? U2.6BC additionally asks a
    REAL database the same question (`live_tables`), because a DDL string nobody executes would let
    the source read canonical while a tenant's rows lived in a global namespace.
  * The negative control that proved the probe could not be fooled by a mere tenant COLUMN
    (`operation_commit_claims`) is kept, not deleted — rebuilt against a synthetic table, so the
    probe is still shown FAILING on the shape it used to pass.
  * `tables_not_tenant_first` must now be EMPTY, which was its own stated deletion condition.

DEF-6 lives on here too: the frozen plan once said "6 of 8" when the truth was 7, and executed
literally it would have migrated 6, left 1, and marked the phase done with AC-SEC-001 still red. The
lesson was never the arithmetic — it was that a COUNT is not a scope. So every assertion below
compares SETS.
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freight_recon.migrations.phase2_tenant_first import (
    CANONICAL_TENANT_TABLES,
    TENANT_EXEMPT_TABLES,
)
from phase0 import manifest, schema_probe


def test_the_probe_evaluates_a_real_population():
    _, ev = schema_probe.tables()
    ev.require_population(minimum=8)


def test_the_live_probe_evaluates_a_real_population():
    """The live leg needs its own denominator: a probe that built nothing would report no offenders."""
    _, ev = schema_probe.live_tables()
    ev.require_population(minimum=8)


def test_ac_sec_001_is_green_in_source_and_the_probe_names_every_table_it_checked():
    """The oracle is the exact SET, in both legs. 'No offenders' from an empty scan is not a pass."""
    tables, ev = schema_probe.tables()
    ev.require_population()
    offenders = sorted(t.name for t in tables if not t.canonical)
    exempt = manifest.tables_tenant_exempt()
    unexplained = sorted(set(offenders) - exempt)
    assert not unexplained, (
        f"tables are not tenant-first and are not adjudicated as exempt: {unexplained}\n{ev.report()}"
    )
    assert manifest.tables_not_tenant_first() == set(), (
        "the manifest still lists tables as not-tenant-first; AC-SEC-001 cannot be green while its "
        f"own baseline says otherwise: {sorted(manifest.tables_not_tenant_first())}"
    )


def test_ac_sec_001_is_green_in_a_real_database_not_only_in_source():
    """The leg that matters. Source says what was typed; this says what a tenant's rows live in."""
    tables, ev = schema_probe.live_tables()
    ev.require_population(minimum=8)
    live = {t.name: t for t in tables}
    missing = sorted(set(CANONICAL_TENANT_TABLES) - set(live))
    assert not missing, f"a fresh database does not even contain {missing}\n{ev.report()}"
    not_first = sorted(n for n in CANONICAL_TENANT_TABLES if not live[n].canonical)
    assert not not_first, (
        f"these tables exist in a REAL database without tenant first in the key: {not_first}. "
        f"The source may claim canonical; the database is what holds the rows.\n{ev.report()}"
    )


def test_the_two_legs_agree():
    """Source and live must describe the SAME schema. Divergence means one of them is fiction."""
    src = {t.name for t in schema_probe.tables()[0]}
    live = {t.name for t in schema_probe.live_tables()[0]}
    assert src == live, (
        f"the schema in source and the schema a database actually gets disagree.\n"
        f"in source only: {sorted(src - live)}\nin the database only: {sorted(live - src)}"
    )


def test_the_legacy_global_keyed_table_is_gone_not_merely_accompanied():
    """`operation_commit_claims` was THE example: a tenant column, and still unsafe."""
    live = {t.name for t in schema_probe.live_tables()[0]}
    assert "operation_commit_claims" not in live, (
        "the legacy globally-keyed reservation table still exists in a fresh database"
    )
    assert "effect_grants" in live, "the canonical ledger is absent from a fresh database"


def test_a_tenant_column_alone_still_does_not_count_as_tenant_first():
    """The negative control, PRESERVED.

    The old version pointed at `operation_commit_claims`, which no longer exists — so the honest
    move is to rebuild the shape it had and prove the probe still refuses it. A negative control
    that is deleted because its subject was fixed leaves a probe nobody has seen say "no".
    """
    with sqlite3.connect(":memory:") as conn:
        conn.execute(
            "CREATE TABLE looks_safe ("
            " commit_key TEXT PRIMARY KEY, tenant TEXT NOT NULL, payload TEXT NOT NULL)"
        )
        info = conn.execute("PRAGMA table_info(looks_safe)").fetchall()
        colnames = [r[1] for r in info]
        pk = [r[1] for r in sorted([r for r in info if r[5]], key=lambda r: r[5])]
        t = schema_probe.Table(
            "looks_safe", "synthetic", colnames, pk,
            any(c in schema_probe.TENANT_COLUMNS for c in colnames),
            bool(pk) and pk[0] in schema_probe.TENANT_COLUMNS,
        )
    assert t.has_tenant_column is True, "the fixture must actually carry a tenant column"
    assert t.tenant_first_in_key is False
    assert t.canonical is False, (
        "the probe called a table canonical because it had a tenant column. That is the exact "
        "mistake AC-SEC-001 exists to refuse: the key, not the column, is the uniqueness domain."
    )


def test_the_scope_is_an_exact_set_never_a_count():
    """DEF-6, kept as a live assertion rather than a memory.

    The plan said '6 of 8' when the truth was 7. Executed literally, Phase 2 migrates six, leaves
    one, and reports done. The defence is not counting more carefully — it is never counting.
    """
    live = {t.name for t in schema_probe.live_tables()[0]}
    tenant_owned = {t.name for t in schema_probe.live_tables()[0] if t.canonical}
    assert set(CANONICAL_TENANT_TABLES) <= tenant_owned, (
        f"the exact seven are not all tenant-first: "
        f"{sorted(set(CANONICAL_TENANT_TABLES) - tenant_owned)}"
    )
    unaccounted = live - tenant_owned - set(TENANT_EXEMPT_TABLES)
    assert not unaccounted, (
        f"table(s) neither tenant-first nor adjudicated exempt: {sorted(unaccounted)}"
    )


def test_no_new_tenantless_table_appeared():
    """REG-1. A new persisted table must be tenant-first, or be adjudicated in the manifest."""
    tables, _ = schema_probe.tables()
    known = (
        manifest.tables_not_tenant_first()
        | manifest.tables_tenant_first()
        | manifest.tables_tenant_exempt()
    )
    new = {t.name for t in tables} - known
    assert not new, (
        f"NEW table(s) not in the baseline manifest: {sorted(new)}. "
        f"A new persisted table must be tenant-first (REG-1), or be adjudicated deliberately."
    )


def test_the_exempt_list_is_not_an_escape_hatch():
    """An exemption without a reason is an indefinite allowance wearing a temporary label."""
    entries = manifest.load()["expected_noncanonical_schema"]["tables_tenant_exempt"]
    assert entries, "the exempt list must not be empty-by-omission; it is asserted against"
    assert {e["table"] for e in entries} == set(TENANT_EXEMPT_TABLES), (
        "the manifest's exempt tables and the code's exempt tables disagree"
    )
    for e in entries:
        for field in ("reason", "removed_by_phase", "accountable_unit", "deletion_condition"):
            assert e.get(field), f"exempt table {e['table']} has no {field}"
