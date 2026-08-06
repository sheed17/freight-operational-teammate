"""U0.12 - the baseline manifest's own integrity.

The manifest is the only place a Phase-0 allowance may live. Every allowance must carry a reason, a
removal phase, an accountable unit and a deletion condition - enforced here, not by review etiquette.

    No indefinite allowance. No wildcard allowance. No allowance justified only as "legacy".

An allowance without a deletion condition is an indefinite allowance wearing a temporary label.
"""

import ast
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from phase0 import import_probe, manifest

FORBIDDEN_JUSTIFICATIONS = ("legacy", "historical", "for now", "tbd", "temporary")

ROOT = Path(__file__).resolve().parents[2]


def test_the_manifest_exists_and_parses():
    assert manifest.load()


@pytest.mark.parametrize("section", ["expected_current_defects", "expected_acceptance_failures",
                                     "expected_deprecated_terms"])
def test_every_allowance_names_a_reason_a_phase_a_unit_and_a_deletion_condition(section):
    entries = manifest.allowance_sections()[section]
    assert entries, f"{section} is empty - the probe would prove nothing"
    for e in entries:
        label = e.get("id") or e.get("case") or e.get("term")
        for field in ("reason", "removed_by_phase", "accountable_unit", "deletion_condition"):
            assert e.get(field), f"{section}/{label}: missing {field}"


def test_no_allowance_is_justified_only_as_legacy():
    for section, entries in manifest.allowance_sections().items():
        for e in entries:
            label = e.get("id") or e.get("case") or e.get("term")
            reason = str(e.get("reason", "")).strip().lower()
            assert len(reason) > 25, f"{section}/{label}: reason too thin to adjudicate: {reason!r}"
            assert reason not in FORBIDDEN_JUSTIFICATIONS, f"{section}/{label}: {reason!r} is not a reason"


def test_no_wildcard_allowance():
    """A wildcard would let anything through under a rule nobody could adjudicate."""
    raw = Path(manifest.MANIFEST if hasattr(manifest, "MANIFEST") else
               Path(__file__).resolve().parents[2] / "docs" / "implementation"
               / "phase-0-baseline-manifest.yaml").read_text(encoding="utf-8")
    for section in ("edges:", "tables_not_tenant_first:", "effect_capable_by_import:"):
        assert section in raw, f"population proof failed: {section} absent - the scan sees nothing"
        assert f"{section}\n    - '*'" not in raw
        assert f"{section}\n    - \"*\"" not in raw
    assert "\n    - '*'" not in raw and '\n    - "*"' not in raw


def _production_gate_registry_population() -> list[str]:
    """AST sweep over ALL of src/ and scripts/: every `GateRegistry(...)` construction and every
    `register_gate(...)` call. Textual matching would fire on the class definition, on two kernel
    type assertions and on the deferral comments, so it is AST or nothing."""
    sites: list[str] = []
    swept = 0
    for root in ("src", "scripts"):
        for path in sorted((ROOT / root).rglob("*.py")):
            swept += 1
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
                if name in {"GateRegistry", "register_gate"}:
                    sites.append(f"{path.relative_to(ROOT)}:{node.lineno}: {name}")
    assert swept > 100, f"the production sweep walked only {swept} modules - it saw a corner"
    return sites


def test_r07_containment_record_holds_only_while_its_mechanical_conditions_hold():
    """REPLACED at the R-07 CLOSURE CONTENT COMMIT (CLAUDE.md sec 5 rule 20 - replaced, not
    deleted). It was `test_r07_is_never_described_as_contained`, and for its whole life it was
    right: from P0 through the second P4 finalization, `CONTAINED` in this file would have been a
    lie, so the guard forbade the word outright.

    R-07 is now recorded CONTAINED, by the separate content commit repository authority reserved for
    exactly that act. A flipped literal would be a WEAKER guard than the one it replaces - it would
    assert a word instead of a state. So this guard does not assert the word. It asserts that the
    CONTAINED record is only allowed to stand while every mechanical condition that earns it still
    holds, and it fails the build the moment any one of them stops holding:

      1. no live effect-capable violation edge exists;
      2. the recorded and live violation surfaces agree (a cut that is not recorded, and a recorded
         cut that is not real, both fail);
      3. the production GateRegistry population is EMPTY - registering a production gate before
         Phase 8 invalidates the record;
      4. no reachable legacy callback-to-actuator route exists;
      5. the full review / adjudication / finalizer evidence chain is present and exact.

    The RULE the old guard protected is permanent and is asserted below in its own right: an
    allowance in this file is never containment, and discipline is never a mechanism. What changed
    is that a mechanism exists to point at.
    """
    legacy = manifest.load()["expected_legacy_paths"]

    # --- the record itself, in the exact repository-authorized spelling -----------------------
    assert legacy["risk_id"] == "R-07"
    assert legacy["status"] == "CONTAINED", (
        f"the R-07 record reads {legacy['status']!r}; the authorized contained spelling is exactly "
        "'CONTAINED'"
    )
    assert legacy["removed_by_phase"] == "P4"

    # --- (1)+(2) the mechanical close condition, live AND recorded, both-sided ----------------
    live = import_probe.effect_adapter_violation_edges()
    recorded = manifest.recorded_effect_violation_edges()
    assert live == set(), (
        f"R-07 is recorded CONTAINED while a LIVE effect-capable violation edge exists: "
        f"{sorted(live)}"
    )
    assert recorded == set(), (
        f"R-07 is recorded CONTAINED while the manifest still records a residual violation: "
        f"{sorted(recorded)}"
    )
    assert live == recorded, (
        f"R-07 is recorded CONTAINED while live and recorded violation surfaces DISAGREE: "
        f"live-only={sorted(live - recorded)}, recorded-only={sorted(recorded - live)}"
    )

    # --- (3) the production gate registry must still be empty ---------------------------------
    populated = _production_gate_registry_population()
    assert not populated, (
        "R-07 is recorded CONTAINED while the production GateRegistry population is NOT empty - "
        "production gate registration is DEFERRED to U8.1 / P8 by founder decision, and a gate "
        f"registered before Phase 8 invalidates the containment record:\n  " + "\n  ".join(populated)
    )

    # --- (4) no reachable legacy callback-to-actuator route -----------------------------------
    callback = (ROOT / "scripts" / "run_action_callback_server.py").read_text(encoding="utf-8")
    tree = ast.parse(callback)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.rsplit(".", 1)[-1])
        elif isinstance(node, ast.Import):
            imported |= {a.name.rsplit(".", 1)[-1] for a in node.names}
    regained = imported & import_probe.EFFECT_CAPABLE_ADAPTERS
    assert not regained, (
        "R-07 is recorded CONTAINED while the deployed callback server imports effect-capable "
        f"adapter(s) again - a direct actuator route: {sorted(regained)}"
    )
    constructed = {
        name for n in ast.walk(tree) if isinstance(n, ast.Call)
        for name in [getattr(n.func, "id", None) or getattr(n.func, "attr", None)]
        if isinstance(name, str)
    }
    forbidden = {"CdpActuator", "CdpBrowserSession", "OperatorAgent", "OperationRouter"}
    assert not (constructed & forbidden), (
        "R-07 is recorded CONTAINED while the deployed callback server constructs a live-write "
        f"driver again: {sorted(constructed & forbidden)}"
    )

    # --- (5) the evidence chain is present, exact and complete --------------------------------
    ev = legacy["containment_evidence"]
    REQUIRED_IDENTITIES = {
        "implementation_candidate": "0891d1a19a9c47155a56a3f4b2116e5a4d4aa75e",
        "first_finalizer_metadata_commit": "86306d5c4d866baf1a7fb6e4bd8220ce31017acd",
        "p4_acceptance_closure_candidate": "42ea24cfc76fac19406e7eaa44b695b8d032b3aa",
        "second_finalizer_metadata_commit": "06ebfdb35a544df8e9cf36d739cc54a0b6877e1f",
    }
    for key, value in REQUIRED_IDENTITIES.items():
        assert ev.get(key) == value, (
            f"containment_evidence.{key} is {ev.get(key)!r}, not the accepted {value}"
        )
    REQUIRED_DOCUMENTS = {
        "accepted_independent_rereview":
            "181e1a37a413fd35f537e00a7e1423bf192f88205270fa15932fbabeb955d316",
        "final_adjudication":
            "078cfea8f7d691da0c7649ddaa2f1f64bc7138dc64b91814dda1d6cc68cb997e",
        "accepted_targeted_independent_review":
            "5547aa5e8d89ced661b4f6e415767f8259809bdf5d175615065158fa871a8ea5",
        "accepted_targeted_adjudication":
            "23496e6cb895c3ceb591947b9828de1e248ca4ed0f46c82282c1a1c256499567",
        "second_finalization_report":
            "96ef5fe85016f2de5d5840814d95dd170947474a3259ac8bb902df9f485a1fa0",
    }
    for key, digest in REQUIRED_DOCUMENTS.items():
        text = str(ev.get(key, ""))
        assert digest in text, (
            f"containment_evidence.{key} does not carry the accepted SHA-256 {digest} - the "
            "containment record may not cite evidence it cannot pin"
        )
        named = re.search(r"docs/implementation/[\w./-]+\.md", text)
        assert named, f"containment_evidence.{key} names no report path"
        assert (ROOT / named.group(0)).exists(), (
            f"containment_evidence.{key} cites {named.group(0)}, which does not exist"
        )
    assert ev["canonical_suite"] == "1961 passed / 0 failed / 1 skipped / 1962 collected"
    assert ev["clean_clone"] == "PASS"
    assert ev["violation_edges"] == "0 live / 0 recorded, agreeing both-sided"
    assert "EMPTY" in ev["production_gate_registry"]
    assert "DEFERRED" in ev["phase_8_gate_registration"] and "P8" in ev["phase_8_gate_registration"]
    assert ev["reachable_legacy_callback_to_actuator_path"] == "NONE"
    assert str(ev["p5_implementation"]).startswith("NOT BEGUN")

    # --- the containment claim is bounded, and says what it is NOT ----------------------------
    mech = legacy["containment_mechanism"]
    assert "STRUCTURAL" in mech, "the mechanism must be stated structurally, not as a test result"
    for phrase in ("effect_boundary", "REFUSES", "ROUTE_NOT_CONFIGURED"):
        assert phrase in mech, f"the containment mechanism no longer names {phrase!r}"
    assert "not production writes enabled" in mech, (
        "the record must keep stating that containment is NOT production writes enabled"
    )
    assert "not autonomy of any kind" in mech, (
        "the record must keep disclaiming autonomy - containment is not bounded autonomy"
    )
    # the permanent rule the superseded guard existed to protect
    assert "discipline is never containment" in mech, (
        "the permanent rule was dropped: discipline is never containment"
    )


def test_no_allowance_section_may_be_read_as_containment():
    """The rule the R-07 guard always really protected, now stated in its own right and applied to
    EVERY allowance section rather than only to R-07: a recorded allowance is a receipt for a known
    hole, never a mechanism. This is the half of the superseded assertion that never expires."""
    raw = (ROOT / "docs" / "implementation" / "phase-0-baseline-manifest.yaml").read_text(encoding="utf-8")
    assert "An allowance here is" in raw and "not containment" in raw, (
        "the manifest header stopped saying that an allowance is not containment"
    )
    sections = manifest.allowance_sections()
    assert sections, "allowance discovery produced nothing - this guard would pass vacuously"
    offenders = []
    for section, entries in sections.items():
        assert entries, f"{section} is empty - the scan would prove nothing"
        for e in entries:
            label = e.get("id") or e.get("case") or e.get("term")
            blob = " ".join(str(v) for v in e.values())
            if re.search(r"\bthis allowance (?:is|provides|constitutes) containment\b", blob, re.I):
                offenders.append(f"{section}/{label}")
    assert not offenders, f"allowance(s) claiming to BE containment: {offenders}"


def test_every_prohibited_regression_names_the_test_that_detects_it():
    """A rule with no detector is a wish."""
    regs = manifest.load()["prohibited_new_regressions"]
    assert len(regs) >= 8
    tests_dir = Path(__file__).resolve().parent
    for r in regs:
        detector = r["detected_by"]
        assert (tests_dir / f"{detector}.py").exists(), f"{r['id']}: no such detector {detector}"


def test_every_required_invariant_names_an_accountable_unit():
    for inv in manifest.load()["required_invariants"]:
        assert inv["rule"] and inv["reason"] and inv["accountable_unit"]


def test_the_test_count_ratchet_direction_is_recorded():
    """Tests may be added. A DROP is a hard failure - that is how a guard disappears unnoticed."""
    baseline = manifest.load()["baseline"]
    assert baseline["tests_passing_at_baseline"] == 677
    assert ">=" in baseline["test_count_rule"]
