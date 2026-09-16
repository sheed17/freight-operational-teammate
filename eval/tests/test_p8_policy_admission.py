"""U8.1 — the P8 policy admission kernel: the acceptance battery for the FIRST coherent P8 slice.

Every test here could have failed before this slice existed, and the load-bearing ones are the RED
half of a mutant in `scripts/mutate_p8_policy_admission.py`. The battery measures the DATABASE (a
fresh canonical schema, written against), the AST (the brake never depends on the policy engine;
the kernel stays the sole gate minter; no model reaches the decision path) and the CLAIM LEDGER
(the CAS really does match zero rows) — not narration.

### WHAT THIS BATTERY IS ABOUT. Before U8.1, `GateRegistry._DEFAULT` answered
`HUMAN_APPROVAL_REQUIRED` for any action class nobody had classified. The VALUE was safe; the
MECHANISM was F-20 — forgetting was survivable, and a class nobody had thought about was
indistinguishable from one somebody had decided needed a human. So the tests that matter here are
about the FAILURE MODE, and several of them assert that something REFUSES where it previously
answered. `test_f20_...` names each.
"""

from __future__ import annotations

import ast
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval"), str(ROOT / "eval" / "tests")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from freight_recon import product_policy  # noqa: E402
from freight_recon.checkpoint import (  # noqa: E402
    GateDecision,
    GateEntry,
    GateRegistry,
    UnclassifiedActionClass as KernelUnclassified,
)
from freight_recon.commit_key import OCCURRENCE_RULES  # noqa: E402
from freight_recon.policy import (  # noqa: E402
    M11Machine,
    PolicyDecision,
    PolicyEvaluationInputs,
    gate_rank,
    narrows_or_holds,
)
from freight_recon.policy_admission import (  # noqa: E402
    SIGNAL_PERMANENT_TRUTH_APPLIED,
    SIGNAL_TENANT_BROADENING_REFUSED,
    PolicyAdmissionAuthority,
    resolve_ceiling,
)
from freight_recon.product_policy import (  # noqa: E402
    ACTION_CLASS_POPULATION,
    PRODUCT_POLICY,
    REGISTERED_ACTION_CLASS_COUNT,
    IncompleteProductPolicy,
    ProductPolicyEntry,
    product_gate_for,
    verify_registration_complete,
)
from freight_recon.schema import (  # noqa: E402
    create_canonical_schema,
    enable_and_verify_foreign_keys,
)

TENANT = "acme-brokerage"
CLOCK = lambda: datetime(2026, 9, 3, 12, 0, 0, tzinfo=timezone.utc)  # noqa: E731
NOW = "2026-09-03T12:00:00Z"
ADMISSION_SRC = (ROOT / "src" / "freight_recon" / "policy_admission.py").read_text(encoding="utf-8")
PRODUCT_SRC = (ROOT / "src" / "freight_recon" / "product_policy.py").read_text(encoding="utf-8")
BRAKE_SRC = (ROOT / "src" / "freight_recon" / "brake.py").read_text(encoding="utf-8")


# ------------------------------------------------------------------ helpers

def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    return conn


def _human(conn, hid="po", *, role="POLICY_OWNER", tenant=TENANT):
    conn.execute(
        "INSERT INTO tenant_humans (tenant, human_id, display_name, authority_role, state, "
        "recorded_at, recorded_by, recorded_by_kind) VALUES (?,?,?,?,'ACTIVE',?,?, 'human')",
        (tenant, hid, hid, role, "2026-01-01T00:00:00Z", "founder"))
    conn.commit()
    return hid


def _approval_row(conn, aid, *, mfp, tenant=TENANT):
    cols = dict(
        tenant=tenant, approval_id=aid, commit_key=f"ck-{aid}", action_class="change_policy",
        state="GRANTED", version=1, material_facts_fingerprint=mfp, canonical_payload=b"{}",
        fingerprint_version="fp_v1", entity_versions_json='{"policy:%s": 1}' % aid,
        policy_version="1", brake_version="bv1", gate_decision="HUMAN_APPROVAL_REQUIRED",
        required_signatures=1, rendered_facts="{}", requested_at="2026-01-01T00:00:00Z",
        expires_at="2027-01-01T00:00:00Z", frozen=0, granted_by="po",
        created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
    conn.execute(f"INSERT INTO approvals ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                 tuple(cols.values()))
    conn.commit()
    return aid


def _activate(conn, *, scope, gate, policy_id, owner="po", tenant=TENANT,
              ceiling=GateDecision.HUMAN_APPROVAL_REQUIRED):
    """Activate a tenant policy through M11's real seven-transition path (no shortcut)."""
    m = M11Machine(conn, tenant=tenant, clock=CLOCK, product_ceiling=ceiling)
    aid, diff = f"appr-{policy_id}", f"DIFF-{policy_id}"
    _approval_row(conn, aid, mfp=diff, tenant=tenant)
    m.propose_draft(scope=scope, scope_kind="action_class", gate_decision=gate, caps={},
                    predicate={"clauses": []}, authored_by=owner, policy_id=policy_id)
    m.submit(policy_id, actor_id=owner)
    m.approve(policy_id, approval_id=aid, diff_fingerprint=diff, approved_by=owner)
    m.activate(policy_id, activated_by=owner)
    return policy_id


def _inputs(action_class="raise_invoice", *, tenant=TENANT, **kw) -> PolicyEvaluationInputs:
    return PolicyEvaluationInputs(tenant=tenant, action_class=action_class, now=NOW, **kw)


def _authority(conn, *, tenant=TENANT) -> PolicyAdmissionAuthority:
    return PolicyAdmissionAuthority(conn, tenant=tenant, clock=CLOCK)


# ==================================================================================================
# REQUIREMENT 1 — EXPLICIT GATE DECISIONS. NO ACCIDENTAL DEFAULT. (F-20, U8.1, AC-CKPT-6-missing)
# ==================================================================================================

def test_u81_the_action_class_population_is_DISCOVERED_from_repository_authority():
    """### THE POPULATION IS NOT A HAND-WRITTEN PARALLEL LIST.

    `ACTION_CLASS_POPULATION` is derived from `commit_key.OCCURRENCE_RULES` — the repository's
    existing per-action-class registration (K-5's `occurrence_key_rule`). A second list maintained
    by hand would drift, and the drift would be invisible, which is F-20 wearing different clothes.
    """
    assert ACTION_CLASS_POPULATION == frozenset(OCCURRENCE_RULES), (
        "the classified population and the occurrence-rule population have diverged: "
        f"policy-only={sorted(ACTION_CLASS_POPULATION - set(OCCURRENCE_RULES))}, "
        f"rules-only={sorted(set(OCCURRENCE_RULES) - ACTION_CLASS_POPULATION)}"
    )
    # ### PROVE THE POPULATION BEFORE ASSERTING ANYTHING OVER IT (CLAUDE.md §6): a total
    # classification over an empty set is vacuously total.
    assert len(ACTION_CLASS_POPULATION) >= 8, (
        f"the discovered population collapsed to {len(ACTION_CLASS_POPULATION)} — every "
        "completeness assertion below would pass over almost nothing"
    )


def test_u81_every_registered_action_class_carries_exactly_ONE_explicit_gate():
    """U8.1's registration obligation, with its DENOMINATOR printed.

    `pr-sequence.md` U8.1: enumerate every registered Action Class · require exactly ONE positive
    gate decision each · prove a NON-ZERO evaluated registration count.
    """
    verified = verify_registration_complete()
    assert verified == REGISTERED_ACTION_CLASS_COUNT == len(ACTION_CLASS_POPULATION)
    assert verified > 0, "a registration check that verified ZERO classes is the M-9 false green"
    for action_class in sorted(ACTION_CLASS_POPULATION):
        entry = PRODUCT_POLICY[action_class]
        assert isinstance(entry.gate, GateDecision), f"{action_class}: gate is not a canonical member"
        assert str(entry.authority).strip(), f"{action_class}: classified without citing an authority"
    print(f"U8.1 registered action classes verified: {verified} / "
          f"{len(ACTION_CLASS_POPULATION)} discovered")


def test_u81_autonomy_is_granted_to_NO_action_class_at_this_slice():
    """PHASE-OUTPUTS.md P8 records autonomy as prohibited until P14, and ADR-010 §15 Q1 says
    nothing graduates until the thresholds are validated. So this is a POSITIVE assertion that the
    autonomous set is empty — not an accident of the table above."""
    autonomous = sorted(a for a, e in PRODUCT_POLICY.items()
                        if e.gate is GateDecision.AUTONOMOUS_WITHIN_CAPS)
    assert autonomous == [], (
        f"action class(es) {autonomous} were granted AUTONOMOUS_WITHIN_CAPS at U8.1. Autonomy is "
        "prohibited until P14 and requires a graduation dossier no class has."
    )
    assert all(e.caps is None for e in PRODUCT_POLICY.values()), (
        "a cap was invented for a class that cannot act alone — a freight business rule nobody chose"
    )


def test_u81_an_unclassified_action_class_FAILS_CLOSED_at_configuration_time():
    """### THE STARTUP FAILURE. Not a warning. Not a default. (ADR-010 §3.1/§10, F-20.)

    Every member of the discovered population is dropped in turn, so this is not a claim about one
    convenient class — it is the property, over the whole population, with its denominator.
    """
    checked = 0
    for victim in sorted(ACTION_CLASS_POPULATION):
        partial = {k: v for k, v in PRODUCT_POLICY.items() if k != victim}
        with pytest.raises(IncompleteProductPolicy) as exc:
            verify_registration_complete(policy=partial)
        assert victim in str(exc.value), (
            f"the refusal does not NAME the unclassified class {victim!r}; an operator cannot act "
            "on 'registration incomplete'"
        )
        checked += 1
    assert checked == len(ACTION_CLASS_POPULATION) >= 8, f"only {checked} classes were exercised"


def test_u81_a_gate_declared_for_an_UNREGISTERED_class_is_also_refused():
    """Drift in the other direction. Tolerated one way, it becomes invisible both ways."""
    bogus = dict(PRODUCT_POLICY)
    bogus["wire_out"] = ProductPolicyEntry(
        gate=GateDecision.HUMAN_APPROVAL_REQUIRED, authority="a class that does not exist")
    with pytest.raises(IncompleteProductPolicy) as exc:
        verify_registration_complete(policy=bogus)
    assert "wire_out" in str(exc.value)


def test_u81_an_EMPTY_population_is_refused_rather_than_passing_vacuously():
    """M-9: a check that parsed nothing is worse than no check. If the population authority is
    emptied or renamed, the completeness check must FAIL, not report a complete classification."""
    with pytest.raises(IncompleteProductPolicy) as exc:
        verify_registration_complete(population=frozenset(), policy={})
    assert "EMPTY" in str(exc.value)


def test_u81_a_null_gate_and_a_prompt_string_are_both_refused_as_policy():
    """The registry's two named hostile cases: 'a null gate decision' and 'a prompt string admitted
    as policy' (IMPLEMENTATION-REGISTRY P8 `rebaseline_contract.hostile_cases`)."""
    with pytest.raises(product_policy.ProductPolicyError):
        ProductPolicyEntry(gate=None, authority="x")  # type: ignore[arg-type]
    with pytest.raises(product_policy.ProductPolicyError):
        ProductPolicyEntry(gate="HUMAN_APPROVAL_REQUIRED", authority="x")  # type: ignore[arg-type]
    with pytest.raises(product_policy.ProductPolicyError):
        ProductPolicyEntry(gate="never bill without a POD", authority="x")  # type: ignore[arg-type]
    # ...and an uncited classification is refused too: a preference is not a policy.
    with pytest.raises(product_policy.ProductPolicyError):
        ProductPolicyEntry(gate=GateDecision.HUMAN_APPROVAL_REQUIRED, authority="  ")


def test_f20_the_gate_registry_NO_LONGER_resolves_an_unregistered_class_to_a_default():
    """### THE P3 SCAFFOLDING THAT DID NOT SURVIVE P8, asserted as the behaviour CHANGE it is.

    Until U8.1 this returned `GateEntry(HUMAN_APPROVAL_REQUIRED)`. The value was safe. The
    mechanism was F-20: a gate expressible as an absence is not a gate, and an action class nobody
    classified looked exactly like one somebody had decided needed a human.
    """
    empty = GateRegistry({}, policy_version="pv1")
    with pytest.raises(KernelUnclassified) as exc:
        empty.gate_for("adjust_invoice")
    message = str(exc.value)
    assert "adjust_invoice" in message
    # The refusal must not merely *mention* the old answer as the thing it is refusing to give.
    assert "not equivalent" in message.lower() or "refus" in message.lower()

    # And the kernel no longer carries a default at all — a reachable `_DEFAULT` would be the
    # fallback re-entering by the back door.
    assert not hasattr(GateRegistry, "_DEFAULT"), (
        "GateRegistry._DEFAULT is back. An unclassified action class must REFUSE, not resolve."
    )


def test_f20_a_registered_class_still_resolves_and_the_refusal_is_not_blanket():
    """The positive control for the test above: the refusal is about ABSENCE, not about everything.
    A guard that refuses every lookup would also pass the test above and would be useless."""
    reg = GateRegistry({"raise_invoice": GateEntry(gate=GateDecision.HUMAN_APPROVAL_REQUIRED)},
                       policy_version="pv1")
    assert reg.gate_for("raise_invoice").gate is GateDecision.HUMAN_APPROVAL_REQUIRED
    assert reg.gate_for("RAISE_INVOICE  ").gate is GateDecision.HUMAN_APPROVAL_REQUIRED


# ==================================================================================================
# REQUIREMENT 2 — THE FOUR GATES STAY SEMANTICALLY DISTINCT. THE DISTINCTION IS CONSTITUTIONAL.
# ==================================================================================================

def test_the_four_gates_have_four_distinct_ranks_and_the_order_is_not_a_string_compare():
    ranks = {g: gate_rank(g) for g in GateDecision}
    assert len(set(ranks.values())) == 4, f"two gates collapsed to one rank: {ranks}"
    assert (ranks[GateDecision.AUTONOMOUS_WITHIN_CAPS]
            > ranks[GateDecision.HUMAN_APPROVAL_REQUIRED]
            > ranks[GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED]
            > ranks[GateDecision.FORBIDDEN])
    # ### THE STRING COMPARE WOULD INVERT THE MOST DANGEROUS PAIR IN THE SYSTEM.
    assert "AUTONOMOUS_WITHIN_CAPS" < "HUMAN_APPROVAL_REQUIRED", (
        "the premise of this guard changed: alphabetically AUTONOMOUS used to sort first, which is "
        "why the rank must be explicit"
    )


def test_permanent_human_assertion_required_is_NOT_collapsed_into_human_approval_required():
    """### THE DISTINCTION *IS* THE DISTINCTION BETWEEN A PERMANENT TRUTH AND A POLICY (ADR-010 §3.1).

    Collapsing them would either freeze money-out forever (wrong — it is policy) or make the
    Authorization Assertion graduatable (catastrophic — it is permanent, ADR-003).
    """
    perm, human = (GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED,
                   GateDecision.HUMAN_APPROVAL_REQUIRED)
    assert perm is not human and gate_rank(perm) < gate_rank(human)
    # A tenant sitting at the permanent gate may NOT be relaxed to the merely-human gate: that is
    # a BROADENING, and the ratchet only turns the safe way.
    assert not narrows_or_holds(human, perm)
    assert narrows_or_holds(perm, human)


def test_permanent_human_assertion_required_can_NEVER_graduate_to_autonomy():
    """ADR-010 §3.1: 'NEVER. Cannot graduate. Ever.'"""
    assert not narrows_or_holds(GateDecision.AUTONOMOUS_WITHIN_CAPS,
                               GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED)


def test_human_approval_required_MAY_graduate_because_it_is_policy_not_permanent_truth():
    """The other half of the same distinction: HUMAN_APPROVAL_REQUIRED is CURRENT POLICY and the
    architecture must not quietly forbid it forever (ADR-010 §3, operating-model §7.6). The ladder
    admits the move; nothing in this slice performs one."""
    assert narrows_or_holds(GateDecision.HUMAN_APPROVAL_REQUIRED,
                           GateDecision.AUTONOMOUS_WITHIN_CAPS)


def test_forbidden_is_NOT_collapsed_into_permanent_human_assertion_required():
    """### 'ONLY A HUMAN MAY EVER DO THIS' AND 'NOBODY MAY EVER DO THIS' ARE DIFFERENT SENTENCES.

    ADR-010's own Amendment Record A4 calls the collapse a LATENT DEFECT: it routed the
    permanent-truth gate straight to REJECTED, so an accessorial a human COULD have authorized
    would have been rejected outright instead of asked about.
    """
    forbidden, perm = GateDecision.FORBIDDEN, GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED
    assert forbidden is not perm and gate_rank(forbidden) < gate_rank(perm)
    assert not narrows_or_holds(perm, forbidden), (
        "PERMANENT_HUMAN_ASSERTION_REQUIRED is being treated as no broader than FORBIDDEN — the "
        "two have been collapsed, and a human-authorizable action would be refused outright"
    )


def test_no_human_approval_unlocks_forbidden_but_one_can_satisfy_the_permanent_gate():
    """The behavioural half of the two assertions above, at the admission layer."""
    conn = _conn()
    _human(conn)
    # A tenant narrowing to FORBIDDEN: nothing below may unlock it.
    _activate(conn, scope="raise_invoice", gate=GateDecision.FORBIDDEN, policy_id="p-forbid")
    d = _authority(conn).resolve(_inputs("raise_invoice"))
    assert d.gate_decision is GateDecision.FORBIDDEN

    # A tenant narrowing to the permanent-assertion gate: still a HUMAN gate, not a prohibition.
    _activate(conn, scope="file_document",
              gate=GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED, policy_id="p-perm")
    d2 = _authority(conn).resolve(_inputs("file_document"))
    assert d2.gate_decision is GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED
    assert d2.gate_decision is not GateDecision.FORBIDDEN


# ==================================================================================================
# REQUIREMENT 3 — PRODUCT POLICY + TENANT POLICY LAYERING
# ==================================================================================================

def test_the_ceiling_for_every_class_is_the_product_policy_when_no_permanent_truth_applies():
    for action_class in sorted(ACTION_CLASS_POPULATION):
        assert resolve_ceiling(action_class) is product_gate_for(action_class)


def test_a_tenant_policy_MAY_narrow_the_product_ceiling():
    conn = _conn()
    _human(conn)
    assert product_gate_for("record_payable") is GateDecision.HUMAN_APPROVAL_REQUIRED
    _activate(conn, scope="record_payable", gate=GateDecision.FORBIDDEN, policy_id="p-narrow")
    d = _authority(conn).resolve(_inputs("record_payable"))
    assert d.gate_decision is GateDecision.FORBIDDEN, "a tenant narrowing was not honoured"
    assert d.security_signals == ()
    assert d.rules_rejected == ()


def test_a_tenant_policy_may_NEVER_broaden_the_product_ceiling_and_the_refusal_is_ATTRIBUTABLE():
    """### THE HOSTILE CASE, AT THE MOMENT OF DECISION AND NOT ONLY AT ACTIVATION.

    M11's PO-3 guard already refuses to ACTIVATE a policy broader than the ceiling. This asserts
    the second line of defence: an ACTIVE row that sits above the ceiling — activated when the
    ceiling was broader, or written by a path that bypassed the guard — must still be REFUSED at
    the moment it would decide something, and the refusal must NAME the policy responsible.
    """
    conn = _conn()
    _human(conn)
    # Activate legitimately under a deliberately broader machine ceiling, so the row is real,
    # ACTIVE, human-activated and fully event-sourced — then evaluate it against the REAL product
    # ceiling, which is narrower. This is the "activated when the ceiling was broader" case.
    _activate(conn, scope="raise_invoice", gate=GateDecision.AUTONOMOUS_WITHIN_CAPS,
              policy_id="p-broad", ceiling=GateDecision.AUTONOMOUS_WITHIN_CAPS)
    assert product_gate_for("raise_invoice") is GateDecision.HUMAN_APPROVAL_REQUIRED

    d = _authority(conn).resolve(_inputs("raise_invoice"))
    assert d.decision == "DENY", "a broadening tenant policy was not refused"
    assert d.gate_decision is GateDecision.HUMAN_APPROVAL_REQUIRED, (
        "the refusal did not fall back to the CEILING — it must not adopt the broader gate"
    )
    assert d.escalation_required is True
    assert SIGNAL_TENANT_BROADENING_REFUSED in d.security_signals
    assert d.rules_matched == ()
    assert any(rule == "p-broad" for rule, _why in d.rules_rejected), (
        f"the refusal is not attributable to the offending policy: {d.rules_rejected}"
    )
    assert "BROADER" in d.reason or "broader" in d.reason
    assert d.reason.strip(), "a refusal must always carry a human-readable reason"


def test_a_permanent_product_truth_CANNOT_be_overridden_from_below(monkeypatch):
    """### LAYER 2 IS ABOVE PRODUCT POLICY AND TENANT POLICY BOTH (ADR-010 §8).

    The production permanent set is EMPTY by decision, so the LAYER is exercised against a fixture
    member. A layer whose override-refusal has never been seen to fire is a decoration
    (CLAUDE.md §6) — so it is made to fire.
    """
    monkeypatch.setitem(product_policy.PERMANENT_PRODUCT_TRUTHS, "raise_invoice",
                        GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED)
    # Product policy nominally says the merely-human gate; the permanent truth is narrower and wins.
    assert product_gate_for("raise_invoice") is GateDecision.HUMAN_APPROVAL_REQUIRED
    assert resolve_ceiling("raise_invoice") is GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED

    conn = _conn()
    _human(conn)
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED,
              policy_id="p-tenant")
    d = _authority(conn).resolve(_inputs("raise_invoice"))
    assert d.decision == "DENY", "a tenant policy overrode a Permanent Product Truth"
    assert d.gate_decision is GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED
    assert SIGNAL_PERMANENT_TRUTH_APPLIED in d.security_signals
    assert SIGNAL_TENANT_BROADENING_REFUSED in d.security_signals


def test_the_permanent_product_truth_set_is_EMPTY_BY_DECISION_and_the_forbidden_set_too():
    """ADR-010 §3.1 and §15 Q3: an empty set is a POSITIVE ASSERTION, not an oversight. Inventing a
    member to make the enum feel used would be design by symmetry."""
    assert product_policy.PERMANENT_PRODUCT_TRUTHS == {}
    forbidden = sorted(a for a, e in PRODUCT_POLICY.items() if e.gate is GateDecision.FORBIDDEN)
    assert forbidden == [], f"a FORBIDDEN member was invented at v1: {forbidden}"


def test_the_authority_is_bound_to_one_tenant_and_refuses_inputs_naming_another():
    conn = _conn()
    _human(conn)
    with pytest.raises(Exception):
        _authority(conn).resolve(_inputs("raise_invoice", tenant="other-brokerage"))


# ==================================================================================================
# REQUIREMENT 4 — POLICY VERSION IS MATERIAL
# ==================================================================================================

def test_the_bound_version_is_the_TENANT_MONOTONIC_MAX_not_the_governing_rows_own_version():
    """### THE UNDER-VOIDING DEFECT THIS SLICE CLOSES.

    `policies` carries `UNIQUE (tenant, policy_version)`, so activating a policy in scope B raises
    the tenant's MAX while the ACTIVE row in scope A keeps the number it was born with. M11's own
    docstring fixes the namespace as the TENANT: 'a change in ANY scope advances the tenant's
    policy_version, so the void reaches in-flight authority in EVERY scope — over-voiding is the
    fail-closed direction and UNDER-VOIDING IS NOT AVAILABLE.'

    Binding the row's own number would mean a policy change in another scope did NOT move the value
    the claim CAS revalidates. This asserts the bound value moves.
    """
    conn = _conn()
    _human(conn)
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pA")
    first = _authority(conn).resolve(_inputs("raise_invoice")).policy_version

    row_version = conn.execute(
        "SELECT policy_version FROM policies WHERE tenant=? AND policy_id='pA'", (TENANT,)
    ).fetchone()[0]

    # A change in a DIFFERENT scope. Scope A's own ACTIVE row is untouched.
    _activate(conn, scope="record_payable", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pB")
    second = _authority(conn).resolve(_inputs("raise_invoice")).policy_version

    still = conn.execute(
        "SELECT policy_version FROM policies WHERE tenant=? AND policy_id='pA'", (TENANT,)
    ).fetchone()[0]
    assert still == row_version, "the fixture is wrong: scope A's row moved, so this proves nothing"

    assert second != first, (
        "a policy activation in ANOTHER scope did NOT move the bound policy_version. That is "
        "UNDER-VOIDING: in-flight authority for this scope would survive a policy change, and "
        f"the claim CAS would still match. bound={first!r} then {second!r}, row={row_version!r}"
    )
    assert int(second) > int(first), "the tenant policy_version must be MONOTONIC"
    assert second == str(_authority(conn).current_policy_version())


def test_the_version_is_durable_and_monotonic_per_tenant_and_tenants_do_not_share_it():
    conn = _conn()
    _human(conn)
    _human(conn, "po2", tenant="other-brokerage")
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pA")
    mine = _authority(conn).current_policy_version()
    theirs = PolicyAdmissionAuthority(conn, tenant="other-brokerage", clock=CLOCK) \
        .current_policy_version()
    assert theirs == "0", f"another tenant's version leaked: {theirs!r}"
    assert int(mine) >= 1

    seen = [int(mine)]
    for i, scope in enumerate(("record_payable", "file_document", "update_status")):
        _activate(conn, scope=scope, gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id=f"p{i}")
        seen.append(int(_authority(conn).current_policy_version()))
    assert seen == sorted(set(seen)), f"the version is not strictly monotonic: {seen}"


def test_there_is_exactly_ONE_version_authority_and_the_admission_layer_DELEGATES():
    """Rule 17 / ADR-010: no second version authority. The admission layer must not compute,
    cache or store a version of its own."""
    tree = ast.parse(ADMISSION_SRC)
    assigned = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign)
                for t in n.targets if isinstance(t, ast.Name)}
    assert not {"policy_version", "POLICY_VERSION", "_policy_version"} & assigned, (
        "the admission layer assigns its own policy_version — that is a second version authority"
    )
    assert "current_policy_version" in ADMISSION_SRC
    for forbidden in ("CREATE TABLE", "INSERT INTO", "UPDATE "):
        assert forbidden not in ADMISSION_SRC, (
            f"the admission layer contains {forbidden!r}: it is a READER that composes existing "
            "authorities, and a writer here would be a second policy store"
        )


# ==================================================================================================
# REQUIREMENT 5 — A DETERMINISTIC PolicyDecision, AND NO MODEL ANYWHERE NEAR IT
# ==================================================================================================

def test_the_policy_decision_carries_every_field_adr_010_5_3_requires():
    fields = set(PolicyDecision.__dataclass_fields__)
    required = {
        "gate_decision", "decision", "policy_version", "rules_evaluated", "rules_matched",
        "rules_rejected", "caps_applied", "reason", "security_signals", "escalation_required",
    }
    missing = sorted(required - fields)
    assert not missing, f"PolicyDecision is missing ADR-010 §5.3 field(s): {missing}"


def test_identical_inputs_and_version_produce_a_BYTE_IDENTICAL_decision():
    """ADR-010 §5.3 / M-50, and the registry's determinism requirement."""
    conn = _conn()
    _human(conn)
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pA")
    inputs = _inputs("raise_invoice")
    first = _authority(conn).resolve(inputs).to_bytes()
    for _ in range(50):
        assert _authority(conn).resolve(inputs).to_bytes() == first
    # ...and a fresh authority object over the same durable state agrees.
    assert PolicyAdmissionAuthority(conn, tenant=TENANT, clock=CLOCK).resolve(inputs).to_bytes() == first


def test_a_decision_always_carries_a_reason_including_on_permit():
    conn = _conn()
    _human(conn)
    _activate(conn, scope="raise_invoice", gate=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id="pA")
    d = _authority(conn).resolve(_inputs("raise_invoice"))
    assert d.decision in ("PERMIT", "DENY")
    assert d.reason.strip(), "a system that can block but not explain has relocated the problem"


def test_the_decision_path_has_NO_model_call_and_NO_readable_confidence():
    """ADR-010 §5.1/§5.4: the model has NO role, and `confidence` is structurally absent — a guard
    cannot read it even by trying."""
    assert "confidence" not in PolicyEvaluationInputs.__dataclass_fields__
    banned = ("anthropic", "openai", "llm", "completion", "brain_runtime", "operator_brain",
              "extraction", "agent_memory", "knowledge")
    for module_src, label in ((ADMISSION_SRC, "policy_admission"), (PRODUCT_SRC, "product_policy")):
        tree = ast.parse(module_src)
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.rsplit(".", 1)[-1].lower())
            elif isinstance(node, ast.Import):
                imported |= {a.name.rsplit(".", 1)[-1].lower() for a in node.names}
        offenders = sorted(imported & set(banned))
        assert not offenders, f"{label} imports {offenders}: the model has NO role in evaluation"


def test_a_model_inferred_fact_cannot_be_branched_on_at_any_confidence():
    """AC-SAFE-015 at the policy layer: the gating accessor raises on read, so a guess cannot
    become a gate by being passed through the admission layer either."""
    from freight_recon.checkpoint import (
        EvidenceCondition,
        GateReadOfInferredFact,
        ProvenanceClass,
        ProvenancedFact,
    )
    guess = ProvenancedFact(
        field="amount", provenance=ProvenanceClass.MODEL_INFERRED,
        evidence_condition=EvidenceCondition.CONSISTENT, _value=1)
    with pytest.raises(GateReadOfInferredFact):
        _ = guess.value
    # ...and there is no confidence to raise it above: the field does not exist on the type.
    assert "confidence" not in ProvenancedFact.__dataclass_fields__


# ==================================================================================================
# THE BRAKE MUST NOT DEPEND ON THE POLICY ENGINE (ADR-011 §0 — the registry's hostile case)
# ==================================================================================================

def test_the_brake_does_NOT_depend_on_the_policy_engine():
    """### 'ONE OF THE REASONS YOU PULL THE BRAKE IS THAT THE POLICY ENGINE IS WRONG.'

    A brake implemented on top of policy depends on the very subsystem it exists to overrule. This
    is asserted by AST over the brake's real imports, in both directions.
    """
    POLICY_MODULES = {"policy", "product_policy", "policy_admission"}
    tree = ast.parse(BRAKE_SRC)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.rsplit(".", 1)[-1])
        elif isinstance(node, ast.ImportFrom) and node.module is None:
            imported |= {a.name for a in node.names}
        elif isinstance(node, ast.Import):
            imported |= {a.name.rsplit(".", 1)[-1] for a in node.names}
    leaked = sorted(imported & POLICY_MODULES)
    assert not leaked, (
        f"brake.py imports the policy engine ({leaked}). The brake must be engageable when the "
        "policy engine is exactly what is broken (ADR-011 §0); a safety control that requires the "
        "system to be healthy is not a safety control."
    )
    # ...and the composition does not reach back the other way either: step 7 is not step 6.
    admission_tree = ast.parse(ADMISSION_SRC)
    admission_imports: set[str] = set()
    for node in ast.walk(admission_tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            admission_imports.add(node.module.rsplit(".", 1)[-1])
        elif isinstance(node, ast.Import):
            admission_imports |= {a.name.rsplit(".", 1)[-1] for a in node.names}
    assert "brake" not in admission_imports, (
        "the policy admission layer imports the brake: steps 6 and 7 are two checks, not one"
    )


# ==================================================================================================
# END TO END — DURABLE AUTHORITY → DETERMINISTIC DECISION → CHECKPOINT PERMIT/REFUSE → EXACT VERSION
# ==================================================================================================
#
# These are the cases that make the slice COHERENT rather than four parts that each work alone. They
# drive the real kernel (`run_checkpoint` / `claim_grant_cas`), the real ledger and the real M11
# rows, and they assert the universal oracle of `platform-safety-acceptance.md` PART B: the outcome
# is ALWAYS EXACTLY ONE of (a) one witness AND one claimed grant, or (b) NO authorization capability
# whatsoever. Nothing in between is allowed to exist.

from freight_recon.checkpoint import (  # noqa: E402
    CheckpointInputs,
    CheckpointKernel,
    CheckpointRequest,
    claim_grant_cas,
    run_checkpoint,
)
from phase3_kit import (  # noqa: E402
    Clock,
    live_reader,
    make_approval,
    make_effect,
    make_facts,
    make_store,
    params_for,
)


def _wired(tmp_path, *, action_class="raise_invoice", tenant=TENANT, scope_gate=None,
           policy_id="pA", name="p8.db", machine_ceiling=None):
    """A kernel with a REAL P8 policy authority bound, over a real canonical schema.

    The store's own connection carries the M11 tables, so the policy read at step 6 and the policy
    re-read at claim happen on the SAME connection as the seven steps — which is what makes the
    version comparison meaningful rather than a read of some other database.
    """
    store = make_store(tmp_path, tenant, name=name)
    create_canonical_schema(store.conn)
    enable_and_verify_foreign_keys(store.conn)
    store.conn.row_factory = sqlite3.Row
    _human(store.conn, tenant=tenant)
    # `machine_ceiling` exists ONLY to build the "activated when the ceiling was broader" row
    # that the broadening case needs. M11's PO-3 guard refuses a broadening at ACTIVATION, which
    # is its job and is asserted by its own battery; this fixture reaches PAST that guard so the
    # ADMISSION layer's second line of defence has something real to refuse.
    _activate(store.conn, scope=action_class,
              gate=scope_gate or GateDecision.HUMAN_APPROVAL_REQUIRED, policy_id=policy_id,
              tenant=tenant,
              ceiling=machine_ceiling or scope_gate or GateDecision.HUMAN_APPROVAL_REQUIRED)
    authority = PolicyAdmissionAuthority(store.conn, tenant=tenant, clock=CLOCK)
    clock = Clock()
    kernel = CheckpointKernel(
        store,
        GateRegistry({}, policy_version="pv1"),   # ### the production registry stays EMPTY
        clock=clock,
        policy_authority=authority,
    )
    return store, kernel, clock, authority


def _scenario(kernel, clock, authority, *, action_class="raise_invoice", tenant=TENANT,
              resource="load:4471"):
    """The green scenario, with the approval bound to the DURABLE policy version."""
    effect = make_effect(tenant=tenant, action_class=action_class, resource=resource)
    facts = make_facts(entity_ref=resource)
    versions = {resource: 17}
    approval = make_approval(effect, facts, versions, clock,
                             policy_version=authority.current_policy_version())
    world = {"facts": dict(facts), "projection": {"status": "DELIVERED"}, "versions": dict(versions)}
    inputs = CheckpointInputs(
        material_facts_reader=live_reader(lambda: dict(world["facts"])),
        projection_assertion={"status": "DELIVERED"},
        projected_state_reader=live_reader(lambda: dict(world["projection"])),
        entity_version_reader=live_reader(lambda: dict(world["versions"])),
        approval=approval,
    )
    request = CheckpointRequest(effect=effect, actor="pipeline",
                               accountable_owner="owner:rasheed", target_entity_ref=resource)
    return effect, inputs, request, world


def _rows(store, table, commit_key):
    return store.conn.execute(
        f"SELECT * FROM {table} WHERE tenant = ? AND commit_key = ?",
        (store.tenant, commit_key)).fetchall()


def test_e2e_a_durable_tenant_policy_PERMITS_and_the_exact_version_is_BOUND(tmp_path):
    """### (a): ONE witness, ONE claimed grant, and both bound to the DURABLE version.

    This is the positive control for every refusal below. A battery in which the happy path does
    not work proves only that nothing works.
    """
    store, kernel, clock, authority = _wired(tmp_path)
    effect, inputs, request, _world = _scenario(kernel, clock, authority)
    bound = authority.current_policy_version()
    assert bound != "pv1", "the durable version must not be the registry's static string"

    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized, f"the green path refused: {outcome}"

    witnesses = _rows(store, "checkpoint_witnesses", effect.key())
    grants = _rows(store, "effect_grants", effect.key())
    assert len(witnesses) == 1 and len(grants) == 1
    assert witnesses[0]["policy_version"] == bound, (
        f"the witness bound {witnesses[0]['policy_version']!r}, not the durable {bound!r}"
    )
    assert grants[0]["policy_version"] == bound
    assert witnesses[0]["gate_decision"] == GateDecision.HUMAN_APPROVAL_REQUIRED.value
    assert grants[0]["gate_decision"] == GateDecision.HUMAN_APPROVAL_REQUIRED.value

    claim = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    assert claim.claimed, f"the claim refused on the green path: {claim.cause}"


def test_e2e_a_policy_change_between_checkpoint_and_claim_makes_the_claim_FAIL_CLOSED(tmp_path):
    """### AC-SAFE-010 / ADR-010 §9.1, THROUGH THE P8 AUTHORITY.

    Mint under the current version, activate a policy (which advances the tenant's version), then
    claim. The CAS must match ZERO ROWS and the adapter must do nothing. This is the property the
    whole version-binding half of the slice exists for.
    """
    store, kernel, clock, authority = _wired(tmp_path)
    effect, inputs, request, _world = _scenario(kernel, clock, authority)
    minted_under = authority.current_policy_version()

    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized
    assert _rows(store, "effect_grants", effect.key())[0]["policy_version"] == minted_under

    # ### THE WORLD MOVES: a new policy is activated, in a DIFFERENT scope.
    _activate(store.conn, scope="record_payable", gate=GateDecision.HUMAN_APPROVAL_REQUIRED,
              policy_id="pB")
    now_at = authority.current_policy_version()
    assert now_at != minted_under, "the fixture did not actually change the policy version"

    claim = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    assert not claim.claimed, "a grant minted under a superseded policy version was CLAIMED"
    assert claim.cause == "POLICY_CHANGED", f"the cause was {claim.cause!r}"

    # ### AND THE LEDGER PROVES THE CAS MATCHED ZERO ROWS: the grant is still GRANTED, never CLAIMED.
    grant = _rows(store, "effect_grants", effect.key())[0]
    assert grant["state"] == "GRANTED", f"the grant moved to {grant['state']!r} anyway"
    assert grant["claimed_at"] is None


def test_e2e_a_tenant_policy_NARROWED_to_forbidden_refuses_at_step_6_with_no_witness(tmp_path):
    """### (b): NO authorization capability whatsoever — no witness row, no grant row.

    The tenant narrows to FORBIDDEN. A valid, unexpired, correctly-authorised human approval is
    bound, and it changes nothing: no approval unlocks FORBIDDEN.
    """
    store, kernel, clock, authority = _wired(tmp_path, scope_gate=GateDecision.FORBIDDEN,
                                             policy_id="p-forbid")
    effect, inputs, request, _world = _scenario(kernel, clock, authority)
    assert inputs.approval is not None and inputs.approval.state == "GRANTED"

    outcome = run_checkpoint(kernel, request, inputs)
    assert not outcome.authorized, "FORBIDDEN was unlocked by a human approval"
    assert outcome.step == 6, f"refused at step {outcome.step}, not the policy step"
    assert outcome.reason == "FORBIDDEN_ACTION_CLASS", outcome.reason
    assert _rows(store, "checkpoint_witnesses", effect.key()) == []
    assert _rows(store, "effect_grants", effect.key()) == []


def test_e2e_an_unclassified_action_class_refuses_at_step_6_and_mints_nothing(tmp_path):
    """### F-20 END TO END. Before U8.1 this checkpoint would have PROCEEDED on the silent
    `HUMAN_APPROVAL_REQUIRED` default — with a human approval bound, it would have reached step 7
    and minted. Now the absence itself is the refusal."""
    store, kernel, clock, authority = _wired(tmp_path)
    # `wire_out` is in NO population: not in OCCURRENCE_RULES, not in PRODUCT_POLICY.
    assert "wire_out" not in ACTION_CLASS_POPULATION
    effect, inputs, request, _world = _scenario(kernel, clock, authority, action_class="wire_out")

    outcome = run_checkpoint(kernel, request, inputs)
    assert not outcome.authorized
    assert outcome.step == 6 and outcome.reason == "UNCLASSIFIED_ACTION_CLASS", (
        f"step={outcome.step} reason={outcome.reason!r}"
    )
    assert "wire_out" in outcome.detail
    assert _rows(store, "checkpoint_witnesses", effect.key()) == []
    assert _rows(store, "effect_grants", effect.key()) == []


def test_e2e_a_broadening_tenant_policy_cannot_authorize_anything(tmp_path):
    """The hostile case, end to end: an ACTIVE row above the ceiling denies rather than admits."""
    store, kernel, clock, authority = _wired(
        tmp_path, scope_gate=GateDecision.AUTONOMOUS_WITHIN_CAPS, policy_id="p-broad",
        machine_ceiling=GateDecision.AUTONOMOUS_WITHIN_CAPS)
    # The row is real, ACTIVE and human-activated, and it sits ABOVE the PRODUCT ceiling.
    assert product_gate_for("raise_invoice") is GateDecision.HUMAN_APPROVAL_REQUIRED
    assert store.conn.execute(
        "SELECT gate_decision FROM policies WHERE policy_id = 'p-broad' AND state = 'ACTIVE'"
    ).fetchone()[0] == GateDecision.AUTONOMOUS_WITHIN_CAPS.value

    effect, inputs, request, _world = _scenario(kernel, clock, authority)
    outcome = run_checkpoint(kernel, request, inputs)
    assert not outcome.authorized, "a broadening tenant policy authorized an effect"
    assert outcome.step == 6
    assert outcome.reason == "POLICY_DENIED", outcome.reason
    assert _rows(store, "effect_grants", effect.key()) == []


def test_e2e_an_unreadable_policy_store_refuses_and_never_means_unchanged(tmp_path):
    """### 'CANNOT READ THE POLICY' NEVER MEANS 'UNCHANGED' (ADR-010 §11).

    The symmetric twin of the brake's `BRAKE_UNREADABLE`. The policy store is dropped between mint
    and claim; the claim must refuse rather than compare against a stale cached value.

    ### WHAT "THE POLICY STORE" MEANS CHANGED AT U8.1/P8, AND THIS DROPS BOTH TABLES (rule 20).
    The version the claim re-reads now comes from `policy_epochs`, not from `MAX(policy_version)`
    over `policies`, so dropping `policies` alone would no longer make the read fail — the test
    would pass for the wrong reason, or not at all. `policy_epochs` also holds an FK into
    `policies`, so the drop order matters: the child goes first.
    """
    store, kernel, clock, authority = _wired(tmp_path)
    effect, inputs, request, _world = _scenario(kernel, clock, authority)
    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized

    store.conn.execute("DROP TABLE policy_epochs")
    store.conn.execute("DROP TABLE policies")
    store.conn.commit()

    claim = claim_grant_cas(kernel, outcome.handle, params_for(effect))
    assert not claim.claimed, "an unreadable policy store was treated as 'policy unchanged'"
    assert claim.cause == "POLICY_UNREADABLE", claim.cause
    grant = _rows(store, "effect_grants", effect.key())[0]
    assert grant["state"] == "GRANTED" and grant["claimed_at"] is None


def test_e2e_the_unbound_kernel_is_exactly_p3_minus_the_default(tmp_path):
    """The ships-dark path still works: no authority bound ⇒ the registry decides, and an
    unregistered class refuses instead of silently resolving."""
    from phase3_kit import default_registry, green_scenario

    store, kernel, _clock, effect, *_rest, inputs, request = green_scenario(
        tmp_path, registry=default_registry())
    assert kernel.policy_authority is None
    assert kernel.policy_version() == "pv1"
    outcome = run_checkpoint(kernel, request, inputs)
    assert outcome.authorized, f"the P3 path regressed: {outcome}"

    # ...and the class the registry does not carry now REFUSES rather than defaulting.
    store2, kernel2, _c2, effect2, *_r2, inputs2, request2 = green_scenario(
        tmp_path, action_class="record_payment", resource="load:9001",
        registry=default_registry())
    outcome2 = run_checkpoint(kernel2, request2, inputs2)
    assert not outcome2.authorized
    assert outcome2.reason == "UNCLASSIFIED_ACTION_CLASS", outcome2.reason


# ==================================================================================================
# THE PRICE OF EDITING THE KERNEL — the three invariants CLAUDE.md §10 actually protects
# ==================================================================================================

def test_the_three_kernel_invariants_claude_md_10_protects_still_hold(tmp_path):
    """### THE REPLACEMENT FOR `checkpoint.py`'s BYTE-IDENTITY GUARD (rule 20).

    U8.1 edits checkpoint step 6, so the P6 guard that froze `checkpoint.py` byte-for-byte was
    dropped (see `test_phase6_policy.py::test_the_neighbouring_machines_are_unchanged`). CLAUDE.md
    §10 never said the kernel may not be edited — it names three things that may not be WEAKENED.
    A hash proved all three by accident; this proves each on purpose, which is the stronger guard
    because it survives a legitimate edit and still fails a weakening one.
    """
    from freight_recon.checkpoint import CheckpointError, CheckpointPassed

    # ### (1) `CheckpointPassed` STAYS UNCONSTRUCTABLE. Code that has not passed the seven steps
    # has nothing to hand to `mint_grant`.
    with pytest.raises((CheckpointError, TypeError)):
        CheckpointPassed(checkpoint_id="forged", tenant=TENANT, commit_key="ck")  # type: ignore[call-arg]

    # ### (2) THE WITNESS TABLE STAYS APPEND-ONLY. Proved against a real database by ATTEMPTING
    # the forbidden writes, behind a positive control that the row is really there to update.
    store, kernel, clock, authority = _wired(tmp_path, name="p8-kernel.db")
    effect, inputs, request, _world = _scenario(kernel, clock, authority)
    assert run_checkpoint(kernel, request, inputs).authorized
    rows = _rows(store, "checkpoint_witnesses", effect.key())
    assert len(rows) == 1, "the positive control failed: there is no witness row to protect"

    for sql, label in (
        ("UPDATE checkpoint_witnesses SET policy_version = 'tampered' WHERE tenant = ?", "UPDATE"),
        ("DELETE FROM checkpoint_witnesses WHERE tenant = ?", "DELETE"),
    ):
        with pytest.raises(sqlite3.DatabaseError):
            store.conn.execute(sql, (store.tenant,))
            store.conn.commit()
        store.conn.rollback()
    after = _rows(store, "checkpoint_witnesses", effect.key())
    assert len(after) == 1 and after[0]["policy_version"] == rows[0]["policy_version"], (
        "a witness row was mutated: the table is no longer append-only"
    )

    # ### (3) THE CLAIM CAS's WHERE CLAUSE MAY NEVER LOSE A PREDICATE. Asserted on the SQL text of
    # the one UPDATE that claims a grant, by name, so a dropped predicate is a RED test and not a
    # silently wider claim.
    src = (ROOT / "src" / "freight_recon" / "checkpoint.py").read_text(encoding="utf-8")
    cas = src[src.index("UPDATE effect_grants"):]
    cas = cas[:cas.index('"""')]
    for predicate in ("tenant = ?", "grant_id = ?", "state = 'GRANTED'", "expires_at > ?",
                      "brake_version = ?", "policy_version = ?"):
        assert predicate in cas, (
            f"the claim CAS lost the {predicate!r} predicate. Every one of these is load-bearing: "
            "dropping one widens what may be claimed, which is the one thing this WHERE clause "
            f"exists to prevent.\n{cas}"
        )


def test_the_production_gate_registry_population_is_STILL_empty_after_u81(tmp_path):
    """### U8.1 DID NOT POPULATE THE KERNEL'S REGISTRY, AND THAT IS A DELIBERATE DESIGN CHOICE.

    R-07's containment record rests on condition (3) — *"the production GateRegistry population is
    EMPTY"* — and `CURRENT.md` says it *"stays EMPTY until U8.1/P8"*. U8.1 could have populated it
    and re-adjudicated that condition. It did not, because ADR-010 §3 puts the product ceiling in
    **CONFIG** rather than in the kernel's own code: `product_policy.py` declares it, with its own
    import-time completeness failure, and `checkpoint.py` remains the sole MINTER.

    ### SO THIS IS NOT "NO GATES EXIST" ANY MORE, AND A READER MUST NOT INFER THAT. Every one of
    the discovered action classes now carries an explicit gate — it just does not live in the P3
    registry. This test exists so the two facts are recorded together and neither can be read as
    the other.
    """
    import sys as _sys
    _sys.path.insert(0, str(ROOT / "eval"))
    from phase0 import gate_scan

    sites: list[str] = []
    swept = 0
    for root in ("src", "scripts"):
        for path in sorted((ROOT / root).rglob("*.py")):
            swept += 1
            sites += gate_scan.gate_registration_sites(
                path.read_text(encoding="utf-8"), label=str(path.relative_to(ROOT)))
    assert swept > 100, f"the sweep walked only {swept} modules — it saw a corner"
    assert sites == [], f"U8.1 populated the kernel registry after all: {sites}"

    # ...and the gates DO exist, in the module that declares them. Both halves, in one place.
    assert REGISTERED_ACTION_CLASS_COUNT == len(ACTION_CLASS_POPULATION) >= 8
    print(f"kernel GateRegistry registrations: 0 (swept {swept} modules); "
          f"product_policy classifications: {REGISTERED_ACTION_CLASS_COUNT}")
