"""Canonical Corpus Errata guards (2026-07-16).

Phase 0 found four propagated corpus defects. This file stops each from coming back:

  DEF-4  141 transitions declared vs 134 enumerated   -> corrected to 134
  DEF-5  92 emitted events declared vs 98 enumerated  -> corrected to 98
  DEF-6  "6 of 8" non-tenant-first tables             -> corrected to 7 of 8
  P0-F1  U0.3 placed at Phase 0                       -> DEFERRED_BY_DEPENDENCY, required at P8

The oracle throughout is EXACT SET EQUALITY. Counts are diagnostics. A count match with different
members must fail - because the defect being corrected was precisely a number that had drifted away
from the members it claimed to count, while every count-based check kept agreeing with it.
"""

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0 import manifest, schema_probe, spec_corpus
from phase0.sources import ACCEPTANCE, IMPLEMENTATION, SPECIFICATIONS

# Documents that are HISTORICAL EVIDENCE: they may keep the old totals, but only under a
# supersession note. Everything else is normative and must carry the corrected values.
HISTORICAL = {
    "state-machine-specification-review.md",
    "event-specification-review.md",
    "acceptance-specification-review.md",
    "phase-0-implementation-review.md",
    "implementation-planning-review.md",
    "canonical-corpus-errata-review.md",
    "phase-0-baseline-manifest.yaml",
}
# Occurrences of "141"/"92" that are DIFFERENT METRICS and must never be rewritten.
NONCANONICAL_METRIC = {
    "target-spec-revision-report.md",   # "141 named validating tests" - a test count, not transitions
}


# ---------------------------------------------------------------------------- ERRATA 3: tenant set

def test_tenant_offending_tables_exact_set_not_count():
    """REGRESSION 8: the tenant migration list must not contain only six of the seven."""
    tables, ev = schema_probe.tables()
    ev.require_population(minimum=8)
    enumerated = {t.name for t in tables if not t.canonical}
    registered = manifest.tables_not_tenant_first()
    assert enumerated == registered, (
        f"tenant-posture set drift.\n"
        f"  offending but unregistered: {sorted(enumerated - registered)}\n"
        f"  registered but not offending: {sorted(registered - enumerated)}"
    )
    assert len(enumerated) == 7, "diagnostic only - the set equality above is the oracle"


def test_u21_scope_names_all_seven_tables():
    """REGRESSION 9: every offending table must have a Phase-2 migration unit."""
    plan = (IMPLEMENTATION / "migration-plan.md").read_text(encoding="utf-8")
    assert "PART 7" in plan, "migration-plan.md PART 7 (the seven-table scope) is missing"
    for table in manifest.tables_not_tenant_first():
        assert f"`{table}`" in plan, f"{table} has no entry in U2.1's scope (migration-plan PART 7)"
        row = next((l for l in plan.split("\n") if f"`{table}`" in l and "U2.1" in l), None)
        assert row, f"{table} is named but has no U2.1 migration unit"


def test_the_already_canonical_table_is_not_in_u21_scope():
    """The control: don't migrate what is already right."""
    assert manifest.tables_tenant_first() == {"autonomous_run_counters"}
    assert "autonomous_run_counters" not in manifest.tables_not_tenant_first()


# A superseded value may be NAMED as the defect it was - the same rule that lets the planning review
# name AC-SEC-000. Naming a defect is not asserting it. The marker must be explicit and on the line.
SUPERSESSION_MARKERS = ("errata", "miscount", "superseded", "was 6/8", "was 141", "was 92",
                        "previously", "incorrect", "wrong")


def _names_the_defect(line: str) -> bool:
    return any(m in line.lower() for m in SUPERSESSION_MARKERS)


def test_no_normative_document_still_says_six_of_eight():
    """REGRESSION 14: a superseded total must not be treated as a current normative value."""
    offenders, scanned = [], 0
    for path in list(IMPLEMENTATION.glob("*.md")) + list(IMPLEMENTATION.glob("*.yaml")):
        if path.name in HISTORICAL:
            continue
        scanned += 1
        for i, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            if re.search(r"\b6\s*/\s*8\b|\b6 of 8\b|\b6 offending\b|\b6 tables\b|\bsix tables\b", line) and not _names_the_defect(line):
                offenders.append(f"{path.name}:{i}: {line.strip()[:70]}")
    assert scanned >= 8, f"only {scanned} normative documents scanned - a negative over too small a population proves nothing"
    assert not offenders, (
        "normative document(s) state the superseded 6/8 as if current:\n  " + "\n  ".join(offenders)
    )


# ------------------------------------------------------- ERRATA 1+2: no stale totals in normative docs

def test_no_normative_document_still_requires_141_transitions():
    """REGRESSION 12."""
    offenders, scanned = [], 0
    for root in (ACCEPTANCE, IMPLEMENTATION, SPECIFICATIONS):
        for path in root.rglob("*.md"):
            if path.name in HISTORICAL or path.name in NONCANONICAL_METRIC:
                continue
            scanned += 1
            for i, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
                if "141" in line and not _names_the_defect(line):
                    offenders.append(f"{path.relative_to(path.parents[2])}:{i}: {line.strip()[:70]}")
    assert scanned >= 20, f"only {scanned} normative documents scanned - a negative result over too small a population proves nothing"
    assert not offenders, "normative document(s) still cite 141 transitions:\n  " + "\n  ".join(offenders)


def test_no_normative_document_still_requires_92_emitted_events():
    """REGRESSION 13. Only checks EVENT-context 92s - CommandIntent's 92 hits are a different metric."""
    offenders, scanned = [], 0
    for root in (ACCEPTANCE, SPECIFICATIONS):
        for path in root.rglob("*.md"):
            if path.name in HISTORICAL or path.name in NONCANONICAL_METRIC:
                continue
            scanned += 1
            for i, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
                if not re.search(r"\b92\b", line):
                    continue
                if _names_the_defect(line):
                    continue
                if re.search(r"92\s*(states|hits|/\s*16)", line):     # different metrics
                    continue
                offenders.append(f"{path.name}:{i}: {line.strip()[:70]}")
    assert scanned >= 20, f"only {scanned} normative documents scanned - a negative result over too small a population proves nothing"
    assert not offenders, "normative document(s) still cite 92 emitted events:\n  " + "\n  ".join(offenders)


def test_the_noncanonical_141_metric_was_not_corrupted_by_the_errata():
    """A global find-and-replace would have broken this. It is a TEST count, not a transition count."""
    report = (SPECIFICATIONS.parent / "architecture" / "target-spec-revision-report.md").read_text()
    assert "141 named validating tests" in report, (
        "the errata pass corrupted an unrelated metric: '141 named validating tests' in the target "
        "spec revision report is a TEST count that coincidentally equals the wrong transition total."
    )


def test_the_noncanonical_92_metric_was_not_corrupted_by_the_errata():
    """'92 states' is a STATE count. Same trap, different number."""
    review = (SPECIFICATIONS / "state-machine-specification-review.md").read_text()
    assert "**92 states**" in review, (
        "the errata pass corrupted an unrelated metric: '92 states' is the state count, not the "
        "emitted-event count."
    )


# ------------------------------------------------------------------ historical records are preserved

def test_historical_records_keep_their_totals_under_a_supersession_note():
    """Do not falsify the review trail. Annotate it."""
    for name in ("state-machine-specification-review.md", "event-specification-review.md",
                 "acceptance-specification-review.md"):
        text = (SPECIFICATIONS / name).read_text(encoding="utf-8")
        assert "ERRATA — 2026-07-16" in text, f"{name}: historical total with no supersession note"
        assert "HISTORICAL EVIDENCE" in text, f"{name}: not marked non-normative"


def test_the_source_arithmetic_error_is_preserved_for_the_record():
    """The per-machine list that sums to 134 while declaring 141 is the error at its origin."""
    review = (SPECIFICATIONS / "state-machine-specification-review.md").read_text(encoding="utf-8")
    assert "14/25/13/11/8/11/7/8/7/9/7/9/5" in review
    assert "141 legal transitions" in review, "the historical claim was rewritten instead of annotated"
    assert sum([14, 25, 13, 11, 8, 11, 7, 8, 7, 9, 7, 9, 5]) == 134


# ----------------------------------------------------------------------- ERRATA 4: U0.3 placement

def test_u03_is_deferred_by_dependency_not_waived():
    """REGRESSION 10: U0.3 must never be marked complete during Phase 0."""
    assert manifest.expected_failures()["AC-CKPT-6-missing"] == (
        "DEFERRED_BY_DEPENDENCY - REQUIRED AT PHASE 8"
    )
    entry = next(f for f in manifest.load()["expected_acceptance_failures"]
                 if f["case"] == "AC-CKPT-6-missing")
    assert entry["green_at_phase"] == "P8"
    assert entry["accountable_unit"] == "U8.1"


def test_u03_phase0_obligation_is_recorded_and_bounded():
    pr = (IMPLEMENTATION / "pr-sequence.md").read_text(encoding="utf-8")
    assert "DEFERRED_BY_DEPENDENCY — REQUIRED AT PHASE 8" in pr
    assert "planned dependency, NOT a waiver" in pr
    for obligation in ("THE PHASE-0 OBLIGATION", "THE PHASE-8 COMPLETION OBLIGATION"):
        assert obligation in pr, f"{obligation} is not recorded"
    assert "FAIL if a zero-row runtime checker reports success" in pr
    assert "may NOT be marked implemented before P8" in pr


def test_u81_carries_the_phase8_completion_obligation():
    """REGRESSION 11: the Phase-8 owner must inherit the real check."""
    pr = (IMPLEMENTATION / "pr-sequence.md").read_text(encoding="utf-8")
    u81 = next(l for l in pr.split("\n") if l.startswith("**P8:**"))
    for required in ("reject null", "FAIL STARTUP", "non-zero evaluated count"):
        assert required in u81, f"U8.1 does not carry '{required}'"


def test_no_placeholder_policy_runtime_was_added_by_the_errata():
    """The errata pass must not smuggle in the very structures it deferred."""
    import freight_recon
    src = Path(freight_recon.__file__).parent
    for token in ("HUMAN_APPROVAL_REQUIRED", "AUTONOMOUS_WITHIN_CAPS",
                  "PERMANENT_HUMAN_ASSERTION_REQUIRED"):
        hits = [p.name for p in src.rglob("*.py") if token in p.read_text(encoding="utf-8")]
        assert not hits, f"placeholder policy runtime appeared during the errata pass: {token} in {hits}"
