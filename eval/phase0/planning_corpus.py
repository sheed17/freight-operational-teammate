"""Parse the frozen implementation-planning corpus into resolvable identifiers and a graph.

Phase 0 exists partly because this corpus previously contained an identifier that did not resolve:
`AC-SEC-000`, used as a completion oracle for unit U0.3 (planning review M-1). An oracle naming a
test that does not exist is not an oracle - it is a unit that can never be proven done, and would
have been marked done anyway.
"""

from __future__ import annotations

import re
from pathlib import Path

from .evaluation import Evaluation
from .sources import ACCEPTANCE, IMPLEMENTATION, rel, require

ID_PATTERNS = {
    "acceptance": re.compile(r"\bAC-[A-Z]+-[0-9A-Za-z-]+\b"),
    "unit": re.compile(r"\bU\d+\.\d+\b"),
    "phase": re.compile(r"\bP(?:1[0-4]|[0-9])\b"),
    "gate": re.compile(r"\bG(?:10|[0-9])\b"),
    "risk": re.compile(r"\bR-\d{2}\b"),
    "entrypoint": re.compile(r"\bEP-\d+\b"),
    "loophole": re.compile(r"\bPL-\d+\b"),
    "migration": re.compile(r"\bM-\d\b"),
    "cutover": re.compile(r"\bC-\d\b"),
}

# Series-glob notation (`AC-MACH-2*`, `AC-DEG-W6-*`) is deliberate shorthand, not an identifier.
GLOB_SUFFIX = re.compile(r"AC-[A-Z]+-\d$")


def _is_glob_citation(token: str, text: str) -> bool:
    """True when the token is followed by `*` (or `-*`) in the source - i.e. `AC-DEG-W6-*`.

    The `-?` matters: the id regex stops at the word boundary before the hyphen, so the source reads
    `AC-DEG-W6-*` while the captured token is `AC-DEG-W6`. Without it the glob is mistaken for an
    invented identifier.
    """
    return bool(re.search(re.escape(token) + r"-?\*", text))


def _files() -> list[Path]:
    require(IMPLEMENTATION)
    return sorted(p for p in IMPLEMENTATION.glob("*.md"))


def canonical_acceptance_ids() -> Evaluation:
    """Every acceptance identifier declared anywhere in the FROZEN acceptance corpus."""
    ev = Evaluation(name="planning.canonical_acceptance_ids")
    require(ACCEPTANCE)
    for path in sorted(ACCEPTANCE.glob("*.md")):
        ev.sources_inspected.append(rel(path))
        for m in ID_PATTERNS["acceptance"].finditer(path.read_text(encoding="utf-8")):
            ev.candidates.append(m.group())
            ev.parsed.append(m.group())
            if m.group() not in ev.accepted:
                ev.accepted.append(m.group())
    return ev


def cited_acceptance_ids() -> Evaluation:
    """Every acceptance identifier CITED by the implementation-planning corpus."""
    ev = Evaluation(name="planning.cited_acceptance_ids")
    for path in _files():
        ev.sources_inspected.append(rel(path))
        text = path.read_text(encoding="utf-8")
        for m in ID_PATTERNS["acceptance"].finditer(text):
            token = m.group()
            ev.candidates.append(token)
            if GLOB_SUFFIX.match(token) or _is_glob_citation(token, text):
                ev.rejected.append(f"{rel(path)}: {token} (series-glob shorthand, not an id)")
                continue
            ev.parsed.append(token)
            if token not in ev.accepted:
                ev.accepted.append(token)
    return ev


def ids_of(kind: str) -> Evaluation:
    ev = Evaluation(name=f"planning.{kind}_ids")
    pat = ID_PATTERNS[kind]
    for path in _files():
        ev.sources_inspected.append(rel(path))
        for m in pat.finditer(path.read_text(encoding="utf-8")):
            ev.candidates.append(m.group())
            ev.parsed.append(m.group())
            if m.group() not in ev.accepted:
                ev.accepted.append(m.group())
    return ev


def gate_plan_text() -> str:
    return require(IMPLEMENTATION / "release-gate-plan.md").read_text(encoding="utf-8")


def declared_units() -> Evaluation:
    """Units declared by the PR sequence - the canonical unit namespace."""
    ev = Evaluation(name="planning.declared_units")
    path = require(IMPLEMENTATION / "pr-sequence.md")
    ev.sources_inspected.append(rel(path))
    for m in ID_PATTERNS["unit"].finditer(path.read_text(encoding="utf-8")):
        ev.candidates.append(m.group())
        ev.parsed.append(m.group())
        if m.group() not in ev.accepted:
            ev.accepted.append(m.group())
    return ev


def referenced_units() -> Evaluation:
    """Units referenced anywhere else in the planning corpus."""
    ev = Evaluation(name="planning.referenced_units")
    for path in _files():
        if path.name == "pr-sequence.md":
            continue
        ev.sources_inspected.append(rel(path))
        for m in ID_PATTERNS["unit"].finditer(path.read_text(encoding="utf-8")):
            ev.candidates.append(m.group())
            ev.parsed.append(m.group())
            if m.group() not in ev.accepted:
                ev.accepted.append(m.group())
    return ev


def checkpoint_scheme() -> tuple[list[int], list[str], Evaluation]:
    """The 105 checkpoint cases are declared by SCHEME, not enumerated.

    platform-safety-acceptance.md declares "7 steps x 15 conditions = 105", lists the 15 conditions,
    and gives the ID form `AC-CKPT-<step>-<condition>` with the example `AC-CKPT-3-stale`. So
    `AC-CKPT-6-missing` is a legitimate derived identifier even though that literal string never
    appears in the corpus. A resolver that only string-matches would call it invented - which is how
    a correct citation gets "fixed" into a wrong one.
    """
    ev = Evaluation(name="planning.checkpoint_scheme")
    path = require(ACCEPTANCE / "platform-safety-acceptance.md")
    ev.sources_inspected.append(rel(path))
    text = path.read_text(encoding="utf-8")

    m = re.search(r"\*\*Conditions \(per step\):\*\*(.+)", text)
    if not m:
        ev.unmatched.append("the 'Conditions (per step)' declaration was not found")
        return [], [], ev
    conditions = [c.strip() for c in re.findall(r"`([^`]+)`", m.group(1))]
    for c in conditions:
        ev.candidates.append(c)
        ev.parsed.append(c)
        ev.accepted.append(c)

    steps_m = re.search(r"\*\*(\d+) steps [x×] (\d+) conditions = (\d+)", text)
    if not steps_m:
        ev.unmatched.append("the 'N steps x M conditions = K' declaration was not found")
        return [], conditions, ev
    n_steps, n_conditions, total = (int(steps_m.group(i)) for i in (1, 2, 3))
    if len(conditions) != n_conditions:
        ev.unmatched.append(
            f"the corpus declares {n_conditions} conditions but lists {len(conditions)}"
        )
    if n_steps * n_conditions != total:
        ev.unmatched.append(f"{n_steps} x {n_conditions} != {total}")
    return list(range(1, n_steps + 1)), conditions, ev


def checkpoint_id_is_valid(token: str) -> bool:
    """Resolve `AC-CKPT-<step>-<condition>` against the declared scheme."""
    m = re.fullmatch(r"AC-CKPT-(\d+)-([a-z-]+)", token)
    if not m:
        return False
    step, condition = int(m.group(1)), m.group(2)
    steps, conditions, _ = checkpoint_scheme()
    if step not in steps:
        return False
    normalised = {c.split()[0] for c in conditions} | {c.replace(" ", "-") for c in conditions}
    return condition in normalised
