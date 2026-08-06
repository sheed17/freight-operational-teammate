"""Structured parser for canonical RISK STATUS CLAIMS, and the R-07 claim vocabulary.

WHY THIS EXISTS. The guards this replaces asked whether a copula from a closed three-verb set
(`is` / `stays` / `remains`) FOLLOWED the risk id:

    R-07[^.\\n|]{0,60}?\\b(?:is|stays|remains)\\s+\\*{0,3}(?:OPEN|NOT\\s+CONTAINED|UNCONTAINED)\\b

That is a word-order assumption, and it is structurally blind to the grammar this repository
actually writes canonical status in. Its own `Current risk` rows are copula-free markdown table
cells built on an em-dash --- `| **Current risk** | ### **R-07 - OPEN, NOT CONTAINED.** ... |` ---
so the pattern could never see them. It equally missed every verb-precedes construction
(`keeps R-07 OPEN`, `leaves R-07 open`), every negated-containment construction
(`R-07 not contained`, `does not contain R-07`) and every line-wrapped one. Measured: 8 of 12
relevant forms missed, and 0 of the 5 live defects caught while the suite reported green.

A third substring alternation would be the same defect a third time. So this module does not match
word order at all. It PARSES:

  1. SEGMENT the document into CLAIM UNITS - markdown table cells and sentences - so a claim is
     bounded by the structure it is written in, and a neighbouring sentence's vocabulary cannot
     leak into it.
  2. NORMALIZE each unit - markdown emphasis stripped, whitespace runs collapsed - so `**OPEN**`,
     `### **R-07`, and a construction wrapped across three source lines all read alike.
  3. Decide POLARITY from a CLOSED vocabulary, checking NEGATED containment before plain
     containment, so `not contained` never reads as `contained`.

Word order is irrelevant to every step. `R-07 remains open`, `keeps R-07 open` and
`does not contain R-07` are the same parse.

TWO THINGS THIS DELIBERATELY DOES NOT DO.

  * It does not treat every `open` near `R-07` as a status claim. This repository names registers
    with the same word - "Open risks and findings", "an open decision", "the open-risks table" -
    and a guard that fires on those is the unrelated-identifier failure CLAUDE.md sec 9 names.
    `open` immediately qualifying a register noun is not a claim about a risk's state.
  * It does not erase history. A superseded claim survives IN PLACE by being QUOTED or by carrying
    an explicit HISTORICAL / SUPERSEDED marker on its line - the two mechanisms the control system
    already recognises.

QUOTE PARITY IS BLOCK-BOUNDED, NOT FILE-BOUNDED (this closes F-05). The rule it replaces asked
`text.count('"', 0, pos) % 2 == 1` over the WHOLE FILE, so one unbalanced double quote anywhere
silently exempted every later claim to the end of the document. Parity is now counted from the
start of the enclosing block, so a stray quote can only ever reach the block that contains it. It
is strictly narrower than what it replaces, and it still admits the multi-line quoted supersessions
the corpus legitimately uses (EFFECT-PATH-INVENTORY.yaml, phase-0-baseline-manifest.yaml).

CONDITIONAL PROSE IS EXEMPT ONLY WHEN THE CONDITION GOVERNS THE CLAIM. The predecessor exempted any
window containing `if` / `until` / `unless` / `cannot` / `never` and so on, wherever it fell - and
that is precisely how two of the five live defects escaped:

    "R-07 still recorded OPEN unless the unit is P4 itself"        (unless AFTER the claim)
    "(it keeps R-07 OPEN): ... the residual ... cannot spread."     (cannot AFTER the claim)

Both are assertions with a trailing qualifier, not hypotheticals. A conditional marker therefore
exempts a claim only when it INTRODUCES it - i.e. appears BEFORE the risk id in the same claim
unit, as in "R-07 may not be recorded CONTAINED until the gate asserts empty".
"""

from __future__ import annotations

import re
from dataclasses import dataclass

RISK_ID = "R-07"

OPEN = "OPEN"
CONTAINED = "CONTAINED"

# Closed polarity vocabularies. Negated containment is listed first and matched first.
_NEGATED_CONTAINMENT = re.compile(
    r"\b(?:not|never|no\s+longer|nor)\s+(?:\w+\s+){0,3}?contain(?:ed|ing|s)?\b"
    r"|\buncontained\b",
    re.I,
)
_OPEN_TOKEN = re.compile(r"\bOPEN\b", re.I)
_CONTAINED_TOKEN = re.compile(r"\bCONTAINED\b", re.I)

# `open` as an ordinary adjective naming a register, not asserting a risk's state.
_REGISTER_NOUN = re.compile(
    r"\bopen[-\s]+(?:risk|finding|decision|question|item|issue|blocker|validation|"
    r"table|list|register|section|matter|point|thread)s?\b",
    re.I,
)

_HISTORICAL_MARKER = re.compile(r"\bHISTORICAL\b|\bSUPERSEDED\b", re.I)

# Markers that make a mention hypothetical rather than assertive - but ONLY when they GOVERN the
# polarity token, i.e. fall between the start of the claim unit and the end of that token. A marker
# trailing AFTER the claim qualifies an assertion; it does not turn it into a hypothetical, and
# treating it as one is how two of the five live defects escaped the guard this replaces:
#     "R-07 still recorded OPEN unless the unit is P4 itself"   <- unless AFTER  => LIVE
#     "(it keeps R-07 OPEN): ... the residual ... cannot spread" <- cannot AFTER => LIVE
# versus the legitimate rule, whose modal governs the token:
#     "R-07 may not be marked CONTAINED before this phase completes"             => hypothetical
#
# `requires` / `required` are DELIBERATELY ABSENT. A prescriptive instruction is not a hypothetical,
# and "a supervisor must require R-07 to remain recorded OPEN" is a control-system defect precisely
# BECAUSE it prescribes. Exempting it would re-open the hole this guard exists to close.
_CONDITIONAL = re.compile(
    r"\b(?:if|unless|until|once|when|whenever|while|before|after|should|would|could|"
    r"may\s+not|must\s+not|cannot|can\s+not|can\s+never|never\s+be|shall\s+not|"
    r"so\s+long\s+as|as\s+long\s+as|in\s+order\s+(?:for|to))\b",
    re.I,
)

_TABLE_ROW = re.compile(r"^\s*\|")
# Sentence boundaries only. A colon or semicolon INTRODUCES a claim's value rather than ending it
# ("Current risk: R-07 - OPEN"), so splitting on those would cut a claim in half and lose it - the
# `R-07: OPEN` form is exactly that mistake, and it is one of the forms this guard must catch.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z*#`\[(\"'>-])")


@dataclass(frozen=True)
class StatusClaim:
    """One parsed claim about `risk_id`'s state, with its provenance and any exemption."""

    risk_id: str
    polarity: str          # OPEN | CONTAINED
    line: int              # 1-indexed line in the source document
    excerpt: str           # normalized claim unit, for the failure message
    exemption: str | None  # None => LIVE; otherwise why it is not a live claim

    @property
    def is_live(self) -> bool:
        return self.exemption is None


def normalize(segment: str) -> str:
    """Markdown emphasis and heading marks removed, whitespace runs collapsed to one space.

    This is what makes line-wrapped and `**`-decorated constructions unescapable: the parser never
    sees a line boundary or an emphasis run, so it cannot be evaded by inserting one.
    """
    flat = re.sub(r"[*_`#]+", " ", segment)
    return re.sub(r"\s+", " ", flat).strip()


def strip_historical_blocks(text: str) -> str:
    """Explicitly-labelled <details> blocks may retain superseded claims in place."""
    return re.sub(r"<details>.*?</details>", "", text, flags=re.S)


def _blocks(text: str):
    """Yield (block_text, block_offset). A block is a run of contiguous non-blank lines; a table
    row is always its own block so a row can never merge with the prose around it."""
    lines = text.split("\n")
    buf: list[str] = []
    buf_off = 0
    off = 0
    for line in lines:
        if not line.strip() or _TABLE_ROW.match(line):
            if buf:
                yield "\n".join(buf), buf_off
                buf = []
            if _TABLE_ROW.match(line):
                yield line, off
        else:
            if not buf:
                buf_off = off
            buf.append(line)
        off += len(line) + 1
    if buf:
        yield "\n".join(buf), buf_off


def claim_units(text: str):
    """Yield (unit_text, unit_offset): markdown table cells, then sentences within prose blocks."""
    for block, block_off in _blocks(text):
        if _TABLE_ROW.match(block):
            pos = block_off
            for cell in block.split("|"):
                yield cell, pos
                pos += len(cell) + 1
            continue
        pos = block_off
        for piece in _SENTENCE_SPLIT.split(block):
            idx = text.find(piece, pos) if piece else -1
            yield piece, (idx if idx != -1 else pos)
            pos += len(piece)


def _quoted(text: str, block_start: int, pos: int) -> bool:
    """Inside a double-quoted span, counted from the START OF THE BLOCK (see module docstring)."""
    return text.count('"', block_start, pos) % 2 == 1


def _block_start_for(text: str, pos: int) -> int:
    para = text.rfind("\n\n", 0, pos)
    return 0 if para == -1 else para + 2


def _line_of(text: str, pos: int) -> tuple[int, str]:
    line_no = text.count("\n", 0, pos) + 1
    start = text.rfind("\n", 0, pos) + 1
    end = text.find("\n", pos)
    return line_no, text[start: end if end != -1 else len(text)]


def _polarity(unit_norm: str) -> tuple[str, int] | None:
    """(polarity, end offset of the deciding token) for a normalized unit mentioning the risk id.

    Negated containment is decided FIRST, so `not contained` can never read as `contained`. The
    token's end offset is returned so the caller can ask which modals GOVERN it.
    """
    neg = _NEGATED_CONTAINMENT.search(unit_norm)
    if neg:
        return OPEN, neg.end()
    without_registers = _REGISTER_NOUN.sub(lambda m: " " * len(m.group(0)), unit_norm)
    opn = _OPEN_TOKEN.search(without_registers)
    if opn:
        return OPEN, opn.end()
    con = _CONTAINED_TOKEN.search(unit_norm)
    if con:
        return CONTAINED, con.end()
    return None


def parse_status_claims(text: str, risk_id: str = RISK_ID) -> list[StatusClaim]:
    """Every parsed claim about `risk_id` in `text`, live and exempt alike.

    Returning exempt claims too is deliberate: a caller can then assert that the corpus still
    CONTAINS the status construction, which is what makes the guard fail when the construction
    disappears rather than passing over a document that stopped saying anything.
    """
    body = strip_historical_blocks(text)
    risk_rx = re.compile(re.escape(risk_id), re.I)
    claims: list[StatusClaim] = []
    for unit, unit_off in claim_units(body):
        if not risk_rx.search(unit):
            continue
        norm = normalize(unit)
        if not risk_rx.search(norm):
            continue
        decided = _polarity(norm)
        if decided is None:
            continue
        polarity, token_end = decided

        risk_at = risk_rx.search(unit)
        risk_pos = unit_off + (risk_at.start() if risk_at else 0)
        line_no, line_text = _line_of(body, risk_pos)

        exemption = None
        block_start = _block_start_for(body, risk_pos)
        if _quoted(body, block_start, risk_pos):
            exemption = "quoted"
        elif _HISTORICAL_MARKER.search(line_text):
            exemption = "marked-historical"
        elif _CONDITIONAL.search(norm[:token_end]):
            # a modal that GOVERNS the polarity token - see _CONDITIONAL's note
            exemption = "hypothetical"

        claims.append(
            StatusClaim(risk_id=risk_id, polarity=polarity, line=line_no,
                        excerpt=norm[:160], exemption=exemption)
        )
    return claims


def live_open_claims(text: str, risk_id: str = RISK_ID) -> list[StatusClaim]:
    return [c for c in parse_status_claims(text, risk_id) if c.is_live and c.polarity == OPEN]


def live_contained_claims(text: str, risk_id: str = RISK_ID) -> list[StatusClaim]:
    return [c for c in parse_status_claims(text, risk_id) if c.is_live and c.polarity == CONTAINED]


def live_authority_documents(root) -> list[str]:
    """THE single discovered live-authority population, shared by every status-claim guard.

    It lives here rather than in one test module because the targeted adjudication's finding was
    that the two R-07 guards ran over DIFFERENT corpora - one discovered, one a hard-coded
    four-tuple that could never grow - and only one of them reached the documents where the live
    false claims were. Two guards deriving the same population from one definition is what makes
    "unified" mechanical rather than a claim in a docstring.

    Current-authority documents plus the root control docs and agent lenses, minus the review family
    and everything the authority map classifies as historical. Two principled exclusions, both
    derived rather than hand-listed:

      * THE REGISTRY ITSELF. It is the authority these documents are compared AGAINST, not a
        restatement of it, and it explains the very contradictions these guards remove - a guard
        that fires on the text explaining the defect is the substring-guard failure CLAUDE.md sec 9
        names.
      * FROZEN ACCEPTANCE CONTRACTS (U-*-ACCEPTANCE.yaml). Their criteria record what an agent had
        to state AT ITS OWN MOMENT, bound to an adjudicated result and an independent report.
        Rewriting them would falsify closed history, which no correction may do.
    """
    from control import inventory as inv

    docs = list(inv.current_authority_documents())
    docs += inv.root_control_like_documents() + inv.agent_files() + inv.compatibility_agent_files()
    historical = set(inv.implementation_review_documents()) | set(inv.historical_documents())
    frozen = {d for d in docs if re.search(r"U-[\w-]+-ACCEPTANCE\.yaml$", d)}
    excluded = historical | frozen | {"docs/implementation/IMPLEMENTATION-REGISTRY.yaml"}
    out = sorted({d for d in docs if d not in excluded and (root / d).exists()})
    assert len(out) >= 15, f"the live-authority scan population collapsed to {len(out)}"
    return out
