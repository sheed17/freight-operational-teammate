"""The import graph, by AST — not by reputation and not by grep.

The planning recon found `orient_tms.py` importing `cdp_actuator` while classified read-only:
read-only by convention, actuator-capable by import. Only the import graph finds that. A module's
docstring is not evidence about what it can do.

This probe DETECTS. It does not contain. Containment is U4.9 (Phase 4) and requires the pipeline
client to exist first — enabling a gate earlier would only force wrappers, and a wrapper that logs
the bypass is not containment (roadmap, PL-6).
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from .evaluation import Evaluation
from .sources import SCRIPTS, SRC, python_files, rel

# The modules that can touch an external system. Named from the frozen adapter inventory.
ADAPTER_MODULES = {
    "cdp_actuator", "cdp_session", "browser_use_adapter", "browser_tms_adapter",
    "truckingoffice_write", "multistep_write", "discovered_write", "tms_write",
    "browser_agent", "browser_use_write",
}

# ---------------------------------------------------------------------------------------------
# THE P4 BOUNDARY-AWARE PARTITION (the U4.9 import gate).
#
# ADR-004 §4.2: "no module outside `pipeline/` imports `adapters/`." This repository is a flat
# package, so the rule is expressed as a partition over module names rather than directories.
# The gate forbids EFFECT-CAPABLE adapter imports by any module that is not the containment
# boundary, another adapter (intra-layer composition), or a recorded, mock-guarded quarantine.
# ---------------------------------------------------------------------------------------------

# The write-capable adapters — the ones that PRODUCE an external effect. `cdp_session` is the
# read substrate (navigate + evaluate; ADR/repository authority keeps it importable by read-only
# tooling — EP-8's disposition removes only the `cdp_actuator` import), so it is deliberately NOT
# in this set. The deterministic money-path actuation lives in `cdp_actuator`, which IS here.
#
# `browser_use_adapter` WAS in this set and is not any more (EP-14). That is a RECLASSIFICATION on
# structural grounds, not a relaxation: it held `BrowserUseWriteLedger` (a payable write) and
# `NativeBrowserUseRunner` (a driver that runs an ARBITRARY task), and both now live in
# `browser_use_write`. What remains cannot express a write — no write method exists on it, it
# imports no effect-capable adapter, and its transport takes a vetted task ID plus data rather than
# a caller-authored task string. The proof is `test_browser_use_readonly_surface.py` (structural,
# call-closure and behavioural) plus the boundary mutation battery, which is the same standard the
# F2 CDP split had to meet before `cdp_readonly` was trusted as the read substrate. Reclassifying
# it on the strength of its docstring — which already said "Read-only Browser Use TMS adapter"
# while the write ledger sat in the same file — is exactly what this set exists to prevent.
EFFECT_CAPABLE_ADAPTERS = {
    "cdp_actuator", "browser_tms_adapter",
    "truckingoffice_write", "multistep_write", "discovered_write", "tms_write",
    "browser_agent", "browser_use_write",
}

# The ONE containment boundary: the only non-adapter module permitted to import an effect-capable
# adapter. Everything consequential flows through `execute_effect` here (P4).
CONTAINMENT_BOUNDARY = {"effect_boundary"}

# The adapter layer: modules that may import an effect-capable adapter because they ARE part of the
# adapter substrate (adapters compose, and the mock write server is the test double of one). A
# module importing itself is already excluded by the probe.
ADAPTER_LAYER = EFFECT_CAPABLE_ADAPTERS | {"cdp_session", "mock_tms_write_server"}

# Quarantined, mock-guarded, test-only entry points: retained for evidence, structurally excluded
# from production execution, and proven mock-guarded by `test_no_mock_effect_in_production`. They
# are recorded here (NOT in the shrinking violation allowlist) so the gate can distinguish a
# quarantined fixture from a live-production bypass. Populated as P4 quarantines each one.
QUARANTINE_IMPORTERS: set[str] = {"enter_tms_payable", "run_dogfood_pilot"}


@dataclass(frozen=True)
class ImportSite:
    module: str          # repo-relative path of the importer
    imported: str        # the adapter module imported
    symbols: tuple[str, ...]
    lineno: int
    dynamic: bool = False

    @property
    def key(self) -> str:
        return f"{self.module}::{self.imported}"


def _module_name(node: ast.AST) -> list[tuple[str, tuple[str, ...], int, bool]]:
    """Every way an adapter module can enter a namespace.

    The mutation harness caught this: a first version read only the MODULE of an ImportFrom, so
    `from freight_recon.cdp_actuator import x` was seen (module == cdp_actuator) but
    `from freight_recon import cdp_actuator` was INVISIBLE - the adapter name lands in the imported
    symbols, not the module. The guard could be bypassed by changing import style, which is exactly
    the "effect path hidden behind an alias" case it exists to catch.
    """
    out = []
    if isinstance(node, ast.Import):
        # import freight_recon.cdp_actuator [as x]
        for a in node.names:
            out.append((a.name.split(".")[-1], (), node.lineno, False))
    elif isinstance(node, ast.ImportFrom):
        if node.module:
            # from freight_recon.cdp_actuator import press  -> module IS the adapter
            out.append((node.module.split(".")[-1], tuple(a.name for a in node.names), node.lineno, False))
        # from freight_recon import cdp_actuator [as x]     -> the adapter is an imported NAME
        for a in node.names:
            if a.name in ADAPTER_MODULES:
                out.append((a.name, (a.name,), node.lineno, False))
    elif isinstance(node, ast.Call):
        # dynamic: importlib.import_module("x") / __import__("x")
        fn = node.func
        name = getattr(fn, "attr", None) or getattr(fn, "id", None)
        if name in ("import_module", "__import__") and node.args:
            arg = node.args[0]
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                out.append((arg.value.split(".")[-1], (), node.lineno, True))
    return out


def adapter_import_sites() -> tuple[list[ImportSite], Evaluation]:
    """Every module that imports an adapter directly, with the symbols it pulls in."""
    ev = Evaluation(name="imports.direct_adapter_sites")
    sites: list[ImportSite] = []
    files = python_files(SRC, SCRIPTS)
    for path in files:
        ev.sources_inspected.append(rel(path))
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            ev.unmatched.append(f"{rel(path)}: unparseable ({exc})")
            continue
        for node in ast.walk(tree):
            for mod, symbols, lineno, dynamic in _module_name(node):
                if mod not in ADAPTER_MODULES:
                    continue
                if path.stem == mod:
                    continue  # a module importing itself is not a site
                ev.candidates.append(f"{rel(path)}:{lineno}")
                site = ImportSite(rel(path), mod, symbols, lineno, dynamic)
                ev.parsed.append(site.key)
                if site.key in {s.key for s in sites}:
                    ev.duplicates.append(site.key)
                    continue
                sites.append(site)
                ev.accepted.append(site.key)
    return sites, ev


def is_adapter_module(path: Path) -> bool:
    return path.stem in ADAPTER_MODULES


def _importer_stem(module_path: str) -> str:
    """The importer module's stem, e.g. `scripts/orient_tms.py` -> `orient_tms`."""
    return Path(module_path).stem


def is_effect_capable_violation(site: ImportSite) -> bool:
    """The single partition decision the gate turns on, exposed so it can be exercised directly.

    A site is a VIOLATION iff it imports an EFFECT-CAPABLE adapter AND its importer is not one of
    the three exempt classes: the containment boundary, another adapter (intra-layer composition),
    or a recorded, mock-guarded quarantine importer. A read-substrate import (`cdp_session`) is
    never a violation — it produces no external effect. The exempt set is recomputed on each call
    so a test can extend `QUARANTINE_IMPORTERS` and watch the gate react; it is not frozen at
    import time.
    """
    if site.imported not in EFFECT_CAPABLE_ADAPTERS:
        return False  # a read-substrate import (cdp_session) is not an effect
    allowed = CONTAINMENT_BOUNDARY | ADAPTER_LAYER | QUARANTINE_IMPORTERS
    return _importer_stem(site.module) not in allowed


def effect_adapter_import_violations() -> tuple[list[ImportSite], Evaluation]:
    """THE P4 import gate, boundary-aware. A VIOLATION is an import of an EFFECT-CAPABLE adapter by
    a module that is not the containment boundary, another adapter, or a recorded quarantine.

    This is stricter where it matters (it names the boundary and refuses everyone else) and looser
    only where the architecture is: adapters compose, and the read substrate (`cdp_session`) is not
    an effect. The decision is `is_effect_capable_violation`, recomputed each call so a test can
    extend `QUARANTINE_IMPORTERS` and see the gate react — nothing is frozen at import time.
    """
    sites, base_ev = adapter_import_sites()
    ev = Evaluation(name="imports.effect_adapter_violations")
    ev.sources_inspected = list(base_ev.sources_inspected)
    violations: list[ImportSite] = []
    for s in sites:
        if s.imported not in EFFECT_CAPABLE_ADAPTERS:
            continue  # a read-substrate import (cdp_session) is not an effect
        ev.candidates.append(s.key)
        if is_effect_capable_violation(s):
            ev.accepted.append(f"{s.module} -> {s.imported}")
            violations.append(s)
    return violations, ev


def effect_adapter_violation_edges() -> set[str]:
    sites, _ = effect_adapter_import_violations()
    return {f"{s.module} -> {s.imported}" for s in sites}
