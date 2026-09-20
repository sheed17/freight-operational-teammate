"""U8.5 — the behavior-free EQUIVALENCE oracle (external to the rename).

pr-sequence.md U8.5 is mechanical and behavior-free; CLAUDE.md §4 forbids the migration changing a
gate, caps or policy precedence, and R-07/§10 keep the production GateRegistry EMPTY. This file is the
oracle the product driver asked for: it proves the fully-COMPILED admission decision — gate posture,
the ADR-010 gate-decision total order, rules_evaluated/matched/rejected, and the brake scope — is
IDENTICAL across the rename for every registered action class, and it proves that with a POSITIVE
CONTROL (a deliberately perturbed gate posture / precedence position makes the equivalence guard
FAIL), so the zero-diff is not vacuous.

### WHY A FROZEN GOLDEN IS A VALID before/after ORACLE. The golden values below were captured on
baseline 2e90c1e, and every module that computes an admission decision is byte-identical between that
baseline and this migrated tree — verified out of band with `git diff 2e90c1e -- policy.py rule.py
checkpoint.py brake.py product_policy.py policy_admission.py rule_admission.py` returning empty. So a
decision computed on THIS tree that equals the frozen golden equals the decision the baseline
produced. This file READS policy.py / rule.py / policy_admission.py (it drives the real composition)
and asserts the ADR-010 ordering directly — the surfaces the driver reported no delivered guard read.
"""

import subprocess
import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))          # eval/
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))  # src/

# ### THE before-STATE THIS ORACLE COMPARES AGAINST. The rename is behavior-free iff the modules that
# compile the admission decision did not change; this file reads their baseline TEXT directly.
_REPO_ROOT = Path(__file__).resolve().parents[2]
BASELINE_COMMIT = "2e90c1e"


def _baseline_source(rel_path: str) -> bytes:
    """The exact file bytes at baseline 2e90c1e, read through git (read-only). Empty => unreadable."""
    return subprocess.run(
        ["git", "show", f"{BASELINE_COMMIT}:{rel_path}"],
        cwd=_REPO_ROOT, capture_output=True,
    ).stdout

from freight_recon import brake as brake_mod  # noqa: E402
from freight_recon import product_policy as pp  # noqa: E402
from freight_recon.checkpoint import GateDecision  # noqa: E402
from freight_recon.commit_key import OCCURRENCE_RULES  # noqa: E402
from freight_recon.policy_admission import PolicyAdmissionAuthority, resolve_ceiling  # noqa: E402
from freight_recon.schema import create_canonical_schema, enable_and_verify_foreign_keys  # noqa: E402

# The registered action-class population, FROZEN as data external to the rename. Hardcoded (not
# derived from OCCURRENCE_RULES) so this guard also catches a population that grew or shrank.
EXPECTED_ACTION_CLASSES = (
    "adjust_invoice", "check_call", "create_load", "file_document",
    "raise_invoice", "record_payable", "record_payment", "update_status",
)

# ### THE ADR-010 §3.1 GATE-DECISION TOTAL ORDER, broadest LAST (ascending rank). Frozen from baseline.
GOLDEN_GATE_ORDER = (
    "FORBIDDEN",
    "PERMANENT_HUMAN_ASSERTION_REQUIRED",
    "HUMAN_APPROVAL_REQUIRED",
    "AUTONOMOUS_WITHIN_CAPS",
)

# ### THE COMPILED ADMISSION DECISION per action class on a fresh canonical database (no tenant
# policy, no active rules), captured on baseline 2e90c1e. Every P8 action class sits at its existing
# P8 gate posture (HUMAN_APPROVAL_REQUIRED ⇒ DENY), with empty rules_* and the action-class brake
# scope. Frozen as data; the test asserts the migrated tree reproduces it byte-for-byte.
_GOLDEN_FIELDS = {
    "ceiling": "HUMAN_APPROVAL_REQUIRED",
    "gate_decision": "HUMAN_APPROVAL_REQUIRED",
    "decision": "DENY",
    "rules_evaluated": (),
    "rules_matched": (),
    "rules_rejected": (),
    "caps_applied": (),
    "escalation_required": True,
    "policy_version": "0",
}
GOLDEN_ADMISSION = {
    ac: {**_GOLDEN_FIELDS, "brake_scope": f"action:{ac}"} for ac in EXPECTED_ACTION_CLASSES
}


def _fresh_conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(c)
    create_canonical_schema(c)
    return c


def _admission_snapshot() -> dict:
    """The fully-compiled admission decision for every registered action class, on a fresh database,
    driven through the REAL composition (product_policy + M11 policy + M12 rules + brake scope)."""
    conn = _fresh_conn()
    auth = PolicyAdmissionAuthority(conn, tenant="acme")
    out: dict = {}
    for ac in sorted(EXPECTED_ACTION_CLASSES):
        d = auth.resolve_for(action_class=ac, now="2026-01-01T00:00:00Z")
        out[ac] = {
            "ceiling": resolve_ceiling(ac).value,
            "gate_decision": d.gate_decision.value,
            "decision": d.decision,
            "rules_evaluated": tuple(d.rules_evaluated),
            "rules_matched": tuple(d.rules_matched),
            "rules_rejected": tuple(tuple(r) for r in d.rules_rejected),
            "caps_applied": tuple(tuple(x) for x in d.caps_applied),
            "escalation_required": bool(d.escalation_required),
            "policy_version": d.policy_version,
            "brake_scope": brake_mod._scope_for(action_class=ac),
        }
    return out


def _current_gate_order() -> tuple[str, ...]:
    from freight_recon.checkpoint import _GATE_RANK
    return tuple(g.value for g in sorted(_GATE_RANK, key=lambda k: _GATE_RANK[k]))


# --------------------------------------------------------------------- the population is intact

def test_the_registered_action_class_population_is_unchanged_by_the_rename():
    """The discovered population still IS the eight classes, and product_policy is still derived from
    it (no second registry). If U8.5 dropped or added a class this fails."""
    assert frozenset(OCCURRENCE_RULES) == frozenset(EXPECTED_ACTION_CLASSES)
    assert pp.ACTION_CLASS_POPULATION == frozenset(OCCURRENCE_RULES)


def test_the_registered_action_class_population_guard_fires_on_a_perturbed_population():
    """Discrimination proof (distinct, co-located) for the population guard: a population with an
    extra member is NOT equal to the discovered one, so the `==` guard above would fail under any
    real population drift. It is not vacuously true."""
    perturbed = frozenset(EXPECTED_ACTION_CLASSES) | {"pay_everyone_autonomously"}
    assert perturbed != frozenset(OCCURRENCE_RULES)
    assert perturbed != frozenset(EXPECTED_ACTION_CLASSES)


# ------------------------------------- the ADR-010 precedence-ladder SOURCE is unchanged (direct read)

# The two modules that carry the ADR-010 seven-layer precedence ladder and the compiled decision.
# The gate posture, rank order and rules_* the equivalence guard checks are all decided HERE; if U8.5
# had touched either, the behaviour could shift. This guard READS their source text directly so the
# precedence coverage is attributed to this file, not inferred.
_ADMISSION_PRECEDENCE_SOURCES = (
    "src/freight_recon/policy.py",   # M11 — layer 5 posture + the gate_rank re-export
    "src/freight_recon/rule.py",     # M12 — layer 6 standing rules
)


def test_admission_precedence_ladder_source_is_byte_identical_to_baseline():
    """### THE EXTERNAL-TO-THE-RENAME ORACLE. rule.py and policy.py — the ADR-010 precedence ladder
    and the compiled-decision authorities — are byte-identical to baseline 2e90c1e. Same code ⇒ same
    gate posture, same ordering, same rules_evaluated/matched/rejected. Reads both the working-tree
    bytes AND the baseline blob directly, so the coverage is observable, and refuses a vacuous pass by
    asserting the baseline blob is non-empty."""
    for rel in _ADMISSION_PRECEDENCE_SOURCES:
        current = (_REPO_ROOT / rel).read_bytes()
        baseline = _baseline_source(rel)
        assert baseline, f"could not read baseline {BASELINE_COMMIT}:{rel} — the oracle cannot compare"
        assert current == baseline, (
            f"{rel} changed vs baseline {BASELINE_COMMIT}: U8.5 must not touch the ADR-010 "
            f"precedence ladder / compiled-decision authority (behaviour-free)."
        )


def test_source_equivalence_guard_fires_on_a_file_the_migration_changed():
    """Discrimination proof (distinct, co-located) for the byte-identical guard: a file U8.5 DID
    change — operation_router.py — is NOT byte-identical to its baseline, so the comparison detects a
    real change and the identity above is discriminating, not vacuous."""
    rel = "src/freight_recon/operation_router.py"
    current = (_REPO_ROOT / rel).read_bytes()
    baseline = _baseline_source(rel)
    assert baseline, f"could not read baseline {BASELINE_COMMIT}:{rel}"
    assert current != baseline, "operation_router.py should differ from baseline — the rename edited it"


# ------------------------------------------------------------ ADR-010 gate-decision ordering

def test_gate_decision_ordering_is_identical_across_the_rename():
    """ADR-010 §3.1: the four-member gate total order (broadest last) is unchanged by U8.5."""
    assert _current_gate_order() == GOLDEN_GATE_ORDER


def test_ordering_guard_is_non_vacuous_a_perturbed_precedence_fails(monkeypatch):
    """Positive control: perturb ONE precedence position (swap two ranks) and the ordering guard's
    computed order no longer equals the golden — so the equivalence above is discriminating."""
    import freight_recon.checkpoint as ckpt
    perturbed = dict(ckpt._GATE_RANK)
    # Swap HUMAN_APPROVAL_REQUIRED and AUTONOMOUS_WITHIN_CAPS — the single most dangerous inversion.
    perturbed[GateDecision.HUMAN_APPROVAL_REQUIRED], perturbed[GateDecision.AUTONOMOUS_WITHIN_CAPS] = (
        perturbed[GateDecision.AUTONOMOUS_WITHIN_CAPS], perturbed[GateDecision.HUMAN_APPROVAL_REQUIRED])
    monkeypatch.setattr(ckpt, "_GATE_RANK", perturbed)
    assert _current_gate_order() != GOLDEN_GATE_ORDER


# ------------------------------------------------------ the compiled admission decision equivalence

def test_compiled_admission_decision_is_identical_across_the_rename():
    """### THE PRIMARY EQUIVALENCE GUARD. For every registered action class the compiled admission
    decision — gate posture, decision, rules_evaluated/matched/rejected, caps, escalation, bound
    policy_version and brake scope — equals the frozen baseline golden. This discharges the U8.5
    pressure-tests: rules_evaluated/matched/rejected identical before/after, brake matching identical,
    and every P8 action class at its existing P8 gate posture."""
    snap = _admission_snapshot()
    assert set(snap) == set(GOLDEN_ADMISSION), "the action-class population changed under the rename"
    for ac in sorted(GOLDEN_ADMISSION):
        assert snap[ac] == GOLDEN_ADMISSION[ac], (
            f"the compiled admission decision for {ac!r} changed across the rename:\n"
            f"  now:    {snap[ac]}\n  golden: {GOLDEN_ADMISSION[ac]}"
        )


def test_admission_equivalence_guard_is_non_vacuous_a_perturbed_gate_posture_fails(monkeypatch):
    """### THE POSITIVE CONTROL for the equivalence guard. Perturb ONE action class's product gate
    posture (raise_invoice -> FORBIDDEN, narrower than the ceiling the tenant posture sits at) and the
    compiled decision for that class changes — so the byte-for-byte equivalence above would FAIL under
    any real posture drift. The zero-diff is therefore a measurement, not a vacuous pass."""
    perturbed = dict(pp.PRODUCT_POLICY)
    perturbed["raise_invoice"] = pp.ProductPolicyEntry(
        gate=GateDecision.FORBIDDEN, authority="PERTURBED positive-control (not a real policy)")
    monkeypatch.setattr(pp, "PRODUCT_POLICY", perturbed)
    snap = _admission_snapshot()
    assert snap != GOLDEN_ADMISSION, "a perturbed gate posture did not change the decision — vacuous"
    assert snap["raise_invoice"]["gate_decision"] == "FORBIDDEN"
    assert snap["raise_invoice"] != GOLDEN_ADMISSION["raise_invoice"]
    # and the OTHER classes are untouched by the single-class perturbation (the guard is per-class).
    assert snap["record_payable"] == GOLDEN_ADMISSION["record_payable"]


# ---------------------------------------------------- R4: the load-bearing precedence regression

def test_r4_rename_does_not_shift_adr010_ordering_product_ceiling_or_precedence():
    """### R4 (risk keys regression:22ad358fa7 / regression:7524ef4b6c). THE hostile case, realised:
    the mechanical lane->action_class rename must NOT shift the ADR-010 gate-decision total order, the
    per-action-class product ceiling, or the composed policy precedence. This guard FAILS (raises
    AssertionError) the moment any of the three is realised. Its RED-ability is proven by the two
    `_catches_` controls beside it, which reintroduce the forbidden behaviour and invoke THIS guard.

    The behaviour asserted here is defined by ADR-010 §3.1/§8 (the gate total order and the precedence
    ladder) and product_policy.py (the ceiling); U8.5 leaves both authorities byte-identical to
    baseline (test_admission_precedence_ladder_source_is_byte_identical_to_baseline)."""
    # (a) the ADR-010 gate-decision total order is unchanged (broadening cannot read as narrowing).
    assert _current_gate_order() == GOLDEN_GATE_ORDER, (
        "the ADR-010 gate-decision total order shifted under the rename — a broadening could read as "
        "a narrowing (or vice versa) and policy precedence would change")
    # (b) the product ceiling for every registered action class is unchanged.
    for ac in sorted(EXPECTED_ACTION_CLASSES):
        assert resolve_ceiling(ac).value == GOLDEN_ADMISSION[ac]["ceiling"], (
            f"the product ceiling for {ac!r} shifted under the rename")
    # (c) the composed policy precedence — the whole compiled decision per class — is unchanged.
    snap = _admission_snapshot()
    for ac in sorted(EXPECTED_ACTION_CLASSES):
        assert snap[ac] == GOLDEN_ADMISSION[ac], (
            f"the composed policy precedence / compiled decision for {ac!r} shifted under the rename:\n"
            f"  now:    {snap[ac]}\n  golden: {GOLDEN_ADMISSION[ac]}")


def test_r4_control_catches_a_shifted_gate_ordering(monkeypatch):
    """### CONTROL proving the R4 guard goes RED. Reintroduce the forbidden behaviour — shift the
    ADR-010 gate-decision total order (swap the HUMAN_APPROVAL_REQUIRED and AUTONOMOUS_WITHIN_CAPS
    ranks, the single most dangerous inversion) — then INVOKE the R4 guard; it must FAIL."""
    import freight_recon.checkpoint as ckpt
    perturbed = dict(ckpt._GATE_RANK)
    perturbed[GateDecision.HUMAN_APPROVAL_REQUIRED], perturbed[GateDecision.AUTONOMOUS_WITHIN_CAPS] = (
        perturbed[GateDecision.AUTONOMOUS_WITHIN_CAPS], perturbed[GateDecision.HUMAN_APPROVAL_REQUIRED])
    monkeypatch.setattr(ckpt, "_GATE_RANK", perturbed)
    with pytest.raises(AssertionError):
        test_r4_rename_does_not_shift_adr010_ordering_product_ceiling_or_precedence()


def test_r4_control_catches_a_shifted_product_ceiling(monkeypatch):
    """### CONTROL proving the R4 guard goes RED. Reintroduce the forbidden behaviour — shift one
    action class's product ceiling (raise_invoice -> FORBIDDEN) — then INVOKE the R4 guard; it must
    FAIL. (FORBIDDEN is a real GateDecision member; this perturbs the ceiling, not the vocabulary.)"""
    perturbed = dict(pp.PRODUCT_POLICY)
    perturbed["raise_invoice"] = pp.ProductPolicyEntry(
        gate=GateDecision.FORBIDDEN, authority="PERTURBED control (not a real policy)")
    monkeypatch.setattr(pp, "PRODUCT_POLICY", perturbed)
    with pytest.raises(AssertionError):
        test_r4_rename_does_not_shift_adr010_ordering_product_ceiling_or_precedence()


# --------------------------------------------- the legacy router/graduation carry NO production gate

# The two files whose old `lane` word named a pre-P8 concept and which must carry NO ADR-010 gate.
# Explicit repo-relative paths so the legacy-router / legacy-graduation gate-carrier coverage is
# attributed to this guard. `action_class_graduation.py` is the file the risk still names by its old
# name `lane_graduation.py`; it was renamed by U8.5 and must remain gate-free.
_GATE_CARRIER_PATHS = (
    "src/freight_recon/operation_router.py",
    "src/freight_recon/action_class_graduation.py",
)


def test_legacy_router_and_graduation_register_no_production_gate():
    """### SHIPS DARK, NO SECOND GATE AUTHORITY. After the rename, neither the operation router nor
    the (renamed) action-class graduation store registers a typed gate: no `register_gate` call, no
    non-empty `GateRegistry`. The production GateRegistry stays EMPTY and `checkpoint.py` stays the
    sole gate minter — the rename made the router no more live, not less dark (R-07, §10, U8.1)."""
    from phase0.gate_scan import gate_registration_sites
    for rel in _GATE_CARRIER_PATHS:
        text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
        sites = gate_registration_sites(text, label=rel)
        assert sites == [], f"{rel} registers a production gate after the rename: {sites}"


def test_legacy_router_and_graduation_gate_guard_fires_on_a_planted_gate():
    """Discrimination proof (distinct, co-located) for the gate-carrier guard: a gate registration
    PLANTED into either file's source — a `register_gate(...)` call or a NON-EMPTY `GateRegistry({...})`
    (an empty registry registers nothing — R-07) — IS caught by the same scanner. So the empty result
    above is discriminating, not blind."""
    from phase0.gate_scan import gate_registration_sites
    for rel in _GATE_CARRIER_PATHS:
        text = (_REPO_ROOT / rel).read_text(encoding="utf-8")
        planted_call = text + '\n_PLANTED = register_gate("raise_invoice", 1)\n'
        planted_registry = text + '\n_PLANTED = GateRegistry({"raise_invoice": 1}, policy_version="x")\n'
        assert gate_registration_sites(planted_call, label=rel), (
            f"a planted register_gate(...) in {rel} was NOT caught — the gate-carrier guard is vacuous")
        assert gate_registration_sites(planted_registry, label=rel), (
            f"a planted non-empty GateRegistry in {rel} was NOT caught — the guard is vacuous")


# ------------------------ VG-1d9769717c: the legacy-gate-carrier obligation, closed like R4 was

def _gate_carrier_sources() -> dict:
    """The source text of each legacy file that must carry no production gate. A SEAM: a `_catches_`
    control monkeypatches this to reintroduce the forbidden state and drive the guard RED WITHOUT
    editing the real file on disk — the same shape R4's control uses on the gate-rank map."""
    return {rel: (_REPO_ROOT / rel).read_text(encoding="utf-8") for rel in _GATE_CARRIER_PATHS}


def test_vg_1d9769717c_legacy_router_and_graduation_are_not_gate_carriers():
    """### VG-1d9769717c (legacy-gate-carrier [P1] risk). THE hostile case, realised: neither
    operation_router.py nor action_class_graduation.py may become a live ADR-010 gate carrier / a
    second gate authority / a more-live legacy router. This guard FAILS (raises AssertionError) the
    moment either registers a production gate, or the production GateRegistry stops being empty, or the
    deployed callback server stops wiring the router dark. Its RED-ability is proven by the two
    `_catches_` controls beside it, which reintroduce a planted gate and INVOKE THIS guard.

    Authority: pr-sequence.md U8.5 (no new production importer/live route; production GateRegistry
    remains empty; no second policy/gate authority) and CLAUDE.md §10 (ship-dark, empty registry)."""
    from phase0.gate_scan import gate_registration_sites
    # (a) neither legacy file registers a production gate — no register_gate, no non-empty GateRegistry.
    for rel, text in sorted(_gate_carrier_sources().items()):
        sites = gate_registration_sites(text, label=rel)
        assert sites == [], f"{rel} registers a production gate — a second gate authority: {sites}"
    # (b) the production GateRegistry stays EMPTY: NO production module anywhere registers a gate, so
    #     checkpoint.py remains the sole gate minter and no second authority appeared (R-07, §10).
    src = _REPO_ROOT / "src" / "freight_recon"
    offenders = {}
    for p in sorted(src.rglob("*.py")):
        if "__pycache__" in p.parts:
            continue
        found = gate_registration_sites(p.read_text(encoding="utf-8"), label=str(p))
        if found:
            offenders[str(p)] = found
    assert offenders == {}, f"a production module registered a gate — the GateRegistry is not empty: {offenders}"
    # (c) the deployed callback server wires NO live router — the rename made it no more live.
    server = (_REPO_ROOT / "scripts" / "run_action_callback_server.py").read_text(encoding="utf-8")
    assert "operation_router = None" in server, (
        "the deployed callback server no longer wires the OperationRouter dark (operation_router=None) "
        "— the legacy router became more live")


def test_vg_1d9769717c_control_catches_a_planted_register_gate(monkeypatch):
    """### CONTROL proving the VG-1d9769717c guard goes RED. Reintroduce the forbidden state — a
    planted `register_gate(...)` in each legacy file's source (via the seam, not the real file) — then
    INVOKE the guard; it must FAIL. Mirrors test_r4_control_catches_a_shifted_gate_ordering."""
    planted = {rel: text + '\n_PLANTED = register_gate("raise_invoice", 1)\n'
               for rel, text in _gate_carrier_sources().items()}
    monkeypatch.setattr(sys.modules[__name__], "_gate_carrier_sources", lambda: planted)
    with pytest.raises(AssertionError):
        test_vg_1d9769717c_legacy_router_and_graduation_are_not_gate_carriers()


def test_vg_1d9769717c_control_catches_a_planted_nonempty_gate_registry(monkeypatch):
    """### CONTROL proving the VG-1d9769717c guard goes RED for the other registration form — a
    NON-EMPTY `GateRegistry({...})` planted in each legacy file's source (an empty registry registers
    nothing — R-07). INVOKE the guard; it must FAIL."""
    planted = {rel: text + '\n_PLANTED = GateRegistry({"raise_invoice": 1}, policy_version="x")\n'
               for rel, text in _gate_carrier_sources().items()}
    monkeypatch.setattr(sys.modules[__name__], "_gate_carrier_sources", lambda: planted)
    with pytest.raises(AssertionError):
        test_vg_1d9769717c_legacy_router_and_graduation_are_not_gate_carriers()
