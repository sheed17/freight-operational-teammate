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


def test_dynamic_imports_are_detected():
    """An effect path hidden behind importlib is still an effect path."""
    import ast

    from phase0.import_probe import _module_name

    tree = ast.parse("import importlib\nm = importlib.import_module('cdp_actuator')\n")
    found = [n for node in ast.walk(tree) for n in _module_name(node)]
    dynamic = [f for f in found if f[3]]
    assert dynamic, "importlib.import_module('cdp_actuator') was not detected as a dynamic import"
    assert dynamic[0][0] == "cdp_actuator"
