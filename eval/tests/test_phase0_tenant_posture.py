"""U0.4 - the tenant-first structural probe (AC-SEC-001), and the no-new-tenantless-table guard.

AC-SEC-001 is RED BY DESIGN. Phase 0 does not migrate the schema; it records the posture and stops
it getting worse. The canonical rule is not "a tenant column exists" - it is that tenant is FIRST in
the key. `operation_commit_claims` has a tenant column and is still unsafe: its PRIMARY KEY is
`commit_key` alone, so the uniqueness domain is global and one tenant's key can collide with
another's.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0 import manifest, schema_probe


def test_the_probe_evaluates_a_real_population():
    _, ev = schema_probe.tables()
    ev.require_population(minimum=8)


def test_ac_sec_001_is_red_and_the_probe_names_the_offending_tables():
    """The oracle: the probe must NAME them. 'Some tables are wrong' is not a finding."""
    tables, ev = schema_probe.tables()
    ev.require_population()
    offenders = sorted(t.name for t in tables if not t.canonical)
    assert offenders, "AC-SEC-001 cannot be red with zero offenders - the probe found nothing"
    assert set(offenders) == manifest.tables_not_tenant_first(), (
        f"tenant posture CHANGED. Recomputed: {offenders}\n"
        f"Manifest:   {sorted(manifest.tables_not_tenant_first())}\n"
        f"{ev.report()}"
    )


def test_the_true_count_is_seven_of_eight_not_six():
    """DEF-6: the frozen plan says '6 of 8' in seven places. Exactly one table is tenant-first.

    This matters beyond arithmetic: U2.1 is scoped to 'the 6 offending tables'. Executed literally,
    Phase 2 migrates 6, leaves 1, and AC-SEC-001 stays red with the phase marked done.
    """
    tables, _ = schema_probe.tables()
    canonical = [t.name for t in tables if t.canonical]
    assert canonical == ["autonomous_run_counters"], f"expected exactly one tenant-first table, got {canonical}"
    assert len(tables) == 8
    assert len([t for t in tables if not t.canonical]) == 7


def test_a_tenant_column_alone_does_not_count_as_tenant_first():
    """The negative control: the probe must not be fooled by the presence of a tenant column."""
    tables, _ = schema_probe.tables()
    t = next(x for x in tables if x.name == "operation_commit_claims")
    assert t.has_tenant_column is True
    assert t.tenant_first_in_key is False
    assert t.canonical is False


def test_no_new_tenantless_table_appeared(): 
    """REG-1. A new persisted table must be tenant-first, or be adjudicated in the manifest."""
    tables, _ = schema_probe.tables()
    known = manifest.tables_not_tenant_first() | manifest.tables_tenant_first()
    new = {t.name for t in tables} - known
    assert not new, (
        f"NEW table(s) not in the baseline manifest: {sorted(new)}. "
        f"A new persisted table must be tenant-first (REG-1), or be adjudicated deliberately."
    )
