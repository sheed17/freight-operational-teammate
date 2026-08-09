"""Bootstrap, hermeticity and U-HANDOFF-1B correction guards.

The independent clean-clone rehearsal proved the repository was reproducible only on the machine
that authored it: an unenforced Python floor, an undeclared dependency, 46 tests reading a
gitignored workspace database, and a status guard that verified test COUNTS rather than test
RESULTS. Every guard here holds one of those corrections in place, and the M-4 guards hold the
re-grounded figures (transition/event audit, effect-path inventory, table partition, graph
consistency, banners, frontmatter) against drift.

Discipline as everywhere in this suite: discover, never enumerate; exact sets, not counts;
negative assertions over proven populations; whole-token matching.
"""

from __future__ import annotations

import ast
import itertools
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from check_env import check as env_check, required_floor  # noqa: E402

IMPL = ROOT / "docs" / "implementation"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def require_population(items, what: str):
    assert items, f"no {what} to assert over - this test would pass vacuously"
    return items


# ============================================================ H-1: bootstrap

def test_python_below_the_floor_fails_immediately_and_compliant_proceeds():
    """Acceptance 1+2: the check refuses 3.10 with the exact versions, accepts the floor."""
    floor = required_floor((ROOT / "pyproject.toml").read_text())
    assert floor >= (3, 11), f"the declared floor {floor} regressed below 3.11"
    assert env_check((3, 10)) == 1, "Python 3.10 was allowed to proceed to dependency resolution"
    assert env_check((floor[0], floor[1])) == 0, "the exact floor version was refused"
    assert env_check(None) == 0, "the ACTIVE interpreter fails its own floor - the venv is wrong"


def test_the_bootstrap_docs_run_the_env_check_before_installing():
    for f in (ROOT / "README.md", ROOT / "CLAUDE.md"):
        text = read(f)
        assert "check_env.py" in text, f"{f.name} no longer runs the fail-fast env check"
    readme = read(ROOT / "README.md")
    check_pos = readme.find("check_env.py")
    install_pos = readme.find("pip install -e")
    assert 0 < check_pos < install_pos, "README runs pip install before the env check"


STDLIB_OK = {
    "annotations",  # __future__
}
# import name -> distribution that declares it
IMPORT_TO_DIST = {
    "pydantic": "pydantic", "instructor": "instructor", "anthropic": "anthropic",
    "openai": "openai", "fitz": "pymupdf", "pymupdf": "pymupdf", "yaml": "pyyaml",
    "dotenv": "python-dotenv", "reportlab": "reportlab", "PIL": "pillow",
    "websocket": "websocket-client",
    "browser_use": "browser-use",  # optional extra [browser-agent]
    "pytest": "pytest",            # dev extra
}


def _declared_distributions() -> set[str]:
    text = (ROOT / "pyproject.toml").read_text()
    return {m.group(1).lower() for m in re.finditer(r'"([A-Za-z0-9_.\[\]-]+?)[><=~!]', text)}


def test_every_third_party_import_in_src_is_declared():
    """Acceptance 3: the websocket lesson, generalised. A clean install must satisfy every
    import; a dependency present only in the developer's environment is a clean-clone failure
    waiting to be discovered by whoever clones next."""
    import sys as _sys
    stdlib = set(_sys.stdlib_module_names)
    declared = _declared_distributions()
    declared_bases = {re.sub(r"\[.*\]", "", d) for d in declared}
    offenders, seen = [], set()
    for f in (ROOT / "src").rglob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [node.module.split(".")[0]]
            for m in mods:
                if m in stdlib or m in STDLIB_OK or m == "freight_recon" or m in seen:
                    continue
                seen.add(m)
                dist = IMPORT_TO_DIST.get(m)
                if dist is None:
                    offenders.append(f"{f.relative_to(ROOT)}: import {m} has no known distribution mapping")
                elif dist.lower() not in declared_bases:
                    offenders.append(f"{f.relative_to(ROOT)}: import {m} -> {dist} is NOT declared in pyproject.toml")
    require_population(seen, "third-party imports")
    assert not offenders, "undeclared third-party imports (the websocket defect, recurring):\n  " + "\n  ".join(offenders)
    assert "websocket-client" in declared_bases, "websocket-client left the declared dependencies"


def test_collection_succeeds_with_zero_errors():
    """Acceptance 5 (in-checkout form; the clean-clone gate proves the fresh-venv form)."""
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "eval/", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert "error" not in r.stdout.lower().split("=")[-1], f"collection errors:\n{r.stdout[-800:]}"
    m = re.search(r"(\d+) tests? collected", r.stdout)
    assert m and int(m.group(1)) > 1000


# ============================================================ H-2: hermeticity

def test_no_test_reads_the_workspace_database_or_home_directory():
    """Acceptance 7-9: static proof over every test file. The fixture builder's docstring may
    NAME the old path (it documents the correction); no test may USE it."""
    offenders = []
    files = sorted((ROOT / "eval").rglob("test_*.py")) + [ROOT / "eval" / "conftest.py"]
    # This guard file itself is excluded: its detection patterns ARE the forbidden strings, and a
    # guard that flags its own hunting expressions is the substring-self-match defect again.
    files = [f for f in files if f.exists() and f.name != "test_bootstrap_hermeticity.py"]
    require_population(files, "test files")
    for f in files:
        text = f.read_text(encoding="utf-8")
        for pat, label in [
            (r"active_workspace", "the developer-local workspace"),
            (r"/Users/[a-z]", "an absolute home path"),
            (r"Path\.home\(\)|expanduser\(", "the home directory"),
        ]:
            for m in re.finditer(pat, text):
                line = text[: m.start()].count("\n") + 1
                offenders.append(f"{f.relative_to(ROOT)}:{line}: {label}")
    assert not offenders, (
        "tests depending on developer-local state (the 46-failure clean-clone defect):\n  "
        + "\n  ".join(offenders)
    )


def test_no_test_skips_itself_when_a_database_is_absent():
    """Silently skipping on missing state would hide the hermeticity failure instead of fixing
    it - the prompt names this forbidden dodge explicitly."""
    offenders = []
    for f in sorted((ROOT / "eval" / "tests").glob("test_*.py")):
        if f.name == "test_bootstrap_hermeticity.py":
            continue  # this file quotes the forbidden pattern in order to hunt it
        text = f.read_text(encoding="utf-8")
        if re.search(r"skipif.{0,120}(exists|sqlite|workspace|database)", text, re.S | re.I):
            offenders.append(f.name)
    assert not offenders, f"tests that skip when a database is absent: {offenders}"


def test_the_legacy_fixture_is_deterministic_and_self_consistent(tmp_path):
    """Acceptance 6: two builds are byte-identical; the population equals the exported constants."""
    import hashlib
    from fixtures.legacy_workspace import (
        LEGACY_AUDIT_EVENTS, LEGACY_RUNS, build_legacy_workspace,
    )
    a = build_legacy_workspace(tmp_path / "a.db")
    b = build_legacy_workspace(tmp_path / "b.db")
    ha, hb = (hashlib.sha256(p.read_bytes()).hexdigest() for p in (a, b))
    assert ha == hb, "the legacy fixture is not byte-deterministic across builds"
    import sqlite3
    conn = sqlite3.connect(a)
    runs = conn.execute("SELECT COUNT(*) FROM workflow_runs").fetchone()[0]
    events = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    sec = conn.execute("SELECT COUNT(*) FROM security_events").fetchone()[0]
    conn.close()
    assert (runs, events, sec) == (LEGACY_RUNS, LEGACY_AUDIT_EVENTS, 0)


def test_a_clean_clone_has_no_workspace_database():
    """Acceptance 1 (fixture proof): the path is ignored AND untracked, so a clone cannot have it."""
    tracked = subprocess.run(["git", "ls-files", "data/active_workspace"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
    assert not tracked, f"workspace files are TRACKED and would ship in a clone: {tracked}"
    ignored = subprocess.run(["git", "check-ignore", "data/active_workspace/x"], cwd=ROOT,
                             capture_output=True, text=True).returncode == 0
    assert ignored, "data/active_workspace is no longer gitignored"


# ============================================================ G2: the transition/event contract
#
# The G2 targeted architecture adjudication over certified predecessor 6e8127d ruled
# INTERPRETATION C - HYBRID: the PRODUCER predicate is membership in events/registry.md sec 3, and
# the COMPLETENESS predicate is the presence of a durable write (GR-2). NEITHER READS PROSE.
#
# Interpretation B ("explicitly documented non-producing") was refused because its predicate is
# PROSE-DEPENDENT AND SELF-CERTIFYING: a row exempts itself by writing the right words in the Event
# column. That failure is not hypothetical - 07-conflict:CF-7 and 09-exception:EC-7 both carried
# "(no state change)", the old parser honoured it as a non-production declaration, and BOTH ROWS IN
# FACT PERFORM DURABLE WRITES. Two real defects were being laundered into legal exemptions.
#
# The adjudicated defects these guards hold closed:
#   G2-D1  the old classifier's `else` branch was a FALSE GREEN - it never checked that the cell
#          named a canonical event, so 12-rule:RU-8 (Event cell "(Exception raised)") passed as
#          evented while naming nothing at all. UNKNOWN CLASSIFICATION IS NOW A FAILURE.
#   G2-D3  01-work-item:WI-14 said "same guards as WI-5/6/7/3/12 respectively" over FOUR target
#          states and FIVE references. Ownership is resolved by TARGET STATE, never positionally.
#   G2-D5  no column-count guard existed. 03-external-effect-grant:EF-5x carried 7 cells against 8
#          headers; a cell missing BEFORE the Event column would have shifted classification
#          silently. The row is repaired and the guard is here.
#   G2-D7  the anti-"24" guard collided with the truth - the computed count of NON-PRODUCER
#          transitions is ALSO 24, a different quantity that happens to share a value.
#   G2-D11 nothing asserted the sec-3 producer map and the 134-row corpus were bijective in BOTH
#          directions.
#   G2-D12 the audit recorded 121/13; the corrected as-found split was 120/14.
#   G2-D14 the audit classified EF-3 as DOCUMENTED_NON_PRODUCING; it is the declared sec-3 producer
#          of the EXISTING canonical event EffectExecuted.
#
# Discipline as everywhere here: exact sets, never counts; positive anchors before every negative
# assertion; whole-token matching; and no guard may pass by measuring nothing.

SPECS = ROOT / "docs" / "specifications"
MACHINES = SPECS / "state-machines"

CLASS_TOKENS = ("NON_PRODUCING", "DELEGATES_TO", "CONSUMES", "EVENT_REQUIRED")
CLASS_TOKEN_RE = re.compile(r"\b(" + "|".join(CLASS_TOKENS) + r"):([A-Za-z0-9_,;=-]+)")
NON_PRODUCING_REASONS = {"ENUMERATED_NO_OP", "GR1_ILLEGAL_REFUSAL"}
# The only declared deviation from "exactly one producer transition" (events/registry.md sec 9).
COORDINATION_EVENTS = {"RealityEstablished", "ConflictRaised", "PolicyVersionChanged",
                       "IllegalTransitionAttempted"}


def _audit() -> dict:
    return yaml.safe_load(read(IMPL / "TRANSITION-EVENT-AUDIT.yaml"))


def _bare(cell: str) -> bool:
    return re.sub(r"[*`\s]", "", cell) in ("", "—", "-", "–")


def _expand_producers(field: str | None) -> list[str]:
    """The registry's own shorthand: `PL-7v/9v` -> [PL-7v, PL-9v]; `IB-2/2r/2h` -> three ids. A
    bare suffix inherits the preceding machine prefix."""
    out: list[str] = []
    prefix = None
    for tok in (field or "").split("/"):
        tok = tok.strip()
        m = re.match(r"^([A-Z]{2})-(\d+[a-z]*)", tok)
        if m:
            prefix = m.group(1)
            out.append(f"{prefix}-{m.group(2)}")
            continue
        m = re.match(r"^(\d+[a-z]*)", tok)
        if m and prefix:
            out.append(f"{prefix}-{m.group(1)}")
    return out


def _event_registry() -> dict:
    """events/registry.md sec 3. F15 is a LENS over cross-machine consumption and declares no
    contract (sec 9); counting it would double-count every event it names."""
    section = read(SPECS / "events" / "registry.md")
    section = section.split("## 3. CANONICAL EVENT LIST")[1].split("## 4.")[0]
    declared = []
    for line in section.split("\n"):
        fam = re.match(r"^\*\*(F\d+)\s", line)
        if not fam:
            continue
        for m in re.finditer(r"`([A-Za-z][A-Za-z0-9]*)`(‡?)(?:\(([^)]*)\))?", line):
            declared.append({"family": fam.group(1), "name": m.group(1),
                             "coordination": m.group(2) == "‡",
                             "producers": _expand_producers(m.group(3))})
    contracts = [e for e in declared if e["family"] != "F15"]
    owned = [e for e in contracts if int(e["family"][1:]) <= 13]
    producers_of: dict[str, set[str]] = {}
    for e in owned:
        for tid in e["producers"]:
            producers_of.setdefault(tid, set()).add(e["name"])
    return {"declared": declared, "contracts": contracts, "owned": owned,
            "corpus": [e["name"] for e in contracts], "producers_of": producers_of}


def _canonical_states() -> set[str]:
    text = read(MACHINES / "registry.md")
    text = text.split("## 4. CANONICAL STATE REGISTRY")[1].split("## 5.")[0]
    return set(re.findall(r"`([A-Z][A-Z_]*)`", text))


def _states_in(fragment: str, states: set[str]) -> set[str]:
    return {t for t in re.findall(r"[A-Z][A-Z_]{2,}", fragment) if t in states}


def _transition_rows() -> list[dict]:
    r"""Every transition row across the 13 machine files, with its From-To / Writes / Event cells
    resolved BY HEADER NAME (the columns are not in the same order in every machine) and its cell
    count recorded against its header count (G2-D5). Escape-aware split on `(?<!\\)\|` - the
    U-HANDOFF-1B correction, without which `H\\|S` in the Trig column shifts every later cell."""
    rows = []
    for f in sorted(MACHINES.glob("*.machine.md")):
        short = f.name.replace(".machine.md", "")
        headers = None
        for lineno, line in enumerate(f.read_text(encoding="utf-8").split("\n"), 1):
            if not line.strip().startswith("|"):
                headers = None
                continue
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line)[1:-1]]
            if not cells:
                continue
            if re.sub(r"[*\s]", "", cells[0]) == "ID":
                headers = [re.sub(r"[*`\s]", "", h).lower() for h in cells]
                continue
            if headers is None or re.match(r"^[-: ]+$", cells[0]):
                continue
            tid = re.sub(r"[*`\s]", "", cells[0])
            if not re.fullmatch(r"[A-Z]{2}-\d+[a-z]?", tid):
                continue

            def col(pred, _cells=cells, _headers=headers):
                i = next((i for i, h in enumerate(_headers) if pred(h)), None)
                return _cells[i] if i is not None and i < len(_cells) else ""

            rows.append({
                "key": f"{short}:{tid}", "id": tid, "machine": short, "line": lineno,
                "n_cells": len(cells), "n_headers": len(headers),
                "from_to": col(lambda h: h.startswith("from")),
                "writes": col(lambda h: h.startswith("writes") or h == "prov"),
                "event": col(lambda h: h.startswith("event")),
            })
    return rows


def _durable_write(row: dict, states: set[str]) -> bool:
    """GR-2's subject. A row writes durably iff its To side names a canonical state its From side
    does not, OR its Writes / Prov column is non-empty. Both read STRUCTURED columns."""
    if not _bare(row["writes"]):
        return True
    if "→" not in row["from_to"]:
        return False
    left, right = row["from_to"].split("→", 1)
    return bool(_states_in(right, states) - _states_in(left, states))


def _classify(rows: list[dict], producers_of: dict[str, set[str]]) -> dict:
    """The G2 classifier. sec-3 membership decides PRODUCER. Every other row MUST carry exactly one
    structured token. A row the classifier cannot decide is an ERROR - never a pass, never a skip."""
    classified, errors = {}, []
    for row in rows:
        tokens = CLASS_TOKEN_RE.findall(row["event"])
        if row["id"] in producers_of:
            if tokens:
                errors.append(
                    f"{row['key']}: a declared sec-3 producer carries a {tokens[0][0]} token - "
                    "producer identity is decided by the registry, never by the row"
                )
            classified[row["key"]] = {"class": "PRODUCER", "arg": None, "row": row}
            continue
        if len(tokens) != 1:
            errors.append(
                f"{row['key']} (line {row['line']}): {len(tokens)} classification tokens in Event "
                f"cell {row['event'][:70]!r}. A non-producer row must carry exactly one of "
                f"{list(CLASS_TOKENS)}. UNKNOWN CLASSIFICATION IS A BUILD FAILURE - it may never "
                "silently PASS or SKIP."
            )
            continue
        classified[row["key"]] = {"class": tokens[0][0], "arg": tokens[0][1], "row": row}
    return {"classified": classified, "errors": errors}


def _resolve_delegation(spec: str, rows_by_id: dict, producers_of: dict, states: set[str]) -> dict:
    """`BLOCKED=WI-5,WI-6;AWAITING_HUMAN=WI-7` -> {state: owner_event}. Ownership is resolved by
    TARGET STATE and never positionally (G2-D3): WI-5 and WI-6 BOTH target BLOCKED, so the word
    "respectively" over four states and five references could not decide it."""
    resolution, errors = {}, []
    for branch in [b for b in spec.split(";") if b]:
        if "=" not in branch:
            errors.append(f"malformed delegation branch {branch!r} - expected <TO_STATE>=<ids>")
            continue
        state, ids = branch.split("=", 1)
        targets = [t for t in ids.split(",") if t]
        if state not in states:
            errors.append(f"{state!r} is not a canonical state (state-machines/registry.md sec 4)")
        if not targets:
            errors.append(f"{state}: ZERO delegation targets - delegation may never resolve to "
                          "zero owners")
            continue
        owners: set[str] = set()
        for tid in targets:
            if tid not in rows_by_id:
                errors.append(f"{state}: delegation target {tid} does not exist in the corpus")
                continue
            if tid not in producers_of:
                errors.append(f"{state}: delegation target {tid} is not a sec-3 producer of any "
                              "event, so it owns nothing to delegate")
                continue
            target_to = _states_in(rows_by_id[tid]["from_to"].split("→", 1)[-1], states)
            if state not in target_to:
                errors.append(f"{state}: delegation target {tid} does not itself transition to "
                              f"{state} (its To set is {sorted(target_to)}) - positional matching "
                              "is forbidden; targets are matched by target state")
            owners |= producers_of[tid]
        if len(owners) == 0:
            errors.append(f"{state}: delegation resolves to ZERO event owners")
        elif len(owners) > 1:
            errors.append(f"{state}: delegation resolves to {sorted(owners)} - DUPLICATE/AMBIGUOUS "
                          "ownership. Exactly one valid delegation owner is required.")
        else:
            resolution[state] = next(iter(owners))
    return {"resolution": resolution, "errors": errors}


def _g2_state() -> dict:
    """One parse, shared by the guards below, so they cannot disagree with each other."""
    registry = _event_registry()
    rows = _transition_rows()
    states = _canonical_states()
    return {"registry": registry, "rows": rows, "states": states,
            "rows_by_id": {r["id"]: r for r in rows},
            "result": _classify(rows, registry["producers_of"])}


# ------------------------------------------------------------ corpus integrity

def test_the_transition_corpus_is_positively_anchored_and_every_row_is_column_aligned():
    """G2-D5. The 134 rows are anchored by EXACT SET EQUALITY against the registered expectation -
    a count match with different members must fail - and every row's cell count must equal its
    table's header count. A row short one cell BEFORE the Event column shifts every later value and
    silently changes its classification; EF-5x was exactly that row."""
    sys.path.insert(0, str(ROOT / "eval"))
    from phase0 import manifest

    rows = require_population(_transition_rows(), "transition rows")
    keys = [r["key"] for r in rows]
    assert len(keys) == len(set(keys)), (
        f"duplicate transition keys: {sorted(k for k in set(keys) if keys.count(k) > 1)}"
    )
    expected = {f"{f.replace('.machine.md', '')}:{t}"
                for f, ids in manifest.canonical_expected()["transitions"].items() for t in ids}
    assert len(expected) == 134, f"the registered expectation drifted from 134: {len(expected)}"
    assert set(keys) == expected, (
        f"transition corpus drifted: corpus-only={sorted(set(keys) - expected)}, "
        f"registered-only={sorted(expected - set(keys))}"
    )
    misaligned = [f"{r['key']} (line {r['line']}): {r['n_cells']} cells vs {r['n_headers']} headers"
                  for r in rows if r["n_cells"] != r["n_headers"]]
    assert not misaligned, (
        "transition rows whose cell count differs from their header count - a missing cell shifts "
        "every later column and can change an Event classification silently:\n  "
        + "\n  ".join(misaligned)
    )


def test_no_new_canonical_event_was_minted_and_the_total_is_still_98():
    """The frozen registry. AC-TRACE-000 asserts 98/98 and five canonical documents repeat it.
    Exact set equality against the registered expectation, so a swap at constant total fails."""
    sys.path.insert(0, str(ROOT / "eval"))
    from phase0 import manifest

    registry = _event_registry()
    owned = {e["name"] for e in registry["owned"]}
    assert len(owned) == 98, f"the F1-F13 canonical event total is {len(owned)}, not 98"
    assert owned == manifest.expected_event_names(), (
        "the canonical event set drifted from the registered expectation: "
        f"registry-only={sorted(owned - manifest.expected_event_names())}, "
        f"expected-only={sorted(manifest.expected_event_names() - owned)}"
    )
    security = [e["name"] for e in registry["contracts"] if e["family"] == "F14"]
    assert len(security) == 13, f"the F14 security-event count is {len(security)}, not 13"
    assert not [e for e in registry["declared"] if e["family"] == "F15" and e["producers"]], (
        "F15 declared a producer transition - it is a lens over cross-machine consumption and "
        "declares no contract (events/registry.md sec 9)"
    )


# ------------------------------------------------------------ the producer map <-> corpus bijection

def test_the_producer_map_and_the_transition_corpus_are_bijective():
    """G2-D11. The sec-3 map, the corpus and the classification form ONE relation, asserted in both
    directions. Zero-owner and duplicate-owner are separate prohibitions, both fail-closed."""
    g2 = _g2_state()
    registry, rows = g2["registry"], g2["rows"]
    owned = require_population(registry["owned"], "canonical event contracts")
    corpus_ids = {r["id"] for r in rows}

    # zero-owner prohibition: every canonical event has at least one producer, and it exists.
    orphans = [e["name"] for e in owned if not e["producers"]]
    assert not orphans, f"canonical events with NO declared producer transition: {sorted(orphans)}"
    dangling = sorted({tid for e in owned for tid in e["producers"]} - corpus_ids)
    assert not dangling, (
        f"declared producer transition(s) that do not exist in the 134-row corpus: {dangling}"
    )

    # duplicate-owner prohibition: declared once, and (unless a declared coordination event) the
    # producers all belong to ONE machine - registry sec 182, "no event is emitted by two
    # incompatible transitions".
    names = [e["name"] for e in owned]
    assert len(names) == len(set(names)), (
        f"canonical event(s) declared more than once: "
        f"{sorted(n for n in set(names) if names.count(n) > 1)}"
    )
    spanning = [(e["name"], e["producers"]) for e in owned
                if not e["coordination"] and len({p.split("-")[0] for p in e["producers"]}) > 1]
    assert not spanning, (
        "non-coordination event(s) whose producers span more than one machine - only the declared "
        f"coordination events may do that: {spanning}"
    )
    declared_coordination = {e["name"] for e in registry["contracts"] if e["coordination"]}
    assert declared_coordination == COORDINATION_EVENTS, (
        f"the declared coordination-event set drifted: {sorted(declared_coordination)}"
    )

    # reverse direction: every producer row must still NAME a canonical event in its Event cell, so
    # a producer cannot go silent in the specification the map is derived from. EF-3 was silent -
    # it documented the event it does NOT emit and omitted the one it owns (G2-D14).
    corpus_names = set(registry["corpus"])
    silent = []
    for tid in sorted(registry["producers_of"]):
        cell = g2["rows_by_id"][tid]["event"]
        if not [n for n in re.findall(r"`([A-Za-z][A-Za-z0-9]*)", cell) if n in corpus_names]:
            silent.append(f"{g2['rows_by_id'][tid]['key']}: {cell[:70]!r}")
    assert not silent, (
        "declared producer transition(s) naming no canonical event in their Event cell:\n  "
        + "\n  ".join(silent)
    )


def test_ef_3_is_a_producer_of_the_existing_effect_executed_event():
    """G2-D2 / G2-D14, pinned by name. Two independent authorities already assign the event -
    events/registry.md sec 3 `EffectExecuted`(EF-3) and 03-external-effect-grant-events.md - so
    this needed NO new event type and NO naming discretion. The old cell was true about
    EffectAttempted and silently omitted the event the row owns; a second EffectAttempted would be
    a Sev-0 orphan (M3 sec 19/38), which is an argument against duplicating ONE event, not against
    emitting the row's own."""
    registry = _event_registry()
    assert registry["producers_of"].get("EF-3") == {"EffectExecuted"}, (
        f"EF-3's sec-3 ownership drifted: {registry['producers_of'].get('EF-3')}"
    )
    cell = _g2_state()["rows_by_id"]["EF-3"]["event"]
    assert "`EffectExecuted`" in cell, f"EF-3 no longer names EffectExecuted: {cell!r}"
    family = read(SPECS / "events" / "03-external-effect-grant-events.md")
    assert "EffectExecuted" in family and "EF-3" in family, (
        "the M3 event family file no longer corroborates the EffectExecuted/EF-3 assignment"
    )
    # PL-10 (M2) names EffectExecuted but does NOT own it - it consumes the co-transition.
    assert "EF-3" not in read(IMPL / "TRANSITION-EVENT-AUDIT.yaml").split("EVENT_REQUIRED")[1].split("CONSUMES")[0], (
        "EF-3 is recorded as an open event obligation - it is a producer with an existing event"
    )


# ------------------------------------------------------------ classification, fail-closed

def test_every_transition_is_classified_and_unknown_classification_is_a_failure():
    """G2-D1. The old classifier assigned rows to EVENTED through an `else` branch that never
    checked the cell named a canonical event. Here every row resolves to a member of a CLOSED
    vocabulary or the build fails."""
    g2 = _g2_state()
    assert not g2["result"]["errors"], (
        "unclassified or malformed transition rows:\n  " + "\n  ".join(g2["result"]["errors"])
    )
    classified = require_population(g2["result"]["classified"], "classified transitions")
    assert len(classified) == 134, f"only {len(classified)} of 134 rows classified"
    counts: dict[str, int] = {}
    for rec in classified.values():
        counts[rec["class"]] = counts.get(rec["class"], 0) + 1
    audit = _audit()
    assert counts == audit["computed_classification"], (
        f"the audit's classification drifted from the specification: computed={counts}, "
        f"recorded={audit['computed_classification']}"
    )
    assert sum(counts.values()) == audit["meta"]["total_transitions"] == 134


def test_non_producing_rows_are_structurally_declared_and_perform_zero_durable_writes():
    """A NON_PRODUCING row that declares a durable write FAILS. Prose never establishes
    non-production: 'no state change' is not a classification token and carries no weight."""
    g2 = _g2_state()
    marked = require_population(
        {k: v for k, v in g2["result"]["classified"].items() if v["class"] == "NON_PRODUCING"},
        "NON_PRODUCING transitions",
    )
    offenders = []
    for key, rec in sorted(marked.items()):
        if rec["arg"] not in NON_PRODUCING_REASONS:
            offenders.append(f"{key}: reason code {rec['arg']!r} is outside the closed set "
                             f"{sorted(NON_PRODUCING_REASONS)}")
        if _durable_write(rec["row"], g2["states"]):
            offenders.append(
                f"{key}: declared NON_PRODUCING but performs a durable write "
                f"(From->To {rec['row']['from_to'][:40]!r}, Writes {rec['row']['writes'][:40]!r})"
            )
    assert not offenders, "invalid NON_PRODUCING declarations:\n  " + "\n  ".join(offenders)
    recorded = {m["key"]: m["reason_code"]
                for c in _audit()["classes"] if c["name"] == "NON_PRODUCING" for m in c["members"]}
    assert {k: v["arg"] for k, v in marked.items()} == recorded, (
        f"the audit's NON_PRODUCING members drifted: computed={ {k: v['arg'] for k, v in marked.items()} }, "
        f"recorded={recorded}"
    )


def test_delegation_resolves_to_exactly_one_owner_per_target_state():
    """G2-D3. Every target must exist, be a producer, and itself transition to the state it is
    delegated for; every branch must resolve to EXACTLY ONE event; and the declared states must
    cover the delegating row's own To set exactly - no branch may be silently dropped."""
    g2 = _g2_state()
    marked = require_population(
        {k: v for k, v in g2["result"]["classified"].items() if v["class"] == "DELEGATES_TO"},
        "DELEGATES_TO transitions",
    )
    offenders = []
    for key, rec in sorted(marked.items()):
        got = _resolve_delegation(rec["arg"], g2["rows_by_id"], g2["registry"]["producers_of"],
                                 g2["states"])
        offenders += [f"{key}: {e}" for e in got["errors"]]
        own_to = _states_in(rec["row"]["from_to"].split("→", 1)[-1], g2["states"])
        if set(got["resolution"]) != own_to:
            offenders.append(
                f"{key}: declared branches {sorted(got['resolution'])} do not cover its own To set "
                f"{sorted(own_to)} exactly"
            )
    assert not offenders, "invalid DELEGATES_TO declarations:\n  " + "\n  ".join(offenders)
    recorded = {m["key"]: {s: b["owner_event"] for s, b in m["resolution"].items()}
                for c in _audit()["classes"] if c["name"] == "DELEGATES_TO" for m in c["members"]}
    computed = {k: _resolve_delegation(v["arg"], g2["rows_by_id"],
                                       g2["registry"]["producers_of"], g2["states"])["resolution"]
                for k, v in marked.items()}
    assert computed == recorded, f"delegation ownership drifted: {computed} vs {recorded}"
    # the positional reading is gone from the corpus, not merely unused
    for f in sorted(MACHINES.glob("*.machine.md")):
        assert "respectively" not in f.read_text(encoding="utf-8"), (
            f"{f.name} resolves delegation positionally again ('respectively') - WI-14 has four "
            "target states and five references, so positional matching cannot decide it"
        )


def test_consuming_rows_name_an_event_owned_by_a_different_transition():
    """The co-transition rows. Correct architecture, not a violation - registry sec 182 gives the
    event ONE producer and makes the other machine a consumer. The guard proves the consumed event
    exists and that the consuming row is NOT its producer."""
    g2 = _g2_state()
    marked = require_population(
        {k: v for k, v in g2["result"]["classified"].items() if v["class"] == "CONSUMES"},
        "CONSUMES transitions",
    )
    corpus = set(g2["registry"]["corpus"])
    offenders = []
    for key, rec in sorted(marked.items()):
        names = [n for n in rec["arg"].split(",") if n]
        if not names:
            offenders.append(f"{key}: CONSUMES names no event")
        for name in names:
            if name not in corpus:
                offenders.append(f"{key}: consumes {name!r}, which is not a canonical event")
            elif name in g2["registry"]["producers_of"].get(rec["row"]["id"], set()):
                offenders.append(f"{key}: declares it CONSUMES {name}, which it actually OWNS")
    assert not offenders, "invalid CONSUMES declarations:\n  " + "\n  ".join(offenders)
    recorded = {m["key"]: m["consumes"]
                for c in _audit()["classes"] if c["name"] == "CONSUMES" for m in c["members"]}
    computed = {k: [n for n in v["arg"].split(",") if n] for k, v in marked.items()}
    assert computed == recorded, f"the audit's CONSUMES members drifted: {computed} vs {recorded}"


def test_every_durable_write_is_recorded_by_an_event_or_a_registered_open_obligation():
    """GR-2's converse - 'no state change without its event'. A durable-writing row must be a sec-3
    producer, consume a co-transitioned event, or carry a REGISTERED open obligation. There is no
    fourth option and no silent exemption."""
    g2 = _g2_state()
    classified = require_population(g2["result"]["classified"], "classified transitions")
    durable = require_population(
        [k for k, v in classified.items() if _durable_write(v["row"], g2["states"])],
        "durable-writing transitions",
    )
    unrecorded = [k for k in durable
                  if classified[k]["class"] not in
                  ("PRODUCER", "CONSUMES", "DELEGATES_TO", "EVENT_REQUIRED")]
    assert not unrecorded, f"durable writes with no event and no recorded obligation: {unrecorded}"
    open_rows = sorted(k for k in durable if classified[k]["class"] == "EVENT_REQUIRED")
    recorded = sorted(m for c in _audit()["classes"] if c["name"] == "EVENT_REQUIRED"
                      for m in c["members"])
    assert open_rows == recorded, (
        f"the open GR-2 violations drifted: computed={open_rows}, recorded={recorded}"
    )


def test_the_founder_gated_event_obligations_are_explicit_and_cannot_be_silently_discharged():
    """The seven durable writes no canonical event records. Each carries a registered obligation id
    that is NOT an event-shaped name and is NOT in the canonical corpus - a placeholder masquerading
    as a canonical event name is exactly what the founder/architect boundary forbids. While any
    obligation is open, the audit may not record a discharged status."""
    g2 = _g2_state()
    audit = _audit()
    obligations = require_population(audit["founder_gated_event_obligations"],
                                     "founder-gated event obligations")
    by_id = {o["id"]: o for o in obligations}
    corpus = set(g2["registry"]["corpus"])
    marked = {k: v for k, v in g2["result"]["classified"].items() if v["class"] == "EVENT_REQUIRED"}
    assert {v["arg"] for v in marked.values()} == set(by_id), (
        f"obligation ids in the specs {sorted(v['arg'] for v in marked.values())} do not match the "
        f"registered obligations {sorted(by_id)}"
    )
    offenders = []
    for oid, obligation in sorted(by_id.items()):
        if oid in corpus or re.fullmatch(r"[A-Z][A-Za-z0-9]*", oid):
            offenders.append(f"{oid}: reads as a canonical event NAME - obligations record the "
                             "missing fact, they never mint a name")
        for field in ("transition", "durable_write", "semantic_obligation", "decision_required"):
            if not str(obligation.get(field, "")).strip():
                offenders.append(f"{oid}: missing {field} - the gated decision must stay explicit")
        if obligation["transition"] not in marked:
            offenders.append(f"{oid}: names {obligation['transition']}, which is not EVENT_REQUIRED")
    assert not offenders, "invalid founder-gated obligations:\n  " + "\n  ".join(offenders)
    assert audit["meta"]["open_founder_gated_obligations"] == len(obligations)
    assert audit["meta"]["status"] == "G2_PARTIALLY_DISCHARGED_FOUNDER_GATED", (
        f"G2 records status {audit['meta']['status']!r} while {len(obligations)} founder-gated "
        "event obligations are open - G2 may not be recorded discharged until they are decided"
    )
    assert audit["meta"]["canonical_events_F1_F13"] == 98


# ------------------------------------------------------------ audit + control-document truthfulness

def test_transition_event_audit_matches_the_specs():
    """The audit's exact members must equal a fresh mechanical computation - exact SETS, so a
    same-count substitution fails, and a spec edit that changes any class fails until the audit is
    re-derived. G2-D12: the retired 121/13 pair may be recorded as history, never as the finding."""
    g2 = _g2_state()
    audit = _audit()
    assert not g2["result"]["errors"], g2["result"]["errors"]
    computed = {}
    for key, rec in g2["result"]["classified"].items():
        computed.setdefault(rec["class"], set()).add(key)
    assert sum(len(v) for v in computed.values()) == audit["meta"]["total_transitions"] == 134
    recorded_classes = {c["name"]: c["members"] for c in audit["classes"]}
    for name in ("NON_PRODUCING", "DELEGATES_TO", "EVENT_REQUIRED", "CONSUMES"):
        members = require_population(recorded_classes.get(name), f"audit class {name}")
        keys = {m if isinstance(m, str) else m["key"] for m in members}
        assert computed[name] == keys, (
            f"class {name} drifted: computed-only={sorted(computed[name] - keys)}, "
            f"audit-only={sorted(keys - computed[name])}"
        )
    view = audit["producer_view"]
    assert view["producer_transitions"] == len(computed["PRODUCER"]) == 110
    assert view["non_producer_transitions"] == 134 - len(computed["PRODUCER"]) == 24
    assert view["events_with_zero_producers"] == 0
    assert view["declared_producers_absent_from_the_corpus"] == 0
    # the historical measurement stays labelled historical and is not restated as current truth
    found = audit["adjudicated_as_found"]
    assert (found["transitions_naming_a_canonical_event"],
            found["transitions_not_naming_a_canonical_event"]) == (120, 14)
    assert "HISTORICAL" in found["note"], "the as-found split lost its historical label"
    retired = {str(r["figure"]) for r in audit["retired_figures"]}
    assert {"24", "121 / 13"} <= retired, f"a retired figure left the record: {sorted(retired)}"


def test_the_retired_24_figure_does_not_reappear_in_control_documents():
    """G2-D7. The old figure was never mechanically computed. Naming it as RETIRED is allowed;
    citing it as the finding's count is not.

    THE CARVE-OUT, AND WHY IT IS NOT A DODGE. The G2 adjudication computed that exactly 24 of the
    134 rows are NOT producer transitions. That is a DIFFERENT quantity from the retired count of
    transitions naming no event, and it happens to share a value. Without this carve-out a TRUE
    sentence would trip the guard, and the only ways out would be to contort the phrasing or to
    stop stating the truth - both evidence-hiding. The carve-out therefore admits the phrase only
    when the sentence says NON-PRODUCER, which the retired figure never meant."""
    offenders = []
    for f in [ROOT / "CLAUDE.md", ROOT / "README.md", ROOT / "ARCHITECTURE.md",
              IMPL / "CURRENT.md", IMPL / "PHASE-OUTPUTS.md"]:
        text = read(f)
        for m in re.finditer(r"\b24\b(?![0-9])[^.\n]{0,50}(transitions?|event)", text):
            window = text[max(0, m.start() - 120): m.end() + 120]
            if re.search(r"retired|never mechanically", window, re.I):
                continue
            if re.search(r"non-producer|not producer transitions", window, re.I):
                continue  # the computed non-producer count - a different quantity (G2-D7)
            offenders.append(f"{f.name}: {m.group(0)!r}")
    assert not offenders, f"the uncomputed '24' figure is back as a live count: {offenders}"


def test_the_retired_naming_split_does_not_reappear_as_the_current_finding():
    """G2-D12/G2-D13 anti-drift. '13 of 134' and '121 name an event' were the pre-adjudication
    pair; the corrected AS-FOUND split is 120/14 and the current corpus is classified, not split.
    Either figure may appear as history; neither may be restated as the live finding."""
    offenders = []
    for f in [ROOT / "CLAUDE.md", ROOT / "README.md", ROOT / "ARCHITECTURE.md",
              IMPL / "CURRENT.md", IMPL / "PHASE-OUTPUTS.md", ROOT / "docs" / "product"
              / "OPEN-VALIDATION-ITEMS.md"]:
        text = read(f)
        for m in re.finditer(r"\b(?:13|121)\b\s*(?:of\s*134|transitions)[^.\n]{0,60}", text):
            window = text[max(0, m.start() - 160): m.end() + 160]
            if re.search(r"retired|superseded|historical|as[- ]found|corrected", window, re.I):
                continue
            offenders.append(f"{f.name}: {m.group(0)[:80]!r}")
    assert not offenders, (
        "the retired 121/13 naming split is being cited as the current finding:\n  "
        + "\n  ".join(offenders)
    )


# ------------------------------------------------------------ hostile cases for each adjudicated defect

def _synthetic(tid, event, writes="—", from_to="`A_STATE` → `A_STATE`"):
    return {"key": f"synthetic:{tid}", "id": tid, "machine": "synthetic", "line": 0,
            "n_cells": 8, "n_headers": 8, "from_to": from_to, "writes": writes, "event": event}


def test_hostile_an_unclassifiable_row_fails_rather_than_passing():
    """G2-D1's exact shape: a row whose Event cell names nothing canonical and carries no token.
    The old `else` branch called this EVENTED."""
    for cell in ("*(Exception raised)*", "—", "*(no state change)*", "as those", ""):
        result = _classify([_synthetic("ZZ-1", cell)], {})
        assert result["errors"] and not result["classified"], (
            f"Event cell {cell!r} was classified instead of failing - unknown classification must "
            "be a BUILD FAILURE, never a pass and never a skip"
        )
    ok = _classify([_synthetic("ZZ-1", "`NON_PRODUCING:ENUMERATED_NO_OP`")], {})
    assert not ok["errors"] and ok["classified"]["synthetic:ZZ-1"]["class"] == "NON_PRODUCING", (
        "the classifier rejects a well-formed declaration - the guard would be vacuous"
    )


def test_hostile_two_class_tokens_on_one_row_fail():
    result = _classify(
        [_synthetic("ZZ-2", "`NON_PRODUCING:ENUMERATED_NO_OP` `CONSUMES:WorkBlocked`")], {})
    assert result["errors"], "a row declaring two classes was accepted"


def test_hostile_a_producer_row_may_not_self_declare_a_class():
    """Producer identity is decided by events/registry.md sec 3. A row that could re-declare itself
    NON_PRODUCING would reintroduce prose-style self-certification with better syntax."""
    result = _classify([_synthetic("WI-1", "`NON_PRODUCING:ENUMERATED_NO_OP`")],
                       {"WI-1": {"WorkItemCreated"}})
    assert result["errors"], "a declared sec-3 producer was allowed to declare itself NON_PRODUCING"


def test_hostile_non_producing_with_a_durable_write_fails():
    """CF-7 and EC-7's exact defect: a row claiming silence while writing durably."""
    states = _canonical_states()
    by_field = _synthetic("ZZ-3", "`NON_PRODUCING:ENUMERATED_NO_OP`", writes="`severity`")
    by_state = _synthetic("ZZ-4", "`NON_PRODUCING:ENUMERATED_NO_OP`",
                          from_to="`DRAFT` → `PROPOSED`")
    assert _durable_write(by_field, states), "a non-empty Writes column was not read as durable"
    assert _durable_write(by_state, states), "a real state change was not read as durable"
    assert not _durable_write(_synthetic("ZZ-5", "x", from_to="`GRANTED` → `GRANTED`"), states), (
        "a same-state zero-write row was read as durable - AP-8 would be a false violation"
    )


def test_hostile_delegation_that_resolves_to_zero_or_several_owners_fails():
    """Zero-owner and duplicate-owner are separate prohibitions and both must fail closed."""
    g2 = _g2_state()
    rows_by_id, states = g2["rows_by_id"], g2["states"]
    producers = g2["registry"]["producers_of"]

    missing = _resolve_delegation("BLOCKED=WI-999", rows_by_id, producers, states)
    assert missing["errors"], "a delegation to a non-existent transition was accepted"

    empty = _resolve_delegation("BLOCKED=", rows_by_id, producers, states)
    assert empty["errors"], "a delegation with zero targets was accepted"

    non_producer = _resolve_delegation("BLOCKED=PL-7a", rows_by_id, producers, states)
    assert non_producer["errors"], "a delegation to a non-producing target was accepted"

    ambiguous = _resolve_delegation("BLOCKED=WI-5,WI-7", rows_by_id, producers, states)
    assert ambiguous["errors"], (
        "a delegation resolving to two different owner events was accepted - duplicate ownership "
        "must fail closed"
    )
    wrong_state = _resolve_delegation("CLOSED=WI-5", rows_by_id, producers, states)
    assert wrong_state["errors"], (
        "a delegation whose target does not transition to the declared state was accepted - that "
        "is positional matching wearing a target-state disguise"
    )
    good = _resolve_delegation("BLOCKED=WI-5,WI-6", rows_by_id, producers, states)
    assert not good["errors"] and good["resolution"] == {"BLOCKED": "WorkBlocked"}, (
        f"the real WI-14 BLOCKED branch does not resolve: {good}"
    )


def test_hostile_a_column_short_row_is_detected_rather_than_shifting_silently():
    """G2-D5. EF-5x carried 7 cells against 8 headers. The Event cell still resolved by luck; a
    cell missing BEFORE the Event column would have shifted the classification without a sound."""
    shifted = _synthetic("ZZ-6", "`CONSUMES:WorkBlocked`")
    shifted["n_cells"] = 7
    assert shifted["n_cells"] != shifted["n_headers"], "the fixture does not model the defect"
    live = [r for r in _transition_rows() if r["n_cells"] != r["n_headers"]]
    assert not live, f"a column-short row is live in the corpus again: {[r['key'] for r in live]}"


def test_hostile_the_g2_status_cannot_be_flipped_to_discharged_while_obligations_are_open():
    """The fail-closed property, asserted over the file's own contract rather than over prose."""
    audit = _audit()
    assert audit["meta"]["discharged_status_value_forbidden_while_obligations_open"] is True
    assert audit["meta"]["open_founder_gated_obligations"] > 0
    assert "DISCHARGED_FOUNDER_GATED" in audit["meta"]["status"]
    assert "PARTIALLY" in audit["meta"]["status"], (
        "G2 records a fully-discharged status while founder-gated obligations remain open"
    )


# ============================================================ M-4: table partition

def test_the_canonical_table_partition_is_exact_and_disjoint():
    """P3 widened the partition from three classes to five. The doctrine is unchanged: the classes
    must be PAIRWISE disjoint and must together explain EVERY canonical table, by membership and
    not by count - a same-count substitution must still fail. The counts below are asserted only
    after the membership equality, so they document the shape rather than standing in for it."""
    from freight_recon.migrations.phase2_tenant_first import (
        CANONICAL_TENANT_TABLES, TENANT_EXEMPT_TABLES,
    )
    from freight_recon.migrations.phase3_checkpoint import P3_EXEMPT_TABLES, P3_TENANT_TABLES
    from freight_recon.schema import CANONICAL_TABLES

    classes = {
        "migrated": set(CANONICAL_TENANT_TABLES),
        "already_tenant_first": {"autonomous_run_counters"},
        "exempt": set(TENANT_EXEMPT_TABLES),
        "p3_tenant": set(P3_TENANT_TABLES),
        "p3_exempt": set(P3_EXEMPT_TABLES),
    }
    for a, b in itertools.combinations(sorted(classes), 2):
        overlap = classes[a] & classes[b]
        assert not overlap, f"partition classes {a} and {b} overlap: {sorted(overlap)}"

    union = set().union(*classes.values())
    assert set(CANONICAL_TABLES) == union, (
        "the partition no longer explains every canonical table: "
        f"canonical-only={sorted(set(CANONICAL_TABLES) - union)}, "
        f"partition-only={sorted(union - set(CANONICAL_TABLES))}"
    )
    shape = {name: len(members) for name, members in classes.items()}
    assert shape == {"migrated": 7, "already_tenant_first": 1, "exempt": 3,
                     "p3_tenant": 2, "p3_exempt": 1}, f"the partition shape drifted: {shape}"

    text = read(IMPL / "CURRENT.md")
    assert "autonomous_run_counters" in text, (
        "CURRENT.md hides the eighth tenant-first table again (the rehearsal's 7+3-vs-11 finding)"
    )
    for t in sorted(union):
        assert t in text, f"CURRENT.md's partition no longer names {t}"


# ============================================================ M-4: effect-path inventory

def test_the_effect_path_inventory_is_exact_and_fully_classified():
    """M-4, re-grounded at P4. The original guard pinned the SIX live-write paths. P4 has now
    executed the REMOVE_BEFORE_ENABLE disposition on four of them (EP-6/7/9/10), so this guard is
    REPLACED (rule 20) with the post-cutover truth AND a stronger check: the four are proven GONE
    from disk, and the live-write set is pinned to the two ADAPT paths that remain. R-07 stays OPEN
    because those two (plus the two read-by-convention actuator-capable paths) are not yet cut."""
    inv = yaml.safe_load(read(IMPL / "EFFECT-PATH-INVENTORY.yaml"))
    paths = require_population(inv["paths"], "effect paths")
    ids = [p["id"] for p in paths]
    assert len(ids) == len(set(ids)), "duplicate effect-path IDs"

    REMOVED = {"EP-6", "EP-7", "EP-9", "EP-10"}
    # EP-3 left this set at P4: its browser surface is now the read-only navigator and it imports no
    # adapter, so it is no longer a production-reachable live-write path. EP-1 alone remains, and it
    # is the one whose containment is the P12-scale supervised-write integration.
    LIVE = {"EP-1"}
    for p in paths:
        for field in ("path", "external_system", "production_reachable", "enablement",
                      "authority_bypass", "classification", "containment_phase", "disposition"):
            assert field in p, f"{p['id']}: unclassified - missing {field}"
        if p["id"] not in LIVE:
            assert "excluded_from_the_six_because" in p, (
                f"{p['id']}: not a current live-write path but no reason stated"
            )

    # the P4 deletion actually happened: exact removed set, and every removed file is GONE on disk.
    removed = {p["id"] for p in paths if p["classification"] == "REMOVED_AT_P4"}
    assert removed == REMOVED, f"the P4-removed set drifted: {sorted(removed)}"
    removed_pop = require_population(
        [p for p in paths if p["id"] in REMOVED], "P4-removed effect paths"
    )
    for p in removed_pop:
        f = ROOT / p["path"]
        assert not f.exists(), (
            f"{p['id']} is classified REMOVED_AT_P4 but {p['path']} still exists on disk - "
            f"the deletion was recorded but not performed (a false green)"
        )

    # the live-write set shrank from six to exactly the two ADAPT paths still awaiting conversion.
    live = {p["id"] for p in paths if p["classification"] == "PRODUCTION_LIVE_WRITE"}
    assert live == LIVE, f"the production-reachable live-write set drifted: {sorted(live)}"

    # every import-probe candidate from the (shrunk) manifest is still adjudicated here.
    manifest = yaml.safe_load(read(IMPL / "phase-0-baseline-manifest.yaml"))
    probe_scripts = {e["script"] for e in manifest["expected_legacy_paths"]["effect_capable_by_import"]}
    inventory_scripts = {p["path"] for p in paths}
    missing = probe_scripts - inventory_scripts
    assert not missing, f"import-probe candidates left unclassified: {sorted(missing)}"
    # and the manifest no longer lists a deleted path as effect-capable-by-import.
    still_listed = {p["path"] for p in paths if p["id"] in REMOVED} & probe_scripts
    assert not still_listed, (
        f"deleted path(s) still listed as effect-capable-by-import: {sorted(still_listed)}"
    )
    ep14 = next(p for p in paths if p["id"] == "EP-14")
    assert ep14["path"] == "scripts/read_tms_browser_use.py", "the P0-F4 adjudication is gone"
    # R-07's status as this inventory RESTATES it. The canonical record is the baseline manifest;
    # this file is scoped to the live-write adjudication and must AGREE with it rather than drift.
    # Re-pointed at the R-07 closure content commit (rule 20): it asserted the literal "R-07 OPEN"
    # for the whole time that was true, and now asserts the recorded closure together with its
    # bound - because an unbounded CONTAINED in an effect-path inventory reads as enablement.
    recorded = yaml.safe_load(
        read(IMPL / "phase-0-baseline-manifest.yaml"))["expected_legacy_paths"]
    assert recorded["status"] == "CONTAINED", (
        f"the canonical R-07 record reads {recorded['status']!r}"
    )
    assert str(inv["meta"]["risk"]).strip().startswith("R-07 CONTAINED"), (
        "the inventory's meta.risk no longer agrees with the canonical R-07 CONTAINED record: "
        f"{str(inv['meta']['risk'])[:80]!r}"
    )
    assert re.search(r"NOT mean any production write is enabled",
                     " ".join(str(inv["meta"]["risk"]).split()), re.I), (
        "the inventory records R-07 CONTAINED without the bound - containment is not enablement"
    )


# ============================================================ M-1: full graph consistency

def test_the_implementation_graph_is_consistent_and_protects_the_safety_wall():
    units = yaml.safe_load(read(IMPL / "IMPLEMENTATION-REGISTRY.yaml"))["units"]
    by_id = {u["unit_id"]: u for u in units}
    ids = set(by_id)
    edges = 0
    for u in units:
        for d in u["dependencies"]:
            assert d in ids, f"{u['unit_id']} depends on unknown {d}"
            edges += 1
        assert u["unlocked_by"] == u["dependencies"], (
            f"{u['unit_id']}: unlocked_by diverged from dependencies - the derived view drifted"
        )
        expected_dependents = sorted([v["unit_id"] for v in units if u["unit_id"] in v["dependencies"]])
        assert sorted(u["blocks"]) == expected_dependents, (
            f"{u['unit_id']}: blocks {u['blocks']} != actual dependents {expected_dependents}"
        )
        assert sorted(u["next_units_unlocked"]) == expected_dependents, (
            f"{u['unit_id']}: next_units_unlocked diverged from actual dependents"
        )
    assert edges >= 16, f"only {edges} dependency edges - the graph collapsed"
    # acyclic
    state: dict[str, int] = {}
    def visit(n):
        if state.get(n) == 1:
            raise AssertionError(f"dependency cycle through {n}")
        if state.get(n) == 2:
            return
        state[n] = 1
        for d in by_id[n]["dependencies"]:
            visit(d)
        state[n] = 2
    for n in ids:
        visit(n)
    # the safety wall
    assert "U-HANDOFF-1" in by_id["P3"]["dependencies"], "P3 no longer requires the rehearsal gate"
    assert "U-REBASELINE-1" in by_id["P3"]["dependencies"], (
        "P3 no longer requires the founder rebaseline (U-HANDOFF-1D registration)"
    )
    assert by_id["P4"]["dependencies"] == ["P3"], "P4 can begin without P3"
    assert by_id["P5"]["dependencies"] == ["P4"], (
        "P5 can begin without P4 - the rehearsal's exact bypass finding (P5 deps were [P2])"
    )
    ready = [u["unit_id"] for u in units if u["status"] == "READY"]
    # P3 adjudicated COMPLETE -> P4 READY; P4 then adjudicated COMPLETE -> P5 READY. The safety
    # wall above is what makes this legal: P5 may only be selected because P4 is genuinely COMPLETE.
    assert ready == ["P5"], f"READY set drifted: {ready}"
    assert by_id["P4"]["status"] == "COMPLETE", (
        f"P5 is READY while P4 is {by_id['P4']['status']} - the containment wall is bypassed"
    )
    p4_criteria = by_id["P4"].get("acceptance_criteria")
    assert p4_criteria and sum(int(c["weight"]) for c in p4_criteria) == 100 and all(
        str(c["result"]).upper() == "PASS" for c in p4_criteria
    ), "P4 unlocked P5 without a real, full-weight, fully-PASS weighted acceptance contract"


# ============================================================ H-3 / H-4: authority

def test_registry_md_carries_no_independent_status_authority():
    text = read(IMPL / "registry.md")
    assert "INDEX ONLY — NO INDEPENDENT STATUS AUTHORITY" in text, (
        "registry.md lost its authority banner (the rehearsal found it contradicting the "
        "canonical registry on Phase 2)"
    )
    # DELEGATED at the R-01/R-02 remediation: only a SELF-LABELLING <details> block is quarantined.
    # registry.md's block labels itself "Historical status table (pre-Blocker snapshot - WRONG
    # about Phase 2; retained as evidence)", so it still exempts - by saying so, not by existing.
    sys.path.insert(0, str(ROOT / "eval"))
    from control import status_claims

    live = status_claims.strip_historical_blocks(text)
    live = "\n".join(l for l in live.split("\n") if not l.startswith(">"))  # the banner DESCRIBES the defect
    assert not re.search(r"Phase 2[^|\n]{0,40}IN PROGRESS", live), (
        "registry.md asserts Phase 2 IN PROGRESS outside the quarantined historical block"
    )
    assert not re.search(r"(begin|Blocking:)[^\n]{0,60}U2\.6B\b", live), (
        "registry.md carries live instructions to begin U2.6B"
    )


ROOT_ALLOWED_NON_AUTHORITY = {
    # tooling/config files a root scan must not flag; никаких roadmap semantics
    ".gitignore", "pyproject.toml", ".env.example", "LICENSE", "Makefile",
    "requirements.txt",
}


def test_every_root_document_is_classified_dynamically():
    """H-4: DISCOVERED, never enumerated. A new root file that smells like authority (roadmap,
    stages, product, status, agent instructions) must be classified in the authority map or fail."""
    amap = read(ROOT / "docs" / "CANONICAL-DOCUMENTS.md")
    offenders = []
    candidates = [p for p in ROOT.iterdir()
                  if p.is_file() and p.suffix in (".md", ".txt") and p.name not in ROOT_ALLOWED_NON_AUTHORITY]
    require_population(candidates, "root documents")
    for p in candidates:
        if p.name not in amap:
            offenders.append(f"{p.name}: root document unclassified by the authority map")
            continue
        text = read(p)
        for m in re.finditer(r"Stage [1-8] —|8-stage roadmap", text):
            ctx = text[max(0, m.start() - 250): m.end() + 250]
            if not re.search(r"superseded|historical|SUPERSEDED", ctx, re.I):
                offenders.append(f"{p.name}: presents the stage roadmap without marking it superseded")
                break
    assert not offenders, "unclassified or unbannered root authority (the stages.txt defect):\n  " + "\n  ".join(offenders)
    assert not (ROOT / "stages.txt").exists(), "stages.txt returned to the repository root"


# ============================================================ M-2: banners, dynamically

def _classified_from_map(cls_names: tuple[str, ...]) -> list[str]:
    amap = read(ROOT / "docs" / "CANONICAL-DOCUMENTS.md")
    out = []
    for ln in amap.split("\n"):
        if not ln.strip().startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) >= 2 and any(c in cells[1] for c in cls_names):
            out.extend(re.findall(r"`([A-Za-z0-9_.]+\.(?:md|txt))`", cells[0]))
    return sorted(set(out))


def test_every_superseded_or_quarantined_document_is_disarmed_in_file():
    """M-2: derived from the authority map's OWN classifications - not a hand-enumerated list.
    Classifying a new file SUPERSEDED without bannering it fails immediately."""
    names = require_population(
        _classified_from_map(("SUPERSEDED", "QUARANTINED_GUIDANCE")),
        "superseded/quarantined documents",
    )
    offenders = []
    for name in names:
        p = ROOT / "docs" / name
        if not p.exists():
            offenders.append(f"{name}: classified but missing")
            continue
        head = read(p)[:1200]
        if "DO NOT FOLLOW" not in head:
            offenders.append(f"{name}: no in-file disarming banner - a grep-first reader sees old authority")
    assert not offenders, "superseded documents without in-file banners:\n  " + "\n  ".join(offenders)


def test_no_docs_root_file_claims_to_be_the_source_of_truth_unbannered():
    offenders = []
    files = require_population(sorted((ROOT / "docs").glob("*.md")), "docs-root files")
    for p in files:
        if p.name == "CANONICAL-DOCUMENTS.md":
            continue  # the map IS the authority document
        text = read(p)
        if re.search(r"[Tt]his (is|file is|doc(ument)? is) the (canonical|single source|source of truth)", text):
            if "DO NOT FOLLOW" not in text[:1200]:
                offenders.append(p.name)
    assert not offenders, f"docs-root files self-claiming authority without a banner: {offenders}"


# ============================================================ M-3: frontmatter, separately from body

def _frontmatter(p: Path) -> str:
    text = read(p)
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


def test_agent_frontmatter_describes_the_current_program_not_the_stages():
    """The listing shows frontmatter WITHOUT the body's banner, so the frontmatter itself must
    be clean - the rehearsal found the steward advertising the 8-stage roadmap there."""
    files = require_population(sorted(ROOT.glob(".claude/agents/*.md")), "claude agent definitions")
    for p in files:
        fm = _frontmatter(p)
        assert fm, f"{p.name}: no frontmatter"
        assert not re.search(r"8-stage|Stage [1-8]\b|extraction proof", fm, re.I), (
            f"{p.name}: frontmatter advertises the superseded stage roadmap"
        )
    steward = _frontmatter(ROOT / ".claude/agents/roadmap-steward.md")
    assert re.search(r"P0-P14|P0–P14", steward), (
        "the steward's frontmatter no longer names the current implementation program"
    )
    assert re.search(r"CURRENT\.md", steward), (
        "the steward's frontmatter no longer names the status authority"
    )
    assert re.search(r"Phase 3 does not start automatically", steward), (
        "the steward's frontmatter lost the no-automatic-Phase-3 statement"
    )
    # codex surfaces have no frontmatter; their first visible lines must be the compat pointer
    for p in sorted(ROOT.glob(".codex/agents/*.md")):
        head = read(p)[:300]
        assert "COMPATIBILITY SURFACE" in head, f"{p.name}: stale-capable head without compat pointer"


# ============================================================ status-result truthfulness (unit level)

def test_the_finalizer_refuses_count_arguments():
    """The 1A finalizer accepted --passed on faith; the 1B one read a pre-existing artifact,
    which U-HANDOFF-1C proved forgeable. The canonical finalizer now EXECUTES everything and
    offers no count flag; the superseded script is a refusing shim, not a second route."""
    src = read(ROOT / "scripts" / "finalize_status.py")
    assert not re.search(r"add_argument\(\s*['\"]--passed", src), (
        "the finalizer accepts hand-supplied counts again"
    )
    assert "_step_run_suite" in src and "_step_run_gate" in src, (
        "the finalizer no longer executes the suite and gate itself"
    )
    shim = read(ROOT / "scripts" / "update_current_status.py")
    assert "REFUSED" in shim and "finalize_status.py" in shim, (
        "the superseded finalizer no longer refuses - a weaker second route exists"
    )


def test_the_runner_refuses_dirty_trees():
    src = read(ROOT / "scripts" / "run_canonical_suite.py")
    assert re.search(r"REFUSED.{0,80}dirty", src, re.S | re.I), (
        "the canonical runner no longer refuses dirty working trees - developer-local results "
        "could re-enter the record"
    )


def test_collection_totals_alone_cannot_satisfy_status_reality():
    """Acceptance 12: the guard must CALL the artifact validator inside the artifact-backing
    test - by AST, because a substring check was satisfied by the import line while the actual
    call had been deleted (mutation B-6 proved it)."""
    tree = ast.parse(read(ROOT / "eval" / "tests" / "test_status_reality.py"))
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "test_the_status_record_is_backed_by_a_real_suite_result"), None)
    assert fn is not None, "the artifact-backing guard is gone from status-reality"
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and getattr(n.func, "id", getattr(n.func, "attr", "")) == "artifact_consistency_errors"]
    assert calls, (
        "status-reality's artifact-backing test no longer CALLS artifact_consistency_errors - "
        "collection-only verification is the exact false green the clean-clone rehearsal found"
    )
    assert "exit_status" in read(ROOT / "scripts" / "suite_result.py")


# ============================================================ authority-map family coverage

def test_every_implementation_document_is_classified_or_family_covered():
    amap = read(ROOT / "docs" / "CANONICAL-DOCUMENTS.md")
    assert "FAMILY RULE" in amap, "the review family rule left the authority map"
    offenders = []
    for p in sorted(IMPL.glob("*.md")):
        if "review" in p.name or p.name.startswith(("u2-6", "u-handoff", "phase-0-i", "phase-1", "phase-2")):
            continue  # covered by the review family rule
        if p.name not in amap:
            offenders.append(p.name)
    assert not offenders, f"implementation documents neither classified nor family-covered: {offenders}"


# ============================================================ M-4: no brittle line citations

def test_control_documents_cite_the_kb_finding_by_symbol_not_line_number():
    """The recorded citation `action_callback.py:1639` had already drifted to line 1657 when the
    rehearsal checked - a line number goes stale on any edit above it. Control documents cite the
    symbol; THIS guard verifies the actual sites still exist, mechanically."""
    for f in [ROOT / "CLAUDE.md", IMPL / "CURRENT.md", IMPL / "LEGACY-DISPOSITION.md",
              ROOT / "README.md", ROOT / "ARCHITECTURE.md"]:
        assert not re.search(r"action_callback\.py:\d+", read(f)), (
            f"{f.name} cites the KB finding by line number again - it was stale within two commits"
        )
    src = read(ROOT / "src" / "freight_recon" / "action_callback.py")
    assert 'tenant="default"' in src and "_learn_correction" in src, (
        "the KB default-tenant site moved or closed - update the finding truthfully, do not "
        "let the citation dangle"
    )
    ops = read(ROOT / "src" / "freight_recon" / "ops_control.py")
    assert ops.count('tenant="default"') == 5, (
        f"ops_control.py now has {ops.count(chr(39) + 'tenant=' + chr(39))} default-tenant sites, "
        "not the recorded 5 - update the finding truthfully"
    )


def test_handoff_10_keeps_the_rehearsal_repository_only():
    """The criterion must distinguish DESCRIBING the broad posture from OPERATING under it - a
    rehearsal that claims live external tools has broken its own evidence boundary."""
    text = read(IMPL / "U-HANDOFF-1-ACCEPTANCE.yaml")
    m = re.search(r"- id: HANDOFF-10\n(.*?)- id: HANDOFF-11", text, re.S)
    assert m, "HANDOFF-10 missing"
    body = m.group(1)
    assert re.search(r"repository-only", body), (
        "HANDOFF-10 no longer requires the rehearsal itself to remain repository-only"
    )
    assert re.search(r"WITHOUT claiming", body), (
        "HANDOFF-10 lost the describe-vs-operate distinction"
    )
