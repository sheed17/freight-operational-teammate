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
    outside them is live instruction."""
    return re.sub(r"<details>.*?</details>", "", text, flags=re.S)


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

def test_no_completed_unit_is_described_as_ready_or_pending_in_live_guidance():
    """(6) A COMPLETE unit may not still be described as READY / awaiting review / next work in any
    LIVE current-authority or auto-loaded surface. Historical review documents are excluded by the
    family rule - they are evidence, and rewriting them would destroy the audit trail."""
    done = require_population(sorted(completed_units()), "completed units")
    reviews = set(inv.implementation_review_documents())
    docs = [d for d in inv.current_authority_documents() if d.endswith(".md")]
    # FIXED-SPECIFICATION: the five root control documents are a fixed architectural set (the same
    # set the authority map section 2 enumerates). They are AUGMENTED onto the DISCOVERED
    # current-authority population above - not a substitute for discovery; a new current-authority
    # document under docs/ still enters via inventory.current_authority_documents().
    docs += [f for f in inv.tracked_files()
             if f in {"PRODUCT.md", "ARCHITECTURE.md", "CLAUDE.md", "README.md", "AGENTS.md"}]
    docs += inv.agent_files() + inv.compatibility_agent_files()
    docs = require_population(sorted(set(docs) - reviews), "live current-authority documents")

    # STALE PATTERNS: a completed unit presented as the live program or as unfinished.
    offenders = []
    for rel in docs:
        text = strip_historical((ROOT / rel).read_text(encoding="utf-8"))
        for unit in done:
            u = re.escape(unit)
            for pat, label in [
                (rf"[Nn]ext approved (?:unit|work|program)[^\n]{{0,140}}\b{u}\b", "named as next approved work"),
                (rf"\b{u}\b[^\n]{{0,80}}\bthe (?:single|one and only) READY unit", "called the READY unit"),
                (rf"\b{u}\b[^\n]{{0,60}}awaiting (?:the )?independent", "described as awaiting review"),
                (rf"BLOCKED[^\n]{{0,40}}behind[^\n]{{0,30}}\b{u}\b", "still blocking later phases"),
            ]:
                for m in re.finditer(pat, text):
                    ln = text[: m.start()].count("\n") + 1
                    offenders.append(f"{rel}:{ln}: COMPLETED {unit} {label}: {m.group(0)[:110]}")
    assert not offenders, (
        "COMPLETED units still described as live/unfinished work in current guidance "
        "(the switch-consistency defect):\n  " + "\n  ".join(offenders)
    )
