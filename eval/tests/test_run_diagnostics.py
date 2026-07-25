"""Tests for run diagnostics: turn a step trace into a legible 'why + fix'."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.run_diagnostics import diagnose_run, render_diagnosis  # noqa: E402


def test_diagnoses_the_real_carrier_payable_failure():
    # A trace shaped like the live transporters.io run: repeated row-click + search failures, a 404,
    # then step exhaustion.
    steps = [
        {"action": "CLICK", "target": "View Orders", "ok": True},
        {"action": "TYPE", "target": "filter[q]", "ok": True},
        {"action": "CLICK", "target": "LD-560001", "ok": False},
        {"action": "CLICK", "target": "LD-560001", "ok": False},
        {"action": "CLICK", "target": "LD-560001", "ok": False},
        {"action": "NAVIGATE", "target": "https://x/orders/1002", "ok": True,
         "why": "the current page is a 404 for the order URL"},
        {"action": "CLICK", "target": "Search orders, customers… ⌘K", "ok": False},
        {"action": "CLICK", "target": "Search orders, customers… ⌘K", "ok": False},
    ]
    d = diagnose_run(steps, status="FAILED", note="did not finish within 20 steps")
    assert d.outcome == "FAILED" and d.exhausted_steps
    # the row-click failure is caught as the top blocker
    top = d.repeated_failures[0]
    assert top["action"] == "CLICK" and "LD-560001" in top["target"] and top["count"] == 3
    # the search failures are caught too
    assert any("Search" in rf["target"] for rf in d.repeated_failures)
    assert d.dead_ends  # the 404
    fixes = " ".join(d.suggested_fixes).lower()
    assert "click resolution" in fixes and "command-palette" in fixes and "recipe" in fixes
    assert "id mapping" in fixes
    text = render_diagnosis(d)
    assert "Why:" in text and "3× failed" in text and "Fix:" in text


def test_one_off_failures_are_noise_not_blockers():
    steps = [
        {"action": "CLICK", "target": "Save", "ok": False},  # single failure -> not a blocker
        {"action": "CLICK", "target": "Save", "ok": True},
        {"action": "DONE", "target": "", "ok": True},
    ]
    d = diagnose_run(steps, status="DONE", note="done")
    assert d.repeated_failures == [] and d.is_clean()


def test_clean_run_reads_clean():
    steps = [{"action": "CLICK", "target": "Save", "ok": True}, {"action": "READ", "target": "inv", "ok": True}]
    d = diagnose_run(steps, status="DONE", note="invoice INV-1 created")
    assert d.is_clean() and "cleanly" in d.summary


def test_diagnosis_corpus_universal_failure_patterns():
    # A growing, TMS-agnostic eval: each scenario is a universal failure shape the engine must name +
    # suggest the right internal fix. Add rows here as new failure patterns show up in the wild.
    corpus = [
        ("row_click", [{"action": "CLICK", "target": "REC-9", "ok": False}] * 3, "FAILED",
         "did not finish within 20 steps", "click resolution"),
        ("palette_search", [{"action": "TYPE", "target": "Search… ⌘K", "ok": False}] * 2, "ESCALATED",
         "stuck", "command-palette"),
        ("dead_end_url", [{"action": "NAVIGATE", "target": "/x/1002", "ok": True, "why": "page is a 404"}],
         "FAILED", "did not finish within 20 steps", "id mapping"),
        ("exhausted", [{"action": "READ", "target": "x", "ok": True}] * 5, "FAILED",
         "did not finish within 20 steps", "recipe"),
    ]
    for name, steps, status, note, expected_fix in corpus:
        d = diagnose_run(steps, status=status, note=note)
        fixes = " ".join(d.suggested_fixes).lower()
        assert expected_fix in fixes, f"{name}: expected '{expected_fix}' in fixes, got {d.suggested_fixes}"


def test_agent_prompt_guards_against_guessing_urls():
    # The universal behavior fix: never NAVIGATE to a guessed record URL.
    from freight_recon.operator_agent import _decide_prompt

    p = _decide_prompt("open the record", {"url": "x"}, [])
    assert "guessed record URL" in p and "will 404" in p


def test_agent_prompt_covers_edge_cases_and_anti_hallucination():
    from freight_recon.operator_agent import _decide_prompt

    p = _decide_prompt("record a payable", {"url": "x"}, [])
    # fail-closed on every dangerous ambiguity
    for token in ("record not found", "already exists", "ambiguous", "blocked", "rejected"):
        assert token in p, f"missing edge-case guard: {token}"
    # anti-hallucination: only DONE after a readback; never invent
    assert "DO NOT HALLUCINATE" in p
    assert "Only report DONE AFTER you have READ the saved record back" in p
    assert "Never describe a record, number" in p


def test_diagnosis_names_missing_record_as_a_data_gap_not_an_engine_bug():
    # A "record not found" escalation is a data/precondition gap — the fix is for the owner, not the engine.
    d = diagnose_run([], status="ESCALATED", note="record not found: LD-560001")
    assert "isn't in this system" in d.summary
    assert any("data gap" in f for f in d.suggested_fixes)
    # and it is NOT blamed on click resolution / recipes
    assert not any("click resolution" in f or "recipe" in f for f in d.suggested_fixes)
