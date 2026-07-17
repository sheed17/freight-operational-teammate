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
