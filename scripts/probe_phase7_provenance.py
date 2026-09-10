#!/usr/bin/env python3
"""P7 (provenance-safety core) behavioural probe.

Operates the four provenance-safety rules directly and prints a PASS line per rule with BOTH a
refusal the driver can see AND a positive control that the legitimate path is admitted. This is the
surface a reviewer runs to observe P7 provenance behaviour without schema introspection.

Run:  .venv/bin/python scripts/probe_phase7_provenance.py
      .venv/bin/python scripts/probe_phase7_provenance.py --list
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from freight_recon import provenance as P  # noqa: E402
from freight_recon.checkpoint import (  # noqa: E402
    EvidenceCondition,
    GateReadOfInferredFact,
    ProvenanceClass,
    ProvenancedFact,
)

SIX = {"SYSTEM_IMPORTED", "OWNER_ASSERTED", "LINKER_INFERRED",
       "MODEL_EXTRACTED", "MODEL_INFERRED", "RECONCILED"}

_CASES: dict = {}


def case(name):
    def deco(fn):
        _CASES[name] = fn
        return fn
    return deco


def _refused(exc_type, fn) -> bool:
    try:
        fn()
        return False
    except exc_type:
        return True


@case("ac2-exactly-six-classes-one-authority")
def _c() -> list[str]:
    from freight_recon.evidence import MODEL_EXTRACTED as EV_ME
    from freight_recon.migrations.phase6_observations import (
        OBSERVATION_FORBIDDEN_PROVENANCE, OBSERVATION_PROVENANCE_ALLOWED)
    six = P.PROVENANCE_CLASS_VALUES == SIX
    m5 = {*OBSERVATION_PROVENANCE_ALLOWED, OBSERVATION_FORBIDDEN_PROVENANCE} == SIX
    ev = EV_ME == ProvenanceClass.MODEL_EXTRACTED.value
    seventh_refused = _refused(P.ProvenanceError, lambda: P.as_class("BROKER_VOUCHED"))
    return [f"AC-2 exactly the six classes, no seventh: {six and seventh_refused}",
            f"AC-2 one authority (kernel == M5 vocabulary == evidence constant): {m5 and ev}"]


@case("rp1-runtime-assignment")
def _c() -> list[str]:
    guess = P.assign_at_runtime(P.Acquisition.MODEL_GUESS) is ProvenanceClass.MODEL_INFERRED
    human = P.assign_at_runtime(P.Acquisition.AUTHENTICATED_HUMAN_ACT) is ProvenanceClass.OWNER_ASSERTED
    content_refused = _refused(P.ProvenanceFromContent,
                               lambda: P.reject_content_supplied_provenance({"provenance_class": "OWNER_ASSERTED"}))
    P.reject_content_supplied_provenance({"amount": "2850"})  # positive control: no key -> admitted
    forged = _refused(P.ProvenanceError, lambda: P.assign_at_runtime("OWNER_ASSERTED"))
    return [f"R-P1 a model guess is assigned MODEL_INFERRED, a human act OWNER_ASSERTED: {guess and human}",
            f"R-P1 inbound content carrying provenance_class is REFUSED (positive control admitted): {content_refused}",
            f"R-P1 a caller cannot forge a class in place of an acquisition: {forged}"]


@case("ac4-model-inferred-cannot-gate")
def _c() -> list[str]:
    refused = _refused(GateReadOfInferredFact,
                       lambda: P.read_for_consequential_gate("MODEL_INFERRED", 2850))
    positive = P.read_for_consequential_gate("SYSTEM_IMPORTED", 2850) == 2850
    # 'at any confidence': the same refusal holds for any value, and there is no confidence parameter.
    any_conf = all(_refused(GateReadOfInferredFact,
                            lambda v=v: P.read_for_consequential_gate("MODEL_INFERRED", v))
                   for v in (0.99, 1.0, "very likely"))
    # one authority: the kernel's own gate accessor enforces the identical rule.
    kf = ProvenancedFact(field="amount", provenance=ProvenanceClass.MODEL_INFERRED,
                         evidence_condition=EvidenceCondition.CONSISTENT, _value=2850)
    kernel = _refused(GateReadOfInferredFact, lambda: kf.value)
    return [f"AC-4 a MODEL_INFERRED fact is REFUSED at a consequential gate (SYSTEM_IMPORTED admitted): {refused and positive}",
            f"AC-4 refused at ANY confidence, and there is no confidence parameter: {any_conf}",
            f"AC-4 the kernel's ProvenancedFact enforces the same rule (one authority): {kernel}"]


@case("rp2-no-laundering")
def _c() -> list[str]:
    launder_refused = _refused(P.ProvenanceLaundering,
                               lambda: P.reassign("MODEL_INFERRED", "LINKER_INFERRED"))
    counterparty_refused = _refused(P.ProvenanceLaundering,
                                    lambda: P.reassign("MODEL_EXTRACTED", "OWNER_ASSERTED"))
    weaken_ok = P.reassign("OWNER_ASSERTED", "MODEL_INFERRED") is ProvenanceClass.MODEL_INFERRED
    human_ok = P.reassign("MODEL_INFERRED", "OWNER_ASSERTED",
                          authenticated_human_act=True) is ProvenanceClass.OWNER_ASSERTED
    six_path = all(P.derive_through("MODEL_INFERRED", p) is ProvenanceClass.MODEL_INFERRED
                   for p in P.DERIVATION_PATHS)
    return [f"R-P2 a guess cannot be mechanically strengthened, a counterparty reading cannot be promoted: {launder_refused and counterparty_refused}",
            f"R-P2 weakening is allowed and a human act may create OWNER_ASSERTED (positive controls): {weaken_ok and human_ok}",
            f"R-P2 a MODEL_INFERRED fact stays MODEL_INFERRED through all six derivation paths: {six_path}"]


@case("rp3-owner-asserted-protected")
def _c() -> list[str]:
    owner = P.ProvenanceRecord(value="load-4471", provenance_class="OWNER_ASSERTED")
    recompute_refused = _refused(P.OwnerAssertedRecompute,
                                 lambda: P.machine_recompute(owner, new_value="load-44718",
                                                             new_class="LINKER_INFERRED"))
    preserved = owner.value == "load-4471"
    non_owner = P.ProvenanceRecord(value="x", provenance_class="MODEL_EXTRACTED")
    positive = P.machine_recompute(non_owner, new_value="y",
                                   new_class="LINKER_INFERRED").provenance_class is ProvenanceClass.LINKER_INFERRED
    human = P.human_reassert(owner, new_value="load-44718").provenance_class is ProvenanceClass.OWNER_ASSERTED
    return [f"R-P3 a machine recompute of an OWNER_ASSERTED value is REFUSED and the owner value is preserved: {recompute_refused and preserved}",
            f"R-P3 a non-owner record IS recomputable (positive control), and a human may re-assert: {positive and human}"]


def _run(names: list[str]) -> int:
    wrong = 0
    for name in names:
        for line in _CASES[name]():
            print(line)
            if line.rstrip().endswith(": False") or "### WRONG ###" in line:
                wrong += 1
    print(f"behaviours as specified, {wrong} wrong")
    return 0 if wrong == 0 else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--case")
    args = ap.parse_args()
    if args.list:
        for n in _CASES:
            print(n)
        return 0
    return _run([args.case] if args.case else list(_CASES))


if __name__ == "__main__":
    sys.exit(main())
