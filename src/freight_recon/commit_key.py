"""The canonical Commit Key: the identity of ONE logical external effect.

THE RULE (ADR-009): the Commit Key identifies the EFFECT, never the CONTENT of the decision.

    Commit Key answers:            "Is this the same logical effect?"
    Material decision content answers: "Are the facts and approved values still identical?"

Those are different questions and they must never share a field. The defect this module replaces
answered the first question with the second: `approved_amount` was part of the commit identity, so
approving GBP 2,850 and then GBP 3,100 for the same invoice produced two different identities, two
reservations, and TWO INVOICES. The amount is not who the effect is; it is what the effect says.

The amount is not a parameter of anything here. It cannot be passed in, so it cannot be included
by mistake, and no future edit can add it without changing a frozen dataclass that the guards watch.

The amount is NOT discarded: it travels as material facts, separately, where drift can invalidate an
approval without ever splitting the effect's identity.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

# Bump only if the derivation itself changes. Every stored key is prefixed, so a future version can
# be told apart from this one without guessing.
KEY_VERSION = "ck_v1"


class UnidentifiableEffect(ValueError):
    """A consequential effect whose logical identity cannot be determined.

    Raised, never swallowed. The caller must fail closed: escalate to a human. It must NOT invent a
    discriminator, and it must NOT fall back to None, a UUID, a request id, a timestamp, an approval
    id, a retry counter, or a hash of the mutable payload. Every one of those is attempt-scoped, and
    an attempt-scoped identity makes every retry a NEW logical effect - which is the double-pay bug
    with extra steps.
    """


def _norm(value: str, *, field: str) -> str:
    text = str(value or "").strip().lower()
    if not text:
        raise UnidentifiableEffect(f"commit key field {field!r} is empty; refusing to mint an identity")
    return text


@dataclass(frozen=True)
class LogicalEffect:
    """The stable identity of one logical external effect. Nothing mutable may appear here.

    Frozen and exactly six fields, deliberately: the shape IS the contract. Adding `approved_amount`
    to a Commit Key now requires editing this dataclass, which fails a structural guard.
    """

    tenant: str             # WHO. Two tenants may hold the same external id and must never collide.
    action_class: str       # WHAT KIND of effect (raise_invoice, file_document, ...).
    target_system: str      # WHICH external system holds the truth.
    target_resource_id: str # WHICH business subject (the load / invoice reference).
    target_operation: str   # WHICH operation on it.
    occurrence_key: str     # WHICH legitimate repetition. "" when repetition is not legitimate.

    def key(self) -> str:
        return commit_key(self)


def commit_key(effect: LogicalEffect) -> str:
    """SHA256 over the canonical logical-effect identity.

    Field order is fixed and each field is normalised and separated, so payload-field ordering,
    casing and surrounding whitespace cannot change the identity of the same logical effect.
    `occurrence_key` may be empty (repetition not legitimate); every other field must be present.
    """
    parts = [
        KEY_VERSION,
        _norm(effect.tenant, field="tenant"),
        _norm(effect.action_class, field="action_class"),
        _norm(effect.target_system, field="target_system"),
        _norm(effect.target_resource_id, field="target_resource_id"),
        _norm(effect.target_operation, field="target_operation"),
        str(effect.occurrence_key or "").strip().lower(),   # "" is legitimate: a single-occurrence effect
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------------------------
# Occurrence rules: when is a REPEATED effect on the same target a legitimate NEW effect?
# --------------------------------------------------------------------------------------------
# This is the question the amount was silently (and wrongly) answering. Two payments of GBP 500 and
# GBP 700 against one invoice are two legitimate effects - but the AMOUNT must not be what tells
# them apart, because then a re-read of ONE payment at a corrected figure also looks like two.
#
# So each action class declares how repetition is discriminated:
#
#   SINGLE    - repetition is NOT legitimate. occurrence_key = "". A second attempt is the SAME
#               logical effect and must converge (commit-once).
#   DERIVED   - repetition IS legitimate and a deterministic, drift-free discriminator exists in the
#               request itself (the document's content digest; the target status being set).
#   CANONICAL - repetition IS legitimate, and the thing that makes two occurrences distinct is a real
#               BUSINESS OCCURRENCE with its own canonical identity. Until that entity exists and can
#               be resolved, the operation FAILS CLOSED.
#
# Phase 1 first shipped a CANONICAL-shaped hole: a free-form `params["occurrence_key"]` that any
# caller could set. That was the same defect the amount had, wearing a different field name - vary it
# per retry and every attempt mints a new logical effect, which is exactly what commit-once exists to
# prevent. Identity may not enter through an untyped dictionary. It comes from a resolved canonical
# occurrence or it does not come at all.

SINGLE = "SINGLE"
DERIVED_DOCUMENT_DIGEST = "DERIVED_DOCUMENT_DIGEST"
DERIVED_TARGET_STATUS = "DERIVED_TARGET_STATUS"
CANONICAL_OCCURRENCE_REQUIRED = "CANONICAL_OCCURRENCE_REQUIRED"


@dataclass(frozen=True)
class CanonicalOccurrence:
    """A resolved business occurrence: WHICH legitimate repetition this effect is.

    Only a resolver may produce one, and a resolver must have proved the occurrence EXISTS, is bound
    to the right entity, and belongs to this tenant. There is deliberately no path from a request
    payload to this type: a caller cannot hand one over, so a caller cannot manufacture identity.
    """

    entity: str          # the canonical entity, e.g. "Payment Application"
    occurrence_id: str   # its canonical identifier, e.g. a payment_application_id

    def key(self) -> str:
        return f"{self.entity.strip().lower()}:{self.occurrence_id.strip().lower()}"


@dataclass(frozen=True)
class OccurrenceSource:
    """Where an action class's occurrence identity MUST come from, and who will build it."""

    field: str           # the typed canonical field, named by the frozen specs
    entity: str          # the canonical entity that owns it
    phase: str           # the phase that introduces that entity
    unit: str            # the implementation unit
    why: str             # why the obvious discriminator is not allowed to be identity


# The canonical occurrence source per action class, taken from the FROZEN specifications - not
# invented here, and not aliased.
CANONICAL_OCCURRENCE_SOURCES: dict[str, OccurrenceSource] = {
    "record_payment": OccurrenceSource(
        field="payment_application_id",
        entity="Payment Application",       # domain E34, 09-financial.md
        phase="P9",
        unit="U9.*",
        why=(
            "Two partial payments against one invoice are separate logical effects because they are "
            "separate Payment Application occurrences - NOT because their amounts differ. The frozen "
            "spec is explicit: the remittance reference (check no./ACH trace) is the occurrence_key "
            "for payment idempotency (ADR-009), and a partial payment is a distinct occurrence. The "
            "amount is a material fact."
        ),
    ),
    "adjust_invoice": OccurrenceSource(
        field="compensation_id",
        entity="Compensation",              # foundational entity 13-compensation.md
        phase="P8",
        unit="U8.4",
        why=(
            "The frozen invoice spec: a void/credit IS a Compensation (a gated effect); a rebill is a "
            "NEW invoice under a distinct action class (REISSUE_INVOICE), not this effect repeated. "
            "One invoice may legitimately receive several distinct adjustments, so the invoice's own "
            "identity is not enough. The changed line values are material facts."
        ),
    ),
    "check_call": OccurrenceSource(
        field="expectation_id",
        entity="Expectation",               # foundational entity 11-expectation.md
        phase="P8",
        unit="U8.4",
        why=(
            "Repeated check calls are distinct only where distinct Expectation occurrences exist. The "
            "note is free text and often model-authored; a timestamp taken at call time is "
            "attempt-scoped. Neither may carry identity."
        ),
    ),
}

# Keyed by the current lane name (the action class's ancestor; renamed at P8, NOT here).
OCCURRENCE_RULES: dict[str, str] = {
    # One invoice per (load, customer). A second attempt is the same effect. THE double-pay case.
    "raise_invoice": SINGLE,
    # One payable per (load, carrier).
    "record_payable": SINGLE,
    # One load per reference.
    "create_load": SINGLE,
    # Filing a POD and a BOL on one load are two effects; filing the SAME bytes twice is one.
    "file_document": DERIVED_DOCUMENT_DIGEST,
    # Setting DELIVERED and setting PICKED_UP are two effects; setting DELIVERED twice is one.
    "update_status": DERIVED_TARGET_STATUS,
    # --- repetition legitimate; identity belongs to a canonical occurrence that does not exist yet ---
    "record_payment": CANONICAL_OCCURRENCE_REQUIRED,
    "adjust_invoice": CANONICAL_OCCURRENCE_REQUIRED,
    "check_call": CANONICAL_OCCURRENCE_REQUIRED,
}


class UnresolvedCanonicalOccurrence(UnidentifiableEffect):
    """The occurrence entity this operation needs does not exist yet. Fail closed, and say which."""


def occurrence_key_for(
    action_class: str,
    *,
    resolved: CanonicalOccurrence | None = None,
    document_digest: str | None = None,
    target_status: str | None = None,
) -> str:
    """The occurrence discriminator for one action class, or raise.

    `resolved` is the ONLY way a repetition-legitimate operation gets an occurrence, and it can only
    come from a resolver that proved the occurrence exists, is bound to the right entity, and belongs
    to this tenant. There is no free-form parameter, so there is nothing for a caller to vary between
    retries.
    """
    rule = OCCURRENCE_RULES.get(action_class)
    if rule is None:
        raise UnidentifiableEffect(
            f"action class {action_class!r} declares no occurrence rule. A new consequential "
            f"operation must state whether repetition is legitimate before it may run."
        )
    if rule is SINGLE:
        return ""
    if rule is DERIVED_DOCUMENT_DIGEST:
        if not document_digest:
            raise UnidentifiableEffect(
                "filing a document needs the document's content digest as its occurrence key; "
                "the file could not be read"
            )
        return str(document_digest).strip().lower()
    if rule is DERIVED_TARGET_STATUS:
        if not target_status:
            raise UnidentifiableEffect(
                "a status change needs the target status as its occurrence key; none was given"
            )
        return str(target_status).strip().lower()

    source = CANONICAL_OCCURRENCE_SOURCES[action_class]
    if resolved is None:
        raise UnresolvedCanonicalOccurrence(
            f"{action_class!r} may legitimately repeat, and which occurrence it is can only come from "
            f"a resolved {source.entity} ({source.field}). No such resolver exists yet: "
            f"{source.entity} arrives at {source.phase} ({source.unit}). Until then this operation "
            f"FAILS CLOSED and a human performs it. {source.why}"
        )
    if resolved.entity.strip().lower() != source.entity.strip().lower():
        raise UnidentifiableEffect(
            f"{action_class!r} needs a {source.entity} occurrence; got {resolved.entity!r}. An "
            f"occurrence bound to the wrong entity is not this effect's identity."
        )
    if not str(resolved.occurrence_id or "").strip():
        raise UnidentifiableEffect(f"the {source.entity} occurrence carries no identifier")
    return resolved.key()


def document_digest(path: str) -> str:
    """Content digest of the file being filed. Content-addressed, so re-filing the same bytes is one
    effect, and filing different bytes is a different effect - without the file's CONTENTS ever
    entering the key."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()
