"""U4.9 - THE BOUNDARY-AWARE IMPORT GATE (P4 containment, R-07 surface).

This is the gate the Phase-0 detection probe (`test_phase0_adapter_imports.py`) explicitly is NOT:
that one only stops the raw adapter-import surface from GROWING. This one is the containment
partition. A VIOLATION is an import of an EFFECT-CAPABLE adapter - a module that produces an
external effect - by a module that is not:

  * the ONE containment boundary (`effect_boundary`, where `execute_effect` lives),
  * another adapter (adapters legitimately compose), or
  * a recorded, mock-guarded quarantine importer.

The read substrate (`cdp_session`: navigate + evaluate) is deliberately NOT effect-capable, so a
read-only tool importing it is never a violation. That distinction is the whole point of a
boundary-aware gate: it is stricter than a blanket adapter ban where it matters (it names the
boundary and refuses everyone else) and looser only where the architecture genuinely is.

The gate is EXACT and BOTH-SIDED against the manifest's recorded violation list:
  * no live violation may exist that the manifest has not recorded (a new bypass fails), and
  * no recorded edge may remain that is not really a live violation (the list provably shrinks).
Together they pin `live == recorded`, so the recorded list can only be edited DOWNWARD in lockstep
with a real cut. When it reaches EMPTY and the gate asserts empty, an external effect without a
grant is structurally impossible - the mechanical close condition for R-07.

The partition decision (`is_effect_capable_violation`) is exercised directly, branch by branch,
with a synthetic new-bypass site proving the gate is not vacuous.
"""

import ast
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from phase0 import import_probe, manifest
from phase0.import_probe import ImportSite, is_effect_capable_violation

# The ONE effect-capable adapter a mock-only quarantine importer may legitimately import: the home of
# `MockTmsWriteLedger`. `enter_approved_payable` writes to a live TMS ONLY when handed a live ledger;
# handed the mock JSON ledger it is inert. Every OTHER effect-capable adapter reaches an external
# system directly, so importing any of them forfeits the quarantine exemption.
_MOCK_LEDGER_HOME = "tms_write"

# Class names that, if CONSTRUCTED, drive a real external system. A quarantine importer must build
# none of them (finding F1). This is belt-and-suspenders behind the import proof: these classes live
# in the effect-capable adapters above, so an importer that imports none of those cannot reach them —
# but naming them makes a resurrected live-write construction fail loudly and specifically.
_LIVE_WRITE_DRIVERS = frozenset({
    "BrowserUseWriteLedger", "NativeBrowserUseRunner", "BrowserUseTmsAdapter",
    "CdpActuator", "CdpBrowserSession",
    "TruckingOfficeInvoiceLedger", "MultiStepInvoiceLedger", "DiscoveredInvoiceLedger",
})


def _effect_adapters_imported_by(module_rel: str) -> set[str]:
    """The EFFECT-CAPABLE adapter modules `module_rel` imports, from the AST import graph (static AND
    dynamic — `import_probe` detects importlib/__import__ too). This is structural: it reads what the
    module CAN reach, not what a docstring or a substring claims."""
    sites, _ = import_probe.adapter_import_sites()
    return {s.imported for s in sites
            if s.module == module_rel and s.imported in import_probe.EFFECT_CAPABLE_ADAPTERS}


def _constructed_callable_names(path: Path) -> set[str]:
    """Every callable NAME invoked in the module (a Call whose func is a bare Name or an Attribute).
    Used to prove a quarantine importer constructs the mock ledger and no live write driver — by AST,
    not by `"MockTmsWriteLedger" in text`, which a live-driver construction elsewhere in the file
    passes vacuously (exactly the F1 defect)."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            if isinstance(fn, ast.Name):
                names.add(fn.id)
            elif isinstance(fn, ast.Attribute):
                names.add(fn.attr)
    return names


def _live_violation_edges() -> set[str]:
    return import_probe.effect_adapter_violation_edges()


# --------------------------------------------------------------------------- population is real

def test_the_gate_evaluates_a_real_population_of_effect_candidates():
    """A negative gate over an empty candidate set passes vacuously. Prove the population."""
    _, ev = import_probe.effect_adapter_import_violations()
    ev.require_population(minimum=1)  # at least one effect-capable import considered
    assert len(ev.candidates) >= 10, (
        f"only {len(ev.candidates)} effect-capable import candidates - the probe walked a corner"
    )
    assert len(ev.sources_inspected) > 100, "the gate must walk the whole tree, not a subset"


def test_effect_capable_adapter_set_excludes_the_read_substrate():
    """`cdp_session` is the read substrate - navigate + evaluate, no external effect. It must NOT
    be treated as effect-capable, or every read-only orientation tool becomes a false violation."""
    assert "cdp_session" not in import_probe.EFFECT_CAPABLE_ADAPTERS
    assert "cdp_session" in import_probe.ADAPTER_MODULES  # still an adapter, just not effect-capable
    # the deterministic money-path actuator IS effect-capable
    assert "cdp_actuator" in import_probe.EFFECT_CAPABLE_ADAPTERS


# ------------------------------------------------------------------- exact, both-sided gate

def test_no_unrecorded_effect_violation_exists():
    """The gate proper. A live effect-capable bypass that the manifest has not recorded is a NEW
    hole in containment and fails immediately."""
    live = _live_violation_edges()
    recorded = manifest.recorded_effect_violation_edges()
    unrecorded = live - recorded
    assert not unrecorded, (
        "UNRECORDED effect-capable adapter import(s) - a new containment bypass:\n  "
        + "\n  ".join(sorted(unrecorded))
        + "\n\nRoute the effect through effect_boundary.execute_effect (P4). The gate's recorded "
        "violation list is SHRINKING-ONLY; a new edge may not be added to it."
    )


def test_no_recorded_violation_is_stale():
    """The other side: a recorded residual that is no longer a live violation must be REMOVED from
    the manifest, so the list provably shrinks toward EMPTY rather than freezing at a headline."""
    live = _live_violation_edges()
    recorded = manifest.recorded_effect_violation_edges()
    stale = recorded - live
    assert not stale, (
        "STALE recorded violation(s) - the edge was cut but the manifest still lists it:\n  "
        + "\n  ".join(sorted(stale))
        + "\n\nRemove it from effect_adapter_import_gate.violation_edges. The list must reach EMPTY."
    )


def test_the_recorded_list_and_the_tree_agree_exactly():
    """Belt and suspenders: pin live == recorded as a single equality so neither side can drift."""
    assert _live_violation_edges() == manifest.recorded_effect_violation_edges()


# ------------------------------------------------------------- the close condition is mechanical

def test_r07_close_condition_is_empty_not_shrinking():
    """The gate closes R-07 only when the violation list is EMPTY - not merely smaller. Encode the
    condition so it cannot silently become "small enough"."""
    gate = manifest.effect_adapter_import_gate()
    assert "EMPTY" in gate["deletion_condition"], "the close condition stopped requiring EMPTY"
    # today the list is non-empty, so R-07 must still read OPEN in the manifest
    if manifest.recorded_effect_violation_edges():
        assert gate["status"].strip().startswith("OPEN"), (
            "residual violations remain but the gate no longer records R-07 as OPEN"
        )


# ------------------------------------------------------- the partition decision, branch by branch

def _site(module: str, imported: str) -> ImportSite:
    return ImportSite(module=module, imported=imported, symbols=(), lineno=1)


def test_a_new_non_boundary_effect_import_is_caught():
    """MUTATION: a brand-new module that imports an effect-capable adapter is a violation. This is
    the exact bypass the gate exists to catch - proven on the real decision function, not a copy."""
    assert is_effect_capable_violation(_site("scripts/evil_new_bypass.py", "tms_write"))
    assert is_effect_capable_violation(_site("src/freight_recon/sneaky_writer.py", "cdp_actuator"))


def test_the_containment_boundary_may_import_effect_adapters():
    """`effect_boundary` is the ONE module allowed to hold an effect-capable adapter - that is what
    containment means: exactly one door."""
    assert not is_effect_capable_violation(
        _site("src/freight_recon/effect_boundary.py", "tms_write")
    )


def test_adapters_may_compose_with_each_other():
    """Intra-layer composition is legitimate: an adapter importing another adapter is not a bypass."""
    assert not is_effect_capable_violation(_site("src/freight_recon/cdp_actuator.py", "tms_write"))
    assert not is_effect_capable_violation(
        _site("src/freight_recon/discovered_write.py", "truckingoffice_write")
    )


def test_a_read_substrate_import_is_never_a_violation():
    """A non-boundary module importing `cdp_session` produces no effect and must never be flagged."""
    assert not is_effect_capable_violation(_site("scripts/some_new_reader.py", "cdp_session"))


def test_a_recorded_quarantine_importer_is_not_a_live_violation():
    """A mock-guarded quarantine importer is recorded (not in the shrinking violation list) so the
    gate can tell a quarantined fixture from a live-production bypass."""
    for stem in import_probe.QUARANTINE_IMPORTERS:
        assert not is_effect_capable_violation(_site(f"scripts/{stem}.py", "tms_write")), (
            f"quarantine importer {stem} was flagged as a live violation"
        )
    # and the quarantine importers are genuinely disjoint from the boundary and adapter layer
    assert not (import_probe.QUARANTINE_IMPORTERS & import_probe.CONTAINMENT_BOUNDARY)
    assert not (import_probe.QUARANTINE_IMPORTERS & import_probe.ADAPTER_LAYER)


def test_every_quarantine_importer_is_structurally_production_unreachable():
    """F1. The gate EXEMPTS quarantine importers from the violation list; that exemption must be
    EARNED by STRUCTURE, not by a substring. A quarantine importer is production-unreachable iff it
    imports NO effect-capable adapter that reaches a live external system — the only one it may
    import is `tms_write`, the home of the MOCK ledger. This is the AST import graph, so a
    live-browser path (EP-12's former `--browser`, which imported `browser_use_adapter` and built a
    real `BrowserUseWriteLedger` against an operator-supplied URL) FAILS here even though the file
    still contains the string `MockTmsWriteLedger` — the exact hole the old substring check left."""
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    assert import_probe.QUARANTINE_IMPORTERS, "no quarantine importers to prove - vacuous"
    for stem in import_probe.QUARANTINE_IMPORTERS:
        path = scripts_dir / f"{stem}.py"
        assert path.exists(), f"recorded quarantine importer {stem} does not exist"
        imported = _effect_adapters_imported_by(f"scripts/{stem}.py")
        live_reaching = imported - {_MOCK_LEDGER_HOME}
        assert not live_reaching, (
            f"quarantine importer {stem} imports effect-capable adapter(s) that reach a live external "
            f"system: {sorted(live_reaching)}. Its gate exemption is a LIVE BYPASS wearing a "
            f"quarantine label. Route it through effect_boundary.execute_effect, or remove the live "
            f"import (F1)."
        )


def test_every_quarantine_importer_constructs_the_mock_and_no_live_driver():
    """F1, the other half: the exemption must be POSITIVELY earned — the importer genuinely builds
    the mock write ledger (so it is a real mock-write fixture, not an inert stub given the label) —
    and it must construct NO live write driver by name. Both are read from the AST (constructor
    Calls), never from `"MockTmsWriteLedger" in text`, which a file that ALSO builds a live driver
    passes vacuously."""
    scripts_dir = Path(__file__).resolve().parents[2] / "scripts"
    assert import_probe.QUARANTINE_IMPORTERS, "no quarantine importers to prove - vacuous"
    for stem in import_probe.QUARANTINE_IMPORTERS:
        path = scripts_dir / f"{stem}.py"
        constructed = _constructed_callable_names(path)
        assert "MockTmsWriteLedger" in constructed, (
            f"quarantine importer {stem} does not CONSTRUCT MockTmsWriteLedger — its exemption is "
            f"unearned (an inert stub, or it writes through something else)"
        )
        live = constructed & _LIVE_WRITE_DRIVERS
        assert not live, (
            f"quarantine importer {stem} constructs live write driver(s) {sorted(live)} — a live "
            f"bypass mislabelled as quarantine (F1)"
        )


def test_the_boundary_is_exactly_one_module():
    """Containment requires a SINGLE door. More than one boundary module is more than one place an
    effect can originate - a design regression the gate must refuse to normalise."""
    assert import_probe.CONTAINMENT_BOUNDARY == {"effect_boundary"}


def test_brain_runtime_holds_no_effect_capable_import():
    """P4: brain_runtime was rewired to INJECT its effect executor instead of importing the
    effect-capable write path. Prove the `brain_runtime -> tms_write` edge is structurally gone — the
    module imports no effect-capable adapter at all, so it holds no path to an ungated write."""
    imported = _effect_adapters_imported_by("src/freight_recon/brain_runtime.py")
    assert imported == set(), (
        f"brain_runtime imports effect-capable adapter(s) {sorted(imported)}; its effect executor "
        f"must be injected, not imported (P4 adapter containment)"
    )


def test_brain_runtime_gated_submit_fails_closed_without_an_injected_executor():
    """The injection is fail-CLOSED: a missing enter_fn/approved_amount_fn raises, rather than
    silently reaching for the ungated `enter_approved_payable` default the old code imported."""
    import freight_recon.brain_runtime as br

    with pytest.raises(ValueError):
        br.build_gated_submit(store=None, run_id=1, build_ledger=lambda ctx: object(),
                              enter_fn=None, approved_amount_fn=None)


def test_every_live_effect_importer_is_boundary_adapter_quarantine_or_recorded():
    """Exhaustiveness: there is no fourth, unclassified way to import an effect-capable adapter.
    Every effect-capable importer in the tree is the boundary, an adapter, a recorded quarantine,
    or a recorded violation - nothing falls through the partition unnoticed."""
    sites, _ = import_probe.adapter_import_sites()
    recorded = manifest.recorded_effect_violation_edges()
    exempt = (
        import_probe.CONTAINMENT_BOUNDARY
        | import_probe.ADAPTER_LAYER
        | import_probe.QUARANTINE_IMPORTERS
    )
    unclassified = []
    for s in sites:
        if s.imported not in import_probe.EFFECT_CAPABLE_ADAPTERS:
            continue
        edge = f"{s.module} -> {s.imported}"
        if import_probe._importer_stem(s.module) in exempt or edge in recorded:
            continue
        unclassified.append(edge)
    assert not unclassified, f"effect-capable importer fell through the partition: {unclassified}"
