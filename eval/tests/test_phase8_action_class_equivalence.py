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

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))          # eval/
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))  # src/

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


# --------------------------------------------- the legacy router/graduation carry NO production gate

_SRC = Path(__file__).resolve().parents[2] / "src" / "freight_recon"
_LEGACY_GATE_CARRIERS = ("operation_router.py", "action_class_graduation.py")


def test_legacy_router_and_graduation_register_no_production_gate():
    """### SHIPS DARK, NO SECOND GATE AUTHORITY. After the rename, neither the operation router nor
    the (renamed) action-class graduation store registers a typed gate: no `GateEntry`, no non-empty
    `GateRegistry`. The production GateRegistry stays EMPTY and `checkpoint.py` stays the sole gate
    minter — the rename made the router no more live, not less dark (R-07, §10, U8.1)."""
    from phase0.gate_scan import gate_registration_sites
    for name in _LEGACY_GATE_CARRIERS:
        text = (_SRC / name).read_text(encoding="utf-8")
        sites = gate_registration_sites(text, label=name)
        assert sites == [], f"{name} registers a production gate after the rename: {sites}"


def test_gate_carrier_guard_is_non_vacuous_a_planted_gate_is_caught():
    """Positive control: a gate registration PLANTED into either file's source IS caught by the same
    scanner, so the empty result above is discriminating, not blind."""
    from phase0.gate_scan import gate_registration_sites
    for name in _LEGACY_GATE_CARRIERS:
        text = (_SRC / name).read_text(encoding="utf-8")
        # The scanner recognises a `register_gate(...)` call and a NON-EMPTY `GateRegistry({...})` as
        # real registrations (an empty registry registers nothing — R-07). Plant each and confirm it
        # is caught, so the empty result above is discriminating, not blind.
        planted_call = text + '\n_PLANTED = register_gate("raise_invoice", 1)\n'
        planted_registry = text + '\n_PLANTED = GateRegistry({"raise_invoice": 1}, policy_version="x")\n'
        assert gate_registration_sites(planted_call, label=name), (
            f"a planted register_gate(...) in {name} was NOT caught — the gate-carrier guard is vacuous")
        assert gate_registration_sites(planted_registry, label=name), (
            f"a planted non-empty GateRegistry in {name} was NOT caught — the guard is vacuous")
