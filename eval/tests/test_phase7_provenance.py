"""P7 — the provenance-safety core — acceptance and hostile battery.

Covers the four highest-weighted P7 criteria as OPERABLE rules, each with a refusal AND a positive
control that the legitimate path is admitted:

  * AC-2  — exactly the six provenance classes, ONE authority (kernel + M5 + M6 + evidence agree),
            runtime-assigned (R-P1).
  * AC-4  — a MODEL_INFERRED fact may not be read by a consequential gate (AC-SAFE-015), at any
            confidence; proved consistent with the kernel's own ProvenancedFact enforcement.
  * AC-3  — no provenance laundering (R-P2): a guess never strengthens by copy/cache/re-observe/
            reconcile/serialize/process-boundary; the sole strengthening route is a human act.
  * AC-5  — OWNER_ASSERTED is never machine-recomputed (R-P3, the L-A defect): the attempt fails
            closed and the owner's value is preserved.

Several node ids are the guards `scripts/mutate_phase7_provenance.py` turns RED — a guard never seen
to fail is a decoration.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "freight_recon"

from freight_recon import provenance as P  # noqa: E402
from freight_recon.checkpoint import (  # noqa: E402
    EvidenceCondition,
    GateReadOfInferredFact,
    ProvenanceClass,
    ProvenancedFact,
)

SIX = {"SYSTEM_IMPORTED", "OWNER_ASSERTED", "LINKER_INFERRED",
       "MODEL_EXTRACTED", "MODEL_INFERRED", "RECONCILED"}


def require_population(items, what: str):
    assert items, f"no {what} to assert over - this test would pass vacuously"
    return items


# =============================================================== AC-2: six classes, one authority


def test_exactly_the_six_provenance_classes_and_no_seventh():
    """AC-2: EXACT SET EQUALITY over the six identifiers, both directions — a count match with a
    different member must fail. Derived from the kernel enum, so a seventh cannot be smuggled in."""
    assert P.PROVENANCE_CLASS_VALUES == SIX
    assert {pc.value for pc in P.PROVENANCE_CLASSES} == SIX
    assert len(P.PROVENANCE_CLASSES) == 6
    with pytest.raises(P.ProvenanceError):
        P.as_class("BROKER_VOUCHED")  # a plausible seventh is refused


def test_provenance_is_one_authority_across_kernel_m5_m6_and_evidence():
    """AC-2 'ONE authority': the kernel enum, M5's observation vocabulary, M6's binding vocabulary and
    the Evidence store's MODEL_EXTRACTED constant all speak the same six. Two definitions that could
    silently disagree is the defect a single authority prevents."""
    from freight_recon.evidence import MODEL_EXTRACTED as EV_MODEL_EXTRACTED
    from freight_recon.migrations.phase6_identity_binding_claims import (
        CONFIRMED_ALLOWED_PROVENANCE,
        LAUNDERABLE_MODEL_PROVENANCE,
        PROVENANCE_BY_METHOD,
    )
    from freight_recon.migrations.phase6_observations import (
        OBSERVATION_FORBIDDEN_PROVENANCE,
        OBSERVATION_PROVENANCE_ALLOWED,
    )

    # M5: the five an observation may carry plus the one it may never == the canonical six.
    m5_vocab = {*OBSERVATION_PROVENANCE_ALLOWED, OBSERVATION_FORBIDDEN_PROVENANCE}
    assert m5_vocab == SIX, f"M5's provenance vocabulary drifted from the six: {m5_vocab ^ SIX}"
    # M6: every provenance it derives or admits is one of the six.
    m6_used = ({*PROVENANCE_BY_METHOD.values()} | {*CONFIRMED_ALLOWED_PROVENANCE}
               | {*LAUNDERABLE_MODEL_PROVENANCE})
    require_population(m6_used, "M6 provenance values")
    assert m6_used <= SIX, f"M6 uses a provenance value outside the six: {m6_used - SIX}"
    # Evidence: its one provenance constant is the canonical MODEL_EXTRACTED.
    assert EV_MODEL_EXTRACTED == ProvenanceClass.MODEL_EXTRACTED.value


# =============================================================== R-P1: runtime assignment


def test_provenance_is_assigned_by_the_runtime_from_how_the_value_was_obtained():
    """R-P1: the class is a function of the Acquisition — the runtime's record of HOW it got the
    value — and nothing else. Every acquisition maps to exactly the ADR-002 sec 2.3 meaning."""
    expected = {
        P.Acquisition.EXTERNAL_SYSTEM_OF_RECORD: ProvenanceClass.SYSTEM_IMPORTED,
        P.Acquisition.AUTHENTICATED_HUMAN_ACT: ProvenanceClass.OWNER_ASSERTED,
        P.Acquisition.DETERMINISTIC_RULE: ProvenanceClass.LINKER_INFERRED,
        P.Acquisition.MODEL_READ_FROM_ARTIFACT: ProvenanceClass.MODEL_EXTRACTED,
        P.Acquisition.MODEL_GUESS: ProvenanceClass.MODEL_INFERRED,
        P.Acquisition.RECONCILIATION_OF_SOURCES: ProvenanceClass.RECONCILED,
    }
    for acquisition in require_population(list(P.Acquisition), "acquisition methods"):
        assert P.assign_at_runtime(acquisition) is expected[acquisition]
    # a model 'guess' can only ever be MODEL_INFERRED — never chosen up.
    assert P.assign_at_runtime(P.Acquisition.MODEL_GUESS) is ProvenanceClass.MODEL_INFERRED
    # a caller cannot pass a class string in place of an acquisition (not caller-forgeable).
    with pytest.raises(P.ProvenanceError):
        P.assign_at_runtime("OWNER_ASSERTED")  # type: ignore[arg-type]


def test_inbound_content_cannot_choose_its_own_provenance():
    """R-P1: a payload/document/event carrying `provenance_class` (or `provenance`) is refused — a
    counterparty asserting OWNER_ASSERTED is a fraud signal, never authority (ADR-003)."""
    for key in ("provenance_class", "provenance"):
        with pytest.raises(P.ProvenanceFromContent):
            P.reject_content_supplied_provenance({key: "OWNER_ASSERTED", "amount": "2850"})
    # positive control: ordinary content with no provenance key is admitted.
    P.reject_content_supplied_provenance({"amount": "2850", "carrier": "ACME"})


# =============================================================== AC-4 / AC-SAFE-015: gate reads


def test_a_model_inferred_fact_cannot_be_read_by_a_consequential_gate():
    """AC-4 / AC-SAFE-015: reading a MODEL_INFERRED value for a consequential gate raises the kernel's
    GateReadOfInferredFact. The positive control proves the refusal is not unconditional: a
    SYSTEM_IMPORTED value reads through."""
    with pytest.raises(GateReadOfInferredFact):
        P.read_for_consequential_gate("MODEL_INFERRED", 2850)
    assert P.may_gate_consequential_action("MODEL_INFERRED") is False
    # positive control: every other class may be read by a gate (subject to the checkpoint's own
    # live revalidation and money fence, which this layer does not replace).
    for pc in SIX - {"MODEL_INFERRED"}:
        assert P.may_gate_consequential_action(pc) is True
        assert P.read_for_consequential_gate(pc, 2850) == 2850


def test_confidence_cannot_rescue_a_model_inferred_gate_read():
    """AC-4: there is no confidence — the gate-read carries no confidence parameter, so a
    MODEL_INFERRED fact is refused whatever value it holds. 'At confidence 1.0 it STILL refuses.'"""
    import inspect
    sig = inspect.signature(P.read_for_consequential_gate)
    assert "confidence" not in sig.parameters, "a confidence parameter would let a guess be argued up"
    for value in (2850, 0.99, 1.0, "very likely"):
        with pytest.raises(GateReadOfInferredFact):
            P.read_for_consequential_gate("MODEL_INFERRED", value)


def test_the_kernel_gate_enforces_the_same_rule_this_layer_states():
    """One authority: the kernel's ProvenancedFact.value IS the enforcing gate accessor, and it
    refuses MODEL_INFERRED. This layer's predicate agrees with it, member by member — it states the
    rule the kernel enforces, it does not compete with it."""
    for pc in ProvenanceClass:
        fact = ProvenancedFact(field="amount", provenance=pc,
                               evidence_condition=EvidenceCondition.CONSISTENT, _value=2850)
        if P.may_gate_consequential_action(pc):
            assert fact.value == 2850, f"{pc}: layer says gateable but the kernel refused"
        else:
            with pytest.raises(GateReadOfInferredFact):
                _ = fact.value


# =============================================================== AC-3 / R-P2: no laundering


def test_provenance_may_weaken_but_never_mechanically_strengthen():
    """R-P2: weakening is always allowed; a mechanical strengthen is refused as laundering. The sole
    strengthening route is a new authenticated human act creating OWNER_ASSERTED."""
    # strengthening a guess by a mechanical route is refused (the canonical R-P2 example).
    with pytest.raises(P.ProvenanceLaundering):
        P.reassign("MODEL_INFERRED", "LINKER_INFERRED")
    with pytest.raises(P.ProvenanceLaundering):
        P.reassign("MODEL_INFERRED", "OWNER_ASSERTED")  # no human act
    # a counterparty MODEL_EXTRACTED reading cannot be mechanically promoted (ADR-003).
    with pytest.raises(P.ProvenanceLaundering):
        P.reassign("MODEL_EXTRACTED", "OWNER_ASSERTED")
    # positive controls: weakening is allowed, and a human act legitimately creates OWNER_ASSERTED.
    assert P.reassign("OWNER_ASSERTED", "MODEL_INFERRED") is ProvenanceClass.MODEL_INFERRED
    assert P.reassign("LINKER_INFERRED", "MODEL_EXTRACTED") is ProvenanceClass.MODEL_EXTRACTED
    assert P.reassign("MODEL_INFERRED", "OWNER_ASSERTED",
                      authenticated_human_act=True) is ProvenanceClass.OWNER_ASSERTED


def test_a_model_inferred_fact_stays_model_inferred_through_every_derivation_path():
    """R-P2: the six-path sweep — copy / cache / re-observe / reconcile / serialize / process-boundary
    — over a PROVEN NON-EMPTY path population. A guess emerges a guess every time; laundering is a
    guess acquiring authority by moving through layers."""
    paths = require_population(P.DERIVATION_PATHS, "derivation paths")
    assert len(paths) == 6, f"the six-path sweep collapsed to {len(paths)} paths"
    for path in paths:
        assert P.derive_through("MODEL_INFERRED", path) is ProvenanceClass.MODEL_INFERRED, path
    # carry never strengthens, for any source class.
    for pc in SIX:
        assert P.carry(pc) is P.as_class(pc)


# =============================================================== AC-5 / R-P3: OWNER_ASSERTED


def test_owner_asserted_is_never_machine_recomputed_and_the_value_is_preserved():
    """R-P3 / AC-SAFE-016: a machine recompute over an OWNER_ASSERTED record is ILLEGAL — it raises,
    persists nothing, and the owner's value is preserved byte-identical. The positive control proves a
    non-owner record IS recomputable, so the guard is not unconditional."""
    owner = P.ProvenanceRecord(value="load-4471", provenance_class="OWNER_ASSERTED")
    for new_class in ("LINKER_INFERRED", "MODEL_EXTRACTED", "MODEL_INFERRED", "RECONCILED",
                      "SYSTEM_IMPORTED"):
        with pytest.raises(P.OwnerAssertedRecompute):
            P.machine_recompute(owner, new_value="load-44718", new_class=new_class)
        assert owner.value == "load-4471", "the owner's value was not preserved after the refusal"
    # a machine may never assert OWNER_ASSERTED either — that is a human's authority.
    non_owner = P.ProvenanceRecord(value="x", provenance_class="MODEL_EXTRACTED")
    with pytest.raises(P.OwnerAssertedRecompute):
        P.machine_recompute(non_owner, new_value="y", new_class="OWNER_ASSERTED")
    # positive control: recomputing a non-owner record with a machine class succeeds.
    recomputed = P.machine_recompute(non_owner, new_value="y", new_class="LINKER_INFERRED")
    assert recomputed.provenance_class is ProvenanceClass.LINKER_INFERRED
    # the ONE legal overwrite: a new authenticated human act supersedes with OWNER_ASSERTED.
    superseding = P.human_reassert(owner, new_value="load-44718")
    assert superseding.provenance_class is ProvenanceClass.OWNER_ASSERTED
    assert owner.value == "load-4471", "human_reassert must not mutate the prior record in place"


# =============================================================== ships dark (AC-15 touch)


def test_the_provenance_module_ships_dark_with_no_production_importer():
    """P7 ships dark: nothing in production imports the provenance-safety module. Discovered by AST
    over the whole src tree with the denominator printed — never a hand-enumerated filename list."""
    importers = []
    inspected = 0
    for path in require_population(sorted(SRC.rglob("*.py")), "src modules"):
        if path.name == "provenance.py":
            continue
        inspected += 1
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.endswith(".provenance"):
                importers.append(path.name)
            if isinstance(node, ast.ImportFrom) and not node.module and any(
                a.name == "provenance" for a in node.names
            ):
                importers.append(path.name)
    print(f"AC-15 (provenance): inspected {inspected} src modules for a production importer")
    assert inspected > 0
    assert not importers, f"the provenance-safety module has production importer(s): {importers}"
