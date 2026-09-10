"""P7 — generic evidence/claim lineage traversal (AC-7).

A canonical material fact used by downstream logic can be traced BACKWARD to the complete chain that
justifies it: claim -> provenance -> its terminating justification (an Evidence span, a registered
rule id, or a human decision_ref) -> and, for evidence-backed claims, on to the source Observation.
An escalation carries that chain rather than a pointer telling a human to go and look (PRODUCT.md
sec 9). ### FAIL CLOSED on a missing link — a claim whose evidence we cannot reach is a claim we
cannot defend.

This proves P7's OWN generic lineage mechanism (ADR-002 sec 2.1 concern 5, ADR-007 sec 13) over the
landed Evidence store; it requires no P9 domain entity. It reuses the kernel's ProvenanceClass — one
authority — and builds no second store. Ships dark.
"""

from __future__ import annotations

from dataclasses import dataclass

from .checkpoint import ProvenanceClass
from .evidence import EvidenceAbsent, EvidenceStore
from .provenance import as_class

# The provenance classes whose justification terminates in retained EVIDENCE (a document + span).
_EVIDENCE_BACKED = frozenset({ProvenanceClass.MODEL_EXTRACTED, ProvenanceClass.SYSTEM_IMPORTED})
# ...in a registered RULE with an id.
_RULE_BACKED = frozenset({ProvenanceClass.LINKER_INFERRED, ProvenanceClass.RECONCILED})
# ...in a human decision_ref.
_HUMAN_BACKED = frozenset({ProvenanceClass.OWNER_ASSERTED})


class LineageIncomplete(RuntimeError):
    """A canonical field's chain does not terminate in evidence, a rule id, or a decision_ref (AC-7).
    A consequential action on it BLOCKS — the fact cannot be walked back to why it is believed."""


@dataclass(frozen=True)
class CanonicalClaim:
    """A canonical material fact and the pointer to what justifies it. Exactly one justification is
    expected, and which one is DERIVED from the provenance class (not chosen freely)."""

    field: str
    provenance_class: ProvenanceClass
    evidence_id: str | None = None
    rule_id: str | None = None
    decision_ref: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "provenance_class", as_class(self.provenance_class))


def trace(store: EvidenceStore, tenant: object, claim: CanonicalClaim) -> dict:
    """Walk `claim` to its complete justification chain, or FAIL CLOSED. The returned chain always
    terminates in one of: an Evidence span, a registered rule id, or a human decision_ref — never a
    dangling pointer, and never a MODEL_INFERRED guess (which has no artifact and cannot justify a
    consequential field)."""
    pc = claim.provenance_class
    chain: dict = {"field": claim.field, "provenance_class": pc.value}

    if pc is ProvenanceClass.MODEL_INFERRED:
        raise LineageIncomplete(
            f"field {claim.field!r} is MODEL_INFERRED: a guess has no artifact, rule or decision to "
            f"walk back to. It may never justify a consequential field (ADR-002 sec 2.3)."
        )

    if pc in _EVIDENCE_BACKED:
        if not claim.evidence_id:
            raise LineageIncomplete(
                f"field {claim.field!r} is {pc.value} but names no Evidence: a claim read off an "
                f"artifact must point at the artifact (entity 08-evidence sec 13)."
            )
        # EvidenceStore.trace raises EvidenceAbsent when the artifact is lost — fail closed.
        ev_chain = store.trace(tenant, claim.evidence_id)
        spans = ev_chain["spans"]
        if pc is ProvenanceClass.MODEL_EXTRACTED and not spans:
            raise LineageIncomplete(
                f"field {claim.field!r} is MODEL_EXTRACTED but its Evidence has no span: the region "
                f"that makes the reading checkable is the whole point (entity sec 13/43(c))."
            )
        chain["terminates_in"] = "evidence"
        chain["evidence"] = ev_chain["evidence"]
        chain["spans"] = spans
        chain["source_observation_id"] = ev_chain["source_observation_id"]
        return chain

    if pc in _RULE_BACKED:
        if not (claim.rule_id and str(claim.rule_id).strip()):
            raise LineageIncomplete(
                f"field {claim.field!r} is {pc.value} but names no registered rule id: a "
                f"deterministic derivation must carry the rule that produced it (ADR-002 sec 2.3)."
            )
        chain["terminates_in"] = "rule_id"
        chain["rule_id"] = claim.rule_id
        return chain

    if pc in _HUMAN_BACKED:
        if not (claim.decision_ref and str(claim.decision_ref).strip()):
            raise LineageIncomplete(
                f"field {claim.field!r} is OWNER_ASSERTED but names no decision_ref: an owner's "
                f"assertion must carry the decision record behind it (ADR-007 sec 4.3)."
            )
        chain["terminates_in"] = "decision_ref"
        chain["decision_ref"] = claim.decision_ref
        return chain

    raise LineageIncomplete(f"field {claim.field!r}: no justification route for {pc.value}")


def is_defensible(store: EvidenceStore, tenant: object, claim: CanonicalClaim) -> bool:
    """True when the claim's chain can be walked to a terminating justification; False (fail closed)
    when a link is missing or the evidence is absent. This is the AC-7 audit-reconstruction predicate."""
    try:
        trace(store, tenant, claim)
        return True
    except (LineageIncomplete, EvidenceAbsent):
        return False
