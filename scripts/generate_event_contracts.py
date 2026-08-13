#!/usr/bin/env python3
"""Derive the canonical event contracts from the specification into a runtime data file.

WHY THIS SCRIPT EXISTS AT ALL

`docs/specifications/events/registry.md` §6 says the registry "is the sole canonical list of event
names and versions". A runtime that hand-transcribed those names would be a SECOND authority for
the same list, and the two would drift — this repository has the scar tissue to prove it. So the
names, versions, producers, payload contracts, consequential set and strict-order families are
DERIVED, mechanically, from the specification that already governs them.

WHY THE OUTPUT IS A COMMITTED FILE AND NOT AN IMPORT-TIME PARSE

`pyproject.toml` packages `src/freight_recon` and nothing else: `docs/` is not in the wheel. A
runtime that parsed the markdown on import would work in this checkout and fail wherever the
package is actually installed. So the derivation runs HERE, the result is committed as
`src/freight_recon/event_contracts_data.json`, and
`eval/tests/test_p5_event_contracts.py::test_the_generated_contract_data_is_exactly_what_the_specification_derives`
re-runs this derivation and fails the build if the committed file is one character stale. The
specification stays the single authority; the generated file is a build artifact that cannot drift
without the suite going red.

    python3 scripts/generate_event_contracts.py            # rewrite the data file
    python3 scripts/generate_event_contracts.py --check    # exit 1 if it is stale

THE FOUR SOURCES, AND WHAT EACH ONE DECIDES

    events/registry.md §3      the NAMES, their family, their producer transitions, ‡coordination
    events/registry.md §5      which events are CONSEQUENTIAL (must pin the decision context)
    events/registry.md §8      which families require STRICT per-aggregate ordering
    events/NN-*.md             per-event PAYLOAD contracts, and each family's aggregate_type default

§3 is the binding list; a family file that named an event §3 does not list would be defective, and
the derivation asserts the two agree in BOTH directions rather than trusting either.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVENTS = ROOT / "docs" / "specifications" / "events"
TARGET = ROOT / "src" / "freight_recon" / "event_contracts_data.json"

# The F15 "Coordination" file is a LENS over cross-machine consumption and declares no contract
# (registry §9). Its rows re-list events that already belong to F3/F7/F11/F14, so reading it as a
# contract source would silently overwrite four real contracts with a summary of themselves.
LENS_FAMILY = "F15"

_TRANSITION_ID = re.compile(r"^[A-Z]{2}-[0-9]+[a-z]*$")


# ------------------------------------------------------------------------------ small utilities

def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def strip_emphasis(text: str) -> str:
    """Markdown emphasis carries no meaning here. `### ` is this corpus's "look at this" marker."""
    return text.replace("###", "").replace("**", "").strip()


def split_top_level(text: str, separator: str = ",") -> list[str]:
    """Split on `separator`, ignoring separators inside (), {} or backticks.

    Necessary because a payload term's annotation legitimately contains commas —
    `caps_evaluated`(R — each cap id with its limit, and the observed value) is ONE term, and a
    naive `text.split(",")` turns it into three fields nobody declared.
    """
    parts: list[str] = []
    depth_paren = depth_brace = 0
    in_tick = False
    current: list[str] = []
    for ch in text:
        if ch == "`":
            in_tick = not in_tick
        elif not in_tick:
            if ch == "(":
                depth_paren += 1
            elif ch == ")":
                depth_paren = max(0, depth_paren - 1)
            elif ch == "{":
                depth_brace += 1
            elif ch == "}":
                depth_brace = max(0, depth_brace - 1)
        if ch == separator and not in_tick and depth_paren == 0 and depth_brace == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(ch)
    parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def markdown_rows(path: Path) -> list[tuple[list[str], list[str]]]:
    """Every data row of every table in one file, as (headers, cells).

    Escape-aware split on `(?<!\\)\\|`, the same correction `test_bootstrap_hermeticity` carries:
    without it a cell containing `H\\|S` shifts every later column by one.
    """
    out: list[tuple[list[str], list[str]]] = []
    headers: list[str] | None = None
    for line in read(path).split("\n"):
        if not line.strip().startswith("|"):
            headers = None
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line)[1:-1]]
        if not cells:
            continue
        if re.sub(r"[*`\s]", "", cells[0]).lower().startswith("event"):
            headers = cells
            continue
        if headers is None or re.match(r"^[-: ]+$", cells[0]):
            continue
        out.append((headers, cells))
    return out


def column(headers: list[str], cells: list[str], prefix: str) -> str:
    flat = [re.sub(r"[*`\s]", "", h).lower() for h in headers]
    index = next((i for i, h in enumerate(flat) if h.startswith(prefix)), None)
    if index is None or index >= len(cells):
        return ""
    return cells[index]


# ------------------------------------------------------------------- §3: names and their producers

def expand_producers(raw: str | None) -> tuple[str, ...]:
    """`EF-3u/4c/4u` ⇒ EF-3u, EF-4c, EF-4u. The corpus abbreviates a repeated machine prefix.

    Anything that is not transition-shaped after expansion is DROPPED, not guessed at: §3 writes
    F14's producers as prose (`any machine, GR-1`, `detector`, `inbox`), and a rule id is not a
    transition. Those contracts simply carry no producer set, and the validator does not check a
    producer it was never given.
    """
    if not raw:
        return ()
    out: list[str] = []
    prefix: str | None = None
    for token in re.split(r"[/\s,]+", raw.strip()):
        if not token:
            continue
        m = re.match(r"^([A-Z]{2})-(\d+[a-z]*)", token)
        if m:
            prefix = m.group(1)
            out.append(f"{prefix}-{m.group(2)}")
            continue
        m = re.match(r"^(\d+[a-z]*)$", token)
        if m and prefix:
            out.append(f"{prefix}-{m.group(1)}")
    seen: list[str] = []
    for tid in out:
        if not _TRANSITION_ID.match(tid) or tid in seen:
            continue
        # ### `GR-n` IS A GLOBAL RULE, NOT A TRANSITION (registry §10, GR-1..GR-16). It is
        # transition-SHAPED, so the regex above accepts it, and §3 writes F14's producer as
        # `IllegalTransitionAttempted‡(any machine, GR-1)`. Left in, it made the runtime demand
        # that an illegal-transition record be attributed to a rule id — refusing the event no
        # matter which real transition attempted the illegal move, which is every one of them.
        # This is the one prefix that is shaped like a transition and is not one.
        if tid.startswith("GR-"):
            continue
        seen.append(tid)
    return tuple(seen)


def parse_canonical_list() -> list[dict]:
    """§3 — the binding name list. One entry per declared contract, F15 excluded (§9)."""
    text = read(EVENTS / "registry.md")
    try:
        section = text.split("## 3. CANONICAL EVENT LIST")[1].split("## 4.")[0]
    except IndexError:  # pragma: no cover - a restructured registry must fail loudly
        raise SystemExit("events/registry.md §3 not found — the canonical list cannot be derived")
    declared: list[dict] = []
    for line in section.split("\n"):
        family = re.match(r"^\*\*(F\d+)\s", line)
        if not family:
            continue
        if family.group(1) == LENS_FAMILY:
            continue
        for m in re.finditer(r"`([A-Za-z][A-Za-z0-9]*)`(‡?)(?:\(([^)]*)\))?", line):
            declared.append({
                "name": m.group(1),
                "family": family.group(1),
                "coordination": m.group(2) == "‡",
                "producers": expand_producers(m.group(3)),
            })
    if not declared:
        raise SystemExit("events/registry.md §3 parsed to zero contracts — refusing to emit")
    return declared


def parse_consequential() -> tuple[str, ...]:
    """§5's CONSEQUENTIAL list, read from the LIST LINE ONLY.

    The amendment note beneath the list also names `PolicyApproved`; reading the prose as the list
    would let the list itself be emptied while a guard stayed green. That is F-05, and this is the
    same defence `_consequential_events` uses.
    """
    text = read(EVENTS / "registry.md")
    section = text.split("## 5. WHICH EVENTS ARE CONSEQUENTIAL")[1].split("\n## ")[0]
    listing = [l for l in section.split("\n") if l.strip().startswith("`")]
    if len(listing) != 1:
        raise SystemExit(
            f"events/registry.md §5 has {len(listing)} list lines; exactly one is required for the "
            f"CONSEQUENTIAL set to be decidable"
        )
    names = tuple(re.findall(r"`([A-Za-z][A-Za-z0-9]*)`", listing[0]))
    if not names:
        raise SystemExit("events/registry.md §5 parsed to an empty CONSEQUENTIAL set")
    return names


def parse_conditionally_consequential() -> tuple[str, ...]:
    """§5 members whose membership carries a QUALIFIER, e.g.

        `ClaimConfirmed`(when it backs a money action)

    ### A QUALIFIER IS NOT DECORATION, AND THIS FILE ALREADY HONOURS TWO OTHERS. §5 qualifies
    `material_facts_fingerprint` with "where an amount is involved" (so it is not required
    unconditionally — debt U53-D3), and `ClaimConfirmed`'s family row qualifies its human-actor
    requirement with "`OWNER_ASSERTED` requires" (so it is not in `HUMAN_ONLY_EVENTS`). This is the
    third conditional on the same list and it was being discarded: every `ClaimConfirmed` was
    forced to pin a decision context, so an ordinary deterministic `LINKER_INFERRED` binding that
    backs no money action was refused on a rule §5 does not apply to it.

    Whether a binding backs a money action is a property of the DECISION, not of the envelope, so
    this layer cannot decide it — exactly as with the fingerprint. The honest outcome is to record
    conditional membership and not enforce the pins for it.
    """
    text = read(EVENTS / "registry.md")
    section = text.split("## 5. WHICH EVENTS ARE CONSEQUENTIAL")[1].split("\n## ")[0]
    listing = [l for l in section.split("\n") if l.strip().startswith("`")]
    if len(listing) != 1:
        raise SystemExit("events/registry.md §5 has no single list line")
    return tuple(re.findall(r"`([A-Za-z][A-Za-z0-9]*)`\s*\(", listing[0]))


def parse_strict_order_families() -> tuple[str, ...]:
    """§8's strict-order families — the LEFT half of a line that carries BOTH halves.

    ### THE TRAP THIS FUNCTION EXISTS TO AVOID. §8 writes the whole ordering split on ONE line:

        - **Strict per-aggregate ordering REQUIRED:** F2 … F3 … F4 … F11 … F13 …
          **Order-tolerant:** F5 Observation …, F7 Conflict …, F9 Exception, F14 Security …

    Selecting that line and running `re.findall(r"F\\d+")` over it harvests the ORDER-TOLERANT
    families too, and marks F5, F7, F9 and F14 strict — the exact opposite of what the registry
    says, for 31 of 118 contracts. It is silent because nothing in this unit reads the flag yet;
    P6's consumers would have been the ones to find out.

    So the line is split on the second half's label first, and both halves are returned to the
    caller's assertion that they are disjoint.
    """
    text = read(EVENTS / "registry.md")
    section = text.split("## 8. ORDERING")[1].split("\n## ")[0]
    line = next((l for l in section.split("\n") if "Strict per-aggregate ordering REQUIRED" in l), "")
    if not line:
        raise SystemExit("events/registry.md §8 has no strict-ordering line")
    if "Order-tolerant" not in line:
        raise SystemExit(
            "events/registry.md §8's ordering line no longer carries its 'Order-tolerant:' half; "
            "the strict half can no longer be delimited and would silently absorb the other one"
        )
    strict_half, _, tolerant_half = line.partition("Order-tolerant")
    families = tuple(dict.fromkeys(re.findall(r"\b(F\d+)\b", strict_half)))
    tolerant = tuple(dict.fromkeys(re.findall(r"\b(F\d+)\b", tolerant_half)))
    if not families:
        raise SystemExit("events/registry.md §8 declared no strict-order families")
    if not tolerant:
        raise SystemExit("events/registry.md §8 declared no order-tolerant families")
    overlap = sorted(set(families) & set(tolerant))
    if overlap:
        raise SystemExit(f"events/registry.md §8 lists {overlap} as BOTH strict and order-tolerant")
    return families


# ------------------------------------------------------------ family files: payloads and defaults

def parse_family_default_aggregate_type(path: Path) -> str | None:
    """`**Family defaults:** \\`aggregate_type=work_item\\`; …`

    F14's default is "the offending machine's" — prose, not a slug — so it yields None and the
    validator does not check an aggregate type the specification declined to fix.
    """
    for line in read(path).split("\n"):
        if "Family defaults:" not in line:
            continue
        m = re.search(r"aggregate_type\s*=\s*`?([a-z][a-z0-9_]*)`?", line)
        return m.group(1) if m else None
    return None


def parse_family_version(headers: list[str]) -> int:
    """The family table's `Event · v1 · producer` header carries the current version of its events.

    Per-FAMILY rather than per-EVENT because that is how the corpus states it today (registry §2
    field 3: "Current version `v1`"). The day one event ships v2, this header can no longer express
    it and this function must be revisited — which is stated here rather than discovered later.
    """
    m = re.search(r"\bv(\d+)\b", headers[0])
    return int(m.group(1)) if m else 1


def parse_payload(cell: str) -> tuple[list[dict], list[dict]]:
    """One `Payload` cell ⇒ (field specs, one-of groups).

    THE GRAMMAR, as the corpus actually writes it:

        —                            no payload beyond the envelope
        `name`                       required
        `name?`                      optional
        `name[]`                     required, list-valued
        `name[]?`                    optional, list-valued
        `name=VALUE`                 required, fixed to VALUE
        `name∈{a,b,c}`               required, constrained to an enum
        `a \\| b`                     a ONE-OF group — exactly one member
        …(R)  …(R, prose)  …(R ∈ {A,B})   an annotation on the term just declared

    ### A FIELD IS A BACKTICKED TOKEN AT TOP LEVEL — NEVER ONE INSIDE AN ANNOTATION. That rule is
    load-bearing: `missing`(R, e.g. `commodity`) declares ONE field, and `diff_fingerprint`(R, the
    `material_facts_fingerprint` of the diff) declares one field, not two. Reading annotations as
    declarations would invent required fields nobody specified and refuse every legitimate event.

    ### AN UNMARKED FIELD IS REQUIRED. `?` is the only optionality marker the corpus uses, and the
    fail-closed reading of an unmarked field is the one that cannot silently drop a fact.
    """
    text = strip_emphasis(cell)
    if not text or text in {"—", "-", "–"}:
        return [], []

    fields: list[dict] = []
    one_of: list[dict] = []

    for term in split_top_level(text):
        m = re.search(r"`([^`]+)`", term)
        if not m:
            continue                      # prose-only fragment, e.g. a trailing "(dual control)"
        declaration = m.group(1).strip()
        annotation = term[m.end():]

        # --- a ONE-OF group: `rule_id \| decision_ref`, `phase_seq \| linked_work_item_id`
        if r"\|" in declaration or "|" in declaration:
            members = [p.strip().strip("`?") for p in re.split(r"\\?\|", declaration) if p.strip()]
            members = [p for p in members if re.fullmatch(r"[a-z][a-z0-9_]*", p)]
            if len(members) >= 2:
                one_of.append({"members": tuple(members), "required": "?" not in declaration})
            continue

        optional = declaration.endswith("?")
        declaration = declaration.rstrip("?").strip()

        fixed: str | None = None
        enum: tuple[str, ...] | None = None

        if "∈" in declaration:
            name_part, _, enum_part = declaration.partition("∈")
            enum = tuple(v.strip() for v in enum_part.strip().strip("{}").split(",") if v.strip())
            declaration = name_part.strip()
        elif "=" in declaration:
            name_part, _, value_part = declaration.partition("=")
            fixed = value_part.strip()
            declaration = name_part.strip()

        listed = declaration.endswith("[]")
        name = declaration[:-2].strip() if listed else declaration
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            continue                      # not a field declaration (a cross-reference, a word)

        # The annotation may carry the enum or the fixed value instead of the declaration:
        #   `kind`(R ∈ {SYSTEM_VS_SYSTEM,…})      `gate_decision`(R, `= AUTONOMOUS_WITHIN_CAPS`)
        if enum is None:
            m_enum = re.search(r"∈\s*\{([^}]*)\}", annotation)
            if m_enum:
                enum = tuple(v.strip() for v in m_enum.group(1).split(",") if v.strip())
        if fixed is None:
            # ### ONLY THE BACKTICKED, ANCHORED FORM COUNTS: `gate_decision`(R, `= AUTONOMOUS_WITHIN_CAPS`).
            #
            # An earlier version read any `= word` out of the free prose, and that invented two
            # fixed values that made their contracts UNSATISFIABLE:
            #   IB-1  `provenance_class`(R = f(match_method))                 -> fixed 'f'
            #   OB-1  `natural_key`(R = tenant+source+external_id+…)          -> fixed 'tenant'
            # Both annotations are DERIVATION FORMULAS, not literals: IB-1's says the provenance
            # class is a function of the match method (SD-6), and OB-1's spells out §4's
            # source-natural identity. The runtime then refused every legitimate `ClaimProposed`
            # and every `ObservationReceived` in the corpus.
            #
            # The same rule the field-name extractor already obeys applies here: an annotation is
            # PROSE unless it is explicitly marked as a value. A guessed fixed value is exactly the
            # class of invention this file exists to prevent, so an unmarked `=` yields nothing.
            m_fixed = re.search(r"`\s*=\s*([A-Za-z][A-Za-z0-9_]*)\s*`", annotation)
            if m_fixed:
                fixed = m_fixed.group(1).strip()

        fields.append({
            "name": name,
            "required": not optional,
            "listed": listed,
            "enum": enum,
            "fixed": fixed,
        })

    # A name declared twice in one cell is a defective contract, not something to merge quietly.
    seen = [f["name"] for f in fields]
    duplicated = sorted({n for n in seen if seen.count(n) > 1})
    if duplicated:
        raise SystemExit(f"payload cell declares {duplicated} more than once: {cell!r}")
    return fields, one_of


# ### THE UNCONDITIONAL HUMAN-ONLY DECLARATION, as the family files write it.
#
# Twelve rows mention `actor_type=human`; only some mean it EXCLUSIVELY, and the distinction is
# load-bearing in both directions:
#
#   UNCONDITIONAL - "`actor_type=human` ONLY", "AUTHENTICATED HUMAN ONLY". These are the
#       authority-BROADENING acts plus the human consent that binds Material Facts:
#       ApprovalGranted(AP-2), PolicyApproved(PO-3), PolicyActivated(PO-4), RuleActivated(RU-5),
#       BrakeReleased(BR-4), BrakeNarrowed(BR-3).
#
#   CONDITIONAL - `ClaimConfirmed`(IB-2) says "### **`OWNER_ASSERTED` requires `actor_type=human`
#       (ER-10)**", and its Proves cell says a binding is canonical "via a **deterministic** method
#       OR an **authenticated human**". Reading that as human-only would refuse every legitimate
#       deterministic (LINKER_INFERRED / RECONCILED) confirmation in the corpus. ER-10's provenance
#       rule already covers the conditional half.
#
#   ADVISORY - rows naming `actor_type=human` without "ONLY" (HumanDecided, OwnershipTransferred,
#       ApprovalRevoked, ExceptionAcknowledged, PolicySubmitted, RuleConfirmed) state the expected
#       actor without declaring exclusivity. Treated as NOT enforced here, conservatively, and
#       recorded as debt rather than guessed at - refusing a legitimate event is as much a defect
#       as admitting an illegitimate one.
#
# `ONLY` must be whole-token and must follow the human declaration within the same clause, so a
# sentence merely containing the word cannot promote a row.
_HUMAN_ONLY = re.compile(
    r"(?:`actor_type\s*=\s*human`[^.;]{0,40}?\bONLY\b|AUTHENTICATED\s+HUMAN\s+ONLY)",
    re.IGNORECASE,
)


def parse_human_only(notes: str) -> bool:
    return bool(_HUMAN_ONLY.search(notes))


def parse_family_files() -> dict[str, dict]:
    """Every F1–F14 contract row, keyed by event name. The F15 lens is skipped (§9)."""
    contracts: dict[str, dict] = {}
    for path in sorted(EVENTS.glob("[0-9][0-9]-*.md")):
        family = re.match(r"^(\d+)-", path.name)
        if family and int(family.group(1)) == 15:
            continue
        aggregate_type = parse_family_default_aggregate_type(path)
        for headers, cells in markdown_rows(path):
            names = re.findall(r"`([A-Za-z][A-Za-z0-9]*)`", cells[0])
            if not names:
                continue
            name = names[0]
            if name in contracts:
                raise SystemExit(
                    f"{name} has a contract row in both {contracts[name]['source']} and "
                    f"{path.name}; a contract has exactly one owning family file"
                )
            fields, one_of = parse_payload(column(headers, cells, "payload"))
            # The constraint lives in the row's Notes/tests cell, which is the last column in
            # every family table; `column(..., "notes")` finds it by header name where the header
            # is written that way, and the whole row is the fallback so a renamed header cannot
            # silently drop every actor constraint at once.
            notes = column(headers, cells, "notes") or " | ".join(cells)
            contracts[name] = {
                "source": path.name,
                "aggregate_type": aggregate_type,
                "current_version": parse_family_version(headers),
                "fields": fields,
                "one_of": one_of,
                "human_only": parse_human_only(notes),
            }
    return contracts


# ------------------------------------------------------------------------------------ derivation

def derive() -> list[dict]:
    """The two sources, reconciled in BOTH directions, into one ordered contract list."""
    canonical = parse_canonical_list()
    family_rows = parse_family_files()
    consequential = set(parse_consequential())
    conditional = set(parse_conditionally_consequential())
    strict_families = set(parse_strict_order_families())

    declared_names = {e["name"] for e in canonical}
    missing = sorted(declared_names - set(family_rows))
    extra = sorted(set(family_rows) - declared_names)
    if missing:
        raise SystemExit(f"§3 names {missing} but no family file declares a contract for them")
    if extra:
        raise SystemExit(f"family files declare {extra}, which §3's canonical list does not name")

    unknown_consequential = sorted(consequential - declared_names)
    if unknown_consequential:
        raise SystemExit(f"§5 marks {unknown_consequential} consequential, but §3 does not name them")

    contracts: list[dict] = []
    for entry in sorted(canonical, key=lambda e: e["name"]):
        row = family_rows[entry["name"]]
        family_number = int(entry["family"][1:])
        contracts.append({
            "name": entry["name"],
            "family": entry["family"],
            "source": row["source"],
            "current_version": row["current_version"],
            "producers": entry["producers"],
            "coordination": entry["coordination"],
            "aggregate_type": row["aggregate_type"],
            # F1–F13 are the machine-emitted corpus the registry counts (105). F14 is the
            # audit/security surface: real contracts, but not emitted by a producer transition.
            "emitted_corpus": family_number <= 13,
            "consequential": entry["name"] in consequential,
            "consequential_conditional": entry["name"] in conditional,
            "strict_order": entry["family"] in strict_families,
            "human_only": row["human_only"],
            "fields": row["fields"],
            "one_of": row["one_of"],
        })
    return contracts


# -------------------------------------------------------------------------------------- emission

def render(contracts: list[dict]) -> str:
    """The committed artifact: JSON, not Python.

    ### WHY JSON, AND WHY THAT DECISION MATTERS MORE THAN IT LOOKS. An earlier version emitted a
    `.py` module holding one tuple literal. It was inert in practice, but "inert" was then a claim
    about its CONTENTS rather than a property of its FORM: a `.py` file can always grow code, and
    proving it had not required an AST guard - which an independent review promptly defeated with a
    module-level `if` that assembles a policy decision at import time with no function, class or
    call anywhere in it.

    JSON cannot execute. Nothing needs to prove that it does not.

    It also removes the reason the Phase-0 gate-confinement guard had to change at all: that guard
    scans `src.rglob("*.py")`, so `AUTONOMOUS_WITHIN_CAPS` living in a `.json` file is not a Python
    module carrying a gate token, and the guard's original kernel-only confinement stands
    unmodified. The safest change to a safety guard is the one you do not have to make.

    Packaging is unaffected: hatchling ships everything under `src/freight_recon`, so the data file
    installs beside the modules exactly as the `.py` would have.
    """
    return json.dumps(
        {
            "_generated_by": "scripts/generate_event_contracts.py",
            "_derived_from": [
                "docs/specifications/events/registry.md (§3 names, §5 consequential, §8 ordering)",
                "docs/specifications/events/NN-*.md (F1-F14 family files: payloads, defaults, "
                "actor constraints)",
            ],
            "_authority": (
                "events/registry.md §6 is the sole canonical list of event names and versions. "
                "This file is its mechanical projection; a guard re-derives it on every suite run. "
                "The `gate_decision` fixed value AUTONOMOUS_WITHIN_CAPS on "
                "AutonomousAdmissionRecorded (PL-7a) is ADR-010's typed gate ladder, named here "
                "because that event RECORDS which decision admitted autonomous work. This file "
                "declares; it evaluates nothing, and being JSON it cannot."
            ),
            "_counts": {
                "total": len(contracts),
                "emitted_corpus_f1_f13": sum(1 for c in contracts if c["emitted_corpus"]),
                "audit_security_f14": sum(1 for c in contracts if not c["emitted_corpus"]),
            },
            "contracts": contracts,
        },
        indent=2,
        ensure_ascii=False,
        sort_keys=False,
    ) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="exit 1 if the committed data module is stale; write nothing")
    args = parser.parse_args()

    rendered = render(derive())
    if args.check:
        current = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
        if current != rendered:
            print(f"STALE: {TARGET.relative_to(ROOT)} does not match the specification derivation")
            return 1
        print(f"current: {TARGET.relative_to(ROOT)} matches the specification")
        return 0

    TARGET.write_text(rendered, encoding="utf-8")
    contracts = derive()
    emitted = sum(1 for c in contracts if c["emitted_corpus"])
    print(f"wrote {TARGET.relative_to(ROOT)}: {len(contracts)} contracts "
          f"({emitted} emitted F1-F13, {len(contracts) - emitted} audit/security F14)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
