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


# =============================================================================================
# THE TRANSITIVE IMPORT CLOSURE, SPELLING-COMPLETE.
#
# `adapter_import_sites` above answers "who imports an adapter DIRECTLY". A dark-surface guard needs
# the other question: "what can this module reach, through any number of hops, in any legal import
# spelling". It lives here rather than in a test because the FIRST version of the M2 dark-surface
# guard shipped its own walker, and that walker recognised two of Python's import forms out of six
# — it followed `from .x import y` and `import freight_recon.x`, and was blind to
# `from freight_recon.x import y` (the DOMINANT spelling in this package), to `from . import x`
# (in live use at `governed_write_route.py` and `action_callback.py`), and to
# `importlib.import_module`. A closure walk that stops at the first unrecognised spelling reports an
# empty leak set and looks green. One walker, in the repository's own import authority, mutation-
# proven against every spelling, is the answer to that class of defect — not a second walker.
# =============================================================================================

_PACKAGE = "freight_recon"


def package_modules() -> dict[str, Path]:
    """Every importable module of the package, dotted-relative to it. `migrations/x.py` -> `migrations.x`."""
    out: dict[str, Path] = {}
    for path in python_files(SRC):
        rel_parts = path.relative_to(SRC).with_suffix("").parts
        if rel_parts and rel_parts[-1] == "__init__":
            rel_parts = rel_parts[:-1]
        if not rel_parts:
            continue  # the package's own __init__
        out[".".join(rel_parts)] = path
    return out


def _package_of(module: str) -> str:
    """The package a module lives in, dotted-relative to `freight_recon`. Top level -> ""."""
    return module.rpartition(".")[0]


def _ascend(package: str, level: int) -> str | None:
    """Resolve `level` leading dots from `package`. `None` when it climbs out of the package."""
    parts = [p for p in package.split(".") if p]
    for _ in range(level - 1):
        if not parts:
            return None
        parts.pop()
    return ".".join(parts)


def _targets_from(base: str, names: tuple[str, ...]) -> set[str]:
    """A dotted base plus the names imported from it, and every proper prefix of the base.

    `from freight_recon.migrations.x import Y` can bind the module `migrations.x` AND, when `Y` is
    itself a submodule, `migrations.x.Y`. Both are emitted; the closure walk discards whichever does
    not resolve to a file, so a symbol is never mistaken for a module.
    """
    out: set[str] = set()
    if base:
        out.add(base)
        parts = base.split(".")
        for i in range(1, len(parts)):
            out.add(".".join(parts[:i]))
    for name in names:
        out.add(f"{base}.{name}" if base else name)
    return out


def module_import_targets(tree: ast.AST, module: str) -> set[str]:
    """Every module of THIS package that `module`'s source can pull into its namespace.

    Covers all six spellings the package actually uses or could use:
        import freight_recon.a.b [as x]
        from freight_recon.a.b import n
        from freight_recon import n
        from .a import n          /  from ..a import n
        from . import n           /  from .. import n
        importlib.import_module("freight_recon.a")  /  __import__(...)  /  import_module(".a", pkg)
    """
    package = _package_of(module)
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _PACKAGE:
                    continue
                if alias.name.startswith(f"{_PACKAGE}."):
                    out |= _targets_from(alias.name.split(".", 1)[1], ())
        elif isinstance(node, ast.ImportFrom):
            names = tuple(a.name for a in node.names)
            if node.level:
                base = _ascend(package, node.level)
                if base is None:
                    continue  # climbs out of the package: not our graph
                if node.module:
                    base = f"{base}.{node.module}" if base else node.module
                out |= _targets_from(base, names)
            elif node.module == _PACKAGE:
                out |= _targets_from("", names)
            elif node.module and node.module.startswith(f"{_PACKAGE}."):
                out |= _targets_from(node.module.split(".", 1)[1], names)
        elif isinstance(node, ast.Call):
            fn = node.func
            fname = getattr(fn, "attr", None) or getattr(fn, "id", None)
            if fname not in ("import_module", "__import__") or not node.args:
                continue
            arg = node.args[0]
            if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
                continue
            spelled = arg.value
            if spelled.startswith("."):
                level = len(spelled) - len(spelled.lstrip("."))
                base = _ascend(package, level)
                if base is None:
                    continue
                tail = spelled[level:]
                out |= _targets_from(f"{base}.{tail}" if base and tail else (tail or base), ())
            elif spelled == _PACKAGE:
                continue
            elif spelled.startswith(f"{_PACKAGE}."):
                out |= _targets_from(spelled.split(".", 1)[1], ())
    return out


def package_import_closure(roots) -> tuple[set[str], Evaluation]:
    """The transitive closure of package modules reachable from `roots`, dotted-relative names.

    The roots themselves are included. An unresolvable target is DROPPED (it was a symbol, not a
    module) and an unparseable source is recorded in `unmatched` rather than skipped silently.
    """
    ev = Evaluation(name="imports.package_closure")
    modules = package_modules()
    seen: set[str] = set()
    frontier = [r for r in roots]
    for root in frontier:
        if root not in modules:
            raise FileNotFoundError(
                f"import closure root {root!r} is not a module of {_PACKAGE}. A closure walk from a "
                f"root that does not exist reaches nothing and reports green."
            )
    while frontier:
        module = frontier.pop()
        if module in seen:
            continue
        seen.add(module)
        path = modules.get(module)
        if path is None:
            continue
        ev.sources_inspected.append(rel(path))
        ev.accepted.append(module)
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            ev.unmatched.append(f"{rel(path)}: unparseable ({exc})")
            continue
        for target in module_import_targets(tree, module):
            ev.candidates.append(f"{module} -> {target}")
            if target in modules and target not in seen:
                frontier.append(target)
    return seen, ev


def effect_capable_reachable_from(roots) -> tuple[set[str], Evaluation]:
    """Which EFFECT-CAPABLE adapters `roots` can reach transitively. Empty == the surface is dark.

    The population is `EFFECT_CAPABLE_ADAPTERS` — this module's own authority, the same set the P4
    import gate partitions on — so an adapter added there is guarded here on the same commit,
    without anybody remembering to update a second list.
    """
    closure, ev = package_import_closure(roots)
    ev.name = "imports.effect_capable_reachable"
    return {m for m in closure if m.rpartition(".")[2] in EFFECT_CAPABLE_ADAPTERS}, ev
