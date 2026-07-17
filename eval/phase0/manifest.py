"""Load and validate the adjudicated baseline manifest.

The manifest is the only place a Phase-0 allowance may live, and every allowance must carry a
reason, a risk id, the phase that removes it, a deletion condition and an accountable unit. That is
enforced here, not by review etiquette: an allowance without a deletion condition is an indefinite
allowance wearing a temporary label.
"""

from __future__ import annotations

from functools import lru_cache

import yaml

from .sources import MANIFEST, require

REQUIRED_ALLOWANCE_FIELDS = ("reason", "removed_by_phase", "accountable_unit", "deletion_condition")


@lru_cache(maxsize=1)
def load() -> dict:
    return yaml.safe_load(require(MANIFEST).read_text(encoding="utf-8"))


def tables_not_tenant_first() -> set[str]:
    return set(load()["expected_noncanonical_schema"]["tables_not_tenant_first"])


def tables_tenant_first() -> set[str]:
    return set(load()["expected_noncanonical_schema"]["tables_tenant_first"])


def tables_tenant_exempt() -> set[str]:
    """Tables adjudicated as NOT tenant-owned. Each must justify itself like any other allowance."""
    return {e["table"] for e in load()["expected_noncanonical_schema"]["tables_tenant_exempt"]}


def allowed_adapter_import_edges() -> set[str]:
    return set(load()["adapter_import_allowlist"]["edges"])


def effect_capable_scripts() -> set[str]:
    return {e["script"] for e in load()["expected_legacy_paths"]["effect_capable_by_import"]}


def classified_references() -> dict[str, str]:
    return {
        e["script"]: e["classification"]
        for e in load()["expected_legacy_paths"]["references_to_effect_capable"]
    }


def deprecated_counts() -> dict[str, int]:
    return {t["term"]: t["count"] for t in load()["expected_deprecated_terms"]["terms"]}


def expected_failures() -> dict[str, str]:
    return {f["case"]: f["status"] for f in load()["expected_acceptance_failures"]}


def spec_counts() -> dict[str, int]:
    return load()["spec_counts"]


def allowance_sections() -> dict[str, list[dict]]:
    """Every section whose entries are allowances that must justify themselves."""
    m = load()
    return {
        "expected_current_defects": m["expected_current_defects"],
        "expected_acceptance_failures": [
            {**f, "removed_by_phase": f.get("green_at_phase"), "deletion_condition": f.get("reason")}
            for f in m["expected_acceptance_failures"]
        ],
        "expected_deprecated_terms": [
            {**t, "reason": m["expected_deprecated_terms"]["reason"],
             "deletion_condition": m["expected_deprecated_terms"]["deletion_condition"]}
            for t in m["expected_deprecated_terms"]["terms"]
        ],
    }


@lru_cache(maxsize=1)
def canonical_expected() -> dict:
    """The REGISTERED expected identifier sets — the second leg of the exact-set oracle."""
    from .sources import ROOT
    path = ROOT / "eval" / "phase0" / "canonical_expected.yaml"
    return yaml.safe_load(require(path).read_text(encoding="utf-8"))


def expected_transition_ids() -> set[str]:
    return {t for ids in canonical_expected()["transitions"].values() for t in ids}


def expected_event_names() -> set[str]:
    return {n for ns in canonical_expected()["emitted_events"].values() for n in ns}
