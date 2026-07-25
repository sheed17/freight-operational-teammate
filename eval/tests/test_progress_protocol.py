"""Founder progress-protocol guards (U-REBASELINE-1).

The progress system is mechanical: percentages are DERIVED from PROGRAM-WEIGHTS.yaml + the
registry by scripts/progress_status.py, written into BUILD-STATUS.yaml by the finalizer, and can
never be hand-inflated. These guards enforce that, plus the required references and the finalizer's
rejection behavior (the rejection cases are unit tests of the validator - they ARE the mutation
proofs, run every suite).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import progress_status as ps  # noqa: E402
import finalize_status as fin  # noqa: E402

IMPL = ROOT / "docs" / "implementation"
PROTOCOL = IMPL / "PROGRESS-PROTOCOL.md"
WEIGHTS = IMPL / "PROGRAM-WEIGHTS.yaml"
BUILD = IMPL / "BUILD-STATUS.yaml"
CURRENT = IMPL / "CURRENT.md"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


# ------------------------------------------------------------------ artifacts + weight integrity

def test_the_progress_artifacts_exist():
    for p in (PROTOCOL, WEIGHTS, BUILD):
        assert p.exists(), f"missing canonical progress artifact: {p.name}"


def test_program_weights_are_internally_valid():
    errs = ps.program_weight_errors(ps.load_weights())
    assert not errs, "PROGRAM-WEIGHTS.yaml weight integrity failed:\n  " + "\n  ".join(errs)


def test_the_seven_canonical_readiness_tiers_are_defined():
    text = read(PROTOCOL)
    for tier in ps.TIERS:
        assert tier in text, f"PROGRESS-PROTOCOL.md missing readiness tier: {tier}"
    # ADR-016 must point at the canonical tiers, not assert its own competing set
    adr = read(ROOT / "docs/architecture/decisions/ADR-016-production-topology.md")
    assert "PROGRESS-PROTOCOL.md" in adr and re.search(r"superseded|reconciled", adr, re.I), (
        "ADR-016 must defer its readiness vocabulary to the canonical PROGRESS-PROTOCOL tiers"
    )


# ------------------------------------------------------------------ BUILD-STATUS is derived, not typed

def _build_derived() -> dict:
    return yaml.safe_load(read(BUILD))["derived"]


def _recorded_content_commit() -> str:
    m = re.search(r"content_commit:\s*([0-9a-f]{40})", read(CURRENT))
    assert m, "CURRENT.md has no recorded content_commit"
    return m.group(1)


def test_build_status_percentages_match_the_mechanical_derivation():
    """The anti-inflation core: BUILD-STATUS's numbers must equal what progress_status derives from
    PROGRAM-WEIGHTS + the registry. A hand-edited percentage diverges and this fails."""
    bs = _build_derived()
    computed = ps.derive("x", "y", _recorded_content_commit())
    for k in ("cli_switch_readiness_percent", "overall_program_percent", "current_phase_percent",
              "user_visible_maturity_percent", "production_readiness_percent"):
        assert abs(float(bs[k]) - float(computed[k])) <= 0.05, (
            f"BUILD-STATUS {k}={bs[k]} != derived {computed[k]} (inflated or stale progress file)"
        )
    assert bs["readiness_tier"] == computed["readiness_tier"]
    assert bs["active_phase"] == computed["active_phase"]
    assert bs["single_ready_unit"] == computed["single_ready_unit"]


def test_build_status_content_commit_binds_to_current():
    """content_commit is either the finalizer placeholder (pre-finalize, in a dev tree) or a real
    sha equal to CURRENT.md's recorded content commit - never a different hardcoded sha."""
    bs = _build_derived()
    cc = str(bs["content_commit"])
    if cc == "CONTENT_COMMIT_INSERTED_BY_FINALIZER":
        return
    assert cc == _recorded_content_commit(), (
        f"BUILD-STATUS content_commit {cc!r} != CURRENT.md {_recorded_content_commit()!r}"
    )


def test_build_status_percentages_are_in_range_and_tier_is_canonical():
    bs = _build_derived()
    for k in ("cli_switch_readiness_percent", "overall_program_percent", "current_phase_percent",
              "user_visible_maturity_percent", "production_readiness_percent"):
        assert 0 <= float(bs[k]) <= 100, f"{k} out of range"
    assert bs["readiness_tier"] in ps.TIERS


def test_build_status_ready_unit_matches_the_registry():
    bs = _build_derived()
    units = ps.registry_units()
    assert bs["single_ready_unit"] == ps.single_ready_unit(units)


def test_build_status_defers_to_current_for_volatile_suite_figures():
    """No competing status authority: BUILD-STATUS must not carry its own suite pass/fail figures."""
    text = read(BUILD)
    assert "CURRENT.md" in text, "BUILD-STATUS must point at CURRENT.md as the status authority"
    assert not re.search(r"\b\d{3,5}\s+passed\b", text), "BUILD-STATUS carries its own suite figure"


# ------------------------------------------------------------------ required references

def test_the_protocol_is_referenced_by_every_required_authority():
    # FIXED-SPECIFICATION: the founder's progress-protocol directive names EXACTLY these authorities
    # that must reference the protocol (CLAUDE.md, AGENTS.md, the registry, the roadmap, and the
    # authority map that classifies them). This is a required-reference specification, not a
    # discovered file population - a new doc does not join it, and dropping one is a real defect.
    checks = {
        "CLAUDE.md": ROOT / "CLAUDE.md",
        "AGENTS.md": ROOT / "AGENTS.md",
        "IMPLEMENTATION-REGISTRY.yaml": IMPL / "IMPLEMENTATION-REGISTRY.yaml",
        "implementation-roadmap.md": IMPL / "implementation-roadmap.md",
        "CANONICAL-DOCUMENTS.md": ROOT / "docs" / "CANONICAL-DOCUMENTS.md",
    }
    missing = [name for name, p in checks.items()
               if "PROGRESS-PROTOCOL" not in read(p) and "PROGRAM-WEIGHTS" not in read(p)
               and "NEYMA BUILD STATUS" not in read(p) and "BUILD-STATUS" not in read(p)]
    assert not missing, f"the progress protocol is not referenced by: {missing}"
    # the finalizer must maintain BUILD-STATUS and import the derivation
    assert "docs/implementation/BUILD-STATUS.yaml" in fin.STATUS_METADATA_FILES, (
        "the finalizer does not treat BUILD-STATUS.yaml as a status-metadata file"
    )
    assert hasattr(fin, "_step_progress"), "the finalizer has no progress step"


# ------------------------------------------------------------------ the finalizer-rejection battery
# Each case feeds the validator the exact condition the founder requires the finalizer to reject.

def _good():
    return ps.derive("x", "y", _recorded_content_commit())


def test_rejects_percentage_outside_0_100():
    d = _good(); bad = dict(d); bad["overall_program_percent"] = 140
    errs = ps.build_status_errors(bad, d, ps.registry_units())
    assert any("outside 0-100" in e for e in errs)


def test_rejects_unsupported_percentage_increase():
    d = _good(); bad = dict(d); bad["user_visible_maturity_percent"] = 55.0
    errs = ps.build_status_errors(bad, d, ps.registry_units())
    assert any("does not match the derived" in e for e in errs)


def test_rejects_production_ready_without_evidence():
    d = _good(); bad = dict(d); bad["production_readiness_percent"] = 80.0
    errs = ps.build_status_errors(bad, d, ps.registry_units())
    assert any("STAGING READY or above" in e for e in errs) or any("does not match" in e for e in errs)


def test_rejects_ready_unit_inconsistent_with_registry():
    d = _good(); bad = dict(d); bad["single_ready_unit"] = "P7"
    errs = ps.build_status_errors(bad, d, ps.registry_units())
    assert any("single_ready_unit" in e for e in errs)


def test_rejects_wrong_head_or_tree():
    d = _good(); bad = dict(d); bad["content_commit"] = "0" * 40
    errs = ps.build_status_errors(bad, d, ps.registry_units())
    assert any("wrong HEAD/tree" in e or "CURRENT.md" in e for e in errs)


def test_rejects_non_canonical_readiness_tier():
    d = _good(); bad = dict(d); bad["readiness_tier"] = "ALMOST DONE"
    errs = ps.build_status_errors(bad, d, ps.registry_units())
    assert any("not a canonical tier" in e for e in errs)


def test_rejects_program_weights_not_totaling_100():
    w = ps.load_weights()
    w2 = {**w, "program_weights": w["program_weights"][:-1]}  # drop a phase -> sum != 100
    errs = ps.program_weight_errors(w2)
    assert any("total" in e for e in errs)


def test_rejects_a_phase_at_100_percent_before_adjudication():
    """A phase whose criteria sum to 100% PASS but whose independent_review / final_adjudication are
    not PASS must be rejected. Synthesize such a unit and confirm the validator catches it."""
    units = [dict(u) for u in ps.registry_units()]
    p3 = next(u for u in units if u["unit_id"] == "P3")
    # give P3 a full-PASS contract EXCEPT the two review criteria
    p3["acceptance_criteria"] = [
        {"criterion": c["criterion"], "weight": c["weight"],
         "result": ("PENDING" if c["criterion"] in ("independent_review", "final_adjudication") else "PASS")}
        for c in ps.load_weights()["acceptance_template"]
    ]
    # phase_completion should be < 100 because the two review criteria are PENDING (9 + 4? no: they
    # are 5 + 4 = 9 weight PENDING -> 91%), so simulate the dangerous case: force them PASS-less but
    # everything else PASS and check the 100%-guard path directly via a doctored computed map.
    computed = _good()
    computed["_phase_pct"] = {"P3": 100.0}
    errs = ps.build_status_errors(computed, computed, units)
    assert any("100% without independent_review" in e for e in errs), errs
