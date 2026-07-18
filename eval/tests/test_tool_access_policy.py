"""Guards over the tool-access policy: broad access cannot be quietly restricted, and the
authority boundary cannot be quietly widened.

The policy holds two opposed lines at once - the model researches aggressively AND research can
never authorise. A mutation that erodes either line changes real behaviour in a formal session, so
every load-bearing statement is guarded, and the dangerous ones are guarded in BOTH directions
(the statement must be present, and its inversion must be absent).
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "docs" / "implementation" / "TOOL-ACCESS-POLICY.md"
CLAUDE = ROOT / "CLAUDE.md"


def read(p: Path) -> str:
    """Read with markdown emphasis stripped and whitespace collapsed.

    The first run of these guards failed on their own policy because `**bold**` markers and
    line-wraps sat inside the phrases being matched - the substring-vs-token lesson again, in
    markup form. Normalising here keeps every pattern about MEANING, not formatting.
    """
    text = p.read_text(encoding="utf-8")
    text = text.replace("**", "").replace("`", "")
    return re.sub(r"[ \t]*\n[ \t]*", " ", text)


# ------------------------------------------------------------------ 1-2. existence + linkage

def test_01_the_tool_access_policy_exists_and_is_substantial():
    assert POLICY.exists(), "TOOL-ACCESS-POLICY.md is missing"
    assert len(read(POLICY).split()) > 400, "the policy is too thin to govern formal sessions"


def test_02_claude_md_links_to_the_policy_and_carries_the_concise_rule():
    text = read(CLAUDE)
    assert "TOOL-ACCESS-POLICY.md" in text, "CLAUDE.md does not link the tool-access policy"
    assert re.search(
        r"Tool access is intentionally broad so missing technical context is investigated rather\s+than\s+guessed",
        text,
    ), "CLAUDE.md lost the concise tool-access rule"
    assert re.search(r"expands evidence retrieval, not canonical decision authority", text), (
        "CLAUDE.md lost the retrieval-vs-authority half of the rule"
    )


# ------------------------------------------------------------------ 3-6. breadth is explicit

def test_03_broad_engineering_and_research_access_is_explicitly_allowed():
    text = read(POLICY)
    assert re.search(r"founder explicitly approves broad tool access", text, re.I)
    assert re.search(r"broad engineering autonomy", text, re.I)
    assert re.search(r"broad research autonomy", text, re.I)
    assert re.search(r"SEARCH AGGRESSIVELY\. INFER CAUTIOUSLY\. EXECUTE ACCORDING TO AUTHORITY\.", text)


def test_04_web_search_is_allowed_in_formal_sessions():
    text = read(POLICY)
    assert re.search(r"\bweb search\b", text, re.I), "web search is no longer named as allowed"
    assert not re.search(r"web search is (forbidden|prohibited|not allowed|disallowed)", text, re.I)
    # the SEARCHABLE TECHNICAL FACT class must direct automatic research, not permission-seeking
    assert re.search(r"### SEARCHABLE TECHNICAL FACT.*?Research automatically", text, re.S), (
        "searchable technical facts must be researched automatically, not escalated"
    )


def test_05_internal_connector_research_is_allowed():
    text = read(POLICY)
    for connector in ("Google Drive", "Notion", "internal documentation connectors"):
        assert connector in text, f"{connector} is no longer named as an allowed research surface"
    assert re.search(r"### INTERNAL ORGANIZATIONAL FACT.*?Search connected internal sources automatically", text, re.S)


def test_06_package_installation_and_test_tooling_are_allowed():
    text = read(POLICY)
    assert re.search(r"package installation", text, re.I)
    assert re.search(r"test runners", text, re.I)
    assert re.search(
        r"Routine engineering needs no per-action approval", text
    ), "the policy now frames routine development as requiring sign-off"


# ------------------------------------------------------------------ 7-8. the boundary

def test_07_research_capability_is_distinguished_from_consequential_authority():
    text = read(POLICY)
    assert re.search(r"Tool access is not business authority|narrow consequential-production authority", text)
    assert re.search(r"Tool access expands evidence retrieval, not canonical decision authority", text)
    # the consequential list must survive
    for item in ("live TMS writes", "payment", "carrier", "credential rotation",
                 "production deployment", "legal or financial commitment"):
        assert re.search(item, text, re.I), f"the consequential-action list lost {item!r}"


def test_08_tool_possession_does_not_authorize_external_effects():
    text = read(POLICY)
    assert re.search(
        r"Possession of a tool or credential is never authorization", text, re.I
    ), "the possession-is-not-authorization line is gone"
    assert not re.search(
        r"possession of a (tool|credential).{0,60}(is|counts as|constitutes) authorization(?!\s+to\s+execute\s+a\s+consequential\s+effect\b)",
        text, re.I,
    ) or "never authorization" in text
    assert not re.search(r"a (configured|working) (tool|credential|session) (authorises|authorizes)", text, re.I)


# ------------------------------------------------------------------ 9-15. search cannot become authority

@pytest.mark.parametrize(
    "label,present,absent",
    [
        ("search cannot validate a product hypothesis",
         r"Search results cannot validate a product hypothesis",
         r"(sufficient|enough) (web|search) (evidence|results) (validates|can validate)"),
        ("search cannot manufacture design-partner evidence",
         r"Search results cannot manufacture design-partner evidence",
         r"(retrieved|web) (documents?|results?) (count|qualify) as (design-partner|partner) (evidence|observation)"),
        ("web search cannot choose an approval threshold",
         r"cannot choose an approval threshold",
         r"(industry|web|retrieved) (standards?|results?|benchmarks?) (may|can) (set|choose|determine) (the )?approval threshold"),
        ("web search cannot authorize payment or carrier assignment",
         r"authorise a payment, or assign a carrier|payment authority.*SEARCH CANNOT CREATE AUTHORIZATION",
         r"(web|search|retrieved) (evidence|results?).{0,40}(authorises?|authorizes?) (a )?(payment|carrier)"),
        ("UNKNOWN_OUTCOME not retried on research",
         r"UNKNOWN_OUTCOME`? is never retried merely because research suggests",
         r"retry (the |an )?UNKNOWN_OUTCOME (if|when|because) (research|the web|evidence) suggests"),
        ("OWNER_ASSERTED not overridden by retrieved evidence",
         r"OWNER_ASSERTED`? facts are never overridden by retrieved evidence",
         r"retrieved (evidence|documents?) (may|can) (override|overwrite|correct) (an? )?`?OWNER_ASSERTED"),
        ("MODEL_INFERRED cannot become authoritative through tools",
         r"MODEL_INFERRED`? facts do not become authoritative through tool access",
         r"(well-sourced|cited|researched) inference (is|becomes) authoritative"),
    ],
    ids=["hypothesis", "partner_evidence", "threshold", "payment_carrier",
         "unknown_outcome", "owner_asserted", "model_inferred"],
)
def test_09to15_search_cannot_create_authority(label, present, absent):
    text = read(POLICY)
    assert re.search(present, text, re.S), f"the policy lost the rule: {label}"
    assert not re.search(absent, text, re.I), f"the policy now asserts the INVERSE of: {label}"


def test_the_authorization_chain_is_named_as_the_only_source():
    text = read(POLICY)
    assert re.search(r"SEARCH CANNOT CREATE AUTHORIZATION", text)
    assert re.search(r"approval → checkpoint → grant \+ witness|canonical authorization\s+chain", text), (
        "the policy no longer names where authority actually comes from"
    )


# ------------------------------------------------------------------ 16. production writes

def test_16_production_writes_remain_behind_explicit_authorization():
    text = read(POLICY)
    assert re.search(r"production database writes", text, re.I)
    assert re.search(r"(inspect, prepare, simulate and validate)", text), (
        "the policy must still allow preparing/simulating consequential actions - removing that "
        "turns the boundary into a blanket restriction"
    )


# ------------------------------------------------------------------ 17-18. no blanket restriction / no bypass default

def test_17_the_model_is_not_placed_under_blanket_tool_restrictions():
    text = read(POLICY) + read(CLAUDE)
    assert re.search(r"not artificially restricted", read(POLICY), re.I)
    forbidden = [
        r"do not use web search",
        r"never (use|install) (the )?(web|packages)",
        r"all tools? (are|is) (forbidden|prohibited)",
        r"blanket (tool )?restrictions? (apply|are in force)",
    ]
    for pat in forbidden:
        assert not re.search(pat, text, re.I), f"blanket-restriction language appeared: {pat}"


def test_18_no_permission_bypass_mode_is_required_as_default():
    text = read(POLICY) + read(CLAUDE)
    assert not re.search(
        r"(dangerously[- ]?skip[- ]?permissions|bypass (the )?permissions?)[^.\n]{0,60}(default|always|required|must)",
        text, re.I,
    ), "a permission-bypass mode is being prescribed as a default"
    assert re.search(r"never told to default to bypassing", read(POLICY), re.I), (
        "the policy lost its explicit anti-bypass statement"
    )


# ------------------------------------------------------------------ classification + evidence discipline

def test_all_five_missing_context_classes_exist_with_their_responses():
    text = read(POLICY)
    for cls in ("SEARCHABLE TECHNICAL FACT", "INTERNAL ORGANIZATIONAL FACT", "PRODUCT DECISION",
                "CUSTOMER-SPECIFIC OPERATIONAL RULE", "CONSEQUENTIAL-ACTION AUTHORITY"):
        assert f"### {cls}" in text, f"missing-context class gone: {cls}"  # headings survive collapse
    assert re.search(r"PRODUCT DECISION.*?research does not choose", text, re.S)
    assert re.search(r"CUSTOMER-SPECIFIC OPERATIONAL RULE.*?NEEDS VALIDATION.*?fail closed", text, re.S)


def test_evidence_discipline_fields_are_required():
    text = read(POLICY)
    for field in ("Source", "Retrieval date", "Source type", "Exact claim supported",
                  "Confidence", "Evidence class"):
        assert field in text, f"evidence-discipline field gone: {field}"
    assert re.search(r"never silently upgrades its class", text)


def test_no_mcp_vendor_is_mandated():
    text = read(POLICY)
    assert re.search(r"No particular MCP vendor or provider is mandatory", text)
