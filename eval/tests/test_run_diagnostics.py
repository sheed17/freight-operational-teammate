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
