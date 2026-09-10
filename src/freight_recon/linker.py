"""P7 — the deterministic identity linker (AC-8, AC-9), conflict closure (AC-10) and the
correction-vs-supersession distinction (AC-11). ### THE MODEL READS; THE LINKER DECIDES.

This is the decision PROCEDURE, not a second table or a second engine. It REUSES:
  * M6's canonical binding vocabulary — `MATCH_METHODS`, the SD-6 `PROVENANCE_BY_METHOD` mapping and
    `CONFIRMED_ALLOWED_PROVENANCE` (which classes may confirm a consequential binding);
  * M7's conflict-state vocabulary — `TERMINAL_CONFLICT_STATES`, `OPEN_CONFLICT_STATES`;
  * the provenance-safety core — R-P3 (`machine_recompute`) so a relink can never overwrite an
    `OWNER_ASSERTED` binding, and the six-class authority.
It builds no `identity_binding_claims` table (M6 owns that) and no `conflicts` table (M7 owns that);
it produces the bindings M6 records and the conflicts M7 records. Ships dark — no production importer.

ADR-007 sec 4.1 — binding is attempted in a FIXED ORDER and the first that CONFIRMS wins:
  1. EXACT_ID (an exact unique identifier match)      -> LINKER_INFERRED  -> may confirm
  2. RULE (a registered deterministic rule with an id) -> LINKER_INFERRED  -> may confirm
  3. RECONCILIATION (>= 2 agreeing sources, rule allows) -> RECONCILED     -> may confirm
  4. MODEL_EXTRACT (a model READ an identifier off an artifact) -> MODEL_EXTRACTED -> ### DOES NOT
     confirm: the extracted identifier RE-ENTERS at step 1 so the deterministic linker decides.
  5. MODEL_INFER (a model GUESSED)                     -> MODEL_INFERRED   -> ### NEVER confirms:
     routes to AMBIGUOUS and gets a human, at confidence 1.0 as at 0.5.
  6. HUMAN (an authenticated, authorized human)        -> OWNER_ASSERTED   -> confirms.

Confidence orders a human's queue and authorizes NOTHING. Ambiguous, multiple or weak candidates
FAIL CLOSED to human handling — the linker never guesses a bind.

### THE MECHANISM IS WHAT THIS ACCEPTS, NOT A RULE SET. ADR-007 sec 15 Q1 records the registered
freight identity rules as `NEEDS VALIDATION`, discovered per customer at onboarding, so this module
implements the ordered mechanism and invents no freight rule.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

from .migrations.phase6_conflicts import OPEN_CONFLICT_STATES, TERMINAL_CONFLICT_STATES
from .migrations.phase6_identity_binding_claims import (
    CONFIRMED_ALLOWED_PROVENANCE,
    MATCH_METHODS,
    PROVENANCE_BY_METHOD,
)
from .provenance import (
    OwnerAssertedRecompute,
    ProvenanceClass,
    ProvenanceRecord,
    as_class,
    machine_recompute,
)

# The deterministic methods that may CONFIRM, in ADR-007 sec 4.1 order. MODEL_EXTRACT and MODEL_INFER
# are handled specially (re-enter / never confirm); HUMAN is the authenticated-human route.
_CONFIRMING_ORDER: tuple[str, ...] = ("EXACT_ID", "RULE", "RECONCILIATION")

# The reasons a binding fails closed to a human (M6's closed ClaimAmbiguous.reason enum).
REASON_MODEL_INFERRED = "model_inferred"
REASON_MULTIPLE = "multiple"
REASON_SINGLE_WEAK = "single_weak"


class LinkStatus(enum.Enum):
    CONFIRMED = "CONFIRMED"     # a deterministic method bound it
    AMBIGUOUS = "AMBIGUOUS"     # fail closed to a human — no bind
    CONFLICT = "CONFLICT"       # mutually exclusive confirming candidates — blocks, first-class


class LinkerError(RuntimeError):
    """A structural misuse of the linker. Fail closed."""


@dataclass(frozen=True)
class Signal:
    """A candidate binding signal. A model may PROPOSE one (match_method MODEL_EXTRACT / MODEL_INFER);
    the linker reads it but never lets it decide. `confidence` may be attached and is IGNORED for
    authority — it orders a queue, it gates nothing."""

    match_method: str
    identifier: str          # the entity this signal points at, e.g. "load-4471"
    source: str = ""
    rule_id: str | None = None   # required for a RULE signal to be a REGISTERED rule
    confidence: float | None = None

    def __post_init__(self) -> None:
        if self.match_method not in MATCH_METHODS:
            raise LinkerError(
                f"unknown match_method {self.match_method!r}; the six are {MATCH_METHODS}"
            )
        if not str(self.identifier or "").strip():
            raise LinkerError("a binding signal must name the identifier it points at")


@dataclass(frozen=True)
class LinkOutcome:
    subject_ref: str
    status: LinkStatus
    bound_identifier: str | None = None
    provenance_class: ProvenanceClass | None = None
    match_method: str | None = None
    reason: str | None = None                 # set when AMBIGUOUS
    conflict_parties: tuple[str, ...] = ()     # set when CONFLICT

    @property
    def is_binding(self) -> bool:
        return self.status is LinkStatus.CONFIRMED


def _distinct_identifiers(signals: list[Signal]) -> list[str]:
    seen: list[str] = []
    for s in signals:
        if s.identifier not in seen:
            seen.append(s.identifier)
    return seen


def link(subject_ref: str, signals: list[Signal], *, authenticated_human: bool = False) -> LinkOutcome:
    """Decide the binding for `subject_ref` from candidate signals, in ADR-007 sec 4.1 order. Returns
    a CONFIRMED binding, an AMBIGUOUS fail-closed outcome (no bind), or a first-class CONFLICT.

    A model-proposed binding is NEVER committed as authority: a MODEL_EXTRACT identifier re-enters as
    a deterministic EXACT_ID candidate (the linker decides), and a MODEL_INFER guess routes straight to
    AMBIGUOUS — at any confidence."""
    if not str(subject_ref or "").strip():
        raise LinkerError("link requires a subject_ref — the artifact being bound")
    by_method: dict[str, list[Signal]] = {m: [] for m in MATCH_METHODS}
    for s in signals:
        by_method[s.match_method].append(s)

    # (6) An authenticated human assertion binds OWNER_ASSERTED outright. A HUMAN signal WITHOUT an
    # authenticated human is not owner-asserted — it fails closed rather than being trusted.
    if by_method["HUMAN"]:
        if not authenticated_human:
            return LinkOutcome(subject_ref, LinkStatus.AMBIGUOUS, reason=REASON_SINGLE_WEAK)
        ids = _distinct_identifiers(by_method["HUMAN"])
        if len(ids) > 1:
            return LinkOutcome(subject_ref, LinkStatus.CONFLICT, conflict_parties=tuple(ids))
        return LinkOutcome(subject_ref, LinkStatus.CONFIRMED, bound_identifier=ids[0],
                           provenance_class=ProvenanceClass.OWNER_ASSERTED, match_method="HUMAN")

    # (4) MODEL_EXTRACT does not itself confirm: its identifier RE-ENTERS as an EXACT_ID candidate so
    # the deterministic linker — not the model — decides.
    reentered = list(by_method["EXACT_ID"])
    for s in by_method["MODEL_EXTRACT"]:
        reentered.append(Signal(match_method="EXACT_ID", identifier=s.identifier,
                                source=f"reentered_from_model_extract:{s.source}"))
    effective = {**by_method, "EXACT_ID": reentered}

    # (1)-(3) the confirming deterministic methods, in order; the first that yields exactly one
    # identifier wins. More than one distinct identifier for a method is a first-class CONFLICT.
    for method in _CONFIRMING_ORDER:
        method_signals = effective[method]
        if method == "RECONCILIATION":
            # reconciliation confirms only across >= 2 agreeing sources.
            if len({s.source for s in method_signals}) < 2:
                if method_signals:
                    return LinkOutcome(subject_ref, LinkStatus.AMBIGUOUS, reason=REASON_SINGLE_WEAK)
                continue
        if method == "RULE" and any(not s.rule_id for s in method_signals):
            # a RULE signal without a registered rule id is not a registered rule — it cannot confirm.
            return LinkOutcome(subject_ref, LinkStatus.AMBIGUOUS, reason=REASON_SINGLE_WEAK)
        ids = _distinct_identifiers(method_signals)
        if not ids:
            continue
        if len(ids) > 1:
            return LinkOutcome(subject_ref, LinkStatus.CONFLICT, conflict_parties=tuple(ids))
        provenance = as_class(PROVENANCE_BY_METHOD[method])
        if provenance.value not in CONFIRMED_ALLOWED_PROVENANCE:
            # defensive: a method whose provenance may not confirm never binds here.
            return LinkOutcome(subject_ref, LinkStatus.AMBIGUOUS, reason=REASON_SINGLE_WEAK)
        return LinkOutcome(subject_ref, LinkStatus.CONFIRMED, bound_identifier=ids[0],
                           provenance_class=provenance, match_method=method)

    # (5) A model inference NEVER confirms — it routes to AMBIGUOUS and gets a human, at any confidence.
    if by_method["MODEL_INFER"]:
        return LinkOutcome(subject_ref, LinkStatus.AMBIGUOUS, reason=REASON_MODEL_INFERRED)
    # Nothing deterministic bound: fail closed to a human rather than guess.
    return LinkOutcome(subject_ref, LinkStatus.AMBIGUOUS, reason=REASON_SINGLE_WEAK)


def relink(existing: ProvenanceRecord, subject_ref: str, signals: list[Signal],
           *, authenticated_human: bool = False) -> ProvenanceRecord:
    """AC-9: re-running the linker over an existing binding may never overwrite an `OWNER_ASSERTED`
    one. If the existing binding is owner-asserted, the machine recompute is REFUSED (R-P3) and the
    owner's value is preserved byte-identical; a disagreement is a Conflict, never a silent overwrite.
    For a non-owner binding, a fresh deterministic bind supersedes it."""
    outcome = link(subject_ref, signals, authenticated_human=authenticated_human)
    proposed_class = outcome.provenance_class or ProvenanceClass.MODEL_INFERRED
    proposed_value = outcome.bound_identifier if outcome.is_binding else existing.value
    # machine_recompute raises OwnerAssertedRecompute when `existing` is OWNER_ASSERTED — the owner
    # binding survives the relinker, exactly the L-A defect this rule exists to prevent.
    return machine_recompute(existing, new_value=proposed_value, new_class=proposed_class.value)


def owner_binding_survives_replay(bindings: list[ProvenanceRecord]) -> bool:
    """AC-9: replaying/rebuilding reconstructs projections, not the owner's mind. An OWNER_ASSERTED
    binding replays byte-identical: reconstructing a record from its own fields yields an equal record,
    and a relink attempt over it is refused. Proved over a population PROVEN NON-EMPTY by the caller."""
    for b in bindings:
        rebuilt = ProvenanceRecord(value=b.value, provenance_class=b.provenance_class)
        if rebuilt != b:
            return False
        if b.provenance_class is ProvenanceClass.OWNER_ASSERTED:
            try:
                machine_recompute(b, new_value="RELINKED", new_class="LINKER_INFERRED")
                return False  # a relink overwrote an owner binding on replay — the L-A defect
            except OwnerAssertedRecompute:
                pass
    return True


# ------------------------------------------------------------------- AC-10: conflict closes two ways


class ConflictClosureRefused(RuntimeError):
    """A Conflict was closed by something other than a registered rule or a human decision_ref
    (AC-10). Not a model, not recency, not source priority, not a timeout, not last-write-wins."""


def close_conflict(*, rule_id: str | None = None, decision_ref: str | None = None) -> str:
    """AC-10: a Conflict closes EXACTLY TWO WAYS and no third — a REGISTERED versioned rule carrying a
    `rule_id` (RESOLVED_BY_RULE), or an authenticated human carrying a `decision_ref` (RESOLVED_BY_HUMAN).
    Exactly one must be supplied. Returns the terminal state (M7's vocabulary). Anything else — a model,
    recency, source priority, a timeout — cannot close it, and `AutoResolve` is illegal."""
    has_rule = bool(rule_id and str(rule_id).strip())
    has_human = bool(decision_ref and str(decision_ref).strip())
    if has_rule and has_human:
        raise ConflictClosureRefused(
            "a Conflict closes ONE way at a time — a registered rule OR a human decision, never both"
        )
    if has_rule:
        return "RESOLVED_BY_RULE"
    if has_human:
        return "RESOLVED_BY_HUMAN"
    raise ConflictClosureRefused(
        "a Conflict closes ONLY via a registered rule (rule_id) or a human decision (decision_ref) "
        "(AC-10, ADR-007 sec 5.3): never by a model, recency, source priority, a timeout or "
        "last-write-wins. A Conflict that times out is a Conflict resolved by a clock, and the clock "
        "knows nothing about freight — it ages and escalates, it never resolves."
    )


def conflict_blocks(state: str) -> bool:
    """AC-10: while a Conflict is open (RAISED/OPEN/ESCALATED) it BLOCKS every dependent consequential
    action; a terminal state does not."""
    if state in OPEN_CONFLICT_STATES:
        return True
    if state in TERMINAL_CONFLICT_STATES:
        return False
    raise LinkerError(f"unknown conflict state {state!r}; the five are the M7 vocabulary")


# ------------------------------------------------------------------- AC-11: correction != supersession


@dataclass(frozen=True)
class Claim:
    claim_id: str
    subject_ref: str
    value: object
    provenance_class: ProvenanceClass

    def __post_init__(self) -> None:
        object.__setattr__(self, "provenance_class", as_class(self.provenance_class))


@dataclass(frozen=True)
class ClaimHistory:
    """The result of a supersession or a correction. The prior claim is ALWAYS retained and remains
    attributable — conflating supersession and correction loses money, so they are distinct outcomes."""

    current: Claim
    retained: tuple[Claim, ...]
    kind: str                      # "supersession" | "correction"
    corrected_event: dict | None = None       # ClaimCorrected{...} for a correction, else None
    downstream_obligation: bool = False        # a correction produces one; a supersession does not


def supersede(prior: Claim, new_value: object, new_provenance: object) -> ClaimHistory:
    """AC-11 supersession: a newer claim replaces an older one that was TRUE WHEN MADE. The prior is
    RETAINED (never deleted) and nothing downstream is invalidated — no remediation obligation."""
    new_claim = Claim(claim_id=f"{prior.claim_id}+1", subject_ref=prior.subject_ref,
                      value=new_value, provenance_class=as_class(new_provenance))
    return ClaimHistory(current=new_claim, retained=(prior,), kind="supersession",
                        downstream_obligation=False)


def correct(prior: Claim, new_value: object, *, decision_ref: str, new_provenance: object) -> ClaimHistory:
    """AC-11 correction: an existing CONFIRMED claim is declared WRONG. The prior claim is RETAINED and
    remains ATTRIBUTABLE, a `ClaimCorrected` event is produced carrying the prior, the new, the
    decision_ref and the provenance, and a downstream remediation obligation is raised (the lineage is
    walked FORWARD to identify what rested on the wrong claim). A correction that does not propagate is
    a lie with a timestamp."""
    if not str(decision_ref or "").strip():
        raise LinkerError("a correction is a human decision and requires a decision_ref (AC-11)")
    new_claim = Claim(claim_id=f"{prior.claim_id}#corrected", subject_ref=prior.subject_ref,
                      value=new_value, provenance_class=as_class(new_provenance))
    corrected_event = {
        "event": "ClaimCorrected",
        "prior": prior.claim_id,
        "new": new_claim.claim_id,
        "decision_ref": decision_ref,
        "provenance_class": new_claim.provenance_class.value,
    }
    return ClaimHistory(current=new_claim, retained=(prior,), kind="correction",
                        corrected_event=corrected_event, downstream_obligation=True)
