"""The canonical dynamic inventory layer (U-HANDOFF-1C, H-6).

The repository's own rule - "never enumerate filenames in a guard; discover them" - had been
violated systemically by the guards themselves: volatile-figure scans, retired-count scans,
citation scans, banner requirements and review-document classification each carried a private
hand-typed file list, and a new file entered none of them. This module is the single discovery
layer every control guard consumes.

Populations derive ONLY from:
  - `git ls-files` (the tracked tree - untracked local files are never silently in scope,
    tracked files are never silently out of scope)
  - the canonical authority map's OWN classification rows (docs/CANONICAL-DOCUMENTS.md)
  - documented family rules (the review-document family)
  - file type and location
  - test collection (for test modules)

Nothing here excludes a file because its name contains "review", "historical", "old", "legacy",
"archive" or "errata" - classification decides treatment, names do not.

FIXED-SPECIFICATION annotations: deliberately specified safety invariants (HANDOFF-01..13, the
P0..P14 phase chain, the canonical table partition, the seven checkpoint steps) are ALLOWED to be
literal. Discovery populations are not. The meta-guard in test_false_green_defenses.py enforces
the distinction across guard modules.
"""

from __future__ import annotations

import re
import subprocess
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUTHORITY_MAP = ROOT / "docs" / "CANONICAL-DOCUMENTS.md"

# Authority classes whose documents may direct current decisions.
CURRENT_AUTHORITY_CLASSES = (  # FIXED-SPECIFICATION: the authority model's own vocabulary
    "CANONICAL", "CURRENT_STATUS", "IMPLEMENTATION_CONTROL", "ACCEPTANCE_ORACLE",
)
HISTORICAL_CLASSES = ("HISTORICAL", "SUPERSEDED", "QUARANTINED_GUIDANCE", "NEEDS_VALIDATION",
                      "EVIDENCE")

TEXT_SUFFIXES = (".md", ".txt", ".yaml", ".yml", ".json", ".toml", ".ini", ".cfg")


@lru_cache(maxsize=1)
def tracked_files() -> tuple[str, ...]:
    out = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True)
    return tuple(sorted(l for l in out.stdout.split("\n") if l))


def tracked_textual_files() -> list[str]:
    return [f for f in tracked_files() if f.endswith(TEXT_SUFFIXES)]


# ------------------------------------------------------------------ authority-map parsing

@lru_cache(maxsize=1)
def _map_rows() -> list[tuple[str, str]]:
    """(subject-cell, full-row) for every table row in the authority map."""
    rows = []
    for ln in AUTHORITY_MAP.read_text(encoding="utf-8").split("\n"):
        if not ln.strip().startswith("|"):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", ln.strip())[1:-1]]
        if len(cells) >= 2:
            rows.append((cells[0], ln))
    return rows


def _files_in_cell(cell: str) -> list[str]:
    """Filenames named in a map cell - both `backticked` names and [link](path) targets."""
    names = re.findall(r"`([A-Za-z0-9_./-]+\.(?:md|txt|yaml|yml|json))`", cell)
    names += re.findall(r"\]\(([A-Za-z0-9_./-]+\.(?:md|txt|yaml|yml|json))\)", cell)
    return names


def _resolve(name: str) -> str | None:
    """Map a map-cell filename to its tracked repo-relative path."""
    name = name.lstrip("./")
    candidates = [name, f"docs/{name}", f"docs/{name.lstrip('../')}"]
    if name.startswith("implementation/") or name.startswith("product/") or name.startswith("architecture/"):
        candidates.append(f"docs/{name}")
    tracked = set(tracked_files())
    for c in candidates:
        if c in tracked:
            return c
    # basename fallback - unique basenames only
    base = name.split("/")[-1]
    hits = [f for f in tracked if f.endswith("/" + base) or f == base]
    return hits[0] if len(hits) == 1 else None


def classified(classes: tuple[str, ...]) -> dict[str, str]:
    """path -> class for every file whose SUBJECT cell row carries one of the classes."""
    out: dict[str, str] = {}
    for subject, row in _map_rows():
        cls = next((c for c in classes if re.search(rf"\b{c}\b", row)), None)
        if not cls:
            continue
        # the class must be a CLASSIFICATION of this row, not the subject merely naming it -
        # heuristic: the class token appears outside the subject cell
        remainder = row.replace(subject, "", 1)
        if not re.search(rf"\b{cls}\b", remainder):
            continue
        for name in _files_in_cell(subject):
            path = _resolve(name)
            if path:
                out.setdefault(path, cls)
    return out


# ------------------------------------------------------------------ document populations

def implementation_review_documents() -> list[str]:
    """The review FAMILY, by documented rule: docs/implementation markdown that is a review or
    phase/blocker/handoff record - matched by content-role markers, not by belief."""
    out = []
    for f in tracked_files():
        if not (f.startswith("docs/implementation/") and f.endswith(".md")):
            continue
        base = f.rsplit("/", 1)[-1]
        if re.search(r"review", base, re.I) or re.match(r"(u2-6|u-handoff-\d|phase-\d-)", base):
            out.append(f)
    return sorted(out)


def historical_documents() -> list[str]:
    """Every tracked document that is historical evidence rather than current authority:
    map-classified historical/superseded/quarantined + the review family + pre-reset docs root."""
    out = set(classified(HISTORICAL_CLASSES))
    out |= set(implementation_review_documents())
    current = set(current_authority_documents())
    # docs/ root files that are not classified as current authority are pre-reset evidence
    for f in tracked_files():
        if re.fullmatch(r"docs/[^/]+\.(md|txt)", f) and f not in current and f != "docs/CANONICAL-DOCUMENTS.md":
            out.add(f)
    return sorted(out - current)


def current_authority_documents() -> list[str]:
    """Documents that may direct current decisions: map-classified into a current-authority class,
    plus the root control documents the map itself lists as CANONICAL, MINUS anything that is
    simultaneously in the historical family (a review is evidence even if a row mentions it)."""
    out = set(classified(CURRENT_AUTHORITY_CLASSES))
    out -= set(implementation_review_documents())
    return sorted(out)


def banner_required_documents() -> list[str]:
    """Everything historical that could be mistaken for authority: superseded/quarantined map
    classes + every implementation review + pre-reset docs-root documents."""
    sup = {p for p, c in classified(("SUPERSEDED", "QUARANTINED_GUIDANCE")).items()}
    return sorted(sup | set(implementation_review_documents()))


def root_control_like_documents() -> list[str]:
    return sorted(f for f in tracked_files()
                  if "/" not in f and f.endswith((".md", ".txt")))


def agent_files() -> list[str]:
    return sorted(f for f in tracked_files() if re.match(r"\.claude/agents/.+\.md$", f))


def compatibility_agent_files() -> list[str]:
    return sorted(f for f in tracked_files() if re.match(r"\.codex/agents/.+\.md$", f))


# ------------------------------------------------------------------ test populations

def canonical_test_modules() -> list[str]:
    return sorted(f for f in tracked_files()
                  if re.match(r"eval/(tests/)?test_[a-z0-9_]+\.py$", f))


def control_guard_modules() -> list[str]:
    """Test modules that guard the control plane - discovered by what they REFERENCE, never by a
    typed list: a module that reads control documents or control scripts is a control guard."""
    out = []
    marker = re.compile(
        r"CANONICAL-DOCUMENTS|CLAUDE\.md|PRODUCT\.md|ARCHITECTURE\.md|CURRENT\.md|"
        r"IMPLEMENTATION-REGISTRY|IMPLEMENTATION-SURFACE|TOOL-ACCESS-POLICY|"
        r"U-HANDOFF-1-ACCEPTANCE|LEGACY-DISPOSITION|PHASE-OUTPUTS|SUITE-RESULT|"
        r"TRANSITION-EVENT-AUDIT|EFFECT-PATH-INVENTORY|baseline-manifest|"
        r"suite_result|update_current_status|check_env|finalize_status|clean_clone_gate|"
        r'"implementation"|AUTO-LOADED-GUIDANCE'
    )
    for f in canonical_test_modules():
        if marker.search((ROOT / f).read_text(encoding="utf-8")):
            out.append(f)
    return sorted(out)


def skip_xfail_sites() -> list[dict]:
    """Every static skip/xfail-capable construct in every canonical test module, by AST."""
    import ast
    sites = []
    for f in canonical_test_modules():
        tree = ast.parse((ROOT / f).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            construct = None
            if isinstance(node, ast.Call):
                fn = node.func
                dotted = ""
                while isinstance(fn, ast.Attribute):
                    dotted = "." + fn.attr + dotted
                    fn = fn.value
                if isinstance(fn, ast.Name):
                    dotted = fn.id + dotted
                if dotted in ("pytest.skip", "pytest.xfail", "pytest.importorskip",
                              "unittest.skip", "unittest.skipIf", "unittest.skipUnless"):
                    construct = dotted
            elif isinstance(node, ast.Attribute):
                # decorators like pytest.mark.skip / skipif / xfail
                dotted = []
                fn = node
                while isinstance(fn, ast.Attribute):
                    dotted.append(fn.attr)
                    fn = fn.value
                if isinstance(fn, ast.Name):
                    dotted.append(fn.id)
                path = ".".join(reversed(dotted))
                if re.fullmatch(r"pytest\.mark\.(skip|skipif|xfail)", path):
                    construct = path
            if construct:
                sites.append({"file": f, "line": node.lineno, "construct": construct})
        # module-level pytestmark
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for t in node.targets:
                    if isinstance(t, ast.Name) and t.id == "pytestmark":
                        sites.append({"file": f, "line": node.lineno, "construct": "pytestmark"})
    # dedupe (a decorator Attribute may be walked once per use site already; keep unique)
    uniq = {(s["file"], s["line"], s["construct"]): s for s in sites}
    return sorted(uniq.values(), key=lambda s: (s["file"], s["line"]))


def absolute_line_citations() -> list[dict]:
    """Every `<file>.py:<number>` citation in tracked markdown - brittle by construction."""
    out = []
    for f in tracked_files():
        if not f.endswith(".md"):
            continue
        text = (ROOT / f).read_text(encoding="utf-8")
        for m in re.finditer(r"([A-Za-z0-9_]+\.py):(\d{2,})", text):
            out.append({"file": f, "line": text[: m.start()].count("\n") + 1,
                        "citation": m.group(0)})
    return out


def negative_assertion_functions() -> list[dict]:
    """Every test function in every canonical test module whose asserts include a NEGATIVE
    membership/search claim (vacuously true over an empty population), plus whether the same
    function proves its population. Discovered by AST - the hand-typed NEGATIVE_ASSERTION_TESTS
    dict this replaces protected six tests and could never learn a seventh.

    Scope: only functions that GATHER A CORPUS (glob/read/parse/load over files) are
    vacuous-risk - a negative over a value constructed inside the same test cannot be emptied by
    a parser returning nothing. The corpus-gathering predicate is what keeps this discovery
    precise instead of flagging every string-scrub test in the suite."""
    import ast
    out = []
    for f in canonical_test_modules():
        tree = ast.parse((ROOT / f).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_"):
                continue
            negative = False
            for a in ast.walk(node):
                if isinstance(a, ast.Assert):
                    for c in ast.walk(a.test):
                        if isinstance(c, ast.Compare) and any(
                            isinstance(op, ast.NotIn) for op in c.ops
                        ):
                            # `x not in <literal>` is not population-dependent; flag only
                            # comparisons against a NAME/CALL population
                            if not isinstance(c.comparators[0], (ast.Constant, ast.List,
                                                                 ast.Tuple, ast.Set, ast.Dict)):
                                negative = True
            if not negative:
                continue
            src = ast.get_source_segment((ROOT / f).read_text(encoding="utf-8"), node) or ""
            if not re.search(
                r"\.r?glob\(|read_text\(|ls-files|parse_tables|occurrences\(|"
                r"\btransitions\(\)|manifest\.load\(|spec_corpus|safe_load\(|iterdir\(",
                src,
            ):
                continue  # local-value negative: cannot be emptied by a parser
            # A function proves its population by: an explicit require_population call, a length
            # floor, OR a POSITIVE assertion over the same gathered data (a positive membership or
            # equality that would fail on an empty/degenerate corpus). Purely-negative functions
            # are the vacuous-risk class.
            positive = False
            for a in ast.walk(node):
                if isinstance(a, ast.Assert):
                    for c in ast.walk(a.test):
                        if isinstance(c, ast.Compare) and any(
                            isinstance(op, (ast.In, ast.Eq, ast.Gt, ast.GtE)) for op in c.ops
                        ):
                            positive = True
            proves = positive or bool(re.search(
                r"require_population|ev\.require_population|len\([^)]*\)\s*[>=]=?\s*\d", src))
            out.append({"file": f, "function": node.name, "proves_population": proves})
    return out
