"""Audit reconstruction: explaining how operational state was reached (P5 U5.6, `AC-AUD-*`).

    `explain(effect_id)` MUST reconstruct ALL EIGHTEEN, using the beliefs OF THAT DAY — not
    current state. — `observability-and-audit-acceptance.md`

### THE ONE RULE THAT MAKES THIS HARD, AND THE ONLY MECHANISM THAT SATISFIES IT.

`AC-AUD-002`: *change the policy/rule/model TODAY ⇒ `explain(...)` returns the ORIGINAL versions,
byte-identical to the pre-change response.* An explanation assembled by looking anything up — the
current policy, the current brake, the current provenance of a claim — is wrong the first time
anything changes, and it is wrong in the direction that makes an audit useless: it describes the
system as it is now while claiming to describe a decision made 90 days ago.

So **this module reads events and nothing else.** It takes no store, opens no connection, and
consults no registry. Every one of the eighteen fields is either carried in an event envelope or
its payload, or it is reported as UNRECONSTRUCTIBLE by name. A field that cannot be found is never
filled in from today's state, because a plausible answer is worse than a stated absence — §5's pins
(`policy_version`, `brake_version`, `entity_versions`, `material_facts_fingerprint`) exist
precisely so that the decision context travels WITH the fact, and this is the code that spends them.

### WHAT UNKNOWN MEANS HERE. `AC-AUD-006` requires an UNKNOWN to be explainable AS an unknown — the
reason, the exposure, what was tried, and the specific human question. So `unknown` is a first-class
reconstructed field, not an empty string, and `ER-6` (`OutcomeUnknown` MUST carry `unknown_reason`)
is what makes it reconstructible at all.

WHAT THIS DOES NOT DO YET, STATED SO NOBODY READS MORE INTO IT

`EX-1`, the acceptance fixture, is *"a completed consequential trace (a POD→invoice→payment chain)
90 days old"*. That chain is produced by the freight-domain machines, which are **P6**. This module
is the reconstruction MECHANISM and it is exercised against canonical-event histories; the
end-to-end `EX-1` fixture and its `AC-AUD-005` latency figure arrive when there is a real chain to
reconstruct. Claiming `AC-AUD-*` green today would be claiming a freight capability that does not
exist.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .event_contracts import CONTRACTS, contract_for
from .event_envelope import EventEnvelope

# The marker for a field the corpus does not carry. ### NEVER `None`, and never omitted: "we have
# no evidence of an approval" and "there was no approval" are different findings, and an audit that
# renders them identically is an audit that cannot be trusted about the second one.
UNRECONSTRUCTIBLE = "UNRECONSTRUCTIBLE"

# The eighteen, verbatim from `observability-and-audit-acceptance.md`. Named here so the response
# shape is the specification's rather than a convenient subset — `AC-AUD-001`'s oracle is a
# field-by-field assertion, so a missing key must be a missing KEY, not a quietly narrower answer.
EIGHTEEN_FIELDS: tuple[str, ...] = (
    "what_happened",
    "who_acted",
    "accountable_owner",
    "what_was_known",
    "what_was_unknown",
    "what_conflicted",
    "what_evidence_existed",
    "provenance_of_material_facts",
    "entity_versions_pinned",
    "what_approval_existed",
    "policy_version_applied",
    "brake_version_applied",
    "why_the_checkpoint_passed_or_failed",
    "commit_key_held",
    "adapter_operation_ran",
    "what_verification_proved",
    "why_the_work_item_closed_or_stayed_open",
    "material_facts_fingerprint",
)


class AuditError(RuntimeError):
    """The explanation cannot be reconstructed. It is never approximated."""


@dataclass(frozen=True)
class Explanation:
    """One reconstructed answer, plus the evidence it was reconstructed from.

    `trace` is the ordered event ids the answer folds — so an explanation can be re-derived by hand
    from the same corpus, which is what `AC-AUD-004`'s "evidence traversal from any canonical field"
    is for. An explanation nobody can check is a claim.
    """

    subject: str
    tenant_id: str
    fields: Mapping[str, Any]
    trace: tuple[str, ...]
    as_of: str

    def __getitem__(self, name: str) -> Any:
        return self.fields[name]

    @property
    def reconstructed(self) -> tuple[str, ...]:
        return tuple(k for k, v in self.fields.items() if v != UNRECONSTRUCTIBLE)

    @property
    def unreconstructible(self) -> tuple[str, ...]:
        return tuple(k for k, v in self.fields.items() if v == UNRECONSTRUCTIBLE)


# --------------------------------------------------------------------- reading beliefs-of-that-day

def _last(values: Sequence[Any]) -> Any:
    return values[-1] if values else UNRECONSTRUCTIBLE


def _payload_of(events: Sequence[EventEnvelope], *names: str) -> list[Mapping[str, Any]]:
    wanted = set(names)
    return [e.payload for e in events if e.event_name in wanted]


def _pin(events: Sequence[EventEnvelope], attribute: str, *, subject: str | None = None) -> Any:
    """The pinned envelope value AS IT WAS, from the SUBJECT'S OWN aggregate where it has one.

    ### SUBJECT-SCOPED, BECAUSE A CHAIN SPANS SEVERAL AGGREGATES AND THEY PIN DIFFERENT THINGS.
    Taking the last value across the whole chain reported the COMPENSATION's SD-3 set as the
    EFFECT's — the identical defect that was fixed in `what_was_known` and left live here, five of
    the eighteen fields wide. It was green only because a redelivered event happened to sit last in
    corpus order, so a fixture's arrangement was holding up a correctness assertion.

    Within the subject's own events, LAST still wins: a chain's later consequential events pin the
    context the decision actually executed under. The fall-back to the whole chain is deliberate and
    only reached when the subject's own aggregate pinned nothing at all.
    """
    def carried(pool: Sequence[EventEnvelope]) -> list[Any]:
        return [getattr(e, attribute) for e in pool
                if getattr(e, attribute, None) not in (None, "", {}, [])]

    if subject is not None:
        own = carried([e for e in events if e.aggregate_id == subject])
        if own:
            return _last(own)
    return _last(carried(events))


def explain(
    events: Iterable[EventEnvelope],
    *,
    subject: str,
    tenant: str,
) -> Explanation:
    """Reconstruct the eighteen for one subject, from its events alone.

    `events` is the subject's causal chain — every canonical fact about it, in corpus order.
    Assembling that chain is the caller's job (`chain_for` does it for an aggregate); this function
    does the reading, and it reads NOTHING else.
    """
    # ### DEDUP ONCE, BEFORE ANY FIELD IS ASSEMBLED (§4, AC-EVT-004). The rebuild ignores a
    # redelivered fact; an explanation that did not would report one grant claimed TWICE — and
    # `GrantDoubleClaimAttempted` is a real F14 security event, so a spurious double-claim in an
    # audit is materially misleading rather than merely untidy.
    ordered, _seen = [], set()
    for event in events:
        identity = (event.tenant_id, event.event_id)
        if identity in _seen:
            continue
        _seen.add(identity)
        ordered.append(event)

    # ### ORDERED BY TIME, NOT BY CORPUS POSITION — the same rule the fold obeys, and found the
    # same way. Handed one chain in two arrival orders, `explain` returned two different answers:
    # `what_happened`, `who_acted`'s evidence and every list field followed the caller's ordering.
    # §8 gives NO global order, so corpus position is an artefact of delivery; an explanation that
    # varies with it is not a reconstruction of history. `occurred_at` is when the fact HAPPENED
    # (§1); `aggregate_version` then `event_id` break ties deterministically, so the answer is a
    # pure function of the SET of facts.
    ordered.sort(key=lambda e: (e.occurred_at, e.aggregate_version, e.event_id))
    if not ordered:
        raise AuditError(
            f"no events for subject {subject!r}: an explanation with no evidence is not an "
            f"explanation. A subject with no facts is a finding to report, not a blank to fill."
        )
    foreign = sorted({e.tenant_id for e in ordered} - {tenant})
    if foreign:
        raise AuditError(
            f"the chain for {subject!r} carries events for tenant(s) {foreign} but the explanation "
            f"is bound to {tenant!r}. [C-1] — an audit never reads across a tenant boundary."
        )

    names = [e.event_name for e in ordered]
    fields: dict[str, Any] = {}

    # --- what happened, and who said so ------------------------------------------------------
    fields["what_happened"] = [
        {"event": e.event_name, "transition": e.producer_transition_id, "occurred_at": e.occurred_at}
        for e in ordered
    ]
    fields["who_acted"] = sorted({f"{e.actor_type}:{e.actor_id}" for e in ordered})
    fields["accountable_owner"] = _pin(ordered, "accountable_owner_id")
    if fields["accountable_owner"] == UNRECONSTRUCTIBLE:
        # An owner declared by the Work Item that opened the chain is the accountable owner for
        # everything the chain did — I1 gives every obligation exactly one.
        owners = [e.payload.get("owner_id") for e in ordered if e.payload.get("owner_id")]
        fields["accountable_owner"] = _last(owners)

    # --- what was known, unknown, conflicted --------------------------------------------------
    # ### KEYED BY AGGREGATE, NOT FLATTENED ACROSS THE CHAIN. A consequential chain spans several
    # aggregates — a grant, an approval, a compensation — and more than one of them declares an
    # `approval_id`. Flattening them into one dict made the last-folded value win, so the
    # explanation reported the COMPENSATION's approval as the effect's approval, and the audit
    # silently disagreed with the rebuild about the same history. Two readings of one corpus that
    # disagree is the failure this whole unit exists to make impossible, so "what was known" is
    # reported per aggregate and folds exactly as `event_replay` folds: by ascending
    # `aggregate_version`, tie-broken by `event_id`.
    known: dict[str, dict[str, Any]] = {}
    by_aggregate: dict[str, list[EventEnvelope]] = {}
    for event in ordered:
        by_aggregate.setdefault(f"{event.aggregate_type}:{event.aggregate_id}", []).append(event)
    for ref, group in by_aggregate.items():
        folded: dict[str, Any] = {}
        seen_ids: set[str] = set()
        for event in sorted(group, key=lambda e: (e.aggregate_version, e.event_id)):
            if event.event_id in seen_ids:          # a redelivered fact is the same fact (§4)
                continue
            seen_ids.add(event.event_id)
            contract = CONTRACTS.get(event.event_name)
            declared = contract.declared_field_names if contract else frozenset()
            for key, value in event.payload.items():
                if key in declared:
                    folded[key] = value
        known[ref] = folded
    fields["what_was_known"] = known

    # ER-6: an `OutcomeUnknown` MUST carry `unknown_reason`, which is what makes AC-AUD-006's
    # "explainable AS an unknown" reconstructible instead of a blank.
    unknowns = _payload_of(ordered, "OutcomeUnknown", "VerificationUnavailable",
                           "VerificationConflict", "ExpectationIndeterminate")
    fields["what_was_unknown"] = [
        {"reason": p.get("unknown_reason", UNRECONSTRUCTIBLE),
         "exposure": p.get("exposure", UNRECONSTRUCTIBLE),
         "coverage_gap": p.get("coverage_gap", UNRECONSTRUCTIBLE)}
        for p in unknowns
    ] or UNRECONSTRUCTIBLE

    conflicts = [e for e in ordered if e.event_name in
                 {"ConflictRaised", "ConflictOpened", "ConflictPartyAttached",
                  "ConflictEscalated", "ConflictResolved", "VerificationConflict"}]
    fields["what_conflicted"] = [
        {"event": e.event_name, "kind": e.payload.get("kind"),
         "field": e.payload.get("field"), "parties": e.payload.get("parties")}
        for e in conflicts
    ] or UNRECONSTRUCTIBLE

    # --- evidence and provenance ---------------------------------------------------------------
    evidence: list[Any] = []
    for event in ordered:
        for ref in (event.evidence_refs or ()):
            if ref not in evidence:
                evidence.append(ref)
        payload_ref = event.payload.get("evidence_ref")
        if payload_ref is not None and payload_ref not in evidence:
            evidence.append(payload_ref)
    fields["what_evidence_existed"] = evidence or UNRECONSTRUCTIBLE

    # ### PROVENANCE AS IT WAS CARRIED — never as it is now, and never strengthened (ER-14, R-P2).
    provenance: list[dict[str, Any]] = []
    for event in ordered:
        carried = event.payload.get("provenance_class")
        if carried is not None:
            provenance.append({"event": event.event_name, "event_id": event.event_id,
                               "provenance_class": carried})
        if event.provenance_refs:
            provenance.append({"event": event.event_name, "event_id": event.event_id,
                               "provenance_refs": dict(event.provenance_refs)})
    fields["provenance_of_material_facts"] = provenance or UNRECONSTRUCTIBLE

    # --- the pins: the decision context, reproduced rather than looked up ----------------------
    fields["entity_versions_pinned"] = _pin(ordered, "entity_versions", subject=subject)
    fields["policy_version_applied"] = _pin(ordered, "policy_version", subject=subject)
    fields["brake_version_applied"] = _pin(ordered, "brake_version", subject=subject)
    fields["material_facts_fingerprint"] = _pin(ordered, "material_facts_fingerprint", subject=subject)

    # --- approval, checkpoint, key, adapter, verification ---------------------------------------
    approvals = [e for e in ordered if e.event_name in
                 {"ApprovalRequested", "ApprovalGranted", "ApprovalDenied", "ApprovalBound",
                  "ApprovalConsumed", "ApprovalVoided", "ApprovalRevoked", "ApprovalExpired",
                  "ApprovalFrozen"}]
    fields["what_approval_existed"] = [
        {"event": e.event_name, "approval_id": e.payload.get("approval_id", UNRECONSTRUCTIBLE),
         "granted_by": e.payload.get("granted_by", UNRECONSTRUCTIBLE),
         "cause": e.payload.get("cause", UNRECONSTRUCTIBLE),
         "frozen": e.payload.get("frozen", UNRECONSTRUCTIBLE)}
        for e in approvals
    ] or UNRECONSTRUCTIBLE

    # ### WHY THE CHECKPOINT PASSED **OR FAILED — WHICH OF THE SEVEN**. `CheckpointFailed` carries
    # `step`(R, 1-7) and `reason`(R) exactly so this question has an answer that is not "it failed".
    checkpoints = [e for e in ordered if e.event_name in {"CheckpointPassed", "CheckpointFailed"}]
    fields["why_the_checkpoint_passed_or_failed"] = [
        {"outcome": e.event_name,
         "checkpoint_id": e.payload.get("checkpoint_id"),
         "step": e.payload.get("step", UNRECONSTRUCTIBLE),
         "reason": e.payload.get("reason", UNRECONSTRUCTIBLE)}
        for e in checkpoints
    ] or UNRECONSTRUCTIBLE

    commit_keys = [p.get("commit_key") for p in
                   _payload_of(ordered, "PipelineStarted", "EffectGranted",
                               "DuplicateProposalAbsorbed")
                   if p.get("commit_key") is not None]
    fields["commit_key_held"] = _last(commit_keys)

    attempts = [e for e in ordered if e.event_name in
                {"EffectAttempted", "EffectExecuted", "EffectFailed", "GrantClaimed",
                 "ClaimRefused", "EffectRecorded"}]
    fields["adapter_operation_ran"] = [
        {"event": e.event_name, "grant_id": e.payload.get("grant_id", UNRECONSTRUCTIBLE),
         "cause": e.payload.get("cause", UNRECONSTRUCTIBLE)}
        for e in attempts
    ] or UNRECONSTRUCTIBLE

    verifications = [e for e in ordered if e.event_name in
                     {"EffectVerified", "VerificationConflict", "VerificationUnavailable",
                      "VerificationDeferred", "RealityEstablished"}]
    fields["what_verification_proved"] = [
        {"event": e.event_name,
         "verification_outcome": e.payload.get("verification_outcome"),
         "health_signal": e.payload.get("health_signal"),
         "matched_fingerprint": e.payload.get("matched_fingerprint"),
         "outcome": e.payload.get("outcome")}
        for e in verifications
    ] or UNRECONSTRUCTIBLE

    # ### CLOSED **OR STAYED OPEN** — the second half is the one that matters operationally, and it
    # is why an absence of a closure event is reported as an open obligation rather than as nothing.
    closures = [e for e in ordered if e.event_name in
                {"WorkItemClosed", "WorkItemCancelled", "PipelineClosed", "Reopened",
                 "WorkBlocked", "WorkEscalated", "ExceptionResolved"}]
    if closures:
        fields["why_the_work_item_closed_or_stayed_open"] = [
            {"event": e.event_name, "decision_ref": e.payload.get("decision_ref"),
             "reason": e.payload.get("reason")}
            for e in closures
        ]
    else:
        fields["why_the_work_item_closed_or_stayed_open"] = {
            "state": "STILL_OPEN",
            "detail": "no closure, cancellation or reopen event exists in this chain",
        }

    missing = [f for f in EIGHTEEN_FIELDS if f not in fields]
    if missing:                                             # pragma: no cover - structural
        raise AuditError(f"explain() failed to answer {missing}; all eighteen are mandatory")

    return Explanation(
        subject=subject, tenant_id=tenant,
        fields={name: fields[name] for name in EIGHTEEN_FIELDS},
        trace=tuple(e.event_id for e in ordered),
        # The latest instant in the chain, not the last position in the corpus — corpus order is
        # arrival order, and an audit's "as of" is a time.
        as_of=max(e.occurred_at for e in ordered),
    )


def chain_for(events: Iterable[EventEnvelope], *, tenant: str, aggregate_type: str,
              aggregate_id: str) -> list[EventEnvelope]:
    """One subject's causal chain, in corpus order — ANCESTORS as well as descendants.

    ### WALKING FORWARD ONLY WAS THE DEFECT, AND IT COST SIX OF THE EIGHTEEN FIELDS. An effect's
    explanation lives mostly in what came BEFORE it: `CheckpointPassed` causes `EffectGranted`,
    `ApprovalGranted` causes `CheckpointPassed`, `WorkItemCreated` opens the whole obligation. A
    descendants-only walk returned an `eg-5501` chain that excluded every one of them, so
    `explain()` answered UNRECONSTRUCTIBLE for "why the checkpoint passed or failed (which of the
    seven)", "the accountable owner" and "what approval existed" — against facts sitting in the
    same corpus, and against a spec whose text is "MUST reconstruct ALL EIGHTEEN". That is not the
    honest-absence case this module argues for; it is a chain assembler that would not fetch them.

    So the walk closes over causation in BOTH directions until it stops growing: an event is in the
    chain if it is on the subject's aggregate, if it caused something in the chain, or if it was
    caused by something in the chain.

    Tenant-partitioned throughout, so the walk can never cross [C-1] — a foreign `causation_id`
    simply does not resolve. Bounded by the corpus size and it breaks as soon as a pass adds
    nothing, so it terminates.
    """
    ordered = [e for e in events if e.tenant_id == tenant]
    roots = [e for e in ordered
             if e.aggregate_type == aggregate_type and e.aggregate_id == aggregate_id]
    if not roots:
        return []
    by_id = {e.event_id: e for e in ordered}
    chain_ids = {e.event_id for e in roots}
    for _ in range(len(ordered)):
        grown: set[str] = set()
        for event in ordered:
            if event.event_id in chain_ids:
                # ANCESTOR: the fact that caused this one is part of why this one happened.
                parent = event.causation_id
                if parent and parent in by_id and parent not in chain_ids:
                    grown.add(parent)
            elif event.causation_id in chain_ids:
                # DESCENDANT: what this chain went on to cause.
                grown.add(event.event_id)
        if not grown:
            break
        chain_ids |= grown
    return [e for e in ordered if e.event_id in chain_ids]
