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
    assert "operational execution layer" in text
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
    assert "operational execution layer for small and medium freight brokerages" in body, \
        "CLAUDE.md section 2 no longer carries the canonical product definition"
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


def test_9_phase_3_is_recorded_not_started():
    for path in (CURRENT, CLAUDE, README):
        assert re.search(r"(P3|Phase 3).{0,80}NOT STARTED", read(path), re.I | re.S), \
            f"{path.name} must record Phase 3 NOT STARTED"


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
        (r"\b24\b.{0,80}(transitions|event)", "24 event-less transitions"),
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

def test_24_the_next_approved_work_is_handoff_readiness_not_phase_3():
    ready = [u for u in registry_units() if u["status"] == "READY"]
    assert len(ready) == 1
    unit = ready[0]
    assert unit["unit_id"] == "U-HANDOFF-1", f"the READY unit is {unit['unit_id']}, expected U-HANDOFF-1"
    assert "rehearsal" in unit["name"].lower()
    prohibited = " ".join(str(x) for x in unit["prohibited_scope"]).lower()
    assert "phase 3" in prohibited, "U-HANDOFF-1 must prohibit Phase 3 implementation"
    p3 = next(u for u in registry_units() if u["unit_id"] == "P3")
    assert p3["status"] == "BLOCKED", f"P3 is {p3['status']}, must be BLOCKED"
    assert "U-HANDOFF-1" in p3["dependencies"], "P3 must depend on the handoff rehearsal"
    assert re.search(r"ZERO-CONTEXT CLI HANDOFF REHEARSAL", read(CURRENT), re.I), \
        "CURRENT.md must name the next approved program"


def test_24b_the_current_status_file_does_not_direct_an_agent_into_phase_3():
    text = read(CURRENT)
    assert re.search(r"(must NOT begin|Not yet).{0,400}Phase 3", text, re.I | re.S), \
        "CURRENT.md must explicitly forbid beginning Phase 3"


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

SUPERSEDED_MUST_STAY_SUPERSEDED = [
    "PRODUCT_ROADMAP.md", "NEYMA_VISION.md", "AGENTIC_ARCHITECTURE.md", "OWNER_OPERATOR_ROADMAP.md",
]


@pytest.mark.parametrize("doc", SUPERSEDED_MUST_STAY_SUPERSEDED)
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
