#!/usr/bin/env python3
"""Build `GC-1`, the immutable golden corpus, and pin its digests (P5 U5.4).

    THE CORPUS ORACLE: `rebuild(GC-1) -> digest D`. D is pinned in the repo. Every build, every
    version, forever: the SAME D. A changed digest is a FAILING build until a human explains
    why — a rebuild that "looks right" is not a pass.
        — docs/specifications/acceptance/event-and-replay-acceptance.md

WHAT GC-1 MUST SPAN, AND WHAT IT ACTUALLY SPANS

The acceptance spec requires: >=1 schema version change - >=2 tenants - >=1 correction (+ its
propagation) - >=1 UNKNOWN_OUTCOME - >=1 compensation - >=1 brake episode - >=1 parked dangling
reference - >=1 duplicate delivery.

Seven of the eight are built here from real canonical contracts. The eighth is NOT, and the reason
is recorded rather than papered over:

### THE SCHEMA VERSION CHANGE IS DEFERRED BY DEPENDENCY. Every one of the 118 canonical contracts
is at `v1` - `events/registry.md` sec 2 field 3 sets the default and no contract overrides it. A
schema version change requires a BREAKING change to a canonical contract plus a registered
upcaster (sec 6), and minting one is a specification amendment under founder/architect authority,
exactly as the 98 -> 105 event mint was. Fabricating a `v2` here to make this fixture look complete
would put a version in the golden corpus that the specification does not declare - a false green in
the one artifact whose whole job is to be trustworthy forever.

The machinery it would exercise EXISTS and is proven: `event_contracts.UpcasterRegistry` chains
`vN->vN+1` deterministically, refuses a missing link and refuses an unsupported future version,
tested against a synthetic contract set in `test_p5_event_contracts.py`. The day a real `v2` is
minted, this builder gains the span and `AC-EVT-009` becomes executable. Until then it is recorded
open, and `test_p5_replay_and_audit.py` asserts the deferral is REAL - that every contract is still
v1 - so this note cannot outlive its own truth.

WHY A BUILDER AND NOT A HAND-WRITTEN JSON BLOB

The corpus is committed as JSON and is the fixture of record. This script is how it is DERIVED, so
that every event in it is a genuinely canonical fact - constructed through `EventEnvelope` and
validated against its contract by `event_contracts.validate` before it is written. A hand-written
corpus would be exactly the thing U5.3 spent three reviews proving nobody should trust: a set of
event-shaped documents nobody checked.

    python3 scripts/build_gc1_corpus.py            # rebuild the corpus and re-pin the digests
    python3 scripts/build_gc1_corpus.py --check    # exit 1 if committed corpus or digests are stale

### RE-PINNING IS AN EXPLICIT HUMAN ACT. `--check` is what CI runs. Running this script without
`--check` rewrites the pinned digest, which is precisely the act the acceptance oracle says a human
must explain - so it is never automatic and never invoked by a test.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from freight_recon.event_contracts import (  # noqa: E402
    CONTRACTS,
    ValidationMode,
    contract_for,
    validate,
)
from freight_recon.event_envelope import EventEnvelope, format_instant  # noqa: E402
from freight_recon.event_replay import corpus_digest, replay  # noqa: E402

CORPUS_PATH = ROOT / "eval" / "fixtures" / "gc1-corpus.json"
PIN_PATH = ROOT / "eval" / "fixtures" / "gc1-pinned-digests.json"

# Two tenants (>=2 required). Real-shaped brokerage ids, never a sentinel - `require_tenant`
# refuses "default"/"test" and an event whose tenant is a placeholder is an event that will
# eventually be read by the wrong brokerage.
TENANT_A = "brokerage-northwind"
TENANT_B = "brokerage-cascade"

# A fixed epoch. ### NOTHING HERE MAY READ THE WALL CLOCK: a corpus whose timestamps moved would
# produce a new digest on every build, and the pinned-digest oracle would be untestable.
EPOCH = datetime(2026, 5, 1, 9, 0, 0, tzinfo=timezone.utc)


def deterministic_uuid(seed: str) -> str:
    """A reproducible, genuinely v4-shaped UUID. sec 1 requires v4; a fixture requires determinism."""
    raw = bytearray(hashlib.sha256(f"gc1|{seed}".encode("utf-8")).digest()[:16])
    raw[6] = (raw[6] & 0x0F) | 0x40
    raw[8] = (raw[8] & 0x3F) | 0x80
    return str(uuid.UUID(bytes=bytes(raw)))


class CorpusBuilder:
    """Accumulates canonical events in arrival order, validating each against its contract."""

    def __init__(self) -> None:
        self.events: list[EventEnvelope] = []
        self._minute = 0

    def _instant(self) -> str:
        self._minute += 1
        return format_instant(EPOCH + timedelta(minutes=self._minute))

    def emit(
        self,
        *,
        tenant: str,
        name: str,
        aggregate_id: str,
        aggregate_version: int,
        payload: dict,
        seed: str,
        causation: str | None = None,
        correlation: str = "corr-gc1",
        actor_type: str | None = None,
        actor_id: str | None = None,
        transition: str | None = None,
        work_item_id: str | None = None,
        **envelope_extras: object,
    ) -> EventEnvelope:
        contract = contract_for(name)
        when = self._instant()
        fields: dict = {
            "event_id": deterministic_uuid(seed),
            "event_name": name,
            "event_version": contract.current_version,
            "occurred_at": when,
            "recorded_at": when,
            "tenant_id": tenant,
            "aggregate_type": contract.aggregate_type or "work_item",
            "aggregate_id": aggregate_id,
            "aggregate_version": aggregate_version,
            "causation_id": causation,
            "correlation_id": correlation,
            "producer_component": f"m-{contract.family.lower()}",
            "producer_transition_id": transition or (contract.producers[0] if contract.producers
                                                     else "GR-1"),
            "actor_type": actor_type or ("human" if contract.human_only else "system"),
            "actor_id": actor_id or ("ops-lead-1" if contract.human_only else "system"),
            "trace_id": f"trace-{seed}",
            "payload": payload,
        }
        if work_item_id:
            fields["work_item_id"] = work_item_id
        if contract.consequential and not contract.consequential_conditional:
            fields.setdefault("entity_versions", {f"{fields['aggregate_type']}:{aggregate_id}": 1})
            fields.setdefault("policy_version", "policy-2026-04")
            fields.setdefault("brake_version", "brake-7")
        fields.update(envelope_extras)
        envelope = EventEnvelope(**fields)
        # ### VALIDATED AS A PRODUCER WOULD BE. A golden corpus containing a fact that the runtime
        # would refuse to emit is a fixture that tests the wrong system.
        validate(envelope, mode=ValidationMode.PRODUCER)
        self.events.append(envelope)
        return envelope


def build() -> list[EventEnvelope]:
    """The corpus. Each block below is one of the spans the acceptance spec requires."""
    b = CorpusBuilder()

    # --- TENANT A: a consequential chain, ending in an UNKNOWN_OUTCOME and a compensation -------
    wi = "wi-4401"
    created = b.emit(tenant=TENANT_A, name="WorkItemCreated", aggregate_id=wi, aggregate_version=1,
                     seed="a-wi-created", work_item_id=wi,
                     payload={"owner_id": "dispatcher-amy", "type": "carrier_invoice_review"},
                     accountable_owner_id="dispatcher-amy")
    started = b.emit(tenant=TENANT_A, name="PipelineStarted", aggregate_id="pi-9001",
                     aggregate_version=1, seed="a-pipeline", causation=created.event_id,
                     work_item_id=wi, payload={"commit_key": "ck-gc1-0001"})
    b.emit(tenant=TENANT_A, name="PolicyEvaluated", aggregate_id="pi-9001", aggregate_version=2,
           seed="a-policy-eval", causation=started.event_id, work_item_id=wi,
           payload={"policy_version": "policy-2026-04", "gate_decision": "HUMAN_APPROVAL_REQUIRED",
                    "decision": "gate", "rules_matched": ["rule-amount-cap"],
                    "reason": "amount above autonomous cap"})
    requested = b.emit(tenant=TENANT_A, name="ApprovalRequested", aggregate_id="ap-3301",
                       aggregate_version=1, seed="a-appr-req", causation=started.event_id,
                       work_item_id=wi,
                       payload={"fingerprint": "fp_v1:aa11", "gate_decision": "HUMAN_APPROVAL_REQUIRED",
                                "rendered_facts": {"amount_minor": 128450, "currency": "USD"},
                                "expires_at": "2026-05-02T09:00:00.000Z"},
                       material_facts_fingerprint="fp_v1:aa11")
    granted = b.emit(tenant=TENANT_A, name="ApprovalGranted", aggregate_id="ap-3301",
                     aggregate_version=2, seed="a-appr-granted", causation=requested.event_id,
                     work_item_id=wi, actor_type="human", actor_id="controller-dana",
                     payload={"granted_by": "controller-dana"},
                     material_facts_fingerprint="fp_v1:aa11")
    passed = b.emit(tenant=TENANT_A, name="CheckpointPassed", aggregate_id="pi-9001",
                    aggregate_version=3, seed="a-checkpoint", causation=granted.event_id,
                    work_item_id=wi,
                    evidence_refs=["sha256:c0ffee11deadbeef22c0ffee33deadbeef44c0ffee55deadbe"],
                    payload={"checkpoint_id": "cp-7701", "material_facts_fingerprint": "fp_v1:aa11",
                             "entity_versions": {"work_item:wi-4401": 1, "load:ld-560003": 4},
                             "policy_version": "policy-2026-04", "brake_version": "brake-7",
                             "approval_id": "ap-3301",
                             "projected_observations_used": ["obs-2201"],
                             "native_claims_used": ["ib-1101"]},
                    material_facts_fingerprint="fp_v1:aa11")
    grant = b.emit(tenant=TENANT_A, name="EffectGranted", aggregate_id="eg-5501",
                   aggregate_version=1, seed="a-grant", causation=passed.event_id, work_item_id=wi,
                   payload={"grant_id": "eg-5501", "checkpoint_id": "cp-7701",
                            "commit_key": "ck-gc1-0001",
                            "material_facts_fingerprint": "fp_v1:aa11",
                            "entity_versions": {"work_item:wi-4401": 1},
                            "policy_version": "policy-2026-04", "brake_version": "brake-7",
                            "approval_id": "ap-3301",
                            "expires_at": "2026-05-01T10:00:00.000Z"},
                   material_facts_fingerprint="fp_v1:aa11")
    claimed = b.emit(tenant=TENANT_A, name="GrantClaimed", aggregate_id="eg-5501",
                     aggregate_version=2, seed="a-claimed", causation=grant.event_id,
                     work_item_id=wi, payload={"grant_id": "eg-5501"},
                     material_facts_fingerprint="fp_v1:aa11")
    # EF-2 legitimately emits GrantClaimed AND EffectAttempted on ONE aggregate at ONE version -
    # the case a UNIQUE index would have made uninsertable (the U5.7/U5.8 build found that).
    attempted = b.emit(tenant=TENANT_A, name="EffectAttempted", aggregate_id="eg-5501",
                       aggregate_version=2, seed="a-attempted", causation=claimed.event_id,
                       work_item_id=wi, payload={"grant_id": "eg-5501"},
                       material_facts_fingerprint="fp_v1:aa11")

    # >=1 UNKNOWN_OUTCOME. ER-6: it MUST carry `unknown_reason`, which is what makes AC-AUD-006's
    # "explainable AS an unknown" reconstructible at all.
    unknown = b.emit(tenant=TENANT_A, name="OutcomeUnknown", aggregate_id="eg-5501",
                     aggregate_version=3, seed="a-unknown", causation=attempted.event_id,
                     work_item_id=wi, transition="EF-3u",
                     payload={"exposure": {"amount_minor": 128450, "currency": "USD"},
                              "unknown_reason": "UNKNOWN_OUTCOME"},
                     material_facts_fingerprint="fp_v1:aa11")
    # AP-9: the freeze is an EMITTED fact, never derived from an absence (ER-16).
    b.emit(tenant=TENANT_A, name="ApprovalFrozen", aggregate_id="ap-3301", aggregate_version=3,
           seed="a-frozen", causation=unknown.event_id, work_item_id=wi,
           payload={"frozen": True, "unknown_outcome_ref": unknown.event_id,
                    "effect_grant_id": "eg-5501", "frozen_at": "2026-05-01T09:12:00.000Z"})

    # >=1 compensation.
    comp = b.emit(tenant=TENANT_A, name="CompensationRequired", aggregate_id="cm-6601",
                  aggregate_version=1, seed="a-comp-req", causation=unknown.event_id,
                  work_item_id=wi,
                  payload={"original_effect_id": "eg-5501",
                           "exposure": {"amount_minor": 128450, "currency": "USD"},
                           "reason": "unknown outcome on a payable write",
                           "decision_ref": "dec-9901"})
    b.emit(tenant=TENANT_A, name="CompensationApproved", aggregate_id="cm-6601",
           aggregate_version=2, seed="a-comp-appr", causation=comp.event_id, work_item_id=wi,
           payload={"approval_id": "ap-3302"})

    # >=1 brake episode. BR-1 may be engaged by automation (ER-12 permits narrowing authority);
    # BR-4's release is `actor_type=human` ONLY, and the corpus exercises both halves.
    engaged = b.emit(tenant=TENANT_A, name="BrakeEngaged", aggregate_id="br-01",
                     aggregate_version=1, seed="a-brake-on",
                     payload={"scope": {"tenant": TENANT_A, "action_class": "invoice_write"},
                              "actor": "detector-unknown-outcome",
                              "reason": "unresolved UNKNOWN_OUTCOME on a payable",
                              "brake_version": "brake-8"})
    b.emit(tenant=TENANT_A, name="BrakeReleased", aggregate_id="br-01", aggregate_version=2,
           seed="a-brake-off", causation=engaged.event_id,
           actor_type="human", actor_id="controller-dana",
           payload={"released_by": "controller-dana", "release_decision_ref": "dec-9902",
                    "brake_version": "brake-9"})

    # --- TENANT B: a correction and its propagation, and the dangling reference -----------------
    proposed = b.emit(tenant=TENANT_B, name="ClaimProposed", aggregate_id="ib-2201",
                      aggregate_version=1, seed="b-claim-proposed",
                      actor_type="model", actor_id="linker-v3",
                      payload={"provenance_class": "LINKER_INFERRED", "subject_ref": "obs-7701",
                               "entity_ref": "load:ld-880012", "match_method": "reference_exact"},
                     # sec 1 marks `provenance_refs` required-when-applicable for "any claim/value
                     # carried", and `evidence_refs` content-addressed. A corpus with neither made
                     # AC-AUD-004's evidence traversal untestable and left two audit fields
                     # permanently UNRECONSTRUCTIBLE for every chain.
                     provenance_refs={"provenance_class": "LINKER_INFERRED",
                                      "lineage": ["obs-7701"]},
                     evidence_refs=["sha256:8f1c2d3e4a5b6c7d8e9f0a1b2c3d4e5f"])
    confirmed = b.emit(tenant=TENANT_B, name="ClaimConfirmed", aggregate_id="ib-2201",
                       aggregate_version=2, seed="b-claim-confirmed", causation=proposed.event_id,
                       payload={"provenance_class": "LINKER_INFERRED", "rule_id": "rule-ref-exact"},
                       provenance_refs={"provenance_class": "LINKER_INFERRED",
                                        "lineage": ["obs-7701", proposed.event_id]},
                       evidence_refs=["sha256:8f1c2d3e4a5b6c7d8e9f0a1b2c3d4e5f"])
    # >=1 CORRECTION + its PROPAGATION. IB-7 fixes `provenance_class=OWNER_ASSERTED`, so ER-10
    # requires an authenticated human - a machine actor here would be the laundering it forbids.
    corrected = b.emit(tenant=TENANT_B, name="ClaimCorrected", aggregate_id="ib-2201",
                       aggregate_version=3, seed="b-claim-corrected", causation=confirmed.event_id,
                       actor_type="human", actor_id="ops-manager-lee",
                       payload={"decision_ref": "dec-7702", "prior": "load:ld-880012",
                                "new": "load:ld-880099", "provenance_class": "OWNER_ASSERTED"})
    # The propagation: the correction invalidates downstream work.
    b.emit(tenant=TENANT_B, name="ExceptionRaised", aggregate_id="ec-3301", aggregate_version=1,
           seed="b-exception", causation=corrected.event_id,
           payload={"severity": "SEV2", "source_ref": corrected.event_id,
                    "specific_question": "re-bind the payable to load ld-880099?"})

    # >=1 PARKED DANGLING REFERENCE: an event naming an aggregate the corpus creates LATER, so a
    # rebuild must tolerate it (M-26 parks it in the live inbox; a rebuild folds it in order).
    b.emit(tenant=TENANT_B, name="ObservationBound", aggregate_id="obs-7702", aggregate_version=1,
           seed="b-obs-bound", transition="OB-3",
           payload={"provenance_class": "RECONCILED", "bound_entity_ref": "work_item:wi-8899",
                    "binding_claim_id": "ib-2202"},
           entity_versions={"work_item:wi-8899": 1})
    b.emit(tenant=TENANT_B, name="WorkItemCreated", aggregate_id="wi-8899", aggregate_version=1,
           seed="b-late-wi", payload={"owner_id": "dispatcher-raj", "type": "appointment_followup"},
           accountable_owner_id="dispatcher-raj")

    return b.events


def duplicate_delivery(events: list[EventEnvelope]) -> list[EventEnvelope]:
    """>=1 DUPLICATE DELIVERY, appended byte-identically.

    ### THE SAME `event_id`, NOT A COPY WITH A NEW ONE. sec 4: an outbox retry re-sends the
    IDENTICAL row, so the duplicate a corpus must contain is the same fact arriving twice. A
    rebuild MUST fold it to the same state - which is the property `AC-EVT-004` names and the
    reason the digest is worth pinning.
    """
    return [*events, events[7]]


def render_corpus(events: list[EventEnvelope]) -> str:
    return json.dumps(
        {
            "_corpus": "GC-1",
            "_authority": "docs/specifications/acceptance/event-and-replay-acceptance.md",
            "_immutable": (
                "GC-1 is an immutable fixture and is NEVER reset between replay tests. Editing it "
                "changes the pinned digests, which is a FAILING build until a human explains why."
            ),
            "_spans": {
                "tenants": 2,
                "correction_and_propagation": True,
                "unknown_outcome": True,
                "compensation": True,
                "brake_episode": True,
                "parked_dangling_reference": True,
                "duplicate_delivery": True,
                "schema_version_change": False,
            },
            "_schema_version_change": (
                "NOT SPANNED BY GC-1, AND PROVEN ELSEWHERE. Every one of the 118 canonical "
                "contracts is at v1: a schema version change requires a breaking change to a "
                "canonical contract plus a registered upcaster (events/registry.md sec 6), which "
                "is a specification amendment under founder/architect authority - the same "
                "authority that minted 98 -> 105. Minting one to satisfy a fixture would put a "
                "version in the golden corpus that the specification does not declare. "
                "### AC-EVT-009 (v1+v2+v3 in one corpus, one digest, run twice identical) IS "
                "SATISFIED, through the real replay path, by the TEST-ONLY versioned fixture in "
                "eval/tests/test_p5_replay_and_audit.py section 8 - neither the oracle nor the "
                "span requires the versioned contract to be one of the 105, and GC-1 is kept "
                "purely canonical because that is what makes IT trustworthy. GC-1 gains the span "
                "inline the day a real v2 exists."
            ),
            "events": [e.as_document() for e in events],
        },
        indent=2, ensure_ascii=False,
    ) + "\n"


def render_pins(events: list[EventEnvelope]) -> str:
    result = replay(events)
    return json.dumps(
        {
            "_oracle": (
                "rebuild(GC-1) -> D. D is pinned here. Every build, every version, forever: the "
                "SAME D. A changed digest is a FAILING build until a human explains why."
            ),
            "corpus_digest": corpus_digest(events),
            "rebuild_digest": result.digest(),
            "event_count": len(events),
            "aggregate_count": len(result.aggregates),
            "tenants": list(result.tenants),
        },
        indent=2, ensure_ascii=False,
    ) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if the committed corpus or pinned digests are stale")
    args = parser.parse_args()

    events = duplicate_delivery(build())
    corpus, pins = render_corpus(events), render_pins(events)

    if args.check:
        stale = []
        for path, rendered in ((CORPUS_PATH, corpus), (PIN_PATH, pins)):
            current = path.read_text(encoding="utf-8") if path.exists() else ""
            if current != rendered:
                stale.append(str(path.relative_to(ROOT)))
        if stale:
            print(f"STALE: {stale}")
            return 1
        print("current: GC-1 corpus and pinned digests match the builder")
        return 0

    CORPUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    CORPUS_PATH.write_text(corpus, encoding="utf-8")
    PIN_PATH.write_text(pins, encoding="utf-8")
    result = replay(events)
    print(f"wrote {CORPUS_PATH.relative_to(ROOT)}: {len(events)} events, "
          f"{len(result.aggregates)} aggregates, tenants={list(result.tenants)}")
    print(f"wrote {PIN_PATH.relative_to(ROOT)}: rebuild_digest={result.digest()[:16]}...")
    print("### the pinned digest CHANGED if this rewrote it - explain why, or restore it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
