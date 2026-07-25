"""U0.9 - the direct adapter import guard. DETECTION ONLY.

This is NOT the U4.9 containment gate. That gate lands in Phase 4, after the pipeline client exists,
because a gate enabled earlier would only force wrappers - and a wrapper that logs the bypass is not
containment (roadmap; loophole PL-6). Every current site is allowlisted, so this guard cannot induce
wrapper behaviour. It exists to stop the surface GROWING.

The allowlist is shrinking-only. Adding an entry is prohibited.
"""

import sys
from pathlib import Path

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


def test_orient_tms_is_recorded_as_actuator_capable_despite_being_read_only():
    """EP-8, the worked example: read-only by convention, actuator-capable by import.

    Only the import graph finds this. A module's docstring is not evidence about what it can do.
    Removing the import is U4.7 (Phase 4), not Phase 0.
    """
    assert "scripts/orient_tms.py -> cdp_actuator" in _edges()
    assert "scripts/orient_tms.py -> cdp_actuator" in manifest.allowed_adapter_import_edges()


def test_dynamic_imports_are_detected():
    """An effect path hidden behind importlib is still an effect path."""
    import ast

    from phase0.import_probe import _module_name

    tree = ast.parse("import importlib\nm = importlib.import_module('cdp_actuator')\n")
    found = [n for node in ast.walk(tree) for n in _module_name(node)]
    dynamic = [f for f in found if f[3]]
    assert dynamic, "importlib.import_module('cdp_actuator') was not detected as a dynamic import"
    assert dynamic[0][0] == "cdp_actuator"
