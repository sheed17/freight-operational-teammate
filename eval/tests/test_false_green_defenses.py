"""False-green defenses (U-HANDOFF-1C): the guards that make the hostile review's attacks fail.

Each section corresponds to a HIGH finding from the hostile formal handoff-readiness review:

  H-1  a handwritten green artifact was accepted -> finalization must EXECUTE, never attest
  H-2  pytest addopts silently removed 31 tests  -> isolated config + exact node identity
  H-3  skip detection covered 25 of 106 files    -> whole-suite static + approved-skip manifest
  H-4  a live "24 event-less" contradiction      -> dynamic stale-claim scan, banner-position aware
  H-5  P6+ could bypass the safety wall          -> TRANSITIVE ancestry for the whole chain
  H-6  hand-enumerated guard populations         -> central inventory + a meta-guard against literals

Everything here consumes eval/control/inventory.py - populations are discovered, never typed.
"""

from __future__ import annotations

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eval"))
sys.path.insert(0, str(ROOT / "scripts"))
from control import inventory as inv  # noqa: E402
from suite_result import (  # noqa: E402
    APPROVED_SKIPS_RELPATH, ARTIFACT_RELPATH, NODE_MANIFEST_RELPATH, payload_hash,
)

IMPL = ROOT / "docs" / "implementation"


def read(p: Path | str) -> str:
    return (ROOT / p if isinstance(p, str) else p).read_text(encoding="utf-8")


def require_population(items, what: str):
    assert items, f"no {what} to assert over - this test would pass vacuously"
    return items


def _strip_quarantine(text: str) -> str:
    """Remove <details> blocks and blockquote banner lines - the sanctioned homes of stale text."""
    text = re.sub(r"<details>.*?</details>", "", text, flags=re.S)
    return "\n".join(l for l in text.split("\n") if not l.lstrip().startswith(">"))


# ============================================================ H-1: execution, not attestation

def test_a_perfect_forged_artifact_cannot_complete_finalization(tmp_path, monkeypatch):
    """THE HOSTILE ATTACK, REPRODUCED: a structurally perfect green artifact with every unkeyed
    hash correctly recomputed sits at the canonical path - and no tests run. Finalization must
    abort without touching status, without consuming the forgery."""
    import finalize_status as fz

    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    tree = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()
    forged = {
        "command": ".venv/bin/python -m pytest -c pytest-canonical.ini -v",
        "commit": head, "tree": tree, "python_version": "3.12.0", "platform": "forged",
        "passed": 1206, "failed": 0, "skipped": 1, "collected": 1207, "deselected": 0,
        "duration_seconds": 400.0, "exit_status": 0, "completed_at": "2026-07-19T00:00:00+00:00",
        "config_sha256": "0" * 64, "runner_sha256": "0" * 64, "manifest_sha256": "0" * 64,
        "skipped_nodes": ["eval/tests/test_phase0_guard_integrity.py::test_red_by_design_cases_actually_fail"],
    }
    forged["payload_sha256"] = payload_hash(forged)  # every unkeyed hash correct

    art = tmp_path / "SUITE-RESULT.json"
    art.write_text(json.dumps(forged))
    status_before = read(IMPL / "CURRENT.md")

    # The forger cannot run the real suite; simulate 'no tests ran' by making every execution
    # step fail, then prove the perfect artifact rescues nothing.
    monkeypatch.setattr(fz, "ARTIFACT_RELPATH", str(art.relative_to(tmp_path)), raising=False)
    # Neutralize the earlier pipeline steps so the test provably exercises the FORGERY path:
    # without this, a dirty authoring tree would abort at step 1 and this test would pass for
    # the wrong reason. The dirty-tree refusal has its own coverage.
    for benign in ("_step_dirty_tree", "_step_python_floor", "_step_dependencies",
                   "_step_population"):
        monkeypatch.setattr(fz, benign, lambda *a, **k: None)
    monkeypatch.setattr(fz, "_receipt_baselines", lambda: {})
    monkeypatch.setitem(fz.EXECUTORS, "suite", lambda: (_ for _ in ()).throw(RuntimeError("no tests ran")))
    monkeypatch.setitem(fz.EXECUTORS, "gate", lambda: 1)
    with pytest.raises((SystemExit, RuntimeError)):
        fz.finalize()
    assert art.exists() and json.loads(art.read_text())["passed"] == 1206, (
        "the forged artifact was consumed/altered - it must simply be ignored"
    )
    assert read(IMPL / "CURRENT.md") == status_before, (
        "finalization touched status despite the suite never running - the forged artifact "
        "substituted for execution"
    )


def test_the_finalizer_offers_no_bypass_surface():
    """No count flags, no artifact path, no trust flag, no skip-suite, no skip-gate, no filter."""
    src = read("scripts/finalize_status.py")
    for forbidden in ("--passed", "--failed", "--skipped", "--artifact", "--trust",
                      "--skip-suite", "--skip-gate", "--skip-clean-clone", "--no-suite",
                      "--use-existing", "-k"):
        assert not re.search(rf"add_argument\(\s*['\"]{re.escape(forbidden)}", src), (
            f"the finalizer offers a bypass flag: {forbidden}"
        )
    assert "_receipt_baselines" in src and "predates this invocation" in src, (
        "the finalizer lost its receipt-freshness proof - a pre-existing gate record could "
        "substitute for running the gate (the first design DELETED tracked receipts, which "
        "dirtied the tree mid-run; hash-freshness proves this-run authorship without deletion)"
    )
    assert "load_artifact" not in src, (
        "the finalizer reads a pre-existing artifact - evidence must be an OUTPUT of the run"
    )
    fn = re.search(r"def finalize\(\).*?(?=\ndef main)", src, re.S)
    assert fn, "finalize() missing"
    body = fn.group(0)
    for step in ("_step_dirty_tree", "_step_python_floor", "_step_dependencies",
                 "_step_population", "_receipt_baselines", "_step_run_suite",
                 "_step_run_gate", "_step_run_guards_and_gates"):
        assert step in body, f"finalize() no longer executes {step}"


def test_the_superseded_finalizer_shim_refuses():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "update_current_status.py")],
                       cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 2 and "REFUSED" in r.stderr, (
        "the superseded finalizer still runs - a second, weaker finalization route exists"
    )


def test_the_trust_model_is_documented_honestly():
    """No claim of impossible local cryptographic attestation; CI provenance documented as later."""
    src = read("scripts/suite_result.py")
    assert re.search(r"cannot prove that tests ran|not independent cryptographic proof|GENERATED EVIDENCE", src, re.S)
    assert re.search(r"CI provenance", src), "the future-CI note is gone"
    assert "artifact_consistency_errors" in src and "def validation_errors" not in src, (
        "the validator's name again implies validation proves execution"
    )


def test_the_gate_result_must_come_from_the_gate_process():
    src = read("scripts/finalize_status.py")
    assert re.search(r"gate wrote no result|gate_path\.exists\(\)", src), (
        "the finalizer accepts a gate PASS without the gate's own record"
    )
    assert re.search(r'gate\.get\("commit"\) != head', src), (
        "the finalizer no longer binds the gate result to the finalized commit"
    )
    gate_src = read("scripts/clean_clone_gate.py")
    assert "_write_result(passed=False" in gate_src, "the gate cannot record its own failures"
    assert "NOTE:" not in gate_src, "advisory NOTE language returned to the gate"
    assert re.search(r'_fail\(f?"?\{?counts\[.failed.\]\}? failures on a clean clone', gate_src) or \
        re.search(r"_fail\(.{0,60}failures on a clean clone", gate_src), (
        "a clean-clone failure count is no longer decisive"
    )


# ============================================================ H-2: config isolation + exact nodes

def test_the_canonical_config_is_isolated_and_unfiltered():
    cfg = read("pytest-canonical.ini")
    for tok in ("--ignore", "-k ", "-m ", "--deselect", "testpaths = tests"):
        assert tok not in cfg, f"the canonical config carries filtering: {tok!r}"
    assert re.search(r"^testpaths = eval$", cfg, re.M), "canonical testpaths is not eval"
    runner = read("scripts/run_canonical_suite.py")
    assert re.search(r'env\["PYTEST_ADDOPTS"\] = ""', runner), (
        "the runner inherits ambient PYTEST_ADDOPTS - the exact H-2 injection channel"
    )
    assert '"-c", str(CANONICAL_CONFIG)' in runner, "the runner does not pin the canonical config"
    assert "_config_is_clean" in runner, "the runner no longer self-checks its config"


def test_the_node_manifest_is_exact_identities_not_a_count():
    manifest = json.loads(read(NODE_MANIFEST_RELPATH))
    nodes = require_population(manifest["node_ids"], "manifest node ids")
    assert len(nodes) == len(set(nodes)) == manifest["node_count"]
    assert all(re.match(r"^eval/.+::", n) for n in nodes[:50])
    # count-only derivation rule: the count is DERIVED from the exact set
    assert manifest["node_count"] == len(manifest["node_ids"])
    for key in ("config_sha256", "runner_sha256", "manifest_sha256"):
        assert manifest.get(key), f"manifest lacks {key} binding"


def test_manifest_regeneration_is_not_reachable_from_finalization():
    fz = read("scripts/finalize_status.py")
    assert "regenerate_test_manifest" not in fz, (
        "finalization can regenerate the manifest - population changes must be explicit acts"
    )
    rg = read("scripts/regenerate_test_manifest.py")
    assert re.search(r"refusing to write an empty manifest", rg)


def test_the_runner_verifies_execution_against_collection():
    src = read("scripts/run_canonical_suite.py")
    # the COMPARISONS must exist, not merely the field names - a mutation that hardcoded
    # unexecuted_nodes=[] while keeping the key slipped past a substring check (battery H2-exec)
    assert re.search(r"unexecuted = sorted\(recorded - executed\)", src), (
        "the runner no longer computes the unexecuted set from the real difference"
    )
    assert re.search(r"rogue = sorted\(executed - recorded\)", src), (
        "the runner no longer computes the rogue set from the real difference"
    )
    assert re.search(r'"unexecuted_nodes": unexecuted', src) and re.search(r'"rogue_nodes": rogue', src), (
        "the runner records something other than the computed differences"
    )
    assert re.search(r"missing or extra", src), "collection-vs-manifest divergence no longer aborts"


# ============================================================ H-3: whole-suite skip enforcement

def _approved() -> dict:
    return yaml.safe_load(read(APPROVED_SKIPS_RELPATH))


def test_every_static_skip_site_in_the_whole_suite_is_approved():
    """The old detector covered 25 of 106 files and excluded the control guards. This covers
    EVERY tracked canonical test module via AST discovery, exact-set both directions."""
    modules = require_population(inv.canonical_test_modules(), "canonical test modules")
    assert len(modules) >= 100, f"module discovery collapsed to {len(modules)}"
    sites = inv.skip_xfail_sites()
    observed = {(s["file"], s["construct"]) for s in sites}
    approved = {(a["file"], a["construct"]) for a in _approved()["static_sites"]}
    unapproved = sorted(observed - approved)
    vanished = sorted(approved - observed)
    assert not unapproved, (
        f"skip-capable constructs outside the approved manifest: {unapproved} - an unlisted "
        "skip is a test that can silently stop existing"
    )
    assert not vanished, (
        f"approved skip sites no longer exist: {vanished} - update the manifest intentionally; "
        "silence must not change meaning in either direction"
    )
    for entry in _approved()["static_sites"]:
        for field in ("reason", "owning_document", "permanence", "review_condition", "node"):
            assert entry.get(field), f"approved skip {entry['file']} lacks {field}"
        # the manifest reason must describe the ACTUAL skip in the source - a reason edited away
        # from reality is an approval of something else
        src_text = read(entry["file"])
        m = re.search(r"pytest\.skip\(\s*[\"']([^\"']{10,60})", src_text)
        if m and entry["construct"] == "pytest.skip":
            anchor_words = [w for w in re.findall(r"[a-z-]{4,}", m.group(1).lower())][:3]
            assert any(w in entry["reason"].lower() for w in anchor_words), (
                f"approved-skip reason for {entry['file']} no longer describes the actual skip "
                f"message ({m.group(1)!r})"
            )


def test_expected_canonical_run_skips_are_exact_and_within_the_manifest():
    approved = _approved()
    expected = require_population(approved["expected_canonical_run_skips"], "expected skips")
    manifest_nodes = set(json.loads(read(NODE_MANIFEST_RELPATH))["node_ids"])
    for node in expected:
        assert node in manifest_nodes, f"approved skip {node} is not a real collected node"
    assert len(expected) == 1, (
        f"the expected canonical skip set grew to {len(expected)} - every addition needs the "
        "same adjudication the first one got"
    )
    # the dirty-tree NOT-RUN skips must never be canonical-run-approved
    for site in approved["static_sites"]:
        if "dirty" in site["reason"].lower():
            assert site["node"] not in expected, (
                "a dirty-tree NOT-RUN skip was approved for canonical runs - that re-opens M-4"
            )


def test_no_module_level_pytestmark_or_importorskip_hides_tests():
    sites = inv.skip_xfail_sites()
    marks = [s for s in sites if s["construct"] in ("pytestmark", "pytest.importorskip")]
    assert not marks, f"module-level skip machinery present: {marks}"


# ============================================================ H-4: the retired-24, dynamically

_STALE_24 = re.compile(r"\b24\b[^.\n]{0,60}(event-less|transitions?[^.\n]{0,30}(no event|cite no))"
                       r"|\b24 of 134\b|24 EVENT-LESS", re.I)


def _retired_context(text: str, start: int, end: int) -> bool:
    ctx = text[max(0, start - 450): end + 450]
    return bool(re.search(r"retired|never mechanically computed|RETIRED|CORRECTION|"
                          r"COUNT[ _]NEEDS[ _]ADJUDICATION|since-retired", ctx))


def test_no_current_authority_document_carries_a_live_24_claim():
    """DISCOVERED population: every current-authority document from the inventory - planting a
    new control document containing the retired claim fails without touching this guard."""
    docs = require_population(inv.current_authority_documents(), "current-authority documents")
    offenders = []
    for rel in docs:
        text = read(rel)
        for m in _STALE_24.finditer(text):
            if not _retired_context(text, m.start(), m.end()):
                offenders.append(f"{rel}: {m.group(0)!r}")
    assert not offenders, (
        "live stale '24' claims in current-authority documents (H-4):\n  " + "\n  ".join(offenders)
    )


def test_historical_documents_disarm_before_any_stale_claim():
    """Banner POSITION matters: a grep-first or direct-open reader must meet the disarming
    context before the stale claim. The banner must sit in the first meaningful block AND
    physically precede every stale occurrence."""
    offenders = []
    banner_pat = re.compile(r"NOT CURRENT AUTHORITY|DO NOT FOLLOW|SUPERSEDED — DO NOT|HISTORICAL —")
    for rel in require_population(inv.banner_required_documents(), "banner-required documents"):
        text = read(rel)
        m = banner_pat.search(text)
        if not m:
            offenders.append(f"{rel}: no disarming banner at all")
            continue
        head = "\n".join(text.split("\n")[:10])
        if not banner_pat.search(head):
            offenders.append(f"{rel}: banner exists but not in the first meaningful block")
            continue
        for stale in list(_STALE_24.finditer(text)) + list(re.finditer(r"READY TO BEGIN", text)):
            if stale.start() < m.start():
                offenders.append(f"{rel}: stale claim {stale.group(0)!r} precedes the banner")
    assert not offenders, "historical documents not disarmed-in-place:\n  " + "\n  ".join(offenders)


# ============================================================ H-5: transitive safety ancestry

def _graph() -> dict[str, list[str]]:
    units = yaml.safe_load(read("docs/implementation/IMPLEMENTATION-REGISTRY.yaml"))["units"]
    return {u["unit_id"]: list(u["dependencies"]) for u in units}


def _ancestors(g: dict[str, list[str]], node: str) -> set[str]:
    seen: set[str] = set()
    stack = list(g.get(node, []))
    while stack:
        n = stack.pop()
        if n in seen:
            continue
        seen.add(n)
        stack.extend(g.get(n, []))
    return seen


# FIXED-SPECIFICATION: the P0..P14 linear chain is a deliberately specified safety invariant,
# not a discovery population - the prohibition on hand-enumeration applies to discovery.
PHASES = [f"P{i}" for i in range(15)]


def test_the_complete_safety_wall_is_transitively_protected():
    """Not named examples - EVERY phase: P3 is a transitive ancestor of P4..P14, P4 of P5..P14,
    and each phase keeps its intended direct predecessor. The hostile review's exact attack -
    P6 depending on P2 with all derived views self-consistent - fails here."""
    g = _graph()
    # phase units are DISCOVERED from the registry, so an inserted P15 (or P99) with a
    # wall-bypassing dependency is caught without touching this guard
    phase_nums = sorted(int(u[1:]) for u in g if re.fullmatch(r"P\d+", u))
    assert phase_nums[:4] == [0, 1, 2, 3] and max(phase_nums) >= 14, f"phase set implausible: {phase_nums}"
    for i in (n for n in phase_nums if n >= 4):
        anc = _ancestors(g, f"P{i}")
        assert "P3" in anc, f"P{i} lost P3 as a transitive ancestor - the checkpoint wall is bypassed"
    for i in (n for n in phase_nums if n >= 5):
        anc = _ancestors(g, f"P{i}")
        assert "P4" in anc, f"P{i} lost P4 as a transitive ancestor - containment is bypassed"
    for i in (n for n in phase_nums if 4 <= n <= 14):
        assert f"P{i-1}" in g[f"P{i}"], (
            f"P{i} no longer directly depends on P{i-1} - the linear roadmap chain is broken"
        )
    assert set(g["P3"]) >= {"P2", "U-HANDOFF-1"}, "P3 lost its gate dependencies"
    units = yaml.safe_load(read("docs/implementation/IMPLEMENTATION-REGISTRY.yaml"))["units"]
    by_id = {u["unit_id"]: u for u in units}
    for u in units:
        if u["status"] == "READY":
            incomplete = [d for d in _ancestors(g, u["unit_id"]) | set(g[u["unit_id"]])
                          if by_id[d]["status"] != "COMPLETE"]
            assert not incomplete, (
                f"{u['unit_id']} is READY while transitive dependencies are incomplete: {incomplete}"
            )
    # no disconnected implementation island: every phase reaches P0
    for i in range(1, 15):
        assert "P0" in _ancestors(g, f"P{i}"), f"P{i} is disconnected from the programme root"


# ============================================================ H-6: the meta-guard

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
    assert not offenders, "hand-enumerated populations inside control guards (H-6):\n  " + "\n  ".join(offenders)


def test_every_corpus_scanning_negative_assertion_proves_its_population():
    """The generalized, DISCOVERED replacement for the hand-typed NEGATIVE_ASSERTION_TESTS dict."""
    funcs = require_population(inv.negative_assertion_functions(),
                               "corpus-scanning negative-assertion tests")
    assert len(funcs) >= 10, f"discovery collapsed to {len(funcs)} functions"
    unproven = [f"{f['file']}::{f['function']}" for f in funcs if not f["proves_population"]]
    assert not unproven, (
        "corpus-scanning negative assertions without a population proof (vacuously green over "
        "an empty parse):\n  " + "\n  ".join(unproven)
    )


def test_volatile_suite_figures_live_only_in_the_status_block():
    """Refactored from a hand-typed 5-file list to the DISCOVERED current-authority + agent
    population."""
    docs = [d for d in inv.current_authority_documents() if d.endswith(".md")]
    docs += inv.agent_files() + inv.compatibility_agent_files()
    docs = [d for d in require_population(docs, "scannable authority documents")
            if d != "docs/implementation/CURRENT.md"]
    offenders = []
    for rel in docs:
        text = _strip_quarantine(read(rel))
        for m in re.finditer(r"\b\d{3,5}\s+(?:tests?\s+)?(?:passed|passing)\b", text, re.I):
            line = text[: m.start()].count("\n") + 1
            offenders.append(f"{rel}:{line}: {m.group(0)!r}")
    assert not offenders, "volatile suite figures outside CURRENT.md's block:\n  " + "\n  ".join(offenders)


def test_no_current_authority_document_cites_source_lines_absolutely():
    """Refactored from a hand-typed file list: DISCOVERED population. Scope: implementation-
    control, status and root control documents - the files that claim to describe CURRENT
    reality. The frozen architecture corpus (semantic model, target spec) cites reset-snapshot
    line numbers BY DESIGN: those documents open with their layer and date and describe the
    repository AS OF THE RESET, so their citations are snapshot evidence, not current authority -
    and editing the frozen corpus to relieve a guard would be the greater sin."""
    offenders = []
    scope = [rel for rel in require_population(inv.current_authority_documents(),
                                               "current-authority documents")
             if rel.startswith("docs/implementation/") or "/" not in rel]
    for rel in require_population(scope, "current-reality documents"):
        if not rel.endswith(".md"):
            continue
        text = read(rel)
        if "reset-snapshot citation" in text:
            # the document declares its citations as coordinates of DELETED pre-reset code, and
            # guards separately assert those symbols stayed deleted - not current authority
            continue
        for m in re.finditer(r"[A-Za-z0-9_]+\.py:\d{2,}", text):
            offenders.append(f"{rel}: {m.group(0)}")
    assert not offenders, (
        "absolute source-line citations in current authority (they drift within commits):\n  "
        + "\n  ".join(offenders)
    )
    # the underlying KB finding must still be real - symbol-verified, never line-verified
    src = read("src/freight_recon/action_callback.py")
    assert 'tenant="default"' in src and "_learn_correction" in src
    assert read("src/freight_recon/ops_control.py").count('tenant="default"') == 5


def test_bare_pytest_collects_the_canonical_population():
    """LOW: pyproject pointed testpaths at a nonexistent tests/ dir - bare `pytest` quietly
    collected zero canonical tests."""
    pyproject = read("pyproject.toml")
    m = re.search(r'^testpaths = \["(.+?)"\]', pyproject, re.M)
    assert m and m.group(1) == "eval", f"pyproject testpaths is {m.group(1) if m else 'MISSING'!r}"
    assert (ROOT / "eval").is_dir()


def test_the_status_block_branch_field_is_advisory():
    """LOW: a branch name is not stable across bundles and clones - it may be recorded only as
    explicitly advisory, never as verified reality."""
    text = read(IMPL / "CURRENT.md")
    m = re.search(r"```yaml\n# status-block:.*?```", text, re.S)
    assert m, "status-block missing"
    block = m.group(0)
    assert "recorded_authoring_branch" in block or "branch" not in block, (
        "the status block presents an unverified branch name as current reality"
    )
    if "recorded_authoring_branch" in block:
        assert "advisory" in block, "the authoring-branch field lost its advisory marker"


def test_finalization_refuses_a_dirty_tree_before_anything_runs(monkeypatch, tmp_path):
    """M-4 at the finalizer: a dirty tracked tree aborts at step one - never a silent pass,
    never a run recorded from uncommitted state. Uses the REAL dirty-check against a temp git
    repo so the authoring checkout's own state cannot fake the result either way."""
    import subprocess as sp
    import finalize_status as fz

    repo = tmp_path / "r"
    repo.mkdir()
    sp.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "f.txt").write_text("x")
    sp.run(["git", "add", "."], cwd=repo, check=True)
    sp.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c"],
           cwd=repo, check=True)
    (repo / "f.txt").write_text("dirty")

    monkeypatch.setattr(fz, "ROOT", repo)
    with pytest.raises(SystemExit) as exc:
        fz._step_dirty_tree()
    assert "dirty" in str(exc.value)
    # and a clean tree passes the same real check
    sp.run(["git", "add", "."], cwd=repo, check=True)
    sp.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "c2"],
           cwd=repo, check=True)
    fz._step_dirty_tree()  # must not raise
