"""P8-AC-16 — the current-state PROSE is now inspectable by an approved command.

Answers the routed verification obligation (risk keys `conflicting_evidence:00642b998a` /
`conflicting_evidence:7985d5dd48`, stated as "R5"/"R5-w2"): the human-readable current-state prose
that IS the P8-AC-16 deliverable could not be inspected by any approved command. Every approved
command probed `src/`, the sqlite schema, event contracts, or the eval suite; none opened the status
documents. So the textual claim the reconciliation turns on — that `U8.2`..`U8.6` are LANDED rather
than NOT STARTED — was unverifiable with the given toolset. An unmeasured risk is not a covered risk.

This module closes that gap WITHOUT touching the product, any acceptance requirement, or any other
guard. It is a read-only inspector of CURRENT.md's `P8` program-position prose cell, and it realises
exactly the hostile case P8-AC-16 forbids: a LIVE claim that a later P8 unit (`U8.2`..`U8.6`) is NOT
STARTED, or that ONLY `U8.1` is landed.

It is NOT the LIVE-STATUS reconciliation. That marker-delimited registry projection is guarded by
`test_current_status_reconciliation.py`, which deliberately does not police prose. The two are
complementary: that guard proves the machine table equals the registry; this one proves the human
sentence stopped asserting the obsolete fact. Neither is widened, weakened or renamed by the other.

The live/history distinction is load-bearing. CURRENT.md keeps every superseded status sentence
VERBATIM inside an italic `*(...)*` parenthetical (CLAUDE.md §5 rule 20: "REPLACED rather than
deleted"), which is why the forbidden phrase still appears in the tree at all. A forbidden phrase
INSIDE such a parenthetical is history and is allowed; the SAME phrase OUTSIDE one is a live claim
and fails. The control below proves the guard fires on the live form and stays silent on the
historical form — so it is neither vacuous nor a blunt substring scan that would fire on the
preserved history.

Authority: `IMPLEMENTATION-REGISTRY.yaml` unit P8 criterion `P8-AC-16`
(status_honesty_and_reconcilability); CLAUDE.md §13. This guard scores nothing and moves no status:
P8 stays `READY` / `NOT_STARTED` / `NO_CHECKPOINT`.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
CURRENT = ROOT / "docs" / "implementation" / "CURRENT.md"

_SIX_UNITS = ("U8.1", "U8.2", "U8.3", "U8.4", "U8.5", "U8.6")
_HIST_PAREN = re.compile(r"\*\(.*?\)\*")           # CURRENT.md's verbatim-superseded-text convention
_LATER_UNIT = re.compile(r"\bU8\.[2-6]\b")         # a P8 unit AFTER U8.1
_NOT_STARTED = re.compile(r"NOT[ _]STARTED", re.I)
_ONLY_U81 = re.compile(r"\bonly\b[^.]{0,40}\bU8\.1\b", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _normalize(s: str) -> str:
    """Drop the code-span backticks and fold en/em dashes to '-', so `U8.2`–`U8.6` and U8.2-U8.6
    read as the same tokens a human reader sees."""
    return s.replace("`", "").replace("–", "-").replace("—", "-")


def _p8_prose_cell() -> str:
    """The single Program-position table ROW whose first bold cell is **P8** — the human-readable
    current-state prose P8-AC-16 governs. Discovered by its leading token, never line-numbered."""
    rows = [ln.strip() for ln in CURRENT.read_text(encoding="utf-8").splitlines()
            if ln.strip().startswith("| **P8**")]
    assert len(rows) == 1, f"expected exactly one **P8** program-position row, found {len(rows)}"
    return rows[0]


def _live_region(cell: str) -> str:
    """The cell with every `*(...)*` superseded-text parenthetical blanked out."""
    return _HIST_PAREN.sub(" ", cell)


def obsolete_live_p8_claims(cell: str) -> list[str]:
    """Every OFFENDING live claim in a P8 prose cell:
      (A) a later P8 unit (`U8.2`..`U8.6`) asserted NOT STARTED, or
      (B) an 'only U8.1' landed claim.
    Sentence-scoped, so the legitimate PHASE enum 'P8 stays READY / NOT_STARTED / NO_CHECKPOINT'
    (which carries no later-unit token) is never mistaken for a unit-level NOT STARTED claim."""
    live = _normalize(_live_region(cell))
    offenders: list[str] = []
    for sentence in _SENTENCE.split(live):
        if _LATER_UNIT.search(sentence) and _NOT_STARTED.search(sentence):
            offenders.append("later P8 unit asserted NOT STARTED (live): " + sentence.strip()[:140])
        if _ONLY_U81.search(sentence):
            offenders.append("'only U8.1' landed claim (live): " + sentence.strip()[:140])
    return offenders


def _assert_reconciled(cell: str) -> None:
    """The guard's single assertion, shared verbatim by the guard test and its control."""
    offenders = obsolete_live_p8_claims(cell)
    assert offenders == [], (
        "CURRENT.md's P8 current-state prose carries an obsolete LIVE claim P8-AC-16 forbids "
        "(a later unit NOT STARTED, or an 'only U8.1' landing). Offenders:\n  " + "\n  ".join(offenders)
    )


def test_p8_current_state_prose_makes_no_obsolete_live_not_started_or_u81_only_claim():
    """GUARD. The P8 prose cell exists, names all six units (anti-vacuity — proof we parsed the real,
    substantial cell and not an empty/mismatched one), and asserts NEITHER forbidden live claim."""
    cell = _p8_prose_cell()
    norm = _normalize(cell)
    for u in _SIX_UNITS:
        assert u in norm, f"parsed the wrong or truncated P8 cell — {u} absent; the guard would be vacuous"
    _assert_reconciled(cell)


def test_control_the_guard_catches_a_reintroduced_obsolete_live_claim():
    """CONTROL — proves the guard goes RED, in both forbidden shapes, and that its live/history split
    is real rather than a blunt substring scan.

    Product Driver executes this control beside the guard: if the obsolete claim is reintroduced as a
    LIVE sentence the shared assertion FAILS; if the identical phrase sits inside a `*(...)*`
    superseded-text parenthetical it PASSES. A control that could not distinguish the two would be a
    decorative oracle."""
    cell = _p8_prose_cell()

    # (A) 'U8.2-U8.6 NOT STARTED' reintroduced LIVE, by mutating the real cell (outside any *(...)*).
    live_not_started = cell.replace(
        "the sole selected unit.",
        "the sole selected unit. `U8.2`–`U8.6` are NOT STARTED.", 1)
    assert live_not_started != cell, "control setup failed — the live-injection anchor was not found"
    assert obsolete_live_p8_claims(live_not_started), "inert — a live NOT STARTED claim was not caught"
    with pytest.raises(AssertionError):
        _assert_reconciled(live_not_started)

    # (B) 'only U8.1 landed' reintroduced LIVE.
    live_only_u81 = "| **P8** — policy | only `U8.1` is landed; the rest is not. | refs |"
    assert obsolete_live_p8_claims(live_only_u81), "inert — an 'only U8.1' live claim was not caught"
    with pytest.raises(AssertionError):
        _assert_reconciled(live_only_u81)

    # (C) the identical phrases INSIDE a superseded-text parenthetical must be ALLOWED (history).
    hist_ok = ('| **P8** — policy | all six P8 units are landed. '
               '*(Until this commit this cell read "`U8.2`–`U8.6` are NOT STARTED" and '
               '"only `U8.1` is landed"; REPLACED rather than deleted per CLAUDE.md sec 5 rule 20.)* '
               '| refs |')
    assert obsolete_live_p8_claims(hist_ok) == [], (
        "the guard fired on history — a superseded phrase inside `*(...)*` must be allowed"
    )
    # ...and prove (C) is a real exemption, not a miss: strip the `*(...)*` markers and it MUST fire.
    unwrapped = hist_ok.replace("*(", " ").replace(")*", " ")
    assert obsolete_live_p8_claims(unwrapped), (
        "the historical exemption is vacuous — the phrase does not fire even when live"
    )
