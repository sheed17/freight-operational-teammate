"""R-comp-double-act — concurrent creation of compensations for one invalidated effect leaves AT MOST
ONE active (non-NOT_POSSIBLE) compensation row, so the money layer is never compensated twice.

Routed obligation (Product Driver, by identity):
  risk key           : idempotency:aca8bde394
  R-comp-double-act (P1): "Concurrent creation of compensations for one invalidated effect could
                          produce two active (non-NOT_POSSIBLE) compensation rows, so the money layer
                          is compensated twice for a single invalidated effect."

Product principle: an unmeasured risk is not a covered risk, and a guard speaks only for the
obligation it was written to answer. R4 (idempotency:2fcf040507) guarded the active-row count; R4-w2
(idempotency:85e5a223bb) guarded the money reversal. R-comp-double-act sharpens the SAME race onto
its exact predicate — the count of NON-NOT_POSSIBLE rows — under a distinct risk key, and its
distinguishing rigor is the NOT_POSSIBLE-exclusion boundary (M10-AQ-9): a NOT_POSSIBLE row beside one
active row is NOT a money double-act, so the guard must measure `state != 'NOT_POSSIBLE'` exactly, not
a bare row count. This module measures exactly that, and nothing broader. It is a VERIFICATION GAP,
not a product defect.

Authority (not invented here):
  - recovery-and-compensation-acceptance.md AC-REC-003 (no bulk undo — individually-gated) and
    AC-REC-002 (each compensation is the ordinary money-effect pipeline).
  - docs/specifications/entities/22-compensation.md §17 and src/freight_recon/compensation.py: the
    partial-UNIQUE index `ix_compensations_one_active_per_effect ON (tenant, original_effect_id)
    WHERE state != 'NOT_POSSIBLE'` — its WHERE clause is exactly this obligation's predicate.
  - M10-AQ-9 (test_a_second_compensation_after_not_possible_is_insertable_m10_aq_9): NOT_POSSIBLE is
    EXCLUDED from the predicate, so a NOT_POSSIBLE + one active pair is legitimate, not a double-act.
  - CLAUDE.md §6.

Realises the hostile case against the REAL M10 machine on real threads (reusing R4's race helper,
read-only) and fails if two non-NOT_POSSIBLE rows for one invalidated effect exist; the control proves
it goes RED. Changes no product runtime, no mutant, no acceptance requirement; does not modify the R4
file it imports.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import phase6_compensation_kit as ck  # noqa: E402
from freight_recon.compensation import M10Machine  # noqa: E402
from freight_recon.fingerprint import Money  # noqa: E402
# Reuse R4's real-race + non-NOT_POSSIBLE-count helpers READ-ONLY (importing does not modify that
# file; only files changed in answer to THIS correction are bound to R-comp-double-act's risk key).
from test_p8_r4_compensation_concurrency import (  # noqa: E402
    HUMAN, ONE_ACTIVE_INDEX, TENANT, _active_compensation_count, _race_concurrent_raises, _store,
)


def require_population(items, what: str):
    assert items, f"no {what} to assert over — this guard would measure nothing"
    return items


def _non_not_possible_double_act(non_not_possible_count: int) -> bool:
    """R-comp-double-act's forbidden state: more than one NON-NOT_POSSIBLE compensation row for a
    single invalidated effect — the money layer would be compensated more than once."""
    return non_not_possible_count > 1


def _total_rows(conn, tenant: str, original_effect_id: str) -> int:
    return int(conn.execute(
        "SELECT COUNT(*) FROM compensations WHERE tenant = ? AND original_effect_id = ?",
        (tenant, original_effect_id)).fetchone()[0])


# --------------------------------------------------------------------------- the guard
def test_rcompdoubleact_at_most_one_non_not_possible_compensation_row_per_effect(tmp_path):
    """THE GUARD (R-comp-double-act). Eight pipelines concurrently raise a compensation for ONE
    invalidated effect; the count of NON-NOT_POSSIBLE rows must stay <= 1. It also proves the exact
    predicate by the M10-AQ-9 boundary: after the one active row is marked NOT_POSSIBLE, a fresh raise
    yields a NOT_POSSIBLE + active PAIR (two total rows) that is NOT a double-act, because the
    non-NOT_POSSIBLE count is still 1. FAILS ("R-COMP-DOUBLE-ACT VIOLATED") if two non-NOT_POSSIBLE
    rows for one invalidated effect ever exist."""
    store, clk = _store(tmp_path)
    gid = ck.a_verified_original_effect(store, tenant=TENANT, grant_id="g-rcda", clock=clk)
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=HUMAN, seed="rcda", clock=clk)

    wins, refusals = _race_concurrent_raises(store, gid, dref, contenders=8)
    # Proven population (CLAUDE.md §6): all eight actually contended for the money reversal.
    assert len(wins) + len(refusals) == 8, (
        f"only {len(wins) + len(refusals)} of 8 raisers contended; wins={wins} refusals={refusals}")

    non_np = _active_compensation_count(store.conn, TENANT, gid)  # COUNT WHERE state != 'NOT_POSSIBLE'
    assert not _non_not_possible_double_act(non_np), (
        f"R-COMP-DOUBLE-ACT VIOLATED: {non_np} non-NOT_POSSIBLE compensation rows for one invalidated "
        f"effect — the money layer would be compensated {non_np}x (AC-REC-003 no bulk undo).")
    assert non_np == 1, f"expected exactly one non-NOT_POSSIBLE row, found {non_np}"

    # M10-AQ-9 boundary: prove the predicate EXCLUDES NOT_POSSIBLE — a NOT_POSSIBLE row + one active
    # row is NOT a double-act, so the guard measures state != 'NOT_POSSIBLE' exactly (not a bare
    # row count that would false-positive on the legitimate second attempt after NOT_POSSIBLE).
    m = M10Machine(store.conn, tenant=TENANT, clock=clk)
    the_active = store.conn.execute(
        "SELECT compensation_id FROM compensations WHERE tenant = ? AND original_effect_id = ? "
        "AND state != 'NOT_POSSIBLE'", (TENANT, gid)).fetchone()[0]
    m.mark_not_possible(the_active, impossibility_evidence="no reversal endpoint")
    dref2 = ck.a_human_decision(store, tenant=TENANT, actor_id=HUMAN, seed="rcda-after-np", clock=clk)
    m.raise_from_correction(
        original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"),
        reason="second attempt after NOT_POSSIBLE", decision_ref=dref2,
        compensation_id="cmp-rcda-after-np")
    assert _total_rows(store.conn, TENANT, gid) == 2, (
        "the M10-AQ-9 boundary did not create a NOT_POSSIBLE + active pair")
    non_np_after = _active_compensation_count(store.conn, TENANT, gid)
    assert non_np_after == 1 and not _non_not_possible_double_act(non_np_after), (
        f"a NOT_POSSIBLE row was wrongly counted toward the money double-act (non-NOT_POSSIBLE="
        f"{non_np_after}); the predicate must EXCLUDE NOT_POSSIBLE (M10-AQ-9)")
    store.close()


# --------------------------------------------------------------------------- the RED control
def test_rcompdoubleact_control_catches_two_non_not_possible_rows(tmp_path, monkeypatch):
    """THE CONTROL — proves the guard is not vacuous by reintroducing R-comp-double-act's forbidden
    state.

    Facet A — the decision discriminates (two non-NOT_POSSIBLE rows is a double-act; one or zero is not).
    Facet B — real-product tie: with the one-active partial-UNIQUE index dropped on the THROWAWAY test
      database (never the product schema), a SECOND non-NOT_POSSIBLE row for one invalidated effect is
      insertable and the non-NOT_POSSIBLE count reads two — the index is exactly what keeps it to one.
    Facet C — seen RED: with the non-NOT_POSSIBLE count forced to two, THE GUARD's own assertion path
      raises."""
    g = sys.modules[__name__]

    # Facet A — the decision discriminates.
    assert _non_not_possible_double_act(2)
    assert not _non_not_possible_double_act(1)
    assert not _non_not_possible_double_act(0)

    # Facet B — the index is load-bearing on the non-NOT_POSSIBLE predicate.
    store, clk = _store(tmp_path)
    gid = ck.a_verified_original_effect(store, tenant=TENANT, grant_id="g-rcda-ctl", clock=clk)
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=HUMAN, seed="rcdactl", clock=clk)
    m = M10Machine(store.conn, tenant=TENANT, clock=clk)
    r = m.raise_from_correction(
        original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"),
        reason="one", decision_ref=dref, compensation_id="cmp-rcda-ctl-1")
    assert _active_compensation_count(store.conn, TENANT, gid) == 1
    store.conn.execute(f"DROP INDEX {ONE_ACTIVE_INDEX}")
    row = dict(store.conn.execute(
        "SELECT * FROM compensations WHERE compensation_id = ?",
        (r.compensation.compensation_id,)).fetchone())
    assert row["state"] != "NOT_POSSIBLE", "the copied row must be active for the control to be valid"
    row["compensation_id"] = "cmp-rcda-ctl-2"      # a SECOND non-NOT_POSSIBLE row for the SAME effect
    cols = ",".join(row)
    store.conn.execute(
        f"INSERT INTO compensations ({cols}) VALUES ({','.join('?' * len(row))})",
        tuple(row.values()))
    store.conn.commit()
    non_np = _active_compensation_count(store.conn, TENANT, gid)
    assert non_np == 2 and _non_not_possible_double_act(non_np), (
        f"the one-active index is not load-bearing (found {non_np} non-NOT_POSSIBLE after dropping it) "
        f"— the guard's forbidden state would be unreachable and its assertion vacuous")
    store.close()

    # Facet C — the guard, run with the non-NOT_POSSIBLE count forced to two, MUST fail.
    monkeypatch.setattr(g, "_active_compensation_count", lambda *a, **k: 2)
    with pytest.raises(AssertionError, match="R-COMP-DOUBLE-ACT VIOLATED"):
        g.test_rcompdoubleact_at_most_one_non_not_possible_compensation_row_per_effect(tmp_path / "red")
