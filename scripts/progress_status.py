"""Mechanical progress derivation for the founder BUILD-STATUS system (U-REBASELINE-1).

Everything here is a PURE FUNCTION of committed evidence: PROGRAM-WEIGHTS.yaml (the approved
weights), the implementation registry (phase status + the single READY unit) and the per-phase
acceptance-criterion states. Nothing is estimated. See docs/implementation/PROGRESS-PROTOCOL.md.

Design contract (why the finalizer can trust these numbers):
  - a phase's completion is Sum(criterion weight where state==PASS) / 100; PENDING/IN_PROGRESS/
    FAIL/BLOCKED contribute 0 (PROGRESS-PROTOCOL.md sec 3).
  - overall = Sum(program_weight/100 * phase_completion) over the implementation phases.
  - a checklist percentage (cli-switch, production, user-visible) is Sum(weight where the item is
    at or above its required tier) / Sum(weight).
  - the finalizer WRITES the derived numbers into BUILD-STATUS.yaml and then VALIDATES the file,
    so a hand-inflated number cannot survive a finalize.
"""
from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS_RELPATH = "docs/implementation/PROGRAM-WEIGHTS.yaml"
BUILD_STATUS_RELPATH = "docs/implementation/BUILD-STATUS.yaml"
REGISTRY_RELPATH = "docs/implementation/IMPLEMENTATION-REGISTRY.yaml"

# The seven canonical readiness tiers, in order (PROGRESS-PROTOCOL.md sec 5).
TIERS = [
    "SPECIFIED", "LOCALLY IMPLEMENTED", "INTEGRATION TESTED", "STAGING READY",
    "SHADOW-PILOT READY", "SUPERVISED-PRODUCTION READY", "GENERALLY PRODUCTION READY",
]
# tolerate the underscore/no-space spelling used in YAML item tiers
_TIER_ALIASES = {
    "SPECIFICATION_ONLY": "SPECIFIED", "SPECIFIED": "SPECIFIED",
    "LOCALLY_IMPLEMENTED": "LOCALLY IMPLEMENTED", "LOCALLY IMPLEMENTED": "LOCALLY IMPLEMENTED",
    "INTEGRATION_TESTED": "INTEGRATION TESTED", "INTEGRATION TESTED": "INTEGRATION TESTED",
    "STAGING_READY": "STAGING READY", "STAGING READY": "STAGING READY",
    "SHADOW_PILOT_READY": "SHADOW-PILOT READY", "SHADOW-PILOT READY": "SHADOW-PILOT READY",
    "PILOT_READY": "SHADOW-PILOT READY",
    "SUPERVISED_PRODUCTION_READY": "SUPERVISED-PRODUCTION READY",
    "SUPERVISED-PRODUCTION READY": "SUPERVISED-PRODUCTION READY",
    "GENERALLY_PRODUCTION_READY": "GENERALLY PRODUCTION READY",
    "GENERALLY PRODUCTION READY": "GENERALLY PRODUCTION READY",
}
PASS_STATES = {"PASS"}  # only PASS contributes; see the protocol

PRODUCTION_MIN_TIER = "STAGING READY"          # production items count at STAGING+ (protocol sec 4)
USER_VISIBLE_MIN_TIER = "SHADOW-PILOT READY"   # user capabilities count at SHADOW-PILOT+ (protocol)


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def load_weights() -> dict:
    return yaml.safe_load(_read(WEIGHTS_RELPATH))


def _tier_index(tier: str) -> int:
    canon = _TIER_ALIASES.get(str(tier).strip())
    return TIERS.index(canon) if canon in TIERS else -1


# ------------------------------------------------------------------ weight-integrity checks

def _sum(items, key) -> int:
    return sum(int(i[key]) for i in items)


def program_weight_errors(w: dict) -> list[str]:
    errs = []
    pw = w.get("program_weights") or []
    total = _sum(pw, "program_weight")
    if total != 100:
        errs.append(f"program_weights total {total}, must be 100")
    phases = [p["phase"] for p in pw]
    expected = [f"P{i}" for i in range(3, 15)]
    if phases != expected:
        errs.append(f"program_weights phases {phases}, expected {expected}")
    for group in ("acceptance_template", "cli_switch_gates",
                  "production_readiness_checklist", "user_visible_checklist"):
        items = w.get(group) or []
        total = _sum(items, "weight")
        if total != 100:
            errs.append(f"{group} weights total {total}, must be 100")
    return errs


# ------------------------------------------------------------------ derived percentages

def checklist_percent(items: list[dict], min_tier: str) -> float:
    """Sum of weights at or above min_tier, over total weight, as a percent."""
    total = _sum(items, "weight") or 1
    need = _tier_index(min_tier)
    got = sum(int(i["weight"]) for i in items if _tier_index(i.get("readiness_tier", "SPECIFIED")) >= need)
    return round(100.0 * got / total, 1)


def status_checklist_percent(items: list[dict], done_states=("DONE",)) -> float:
    total = _sum(items, "weight") or 1
    got = sum(int(i["weight"]) for i in items if str(i.get("status", "")).upper() in done_states)
    return round(100.0 * got / total, 1)


def phase_completion(phase_id: str, w: dict, registry_units: list[dict]) -> float:
    """A phase's completion from its acceptance criteria. A phase whose criteria are not yet
    instantiated (the normal pre-start case) is 0.0 - code-not-written contributes nothing."""
    unit = next((u for u in registry_units if u["unit_id"] == phase_id), None)
    if not unit:
        return 0.0
    crits = unit.get("acceptance_criteria")  # optional per-phase committed weighted criteria
    if not crits:
        return 0.0
    total = sum(int(c["weight"]) for c in crits) or 1
    got = sum(int(c["weight"]) for c in crits if str(c.get("result", "PENDING")).upper() in PASS_STATES)
    return round(100.0 * got / total, 1)


def overall_program_percent(w: dict, registry_units: list[dict]) -> float:
    total = 0.0
    for p in w.get("program_weights") or []:
        total += (int(p["program_weight"]) / 100.0) * phase_completion(p["phase"], w, registry_units)
    return round(total, 1)


def registry_units() -> list[dict]:
    return yaml.safe_load(_read(REGISTRY_RELPATH))["units"]


def single_ready_unit(registry_units: list[dict]) -> str | None:
    ready = [u["unit_id"] for u in registry_units if u["status"] == "READY"]
    return ready[0] if len(ready) == 1 else None


def derive(head: str, tree: str, content_commit: str) -> dict:
    """Compute the full BUILD-STATUS snapshot from committed evidence. `content_commit` is the
    content baseline (== CURRENT.md's status block), following the two-commit convention."""
    w = load_weights()
    units = registry_units()
    prod = checklist_percent(w["production_readiness_checklist"], PRODUCTION_MIN_TIER)
    user = checklist_percent(w["user_visible_checklist"], USER_VISIBLE_MIN_TIER)
    cli = status_checklist_percent(w["cli_switch_gates"])
    overall = overall_program_percent(w, units)
    # active implementation phase = the lowest-numbered non-complete phase
    active_phase = "P3"
    for p in w["program_weights"]:
        u = next((x for x in units if x["unit_id"] == p["phase"]), None)
        if u and u["status"] != "COMPLETE":
            active_phase = p["phase"]
            break
    active_pct = phase_completion(active_phase, w, units)
    ready = single_ready_unit(units)
    # readiness tier of the canonical product = the highest tier reached by any implementation
    # phase; SPECIFIED while nothing is built.
    tier = "SPECIFIED"
    return {
        "content_commit": content_commit,
        "content_tree": tree,
        "active_phase": active_phase,
        "single_ready_unit": ready,
        "cli_switch_readiness_percent": cli,
        "overall_program_percent": overall,
        "current_phase_percent": active_pct,
        "user_visible_maturity_percent": user,
        "production_readiness_percent": prod,
        "readiness_tier": tier,
    }


# ------------------------------------------------------------------ finalizer-rejection validator

def build_status_errors(bs: dict, computed: dict, registry_units: list[dict]) -> list[str]:
    """The conditions the canonical finalizer must reject (PROGRESS-PROTOCOL.md sec 8)."""
    errs = []
    pct_keys = ["cli_switch_readiness_percent", "overall_program_percent",
                "current_phase_percent", "user_visible_maturity_percent",
                "production_readiness_percent"]
    for k in pct_keys:
        v = bs.get(k)
        if not isinstance(v, (int, float)) or not (0 <= v <= 100):
            errs.append(f"{k}={v!r} outside 0-100")
        elif abs(float(v) - float(computed[k])) > 0.05:
            # a hand-edited number that exceeds (or diverges from) the mechanically-derived value
            errs.append(f"{k}={v} does not match the derived {computed[k]} (unsupported / stale)")
    # readiness tier must be canonical
    if bs.get("readiness_tier") not in TIERS:
        errs.append(f"readiness_tier {bs.get('readiness_tier')!r} is not a canonical tier")
    # READY unit consistent with the registry
    ready = single_ready_unit(registry_units)
    if bs.get("single_ready_unit") != ready:
        errs.append(f"single_ready_unit {bs.get('single_ready_unit')!r} != registry {ready!r}")
    # no phase at 100% before its independent review + adjudication criteria PASS
    for p in load_weights().get("program_weights", []):
        pid = p["phase"]
        if computed.get("_phase_pct", {}).get(pid, phase_completion(pid, load_weights(), registry_units)) >= 100.0:
            unit = next((u for u in registry_units if u["unit_id"] == pid), None)
            crits = (unit or {}).get("acceptance_criteria") or []
            done = {c["criterion"]: str(c.get("result", "")).upper() for c in crits}
            if done.get("independent_review") != "PASS" or done.get("final_adjudication") != "PASS":
                errs.append(f"{pid} at 100% without independent_review + final_adjudication PASS")
    # production-ready claim needs evidence: production % > 0 requires at least one item >= STAGING
    if bs.get("production_readiness_percent", 0) > 0:
        w = load_weights()
        staged = [i for i in w["production_readiness_checklist"]
                  if _tier_index(i.get("readiness_tier", "SPECIFIED")) >= _tier_index(PRODUCTION_MIN_TIER)]
        if not staged:
            errs.append("production_readiness_percent > 0 with no item at STAGING READY or above")
    # HEAD/tree binding: content_commit must equal CURRENT.md's recorded content commit
    cur = _read("docs/implementation/CURRENT.md")
    import re
    m = re.search(r"content_commit:\s*([0-9a-f]{40})", cur)
    if m and bs.get("content_commit") != m.group(1):
        errs.append(f"content_commit {bs.get('content_commit')!r} != CURRENT.md {m.group(1)!r} (wrong HEAD/tree)")
    return errs


def render_report(bs: dict) -> str:
    """The NEYMA BUILD STATUS headline block (percentages + tier). Narrative bullets are authored
    by the session; this renders the mechanical header consistently."""
    return (
        "NEYMA BUILD STATUS\n\n"
        f"CLI switch readiness: {bs['cli_switch_readiness_percent']}%\n"
        f"Overall implementation program: {bs['overall_program_percent']}%\n"
        f"Current phase: {bs['active_phase']} — {bs['current_phase_percent']}%\n"
        f"User-visible product maturity: {bs['user_visible_maturity_percent']}%\n"
        f"Production readiness: {bs['production_readiness_percent']}%\n\n"
        f"Current readiness tier:\n{bs['readiness_tier']}\n"
    )
