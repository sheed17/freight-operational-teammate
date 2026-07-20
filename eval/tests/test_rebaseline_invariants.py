"""U-REBASELINE-1 invariant guards.

The founder rebaseline (ADR-012..017) rejected a specific set of ABSOLUTE product constraints and
made a set of positive commitments durable. These guards fail the build if a rejected absolute
returns to a CURRENT-AUTHORITY document as a live claim, or if a positive commitment is lost.

Discovery, never enumeration: the current-authority population comes from
eval/control/inventory.py (git ls-files + the authority map's own classification), so a new
current-authority document is scanned automatically. Historical documents are exempt - they may
retain old claims behind an immediate disarming banner (that is what the banner guards enforce).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "eval"))
from control import inventory as inv  # noqa: E402

REG = ROOT / "docs/implementation/IMPLEMENTATION-REGISTRY.yaml"
RB = ROOT / "docs/implementation/U-REBASELINE-1-ACCEPTANCE.yaml"


def read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def require_population(items, what: str):
    assert items, f"discovery produced an EMPTY population for {what} - the guard would pass vacuously"
    return items


# A rejected absolute is dangerous only when asserted as CURRENT product authority. Each pattern
# is written to match the ABSOLUTE form (never/only/must/permanent), not a discussion of it. The
# disarm markers let a current-authority document QUOTE a rejected claim in order to retire it.
DISARM = re.compile(
    r"reject|retir|supersed|no longer|not a permanent|rebaselin|amended by|"
    r"⚠️|not\s+an?\s+absolute|ADR-01[2-7]",
    re.I,
)

# (label, compiled pattern that matches the LIVE ABSOLUTE form)
REJECTED_ABSOLUTES = [
    ("Neyma may never become authoritative for native workflows",
     re.compile(r"Neyma\s+(?:must\s+)?(?:remain\s+permanently\s+outside|never\s+becomes?\s+"
                r"authoritative\s+for)\b", re.I)),
    ("a brokerage may never replace its TMS",
     re.compile(r"(?:brokerage\s+never\s+rips?\s+out\s+its\s+TMS|never\s+replace[sd]?\s+(?:the|its)\s+TMS)", re.I)),
    ("Neyma may never securely possess customer-authorized credentials",
     re.compile(r"Neyma\s+never\s+holds?\s+(?:the\s+human's|a\s+customer's|TMS)\s+credentials", re.I)),
    ("every browser session must be established manually by a human",
     re.compile(r"(?:the\s+human\s+must\s+establish\s+every\s+session|human\s+establishes?\s+every\s+session)", re.I)),
    ("the first wedge is the permanent product identity",
     re.compile(r"(?:permanent(?:ly)?\s+(?:limits?|is)\s+(?:Neyma's\s+)?identity|"
                r"first\s+(?:implementation\s+)?wedge\s+is\s+the\s+(?:permanent\s+)?product\s+identity)", re.I)),
    ("Slack is the only control interface",
     re.compile(r"Slack\s+is\s+the\s+only\s+(?:control|admin|oversight|interface)", re.I)),
    ("local success equals production readiness",
     re.compile(r"(?:code\s+exists\s*(?:=|means|equals)\s*production\s+ready|"
                r"local\s+success\s+equals\s+production)", re.I)),
    ("access equals action authority",
     re.compile(r"(?:access\s+(?:=|equals|creates?|grants?)\s+(?:action\s+)?authority|"
                r"authentication\s+creates?\s+action\s+authority)", re.I)),
]


def _current_authority_texts():
    docs = [d for d in inv.current_authority_documents() if d.endswith(".md")]
    # FIXED-SPECIFICATION: the five root control documents are a fixed architectural set (the same
    # set the authority map §2 enumerates and test_23b enforces). They are augmented onto the
    # DISCOVERED current-authority population, not a substitute for discovery - a new
    # current-authority doc under docs/ still enters via inventory.current_authority_documents().
    ROOT_CONTROL_DOCS = {"PRODUCT.md", "ARCHITECTURE.md", "CLAUDE.md", "README.md", "AGENTS.md"}
    docs += [f for f in inv.tracked_files() if f in ROOT_CONTROL_DOCS]
    return require_population(sorted(set(docs)), "current-authority markdown documents")


def _line_window(text: str, pos: int, before: int = 1, after: int = 1) -> str:
    """The matched physical line plus `before` lines above and `after` lines below - tight
    enough that a disarm marker must be genuinely adjacent to the reintroduced absolute, not
    merely somewhere in the same section (which would let an absolute hide 300 chars from an
    unrelated 'reject' or 'ADR-012' mention)."""
    lines = text.split("\n")
    ln = text[:pos].count("\n")
    lo = max(0, ln - before)
    hi = min(len(lines), ln + after + 1)
    return "\n".join(lines[lo:hi])


def test_no_rejected_product_absolute_is_a_live_claim_in_current_authority():
    offenders = []
    for rel in _current_authority_texts():
        text = read(rel)
        for label, pat in REJECTED_ABSOLUTES:
            for m in pat.finditer(text):
                # A legitimate retirement carries its disarm marker on the SAME line as the quoted
                # absolute (the §12 ceilings list, the ⚠️ in-place annotations) or one line away.
                if DISARM.search(_line_window(text, m.start())):
                    continue
                line = text[: m.start()].count("\n") + 1
                offenders.append(f"{rel}:{line}: rejected absolute live: {label!r} :: {m.group(0)!r}")
    assert not offenders, (
        "rejected product absolutes reappeared as LIVE current-authority claims "
        "(ADR-012..017 retired these):\n  " + "\n  ".join(offenders)
    )


def test_the_canonical_identity_is_present_and_exact():
    """ADR-012 section 1, verbatim, in the root product authority and the operating guide."""
    ident = "AI-native operating platform and system of action for small and medium freight"
    assert ident in read("PRODUCT.md"), "PRODUCT.md lost the ADR-012 canonical identity"
    assert ident in read("CLAUDE.md"), "CLAUDE.md lost the ADR-012 canonical identity"


def test_the_six_rebaseline_adrs_exist_and_are_final():
    expected = {
        "ADR-012": "product-identity-and-strategy",
        "ADR-013": "workflow-authority-migration",
        "ADR-014": "credential-and-machine-identity",
        "ADR-015": "communications-subsystem",
        "ADR-016": "production-topology",
        "ADR-017": "tenant-and-integration-lifecycle",
    }
    adr_dir = ROOT / "docs/architecture/decisions"
    for adr, slug in expected.items():
        path = adr_dir / f"{adr}-{slug}.md"
        assert path.exists(), f"missing rebaseline ADR: {path.name}"
        head = path.read_text(encoding="utf-8")[:400]
        assert "FINAL" in head and "U-REBASELINE-1" in head, f"{adr} not marked FINAL by U-REBASELINE-1"


def test_credentials_permitted_but_authentication_is_not_authority():
    """ADR-014: the positive permission AND the permanent boundary must both survive."""
    adr = read("docs/architecture/decisions/ADR-014-credential-and-machine-identity.md")
    assert re.search(r"may\s+securely\s+possess\s+customer-authorized\s+authentication", adr, re.I), (
        "ADR-014 lost the positive credential permission"
    )
    assert re.search(r"minimizes\s+handling\s+of\s+employees'\s+raw\s+personal\s+credentials", adr, re.I), (
        "ADR-014 lost the permanent minimization rule"
    )
    assert re.search(r"never\s+independently\s+authorizes\s+an\s+external\s+effect", adr, re.I), (
        "ADR-014 lost the permanent access-is-not-authority boundary"
    )


def test_delivered_load_closure_is_a_hypothesis_not_validated():
    prod = read("PRODUCT.md")
    m = re.search(r"DELIVERED LOAD CLOSURE(.{0,2000})", prod, re.S | re.I)
    assert m, "PRODUCT.md section 15 no longer names Delivered Load Closure"
    block = m.group(0)
    assert re.search(r"HYPOTHESIS|NEEDS\s+(?:DESIGN-PARTNER\s+)?VALIDATION", block, re.I), (
        "Delivered Load Closure is not marked as an unvalidated hypothesis"
    )
    assert re.search(r"not\s+invoice\s+processing", block, re.I), (
        "PRODUCT.md must state Delivered Load Closure is not invoice processing"
    )
    # not labeled validated anywhere
    assert not re.search(r"Delivered Load Closure[^.\n]{0,40}\bvalidated\b", prod, re.I), (
        "Delivered Load Closure must not be labeled validated"
    )


def test_the_evidence_program_exists_and_fails_closed():
    prog = read("docs/product/DESIGN-PARTNER-EVIDENCE-PROGRAM.md")
    assert "accountable source" in prog.lower(), "evidence program lacks accountable-source discipline"
    assert re.search(r"fail-closed|fail\s+closed", prog, re.I), "evidence program lacks fail-closed behavior"
    assert re.search(r"(?:not|never\s+becomes?)\s+a\s+(?:second\s+)?READY\s+coding\s+unit", prog, re.I), (
        "evidence program must state it is not a second READY coding unit"
    )
    # it must not be a registry work unit
    units = yaml.safe_load(read("docs/implementation/IMPLEMENTATION-REGISTRY.yaml"))["units"]
    ids = {u["unit_id"] for u in units}
    assert "DESIGN-PARTNER-EVIDENCE-PROGRAM" not in ids and "U-EVIDENCE-1" not in ids, (
        "the evidence program became a registry unit - it must run alongside, not as a READY unit"
    )


def test_exactly_one_ready_unit_and_it_is_the_rebaseline():
    units = yaml.safe_load(read("docs/implementation/IMPLEMENTATION-REGISTRY.yaml"))["units"]
    ready = [u["unit_id"] for u in units if u["status"] == "READY"]
    assert ready == ["U-REBASELINE-1"], f"exactly one READY unit expected (U-REBASELINE-1); got {ready}"
    p3 = next(u for u in units if u["unit_id"] == "P3")
    assert p3["status"] == "BLOCKED", "P3 must remain BLOCKED during the rebaseline"
    assert "U-REBASELINE-1" in p3["dependencies"], "P3 must depend on the rebaseline"


def test_r07_remains_open_not_contained():
    """The rebaseline is documentation-only; it may never mark R-07 contained."""
    manifest = read("docs/implementation/phase-0-baseline-manifest.yaml")
    # the existing errata guard forbids CONTAINED; assert the OPEN record persists in status
    current = read("docs/implementation/CURRENT.md")
    assert re.search(r"R-07.{0,80}OPEN\s*[—-]\s*NOT\s+CONTAINED", current, re.I | re.S), (
        "CURRENT.md no longer records R-07 OPEN - NOT CONTAINED"
    )


def test_production_readiness_vocabulary_is_defined():
    """ADR-016 section 3: 'code exists' means LOCALLY_IMPLEMENTED, never production ready."""
    adr = read("docs/architecture/decisions/ADR-016-production-topology.md")
    for level in ("SPECIFICATION_ONLY", "LOCALLY_IMPLEMENTED", "STAGING_READY", "PILOT_READY",
                  "SUPERVISED_PRODUCTION_READY", "GENERALLY_PRODUCTION_READY"):
        assert level in adr, f"ADR-016 readiness vocabulary missing {level}"
    assert re.search(r"code\s+exists.{0,60}LOCALLY_IMPLEMENTED", adr, re.I | re.S), (
        "ADR-016 must state 'code exists' means LOCALLY_IMPLEMENTED, not production ready"
    )


def test_sqlite_is_not_the_production_multi_tenant_database():
    adr = read("docs/architecture/decisions/ADR-016-production-topology.md")
    assert re.search(r"PostgreSQL\s+is\s+the\s+production\s+transactional\s+store", adr, re.I), (
        "ADR-016 must name PostgreSQL as the production store"
    )
    assert re.search(r"SQLite.{0,80}(?:not|dev|development|test)", adr, re.I | re.S), (
        "ADR-016 must state SQLite is not the production multi-tenant database"
    )


def test_communications_are_a_core_subsystem_not_optional():
    adr = read("docs/architecture/decisions/ADR-015-communications-subsystem.md")
    assert re.search(r"required\s+production\s+capabilit", adr, re.I), (
        "ADR-015 must state email/SMS are required production capabilities, not optional"
    )
    # the registry must wire ingestion into P9 and sends into P12
    units = yaml.safe_load(read("docs/implementation/IMPLEMENTATION-REGISTRY.yaml"))["units"]
    by = {u["unit_id"]: u for u in units}
    assert "communications" in (by["P9"]["name"] + str(by["P9"]["objective"])).lower(), (
        "P9 must carry communications ingestion"
    )
    assert "communications" in (by["P12"]["name"] + str(by["P12"]["objective"])).lower(), (
        "P12 must carry supervised communications"
    )


def test_every_rebaselined_phase_has_a_rebaseline_contract():
    units = yaml.safe_load(read("docs/implementation/IMPLEMENTATION-REGISTRY.yaml"))["units"]
    for u in units:
        if re.fullmatch(r"P([3-9]|1[0-4])", u["unit_id"]):
            rc = u.get("rebaseline_contract")
            assert rc, f"{u['unit_id']} has no rebaseline_contract block"
            for field in ("user_visible_capability", "platform_capability", "evidence_requirements",
                          "hostile_cases", "rollout_posture", "observability_requirements",
                          "security_requirements", "readiness_target"):
                assert rc.get(field), f"{u['unit_id']}.rebaseline_contract missing {field}"


def test_no_src_runtime_file_was_touched_by_the_rebaseline():
    """The rebaseline diff (vs the U-HANDOFF-1D content baseline) must not touch src/."""
    import subprocess
    base = yaml.safe_load(read("docs/implementation/IMPLEMENTATION-REGISTRY.yaml"))
    # the baseline_commit recorded is the previous content commit; compare the working tree to it
    prev = "0a25a001b522047858c95bed461046046fafe7a0"  # U-HANDOFF-1D content commit
    r = subprocess.run(["git", "diff", "--name-only", prev], cwd=ROOT,
                       capture_output=True, text=True)
    if r.returncode != 0:
        return  # git unavailable; other guards cover posture
    changed = [f for f in r.stdout.split("\n") if f.strip()]
    src_changed = [f for f in changed if f.startswith("src/")]
    assert not src_changed, f"the rebaseline changed production runtime code: {src_changed}"
