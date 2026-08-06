"""Switch-consistency guards (U-REBASELINE-1B).

THE DEFECT THESE EXIST TO PREVENT. When a control transition lands, the *registry* and the
*derived* status flip correctly while **live guidance surfaces keep describing the pre-transition
state**. The independent artifact inspection found exactly that at HEAD 0da4f140: CURRENT.md's top
milestone, the registry and BUILD-STATUS.derived all correctly said "P3 is the sole READY unit",
while CLAUDE.md section 3, CURRENT.md's own "next approved work program" section, BUILD-STATUS's
authored snapshot, the authority map and the implementation index still said "U-REBASELINE-1 is
next, RB-24 is PENDING, P3 is BLOCKED". A fresh agent reads the stale surface first.

DESIGN RULES (from the correction brief, and from this repository's scars):
  - PARSED / STRUCTURED assertions and SCOPED section checks - never fragile global substring
    counts. A count of "how many times X appears" tells you nothing about which claim is live.
  - EXACT MEMBERSHIP / IDENTITY over count floors.
  - HISTORICAL review evidence is NEVER scanned as current authority (the family rule), and
    explicitly-labelled historical blocks inside a current document are exempt in place.
  - The single source of truth for "what is READY" is the REGISTRY; every other live surface is
    checked for AGREEMENT with it, so these guards keep working after the next transition.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eval"))
from control import inventory as inv  # noqa: E402

IMPL = ROOT / "docs" / "implementation"
CURRENT = IMPL / "CURRENT.md"
REGISTRY = IMPL / "IMPLEMENTATION-REGISTRY.yaml"
BUILD_STATUS = IMPL / "BUILD-STATUS.yaml"
CLAUDE = ROOT / "CLAUDE.md"
AUTHORITY_MAP = ROOT / "docs" / "CANONICAL-DOCUMENTS.md"
INDEX = IMPL / "registry.md"
REBASELINE_CONTRACT = IMPL / "U-REBASELINE-1-ACCEPTANCE.yaml"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def require_population(items, what: str):
    assert items, f"discovery produced an EMPTY population for {what} - this guard would pass vacuously"
    return items


def strip_historical(text: str) -> str:
    """Explicitly-labelled historical blocks may retain superseded claims IN PLACE. Everything
    outside them is live instruction.

    DELEGATED at the R-01/R-02 remediation to the one label-aware definition in
    `control.status_claims`. "Explicitly-labelled" is now enforced rather than asserted."""
    from control import status_claims

    return status_claims.strip_historical_blocks(text)


def units() -> list[dict]:
    return yaml.safe_load(read(REGISTRY))["units"]


def ready_units() -> list[str]:
    return [u["unit_id"] for u in units() if u["status"] == "READY"]


def completed_units() -> set[str]:
    return {u["unit_id"] for u in units() if u["status"] == "COMPLETE"}


def build_status() -> dict:
    return yaml.safe_load(read(BUILD_STATUS))


# ------------------------------------------------------------------ (1) CLAUDE.md agrees

def test_claude_status_section_agrees_with_the_registry_and_current():
    """(1) CLAUDE.md's current-status/next-unit section must not disagree with CURRENT.md and the
    registry. CLAUDE.md outranks every other instruction file, so a stale next-unit row there is
    the single most misleading line in the repository."""
    ready = ready_units()
    assert len(ready) == 1, f"exactly one unit may be READY; found {ready}"
    the_ready = ready[0]
    section = re.search(r"## 3\. Current status(.+?)\n## 4\.", read(CLAUDE), re.S)
    assert section, "CLAUDE.md has no '3. Current status' section"
    body = strip_historical(section.group(1))
    row = re.search(r"\|\s*\*\*Next approved unit\*\*\s*\|(.+?)\|\s*$", body, re.M | re.S)
    assert row, "CLAUDE.md section 3 has no 'Next approved unit' row"
    claim = row.group(1)
    assert re.search(rf"\b{re.escape(the_ready)}\b", claim), (
        f"CLAUDE.md's next approved unit does not name the registry's READY unit {the_ready!r}: "
        f"{claim.strip()[:160]}"
    )
    # and it must not name a COMPLETE unit as the next one
    stale = sorted(u for u in completed_units() if re.search(rf"\b{re.escape(u)}\b", claim))
    assert not stale, (
        f"CLAUDE.md's next-approved-unit row names COMPLETED unit(s) {stale} as next work"
    )


# ------------------------------------------------------------------ (2) CURRENT.md is internally consistent

def test_current_md_has_no_two_live_contradictory_next_unit_sections():
    """(2) CURRENT.md must not contain two live, contradictory 'next approved unit' /
    'must not begin' sections. Structural: we parse the LIVE headed sections (historical
    <details> blocks removed) and require every live next-work section to name the registry's
    READY unit and no COMPLETED unit."""
    text = strip_historical(read(CURRENT))
    the_ready = ready_units()[0]
    done = completed_units()

    # level-2 headings ONLY - "### " is a sub-heading INSIDE a section, and splitting on
    # it would decapitate the section body (caught by this guard's own first run).
    sections = re.split(r"^## (?!#)", text, flags=re.M)
    next_work = [s for s in sections
                 if re.match(r".*next approved work", s.split("\n", 1)[0], re.I)]
    require_population(next_work, "live 'next approved work' sections in CURRENT.md")
    assert len(next_work) == 1, (
        f"CURRENT.md has {len(next_work)} live 'next approved work' sections - two live "
        "next-unit sections is exactly the switch-consistency defect"
    )
    body = next_work[0]
    assert re.search(rf"\b{re.escape(the_ready)}\b", body), (
        f"CURRENT.md's live next-work section does not name the READY unit {the_ready!r}"
    )
    # a COMPLETED unit may be MENTIONED (as a closed gate) but never presented as the program
    heading = body.split("\n", 1)[0]
    named_done = sorted(u for u in done if re.search(rf"\b{re.escape(u)}\b", heading))
    assert not named_done, f"CURRENT.md's next-work heading names COMPLETED unit(s): {named_done}"

    must_not = [s for s in sections
                if re.match(r".*must NOT begin", s.split("\n", 1)[0], re.I)]
    assert len(must_not) <= 1, (
        f"CURRENT.md has {len(must_not)} live 'must NOT begin' sections - duplicates contradict"
    )
    if must_not:
        # the READY unit may not appear in the must-not-begin table: it is precisely what MAY begin
        # STRUCTURAL: only the row's SUBJECT (first cell = the thing being forbidden) matters.
        # A row may freely MENTION the READY unit in its reason cell ("P4 requires P3 COMPLETE",
        # "only completing P4 closes R-07, not P3") - that is not forbidding P3. Checking the whole
        # row flagged exactly those two true statements on this guard's first run.
        rows = [ln for ln in must_not[0].split("\n")
                if ln.strip().startswith("|") and not re.match(r"\s*\|[\s\-|]+\|\s*$", ln)]
        offending = []
        for ln in rows:
            cells = [c.strip() for c in ln.strip().strip("|").split("|")]
            if cells and re.search(rf"\b{re.escape(the_ready)}\b", cells[0]):
                offending.append(ln)
        assert not offending, (
            f"CURRENT.md forbids beginning the READY unit {the_ready!r}:\n  "
            + "\n  ".join(o.strip()[:140] for o in offending)
        )


# ------------------------------------------------------------------ (3)+(4) BUILD-STATUS agrees with itself

def test_build_status_snapshot_agrees_with_its_derived_block():
    """(3) The authored snapshot must not contradict the machine-derived block. BUILD-STATUS.yaml
    is classified CURRENT_STATUS, so a stale narrative here is a real status contradiction."""
    bs = build_status()
    derived, snap = bs["derived"], bs["snapshot"]
    ready = derived["single_ready_unit"]
    phase = derived["active_phase"]
    assert ready == ready_units()[0], (
        f"BUILD-STATUS.derived.single_ready_unit {ready!r} != registry READY {ready_units()!r}"
    )
    for field in ("active_work_unit", "next_approved_unit"):
        value = str(snap[field])
        assert re.search(rf"\b{re.escape(ready)}\b", value) or re.search(rf"\b{re.escape(phase)}\b", value), (
            f"BUILD-STATUS.snapshot.{field} disagrees with derived "
            f"(active_phase={phase}, single_ready_unit={ready}): {value[:140]}"
        )
        stale = sorted(u for u in completed_units() if re.search(rf"\b{re.escape(u)}\b", value))
        assert not stale, (
            f"BUILD-STATUS.snapshot.{field} names COMPLETED unit(s) {stale} as active/next work"
        )


def test_build_status_does_not_claim_an_independent_review_is_unstarted_once_it_exists():
    """(4) The snapshot may not DENY a preserved independent review that exists.

    P3 UPDATE (CLAUDE.md sec 5 rule 20). The original read `independent_review_status` as a single
    global fact and demanded the word COMPLETE once U-REBASELINE-1 closed. That field now has to
    carry two different truths at once: the GATE-level reviews (U-HANDOFF-2B,
    U-REBASELINE-REVIEW-1) are complete and preserved, while the PHASE-level review of P3 has not
    started at all. Under the old rule the only way to stay green was to imply P3 had been
    independently reviewed when it had not - the guard would have compelled the false claim it was
    written to prevent. So it now checks the direction that actually protects the reader:
    the closed reviews must still be acknowledged, and an unstarted one may be named honestly.
    """
    snap = build_status()["snapshot"]
    status = str(snap["independent_review_status"])
    report = IMPL / "u-rebaseline-review-1-independent-report.md"
    if report.exists() and "U-REBASELINE-1" in completed_units():
        assert re.search(r"U-REBASELINE-REVIEW-1|U-REBASELINE-1", status), (
            "BUILD-STATUS no longer acknowledges the preserved independent rebaseline report, "
            f"which exists on disk: {status[:160]}"
        )
        assert re.search(r"preserved|adjudicated|COMPLETE|closed", status, re.I), (
            "BUILD-STATUS must record the standing of the closed gate-level independent reviews: "
            f"{status[:160]}"
        )
        # An unstarted PHASE-level review may be stated plainly, but only about a unit the
        # registry agrees is incomplete - it may never be used to describe a COMPLETE unit.
        if re.search(r"NOT STARTED|not started|has not run|awaiting", status, re.I):
            named = {u for u in re.findall(r"\bP\d+\b", status)}
            assert named, (
                "BUILD-STATUS claims an independent review is unstarted without naming which "
                f"unit it means: {status[:160]}"
            )
            wrong = sorted(named & completed_units())
            assert not wrong, (
                f"BUILD-STATUS calls the independent review unstarted for COMPLETE unit(s) "
                f"{wrong}: {status[:160]}"
            )


# ------------------------------------------------------------------ (5) acceptance-oracle agreement

def test_authority_map_and_index_do_not_contradict_the_acceptance_oracle():
    """(5) The authority map and the implementation index may not describe RB-24 as PENDING while
    the acceptance oracle records PASS. Parsed from the oracle, not assumed."""
    contract = yaml.safe_load(read(REBASELINE_CONTRACT))
    results = {c["id"]: str(c["result"]).upper() for c in contract["criteria"]}
    require_population(results, "rebaseline acceptance criteria")
    passed = {k for k, v in results.items() if v == "PASS"}
    for surface in (AUTHORITY_MAP, INDEX):
        text = strip_historical(read(surface))
        for line in text.split("\n"):
            if "U-REBASELINE-1-ACCEPTANCE" not in line and "RB-24" not in line:
                continue
            for crit in re.findall(r"\bRB-\d{2}\b", line):
                if crit in passed and re.search(
                    rf"{crit}[^|\n]{{0,60}}\b(PENDING|pending)\b", line
                ):
                    raise AssertionError(
                        f"{surface.name} describes {crit} as PENDING while the acceptance oracle "
                        f"records {results[crit]}: {line.strip()[:160]}"
                    )
            # the "RB-01..RB-23 PASS, RB-24 PENDING" shorthand
            if re.search(r"RB-01\.\.(RB-)?23[^|\n]{0,40}PASS[^|\n]{0,40}RB-24[^|\n]{0,20}PENDING", line, re.I):
                if "RB-24" in passed:
                    raise AssertionError(
                        f"{surface.name} carries the superseded 'RB-24 PENDING' shorthand while "
                        f"the oracle records RB-24 {results['RB-24']}: {line.strip()[:160]}"
                    )


# ------------------------------------------------------------------ (6) completed units are not still "next"

def live_guidance_documents() -> list[str]:
    """The LIVE current-authority + auto-loaded population, DISCOVERED.

    Extracted so the completed-unit guard (6) and the selected-READY guard (7) provably range over
    the SAME corpus. When they were separate inline expressions, a document could be in one scan and
    not the other and nobody would see it.
    """
    reviews = set(inv.implementation_review_documents())
    docs = [d for d in inv.current_authority_documents() if d.endswith(".md")]
    # FIXED-SPECIFICATION: the five root control documents are a fixed architectural set (the same
    # set the authority map section 2 enumerates). They are AUGMENTED onto the DISCOVERED
    # current-authority population above - not a substitute for discovery; a new current-authority
    # document under docs/ still enters via inventory.current_authority_documents().
    docs += [f for f in inv.tracked_files()
             if f in {"PRODUCT.md", "ARCHITECTURE.md", "CLAUDE.md", "README.md", "AGENTS.md"}]
    docs += inv.agent_files() + inv.compatibility_agent_files()
    return require_population(sorted(set(docs) - reviews), "live current-authority documents")


def _live_text(rel: str) -> str:
    """Historical blocks removed, then whitespace NORMALISED.

    ADJ-01, half two. The stale AGENTS.md sentence read `P4 (adapter\\ncontainment) is the sole
    READY unit` - the unit token and the claim sat on different lines, so every `[^\\n]{0,N}` window
    in this file walked straight past it. A guard that a line wrap defeats is not a guard, and the
    corpus is hard-wrapped prose. Newlines are therefore collapsed to single spaces BEFORE matching;
    line numbers are reported against the original text separately.
    """
    return re.sub(r"\s+", " ", strip_historical((ROOT / rel).read_text(encoding="utf-8")))


# ADJ-01. The completed-unit guard's docstring claimed "a COMPLETE unit may not still be described
# as READY", its population DID reach ARCHITECTURE.md and AGENTS.md, and both files described the
# COMPLETE P4 as READY - yet it passed. It matched only `the (single|one and only) READY unit`,
# while the corpus said `READY *(selected)*`, `the sole READY unit` and `IN PROGRESS, NOT COMPLETE`.
# The population was never the problem; the alternation was. Broadened here.
#
# F-04 CORRECTED AT THE REPLACEMENT CANDIDATE: this comment used to end "and never narrowed: every
# phrasing the original matched still matches." That was not true - see the docstring of
# test_no_completed_unit_is_described_as_ready_or_pending_in_live_guidance below for the exact
# bound change, the two constructions it stopped matching, and why the trade is deliberate.
_READY_SELECTOR = r"(?:sole|single|selected|one and only|only|next)"
_STALE_READY_PATTERNS = (
    (r"the\s+{sel}\s+`?READY`?\s+unit", "called the READY unit"),
    (r"`?READY`?\s+\*?\(?{sel}\)?\*?", "marked READY (selected)"),
    (r"is\s+the\s+{sel}\s+`?READY`?\b", "called the READY unit"),
    (r"`?READY`?\s+unit[^.]{{0,30}}\b{sel}\b", "called the READY unit"),
)


def test_no_completed_unit_is_described_as_ready_or_pending_in_live_guidance():
    """(6) A COMPLETE unit may not still be described as READY / awaiting review / next work in any
    LIVE current-authority or auto-loaded surface. Historical review documents are excluded by the
    family rule - they are evidence, and rewriting them would destroy the audit trail.

    STRENGTHENED for ADJ-01 (the targeted adjudication of `42ea24c`): the READY-selection
    alternation now reaches the constructions the corpus actually uses, and matching happens over
    whitespace-normalised text so a hard line wrap can no longer hide a claim.

    F-04 CORRECTED AT THE REPLACEMENT CANDIDATE - THIS DOCSTRING WAS NOT ACCURATE. It claimed all
    four original patterns survived "verbatim" and that nothing was ever narrowed. The targeted
    review disproved that: the second pattern's bound changed from `[^\\n]{0,80}` to `[^.]{0,80}`.
    That is a large NET improvement - it fixed the line-wrap blindness that was the actual defect -
    but it is not a pure widening. A sentence boundary between the unit token and the claim now
    stops the match, so these no longer match where the original did:

        "P4 v1.0 status: the single READY unit"
        "P4 (see sec. 3) is the single READY unit"

    while this now matches where the original did not:

        "P4 (adapter\\ncontainment) is the single READY unit"

    No live occurrence of the regressed class exists in the current corpus, and the trade is
    deliberate: once matching runs over whitespace-normalised text, `[^\\n]` bounds nothing at all,
    so `[^.]` is what keeps a match inside a single sentence. The defect corrected here is the
    inaccurate CLAIM in a docstring that is itself audit evidence - not the bound.
    """
    done = require_population(sorted(completed_units()), "completed units")
    docs = live_guidance_documents()

    offenders = []
    for rel in docs:
        raw = strip_historical((ROOT / rel).read_text(encoding="utf-8"))
        flat = _live_text(rel)
        for unit in done:
            u = re.escape(unit)
            pats = [
                # --- the four ORIGINAL patterns, unchanged in meaning ---
                (rf"[Nn]ext approved (?:unit|work|program)[^.]{{0,140}}\b{u}\b", "named as next approved work"),
                (rf"\b{u}\b[^.]{{0,80}}\bthe (?:single|one and only) READY unit", "called the READY unit"),
                (rf"\b{u}\b[^.]{{0,60}}awaiting (?:the )?independent", "described as awaiting review"),
                (rf"BLOCKED[^.]{{0,40}}behind[^.]{{0,30}}\b{u}\b", "still blocking later phases"),
                # --- ADJ-01 additions: the phrasings that escaped ---
                (rf"\b{u}\b[^.]{{0,80}}IN PROGRESS,? NOT COMPLETE", "described as in progress / not complete"),
                (rf"\b{u}\b[^.]{{0,80}}\bis\s+(?:still\s+)?(?:executing|in progress)\b", "described as executing"),
            ]
            pats += [
                (rf"\b{u}\b[^.]{{0,80}}" + tpl.format(sel=_READY_SELECTOR), label)
                for tpl, label in _STALE_READY_PATTERNS
            ]
            for pat, label in pats:
                for m in re.finditer(pat, flat, re.I):
                    # locate a line number in the ORIGINAL text for a usable report
                    probe = m.group(0)[:40]
                    idx = raw.find(probe.split("  ")[0][:30])
                    ln = raw[: idx].count("\n") + 1 if idx >= 0 else 0
                    offenders.append(f"{rel}:{ln}: COMPLETED {unit} {label}: {m.group(0)[:110]}")
    assert not offenders, (
        "COMPLETED units still described as live/unfinished work in current guidance "
        "(the switch-consistency defect):\n  " + "\n  ".join(offenders)
    )


# ------------------------------------------------------------------ (7) the READY unit is REACHED

# A unit token: a phase id (P0..P14) or a named control unit (U-HANDOFF-1, U-REBASELINE-1, U4.9...).
_UNIT_TOKEN = re.compile(r"\b(P\d{1,2}|U-[A-Z0-9-]+\d|U\d+(?:\.\d+)?)\b")
# The SELECTED-READY construction itself, independent of which unit it names.
_READY_CONSTRUCTION = re.compile(
    r"(?:the\s+(?:sole|single|one and only|selected|only)\s+`?READY`?(?:\s+unit)?"
    r"|`?READY`?\s+\*?\(\s*selected\s*\)\*?"
    r"|is\s+the\s+(?:sole|single|one and only|selected|only)\s+`?READY`?\b"
    r"|`?READY`?\s+unit[^.]{0,20}\b(?:sole|single|one and only|selected|only)\b)",
    re.I,
)


def test_the_selected_ready_unit_construction_is_present_singular_and_matches_the_registry():
    """(7) ADJ-01, the half the old guard never had: a POSITIVE check that the selected-READY claim
    exists at all, is singular, and names the unit the registry actually holds READY.

    The completed-unit guard (6) is purely NEGATIVE - it can only fire on a unit that is COMPLETE.
    That is why the `42ea24c` defect survived it in a second way: had `ARCHITECTURE.md` simply
    *deleted* its P4 row instead of leaving it stale, guard (6) would have gone quiet and the
    repository would have carried no live statement of which unit is READY at all. Silence would
    have read as compliance.

    So this guard requires the construction to be REACHED and CORRECT:

      * the registry must hold EXACTLY ONE READY unit (the invariant, restated and preserved);
      * the DISCOVERED live corpus must be non-empty and must actually CONTAIN the selected-READY
        construction - absence FAILS rather than passes;
      * every unit the construction attributes must be that same unit - a disagreement FAILS;
      * two different attributed units FAIL, even if the registry itself still says one;
      * the derived surface (`BUILD-STATUS.derived.single_ready_unit`) must agree too.

    It is deliberately NOT hard-coded to P5. Everything is derived from the registry, so the guard
    keeps working - and keeps failing correctly - at the next transition. Matching is
    whole-construction and unit-token-anchored, never a bare substring.
    """
    ready = ready_units()
    assert len(ready) == 1, f"exactly one unit may be READY; the registry holds {ready}"
    the_ready = ready[0]
    assert the_ready in {u["unit_id"] for u in units()}, "the READY id is not a registry unit"

    docs = live_guidance_documents()
    attributed: dict[str, list[str]] = {}
    carriers: list[str] = []
    for rel in docs:
        flat = _live_text(rel)
        found_here = False
        # A PROGRAM RANGE names a span, not a selection. `Phases P0-P14` sitting before "the single
        # READY unit" in an agent's description would otherwise attribute the claim to P14 - a false
        # positive found by this guard's own first run. Ranges are blanked (length-preserving) so
        # offsets stay valid; a construction with no unit token left near it is simply not a claim
        # about any unit, and is skipped rather than guessed at.
        flat = re.sub(r"\bP\d{1,2}\s*[-–—]\s*P\d{1,2}\b", lambda m: " " * len(m.group(0)), flat)
        for m in _READY_CONSTRUCTION.finditer(flat):
            # the unit this construction is ABOUT: the nearest unit token in the 140 chars before
            # it, else the nearest in the 120 chars after. Anchored on a token, never a substring.
            before = _UNIT_TOKEN.findall(flat[max(0, m.start() - 140): m.start()])
            after = _UNIT_TOKEN.findall(flat[m.end(): m.end() + 120])
            unit = (before[-1] if before else (after[0] if after else None))
            if unit is None:
                continue
            found_here = True
            attributed.setdefault(unit, []).append(f"{rel}: {m.group(0)[:60]!r}")
        if found_here:
            carriers.append(rel)

    # POSITIVE ANCHOR: the construction must be present. An empty scan is a FAILURE, not a pass.
    assert carriers, (
        "no live current-authority document carries a selected-READY construction at all - the "
        "repository states nowhere which unit is READY. Silence is not compliance; this guard "
        f"scanned {len(docs)} documents and found none."
    )
    assert len(carriers) >= 3, (
        f"only {len(carriers)} live document(s) state which unit is READY ({carriers}) - the "
        "selected-READY claim has thinned to the point where losing one file would erase it"
    )

    # EXACT AGREEMENT: one attributed unit, and it is the registry's.
    wrong = {u: where for u, where in attributed.items() if u != the_ready}
    assert not wrong, (
        f"live guidance attributes the selected READY unit to {sorted(wrong)} while the registry "
        f"holds {the_ready!r} READY:\n  " + "\n  ".join(w for ws in wrong.values() for w in ws)
    )
    assert set(attributed) == {the_ready}, (
        f"the selected-READY construction resolves to {sorted(attributed)}, not exactly "
        f"{{{the_ready!r}}}"
    )

    # and the DERIVED surface must not disagree with the prose or the registry
    derived = build_status()["derived"]["single_ready_unit"]
    assert derived == the_ready, (
        f"BUILD-STATUS.derived.single_ready_unit is {derived!r} but the registry holds "
        f"{the_ready!r} READY"
    )
