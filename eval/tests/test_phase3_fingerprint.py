"""Phase 3 — the fp_v1 canonical fingerprint (ADR-005 §3.4–§3.6, §3.13).

Non-determinism in serialization is the single most dangerous bug class in ADR-005: it produces
false drift (annoying) or false no-drift (a wrong payment). These tests attack the serialization
rules directly, including the property test the ADR names as merge-gating.
"""

from __future__ import annotations

import random
import string
import sys
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.fingerprint import (  # noqa: E402
    FINGERPRINT_VERSION,
    FingerprintError,
    Money,
    MoneyMustNotFloat,
    UnknownFingerprintVersion,
    canonical_payload,
    drift_diff,
    fingerprint,
)

FACTS = {
    "amount": Money(285000, "GBP"),
    "counterparty": "Acme Logistics",
    "load": {"ref": "load:4471", "delivered": True},
    "documents": ["pod:abc123", "rate:def456"],
    "noted_at": datetime(2026, 7, 21, 9, 14, 0, 123000, tzinfo=timezone.utc),
}


def test_the_fingerprint_is_deterministic_across_key_order():
    shuffled = dict(reversed(list(FACTS.items())))
    assert canonical_payload(FACTS) == canonical_payload(shuffled)
    assert fingerprint(FACTS) == fingerprint(shuffled)


def test_property_randomized_fact_sets_serialize_identically_regardless_of_insertion_order():
    """The ADR-005 §10 property test: randomized fact sets, two insertion orders, identical
    bytes. Deterministic seed so a failure reproduces."""
    rng = random.Random(20260721)
    checked = 0
    for _ in range(500):
        n = rng.randint(1, 12)
        facts = {}
        for i in range(n):
            key = "".join(rng.choice(string.ascii_lowercase) for _ in range(rng.randint(1, 10))) + str(i)
            kind = rng.randrange(5)
            if kind == 0:
                facts[key] = Money(rng.randrange(10**8), "USD")
            elif kind == 1:
                facts[key] = "".join(rng.choice(string.printable.replace("=", "").replace("\n", "").replace(".", "")) for _ in range(rng.randint(0, 20)))
            elif kind == 2:
                facts[key] = rng.randrange(-10**9, 10**9)
            elif kind == 3:
                facts[key] = rng.choice([True, False, None])
            else:
                facts[key] = sorted("".join(rng.choice(string.ascii_letters) for _ in range(4)) for _ in range(3))
        items = list(facts.items())
        rng.shuffle(items)
        assert canonical_payload(facts) == canonical_payload(dict(items))
        checked += 1
    assert checked == 500, "the property population collapsed"


def test_money_floats_are_a_hard_error_not_a_coercion():
    with pytest.raises(MoneyMustNotFloat):
        Money(2850.00, "GBP")  # type: ignore[arg-type]
    with pytest.raises(MoneyMustNotFloat):
        canonical_payload({"amount": 2850.0})
    with pytest.raises(MoneyMustNotFloat):
        canonical_payload({"amount": Decimal("2850.00")})
    with pytest.raises(MoneyMustNotFloat):
        canonical_payload({"nested": {"fee": 0.1}})


def test_bool_is_not_money_and_currency_is_strict():
    with pytest.raises(MoneyMustNotFloat):
        Money(True, "GBP")  # type: ignore[arg-type]
    for bad in ("gbp", "POUND", "GB", "", None):
        with pytest.raises(FingerprintError):
            Money(285000, bad)  # type: ignore[arg-type]


def test_null_and_absent_are_different_fingerprints():
    with_null = {"amount": Money(1, "GBP"), "memo": None}
    without = {"amount": Money(1, "GBP")}
    assert fingerprint(with_null) != fingerprint(without)


def test_unicode_is_nfc_normalized_but_never_case_folded_or_trimmed():
    composed = {"counterparty": "Acm\u00e9"}       # e-acute as one codepoint, escaped
    decomposed = {"counterparty": "Acme\u0301"}    # e + combining acute, escaped
    assert composed["counterparty"] != decomposed["counterparty"]  # different bytes going in
    assert fingerprint(composed) == fingerprint(decomposed)
    assert fingerprint({"c": "ACME"}) != fingerprint({"c": "acme"})
    assert fingerprint({"c": " acme"}) != fingerprint({"c": "acme"})


def test_timestamps_are_rfc3339_utc_millisecond_z():
    payload = canonical_payload(
        {"at": datetime(2026, 7, 21, 9, 14, 0, 123456, tzinfo=timezone.utc)}).decode()
    assert "at=2026-07-21T09:14:00.123Z" in payload
    with pytest.raises(FingerprintError):
        canonical_payload({"at": datetime(2026, 7, 21, 9, 14)})  # naive => refused


def test_enums_serialize_by_lowercased_name_never_ordinal():
    class Direction(Enum):
        MONEY_OUT = 7
    assert "d=money_out" in canonical_payload({"d": Direction.MONEY_OUT}).decode()


def test_collections_are_sorted_and_nesting_flattens_with_dots():
    a = canonical_payload({"docs": ["b", "a"], "load": {"ref": "x"}}).decode()
    assert "docs=[a,b]" in a
    assert "load.ref=x" in a


def test_reserved_key_characters_are_refused_not_mangled():
    for bad_key in ("a=b", "a\nb", "a.b"):
        with pytest.raises(FingerprintError):
            canonical_payload({bad_key: "v"})


def test_dotted_key_collision_with_nesting_cannot_produce_identical_bytes():
    """{"a.b": x} and {"a": {"b": x}} are different fact sets. The reserved-character rule
    refuses the former outright — identical bytes for different facts is false no-drift."""
    nested = canonical_payload({"a": {"b": "x"}})
    with pytest.raises(FingerprintError):
        canonical_payload({"a.b": "x"})
    assert b"a.b=x" in nested  # the nested spelling owns the flattened form


def test_the_version_envelope_is_inside_the_hashed_bytes():
    payload = canonical_payload(FACTS)
    assert payload.startswith(f"{FINGERPRINT_VERSION}\n".encode())


def test_an_unknown_fingerprint_version_is_refused_never_guessed():
    with pytest.raises(UnknownFingerprintVersion):
        canonical_payload(FACTS, version="fp_v0")
    with pytest.raises(UnknownFingerprintVersion):
        canonical_payload(FACTS, version="fp_v2")


def test_empty_fact_sets_and_empty_mappings_are_refused():
    with pytest.raises(FingerprintError):
        canonical_payload({})
    with pytest.raises(FingerprintError):
        canonical_payload({"load": {}})


def test_drift_diff_names_the_field_old_and_new():
    approved = canonical_payload({"amount": Money(285000, "GBP"), "party": "Acme"})
    current = canonical_payload({"amount": Money(310000, "GBP"), "party": "Acme"})
    diff = drift_diff(approved, current)
    assert len(diff) == 1
    d = diff[0]
    assert d.field == "amount" and d.approved == "285000|GBP" and d.current == "310000|GBP"


def test_drift_diff_reports_appeared_and_vanished_fields():
    approved = canonical_payload({"amount": Money(1, "GBP"), "old": "x"})
    current = canonical_payload({"amount": Money(1, "GBP"), "new": "y"})
    fields = {d.field: (d.approved, d.current) for d in drift_diff(approved, current)}
    assert fields == {"old": ("x", None), "new": (None, "y")}


def test_drift_diff_refuses_a_foreign_envelope():
    with pytest.raises(UnknownFingerprintVersion):
        drift_diff(b"fp_v9\nx=1", canonical_payload({"x": "1"}))
