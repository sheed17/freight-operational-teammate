"""Structured parser for canonical RISK STATUS CLAIMS, and the R-07 claim vocabulary.

WHY THIS EXISTS. The guards this replaces asked whether a copula from a closed three-verb set
(`is` / `stays` / `remains`) FOLLOWED the risk id:

    R-07[^.\\n|]{0,60}?\\b(?:is|stays|remains)\\s+\\*{0,3}(?:OPEN|NOT\\s+CONTAINED|UNCONTAINED)\\b

That is a word-order assumption, and it is structurally blind to the grammar this repository
actually writes canonical status in. It missed every verb-precedes construction (`keeps R-07 OPEN`,
`leaves R-07 open`), every negated-containment construction (`R-07 not contained`, `does not contain
R-07`) and every line-wrapped one. Measured: 8 of 12 relevant forms missed, and 0 of the 5 live
defects caught while the suite reported green.

A third substring alternation would be the same defect a third time. So this module does not match
word order at all. It PARSES:

  1. SEGMENT the document into CLAIM UNITS - whole markdown table ROWS and prose sentences - so a
     claim is bounded by the structure it is written in, and a neighbouring unit's vocabulary cannot
     leak into it.
  2. NORMALIZE each unit - markdown emphasis stripped, whitespace runs collapsed - so `**OPEN**`,
     `### **R-07`, and a construction wrapped across three source lines all read alike.
  3. Decide POLARITY from a CLOSED vocabulary, checking NEGATED containment before plain
     containment, so `not contained` never reads as `contained`.

Word order is irrelevant to every step. `R-07 remains open`, `keeps R-07 open` and
`does not contain R-07` are the same parse.

THE CLAIM UNIT IS THE ROW, NOT THE CELL (this closes R-01). The predecessor split a table row on
`|` and yielded each CELL as an independent claim unit, never re-associating them. That removed the
word-order dependency and installed a CELL-BOUNDARY dependency in its place - and this repository
writes its canonical R-07 status rows with the risk id in one cell and its status in another:

    | **R-07** | Ungated live-write paths | ### **CONTAINED** - recorded in ... |   CURRENT.md
    | **R-07** | ### **CONTAINED.** The containment MECHANISM is built ...      |   CLAUDE.md
    | **R-07 - ungated live-write paths** | ### **CONTAINED** - the mechanism ... |  README.md

Each of those produced TWO units - one with the subject and no polarity, one with the polarity and
no subject - and BOTH were discarded, so the designated status authority, the operating guide and
the public landing document could each be made to read `R-07 - OPEN, NOT CONTAINED` with the entire
guard set green. A markdown table row is ONE RECORD and its cells are that record's FIELDS; subject
in column 1 and status in column 3 is one assertion, not two fragments.

So association is bounded to EXACTLY ONE ROW:

  * WITHIN a row, subject and status associate across any cells, in any column order, with any
    number of descriptive columns before, between or after them.
  * ACROSS rows, never. Two rows are two records, and joining them would let an unrelated row's
    polarity attach to an R-07 row and manufacture a false failure - the unrelated-identifier
    failure mode CLAUDE.md sec 9 names.
  * ACROSS tables, never. A table boundary is a stronger break than a row boundary.
  * BETWEEN a row and the prose around it, never. A table row is always its own unit.

Cells are joined by a literal ` | ` for the polarity decision, which is what bounds the multi-word
patterns: `\\w+` and `[-\\s]+` cannot consume a pipe, so `... is not | contained ...` never reads as
negated containment and `| OPEN | risks |` never reads as the register noun `open risks`. The
association is real; the token sequences are still per-cell.

Header rows and separator/alignment rows are structure, not claims, and are never parsed as claims.
Escaped pipes (`\\|`) do not split a cell. Leading and trailing pipes are optional: a delimiter row
establishes a table, and its header line and following body lines are rows whether or not they carry
an outer pipe. A prose line that merely CONTAINS a pipe is not a table row.

`<details>` IS A PRESENTATION CONTAINER, NOT A TRUTH QUALIFIER (this closes R-02). The predecessor
deleted every `<details>...</details>` region before parsing, under a docstring that claimed to
require an explicit label and code that checked for none. That is not merely a docstring mismatch:
`docs/implementation/CURRENT.md` preserves an incident in which a FALSE TRANSITION CLAIM was planted
inside a `<details>` block, and records the derived control requirement in its own words -

    It sat inside this `<details>` block, where every control guard deliberately stops reading -
    which is exactly why a false claim placed here is MORE dangerous than one in live text, not
    less. ... which is why the roadmap-completeness drift guard reads live text only and REQUIRES
    HISTORICAL BLOCKS TO BE SELF-LABELLING RATHER THAN SILENTLY TRUSTED.

So the default is inverted: details content is PARSED AS LIVE, and is excluded from live counts only
when THAT EXACT BLOCK is self-labelling. The marker must be ATTACHED to the block - found by parsing
the block, never by proximity search - and it must come from the closed vocabulary
`_HISTORICAL_MARKER` (`HISTORICAL` / `SUPERSEDED`), which is the vocabulary every labelled block in
this corpus already uses. It is read from the block's OWN `<summary>`, or, absent one, the first
non-blank line of its OWN body. A label in the prose ABOVE a block exempts nothing: one sentence
placed before a block would otherwise launder everything inside it.

Nesting is depth-tracked, and a block NEVER inherits its parent's label - each block is labelled or
it is read. An unlabelled block nested inside a labelled one is therefore LIVE, which is the
fail-closed direction.

A STRUCTURAL TAG IS A UNIT BOUNDARY (this closes S-03). `details_blocks()` was right about all of
the above and was BYPASSED anyway, one layer down: prose association broke only on blank lines and
table lines, so a marker sentence written IMMEDIATELY above an opener merged with the block's first
content line into one claim unit, and the marker rule below then exempted a claim INSIDE an
unlabelled block using text from OUTSIDE it. Deleting one blank line was the entire attack, and it
also voided the two fail-closed promises above: an unterminated block and an unlabelled block nested
inside a labelled one both became exempt in the no-blank-line arrangement. Prose association now
terminates at every structural `<details>`, `</details>`, `<summary>` and `</summary>` tag, so
classification is IDENTICAL whether or not an author left a blank line. The boundary is the TAG, not
the line carrying it - text inside a `<summary>` is rendered, readable text and remains its own unit,
because a live claim may never disappear because of how this parser segments.

Malformed structure FAILS CLOSED. An unterminated `<details>` grants no exemption at all, so a live
claim can never disappear because the HTML did not parse; a `</details>` with no opener is ignored;
a `<summary>` that is never closed yields no marker. `details_structure_defects()` reports these so
a guard can fail loudly rather than silently widening its blind spot.

Excluded content is EXEMPT AND VISIBLE, never deleted. `parse_status_claims` returns exempt claims
carrying the reason they were exempted, so a caller can still assert the corpus CONTAINS the status
construction. Deleting the text before parsing destroys exactly the auditability the control system
depends on.

STRUCTURAL DECISIONS IGNORE CODE. `<details>`, `</details>` and table pipes inside a fenced code
block or an inline code span are LITERAL MENTIONS, not markup - `CURRENT.md` discusses `<details>`
in backticks INSIDE a `<details>` block, and a depth tracker that counted it would mis-pair every
block after it. The code mask governs STRUCTURE ONLY; it never removes text from a claim, so a
status word inside backticks still counts.

TWO THINGS THIS DELIBERATELY DOES NOT DO.

  * It does not treat every `open` near `R-07` as a status claim. This repository names registers
    with the same word - "Open risks and findings", "an open decision", "the open-risks table" -
    and a guard that fires on those is the unrelated-identifier failure CLAUDE.md sec 9 names.
    `open` immediately qualifying a register noun is not a claim about a risk's state.
  * It does not erase history. A superseded claim survives IN PLACE by being QUOTED, by carrying an
    explicit HISTORICAL / SUPERSEDED marker that GOVERNS it, or by sitting inside a self-labelling
    `<details>` block - the mechanisms the control system already recognises.

QUOTE PARITY IS BOUNDED BY THE CLAIM UNIT'S OWN BLOCK (this closes F-05, and R-04 within it). The
rule this family replaced asked `text.count('"', 0, pos) % 2 == 1` over the WHOLE FILE, so one
unbalanced double quote anywhere silently exempted every later claim to the end of the document.
Its first replacement counted from the preceding blank line - but a markdown table has NO blank
lines between its rows, so the whole table was one parity window and an unbalanced `"` in an early
row exempted every later row of that table. Parity is now counted from the start of the unit's own
block, and a table ROW IS ITS OWN BLOCK, so a stray quote reaches exactly the row that contains it.

THE HISTORICAL MARKER MUST GOVERN THE CLAIM (this closes R-03). The marker was matched anywhere on
the risk id's source line, so `R-07 remains OPEN and NOT CONTAINED today; nothing here is
SUPERSEDED.` exempted itself with a trailing clause. It is now scoped exactly the way `_CONDITIONAL`
is scoped - it must appear BEFORE the risk id, within the claim unit - so one marker discipline
governs this module rather than two contradictory ones.

EXEMPTION IS CLAIM-LOCAL EVEN THOUGH ASSOCIATION IS ROW-WIDE (this closes S-01 and S-02). Ordering
alone was not enough. Both rules above searched the WHOLE ROW-JOINED normalization, because R-01
widened the claim unit to the row and the exemption windows were keyed to that unit - so a word in
any PRECEDING cell qualified a separate cell's value. `| Historical example | unrelated | R-07 |
OPEN - NOT CONTAINED |` read as marked-historical, and `| R-07 | recorded when the gate ran | OPEN |`
read as hypothetical with no adversary present, since `if`, `when`, `before`, `after` and `while` are
ordinary words in an evidence or notes column. Association answers "which subject does this status
belong to" and is correctly ROW-scoped; exemption answers "is this assertion qualified" and is now
CLAIM-LOCAL - the marker must sit in the claim's OWN CELL, before the token it governs. See
`_governing_window_start`. Both axes are needed and neither may be keyed to the other.

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
from functools import lru_cache

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

# THE CLOSED HISTORICAL VOCABULARY. Deliberately unchanged and deliberately NOT widened: every
# self-labelling <details> block in this corpus already marks itself with one of these two words
# ("HISTORICAL - SUPERSEDED DESIGN NOTE", "Historical status ... not authoritative", "Pre-reset
# command list (historical, non-authoritative)"). Widening it - to ARCHIVED, or REJECTED EVIDENCE -
# would be a deliberate act with its own hostile cases, never a loose match; until that is done,
# a block labelled only "REJECTED EVIDENCE" is READ, which is the fail-closed direction.
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

_LEADING_PIPE = re.compile(r"^\s*\|")
# A separator/alignment row cell: `---`, `:---`, `---:`, `:---:`. Structure, never a claim.
_DELIM_CELL = re.compile(r"^:?-+:?$")
# Sentence boundaries only. A colon or semicolon INTRODUCES a claim's value rather than ending it
# ("Current risk: R-07 - OPEN"), so splitting on those would cut a claim in half and lose it - the
# `R-07: OPEN` form is exactly that mistake, and it is one of the forms this guard must catch.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z*#`\[(\"'>-])")

_FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
_BACKTICK_RUN = re.compile(r"`+")
_DETAILS_OPEN = re.compile(r"<details\b[^>]*>", re.I)
_DETAILS_CLOSE = re.compile(r"</details\s*>", re.I)
_SUMMARY = re.compile(r"<summary\b[^>]*>(.*?)</summary\s*>", re.I | re.S)
# The individual `<summary>` delimiters. `_SUMMARY` above matches an OPEN..CLOSE PAIR and is what
# reads a block's label; these match each tag on its own and exist only to bound prose association
# (S-03), which must happen whether or not the pair is well formed.
_SUMMARY_OPEN = re.compile(r"<summary\b[^>]*>", re.I)
_SUMMARY_CLOSE = re.compile(r"</summary\s*>", re.I)
_STRUCTURAL_TAGS = (_DETAILS_OPEN, _DETAILS_CLOSE, _SUMMARY_OPEN, _SUMMARY_CLOSE)

# The cell separator used to join a row's cells for the polarity decision. The pipe is what bounds
# the multi-word patterns to a single cell while the ASSOCIATION spans the row - see the docstring.
_CELL_JOIN = " | "


@dataclass(frozen=True)
class StatusClaim:
    """One parsed claim about `risk_id`'s state, with its provenance and any exemption.

    The table-row fields are populated for a claim parsed out of a markdown table row and are
    `None` for a prose claim. They exist so a failure message can name WHICH CELL asserted the
    polarity: an unlocalized failure is not actionable, and naming the defect is this guard's whole
    value.
    """

    risk_id: str
    polarity: str          # OPEN | CONTAINED
    line: int              # 1-indexed line in the source document
    excerpt: str           # normalized claim unit, for the failure message
    exemption: str | None  # None => LIVE; otherwise why it is not a live claim
    kind: str = "sentence"           # "table-row" | "sentence"
    table_id: int | None = None      # 1-indexed table within the document
    row_index: int | None = None     # 0-indexed row within that table
    cells: tuple[str, ...] = ()      # the row's normalized cells, in order
    subject_cell: int | None = None  # index of the cell naming the risk id
    status_cell: int | None = None   # index of the cell carrying the polarity token

    @property
    def is_live(self) -> bool:
        return self.exemption is None

    @property
    def where(self) -> str:
        """A precise, human-readable location - the row and the two cells that made the claim."""
        if self.kind != "table-row":
            return f"line {self.line}"
        return (f"line {self.line}, table {self.table_id} row {self.row_index}, "
                f"subject cell {self.subject_cell} -> status cell {self.status_cell}")


@dataclass(frozen=True)
class TableRow:
    """One markdown table row, kept whole. The bounded unit R-01 requires."""

    line: int                       # 1-indexed source line
    offset: int                     # absolute offset of the line start
    table_id: int
    row_index: int
    role: str                       # "header" | "separator" | "body"
    raw: str                        # the source line
    cells: tuple[str, ...]          # raw cell text, outer pipes trimmed
    cell_offsets: tuple[int, ...]   # absolute offset of each cell


@dataclass(frozen=True)
class DetailsBlock:
    """One `<details>` region, with the label attached to IT and nothing else."""

    open_start: int
    body_start: int
    body_end: int
    close_end: int
    depth: int
    marker: str | None   # the self-label that exempts it; None => the block is LIVE
    closed: bool

    @property
    def is_historical(self) -> bool:
        return self.marker is not None


@dataclass(frozen=True)
class ClaimUnit:
    """A bounded region of a document within which a subject and a status may associate."""

    text: str                      # raw source text of the unit
    norm: str                      # normalized text, used for every vocabulary decision
    offset: int                    # absolute offset of the unit start
    block_start: int               # where quote parity is counted from
    line: int                      # 1-indexed line the unit starts on
    kind: str                      # "table-row" | "sentence"
    table_id: int | None = None
    row_index: int | None = None
    cells: tuple[str, ...] = ()          # normalized cells, in order
    cell_spans: tuple[tuple[int, int], ...] = ()   # each cell's [start, end) within `norm`


def normalize(segment: str) -> str:
    """Markdown emphasis and heading marks removed, whitespace runs collapsed to one space.

    This is what makes line-wrapped and `**`-decorated constructions unescapable: the parser never
    sees a line boundary or an emphasis run, so it cannot be evaded by inserting one.
    """
    flat = re.sub(r"[*_`#]+", " ", segment)
    return re.sub(r"\s+", " ", flat).strip()


# ------------------------------------------------------------------ structural code mask

@lru_cache(maxsize=64)
def _code_mask(text: str) -> bytes:
    """1 where a character sits inside a fenced code block or an inline code span.

    STRUCTURE ONLY. This decides whether `<details>` is markup or a literal mention, and whether a
    pipe delimits a table cell. It NEVER removes text from a claim: a polarity word inside backticks
    is still a polarity word.
    """
    mask = bytearray(len(text))
    pos = 0
    fence: str | None = None
    for line in text.split("\n"):
        end = min(pos + len(line) + 1, len(text))
        m = _FENCE.match(line)
        if fence is None:
            if m:
                fence = m.group(1)[0]
                mask[pos:end] = b"\x01" * (end - pos)
            else:
                _mask_inline_code(line, pos, mask)
        else:
            mask[pos:end] = b"\x01" * (end - pos)
            if m and m.group(1)[0] == fence:
                fence = None
        pos += len(line) + 1
    return bytes(mask)


def _mask_inline_code(line: str, base: int, mask: bytearray) -> None:
    """A code span opens on a run of N backticks and closes on the next run of exactly N."""
    runs = list(_BACKTICK_RUN.finditer(line))
    i = 0
    while i < len(runs):
        n = len(runs[i].group(0))
        j = i + 1
        while j < len(runs) and len(runs[j].group(0)) != n:
            j += 1
        if j < len(runs):
            lo, hi = base + runs[i].start(), min(base + runs[j].end(), len(mask))
            mask[lo:hi] = b"\x01" * (hi - lo)
            i = j + 1
        else:
            i += 1


def _in_code(text: str, pos: int) -> bool:
    mask = _code_mask(text)
    return pos < len(mask) and mask[pos] == 1


# ------------------------------------------------------------------ <details> classification

def details_blocks(text: str) -> tuple[list[DetailsBlock], list[int]]:
    """Every `<details>` region, depth-tracked, each labelled ONLY by its own attached marker.

    Returns (blocks, stray_close_offsets). An unterminated block is returned with `closed=False`
    and `marker=None`: it grants no exemption, so malformed markup can never hide a live claim.
    """
    tokens: list[tuple[int, int, str]] = []
    for m in _DETAILS_OPEN.finditer(text):
        if not _in_code(text, m.start()):
            tokens.append((m.start(), m.end(), "open"))
    for m in _DETAILS_CLOSE.finditer(text):
        if not _in_code(text, m.start()):
            tokens.append((m.start(), m.end(), "close"))
    tokens.sort()

    stack: list[tuple[int, int]] = []
    blocks: list[DetailsBlock] = []
    stray: list[int] = []
    for start, end, kind in tokens:
        if kind == "open":
            stack.append((start, end))
        elif stack:
            open_start, body_start = stack.pop()
            blocks.append(_build_block(text, open_start, body_start, start, end, len(stack), True))
        else:
            stray.append(start)
    for open_start, body_start in stack:      # UNTERMINATED -> fails closed
        blocks.append(
            DetailsBlock(open_start=open_start, body_start=body_start, body_end=len(text),
                         close_end=len(text), depth=0, marker=None, closed=False)
        )
    blocks.sort(key=lambda b: b.body_start)
    return blocks, stray


def _build_block(text: str, open_start: int, body_start: int,
                 body_end: int, close_end: int, depth: int, closed: bool) -> DetailsBlock:
    """The label must be ATTACHED: this block's own <summary>, or its own first non-blank line."""
    body = text[body_start:body_end]
    source: str | None = None

    if body.lstrip().lower().startswith("<summary"):
        # The block declares a <summary>, so THAT is its label and nothing else may stand in for
        # it. A <summary> that is never closed is MALFORMED and yields NO marker - failing closed,
        # because otherwise `<summary>HISTORICAL` with the closing tag deleted would still exempt
        # the block while `details_structure_defects()` reported the damage to nobody.
        summary = _SUMMARY.search(body)
        if summary and not body[:summary.start()].strip():
            source = summary.group(1)
    else:
        for line in body.split("\n"):
            if line.strip():
                # A NESTED block's own opener is not this block's label. Blocks never inherit, in
                # either direction: an inner label must not exempt its parent, and a parent's label
                # must not exempt an unlabelled child.
                if not _DETAILS_OPEN.search(line):
                    source = line
                break

    marker = None
    if source and _HISTORICAL_MARKER.search(normalize(source)):
        marker = " ".join(source.split())[:120]
    return DetailsBlock(open_start=open_start, body_start=body_start, body_end=body_end,
                        close_end=close_end, depth=depth, marker=marker, closed=closed)


def _innermost_block(blocks: list[DetailsBlock], pos: int) -> DetailsBlock | None:
    """The block that most tightly encloses `pos`. Innermost wins - labels never inherit."""
    best: DetailsBlock | None = None
    for b in blocks:
        if b.body_start <= pos < b.body_end and (best is None or b.body_start > best.body_start):
            best = b
    return best


def details_structure_defects(text: str) -> list[str]:
    """Malformed `<details>` structure, so a guard can fail LOUDLY instead of silently widening.

    Parsing still fails closed on every case here; this reports them so the defect is visible.
    """
    blocks, stray = details_blocks(text)
    defects = [f"unterminated <details> at offset {b.open_start} (line "
               f"{text.count(chr(10), 0, b.open_start) + 1}) - it grants NO exemption"
               for b in blocks if not b.closed]
    defects += [f"</details> with no matching <details> at offset {s} (line "
                f"{text.count(chr(10), 0, s) + 1})" for s in stray]
    for b in blocks:
        if b.closed and "<summary" in text[b.body_start:b.body_end].lower():
            if not _SUMMARY.search(text[b.body_start:b.body_end]):
                defects.append(f"<summary> is never closed in the <details> block at line "
                               f"{text.count(chr(10), 0, b.open_start) + 1} - it yields NO marker")
    return defects


def strip_historical_blocks(text: str) -> str:
    """Blank out ONLY self-labelling historical `<details>` bodies, preserving every offset.

    Live text is returned unchanged, so line numbers computed on the result are the document's real
    line numbers. An UNLABELLED block is left intact - it is live content, and the whole point of
    R-02 is that it must be read. An unlabelled block NESTED INSIDE a labelled one is restored, so
    a parent's label can never launder a child.
    """
    blocks, _ = details_blocks(text)
    if not blocks:
        return text
    out = list(text)
    for b in blocks:                     # sorted outermost-first by body_start
        for i in range(b.body_start, min(b.body_end, len(out))):
            if b.marker:
                if text[i] != "\n":
                    out[i] = " "
            else:
                out[i] = text[i]
    return "".join(out)


# ------------------------------------------------------------------ table structure

def _split_cells(row: str) -> list[tuple[int, str]]:
    """Split a row on UNESCAPED pipes only. `\\|` is content, not a delimiter."""
    cells: list[tuple[int, str]] = []
    start = i = 0
    n = len(row)
    while i < n:
        if row[i] == "\\" and i + 1 < n:
            i += 2
            continue
        if row[i] == "|":
            cells.append((start, row[start:i]))
            start = i + 1
        i += 1
    cells.append((start, row[start:]))
    return cells


def _trim_outer(cells: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """Drop the empty fragments produced by a leading and/or trailing pipe - and only those."""
    if len(cells) > 1 and not cells[0][1].strip():
        cells = cells[1:]
    if len(cells) > 1 and not cells[-1][1].strip():
        cells = cells[:-1]
    return cells


def _has_unescaped_pipe(line: str) -> bool:
    return len(_split_cells(line)) > 1


def _is_delimiter(cells: list[tuple[int, str]]) -> bool:
    return bool(cells) and all(_DELIM_CELL.match(c.strip()) for _, c in cells)


def table_rows(text: str) -> list[TableRow]:
    """Every markdown table row in `text`, grouped into tables and classified.

    A line is a row when it starts with a pipe, OR when a delimiter row establishes a table around
    it - which is what admits GFM's optional leading/trailing pipes without ever mistaking a prose
    line that merely contains a pipe for a table row. Lines inside code are never rows.
    """
    lines = text.split("\n")
    offsets: list[int] = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line) + 1

    def structural(i: int) -> bool:
        return bool(lines[i].strip()) and not _in_code(text, offsets[i])

    kind = ["prose"] * len(lines)
    for i, line in enumerate(lines):
        if structural(i) and _LEADING_PIPE.match(line):
            kind[i] = "row"

    for i, line in enumerate(lines):
        if not structural(i) or not _has_unescaped_pipe(line):
            continue
        if not _is_delimiter(_trim_outer(_split_cells(line))):
            continue
        kind[i] = "delim"
        if i and structural(i - 1) and _has_unescaped_pipe(lines[i - 1]):
            kind[i - 1] = "row"          # the header sits immediately above its delimiter
        j = i + 1
        while j < len(lines) and structural(j) and _has_unescaped_pipe(lines[j]):
            if kind[j] == "prose":
                kind[j] = "row"
            j += 1

    rows: list[TableRow] = []
    table_id = 0
    i = 0
    while i < len(lines):
        if kind[i] == "prose":
            i += 1
            continue
        start = i
        while i < len(lines) and kind[i] != "prose":
            i += 1
        table_id += 1
        for row_index, li in enumerate(range(start, i)):
            if kind[li] == "delim":
                role = "separator"
            elif li + 1 < i and kind[li + 1] == "delim":
                role = "header"
            else:
                role = "body"
            cells = _trim_outer(_split_cells(lines[li]))
            rows.append(TableRow(
                line=li + 1, offset=offsets[li], table_id=table_id, row_index=row_index,
                role=role, raw=lines[li],
                cells=tuple(c for _, c in cells),
                cell_offsets=tuple(offsets[li] + o for o, _ in cells),
            ))
    return rows


# ------------------------------------------------------------------ claim units

def _row_unit(row: TableRow) -> ClaimUnit:
    """One row, one unit. Cells are joined so subject and status associate WITHIN the row only."""
    parts = [normalize(c) for c in row.cells]
    spans: list[tuple[int, int]] = []
    at = 0
    for p in parts:
        spans.append((at, at + len(p)))
        at += len(p) + len(_CELL_JOIN)
    return ClaimUnit(
        text=row.raw, norm=_CELL_JOIN.join(parts), offset=row.offset, block_start=row.offset,
        line=row.line, kind="table-row", table_id=row.table_id, row_index=row.row_index,
        cells=tuple(parts), cell_spans=tuple(spans),
    )


@lru_cache(maxsize=64)
def _structural_tag_spans(text: str) -> tuple[tuple[int, int], ...]:
    """Every `<details>` / `</details>` / `<summary>` / `</summary>` tag that is MARKUP, in order.

    Tags inside code are literal mentions, not structure - the same rule `details_blocks()` uses,
    and for the same reason: `CURRENT.md` discusses `<details>` in backticks INSIDE a `<details>`
    block, and a boundary drawn at that mention would split a sentence that is only talking about
    markup.
    """
    spans: list[tuple[int, int]] = []
    opens: list[int] = []
    for rx in _STRUCTURAL_TAGS:
        for m in rx.finditer(text):
            if not _in_code(text, m.start()):
                spans.append((m.start(), m.end()))
                if rx is _SUMMARY_OPEN:
                    opens.append(m.start())
    spans.sort()

    # AN UNTERMINATED <summary> IS BOUNDED BY ITS OWN LINE. `_build_block` already refuses to read a
    # marker out of a malformed summary - but if that summary's text were allowed to run on into the
    # block body, the prose rule below would grant `marked-historical` from a label this module has
    # just declared void. That is the malformed-block fail-closed promise being defeated from behind,
    # and it is the one arrangement the tag boundaries alone do not close: there is no closing tag to
    # be a boundary. Without a `</summary>` the element cannot extend past the line that opens it.
    closers = {s for s, e in spans if _SUMMARY_CLOSE.match(text, s, e)}
    for start in opens:
        following = [s for s, _ in spans if s > start]
        if not following or following[0] not in closers:
            nl = text.find("\n", start)
            if nl != -1:
                spans.append((nl, nl + 1))
    spans.sort()
    return tuple(spans)


def _prose_blocks(text: str, table_lines: set[int]):
    """Contiguous non-blank prose, bounded by every structure that can contain a claim.

    A run breaks on a blank line; on a table line, so a row can never merge with the prose around
    it, nor prose with a row; and - THIS CLOSES S-03 - at every structural `<details>`, `</details>`,
    `<summary>` and `</summary>` tag.

    Without the tag boundary a marker sentence written IMMEDIATELY above an opener (no blank line)
    merged with the block's first content line into ONE claim unit, and the row-prefix marker rule
    then exempted a claim INSIDE the block using text from OUTSIDE it - `marked-historical`, granted
    behind `details_blocks()`'s back, on a block `details_blocks()` had correctly refused to label.
    The same merge voided two of this module's advertised fail-closed guarantees: an unterminated
    block and an unlabelled block nested inside a labelled one both became exempt when written
    without separating blank lines. Classification must not depend on whether an author left a blank
    line, and now it does not.

    The boundary is the TAG, not the line that carries it: the tag's own text belongs to no unit,
    and the text on either side of it belongs to DIFFERENT units. Breaking on the whole line would
    silently DELETE a claim written inside a `<summary>` - `<summary>R-07 - OPEN</summary>` is
    rendered, readable text, and a live claim may never disappear because of how this parser
    segments. It stays its own unit.
    """
    lines = text.split("\n")
    tags = _structural_tag_spans(text)
    first = 0
    run_start: int | None = None
    run_end = 0
    off = 0

    def flush():
        nonlocal run_start
        if run_start is not None:
            yielded = (text[run_start:run_end], run_start)
            run_start = None
            return yielded
        return None

    for i, line in enumerate(lines):
        line_start, line_end = off, off + len(line)
        off += len(line) + 1
        if not line.strip() or (i + 1) in table_lines:
            out = flush()
            if out:
                yield out
            continue
        while first < len(tags) and tags[first][1] <= line_start:
            first += 1
        cursor = line_start
        k = first
        # `<=` admits the synthetic end-of-line boundary an unterminated <summary> installs; no real
        # tag can start at `line_end`, which is the newline itself.
        while k < len(tags) and tags[k][0] <= line_end:
            tag_start, tag_end = tags[k]
            piece_end = max(cursor, min(tag_start, line_end))
            if text[cursor:piece_end].strip():
                if run_start is None:
                    run_start = cursor
                run_end = piece_end
            out = flush()
            if out:
                yield out
            cursor = max(cursor, min(tag_end, line_end))
            k += 1
        if text[cursor:line_end].strip():
            if run_start is None:
                run_start = cursor
            run_end = line_end
    out = flush()
    if out:
        yield out


def claim_units(text: str) -> list[ClaimUnit]:
    """Every bounded region in which a subject and a status may associate, in document order."""
    rows = table_rows(text)
    table_lines = {r.line for r in rows}
    units = [_row_unit(r) for r in rows if r.role == "body"]

    for block, block_off in _prose_blocks(text, table_lines):
        pos = block_off
        for piece in _SENTENCE_SPLIT.split(block):
            idx = text.find(piece, pos) if piece else -1
            offset = idx if idx != -1 else pos
            units.append(ClaimUnit(
                text=piece, norm=normalize(piece), offset=offset, block_start=block_off,
                line=text.count("\n", 0, offset) + 1, kind="sentence",
            ))
            pos += len(piece)
    units.sort(key=lambda u: (u.offset, u.kind))
    return units


def _quoted(text: str, block_start: int, pos: int) -> bool:
    """Inside a double-quoted span, counted from the START OF THE UNIT'S BLOCK - which for a table
    row is that ROW, so a stray quote can never reach the next row (see the module docstring)."""
    return text.count('"', block_start, pos) % 2 == 1


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _polarity(unit_norm: str) -> tuple[str, int, int] | None:
    """(polarity, start, end) of the deciding token in a normalized unit mentioning the risk id.

    Negated containment is decided FIRST, so `not contained` can never read as `contained`. The
    token's offsets are returned so the caller can ask which modals GOVERN it and which CELL it
    fell in.
    """
    neg = _NEGATED_CONTAINMENT.search(unit_norm)
    if neg:
        return OPEN, neg.start(), neg.end()
    without_registers = _REGISTER_NOUN.sub(lambda m: " " * len(m.group(0)), unit_norm)
    opn = _OPEN_TOKEN.search(without_registers)
    if opn:
        return OPEN, opn.start(), opn.end()
    con = _CONTAINED_TOKEN.search(unit_norm)
    if con:
        return CONTAINED, con.start(), con.end()
    return None


def _cell_at(unit: ClaimUnit, norm_pos: int) -> int | None:
    for idx, (lo, hi) in enumerate(unit.cell_spans):
        if lo <= norm_pos < hi:
            return idx
    return None


def _governing_window_start(unit: ClaimUnit, norm_pos: int) -> int:
    """The EARLIEST offset at which a marker may sit and still GOVERN the claim at `norm_pos`.

    ASSOCIATION AND EXEMPTION ARE DIFFERENT AXES, AND THIS IS WHERE THEY SEPARATE (S-01, S-02).

    R-01 correctly widened the CLAIM UNIT from one cell to one row, so that a subject in column 1
    and a status in column 3 could be read as the one assertion they are. Both exemption rules were
    then left keyed to that widened unit, so the EXEMPTION WINDOW widened with it - and a word in
    ANY preceding cell began qualifying a separate cell's value:

        | Conditional | if X happens | R-07 | OPEN - NOT CONTAINED |   -> wrongly `hypothetical`
        | Historical example | unrelated | R-07 | OPEN - NOT CONTAINED | -> wrongly `marked-historical`

    That fires ACCIDENTALLY, not only adversarially: `if`, `when`, `before`, `after` and `while` are
    ordinary English words that occur constantly in evidence, description and notes columns, so
    `| R-07 | recorded when the gate ran | OPEN |` launders itself with no adversary present.

    A markdown row is ONE RECORD and its cells are that record's FIELDS. A qualifier in one field
    does not qualify another field's value. So ASSOCIATION stays row-scoped - subject and status
    still associate across cells, in any column order, which is R-01 and is untouched - while
    EXEMPTION is CLAIM-LOCAL: the window starts at the beginning of the claim's OWN cell.

    Prose units have no cells, so their window is the whole unit exactly as before.

    If a position cannot be resolved to a cell at all - it fell in the ` | ` join, which no
    vocabulary token can start in - the window collapses to the position itself. That admits no
    preceding text, which is the fail-closed direction: an unresolvable offset must not silently
    restore the row-wide search this exists to remove.
    """
    if unit.kind != "table-row" or not unit.cell_spans:
        return 0
    idx = _cell_at(unit, norm_pos)
    if idx is None:
        return norm_pos
    return unit.cell_spans[idx][0]


def parse_status_claims(text: str, risk_id: str = RISK_ID) -> list[StatusClaim]:
    """Every parsed claim about `risk_id` in `text`, live and exempt alike.

    Returning exempt claims too is deliberate: a caller can then assert that the corpus still
    CONTAINS the status construction, which is what makes the guard fail when the construction
    disappears rather than passing over a document that stopped saying anything. It is also what
    keeps historical evidence AUDITABLE - an excluded claim stays visible AS excluded, rather than
    being deleted before anyone can see it.
    """
    blocks, _ = details_blocks(text)
    risk_rx = re.compile(re.escape(risk_id), re.I)
    claims: list[StatusClaim] = []

    for unit in claim_units(text):
        if not risk_rx.search(unit.text):
            continue
        risk_in_norm = risk_rx.search(unit.norm)
        if not risk_in_norm:
            continue
        decided = _polarity(unit.norm)
        if decided is None:
            continue
        polarity, token_start, token_end = decided

        risk_raw = risk_rx.search(unit.text)
        risk_pos = unit.offset + (risk_raw.start() if risk_raw else 0)
        line_no = unit.line if unit.kind == "table-row" else _line_of(text, risk_pos)

        block = _innermost_block(blocks, risk_pos)
        exemption: str | None = None
        if block is not None and block.is_historical:
            exemption = "historical-details"
        elif _quoted(text, unit.block_start, risk_pos):
            exemption = "quoted"
        elif _HISTORICAL_MARKER.search(
                unit.norm[_governing_window_start(unit, risk_in_norm.start()):risk_in_norm.start()]):
            # The marker must GOVERN the claim: BEFORE the risk id (R-03) and, for a row, inside the
            # SUBJECT'S OWN CELL (S-02). A marker in an unrelated column is a different field.
            exemption = "marked-historical"
        elif _CONDITIONAL.search(
                unit.norm[_governing_window_start(unit, token_start):token_end]):
            # A modal that GOVERNS the polarity token: BEFORE it (R-03) and, for a row, inside the
            # STATUS TOKEN'S OWN CELL (S-01). See _governing_window_start.
            exemption = "hypothetical"

        claims.append(StatusClaim(
            risk_id=risk_id, polarity=polarity, line=line_no,
            excerpt=unit.norm[:160], exemption=exemption, kind=unit.kind,
            table_id=unit.table_id, row_index=unit.row_index, cells=unit.cells,
            subject_cell=_cell_at(unit, risk_in_norm.start()),
            status_cell=_cell_at(unit, token_start),
        ))
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
