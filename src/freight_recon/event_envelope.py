"""THE canonical event envelope (`docs/specifications/events/registry.md` §1).

    An event records a FACT that occurred. It is NEVER a command, and it NEVER authorizes a
    future action. (events/registry.md, preamble — and CLAUDE.md rule 9.)

This module is the envelope and nothing else: the fields every event carries without exception,
the rules that make two systems serialize the same fact to the same bytes, and the three derived
keys the transport is built on —

    ordering key   `(tenant_id, aggregate_id, aggregate_version)`   per-aggregate; NO global order
    partition key  `tenant_id`                                      the FIRST partition dimension
    dedup key      `(tenant_id, event_id)`                          the inbox's identity

WHAT THIS MODULE IS NOT

It is **not** the 105 event contracts. There is no name whitelist here, no per-event payload
schema, and no upcaster: those are U5.3's, they are enumerated in `events/registry.md` §3, and a
half-version of them written here would be a second authority for the same list. `event_name` is
validated for SHAPE (a non-empty PascalCase identifier) and nothing more. A reviewer looking for
"does `CheckpointPassed` carry the right payload" will not find it here, and should not.

WHY THE SERIALIZATION IS `ev_v1` AND NOT `fp_v1` VERBATIM

§1 pins "the `fp_v1` rules of ADR-005 §3.4 — UTF-8 NFC, bytewise-sorted keys, money as integer
minor units (floats forbidden), null ≠ absent, enums by name". Those RULES are obeyed here
exactly, and this module reuses `fingerprint.Money` so that the money rule is enforced at
construction rather than at serialization.

What is not reused is `fingerprint.canonical_payload`'s *shape*. fp_v1 flattens a fact set to
`key=value` lines and SORTS list members, because for a material fact set — a bag of approved
values — order is not identity. An event payload is not a bag: `ConflictRaised.parties[]` is an
ordered list of objects, and fp_v1 would both reorder it and refuse it (a dict inside a list is
"unserializable"). So `ev_v1` applies the same rules to a JSON document tree: keys bytewise-sorted,
lists in DECLARED order, floats and Decimals refused anywhere, `Money` to its two integer/string
fields, enums by name.

The canonical bytes are `b"ev_v1\\n" + <canonical JSON>`, and the canonical JSON is *valid JSON*.
That is deliberate: the bytes the digest is taken over and the bytes stored in the outbox are the
same bytes, so a redelivery is byte-identical by construction and there is no second serializer to
drift from the first.

FIELDS THAT ARE REQUIRED VERSUS FIELDS THAT ARE NULLABLE

§1 marks fields `R` (required always) or `C` (required-when-applicable, nullable otherwise). Every
`R` field is a keyword argument with NO default, so a caller cannot forget one — including
`causation_id`, which is `R` but legitimately `None` for a root ingress event. Making it
defaultless forces "this is a root event" to be *stated* rather than inferred from a caller's
silence. `C` fields default to `None`/empty.

Within the envelope, a `C` field left `None` means "not applicable" and is OMITTED from the
canonical bytes — that is what "nullable otherwise" means. The `null ≠ absent` rule bites inside
the PAYLOAD, where `{"delivered_at": None}` (we looked, there is no value) and `{}` (we did not
look) are different facts and serialize differently.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import MISSING, dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any

from .fingerprint import Money
from .migrations.phase5_event_transport import STRICT_ORDER_AGGREGATE_TYPES
from .tenant import require_tenant

# The serialization version, INSIDE the hashed bytes so a version confusion cannot produce a
# colliding digest (the same discipline as fp_v1).
ENVELOPE_SERIALIZATION_VERSION = "ev_v1"

# The version of the ENVELOPE ITSELF (§1 `schema_version`), distinct from any event's own
# `event_version`. Bumped only when the envelope's field set changes.
ENVELOPE_SCHEMA_VERSION = 1

# §1 `actor_type`. A `model` actor may only produce claim/proposal events — never OWNER_ASSERTED,
# policy activation, or brake release. That restriction is enforced where those events are minted
# (U5.3 and the machines), not here: this module cannot know which name is a policy activation
# without owning the 105-name registry.
ACTOR_TYPES: frozenset[str] = frozenset({"human", "system", "detector", "model"})

# `STRICT_ORDER_AGGREGATE_TYPES` is imported above rather than restated. It is DEFINED beside the
# partial UNIQUE index that enforces it, because a rule and its enforcement living in two files is
# how "strict per-aggregate ordering" quietly becomes a comment.

# RFC-3339, UTC, EXACTLY millisecond precision, `Z` suffix — the same instant format fp_v1 emits,
# so a timestamp means the same bytes in an event as in a fingerprint.
_INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")
_EVENT_NAME = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_TRANSITION_ID = re.compile(r"^[A-Z]{2}-[0-9]+[a-z]*$")
_AGGREGATE_TYPE = re.compile(r"^[a-z][a-z0-9_]*$")


class EnvelopeError(ValueError):
    """This is not a canonical event. Fail closed — never coerce, never fill in a blank.

    A malformed envelope reaching a handler is the whole attack: the fields being validated here
    are the ones that decide WHOSE data this is, WHICH aggregate it orders against, and WHETHER it
    has already been seen.
    """


class MissingEnvelopeField(EnvelopeError):
    """A field §1 marks required always (`R`) is absent, empty, or blank."""


class MalformedEnvelope(EnvelopeError):
    """A field is present but cannot mean what it claims to mean."""


class UnserializableEvent(EnvelopeError):
    """A payload value has no canonical form. Floats are the common case, and are refused
    everywhere, not only in money: float repr is precision folklore, and folklore is not identity.
    """


def format_instant(value: datetime) -> str:
    """One aware datetime to the canonical RFC-3339 UTC-milliseconds form. Naive input refused."""
    if not isinstance(value, datetime):
        raise MalformedEnvelope(f"expected a datetime, got {type(value).__name__}")
    if value.tzinfo is None:
        raise MalformedEnvelope(
            f"{value!r} is naive; an event instant without a timezone is an instant nobody can "
            f"order against another machine's clock"
        )
    as_utc = value.astimezone(timezone.utc)
    return as_utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{as_utc.microsecond // 1000:03d}Z"


def _require_text(value: object, *, field_name: str) -> str:
    if value is None:
        raise MissingEnvelopeField(f"envelope field {field_name!r} is required and was not supplied")
    if not isinstance(value, str):
        raise MalformedEnvelope(
            f"envelope field {field_name!r} must be a string, got {type(value).__name__}"
        )
    text = value.strip()
    if not text:
        raise MissingEnvelopeField(f"envelope field {field_name!r} is empty or blank")
    return text


def _require_instant(value: object, *, field_name: str) -> str:
    text = _require_text(value, field_name=field_name)
    if not _INSTANT.match(text):
        raise MalformedEnvelope(
            f"envelope field {field_name!r} is {text!r}; the canonical form is RFC-3339 UTC with "
            f"exactly millisecond precision and a Z suffix (e.g. 2026-08-12T09:30:00.000Z)"
        )
    return text


def _require_positive_int(value: object, *, field_name: str, minimum: int = 1) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MalformedEnvelope(
            f"envelope field {field_name!r} must be an integer, got {type(value).__name__}"
        )
    if value < minimum:
        raise MalformedEnvelope(f"envelope field {field_name!r} must be >= {minimum}, got {value}")
    return value


# --------------------------------------------------------------------------------------- ev_v1

def _canonical_key(key: object) -> str:
    if not isinstance(key, str) or not key:
        raise UnserializableEvent(f"object keys must be non-empty strings, got {key!r}")
    return unicodedata.normalize("NFC", key)


def _canonical(value: object, *, path: str) -> str:
    """One value, canonically, as valid JSON text. Raises on anything ambiguous."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Money):
        # Money's own constructor already refused floats and non-ISO-4217 codes; here it becomes
        # the two ordinary JSON fields the registry's "integer minor units" rule describes, so a
        # JSON round-trip through the outbox reproduces identical canonical bytes.
        return _canonical({"amount_minor": value.amount_minor, "currency": value.currency},
                          path=path)
    if isinstance(value, (float, Decimal)):
        raise UnserializableEvent(
            f"{path} is a {type(value).__name__} ({value!r}); floats are forbidden in ev_v1 "
            f"exactly as in fp_v1. Money is integer minor units plus an ISO-4217 code "
            f"(freight_recon.fingerprint.Money)."
        )
    if isinstance(value, Enum):
        return json.dumps(str(value.name).lower(), ensure_ascii=False)
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return json.dumps(unicodedata.normalize("NFC", value), ensure_ascii=False)
    if isinstance(value, datetime):
        return json.dumps(format_instant(value), ensure_ascii=False)
    if isinstance(value, Mapping):
        items = [(_canonical_key(k), v) for k, v in value.items()]
        keys = [k for k, _ in items]
        if len(set(keys)) != len(keys):
            raise UnserializableEvent(f"{path} has keys that collide after NFC normalization")
        # Bytewise-sorted keys (§1 / ADR-005 §3.4) — NOT Python's default str ordering, which is
        # by code point and diverges from UTF-8 byte order above the BMP.
        ordered = sorted(items, key=lambda kv: kv[0].encode("utf-8"))
        body = ",".join(
            f"{json.dumps(k, ensure_ascii=False)}:{_canonical(v, path=f'{path}.{k}')}"
            for k, v in ordered
        )
        return "{" + body + "}"
    if isinstance(value, (list, tuple)):
        # DECLARED order, not sorted. An event payload's list is an ordered fact
        # (`ConflictRaised.parties[]`); reordering it would change what the event says.
        return "[" + ",".join(
            _canonical(v, path=f"{path}[{i}]") for i, v in enumerate(value)
        ) + "]"
    if isinstance(value, (set, frozenset)):
        raise UnserializableEvent(
            f"{path} is a {type(value).__name__}; a set has no declared order, so two runs would "
            f"serialize the same fact to different bytes. State the order: use a list."
        )
    raise UnserializableEvent(f"{path} has unserializable type {type(value).__name__}")


def canonical_json(document: Mapping[str, Any]) -> str:
    """The ev_v1 canonical JSON text of one document. Valid JSON; deterministic; float-free."""
    if not isinstance(document, Mapping):
        raise UnserializableEvent("an event document must be a mapping")
    return _canonical(document, path="$")


# ------------------------------------------------------------------------------- the envelope

@dataclass(frozen=True, kw_only=True)
class EventEnvelope:
    """One canonical event. Frozen: §1 says every envelope field is IMMUTABLE once written.

    Field order below follows `events/registry.md` §1's table, so the two can be read side by side.
    Every `R` field is defaultless; every `C` field defaults to absent.
    """

    # --- R: required always -------------------------------------------------------------------
    event_id: str
    event_name: str
    event_version: int
    occurred_at: str
    recorded_at: str
    tenant_id: str
    aggregate_type: str
    aggregate_id: str
    aggregate_version: int
    causation_id: str | None        # R, but `None` for a root ingress event — state it explicitly
    correlation_id: str
    producer_component: str
    producer_transition_id: str
    actor_type: str
    actor_id: str
    trace_id: str
    payload: Mapping[str, Any]

    # --- R, but derivable ---------------------------------------------------------------------
    # §4: transition-natural for internal events, source-natural for externally-observed ones.
    # Left unset it is DERIVED as the transition-natural identity, which is the correct value for
    # every F1–F13 event; an ingestion path supplies the source-natural one explicitly.
    idempotency_identity: str | None = None

    # --- envelope's own version ---------------------------------------------------------------
    schema_version: int = ENVELOPE_SCHEMA_VERSION

    # --- C: required-when-applicable, nullable otherwise --------------------------------------
    work_item_id: str | None = None
    pipeline_instance_id: str | None = None
    accountable_owner_id: str | None = None
    policy_version: str | None = None
    brake_version: str | None = None
    provenance_refs: Mapping[str, Any] | None = None
    evidence_refs: Sequence[str] | None = None
    observation_refs: Sequence[str] | None = None
    material_facts_fingerprint: str | None = None
    entity_versions: Mapping[str, int] | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "event_id", _require_uuid4(self.event_id))
        object.__setattr__(self, "event_name", _require_event_name(self.event_name))
        object.__setattr__(self, "event_version",
                           _require_positive_int(self.event_version, field_name="event_version"))
        object.__setattr__(self, "schema_version",
                           _require_positive_int(self.schema_version, field_name="schema_version"))
        object.__setattr__(self, "occurred_at",
                           _require_instant(self.occurred_at, field_name="occurred_at"))
        object.__setattr__(self, "recorded_at",
                           _require_instant(self.recorded_at, field_name="recorded_at"))
        if self.recorded_at < self.occurred_at:
            # Lexicographic comparison is chronological for this fixed-width UTC form.
            raise MalformedEnvelope(
                f"recorded_at {self.recorded_at!r} precedes occurred_at {self.occurred_at!r}: "
                f"Neyma cannot have persisted a fact before it happened (§1)"
            )
        # THE tenant gate. `require_tenant` is the repository's one tenant contract — it refuses
        # blanks and every sentinel ("default", "test", ...) that means nobody decided. An event
        # whose tenant is a placeholder is an event that will eventually be read by the wrong
        # brokerage, and §1 marks `tenant_id` MANDATORY on EVERY event with no exception.
        try:
            tenant = require_tenant(self.tenant_id, context="EventEnvelope.tenant_id")
        except ValueError as exc:
            # Re-raised as an EnvelopeError so that EVERY way an envelope can be invalid is one
            # exception family. The inbox refuses malformed events by catching `EnvelopeError`;
            # a tenant failure escaping as a bare ValueError would bypass that refusal and
            # propagate to the caller instead of being recorded as REJECTED_MALFORMED.
            raise MalformedEnvelope(f"tenant_id is not a tenant identity: {exc}") from exc
        object.__setattr__(self, "tenant_id", tenant)
        object.__setattr__(self, "aggregate_type", _require_aggregate_type(self.aggregate_type))
        object.__setattr__(self, "aggregate_id",
                           _require_text(self.aggregate_id, field_name="aggregate_id"))
        object.__setattr__(
            self, "aggregate_version",
            _require_positive_int(self.aggregate_version, field_name="aggregate_version"))
        if self.causation_id is not None:
            object.__setattr__(self, "causation_id",
                               _require_uuid4(self.causation_id, field_name="causation_id"))
        object.__setattr__(self, "correlation_id",
                           _require_text(self.correlation_id, field_name="correlation_id"))
        object.__setattr__(self, "producer_component",
                           _require_text(self.producer_component, field_name="producer_component"))
        object.__setattr__(self, "producer_transition_id",
                           _require_transition_id(self.producer_transition_id))
        actor_type = _require_text(self.actor_type, field_name="actor_type").lower()
        if actor_type not in ACTOR_TYPES:
            raise MalformedEnvelope(
                f"actor_type {self.actor_type!r} is not one of {sorted(ACTOR_TYPES)}; an invented "
                f"actor class is an accountability gap wearing a string"
            )
        object.__setattr__(self, "actor_type", actor_type)
        object.__setattr__(self, "actor_id", _require_text(self.actor_id, field_name="actor_id"))
        object.__setattr__(self, "trace_id", _require_text(self.trace_id, field_name="trace_id"))
        if not isinstance(self.payload, Mapping):
            raise MalformedEnvelope(
                f"payload must be a mapping, got {type(self.payload).__name__}; an event body is a "
                f"named set of facts, never a bare value"
            )
        if self.entity_versions is not None and not isinstance(self.entity_versions, Mapping):
            raise MalformedEnvelope("entity_versions must be a mapping of entity ref -> version")
        if self.idempotency_identity is None:
            object.__setattr__(self, "idempotency_identity", self.transition_natural_identity())
        else:
            object.__setattr__(
                self, "idempotency_identity",
                _require_text(self.idempotency_identity, field_name="idempotency_identity"))
        # Serialize once, here: an envelope that cannot be canonically serialized is not a
        # canonical event, and finding that out at publish time would mean a transition already
        # committed against an event that can never be sent.
        canonical_json(self.as_document())

    # --- the three derived keys of §1 / §8 ----------------------------------------------------

    @property
    def ordering_key(self) -> tuple[str, str, int]:
        """`(tenant_id, aggregate_id, aggregate_version)` — per-aggregate. NO global order (§8)."""
        return (self.tenant_id, self.aggregate_id, self.aggregate_version)

    @property
    def partition_key(self) -> str:
        """`tenant_id` — the FIRST partition dimension of every store, stream and inbox [C-1]."""
        return self.tenant_id

    @property
    def dedup_key(self) -> tuple[str, str]:
        """`(tenant_id, event_id)` — §1's dedup identity, and the inbox's key with `consumer_id`."""
        return (self.tenant_id, self.event_id)

    @property
    def requires_strict_order(self) -> bool:
        """True for F2/F3/F4/F11/F13 aggregates, whose transitions are version-monotonic (§8)."""
        return self.aggregate_type in STRICT_ORDER_AGGREGATE_TYPES

    def transition_natural_identity(self) -> str:
        """§4's identity for an internally-emitted event.

        The registry writes it `(tenant_id, aggregate_id, aggregate_version,
        producer_transition_id)`. `event_name` is appended here, and the reason is worth stating:
        §11.4 says "the state transition and the EVENTS it emits", plural, so one transition may
        put more than one contract in its commit. Without the name those rows would collide on a
        key the registry calls an identity, and a UNIQUE constraint over a colliding key is a
        constraint that has to be dropped the first time it is right.
        """
        return "|".join((
            "tn_v1", self.tenant_id, self.aggregate_type, self.aggregate_id,
            str(self.aggregate_version), self.producer_transition_id, self.event_name,
        ))

    # --- serialization ------------------------------------------------------------------------

    def as_document(self) -> dict[str, Any]:
        """The envelope as a plain document. `C` fields left unset are OMITTED (§1 "nullable")."""
        document: dict[str, Any] = {
            "event_id": self.event_id,
            "event_name": self.event_name,
            "event_version": self.event_version,
            "schema_version": self.schema_version,
            "occurred_at": self.occurred_at,
            "recorded_at": self.recorded_at,
            "tenant_id": self.tenant_id,
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "aggregate_version": self.aggregate_version,
            "causation_id": self.causation_id,
            "correlation_id": self.correlation_id,
            "producer_component": self.producer_component,
            "producer_transition_id": self.producer_transition_id,
            "actor_type": self.actor_type,
            "actor_id": self.actor_id,
            "trace_id": self.trace_id,
            "idempotency_identity": self.idempotency_identity,
            "payload": dict(self.payload),
        }
        optional = {
            "work_item_id": self.work_item_id,
            "pipeline_instance_id": self.pipeline_instance_id,
            "accountable_owner_id": self.accountable_owner_id,
            "policy_version": self.policy_version,
            "brake_version": self.brake_version,
            "provenance_refs": self.provenance_refs,
            "evidence_refs": self.evidence_refs,
            "observation_refs": self.observation_refs,
            "material_facts_fingerprint": self.material_facts_fingerprint,
            "entity_versions": self.entity_versions,
            "metadata": self.metadata,
        }
        for name, value in optional.items():
            if value is not None:
                document[name] = value
        return document

    def canonical_bytes(self) -> bytes:
        """`ev_v1\\n` + the canonical JSON. The version lives INSIDE the hashed bytes."""
        return (
            f"{ENVELOPE_SERIALIZATION_VERSION}\n{canonical_json(self.as_document())}"
        ).encode("utf-8")

    def digest(self) -> str:
        """SHA-256 over the canonical bytes. Two systems, same fact, same digest."""
        return hashlib.sha256(self.canonical_bytes()).hexdigest()

    def to_json(self) -> str:
        """The durable form written to the outbox — the same canonical bytes, minus the prefix."""
        return canonical_json(self.as_document())

    @classmethod
    def from_json(cls, text: str) -> "EventEnvelope":
        """Rehydrate. Round-trips the DIGEST exactly, which is the property that matters:
        `Money` degrades to its two fields and a `datetime` to its canonical string, and both
        serialize to the identical bytes they did before.
        """
        try:
            document = json.loads(text)
        except (TypeError, ValueError) as exc:
            raise MalformedEnvelope(f"stored envelope is not JSON: {exc}") from exc
        return cls.from_document(document)

    @classmethod
    def from_document(cls, document: object) -> "EventEnvelope":
        """Build from an untrusted mapping. Unknown keys are a REFUSAL, not a shrug.

        An envelope carrying a field this code does not know is either a newer schema version this
        binary must not guess at, or an injection. Both are refusals — silently dropping the
        unknown key is how a `provenance_class: OWNER_ASSERTED` rider gets to travel unnoticed.
        """
        if not isinstance(document, Mapping):
            raise MalformedEnvelope(
                f"an event envelope must be a mapping, got {type(document).__name__}"
            )
        known = {f for f in cls.__dataclass_fields__}
        supplied = set(document.keys())
        unknown = sorted(supplied - known)
        if unknown:
            raise MalformedEnvelope(
                f"envelope carries field(s) this code does not define: {unknown}. Either it was "
                f"written by a newer schema version — which must be upcast, not guessed at — or "
                f"something appended a rider to a fact."
            )
        missing = sorted(
            name for name, f in cls.__dataclass_fields__.items()
            if f.default is MISSING and f.default_factory is MISSING and name not in supplied
        )
        if missing:
            raise MissingEnvelopeField(
                f"envelope is missing required field(s) {missing} (events/registry.md §1)"
            )
        return cls(**document)


def _require_uuid4(value: object, *, field_name: str = "event_id") -> str:
    text = _require_text(value, field_name=field_name)
    try:
        parsed = uuid.UUID(text)
    except (ValueError, AttributeError, TypeError) as exc:
        raise MalformedEnvelope(
            f"envelope field {field_name!r} is {text!r}, which is not a UUID: {exc}"
        ) from exc
    if parsed.version != 4:
        raise MalformedEnvelope(
            f"envelope field {field_name!r} is a UUID v{parsed.version}; §1 requires v4. A v1 "
            f"UUID leaks a MAC address and a timestamp into an id that crosses tenants."
        )
    return str(parsed)


def _require_event_name(value: object) -> str:
    text = _require_text(value, field_name="event_name")
    if not _EVENT_NAME.match(text):
        raise MalformedEnvelope(
            f"event_name {text!r} is not a canonical name: §3 names are PascalCase identifiers "
            f"(e.g. CheckpointPassed). NOTE: whether the name is one of the canonical 105 is NOT "
            f"checked here — that registry is U5.3's."
        )
    return text


def _require_aggregate_type(value: object) -> str:
    text = _require_text(value, field_name="aggregate_type")
    if not _AGGREGATE_TYPE.match(text):
        raise MalformedEnvelope(
            f"aggregate_type {text!r} is not a canonical entity slug (lower_snake_case, e.g. "
            f"work_item, effect_grant)"
        )
    return text


def _require_transition_id(value: object) -> str:
    text = _require_text(value, field_name="producer_transition_id")
    if not _TRANSITION_ID.match(text):
        raise MalformedEnvelope(
            f"producer_transition_id {text!r} is not a state-machine transition id (e.g. PL-8, "
            f"EF-2r, WI-1). §1 calls this the mechanical link to the state machine; a free-text "
            f"value breaks that link silently."
        )
    return text
