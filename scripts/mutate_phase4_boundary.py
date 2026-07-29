#!/usr/bin/env python3
"""Safe in-memory mutation battery for the P4 adapter-containment boundary.

Doctrine (CLAUDE.md sec 9), identical to the P3 batteries:
  * original bytes are held IN MEMORY - never `git checkout/restore/stash/clean`
  * __pycache__ is purged around every mutation, or a same-length restore within one mtime tick
    leaves poisoned bytecode and reports a false green
  * a guard that does NOT fail on the mutant proves nothing and is reported as a MISS
  * restoration is verified byte-for-byte, and the guard must be GREEN again before moving on
  * every case states the REAL defect it reintroduces; a mutation that reintroduces nothing proves
    nothing, so the cases target load-bearing invariants of the boundary, not decoration

WHAT THIS AUDITS: `src/freight_recon/effect_boundary.py` (the containment boundary) and
`eval/phase0/import_probe.py` (the boundary-aware import gate), plus one CREATE mutation that
resurrects a deleted effect path to prove the deletion is guarded, not merely done.

### THIS IS NOT AN INDEPENDENT REVIEW. It was written by the session that implemented P4. A battery
that agrees with its author is evidence, never adjudication - the independent reviewer runs its own.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv/bin/python"
EB = "src/freight_recon/effect_boundary.py"
PROBE = "eval/phase0/import_probe.py"
EP12 = "scripts/enter_tms_payable.py"
BRAIN = "src/freight_recon/brain_runtime.py"
EP8 = "scripts/orient_tms.py"
EP3 = "scripts/propose_ar_from_tms.py"
RO = "src/freight_recon/cdp_readonly.py"
BUA = "src/freight_recon/browser_use_adapter.py"
RTB = "scripts/read_tms_browser_use.py"
EP1 = "scripts/run_action_callback_server.py"
GWR = "src/freight_recon/governed_write_route.py"
GA = "src/freight_recon/governed_approval.py"
GWREG = "src/freight_recon/governed_write_registry.py"
ACALL = "src/freight_recon/action_callback.py"

AC = "eval/tests/test_adapter_boundary_acceptance.py"
GATE = "eval/tests/test_import_gate.py"
HERM = "eval/tests/test_bootstrap_hermeticity.py"
IMPORTS = "eval/tests/test_phase0_adapter_imports.py"
NAV = "eval/tests/test_cdp_readonly_navigation.py"
BUR = "eval/tests/test_browser_use_readonly_surface.py"
P4W = "eval/tests/test_p4_governed_invoice_write.py"
P4R = "eval/tests/test_p4_governed_write_route.py"
P4D = "eval/tests/test_p4_deployed_governed_route.py"
MANIFEST = "docs/implementation/phase-0-baseline-manifest.yaml"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    """True when the guard PASSES."""
    r = subprocess.run([str(PY), "-m", "pytest", nodeid, "-q", "-p", "no:randomly"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


class SetupFailure(RuntimeError):
    pass


# ---------------------------------------------------------------------------------------------
# TEXT cases: (label, rel_file, old, new, guard_nodeid). The old string must be present exactly
# once (a no-op or an ambiguous anchor is a SETUP-FAIL, never a MISS).
# ---------------------------------------------------------------------------------------------
TEXT_CASES = [
    ("B1  grant validation removed: a refused claim proceeds to touch the world",
     EB,
     "    if not claim.claimed:",
     "    if not claim.claimed and False:  # MUTANT",
     f"{AC}::test_missing_grant_refuses_and_touches_nothing"),

    ("B2  single-use defeated: a consumed capability is accepted a second time",
     EB,
     "    if cap._consumed:",
     "    if cap._consumed and False:  # MUTANT",
     f"{AC}::test_capability_is_single_use"),

    ("B3  tenant guard bypassed: a cross-tenant call is not refused before the claim",
     EB,
     "    if params.tenant.strip().lower() != kernel.store.tenant.strip().lower():",
     "    if False and params.tenant.strip().lower() != kernel.store.tenant.strip().lower():  # MUTANT",
     f"{AC}::test_wrong_tenant_params_are_refused_before_any_claim"),

    ("B4  attempt not recorded before the call: an orphan becomes undetectable",
     EB,
     "    record_effect_attempted(kernel, grant_id=grant_id, params=params)",
     "    pass  # MUTANT: skip the EffectAttempted record",
     f"{AC}::test_valid_claimed_grant_reaches_exactly_one_adapter_call_and_verifies"),

    ("B5  health-signal gate bypassed: a blind readback is no longer OBSERVATION_UNAVAILABLE",
     EB,
     "    if not observation.health_signal:",
     "    if False and not observation.health_signal:  # MUTANT",
     f"{AC}::test_ef4u_blind_readback_is_unavailable_never_verified_failure"),

    ("B6  UNKNOWN downgraded to FAILED (EF-3u): an ambiguous attempt is marked FAILED",
     EB,
     "            kernel, grant_id, to=UNKNOWN_OUTCOME,\n"
     "            unknown_reason=UnknownReason.UNKNOWN_OUTCOME,",
     "            kernel, grant_id, to=FAILED,  # MUTANT\n"
     "            unknown_reason=UnknownReason.UNKNOWN_OUTCOME,",
     f"{AC}::test_ef3u_ambiguous_attempt_is_unknown_never_failed"),

    ("B7  CONFLICTING downgraded to FAILED (EF-4c / AC-ADPT-015)",
     EB,
     "            kernel, grant_id, to=UNKNOWN_OUTCOME,\n"
     "            verification_outcome=VerificationOutcome.OBSERVATION_CONFLICTING,",
     "            kernel, grant_id, to=FAILED,  # MUTANT\n"
     "            verification_outcome=VerificationOutcome.OBSERVATION_CONFLICTING,",
     f"{AC}::test_ef4c_conflicting_readback_is_unknown_not_failed"),

    ("B8  UNKNOWN auto-resolves: the WHO/decision-ref requirement is dropped (EF-5x)",
     EB,
     '    if not str(decision_ref or "").strip() or not str(established_by or "").strip():',
     '    if False and (not str(decision_ref or "").strip() or not str(established_by or "").strip()):  # MUTANT',
     f"{AC}::test_ef5_unknown_resolves_only_by_human_or_proof"),

    ("B9  import gate weakened: a non-boundary effect-adapter import is no longer a violation",
     PROBE,
     "    return _importer_stem(site.module) not in allowed",
     "    return False  # MUTANT: nothing is a violation",
     f"{GATE}::test_a_new_non_boundary_effect_import_is_caught"),

    ("B11 orphan detection disabled: every EffectAttempted is treated as healthy",
     EB,
     '        if grant is not None and grant["state"] in CLAIMED_OR_LATER:',
     '        if True:  # MUTANT: never an orphan',
     f"{AC}::test_orphan_detector_is_not_vacuous_and_auto_engages_the_brake"),

    ("B12 orphan brake disabled: a Sev-0 orphan no longer auto-engages the brake",
     EB,
     "        kernel.brakes.engage(\n"
     "            tenant=kernel.store.tenant, action_class=params.action_class,\n"
     '            actor="orphan-effect-detector"',
     "        kernel.brakes.DISABLED_engage(  # MUTANT\n"
     "            tenant=kernel.store.tenant, action_class=params.action_class,\n"
     '            actor="orphan-effect-detector"',
     f"{AC}::test_orphan_detector_is_not_vacuous_and_auto_engages_the_brake"),

    ("B13 cross-tenant GLOBAL brake disabled: a cross-tenant breach no longer trips the platform brake",
     EB,
     "        kernel.brakes.engage(\n"
     '            tenant=None, actor="cross-tenant-detector"',
     "        kernel.brakes.DISABLED_engage(  # MUTANT\n"
     '            tenant=None, actor="cross-tenant-detector"',
     f"{AC}::test_ac_adpt_016_cross_tenant_is_contained_and_globally_braked"),

    ("B14 adapter constructs authority: a forged capability passes the genuine-registry check",
     EB,
     "    if cap not in _GENUINE_CAPABILITIES:",
     "    if cap not in _GENUINE_CAPABILITIES and False:  # MUTANT",
     f"{AC}::test_forged_capability_is_refused"),

    ("B15 F4: a generic post-attempt exception is laundered into FAILED (no proof of non-occurrence)",
     EB,
     "                kernel, grant_id, to=UNKNOWN_OUTCOME,\n"
     "                unknown_reason=UnknownReason.UNKNOWN_OUTCOME,\n"
     '                payload={"unknown_detail": f"post-attempt adapter exception: "',
     "                kernel, grant_id, to=FAILED,  # MUTANT\n"
     "                unknown_reason=UnknownReason.UNKNOWN_OUTCOME,\n"
     '                payload={"unknown_detail": f"post-attempt adapter exception: "',
     f"{AC}::test_f4_generic_exception_is_never_laundered_into_failed"),

    ("B16 F4: a generic post-attempt exception leaves the grant stuck in CLAIMED (invisible to the sweep)",
     EB,
     "                kernel, grant_id, to=UNKNOWN_OUTCOME,\n"
     "                unknown_reason=UnknownReason.UNKNOWN_OUTCOME,\n"
     '                payload={"unknown_detail": f"post-attempt adapter exception: "',
     '                kernel, grant_id, to="CLAIMED",  # MUTANT: grant never leaves CLAIMED\n'
     "                unknown_reason=UnknownReason.UNKNOWN_OUTCOME,\n"
     '                payload={"unknown_detail": f"post-attempt adapter exception: "',
     f"{AC}::test_f4_generic_post_attempt_exception_leaves_unknown_never_claimed"),

    # B17/B18 anchor on lines WITHOUT a ratcheted deprecated term, so this harness never spreads the
    # frozen mock-ledger vocabulary into scripts/ (the deprecated-vocabulary ratchet counts scripts/*.py).
    ("B17 F1: a quarantine importer regains a live-reaching effect-adapter import (a live bypass mislabelled quarantine)",
     EP12,
     "from freight_recon.cli_tenant import resolve_cli_tenant",
     "from freight_recon.cli_tenant import resolve_cli_tenant\n"
     "from freight_recon.cdp_actuator import CdpActuator  # noqa: E402,F401  # MUTANT: live import",
     f"{GATE}::test_every_quarantine_importer_is_structurally_production_unreachable"),

    ("B18 F1: a quarantine importer constructs a live write driver while still building the mock (substring check would pass)",
     EP12,
     "    charges = []",
     "    charges = []; _live = CdpActuator(None)  # MUTANT: constructs a live write driver",
     f"{GATE}::test_every_quarantine_importer_constructs_the_mock_and_no_live_driver"),

    ("B19 P4: brain_runtime re-imports the effect path (the injection containment is undone)",
     BRAIN,
     "from freight_recon.operator_brain import FlowStep, StepAction, StepResult",
     "from freight_recon.operator_brain import FlowStep, StepAction, StepResult\n"
     "from freight_recon.tms_write import enter_approved_payable  # noqa: F401  # MUTANT: re-import the effect path",
     f"{GATE}::test_brain_runtime_holds_no_effect_capable_import"),

    ("B20 P4: the detective sweep stops running the orphan detector (an orphan goes unbraked)",
     EB,
     "    orphans = detect_orphan_effect_attempts(kernel)\n"
     "    unknowns = pending_unknown_outcomes(kernel)",
     "    orphans = []  # MUTANT: the loop no longer reconciles EffectAttempted records\n"
     "    unknowns = pending_unknown_outcomes(kernel)",
     f"{AC}::test_detective_sweep_finds_orphans_brakes_and_surfaces_unknowns"),

    ("B21 P4: the detective sweep drops the unknown-outcome queue (an UNKNOWN grant goes invisible)",
     EB,
     "    orphans = detect_orphan_effect_attempts(kernel)\n"
     "    unknowns = pending_unknown_outcomes(kernel)",
     "    orphans = detect_orphan_effect_attempts(kernel)\n"
     "    unknowns = []  # MUTANT: unknown outcomes never surface for human resolution",
     f"{AC}::test_detective_sweep_finds_orphans_brakes_and_surfaces_unknowns"),

    # ---- U4.7 / EP-8: the read-only cut must be a mechanism, not a convention ----------------
    # EP-8's original defect was precisely that nothing failed when a "read-only" script held an
    # actuator. These three prove the cut is now load-bearing: re-import the actuator, re-import
    # the mutation-capable session, or smuggle either in dynamically, and a guard fires.

    ("B22 U4.7/EP-8: the read-only orientation tool re-imports the actuator (the exact regression)",
     EP8,
     "from freight_recon.cdp_readonly import ReadOnlyCdpObserver  # noqa: E402",
     "from freight_recon.cdp_actuator import CdpActuator  # noqa: E402,F401  # MUTANT: actuator back\n"
     "from freight_recon.cdp_readonly import ReadOnlyCdpObserver  # noqa: E402",
     f"{IMPORTS}::test_orient_tms_is_structurally_read_only_not_read_only_by_convention"),

    ("B23 U4.7/EP-8: it re-imports the mutation-capable session (F2's evaluate/command primitive)",
     EP8,
     "from freight_recon.cdp_readonly import ReadOnlyCdpObserver  # noqa: E402",
     "from freight_recon.cdp_readonly import ReadOnlyCdpObserver  # noqa: E402\n"
     "from freight_recon.cdp_session import CdpBrowserSession  # noqa: E402,F401  # MUTANT: session back",
     f"{IMPORTS}::test_orient_tms_is_structurally_read_only_not_read_only_by_convention"),

    ("B24 U4.7/EP-8: the actuator is smuggled in dynamically rather than by a static import",
     EP8,
     "    kb = KnowledgeBase(",
     "    __import__('freight_recon.cdp_actuator')  # MUTANT: dynamic actuator acquisition\n"
     "    kb = KnowledgeBase(",
     f"{IMPORTS}::test_orient_tms_is_structurally_read_only_not_read_only_by_convention"),

    # ---- U4.8 / EP-3: the read-only navigation cut ------------------------------------------
    # EP-3's defect was navigation by arbitrary JavaScript plus a click fallback. These prove the
    # cut is load-bearing: bring back the actuator, the evaluate-navigation, or the click.

    ("B25 U4.8/EP-3: the AR proposal tool re-imports the actuator",
     EP3,
     "from freight_recon.cdp_readonly import ReadOnlyCdpNavigator  # noqa: E402",
     "from freight_recon.cdp_actuator import CdpActuator  # noqa: E402,F401  # MUTANT: actuator back\n"
     "from freight_recon.cdp_readonly import ReadOnlyCdpNavigator  # noqa: E402",
     f"{IMPORTS}::test_propose_ar_from_tms_reaches_the_browser_read_only"),

    ("B26 U4.8/EP-3: evaluate-based navigation returns (caller data interpolated into JavaScript)",
     EP3,
     "    act.visit(loads_url)\n    observation = act.observe()",
     "    act.session.evaluate(f\"location.href={loads_url!r}\")  # MUTANT: F2's defect restored\n"
     "    observation = act.observe()",
     f"{IMPORTS}::test_propose_ar_from_tms_reaches_the_browser_read_only"),

    ("B27 U4.8/EP-3: the deleted click fallback comes back for the POD detail read",
     EP3,
     "        if not bool(act.follow(link)):",
     "        if not bool(act.click(load_ref)):  # MUTANT: a SPA onclick can POST an invoice",
     f"{IMPORTS}::test_propose_ar_from_tms_reaches_the_browser_read_only"),

    # ---- EP-3 HOSTILE REVIEW OBLIGATION: a same-origin page-published href is NOT read-only -----
    # The reviewer premise these five defend: legacy systems expose state-changing GET routes, so
    # "the page published this link" is provenance, never authority. Each mutant reopens exactly
    # one of the four provenance barriers and must be caught.

    ("B28 U4.8/EP-3: follow() becomes a generic follower of any observed same-origin anchor",
     RO,
     "        if not (text_bound or path_bound):",
     "        if False:  # MUTANT: row containment alone is treated as authority",
     f"{NAV}::test_no_hostile_shape_in_the_loads_own_row_is_ever_followed"),

    ("B28a U4.8/EP-3: the route-family check stops refusing consequential action routes "
     "(/loads/101/delete, /approve, /pay, /logout become followable)",
     RO,
     "    hits = sorted(t for t in path_tokens if _is_action_token(t, ACTION_ROUTE_TOKENS))\n"
     "    if hits:",
     "    hits = sorted(t for t in path_tokens if _is_action_token(t, ACTION_ROUTE_TOKENS))\n"
     "    if False:  # MUTANT: action routes classify as observational",
     f"{NAV}::test_no_hostile_shape_in_the_loads_own_row_is_ever_followed"),

    ("B28b U4.8/EP-3: the anchor-shape check stops refusing data-method=delete "
     "(a link by tag, a DELETE by behaviour)",
     RO,
     "        if name in attrs and _norm(attrs[name]) not in (\"\", \"get\"):",
     "        if False:  # MUTANT: verb-smuggling anchors are plain links again",
     f"{NAV}::test_no_hostile_shape_in_the_loads_own_row_is_ever_followed"),

    ("B28c U4.8/EP-3: identity binding degrades to substring matching (L-101 selects L-1010, "
     "and 'Delete L-101' selects by containment)",
     RO,
     "        text_bound = _norm(link.get(\"text\")) == lid",
     "        text_bound = lid in _norm(link.get(\"text\"))  # MUTANT: brittle substring match",
     f"{NAV}::test_identity_binding_never_decides_by_substring"),

    ("B28d U4.8/EP-3: follow() trusts the caller's record instead of re-deriving it from the live "
     "page (a forged, well-formed provenance record is accepted)",
     RO,
     "        if current != link:",
     "        if False:  # MUTANT: a forged provenance record is accepted",
     f"{NAV}::test_follow_re_derives_the_record_from_the_live_page"),

    ("B28e U4.8/EP-3: stale provenance is accepted (a record minted against an earlier document is "
     "replayable after the page changed underneath it)",
     RO,
     "        if link.context_seq != self.__context_seq:",
     "        if False:  # MUTANT: stale records replay",
     f"{NAV}::test_a_record_minted_before_a_navigation_is_stale"),

    ("B28f U4.8/EP-3: the caller bills a load whose POD it could not prove, because an unbindable "
     "detail link stops blocking the money button",
     EP3,
     "        if link is None:\n            return None",
     "        if link is None:\n            return True  # MUTANT: unproven POD becomes a greenlight",
     "eval/tests/test_operation_proposal.py"
     "::test_an_unbindable_detail_link_leaves_the_pod_unknown_and_posts_no_money_button"),

    ("B29 U4.8/EP-3: the navigation channel admits arbitrary JavaScript again",
     RO,
     "        if method not in NAVIGATION_CDP_METHODS:",
     "        if method not in (NAVIGATION_CDP_METHODS | {'Runtime.evaluate'}):  # MUTANT",
     f"{NAV}::test_the_navigation_channel_refuses_every_other_method"),

    # Two functions carry a scheme allowlist (the navigation target check and the route-family
    # classifier). Each is anchored separately, because a mutant that reopened only one of them
    # while the other stayed shut would otherwise be reported as caught by the wrong guard.
    # B30 WAS "the navigation scheme allowlist stops refusing javascript: URLs", disabling only the
    # `_REFUSED_SCHEMES` denylist inside navigation_target_is_allowed. After the F-02 remediation
    # that mutant reintroduces NO defect and was correctly reported as a MISS: the parsed-origin
    # policy refuses `javascript:` independently, because its scheme is not http/https. Exactly the
    # situation B30a already documents for the route classifier - a redundancy that a single-rule
    # mutant cannot defeat. Retargeted, per CLAUDE.md sec 9, at the decision whose removal DOES
    # reintroduce a real, reachable defect: the ORIGIN comparison itself, i.e. finding F-02.
    ("B30 F-02/EP-3: the navigation origin policy stops refusing cross-origin targets, so a "
     "page-published link to another origin is navigable again (the exact fail-open the "
     "independent review found)",
     RO,
     "    if candidate != established:\n",
     "    if False:  # MUTANT: cross-origin navigation is allowed again (F-02 reintroduced)\n",
     f"{NAV}::test_a_cross_origin_link_is_refused_with_an_empty_or_absent_filter"),

    # B30b: the OTHER half of F-02 - the fail-closed default. An absent/empty origin configuration
    # must refuse, never degrade to "allow everything", which is what url_matches_filter did.
    ("B30b F-02/EP-3: an absent origin configuration fails OPEN again instead of closed, so an "
     "empty --operation-url-filter means 'allow every target'",
     RO,
     "    established = parse_origin(established_origin) if established_origin else None\n"
     "    if established is None:\n",
     "    established = parse_origin(established_origin) if established_origin else None\n"
     "    if False:  # MUTANT: no established origin means no restriction (F-02 reintroduced)\n",
     f"{NAV}::test_no_established_origin_refuses_everything_rather_than_allowing_everything"),

    # B30c: the origin check is removed from link SELECTION specifically. navigation_target_is_allowed
    # could still be correct while select_load_detail_link never consults it - which is precisely
    # what the reviewer found ("select_load_detail_link performs no independent origin check").
    ("B30c F-02/EP-3: select_load_detail_link stops applying the origin policy to page-published "
     "hrefs, so a cross-origin link whose text matches the load is provenance-selectable again",
     RO,
     "        origin_refusal = link_origin_refusal(\n"
     "            href, resolved, url_filter=url_filter, established_origin=established_origin)\n"
     "        if origin_refusal:\n",
     "        origin_refusal = link_origin_refusal(\n"
     "            href, resolved, url_filter=url_filter, established_origin=established_origin)\n"
     "        if False:  # MUTANT: the selector ignores the origin policy entirely (F-02 reintroduced)\n",
     f"{NAV}::test_a_link_whose_text_matches_the_load_but_whose_href_is_foreign_is_refused"),

    # B30a removes the route classifier's scheme containment ENTIRELY (denylist AND http/https
    # allowlist together). An earlier cut of this case disabled only the denylist and was reported
    # as a MISS - correctly, because the allowlist still refused `javascript:`, so the mutant
    # reintroduced no defect. The two rules are redundant on purpose; the mutant that proves they
    # are load-bearing has to remove both, which is why they live in one function.
    ("B30a U4.8/EP-3: the route classifier's scheme containment is removed, so a javascript: anchor "
     "in the load's row classifies as an observational document",
     RO,
     '    u = str(href or "").strip()\n'
     "    if u.lower().startswith(_REFUSED_SCHEMES):",
     '    u = str(href or "").strip()\n'
     '    return ""  # MUTANT: every scheme is an ordinary document fetch\n'
     "    if u.lower().startswith(_REFUSED_SCHEMES):",
     f"{NAV}::test_the_classifier_fails_closed_on_non_documents"),

    # ---- U4.10 / EP-14: the browser-use read/write split ------------------------------------
    # EP-14's defect was a module that CLAIMED to be a read-only browser-use adapter while holding
    # a payable write ledger and a driver that runs an arbitrary task. These prove the split is
    # load-bearing: put the write half back, restore caller-authored tasks, or make the relocation
    # a growth instead of a swap, and a guard fires.

    ("B31 U4.10/EP-14: the read adapter regains a generic run(task) transport, so a caller can "
     "author any browser-agent task again (read-only by naming, the original defect)",
     BUA,
     "    async def run_vetted(\n"
     "        self, task_id: str, *, base_url: str, load_id: str,\n"
     "        allowed_domains: list[str] | None = None, headless: bool = False,\n"
     "    ) -> str:\n"
     "        task = render_vetted_task(task_id, base_url=base_url, load_id=load_id)",
     "    async def run(self, task: str, **_kw) -> str:  # MUTANT: caller-authored task\n"
     "        return task\n\n"
     "    async def run_vetted(\n"
     "        self, task_id: str, *, base_url: str, load_id: str,\n"
     "        allowed_domains: list[str] | None = None, headless: bool = False,\n"
     "    ) -> str:\n"
     "        task = render_vetted_task(task_id, base_url=base_url, load_id=load_id)",
     f"{BUR}::test_the_read_runner_has_no_generic_run_method"),

    ("B32 U4.10/EP-14: the vetted-task registry stops refusing an unknown task id, so a "
     "caller-supplied sentence becomes the browser agent's task",
     BUA,
     "    if template is None:",
     "    if template is None and False:  # MUTANT: any task id renders",
     f"{BUR}::test_a_caller_authored_task_cannot_be_smuggled_through_the_task_id"),

    ("B33 U4.10/EP-14: the read adapter is reclassified effect-capable-free by DECLARATION while "
     "still importing the write half (an effect import moved into a read-only module)",
     BUA,
     "from .tms_adapter import TmsAdapterError, TmsLoadReadback, TmsPayableReadback",
     "from .browser_use_write import BrowserUseWriteLedger  # noqa: F401  # MUTANT: write reachable\n"
     "from .tms_adapter import TmsAdapterError, TmsLoadReadback, TmsPayableReadback",
     f"{BUR}::test_the_read_module_imports_no_effect_capable_adapter"),

    ("B34 U4.10/EP-14: the probe is weakened instead of the architecture - browser_use_adapter is "
     "declared non-effect-capable while nothing about the module changed",
     PROBE,
     '    "cdp_actuator", "browser_tms_adapter",',
     '    "browser_tms_adapter",  # MUTANT: cdp_actuator quietly reclassified out',
     f"{GATE}::test_a_new_non_boundary_effect_import_is_caught"),

    ("B35 U4.10/EP-14: a SCRIPT gains a direct import of the effect-capable write half (a new "
     "application bypass that the edge COUNT alone would not notice)",
     RTB,
     "from freight_recon.browser_use_adapter import BrowserUseConfig, BrowserUseTmsAdapter  # noqa: E402",
     "from freight_recon.browser_use_adapter import BrowserUseConfig, BrowserUseTmsAdapter  # noqa: E402\n"
     "from freight_recon.browser_use_write import BrowserUseWriteLedger  # noqa: E402,F401  # MUTANT",
     f"{IMPORTS}::test_the_ep14_relocation_is_a_swap_not_a_growth"),

    # ---- U4.11 / EP-1 (READ HALF): the callback server's read closures --------------------------
    # EP-1's read closures held an actuator purely to call .observe(), spliced the load ref into
    # JavaScript source, and composed a /attachments URL the page never published. These prove the
    # cut is load-bearing. EP-1's WRITE path is not cut and is guarded separately (B39).

    ("B36 U4.11/EP-1: a read closure regains a mutation-capable session (it only ever wanted to LOOK)",
     EP1,
     "    from freight_recon.cdp_readonly import ReadOnlyCdpNavigator\n"
     "    from freight_recon.operation_proposal import load_row_from_loads_table",
     "    from freight_recon.cdp_session import CdpBrowserSession  # MUTANT: session back\n"
     "    from freight_recon.cdp_readonly import ReadOnlyCdpNavigator\n"
     "    from freight_recon.operation_proposal import load_row_from_loads_table",
     f"{IMPORTS}::test_the_callback_servers_read_closures_are_structurally_read_only"),

    ("B37 U4.11/EP-1: caller data is spliced into JavaScript source again (F2's exact defect, in "
     "the closure that used to do it)",
     EP1,
     "                return load_row_from_loads_table(act.observe(), load_ref)",
     "                return act.evaluate(_JS + '(' + repr(str(load_ref)) + ')')  # MUTANT",
     f"{IMPORTS}::test_the_callback_servers_read_closures_are_structurally_read_only"),

    ("B38 U4.11/EP-1: the docs reader composes an unobserved /attachments URL again instead of "
     "following a provenance-bound detail link",
     EP1,
     "                link = act.detail_link_for_load(str(load_ref))",
     "                act.visit(loads_url.rstrip('/') + '/attachments')  # MUTANT: composed target\n"
     "                link = act.detail_link_for_load(str(load_ref))",
     f"{IMPORTS}::test_the_callback_servers_read_closures_are_structurally_read_only"),

    ("B39 U4.11/EP-1 WRITE CUT: ANY live write driver is constructed in the callback server (the "
     "write is fully cut now — there is no 'single named factory' left, so any actuator is caught)",
     EP1,
     "    lock = BrowserLock(lock_path) if lock_path else None\n\n"
     "    def _resolve(load_ref: str)",
     "    lock = BrowserLock(lock_path) if lock_path else None\n"
     "    _live = CdpActuator(CdpBrowserSession(cdp_url=cdp_url))  # MUTANT: resurrected effect route\n\n"
     "    def _resolve(load_ref: str)",
     f"{IMPORTS}::test_the_callback_server_constructs_no_live_write_driver"),

    # ---- U4.12 / EP-1 (WRITE HALF): the callback server's live actuator route is CUT ------------
    # EP-1's write was the OperationRouter -> OperatorAgent autonomous browser WRITE, built by
    # _build_live_operation_router (CdpActuator + CdpBrowserSession + OperatorAgent) and driven by the
    # Slack approval handler (router.run) — the callback directly executing an external effect. That
    # factory is DELETED and the effect-capable violation surface is EMPTY. These prove the cut and
    # the gate flip are LOAD-BEARING: resurrect the import, resurrect the construction, lie in the
    # manifest, or drop the boundary's capability check, and a guard fires.

    ("B40 EP-1 WRITE CUT: the callback server re-imports the effect-capable actuator, and the "
     "boundary-aware gate flags a NEW unrecorded violation (the EMPTY surface would catch a bypass)",
     EP1,
     "from freight_recon.action_callback import run_callback_server  # noqa: E402",
     "from freight_recon.action_callback import run_callback_server  # noqa: E402\n"
     "from freight_recon.cdp_actuator import CdpActuator  # noqa: E402,F401  # MUTANT: actuator back",
     f"{GATE}::test_no_unrecorded_effect_violation_exists"),

    ("B41 EP-1 WRITE CUT: the EMPTY-surface assertion is not vacuous — a resurrected actuator import "
     "makes the direct 'violation surface is empty' assertion FAIL",
     EP1,
     "from freight_recon.action_callback import run_callback_server  # noqa: E402",
     "from freight_recon.action_callback import run_callback_server  # noqa: E402\n"
     "from freight_recon.cdp_actuator import CdpActuator  # noqa: E402,F401  # MUTANT: actuator back",
     f"{GATE}::test_the_effect_capable_violation_surface_is_empty"),

    ("B42 EP-1 WRITE CUT: the manifest LIES that the surface is empty — a recorded residual with no "
     "live edge is caught by the both-sided gate (the EMPTY claim cannot be faked by padding)",
     MANIFEST,
     "  violation_edges: []",
     "  violation_edges: [scripts/phantom_bypass.py -> cdp_actuator]  # MUTANT: recorded, not live",
     f"{GATE}::test_no_recorded_violation_is_stale"),

    ("B43 EP-1 WRITE CUT: the governed route's capability check is dropped, so a raw object executes "
     "a bounded write with NO claimed grant (removing the checkpoint/grant/claim path must FAIL)",
     EB,
     "        consume_capability(cap, op_id=op_id)                       # prove authority or raise",
     "        pass  # MUTANT: skip capability consumption — no claimed grant required",
     f"{P4W}::test_the_bounded_perform_refuses_a_capability_it_was_not_handed"),

    # ---- F-01: THE GOVERNED JOIN. The independent review's central finding was that the
    # decision half and the execution half shared no authority: build_checkpoint_approval had zero
    # callers and GovernedWriteIntentQueued had no consumer. These four mutants prove the join is
    # LOAD-BEARING, not decorative — remove any part of it and a guard fails loudly.

    ("B44 F-01: the governed route stops calling build_checkpoint_approval and mints its own "
     "ApprovalRecord instead, so the executed grant is authorized by an identity the human never "
     "signed (the exact two-disconnected-halves defect)",
     GWR,
     "    checkpoint_approval = build_checkpoint_approval(          # <-- THE PRODUCTION CALLER (F-01)",
     "    from .checkpoint import ApprovalRecord as _AR  # MUTANT: bypass the join\n"
     "    checkpoint_approval = _AR(  # MUTANT: no longer derived from the human's decision\n"
     "        approval_id='ap-1', tenant=op.tenant, actor_id='owner:rasheed', actor_kind='HUMAN',\n"
     "        authority=authority, state='GRANTED', fingerprint=fingerprint(fact_set),\n"
     "        canonical_payload=payload_bytes, fingerprint_version='fp_v1',\n"
     "        entity_versions=versions, policy_version=facts.policy_version,\n"
     "        granted_at=_utc(now), expires_at=_utc(now) + approval_ttl)\n"
     "    _unused_build_checkpoint_approval = (",
     f"{P4R}::test_the_full_order_runs_through_the_real_entry_point_with_one_identity"),

    ("B45 F-01: the queued-intent consumer stops reading the queue, so 'advancing the governed "
     "pipeline' terminates in an unread log event again",
     GWR,
     "    intents = queued_write_intents(store, approval_id=approval.approval_id)\n"
     "    if not intents:",
     "    intents = []  # MUTANT: the queue is never read\n"
     "    if False:",
     f"{P4R}::test_the_consumer_refuses_when_nothing_was_queued"),

    ("B46 F-01: the consumption boundary stops binding the approval IDENTITY, so an approval for "
     "one Work Item can authorize a grant for another",
     GWR,
     "    if not _same(approval.approval_id, op.approval_id):",
     "    if False:  # MUTANT: approval identity is no longer bound",
     f"{P4R}::test_every_binding_is_load_bearing_at_the_consumption_boundary"),

    ("B47 F-01: the single-consumption claim is dropped, so two simultaneous consumers of one "
     "queued intent can both proceed toward an external attempt",
     GWR,
     "    if not store.claim_operation_action(\n",
     "    if False and not store.claim_operation_action(  # MUTANT: consumption is no longer single-use\n",
     f"{P4R}::test_a_restart_after_the_claim_cannot_blind_duplicate"),

    ("B48 F-01: the authenticated envelope stops binding approval_id to the operation, so a token "
     "signed for a DIFFERENT approval of the same facts verifies",
     GA,
     "    if not _eq(approval.approval_id, op.approval_id):",
     "    if False:  # MUTANT: the envelope's approval identity is unbound",
     f"{P4R}::test_a_mismatched_approval_id_is_refused"),

    # ---- F-01 (DEPLOYED HALF): the entry point must actually reach the governed route, and the
    # callback must never be able to supply the operation. These prove the deployed wiring and the
    # repository's integrity anchor are load-bearing, not decorative.

    ("B49 F-01 DEPLOYED: run_action_callback_server stops wiring the governed route, so the real "
     "server can never reach the chain (the unremediated half of F-01)",
     EP1,
     "    governed_write_provider, governed_write_kernel = _build_governed_write_route(",
     "    governed_write_provider, governed_write_kernel = (None, None)  # MUTANT: route unwired\n"
     "    _unused = (_build_governed_write_route,) and (",
     f"{P4D}::test_the_deployed_entry_point_wires_the_governed_route"),

    ("B50 F-01 DEPLOYED: the pending-write repository stops checking the recorded payload hash, so "
     "a tampered stored operation authorizes a DIFFERENT effect than the human signed",
     GWREG,
     '        if op.payload_hash() != str(record.get("payload_hash", "")):',
     "        if False:  # MUTANT: the integrity anchor is gone",
     f"{P4D}::test_a_mismatched_stored_intent_is_rejected"),

    ("B51 F-01 DEPLOYED: the repository stops honouring proposal expiry, so a stale pending "
     "operation stays indefinitely authorizable",
     GWREG,
     "        if expires_at is None or datetime.now(timezone.utc) > expires_at:",
     "        if False:  # MUTANT: a proposal never expires",
     f"{P4D}::test_an_expired_proposal_fails_closed"),

    ("B52 F-01 DEPLOYED: the callback falls back to the tap's own channel when the stored receipt "
     "is absent, so a caller-supplied binding wears an authenticated one's clothes",
     ACALL,
     '                receipt_failure = "NO_STORED_CHANNEL_RECEIPT"',
     '                receipt_failure = ""  # MUTANT: accept a tap with no stored channel receipt',
     f"{P4D}::test_a_proposal_with_no_stored_channel_receipt_fails_closed"),
]

# ---------------------------------------------------------------------------------------------
# CREATE case: resurrect a physically-deleted effect path. The clean state is the file ABSENT;
# the mutant is the file PRESENT with an effect-capable import. This proves the deletion is
# GUARDED (the effect-path inventory's on-disk-absence proof fires), not merely performed.
# ---------------------------------------------------------------------------------------------
RESURRECT_PATH = "scripts/run_operate_request.py"
RESURRECT_BODY = (
    '"""MUTANT: a deleted effect path resurrected to prove the deletion is guarded."""\n'
    "from freight_recon import cdp_actuator  # noqa: F401\n"
)
RESURRECT_GUARD = f"{HERM}::test_the_effect_path_inventory_is_exact_and_fully_classified"
RESURRECT_LABEL = "B10 deleted path resurrected: EP-9 comes back and the on-disk-absence proof must fire"


def _run_text_case(case) -> tuple[str, str]:
    _label, rel, old, new, guard = case
    path = ROOT / rel
    original = path.read_bytes()
    text = original.decode("utf-8")

    purge_pycache()
    if not run_guard(guard):
        return "SETUP-FAIL", "guard already RED before mutation"
    n = text.count(old)
    if n == 0:
        return "SETUP-FAIL", f"anchor not found: {old[:50]!r}"
    if n > 1:
        return "SETUP-FAIL", f"anchor is ambiguous ({n} matches): {old[:50]!r}"
    mutated = text.replace(old, new, 1)
    if mutated == text:
        return "SETUP-FAIL", "mutation was a no-op"

    try:
        path.write_text(mutated, encoding="utf-8")
        purge_pycache()
        caught = not run_guard(guard)
    finally:
        path.write_bytes(original)
        purge_pycache()
    if path.read_bytes() != original:
        return "RESTORE-RED", f"byte-for-byte restore FAILED for {rel}"
    if not run_guard(guard):
        return "RESTORE-RED", "guard red after restore - investigate"
    return ("CAUGHT" if caught else "MISS"), ""


def _run_resurrect_case() -> tuple[str, str]:
    path = ROOT / RESURRECT_PATH
    if path.exists():
        return "SETUP-FAIL", f"{RESURRECT_PATH} already exists - the deletion never happened"
    purge_pycache()
    if not run_guard(RESURRECT_GUARD):
        return "SETUP-FAIL", "guard already RED before mutation"
    try:
        path.write_text(RESURRECT_BODY, encoding="utf-8")
        purge_pycache()
        caught = not run_guard(RESURRECT_GUARD)
    finally:
        if path.exists():
            path.unlink()
        purge_pycache()
    if path.exists():
        return "RESTORE-RED", f"{RESURRECT_PATH} was not removed after the mutation"
    if not run_guard(RESURRECT_GUARD):
        return "RESTORE-RED", "guard red after restore - investigate"
    return ("CAUGHT" if caught else "MISS"), ""


def main() -> int:
    results = []
    for case in TEXT_CASES:
        verdict, note = _run_text_case(case)
        results.append((case[0], verdict, note))
    v, n = _run_resurrect_case()
    results.append((RESURRECT_LABEL, v, n))

    print("\n=========== P4 BOUNDARY MUTATION BATTERY ===========")
    for label, verdict, note in sorted(results, key=lambda r: r[0]):
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    print("  NOTE: written by the session that implemented P4 - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
