"""One importer detector for every "who imports this machine?" guard.

### WHY THIS EXISTS. Each foundational machine shipped with its own ships-dark guard, and each guard
carried its own hand-written import matcher. They did not agree about what an import looks like. When
the P9 freight-domain spine first imported the machines — from a SUBPACKAGE, so every import is
`from ..machine import X` — three of those guards stayed green while their machine had a brand-new
importer:

  * M8's matched the SUBSTRING `from .expectation`, which `from ..expectation` does not contain;
  * the Evidence store's matched `node.module in (".evidence", ...)` — the AST never yields a leading
    dot, so it had not been able to see even `lineage.py`'s ordinary sibling import;
  * the provenance module's matched `module.endswith(".provenance")`, blind to `from .provenance` and
    `from ..provenance` alike.

A guard never seen to fail is a decoration (CLAUDE.md sec 6). This module is the ONE matcher, it reads
the AST rather than text, and `test_p9_freight_domain_ships_dark.py` proves it fires on every spelling
below before any guard relies on it.

Spellings recognised, each as "this file imports the module named <stem>":

    from .stem import X            from ..stem import X           from ...pkg.stem import X
    from freight_recon.stem import X                              from freight_recon.pkg.stem import X
    from . import stem             from .. import stem            from freight_recon import stem
    import freight_recon.stem      import freight_recon.stem as s
    importlib.import_module("freight_recon.stem")                 __import__("freight_recon.stem")
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "freight_recon"
SCRIPTS = ROOT / "scripts"

#: The P9 composition module: the one production module entitled to import the P6-P8 machines.
P9_FOUNDATION = "src/freight_recon/freight_domain/foundation.py"

#: Package names whose `from <package> import name` form imports MODULES rather than objects.
_PACKAGES = frozenset({"", "freight_recon", "migrations", "freight_domain"})


def imported_modules(source: str) -> set[str]:
    """The stem of every module `source` imports, in any spelling. A stem is the last dotted
    component — `freight_recon.migrations.phase6_conflicts` yields `phase6_conflicts`, never
    `conflict`."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if module:
                found.add(module.split(".")[-1])
            # `from . import stem` / `from freight_recon import stem`: the NAMES are modules.
            if module.split(".")[-1] in _PACKAGES:
                found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            found.update(alias.name.split(".")[-1] for alias in node.names)
        elif isinstance(node, ast.Call):
            target = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if target in ("import_module", "__import__"):
                for argument in node.args:
                    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                        found.add(argument.value.split(".")[-1])
    return found


def population(*, scripts: bool = False) -> list[Path]:
    """Every Python source a guard sweeps: the whole package, discovered, and optionally the operator
    scripts. Never an enumerated list."""
    files = sorted(SRC.rglob("*.py"))
    if scripts:
        files += sorted(SCRIPTS.rglob("*.py"))
    assert len(files) > 40, f"the sweep found only {len(files)} files; it would prove nothing"
    return files


def importers_of(stem: str, *, scripts: bool = False) -> set[str]:
    """Repo-relative paths of every file that imports the module named `stem` — excluding the module
    itself. Prints its denominator."""
    files = population(scripts=scripts)
    found = {
        path.relative_to(ROOT).as_posix()
        for path in files
        if not (path.stem == stem and path.parent == SRC)
        and stem in imported_modules(path.read_text(encoding="utf-8"))
    }
    print(f"importers_of({stem!r}): swept {len(files)} files, {len(found)} importer(s)")
    return found


def callers_of(attribute: str) -> set[str]:
    """Repo-relative paths of every package file that references `.attribute` — a method call or a
    bound-method read."""
    files = population()
    found = {
        path.relative_to(ROOT).as_posix()
        for path in files
        if any(isinstance(node, ast.Attribute) and node.attr == attribute
               for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))))
    }
    print(f"callers_of({attribute!r}): swept {len(files)} files, {len(found)} caller(s)")
    return found


def import_closure(start: Path) -> set[str]:
    """Every `freight_recon` module stem reachable from `start` by imports, transitively."""
    by_stem: dict[str, list[Path]] = {}
    for path in SRC.rglob("*.py"):
        by_stem.setdefault(path.stem, []).append(path)
    seen: set[str] = set()
    visited: set[Path] = set()
    frontier = [start]
    while frontier:
        path = frontier.pop()
        if path in visited:
            continue
        visited.add(path)
        for stem in imported_modules(path.read_text(encoding="utf-8")):
            if stem in by_stem and stem not in seen:
                seen.add(stem)
                frontier.extend(by_stem[stem])
    return seen
