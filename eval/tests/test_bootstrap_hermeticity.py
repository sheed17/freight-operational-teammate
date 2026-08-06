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


# ============================================================ M-4: transition/event audit

def _audit() -> dict:
    return yaml.safe_load(read(IMPL / "TRANSITION-EVENT-AUDIT.yaml"))


def _computed_classes() -> dict[str, set[str]]:
    """The canonical computation: escape-aware split, per-table Event column."""
    machines = ROOT / "docs" / "specifications" / "state-machines"
    bare, documented, illegal_unnamed, delegating, evented = set(), set(), set(), set(), set()
    for f in sorted(machines.glob("*.machine.md")):
        short = f.name.replace(".machine.md", "")
        ev_idx = None
        for ln in f.read_text(encoding="utf-8").split("\n"):
            if not ln.strip().startswith("|"):
                ev_idx = None
                continue
            c = [x.strip() for x in re.split(r"(?<!\\)\|", ln)[1:-1]]
            if not c:
                continue
            if re.sub(r"[*\s]", "", c[0]) == "ID":
                headers = [re.sub(r"[*`\s]", "", h).lower() for h in c]
                ev_idx = next((i for i, h in enumerate(headers) if h.startswith("event")), None)
                continue
            if ev_idx is None or re.match(r"^[-: ]+$", c[0]):
                continue
            tid = re.sub(r"[*`\s]", "", c[0])
            if not re.fullmatch(r"[A-Z]{2}-\d+[a-z]?", tid):
                continue
            key = f"{short}:{tid}"
            cell = c[ev_idx] if ev_idx < len(c) else ""
            bare_cell = re.sub(r"[*`\s]", "", cell)
            if bare_cell in ("", "—", "-", "–"):
                bare.add(key)
            elif re.search(r"no new event|no state change", cell, re.I):
                documented.add(key)
            elif re.search(r"ILLEGAL", cell) and not re.search(r"IllegalTransition", cell):
                illegal_unnamed.add(key)
            elif re.sub(r"[*`\s]", "", cell) == "asthose":
                delegating.add(key)
            else:
                evented.add(key)
    return {"BARE": bare, "DOCUMENTED_NON_PRODUCING": documented,
            "ILLEGAL_UNNAMED": illegal_unnamed, "DELEGATING": delegating, "EVENTED": evented}


def test_transition_event_audit_matches_the_specs():
    """The audit's exact members must equal a fresh mechanical computation - exact SETS, so a
    same-count substitution fails, and a spec edit that changes any class fails until the audit
    is re-adjudicated."""
    computed = _computed_classes()
    audit = _audit()
    total = sum(len(v) for v in computed.values())
    assert total == audit["meta"]["total_transitions"] == 134, f"transition population drifted: {total}"
    recorded = {c["name"]: set(c["members"]) for c in audit["classes"]}
    for name in ("BARE", "DOCUMENTED_NON_PRODUCING", "ILLEGAL_UNNAMED", "DELEGATING"):
        require_population(recorded.get(name, set()), f"audit class {name}")
        assert computed[name] == recorded[name], (
            f"class {name} drifted: computed-only={sorted(computed[name] - recorded[name])}, "
            f"audit-only={sorted(recorded[name] - computed[name])}"
        )
    not_naming = sum(len(recorded[n]) for n in recorded)
    assert not_naming == audit["meta"]["transitions_not_naming_an_event"]
    assert len(computed["EVENTED"]) == audit["meta"]["transitions_naming_an_event"]
    assert audit["meta"]["status"] == "COUNT_NEEDS_ADJUDICATION", (
        "the finding was closed without the G2 adjudication"
    )


def test_the_retired_24_figure_does_not_reappear_in_control_documents():
    """The old figure was never mechanically computed. Naming it as RETIRED is allowed; citing
    it as the finding's count is not."""
    offenders = []
    for f in [ROOT / "CLAUDE.md", ROOT / "README.md", ROOT / "ARCHITECTURE.md",
              IMPL / "CURRENT.md", IMPL / "PHASE-OUTPUTS.md"]:
        for m in re.finditer(r"\b24\b(?![0-9])[^.\n]{0,50}(transitions?|event)", read(f)):
            ctx = m.group(0)
            if re.search(r"retired|never mechanically", read(f)[max(0, m.start() - 120): m.end() + 120], re.I):
                continue
            offenders.append(f"{f.name}: {ctx!r}")
    assert not offenders, f"the uncomputed '24' figure is back as a live count: {offenders}"


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
