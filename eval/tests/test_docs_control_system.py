"""Executable guards over the documentation control system.

A control system made of prose decays silently: someone adds a module with no disposition, a
registry names a deleted file, a status drifts, or a stale roadmap quietly regains authority. These
guards fail the build instead.

Discipline carried from the implementation phases:
  - DISCOVER files, never enumerate filenames. This repository has produced a
    filename-enumeration blind spot four separate times.
  - Exact SETS, not counts. A same-count substitution must fail.
  - Every negative assertion runs over a PROVEN population.
  - Whole-token / structural matching, never bare substrings that fire on their own text.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
DOCS = ROOT / "docs"
IMPL = DOCS / "implementation"

PRODUCT = ROOT / "PRODUCT.md"
ARCHITECTURE = ROOT / "ARCHITECTURE.md"
CLAUDE = ROOT / "CLAUDE.md"
README = ROOT / "README.md"
AGENTS = ROOT / "AGENTS.md"
AUTHORITY_MAP = DOCS / "CANONICAL-DOCUMENTS.md"
CURRENT = IMPL / "CURRENT.md"
REGISTRY = IMPL / "IMPLEMENTATION-REGISTRY.yaml"
PHASE_OUTPUTS = IMPL / "PHASE-OUTPUTS.md"
LEGACY = IMPL / "LEGACY-DISPOSITION.md"
VALIDATION = DOCS / "product" / "OPEN-VALIDATION-ITEMS.md"
PARTNER = DOCS / "product" / "design-partner-observations.md"
GUIDANCE_REVIEW = IMPL / "AUTO-LOADED-GUIDANCE-REVIEW.md"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def require_population(items, what: str):
    assert items, f"no {what} to assert over - this test would pass vacuously"
    return items


def agent_files() -> list[Path]:
    """DISCOVERED. A new agent definition must not be able to arrive unbannered."""
    return sorted(ROOT.glob(".claude/agents/*.md")) + sorted(ROOT.glob(".codex/agents/*.md"))


def registry_units() -> list[dict]:
    return yaml.safe_load(read(REGISTRY))["units"]


def strip_historical(text: str) -> str:
    """Explicitly-labelled historical blocks may retain superseded claims IN PLACE. Everything
    outside them is live instruction. (Same rule as test_switch_consistency.strip_historical.)"""
    return re.sub(r"<details>.*?</details>", "", text, flags=re.S)


# ============================================================ 1-5. the required documents exist

@pytest.mark.parametrize(
    "path",
    [PRODUCT, ARCHITECTURE, CLAUDE, AUTHORITY_MAP, CURRENT, REGISTRY,
     PHASE_OUTPUTS, LEGACY, VALIDATION, PARTNER, GUIDANCE_REVIEW],
    ids=lambda p: p.name,
)
def test_1to5_required_control_document_exists_and_is_substantial(path: Path):
    assert path.exists(), f"required control document missing: {path}"
    assert len(read(path).split()) > 200, f"{path.name} is too thin to be a control document"


def test_4_there_is_exactly_one_current_status_authority():
    """Two files claiming to be 'the status' is how a repository ends up with three answers."""
    claimants = []
    for md in DOCS.rglob("*.md"):
        text = read(md)
        if re.search(r"THE (single|only) short-form current-status authority", text, re.I):
            claimants.append(md.relative_to(ROOT))
    assert [str(c) for c in claimants] == ["docs/implementation/CURRENT.md"], claimants


def test_5_there_is_exactly_one_implementation_registry():
    found = sorted(p.relative_to(ROOT) for p in IMPL.glob("IMPLEMENTATION-REGISTRY*"))
    assert [str(f) for f in found] == ["docs/implementation/IMPLEMENTATION-REGISTRY.yaml"], found


# ============================================================ 6-7. product identity

NOT_A = [
    "carrier-invoice processor", "document extraction service", "TMS chatbot",
    "collection of disconnected agents", "Slack interface over old workflows",
    "browser automation wrapper", "AP reconciliation tool",
    "invoice product with additional features",
]


def test_6_product_identity_rejects_the_invoice_processor_interpretation():
    text = read(PRODUCT)
    # U-REBASELINE-1 / ADR-012: the canonical identity sentence, verbatim
    assert ("AI-native operating platform and system of action for small and medium freight"
            in text), "PRODUCT.md lost the ADR-012 canonical identity statement"
    missing = [phrase for phrase in NOT_A if phrase.lower() not in text.lower()]
    assert not missing, f"PRODUCT.md does not explicitly reject: {missing}"


def test_6b_claude_md_also_rejects_it_because_agents_read_it_first():
    """The trailing `or "invoice processor" in text` this test used to carry made it
    unconditionally true - the phrase appears in any file that discusses the subject at all.
    Mutation caught it: replacing CLAUDE.md's product definition outright stayed green."""
    text = read(CLAUDE)
    # SECTION-SCOPED. Checking the whole file let the authoritative "Project identity" definition
    # be replaced outright while a passing mention survived elsewhere - mutation caught exactly
    # that. The definition must be in the section that declares it.
    section = re.search(r"## 2\. Project identity(.+?)\n## 3\.", text, re.S)
    assert section, "CLAUDE.md has no Project identity section"
    body = section.group(1)
    assert ("AI-native operating platform and system of action for small and medium freight"
            in body), \
        "CLAUDE.md section 2 no longer carries the ADR-012 canonical product definition"
    assert re.search(r"Neyma is NOT an invoice processor", body, re.I), \
        "CLAUDE.md section 2 must explicitly reject the invoice-processor reading"
    assert not re.search(r"Neyma (processes|handles|reconciles) (carrier )?invoices", body, re.I), \
        "CLAUDE.md section 2 defines the product as invoice work"


LOOPS = {
    "W1": "Quote", "W2": "Procurement", "W3": "Compliance", "W4": "Dispatch",
    "W5": "Tracking", "W6": "Documentation", "W7": "Exceptions", "W8": "Billing",
    "W9": "Settlement", "W10": "Customer Communications", "W11": "Claims",
}


def test_7_exactly_eleven_canonical_loops_present_as_an_exact_set():
    """Exact SET. A twelfth loop is a product decision, and a missing loop must fail."""
    text = read(PRODUCT)
    found = set(re.findall(r"\*\*(W\d{1,2})\*\*", text))
    assert found == set(LOOPS), f"loop set drifted: extra={found - set(LOOPS)}, missing={set(LOOPS) - found}"
    for wid, name in LOOPS.items():
        assert name in text, f"{wid} present but its name {name!r} is not"
    specs = sorted(p.name for p in (DOCS / "specifications" / "workflows").glob("W*.md"))
    assert len(specs) == 11, f"expected 11 workflow specs, found {len(specs)}: {specs}"


# ============================================================ 8-14. preserved status and findings

def test_8_phase_2_is_recorded_complete():
    text = read(CURRENT)
    assert re.search(r"\*\*P2\*\*.*COMPLETE", text), "CURRENT.md must record P2 COMPLETE"


def test_9_no_control_document_claims_a_phase_is_complete_before_the_registry_does():
    """REPLACES `test_9_phase_3_is_recorded_not_started` (P3).

    The original hardcoded one phase and one moment: P3 NOT STARTED. P3 has started, so the
    literal assertion became false and could only be deleted or inverted. Deleting it would drop
    the invariant it was really holding - that a control document must never run AHEAD of the
    registry - which is precisely the failure this replacement was written after observing: the
    working tree claimed 'P3 COMPLETE' while the registry still said READY, all 14 acceptance
    criteria still said PENDING, and the review it cited as evidence did not exist.

    Generalised and derived from the graph, so it protects every phase and cannot go stale:
    a document may only call a phase COMPLETE once the registry records it COMPLETE.
    """
    statuses = {u["unit_id"]: u["status"] for u in registry_units()}
    incomplete = sorted(u for u, s in statuses.items()
                        if s != "COMPLETE" and re.fullmatch(r"P\d+", u))
    assert incomplete, "no incomplete phases found - the guard would prove nothing"

    # POSITIVE status-declaration forms only. A broad "<unit> ... COMPLETE" window scan fires on
    # requirement prose ("Requires `P4` COMPLETE", "may not be recorded COMPLETE") - the guard
    # tripping over its own assertion text, which is the substring-guard defect CLAUDE.md names.
    # These patterns match a document ASSERTING completion, not one describing a precondition.
    def declarations(unit: str) -> list[str]:
        # BOTH spellings. A first version of this guard matched only the `P3` form and walked
        # straight past README.md's "**Implementation Phase 3** | ✅ COMPLETE" - the documents do
        # not agree on one spelling, so a guard that assumes one is a guard with a blind spot.
        n = re.fullmatch(r"P(\d+)", unit)
        alts = [re.escape(unit)] + ([rf"Phase\s+{n.group(1)}"] if n else [])
        u = f"(?:{'|'.join(alts)})"
        return [
            rf"\*\*{u}\*\*[^|\n]*\|[^|\n]*\bCOMPLETE\b",   # status-table row: | **P3** | COMPLETE |
            rf"\b{u}\b[^\n]{{0,40}}?✅\s*\**COMPLETE",       # ✅ COMPLETE badge
            rf"\b{u}`?\s+(?:is|was|are)\s+\**COMPLETE",     # "P3 is COMPLETE"
            rf"\b{u}`?\s*[—:-]\s*\**COMPLETE\b",            # "P3 — COMPLETE"
            rf"\b{u}\b[^.\n]{{0,60}}?\bdelivered\b",        # "Phase 3 delivered"
        ]

    offenders = []
    for path in (CURRENT, CLAUDE, README):
        text = strip_historical(read(path))
        for unit in incomplete:
            for pat in declarations(unit):
                for m in re.finditer(pat, text, re.I):
                    window = " ".join(m.group(0).split())
                    if re.search(r"\bNOT\b|never|may not|requires|until|once\b", window, re.I):
                        continue
                    offenders.append(f"{path.name}: {unit} -> {window[:110]!r}")
    assert not offenders, (
        "a control document declares a phase COMPLETE that the registry does not: "
        f"{offenders}"
    )


def test_10_r07_is_recorded_open_and_never_contained():
    """The manifest is the machine-checked record; the control documents must agree with it."""
    manifest = read(IMPL / "phase-0-baseline-manifest.yaml")
    assert "status: OPEN - NOT CONTAINED" in manifest, "the R-07 manifest record changed"
    assert not re.search(r"^\s*status:\s*CONTAINED", manifest, re.M), "R-07 was marked CONTAINED"
    for path in (CURRENT, CLAUDE, ARCHITECTURE, README):
        assert re.search(r"R-07.{0,120}OPEN", read(path), re.S), \
            f"{path.name} must record R-07 as OPEN"


@pytest.mark.parametrize(
    "pattern,label",
    [
        (r"\b6\b.{0,60}production-reachable live-write|six.{0,40}live-write", "6 live-write paths"),
        (r"\b31\b.{0,60}adapter-import|\b31\b.{0,60}adapter import", "31 adapter-import edges"),
        (r"(COUNT NEEDS ADJUDICATION|name no event outright)", "the transition/event completeness finding"),
        (r'tenant\s*=\s*.default.', "the knowledge-base default-tenant finding"),
    ],
    ids=["live_write", "adapter_imports", "event_less", "default_tenant"],
)
def test_11to14_open_findings_remain_recorded(pattern: str, label: str):
    """Each of these was a real finding. Losing one from the record is losing the finding.

    This originally accepted the finding appearing in ANY of three documents, so deleting it from
    the status authority stayed green because a copy survived in the README. The STATUS AUTHORITY
    is where an agent looks; it must carry every finding itself.
    """
    assert re.search(pattern, read(CURRENT), re.I | re.S), \
        f"{label} is no longer recorded in CURRENT.md - the status authority"
    holders = [p.name for p in (README, CLAUDE) if re.search(pattern, read(p), re.I | re.S)]
    assert holders, f"{label} is recorded nowhere an agent reads before CURRENT.md"


@pytest.mark.parametrize("path", [CURRENT, ARCHITECTURE, PHASE_OUTPUTS], ids=lambda p: p.name)
def test_phase_2_is_never_described_as_making_effects_safe(path: Path):
    """The most dangerous possible misreading of Phase 2.

    Concatenating the three documents let any ONE of them lose the statement silently. Each must
    carry it, because each is read on its own.
    """
    text = read(path)
    assert re.search(r"did NOT make (consequential )?external effects safe", text, re.I), \
        f"{path.name} must state explicitly that Phase 2 did not make effects safe"
    assert not re.search(r"Phase 2 made (consequential )?external effects safe", text, re.I), \
        f"{path.name} claims Phase 2 made external effects safe"


# ============================================================ 15-17. the registry

def test_15_the_registry_has_a_nonzero_exact_unit_population():
    units = require_population(registry_units(), "registry units")
    ids = [u["unit_id"] for u in units]
    assert len(ids) == len(set(ids)), f"duplicate unit ids: {ids}"
    assert len(units) >= 15, f"only {len(units)} units - the remaining programme is not represented"


def test_16_every_ready_unit_has_dependencies_and_acceptance():
    ready = [u for u in registry_units() if u["status"] == "READY"]
    require_population(ready, "READY units")
    for u in ready:
        assert "dependencies" in u, f"{u['unit_id']}: no dependencies key"
        assert u.get("acceptance_contract"), f"{u['unit_id']}: READY with no acceptance contract"
        assert u.get("prohibited_scope"), f"{u['unit_id']}: READY with no prohibited scope"


def test_17_no_unit_is_both_blocked_and_ready_and_exactly_one_is_ready():
    units = registry_units()
    valid = {"BLOCKED", "READY", "IN_PROGRESS", "COMPLETE"}
    bad = [(u["unit_id"], u["status"]) for u in units if u["status"] not in valid]
    assert not bad, f"invalid statuses (no ambiguous values allowed): {bad}"
    ready = [u["unit_id"] for u in units if u["status"] == "READY"]
    assert len(ready) == 1, f"exactly one unit may be READY, found {ready}"


def test_registry_dependencies_all_exist_and_completed_units_have_evidence():
    units = registry_units()
    ids = {u["unit_id"] for u in units}
    for u in units:
        for dep in u.get("dependencies", []):
            assert dep in ids, f"{u['unit_id']} depends on unknown unit {dep}"
        if u["status"] == "COMPLETE":
            assert u.get("completion_evidence"), f"{u['unit_id']} is COMPLETE with no evidence"
        if u["status"] == "BLOCKED":
            deps = [d for d in u.get("dependencies", [])]
            assert deps or u.get("validation_blockers"), \
                f"{u['unit_id']} is BLOCKED by nothing - what unblocks it?"


# ============================================================ 18-19. legacy dispositions

DISPOSITIONS = {"KEEP", "ADAPT", "REWRITE", "MAKE_READ_ONLY", "QUARANTINE", "DELETE"}


def test_18_every_production_module_has_a_disposition():
    """DISCOVERED from the filesystem: a new module cannot arrive without a disposition."""
    doc = read(LEGACY)
    named = set(re.findall(r"`([a-z_0-9]+\.py)`", doc))
    actual = {p.name for p in (ROOT / "src" / "freight_recon").glob("*.py")}
    require_population(actual, "production modules")
    missing = sorted(actual - named)
    assert not missing, f"production modules with no disposition: {missing}"


def test_19_no_permanent_ambiguous_legacy_disposition_exists():
    doc = read(LEGACY)
    found = require_population(
        set(re.findall(r"\*\*(" + "|".join(DISPOSITIONS) + r")\*\*", doc)),
        "dispositions in the registry",
    )
    assert found <= DISPOSITIONS, f"unknown dispositions: {found - DISPOSITIONS}"
    banned = ["LEGACY_BUT_ACTIVE_FOREVER", "PERMANENT_LEGACY", "KEEP_FOREVER", "INDEFINITE"]
    present = [b for b in banned if b in doc.upper()and f"no permanent category equivalent to" not in doc.lower()]
    hits = [b for b in banned if re.search(rf"\*\*{b}\*\*", doc, re.I)]
    assert not hits, f"a permanent ambiguous legacy disposition appeared: {hits}"


def test_no_module_is_kept_merely_for_being_large_or_tested():
    doc = read(LEGACY)
    assert re.search(r"KEEP.{0,200}(not|never).{0,80}(large|tested)", doc, re.I | re.S) or \
        re.search(r"(not|never).{0,80}(large|old|working|tested).{0,200}KEEP", doc, re.I | re.S), \
        "LEGACY-DISPOSITION.md must state that KEEP is not awarded for size, age or test coverage"


# ============================================================ 20. validation items

def test_20_every_unresolved_consequential_rule_has_a_safe_interim_behaviour():
    doc = read(VALIDATION)
    ids = require_population(re.findall(r"### (V-[A-Z0-9]+)", doc), "validation items")
    blocks = re.split(r"### V-[A-Z0-9]+", doc)[1:]
    assert len(blocks) == len(ids)
    missing = [i for i, b in zip(ids, blocks) if "interim behaviour" not in b.lower()]
    assert not missing, f"validation items with no safe interim behaviour: {missing}"
    assert re.search(r"fail closed", doc, re.I), "the fail-closed default must be stated"


# ============================================================ 21-23. guidance and authority

def test_21_auto_loaded_guidance_points_at_the_canonical_root_documents():
    files = require_population(agent_files() + [README, AGENTS], "auto-loaded guidance files")
    for f in files:
        text = read(f)
        assert "CLAUDE.md" in text, f"{f.relative_to(ROOT)} does not point at CLAUDE.md"
        assert "CURRENT.md" in text or "PRODUCT.md" in text, \
            f"{f.relative_to(ROOT)} points at no canonical status or product document"


def test_22_no_auto_loaded_file_defines_invoice_processing_as_the_final_product():
    """Structural: a stale definition is one that asserts the product IS invoice work.

    Naming invoice work is legitimate - the repository does invoice work, and PRODUCT.md must be
    able to say so in order to reject it. What is banned is the DEFINING form.
    """
    defining = [
        r"(?:Neyma|The product|the repo(?:sitory)?) is (?:a |an )?(?:carrier[- ])?invoice",
        r"(?:Neyma|The product) is (?:a |an )?(?:document extraction|AP reconciliation)",
        r"The (?:final |long-term )?product is (?:a |an )?(?:carrier[- ])?invoice",
    ]
    # A line that REJECTS the invoice reading contains the same words as one that ASSERTS it.
    # Matching on the words alone makes this guard fire on its own rejection text - which it did,
    # on the first run, in CLAUDE.md. The distinguishing feature is the surrounding negation, so
    # that is what is checked.
    rejecting = re.compile(
        r"\bnot\b|\bnever\b|\bstale\b|\breject|\bsuperseded\b|\bwrong\b|\bhistorical\b"
        r"|\bpreviously\b|\bused to\b|\bif any\b|\btells you\b|⛔",
        re.I,
    )
    offenders = []
    for f in require_population(agent_files() + [README, AGENTS, CLAUDE, PRODUCT], "guidance files"):
        text = read(f)
        lines = text.split("\n")
        for pat in defining:
            for m in re.finditer(pat, text, re.I):
                idx = text[: m.start()].count("\n")
                context = " ".join(lines[max(0, idx - 1): idx + 2])
                if rejecting.search(context):
                    continue
                offenders.append(f"{f.relative_to(ROOT)}:{idx + 1}: {m.group(0)!r}")
    assert not offenders, f"auto-loaded files defining the product as invoice processing: {offenders}"


def test_22b_every_agent_definition_carries_a_supersession_banner():
    files = require_population(agent_files(), "agent definitions")
    missing = [str(f.relative_to(ROOT)) for f in files if "SUPERSEDED STATUS" not in read(f)]
    assert not missing, f"agent definitions with no supersession banner: {missing}"


def test_22c_agents_md_defers_to_claude_md_and_declares_no_status_of_its_own():
    text = read(AGENTS)
    assert re.search(r"CLAUDE\.md.{0,80}(outranks|not the operating guide)", text, re.I | re.S), \
        "AGENTS.md must defer to CLAUDE.md"
    assert not re.search(r"Stage [1-8][^0-9]{0,40}(IN PROGRESS|Human Review|current)", text, re.I), \
        "AGENTS.md still carries a stage-based status claim"


def test_23_historical_documents_cannot_outrank_canonical_files():
    amap = read(AUTHORITY_MAP)
    for level in ["CANONICAL", "CURRENT_STATUS", "IMPLEMENTATION_CONTROL", "ACCEPTANCE_ORACLE",
                  "EVIDENCE", "HISTORICAL", "SUPERSEDED", "NEEDS_VALIDATION", "QUARANTINED_GUIDANCE"]:
        assert level in amap, f"authority map is missing the {level} level"
    assert re.search(r"No .?HISTORICAL.? document ever outranks", amap, re.I), \
        "the authority map must state the precedence rule explicitly"
    # The superseded roadmap must be named as superseded, in the map AND in what replaced it.
    assert "PRODUCT_ROADMAP.md" in amap and "SUPERSEDED" in amap
    assert re.search(r"8-stage roadmap.{0,120}SUPERSEDED", read(PHASE_OUTPUTS), re.I | re.S), \
        "PHASE-OUTPUTS.md must mark the 8-stage roadmap superseded"


def test_23b_every_root_control_document_appears_in_the_authority_map():
    amap = read(AUTHORITY_MAP)
    for p in [PRODUCT, ARCHITECTURE, CLAUDE, CURRENT, REGISTRY, PHASE_OUTPUTS, LEGACY,
              VALIDATION, PARTNER, README, AGENTS]:
        assert p.name in amap, f"{p.name} is not classified in the authority map"


# ============================================================ 24. the next approved work

def test_24_the_next_approved_work_is_p3_with_every_gate_closed():
    """REPLACED at the P4 ACCEPTANCE/STATUS CLOSURE (CLAUDE.md section 5 rule 20 - replaced, not
    deleted; second replacement of this body).

    The function NAME is frozen to preserve its node identity in TEST-NODE-MANIFEST.json (the same
    convention as test_24b); the BODY asserts the post-adjudication truth. P4 has now been
    adjudicated COMPLETE from independent evidence, so the single READY unit is P5. The durable
    invariants are preserved and re-pointed: an ADJUDICATED phase is COMPLETE only with all 14
    weighted criteria PASS - including independent_review and final_adjudication, which its own
    author structurally cannot supply - and the READY unit's gate ancestry stays closed on
    independent evidence. Both adjudicated phases are now checked, so re-pointing the guard did
    not drop P3's coverage."""
    units = registry_units()
    assert units, "the registry parsed to no units - every assertion here would be vacuous"
    by_id = {u["unit_id"]: u for u in units}
    ready = [u for u in units if u["status"] == "READY"]
    assert len(ready) == 1, f"exactly one unit may be READY, found {[u['unit_id'] for u in ready]}"
    the_ready = ready[0]
    assert the_ready["unit_id"] == "P5", f"the READY unit is {the_ready['unit_id']}, expected P5"

    # An adjudicated phase is COMPLETE ONLY on a fully-PASS weighted contract summing to 100 whose
    # independent_review + final_adjudication were supplied by a session other than the author.
    for phase_id in ("P3", "P4"):
        phase = by_id[phase_id]
        assert phase["status"] == "COMPLETE", f"{phase_id} is {phase['status']}, expected COMPLETE"
        crits = phase.get("acceptance_criteria")
        assert crits, f"{phase_id} has no weighted acceptance contract"
        assert sum(int(c["weight"]) for c in crits) == 100, (
            f"{phase_id} acceptance weights must total 100"
        )
        results = {c["criterion"]: str(c["result"]).upper() for c in crits}
        assert results.get("independent_review") == "PASS" and results.get("final_adjudication") == "PASS", (
            f"{phase_id} COMPLETE without independent_review + final_adjudication PASS - a "
            "self-adjudicated completion is exactly what this guard exists to forbid"
        )
        unpassed = sorted(k for k, v in results.items() if v != "PASS")
        assert not unpassed, f"{phase_id} is COMPLETE while these criteria are not PASS: {unpassed}"

    # every gate ancestor of the READY unit must be COMPLETE - P5 may not be READY on an open gate
    assert the_ready["dependencies"], "the READY unit records no dependencies"
    for dep in the_ready["dependencies"]:
        assert by_id[dep]["status"] == "COMPLETE", (
            f"P5 is READY while dependency {dep} is {by_id[dep]['status']}"
        )
    # the closed gates that let P3 begin still carry their independent-review evidence
    p3 = by_id["P3"]
    for gate in ("U-HANDOFF-1", "U-REBASELINE-1"):
        assert gate in p3["dependencies"], f"P3 lost its {gate} gate dependency"
        evidence = " ".join(str(x) for x in by_id[gate]["completion_evidence"])
        assert "independent" in evidence.lower() or "u-handoff-2b" in evidence.lower(), (
            f"{gate} is COMPLETE without independent-review evidence recorded"
        )
    reb = " ".join(str(x) for x in by_id["U-REBASELINE-1"]["completion_evidence"])
    assert "u-rebaseline-review-1-independent-report.md" in reb, (
        "U-REBASELINE-1 COMPLETE without the preserved independent review report"
    )
    # P4 must still prohibit the NEXT phase's work (events, P5) - the safety wall does not collapse
    # just because P4 finished. A completed phase's prohibited_scope is history that stays true.
    p4_prohibited = " ".join(str(x) for x in by_id["P4"]["prohibited_scope"]).lower()
    assert "events" in p4_prohibited, "P4 must still record that it prohibited P5 (events) work"
    # and the READY unit must in turn prohibit the phase AFTER it
    ready_prohibited = " ".join(str(x) for x in the_ready["prohibited_scope"]).lower()
    assert "entities" in ready_prohibited, "P5 must prohibit P6 (entities) work"
    assert re.search(r"P5", read(CURRENT)), "CURRENT.md must name the next approved program"


def test_24b_the_current_status_file_forbids_the_phase_after_the_ready_one():
    """REPLACED by U-REBASELINE-1B (not deleted - CLAUDE.md section 5 rule 20). This guard used to
    require CURRENT.md to forbid beginning Phase 3. P3 is now the APPROVED READY unit, so that
    prohibition is exactly what must NOT be there any more; the guard would have pinned an obsolete
    instruction. The durable invariant is: CURRENT.md forbids the phase AFTER the READY one, and
    states that the READY phase is not thereby implemented."""
    text = read(CURRENT)
    ready = [u["unit_id"] for u in registry_units() if u["status"] == "READY"]
    assert len(ready) == 1
    m = re.fullmatch(r"P(\d+)", ready[0])
    if not m:
        # a non-phase unit is READY: the old rule applies unchanged - P3 must still be forbidden
        assert re.search(r"(must NOT begin|Not yet).{0,400}Phase 3", text, re.I | re.S), \
            "CURRENT.md must explicitly forbid beginning Phase 3"
        return
    nxt = f"Phase {int(m.group(1)) + 1}"
    assert re.search(rf"(must NOT begin|Not yet).{{0,600}}{re.escape(nxt)}", text, re.I | re.S), \
        f"CURRENT.md must explicitly forbid beginning {nxt} (the phase after the READY {ready[0]})"
    # P3 UPDATE (rule 20 again - this guard has been replaced once already, by U-REBASELINE-1B).
    # The old assertion required "READY ... NOT IMPLEMENTED", which held only while no READY unit
    # had any code behind it. P3 is now implemented AND still READY, because implementation is not
    # adjudication: its independent_review and final_adjudication criteria remain PENDING. So the
    # durable statement CURRENT.md must carry is the one that is still true and still load-bearing
    # - READY does not mean COMPLETE - rather than one that is now simply false.
    assert re.search(rf"{re.escape(ready[0])}\b.{{0,120}}NOT COMPLETE", text, re.I | re.S), \
        f"CURRENT.md must state that {ready[0]} being READY does not mean it is COMPLETE"


# ============================================================ 25. no placeholders presented as fact

def test_25_no_required_document_contains_unresolved_placeholder_text():
    placeholders = [r"\bTBD\b", r"\bTODO\b", r"\bFIXME\b", r"\bXXX\b",
                    r"<placeholder", r"\bLOREM\b", r"FILL ME", r"_DIGEST\b"]
    offenders = []
    for path in [PRODUCT, ARCHITECTURE, CLAUDE, AUTHORITY_MAP, CURRENT, PHASE_OUTPUTS,
                 LEGACY, VALIDATION, PARTNER, GUIDANCE_REVIEW, README, AGENTS]:
        text = read(path)
        for pat in placeholders:
            for m in re.finditer(pat, text, re.I):
                line = text[: m.start()].count("\n") + 1
                offenders.append(f"{path.name}:{line}: {m.group(0)!r}")
    assert not offenders, f"placeholder text presented as fact: {offenders}"


# ============================================================ link integrity

def test_internal_markdown_links_resolve():
    """No internet access required: every relative link must exist on disk."""
    checked = 0
    broken = []
    for path in [PRODUCT, ARCHITECTURE, CLAUDE, AUTHORITY_MAP, CURRENT, PHASE_OUTPUTS,
                 LEGACY, VALIDATION, PARTNER, GUIDANCE_REVIEW, README, AGENTS]:
        text = read(path)
        for m in re.finditer(r"\[[^\]]+\]\(([^)#]+?)\)", text):
            target = m.group(1).strip()
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            checked += 1
            resolved = (path.parent / target).resolve()
            if not resolved.exists():
                line = text[: m.start()].count("\n") + 1
                broken.append(f"{path.name}:{line} -> {target}")
    assert checked > 50, f"only {checked} internal links checked - the scan is not covering the docs"
    assert not broken, f"broken internal links: {broken}"


def test_the_authority_chain_has_a_root_and_no_circular_authority():
    amap = read(AUTHORITY_MAP)
    assert "engineering-principles.md" in amap
    assert re.search(r"chain has a root|authorised by nothing above it", amap, re.I), \
        "the authority map must name the root of the chain"


def test_no_control_document_claims_the_w6_w8_slice_is_validated():
    """The provisional first slice must never be promoted by accident."""
    for path in (PRODUCT, PHASE_OUTPUTS, CURRENT):
        text = read(path)
        if "W6" in text and "W8" in text:
            assert re.search(r"(NEEDS DESIGN-PARTNER VALIDATION|provisional|UNVALIDATED)", text, re.I), \
                f"{path.name} names the W6->W8 slice without marking it provisional"


# ============================================================ the invariants that may never weaken

# Each entry: (label, a pattern asserting the rule, a pattern that must NOT appear).
# Mutation found that NONE of these were guarded: the 11 architecture rules and the 20
# non-negotiable engineering rules could be inverted in place and every test stayed green. A
# control system that states rules but cannot notice them being reversed is documentation, not
# control.
INVARIANTS = [
    ("events are facts, never authority",
     r"[Ee]vents are (facts|FACTS)[^.]{0,80}never",
     r"[Ee]vents (may|can) (grant|carry) (execution )?authority"),
    ("replay cannot mint authority",
     r"[Rr]eplay cannot mint authority",
     r"[Rr]eplay (may|can) mint"),
    ("replay cannot invoke adapters",
     r"[Rr]eplay cannot (invoke|call) (external )?adapters",
     r"[Rr]eplay (may|can) (invoke|call) (external )?adapters"),
    ("MODEL_INFERRED cannot authorise",
     r"`?MODEL_INFERRED`? (facts )?cannot independently authorise",
     r"`?MODEL_INFERRED`? (facts )?(may|can) authorise"),
    ("OWNER_ASSERTED cannot be overwritten",
     r"`?OWNER_ASSERTED`? (facts )?cannot be silently overwritten",
     r"`?OWNER_ASSERTED`? (facts )?(may|can) be (silently )?overwritten"),
    ("timeout never means FAILED",
     r"[Tt]imeout alone never (means|becomes) `?FAILED",
     r"[Tt]imeout (means|becomes) `?FAILED"),
    ("every obligation has an accountable human",
     r"[Ee]very (open |unresolved )?(operational )?obligation has (one|an) accountable human",
     r"obligations? (may|can) (be unowned|have no owner)"),
    ("the brake controls admission, not termination",
     r"[Bb]rake controls (ADMISSION|admission)[^.]{0,60}not[^.]{0,40}termination",
     r"[Bb]rake (terminates|kills) (running )?workers"),
    ("one canonical effect authority",
     r"[Oo]ne canonical effect authority",
     r"[Aa] second effect (table|ledger) is acceptable"),
    ("no permanent second orchestration system",
     r"[Nn]o permanent (second|dual) orchestration",
     r"permanent (second|dual) orchestration (system )?is (fine|acceptable)"),
    ("no permanent second effect-authority system",
     r"[Nn]o permanent (second|dual) effect-authority",
     r"permanent (second|dual) effect-authority (system )?is (fine|acceptable)"),
    ("Commit Key is not Material Facts",
     r"Commit Key (≠|!=|is not the same as|and Material Facts are different)",
     r"Commit Key and Material Facts are the same"),
]


@pytest.mark.parametrize("label,present,absent", INVARIANTS, ids=[i[0] for i in INVARIANTS])
def test_the_invariants_that_may_never_weaken_are_stated_and_not_reversed(label, present, absent):
    """Asserted across the two documents that carry the rules, and checked BOTH ways.

    Asserting only that the rule is present is not enough: the reversed form can be added
    alongside it. Both directions are checked.
    """
    corpus = {"ARCHITECTURE.md": read(ARCHITECTURE), "CLAUDE.md": read(CLAUDE)}
    stated = [name for name, text in corpus.items() if re.search(present, text)]
    assert stated, f"the invariant {label!r} is stated in neither ARCHITECTURE.md nor CLAUDE.md"
    reversed_in = [name for name, text in corpus.items() if re.search(absent, text, re.I)]
    assert not reversed_in, f"the invariant {label!r} appears REVERSED in {reversed_in}"


def test_the_full_non_negotiable_rule_list_is_present_and_numbered():
    """A rule silently dropped from the list is a rule nobody will follow."""
    text = read(CLAUDE)
    section = re.search(r"## 5\. Non-negotiable engineering rules(.+?)\n## 6\.", text, re.S)
    assert section, "CLAUDE.md has no non-negotiable engineering rules section"
    numbered = re.findall(r"^\d+\. ", section.group(1), re.M)
    assert len(numbered) >= 20, f"only {len(numbered)} non-negotiable rules remain, expected >= 20"


def test_architecture_states_the_rules_that_may_never_be_weakened():
    text = read(ARCHITECTURE)
    section = re.search(r"## The rules that may never be weakened(.+)$", text, re.S)
    assert section, "ARCHITECTURE.md no longer carries the never-weaken rule list"
    numbered = re.findall(r"^\d+\. ", section.group(1), re.M)
    assert len(numbered) == 11, f"expected 11 never-weaken rules, found {len(numbered)}"


def test_the_two_key_rule_is_stated(): 
    """A grant alone must never be sufficient. This is the keystone of ADR-004."""
    text = read(ARCHITECTURE)
    assert re.search(r"necessary but[^.]{0,20}NOT sufficient", text, re.I), \
        "ARCHITECTURE.md must state that a grant is necessary but not sufficient"
    assert re.search(r"[Cc]heckpoint [Ww]itness", text), "the Checkpoint Witness is not described"


def test_the_amount_is_recorded_as_absent_from_the_commit_key():
    """The Phase-1 correction. If the documents stop saying it, the next agent puts it back."""
    text = read(ARCHITECTURE)
    assert re.search(r"amount is (NOT|not) in the Commit Key", text, re.I), \
        "ARCHITECTURE.md must record that the amount is not in the Commit Key"


# ============================================================ design-partner evidence integrity

def test_the_absence_of_firsthand_design_partner_observation_is_recorded():
    """The most dangerous documentation drift available: inference presented as observation."""
    text = read(PARTNER)
    assert re.search(r"NO firsthand design-partner observation", text, re.I), \
        "the design-partner record no longer states that no firsthand observation exists"
    directly = re.search(r"## 1\. DIRECTLY OBSERVED(.+?)## 2\.", text, re.S)
    assert directly, "the DIRECTLY OBSERVED section is gone"
    assert re.search(r"NONE", directly.group(1)), \
        "the DIRECTLY OBSERVED section now claims content - an agent may not upgrade evidence class"
    assert re.search(r"founder-operated test brokerage|not an independent (customer|brokerage)", text, re.I), \
        "the record must state that the 'first design partner' is a founder-operated test entity"


def test_every_evidence_class_is_defined_and_says_whether_it_may_authorise():
    text = read(PARTNER)
    for cls in ["DIRECTLY OBSERVED", "REPORTED BY DESIGN PARTNER", "RELAYED BY FOUNDER",
                "EXTERNAL RESEARCH", "ARCHITECTURAL INFERENCE", "NEEDS VALIDATION"]:
        assert cls in text, f"evidence class {cls!r} is missing"


# ============================================================ authority-map integrity

def _superseded_docs() -> list[str]:
    """DISCOVERED from the authority map's own SUPERSEDED/QUARANTINED rows (H-6): a newly
    superseded document enters this population without touching the guard."""
    import sys as _s
    _s.path.insert(0, str(ROOT / "eval"))
    from control import inventory as _inv
    names = sorted({p.rsplit("/", 1)[-1]
                    for p in _inv.classified(("SUPERSEDED", "QUARANTINED_GUIDANCE"))})
    assert len(names) >= 4, f"superseded population collapsed: {names}"
    return names


@pytest.mark.parametrize("doc", _superseded_docs())
def test_pre_reset_documents_cannot_regain_canonical_authority(doc: str):
    """Row-scoped, not file-scoped.

    Checking only that the word SUPERSEDED appears somewhere in the authority map let a row be
    flipped to CANONICAL while the word survived elsewhere - mutation caught exactly that.
    """
    amap = read(AUTHORITY_MAP)
    # Only rows where the document is the SUBJECT (first column). A CANONICAL document's
    # "Supersedes" column legitimately names these files, and counting those rows made this
    # guard fail on correct content.
    rows = []
    for ln in amap.split("\n"):
        if not ln.strip().startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if cells and doc in cells[0]:
            rows.append(ln)
    assert rows, f"{doc} is no longer classified in the authority map as a subject row"
    for row in rows:
        assert not re.search(r"\|\s*\*{0,3}CANONICAL", row), \
            f"{doc} was reclassified CANONICAL: {row.strip()[:120]}"
        assert re.search(r"SUPERSEDED|QUARANTINED_GUIDANCE|HISTORICAL", row), \
            f"{doc} lost its superseded classification: {row.strip()[:120]}"


# ============================================================ implemented-vs-specified registry

SURFACE = IMPL / "IMPLEMENTATION-SURFACE.yaml"
SRC = ROOT / "src" / "freight_recon"

REQUIRED_CONCEPTS = {
    "Tenant", "Commit Key", "Material Facts", "Effect Grant ledger (foundation)",
    "Checkpoint (seven-step)", "Checkpoint Witness", "Effect claim CAS",
    "Adapter containment boundary (P4)", "Work Item",
    "Pipeline Instance", "Expectation", "Obligation", "Evidence (content-addressed)",
    "Provenance classes", "Policy (typed, compile-or-refuse)", "Brake (admission control)",
    "Canonical events (98 contracts)", "Outbox / inbox", "Replay isolation",
    "Reconciliation (canonical)", "The eleven operational loops",
    # U-REBASELINE-1: the wedge slice renamed, plus the five rebaseline surface concepts
    'Delivered Load Closure shadow slice (formerly "first vertical slice W6 -> W8")',
    "Communications subsystem (ingestion + governed sends)",
    "Production deployment topology (PostgreSQL, workers, object storage, secrets)",
    "Web control plane and tenant/integration lifecycle",
    "Workflow-authority migration model",
    "Customer Operational System Map (TMS-agnostic operational graph)",
    "Conversational layer channel stores (one conversation, no per-channel memory)",
}
SURFACE_STATUSES = {"IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "SPECIFICATION_ONLY",
                    "LEGACY_IMPLEMENTATION", "BLOCKED"}


def surface_concepts() -> list[dict]:
    return yaml.safe_load(read(SURFACE))["concepts"]


def _src_contains_symbol(symbol: str) -> bool:
    pat = re.compile(rf"\b{re.escape(symbol)}\b")
    for f in SRC.rglob("*.py"):
        if pat.search(f.read_text(encoding="utf-8")):
            return True
    return False


def test_surface_registry_covers_the_exact_required_concept_set():
    names = {c["name"] for c in surface_concepts()}
    assert names == REQUIRED_CONCEPTS, (
        f"concept set drifted: extra={names - REQUIRED_CONCEPTS}, missing={REQUIRED_CONCEPTS - names}"
    )
    for c in surface_concepts():
        assert c["status"] in SURFACE_STATUSES, f"{c['name']}: invalid status {c['status']!r}"
        assert c.get("specification"), f"{c['name']}: no canonical specification link"
        assert (ROOT / c["specification"]).exists(), f"{c['name']}: spec {c['specification']} missing"
        assert c.get("owning_unit"), f"{c['name']}: no owning work unit"


def test_implemented_concepts_cite_evidence_that_actually_exists():
    """A concept may claim IMPLEMENTED only with living evidence - file AND symbol."""
    checked = 0
    for c in surface_concepts():
        if c["status"] not in {"IMPLEMENTED", "PARTIALLY_IMPLEMENTED", "LEGACY_IMPLEMENTATION"}:
            continue
        assert c.get("evidence"), f"{c['name']} claims {c['status']} with no evidence"
        for ev in c["evidence"]:
            path = ROOT / ev["path"]
            assert path.exists(), f"{c['name']}: evidence file {ev['path']} does not exist"
            assert re.search(rf"\b{re.escape(ev['symbol'])}\b", path.read_text(encoding="utf-8")), (
                f"{c['name']}: symbol {ev['symbol']!r} not found in {ev['path']} - "
                "the registry presents unimplemented work as implemented"
            )
            checked += 1
    assert checked >= 8, f"only {checked} evidence citations verified - population too small"


def test_specification_only_concepts_are_verifiably_absent_from_src():
    """The inverse direction: SPECIFICATION_ONLY must stay true. If someone implements a
    CheckpointWitness without updating this registry (or marks it spec-only while it exists),
    this fails. This is the guard the rehearsal had to substitute with hand-run greps."""
    checked = 0
    for c in surface_concepts():
        if c["status"] not in {"SPECIFICATION_ONLY", "BLOCKED"}:
            continue
        symbols = c.get("absent_symbols")
        assert symbols, f"{c['name']} is {c['status']} but names no absent_symbols to verify"
        for sym in symbols:
            assert not _src_contains_symbol(sym), (
                f"{c['name']} is recorded {c['status']} but {sym!r} exists in src/ - either the "
                "registry is stale or unapproved implementation landed"
            )
            checked += 1
    assert checked >= 15, f"only {checked} absence checks ran - population too small"


def test_a_concept_is_implemented_only_when_its_owning_unit_ran_and_its_symbols_exist():
    """REPLACES `test_the_p3_concepts_are_specification_only_while_p3_is_blocked` (P3).

    The original keyed on `p3_status in {BLOCKED, READY}`, which silently equated READY with
    NOT-BEGUN. That held only while no phase had ever been mid-flight. P3 is now implemented but
    NOT adjudicated COMPLETE - its independent_review and final_adjudication criteria are still
    PENDING - so it is legitimately READY with real code behind it, and the old guard could only
    be satisfied by lying in one direction or the other.

    The surface file records CODE REALITY, so the replacement checks code reality against the
    graph, which is strictly stronger than the rule it replaces:

      * a concept owned by a BLOCKED unit must still be SPECIFICATION_ONLY - work cannot exist
        before the unit that owns it is even permitted to start (the real safety property);
      * a concept claiming IMPLEMENTED must produce its evidence symbols in src/ - the claim is
        checked against the tree rather than trusted.
    """
    units = {u["unit_id"]: u["status"] for u in registry_units()}
    checked = 0
    for c in surface_concepts():
        owner = c.get("owning_unit")
        status = c["status"]
        if owner in units and units[owner] == "BLOCKED":
            # PARTIALLY_IMPLEMENTED is legitimate here and deliberately allowed: an earlier phase
            # routinely lays groundwork a later unit completes - `ProvenanceClass` exists for
            # checkpoint step 3 while the full provenance system remains P7. What may NOT happen
            # is a BLOCKED unit's concept claiming to be FULLY implemented, because that would
            # mean the unit effectively ran without ever becoming READY.
            assert status != "IMPLEMENTED", (
                f"{c['name']!r} is fully IMPLEMENTED while its owning unit {owner} is BLOCKED - "
                "a blocked unit's work cannot already be complete"
            )
            checked += 1
        if status == "IMPLEMENTED":
            symbols = [e["symbol"] for e in c.get("evidence", [])]
            assert symbols, f"{c['name']!r} claims IMPLEMENTED with no evidence symbols"
            missing = [s for s in symbols if not _src_contains_symbol(s)]
            assert not missing, (
                f"{c['name']!r} claims IMPLEMENTED but these symbols are absent from src/: "
                f"{missing} - the surface is asserting code that does not exist"
            )
            checked += 1
    assert checked, "the concept cross-check evaluated nothing and has proven nothing"


# ============================================================ U-HANDOFF-1 executable checklist

CHECKLIST = IMPL / "U-HANDOFF-1-ACCEPTANCE.yaml"


def test_the_handoff_checklist_is_exact_and_fully_adjudicated():
    """U-HANDOFF-1D replaced the all-PENDING guard: the gate is CLOSED, so the truthful state is
    13/13 PASS - but ONLY with the independence machinery intact. Every PASS must name its
    independent evidence, the adjudication block must bind the results to the preserved
    U-HANDOFF-2B report, and that report must actually exist with its truncation disclosed. A
    result drifting back to PENDING/FAIL, a criterion losing its evidence, or the evidence
    report vanishing all fail the build."""
    data = yaml.safe_load(read(CHECKLIST))
    crits = data["criteria"]
    ids = [c["id"] for c in crits]
    assert ids == [f"HANDOFF-{i:02d}" for i in range(1, 14)], (
        f"checklist criteria drifted from the exact 13: {ids}"
    )
    for c in crits:
        assert c.get("statement", "").strip(), f"{c['id']}: empty statement"
        assert c.get("evidence_required", "").strip(), f"{c['id']}: no required evidence"
        assert c["result"] == "PASS", (
            f"{c['id']} is {c['result']!r} - the gate was adjudicated CLOSED with 13/13 PASS; "
            "a drifted result is either an unrecorded re-opening or a corruption, and both must "
            "be surfaced, not silently tolerated"
        )
        evidence = c.get("evidence", "")
        assert evidence.strip(), f"{c['id']}: PASS with no evidence recorded"
        assert re.search(r"U-HANDOFF-2B|independent rehearsal", evidence, re.I), (
            f"{c['id']}: PASS whose evidence names no independent source - a self-passed "
            "criterion is exactly what this checklist exists to prevent"
        )
    assert "independence_requirement" in data["meta"]
    assert "READY FOR HOSTILE HANDOFF-READINESS REVIEW" in data["meta"]["verdict_vocabulary"]
    adj = data["meta"].get("adjudication") or {}
    assert adj.get("adjudicated_by") == "U-HANDOFF-1D", "no adjudication record"
    report_rel = adj.get("evidence_report", "")
    assert report_rel, "adjudication names no evidence report"
    report_path = ROOT / report_rel
    assert report_path.exists(), f"the adjudication's evidence report is missing: {report_rel}"
    report = report_path.read_text(encoding="utf-8")
    assert "HISTORICAL REVIEW" in report.split("\n", 1)[0] or "HISTORICAL REVIEW" in report[:400], (
        "the preserved report must open with its historical-evidence banner"
    )
    assert re.search(r"truncat", report, re.I), (
        "the preserved report must disclose its truncation - presenting the received portion as "
        "the complete report would be fabricated completeness"
    )
    assert adj.get("evidence_caveat", "").strip(), (
        "the adjudication must state its evidence caveat (received-portion + founder-attested "
        "verdict + re-execution) rather than implying the full report was received"
    )


REBASELINE_CHECKLIST = IMPL / "U-REBASELINE-1-ACCEPTANCE.yaml"


def test_the_rebaseline_checklist_is_exact_and_fully_adjudicated():
    """U-REBASELINE-1A: all 24 criteria PASS. RB-24 may ONLY be awarded from the INDEPENDENT review
    - its evidence must cite the preserved independent report, and that report must exist. Replaced
    (not deleted) from the RB-24-must-be-PENDING guard, which was correct until the independent
    evidence arrived."""
    data = yaml.safe_load(read(REBASELINE_CHECKLIST))
    crits = data["criteria"]
    ids = [c["id"] for c in crits]
    assert ids == [f"RB-{i:02d}" for i in range(1, 25)], (
        f"rebaseline criteria drifted from the exact 24: {ids}"
    )
    for c in crits:
        assert c.get("statement", "").strip(), f"{c['id']}: empty statement"
        assert c.get("evidence_required", "").strip(), f"{c['id']}: no required evidence"
        assert c["result"] == "PASS", (
            f"{c['id']} is {c['result']!r} - the adjudicated contract records PASS with evidence"
        )
        assert c.get("evidence", "").strip(), f"{c['id']}: PASS with no evidence recorded"
    rb24 = next(c for c in crits if c["id"] == "RB-24")
    assert "u-rebaseline-review-1-independent-report.md" in rb24["evidence"], (
        "RB-24 must be awarded from the INDEPENDENT review report - a self-certified "
        "fresh-reviewer determination is worthless"
    )
    report = ROOT / "docs/implementation/u-rebaseline-review-1-independent-report.md"
    assert report.exists(), "the independent review report RB-24 cites is missing"
    meta = data["meta"]
    assert meta.get("adjudicated_by") == "U-REBASELINE-1A", "no adjudication record"
    assert meta.get("independent_review", "").endswith("u-rebaseline-review-1-independent-report.md")
    units = registry_units()
    reb = next(u for u in units if u["unit_id"] == "U-REBASELINE-1")
    assert reb["status"] == "COMPLETE", (
        f"U-REBASELINE-1 is {reb['status']} while all 24 criteria PASS - status and contract disagree"
    )


def test_the_checklist_covers_the_new_control_requirements():
    """Restored by U-REBASELINE-1A: this HANDOFF-checklist guard was swallowed by an adjacent
    guard replacement. It guards a different contract (the handoff checklist's coverage), was never
    superseded, and deleting it was an error - CLAUDE.md section 5 rule 20 permits replacement, not
    silent removal."""
    text = read(CHECKLIST)
    assert re.search(r"broad-tool-access|broad tool access", text, re.I), "no tool-access criterion"
    assert re.search(r"distinguishes tool access from action authority", text, re.I)
    assert re.search(r"status block", text, re.I), "no commit/tree/suite verification criterion"
    assert re.search(r"WITHOUT starting it", text), "no first-formal-unit criterion"


# ============================================================ scripts disposition coverage

def test_every_script_has_a_disposition():
    """Extends the src/ coverage guard to scripts/ - the rehearsal's L-1."""
    doc = read(LEGACY)
    named = set(re.findall(r"`scripts/([a-z_0-9]+\.py)`", doc))
    actual = {p.name for p in (ROOT / "scripts").glob("*.py")}
    require_population(actual, "scripts")
    missing = sorted(actual - named)
    assert not missing, f"scripts with no disposition: {missing}"
    phantom = sorted(named - actual)
    assert not phantom, f"dispositions naming scripts that do not exist: {phantom}"


# ============================================================ agent-pair authority (L-3)

def test_agent_surfaces_pair_exactly_and_codex_declares_compatibility():
    """Decision (U-HANDOFF-1A): .claude/agents/ is canonical - the formal CLI environment is
    Claude Code. .codex/agents/ files are compatibility surfaces and must say so. Text sync is
    deliberately NOT enforced; AUTHORITY is: the pair sets must match and every codex file must
    name its canonical counterpart, so the surfaces can no longer appear equally authoritative
    while drifting silently."""
    claude = {p.name for p in ROOT.glob(".claude/agents/*.md")}
    codex = {p.name for p in ROOT.glob(".codex/agents/*.md")}
    require_population(claude, "claude agent definitions")
    assert claude == codex, (
        f"agent surfaces no longer pair: claude-only={claude - codex}, codex-only={codex - claude}"
    )
    for p in sorted(ROOT.glob(".codex/agents/*.md")):
        text = read(p)
        assert "COMPATIBILITY SURFACE" in text, f"{p.name}: no compatibility declaration"
        assert f".claude/agents/{p.name}" in text, f"{p.name}: does not name its canonical counterpart"


# ============================================================ M-1 / M-2 / M-3 stay fixed

def test_phase_reviewer_commands_carry_canonical_approval_authority_only():
    for path in (ROOT / ".claude/agents/phase-code-reviewer.md",
                 ROOT / ".codex/agents/phase-code-reviewer.md"):
        text = read(path)
        assert "Verification Commands — CANONICAL" in text, f"{path.name}: canonical section gone"
        assert re.search(r"pytest eval/ -q\b", text), f"{path.name}: no full-suite command"
        assert "test_status_reality.py" in text, f"{path.name}: status-reality guard not required"
        assert re.search(r"ac_safe_012 or ac_safe_013 or ac_sec_001", text), (
            f"{path.name}: acceptance gates not in the approval sequence"
        )
        assert re.search(r"Historical commands — NO approval authority", text), (
            f"{path.name}: the historical list lost its no-authority label"
        )
        canonical_zone = text.split("Historical commands")[0]
        assert "run_corpus_eval" not in canonical_zone and "generate_realistic_corpus" not in canonical_zone, (
            f"{path.name}: a pre-reset command re-entered the canonical approval sequence"
        )


def test_build_supervisor_states_dual_provider_truthfully():
    """Mutation S-7 slipped past the first version of this guard two ways: the positive check
    matched the section HEADING while the body asserted a universal provider, and the negative
    pattern was case-sensitive. The guard now requires the full dual-provider STATEMENT and scans
    for universal-provider claims case-insensitively."""
    text = read(ROOT / ".claude/agents/build-supervisor.md")
    assert re.search(r"runtime is currently dual-provider.{0,60}not an architecture decision", text, re.S), (
        "the dual-provider statement (not merely the word) is gone"
    )
    assert re.search(r"not canonical product architecture", text), (
        "provider choice is being presented as architecture again"
    )
    assert re.search(r"Do not flag provider-valid code solely because", text)
    assert re.search(r"consolidation.{0,80}explicit approved work unit", text, re.S | re.I)
    assert not re.search(
        r"(this project|the repo(sitory)?) calls (Claude|OpenAI|GPT)(?!-API)|"
        r"calls (Claude|OpenAI) for everything|flag any other provider",
        text, re.I,
    ), "a universal-provider claim is back"


def test_guidance_review_records_the_findings_as_adjudicated():
    text = read(GUIDANCE_REVIEW)
    assert re.search(r"dispositions updated by U-HANDOFF-1A", text), (
        "the guidance review no longer records the U-HANDOFF-1A adjudication"
    )
    assert re.search(r"Model strategy.{0,80}RESOLVED as a contradiction", text, re.S), (
        "the resolved model-strategy contradiction is presented as open again"
    )
    assert re.search(r"No final model strategy was invented", text)
