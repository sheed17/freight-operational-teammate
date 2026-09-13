"""CURRENT.md's live-status projection is reconciled against the machine authority.

CLAUDE.md and CURRENT.md's own header declare CURRENT.md the human short-form status authority and
[`IMPLEMENTATION-REGISTRY.yaml`] the MACHINE authority. CURRENT.md restates status in free narrative,
which an acceptance materializer cannot reconcile without composing prose. This guard does NOT police
that prose — it is human orientation and history under CLAUDE.md §5 rule 20 and is deliberately left
untouched. It reconciles the ONE bounded, marker-delimited `LIVE-STATUS` block CURRENT.md carries for
exactly this purpose: that block is a DETERMINISTIC PROJECTION of the registry's phase-unit lifecycle
fields (`status` / `execution_state` / `checkpoint_state`), and this module proves the projection
cannot drift from the authority.

The direction of authority is one-way and stays that way: the registry is the source, the CURRENT.md
block is a derived view, and nothing here makes CURRENT.md authoritative over the registry. When a
phase lifecycle field changes in the registry (e.g. P7 is later accepted), the block is regenerated
from the registry — the failure message prints the exact expected rows — rather than narrated.
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "docs" / "implementation" / "IMPLEMENTATION-REGISTRY.yaml"
CURRENT = ROOT / "docs" / "implementation" / "CURRENT.md"

# FIXED-SPECIFICATION: the three phase-lifecycle fields the projection carries are the registry's
# own canonical status vocabulary (meta.status_model), the exact contract this guard reconciles — a
# specification, not a discovered file population.
_PROJECTED_FIELDS = ("status", "execution_state", "checkpoint_state")
_BEGIN = "<!-- LIVE-STATUS:BEGIN"
_END = "<!-- LIVE-STATUS:END -->"
_PHASE_ID = re.compile(r"P\d+")


def require_population(items, what: str):
    assert items, f"no {what} to assert over — this guard would pass vacuously"
    return items


def _registry_phase_status() -> dict[str, tuple[str, ...]]:
    """DISCOVERED, never enumerated: every TOP-LEVEL phase unit (`unit_id` = `Pn`) mapped to its
    lifecycle triple. Sub-units (`U-HANDOFF-1`, `U-REBASELINE-1`, per-checkpoint units) are correctly
    excluded — they are not phases and do not appear in the live-status projection."""
    units = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["units"]
    out: dict[str, tuple[str, ...]] = {}
    for u in units:
        uid = str(u.get("unit_id", ""))
        if _PHASE_ID.fullmatch(uid):
            out[uid] = tuple(str(u[f]) for f in _PROJECTED_FIELDS)
    return out


def _current_status_block() -> str:
    text = CURRENT.read_text(encoding="utf-8")
    assert _BEGIN in text and _END in text, (
        "CURRENT.md is missing its bounded LIVE-STATUS block — the acceptance materializer has no "
        "deterministic region to reconcile against the registry"
    )
    start = text.index(_BEGIN)
    end = text.index(_END, start)
    assert start < end, "the LIVE-STATUS markers are out of order in CURRENT.md"
    return text[start:end]


def _rows_of(block: str) -> dict[str, tuple[str, ...]]:
    """The `| Pn | ... |` rows of a markdown table, as `{phase: (field values...)}`. The header and
    separator rows are skipped because their first cell is not a phase id."""
    rows: dict[str, tuple[str, ...]] = {}
    for line in block.split("\n"):
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) == 1 + len(_PROJECTED_FIELDS) and _PHASE_ID.fullmatch(cells[0]):
            rows[cells[0]] = tuple(cells[1:])
    return rows


def _render_projection(status: dict[str, tuple[str, ...]]) -> str:
    """The deterministic renderer, ordered by phase number. This is what a materializer regenerates
    into the marked block; printing it on mismatch makes the guard self-documenting."""
    header = "| Phase | " + " | ".join(_PROJECTED_FIELDS) + " |"
    sep = "|" + "|".join(["---"] * (1 + len(_PROJECTED_FIELDS))) + "|"
    body = [f"| {p} | " + " | ".join(status[p]) + " |"
            for p in sorted(status, key=lambda x: int(x[1:]))]
    return "\n".join([header, sep, *body])


def test_the_live_status_block_reconciles_exactly_with_the_registry():
    """The marked block equals the registry-derived projection, in BOTH directions: every phase unit
    in the registry appears with its exact lifecycle triple, and the block carries no phase the
    registry does not. A mismatch means the human status restatement drifted from the machine
    authority — regenerate the block from the registry."""
    expected = require_population(_registry_phase_status(), "registry phase units")
    assert len(expected) >= 8, f"phase-unit discovery collapsed to {len(expected)} — near-vacuous"
    actual = _rows_of(_current_status_block())
    assert actual == expected, (
        "CURRENT.md's LIVE-STATUS block drifted from IMPLEMENTATION-REGISTRY.yaml (the machine "
        "authority). Regenerate the bounded block from the registry — do not hand-edit it.\n\n"
        "Expected projection:\n" + _render_projection(expected)
        + f"\n\nParsed from CURRENT.md: {actual}"
    )


def test_the_reconciliation_is_populated_and_its_drift_detector_fires():
    """Anti-vacuity (CLAUDE.md §6): an equality that passed could mean "no drift" OR "nothing was
    parsed". Prove the block parsed real rows for real phases, and that the comparison NOTICES a
    single changed cell and a dropped row — the two ways a live restatement drifts."""
    registry = _registry_phase_status()
    actual = _rows_of(_current_status_block())
    assert actual, "no rows parsed out of the LIVE-STATUS block — the parser would compare nothing"
    assert actual == registry, "precondition: the tree is expected to be reconciled here"
    assert _PHASE_ID.fullmatch(sorted(actual)[0]), "parsed a non-phase row into the projection"

    victim = sorted(actual, key=lambda x: int(x[1:]))[0]
    mutated = dict(actual)
    mutated[victim] = ("DRIFTED",) + mutated[victim][1:]
    assert mutated != registry, "the reconciliation would not notice a changed status cell"

    dropped = {k: v for k, v in actual.items() if k != victim}
    assert dropped != registry, "the reconciliation would not notice a dropped phase row"

    extra = {**actual, "P999": ("BLOCKED", "NOT_STARTED", "NO_CHECKPOINT")}
    assert extra != registry, "the reconciliation would not notice an invented phase row"
