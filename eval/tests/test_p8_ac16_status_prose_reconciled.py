"""P8-AC-16 — the current-state PROSE is inspectable by an approved command, in BOTH lifecycle states.

Answers the routed verification obligation (risk keys `conflicting_evidence:00642b998a` /
`conflicting_evidence:7985d5dd48`, stated as "R5"/"R5-w2"): the human-readable current-state prose
that IS the P8-AC-16 deliverable could not be inspected by any approved command. Every approved
command probed `src/`, the sqlite schema, event contracts, or the eval suite; none opened the status
documents. So the textual claim the reconciliation turns on — that `U8.2`..`U8.6` are LANDED rather
than NOT STARTED — was unverifiable with the given toolset. An unmeasured risk is not a covered risk.

This module closes that gap WITHOUT touching the product, any acceptance requirement, or any other
guard. It is a read-only inspector of the human P8 status surfaces, and it realises exactly the
hostile case P8-AC-16 forbids: prose that disagrees with the machine authority.

It is NOT the LIVE-STATUS reconciliation. That marker-delimited registry projection is guarded by
`test_current_status_reconciliation.py`, which deliberately does not police prose. The two are
complementary: that guard proves the machine table equals the registry; this one proves the human
sentence agrees with it. Neither is widened, weakened or renamed by the other.

LIFECYCLE-AWARE, AND THE LIFECYCLE IS READ FROM THE REGISTRY — NEVER CHOSEN BY THE PROSE. Until the
P8 phase acceptance this module hard-coded the PRE-acceptance state (P8 `READY` / `NOT_STARTED` /
`NO_CHECKPOINT`, P9–P14 `BLOCKED`, `P8-AC-16` `PENDING`, "no acceptance" prose). That made the
truthful acceptance record unwritable: the guard went RED the moment the registry said what the
independent review had established, so the record was rolled back. A guard that can only pass in
the state before the event it guards is a deadlock, not a protection. It now recognises exactly TWO
P8 lifecycle triples and holds every surface to whichever one the registry records:

  * PENDING  (`READY` / `NOT_STARTED` / `NO_CHECKPOINT`) — unchanged from before: no surface may
    imply acceptance, the PHASE-OUTPUTS heading reads NOT STARTED, `P8-AC-16` is `PENDING`, and
    every later phase is `BLOCKED`.
  * ACCEPTED (`COMPLETE` / `COMPLETE` / `PHASE_ACCEPTANCE_COMPLETE`) — the mirror image: no surface
    may still claim P8 is not started or unaccepted, the PHASE-OUTPUTS heading reads COMPLETE,
    `P8-AC-16` is `PASS` with recorded adjudication evidence, and P9 has taken the selector.

Any OTHER triple fails, and so does every MIXED state — an accepted registry beside pending prose,
pending registry beside accepted prose, a half-flipped triple, a scored criterion under a pending
phase. There is no third branch to hide in. In BOTH states the ships-dark posture is required:
accepted is not enabled.

The live/history distinction is load-bearing. CURRENT.md keeps every superseded status sentence
VERBATIM inside an italic `*(...)*` parenthetical (the convention CURRENT.md itself cites as
"REPLACED rather than deleted"), which is why the superseded phrases still appear in the tree at all. A phrase INSIDE
such a parenthetical is history and is allowed; the SAME phrase OUTSIDE one is a live claim and
fails. The controls below prove the guard fires on the live form and stays silent on the historical
form — so it is neither vacuous nor a blunt substring scan that would fire on the preserved history.

Authority: `IMPLEMENTATION-REGISTRY.yaml` unit P8 criterion `P8-AC-16`
(status_honesty_and_reconcilability) and `meta.status_model`; CLAUDE.md §13. This guard scores
nothing and moves no status: it reads the registry and holds the prose to it.
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

# The two P8 lifecycle triples this guard recognises (status / execution_state / checkpoint_state).
# meta.status_model's invariant is `status COMPLETE <=> execution_state COMPLETE <=> checkpoint_state
# PHASE_ACCEPTANCE_COMPLETE`, so a half-flipped triple is neither of these and fails.
PENDING, ACCEPTED = "PENDING", "ACCEPTED"
_PENDING_TRIPLE = ("READY", "NOT_STARTED", "NO_CHECKPOINT")
_ACCEPTED_TRIPLE = ("COMPLETE", "COMPLETE", "PHASE_ACCEPTANCE_COMPLETE")
_UNBLOCKED = {"READY", "IN_PROGRESS", "COMPLETE"}


def _normalize(s: str) -> str:
    """Drop the code-span backticks and fold en/em dashes to '-', so `U8.2`–`U8.6` and U8.2-U8.6
    read as the same tokens a human reader sees."""
    return s.replace("`", "").replace("–", "-").replace("—", "-")


def _p8_row_of(text: str) -> str:
    """The single Program-position table ROW whose first bold cell is **P8**, out of a CURRENT.md
    text. Discovered by its leading token, never line-numbered."""
    rows = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("| **P8**")]
    assert len(rows) == 1, f"expected exactly one **P8** program-position row, found {len(rows)}"
    return rows[0]


def _p8_prose_cell() -> str:
    """The human-readable current-state prose P8-AC-16 governs, read from the tree on disk."""
    return _p8_row_of(CURRENT.read_text(encoding="utf-8"))


def _live_region(cell: str) -> str:
    """The cell with every `*(...)*` superseded-text parenthetical blanked out."""
    return _HIST_PAREN.sub(" ", cell)


def _inject_live(cell: str, sentence: str) -> str:
    """`cell` with `sentence` inserted as LIVE prose: immediately before the cell's FIRST `*(...)*`
    superseded-text parenthetical, so it sits outside every one of them in either lifecycle state.
    Anchored on the structure of the cell, not on a phrase that an acceptance rewrites."""
    at = cell.find("*(")
    assert at > 0, "the P8 cell carries no superseded-text parenthetical to anchor a live injection"
    return cell[:at] + sentence + " " + cell[at:]


def obsolete_live_p8_claims(cell: str) -> list[str]:
    """Every OFFENDING live claim in a P8 prose cell — false in EITHER lifecycle state:
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
    substantial cell and not an empty/mismatched one), and asserts NEITHER forbidden live claim.
    Lifecycle-independent: both claims are false whether P8 is pending or accepted."""
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
    live_not_started = _inject_live(cell, "`U8.2`–`U8.6` are NOT STARTED.")
    assert live_not_started != cell, "control setup failed — the live injection changed nothing"
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
# Renamed at the P8 phase acceptance from `..._are_reconciled_and_imply_no_acceptance`: that name
# stated the pre-acceptance half only, and would have been false of an accepted P8.
_GUARD_SURFACES = "test_all_p8_status_surfaces_agree_with_the_registry_lifecycle"
_GUARD_MACHINE = "test_p8_ac16_prose_reconciles_with_the_canonical_machine_authorities"

# Affirmative "this phase is done" predicates. 'is COMPLETE' / 'is now ACCEPTED' /
# PHASE_ACCEPTANCE_COMPLETE / a 17/17 criteria tally are forbidden as LIVE claims about a PENDING P8
# and REQUIRED of the CURRENT.md cell once P8 is ACCEPTED. The negated 'is not COMPLETE' cannot match:
# 'not' breaks the 'is (now) COMPLETE' contiguity, so this predicate needs no separate negation pass
# and cannot be fooled by a distant sibling negation.
_ACCEPTED_COMPLETE = re.compile(
    r"\bis\s+(?:now\s+)?(?:COMPLETE|ACCEPTED)\b"
    r"|PHASE_ACCEPTANCE_COMPLETE"
    r"|\b17\s*/\s*17\b",
    re.I,
)

# The mirror image: affirmative "this phase has NOT started / is NOT accepted" predicates, forbidden
# as LIVE claims about an ACCEPTED P8. The `\**` admits the bold markers CURRENT.md puts round 'not'
# ("is **not** COMPLETE"). 'ACCEPTED IS NOT ENABLED' cannot match: the predicate needs 'is not'
# followed by COMPLETE/ACCEPTED, so the ships-dark sentence is never read as a pending claim.
_STILL_PENDING = re.compile(
    r"NOT[ _]STARTED"
    r"|NO_CHECKPOINT"
    r"|\bis\s+\**not\**\s+(?:yet\s+)?(?:COMPLETE|ACCEPTED)\b"
    r"|\bNOTHING\s+IS\s+SCORED\b",
    re.I,
)


def implies_accepted_or_complete(region: str) -> list[str]:
    """Every affirmative LIVE claim that P8 is ACCEPTED / COMPLETE / scored, in the region's live
    text (superseded *(...)* history exempt)."""
    live = _normalize(_live_region(region))
    return [m.group(0) for m in _ACCEPTED_COMPLETE.finditer(live)]


def implies_still_pending(region: str) -> list[str]:
    """Every affirmative LIVE claim that P8 is still NOT STARTED / unaccepted / unscored, in the
    region's live text (superseded *(...)* history exempt)."""
    live = _normalize(_live_region(region))
    return [m.group(0) for m in _STILL_PENDING.finditer(live)]


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


def _registry_units() -> list[dict]:
    return yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))["units"]


def _registry_phase_status() -> dict[str, tuple[str, str, str]]:
    """Every top-level phase unit (`unit_id` = `Pn`) mapped to its lifecycle triple — the MACHINE
    authority the human prose must agree with."""
    phase = re.compile(r"P\d+")
    out: dict[str, tuple[str, str, str]] = {}
    for u in _registry_units():
        uid = str(u.get("unit_id", ""))
        if phase.fullmatch(uid):
            out[uid] = (str(u["status"]), str(u["execution_state"]), str(u["checkpoint_state"]))
    return out


def lifecycle_of(status: dict) -> str:
    """Which of the TWO recognised lifecycle states the registry records for P8. Read from the machine
    authority and from nothing else — the prose never gets to choose which branch it is held to. Any
    other triple (a half-flipped acceptance, an off-vocabulary value) is neither, and fails."""
    triple = status.get("P8")
    if triple == _PENDING_TRIPLE:
        return PENDING
    if triple == _ACCEPTED_TRIPLE:
        return ACCEPTED
    raise AssertionError(
        f"registry P8 lifecycle is neither pending {_PENDING_TRIPLE} nor accepted {_ACCEPTED_TRIPLE}: "
        f"{triple} — a mixed or half-flipped triple is not a state this repository records")


def _assert_registry_lifecycle(status: dict) -> str:
    """The registry projection is internally consistent with P8's lifecycle, and returns it.

      * PENDING  — every later phase is BLOCKED (nothing is unlocked ahead of the acceptance).
      * ACCEPTED — P9 has taken the selector (it is no longer BLOCKED): meta.status_model.status
        forbids vacating READY without a successor in the same commit.
      * In BOTH — no phase after P8 is unblocked while its predecessor is not COMPLETE. Stated as
        that rule rather than as "P10–P14 are BLOCKED", so this guard does not itself deadlock the
        NEXT acceptance the way its pre-acceptance form deadlocked this one.

    Shared by the guard and its in-process control so the cross-check's discrimination is proven."""
    lifecycle = lifecycle_of(status)
    later = sorted((p for p in status if int(p[1:]) > 8), key=lambda p: int(p[1:]))
    assert later, "no phase after P8 in the projection — the successor check would be vacuous"
    for p in later:
        prev = f"P{int(p[1:]) - 1}"
        assert prev in status, f"registry projection is missing {prev}, the predecessor of {p}"
        if status[prev][0] != "COMPLETE":
            assert status[p][0] == "BLOCKED", (
                f"registry {p} is {status[p][0]} while its predecessor {prev} is not COMPLETE "
                f"({status[prev][0]}) — a phase was unlocked ahead of its predecessor's acceptance")
    if lifecycle == ACCEPTED:
        assert status["P9"][0] in _UNBLOCKED, (
            f"registry P8 is accepted but P9 is {status['P9'][0]} — the selector was vacated without "
            "a successor")
    return lifecycle


def _assert_phase_outputs_heading(heading: str, lifecycle: str) -> None:
    """The PHASE-OUTPUTS P8 heading token is the repo's own status vocabulary and mirrors the
    registry's execution_state: NOT STARTED while pending, COMPLETE once accepted, never the other."""
    assert "IN PROGRESS" not in heading, f"PHASE-OUTPUTS P8 heading implies progress: {heading}"
    if lifecycle == PENDING:
        assert "NOT STARTED" in heading, f"PHASE-OUTPUTS P8 heading lost its NOT STARTED token: {heading}"
        assert "✅ COMPLETE" not in heading, f"PHASE-OUTPUTS P8 heading implies acceptance: {heading}"
    else:
        assert "✅ COMPLETE" in heading, (
            f"PHASE-OUTPUTS P8 heading does not record the accepted phase as COMPLETE: {heading}")
        assert "NOT STARTED" not in heading, (
            f"PHASE-OUTPUTS P8 heading still says NOT STARTED after acceptance: {heading}")


def _assert_prose_ships_dark(live: str) -> None:
    """The ships-dark posture, required of CURRENT.md's live P8 prose in BOTH lifecycle states:
    accepted is not enabled, so acceptance must not be allowed to drop these sentences."""
    low = live.lower()
    assert "ships dark" in low, "CURRENT.md P8 prose no longer states the ship-dark posture"
    assert "no external effect" in low, "CURRENT.md P8 prose no longer states that no external effect is enabled"
    assert "no autonomy" in low, "CURRENT.md P8 prose no longer states that no autonomy is enabled"


def _assert_registry_ships_dark(unit: dict) -> None:
    """The machine side of the same posture, in BOTH lifecycle states: P8's readiness tier is
    LOCALLY_IMPLEMENTED and no higher (ADR-016 §3 — "code exists" only), and its rollback posture is
    dark. Phase acceptance moves the lifecycle fields; it never promotes the readiness tier."""
    tier = str((unit.get("rebaseline_contract") or {}).get("readiness_target"))
    assert tier == "LOCALLY_IMPLEMENTED", (
        f"registry P8 readiness_target is {tier!r}, not LOCALLY_IMPLEMENTED — acceptance must not "
        "promote the readiness tier or imply enablement")
    assert "dark" in str(unit.get("rollback_posture", "")).lower(), (
        f"registry P8 rollback_posture no longer ships dark: {unit.get('rollback_posture')!r}")


def _p8_unit() -> dict:
    unit = next((u for u in _registry_units() if str(u.get("unit_id")) == "P8"), None)
    assert unit is not None, "unit P8 not found in the registry"
    return unit


def test_all_p8_status_surfaces_agree_with_the_registry_lifecycle():
    """GUARD (broadened, lifecycle-aware). Every human-readable P8 status surface — CURRENT.md,
    PHASE-OUTPUTS.md, pr-sequence.md — is free of an obsolete live P8 unit claim AND agrees with the
    lifecycle the REGISTRY records for P8:

      * PENDING  — no surface implies accepted/COMPLETE/scored; the PHASE-OUTPUTS heading reads
        NOT STARTED; CURRENT.md states the READY / NOT_STARTED / NO_CHECKPOINT enum.
      * ACCEPTED — no surface still claims NOT STARTED / unaccepted / unscored; the PHASE-OUTPUTS
        heading reads COMPLETE; CURRENT.md states the acceptance and no longer the pending enum.

    In BOTH: the ships-dark posture is stated in the prose and held in the registry. The live/history
    split is preserved: superseded text inside *(...)* is exempt everywhere."""
    current = _p8_prose_cell()
    po_section, po_heading = _phase_outputs_p8_section()
    pr_line = _pr_sequence_p8_line()

    # machine authority first: the lifecycle every surface below is held to.
    lifecycle = _assert_registry_lifecycle(_registry_phase_status())

    # FIXED-SPECIFICATION: NOT a discovered population — the exact, bounded set of human P8
    # status/roadmap surfaces this AC-16 verification reconciles, each region already extracted above.
    surfaces = {"CURRENT.md": current, "PHASE-OUTPUTS.md": po_section, "pr-sequence.md": pr_line}
    for name, region in surfaces.items():
        assert _normalize(_live_region(region)).strip(), f"{name}: the P8 region parsed empty"
        assert obsolete_live_p8_claims(region) == [], (
            f"{name} carries an obsolete live P8 unit claim: {obsolete_live_p8_claims(region)}")
        if lifecycle == PENDING:
            assert implies_accepted_or_complete(region) == [], (
                f"{name} implies P8 accepted/COMPLETE/scored (live) while the registry records it "
                f"pending: {implies_accepted_or_complete(region)}")
        else:
            assert implies_still_pending(region) == [], (
                f"{name} still claims P8 is not started/unaccepted (live) while the registry records "
                f"it accepted: {implies_still_pending(region)}")

    _assert_phase_outputs_heading(po_heading, lifecycle)

    # the human narrative agreeing with the machine authority.
    live = _normalize(_live_region(current))
    if lifecycle == PENDING:
        for token in _PENDING_TRIPLE:
            assert token in live, f"CURRENT.md P8 prose no longer states the {token} lifecycle enum"
    else:
        assert "PHASE_ACCEPTANCE_COMPLETE" in live and implies_accepted_or_complete(current), (
            "CURRENT.md P8 prose does not state the acceptance the registry records")
        assert not re.search(r"\bREADY\b", live), (
            "CURRENT.md P8 prose still states the READY selector enum after acceptance")

    # ships dark / no live effects / no autonomy — in BOTH states, prose and registry.
    _assert_prose_ships_dark(live)
    _assert_registry_ships_dark(_p8_unit())


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
    crit = next((c for c in _p8_unit().get("acceptance_criteria", []) if str(c.get("id")) == "P8-AC-16"), None)
    assert crit is not None, "P8-AC-16 criterion not found under unit P8 in the registry"
    return crit


def _assert_ac16_criterion(crit: dict, lifecycle: str) -> None:
    """P8-AC-16 is the status-honesty criterion, is required, its own oracle names the status
    reconciliation surfaces, and its RESULT AGREES WITH THE PHASE LIFECYCLE: `PENDING` while P8 is
    pending (nothing is scored ahead of the acceptance), `PASS` with recorded adjudication evidence
    once P8 is accepted (a phase is not accepted over an unscored or unevidenced criterion). Shared
    by the guard and its in-process control."""
    assert lifecycle in (PENDING, ACCEPTED), f"unknown lifecycle {lifecycle!r}"
    assert crit.get("criterion") == "status_honesty_and_reconcilability", (
        f"P8-AC-16 is not the status-honesty criterion: {crit.get('criterion')!r}")
    assert crit.get("required") is True, "P8-AC-16 is no longer required"
    result = str(crit.get("result"))
    if lifecycle == PENDING:
        assert result == "PENDING", (
            f"P8-AC-16 must remain PENDING while P8 is pending (nothing is scored ahead of the "
            f"phase acceptance); found {result!r}")
    else:
        assert result == "PASS", (
            f"P8 is recorded accepted but P8-AC-16 is {result!r} — a phase is not accepted over an "
            "unscored required criterion")
        assert str(crit.get("adjudication_evidence") or "").strip(), (
            "P8-AC-16 is scored PASS with no adjudication_evidence — a result with no recorded "
            "basis is not an established PASS")
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

      * ac_16 — the P8-AC-16 criterion is read from the registry; it exists, is required, its own
        oracle names the reconciliation surfaces, and its result agrees with P8's lifecycle
        (PENDING while pending; PASS with recorded evidence once accepted).
      * event_contracts_data.json — the canonical event-corpus total is read (and proven internally
        self-consistent), and CURRENT.md's LIVE 'event contracts, measured: N' figure must EQUAL it.
        A prose figure that drifts from the machine source is exactly the status dishonesty this
        criterion forbids."""
    _assert_ac16_criterion(_p8_ac16_criterion(), lifecycle_of(_registry_phase_status()))

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


def _replace_once(find: str, repl: str):
    """A whole-file mutation: the first occurrence of `find` becomes `repl`."""
    def mutate(text: str) -> str:
        assert find in text, f"mutation anchor not found: {find!r}"
        return text.replace(find, repl, 1)
    return mutate


def _in_p8_cell(transform):
    """A mutation confined to CURRENT.md's P8 program-position row, so it can only ever change the
    prose this guard governs."""
    def mutate(text: str) -> str:
        cell = _p8_row_of(text)
        mutated = transform(cell)
        assert mutated != cell, "the P8-cell mutation changed nothing"
        assert cell in text, "the P8 row is not a verbatim line of CURRENT.md"
        return text.replace(cell, mutated, 1)
    return mutate


def _mutants(lifecycle: str, obsolete_node: str, surfaces_node: str, machine_node: str) -> list[tuple]:
    """The forbidden LIVE-claim shapes for the lifecycle the registry records, each as
    (file, mutation, guard node that must go RED, label).

    Five are false in EITHER state. Two are the lifecycle's own hostile case, and they are mirror
    images: under a PENDING registry the prose is made to claim acceptance; under an ACCEPTED registry
    the prose is made to claim it is still pending."""
    total = _canonical_event_contract_total()
    common = [
        (CURRENT, _in_p8_cell(lambda c: _inject_live(c, "`U8.2`–`U8.6` are NOT STARTED.")),
         obsolete_node, "CURRENT: later units NOT STARTED (live)"),
        (CURRENT, _in_p8_cell(lambda c: _inject_live(c, "Only `U8.1` is landed; the rest are not.")),
         obsolete_node, "CURRENT: only U8.1 landed (live)"),
        (PR_SEQUENCE, _replace_once("U8.2 ### **compile-or-refuse Rules**",
                                    "U8.2 ### **compile-or-refuse Rules** are NOT STARTED"),
         surfaces_node, "pr-sequence: U8.2 NOT STARTED (live)"),
        (CURRENT, _in_p8_cell(lambda c: c.replace("ships dark", "is live")),
         surfaces_node, "CURRENT: the ships-dark posture is dropped"),
        (CURRENT, _replace_once(f"event contracts, measured: {total}", "event contracts, measured: 999"),
         machine_node, "CURRENT: measured event-contract count contradicts event_contracts_data.json"),
    ]
    if lifecycle == PENDING:
        own = [
            (CURRENT, _in_p8_cell(lambda c: c.replace("and is **not** `COMPLETE`", "and is now `COMPLETE`", 1)),
             surfaces_node, "CURRENT: P8 is now COMPLETE (live) under a PENDING registry"),
            (PHASE_OUTPUTS, _replace_once("Compensation ⛔ NOT STARTED", "Compensation ✅ COMPLETE"),
             surfaces_node, "PHASE-OUTPUTS: P8 heading flipped to COMPLETE under a PENDING registry"),
        ]
    else:
        own = [
            (CURRENT, _in_p8_cell(lambda c: _inject_live(
                c, "P8 stays `READY` / `NOT_STARTED` / `NO_CHECKPOINT` and is **not** `COMPLETE`.")),
             surfaces_node, "CURRENT: P8 still pending (live) under an ACCEPTED registry"),
            (PHASE_OUTPUTS, _replace_once("Compensation ✅ COMPLETE", "Compensation ⛔ NOT STARTED"),
             surfaces_node, "PHASE-OUTPUTS: P8 heading flipped back to NOT STARTED under an ACCEPTED registry"),
        ]
    return common + own


def test_control_battery_drives_the_guards_red_on_each_reintroduced_claim_and_green_on_restore():
    """CONTROL — the discriminating mutation battery, bound to the guard NODE IDS. For each forbidden
    LIVE-claim shape it MUTATES THE REAL status document, runs the relevant guard by node id in a fresh
    process, and requires RED; then it restores the file from an in-memory copy (never git) and requires
    GREEN. A guard that stayed GREEN under a reintroduced claim would be a decorative oracle that proves
    nothing (Founder context §8). The battery is built for the lifecycle the registry records, so it
    discriminates in whichever state the tree is actually in."""
    obsolete_node = f"{_THIS}::{_GUARD_OBSOLETE}"
    surfaces_node = f"{_THIS}::{_GUARD_SURFACES}"
    machine_node = f"{_THIS}::{_GUARD_MACHINE}"

    assert _run_guard_node(obsolete_node) == 0, "positive control failed: obsolete-claim guard not GREEN"
    assert _run_guard_node(surfaces_node) == 0, "positive control failed: surfaces guard not GREEN"
    assert _run_guard_node(machine_node) == 0, "positive control failed: machine-authorities guard not GREEN"

    lifecycle = lifecycle_of(_registry_phase_status())
    mutants = _mutants(lifecycle, obsolete_node, surfaces_node, machine_node)
    assert len(mutants) >= 7, f"the mutation battery collapsed to {len(mutants)} mutants"

    caught = 0
    for path, mutate, node, label in mutants:
        original = path.read_bytes()
        try:
            text = original.decode("utf-8")
            mutated = mutate(text)
            assert mutated != text, f"mutation [{label}] changed nothing in {path.name}"
            path.write_text(mutated, encoding="utf-8")
            rc = _run_guard_node(node)
            assert rc != 0, f"NON-DISCRIMINATING: a guard stayed GREEN under mutation [{label}]"
            caught += 1
        finally:
            path.write_bytes(original)

    assert _run_guard_node(obsolete_node) == 0, "obsolete-claim guard not GREEN after restore"
    assert _run_guard_node(surfaces_node) == 0, "surfaces guard not GREEN after restore"
    assert _run_guard_node(machine_node) == 0, "machine-authorities guard not GREEN after restore"
    print(f"P8-AC-16 status-prose mutation battery ({lifecycle} lifecycle): {caught}/{len(mutants)} "
          "mutants drove a guard RED; 0 escaped; files restored from an in-memory copy.")
    assert caught == len(mutants)


def test_control_the_registry_cross_check_catches_a_mixed_or_out_of_order_projection():
    """CONTROL — proves the registry cross-check is discriminating in BOTH lifecycle states WITHOUT
    mutating the real registry. The two true projections pass and name their lifecycle; every mixed,
    half-flipped or out-of-order projection fails — so lifecycle-awareness opened exactly two states
    and no third."""
    blocked = ("BLOCKED", "NOT_STARTED", "NO_CHECKPOINT")
    selected = ("READY", "NOT_STARTED", "NO_CHECKPOINT")
    pending = {"P8": _PENDING_TRIPLE, **{f"P{n}": blocked for n in range(9, 15)}}
    accepted = dict(pending, P8=_ACCEPTED_TRIPLE, P9=selected)

    # the two true projections: must not raise, and must name the right lifecycle.
    assert _assert_registry_lifecycle(pending) == PENDING
    assert _assert_registry_lifecycle(accepted) == ACCEPTED

    hostile = {
        "half-flipped: status COMPLETE over an unmoved execution/checkpoint state":
            dict(pending, P8=("COMPLETE", "NOT_STARTED", "NO_CHECKPOINT")),
        "half-flipped: accepted checkpoint_state under a READY status":
            dict(pending, P8=("READY", "COMPLETE", "PHASE_ACCEPTANCE_COMPLETE")),
        "off-vocabulary P8 status":
            dict(pending, P8=("ACCEPTED", "COMPLETE", "PHASE_ACCEPTANCE_COMPLETE")),
        "P9 unblocked while P8 is still pending":
            dict(pending, P9=selected),
        "P8 accepted but the selector vacated (P9 still BLOCKED)":
            dict(accepted, P9=blocked),
        "P10 unblocked ahead of P9's acceptance":
            dict(accepted, P10=selected),
        "P8 missing from the projection":
            {k: v for k, v in pending.items() if k != "P8"},
    }
    for label, projection in hostile.items():
        with pytest.raises(AssertionError):
            _assert_registry_lifecycle(projection)
            pytest.fail(f"the registry cross-check accepted a hostile projection: {label}")

    # ...and it does not deadlock the NEXT acceptance: P9 accepted with P10 selected is a true
    # projection of an accepted P8 and must pass.
    next_accepted = dict(accepted, P9=_ACCEPTED_TRIPLE, P10=selected)
    assert _assert_registry_lifecycle(next_accepted) == ACCEPTED


def test_control_the_ac16_criterion_check_catches_a_result_that_disagrees_with_the_lifecycle():
    """CONTROL — proves the 'ac_16' side of the machine-authorities guard is discriminating without
    editing the registry, in BOTH lifecycle states: a P8-AC-16 scored ahead of the acceptance, left
    unscored under an accepted phase, scored with no evidence, made not-required, or whose oracle no
    longer names the reconciliation surfaces must fail; the two true criteria pass."""
    pending = {
        "id": "P8-AC-16",
        "criterion": "status_honesty_and_reconcilability",
        "required": True,
        "result": "PENDING",
        "oracle": "eval/tests/test_current_status_reconciliation.py (...); reconciliation of CURRENT.md and PHASE-OUTPUTS.md.",
    }
    accepted = dict(pending, result="PASS",
                    adjudication_evidence="Adjudicated PASS on <head>/<tree> by an independent session.")
    _assert_ac16_criterion(pending, PENDING)    # true pending criterion: must not raise
    _assert_ac16_criterion(accepted, ACCEPTED)  # true accepted criterion: must not raise

    hostile = [
        (dict(pending, result="PASS"), PENDING, "scored PASS while P8 is pending"),
        (accepted, PENDING, "scored and evidenced while P8 is pending"),
        (pending, ACCEPTED, "still PENDING under an accepted P8"),
        (dict(accepted, adjudication_evidence=""), ACCEPTED, "PASS with empty evidence"),
        ({k: v for k, v in accepted.items() if k != "adjudication_evidence"}, ACCEPTED, "PASS with no evidence field"),
        (dict(accepted, result="FAIL"), ACCEPTED, "FAIL under an accepted P8"),
        (dict(pending, required=False), PENDING, "not required (pending)"),
        (dict(accepted, required=False), ACCEPTED, "not required (accepted)"),
        (dict(pending, oracle="something that names no reconciliation surface"), PENDING, "oracle (pending)"),
        (dict(accepted, oracle="something that names no reconciliation surface"), ACCEPTED, "oracle (accepted)"),
        (accepted, "SOMETHING_ELSE", "an unknown lifecycle"),
    ]
    for crit, lifecycle, label in hostile:
        with pytest.raises(AssertionError):
            _assert_ac16_criterion(crit, lifecycle)
            pytest.fail(f"the ac_16 check accepted a hostile criterion: {label}")


def test_control_the_lifecycle_prose_predicates_and_dark_posture_checks_discriminate():
    """CONTROL — proves the pieces the ACCEPTED branch added are discriminating in-process: the
    'still pending' predicate fires on the pre-acceptance wording when it is LIVE and is silent on
    the same wording kept as history and on the ships-dark sentence; the heading check holds each
    lifecycle to its own token; and the dark-posture checks (prose and registry) fail when the
    posture is dropped or the readiness tier is promoted."""
    pending_wording = ("P8 stays `READY` / `NOT_STARTED` / `NO_CHECKPOINT` and is **not** `COMPLETE`. "
                       "**BUT P8 IS NOT ACCEPTED AND NOTHING IS SCORED.**")
    assert len(implies_still_pending(pending_wording)) >= 4, (
        f"the still-pending predicate missed the pre-acceptance wording: {implies_still_pending(pending_wording)}")
    assert implies_still_pending(f"all six units are landed. *({pending_wording})*") == [], (
        "the still-pending predicate fired on history inside `*(...)*`")
    accepted_wording = ("**COMPLETE** - **17/17** - COMPLETE / COMPLETE / PHASE_ACCEPTANCE_COMPLETE. "
                        "**ACCEPTED IS NOT ENABLED.** It ships dark: no external effect and no autonomy are enabled.")
    assert implies_still_pending(accepted_wording) == [], (
        f"the still-pending predicate fired on the accepted wording: {implies_still_pending(accepted_wording)}")
    assert implies_accepted_or_complete(accepted_wording), "the accepted predicate missed the accepted wording"
    assert implies_accepted_or_complete(pending_wording) == [], (
        "the accepted predicate fired on the pending wording — 'is not COMPLETE' must not match")

    pending_heading = "## P8 — Policy, Rule, Brake ⛔ NOT STARTED"
    accepted_heading = "## P8 — Policy, Rule, Brake ✅ COMPLETE"
    _assert_phase_outputs_heading(pending_heading, PENDING)
    _assert_phase_outputs_heading(accepted_heading, ACCEPTED)
    for heading, lifecycle in ((accepted_heading, PENDING), (pending_heading, ACCEPTED),
                               ("## P8 — Policy 🔄 IN PROGRESS — NOT COMPLETE", PENDING),
                               ("## P8 — Policy 🔄 IN PROGRESS — NOT COMPLETE", ACCEPTED)):
        with pytest.raises(AssertionError):
            _assert_phase_outputs_heading(heading, lifecycle)

    _assert_prose_ships_dark(accepted_wording)
    for dropped in ("ships dark", "no external effect", "no autonomy"):
        with pytest.raises(AssertionError):
            _assert_prose_ships_dark(accepted_wording.replace(dropped, "…"))

    dark = {"rollback_posture": "Ships dark.", "rebaseline_contract": {"readiness_target": "LOCALLY_IMPLEMENTED"}}
    _assert_registry_ships_dark(dark)
    _assert_registry_ships_dark(_p8_unit())  # the real unit, in whichever lifecycle state it is in
    for promoted in ("DEPLOYED", "PILOT_READY", "ENABLED", "PRODUCTION_READY", "PRODUCTION"):
        with pytest.raises(AssertionError):
            _assert_registry_ships_dark(dict(dark, rebaseline_contract={"readiness_target": promoted}))
    with pytest.raises(AssertionError):
        _assert_registry_ships_dark(dict(dark, rollback_posture="Live in production."))
    with pytest.raises(AssertionError):
        _assert_registry_ships_dark({"rollback_posture": "Ships dark."})  # no readiness tier at all
