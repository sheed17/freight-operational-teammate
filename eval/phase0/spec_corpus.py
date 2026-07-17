"""Parse the FROZEN specification corpus into counted records.

Rule (Phase-0 brief §9): do not duplicate the specifications inside the checker. Parse the canonical
registries. Where a count is only derivable by summing across files, sum the files — never trust a
headline number, and never let a headline number stand in for the rows.
"""

from __future__ import annotations

import re
from pathlib import Path

from .evaluation import Evaluation
from .markdown import clean, find_table, parse_tables
from .sources import SPECIFICATIONS, rel, require

MACHINES = SPECIFICATIONS / "state-machines"
EVENTS = SPECIFICATIONS / "events"
DOMAIN = SPECIFICATIONS / "domain-entities"
ADAPTERS = SPECIFICATIONS / "adapters"
WORKFLOWS = SPECIFICATIONS / "workflows"


def transitions() -> Evaluation:
    """Every enumerated transition row across the 13 machine files."""
    ev = Evaluation(name="spec.transitions")
    files = sorted(MACHINES.glob("*.machine.md"))
    if not files:
        raise FileNotFoundError(f"No machine files under {MACHINES}")
    for f in files:
        ev.sources_inspected.append(rel(f))
        tables = [t for t in parse_tables(f) if clean(t["headers"][0]) == "ID"]
        if not tables:
            ev.rejected.append(f"{f.name}: no transition table (header 'ID')")
            continue
        for t in tables:
            for row, ln in zip(t["rows"], t["line_nos"]):
                ev.candidates.append((f.name, ln))
                tid = clean(row[0])
                if not re.fullmatch(r"[A-Z]{2}-\d+[a-z]?", tid):
                    ev.unmatched.append(f"{f.name}:{ln} transition id {tid!r} does not match <XX>-<n>[suffix]")
                    continue
                ev.parsed.append(tid)
                key = f"{f.name}:{tid}"
                if key in ev.accepted:
                    ev.duplicates.append(key)
                else:
                    ev.accepted.append(key)
    return ev


def declared_transition_total() -> tuple[int, int, list[tuple[str, int]]]:
    """The acceptance spec's per-machine table: (sum of its rows, its stated Total, the rows)."""
    path = require(SPECIFICATIONS / "acceptance" / "foundational-machine-acceptance.md")
    t = find_table(path, "Machine", "Transitions")
    per, stated = [], None
    for row in t["rows"]:
        name, value = clean(row[0]), clean(row[1])
        if name.lower() == "total":
            stated = int(value)
            continue
        per.append((name, int(value)))
    return sum(v for _, v in per), stated, per


def events() -> Evaluation:
    """The canonical event list (registry §3), F1..F14. F15 is a lens and declares no contracts."""
    ev = Evaluation(name="spec.events")
    path = require(EVENTS / "registry.md")
    ev.sources_inspected.append(rel(path))
    saw_family = False
    for line in path.read_text(encoding="utf-8").split("\n"):
        m = re.match(r"^\*\*(F\d+)[^:]*:?\*\*(.*)$", line.strip())
        if not m:
            continue
        fam, body = m.group(1), m.group(2)
        saw_family = True
        ev.candidates.append(fam)
        if fam == "F15":
            continue  # "no new contracts — a lens over cross-machine consumption"
        names = re.findall(r"`([A-Za-z]+)`", body)
        if not names:
            ev.unmatched.append(f"{fam}: family line declared no parseable event names")
            continue
        for name in names:
            ev.parsed.append((fam, name))
            key = f"{fam}:{name}"
            if key in ev.accepted:
                ev.duplicates.append(key)
            else:
                ev.accepted.append(key)
    if not saw_family:
        ev.unmatched.append("registry.md: no '**Fn ...:**' family lines found — the canonical list has moved")
    return ev


def emitted_events() -> list[str]:
    """F1..F13 only — the emitted events, excluding F14 audit/security."""
    return [k for k in events().accepted if not k.startswith("F14:")]


def security_events() -> list[str]:
    return [k for k in events().accepted if k.startswith("F14:")]


def _registry_rows(path: Path, *headers: str, name: str, pattern: str | None = None) -> Evaluation:
    ev = Evaluation(name=name)
    require(path)
    ev.sources_inspected.append(rel(path))
    t = find_table(path, *headers)
    for row, ln in zip(t["rows"], t["line_nos"]):
        ev.candidates.append(ln)
        value = clean(row[1]) if len(row) > 1 else ""
        if not value:
            ev.unmatched.append(f"{path.name}:{ln} empty identifier cell")
            continue
        if pattern and not re.search(pattern, clean(row[0])):
            ev.unmatched.append(f"{path.name}:{ln} index {clean(row[0])!r} unexpected")
            continue
        ev.parsed.append(value)
        if value in ev.accepted:
            ev.duplicates.append(value)
        else:
            ev.accepted.append(value)
    return ev


def domain_entities() -> Evaluation:
    return _registry_rows(DOMAIN / "registry.md", "#", "Entity", "File", name="spec.domain_entities", pattern=r"^\d+$")


def adapters() -> Evaluation:
    return _registry_rows(ADAPTERS / "registry.md", "#", "Adapter", "File", name="spec.adapters")


def loops() -> Evaluation:
    ev = Evaluation(name="spec.loops")
    path = require(WORKFLOWS / "registry.md")
    ev.sources_inspected.append(rel(path))
    t = find_table(path, "WF", "Loop")
    for row, ln in zip(t["rows"], t["line_nos"]):
        ev.candidates.append(ln)
        wf = clean(row[0])
        if not re.search(r"W\d+|L\d+", wf):
            ev.unmatched.append(f"registry.md:{ln} loop id {wf!r} unexpected")
            continue
        ev.parsed.append(wf)
        ev.accepted.append(wf) if wf not in ev.accepted else ev.duplicates.append(wf)
    return ev
