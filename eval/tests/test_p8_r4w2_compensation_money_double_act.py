"""R4-w2 — concurrent compensation creation for a single invalidated effect does not DOUBLE-ACT on
the money layer: it drives EXACTLY ONE individually-gated money reversal, never two.

Routed obligation (Product Driver, by identity):
  risk key : idempotency:85e5a223bb
  R4-w2 (P1): "Concurrent compensation creation for a single invalidated effect could produce two
              active compensations rather than exactly one individually-gated compensation,
              double-acting on the money layer."

Product principle: an unmeasured risk is not a covered risk, and a guard speaks only for the
obligation it was written to answer. R4 (idempotency:2fcf040507, guarded in
test_p8_r4_compensation_concurrency.py) proved the ROW invariant — at most one active compensation
row. R4-w2 sharpens the same race onto its MONEY consequence, under a distinct risk key: two active
compensations for one invalidated effect are two reversals the money layer would perform, so the
customer's money is compensated twice for a single invalidated effect. This module measures exactly
that money-double-act and nothing broader. It is a VERIFICATION GAP, not a product defect.

Authority (not invented here):
  - recovery-and-compensation-acceptance.md AC-REC-003 — "no bulk undo": a correction invalidating N
    effects ⇒ N INDIVIDUALLY-GATED Compensations; the aggregate exposure is shown first, and each
    reversal is gated on its own. Two active reversals for ONE invalidated effect is the forbidden
    double-act.
  - AC-REC-002 — a compensation is the ordinary money-effect pipeline (its own witness/grant/approval/
    readback); two active ones ⇒ two money effects.
  - docs/specifications/entities/22-compensation.md §17 and src/freight_recon/compensation.py: the
    partial-UNIQUE index `ix_compensations_one_active_per_effect ON (tenant, original_effect_id)
    WHERE state != 'NOT_POSSIBLE'` serializes concurrent raises to exactly one active row.
  - CLAUDE.md §6.

This realises R4-w2's hostile case against the REAL M10 machine on real threads (reusing R4's race
helper, read-only) and fails if the money layer would be reversed more than once for one invalidated
effect; the control proves it goes RED. It changes no product runtime, no mutant, no acceptance
requirement, and does not modify the R4 file it imports.
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
# Reuse R4's real-race helpers READ-ONLY (importing does not modify that file; only files changed in
# answer to THIS correction are bound to R4-w2's risk key).
from test_p8_r4_compensation_concurrency import (  # noqa: E402
    HUMAN, ONE_ACTIVE_INDEX, TENANT, _race_concurrent_raises, _store,
)


def require_population(items, what: str):
    assert items, f"no {what} to assert over — this guard would measure nothing"
    return items


def _active_money_reversals(conn, tenant: str, original_effect_id: str) -> list[tuple[str, int]]:
    """Every ACTIVE (non-NOT_POSSIBLE) compensation for one invalidated effect, as
    (compensation_id, exposure_amount_minor). Each row is ONE reversal the money layer would perform
    (AC-REC-002: a compensation is the ordinary money-effect pipeline). Read from real DB state."""
    return [(r["compensation_id"], r["exposure_amount_minor"]) for r in conn.execute(
        "SELECT compensation_id, exposure_amount_minor FROM compensations "
        "WHERE tenant = ? AND original_effect_id = ? AND state != 'NOT_POSSIBLE'",
        (tenant, original_effect_id)).fetchall()]


def _money_double_act(active_reversals: list[tuple[str, int]]) -> bool:
    """R4-w2's forbidden state: more than one active compensation for a single invalidated effect —
    the money layer would be reversed more than once for one invalidated effect."""
    return len(active_reversals) > 1


# --------------------------------------------------------------------------- the guard
def test_r4w2_concurrent_compensation_does_not_double_act_on_the_money_layer(tmp_path):
    """THE GUARD (R4-w2). Eight pipelines concurrently raise a compensation for ONE invalidated
    effect; the money layer must be reversed EXACTLY ONCE — exactly one active compensation carries a
    reversal, never two. FAILS ("R4-w2 VIOLATED") if two active compensations for one invalidated
    effect would each drive a money reversal (AC-REC-003 no bulk undo; AC-REC-002 each is a money
    effect)."""
    store, clk = _store(tmp_path)
    gid = ck.a_verified_original_effect(store, tenant=TENANT, grant_id="g-r4w2", clock=clk)
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=HUMAN, seed="r4w2", clock=clk)

    wins, refusals = _race_concurrent_raises(store, gid, dref, contenders=8)
    # Proven population (CLAUDE.md §6): all eight actually contended for the money reversal.
    assert len(wins) + len(refusals) == 8, (
        f"only {len(wins) + len(refusals)} of 8 raisers contended; wins={wins} refusals={refusals}")

    reversals = _active_money_reversals(store.conn, TENANT, gid)
    assert not _money_double_act(reversals), (
        f"R4-w2 VIOLATED: {len(reversals)} active compensations for one invalidated effect "
        f"({reversals}) — the money layer would be reversed {len(reversals)}x for a single "
        f"invalidated effect (AC-REC-003 no bulk undo).")
    assert len(reversals) == 1, f"expected exactly one money reversal, found {len(reversals)}: {reversals}"
    store.close()


# --------------------------------------------------------------------------- the RED control
def test_r4w2_control_catches_a_doubled_money_compensation(tmp_path, monkeypatch):
    """THE CONTROL — proves the guard is not vacuous by reintroducing R4-w2's forbidden money-double-act.

    Facet A — the decision discriminates (two active reversals is a double-act; one is not).
    Facet B — real-product tie: with the one-active partial-UNIQUE index dropped on the THROWAWAY test
      database (never the product schema), a SECOND active compensation for one invalidated effect is
      insertable, so `_active_money_reversals` reads two reversals — the index is exactly what keeps
      the money layer acted on once.
    Facet C — seen RED: with the active reversals forced to two, THE GUARD's own assertion path
      raises."""
    g = sys.modules[__name__]

    # Facet A — the decision discriminates.
    assert _money_double_act([("a", 100), ("b", 100)])
    assert not _money_double_act([("a", 100)])
    assert not _money_double_act([])

    # Facet B — the one-active index is load-bearing on the money layer.
    store, clk = _store(tmp_path)
    gid = ck.a_verified_original_effect(store, tenant=TENANT, grant_id="g-r4w2-ctl", clock=clk)
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=HUMAN, seed="r4w2ctl", clock=clk)
    m = M10Machine(store.conn, tenant=TENANT, clock=clk)
    r = m.raise_from_correction(
        original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"),
        reason="one", decision_ref=dref, compensation_id="cmp-r4w2-ctl-1")
    assert len(_active_money_reversals(store.conn, TENANT, gid)) == 1
    store.conn.execute(f"DROP INDEX {ONE_ACTIVE_INDEX}")
    row = dict(store.conn.execute(
        "SELECT * FROM compensations WHERE compensation_id = ?",
        (r.compensation.compensation_id,)).fetchone())
    row["compensation_id"] = "cmp-r4w2-ctl-2"      # a SECOND active reversal for the SAME effect
    cols = ",".join(row)
    store.conn.execute(
        f"INSERT INTO compensations ({cols}) VALUES ({','.join('?' * len(row))})",
        tuple(row.values()))
    store.conn.commit()
    reversals = _active_money_reversals(store.conn, TENANT, gid)
    assert len(reversals) == 2 and _money_double_act(reversals), (
        f"the one-active index is not load-bearing on the money layer (found {len(reversals)} active "
        f"after dropping it) — the guard's forbidden state would be unreachable and its assertion vacuous")
    store.close()

    # Facet C — the guard, run with the doubled money reversal reintroduced, MUST fail.
    monkeypatch.setattr(g, "_active_money_reversals", lambda *a, **k: [("x", 100), ("y", 100)])
    with pytest.raises(AssertionError, match="R4-w2 VIOLATED"):
        g.test_r4w2_concurrent_compensation_does_not_double_act_on_the_money_layer(tmp_path / "red")
