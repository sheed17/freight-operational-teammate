#!/usr/bin/env python3
"""Deterministic behaviour probe for P8 / U8.6 — the inert Proposal boundary.

Runs a fixed set of behaviours against the real code and prints each with its verdict and a final
tally. It parses nothing it did not itself produce and asserts against a proven population (every
behaviour is exercised, never merely imported), per CLAUDE.md §6. It is NOT an independent review.

    .venv/bin/python scripts/probe_phase8_proposal.py

Scope note: this probe stays on the INERT `ProposedIntent` side of the boundary. It does not import
the interpretation DTO, the M1 Work Item or open an M2 pipeline — P6 ships dark, and a script that
named those would grow a deprecated-vocabulary surface or make a dark machine live. The
interpretation → Proposal conversion and the proposal → M2 seam are exercised end-to-end by
`eval/tests/test_phase8_proposal.py` (which may use the P6 test kits).

Prints `behaviours as specified, 0 wrong` when every behaviour holds; a non-zero count is a defect.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from freight_recon.checkpoint import GateReadOfInferredFact, ProvenanceClass  # noqa: E402
from freight_recon.commit_key import (  # noqa: E402
    CanonicalOccurrence,
    LogicalEffect,
    UnidentifiableEffect,
    UnresolvedCanonicalOccurrence,
    occurrence_key_for,
)
from freight_recon.fingerprint import Money, MoneyMustNotFloat  # noqa: E402
from freight_recon.proposal import (  # noqa: E402
    ProposalError,
    ProposedFact,
    ProposedIntent,
    UnregisteredActionClass,
    build_proposed_intent,
)

T = "tenant-probe"

_results: list[tuple[str, bool]] = []


def check(name: str, ok: bool) -> None:
    _results.append((name, bool(ok)))


def raises(exc, fn, *a, **k) -> bool:
    try:
        fn(*a, **k)
    except exc:
        return True
    except Exception:  # noqa: BLE001
        return False
    return False


def _mature(resource="load:4471|acme", amount_minor=285000, prov=ProvenanceClass.MODEL_EXTRACTED):
    return build_proposed_intent(
        tenant=T, action_class="raise_invoice", target_system="tms:truckingoffice",
        target_resource_id=resource, target_operation="create_invoice",
        work_item_id="wi-1", accountable_owner="dana",
        facts=(ProposedFact.money("approved_amount", Money(amount_minor, "USD"), provenance=prov),))


def _target(action_class, **kw):
    return build_proposed_intent(
        tenant=T, action_class=action_class, target_system="tms:truckingoffice",
        target_resource_id="ld-9|acme", target_operation=action_class, **kw)


def main() -> int:
    p = _mature()
    check("a mature proposal names a registered action_class and can derive its identity",
          p.action_class == "raise_invoice" and p.is_mature)
    check("the commit key is derived and carries no amount (ADR-009)",
          p.logical_effect().key() == LogicalEffect(
              tenant=T, action_class="raise_invoice", target_system="tms:truckingoffice",
              target_resource_id="load:4471|acme", target_operation="create_invoice",
              occurrence_key="").key())
    check("a different proposed amount is the SAME logical effect (amount is not identity)",
          _mature(amount_minor=285000).logical_effect().key()
          == _mature(amount_minor=310000).logical_effect().key())

    check("all eight registered action classes are proposable",
          len({build_proposed_intent(tenant=T, action_class=ac).action_class
               for ac in __import__("freight_recon.product_policy",
                                    fromlist=["ACTION_CLASS_POPULATION"]).ACTION_CLASS_POPULATION}) == 8)
    check("an unregistered action_class is refused, not invented",
          raises(UnregisteredActionClass, build_proposed_intent, tenant=T, action_class="wire_money"))

    check("a float money amount is refused (canonical minor units only)",
          raises(MoneyMustNotFloat, ProposedFact.money_from_amount, 2850.00))
    check("sub-cent precision is refused",
          raises(MoneyMustNotFloat, ProposedFact.money_from_amount, "2850.001"))
    check("a decimal string becomes canonical minor units",
          ProposedFact.money_from_amount("2,850.00") == Money(285000, "USD"))
    check("a proposed money fact serializes as canonical minor units with its provenance",
          p.fact("approved_amount").value == "285000|USD"
          and p.fact("approved_amount").provenance is ProvenanceClass.MODEL_EXTRACTED)

    guess = ProposedFact(field="approved_amount", value="285000|USD",
                         provenance=ProvenanceClass.MODEL_INFERRED)
    check("a MODEL_INFERRED fact is not gate-readable", guess.gate_readable is False)
    check("reading a MODEL_INFERRED fact for a gate refuses structurally",
          raises(GateReadOfInferredFact, guess.read_for_gate))
    inferred = build_proposed_intent(tenant=T, action_class="raise_invoice", facts=(guess,))
    check("a MODEL_INFERRED fact is excluded from a gate's readable facts",
          inferred.gate_readable_facts() == ())
    check("a MODEL_INFERRED fact stays MODEL_INFERRED across a round trip (never promoted)",
          ProposedIntent.from_wire(inferred.to_wire()).fact("approved_amount").provenance
          is ProvenanceClass.MODEL_INFERRED)

    again = ProposedIntent.from_wire(_mature().to_wire())
    check("a serialization round trip preserves action_class, resource and provenance",
          again.action_class == "raise_invoice" and again.target_resource_id == "load:4471|acme"
          and again.logical_effect().key() == _mature().logical_effect().key()
          and again.fact("approved_amount").provenance is ProvenanceClass.MODEL_EXTRACTED)
    tampered = _mature().to_wire()
    tampered["action_class"] = "wire_money"
    check("a tampered wire form naming an unregistered class is refused",
          raises(UnregisteredActionClass, ProposedIntent.from_wire, tampered))
    check("an immature proposal fails closed at the identity boundary",
          raises(UnidentifiableEffect,
                 build_proposed_intent(tenant=T, action_class="raise_invoice").logical_effect))

    # --- occurrence identity has ONE authority: commit_key.occurrence_key_for (P1) ---------------
    declared = {**_mature().to_wire(), "occurrence_key": "retry-2"}   # a HOSTILE form, built here
    check("a wire form that declares its own occurrence is refused",
          raises(ProposalError, ProposedIntent.from_wire, declared))
    check("no caller can hand a proposal an occurrence (there is no parameter for one)",
          raises(TypeError, build_proposed_intent, tenant=T, action_class="raise_invoice",
                 occurrence_key="retry-2"))
    check("a SINGLE proposal's identity converges whatever occurrence inputs ride along",
          len({_target("raise_invoice", **kw).logical_effect().key()
               for kw in ({}, {"target_status": "DELIVERED"}, {"document_digest": "a" * 64})}) == 1)
    check("a derived occurrence is exactly what the canonical authority returns",
          _target("update_status", target_status="DELIVERED").logical_effect().occurrence_key
          == occurrence_key_for("update_status", target_status="DELIVERED"))
    check("an unresolved canonical occurrence fails closed (and the proposal is not mature)",
          raises(UnresolvedCanonicalOccurrence, _target("record_payment").logical_effect)
          and _target("record_payment").is_mature is False)
    pa1 = CanonicalOccurrence(entity="Payment Application", occurrence_id="pa-1")
    check("a correctly resolved canonical occurrence produces the ordinary canonical key",
          _target("record_payment").logical_effect(resolved=pa1).key() == LogicalEffect(
              tenant=T, action_class="record_payment", target_system="tms:truckingoffice",
              target_resource_id="ld-9|acme", target_operation="record_payment",
              occurrence_key=occurrence_key_for("record_payment", resolved=pa1)).key())
    check("a raw string cannot stand in for a resolved canonical occurrence",
          raises(ProposalError, _target("record_payment").logical_effect,
                 resolved="payment application:pa-1"))

    wrong = [name for name, ok in _results if not ok]
    width = max(len(n) for n, _ in _results)
    for name, ok in _results:
        print(f"  {'ok ' if ok else 'XX '} {name.ljust(width)}")
    print(f"\n{len(_results)} behaviours checked, {len(wrong)} wrong")
    print("behaviours as specified, 0 wrong" if not wrong else f"WRONG: {wrong}")
    return 1 if wrong else 0


if __name__ == "__main__":
    raise SystemExit(main())
