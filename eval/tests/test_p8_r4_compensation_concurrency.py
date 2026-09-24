"""R4 — concurrent compensation creation for ONE invalidated effect yields EXACTLY ONE active
compensation, never two.

Routed obligation (Product Driver, by identity):
  risk key : idempotency:2fcf040507
  R4 (P1)  : "Concurrent compensation creation for one invalidated effect could produce two active
             compensations instead of exactly one individually-gated compensation."

Product principle: an unmeasured risk is not a covered risk, and a guard speaks only for the
obligation it was written to answer. The generated-scenario budget could not bind a direct guard to
this risk, so it stayed UNCOVERED. This module is that measurement — nothing broader.

Authority (not invented here):
  - recovery-and-compensation-acceptance.md AC-REC-003 — "no bulk undo": a correction invalidating N
    effects ⇒ N INDIVIDUALLY-GATED Compensations; two active reversals for ONE invalidated effect
    would double-act on the money layer.
  - docs/specifications/entities/22-compensation.md §17 and the M10 machine
    (src/freight_recon/compensation.py): a PARTIAL UNIQUE index
    `ix_compensations_one_active_per_effect ON (tenant, original_effect_id) WHERE state != 'NOT_POSSIBLE'`
    serializes concurrent raises to exactly one active row (the app-level coalesce has a TOCTOU window
    under a race; the index is the backstop).
  - CLAUDE.md §6 — a negative/absence assertion needs a proven population, and a guard protecting a
    tier-1 invariant must be SEEN to go RED or it is a decoration.

This realises R4's hostile case against the REAL M10 machine on real threads (concurrency_kit) and
fails if the forbidden state — two active compensations for one invalidated effect — is ever reached.
It changes no product runtime, no mutant, no acceptance requirement.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import phase6_compensation_kit as ck  # noqa: E402
from concurrency_kit import run_race  # noqa: E402
from freight_recon.compensation import M10Machine  # noqa: E402
from freight_recon.fingerprint import Money  # noqa: E402
from freight_recon.schema import enable_and_verify_foreign_keys  # noqa: E402

TENANT = ck.T_A
HUMAN = "owner:sam"
ONE_ACTIVE_INDEX = "ix_compensations_one_active_per_effect"


def _store(tmp_path: Path):
    clk = ck.Clock()
    store = ck.make_store(tmp_path, TENANT)
    enable_and_verify_foreign_keys(store.conn)
    ck.a_human(store, HUMAN, tenant=TENANT, clock=clk)
    return store, clk


def _active_compensation_count(conn, tenant: str, original_effect_id: str) -> int:
    """The number of ACTIVE (non-NOT_POSSIBLE) compensations for one invalidated effect — the exact
    population entity §17's partial-UNIQUE index bounds to <= 1. Read from real DB state."""
    return int(conn.execute(
        "SELECT COUNT(*) FROM compensations WHERE tenant = ? AND original_effect_id = ? "
        "AND state != 'NOT_POSSIBLE'", (tenant, original_effect_id)).fetchone()[0])


def _two_active_is_a_violation(active_count: int) -> bool:
    """R4's forbidden state: more than one active compensation for a single invalidated effect."""
    return active_count > 1


def _race_concurrent_raises(store, gid: str, dref: str, *, contenders: int = 8):
    """`contenders` pipelines, each on its OWN connection (P3/P4 per-thread-connection discipline),
    concurrently raise a compensation for the SAME invalidated effect. Returns (wins, refusals)."""
    dbpath = [r[2] for r in store.conn.execute("PRAGMA database_list")][0]
    wins: list[str] = []
    refusals: list[str] = []

    def worker(i):
        conn = sqlite3.connect(dbpath)
        conn.row_factory = sqlite3.Row
        enable_and_verify_foreign_keys(conn)
        mm = M10Machine(conn, tenant=TENANT, clock=ck.Clock())
        try:
            rr = mm.raise_from_correction(
                original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"),
                reason="race", decision_ref=dref, compensation_id=f"cmp-r4-{i}")
            wins.append(rr.compensation.compensation_id)
        except Exception as exc:  # noqa: BLE001 — the serialized loser is a RESULT, not a lost thread
            refusals.append(f"{type(exc).__name__}: {exc}")
        finally:
            conn.close()

    run_race(worker, [(i,) for i in range(contenders)], label="r4-compensation")
    return wins, refusals


# --------------------------------------------------------------------------- the guard
def test_r4_concurrent_compensation_creation_yields_exactly_one_active(tmp_path):
    """THE GUARD. Eight pipelines concurrently raise a compensation for ONE invalidated effect; the
    M10 one-active partial-UNIQUE index must serialize them to EXACTLY ONE active compensation. FAILS
    if two active compensations for one invalidated effect ever coexist — R4's forbidden double-act on
    the money layer (AC-REC-003)."""
    store, clk = _store(tmp_path)
    gid = ck.a_verified_original_effect(store, tenant=TENANT, grant_id="g-r4", clock=clk)
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=HUMAN, seed="r4", clock=clk)

    wins, refusals = _race_concurrent_raises(store, gid, dref, contenders=8)
    # Proven population (CLAUDE.md §6): all eight actually reached the index — one active row is not
    # evidence of serialization if seven raisers never contended.
    assert len(wins) + len(refusals) == 8, (
        f"only {len(wins) + len(refusals)} of 8 raisers contended; wins={wins} refusals={refusals}")

    active = _active_compensation_count(store.conn, TENANT, gid)
    assert not _two_active_is_a_violation(active), (
        f"R4 VIOLATED: concurrent creation produced {active} active compensations for one invalidated "
        f"effect — two individually-ungated reversals double-act on the money layer (AC-REC-003).")
    assert active == 1, f"expected exactly one active compensation, found {active}"
    store.close()


# --------------------------------------------------------------------------- the RED control
def test_r4_control_catches_two_active_compensations(tmp_path, monkeypatch):
    """THE CONTROL — proves the guard is not vacuous by reintroducing R4's forbidden state.

    Facet A — the decision discriminates (two active is a violation, one is not).
    Facet B — real-product tie: the one-active partial-UNIQUE index is LOAD-BEARING. With it dropped on
      the THROWAWAY test database (never the product schema), a SECOND active compensation row for one
      invalidated effect IS insertable, and `_active_compensation_count` reads two — so the guard
      measures real DB state and the index is exactly what prevents R4.
    Facet C — seen RED: with the active count forced to the forbidden value, THE GUARD's own assertion
      path raises (the "guard invoked while the forbidden behaviour is reintroduced, expected to fail"
      control CLAUDE.md §6 demands)."""
    g = sys.modules[__name__]

    # Facet A — the decision function discriminates.
    assert _two_active_is_a_violation(2) and not _two_active_is_a_violation(1)

    # Facet B — the one-active index is load-bearing: without it, two active rows coexist for one effect.
    store, clk = _store(tmp_path)
    gid = ck.a_verified_original_effect(store, tenant=TENANT, grant_id="g-r4-ctl", clock=clk)
    dref = ck.a_human_decision(store, tenant=TENANT, actor_id=HUMAN, seed="r4ctl", clock=clk)
    m = M10Machine(store.conn, tenant=TENANT, clock=clk)
    r = m.raise_from_correction(
        original_effect_id=gid, owner_id=HUMAN, exposure=Money(1, "GBP"),
        reason="one", decision_ref=dref, compensation_id="cmp-r4-ctl-1")
    assert _active_compensation_count(store.conn, TENANT, gid) == 1
    # Drop the enforcement on the throwaway DB (simulating the defect; NOT a product schema change),
    # then insert a SECOND active row for the SAME effect by copying the first (a new id only).
    store.conn.execute(f"DROP INDEX {ONE_ACTIVE_INDEX}")
    row = dict(store.conn.execute(
        "SELECT * FROM compensations WHERE compensation_id = ?",
        (r.compensation.compensation_id,)).fetchone())
    row["compensation_id"] = "cmp-r4-ctl-2"        # a SECOND active compensation for the SAME effect
    cols = ",".join(row)
    store.conn.execute(
        f"INSERT INTO compensations ({cols}) VALUES ({','.join('?' * len(row))})",
        tuple(row.values()))
    store.conn.commit()
    active = _active_compensation_count(store.conn, TENANT, gid)
    assert active == 2 and _two_active_is_a_violation(active), (
        f"the one-active index is not load-bearing (found {active} active after dropping it) — the "
        f"guard's forbidden state would be unreachable and its assertion vacuous")
    store.close()

    # Facet C — the guard, run with the forbidden active count reintroduced, MUST fail.
    monkeypatch.setattr(g, "_active_compensation_count", lambda *a, **k: 2)
    with pytest.raises(AssertionError, match="R4 VIOLATED"):
        g.test_r4_concurrent_compensation_creation_yields_exactly_one_active(tmp_path / "red")
