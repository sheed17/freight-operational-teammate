"""False-green defenses: the guards that stop this suite from reporting a pass it did not earn.

These survived the 2026-08 engineering-process simplification because each one protects the TEST
SUITE'S ability to fail, which is what every other safety claim rests on. The finalizer-ceremony
guards that used to live here (forged status receipts, node manifests, clean-clone gate artifacts,
retired-wording scans) were removed with the machinery they policed: CI now runs the suite from a
fresh checkout, so "did the suite really run, on this tree" is answered by the CI log, not by a
committed receipt.

What remains:

  * a test may not silently stop existing (skips, xfails, module-level marks)
  * a negative assertion may not pass vacuously over an empty population
  * a guard may not hand-enumerate the population it guards (this repository produced the same
    filename-enumeration blind spot four separate times)
  * the safety wall in the implementation graph stays transitively intact

Populations are DISCOVERED via eval/control/inventory.py, never typed.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eval"))
from control import inventory as inv  # noqa: E402


def read(p: Path | str) -> str:
    return (ROOT / p if isinstance(p, str) else p).read_text(encoding="utf-8")


def require_population(items, what: str):
    assert items, f"no {what} to assert over - this test would pass vacuously"
    return items


# ============================================================ a test may not silently vanish

APPROVAL = "APPROVED-SKIP:"


def test_every_skip_or_xfail_site_in_the_whole_suite_carries_an_inline_approval():
    """AST over EVERY tracked canonical test module, both directions.

    A skip is silence, and silence is not a pass. The old design kept a separate
    docs/implementation/APPROVED-SKIPS.yaml manifest; that was hand-maintained bookkeeping for a
    population that is currently a single site. The approval now lives on the line itself, where
    it cannot drift away from the code it approves: within the eight lines above a skip-capable
    construct there must be a comment `# APPROVED-SKIP: <reason>` with a real reason.
    """
    modules = require_population(inv.canonical_test_modules(), "canonical test modules")
    assert len(modules) >= 100, f"module discovery collapsed to {len(modules)}"

    offenders = []
    for site in inv.skip_xfail_sites():
        lines = read(site["file"]).split("\n")
        window = "\n".join(lines[max(0, site["line"] - 9): site["line"]])
        m = re.search(rf"#\s*{re.escape(APPROVAL)}\s*(\S.*)", window)
        if not m or len(m.group(1).split()) < 4:
            offenders.append(f"{site['file']}:{site['line']} ({site['construct']})")
    assert not offenders, (
        "skip/xfail sites with no adjacent `# APPROVED-SKIP: <reason>`: " + ", ".join(offenders)
        + " - an unapproved skip is a test that can silently stop existing"
    )


def test_no_module_level_pytestmark_or_importorskip_hides_tests():
    """A module-level mark disables a whole file at once and reports nothing."""
    sites = inv.skip_xfail_sites()
    marks = [s for s in sites if s["construct"] in ("pytestmark", "pytest.importorskip")]
    assert not marks, f"module-level skip machinery present: {marks}"


def test_the_suite_collects_without_a_single_error():
    """A collection error is a whole file's worth of assertions that never ran."""
    import subprocess
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "eval", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True, env={**__import__("os").environ,
                                                       "PYTEST_ADDOPTS": ""},
    )
    assert proc.returncode == 0, f"collection failed:\n{proc.stdout[-4000:]}\n{proc.stderr[-2000:]}"
    assert " error" not in proc.stdout.lower(), f"collection reported errors:\n{proc.stdout[-4000:]}"


def test_no_test_shells_out_to_a_hardcoded_local_virtualenv():
    """CI installs into the runner's own environment and has no virtualenv directory in the repo.
    A test that spawns an interpreter out of a repo-local environment directory passes on a
    developer laptop and fails on every clean checkout - the whole class of local-environment
    dependence CI exists to eliminate. Four tests did exactly this before the 2026-08
    simplification; `sys.executable` is the portable answer.

    STRUCTURAL, NOT A SUBSTRING SCAN. The first version of this guard was a line regex and its
    first offender was its own docstring - the exact defect CLAUDE.md sec 6 names. It now looks
    for the string participating in PATH CONSTRUCTION (a `/` BinOp, or an os.path.join argument),
    which is what actually builds an interpreter path. Naming the directory in an exclusion set,
    a comment or a docstring is not path construction and is correctly ignored.
    """
    venv_dir = "." + "venv"  # not written as one literal, or this guard is its own offender

    def offends(tree: ast.AST) -> list[int]:
        hits = []
        for node in ast.walk(tree):
            if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
                operands = [node.left, node.right]
            elif isinstance(node, ast.Call) and "join" in ast.unparse(node.func):
                operands = list(node.args)
            else:
                continue
            for o in operands:
                if isinstance(o, ast.Constant) and isinstance(o.value, str) and o.value == venv_dir:
                    hits.append(node.lineno)
        return hits

    offenders = []
    for rel in require_population(inv.canonical_test_modules(), "canonical test modules"):
        for line in offends(ast.parse(read(rel))):
            offenders.append(f"{rel}:{line}")
    assert not offenders, (
        "test(s) building an interpreter path out of a repo-local environment directory - use "
        "sys.executable: " + ", ".join(offenders)
    )


# ============================================================ a negative assertion needs a population


def test_every_corpus_scanning_negative_assertion_proves_its_population():
    """`assert X not in results` passes over an empty parse. Every corpus-scanning negative
    assertion must prove it had something to scan."""
    funcs = require_population(inv.negative_assertion_functions(),
                               "corpus-scanning negative-assertion tests")
    assert len(funcs) >= 10, f"discovery collapsed to {len(funcs)} functions"
    unproven = [f"{f['file']}::{f['function']}" for f in funcs if not f["proves_population"]]
    assert not unproven, (
        "corpus-scanning negative assertions without a population proof (vacuously green over "
        "an empty parse):\n  " + "\n  ".join(unproven)
    )


# ============================================================ guards may not enumerate filenames

PATHLIKE = re.compile(r"\.(md|ya?ml|json|py|txt)$")


def test_no_control_guard_hand_enumerates_a_file_population():
    """AST over every DISCOVERED control-guard module: a list/tuple/set/dict literal containing
    3+ path-like strings is a hand-enumerated population unless annotated FIXED-SPECIFICATION
    with a reason on an adjacent line."""
    offenders = []
    for rel in require_population(inv.control_guard_modules(), "control-guard modules"):
        src = read(rel)
        lines = src.split("\n")
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if not isinstance(node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
                continue
            elts = node.keys if isinstance(node, ast.Dict) else node.elts
            strings = [e.value for e in elts
                       if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            pathish = [x for x in strings if PATHLIKE.search(x)]
            if len(pathish) < 3:
                continue
            window = "\n".join(lines[max(0, node.lineno - 8): node.lineno + 2])
            if "FIXED-SPECIFICATION" in window:
                continue
            offenders.append(f"{rel}:{node.lineno}: literal with {len(pathish)} path-like strings "
                             f"({pathish[:3]}...) - discover it or annotate FIXED-SPECIFICATION with a reason")
    assert not offenders, "hand-enumerated populations inside control guards:\n  " + "\n  ".join(offenders)


# ============================================================ the safety wall stays intact


def _graph() -> dict[str, list[str]]:
    units = yaml.safe_load(read("docs/implementation/IMPLEMENTATION-REGISTRY.yaml"))["units"]
    return {u["unit_id"]: list(u.get("dependencies") or []) for u in units}


def _ancestors(g: dict[str, list[str]], unit: str) -> set[str]:
    seen, stack = set(), list(g.get(unit, []))
    while stack:
        cur = stack.pop()
        if cur in seen or cur not in g:
            continue
        seen.add(cur)
        stack.extend(g[cur])
    return seen


def test_the_complete_safety_wall_is_transitively_protected():
    """Not named examples - EVERY phase: P3 (the checkpoint kernel) is a transitive ancestor of
    P4..P14 and P4 (adapter containment) of P5..P14, so no later phase can be re-parented around
    the safety wall while every derived view stays self-consistent."""
    g = _graph()
    phase_nums = sorted(int(u[1:]) for u in g if re.fullmatch(r"P\d+", u))
    assert phase_nums[:4] == [0, 1, 2, 3] and max(phase_nums) >= 14, f"phase set implausible: {phase_nums}"
    for i in (n for n in phase_nums if n >= 4):
        assert "P3" in _ancestors(g, f"P{i}"), (
            f"P{i} lost P3 as a transitive ancestor - the checkpoint wall is bypassed")
    for i in (n for n in phase_nums if n >= 5):
        assert "P4" in _ancestors(g, f"P{i}"), (
            f"P{i} lost P4 as a transitive ancestor - containment is bypassed")
    for i in (n for n in phase_nums if 4 <= n <= 14):
        assert f"P{i-1}" in g[f"P{i}"], (
            f"P{i} no longer directly depends on P{i-1} - the linear roadmap chain is broken")
    for i in range(1, 15):
        assert "P0" in _ancestors(g, f"P{i}"), f"P{i} is disconnected from the programme root"


def test_a_ready_unit_never_has_incomplete_dependencies():
    units = yaml.safe_load(read("docs/implementation/IMPLEMENTATION-REGISTRY.yaml"))["units"]
    by_id = {u["unit_id"]: u for u in units}
    g = _graph()
    ready = [u for u in units if u["status"] == "READY"]
    require_population(ready, "READY units")
    for u in ready:
        incomplete = [d for d in _ancestors(g, u["unit_id"]) | set(g[u["unit_id"]])
                      if by_id[d]["status"] != "COMPLETE"]
        assert not incomplete, (
            f"{u['unit_id']} is READY while transitive dependencies are incomplete: {incomplete}")
