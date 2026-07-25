"""The canonical Material-Facts fingerprint: fp_v1 (ADR-005 §3.4–§3.6).

THE RULE (ADR-005 §3.1): a human does not approve an action. A human approves an action together
with the exact facts that made it correct. If any of those facts change, there is no approval —
there is a new question. This module is the mechanism that makes "any of those facts change"
byte-decidable.

Two systems computing the fingerprint of the same facts must produce the same bytes. Byte-for-byte
determinism is the whole mechanism; anything ambiguous here is a silent bypass. The serialization
rules below are ADR-005 §3.4 verbatim, and the property tests exercise them adversarially.

We store the full canonical payload, not just the hash (§3.5): a hash can prove that something
drifted; it can never say what. The field-level diff that names "amount: 285000|GBP -> 310000|GBP"
is generated from the retained payloads — which is why they are retained.

Version pinning (§3.6): drift is checked by recomputing under the version STORED ON THE APPROVAL,
never the version the code happens to speak today. A refactor of the hashing code must never
silently void every outstanding approval — nor silently validate one it should have voided.
"""

from __future__ import annotations

import hashlib
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

# The only fingerprint algorithm this module speaks. The version is INSIDE the hashed bytes
# (the envelope prefix), so a version confusion cannot produce a colliding hash.
FINGERPRINT_VERSION = "fp_v1"

# Sentinel serialization for an explicitly-null material fact. Distinct from ABSENT (the key does
# not appear at all): ADR-002 C5 — `absent` and `unknown` are different conditions, and the
# serialization must not collapse them.
_NULL = "<null>"


class FingerprintError(ValueError):
    """The fact set cannot be canonically serialized. Fail closed — never coerce."""


class MoneyMustNotFloat(FingerprintError):
    """A float reached the money serializer. `2850.00` and `2850.0` are the same money and
    different bytes — that is a defect waiting to be a double payment. Hard error, no coercion."""


class UnknownFingerprintVersion(FingerprintError):
    """An approval pinned a fingerprint version this code does not implement. Fail closed:
    recomputing under the wrong algorithm could validate an approval it should have voided."""


@dataclass(frozen=True)
class Money:
    """Integer minor units + ISO-4217 code. The ONLY legal money shape in a fingerprint.

    Floats are refused at construction, not merely at serialization, so a float cannot travel
    one step into the fact set before being caught.
    """

    amount_minor: int
    currency: str

    def __post_init__(self) -> None:
        if isinstance(self.amount_minor, bool) or not isinstance(self.amount_minor, int):
            raise MoneyMustNotFloat(
                f"money must be integer minor units, got {type(self.amount_minor).__name__}: "
                f"{self.amount_minor!r}"
            )
        code = str(self.currency or "").strip()
        if len(code) != 3 or not code.isalpha() or not code.isupper():
            raise FingerprintError(f"currency must be an ISO-4217 alpha-3 code, got {self.currency!r}")

    def canonical(self) -> str:
        return f"{self.amount_minor}|{self.currency}"


def _canonical_scalar(value: object, *, key: str) -> str:
    """One scalar, canonically. Raises on anything ambiguous rather than guessing."""
    if value is None:
        return _NULL
    if isinstance(value, Money):
        return value.canonical()
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        # No float is legal ANYWHERE in a fingerprint, not only in money: float repr is
        # locale/precision folklore, and folklore is not identity.
        raise MoneyMustNotFloat(f"field {key!r} is a float ({value!r}); floats are forbidden in fp_v1")
    if isinstance(value, Decimal):
        raise MoneyMustNotFloat(
            f"field {key!r} is a Decimal ({value!r}); serialize money as Money(amount_minor, currency)"
        )
    if isinstance(value, Enum):
        return str(value.name).lower()
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise FingerprintError(f"timestamp field {key!r} is naive; fingerprints require UTC")
        as_utc = value.astimezone(timezone.utc)
        # RFC-3339, UTC, EXACTLY millisecond precision, Z suffix.
        return as_utc.strftime("%Y-%m-%dT%H:%M:%S.") + f"{as_utc.microsecond // 1000:03d}Z"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        # Raw. No trimming, no case-folding, no locale collation. A counterparty name that
        # differs only in case is a different counterparty until a human says otherwise.
        return unicodedata.normalize("NFC", value)
    raise FingerprintError(f"field {key!r} has unserializable type {type(value).__name__}")


def _flatten(facts: dict, *, prefix: str = "") -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for raw_key in facts:
        if not isinstance(raw_key, str) or not raw_key:
            raise FingerprintError(f"fact keys must be non-empty strings, got {raw_key!r}")
        if "=" in raw_key or "\n" in raw_key or "." in raw_key:
            # "." is the nesting separator: allowing it in a literal key would make
            # {"a.b": x} and {"a": {"b": x}} — two DIFFERENT fact sets — serialize to the same
            # bytes. Identical bytes for different facts is false no-drift, the dangerous
            # direction (ADR-005 §7). "=" and newline delimit the payload itself.
            raise FingerprintError(f"fact key {raw_key!r} contains a reserved character (., =, newline)")
        key = f"{prefix}{unicodedata.normalize('NFC', raw_key)}"
        value = facts[raw_key]
        if isinstance(value, dict):
            # Nesting is flattened with `.` separators; an empty dict is a structural nothing and
            # is refused rather than silently vanishing from the identity.
            if not value:
                raise FingerprintError(f"field {key!r} is an empty mapping; state the facts explicitly")
            pairs.extend(_flatten(value, prefix=f"{key}."))
        elif isinstance(value, (list, tuple, set, frozenset)):
            items = sorted(_canonical_scalar(v, key=key) for v in value)
            pairs.append((key, "[" + ",".join(items) + "]"))
        else:
            pairs.append((key, _canonical_scalar(value, key=key)))
    return pairs


def canonical_payload(facts: dict, *, version: str = FINGERPRINT_VERSION) -> bytes:
    """The full fp_v1 canonical bytes for one material fact set.

    A flat, sorted list of key=value pairs, keys sorted bytewise, UTF-8, NFC, prefixed with the
    version envelope so the version is inside the hashed bytes.
    """
    if version != FINGERPRINT_VERSION:
        raise UnknownFingerprintVersion(
            f"approval pinned fingerprint version {version!r}; this code implements "
            f"{FINGERPRINT_VERSION!r} only and will not guess at another algorithm"
        )
    if not isinstance(facts, dict) or not facts:
        raise FingerprintError("a material fact set must be a non-empty mapping")
    pairs = _flatten(facts)
    keys = [k for k, _ in pairs]
    if len(set(keys)) != len(keys):
        dupes = sorted({k for k in keys if keys.count(k) > 1})
        raise FingerprintError(f"fact keys collide after flattening: {dupes}")
    body = "\n".join(f"{k}={v}" for k, v in sorted(pairs, key=lambda kv: kv[0].encode("utf-8")))
    return f"{FINGERPRINT_VERSION}\n{body}".encode("utf-8")


def fingerprint(facts: dict, *, version: str = FINGERPRINT_VERSION) -> str:
    """SHA-256 over the canonical payload. The fast equality check at checkpoint step 2."""
    return hashlib.sha256(canonical_payload(facts, version=version)).hexdigest()


@dataclass(frozen=True)
class DriftedField:
    """One field of a drift diff: exactly which fact changed, from what, to what."""

    field: str
    approved: str | None   # canonical serialization at approval; None = the field did not exist
    current: str | None    # canonical serialization now; None = the field no longer exists


def drift_diff(approved_payload: bytes, current_payload: bytes) -> list[DriftedField]:
    """Field-level diff between two canonical payloads (ADR-005 §3.13).

    A system that blocks an action it cannot explain has merely relocated the owner's problem —
    the diff is a required output, not a log line. Operates on the retained payloads because a
    hash cannot be diffed.
    """
    def parse(payload: bytes) -> dict[str, str]:
        text = payload.decode("utf-8")
        lines = text.split("\n")
        if not lines or lines[0] != FINGERPRINT_VERSION:
            raise UnknownFingerprintVersion(
                f"payload envelope {lines[0]!r} is not {FINGERPRINT_VERSION!r}; refusing to diff "
                f"payloads whose serialization rules this code does not know"
            )
        out: dict[str, str] = {}
        for line in lines[1:]:
            key, sep, value = line.partition("=")
            if not sep:
                raise FingerprintError(f"malformed canonical line {line!r}")
            out[key] = value
        return out

    approved, current = parse(approved_payload), parse(current_payload)
    drifted: list[DriftedField] = []
    for field in sorted(set(approved) | set(current)):
        a, c = approved.get(field), current.get(field)
        if a != c:
            drifted.append(DriftedField(field=field, approved=a, current=c))
    return drifted
