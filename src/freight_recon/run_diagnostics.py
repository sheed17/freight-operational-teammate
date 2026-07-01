"""Understand WHY an agent run struggled — turn a step trace into a legible, structured diagnosis.

This is the first brick of the learning loop Rasheed asked for: instead of a run just saying "did not
finish within 20 steps," we read the actual actions and name the failure — which targets it couldn't
interact with, where it dead-ended (404s), whether it exhausted its budget — and suggest the internal
fix. That makes failures measurable (evals), fixable (actuator/recipe work), and learnable (the same
wall isn't hit twice). Deterministic and pure: it reads the step list the agent already recorded.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

_DEAD_END_RE = re.compile(r"\b404\b|not found|does not exist", re.IGNORECASE)


@dataclass
class RunDiagnosis:
    outcome: str
    summary: str                                  # one-line human "why"
    repeated_failures: list[dict] = field(default_factory=list)  # [{action,target,count}]
    dead_ends: list[str] = field(default_factory=list)           # e.g. a guessed URL that 404'd
    exhausted_steps: bool = False
    suggested_fixes: list[str] = field(default_factory=list)     # what to fix internally

    def is_clean(self) -> bool:
        return self.outcome == "DONE" and not self.repeated_failures and not self.dead_ends


def diagnose_run(steps: list[dict], *, status: str, note: str = "") -> RunDiagnosis:
    """Diagnose a finished run from its recorded steps + final status/note."""
    steps = steps or []
    # 1) which interactions the agent tried but that FAILED — grouped, the repeat ones are the blockers.
    failed = Counter()
    for st in steps:
        if st.get("ok") is False and st.get("action") in ("CLICK", "TYPE", "SELECT"):
            failed[(st.get("action"), _norm(st.get("target")))] += 1
    repeated = [
        {"action": a, "target": t, "count": c}
        for (a, t), c in failed.most_common()
        if c >= 2  # a one-off failure is noise; a repeated one is a real capability gap
    ]

    # 2) dead-ends: a navigation/observation that hit a 404 / missing record.
    dead_ends: list[str] = []
    for st in steps:
        blob = f"{st.get('why','')} {st.get('observed','')} {st.get('note','')}"
        if _DEAD_END_RE.search(blob):
            ref = st.get("target") or "a page"
            if ref not in dead_ends:
                dead_ends.append(str(ref)[:80])

    exhausted = status == "FAILED" and "within" in (note or "") and "step" in (note or "")

    fixes = _suggest_fixes(repeated, dead_ends, exhausted, status)
    summary = _summarize(status, repeated, dead_ends, exhausted, note)
    return RunDiagnosis(
        outcome=status, summary=summary, repeated_failures=repeated,
        dead_ends=dead_ends, exhausted_steps=exhausted, suggested_fixes=fixes,
    )


def render_diagnosis(diag: RunDiagnosis) -> str:
    """Owner-readable 'why it struggled' (for Slack / the audit trail)."""
    lines = [f"🔎 Why: {diag.summary}"]
    for rf in diag.repeated_failures:
        lines.append(f"  • couldn't {rf['action'].lower()} “{rf['target']}” ({rf['count']}× failed)")
    for de in diag.dead_ends:
        lines.append(f"  • dead-end: {de}")
    if diag.suggested_fixes:
        lines.append("Fix: " + "; ".join(diag.suggested_fixes))
    return "\n".join(lines)


# --- helpers ---------------------------------------------------------------------------------

def _norm(target) -> str:
    return " ".join(str(target or "").split())[:60]


def _suggest_fixes(repeated, dead_ends, exhausted, status) -> list[str]:
    fixes: list[str] = []
    for rf in repeated:
        tl = rf["target"].lower()
        if any(k in tl for k in ("search", "⌘", "cmd", "command")):
            fixes.append("teach the actuator to drive the command-palette/global search (⌘K)")
        elif rf["action"] == "CLICK":
            fixes.append(f"improve row/link click resolution (couldn't click “{rf['target']}”)")
        else:
            fixes.append(f"improve {rf['action'].lower()} handling for “{rf['target']}”")
    if dead_ends:
        fixes.append("resolve the real record id instead of guessing a URL (learn the id mapping)")
    if exhausted:
        fixes.append("crystallize a replayable recipe for this flow so it isn't re-explored each time")
    # de-dup preserving order
    seen: set[str] = set()
    return [f for f in fixes if not (f in seen or seen.add(f))]


def _summarize(status, repeated, dead_ends, exhausted, note) -> str:
    if status == "DONE" and not repeated and not dead_ends:
        return "completed cleanly."
    bits = []
    if repeated:
        tgt = repeated[0]["target"]
        bits.append(f"couldn't interact with “{tgt}”" + (f" (+{len(repeated)-1} more)" if len(repeated) > 1 else ""))
    if dead_ends:
        bits.append("hit a dead-end page (404)")
    if exhausted:
        bits.append("ran out of steps exploring (no learned path)")
    if not bits:
        bits.append(note or f"finished {status.lower()}")
    return "; ".join(bits) + "."
