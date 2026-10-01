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

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
CURRENT = ROOT / "docs" / "implementation" / "CURRENT.md"
PHASE_OUTPUTS = ROOT / "docs" / "implementation" / "PHASE-OUTPUTS.md"
PR_SEQUENCE = ROOT / "docs" / "implementation" / "pr-sequence.md"
REGISTRY = ROOT / "docs" / "implementation" / "IMPLEMENTATION-REGISTRY.yaml"
EVENT_CONTRACTS = ROOT / "src" / "freight_recon" / "event_contracts_data.json"

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


# --------------------------------------------------------------------------------------------------
# Correction 2: coverage across EVERY P8 status surface + a registry cross-check, and a discriminating
# mutation battery bound to the guard node ids (drives them RED on the real files, GREEN on restore).
# --------------------------------------------------------------------------------------------------

_GUARD_OBSOLETE = "test_p8_current_state_prose_makes_no_obsolete_live_not_started_or_u81_only_claim"
_GUARD_SURFACES = "test_all_p8_status_surfaces_are_reconciled_and_imply_no_acceptance"
_GUARD_MACHINE = "test_p8_ac16_prose_reconciles_with_the_canonical_machine_authorities"

# Affirmative "this phase is done" predicates. 'is COMPLETE' / 'is now ACCEPTED' /
# PHASE_ACCEPTANCE_COMPLETE / a 17/17 criteria tally are forbidden as LIVE claims about P8. The
# negated 'is not COMPLETE' cannot match: 'not' breaks the 'is (now) COMPLETE' contiguity, so this
# predicate needs no separate negation pass and cannot be fooled by a distant sibling negation.
_ACCEPTED_COMPLETE = re.compile(
    r"\bis\s+(?:now\s+)?(?:COMPLETE|ACCEPTED)\b"
    r"|PHASE_ACCEPTANCE_COMPLETE"
    r"|\b17\s*/\s*17\b",
    re.I,
)


def implies_accepted_or_complete(region: str) -> list[str]:
    """Every affirmative LIVE claim that P8 is ACCEPTED / COMPLETE / scored, in the region's live
    text (superseded *(...)* history exempt)."""
    live = _normalize(_live_region(region))
    return [m.group(0) for m in _ACCEPTED_COMPLETE.finditer(live)]


def _phase_outputs_p8_section() -> tuple[str, str]:
    """The PHASE-OUTPUTS.md `## P8 …` section (heading through the next `## `), plus its heading line.
    The heading carries the repo's own status token vocabulary (COMPLETE / IN PROGRESS / NOT STARTED)."""
    lines = PHASE_OUTPUTS.read_text(encoding="utf-8").splitlines()
    heads = [i for i, ln in enumerate(lines) if ln.startswith("## P8 ")]
    assert len(heads) == 1, f"expected exactly one PHASE-OUTPUTS '## P8' heading, found {len(heads)}"
    start = heads[0]
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return "\n".join(lines[start:end]), lines[start]


def _pr_sequence_p8_line() -> str:
    """The pr-sequence.md `**P8:**` plan row that enumerates the P8 units."""
    rows = [ln.strip() for ln in PR_SEQUENCE.read_text(encoding="utf-8").splitlines()
            if ln.strip().startswith("**P8:**")]
    assert len(rows) == 1, f"expected exactly one pr-sequence '**P8:**' row, found {len(rows)}"
    return rows[0]


def _registry_phase_status() -> dict[str, tuple[str, str, str]]:
    """Every top-level phase unit (`unit_id` = `Pn`) mapped to its lifecycle triple — the MACHINE
    authority the human prose must agree with."""
    units = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["units"]
    phase = re.compile(r"P\d+")
    out: dict[str, tuple[str, str, str]] = {}
    for u in units:
        uid = str(u.get("unit_id", ""))
        if phase.fullmatch(uid):
            out[uid] = (str(u["status"]), str(u["execution_state"]), str(u["checkpoint_state"]))
    return out


def _assert_registry_lifecycle(status: dict) -> None:
    """P8 stands at READY/NOT_STARTED/NO_CHECKPOINT and P9..P14 are BLOCKED. Shared by the guard and
    its in-process control so the cross-check's discrimination is itself proven."""
    assert status.get("P8") == ("READY", "NOT_STARTED", "NO_CHECKPOINT"), (
        f"registry P8 lifecycle is not READY/NOT_STARTED/NO_CHECKPOINT: {status.get('P8')}")
    for p in ("P9", "P10", "P11", "P12", "P13", "P14"):
        assert status.get(p, ("",))[0] == "BLOCKED", f"registry {p} is not BLOCKED: {status.get(p)}"


def test_all_p8_status_surfaces_are_reconciled_and_imply_no_acceptance():
    """GUARD (broadened). Every human-readable P8 status surface — CURRENT.md, PHASE-OUTPUTS.md,
    pr-sequence.md — is free of an obsolete live P8 unit claim AND of an affirmative
    accepted/COMPLETE/scored claim; the PHASE-OUTPUTS P8 heading still reads NOT STARTED; and all of it
    agrees with the registry projection (P8 READY/NOT_STARTED/NO_CHECKPOINT; P9-P14 BLOCKED). The
    live/history split is preserved: superseded text inside *(...)* is exempt everywhere."""
    current = _p8_prose_cell()
    po_section, po_heading = _phase_outputs_p8_section()
    pr_line = _pr_sequence_p8_line()

    # FIXED-SPECIFICATION: NOT a discovered population — the exact, bounded set of human P8
    # status/roadmap surfaces this AC-16 verification reconciles, each region already extracted above.
    surfaces = {"CURRENT.md": current, "PHASE-OUTPUTS.md": po_section, "pr-sequence.md": pr_line}
    for name, region in surfaces.items():
        assert obsolete_live_p8_claims(region) == [], (
            f"{name} carries an obsolete live P8 unit claim: {obsolete_live_p8_claims(region)}")
        assert implies_accepted_or_complete(region) == [], (
            f"{name} implies P8 accepted/COMPLETE/scored (live): {implies_accepted_or_complete(region)}")

    # the PHASE-OUTPUTS P8 heading token is the repo's own status vocabulary; it must read NOT STARTED.
    assert "NOT STARTED" in po_heading, f"PHASE-OUTPUTS P8 heading lost its NOT STARTED token: {po_heading}"
    assert "✅ COMPLETE" not in po_heading and "IN PROGRESS" not in po_heading, (
        f"PHASE-OUTPUTS P8 heading implies acceptance/progress: {po_heading}")

    # machine authority, and the human narrative agreeing with it.
    _assert_registry_lifecycle(_registry_phase_status())
    live = _normalize(_live_region(current))
    for token in ("READY", "NOT_STARTED", "NO_CHECKPOINT"):
        assert token in live, f"CURRENT.md P8 prose no longer states the {token} lifecycle enum"
    assert "ships dark" in live.lower(), "CURRENT.md P8 prose no longer states the ship-dark posture"


# --------------------------------------------------------------------------------------------------
# R5-w3: the status prose is not merely READ but RECONCILED against the canonical MACHINE authorities
# the approved toolset probes — the P8-AC-16 criterion itself ("ac_16") and event_contracts_data.json.
# A guard that only scanned prose in isolation could not detect a conflict between the prose and the
# machine truth, which is exactly the "conflicting_evidence" hazard this obligation names.
# --------------------------------------------------------------------------------------------------

_MEASURED_EVENTS = re.compile(r"event contracts, measured:\s*(\d+)", re.I)


def _p8_ac16_criterion() -> dict:
    """The P8-AC-16 acceptance criterion, read from the MACHINE authority (IMPLEMENTATION-REGISTRY.yaml
    unit P8 `acceptance_criteria`). This is the "ac_16" artifact: the guard is provably about the exact
    criterion whose deliverable is the reconciled prose."""
    reg = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    unit = next((u for u in reg["units"] if str(u.get("unit_id")) == "P8"), None)
    assert unit is not None, "unit P8 not found in the registry"
    crit = next((c for c in unit.get("acceptance_criteria", []) if str(c.get("id")) == "P8-AC-16"), None)
    assert crit is not None, "P8-AC-16 criterion not found under unit P8 in the registry"
    return crit


def _assert_ac16_criterion(crit: dict) -> None:
    """P8-AC-16 is the status-honesty criterion, is required, is still PENDING (this run scores
    nothing), and its own oracle names the status reconciliation surfaces. Shared by the guard and its
    in-process control."""
    assert crit.get("criterion") == "status_honesty_and_reconcilability", (
        f"P8-AC-16 is not the status-honesty criterion: {crit.get('criterion')!r}")
    assert crit.get("required") is True, "P8-AC-16 is no longer required"
    assert str(crit.get("result")) == "PENDING", (
        f"P8-AC-16 must remain PENDING (this run scores nothing); found {crit.get('result')!r}")
    oracle = str(crit.get("oracle", ""))
    assert "test_current_status_reconciliation.py" in oracle and "CURRENT.md" in oracle, (
        "P8-AC-16's own oracle no longer names the status reconciliation surfaces")


def _canonical_event_contract_total() -> int:
    """The canonical event-corpus total, from event_contracts_data.json (the mechanical projection of
    events/registry.md §6). Self-consistency of the projection is asserted so the number the prose is
    reconciled against is itself trustworthy."""
    data = json.loads(EVENT_CONTRACTS.read_text(encoding="utf-8"))
    contracts, counts = data["contracts"], data["_counts"]
    assert len(contracts) == int(counts["total"]), (
        f"event_contracts_data.json is internally inconsistent: len(contracts)={len(contracts)} "
        f"vs _counts.total={counts['total']}")
    return len(contracts)


def _current_measured_event_contract_counts() -> list[int]:
    """Every LIVE 'event contracts, measured: N' figure in CURRENT.md (superseded *(...)* history
    exempt)."""
    live = _HIST_PAREN.sub(" ", CURRENT.read_text(encoding="utf-8"))
    return [int(x) for x in _MEASURED_EVENTS.findall(live)]


def test_p8_ac16_prose_reconciles_with_the_canonical_machine_authorities():
    """GUARD (R5-w3). The AC-16 status-prose deliverable is not scanned in isolation — it is RECONCILED
    against the canonical machine authorities the approved toolset reads:

      * ac_16 — the P8-AC-16 criterion is read from the registry; it exists, is required, is still
        PENDING (this run scores nothing), and its own oracle names the reconciliation surfaces.
      * event_contracts_data.json — the canonical event-corpus total is read (and proven internally
        self-consistent), and CURRENT.md's LIVE 'event contracts, measured: N' figure must EQUAL it.
        A prose figure that drifts from the machine source is exactly the status dishonesty this
        criterion forbids."""
    _assert_ac16_criterion(_p8_ac16_criterion())

    canonical_total = _canonical_event_contract_total()
    claimed = _current_measured_event_contract_counts()
    assert claimed, "CURRENT.md no longer carries a measurable 'event contracts, measured: N' claim"
    for value in claimed:
        assert value == canonical_total, (
            f"status dishonesty: CURRENT.md claims 'event contracts, measured: {value}' but "
            f"event_contracts_data.json canonically holds {canonical_total} contracts")


def _run_guard_node(node: str) -> int:
    """Run ONE guard node id in a fresh pytest process against the tree on disk. 0 == GREEN, non-zero
    == RED. Product Driver runs the guard the same way — by node id — so this measures the guard, not a
    private copy of its logic."""
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", node, "-q", "-p", "no:cacheprovider", "-o", "addopts="],
        cwd=str(ROOT), capture_output=True, text=True)
    return proc.returncode


_THIS = str(Path(__file__).resolve())


def test_control_battery_drives_the_guards_red_on_each_reintroduced_claim_and_green_on_restore():
    """CONTROL — the discriminating mutation battery, bound to the guard NODE IDS. For each forbidden
    LIVE-claim shape it MUTATES THE REAL status document, runs the relevant guard by node id in a fresh
    process, and requires RED; then it restores the file from an in-memory copy (never git) and requires
    GREEN. A guard that stayed GREEN under a reintroduced claim would be a decorative oracle that proves
    nothing (Founder context §8)."""
    obsolete_node = f"{_THIS}::{_GUARD_OBSOLETE}"
    surfaces_node = f"{_THIS}::{_GUARD_SURFACES}"
    machine_node = f"{_THIS}::{_GUARD_MACHINE}"

    assert _run_guard_node(obsolete_node) == 0, "positive control failed: obsolete-claim guard not GREEN"
    assert _run_guard_node(surfaces_node) == 0, "positive control failed: surfaces guard not GREEN"
    assert _run_guard_node(machine_node) == 0, "positive control failed: machine-authorities guard not GREEN"

    mutants = [
        (CURRENT, "the sole selected unit.",
         "the sole selected unit. `U8.2`–`U8.6` are NOT STARTED.",
         obsolete_node, "CURRENT: later units NOT STARTED (live)"),
        (CURRENT, "the sole selected unit.",
         "the sole selected unit. Only `U8.1` is landed; the rest are not.",
         obsolete_node, "CURRENT: only U8.1 landed (live)"),
        (CURRENT, "and is **not** `COMPLETE`", "and is now `COMPLETE`",
         surfaces_node, "CURRENT: P8 is now COMPLETE (live)"),
        (PHASE_OUTPUTS, "Compensation ⛔ NOT STARTED", "Compensation ✅ COMPLETE",
         surfaces_node, "PHASE-OUTPUTS: P8 heading flipped to COMPLETE"),
        (PR_SEQUENCE, "U8.2 ### **compile-or-refuse Rules**",
         "U8.2 ### **compile-or-refuse Rules** are NOT STARTED",
         surfaces_node, "pr-sequence: U8.2 NOT STARTED (live)"),
        (CURRENT, "event contracts, measured: 118", "event contracts, measured: 999",
         machine_node, "CURRENT: measured event-contract count contradicts event_contracts_data.json"),
    ]

    caught = 0
    for path, find, repl, node, label in mutants:
        original = path.read_bytes()
        try:
            text = original.decode("utf-8")
            assert find in text, f"mutation anchor not found for [{label}] in {path.name}: {find!r}"
            path.write_text(text.replace(find, repl, 1), encoding="utf-8")
            rc = _run_guard_node(node)
            assert rc != 0, f"NON-DISCRIMINATING: a guard stayed GREEN under mutation [{label}]"
            caught += 1
        finally:
            path.write_bytes(original)

    assert _run_guard_node(obsolete_node) == 0, "obsolete-claim guard not GREEN after restore"
    assert _run_guard_node(surfaces_node) == 0, "surfaces guard not GREEN after restore"
    assert _run_guard_node(machine_node) == 0, "machine-authorities guard not GREEN after restore"
    print(f"P8-AC-16 status-prose mutation battery: {caught}/{len(mutants)} mutants drove a guard RED; "
          "0 escaped; files restored from an in-memory copy.")
    assert caught == len(mutants)


def test_control_the_registry_cross_check_catches_a_completed_or_unblocked_projection():
    """CONTROL — proves the registry cross-check is discriminating WITHOUT mutating the real registry.
    A synthetic projection that marks P8 COMPLETE, or unblocks P9, must fail the check; the true
    projection must pass."""
    good = {"P8": ("READY", "NOT_STARTED", "NO_CHECKPOINT")}
    for p in ("P9", "P10", "P11", "P12", "P13", "P14"):
        good[p] = ("BLOCKED", "NOT_STARTED", "NO_CHECKPOINT")
    _assert_registry_lifecycle(good)  # true projection: must not raise

    completed = dict(good, P8=("COMPLETE", "COMPLETE", "PHASE_ACCEPTANCE_COMPLETE"))
    with pytest.raises(AssertionError):
        _assert_registry_lifecycle(completed)

    unblocked = dict(good, P9=("READY", "NOT_STARTED", "NO_CHECKPOINT"))
    with pytest.raises(AssertionError):
        _assert_registry_lifecycle(unblocked)


def test_control_the_ac16_criterion_check_catches_a_scored_or_unrequired_criterion():
    """CONTROL — proves the 'ac_16' side of the machine-authorities guard is discriminating without
    editing the registry: a synthetic P8-AC-16 that has been scored PASS, made not-required, or whose
    oracle no longer names the reconciliation surfaces must fail the check; the true criterion passes."""
    good = {
        "id": "P8-AC-16",
        "criterion": "status_honesty_and_reconcilability",
        "required": True,
        "result": "PENDING",
        "oracle": "eval/tests/test_current_status_reconciliation.py (...); reconciliation of CURRENT.md and PHASE-OUTPUTS.md.",
    }
    _assert_ac16_criterion(good)  # true criterion: must not raise

    with pytest.raises(AssertionError):
        _assert_ac16_criterion(dict(good, result="PASS"))
    with pytest.raises(AssertionError):
        _assert_ac16_criterion(dict(good, required=False))
    with pytest.raises(AssertionError):
        _assert_ac16_criterion(dict(good, oracle="something that names no reconciliation surface"))
