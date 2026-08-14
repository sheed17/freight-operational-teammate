"""THE sandboxed replay: reconstructing operational truth from canonical facts (P5 U5.4+U5.5).

    Replay reconstructs state by applying events. **It cannot cause an effect — not by
    discipline, but because it cannot construct a `CheckpointPassed` and therefore cannot mint
    an Effect Grant.** The guarantee is a consequence of the capability model. — ADR-008 §2.11

WHY THIS MODULE IMPORTS ALMOST NOTHING, AND WHY THAT IS THE DESIGN

M-27 requires replay to be side-effect free **STRUCTURALLY**. The weak version of that is a module
that carefully does not call an adapter. The strong version — the one this repository's whole
containment architecture is built on — is a module that *cannot*, because the capability is not
reachable from it.

So this module imports the envelope, the contracts, and the standard library. It imports no
adapter, no effect boundary, no checkpoint kernel, no brake store, no `WorkflowStore`, no network
client. `CheckpointPassed` has no public constructor (P3), an Effect Grant can only be minted
inside the seven-step checkpoint, and neither is importable from here — so GR-11's "replay never
creates a Checkpoint Witness, claims an Effect Grant, or causes an external effect" is a property
of the import graph, not of anyone's care. `test_p5_replay_and_audit.py` asserts the closure.

### AND IT WRITES NOTHING, ANYWHERE. `replay()` takes a source and returns a value. There is no
connection parameter, no store, no `commit`, no output table. A reconstruction is a *reading* of
history; the moment it could write, "reconstruct" and "re-execute" would be one edit apart.

WHAT REPLAY RECONSTRUCTS AT P5, STATED PRECISELY

ADR-008 says replay applies events "through the transition tables". ### THE TRANSITION TABLES ARE
P6. The 13 machines and their 134 transitions do not exist yet, and inventing them here would be
building P6 inside P5 under a different name.

What exists at P5 is the canonical event corpus, so what replay reconstructs at P5 is the
**event-level aggregate state**: for each `(tenant, aggregate_type, aggregate_id)`, the ordered
fold of the facts its events declare, at the version each was declared. That is a complete and
honest answer to "what do we know about this aggregate, and how did we come to know it" — and it
is exactly the substrate P6 will apply transition guards *to*, rather than a placeholder for them.

`AggregateState.fields` therefore carries declared payload facts, not entity attributes. When P6
lands, a machine-aware folder consumes this same ordered history; nothing here has to be undone.

THE ORDERING RULE, WHICH IS THE WHOLE OF DETERMINISM

§8: ordering is `(tenant_id, aggregate_id, aggregate_version)` **per aggregate**, and there is
**NO global order**. A fold that sorted the corpus globally — by `occurred_at`, say — would produce
a different answer whenever two aggregates interleaved differently, and "deterministic" would mean
"deterministic on this machine, today".

So the fold is per-aggregate, ordered by `aggregate_version`, and the digest is taken over
aggregates in sorted key order. Two events of ONE aggregate at ONE version are legal (EF-2 emits
`GrantClaimed` and `EffectAttempted` together), and that tie is broken by `event_id` rather than by
arrival — which makes the reconstruction a pure function of the SET of events.

### THAT IS A STRONGER PROPERTY THAN IT LOOKS, AND AN EARLIER VERSION OF THIS MODULE DID NOT HAVE
IT. Folding in arrival order reproduced whichever copy arrived last instead of the one §8 names
("the severity a rebuild reproduces is the one carried by the HIGHEST `aggregate_version`"), so the
same history delivered in a different order — by a relay that leased aggregates differently, or
after a crash and recovery — rebuilt to a different digest. The pinned-digest oracle would then
have been pinning a property of one delivery rather than of the history, which is the whole thing
it exists not to do. A shuffled corpus now yields the identical digest, and the suite shuffles it.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .event_contracts import CanonicalContract, UpcasterRegistry, contract_for
from .event_contracts import read as read_canonical
from .event_contracts import read_against
from .event_envelope import EnvelopeError, EventEnvelope, canonical_json

# The reconstruction format version, INSIDE the hashed bytes — the same discipline as `ev_v1` and
# `fp_v1`. A change to how state is folded MUST change this, or a rebuild digest would silently
# mean something different from the one pinned beside it.
REPLAY_DIGEST_VERSION = "rb_v1"


class ReplayError(RuntimeError):
    """Replay cannot reconstruct what it was asked to reconstruct. It never guesses."""


class ReplayTenantViolation(ReplayError):
    """A corpus handed a replay an event belonging to a different tenant. [C-1]

    Refused rather than filtered: silently skipping a foreign event would make a rebuild's answer
    depend on what happened to be in the source, and a tenant boundary that is enforced by
    filtering is one `if` away from not being enforced.
    """


# --------------------------------------------------------------------------------- the fold

@dataclass(frozen=True)
class ReplayedEvent:
    """One canonical fact as replay saw it, with where it sat in the corpus."""

    sequence: int                 # the corpus's own arrival order — recorded, never inferred
    envelope: EventEnvelope

    @property
    def key(self) -> tuple[str, str, str]:
        return (self.envelope.tenant_id, self.envelope.aggregate_type, self.envelope.aggregate_id)


@dataclass
class AggregateState:
    """The reconstructed state of ONE aggregate: the ordered fold of the facts it declared.

    `fields` holds DECLARED PAYLOAD facts (see the module docstring on what P5 reconstructs), each
    overwritten by the highest `aggregate_version` that declared it — §8's rule for a field-mutating
    fact, which is what makes `ExceptionSeverityChanged` fold to the latest severity rather than to
    whichever copy arrived last.
    """

    tenant_id: str
    aggregate_type: str
    aggregate_id: str
    version: int = 0
    event_count: int = 0
    fields: dict[str, Any] = field(default_factory=dict)
    event_names: list[str] = field(default_factory=list)
    # Every event id folded in, so a rebuild can say WHICH facts produced this state — the
    # substrate `event_audit.explain` reads.
    event_ids: list[str] = field(default_factory=list)

    def as_document(self) -> dict[str, Any]:
        return {
            "tenant_id": self.tenant_id,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "version": self.version,
            "event_count": self.event_count,
            "event_names": list(self.event_names),
            "fields": dict(self.fields),
        }


@dataclass(frozen=True)
class ReplayResult:
    """What one rebuild produced. Every count is derived from folded events, never from intent."""

    aggregates: dict[tuple[str, str, str], AggregateState]
    events_read: int
    events_folded: int
    rejected: tuple[tuple[str, str], ...] = ()      # (event_id, reason)
    tenants: tuple[str, ...] = ()
    duplicates_ignored: int = 0

    # ### THE INERTNESS COUNTERS. AC-EVT-007's oracle is "0 witnesses, 0 grants, 0 adapter calls,
    # 0 real-consumer emissions". These are not decoration: they are reported so the acceptance
    # case asserts a MEASURED zero rather than the absence of an assertion. They are hard-wired to
    # zero because this module has no way to make them anything else — which is the point, and is
    # asserted structurally by the import-closure guard rather than trusted here.
    witnesses_minted: int = 0
    grants_minted: int = 0
    adapter_calls: int = 0
    consumer_emissions: int = 0

    def state_document(self) -> dict[str, Any]:
        """The reconstruction, canonically ordered. Aggregates sorted by key; NO global event order."""
        return {
            "version": REPLAY_DIGEST_VERSION,
            "aggregates": [self.aggregates[k].as_document() for k in sorted(self.aggregates)],
        }

    def digest(self) -> str:
        """`rebuild(corpus) -> D`. The same corpus gives the same D, on every machine, forever."""
        body = canonical_json(self.state_document())
        return hashlib.sha256(f"{REPLAY_DIGEST_VERSION}\n{body}".encode("utf-8")).hexdigest()


# ------------------------------------------------------------------------------- the sandbox

def _fold(state: AggregateState, envelope: EventEnvelope,
          contracts: Mapping[str, CanonicalContract] | None = None) -> None:
    # Resolved against the SAME contract set the read path used. An earlier version resolved
    # through the global registry here while reading through an explicit set, so a rebuild that
    # validated fine then failed at the fold — two contract authorities inside one rebuild.
    contract = (contracts[envelope.event_name] if contracts is not None
                else contract_for(envelope.event_name))
    state.event_count += 1
    state.event_names.append(envelope.event_name)
    state.event_ids.append(envelope.event_id)
    if envelope.aggregate_version > state.version:
        state.version = envelope.aggregate_version
    # Only DECLARED fields are folded. A payload rider from a newer producer is carried through the
    # transport (§6) and is deliberately NOT folded into reconstructed truth: a rebuild must
    # reproduce what the contract says the fact was, not whatever a producer happened to attach.
    declared = contract.declared_field_names
    for name, value in envelope.payload.items():
        if name in declared:
            state.fields[name] = value


def replay(
    events: Iterable[EventEnvelope | Mapping[str, Any]],
    *,
    tenant: str | None = None,
    upcasters: UpcasterRegistry | None = None,
    strict: bool = True,
    contracts: Mapping[str, CanonicalContract] | None = None,
) -> ReplayResult:
    """Reconstruct operational state from canonical facts. Reads only; writes nothing, anywhere.

    `tenant` binds the rebuild to one tenant and REFUSES a foreign event rather than skipping it
    (see `ReplayTenantViolation`). Left `None`, the corpus may span tenants and each is folded into
    its own aggregates — the keys are tenant-first, so two tenants can never share one.

    `contracts` overrides the contract set used to READ history (never to emit it). Left `None` —
    which is every production path — the canonical registry is used.

    `strict` decides what a non-canonical event does. True (the default) RAISES: a corpus is
    history, and history that cannot be read is not something to quietly reconstruct 90% of. False
    records the refusal in `rejected` and continues, which is what a forensic rebuild of a
    known-damaged corpus needs — and it is reported, never silent.

    ### EVERY EVENT IS UPCAST BEFORE IT IS FOLDED (§6, M-25). A rebuild reads historical versions
    through their upcasters, so a v1 fact folds as the current contract defines it. That is the
    whole reason "no historical event may become unreadable because current code changed" is
    testable rather than aspirational.
    """
    aggregates: dict[tuple[str, str, str], AggregateState] = {}
    collected: dict[tuple[str, str, str], list[EventEnvelope]] = {}
    seen_identities: dict[tuple[str, str], str] = {}
    duplicates = 0
    rejected: list[tuple[str, str]] = []
    tenants: list[str] = []
    read = folded = 0

    for sequence, raw in enumerate(events):
        read += 1
        try:
            envelope = raw if isinstance(raw, EventEnvelope) else EventEnvelope.from_document(raw)
        except EnvelopeError as exc:
            if strict:
                raise ReplayError(
                    f"corpus position {sequence} is not a readable envelope: {exc}"
                ) from exc
            rejected.append((f"<position {sequence}>", str(exc)))
            continue

        # [C-1] FIRST, exactly as the inbox does: whose fact this is outranks what it says.
        if tenant is not None and envelope.tenant_id != tenant:
            raise ReplayTenantViolation(
                f"replay is bound to tenant {tenant!r} and the corpus carries an event for "
                f"{envelope.tenant_id!r} (event {envelope.event_id}). A rebuild does not filter a "
                f"foreign fact out of someone else's history; it refuses to run on it."
            )

        try:
            # `contracts` is the reconstruction seam (see `event_contracts.read_against`): it
            # changes what a REBUILD accepts and can never change what may be emitted, because the
            # outbox gate resolves through the canonical registry with no such parameter. It exists
            # so AC-EVT-009's v1→v2→v3 chain can be proven through the REAL replay path without
            # minting a production version the specification does not declare.
            current = (read_against(contracts, envelope, upcasters=upcasters)
                       if contracts is not None
                       else read_canonical(envelope, upcasters=upcasters))
        except EnvelopeError as exc:
            if strict:
                raise ReplayError(
                    f"corpus event {envelope.event_id} is not a canonical fact: {exc}"
                ) from exc
            rejected.append((envelope.event_id, str(exc)))
            continue

        # ### A REDELIVERED FACT IS THE SAME FACT (§4, AC-EVT-004). The outbox re-sends the
        # IDENTICAL row after a crash, so a durable corpus legitimately CONTAINS the same event
        # twice — GC-1 carries one deliberately. An earlier fold appended both, so `event_count`
        # and the folded name list moved and the rebuild digest changed: a duplicate delivery
        # reconstructed a history that never happened. Dedup is on `(tenant, event_id)`, which is
        # §1's dedup identity and the inbox's own key, so the rebuild and the live consumer agree
        # about what "already seen" means.
        identity = (current.tenant_id, current.event_id)
        previous = seen_identities.get(identity)
        if previous is not None:
            # ### DEDUP REQUIRES PROVING IDENTITY, NOT ASSUMING IT. §4's dedup key is
            # `(tenant, event_id)` and §1 says `event_id` is GLOBALLY UNIQUE — so two DIFFERENT
            # bodies under one id is corpus corruption, not a redelivery. Keeping the first
            # silently made the rebuild depend on arrival order again (same set, two orders, two
            # digests) and swallowed the corruption, which is the under-strict inverse of the
            # over-strictness that plagued U5.3. A redelivery is byte-identical by construction;
            # anything else is history this rebuild cannot read.
            if current.digest() == previous:
                duplicates += 1
                continue
            message = (
                f"event_id {current.event_id} appears twice for tenant {current.tenant_id!r} with "
                f"DIFFERENT bodies ({previous[:12]}… vs {current.digest()[:12]}…). §1 makes "
                f"event_id globally unique, so this is not a redelivery — it is a corpus that "
                f"cannot be read."
            )
            if strict:
                raise ReplayError(message)
            rejected.append((current.event_id, message))
            continue
        seen_identities[identity] = current.digest()
        key = (current.tenant_id, current.aggregate_type, current.aggregate_id)
        collected.setdefault(key, []).append(current)
        if current.tenant_id not in tenants:
            tenants.append(current.tenant_id)
        folded += 1

    # ### THE FOLD IS ORDERED BY THE ORDERING KEY, NOT BY ARRIVAL — AND THIS IS WHAT MAKES A
    # REBUILD DETERMINISTIC RATHER THAN MERELY REPEATABLE.
    #
    # §8's ordering key is `(tenant_id, aggregate_id, aggregate_version)`, and §8 spells out what a
    # fold must reproduce: "the severity a rebuild reproduces is the one carried by the HIGHEST
    # `aggregate_version` severity-change event". Folding in arrival order would instead reproduce
    # whichever copy arrived last — so the same corpus, delivered in a different order by a relay
    # that leased aggregates differently, would rebuild to a different digest. The pinned-digest
    # oracle would then be pinning a property of one delivery, not of the history.
    #
    # The tie inside one version is broken by `event_id`, not by arrival: EF-2 legitimately emits
    # `GrantClaimed` and `EffectAttempted` at ONE version, and a tie broken by arrival would make
    # the fold depend on the corpus's order again for exactly those pairs. With this key the
    # reconstruction is a pure function of the SET of events — which is the strongest form of "the
    # same corpus gives the same D", and the one a shuffled corpus cannot break.
    for key, group in collected.items():
        tenant_id, aggregate_type, aggregate_id = key
        state = AggregateState(tenant_id=tenant_id, aggregate_type=aggregate_type,
                               aggregate_id=aggregate_id)
        for envelope in sorted(group, key=lambda e: (e.aggregate_version, e.event_id)):
            _fold(state, envelope, contracts)
        aggregates[key] = state

    return ReplayResult(
        aggregates=aggregates, events_read=read, events_folded=folded,
        rejected=tuple(rejected), tenants=tuple(sorted(tenants)),
        duplicates_ignored=duplicates,
    )


# ------------------------------------------------------------------- reading the durable transport

def from_outbox(conn: Any, *, tenant: str) -> Iterator[EventEnvelope]:
    """The durable transport as a replay source: every emitted event, in its recorded order.

    ### PUBLISHED **AND** PENDING, DELIBERATELY. The outbox is the record of what was EMITTED, and
    an event's delivery state says what the relay managed to do with it — not whether the fact
    happened. Rebuilding only the PUBLISHED rows would make reconstructed truth depend on relay
    progress, so a crash mid-relay would silently rewrite history.

    `sequence` is the per-tenant allocation order the outbox already assigns, so this is the
    corpus's arrival order rather than an order invented here.
    """
    rows = conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE tenant = ? ORDER BY sequence", (tenant,)
    ).fetchall()
    for row in rows:
        yield EventEnvelope.from_json(row["envelope_json"] if not isinstance(row, tuple) else row[0])


# ------------------------------------------------------------------------ divergence (AC-EVT-015)

@dataclass(frozen=True)
class Divergence:
    """One field where the rebuild and the live projection disagree.

    The F14 contract `ProjectionRebuildDiverged` carries exactly `entity_ref`, `field`, `live`,
    `rebuilt` — so this is shaped to it rather than to a convenient debug format.
    """

    entity_ref: str
    field: str
    live: Any
    rebuilt: Any

    def as_payload(self) -> dict[str, Any]:
        return {"entity_ref": self.entity_ref, "field": self.field,
                "live": self.live, "rebuilt": self.rebuilt}


def compare_to_live(result: ReplayResult,
                    live: Mapping[tuple[str, str, str], Mapping[str, Any]]) -> list[Divergence]:
    """Rebuild vs live projection — *"our beliefs are not derivable from our evidence"*.

    ### THIS RETURNS FINDINGS; IT DOES NOT ENGAGE A BRAKE, AND THAT SEPARATION IS DELIBERATE.
    `events/registry.md` §11 requires `ProjectionRebuildDiverged` to auto-engage a tenant brake, and
    the F14 cross-cutting rule requires that REPLAYING a security event never re-engages one — "the
    auto-action fired once, at the original occurrence". A detector that engaged a brake from inside
    a rebuild could not tell those two cases apart. So the finding is returned to a caller that
    knows which it is, exactly as P4's orphan-effect detective sweep returns rather than acts.

    ### NO PRODUCTION CALLER EXISTS YET. Scheduling this and minting the F14 event belong to the
    phase that owns projections (P6+); this is the mechanism, and it ships dark like everything
    else in P5.
    """
    findings: list[Divergence] = []
    for key in sorted(set(live) | set(result.aggregates)):
        entity_ref = ":".join(key)
        rebuilt_fields = result.aggregates[key].fields if key in result.aggregates else {}
        live_fields = live.get(key, {})
        for name in sorted(set(live_fields) | set(rebuilt_fields)):
            live_value = live_fields.get(name)
            rebuilt_value = rebuilt_fields.get(name)
            if live_value != rebuilt_value:
                findings.append(Divergence(entity_ref=entity_ref, field=name,
                                           live=live_value, rebuilt=rebuilt_value))
    return findings


# ------------------------------------------------------------------------------ the golden corpus

def load_corpus(path: Any) -> list[EventEnvelope]:
    """Read a committed corpus fixture. Order is the file's order, which is the corpus's identity."""
    document = json.loads(path.read_text(encoding="utf-8") if hasattr(path, "read_text")
                          else open(path, encoding="utf-8").read())
    return [EventEnvelope.from_document(e) for e in document["events"]]


def corpus_digest(events: Sequence[EventEnvelope]) -> str:
    """The digest of the CORPUS ITSELF — distinct from the digest of what a rebuild produces.

    Two different questions, and conflating them would hide the interesting failure: this one
    changes when the fixture is edited, and `ReplayResult.digest()` changes when the fixture OR the
    fold changes. A build where the corpus digest holds and the rebuild digest moves is a change in
    how history is interpreted, which is precisely the event worth failing on.
    """
    body = canonical_json({"events": [e.as_document() for e in events]})
    return hashlib.sha256(f"gc_v1\n{body}".encode("utf-8")).hexdigest()
