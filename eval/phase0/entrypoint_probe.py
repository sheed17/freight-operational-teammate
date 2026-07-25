"""Effect-capable entry points, recomputed from the import graph.

An entry point is effect-capable when it can reach an actuator or a write driver. "It's read-only"
is a claim about intent; the import graph is a fact about capability. EP-8 (`orient_tms.py`) is the
worked example: classified read-only, imports `cdp_actuator`.

Phase 0 records these. It does NOT make them safe. The six production-reachable live-write paths
remain physically capable of ungated effects until Phase 4 deletes or converts them (risk R-07,
loophole PL-18). Nothing in this module may be read as containment.
"""

from __future__ import annotations

from dataclasses import dataclass

from .evaluation import Evaluation
from .import_probe import ADAPTER_MODULES, adapter_import_sites
from .sources import SCRIPTS, rel

# Modules that can actuate or write to an external system (as opposed to holding a session/config).
EFFECT_CAPABLE = {
    "cdp_actuator", "truckingoffice_write", "multistep_write", "discovered_write",
    "tms_write", "browser_use_adapter", "browser_tms_adapter", "browser_use_write",
}


@dataclass(frozen=True)
class EntryPoint:
    script: str
    imports: tuple[str, ...]

    @property
    def effect_capable(self) -> bool:
        return bool(set(self.imports) & EFFECT_CAPABLE)


def entry_points() -> tuple[list[EntryPoint], Evaluation]:
    """Every script in scripts/, with the adapter modules it directly imports."""
    ev = Evaluation(name="entrypoints.scripts")
    sites, site_ev = adapter_import_sites()
    by_script: dict[str, set[str]] = {}
    for path in sorted(SCRIPTS.glob("*.py")):
        ev.sources_inspected.append(rel(path))
        by_script.setdefault(rel(path), set())
    for s in sites:
        if s.module in by_script:
            by_script[s.module].add(s.imported)
    out = []
    for script, imports in sorted(by_script.items()):
        ev.candidates.append(script)
        ep = EntryPoint(script, tuple(sorted(imports)))
        ev.parsed.append(script)
        out.append(ep)
        ev.accepted.append(script)
    if site_ev.unmatched:
        ev.unmatched.extend(site_ev.unmatched)
    return out, ev


def effect_capable_entry_points() -> list[EntryPoint]:
    eps, _ = entry_points()
    return [e for e in eps if e.effect_capable]


def script_references() -> tuple[dict[str, set[str]], Evaluation]:
    """Scripts that NAME other scripts — a superset of the spawn graph, deliberately.

    The import graph cannot see a subprocess launch. EP-2 (`run_teammate.py`) is effect-capable only
    because it spawns EP-1/EP-3, and an import-only guard would call the supervisor harmless.

    This probe reports every script that names another and REFUSES to guess which are real spawns.
    A first version of it did guess, by substring, and immediately produced a false positive:
    `run_sunday_readiness.py` only PRINTS the callback-server command inside a runbook string for a
    human to copy. It launches nothing. A guard that cries wolf gets ignored, and an ignored guard is
    not a guard — so each reference is adjudicated in the baseline manifest as SPAWNS or DOCUMENTS,
    by a human, once.
    """
    ev = Evaluation(name="entrypoints.script_references")
    names = {p.name: rel(p) for p in sorted(SCRIPTS.glob("*.py"))}
    out: dict[str, set[str]] = {}
    for path in sorted(SCRIPTS.glob("*.py")):
        ev.sources_inspected.append(rel(path))
        text = path.read_text(encoding="utf-8")
        hits = {other for other in names if other != path.name and other in text}
        if hits:
            ev.candidates.append(rel(path))
            out[rel(path)] = {names[h] for h in hits}
            ev.parsed.append(rel(path))
            ev.accepted.append(rel(path))
    return out, ev


def references_to_effect_capable() -> dict[str, set[str]]:
    """References that point AT an effect-capable script. Each needs a manifest classification."""
    direct = {e.script for e in effect_capable_entry_points()}
    refs, _ = script_references()
    out: dict[str, set[str]] = {}
    for parent, children in refs.items():
        reachable = children & direct
        if reachable and parent not in direct:
            out[parent] = reachable
    return out
