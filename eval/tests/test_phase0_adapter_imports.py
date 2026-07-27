"""U0.9 - the direct adapter import guard. DETECTION ONLY.

This is NOT the U4.9 containment gate. That gate lands in Phase 4, after the pipeline client exists,
because a gate enabled earlier would only force wrappers - and a wrapper that logs the bypass is not
containment (roadmap; loophole PL-6). Every current site is allowlisted, so this guard cannot induce
wrapper behaviour. It exists to stop the surface GROWING.

The allowlist is shrinking-only. Adding an entry is prohibited.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0 import import_probe, manifest


def _edges() -> set[str]:
    sites, ev = import_probe.adapter_import_sites()
    ev.require_population()
    return {f"{s.module} -> {s.imported}" for s in sites}


def test_the_probe_evaluates_a_real_population():
    sites, ev = import_probe.adapter_import_sites()
    ev.require_population(minimum=10)
    assert len(ev.sources_inspected) > 100, "the probe must walk the whole tree, not a corner of it"


def test_no_new_direct_adapter_import_site():
    """REG-2. The guard that actually holds the line until Phase 4 deletes these."""
    new = _edges() - manifest.allowed_adapter_import_edges()
    assert not new, (
        "NEW direct adapter import site(s):\n  " + "\n  ".join(sorted(new)) +
        "\n\nThe allowlist is SHRINKING-ONLY. A new direct adapter import may not be added to the "
        "manifest; route it through the pipeline instead (U4.1)."
    )


def test_the_allowlist_is_shrinking_only():
    """An allowlist entry that no longer exists must be REMOVED, so the list provably shrinks."""
    stale = manifest.allowed_adapter_import_edges() - _edges()
    assert not stale, (
        "Allowlisted import site(s) no longer exist:\n  " + "\n  ".join(sorted(stale)) +
        "\n\nRemove them from the manifest. The list must shrink toward empty at P4."
    )


# ---------------------------------------------------------------------------------------------
# EP-14 RELOCATION AWARENESS - narrowly, and only for the one relocation that actually happened.
#
# The two guards above are set differences over the edge list. That is the right shape for stopping
# GROWTH, but it cannot by itself tell growth from RELOCATION: moving a write ledger from one
# adapter module to another looks like "one entry removed, one entry added". The manifest was
# edited to match, so those guards pass either way - which means they are no longer the thing that
# makes the EP-14 edge swap legitimate. This test is.
#
# It is deliberately NOT a general "relocations are fine" escape hatch. It asserts the nine
# conditions the EP-14 relocation had to satisfy, against the live import graph, for this ONE
# named swap. A different relocation gets no cover from it, and a count-neutral swap that expanded
# actuation reachability fails it.
# ---------------------------------------------------------------------------------------------

_EP14_OLD_EDGE = "src/freight_recon/browser_use_adapter.py -> tms_write"
_EP14_NEW_EDGE = "src/freight_recon/browser_use_write.py -> tms_write"


def test_the_ep14_relocation_is_a_swap_not_a_growth():
    """The nine conditions, each as its own assertion so a failure names which one broke."""
    edges = _edges()
    sites, _ = import_probe.adapter_import_sites()
    violations = import_probe.effect_adapter_violation_edges()

    # 1. the destination was already registered in the frozen canonical inventory
    assert "browser_use_write" in import_probe.ADAPTER_MODULES
    assert "browser_use_write" in import_probe.EFFECT_CAPABLE_ADAPTERS
    assert "browser_use_write" in set(manifest.frozen_effect_capable_adapters()), (
        "the destination is not in the FROZEN manifest inventory - a pre-registration invented by "
        "the session that needed it is a forgery, not authority"
    )

    # 2. the relocation stayed inside the adapter layer
    assert _EP14_NEW_EDGE.startswith("src/freight_recon/"), "the destination left the adapter layer"

    # 3. the old composition edge disappeared
    assert _EP14_OLD_EDGE not in edges, "the old edge survives - this is growth, not relocation"

    # 4. the replacement edge is authorized internal composition
    assert _EP14_NEW_EDGE in edges
    assert "browser_use_write" in import_probe.ADAPTER_LAYER

    # 5. total authorized composition surface did not grow
    assert len(edges) == len(manifest.allowed_adapter_import_edges()) == 14, (
        f"detection surface is {len(edges)} against a manifest of "
        f"{len(manifest.allowed_adapter_import_edges())} - the relocation budget is a SWAP"
    )

    # 6/7. application and script reachability did not expand: nothing outside the boundary and the
    # adapter layer imports the effect-capable destination
    importers = {Path(s.module).stem for s in sites if s.imported == "browser_use_write"}
    assert importers <= import_probe.CONTAINMENT_BOUNDARY | import_probe.ADAPTER_LAYER, (
        f"browser_use_write gained importer(s) {sorted(importers)} outside the boundary/adapter layer"
    )
    assert not [s for s in sites
                if s.imported == "browser_use_write" and s.module.startswith("scripts/")], (
        "a script can now reach the effect-capable browser-use write half"
    )

    # 8. the violation count strictly shrank
    assert "scripts/read_tms_browser_use.py -> browser_use_adapter" not in violations
    assert len(violations) == 1, f"expected exactly the EP-1 residual, got {sorted(violations)}"

    # 9. no read-only module gained effect reachability
    ro_imports = _module_imports(ROOT / "src/freight_recon/browser_use_adapter.py")
    assert not (ro_imports & import_probe.EFFECT_CAPABLE_ADAPTERS), (
        "the read half can reach an effect-capable adapter - an effect import moved INTO a "
        "read-only module"
    )
    for read_only in ("cdp_readonly.py", "browser_use_adapter.py"):
        imports = _module_imports(ROOT / "src/freight_recon" / read_only)
        assert "browser_use_write" not in imports, f"{read_only} reaches the write half"


def test_the_relocation_guard_is_specific_to_ep14():
    """It must not read as blanket permission. If a SECOND effect-capable importer of the write half
    appeared, or the old module became effect-capable again, the conditions above would fail - so
    this records that the guard is scoped to one named swap, not to relocations in general."""
    assert _EP14_OLD_EDGE.count("->") == 1 and _EP14_NEW_EDGE.count("->") == 1
    assert "browser_use_adapter" not in import_probe.EFFECT_CAPABLE_ADAPTERS, (
        "the source module is effect-capable again - the swap's whole justification is gone"
    )


def _module_imports(path: Path) -> set[str]:
    import ast

    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            out.add(node.module.split(".")[-1])
            out |= {a.name for a in node.names}
        elif isinstance(node, ast.Import):
            out |= {a.name.split(".")[-1] for a in node.names}
    return out


def test_orient_tms_is_structurally_read_only_not_read_only_by_convention():
    """EP-8, the worked example — REPLACED (not deleted) with the post-cut truth, U4.7.

    This test used to assert the opposite: that `orient_tms.py -> cdp_actuator` was live and
    allowlisted, because EP-8 was read-only BY CONVENTION while importing an actuator, and only the
    import graph could see it (a module's docstring is not evidence about what it can do).

    U4.7 cut it. The script now holds a `ReadOnlyCdpObserver`, which HAS no evaluate, command,
    navigate, click, type or upload method, so the containment is the absent API rather than a
    promise. The assertion is inverted rather than deleted, so a regression that re-imports the
    actuator fails HERE, on the worked example, with EP-8's name on it.
    """
    edges = _edges()
    assert "scripts/orient_tms.py -> cdp_actuator" not in edges
    assert "scripts/orient_tms.py -> cdp_actuator" not in manifest.allowed_adapter_import_edges()
    # Structurally read-only means it reaches NO adapter module at all, not merely not the actuator.
    assert not [e for e in edges if e.startswith("scripts/orient_tms.py ->")], (
        "EP-8 regained an adapter import; it must reach the browser only via cdp_readonly, which is "
        "not an adapter module and therefore creates no adapter-import edge"
    )


def test_propose_ar_from_tms_reaches_the_browser_read_only(): # EP-3, U4.8
    """EP-3's worked example. It previously navigated by `cdp_session.evaluate("location.href=...")`
    — caller data interpolated into JavaScript, F2's exact defect — and fell back to
    `cdp_actuator.click(load_ref)` to open a load's detail page for the POD check.

    Both are gone: it holds a `ReadOnlyCdpNavigator`, whose only added capability over the observer
    is a document fetch, and which follows only links the observed page itself published. A regained
    adapter import fails here with EP-3's name on it.
    """
    edges = _edges()
    assert not [e for e in edges if e.startswith("scripts/propose_ar_from_tms.py ->")], (
        "EP-3 regained an adapter import; its browser surface must be cdp_readonly only"
    )
    # Proved STRUCTURALLY, by AST, not by substring: this file's own docstring names the primitives
    # it no longer uses, and a substring check would trip on that prose (the F1 defect in reverse).
    import ast
    tree = ast.parse((ROOT / "scripts/propose_ar_from_tms.py").read_text(encoding="utf-8"))
    called = {n.func.attr for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
    forbidden = called & {"evaluate", "command", "click", "click_row_action", "type", "select",
                          "upload_file", "set_file_input", "navigate"}
    assert not forbidden, (
        f"EP-3 invokes {sorted(forbidden)}. Its browser surface is the read-only navigator: a SPA "
        "onclick handler can POST an invoice while being no kind of form submit target, so the "
        "click fallback was deleted rather than guarded, and evaluate-navigation was removed."
    )


def test_dynamic_imports_are_detected():
    """An effect path hidden behind importlib is still an effect path."""
    import ast

    from phase0.import_probe import _module_name

    tree = ast.parse("import importlib\nm = importlib.import_module('cdp_actuator')\n")
    found = [n for node in ast.walk(tree) for n in _module_name(node)]
    dynamic = [f for f in found if f[3]]
    assert dynamic, "importlib.import_module('cdp_actuator') was not detected as a dynamic import"
    assert dynamic[0][0] == "cdp_actuator"
