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

    # 5. the EP-14 SWAP itself is count-neutral (old edge gone, new edge present, proved by 3 and 4
    #    above); live == recorded so neither side of the detection surface drifts. The exact total is
    #    pinned separately: it is the frozen residue PLUS exactly the one authorized P4 boundary edge
    #    (effect_boundary -> browser_use_write), which is proved by
    #    test_import_gate.py::test_the_p4_boundary_write_edge_is_the_one_authorized_addition. This
    #    test is scoped to the EP-14 relocation and must NOT also own the P4 boundary count.
    assert len(edges) == len(manifest.allowed_adapter_import_edges()), (
        f"detection surface is {len(edges)} against a manifest of "
        f"{len(manifest.allowed_adapter_import_edges())} - live and recorded must agree exactly"
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

    # 8. the violation count strictly shrank — and, since the P4 EP-1 write cut, reached EMPTY (the
    #    R-07 mechanical close condition). The EP-14 swap did not itself close R-07; it left exactly the
    #    EP-1 residual, which a later session (this one) cut. Either way the surface only shrinks.
    assert "scripts/read_tms_browser_use.py -> browser_use_adapter" not in violations
    assert len(violations) == 0, f"expected no residual effect-capable violations, got {sorted(violations)}"

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


def test_the_callback_servers_read_closures_are_structurally_read_only():  # EP-1 (partial), U4.11
    """EP-1's READ half. The callback server built five read closures over a mutation-capable
    session, and three of them held a `CdpActuator` purely to call `.observe()`.

    Worse, two of them SPLICED CALLER DATA INTO JAVASCRIPT SOURCE — `_JS + "(" + repr(load_ref) +
    ")"` — which is F2's exact defect, and one COMPOSED a target the page never published
    (`href.rstrip("/") + "/attachments"`), the generic-traversal shape EP-3 removed. All five now
    run on `cdp_readonly`; the column mapping and the document-name scrape are Python over a vetted
    observation, and the detail page is reached through an EP-3 provenance record.

    The read half was the FIRST half of EP-1; the write half is now CUT too (this session), so the
    callback server holds no actuator at all — proved separately by
    `test_the_callback_server_constructs_no_live_write_driver`. This guard remains the read-side wall:
    it fails if any of the five read closures regains a mutation-capable session, an actuator, a
    mutation verb, or a composed navigation target.
    """
    import ast

    path = ROOT / "scripts/run_action_callback_server.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    # Structural, by AST, not by substring: the file's own prose names the primitives it no longer
    # uses, and a text search would trip on that (the F1 defect in reverse).
    read_builders = {"_build_receivables_reader", "_build_tms_brief_reader",
                     "_build_load_amount_resolver", "_build_load_state_reader",
                     "_build_load_docs_reader"}
    seen = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in read_builders:
            continue
        seen.add(node.name)
        names = {n.module.split(".")[-1] for n in ast.walk(node)
                 if isinstance(n, ast.ImportFrom) and n.module}
        forbidden = names & {"cdp_actuator", "cdp_session"}
        assert not forbidden, (
            f"{node.name} imports {sorted(forbidden)} — a closure that only LOOKS at a page must "
            "not hold a mutation-capable session or an actuator"
        )
        called = {n.func.attr for n in ast.walk(node)
                  if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)}
        bad = called & {"evaluate", "command", "click", "type", "select", "upload_file",
                        "set_file_input", "navigate"}
        assert not bad, f"{node.name} invokes {sorted(bad)} on the browser surface"

        # Navigation targets are either CONFIGURATION or PROVENANCE — never composed.
        #
        # `visit()` legitimately takes the operator-configured entry URL, so banning it outright
        # would be wrong. What must never come back is the shape this closure actually had:
        # `href.rstrip("/") + "/attachments"` — a same-origin target NOBODY OBSERVED, assembled by
        # the caller, which is the generic traversal EP-3 removed. So the argument must be a plain
        # name or attribute (the configured URL), not an expression that builds a string. A load's
        # detail document is reached only through `follow(detail_link_for_load(...))`.
        for call in ast.walk(node):
            if not (isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
                    and call.func.attr == "visit" and call.args):
                continue
            target = call.args[0]
            assert isinstance(target, (ast.Name, ast.Attribute)), (
                f"{node.name} navigates to a COMPOSED target "
                f"({ast.dump(target)[:60]}...). A URL the page never published is not reachable by "
                "provenance: use detail_link_for_load()/follow(), or pass the configured entry URL."
            )

    assert seen == read_builders, f"a read closure disappeared or was renamed: {read_builders - seen}"

    # No caller-authored JavaScript anywhere in the file. `location.href=` assignment and a
    # `_JS + "(" + repr(x) + ")"` splice are the two shapes EP-1's reads actually used.
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str) and "querySelectorAll" in node.value.value:
            raise AssertionError(
                "a JavaScript blob is back in the callback server — the read closures build their "
                "results from vetted observations, not from scripts the caller composes"
            )


def test_the_callback_server_constructs_no_live_write_driver():  # EP-1 write CUT (this session)
    """EP-1's write is CUT. The callback server used to construct a live browser-write driver — the
    `_build_agent` factory built a `CdpBrowserSession` + `CdpActuator` + `OperatorAgent`, and the
    Slack approval handler drove it (`router.run`), the callback DIRECTLY executing an external
    effect. That whole factory (`_build_live_operation_router`) is DELETED, not disabled.

    This guard is the INVERSE of the one it replaces (which asserted the actuator lived in exactly one
    named factory): now NO live-write driver is constructed ANYWHERE in the file, no effect-capable
    adapter is imported, and the edge is gone from both DETECTION and the VIOLATION surface. A
    resurrected actuator construction or import fails HERE, on the worked example, with EP-1's name.
    """
    import ast

    path = ROOT / "scripts/run_action_callback_server.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))

    # No CdpActuator / CdpBrowserSession / OperatorAgent construction ANYWHERE in the file (AST Call
    # over the whole tree — the nested-factory carve-out is gone because the factory itself is gone).
    constructed = {n.func.id for n in ast.walk(tree)
                   if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    live_write_drivers = {"CdpActuator", "CdpBrowserSession", "OperatorAgent"}
    resurrected = constructed & live_write_drivers
    assert not resurrected, (
        f"the callback server constructs live write driver(s) {sorted(resurrected)} again — EP-1's "
        "write was CUT; the only external-write path is effect_boundary.execute_invoice_write (dark)"
    )

    # No effect-capable adapter import at all: the file must reach NO adapter module that can write.
    imported = {n.module.split(".")[-1] for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom) and n.module}
    imported |= {a.name.split(".")[-1] for n in ast.walk(tree)
                 if isinstance(n, ast.Import) for a in n.names}
    forbidden = imported & (import_probe.EFFECT_CAPABLE_ADAPTERS | {"cdp_session"})
    assert not forbidden, (
        f"the callback server imports adapter module(s) {sorted(forbidden)} again — it must reach the "
        "browser only via cdp_readonly, which is not an adapter module"
    )

    # The edge is gone from DETECTION and is NOT a live violation.
    assert "scripts/run_action_callback_server.py -> cdp_actuator" not in _edges()
    assert "scripts/run_action_callback_server.py -> cdp_session" not in _edges()
    assert "scripts/run_action_callback_server.py -> cdp_actuator" not in \
        import_probe.effect_adapter_violation_edges()


def test_dynamic_imports_are_detected():
    """An effect path hidden behind importlib is still an effect path."""
    import ast

    from phase0.import_probe import _module_name

    tree = ast.parse("import importlib\nm = importlib.import_module('cdp_actuator')\n")
    found = [n for node in ast.walk(tree) for n in _module_name(node)]
    dynamic = [f for f in found if f[3]]
    assert dynamic, "importlib.import_module('cdp_actuator') was not detected as a dynamic import"
    assert dynamic[0][0] == "cdp_actuator"
