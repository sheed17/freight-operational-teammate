"""Bootstrap, hermeticity and U-HANDOFF-1B correction guards.

The independent clean-clone rehearsal proved the repository was reproducible only on the machine
that authored it: an unenforced Python floor, an undeclared dependency, 46 tests reading a
gitignored workspace database, and a status guard that verified test COUNTS rather than test
RESULTS. Every guard here holds one of those corrections in place, and the M-4 guards hold the
re-grounded figures (transition/event audit, effect-path inventory, table partition, graph
consistency, banners, frontmatter) against drift.

Discipline as everywhere in this suite: discover, never enumerate; exact sets, not counts;
negative assertions over proven populations; whole-token matching.
"""

from __future__ import annotations

import ast
import inspect
import itertools
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from check_env import check as env_check, required_floor  # noqa: E402

IMPL = ROOT / "docs" / "implementation"


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8")


def require_population(items, what: str):
    assert items, f"no {what} to assert over - this test would pass vacuously"
    return items


# ============================================================ H-1: bootstrap

def test_python_below_the_floor_fails_immediately_and_compliant_proceeds():
    """Acceptance 1+2: the check refuses 3.10 with the exact versions, accepts the floor."""
    floor = required_floor((ROOT / "pyproject.toml").read_text())
    assert floor >= (3, 11), f"the declared floor {floor} regressed below 3.11"
    assert env_check((3, 10)) == 1, "Python 3.10 was allowed to proceed to dependency resolution"
    assert env_check((floor[0], floor[1])) == 0, "the exact floor version was refused"
    assert env_check(None) == 0, "the ACTIVE interpreter fails its own floor - the venv is wrong"


def test_the_bootstrap_docs_run_the_env_check_before_installing():
    for f in (ROOT / "README.md", ROOT / "CLAUDE.md"):
        text = read(f)
        assert "check_env.py" in text, f"{f.name} no longer runs the fail-fast env check"
    readme = read(ROOT / "README.md")
    check_pos = readme.find("check_env.py")
    install_pos = readme.find("pip install -e")
    assert 0 < check_pos < install_pos, "README runs pip install before the env check"


STDLIB_OK = {
    "annotations",  # __future__
}
# import name -> distribution that declares it
IMPORT_TO_DIST = {
    "pydantic": "pydantic", "instructor": "instructor", "anthropic": "anthropic",
    "openai": "openai", "fitz": "pymupdf", "pymupdf": "pymupdf", "yaml": "pyyaml",
    "dotenv": "python-dotenv", "reportlab": "reportlab", "PIL": "pillow",
    "websocket": "websocket-client",
    "browser_use": "browser-use",  # optional extra [browser-agent]
    "pytest": "pytest",            # dev extra
}


def _declared_distributions() -> set[str]:
    text = (ROOT / "pyproject.toml").read_text()
    return {m.group(1).lower() for m in re.finditer(r'"([A-Za-z0-9_.\[\]-]+?)[><=~!]', text)}


def test_every_third_party_import_in_src_is_declared():
    """Acceptance 3: the websocket lesson, generalised. A clean install must satisfy every
    import; a dependency present only in the developer's environment is a clean-clone failure
    waiting to be discovered by whoever clones next."""
    import sys as _sys
    stdlib = set(_sys.stdlib_module_names)
    declared = _declared_distributions()
    declared_bases = {re.sub(r"\[.*\]", "", d) for d in declared}
    offenders, seen = [], set()
    for f in (ROOT / "src").rglob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            mods = []
            if isinstance(node, ast.Import):
                mods = [a.name.split(".")[0] for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                mods = [node.module.split(".")[0]]
            for m in mods:
                if m in stdlib or m in STDLIB_OK or m == "freight_recon" or m in seen:
                    continue
                seen.add(m)
                dist = IMPORT_TO_DIST.get(m)
                if dist is None:
                    offenders.append(f"{f.relative_to(ROOT)}: import {m} has no known distribution mapping")
                elif dist.lower() not in declared_bases:
                    offenders.append(f"{f.relative_to(ROOT)}: import {m} -> {dist} is NOT declared in pyproject.toml")
    require_population(seen, "third-party imports")
    assert not offenders, "undeclared third-party imports (the websocket defect, recurring):\n  " + "\n  ".join(offenders)
    assert "websocket-client" in declared_bases, "websocket-client left the declared dependencies"


def test_collection_succeeds_with_zero_errors():
    """Acceptance 5 (in-checkout form; the clean-clone gate proves the fresh-venv form)."""
    r = subprocess.run(
        [sys.executable, "-m", "pytest", "eval/", "--collect-only", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert "error" not in r.stdout.lower().split("=")[-1], f"collection errors:\n{r.stdout[-800:]}"
    m = re.search(r"(\d+) tests? collected", r.stdout)
    assert m and int(m.group(1)) > 1000


# ============================================================ H-2: hermeticity

def test_no_test_reads_the_workspace_database_or_home_directory():
    """Acceptance 7-9: static proof over every test file. The fixture builder's docstring may
    NAME the old path (it documents the correction); no test may USE it."""
    offenders = []
    files = sorted((ROOT / "eval").rglob("test_*.py")) + [ROOT / "eval" / "conftest.py"]
    # This guard file itself is excluded: its detection patterns ARE the forbidden strings, and a
    # guard that flags its own hunting expressions is the substring-self-match defect again.
    files = [f for f in files if f.exists() and f.name != "test_bootstrap_hermeticity.py"]
    require_population(files, "test files")
    for f in files:
        text = f.read_text(encoding="utf-8")
        for pat, label in [
            (r"active_workspace", "the developer-local workspace"),
            (r"/Users/[a-z]", "an absolute home path"),
            (r"Path\.home\(\)|expanduser\(", "the home directory"),
        ]:
            for m in re.finditer(pat, text):
                line = text[: m.start()].count("\n") + 1
                offenders.append(f"{f.relative_to(ROOT)}:{line}: {label}")
    assert not offenders, (
        "tests depending on developer-local state (the 46-failure clean-clone defect):\n  "
        + "\n  ".join(offenders)
    )


def test_no_test_skips_itself_when_a_database_is_absent():
    """Silently skipping on missing state would hide the hermeticity failure instead of fixing
    it - the prompt names this forbidden dodge explicitly."""
    offenders = []
    for f in sorted((ROOT / "eval" / "tests").glob("test_*.py")):
        if f.name == "test_bootstrap_hermeticity.py":
            continue  # this file quotes the forbidden pattern in order to hunt it
        text = f.read_text(encoding="utf-8")
        if re.search(r"skipif.{0,120}(exists|sqlite|workspace|database)", text, re.S | re.I):
            offenders.append(f.name)
    assert not offenders, f"tests that skip when a database is absent: {offenders}"


def test_the_legacy_fixture_is_deterministic_and_self_consistent(tmp_path):
    """Acceptance 6: two builds are byte-identical; the population equals the exported constants."""
    import hashlib
    from fixtures.legacy_workspace import (
        LEGACY_AUDIT_EVENTS, LEGACY_RUNS, build_legacy_workspace,
    )
    a = build_legacy_workspace(tmp_path / "a.db")
    b = build_legacy_workspace(tmp_path / "b.db")
    ha, hb = (hashlib.sha256(p.read_bytes()).hexdigest() for p in (a, b))
    assert ha == hb, "the legacy fixture is not byte-deterministic across builds"
    import sqlite3
    conn = sqlite3.connect(a)
    runs = conn.execute("SELECT COUNT(*) FROM workflow_runs").fetchone()[0]
    events = conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0]
    sec = conn.execute("SELECT COUNT(*) FROM security_events").fetchone()[0]
    conn.close()
    assert (runs, events, sec) == (LEGACY_RUNS, LEGACY_AUDIT_EVENTS, 0)


def test_a_clean_clone_has_no_workspace_database():
    """Acceptance 1 (fixture proof): the path is ignored AND untracked, so a clone cannot have it."""
    tracked = subprocess.run(["git", "ls-files", "data/active_workspace"], cwd=ROOT,
                             capture_output=True, text=True, check=True).stdout.strip()
    assert not tracked, f"workspace files are TRACKED and would ship in a clone: {tracked}"
    ignored = subprocess.run(["git", "check-ignore", "data/active_workspace/x"], cwd=ROOT,
                             capture_output=True, text=True).returncode == 0
    assert ignored, "data/active_workspace is no longer gitignored"


# ============================================================ G2: the transition/event contract
#
# The G2 targeted architecture adjudication over certified predecessor 6e8127d ruled
# INTERPRETATION C - HYBRID: the PRODUCER predicate is membership in events/registry.md sec 3, and
# the COMPLETENESS predicate is the presence of a durable write (GR-2). NEITHER READS PROSE.
#
# Interpretation B ("explicitly documented non-producing") was refused because its predicate is
# PROSE-DEPENDENT AND SELF-CERTIFYING: a row exempts itself by writing the right words in the Event
# column. That failure is not hypothetical - 07-conflict:CF-7 and 09-exception:EC-7 both carried
# "(no state change)", the old parser honoured it as a non-production declaration, and BOTH ROWS IN
# FACT PERFORM DURABLE WRITES. Two real defects were being laundered into legal exemptions.
#
# The adjudicated defects these guards hold closed:
#   G2-D1  the old classifier's `else` branch was a FALSE GREEN - it never checked that the cell
#          named a canonical event, so 12-rule:RU-8 (Event cell "(Exception raised)") passed as
#          evented while naming nothing at all. UNKNOWN CLASSIFICATION IS NOW A FAILURE.
#   G2-D3  01-work-item:WI-14 said "same guards as WI-5/6/7/3/12 respectively" over FOUR target
#          states and FIVE references. Ownership is resolved by TARGET STATE, never positionally.
#   G2-D5  no column-count guard existed. 03-external-effect-grant:EF-5x carried 7 cells against 8
#          headers; a cell missing BEFORE the Event column would have shifted classification
#          silently. The row is repaired and the guard is here.
#   G2-D7  the anti-"24" guard collided with the truth - the computed count of NON-PRODUCER
#          transitions is ALSO 24, a different quantity that happens to share a value.
#   G2-D11 nothing asserted the sec-3 producer map and the 134-row corpus were bijective in BOTH
#          directions.
#   G2-D12 the audit recorded 121/13; the corrected as-found split was 120/14.
#   G2-D14 the audit classified EF-3 as DOCUMENTED_NON_PRODUCING; it is the declared sec-3 producer
#          of the EXISTING canonical event EffectExecuted.
#
# Discipline as everywhere here: exact sets, never counts; positive anchors before every negative
# assertion; whole-token matching; and no guard may pass by measuring nothing.

SPECS = ROOT / "docs" / "specifications"
MACHINES = SPECS / "state-machines"

CLASS_TOKENS = ("NON_PRODUCING", "DELEGATES_TO", "CONSUMES", "EVENT_REQUIRED")
CLASS_TOKEN_RE = re.compile(r"\b(" + "|".join(CLASS_TOKENS) + r"):([A-Za-z0-9_,;=-]+)")
NON_PRODUCING_REASONS = {"ENUMERATED_NO_OP", "GR1_ILLEGAL_REFUSAL"}
# The only declared deviation from "exactly one producer transition" (events/registry.md sec 9).
COORDINATION_EVENTS = {"RealityEstablished", "ConflictRaised", "PolicyVersionChanged",
                       "IllegalTransitionAttempted"}


def _audit() -> dict:
    return yaml.safe_load(read(IMPL / "TRANSITION-EVENT-AUDIT.yaml"))


def _bare(cell: str) -> bool:
    return re.sub(r"[*`\s]", "", cell) in ("", "—", "-", "–")


def _expand_producers(field: str | None) -> list[str]:
    """The registry's own shorthand: `PL-7v/9v` -> [PL-7v, PL-9v]; `IB-2/2r/2h` -> three ids. A
    bare suffix inherits the preceding machine prefix."""
    out: list[str] = []
    prefix = None
    for tok in (field or "").split("/"):
        tok = tok.strip()
        m = re.match(r"^([A-Z]{2})-(\d+[a-z]*)", tok)
        if m:
            prefix = m.group(1)
            out.append(f"{prefix}-{m.group(2)}")
            continue
        m = re.match(r"^(\d+[a-z]*)", tok)
        if m and prefix:
            out.append(f"{prefix}-{m.group(1)}")
    return out


def _event_registry() -> dict:
    """events/registry.md sec 3. F15 is a LENS over cross-machine consumption and declares no
    contract (sec 9); counting it would double-count every event it names."""
    section = read(SPECS / "events" / "registry.md")
    section = section.split("## 3. CANONICAL EVENT LIST")[1].split("## 4.")[0]
    declared = []
    for line in section.split("\n"):
        fam = re.match(r"^\*\*(F\d+)\s", line)
        if not fam:
            continue
        for m in re.finditer(r"`([A-Za-z][A-Za-z0-9]*)`(‡?)(?:\(([^)]*)\))?", line):
            declared.append({"family": fam.group(1), "name": m.group(1),
                             "coordination": m.group(2) == "‡",
                             "producers": _expand_producers(m.group(3))})
    contracts = [e for e in declared if e["family"] != "F15"]
    owned = [e for e in contracts if int(e["family"][1:]) <= 13]
    producers_of: dict[str, set[str]] = {}
    for e in owned:
        for tid in e["producers"]:
            producers_of.setdefault(tid, set()).add(e["name"])
    return {"declared": declared, "contracts": contracts, "owned": owned,
            "corpus": [e["name"] for e in contracts], "producers_of": producers_of}


def _consequential_events() -> list[str]:
    """events/registry.md sec 5's CONSEQUENTIAL list, in declaration order.

    ### THIS SURFACE WAS ENTIRELY UNGUARDED (F-05). No node under eval/ read it, so striking
    `PolicyApproved` - which candidate f01d942's own commit message called "the 'no admin path'
    evidence" - left the whole canonical suite green, while that commit simultaneously claimed
    twenty mutations "each neutering a RULE, or a fact in the specification the guard reads". A
    CONSEQUENTIAL event is the one that must pin the SD-3 `entity_versions` set, the material-facts
    fingerprint, `policy_version` and `brake_version` - exactly what makes a decision reproducible
    from the log. Membership is read from the LIST LINE ONLY: the amendment note beneath it also
    names `PolicyApproved`, and reading the prose as the list would let the list itself be emptied
    while the note kept the guard green.
    """
    section = read(SPECS / "events" / "registry.md")
    section = section.split("## 5. WHICH EVENTS ARE CONSEQUENTIAL")[1].split("\n## ")[0]
    listing = [l for l in section.split("\n") if l.strip().startswith("`")]
    if len(listing) != 1:
        return []                     # UNDECIDABLE - the node below fails closed on an empty result
    return re.findall(r"`([A-Za-z][A-Za-z0-9]*)`", listing[0])


def _canonical_states() -> set[str]:
    text = read(MACHINES / "registry.md")
    text = text.split("## 4. CANONICAL STATE REGISTRY")[1].split("## 5.")[0]
    return set(re.findall(r"`([A-Z][A-Z_]*)`", text))


def _states_in(fragment: str, states: set[str]) -> set[str]:
    return {t for t in re.findall(r"[A-Z][A-Z_]{2,}", fragment) if t in states}


def _transition_rows() -> list[dict]:
    r"""Every transition row across the 13 machine files, with its From-To / Writes / Event cells
    resolved BY HEADER NAME (the columns are not in the same order in every machine) and its cell
    count recorded against its header count (G2-D5). Escape-aware split on `(?<!\\)\|` - the
    U-HANDOFF-1B correction, without which `H\\|S` in the Trig column shifts every later cell."""
    rows = []
    for f in sorted(MACHINES.glob("*.machine.md")):
        short = f.name.replace(".machine.md", "")
        headers = None
        for lineno, line in enumerate(f.read_text(encoding="utf-8").split("\n"), 1):
            if not line.strip().startswith("|"):
                headers = None
                continue
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line)[1:-1]]
            if not cells:
                continue
            if re.sub(r"[*\s]", "", cells[0]) == "ID":
                headers = [re.sub(r"[*`\s]", "", h).lower() for h in cells]
                continue
            if headers is None or re.match(r"^[-: ]+$", cells[0]):
                continue
            tid = re.sub(r"[*`\s]", "", cells[0])
            if not re.fullmatch(r"[A-Z]{2}-\d+[a-z]?", tid):
                continue

            def col(pred, _cells=cells, _headers=headers):
                i = next((i for i, h in enumerate(_headers) if pred(h)), None)
                return _cells[i] if i is not None and i < len(_cells) else ""

            rows.append({
                "key": f"{short}:{tid}", "id": tid, "machine": short, "line": lineno,
                "n_cells": len(cells), "n_headers": len(headers),
                "from_to": col(lambda h: h.startswith("from")),
                "trig": col(lambda h: h.startswith("trig")),
                "writes": col(lambda h: h.startswith("writes") or h == "prov"),
                "event": col(lambda h: h.startswith("event")),
            })
    return rows


# ------------------------------------------------- the trigger-type set: a CLOSED, structured column
#
# ### R3-A. `_resolve_delegation` proved only (target exists · is a sec-3 producer · shares the target
# state). That triple is satisfied by `PL-7a -> DELEGATES_TO:CHECKPOINT=PL-7b`, which is semantically
# FALSE: PL-7b's event asserts a BOUND HUMAN APPROVAL, while PL-7a is the autonomous-within-caps path
# where no human acted. A row could therefore have discharged its GR-2 obligation by delegating to a
# sibling that reaches the same state for an INCOMPATIBLE REASON.
#
# ### THE INVARIANT IS STRUCTURAL AND GENERAL - NO PL-7a SPECIAL CASE, NO PROSE EXCEPTION.
# `Trig` is a CLOSED code set declared in state-machines/registry.md sec 1: H human · S deterministic
# system · X observed external · T timer · P policy change · B brake change · R recovery. A row
# carries one code or a union (`S\|H`). A delegating row hands its OWN trigger to a target: if the two
# trigger-type sets are DISJOINT, the target's transition cannot be the one this row's trigger causes,
# so the target's event cannot record what this row did.
#
#   WI-14  `S|H` -> WI-5 `S`, WI-6 `S|X`, WI-7 `S`, WI-3 `S`, WI-12 `H`     all intersect  ACCEPT
#   CF-6   `S|H` -> CF-3 `S`, CF-4 `H`                                      all intersect  ACCEPT
#   PL-7a  `S`   -> PL-7b `H`                                          {S} n {H} = empty   REJECT
#
# ### AND IT IS NOT SUFFICIENT ON ITS OWN (P5 U5.2 replacement, re-adjudication F-01). The first
# candidate f01d942 shipped the trigger conjunct ALONE and asserted in its subject line that it had
# "close[d] the false-delegation route". Driven over the complete structurally-expressible population
# the real predicate then admitted 157 of 250 triples, 106 of them CROSS-MACHINE, and NINE of them
# sourced at one of the seven founder-gated rows - among them `AP-9 -> GRANTED=EF-2f`, in which M3's
# idempotent claim REFUSAL would stand as the record of an M4 approval freeze, and
# `RU-8 -> EXPIRED=PO-7`, whose own committed prose already says the other aggregate's fact "does not
# record that THIS rule expired". The trigger conjunct closes 4 of 13 adj7-sourced routes, not "the
# route". It is KEPT - it is the only conjunct that refuses `PL-7a -> PL-7b` - and a second is ADDED.
#
# ### THE SECOND CONJUNCT: SAME MACHINE. state-machines/registry.md sec 1 declares the UNIVERSAL
# ORDERING KEY `(tenant_id, aggregate_id, aggregate_version)`. A target on a DIFFERENT machine is a
# DIFFERENT AGGREGATE, so its event carries a different `aggregate_id` and cannot, under this
# repository's own envelope, be the record of THIS aggregate's state change. This is the exact
# structural DUAL of the already-adjudicated CONSUMES rule 5c, which requires CROSS-machine on the
# authority of state-machines/registry.md:182: a co-transition mirror necessarily spans two
# aggregates, and a delegation of one aggregate's own record necessarily does not. Both conjuncts
# derive from one line of specification; neither is fitted to an exploit list.
#
# ### THESE FOUR FIGURES ARE MEASUREMENTS OF THIS FUNCTION, RE-DERIVED (R-03). The rejected
# candidate a6005a8 printed `250 / 167 / 102 / 53` here: the PRIOR ADJUDICATION'S FIGURES, taken from
# an independent five-conjunct RE-IMPLEMENTATION and presented, unattributed, as measurements of the
# predicate below - which they never were, because the real function's other conjuncts (notably
# ambiguous ownership) stay live where a re-implementation's do not. A guard that states something
# other than what it does is the F-04 failure mode, and it was found in the guard that holds the
# residual. The figures below are re-derived by DELETING EACH CONJUNCT FROM THE REAL FUNCTION and
# sweeping all 250 structurally-expressible triples, which is also exactly what the corpus-sweep node
# does on every run.
#
#   base predicate (target exists · sec-3 producer · shares target state)   235 admits · 13 adj7
#   + trigger only                                                          157 admits ·  9 adj7
#   + same-machine only                                                      96 admits ·  2 adj7
#   + BOTH                                                                   51 admits ·  0 adj7
#
# (250 is the size of the EXPRESSIBLE POPULATION, not of any admitted set; the base predicate refuses
# 15 of the 250 on ambiguous or zero ownership.)
#
# Same-machine ALONE is insufficient: it still admits `PL-7a -> PL-7b` and `AP-9 -> AP-2`. Trigger
# ALONE is insufficient: it admits the nine above. Zero declared branches are false-rejected by
# either, measured over WI-14's five and CF-6's two.
#
# ### THE 51 SURVIVORS ARE NECESSARY CONDITIONS, NOT A SEMANTIC PROOF. They are asserted EXACTLY, as
# a named residual, by ADJUDICATED_DELEGATION_ADMITS below. See that record for what remains open.
#
# The whole corpus is swept by
# test_the_delegation_predicate_is_swept_over_the_whole_corpus_and_its_admitted_set_is_exact, which
# CALLS `_resolve_delegation` itself over every (row, target state, same-state producer) triple
# rather than re-implementing a clause inline - the defect (F-03) that let the above ship. It asserts
# the admitted set EXACTLY in both directions, so deleting EITHER conjunct from the predicate turns
# it RED.
#
# UNDECIDABLE IS A FAILURE. A row whose Trig cell yields no canonical code, or whose machine file
# yields no machine number, cannot be judged, so it fails closed rather than being waved through as
# "no constraint".

# FIXED-SPECIFICATION: the seven codes of state-machines/registry.md sec 1, a closed set declared by
# the specification itself - not a discovered population.
TRIGGER_CODES = frozenset("HSXTPBR")
_TRIGGER_TOKEN = re.compile(r"(?<![A-Za-z])([A-Z])(?![A-Za-z])")


def _trigger_types(row: dict) -> set[str]:
    """The row's declared trigger-type set, read from the structured `Trig` column and nothing else.

    `S\\|H` -> {S, H}; `T\\|B\\|P` -> {T, B, P}; `S` -> {S}. Only codes in the closed set count, so a
    stray capital in a cell contributes nothing and an empty result means UNDECIDABLE.
    """
    return {t for t in _TRIGGER_TOKEN.findall(row.get("trig", "") or "") if t in TRIGGER_CODES}


def _durable_write(row: dict, states: set[str]) -> bool:
    """GR-2's subject. A row writes durably iff its To side names a canonical state its From side
    does not, OR its Writes / Prov column is non-empty. Both read STRUCTURED columns."""
    if not _bare(row["writes"]):
        return True
    if "→" not in row["from_to"]:
        return False
    left, right = row["from_to"].split("→", 1)
    return bool(_states_in(right, states) - _states_in(left, states))


def _classify(rows: list[dict], producers_of: dict[str, set[str]]) -> dict:
    """The G2 classifier. sec-3 membership decides PRODUCER. Every other row MUST carry exactly one
    structured token. A row the classifier cannot decide is an ERROR - never a pass, never a skip."""
    classified, errors = {}, []
    for row in rows:
        tokens = CLASS_TOKEN_RE.findall(row["event"])
        if row["id"] in producers_of:
            if tokens:
                errors.append(
                    f"{row['key']}: a declared sec-3 producer carries a {tokens[0][0]} token - "
                    "producer identity is decided by the registry, never by the row"
                )
            classified[row["key"]] = {"class": "PRODUCER", "arg": None, "row": row}
            continue
        if len(tokens) != 1:
            errors.append(
                f"{row['key']} (line {row['line']}): {len(tokens)} classification tokens in Event "
                f"cell {row['event'][:70]!r}. A non-producer row must carry exactly one of "
                f"{list(CLASS_TOKENS)}. UNKNOWN CLASSIFICATION IS A BUILD FAILURE - it may never "
                "silently PASS or SKIP."
            )
            continue
        classified[row["key"]] = {"class": tokens[0][0], "arg": tokens[0][1], "row": row}
    return {"classified": classified, "errors": errors}


def _resolve_delegation(source: dict, spec: str, rows_by_id: dict, producers_of: dict,
                        states: set[str]) -> dict:
    """`BLOCKED=WI-5,WI-6;AWAITING_HUMAN=WI-7` -> {state: owner_event}. Ownership is resolved by
    TARGET STATE and never positionally (G2-D3): WI-5 and WI-6 BOTH target BLOCKED, so the word
    "respectively" over four states and five references could not decide it.

    ### `source` IS REQUIRED, NOT OPTIONAL (R3-A). Target-state agreement alone is a FALSE predicate:
    it accepts `PL-7a -> CHECKPOINT=PL-7b`, where the target's event asserts a bound human approval
    the delegating row never obtained. The delegating row's own `Trig` set must INTERSECT each
    target's, AND the target must live on the SAME MACHINE - a different machine is a different
    aggregate under sec 1's `(tenant_id, aggregate_id, aggregate_version)` ordering key, so its event
    cannot be the record of THIS aggregate's state change. Both conjuncts need the source row, which
    is why it is positional and first. Making it defaultable would restore the fail-open this closes.

    ### BOTH CONJUNCTS ARE REQUIRED AND NEITHER SUFFICES (re-adjudication F-01, ruling on the
    remediation scope). Trigger alone admits nine routes sourced at the seven founder-gated rows;
    same-machine alone still admits `PL-7a -> PL-7b` and `AP-9 -> AP-2`. Together they admit 51 of
    250 expressible triples, none sourced at the seven, and false-reject none of the seven declared
    branches. Each fails CLOSED when its datum is undecidable.
    """
    resolution, errors = {}, []
    source_trig = _trigger_types(source)
    source_machine = _machine_number(source.get("machine", ""))
    if not source_trig:
        errors.append(
            f"{source.get('key', '<row>')}: its own Trig cell {source.get('trig', '')!r} yields no "
            f"canonical trigger code from {sorted(TRIGGER_CODES)} - a delegation whose trigger type "
            "is UNDECIDABLE fails closed; it is never treated as unconstrained"
        )
    if source_machine is None:
        errors.append(
            f"{source.get('key', '<row>')}: its machine {source.get('machine', '')!r} yields no "
            "machine number, so the same-aggregate relationship cannot be DECIDED - a delegation "
            "whose aggregate identity is UNDECIDABLE fails closed"
        )
    for branch in [b for b in spec.split(";") if b]:
        if "=" not in branch:
            errors.append(f"malformed delegation branch {branch!r} - expected <TO_STATE>=<ids>")
            continue
        state, ids = branch.split("=", 1)
        targets = [t for t in ids.split(",") if t]
        if state not in states:
            errors.append(f"{state!r} is not a canonical state (state-machines/registry.md sec 4)")
        if not targets:
            errors.append(f"{state}: ZERO delegation targets - delegation may never resolve to "
                          "zero owners")
            continue
        owners: set[str] = set()
        for tid in targets:
            if tid not in rows_by_id:
                errors.append(f"{state}: delegation target {tid} does not exist in the corpus")
                continue
            if tid not in producers_of:
                errors.append(f"{state}: delegation target {tid} is not a sec-3 producer of any "
                              "event, so it owns nothing to delegate")
                continue
            target_to = _states_in(rows_by_id[tid]["from_to"].split("→", 1)[-1], states)
            if state not in target_to:
                errors.append(f"{state}: delegation target {tid} does not itself transition to "
                              f"{state} (its To set is {sorted(target_to)}) - positional matching "
                              "is forbidden; targets are matched by target state")
            # ---- R3-A: the delegating row's trigger type must INTERSECT the target's. Reaching the
            # same state is not enough - the target must be reachable by the trigger THIS row carries,
            # or its event records a different fact about a different cause.
            target_trig = _trigger_types(rows_by_id[tid])
            if not target_trig:
                errors.append(                                          # UNDECIDABLE fails closed
                    f"{state}: delegation target {tid}'s Trig cell "
                    f"{rows_by_id[tid].get('trig', '')!r} yields no canonical trigger code, so the "
                    "trigger relationship cannot be DECIDED - never a pass, never a skip"
                )
            elif source_trig and not (source_trig & target_trig):
                errors.append(
                    f"{state}: delegation target {tid} has DISJOINT TRIGGER TYPES from the "
                    f"delegating row - the row is triggered by {sorted(source_trig)}, {tid} by "
                    f"{sorted(target_trig)} (state-machines/registry.md sec 1). A target the "
                    "delegating row's own trigger can never fire does not perform this row's "
                    "transition, so its event records a DIFFERENT fact with a DIFFERENT cause and "
                    "cannot be delegated to"
                )
            # ---- SAME MACHINE = SAME AGGREGATE. state-machines/registry.md sec 1's universal
            # ordering key is (tenant_id, aggregate_id, aggregate_version). A target on another
            # machine is another AGGREGATE, so its event carries a different aggregate_id and is the
            # record of a DIFFERENT object's history - never of this row's write. The structural dual
            # of consumes_valid 5c, which requires CROSS-machine for a co-transition mirror.
            target_machine = _machine_number(rows_by_id[tid]["machine"])
            if target_machine is None:
                errors.append(                                          # UNDECIDABLE fails closed
                    f"{state}: delegation target {tid}'s machine "
                    f"{rows_by_id[tid]['machine']!r} yields no machine number, so the "
                    "same-aggregate relationship cannot be DECIDED - never a pass, never a skip"
                )
            elif source_machine is not None and target_machine != source_machine:
                errors.append(
                    f"{state}: delegation target {tid} is CROSS-MACHINE - the delegating row is on "
                    f"M{source_machine}, {tid} on M{target_machine} (state-machines/registry.md "
                    "sec 1: the universal ordering key is (tenant_id, aggregate_id, "
                    "aggregate_version)). A different machine is a DIFFERENT AGGREGATE, so the "
                    "target's event carries a different aggregate_id and records a different "
                    "object's history; it can never be the record of THIS aggregate's write"
                )
            owners |= producers_of[tid]
        if len(owners) == 0:
            errors.append(f"{state}: delegation resolves to ZERO event owners")
        elif len(owners) > 1:
            errors.append(f"{state}: delegation resolves to {sorted(owners)} - DUPLICATE/AMBIGUOUS "
                          "ownership. Exactly one valid delegation owner is required.")
        else:
            resolution[state] = next(iter(owners))
    return {"resolution": resolution, "errors": errors}


# ------------------------------------ THE DELEGATION RESIDUAL: what the predicate still lets through
#
# ### THESE ARE NECESSARY CONDITIONS, NOT A SEMANTIC PROOF - AND THIS RECORD IS THE ADMISSION.
# `_resolve_delegation` proves five structural facts: the target exists, it is a sec-3 producer, it
# transitions to the delegated state, its trigger types intersect the delegating row's, and it lives
# on the same machine (= the same aggregate). Every one is NECESSARY for a delegation to be
# truthful. Together they are NOT SUFFICIENT: nothing here reads what the target's event MEANS.
#
# This is the same standard the repository already accepted for CONSUMES-VALID, whose four conjuncts
# are likewise necessary conditions carrying the recorded ADJUDICATED_UNDECLARED_ACCEPTS residual
# above. What the re-adjudication of f01d942 refused was not the imprecision - it was announcing the
# imprecision as CLOSURE. So the surviving population is asserted EXACTLY, in both directions, and
# the two members that are visibly semantically wrong are NAMED:
#
#   EF-1 -> GRANTED=EF-2f    EF-2f owns `ClaimRefused` - an IDEMPOTENT REFUSAL of a second claim on
#                            an already-claimed grant. It is on M3, it reaches `GRANTED`, and its
#                            trigger intersects EF-1's, so all five conjuncts hold. It is not the
#                            record of EF-1's grant. NOT DECLARED by the corpus and NOT CLOSED here:
#                            refusing it needs a reading of what the event ASSERTS, which no
#                            structured column carries.
#   IB-1 -> PROPOSED=IB-3    same shape on M6.
#
# The remaining 49 are same-machine sibling pairs that reach a shared state (the WI, BR, EX, EC, OB
# and PL clusters). None is DECLARED by the corpus - the corpus declares seven branches, all of them
# in this set - and none is sourced at a member of ADJUDICATED_EVENT_REQUIRED, which is the property
# the founder-gate depends on and which the node below asserts separately.
#
# ### THIS SET IS A MEASUREMENT, NOT A TARGET. It is what
# test_the_delegation_predicate_is_swept_over_the_whole_corpus_and_its_admitted_set_is_exact
# recomputes by CALLING `_resolve_delegation` over all 250 structurally-expressible triples. Deleting
# EITHER conjunct from the predicate makes the set grow and turns that node RED:
#
#   both conjuncts                 51 admitted · 0 sourced at the adjudicated seven · 0 false rejects
#   trigger conjunct deleted       96 admitted · 2 sourced at the adjudicated seven
#   same-machine conjunct deleted 157 admitted · 9 sourced at the adjudicated seven · 106 cross-machine
#   both deleted                  235 admitted · 13 sourced at the adjudicated seven
#
# ### THE TWO MIDDLE LABELS WERE TRANSPOSED AT a6005a8 (R-03) - it read "trigger conjunct deleted
# 157 / same-machine conjunct deleted 96", which is each conjunct's figure attached to the other's
# name. Deleting the TRIGGER conjunct leaves SAME-MACHINE standing, and same-machine alone admits 96
# with 0 cross-machine; deleting the SAME-MACHINE conjunct leaves TRIGGER standing, and trigger alone
# admits 157, of which 106 are cross-machine. The 157 is f01d942's shipped predicate, measured.
#
# ### R-02, RECORDED HERE AS PART OF THE SAME RESIDUAL AND NOT CLOSED (audit G2-D16). The trigger
# conjunct reads the DELEGATING ROW'S OWN `Trig` cell - the same row, same table, same file as the
# `Event` cell a launderer is already editing - so widening that cell to every canonical code defeats
# the conjunct outright and re-admits `AP-9 -> GRANTED=AP-2` and `PL-7a -> CHECKPOINT=PL-7b`, the two
# adj7-sourced triples in the trigger-deleted column above. It was ruled NONBLOCKING by direct
# d59b740 precedent, because the sweep node below refuses it twice on general corpus-wide properties
# keyed on the governance anchor rather than on this mint's names.
# ### FOR THE ADJUDICATED SEVEN THIS IS NOW CLOSED AS A SIDE EFFECT AND NOT BY THIS PREDICATE: the
# chokepoint refuses the whole PRE_EXISTING_STRUCTURAL_PROOF route before `_resolve_delegation` is
# reached, so a widened `Trig` buys nothing there. ### FOR EVERY OTHER ROW IT IS OPEN. Delegation is
# a NECESSARY-CONDITIONS FILTER over the corpus and it still reads cells the editing row owns; that
# is the honest state of it, and this comment is the refusal to round it up to a closure.
ADJUDICATED_DELEGATION_ADMITS = frozenset({
    ("01-work-item:WI-11", "IN_PROGRESS", "WI-13"),
    ("01-work-item:WI-11", "IN_PROGRESS", "WI-9"),
    ("01-work-item:WI-13", "IN_PROGRESS", "WI-11"),
    ("01-work-item:WI-13", "IN_PROGRESS", "WI-9"),
    ("01-work-item:WI-14", "AWAITING_HUMAN", "WI-7"),          # DECLARED
    ("01-work-item:WI-14", "BLOCKED", "WI-5"),                 # DECLARED
    ("01-work-item:WI-14", "BLOCKED", "WI-6"),                 # DECLARED
    ("01-work-item:WI-14", "CANCELLED", "WI-12"),              # DECLARED
    ("01-work-item:WI-14", "CLOSED", "WI-3"),                  # DECLARED
    ("01-work-item:WI-2", "IN_PROGRESS", "WI-4"),
    ("01-work-item:WI-2", "IN_PROGRESS", "WI-8"),
    ("01-work-item:WI-4", "IN_PROGRESS", "WI-2"),
    ("01-work-item:WI-4", "IN_PROGRESS", "WI-8"),
    ("01-work-item:WI-5", "BLOCKED", "WI-6"),
    ("01-work-item:WI-6", "BLOCKED", "WI-5"),
    ("01-work-item:WI-8", "IN_PROGRESS", "WI-2"),
    ("01-work-item:WI-8", "IN_PROGRESS", "WI-4"),
    ("01-work-item:WI-9", "IN_PROGRESS", "WI-11"),
    ("01-work-item:WI-9", "IN_PROGRESS", "WI-13"),
    ("02-pipeline-instance:PL-10", "EXECUTED", "PL-11d"),
    ("02-pipeline-instance:PL-3", "REJECTED", "PL-5"),
    ("02-pipeline-instance:PL-5", "REJECTED", "PL-3"),
    ("02-pipeline-instance:PL-7v", "VOIDED", "PL-9v"),
    ("02-pipeline-instance:PL-9v", "VOIDED", "PL-7v"),
    ("03-external-effect-grant:EF-1", "GRANTED", "EF-2f"),     # NAMED RESIDUAL - see above
    ("03-external-effect-grant:EF-2f", "GRANTED", "EF-1"),
    ("03-external-effect-grant:EF-4", "VERIFIED", "EF-5"),
    ("03-external-effect-grant:EF-5", "VERIFIED", "EF-4"),
    ("04-approval:AP-8", "GRANTED", "AP-9"),
    ("05-observation:OB-3", "BOUND", "OB-4"),
    ("05-observation:OB-4", "BOUND", "OB-3"),
    ("06-identity-binding-claim:IB-1", "PROPOSED", "IB-3"),    # NAMED RESIDUAL - see above
    ("06-identity-binding-claim:IB-2", "CONFIRMED", "IB-2r"),
    ("06-identity-binding-claim:IB-2r", "CONFIRMED", "IB-2"),
    ("06-identity-binding-claim:IB-3", "PROPOSED", "IB-1"),
    ("06-identity-binding-claim:IB-5x", "CONFIRMED", "IB-2"),
    ("06-identity-binding-claim:IB-5x", "CONFIRMED", "IB-2r"),
    ("07-conflict:CF-6", "RESOLVED_BY_HUMAN", "CF-4"),         # DECLARED
    ("07-conflict:CF-6", "RESOLVED_BY_RULE", "CF-3"),          # DECLARED
    ("08-expectation:EX-1", "RAISED", "EX-5"),
    ("08-expectation:EX-2", "DISCHARGED", "EX-4"),
    ("08-expectation:EX-4", "DISCHARGED", "EX-2"),
    ("08-expectation:EX-5", "RAISED", "EX-1"),
    ("09-exception:EC-3", "RESOLVED", "EC-6"),
    ("09-exception:EC-6", "RESOLVED", "EC-3"),
    ("13-brake:BR-1", "ACTIVE", "BR-2"),
    ("13-brake:BR-1", "ACTIVE", "BR-3"),
    ("13-brake:BR-2", "ACTIVE", "BR-1"),
    ("13-brake:BR-2", "ACTIVE", "BR-3"),
    ("13-brake:BR-3", "ACTIVE", "BR-1"),
    ("13-brake:BR-3", "ACTIVE", "BR-2"),
})


# ------------------------------------------------------- CONSUMES-VALID: the co-transition contract
#
# The targeted governance adjudication of candidate 38b4bda REJECTED the first attempt at this class.
# Its guard proved only that the named event EXISTS and that the consuming row does not OWN it - no
# relationship of any kind between the consumer's durable write and the consumed event. So AP-9, the
# corpus's highest-severity open GR-2 obligation, could be relabelled `CONSUMES:ApprovalConsumed`
# (owner AP-7, which is MUTUALLY EXCLUSIVE with it) - and, worse, `CONSUMES:BrakeReleased`, an M13
# brake event with no machine, aggregate, family, causal or temporal relationship whatsoever to an M4
# approval freeze - and the entire suite stayed GREEN. THE CLASS ADMITTED ANY OF THE 98 EVENTS.
#
# THE RULING (adjudication sec 1/sec 2). CONSUMES is legitimate architecture: state-machines/
# registry.md:182 gives a co-transitioned event ONE producer and makes the other machine its
# CONSUMER. What is unauthorized is SELF-CERTIFICATION. `CONSUMES:<event>` is a claim, not a proof;
# moving from the prose `*(no state change)*` that laundered CF-7 to a structured token changes the
# syntax, not the failure mode. The relationship must be proven from authoritative STRUCTURED data.
#
# CONSUMES-VALID, rules 1-7, as adjudicated:
#   1  every named event exists in the sec-3 canonical corpus;
#   2  T is not itself the sec-3 producer of that event;
#   3  the event's sec-3 producer(s) must ALL resolve to rows of the 134-row corpus;
#   4  if T performs NO durable write, GR-2 does not bind it - the marker is DESCRIPTIVE and carries
#      NO EXEMPTING FORCE (an enumerated GR-1 refusal row must be NON_PRODUCING instead);
#   5  if T performs a durable write, all four hold, read from STRUCTURED COLUMNS ONLY:
#        (5a) CO-COMMIT DECLARED BIDIRECTIONALLY AND ROW-BOUND - see below;
#        (5b) NOT MUTUALLY EXCLUSIVE - owner and T are not same-machine rows whose From sets
#             intersect and whose To states differ;
#        (5c) CROSS-MACHINE - T's machine is not the owner's machine;
#        (5d) REPLAY COVERAGE - every field T declares it persists appears in a consumed event's
#             sec-5 payload;
#   6  DOWNGRADE PROHIBITION - EVENT_REQUIRED -> CONSUMES requires 5a-5d in full;
#   7  FAIL CLOSED - any CONSUMES row for which 5a-5d cannot be DECIDED fails the build. Never a
#      pass, never a skip.
#
# The narrative `## M2<->M3 co-transition rule` sections may NEVER be the predicate: a prose section
# is exactly what the G2 adjudication sec F refused. Only the Writes column speaks here.
#
# ---------------------------------------------------------------------------------------------
# ### 5a IS ROW-BOUND, NOT MACHINE-BOUND. THE SECOND REJECTION, AND WHAT IT COST.
#
# Replacement candidate 1ae365a implemented 5a by extracting the MACHINE INTEGER from a co-commit
# declaration and discarding the state token beside it. Its separate targeted re-adjudication
# (sec F) ruled that single reduction the ROOT of both blocking findings:
#
#   ### "A co-commit declaration is not owned by the row that wrote it. It is pooled across the whole
#   ### machine. Every row on machine M inherits every declaration any row on M's partner machine
#   ### ever wrote."
#
# Two manifestations of ONE defect, and one predicate closes both:
#   R-01  INTRA-CLASS. PL-10 (`CLAIMED`->`EXECUTED`) and PL-11 (`EXECUTED`->`VERIFIED`) exchange the
#         events they consume. Both stay M2 rows consuming M3-owned events, so the pooled {3}/{2}
#         sets never move. 5d cannot compensate: NEITHER ROW DECLARES A FIELD, so 5d is structurally
#         vacuous for it. Measured cost: 23 false-accepting (consumer, event) pairs across the 8
#         durable consumers, 0 false rejects.
#   R-02  CROSS-CLASS. PL-7a - the SOLE autonomous entry into CHECKPOINT, severity HIGHEST
#         GOVERNANCE, an OPEN founder-gated obligation - ANNEXES EF-3's "co-commit M2 `EXECUTED`",
#         a declaration written for PL-10's benefit, and is laundered into CONSUMES by ONE TOKEN.
#         open_founder_gated_obligations fell 7 -> 6 and nothing objected.
#
# ### THE FIX USES DATA THAT WAS ALREADY THERE. All twenty co-commit declarations in the corpus
# already carry a backticked canonical state beside the machine token, and in every one that state
# is the COUNTERPART ROW'S `To` STATE. The old parser read the integer and threw the state away.
# 5a therefore binds the ordered pair (MACHINE, TARGET STATE), in BOTH directions:
#
#     forward   there is a state s in To(owner) such that (M(owner), s) is declared by T;
#     reverse   there is a state s in To(T)     such that (M(T),     s) is declared by the OWNER.
#
# ### THE REVERSE LEG IS WHAT CLOSES PL-7a. EF-3's declaration names `EXECUTED` - the state PL-10
# enters - not `CHECKPOINT`. A row can no longer discharge an EVENT_REQUIRED obligation using a
# declaration written for somebody else, because the only row-specific evidence now lives in a cell
# the candidate row does not author. That is what makes the proof non-circular.
#
# UNDECIDABLE IS A FAILURE (rule 7): if either row names no canonical `To` state, or declares the
# machine at issue with no canonical state beside it, the relationship cannot be decided and the
# build fails. PL-9's "M4 `ApprovalConsumed`" leg is exactly that shape - an event name where a
# state belongs - and it is never exercised today because no owner of a PL-9-consumed event lives
# on M4. If one ever does, this fails closed rather than guessing.
#
# What the key may NOT include, all REFUSED by name in the re-adjudication sec H.2 as architecture
# invention: a transition id inside the declaration; the source (`From`) state; an event name inside
# the declaration; a commit/causation identity; a new column. And 5a is a CONJUNCT ADDED TO the
# existing rule, never a disjunct replacing it - 5b, 5c and 5d all remain required in full.

_CO_COMMIT = re.compile(r"co-commit", re.I)
_MACHINE_TOKEN = re.compile(r"\bM(\d{1,2})\b")


def _machine_number(machine: str) -> int | None:
    """M2 from `02-pipeline-instance`. The machine-file prefix IS the machine number (registry
    sec 4 enumerates M1..M13 against exactly these thirteen files)."""
    m = re.match(r"^(\d{1,2})-", machine)
    return int(m.group(1)) if m else None


def _writes_segments(cell: str) -> tuple[str, str]:
    """A Writes cell is `<durable field declaration>[; co-commit <machine declaration>]`.

    Split at the FIRST `co-commit` token: before it the row declares what it PERSISTS, after it
    which OTHER MACHINES commit in the same transaction. This is the repository's OWN convention,
    not this unit's invention - EF-2 carried exactly this shape at the certified predecessor
    ("`claimed_at`; co-commit M2 `CLAIMED`, M4 `CONSUMED`") and PL-9 the co-commit-only form.
    """
    m = _CO_COMMIT.search(cell)
    return (cell, "") if not m else (cell[: m.start()], cell[m.end():])


def _declared_cocommit_pairs(cell: str, states: set[str]) -> tuple[set[tuple[int, str]], set[int]]:
    """### 5a's subject, ROW-BOUND: which (MACHINE, TARGET STATE) pairs this row declares it
    co-commits with, read only from the co-commit segment of the structured Writes column.

    A machine token OWNS the text up to the next machine token, and the states are the canonical
    ones inside BACKTICKS in that span. `{VERIFIED,FAILED}` therefore yields two pairs, which is how
    PL-15 binds EF-5's two-state branch and CM-5's `COMPLETED` in one declaration.

    Returns (pairs, machines_declared_without_a_canonical_state). The second set is what rule 7
    needs: PL-9 writes "M4 `ApprovalConsumed`" - an EVENT NAME where a state belongs - so M4 is
    declared but UNDECIDABLE. It is never exercised today (no owner of a PL-9-consumed event lives
    on M4) and fails closed if it ever is, rather than being silently read as a bare machine.

    ### The old candidate returned `{int(n) for n in _MACHINE_TOKEN.findall(...)}` - the integers
    ### alone. That one reduction pooled every declaration across a whole machine and is the single
    ### root of both blocking findings. The state token was always present; it was simply discarded.
    """
    segment = _writes_segments(cell)[1]
    tokens = list(_MACHINE_TOKEN.finditer(segment))
    pairs: set[tuple[int, str]] = set()
    unstated: set[int] = set()
    for i, tok in enumerate(tokens):
        machine = int(tok.group(1))
        end = tokens[i + 1].start() if i + 1 < len(tokens) else len(segment)
        span = segment[tok.end():end]
        named: set[str] = set()
        for group in re.findall(r"`([^`]*)`", span):
            named |= _states_in(group, states)
        if named:
            pairs |= {(machine, s) for s in named}
        else:
            unstated.add(machine)
    return pairs, unstated


def _declared_write_fields(cell: str) -> set[str]:
    """4(d)'s subject: which fields this row DECLARES it persists. Two structured forms, and
    nothing else counts:
      (i)  a backticked declaration, separator-delimited - `exposure, unknown_reason`
      (ii) a `name=value` assignment, backticked or bare - `frozen=true`
    PROSE DECLARES NO FIELD. That is why PL-10's "ext: the world was touched" contributes none and
    why this cannot be gamed by writing a field name into a sentence.
    """
    segment = _writes_segments(cell)[0]
    fields: set[str] = set()
    for group in re.findall(r"`([^`]*)`", segment):
        for part in re.split(r"[,;|/{}∈]", group.replace("\\|", "|")):
            fields.add(part.split("=")[0].strip().strip("*? []()"))
    fields |= set(re.findall(r"\b([a-z][a-z0-9_]*)\s*=", segment))
    return {f for f in fields if re.fullmatch(r"[a-z][a-z0-9_]*", f)}


def _event_payloads() -> dict[str, set[str]]:
    """state-machines/registry.md sec 5 - every event's declared ADDED payload. 4(d) reads this and
    nothing else: an event can record only what its payload carries."""
    section = read(MACHINES / "registry.md")
    section = section.split("## 5. CANONICAL EVENT REGISTRY")[1].split("## 6.")[0]
    payloads: dict[str, set[str]] = {}
    for line in section.split("\n"):
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line)[1:-1]]
        if len(cells) < 3 or cells[0].startswith("-"):
            continue
        if re.sub(r"[*`\s]", "", cells[0]) == "Event":
            continue
        fields = _declared_write_fields(cells[2])
        for name in re.findall(r"`([A-Za-z][A-Za-z0-9]*)`", cells[0]):
            payloads.setdefault(name, set()).update(fields)
    return payloads


def _side_states(row: dict, states: set[str], right: bool) -> set[str]:
    if "→" not in row["from_to"]:
        return set() if right else _states_in(row["from_to"], states)
    return _states_in(row["from_to"].split("→", 1)[1 if right else 0], states)


def _mutually_exclusive(a: dict, b: dict, states: set[str]) -> bool:
    """4(b). Same machine, From sets intersect, To states differ ⇒ the two rows cannot both fire on
    one aggregate. Decisive, because if the producer's transition did not fire then its event was
    never emitted and it can record NOTHING. AP-9 (`GRANTED`->`GRANTED` frozen) and AP-7
    (`GRANTED`->`CONSUMED`) are exactly that pair - which is how AP-9 was laundered."""
    if a["machine"] != b["machine"]:
        return False
    if not (_side_states(a, states, False) & _side_states(b, states, False)):
        return False
    return _side_states(a, states, True) != _side_states(b, states, True)


def _consumes_context(g2: dict) -> dict:
    """Everything CONSUMES-VALID reads, resolved once. Hostile tests overlay this to inject
    synthetic rows, so the contract they exercise is the one the live corpus is judged by."""
    return {"rows_by_id": dict(g2["rows_by_id"]),
            "owners_of": {e["name"]: list(e["producers"]) for e in g2["registry"]["owned"]},
            "corpus": set(g2["registry"]["corpus"]),
            "producers_of": g2["registry"]["producers_of"],
            "payloads": _event_payloads(), "states": g2["states"]}


def _consumes_relationship_errors(row: dict, names: list[str], ctx: dict) -> list[str]:
    """CONSUMES-VALID applied to one row. Returns EVERY reason the declaration is not proven; an
    empty list is the only pass. Undecidable is an error, never a pass and never a skip (rule 6)."""
    states, errors = ctx["states"], []
    key, consumer_m = row["key"], _machine_number(row["machine"])
    if not names:
        return [f"{key}: CONSUMES names no event"]
    durable = _durable_write(row, states)
    declared, declared_unstated = _declared_cocommit_pairs(row["writes"], states)
    consumer_to = _side_states(row, states, True)
    covered: set[str] = set()
    for name in names:
        if name not in ctx["corpus"]:                                              # rule 1
            errors.append(f"{key}: consumes {name!r}, which is not a canonical event")
            continue
        # The owner must be a CORPUS TRANSITION. An event whose sec-3 producer is a RULE - as
        # IllegalTransitionAttempted's is, GR-1 - offers no transition to co-commit with, so it can
        # never be consumed. PL-15x and IB-5x are therefore NON_PRODUCING, per G2 sec H step 7.
        owners = ctx["owners_of"].get(name, [])
        owner_rows = [ctx["rows_by_id"][o] for o in owners if o in ctx["rows_by_id"]]
        if not owners or len(owner_rows) != len(owners):
            errors.append(
                f"{key}: consumes {name!r} whose declared sec-3 producer(s) "
                f"{owners or ['<none declared>']} do not all resolve to rows of the 134-row corpus "
                "- an event owned by a RULE rather than by a transition cannot be consumed, and "
                "such a row must be NON_PRODUCING"
            )
            continue
        if name in ctx["producers_of"].get(row["id"], set()):                       # rule 2
            errors.append(f"{key}: declares it CONSUMES {name}, which it actually OWNS")
            continue
        covered |= ctx["payloads"].get(name, set())
        if not durable:
            continue      # rule 3 - GR-2 does not bind; DESCRIPTIVE marker, no exempting force
        for owner in owner_rows:
            owner_m = _machine_number(owner["machine"])
            if _mutually_exclusive(row, owner, states):                             # 4(b)
                errors.append(
                    f"{key}: consumes {name!r} owned by {owner['key']}, which is MUTUALLY "
                    "EXCLUSIVE with it (same machine, From sets intersect, To states differ). If "
                    "the owner's transition did not fire, its event was never emitted and records "
                    "nothing"
                )
            if owner_m == consumer_m:                                               # 4(c)
                errors.append(
                    f"{key}: consumes {name!r} owned by {owner['key']} on its OWN machine "
                    f"(M{consumer_m}) - a within-machine relationship is production or delegation, "
                    "never consumption"
                )
            # ---- 5a FORWARD: T must name the state the OWNER ENTERS, on the owner's machine.
            owner_to = _side_states(owner, states, True)
            if not owner_to:
                errors.append(                                                      # rule 7
                    f"{key}/{name}: UNDECIDABLE - owner {owner['key']} names no canonical To state, "
                    "so no row-bound co-commit can be decided against it"
                )
            elif not any((owner_m, s) in declared for s in owner_to):
                if owner_m in declared_unstated:
                    errors.append(                                                  # rule 7
                        f"{key}/{name}: UNDECIDABLE - declares co-commit with M{owner_m} but names "
                        "no canonical state beside it, so WHICH ROW on that machine is unknown"
                    )
                else:
                    errors.append(
                        f"{key}/{name}: FORWARD - declares co-commit {sorted(declared)}, owner "
                        f"{owner['key']} enters M{owner_m} {sorted(owner_to)}. The declaration must "
                        "name the state the OWNER ENTERS: a machine number alone is pooled across "
                        "every row of that machine and identifies no relationship"
                    )
            # ---- 5a REVERSE: the OWNER must name the state T ENTERS, on T's machine. ### THIS IS
            # the leg a candidate row cannot author for itself, and it is what closes PL-7a.
            reciprocal, reciprocal_unstated = _declared_cocommit_pairs(owner["writes"], states)
            if not consumer_to:
                errors.append(                                                      # rule 7
                    f"{key}/{name}: UNDECIDABLE - it names no canonical To state, so the owner's "
                    "reciprocal declaration cannot be bound to it"
                )
            elif not any((consumer_m, s) in reciprocal for s in consumer_to):
                if consumer_m in reciprocal_unstated:
                    errors.append(                                                  # rule 7
                        f"{key}/{name}: UNDECIDABLE - owner {owner['key']} declares co-commit with "
                        f"M{consumer_m} but names no canonical state beside it"
                    )
                else:
                    errors.append(
                        f"{key}/{name}: REVERSE - owner {owner['key']} declares co-commit "
                        f"{sorted(reciprocal)}, consumer enters M{consumer_m} {sorted(consumer_to)}. "
                        "The owner's own cell must name the state THIS row enters; a declaration "
                        "written for a different row on this machine is not evidence for this one"
                    )
    if durable:                                                                     # 4(d)
        missing = sorted(_declared_write_fields(row["writes"]) - covered)
        if missing:
            errors.append(
                f"{key}: its durable write declares {missing}, which no consumed event's sec-5 "
                f"payload carries (the consumed payloads cover {sorted(covered) or 'nothing'}) - a "
                "full-history replay could not reconstruct the write, so GR-2 is NOT discharged"
            )
    return errors


# ### THE TWO ACCEPTED-BUT-UNDECLARED PAIRS, ADJUDICATED INDIVIDUALLY AND CARRIED EXPLICITLY.
#
# The row binding takes the durable-consumer matrix from 23 undeclared accepts to these two. Neither
# is a silent allowance: both were ruled on by name in the re-adjudication sec H.5, and the matrix
# node asserts this set EXACTLY - no more, and no fewer.
#
#   PL-9 -> EffectAttempted     ### NOT A FALSE ACCEPT. events/registry.md sec 3 declares
#                               `EffectAttempted`(EF-2) - THE SAME OWNER ROW as GrantClaimed - and
#                               PL-9's own Writes cell names it: "co-commit: M3 `CLAIMED` + M4
#                               `ApprovalConsumed` + `EffectAttempted` (emitted BEFORE the call)".
#                               Same owner row, same transaction, one authorized semantic operation.
#                               The relationship is architecturally TRUE.
#
#   PL-11c -> OutcomeUnknown    ### CARRIED RESIDUAL - JUSTIFIED, INHERITED, NOT CLOSED HERE.
#                               OutcomeUnknown's sec-3 producers are EF-3u/EF-4c/EF-4u. EF-4c and
#                               EF-4u ARE PL-11c's genuine partners; only EF-3u is causally wrong,
#                               and it passes because all three declare M2 `NEEDS_VERIFICATION` and
#                               both PL-10u and PL-11c target NEEDS_VERIFICATION - so the
#                               (machine, To-state) key is not injective when two rows on one
#                               machine share a target state.
#                               ### ROOT CAUSE: events/registry.md sec 3's three-producer list - a
#                               FROZEN, FORBIDDEN SURFACE. All three closures were considered and
#                               REFUSED by the re-adjudication: narrowing sec 3 is a producer-map
#                               change (forbidden, the 98 is frozen); adding a `From` state to
#                               co-commit declarations invents a convention no declaration carries;
#                               and requiring (owner, machine, state) to resolve to exactly one
#                               consumer row was VERIFIED TO OVER-REJECT - EF-5's M2
#                               `{VERIFIED,FAILED}` resolves to PL-11, PL-10f and PL-15, producing
#                               FALSE REJECTS OF LEGITIMATE ROWS, which is worse than the residual.
#                               Measured against sec 3 AS FROZEN it is not a proven false accept;
#                               it is an imprecision inherited from a frozen producer map.
ADJUDICATED_UNDECLARED_ACCEPTS = frozenset({
    ("02-pipeline-instance:PL-9", "EffectAttempted"),
    ("02-pipeline-instance:PL-11c", "OutcomeUnknown"),
})


# ------------------------------------------- the EVENT_REQUIRED set, frozen by IDENTITY not by count
#
# The rejected candidate held this population with {spec obligation ids} == {registered obligation
# ids} plus open_founder_gated_obligations == len(obligations). Both are CONSISTENCY checks: a
# coordinated edit that removes a row from the specs, from the obligation registry and from the count
# satisfies all of them. That is exactly how PL-7a - the SOLE autonomous entry into CHECKPOINT - went
# 7 -> 6 with nothing objecting. ### A COUNT IS NOT THE INVARIANT; THE COUNT IS A CONSEQUENCE.
#
# The anchor below is the adjudicated seven, held in the control artifact itself so that editing the
# audit alone cannot move it. A member may leave ONLY through a recorded discharge that names its
# route and cites its authority - and the route is then RE-PROVEN MECHANICALLY, so writing the
# discharge record is not itself the discharge.
ADJUDICATED_EVENT_REQUIRED = frozenset({
    "02-pipeline-instance:PL-7a", "04-approval:AP-9", "07-conflict:CF-7", "09-exception:EC-7",
    "11-policy:PO-2", "11-policy:PO-3", "12-rule:RU-8",
})
# "No third route exists. Silent deletion is a build failure."
DISCHARGE_ROUTES = ("MINTED_CANONICAL_EVENT", "PRE_EXISTING_STRUCTURAL_PROOF")


def _registered_durable_writes(audit: dict) -> dict[str, str]:
    """`{transition: durable_write}` from the FOUNDER-GATED OBLIGATION REGISTER.

    This is the authoritative statement of WHAT WRITE each frozen-set member performs, written when
    the obligation was adjudicated and held under
    test_the_founder_gated_event_obligations_are_explicit_and_cannot_be_silently_discharged, which
    requires every register entry to carry a NON-EMPTY `durable_write` and forbids the register to
    shrink. It is therefore a datum the discharging edit may not quietly empty.
    """
    return {str(o.get("transition", "")): str(o.get("durable_write", "") or "").strip()
            for o in (audit.get("founder_gated_event_obligations") or [])}


# ### THE CHOKEPOINT (P5 U5.2 SECOND REPLACEMENT). DEFAULT-DENY FOR THE ADJUDICATED SEVEN, DECIDED
# ### BEFORE ANY ROUTE PREDICATE RUNS.
#
# FOUR candidates have now been rejected on ONE defect wearing four different coats: a discharge
# admitted on evidence THE DISCHARGING EDIT ITSELF SUPPLIES.
#
#   38b4bda   AP-9  `CONSUMES:BrakeReleased`            - a claim taken as its own proof
#   1ae365a   PL-7a `CONSUMES:EffectExecuted`           - a pooled machine declaration annexed
#   f01d942   a weak `DELEGATES_TO` predicate, AND `NON_PRODUCING` re-reading the row's own `Writes`
#   a6005a8   `CONSUMES` under PRE_EXISTING_STRUCTURAL_PROOF, re-reading the row's own `Writes`
#
# Each remediation patched the route that had been found, and the next route appeared. The separate
# targeted adjudication of a6005a8 ruled that ROUTE-BY-ROUTE PATCHING IS THE WRONG REMEDIATION, and
# proved why. Applied honestly to this corpus, N-01's rule - "a discharge may never be admitted on a
# re-reading of a cell the discharging edit is itself permitted to change" - has a stark consequence:
# ### EVERY INPUT TO EVERY STRUCTURAL ROUTE PREDICATE IS SUCH A CELL. The row's `Writes`, its `Trig`
# and its `From -> To`; the OWNER row's `Writes` (the bidirectionally forged co-commit, N-02); and
# events/registry.md sec 3 itself (the MINTED re-attribution). There is no structural discharge of an
# adjudicated member that is not self-certifying, because ### THE ADJUDICATION IS THE ONLY FACT THE
# EDIT CANNOT AUTHOR. Patching route n guarantees route n+1; n+1 and n+2 were both found while
# reproducing the review of n.
#
# So the seven do not get a predicate. They get an AUTHORIZATION, checked ONCE, HERE, BEFORE
# DISPATCH, and DEFAULT-DENY:
#
#   PRE_EXISTING_STRUCTURAL_PROOF   STRUCTURALLY UNAVAILABLE, in ALL THREE sub-routes - CONSUMES,
#                                   DELEGATES_TO and NON_PRODUCING. This is N-01 GENERALISED:
#                                   a6005a8 applied the bar to NON_PRODUCING alone and was rejected
#                                   on the CONSUMES sub-route beside it.
#   MINTED_CANONICAL_EVENT          admissible ONLY when `(key, event)` is in the guard-resident
#                                   founder-authorization table below. The sec-3 checks in the route
#                                   body then CORROBORATE that authorization; they never grant it.
#   anything else                   REFUSED.
#
# ### WHY THIS STOPS A FIFTH ROUTE, WHICH NO ROUTE PATCH DOES. For a member of
# ADJUDICATED_EVENT_REQUIRED the admissible-discharge set is now a FINITE EXPLICIT WHITELIST of
# (row, event) pairs, and for every other (route, event) NO PREDICATE IS CONSULTED AT ALL. A
# sub-route added to PRE_EXISTING_STRUCTURAL_PROOF next year is unreachable for these rows by
# construction; a new top-level route string is refused here AND by `DISCHARGE_ROUTES` in the caller;
# and an EIGHTH obligation joining the frozen set inherits default-deny automatically - which the
# seven-name `MINTED` dict in test_p5_canonical_event_mint.py, a record comparison in another file,
# cannot do for it.
#
# ### THE ROUTE PREDICATES BELOW ARE NOT WEAKENED AND MUST NOT BE PATCHED FOR THIS.
# `_consumes_relationship_errors`, `_resolve_delegation` and `_durable_write` remain the GENERAL
# CORPUS PREDICATES they are, judging the other 127 rows on their structure. The chokepoint does not
# make them stricter; it removes the seven adjudicated rows from their jurisdiction entirely.
#
# ### ZERO FALSE REJECTS, AND THE REASON IS STRUCTURAL RATHER THAN MEASURED. All seven recorded
# discharges are route MINTED_CANONICAL_EVENT (TRANSITION-EVENT-AUDIT.yaml,
# `frozen_event_required_set.discharges`), and the audit's own note records that
# PRE_EXISTING_STRUCTURAL_PROOF "remains available and unused". Nothing legitimate uses the route
# this bars, so barring it refuses nothing the corpus asserts.
#
# ### THIS TABLE IS AN AUTHORIZATION, NOT A MEASUREMENT, AND THAT IS WHY IT IS A LITERAL. Every other
# frozen population in this file is re-derived from structured data and asserted; this one may not
# be, because its subject is FOUNDER/ARCHITECT DECISIONS D1 and D2 (2026-08-12), which no column of
# any table carries. A route whose premise is an authorization cannot have a predicate - the only
# faithful mechanization of "the founder minted this fact for this row" is the list of pairs the
# founder authorized. Adding a pair here is an adjudicated act of the same weight as amending
# ADJUDICATED_EVENT_REQUIRED itself. The table is held against the audit's recorded discharges in
# BOTH directions by test_the_founder_authorization_table_and_the_recorded_discharges_agree_exactly,
# so it can neither drift from the record nor be quietly widened to cover one.
FOUNDER_AUTHORIZED_DISCHARGES = frozenset({
    ("02-pipeline-instance:PL-7a", "AutonomousAdmissionRecorded"),
    ("04-approval:AP-9", "ApprovalFrozen"),
    ("07-conflict:CF-7", "ConflictPartyAttached"),
    ("09-exception:EC-7", "ExceptionSeverityChanged"),
    ("11-policy:PO-2", "PolicySubmitted"),
    ("11-policy:PO-3", "PolicyApproved"),
    ("12-rule:RU-8", "RuleExpired"),
})

# The single phrase every chokepoint refusal carries, so a hostile node can assert that THE
# CHOKEPOINT refused - not a mint-name literal, not a count literal, not a fixture premise.
CHOKEPOINT_MARK = "ADJUDICATED-DISCHARGE CHOKEPOINT"


def _adjudicated_discharge_authorization_errors(key: str, entry: dict) -> list:
    """### THE CHOKEPOINT ITSELF. Default-deny, for a member of ADJUDICATED_EVENT_REQUIRED only.

    Called before dispatch, so no route predicate is reached for a discharge this refuses. It reads
    EXACTLY TWO THINGS: the route string and the event name from the discharge record, both of which
    the launderer authors - and it compares them against a table the launderer cannot author without
    editing this guard. It reads NO specification cell, so there is no cell to forge.
    """
    route = entry.get("route")
    event = str(entry.get("event", ""))
    if route == "PRE_EXISTING_STRUCTURAL_PROOF":
        return [
            f"### {key}: {CHOKEPOINT_MARK} - PRE_EXISTING_STRUCTURAL_PROOF IS NOT AN AVAILABLE "
            "DISCHARGE ROUTE FOR AN ADJUDICATED FOUNDER-GATED ROW, in ANY of its three sub-routes "
            "(CONSUMES, DELEGATES_TO, NON_PRODUCING). Every input those predicates read - this "
            "row's `Writes`, `Trig` and `From -> To` cells, and the OWNER row's `Writes` cell - is "
            "authored by the very edit performing the discharge, so a structural proof of an "
            "adjudicated member is a proof the launderer writes for itself. Four candidates were "
            "rejected on four different such routes. A member leaves ONLY by a canonical event "
            "MINTED for it under founder/architect authority, and only for a (row, event) pair in "
            "FOUNDER_AUTHORIZED_DISCHARGES. Retracting or re-founding the write is an AMENDMENT OF "
            "THE ADJUDICATED SET, which has its own guard and its own authority"
        ]
    if route == "MINTED_CANONICAL_EVENT":
        if (key, event) not in FOUNDER_AUTHORIZED_DISCHARGES:
            return [
                f"### {key}: {CHOKEPOINT_MARK} - NO FOUNDER AUTHORIZATION EXISTS FOR THE MINTED "
                f"DISCHARGE {event!r}. The MINTED route's premise is that a founder/architect "
                "created a canonical fact FOR THIS ROW; that premise is not a property of any "
                "structured column, so it cannot be re-derived from events/registry.md sec 3 - "
                "sec 3 is a surface the discharging edit may also author, and re-attributing this "
                "row to some OTHER same-machine canonical event corroborates from sec 3 perfectly "
                "well. The authorized pairs are held in this guard as "
                "FOUNDER_AUTHORIZED_DISCHARGES; this row/event pair is not one of them"
            ]
        return []
    return [
        f"### {key}: {CHOKEPOINT_MARK} - discharge route {route!r} is not authorized for an "
        "adjudicated founder-gated row. DEFAULT-DENY: the admissible set for these rows is a finite "
        "explicit whitelist, so a route added to this guard later - or invented in the record - is "
        "unreachable for them until it is adjudicated"
    ]


# ### N-01 (P5 U5.2 replacement). A DISCHARGE MAY NEVER BE ADMITTED ON A RE-READING OF A CELL THE
# ### DISCHARGING EDIT IS ITSELF PERMITTED TO CHANGE.
#
# The first candidate f01d942 re-proved the NON_PRODUCING route with `_durable_write(rec["row"])` -
# a re-reading of the row's own `Writes` cell. That cell is authored by the very edit performing the
# discharge, so the route was self-certifying: empty the Writes cell, flip the Event cell to
# `NON_PRODUCING:ENUMERATED_NO_OP`, coordinate the audit records, and the row leaves the frozen seven
# with the discharge machinery green. Three of the seven - AP-9, CF-7 and EC-7, precisely those whose
# durable write is a FIELD write rather than a state change - fell to a TWO-CELL specification edit,
# AP-9 being the row of the 38b4bda rejection. This is the same self-certification the 38b4bda
# adjudication forbade for CONSUMES, applied to the one route that never received the ruling.
#
# THE RULE. For a member of ADJUDICATED_EVENT_REQUIRED the register's own `durable_write` field is
# authoritative, not the row's cell - and every member's register entry records one, because the
# obligation EXISTS only because the write does. The NON_PRODUCING route is therefore STRUCTURALLY
# UNAVAILABLE to a frozen-set member: a row may leave by minting the fact it was missing, or by
# proving a PRE-EXISTING relationship (CONSUMES / DELEGATES_TO) that acquires somebody else's event -
# never by asserting that the write the adjudication recorded does not happen. Retracting the write
# itself is an amendment of the adjudicated set, which has its own guard and its own authority.
# ZERO FALSE REJECTS: no discharge in this corpus uses the route, and the register field it reads is
# separately held non-empty and non-shrinkable.
#
# ### KEPT UNDER THE CHOKEPOINT, NOT REPLACED BY IT (P5 U5.2 second replacement) - AND STATED
# ### HONESTLY: IT IS NOW UNREACHABLE. The chokepoint above refuses PRE_EXISTING_STRUCTURAL_PROOF for
# an adjudicated member before this branch is reached, and `_discharge_route_errors` has exactly ONE
# caller, the loop over ADJUDICATED_EVENT_REQUIRED in `_event_required_set_errors`. So every branch
# below the chokepoint - this NON_PRODUCING bar, the CONSUMES branch and the DELEGATES_TO branch - is
# dead on the discharge path today, and NO MUTATION OF THEM CAN BE CAUGHT BY THIS SUITE. That is
# recorded rather than papered over: the a6005a8 adjudication ruled expressly that N-01's bar and its
# register-authority defence in depth are to be KEPT, because they are what the chokepoint
# generalises and they are what would still stand if the chokepoint were ever narrowed or its caller
# widened. `_event_required_set_errors` separately requires every adjudicated member to carry a
# non-empty registered `durable_write`, and THAT assertion is live and is caught by mutation.
# `_consumes_relationship_errors` and `_resolve_delegation` themselves remain fully live as the
# CLASSIFICATION predicates over the whole corpus, which is a different call path entirely.
def _discharge_route_errors(key: str, entry: dict, rec: dict, ctx: dict, states: set[str],
                            audit: dict) -> list:
    """### A discharge is real only if it is AUTHORIZED, and only then if the row also satisfies the
    corroborating facts. This is what stops a launderer from simply WRITING a discharge record.

    ### ORDER MATTERS AND IS THE WHOLE POINT (the a6005a8 re-adjudication). For a member of
    ADJUDICATED_EVENT_REQUIRED the chokepoint runs FIRST, before any route predicate is dispatched,
    and it is DEFAULT-DENY. Only a founder-authorized MINTED pair survives it, and only then do the
    sec-3 checks below run - as CORROBORATION of an authorization, never as the authorization. The
    structural predicates are unchanged general corpus predicates; the seven are simply outside their
    jurisdiction, because every cell those predicates read is a cell the discharging edit authors."""
    route = entry.get("route")
    if key in ADJUDICATED_EVENT_REQUIRED:
        refused = _adjudicated_discharge_authorization_errors(key, entry)
        if refused:
            return refused
    if route == "MINTED_CANONICAL_EVENT":
        event = str(entry.get("event", ""))
        if event not in ctx["corpus"]:
            return [f"{key}: claims minted canonical event {event!r}, which is not in the sec-3 "
                    "corpus - the frozen 98 is founder/architect authority"]
        if event not in ctx["producers_of"].get(rec["row"]["id"], set()):
            return [f"{key}: claims {event!r} but sec 3 does not declare this row a producer of it"]
        return []
    if route == "PRE_EXISTING_STRUCTURAL_PROOF":
        if rec["class"] == "CONSUMES":
            return [f"{key}: claims a pre-existing structural CONSUMES proof that does not hold: {e}"
                    for e in _consumes_relationship_errors(
                        rec["row"], [n for n in rec["arg"].split(",") if n], ctx)]
        if rec["class"] == "NON_PRODUCING":
            # ---- N-01. The route may NOT be re-proven from the row's own `Writes` cell, which the
            # discharging edit authors. The obligation register is the authority.
            registered = _registered_durable_writes(audit).get(key)
            if registered is None:
                return [f"{key}: claims the NON_PRODUCING route while carrying NO entry in "
                        "founder_gated_event_obligations - the durable write this row was gated on "
                        "can then only be re-read from the row's OWN Writes cell, which the "
                        "discharging edit authors. FAIL CLOSED: the register may not shrink"]
            if registered:
                return [
                    f"### {key}: NON_PRODUCING IS NOT AN AVAILABLE DISCHARGE ROUTE FOR AN "
                    f"ADJUDICATED FOUNDER-GATED ROW. The obligation register records its durable "
                    f"write as {registered!r}. Re-proving 'this row writes nothing' from the row's "
                    "own `Writes` cell would let the DISCHARGING EDIT supply its own evidence - the "
                    "self-certification the 38b4bda adjudication forbade. A member leaves by "
                    "MINTING the fact it was missing, or by proving a PRE-EXISTING CONSUMES / "
                    "DELEGATES_TO relationship that acquires another row's event. Retracting the "
                    "write is an AMENDMENT OF THE ADJUDICATED SET, not a discharge of it"
                ]
            return ([f"{key}: claims NON_PRODUCING while still performing a durable write"]
                    if _durable_write(rec["row"], states) else [])
        if rec["class"] == "DELEGATES_TO":
            return [f"{key}: claims a DELEGATES_TO proof that does not resolve: {e}"
                    for e in _resolve_delegation(rec["row"], rec["arg"], ctx["rows_by_id"],
                                                 ctx["producers_of"], states)["errors"]]
        return [f"{key}: claims a structural proof but is classified {rec['class']}"]
    return []                                     # an unknown route is reported by the caller


def _event_required_set_errors(classified: dict, audit: dict, ctx: dict, states: set[str]) -> list:
    """SET IDENTITY, both ways, plus authorized-discharge evidence. Fail closed."""
    errors: list[str] = []
    record = audit.get("frozen_event_required_set")
    if not isinstance(record, dict):
        return ["the audit carries no `frozen_event_required_set` record - the EVENT_REQUIRED "
                "population would then be held by a COUNT, which is how PL-7a disappeared"]
    for field in ("record_id", "adjudication", "adjudication_digest", "recorded_on"):
        if not str(record.get(field, "")).strip():
            errors.append(f"frozen_event_required_set.{field} is empty - the frozen set must be a "
                          "NAMED, DATED, ADJUDICATION-ATTRIBUTED record")
    frozen = {str(k) for k in (record.get("members") or [])}
    if frozen != set(ADJUDICATED_EVENT_REQUIRED):
        errors.append(
            "the audit's frozen EVENT_REQUIRED record no longer equals the adjudicated seven: "
            f"record-only={sorted(frozen - ADJUDICATED_EVENT_REQUIRED)}, "
            f"adjudicated-only={sorted(ADJUDICATED_EVENT_REQUIRED - frozen)}"
        )
    discharges = {}
    for entry in record.get("discharges") or []:
        key = str(entry.get("transition", ""))
        discharges[key] = entry
        if key not in ADJUDICATED_EVENT_REQUIRED:
            errors.append(f"discharge names {key!r}, which was never in the frozen set")
        if entry.get("route") not in DISCHARGE_ROUTES:
            errors.append(f"{key}: discharge route {entry.get('route')!r} is not one of "
                          f"{list(DISCHARGE_ROUTES)} - NO THIRD ROUTE EXISTS")
        if not str(entry.get("authority", "")).strip():
            errors.append(f"{key}: the discharge cites no authority - it may not be self-certified "
                          "by the same edit that performs the reclassification")
    # ### N-01's AUTHORITY MUST EXIST BEFORE IT CAN BE CONSULTED. Every adjudicated member records
    # its durable write in the obligation register; that field is what makes the NON_PRODUCING route
    # structurally unavailable, so an empty or missing one is a build failure HERE and not only in
    # the register's own node. Fail closed: a launderer who empties the field must also delete this.
    registered_writes = _registered_durable_writes(audit)
    for key in sorted(ADJUDICATED_EVENT_REQUIRED):
        if not registered_writes.get(key):
            errors.append(
                f"{key}: the founder-gated obligation register records no durable_write for this "
                "adjudicated member. That field is the AUTHORITY that bars the NON_PRODUCING "
                "discharge route (N-01); without it the route would fall back to re-reading the "
                "row's own Writes cell, which the discharging edit authors"
            )
    computed = {k for k, v in classified.items() if v["class"] == "EVENT_REQUIRED"}
    for key in sorted(ADJUDICATED_EVENT_REQUIRED):
        if key in computed:
            if key in discharges:
                errors.append(f"{key}: a discharge is recorded while the row is still EVENT_REQUIRED")
            continue
        entry = discharges.get(key)
        if not entry:
            errors.append(
                f"### {key} LEFT EVENT_REQUIRED WITH NO RECORDED DISCHARGE. Silent deletion is a "
                "build failure. It may leave only by (i) a canonical event minted under "
                "founder/architect authority, or (ii) a pre-existing structural proof it actually "
                "satisfies - and never on the strength of a token its own row added."
            )
            continue
        rec = classified.get(key)
        if rec is None:
            errors.append(f"{key}: discharged, and no longer classified at all")
            continue
        errors += _discharge_route_errors(key, entry, rec, ctx, states, audit)
    for key in sorted(computed - set(ADJUDICATED_EVENT_REQUIRED)):
        errors.append(
            f"{key} JOINED EVENT_REQUIRED without amending the frozen adjudicated record - "
            "registering a new founder-gated obligation is an adjudicated act"
        )
    return errors


def _g2_state() -> dict:
    """One parse, shared by the guards below, so they cannot disagree with each other."""
    registry = _event_registry()
    rows = _transition_rows()
    states = _canonical_states()
    return {"registry": registry, "rows": rows, "states": states,
            "rows_by_id": {r["id"]: r for r in rows},
            "result": _classify(rows, registry["producers_of"])}


# ------------------------------------------------------------ corpus integrity

def test_the_transition_corpus_is_positively_anchored_and_every_row_is_column_aligned():
    """G2-D5. The 134 rows are anchored by EXACT SET EQUALITY against the registered expectation -
    a count match with different members must fail - and every row's cell count must equal its
    table's header count. A row short one cell BEFORE the Event column shifts every later value and
    silently changes its classification; EF-5x was exactly that row."""
    sys.path.insert(0, str(ROOT / "eval"))
    from phase0 import manifest

    rows = require_population(_transition_rows(), "transition rows")
    keys = [r["key"] for r in rows]
    assert len(keys) == len(set(keys)), (
        f"duplicate transition keys: {sorted(k for k in set(keys) if keys.count(k) > 1)}"
    )
    expected = {f"{f.replace('.machine.md', '')}:{t}"
                for f, ids in manifest.canonical_expected()["transitions"].items() for t in ids}
    assert len(expected) == 134, f"the registered expectation drifted from 134: {len(expected)}"
    assert set(keys) == expected, (
        f"transition corpus drifted: corpus-only={sorted(set(keys) - expected)}, "
        f"registered-only={sorted(expected - set(keys))}"
    )
    misaligned = [f"{r['key']} (line {r['line']}): {r['n_cells']} cells vs {r['n_headers']} headers"
                  for r in rows if r["n_cells"] != r["n_headers"]]
    assert not misaligned, (
        "transition rows whose cell count differs from their header count - a missing cell shifts "
        "every later column and can change an Event classification silently:\n  "
        + "\n  ".join(misaligned)
    )


MINTED_2026_08_12 = {
    "AutonomousAdmissionRecorded": "PL-7a", "ApprovalFrozen": "AP-9",
    "ConflictPartyAttached": "CF-7", "ExceptionSeverityChanged": "EC-7",
    "PolicySubmitted": "PO-2", "PolicyApproved": "PO-3", "RuleExpired": "RU-8",
}


def test_the_canonical_event_registry_equals_its_registered_expectation_exactly():
    """### REPLACED, NOT WEAKENED (P5 U5.2; CLAUDE.md sec 5 rule 20). This node was
    `test_no_new_canonical_event_was_minted_and_the_total_is_still_98`, and it asserted the literal
    98 because the registry was frozen to every session below founder/architect authority. Seven
    events have now been minted BY that authority, so the literal became false and the node could only
    be deleted or re-pointed. RE-POINTED, and the invariant it actually carries is unchanged:

      * the canonical set equals the REGISTERED expectation by EXACT SET EQUALITY, so a swap at
        constant total still fails - that was always the real oracle, and the number was the
        diagnostic;
      * the seven minted names are pinned INDIVIDUALLY to the transitions they were authorized for,
        so "seven were added" cannot be satisfied by seven DIFFERENT events;
      * every other name is byte-identical to the certified predecessor's set - the mint added, and
        changed nothing.

    Deleting this node instead would have removed the only place the event corpus is bound to a
    reviewed list at all."""
    sys.path.insert(0, str(ROOT / "eval"))
    from phase0 import manifest

    registry = _event_registry()
    owned = {e["name"] for e in registry["owned"]}
    assert len(owned) == 105, f"the F1-F13 canonical event total is {len(owned)}, not 105"
    # the mint, name by name and producer by producer - not merely "seven more than before"
    for name, tid in sorted(MINTED_2026_08_12.items()):
        assert name in owned, f"{name} left the canonical corpus"
        assert registry["producers_of"].get(tid) == {name}, (
            f"{tid}'s sec-3 ownership is {registry['producers_of'].get(tid)}, not {{{name!r}}} - the "
            "authorized mint bound exactly one event to exactly one transition"
        )
    # nothing else moved: the corpus is the pre-mint 98 plus exactly these seven
    assert len(owned - set(MINTED_2026_08_12)) == 98, (
        "the canonical corpus is not the previous 98 plus the seven authorized names - something "
        f"other than the mint changed it: {sorted(owned - set(MINTED_2026_08_12))}"
    )
    assert owned == manifest.expected_event_names(), (
        "the canonical event set drifted from the registered expectation: "
        f"registry-only={sorted(owned - manifest.expected_event_names())}, "
        f"expected-only={sorted(manifest.expected_event_names() - owned)}"
    )
    security = [e["name"] for e in registry["contracts"] if e["family"] == "F14"]
    assert len(security) == 13, f"the F14 security-event count is {len(security)}, not 13"
    assert not [e for e in registry["declared"] if e["family"] == "F15" and e["producers"]], (
        "F15 declared a producer transition - it is a lens over cross-machine consumption and "
        "declares no contract (events/registry.md sec 9)"
    )


# ------------------------------------------------------------ the producer map <-> corpus bijection

def test_the_consequential_event_list_is_a_guarded_subset_of_the_canonical_corpus():
    """### F-05. events/registry.md sec 5 decides WHICH events must carry the SD-3 `entity_versions`
    set, the material-facts fingerprint, `policy_version` and `brake_version` - the pins that let a
    replay reproduce the decision context of a consequential act. Nothing in eval/ read that list, so
    a member could be struck with the entire canonical suite green.

    Three properties, all read from the LIST LINE and never from the prose beneath it:

      (1) the list is DECIDABLE and non-empty - an unparseable sec 5 fails closed rather than
          silently yielding an empty set that every subset assertion would then satisfy;
      (2) every member EXISTS in the sec-3 canonical corpus - a consequential event that is not a
          canonical event is a pin obligation attached to nothing;
      (3) the SAFETY SPINE is present. These are not a sample: each is the event that carries the
          decision context of an act with real-world consequence, and `PolicyApproved` is here
          because P5 U5.2 promoted it and the promotion was offered as the "no admin path" evidence.
          The list may GROW - a new consequential event is normal - but a member may not silently
          LEAVE."""
    consequential = require_population(_consequential_events(),
                                       "events/registry.md sec 5 CONSEQUENTIAL members")
    assert len(consequential) == len(set(consequential)), (
        f"sec 5 names an event twice: "
        f"{sorted({n for n in consequential if consequential.count(n) > 1})}"
    )
    corpus = set(_event_registry()["corpus"])
    dangling = sorted(set(consequential) - corpus)
    assert not dangling, (
        f"sec 5 declares {dangling} CONSEQUENTIAL, and sec 3 does not declare them at all - a pin "
        "obligation attached to an event that does not exist"
    )
    # FIXED-SPECIFICATION: the acts whose decision context a replay must be able to reproduce.
    spine = {"ApprovalRequested", "ApprovalGranted", "ApprovalConsumed", "CheckpointPassed",
             "EffectGranted", "GrantClaimed", "EffectAttempted", "EffectExecuted", "EffectVerified",
             "EffectFailed", "OutcomeUnknown", "RealityEstablished", "CompensationApproved",
             "CompensationStarted", "CompensationCompleted", "ClaimConfirmed", "PolicyApproved",
             "PolicyActivated", "PolicyVersionChanged", "BrakeEngaged", "BrakeReleased"}
    missing = sorted(spine - set(consequential))
    assert not missing, (
        f"### {missing} LEFT sec 5's CONSEQUENTIAL LIST. A consequential event that stops being "
        "consequential stops having to pin the SD-3 entity_versions set, the material-facts "
        "fingerprint, policy_version and brake_version - so a replay can no longer reproduce the "
        "decision context of the act it records. Removing one is an adjudicated act, not an edit"
    )


def test_the_producer_map_and_the_transition_corpus_are_bijective():
    """G2-D11. The sec-3 map, the corpus and the classification form ONE relation, asserted in both
    directions. Zero-owner and duplicate-owner are separate prohibitions, both fail-closed."""
    g2 = _g2_state()
    registry, rows = g2["registry"], g2["rows"]
    owned = require_population(registry["owned"], "canonical event contracts")
    corpus_ids = {r["id"] for r in rows}

    # zero-owner prohibition: every canonical event has at least one producer, and it exists.
    orphans = [e["name"] for e in owned if not e["producers"]]
    assert not orphans, f"canonical events with NO declared producer transition: {sorted(orphans)}"
    dangling = sorted({tid for e in owned for tid in e["producers"]} - corpus_ids)
    assert not dangling, (
        f"declared producer transition(s) that do not exist in the 134-row corpus: {dangling}"
    )

    # duplicate-owner prohibition: declared once, and (unless a declared coordination event) the
    # producers all belong to ONE machine - registry sec 182, "no event is emitted by two
    # incompatible transitions".
    names = [e["name"] for e in owned]
    assert len(names) == len(set(names)), (
        f"canonical event(s) declared more than once: "
        f"{sorted(n for n in set(names) if names.count(n) > 1)}"
    )
    spanning = [(e["name"], e["producers"]) for e in owned
                if not e["coordination"] and len({p.split("-")[0] for p in e["producers"]}) > 1]
    assert not spanning, (
        "non-coordination event(s) whose producers span more than one machine - only the declared "
        f"coordination events may do that: {spanning}"
    )
    declared_coordination = {e["name"] for e in registry["contracts"] if e["coordination"]}
    assert declared_coordination == COORDINATION_EVENTS, (
        f"the declared coordination-event set drifted: {sorted(declared_coordination)}"
    )

    # reverse direction: every producer row must still NAME a canonical event in its Event cell, so
    # a producer cannot go silent in the specification the map is derived from. EF-3 was silent -
    # it documented the event it does NOT emit and omitted the one it owns (G2-D14).
    corpus_names = set(registry["corpus"])
    silent = []
    for tid in sorted(registry["producers_of"]):
        cell = g2["rows_by_id"][tid]["event"]
        if not [n for n in re.findall(r"`([A-Za-z][A-Za-z0-9]*)", cell) if n in corpus_names]:
            silent.append(f"{g2['rows_by_id'][tid]['key']}: {cell[:70]!r}")
    assert not silent, (
        "declared producer transition(s) naming no canonical event in their Event cell:\n  "
        + "\n  ".join(silent)
    )


def test_ef_3_is_a_producer_of_the_existing_effect_executed_event():
    """G2-D2 / G2-D14, pinned by name. Two independent authorities already assign the event -
    events/registry.md sec 3 `EffectExecuted`(EF-3) and 03-external-effect-grant-events.md - so
    this needed NO new event type and NO naming discretion. The old cell was true about
    EffectAttempted and silently omitted the event the row owns; a second EffectAttempted would be
    a Sev-0 orphan (M3 sec 19/38), which is an argument against duplicating ONE event, not against
    emitting the row's own."""
    registry = _event_registry()
    assert registry["producers_of"].get("EF-3") == {"EffectExecuted"}, (
        f"EF-3's sec-3 ownership drifted: {registry['producers_of'].get('EF-3')}"
    )
    cell = _g2_state()["rows_by_id"]["EF-3"]["event"]
    assert "`EffectExecuted`" in cell, f"EF-3 no longer names EffectExecuted: {cell!r}"
    family = read(SPECS / "events" / "03-external-effect-grant-events.md")
    assert "EffectExecuted" in family and "EF-3" in family, (
        "the M3 event family file no longer corroborates the EffectExecuted/EF-3 assignment"
    )
    # PL-10 (M2) names EffectExecuted but does NOT own it - it consumes the co-transition.
    assert "EF-3" not in read(IMPL / "TRANSITION-EVENT-AUDIT.yaml").split("EVENT_REQUIRED")[1].split("CONSUMES")[0], (
        "EF-3 is recorded as an open event obligation - it is a producer with an existing event"
    )


# ------------------------------------------------------------ classification, fail-closed

def test_every_transition_is_classified_and_unknown_classification_is_a_failure():
    """G2-D1. The old classifier assigned rows to EVENTED through an `else` branch that never
    checked the cell named a canonical event. Here every row resolves to a member of a CLOSED
    vocabulary or the build fails."""
    g2 = _g2_state()
    assert not g2["result"]["errors"], (
        "unclassified or malformed transition rows:\n  " + "\n  ".join(g2["result"]["errors"])
    )
    classified = require_population(g2["result"]["classified"], "classified transitions")
    assert len(classified) == 134, f"only {len(classified)} of 134 rows classified"
    # Every class in the closed vocabulary is counted, INCLUDING the ones with zero members. A dict
    # built only from observed classes silently drops an emptied class, and "the key is absent" would
    # then compare equal to nothing at all - which is how an emptied class stops being asserted.
    counts: dict[str, int] = {c: 0 for c in ("PRODUCER", *CLASS_TOKENS)}
    for rec in classified.values():
        counts[rec["class"]] = counts.get(rec["class"], 0) + 1
    audit = _audit()
    assert counts == audit["computed_classification"], (
        f"the audit's classification drifted from the specification: computed={counts}, "
        f"recorded={audit['computed_classification']}"
    )
    assert sum(counts.values()) == audit["meta"]["total_transitions"] == 134


def test_non_producing_rows_are_structurally_declared_and_perform_zero_durable_writes():
    """A NON_PRODUCING row that declares a durable write FAILS. Prose never establishes
    non-production: 'no state change' is not a classification token and carries no weight."""
    g2 = _g2_state()
    marked = require_population(
        {k: v for k, v in g2["result"]["classified"].items() if v["class"] == "NON_PRODUCING"},
        "NON_PRODUCING transitions",
    )
    offenders = []
    for key, rec in sorted(marked.items()):
        if rec["arg"] not in NON_PRODUCING_REASONS:
            offenders.append(f"{key}: reason code {rec['arg']!r} is outside the closed set "
                             f"{sorted(NON_PRODUCING_REASONS)}")
        if _durable_write(rec["row"], g2["states"]):
            offenders.append(
                f"{key}: declared NON_PRODUCING but performs a durable write "
                f"(From->To {rec['row']['from_to'][:40]!r}, Writes {rec['row']['writes'][:40]!r})"
            )
    assert not offenders, "invalid NON_PRODUCING declarations:\n  " + "\n  ".join(offenders)
    recorded = {m["key"]: m["reason_code"]
                for c in _audit()["classes"] if c["name"] == "NON_PRODUCING" for m in c["members"]}
    assert {k: v["arg"] for k, v in marked.items()} == recorded, (
        f"the audit's NON_PRODUCING members drifted: computed={ {k: v['arg'] for k, v in marked.items()} }, "
        f"recorded={recorded}"
    )


def test_delegation_resolves_to_exactly_one_owner_per_target_state():
    """G2-D3. Every target must exist, be a producer, and itself transition to the state it is
    delegated for; every branch must resolve to EXACTLY ONE event; and the declared states must
    cover the delegating row's own To set exactly - no branch may be silently dropped."""
    g2 = _g2_state()
    marked = require_population(
        {k: v for k, v in g2["result"]["classified"].items() if v["class"] == "DELEGATES_TO"},
        "DELEGATES_TO transitions",
    )
    offenders = []
    for key, rec in sorted(marked.items()):
        got = _resolve_delegation(rec["row"], rec["arg"], g2["rows_by_id"],
                                  g2["registry"]["producers_of"], g2["states"])
        offenders += [f"{key}: {e}" for e in got["errors"]]
        own_to = _states_in(rec["row"]["from_to"].split("→", 1)[-1], g2["states"])
        if set(got["resolution"]) != own_to:
            offenders.append(
                f"{key}: declared branches {sorted(got['resolution'])} do not cover its own To set "
                f"{sorted(own_to)} exactly"
            )
    assert not offenders, "invalid DELEGATES_TO declarations:\n  " + "\n  ".join(offenders)
    recorded = {m["key"]: {s: b["owner_event"] for s, b in m["resolution"].items()}
                for c in _audit()["classes"] if c["name"] == "DELEGATES_TO" for m in c["members"]}
    computed = {k: _resolve_delegation(v["row"], v["arg"], g2["rows_by_id"],
                                       g2["registry"]["producers_of"], g2["states"])["resolution"]
                for k, v in marked.items()}
    assert computed == recorded, f"delegation ownership drifted: {computed} vs {recorded}"
    # the positional reading is gone from the corpus, not merely unused
    for f in sorted(MACHINES.glob("*.machine.md")):
        assert "respectively" not in f.read_text(encoding="utf-8"), (
            f"{f.name} resolves delegation positionally again ('respectively') - WI-14 has four "
            "target states and five references, so positional matching cannot decide it"
        )


def test_consuming_rows_name_an_event_owned_by_a_different_transition():
    """The two NECESSARY-BUT-NOT-SUFFICIENT properties: the consumed event exists, and the consuming
    row is not its own sec-3 producer.

    ### THESE TWO WERE THE WHOLE OF THE REJECTED CANDIDATE'S PROOF, AND THEY ARE NOT ENOUGH. They
    are kept here as the cheap membership check; the RELATIONSHIP is proven by
    test_consuming_rows_prove_an_authoritative_co_transition_relationship, which is what makes the
    class non-self-certifying. Neither node may be deleted without the other."""
    g2 = _g2_state()
    marked = require_population(
        {k: v for k, v in g2["result"]["classified"].items() if v["class"] == "CONSUMES"},
        "CONSUMES transitions",
    )
    corpus = set(g2["registry"]["corpus"])
    offenders = []
    for key, rec in sorted(marked.items()):
        names = [n for n in rec["arg"].split(",") if n]
        if not names:
            offenders.append(f"{key}: CONSUMES names no event")
        for name in names:
            if name not in corpus:
                offenders.append(f"{key}: consumes {name!r}, which is not a canonical event")
            elif name in g2["registry"]["producers_of"].get(rec["row"]["id"], set()):
                offenders.append(f"{key}: declares it CONSUMES {name}, which it actually OWNS")
    assert not offenders, "invalid CONSUMES declarations:\n  " + "\n  ".join(offenders)
    recorded = {m["key"]: m["consumes"]
                for c in _audit()["classes"] if c["name"] == "CONSUMES" for m in c["members"]}
    computed = {k: [n for n in v["arg"].split(",") if n] for k, v in marked.items()}
    assert computed == recorded, f"the audit's CONSUMES members drifted: {computed} vs {recorded}"


def test_consuming_rows_prove_an_authoritative_co_transition_relationship():
    """### CONSUMES-VALID. The finding the targeted adjudication of 38b4bda upheld and strengthened.

    A durable-writing consumer must stand in a relationship the repository's own STRUCTURED
    authority proves: a bidirectionally declared co-commit with the sec-3 owner's machine, on a
    DIFFERENT machine, NOT mutually exclusive with it, and with every persisted field carried by a
    consumed event's sec-5 payload. Nothing here reads prose, a narrative co-transition section, an
    event family, a target state, or a name resemblance - all of which the adjudication ruled
    insufficient by name.

    The owner and the owner's machine are additionally pinned INTO the audit record, so a reviewer
    reads the same relationship the guard computed rather than the builder's assertion about it."""
    g2 = _g2_state()
    ctx = _consumes_context(g2)
    require_population(ctx["payloads"], "sec-5 event payload declarations")
    marked = require_population(
        {k: v for k, v in g2["result"]["classified"].items() if v["class"] == "CONSUMES"},
        "CONSUMES transitions",
    )
    # every machine file resolves to a machine number, or 4(c) would silently compare None to None
    unnumbered = sorted({r["machine"] for r in g2["rows"] if _machine_number(r["machine"]) is None})
    assert not unnumbered, f"machine files with no resolvable machine number: {unnumbered}"

    offenders: list[str] = []
    for key, rec in sorted(marked.items()):
        offenders += _consumes_relationship_errors(
            rec["row"], [n for n in rec["arg"].split(",") if n], ctx)
    assert not offenders, (
        "CONSUMES declarations that do not prove an authoritative co-transition relationship:\n  "
        + "\n  ".join(offenders)
    )

    recorded = {m["key"]: m for c in _audit()["classes"] if c["name"] == "CONSUMES"
                for m in c["members"]}
    assert set(recorded) == set(marked), (
        f"CONSUMES membership drifted: computed-only={sorted(set(marked) - set(recorded))}, "
        f"audit-only={sorted(set(recorded) - set(marked))}"
    )
    for key, rec in sorted(marked.items()):
        names = [n for n in rec["arg"].split(",") if n]
        owners = sorted({o for n in names for o in ctx["owners_of"].get(n, [])})
        machines = sorted({f"M{_machine_number(ctx['rows_by_id'][o]['machine'])}" for o in owners})
        entry = recorded[key]
        assert sorted(entry["owner"]) == owners, (
            f"{key}: the audit records owner {sorted(entry['owner'])} but sec 3 declares {owners}"
        )
        assert sorted(entry["owner_machine"]) == machines, (
            f"{key}: the audit records owner_machine {sorted(entry['owner_machine'])} but the "
            f"owning rows live on {machines}"
        )
        assert entry["durable_write"] is _durable_write(rec["row"], g2["states"]), (
            f"{key}: the audit records durable_write={entry['durable_write']!r}, which the "
            "structured columns contradict"
        )


def test_every_durable_write_is_recorded_by_an_event_or_a_registered_open_obligation():
    """GR-2's converse. The G2 adjudication sec G states it verbatim as:

        "Every transition performing a durable write is a sec-3 producer of >=1 event OR carries a
         valid DELEGATES_TO. No third option."

    The targeted adjudication of 38b4bda ruled (its sec 1, answer B) that this enumerates the ways a
    durable write may ACQUIRE AN EVENT, not a closed list of classification labels - because the same
    document's sec D certifies the co-transition rows as correct architecture, and a reading that
    makes an adjudication contradict itself is not its meaning. A consumer therefore discharges GR-2
    only when its acquisition of the owner's event is PROVEN by CONSUMES-VALID; a CONSUMES row that
    fails that contract discharges NOTHING here. EVENT_REQUIRED is a RECORDED OPEN VIOLATION, never
    a discharge."""
    g2 = _g2_state()
    ctx = _consumes_context(g2)
    classified = require_population(g2["result"]["classified"], "classified transitions")
    durable = require_population(
        [k for k, v in classified.items() if _durable_write(v["row"], g2["states"])],
        "durable-writing transitions",
    )
    discharged, unrecorded = [], []
    for key in sorted(durable):
        rec = classified[key]
        if rec["class"] in ("PRODUCER", "DELEGATES_TO"):
            discharged.append(key)
        elif rec["class"] == "CONSUMES":
            errors = _consumes_relationship_errors(
                rec["row"], [n for n in rec["arg"].split(",") if n], ctx)
            (unrecorded if errors else discharged).append(key)
        elif rec["class"] != "EVENT_REQUIRED":
            unrecorded.append(key)
    require_population(discharged, "durable writes discharged by a proven event acquisition")
    assert not unrecorded, (
        "durable writes that acquire no event and carry no registered obligation - a CONSUMES row "
        f"appears here when its co-transition relationship is not proven: {unrecorded}"
    )
    open_rows = sorted(k for k in durable if classified[k]["class"] == "EVENT_REQUIRED")
    recorded = sorted(m for c in _audit()["classes"] if c["name"] == "EVENT_REQUIRED"
                      for m in c["members"])
    assert open_rows == recorded, (
        f"the open GR-2 violations drifted: computed={open_rows}, recorded={recorded}"
    )


def _recorded_discharges(audit: dict) -> dict[str, dict]:
    """The transitions the audit records as DISCHARGED, keyed by transition. A claim, not a proof -
    `_discharge_route_errors` must first find each (row, event) pair in the guard's founder
    authorization table, and only then corroborates it against events/registry.md sec 3."""
    record = audit.get("frozen_event_required_set") or {}
    return {str(e.get("transition", "")): e for e in (record.get("discharges") or [])}


def _g2_status_errors(audit: dict) -> list[str]:
    """### THE FAIL-CLOSED STATUS PREDICATE, extracted so it can be attacked over a MUTATED audit.

    Held as a predicate rather than as three literal assertions because the property is
    CONDITIONAL - "no discharged status value WHILE an obligation is open" - and a literal assertion
    can only ever describe whichever side of the condition the corpus happens to be on today. The
    hostile node feeds it a synthetic open obligation and requires it to bite.
    """
    errors: list[str] = []
    meta = audit["meta"]
    obligations = audit["founder_gated_event_obligations"] or []
    if not obligations:
        return ["the founder-gated obligation register is EMPTY - discharged obligations are "
                "RETAINED with their discharge recorded, never deleted; an empty register means the "
                "history of the finding was erased, which is a build failure and not tidying"]
    open_ids = [o["id"] for o in obligations if str(o.get("status", "OPEN")).upper() != "DISCHARGED"]
    if meta.get("discharged_status_value_forbidden_while_obligations_open") is not True:
        errors.append("the audit no longer asserts that a discharged status is forbidden while "
                      "obligations are open - the fail-closed rule cannot be switched off")
    if meta.get("open_founder_gated_obligations") != len(open_ids):
        errors.append(
            f"meta.open_founder_gated_obligations={meta.get('open_founder_gated_obligations')!r} "
            f"but {len(open_ids)} obligation(s) carry a non-DISCHARGED status: {sorted(open_ids)}"
        )
    if meta.get("discharged_founder_gated_obligations") != len(obligations) - len(open_ids):
        errors.append("meta.discharged_founder_gated_obligations disagrees with the register")
    if meta.get("total_founder_gated_obligations") != len(obligations):
        errors.append("meta.total_founder_gated_obligations disagrees with the register - the "
                      "retained history and the count of it must not drift apart")
    status = str(meta.get("status", ""))
    if open_ids and "DISCHARGED" in status and "PARTIALLY" not in status:
        errors.append(
            f"### G2 records status {status!r} while {len(open_ids)} founder-gated obligation(s) "
            f"are OPEN: {sorted(open_ids)}. A discharged status value may not be set while any "
            "obligation is open - that is the whole fail-closed rule"
        )
    return errors


def test_the_founder_gated_event_obligations_are_explicit_and_cannot_be_silently_discharged():
    """The seven durable writes no canonical event recorded. Each carries a registered obligation id
    that is NOT an event-shaped name and is NOT in the canonical corpus - a placeholder masquerading
    as a canonical event name is exactly what the founder/architect boundary forbids.

    ### REPLACED, NOT WEAKENED (P5 U5.2). All seven are now DISCHARGED by minted canonical events
    under founder/architect authority, so the old "spec EVENT_REQUIRED ids == registered obligation
    ids" equality would now read `{} == {}` and pass over nothing. The equality is kept for the OPEN
    obligations, where it is what it always was, and a second, equally exact equality is added for the
    DISCHARGED ones: each must be absent from the specs, must name the event that discharged it, and
    that discharge must be recorded in `frozen_event_required_set.discharges` and re-proven there.

    ### THE REGISTER ITSELF MAY NOT SHRINK. A discharged obligation stays, with its
    `semantic_obligation` and `why_it_matters` intact. Deleting one erases the record of what was
    wrong, which is exactly how a repaired defect regresses unnoticed."""
    g2 = _g2_state()
    audit = _audit()
    obligations = require_population(audit["founder_gated_event_obligations"],
                                     "founder-gated event obligations")
    by_id = {o["id"]: o for o in obligations}
    corpus = set(g2["registry"]["corpus"])
    marked = {k: v for k, v in g2["result"]["classified"].items() if v["class"] == "EVENT_REQUIRED"}
    discharges = _recorded_discharges(audit)

    open_ids = {o["id"] for o in obligations if str(o.get("status", "OPEN")).upper() != "DISCHARGED"}
    assert {v["arg"] for v in marked.values()} == open_ids, (
        f"obligation ids carried by EVENT_REQUIRED rows {sorted(v['arg'] for v in marked.values())} "
        f"do not match the OPEN registered obligations {sorted(open_ids)}"
    )
    offenders = []
    for oid, obligation in sorted(by_id.items()):
        if oid in corpus or re.fullmatch(r"[A-Z][A-Za-z0-9]*", oid):
            offenders.append(f"{oid}: reads as a canonical event NAME - obligations record the "
                             "missing fact, they never mint a name")
        for field in ("transition", "durable_write", "semantic_obligation", "decision_required"):
            if not str(obligation.get(field, "")).strip():
                offenders.append(f"{oid}: missing {field} - the gated decision must stay explicit, "
                                 "discharged or not")
        transition, discharged = obligation["transition"], oid not in open_ids
        if not discharged and transition not in marked:
            offenders.append(f"{oid}: names {transition}, which is not EVENT_REQUIRED")
        if discharged:
            if transition in marked:
                offenders.append(f"{oid}: recorded DISCHARGED while {transition} is still "
                                 "EVENT_REQUIRED in the specification")
            event = str(obligation.get("discharging_event", ""))
            if event not in corpus:
                offenders.append(f"{oid}: names discharging_event {event!r}, which is not a "
                                 "canonical event - a discharge may not point at a name that does "
                                 "not exist")
            entry = discharges.get(transition)
            if not entry:
                offenders.append(f"{oid}: recorded DISCHARGED with no entry in "
                                 "frozen_event_required_set.discharges - the two records must agree, "
                                 "and the discharge record is the one that gets re-proven")
            elif str(entry.get("event", "")) != event:
                offenders.append(f"{oid}: the obligation names {event!r} and its discharge record "
                                 f"names {entry.get('event')!r}")
            elif str(entry.get("route", "")) != str(obligation.get("discharge_route", "")):
                offenders.append(f"{oid}: obligation route and discharge route disagree")
            if not str(obligation.get("discharge_authority", "")).strip():
                offenders.append(f"{oid}: discharged with no authority cited")
    assert not offenders, "invalid founder-gated obligations:\n  " + "\n  ".join(offenders)

    assert not _g2_status_errors(audit), (
        "the G2 status record is not fail-closed:\n  " + "\n  ".join(_g2_status_errors(audit))
    )
    assert audit["meta"]["canonical_events_F1_F13"] == len(
        {e["name"] for e in g2["registry"]["owned"]}
    ), "the audit's canonical event total disagrees with events/registry.md sec 3"


def test_the_event_required_set_is_frozen_by_identity_and_never_by_count():
    """### THE SET, NOT THE COUNT. The companion to the node above, and the reason PL-7a can no
    longer vanish.

    The guard above proves the specs and the obligation registry AGREE with each other. It cannot
    prove either is TRUE, and a coordinated edit satisfies both while removing a member - which is
    exactly what happened: open_founder_gated_obligations went 7 -> 6 unchallenged. This node binds
    the population to the ADJUDICATED SEVEN by exact set equality, reads the frozen record from a
    named, dated, adjudication-attributed record in the audit, and requires any departure to carry a
    discharge whose route is then RE-PROVEN from structured data.

    ### AMENDED (R3-B), AND THE ANCHOR IS UNMOVED. The previous form asserted
    `computed == ADJUDICATED_EVENT_REQUIRED == registered` UNCONDITIONALLY. That made BOTH authorized
    discharge routes dead code: no discharge of any kind could ever pass, however properly recorded
    and however completely re-proven, so the routes the adjudication defined could never be used and
    the audit's own `authorized_discharge_routes` were decorative. The amendment is precisely scoped:

        computed == ADJUDICATED_EVENT_REQUIRED - {re-proven recorded discharges}

    ### `ADJUDICATED_EVENT_REQUIRED` IS STILL THE ANCHOR AND IS STILL LITERAL. It is not recomputed,
    not read from the audit, and not reduced by anything the audit says on its own: a member leaves
    ONLY by a discharge that `_event_required_set_errors` has already RE-PROVEN from
    events/registry.md sec 3 in the assertion above this one - which runs FIRST, so no subtraction
    happens until every claimed discharge has survived its own re-derivation. A row that simply
    disappears from the specs still trips "LEFT EVENT_REQUIRED WITH NO RECORDED DISCHARGE", and a row
    that JOINS still trips the converse. The unlocked route is the authorized one; nothing else moved.

    The count is asserted last, and only as a CONSEQUENCE of the membership."""
    g2 = _g2_state()
    audit = _audit()
    ctx = _consumes_context(g2)

    # (1) every recorded discharge is RE-PROVEN here, and a silent departure is still a failure.
    errors = _event_required_set_errors(g2["result"]["classified"], audit, ctx, g2["states"])
    assert not errors, "the frozen EVENT_REQUIRED set is not intact:\n  " + "\n  ".join(errors)

    # (2) the anchor, minus only what (1) just re-proved. Discharges are read from the record, but
    #     the record buys nothing that (1) has not already independently verified.
    discharged = set(_recorded_discharges(audit))
    assert discharged <= set(ADJUDICATED_EVENT_REQUIRED), (
        f"a discharge names a transition that was never in the adjudicated set: "
        f"{sorted(discharged - set(ADJUDICATED_EVENT_REQUIRED))}"
    )
    expected_open = set(ADJUDICATED_EVENT_REQUIRED) - discharged
    computed = {k for k, v in g2["result"]["classified"].items() if v["class"] == "EVENT_REQUIRED"}
    registered_open = {str(o["transition"]) for o in audit["founder_gated_event_obligations"]
                       if str(o.get("status", "OPEN")).upper() != "DISCHARGED"}
    assert computed == expected_open == registered_open, (
        f"three-way set identity broke: computed={sorted(computed)}, "
        f"anchored-minus-discharged={sorted(expected_open)}, registered-open={sorted(registered_open)}"
    )

    # (3) the register still holds ALL SEVEN, discharged or not. The anchor may not be shrunk by
    #     deleting the history of a member that left it.
    assert {str(o["transition"]) for o in audit["founder_gated_event_obligations"]} == set(
        ADJUDICATED_EVENT_REQUIRED
    ), (
        "the obligation register no longer covers the adjudicated seven. A DISCHARGED obligation is "
        "RETAINED, with its semantic_obligation and why_it_matters intact - deleting it erases the "
        "record of what was wrong, which is how a repaired defect regresses unnoticed"
    )
    assert len(computed) == audit["meta"]["open_founder_gated_obligations"]
    assert len(discharged) == audit["meta"]["discharged_founder_gated_obligations"]


# ------------------------------------------------------------ audit + control-document truthfulness

def test_transition_event_audit_matches_the_specs():
    """The audit's exact members must equal a fresh mechanical computation - exact SETS, so a
    same-count substitution fails, and a spec edit that changes any class fails until the audit is
    re-derived. G2-D12: the retired 121/13 pair may be recorded as history, never as the finding."""
    g2 = _g2_state()
    audit = _audit()
    assert not g2["result"]["errors"], g2["result"]["errors"]
    computed = {}
    for key, rec in g2["result"]["classified"].items():
        computed.setdefault(rec["class"], set()).add(key)
    assert sum(len(v) for v in computed.values()) == audit["meta"]["total_transitions"] == 134
    recorded_classes = {c["name"]: c for c in audit["classes"]}
    for name in ("NON_PRODUCING", "DELEGATES_TO", "CONSUMES"):
        members = require_population(recorded_classes.get(name, {}).get("members"),
                                     f"audit class {name}")
        keys = {m if isinstance(m, str) else m["key"] for m in members}
        assert computed.get(name, set()) == keys, (
            f"class {name} drifted: computed-only={sorted(computed.get(name, set()) - keys)}, "
            f"audit-only={sorted(keys - computed.get(name, set()))}"
        )
    # ### EVENT_REQUIRED IS HANDLED SEPARATELY BECAUSE IT IS LEGITIMATELY EMPTY, and an empty class
    # must not be waved through by a require_population() that would refuse it. Its emptiness is
    # asserted against the SPECIFICATION, and the seven that left are asserted against the frozen
    # anchor - so "empty" here is a proven claim about a known population, not an unmeasured one.
    er = recorded_classes["EVENT_REQUIRED"]
    assert computed.get("EVENT_REQUIRED", set()) == {m if isinstance(m, str) else m["key"]
                                                     for m in (er.get("members") or [])}, (
        "the audit's EVENT_REQUIRED members drifted from the specification"
    )
    assert {m["key"] for m in (er.get("discharged_members") or [])} == set(
        ADJUDICATED_EVENT_REQUIRED
    ) - computed.get("EVENT_REQUIRED", set()), (
        "the audit's discharged_members list does not account for exactly the adjudicated members "
        "that are no longer EVENT_REQUIRED"
    )
    view = audit["producer_view"]
    assert view["producer_transitions"] == len(computed["PRODUCER"]) == 117
    assert view["non_producer_transitions"] == 134 - len(computed["PRODUCER"]) == 17
    assert view["events_with_zero_producers"] == 0
    assert view["declared_producers_absent_from_the_corpus"] == 0
    # the historical measurement stays labelled historical and is not restated as current truth
    found = audit["adjudicated_as_found"]
    assert (found["transitions_naming_a_canonical_event"],
            found["transitions_not_naming_a_canonical_event"]) == (120, 14)
    assert "HISTORICAL" in found["note"], "the as-found split lost its historical label"
    retired = {str(r["figure"]) for r in audit["retired_figures"]}
    assert {"24", "121 / 13"} <= retired, f"a retired figure left the record: {sorted(retired)}"


# Whether a document is classified AT ALL is discovered dynamically, by
# test_every_implementation_document_is_classified_or_family_covered. Which documents have their G2
# claims POLICED is a different and adjudicated question:
#
# FIXED-SPECIFICATION: the G2 targeted architecture adjudication sec E named EXACTLY these five
# documents as the anti-drift population for the retired transition/event figures, and its successor
# adjudication reaffirmed that scope when it upheld F-02 against PHASE-OUTPUTS.md. An ADJUDICATED
# SCOPE, not a discovered population: a new markdown file does not silently join it, and dropping
# one of these five is a real defect rather than housekeeping.
CONTROL_POPULATION = ("CLAUDE.md", "README.md", "ARCHITECTURE.md",
                      "docs/implementation/CURRENT.md", "docs/implementation/PHASE-OUTPUTS.md")


def _enclosing_sentence(text: str, start: int, end: int) -> str:
    """The sentence a match sits in, bounded by `.` or a newline. Used INSTEAD of a character window
    for the retired-label carve-out - see the docstring below for why the window was a defect."""
    left = max(text.rfind(".", 0, start), text.rfind("\n", 0, start)) + 1
    right = min((i for i in (text.find(".", end), text.find("\n", end)) if i != -1),
                default=len(text))
    return text[left:right]


def test_the_retired_24_figure_does_not_reappear_in_control_documents():
    """G2-D7. The old figure was never mechanically computed. Naming it as RETIRED is allowed;
    citing it as the finding's count is not.

    THE CARVE-OUT, AND WHY IT IS NOT A DODGE. The G2 adjudication computed that exactly 24 of the
    134 rows are NOT producer transitions. That is a DIFFERENT quantity from the retired count of
    transitions naming no event, and it happens to share a value. Without a carve-out a TRUE
    sentence would trip the guard, and the only ways out would be to contort the phrasing or to
    stop stating the truth - both evidence-hiding.

    ### F-03: THE CARVE-OUT'S FIRST FORM WAS ITSELF THE DEFECT, and it was a defect in a guard this
    unit introduced. It keyed on `non-producer` appearing anywhere in a +/-120 CHARACTER WINDOW, so
    appending one clause to a false sentence bought amnesty for it:

        "24 of the 134 transitions name no event outright, which is the non-producer population."
        -> GUARD BYPASSED, suite green.

    A proximity window is exactly the prose-proximity predicate the G2 adjudication sec F refused for
    classification, and it is no more defensible for anti-drift. The carve-out is now scoped to
    MEANING, structurally: `24` and `non-producer` must fall inside the SAME CLAUSE, and the
    retired-label carve-out inside the SAME SENTENCE. test_hostile_the_retired_24_carve_out_cannot_be
    _bought_with_a_trailing_clause asserts the sentence above FAILS."""
    offenders = []
    for rel in CONTROL_POPULATION:
        text = read(ROOT / rel)
        offenders += [f"{rel}: {hit!r}" for hit in _retired_24_offenders(text)]
    assert not offenders, f"the uncomputed '24' figure is back as a live count: {offenders}"


def _retired_24_offenders(text: str) -> list[str]:
    """Shared by the guard and its hostile node, so the attack is judged by the same predicate."""
    offenders = []
    for m in re.finditer(r"\b24\b(?![0-9])[^.\n]{0,50}(transitions?|event)", text):
        clause = m.group(0)
        # the computed non-producer count - a different quantity (G2-D7). SAME CLAUSE, not a window:
        # the two tokens must belong to one statement, which is what makes the sentence be ABOUT
        # non-producers rather than merely mention them somewhere nearby.
        if re.search(r"\b24\b(?![0-9])[^.\n]{0,40}(?:non-producer|not producer transitions)",
                     clause, re.I):
            continue
        if re.search(r"retired|never mechanically",
                     _enclosing_sentence(text, m.start(), m.end()), re.I):
            continue
        offenders.append(clause)
    return offenders


def test_a_retired_g2_status_token_never_appears_as_a_live_claim():
    """F-02. A retired STATUS TOKEN is not a retired FIGURE, and the two anti-drift guards either
    side of this one caught neither.

    `PHASE-OUTPUTS.md`'s P5 "Blocked on" row told every future agent that the transition/event
    finding "must be adjudicated first - COUNT NEEDS ADJUDICATION, 4 classes" - and G2 HAD BEEN
    ADJUDICATED, at 6e8127d, by the very adjudication that authorized this unit. Three falsehoods in
    one IMPLEMENTATION_CONTROL row: the adjudication had happened, the vocabulary is five classes not
    four, and `COUNT NEEDS ADJUDICATION` is a status value this unit's own commit retired. It read as
    a live block on work already done, and it hid the real block - founder/architect event naming.

    The forbidden tokens are read from the audit's own `retired_status_tokens` record rather than
    hard-coded here, so retiring a token registers its own guard. HISTORICAL EVIDENCE DOCUMENTS ARE
    NOT IN SCOPE: `p4-r07-closure-handoff.md` and the `u-handoff-*` reviews carry these tokens truly,
    as of their own commits, and erasing them would be evidence-hiding."""
    tokens = require_population(_audit().get("retired_status_tokens"), "retired status tokens")
    for entry in tokens:
        assert str(entry.get("superseded_by", "")).strip(), (
            f"retired status token {str(entry['token'])!r} records no superseding value - a "
            "retirement with no replacement tells a reader nothing"
        )
    offenders = []
    for rel in CONTROL_POPULATION:
        offenders += [f"{rel}: {hit}" for hit in _retired_token_offenders(read(ROOT / rel), tokens)]
    assert not offenders, (
        "a RETIRED G2 status token is stated as a live claim in a control document - it directs an "
        "agent to redo settled work and conceals the real block:\n  " + "\n  ".join(offenders)
    )


def _retired_token_offenders(text: str, tokens: list[dict]) -> list[str]:
    """Shared by the guard and its hostile node. A token whose ENCLOSING SENTENCE marks it retired,
    superseded or historical is allowed - that is how history stays readable without becoming a live
    instruction. Anything else is a live claim."""
    offenders = []
    for entry in tokens:
        token = str(entry["token"])
        pattern = re.compile(re.escape(token).replace(r"\ ", r"[ _]"), re.I)
        for m in pattern.finditer(text):
            sentence = _enclosing_sentence(text, m.start(), m.end())
            if re.search(r"retired|superseded|historical|no longer|was the|before the",
                         sentence, re.I):
                continue
            offenders.append(f"{token!r} stated live in {sentence.strip()[:100]!r}")
    return offenders


def test_the_retired_naming_split_does_not_reappear_as_the_current_finding():
    """G2-D12/G2-D13 anti-drift. '13 of 134' and '121 name an event' were the pre-adjudication
    pair; the corrected AS-FOUND split is 120/14 and the current corpus is classified, not split.
    Either figure may appear as history; neither may be restated as the live finding."""
    offenders = []
    for f in [ROOT / "CLAUDE.md", ROOT / "README.md", ROOT / "ARCHITECTURE.md",
              IMPL / "CURRENT.md", IMPL / "PHASE-OUTPUTS.md", ROOT / "docs" / "product"
              / "OPEN-VALIDATION-ITEMS.md"]:
        text = read(f)
        for m in re.finditer(r"\b(?:13|121)\b\s*(?:of\s*134|transitions)[^.\n]{0,60}", text):
            window = text[max(0, m.start() - 160): m.end() + 160]
            if re.search(r"retired|superseded|historical|as[- ]found|corrected", window, re.I):
                continue
            offenders.append(f"{f.name}: {m.group(0)[:80]!r}")
    assert not offenders, (
        "the retired 121/13 naming split is being cited as the current finding:\n  "
        + "\n  ".join(offenders)
    )


# ------------------------------------------------------------ hostile cases for each adjudicated defect

def _synthetic(tid, event, writes="—", from_to="`A_STATE` → `A_STATE`", machine="synthetic"):
    return {"key": f"{machine}:{tid}", "id": tid, "machine": machine, "line": 0,
            "n_cells": 8, "n_headers": 8, "from_to": from_to, "writes": writes, "event": event}


def test_hostile_an_unclassifiable_row_fails_rather_than_passing():
    """G2-D1's exact shape: a row whose Event cell names nothing canonical and carries no token.
    The old `else` branch called this EVENTED."""
    for cell in ("*(Exception raised)*", "—", "*(no state change)*", "as those", ""):
        result = _classify([_synthetic("ZZ-1", cell)], {})
        assert result["errors"] and not result["classified"], (
            f"Event cell {cell!r} was classified instead of failing - unknown classification must "
            "be a BUILD FAILURE, never a pass and never a skip"
        )
    ok = _classify([_synthetic("ZZ-1", "`NON_PRODUCING:ENUMERATED_NO_OP`")], {})
    assert not ok["errors"] and ok["classified"]["synthetic:ZZ-1"]["class"] == "NON_PRODUCING", (
        "the classifier rejects a well-formed declaration - the guard would be vacuous"
    )


def test_hostile_two_class_tokens_on_one_row_fail():
    result = _classify(
        [_synthetic("ZZ-2", "`NON_PRODUCING:ENUMERATED_NO_OP` `CONSUMES:WorkBlocked`")], {})
    assert result["errors"], "a row declaring two classes was accepted"


def test_hostile_a_producer_row_may_not_self_declare_a_class():
    """Producer identity is decided by events/registry.md sec 3. A row that could re-declare itself
    NON_PRODUCING would reintroduce prose-style self-certification with better syntax."""
    result = _classify([_synthetic("WI-1", "`NON_PRODUCING:ENUMERATED_NO_OP`")],
                       {"WI-1": {"WorkItemCreated"}})
    assert result["errors"], "a declared sec-3 producer was allowed to declare itself NON_PRODUCING"


def test_hostile_non_producing_with_a_durable_write_fails():
    """CF-7 and EC-7's exact defect: a row claiming silence while writing durably."""
    states = _canonical_states()
    by_field = _synthetic("ZZ-3", "`NON_PRODUCING:ENUMERATED_NO_OP`", writes="`severity`")
    by_state = _synthetic("ZZ-4", "`NON_PRODUCING:ENUMERATED_NO_OP`",
                          from_to="`DRAFT` → `PROPOSED`")
    assert _durable_write(by_field, states), "a non-empty Writes column was not read as durable"
    assert _durable_write(by_state, states), "a real state change was not read as durable"
    assert not _durable_write(_synthetic("ZZ-5", "x", from_to="`GRANTED` → `GRANTED`"), states), (
        "a same-state zero-write row was read as durable - AP-8 would be a false violation"
    )


def test_hostile_delegation_that_resolves_to_zero_or_several_owners_fails():
    """Zero-owner and duplicate-owner are separate prohibitions and both must fail closed."""
    g2 = _g2_state()
    rows_by_id, states = g2["rows_by_id"], g2["states"]
    producers = g2["registry"]["producers_of"]
    wi14 = rows_by_id["WI-14"]                       # the real delegating row, for its real Trig set

    missing = _resolve_delegation(wi14, "BLOCKED=WI-999", rows_by_id, producers, states)
    assert missing["errors"], "a delegation to a non-existent transition was accepted"

    empty = _resolve_delegation(wi14, "BLOCKED=", rows_by_id, producers, states)
    assert empty["errors"], "a delegation with zero targets was accepted"

    # AP-8 is a NON_PRODUCING row: it owns no sec-3 event, so it has nothing to delegate. (PL-7a used
    # to serve here and no longer can - it became a sec-3 producer when its event was minted, which
    # is exactly the kind of drift that turns a hostile fixture into a green no-op.)
    assert "AP-8" not in producers, "AP-8 became a producer - pick another non-producing target"
    non_producer = _resolve_delegation(wi14, "BLOCKED=AP-8", rows_by_id, producers, states)
    assert any("not a sec-3 producer" in e for e in non_producer["errors"]), (
        f"a delegation to a non-producing target was accepted: {non_producer}"
    )

    ambiguous = _resolve_delegation(wi14, "BLOCKED=WI-5,WI-7", rows_by_id, producers, states)
    assert ambiguous["errors"], (
        "a delegation resolving to two different owner events was accepted - duplicate ownership "
        "must fail closed"
    )
    wrong_state = _resolve_delegation(wi14, "CLOSED=WI-5", rows_by_id, producers, states)
    assert wrong_state["errors"], (
        "a delegation whose target does not transition to the declared state was accepted - that "
        "is positional matching wearing a target-state disguise"
    )
    good = _resolve_delegation(wi14, "BLOCKED=WI-5,WI-6", rows_by_id, producers, states)
    assert not good["errors"] and good["resolution"] == {"BLOCKED": "WorkBlocked"}, (
        f"the real WI-14 BLOCKED branch does not resolve: {good}"
    )


# ------------------------------------------------------ R3-A: the FALSE-DELEGATION predicate

def test_hostile_a_row_may_not_delegate_to_a_sibling_its_own_trigger_can_never_fire(monkeypatch):
    """### R3-A, REPRODUCED EXACTLY AND ASSERTED TO FAIL: `PL-7a -> DELEGATES_TO:CHECKPOINT=PL-7b`.

    Both rows end in `CHECKPOINT` on M2 and PL-7b is a declared sec-3 producer (`ApprovalBound`), so
    the OLD predicate - target exists, is a producer, shares the target state - accepted it in full.
    It is semantically FALSE. PL-7b's event asserts an approval BOUND BY A HUMAN to this commit_key;
    PL-7a is the autonomous-within-caps path, where no human acted at all. Delegating would have let
    the corpus's HIGHEST-GOVERNANCE row claim a human-approval event as its own record.

    ### THE REJECTION IS STRUCTURAL AND GENERAL. `Trig` is the closed code set of
    state-machines/registry.md sec 1; PL-7a is `S` and PL-7b is `H`, so `{S} n {H}` is empty. No
    PL-7a special case exists in the predicate and no prose is read - delete the trigger clause and
    this node fails, which is the only thing that makes it worth having.

    ### AND IT HOLDS INDEPENDENTLY OF THE FROZEN-SET ANCHOR - PROVEN, NOT ASSERTED (F-04). The
    candidate f01d942 wrote
    `assert empty_anchor["errors"] and not frozenset() & ADJUDICATED_EVENT_REQUIRED`, in which
    `empty_anchor` was a BYTE-IDENTICAL recomputation of `got` three lines above and the second
    conjunct is CONSTANT `True` for any anchor value, under a docstring claiming it "re-runs the
    whole delegation resolution with ADJUDICATED_EVENT_REQUIRED emptied". It did not. The property is
    TRUE - the independent review and the separate re-adjudication each verified it - so what follows
    replaces a FALSE PROOF OF A TRUE CLAIM with the two verifications that were only described:

      (i)  a real `monkeypatch.setattr` of this module's `ADJUDICATED_EVENT_REQUIRED` to
           `frozenset()`, after which the false delegation must still be refused and both declared
           branches must still resolve;
      (ii) a real AST scan of `_resolve_delegation`'s own source, asserting it names no frozen-set
           anchor at all - which is WHY (i) holds, and is the stronger of the two.

    A predicate that only works while a particular row happens to be under a separate guard is not a
    predicate at all."""
    g2 = _g2_state()
    rows_by_id, states, producers = g2["rows_by_id"], g2["states"], g2["registry"]["producers_of"]
    pl7a, pl7b = rows_by_id["PL-7a"], rows_by_id["PL-7b"]

    # ### FIXTURE PREMISES, NOT RULE GUARDS (R-06). The five assertions below state what the corpus
    # must still look like for the real assertions further down to be about anything. They fire on
    # ANY edit to PL-7a or PL-7b, including edits no rule forbids, so a mutation that trips one of
    # them has NOT been caught by a guard and MUST NOT be counted as a defence. Both prior candidates
    # inflated `remediated: N failed` counts with this class; they are marked here so nobody can.
    assert _trigger_types(pl7a) == {"S"}, f"FIXTURE PREMISE: PL-7a's Trig moved: {pl7a['trig']!r}"
    assert _trigger_types(pl7b) == {"H"}, f"FIXTURE PREMISE: PL-7b's Trig moved: {pl7b['trig']!r}"
    assert "CHECKPOINT" in _states_in(pl7b["from_to"].split("→", 1)[-1], states), "FIXTURE PREMISE"
    assert "CHECKPOINT" in _states_in(pl7a["from_to"].split("→", 1)[-1], states), "FIXTURE PREMISE"
    assert producers.get("PL-7b") == {"ApprovalBound"}, (
        "FIXTURE PREMISE: PL-7b no longer owns ApprovalBound - the false delegation would fail for "
        "a different, incidental reason and this node would stop testing R3-A"
    )

    got = _resolve_delegation(pl7a, "CHECKPOINT=PL-7b", rows_by_id, producers, states)
    joined = " ".join(got["errors"])
    assert got["errors"], (
        "### R3-A IS BACK: PL-7a delegated to PL-7b. The three old conjuncts - target exists, is a "
        "sec-3 producer, shares the target state - are ALL satisfied here, and they are not enough: "
        "the autonomous path would be recorded by an event asserting a human approval"
    )
    assert "DISJOINT TRIGGER TYPES" in joined, (
        f"the delegation failed for some other reason, so the general invariant is not the thing "
        f"doing the work: {got['errors']}"
    )
    # ### FIXTURE PREMISES, NOT RULE GUARDS (R-06). These two assert that no OTHER conjunct is doing
    # the work, i.e. that the fixture still isolates the trigger invariant. Tripping one means the
    # fixture drifted, never that a rule caught something.
    assert "does not itself transition to" not in joined, (
        "FIXTURE PREMISE: the target-state conjunct fired, which means this fixture is not isolating "
        "the trigger invariant - PL-7b does reach CHECKPOINT, and that is precisely why the old "
        "predicate passed"
    )
    assert "CROSS-MACHINE" not in joined, (
        "FIXTURE PREMISE: the same-machine conjunct fired, which means this fixture is not isolating "
        "the trigger invariant - PL-7a and PL-7b are BOTH on M2, which is exactly why same-machine "
        "ALONE is insufficient and the trigger conjunct had to be KEPT"
    )

    # ### (ii) AST SCAN - REAL, over the predicate's own source. If `_resolve_delegation` names no
    # frozen-set anchor, it CANNOT be borrowing the frozen-set guard's authority, whatever any
    # monkeypatch shows. This is the claim f01d942's commit record made and its tree did not contain.
    anchors = {"ADJUDICATED_EVENT_REQUIRED", "ADJUDICATED_UNDECLARED_ACCEPTS",
               "ADJUDICATED_DELEGATION_ADMITS", "DISCHARGE_ROUTES"}
    tree = ast.parse(textwrap.dedent(inspect.getsource(_resolve_delegation)))
    named = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
            {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | \
            {c.value for c in ast.walk(tree) if isinstance(c, ast.Constant)
             and isinstance(c.value, str)}
    assert not (named & anchors), (
        f"### `_resolve_delegation` REFERENCES A FROZEN-SET ANCHOR {sorted(named & anchors)}. Its "
        "verdict would then depend on which rows are separately adjudicated, so it would not be a "
        "general predicate over the corpus at all"
    )

    # ### (i) MONKEYPATCH - REAL. The anchor is emptied on this module for the duration of the call.
    monkeypatch.setattr(sys.modules[__name__], "ADJUDICATED_EVENT_REQUIRED", frozenset())
    assert sys.modules[__name__].ADJUDICATED_EVENT_REQUIRED == frozenset(), (
        "the monkeypatch did not take - the assertion below would be re-running the unpatched code, "
        "which is precisely the tautology this replaces"
    )
    empty_anchor = _resolve_delegation(pl7a, "CHECKPOINT=PL-7b", rows_by_id, producers, states)
    assert empty_anchor["errors"], (
        "with `ADJUDICATED_EVENT_REQUIRED` EMPTIED the false delegation is accepted - the refusal "
        "was borrowing the frozen-set guard's authority rather than deciding anything itself"
    )
    assert "DISJOINT TRIGGER TYPES" in " ".join(empty_anchor["errors"]), (
        f"with the anchor emptied it fails for a different reason: {empty_anchor['errors']}"
    )

    # POSITIVE CONTROL, ALSO UNDER THE EMPTIED ANCHOR: the two legitimate delegating rows are
    # accepted by the very same predicate, so the refusal above is not a blanket ban.
    for key, spec, expected in (
        ("WI-14", "BLOCKED=WI-5,WI-6", {"BLOCKED": "WorkBlocked"}),
        ("CF-6", "RESOLVED_BY_HUMAN=CF-4", {"RESOLVED_BY_HUMAN": "ConflictResolved"}),
    ):
        ok = _resolve_delegation(rows_by_id[key], spec, rows_by_id, producers, states)
        assert not ok["errors"] and ok["resolution"] == expected, (
            f"{key}'s real branch is rejected by the delegation predicate - it would be over-strict "
            f"and would break legitimate delegation: {ok}"
        )


def test_the_delegation_predicate_is_swept_over_the_whole_corpus_and_its_admitted_set_is_exact():
    """### THE CORPUS-WIDE SWEEP, DRIVING THE REAL PREDICATE, ASSERTING THE ADMITTED SET EXACTLY.

    ### WHAT THIS REPLACES, AND WHY (F-03). The node this supersedes recomputed the trigger clause
    INLINE and never called `_resolve_delegation` at all, so deleting the invariant from the
    predicate left it GREEN - only a single hostile node on one hand-picked pair went red. It also
    asserted zero false REJECTS and nothing whatever about false ACCEPTS, which is the inverse of the
    selection-bias correction the CONSUMES re-adjudication demanded: it measured only the half that
    could not fail. That is what let a predicate admitting 157 of 250 triples, nine of them sourced
    at the founder-gated seven, ship described as having "close[d] the false-delegation route".

    ### SO: no re-implementation. Every one of the 250 structurally-expressible triples is put
    through `_resolve_delegation` ITSELF, and four properties are asserted:

      (1) the ADMITTED set equals `ADJUDICATED_DELEGATION_ADMITS` EXACTLY, in BOTH directions.
          Deleting EITHER conjunct from the predicate makes the set grow and turns this RED
          (trigger deleted -> 96; same-machine deleted -> 157; both -> 235; the two middle figures
          were TRANSPOSED here at a6005a8 - R-03). Adding an over-strict conjunct makes it shrink
          and also turns this RED.
      (2) NOT ONE admitted triple is sourced at a member of `ADJUDICATED_EVENT_REQUIRED`. This is
          the property the founder gate depends on and it is asserted over the WHOLE corpus, not
          over the routes anybody thought to name.
      (3) zero false rejects: every branch the corpus DECLARES is admitted, ground truth being the
          declaration and never the predicate under test.
      (4) `PL-7a -> PL-7b` is INSIDE the swept population and is rejected there.

    ### WHAT THIS DOES NOT PROVE. The 51 survivors are NECESSARY CONDITIONS, not a semantic proof;
    two of them are visibly wrong and are NAMED in `ADJUDICATED_DELEGATION_ADMITS`. This node holds
    the residual EXACT so it cannot silently grow - it does not claim the residual is empty."""
    g2 = _g2_state()
    rows, states = g2["rows"], g2["states"]
    rows_by_id, producers = g2["rows_by_id"], g2["registry"]["producers_of"]
    require_population(rows, "transition rows")

    # both conjuncts must be DECIDABLE for every row, or the invariant is unenforceable somewhere
    undecidable = sorted(r["key"] for r in rows if not _trigger_types(r))
    assert not undecidable, (
        f"rows whose Trig cell yields no canonical code from state-machines/registry.md sec 1 - the "
        f"trigger invariant cannot be decided for them and they fail closed: {undecidable}"
    )
    unnumbered = sorted(r["key"] for r in rows if _machine_number(r["machine"]) is None)
    assert not unnumbered, (
        f"rows whose machine yields no machine number - the same-aggregate conjunct cannot be "
        f"decided for them and they fail closed: {unnumbered}"
    )

    # ---- the complete structurally-expressible population, judged by the REAL predicate
    expressible, admitted, rejected = [], set(), []
    for row in rows:
        row_to = _states_in(row["from_to"].split("→", 1)[-1], states)
        for tid in sorted(producers):
            if tid == row["id"]:
                continue
            target_to = _states_in(rows_by_id[tid]["from_to"].split("→", 1)[-1], states)
            for state in sorted(row_to & target_to):
                triple = (row["key"], state, tid)
                expressible.append(triple)
                got = _resolve_delegation(row, f"{state}={tid}", rows_by_id, producers, states)
                if got["errors"]:
                    rejected.append(triple)
                else:
                    admitted.add(triple)
    assert len(expressible) > 200, (
        f"only {len(expressible)} structurally-expressible delegations found - the sweep collapsed "
        "and every conclusion below would be over a population too small to mean anything"
    )
    assert len(set(expressible)) == len(expressible), "the sweep enumerated a triple twice"

    # (1) THE ADMITTED SET IS EXACT, BOTH WAYS.
    assert admitted == set(ADJUDICATED_DELEGATION_ADMITS), (
        "### THE DELEGATION PREDICATE'S ADMITTED SET MOVED.\n"
        f"  NEWLY ADMITTED (the predicate got WEAKER - a conjunct was deleted or narrowed): "
        f"{sorted(admitted - set(ADJUDICATED_DELEGATION_ADMITS))}\n"
        f"  NO LONGER ADMITTED (the predicate got STRICTER - check for false rejects first): "
        f"{sorted(set(ADJUDICATED_DELEGATION_ADMITS) - admitted)}\n"
        "  ADJUDICATED_DELEGATION_ADMITS is a MEASUREMENT of what the predicate lets through, "
        "recorded as a residual. It is not a target and it may not be edited to match a weakened "
        "predicate - re-derive WHY the population moved."
    )

    # (2) NOT ONE ADMITTED TRIPLE IS SOURCED AT A FOUNDER-GATED ROW.
    at_the_seven = sorted(t for t in admitted if t[0] in ADJUDICATED_EVENT_REQUIRED)
    assert not at_the_seven, (
        "### A FOUNDER-GATED ROW CAN DELEGATE ITS OBLIGATION AWAY. The delegation predicate admits "
        f"{at_the_seven}, each of which would let one of the adjudicated seven be 'recorded by' "
        "another row's event. This is the route that rejected f01d942, reopened."
    )

    # (3) zero false rejects, ground truth read off the corpus's own declarations
    declared = [(k, v) for k, v in g2["result"]["classified"].items() if v["class"] == "DELEGATES_TO"]
    require_population(declared, "declared DELEGATES_TO rows")
    declared_triples = set()
    for key, rec in declared:
        for branch in [b for b in rec["arg"].split(";") if b]:
            state, ids = branch.split("=", 1)
            for tid in [t for t in ids.split(",") if t]:
                declared_triples.add((key, state, tid))
    require_population(declared_triples, "declared delegation branches")
    false_rejects = sorted(declared_triples - admitted)
    assert not false_rejects, (
        f"### the corpus DECLARES {false_rejects} and the predicate refuses it. Either the predicate "
        "over-rejects - an invariant that refuses the corpus's own legitimate members is worse than "
        "the hole it closes - OR THE DECLARATION IS FORGED. ### DO NOT RELAX THE PREDICATE TO CLEAR "
        "THIS. Establish first that the delegating row and its target are the SAME AGGREGATE and are "
        "reachable by the SAME TRIGGER; a cross-machine or trigger-disjoint 'declaration' newly "
        "added to a founder-gated row is the laundering this node exists to surface, and property "
        "(2) above will be red beside it."
    )

    # (4) the false delegation is INSIDE the swept population and is rejected there
    false_route = ("02-pipeline-instance:PL-7a", "CHECKPOINT", "PL-7b")
    assert false_route in expressible, (
        "PL-7a -> PL-7b is no longer a structurally-expressible delegation, so this sweep has "
        "stopped covering the case R3-A is about"
    )
    assert false_route in set(rejected), (
        "### the delegation predicate does not reject PL-7a -> PL-7b in the corpus-wide sweep"
    )
    # and it is a REAL constraint: it excludes the large majority of the expressible population
    assert len(admitted) < len(expressible) // 2, (
        f"the predicate admits {len(admitted)} of {len(expressible)} expressible delegations - at "
        "that rate it has stopped being a constraint"
    )


def test_hostile_a_column_short_row_is_detected_rather_than_shifting_silently():
    """G2-D5. EF-5x carried 7 cells against 8 headers. The Event cell still resolved by luck; a
    cell missing BEFORE the Event column would have shifted the classification without a sound."""
    shifted = _synthetic("ZZ-6", "`CONSUMES:WorkBlocked`")
    shifted["n_cells"] = 7
    assert shifted["n_cells"] != shifted["n_headers"], "the fixture does not model the defect"
    live = [r for r in _transition_rows() if r["n_cells"] != r["n_headers"]]
    assert not live, f"a column-short row is live in the corpus again: {[r['key'] for r in live]}"


def test_hostile_the_g2_status_cannot_be_flipped_to_discharged_while_obligations_are_open():
    """The fail-closed property, ATTACKED over a mutated audit rather than described over this one.

    ### REPLACED (P5 U5.2), AND THE REPLACEMENT IS STRICTLY STRONGER. The previous form asserted
    three literals: obligations open > 0, and the status string containing DISCHARGED_FOUNDER_GATED
    and PARTIALLY. Those described the corpus of the day. All seven obligations are now discharged,
    so the literals became false - and, worse, the property they stood for ("no discharged status
    WHILE an obligation is open") was never actually exercised: the condition was true throughout, so
    the branch that matters never ran.

    This node now feeds `_g2_status_errors` a SYNTHETIC OPEN OBLIGATION beside the discharged status
    and requires it to bite, then feeds it the live audit and requires silence. The rule is proven in
    the state that makes it load-bearing, which is the state the repository is not in."""
    audit = _audit()
    live = _g2_status_errors(audit)
    assert not live, "the live G2 status record is not fail-closed:\n  " + "\n  ".join(live)

    # positive control: the mutation must actually change the OPEN population, or it tests nothing
    obligations = audit["founder_gated_event_obligations"]
    assert all(str(o.get("status", "")).upper() == "DISCHARGED" for o in obligations), (
        "not every obligation is discharged, so the mutation below would not be introducing the "
        "condition this node exists to exercise"
    )
    reopened = {**audit, "founder_gated_event_obligations": [
        {**obligations[0], "status": "OPEN"}, *obligations[1:]]}
    errors = _g2_status_errors(reopened)
    assert errors, (
        "### an OPEN founder-gated obligation coexisted with a discharged status value and nothing "
        "objected - the fail-closed rule is decorative"
    )
    assert any("are OPEN" in e for e in errors), (
        f"the mutation was caught, but not by the status rule - the count mismatch alone would fire "
        f"even for an honest recount, so it does not prove the status rule works: {errors}"
    )

    # and the rule may not be switched off by editing its own declaration
    disarmed = {**audit, "meta": {**audit["meta"],
                                  "discharged_status_value_forbidden_while_obligations_open": False}}
    assert _g2_status_errors(disarmed), "the fail-closed declaration was allowed to be turned off"

    # nor by emptying the register so that "no obligation is open" becomes vacuously true
    erased = {**audit, "founder_gated_event_obligations": []}
    assert _g2_status_errors(erased), (
        "deleting the whole obligation register was accepted - an empty register makes every "
        "'nothing is open' claim vacuously true and erases the record of the finding"
    )


# ------------------------------------------------- hostile cases for the CONSUMES relationship (F-07)
#
# The rejected candidate's hostile battery claimed "one per adjudicated defect class" and had NO node
# for CONSUMES - the one exempting class with no independent truth predicate. The targeted
# adjudication raised that omission to HIGH and merged it into F-01, because it is CAUSALLY WHY F-01
# SHIPPED: the candidate's own tooling would have caught the laundering had the battery been complete.
# These nodes are therefore not scheduled alongside the fix; they ARE its acceptance test.
#
# Every node below carries a POSITIVE CONTROL, so none can pass because it measured nothing, and each
# asserts the corpus it attacks is real - a mutation that no longer targets anything is not a proof.


def _ap9(g2: dict) -> dict:
    return g2["rows_by_id"]["AP-9"]


def test_hostile_ap_9_may_not_consume_a_mutually_exclusive_producer():
    """### VARIANT 1 of the reproduced exploit - the independent reviewer's, reproduced by the
    adjudicator: AP-9 relabelled `CONSUMES:ApprovalConsumed`.

    `ApprovalConsumed`'s sec-3 owner is AP-7 (`GRANTED`->`CONSUMED`). AP-9 is
    `GRANTED`->`GRANTED` *(frozen)*. Same machine, same From, divergent To: THEY CANNOT BOTH FIRE ON
    ONE APPROVAL, so AP-7's event records nothing about AP-9's freeze. Under the rejected guard this
    passed 42/42 G2 nodes and 2088 suite nodes. It must now fail on 4(b) AND 4(c)."""
    g2 = _g2_state()
    ctx = _consumes_context(g2)
    assert "ApprovalConsumed" in ctx["corpus"] and ctx["owners_of"]["ApprovalConsumed"] == ["AP-7"], (
        "the exploit no longer targets the real corpus - ApprovalConsumed/AP-7 moved"
    )
    errors = _consumes_relationship_errors(_ap9(g2), ["ApprovalConsumed"], ctx)
    assert errors, "AP-9 was laundered into CONSUMES by a MUTUALLY EXCLUSIVE producer"
    joined = " ".join(errors)
    assert "MUTUALLY" in joined and "OWN machine" in joined, (
        f"the laundering failed for the wrong reasons - 4(b) and 4(c) must both bite: {errors}"
    )
    # positive control: the paradigm co-transition row is accepted by the very same predicate
    pl9 = g2["rows_by_id"]["PL-9"]
    assert not _consumes_relationship_errors(pl9, ["GrantClaimed"], ctx), (
        "PL-9, the genuine declared M2<->M3 co-transition, is rejected - the guard would be vacuous"
    )


def test_hostile_ap_9_may_not_consume_a_wholly_unrelated_canonical_event():
    """### VARIANT 2 - the adjudicator's own extension, and the one that changed the finding's
    character: AP-9 relabelled `CONSUMES:BrakeReleased`, owner BR-4 (M13 Brake).

    `BrakeReleased` is a HUMAN-ONLY brake release with no machine, aggregate, family, causal or
    temporal relationship whatsoever to an M4 approval freeze. This also passed 42/42. It proved the
    class required not even same-machine, same-aggregate or same-family proximity: IT ADMITTED ANY OF
    THE 98 CANONICAL EVENTS. The missing invariant was not a refinement of a weak relational check -
    THERE WAS NO RELATIONAL CHECK AT ALL."""
    g2 = _g2_state()
    ctx = _consumes_context(g2)
    assert "BrakeReleased" in ctx["corpus"] and ctx["owners_of"]["BrakeReleased"] == ["BR-4"], (
        "the exploit no longer targets the real corpus - BrakeReleased/BR-4 moved"
    )
    assert _machine_number(ctx["rows_by_id"]["BR-4"]["machine"]) == 13
    errors = _consumes_relationship_errors(_ap9(g2), ["BrakeReleased"], ctx)
    assert errors, "AP-9 was laundered into CONSUMES by an ARBITRARY unrelated canonical event"
    joined = " ".join(errors)
    assert "co-commit" in joined, f"4(a) did not bite on an undeclared relationship: {errors}"
    assert "frozen" in joined and "replay" in joined, (
        f"4(d) did not bite - no F4 event carries the approval's `frozen` flag: {errors}"
    )


def test_hostile_an_event_required_and_a_consumes_row_may_not_be_swapped_at_constant_totals():
    """### THE COORDINATED SPEC+AUDIT LAUNDERING, WITH EVERY CLASS TOTAL HELD EXACTLY CONSTANT.

    This is the shape that defeated the previous 18 membership mutations. Those fail because the
    audit was NOT updated to match the spec - they trip the drift assertion, not any check on whether
    the new classification is TRUE. The real exploit updates both consistently, which is the ordinary
    shape of a legitimate builder commit. Then every set-equality guard is satisfied, because
    computed == recorded, and the arithmetic still closes.

    ### REPOINTED (P5 U5.2), SAME EXPLOIT, SAME TWO INDEPENDENT REFUSALS. The original swapped AP-9
    (then EVENT_REQUIRED) with PL-6 (CONSUMES). AP-9 is now the sec-3 producer of `ApprovalFrozen`,
    so that exact pair no longer exists - but the exploit does, and it survives the discharge in a
    sharper form: EVENT_REQUIRED is now EMPTY, so a launderer's move is to push a row INTO it (a
    plausible-looking "newly discovered obligation") in exchange for pulling one out, keeping the
    totals square. PL-6 stands in as the row pushed in, and AP-9 as the row whose GR-2 discharge is
    attacked from the other side by relabelling it a consumer.

    ### A CANDIDATE MUST NOT BE ACCEPTED BECAUSE ITS CLASSES RECONCILE: set equality between a
    specification and its audit proves the two AGREE, never that either is TRUE."""
    g2 = _g2_state()
    ctx = _consumes_context(g2)
    audit = _audit()
    live = {k: v["class"] for k, v in g2["result"]["classified"].items()}
    # ### FIXTURE PREMISES, NOT RULE GUARDS (R-06). Both state the starting classification the swap
    # below is a swap OF. They fire on any edit to AP-9 or PL-6 and are not defences.
    assert live["04-approval:AP-9"] == "PRODUCER", (
        "FIXTURE PREMISE: AP-9 is not a producer - its discharge is the premise of this node"
    )
    assert live["02-pipeline-instance:PL-6"] == "CONSUMES", "FIXTURE PREMISE"

    # the swap: PL-6 joins EVENT_REQUIRED, AP-9 leaves PRODUCER for CONSUMES. Totals are preserved
    # exactly, which is what defeated eighteen earlier membership mutations.
    swapped = dict(live)
    swapped["04-approval:AP-9"] = "CONSUMES"
    swapped["02-pipeline-instance:PL-6"] = "EVENT_REQUIRED"
    every = ("PRODUCER", *CLASS_TOKENS)
    before = {c: sum(1 for v in live.values() if v == c) for c in every}
    after = {c: sum(1 for v in swapped.values() if v == c) for c in every}
    # ### FIXTURE PREMISES, NOT RULE GUARDS (R-06). These three assert that the SWAP THIS NODE
    # CONSTRUCTS really is constant-total, and that the live classification and the audit agreed
    # before it. They are properties of the fixture, not refusals of anything.
    assert before["CONSUMES"] == after["CONSUMES"], (
        "FIXTURE PREMISE: the CONSUMES total moved - not the exploit shape"
    )
    assert before["PRODUCER"] - 1 == after["PRODUCER"], (
        "FIXTURE PREMISE: the swap did not remove exactly one producer"
    )
    assert before == audit["computed_classification"], (
        "FIXTURE PREMISE: the live classification and the audit already disagree, so this node would "
        "be measuring that disagreement rather than the swap"
    )

    # (1) the relational contract rejects the new consumer, whatever event it nominates.
    for event in ("ApprovalConsumed", "BrakeReleased", "RealityEstablished", "GrantClaimed"):
        assert _consumes_relationship_errors(_ap9(g2), [event], ctx), (
            f"AP-9 discharged GR-2 by consuming {event} at constant class totals"
        )
    # (1b) and it may not consume its OWN newly minted event either - rule 2 owns that case, and a
    #      row that produces an event cannot also claim to be receiving it from somewhere else.
    assert _consumes_relationship_errors(_ap9(g2), ["ApprovalFrozen"], ctx), (
        "AP-9 was allowed to declare it CONSUMES the event it actually OWNS"
    )
    # (2) PL-6 cannot JOIN the frozen EVENT_REQUIRED set. Registering a new founder-gated obligation
    #     is an adjudicated act, and the anchor refuses an addition exactly as it refuses a silent
    #     departure - the direction that only became reachable once the class emptied.
    joined = _event_required_set_errors(
        {**g2["result"]["classified"],
         "02-pipeline-instance:PL-6": {**g2["result"]["classified"]["02-pipeline-instance:PL-6"],
                                       "class": "EVENT_REQUIRED", "arg": "G2-OB-INVENTED"}},
        audit, ctx, g2["states"])
    assert any("JOINED EVENT_REQUIRED" in e for e in joined), (
        f"PL-6 joined the frozen EVENT_REQUIRED set unchallenged: {joined}"
    )
    # (3) the obligation registry rejects it too: every registered obligation names the transition
    #     that carries it, so an id cannot migrate to a different row.
    by_id = {o["id"]: o for o in audit["founder_gated_event_obligations"]}
    for oid, obligation in by_id.items():
        assert obligation["transition"] != "02-pipeline-instance:PL-6", (
            f"obligation {oid} would accept PL-6, which is not the row it records"
        )
    assert by_id["G2-OB-AP-9-FREEZE-FACT-UNRECORDED"]["transition"] == "04-approval:AP-9"


def test_hostile_two_consumers_may_not_swap_their_producers():
    """### R-01, BOTH STRUCTURAL SUB-CLASSES. Constant totals, constant membership, only the
    RELATIONSHIP mutated.

    ### THE SELECTION BIAS THIS NODE EXISTS TO CORRECT. The previous candidate tested this with
    PL-10f <-> PL-11c ONLY, and its own docstring conceded that 5a/5b/5c are all satisfied by a
    producer swap and that "the swap is caught by 4(d) alone". It then chose the one pair where 5d
    happens to engage - both rows declare a named field - and left the structurally weaker
    sub-class untested. The re-adjudication called that out: the information sufficient to find
    R-01 was written into the candidate's own test comment.

    There are exactly TWO sub-classes of durable consumer and BOTH are exercised here:

      FIELD-DECLARING  PL-10f <-> PL-11c. `EffectFailed` carries `failure_proof`, the Verification*
                       events carry `unknown_reason`, so after the swap neither consumer's field is
                       in its event's payload. 5d bites. (Retained regression.)
      STATE-ONLY       ### PL-10 <-> PL-11. NEITHER declares a field, so 5d is STRUCTURALLY VACUOUS
                       and cannot save this case. It is caught only because 5a is ROW-BOUND: PL-10
                       declares M3 `ATTEMPTED` (EF-3's target) and PL-11 declares M3 `VERIFIED`
                       (EF-4's), and the exchange puts each against the wrong owner in BOTH
                       directions. Under the machine-integer rule this pair passed silently.

    Each case asserts its OWN failure reason, so neither can pass because some other clause
    happened to fire."""
    g2 = _g2_state()
    ctx = _consumes_context(g2)
    R = g2["rows_by_id"]
    pl10f, pl11c, pl10, pl11 = R["PL-10f"], R["PL-11c"], R["PL-10"], R["PL-11"]

    # positive controls: all four are accepted as actually declared
    assert not _consumes_relationship_errors(pl10f, ["EffectFailed"], ctx)
    assert not _consumes_relationship_errors(
        pl11c, ["VerificationConflict", "VerificationUnavailable"], ctx)
    assert not _consumes_relationship_errors(pl10, ["EffectExecuted"], ctx)
    assert not _consumes_relationship_errors(pl11, ["EffectVerified"], ctx)

    # sub-class 1 - field-declaring: 5d is the clause that bites
    for row, swapped_to in ((pl10f, ["VerificationConflict"]), (pl11c, ["EffectFailed"])):
        errors = _consumes_relationship_errors(row, swapped_to, ctx)
        assert errors and "replay" in " ".join(errors), (
            f"{row['key']} accepted the swapped event {swapped_to} - a durable write was covered by "
            f"an event that does not carry it: {errors}"
        )

    # ### sub-class 2 - state-only: 5d declares nothing, so ONLY the row binding can catch it, and
    # ### it must catch it in BOTH directions.
    for row, swapped_to in ((pl10, ["EffectVerified"]), (pl11, ["EffectExecuted"])):
        assert not _declared_write_fields(row["writes"]), (
            f"{row['key']} now declares a field, so it is no longer the state-only sub-class and "
            "this node has stopped testing the case 5d cannot reach"
        )
        errors = _consumes_relationship_errors(row, swapped_to, ctx)
        joined = " ".join(errors)
        assert errors, (
            f"### R-01 IS BACK: {row['key']} accepted {swapped_to} at constant totals AND constant "
            "membership, with 5d vacuous - the co-commit declaration is pooled across the machine "
            "again instead of belonging to the row that wrote it"
        )
        assert "FORWARD" in joined and "REVERSE" in joined, (
            f"{row['key']}: the swap must fail in BOTH directions - a one-legged rejection means "
            f"one side is still satisfiable by a sibling row's declaration: {errors}"
        )
        assert "replay" not in joined, (
            f"{row['key']}: 5d fired, so this pair is not the state-only sub-class the node claims "
            f"to cover and the weaker case is once again untested: {errors}"
        )


def test_the_relation_matrix_over_every_consumer_and_every_canonical_event_is_exact():
    """### THE EXHAUSTIVE MATRIX. Not a sample - every CONSUMES row against every canonical contract.

    The re-adjudication refused hand-selected hostile examples as sufficient evidence and required
    the FULL FINITE RELATION MATRIX, because sampling is what hid R-01: 9 consumers x 111 F1-F14
    contracts is 999 evaluations and runs in about a second.

    ### THE EXPECTATION IS DERIVED INDEPENDENTLY OF THE PREDICATE UNDER TEST. Ground truth is the
    relationship set the SPECIFICATION ITSELF DECLARES - each row's own `CONSUMES:` token - read
    straight off the corpus. It never calls _consumes_relationship_errors, so this node cannot be
    tautological: if the guard and the declarations disagree anywhere, that disagreement is the
    result, not something the test defines away.

    Measured against candidate 1ae365a's machine-integer rule this matrix showed 23 false accepts
    across the 8 durable consumers with 0 false rejects. It must now show ZERO of both, with the
    single named, authority-cited exception below and nothing else."""
    g2 = _g2_state()
    ctx = _consumes_context(g2)
    states = g2["states"]
    marked = require_population(
        {k: v for k, v in g2["result"]["classified"].items() if v["class"] == "CONSUMES"},
        "CONSUMES transitions",
    )
    corpus = sorted(require_population(ctx["corpus"], "canonical event contracts"))
    declared = {k: {n for n in v["arg"].split(",") if n} for k, v in marked.items()}

    durable = {k: v for k, v in marked.items() if _durable_write(v["row"], states)}
    zero_write = {k: v for k, v in marked.items() if k not in durable}
    require_population(durable, "durable CONSUMES rows")
    require_population(zero_write, "zero-write CONSUMES rows")

    false_accepts, false_rejects, evaluated = [], [], 0
    for key, rec in sorted(durable.items()):
        for event in corpus:
            evaluated += 1
            accepted = not _consumes_relationship_errors(rec["row"], [event], ctx)
            if accepted and event not in declared[key]:
                false_accepts.append((key, event))
            elif event in declared[key] and not accepted:
                false_rejects.append((key, event))

    assert not false_rejects, (
        "### FALSE REJECTS: the guard refuses a relationship the specification declares. The row "
        f"binding must accept EVERY current valid consumer: {false_rejects}"
    )
    unexplained = sorted(set(false_accepts) - ADJUDICATED_UNDECLARED_ACCEPTS)
    assert not unexplained, (
        f"### {len(unexplained)} UNDECLARED (consumer, event) PAIRS ARE ACCEPTED with no adjudicated "
        f"justification. Each is a relationship the corpus does not declare and the guard cannot "
        f"distinguish: {unexplained}"
    )
    stale = sorted(ADJUDICATED_UNDECLARED_ACCEPTS - set(false_accepts))
    assert not stale, (
        f"an adjudicated exception no longer occurs: {stale}. Remove it from the record rather than "
        "carrying a justification for something that is not happening - a stale carve-out is a "
        "standing licence for a future false accept"
    )
    # the exceptions are NAMED in the audit too, so a reader meets them as findings, not as silence
    residuals = {str(r["pair"]) for r in _audit()["consumes_relation_matrix"]["carried_residuals"]}
    assert residuals == {f"{k} -> {e}" for k, e in ADJUDICATED_UNDECLARED_ACCEPTS}, (
        f"the audit's carried residual list drifted from the guard's exception set: {sorted(residuals)}"
    )

    # rule 4 / R-08: a zero-durable-write row is DESCRIPTIVE. It accepts broadly and that is
    # ADJUDICATED CORRECT, because GR-2 never binds it - its marker exempts nothing.
    for key, rec in sorted(zero_write.items()):
        accepts = [e for e in corpus if not _consumes_relationship_errors(rec["row"], [e], ctx)]
        assert declared[key] <= set(accepts), f"{key}: its own declared event is rejected"
        assert len(accepts) > len(declared[key]), (
            f"{key}: a zero-write row is being held to 5a-5d, which rule 4 does not require"
        )
    assert evaluated == len(durable) * len(corpus) >= 800, (
        f"the matrix is not exhaustive: {evaluated} evaluations over {len(durable)} durable "
        f"consumers x {len(corpus)} contracts"
    )


def test_hostile_an_open_obligation_may_not_annex_another_rows_co_commit_declaration():
    """### R-02, THE PL-7a LAUNDERING, REPRODUCED EXACTLY AND ASSERTED TO FAIL.

    PL-7a is `VALIDATED`->`CHECKPOINT` on M2: the SOLE autonomous entry into CHECKPOINT
    (gate = AUTONOMOUS_WITHIN_CAPS), severity HIGHEST GOVERNANCE, an OPEN founder-gated obligation.
    The complete exploit is three coordinated edits - the ordinary shape of a legitimate commit:

        spec   Writes  `—`  ->  co-commit M3 `ATTEMPTED`
        spec   Event   EVENT_REQUIRED:G2-OB-PL-7A-...  ->  CONSUMES:EffectExecuted
        audit  move PL-7a into CONSUMES.members, DELETE its obligation, 7 -> 6

    Against candidate 1ae365a all three passed at 53 passed / 0 failed, identical to baseline.

    ### WHY IT WORKED. PL-7a is the only durable EVENT_REQUIRED row on M2 - the one machine for
    which an M3 owner already declares a reciprocal - and its Writes cell names no field, so 5d is
    vacuous. It supplied its own forward token and ANNEXED EF-3's `co-commit M2 `EXECUTED``, a
    declaration written for PL-10's benefit.

    ### WHY IT NOW FAILS. The reverse leg is row-bound: EF-3 names `EXECUTED`, the state PL-10
    enters, not `CHECKPOINT`. And the frozen-set guard refuses an UNPROVEN departure independently.
    Both are asserted, because either alone would leave the other unproven.

    ### AMENDED (P5 U5.2), AND THE AMENDMENT IS WHERE THE CARE GOES. PL-7a's obligation is now
    LEGITIMATELY discharged - by a minted canonical event, re-proven from events/registry.md sec 3 -
    so "PL-7a left EVENT_REQUIRED" is no longer by itself a defect, and asserting that it is would be
    asserting something false. The laundering property is preserved by attacking the DISCHARGE RECORD
    instead of the departure:

      (2) DELETE the recorded discharge and leave the row out of EVENT_REQUIRED -> the departure is
          now silent, and must fail. This is the exact original defect, one indirection along.
      (3) FORGE a PRE_EXISTING_STRUCTURAL_PROOF discharge for the laundered CONSUMES row -> must fail,
          because the structural proof is re-derived and does not hold.
      (4) FORGE a MINTED_CANONICAL_EVENT discharge naming an event PL-7a does not produce -> must
          fail, which is the route this unit actually used and therefore the one most worth attacking.
    """
    g2 = _g2_state()
    ctx = _consumes_context(g2)
    audit = _audit()
    states = g2["states"]
    pl7a = g2["rows_by_id"]["PL-7a"]
    assert _durable_write(pl7a, states) and _bare(pl7a["writes"]), (
        "PL-7a is no longer the durable, field-less M2 row the exploit needs - this node has "
        "stopped testing the case"
    )
    assert ctx["owners_of"]["EffectExecuted"] == ["EF-3"], "EffectExecuted/EF-3 moved"
    assert ctx["producers_of"].get("PL-7a") == {"AutonomousAdmissionRecorded"}, (
        "PL-7a's own minted event moved - the discharge this node attacks is not the one recorded"
    )

    # (1) the annexation itself, with PL-7a's own forward token added exactly as the exploit adds it
    laundered = {**pl7a, "writes": "co-commit M3 `ATTEMPTED`"}
    errors = _consumes_relationship_errors(laundered, ["EffectExecuted"], ctx)
    joined = " ".join(errors)
    assert errors, (
        "### R-02 IS BACK: PL-7a discharged the corpus's HIGHEST GOVERNANCE open obligation by "
        "adding ONE co-commit token and annexing a declaration written for another row"
    )
    assert "REVERSE" in joined, (
        f"the annexation must fail on the REVERSE leg specifically - that is the leg PL-7a cannot "
        f"author for itself, and any other rejection would be incidental: {errors}"
    )
    assert "CHECKPOINT" in joined and "EXECUTED" in joined, (
        f"the rejection does not turn on the two states that distinguish the rows: {errors}"
    )
    # a candidate-authored token buys the forward leg and NOTHING else - stated as a fact, not hoped
    forward_only = [e for e in errors if "FORWARD" in e]
    assert not forward_only, (
        f"the fixture no longer models 'the candidate can satisfy its own forward leg': {errors}"
    )

    laundered_classes = dict(g2["result"]["classified"])
    laundered_classes["02-pipeline-instance:PL-7a"] = {
        "class": "CONSUMES", "arg": "EffectExecuted", "row": laundered}
    record = audit["frozen_event_required_set"]
    others = [d for d in record["discharges"] if d["transition"] != "02-pipeline-instance:PL-7a"]
    assert len(others) == len(record["discharges"]) - 1, "PL-7a's discharge record is missing"

    def with_discharges(entries):
        return {**audit, "frozen_event_required_set": {**record, "discharges": [*others, *entries]}}

    # (2) SILENT DEPARTURE. Strip PL-7a's discharge and leave it out of EVENT_REQUIRED: exactly the
    #     shape of the original laundering, and it must still be a build failure.
    errors = _event_required_set_errors(laundered_classes, with_discharges([]), ctx, states)
    assert any("PL-7a" in e and "NO RECORDED DISCHARGE" in e for e in errors), (
        "PL-7a left the frozen EVENT_REQUIRED set with no recorded discharge and nothing objected - "
        f"the population is being held by a count again: {errors}"
    )
    # (3) A SELF-WRITTEN STRUCTURAL PROOF does not make the discharge real.
    forged_structural = with_discharges([{"transition": "02-pipeline-instance:PL-7a",
                                          "route": "PRE_EXISTING_STRUCTURAL_PROOF",
                                          "authority": "asserted by this edit"}])
    errors = _event_required_set_errors(laundered_classes, forged_structural, ctx, states)
    # ### REWORDED, NOT WEAKENED (P5 U5.2 second replacement). This previously asserted the substring
    # `"does not hold"` of `_consumes_relationship_errors`' refusal - i.e. it asserted that the
    # STRUCTURAL PREDICATE was what refused. For a member of ADJUDICATED_EVENT_REQUIRED the predicate
    # is no longer reached at all: the chokepoint refuses the whole route before dispatch, which is a
    # STRICTER refusal reached SOONER. The node still refuses; it now names the thing that refuses.
    assert any(CHOKEPOINT_MARK in e and "02-pipeline-instance:PL-7a" in e for e in errors), (
        f"a SELF-WRITTEN structural discharge record was accepted as the discharge: {errors}"
    )
    # (4) ### THE ROUTE THIS UNIT ACTUALLY USED, ATTACKED. A minted-event discharge that names an
    #     event this row does not produce - or a name that is not canonical at all - must fail. The
    #     record is a claim; sec 3 decides.
    for event, why in (("ApprovalBound", "an event owned by PL-7b, the human-gated sibling"),
                       ("EffectExecuted", "an event owned by EF-3 on another machine"),
                       ("NotACanonicalEventName", "a name that is not in the corpus at all")):
        forged_mint = with_discharges([{"transition": "02-pipeline-instance:PL-7a",
                                        "route": "MINTED_CANONICAL_EVENT", "event": event,
                                        "authority": "founder/architect, allegedly"}])
        errors = _event_required_set_errors(laundered_classes, forged_mint, ctx, states)
        assert errors, f"PL-7a discharged itself by naming {event} - {why}"
    # (5) and an UNKNOWN route is not a third route.
    forged_route = with_discharges([{"transition": "02-pipeline-instance:PL-7a",
                                     "route": "ADJUDICATED_AS_FINE", "authority": "x"}])
    errors = _event_required_set_errors(laundered_classes, forged_route, ctx, states)
    assert any("NO THIRD ROUTE" in e for e in errors), f"an invented route was accepted: {errors}"

    # positive control: the real seven, unmutated, with their real discharges, pass
    assert not _event_required_set_errors(g2["result"]["classified"], audit, ctx, states), (
        "the unmutated adjudicated set does not pass - the guard would be vacuous"
    )


# ==================================================== THE CHOKEPOINT'S OWN HOSTILE BATTERY
#
# ### ONE NODE PER ADJUDICATED MEMBER, ALL FOUR LAUNDERING SHAPES, AND NO NAME-PINNED GAPS.
# The a6005a8 rejection turned on the fact that AP-9 had two name-pinned regression nodes and CF-7
# and EC-7 had NONE - which is precisely why R-01 reached them and neither the builder's battery nor
# the first review noticed. Every one of the seven now has its own node, and every node runs all
# four shapes, so a future route cannot land on the two rows nobody wrote a test for.
#
# THE FOUR SHAPES, each the actual exploit that rejected a candidate or was proven by an adjudicator:
#
#   R-01   CONSUMES with the row's own `Writes` cell EMPTIED, so `_durable_write` returns False and
#          consumes_valid rule 3 short-circuits past 4(b), 4(c), 5a and 5d. Rejected a6005a8.
#          Accepted at a6005a8 for AP-9, CF-7 and EC-7 - the three whose durable write is a FIELD
#          write rather than a state change.
#   N-02   BIDIRECTIONALLY FORGED CO-COMMIT: the consumer declares `co-commit: M13 `RELEASED`` and
#          the OWNER row BR-4's own `Writes` cell is forged to declare the reciprocal. 5a's REVERSE
#          leg is "the leg a candidate row cannot author for itself" - true of the row, FALSE OF THE
#          EDIT, which authors both rows. Accepted at a6005a8 for ALL SEVEN.
#   R-02   DELEGATES_TO with the row's own `Trig` cell WIDENED to every canonical trigger code,
#          defeating the trigger conjunct outright. Accepted at a6005a8 for PL-7a and AP-9, the two
#          members with a same-machine expressible target.
#   MINT   RE-ATTRIBUTION: point the row at an EXISTING same-machine canonical event through a sec-3
#          edit, so `event in corpus` and `event in producers_of[row]` both corroborate perfectly.
#          Accepted at a6005a8 for ALL SEVEN.
#
# ### AND EACH NODE PROVES THE CHOKEPOINT IS WHAT REFUSES. Neutering
# `_adjudicated_discharge_authorization_errors` alone - one monkeypatch, nothing else touched - must
# put the laundering straight back through. If a node could pass with the chokepoint neutered it
# would be measuring some incidental property of the row, exactly the way `_ap9(g2)` was measuring
# AP-9 "with the Writes cell populated" while the launderer emptied it.
_LAUNDERING_TRIGGER_WIDENED = r"S\|H\|X\|T\|P\|B\|R"
# CF-7 and EC-7 name no canonical To state ("*(more parties)*", "*(severity change)*"), so 5a's
# forward leg has no state to bind. The adjudication established that supplying one is a one-cell
# edit inside the same laundering, so the shapes below supply it rather than letting these two rows
# be refused on an accident of their own prose.
_LAUNDERING_TO_STATE = {
    "07-conflict:CF-7": "`{RAISED,OPEN}` → `OPEN`",
    "09-exception:EC-7": "`{OPEN,ACKNOWLEDGED,ESCALATED}` → `ESCALATED`",
}
_LAUNDERING_DELEGATION = {
    "02-pipeline-instance:PL-7a": "CHECKPOINT=PL-7b",     # admitted at a6005a8 with Trig widened
    "04-approval:AP-9": "GRANTED=AP-2",                   # admitted at a6005a8 with Trig widened
    "07-conflict:CF-7": "OPEN=CF-1",
    "09-exception:EC-7": "OPEN=EX-1",
    "11-policy:PO-2": "PROPOSED=PO-1",
    "11-policy:PO-3": "APPROVED=PO-4",
    "12-rule:RU-8": "EXPIRED=RU-5",
}
_LAUNDERING_REATTRIBUTION = {
    "02-pipeline-instance:PL-7a": "CheckpointPassed",
    "04-approval:AP-9": "ApprovalGranted",
    "07-conflict:CF-7": "ConflictOpened",
    "09-exception:EC-7": "ExceptionEscalated",
    "11-policy:PO-2": "PolicyProposed",
    "11-policy:PO-3": "PolicyActivated",
    "12-rule:RU-8": "RuleRevoked",
}


def _laundering(g2: dict, ctx: dict, key: str, shape: str) -> tuple[dict, dict, dict]:
    """Build one laundering of one adjudicated member -> (class record, ctx overlay, discharge).

    Every edit here is one a builder may make in the ordinary course: a specification cell, another
    row's specification cell, or an events/registry.md sec-3 line. NO GUARD FILE IS TOUCHED, which
    is the whole point - a defence that requires the launderer to edit the guard is not a defence
    against the launderer, it is a defence against carelessness.
    """
    states = g2["states"]
    row = dict(g2["result"]["classified"][key]["row"])
    forged = {"transition": key, "route": "PRE_EXISTING_STRUCTURAL_PROOF", "event": "BrakeReleased",
              "authority": "asserted by this edit"}
    if shape == "R-01":
        laundered = {**row, "writes": "—", "event": "`CONSUMES:BrakeReleased`"}
        return {"class": "CONSUMES", "arg": "BrakeReleased", "row": laundered}, ctx, forged
    if shape == "N-02":
        from_to = _LAUNDERING_TO_STATE.get(key, row["from_to"])
        to_state = sorted(_states_in(from_to.split("→", 1)[-1], states))[0]
        laundered = {**row, "from_to": from_to, "writes": "co-commit: M13 `RELEASED`",
                     "event": "`CONSUMES:BrakeReleased`"}
        owner = dict(ctx["rows_by_id"]["BR-4"])
        owner["writes"] = (f"{owner['writes']}; co-commit: "
                           f"M{_machine_number(row['machine'])} `{to_state}`")
        overlay = {**ctx, "rows_by_id": {**ctx["rows_by_id"], "BR-4": owner}}
        return {"class": "CONSUMES", "arg": "BrakeReleased", "row": laundered}, overlay, forged
    if shape == "R-02":
        spec = _LAUNDERING_DELEGATION[key]
        laundered = {**row, "trig": _LAUNDERING_TRIGGER_WIDENED, "event": f"`DELEGATES_TO:{spec}`"}
        return ({"class": "DELEGATES_TO", "arg": spec, "row": laundered}, ctx,
                {**forged, "event": "n/a"})
    if shape == "MINT":
        event = _LAUNDERING_REATTRIBUTION[key]
        producers = {k: set(v) for k, v in ctx["producers_of"].items()}
        producers[row["id"]] = {event}                                   # the sec-3 edit, mechanised
        overlay = {**ctx, "producers_of": producers}
        return ({"class": "PRODUCER", "arg": None, "row": row}, overlay,
                {"transition": key, "route": "MINTED_CANONICAL_EVENT", "event": event,
                 "authority": "founder/architect, allegedly"})
    raise AssertionError(f"unknown laundering shape {shape!r}")


def _assert_no_laundering_discharges(monkeypatch, key: str):
    """The whole battery for one adjudicated member. Two halves, and the second is the load-bearing
    one: WITH the chokepoint every shape is refused BY THE CHOKEPOINT, and WITHOUT it the general
    predicates put at least the two universal shapes straight back through."""
    g2 = _g2_state()
    base_ctx = _consumes_context(g2)
    audit = _audit()
    states = g2["states"]
    record = audit["frozen_event_required_set"]
    assert key in ADJUDICATED_EVENT_REQUIRED, f"{key} is not an adjudicated member"
    assert key in g2["result"]["classified"], f"{key} is no longer a corpus row"

    def attempt(shape):
        rec, ctx, entry = _laundering(g2, base_ctx, key, shape)
        classified = {**g2["result"]["classified"], key: rec}
        others = [d for d in record["discharges"] if d["transition"] != key]
        assert len(others) == len(record["discharges"]) - 1, (
            f"{key} has no recorded discharge to replace - this node is not testing a laundering"
        )
        laundered_audit = {**audit,
                           "frozen_event_required_set": {**record, "discharges": [*others, entry]}}
        return [e for e in _event_required_set_errors(classified, laundered_audit, ctx, states)
                if key in e]

    for shape in ("R-01", "N-02", "R-02", "MINT"):
        errors = attempt(shape)
        assert errors, (
            f"### {key} WAS DISCHARGED BY LAUNDERING {shape}. A founder-gated obligation left the "
            "adjudicated set with the discharge machinery green. This is the defect that rejected "
            "38b4bda, 1ae365a, f01d942 and a6005a8, in its fifth coat."
        )
        assert any(CHOKEPOINT_MARK in e for e in errors), (
            f"{key}/{shape} is refused, but NOT by the chokepoint: {errors}. A refusal that comes "
            "from a route predicate is a refusal that reads a cell the discharging edit authors, "
            "and the next shape of the same edit will get past it - which is how four candidates "
            "were rejected in a row."
        )

    # ### THE LOAD-BEARING HALF. Neuter the chokepoint and NOTHING ELSE. If the launderings do not
    # come back, the assertions above were being carried by something incidental.
    monkeypatch.setattr(sys.modules[__name__], "_adjudicated_discharge_authorization_errors",
                        lambda key, entry: [])
    assert _adjudicated_discharge_authorization_errors("x", {"route": "NOPE"}) == [], (
        "the monkeypatch did not take - the assertion below would be re-running the guarded code"
    )
    readmitted = {shape for shape in ("R-01", "N-02", "R-02", "MINT") if not attempt(shape)}
    assert {"N-02", "MINT"} <= readmitted, (
        f"### with the chokepoint neutered only {sorted(readmitted)} launder {key}. The two shapes "
        "asserted here are the ones the adjudication proved accepted for ALL SEVEN at a6005a8 - the "
        "bidirectionally forged co-commit and the same-machine MINT re-attribution - so if either "
        "no longer lands, the fixture has stopped modelling the exploit and the chokepoint's "
        "necessity is no longer being demonstrated by this node."
    )


def test_hostile_no_laundering_discharges_pl_7a(monkeypatch):
    """PL-7a - the SOLE autonomous entry into CHECKPOINT, HIGHEST GOVERNANCE, the row whose silent
    7->6 departure started this whole line of rejections."""
    _assert_no_laundering_discharges(monkeypatch, "02-pipeline-instance:PL-7a")


def test_hostile_no_laundering_discharges_ap_9(monkeypatch):
    """AP-9 - the row of the 38b4bda rejection, and the only member that ever had name-pinned
    regression nodes of its own."""
    _assert_no_laundering_discharges(monkeypatch, "04-approval:AP-9")


def test_hostile_no_laundering_discharges_cf_7(monkeypatch):
    """### CF-7 - ONE OF THE TWO ROWS THAT HAD NO NAME-PINNED NODE AT ALL, which is exactly why R-01
    reached it and why a6005a8 was rejected."""
    _assert_no_laundering_discharges(monkeypatch, "07-conflict:CF-7")


def test_hostile_no_laundering_discharges_ec_7(monkeypatch):
    """### EC-7 - the other one. Same gap, same reason."""
    _assert_no_laundering_discharges(monkeypatch, "09-exception:EC-7")


def test_hostile_no_laundering_discharges_po_2(monkeypatch):
    """PO-2 - `DRAFT`->`PROPOSED` on M11, a state change, so R-01 never reached it and the earlier
    batteries stopped there. N-02 and the MINT re-attribution both reach it."""
    _assert_no_laundering_discharges(monkeypatch, "11-policy:PO-2")


def test_hostile_no_laundering_discharges_po_3(monkeypatch):
    """PO-3 - `PROPOSED`->`APPROVED` on M11."""
    _assert_no_laundering_discharges(monkeypatch, "11-policy:PO-3")


def test_hostile_no_laundering_discharges_ru_8(monkeypatch):
    """RU-8 - the row the adjudication used to demonstrate N-02 end to end, and whose own committed
    prose says the other aggregate's fact "does not record that THIS rule expired"."""
    _assert_no_laundering_discharges(monkeypatch, "12-rule:RU-8")


def test_the_founder_authorization_table_and_the_recorded_discharges_agree_exactly():
    """### THE AUTHORIZATION TABLE IS HELD AGAINST THE RECORD, IN BOTH DIRECTIONS.

    `FOUNDER_AUTHORIZED_DISCHARGES` is the only literal in this file that is NOT a re-derived
    measurement, because its subject - founder/architect decisions D1 and D2 - is not a property of
    any structured column. That makes its integrity worth asserting directly:

      - every authorized pair is actually recorded as a discharge, so the table cannot be widened in
        advance of a decision, nor left holding a pair whose discharge was withdrawn;
      - every recorded discharge is authorized, so the audit cannot re-point a discharge at another
        event - the MINT re-attribution - without this node going red beside the chokepoint;
      - the table's key set is exactly `ADJUDICATED_EVENT_REQUIRED`, so it can neither cover a row
        that was never gated nor silently drop one that was.

    It does NOT establish that the seven decisions were made; nothing in a repository can. It
    establishes that the guard, the audit record and the adjudicated anchor say the same thing."""
    audit = _audit()
    record = audit["frozen_event_required_set"]
    recorded = {(str(d.get("transition", "")), str(d.get("event", "")))
                for d in require_population(record.get("discharges") or [], "recorded discharges")}
    assert recorded == set(FOUNDER_AUTHORIZED_DISCHARGES), (
        "### THE FOUNDER AUTHORIZATION TABLE AND THE RECORDED DISCHARGES DISAGREE.\n"
        f"  recorded but NOT authorized (a re-attribution, or a discharge nobody authorized): "
        f"{sorted(recorded - set(FOUNDER_AUTHORIZED_DISCHARGES))}\n"
        f"  authorized but NOT recorded (the table was widened ahead of a decision): "
        f"{sorted(set(FOUNDER_AUTHORIZED_DISCHARGES) - recorded)}"
    )
    assert {k for k, _ in FOUNDER_AUTHORIZED_DISCHARGES} == set(ADJUDICATED_EVENT_REQUIRED), (
        "the authorization table's rows are no longer exactly the adjudicated seven - it authorizes "
        f"{sorted({k for k, _ in FOUNDER_AUTHORIZED_DISCHARGES} ^ set(ADJUDICATED_EVENT_REQUIRED))} "
        "differently from the anchor"
    )
    assert len({k for k, _ in FOUNDER_AUTHORIZED_DISCHARGES}) == len(FOUNDER_AUTHORIZED_DISCHARGES), (
        "a row appears twice in the authorization table - a member may be discharged by exactly one "
        "founder-authorized event"
    )


def test_the_adjudicated_discharge_chokepoint_is_default_deny_and_decides_before_dispatch():
    """### DEFAULT-DENY IS THE PROPERTY, NOT THE LIST OF THINGS IT HAPPENS TO REFUSE.

    Four candidates were rejected on four different routes because each guard enumerated the routes
    it knew about and let the rest through. This asserts the inverse shape directly on the chokepoint
    function: an UNKNOWN route string is refused without anybody having thought of it, a
    PRE_EXISTING_STRUCTURAL_PROOF is refused whatever the row is classified as, and an authorized
    MINT is admitted ONLY for its own authorized event.

    ### AND IT DECIDES BEFORE DISPATCH, WHICH IS THE PART THAT GENERALISES. The chokepoint takes only
    the key and the discharge record - it is not given `rec`, `ctx` or `states`, so it CANNOT read a
    specification cell even by accident, and there is no cell for a launderer to forge. An AST scan
    asserts that, because a signature can be widened by a later edit and a comment cannot stop it."""
    for route in ("PRE_EXISTING_STRUCTURAL_PROOF", "FOUNDER_WAIVER", "ADJUDICATED_AS_FINE", "", None):
        for key in sorted(ADJUDICATED_EVENT_REQUIRED):
            errors = _adjudicated_discharge_authorization_errors(
                key, {"route": route, "event": "ApprovalFrozen"})
            assert errors and all(CHOKEPOINT_MARK in e for e in errors), (
                f"route {route!r} was admitted for {key} without a founder authorization: {errors}"
            )
    for key, event in sorted(FOUNDER_AUTHORIZED_DISCHARGES):
        assert not _adjudicated_discharge_authorization_errors(
            key, {"route": "MINTED_CANONICAL_EVENT", "event": event}), (
            f"the chokepoint refuses the AUTHORIZED discharge {key} -> {event}: it would be "
            "refusing the corpus's own seven, which is worse than the hole it closes"
        )
        for other in sorted({e for _, e in FOUNDER_AUTHORIZED_DISCHARGES} - {event}):
            assert _adjudicated_discharge_authorization_errors(
                key, {"route": "MINTED_CANONICAL_EVENT", "event": other}), (
                f"{key} was discharged by {other}, another member's authorized event - the table "
                "is being read as a set of NAMES rather than a set of (row, event) PAIRS"
            )

    # ### THE CHOKEPOINT READS NO SPECIFICATION CELL. Proven from its own source, not from its
    # signature: any of these names appearing inside it would mean a launderer-authored datum had
    # been let back into the one decision that must not depend on one.
    forbidden = {"rec", "ctx", "states", "row", "audit", "writes", "trig", "from_to",
                 "_durable_write", "_consumes_relationship_errors", "_resolve_delegation",
                 "_registered_durable_writes", "_transition_rows", "_event_registry"}
    tree = ast.parse(textwrap.dedent(
        inspect.getsource(_adjudicated_discharge_authorization_errors)))
    named = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} | \
            {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)} | \
            {a.arg for a in ast.walk(tree) if isinstance(a, ast.arg)} | \
            {c.value for c in ast.walk(tree) if isinstance(c, ast.Constant)
             and isinstance(c.value, str)}
    assert not (named & forbidden), (
        f"### the chokepoint now reads {sorted(named & forbidden)}. Its whole value is that it "
        "decides from the adjudication and the discharge record alone; give it a specification "
        "input and it becomes the fifth self-certifying route."
    )
    # and the dispatcher consults it BEFORE either route branch
    body = inspect.getsource(_discharge_route_errors)
    gate = body.find("_adjudicated_discharge_authorization_errors")
    assert 0 < gate < body.find('"MINTED_CANONICAL_EVENT"'), (
        "the chokepoint is no longer evaluated before the route dispatch in "
        "`_discharge_route_errors` - a route predicate would then run first, and a predicate that "
        "returns [] IS an accepted discharge"
    )


def test_hostile_a_rule_owned_event_can_never_be_consumed():
    """`IllegalTransitionAttempted` IS a canonical name, so rule 1 passes - and its declared sec-3
    producer is the RULE `GR-1`, which is not a transition, so there is no row to co-commit with.
    That is the mechanical reason PL-15x and IB-5x are NON_PRODUCING, and it is what the first
    candidate got wrong against G2 sec H step 7's explicit ruling."""
    g2 = _g2_state()
    ctx = _consumes_context(g2)
    assert "IllegalTransitionAttempted" in ctx["corpus"], (
        "the event left the corpus - this node would then pass for the wrong reason"
    )
    assert not ctx["owners_of"].get("IllegalTransitionAttempted"), (
        "IllegalTransitionAttempted acquired a transition owner - G2-D8's schema gap changed"
    )
    for key in ("02-pipeline-instance:PL-15x", "06-identity-binding-claim:IB-5x"):
        assert g2["result"]["classified"][key]["class"] == "NON_PRODUCING", (
            f"{key} is not NON_PRODUCING - it diverged from the adjudicated disposition again"
        )
        errors = _consumes_relationship_errors(
            g2["result"]["classified"][key]["row"], ["IllegalTransitionAttempted"], ctx)
        assert errors and "RULE" in " ".join(errors), (
            f"{key} was accepted back into CONSUMES against G2 sec H step 7: {errors}"
        )


def test_hostile_a_consumer_whose_relationship_is_undeclared_or_dangling_fails():
    """Malformed relationships and one nonexistent event, isolating 5a from everything else.

    The consumer and owner are synthetic so the ONLY variable is the co-commit declaration: the same
    pair passes once BOTH rows declare it AT THE RIGHT STATE and fails when either side is missing,
    names the wrong state, or names no state at all. That is what makes 5a bidirectional AND
    row-bound rather than a formality one row can satisfy alone.

    ### The `co-commit M7` / `co-commit M5 <wrong state>` cases are the ones the previous candidate
    would have PASSED: it compared machine integers, so any declaration anywhere on the partner
    machine satisfied it."""
    g2 = _g2_state()
    ctx = _consumes_context(g2)
    # Real canonical states, because the row binding reads canonical state tokens and a synthetic
    # placeholder would make every assertion below pass for the wrong reason.
    owner = _synthetic("QQ-1", "`SomeEvent`", writes="`widget_id`; co-commit M5 `CONFIRMED`",
                       from_to="`OPEN` → `RESOLVED`", machine="07-conflict")
    consumer = _synthetic("QQ-2", "`CONSUMES:SomeEvent`",
                          writes="`widget_id`; co-commit M7 `RESOLVED`",
                          from_to="`RECEIVED` → `CONFIRMED`", machine="05-observation")
    ctx = {**ctx,
           "rows_by_id": {**ctx["rows_by_id"], "QQ-1": owner},
           "owners_of": {**ctx["owners_of"], "SomeEvent": ["QQ-1"]},
           "corpus": ctx["corpus"] | {"SomeEvent"},
           "payloads": {**ctx["payloads"], "SomeEvent": {"widget_id"}}}
    assert not _consumes_relationship_errors(consumer, ["SomeEvent"], ctx), (
        "a fully declared, correctly row-bound cross-machine co-commit is rejected - the fixture "
        "does not model a valid relationship, so the negatives below would prove nothing"
    )
    no_forward = {**consumer, "writes": "`widget_id`"}
    assert _consumes_relationship_errors(no_forward, ["SomeEvent"], ctx), (
        "a consumer that declares NO co-commit was accepted"
    )
    silent_owner = {**ctx, "rows_by_id": {**ctx["rows_by_id"],
                                          "QQ-1": {**owner, "writes": "`widget_id`"}}}
    assert _consumes_relationship_errors(consumer, ["SomeEvent"], silent_owner), (
        "an owner that does not declare the RECIPROCAL co-commit was accepted"
    )
    # ### the row binding proper: RIGHT MACHINE, WRONG STATE, in each direction independently.
    wrong_forward = {**consumer, "writes": "`widget_id`; co-commit M7 `ESCALATED`"}
    errors = _consumes_relationship_errors(wrong_forward, ["SomeEvent"], ctx)
    assert errors and "FORWARD" in " ".join(errors), (
        f"a consumer naming the owner's MACHINE but the WRONG STATE was accepted - 5a is still "
        f"pooled across the machine: {errors}"
    )
    wrong_reverse = {**ctx, "rows_by_id": {
        **ctx["rows_by_id"], "QQ-1": {**owner, "writes": "`widget_id`; co-commit M5 `AMBIGUOUS`"}}}
    errors = _consumes_relationship_errors(consumer, ["SomeEvent"], wrong_reverse)
    assert errors and "REVERSE" in " ".join(errors), (
        f"an owner naming the consumer's MACHINE but the WRONG STATE was accepted - this is the "
        f"exact shape by which PL-7a annexed a declaration written for PL-10: {errors}"
    )
    # ### rule 7: a machine token with no canonical state beside it is UNDECIDABLE, never a pass.
    bare_machine = {**consumer, "writes": "`widget_id`; co-commit M7"}
    errors = _consumes_relationship_errors(bare_machine, ["SomeEvent"], ctx)
    assert errors and "UNDECIDABLE" in " ".join(errors), (
        f"a bare machine token was read as a relationship instead of failing closed: {errors}"
    )
    dangling = {**ctx, "rows_by_id": {k: v for k, v in ctx["rows_by_id"].items() if k != "QQ-1"}}
    assert _consumes_relationship_errors(consumer, ["SomeEvent"], dangling), (
        "a consumed event whose declared producer is absent from the corpus was accepted"
    )
    # (`ApprovalFrozen` used to stand here as the obviously-non-canonical name. It is canonical now -
    # AP-9's minted event - which would have made this the only kind of test failure worse than a
    # false green: an assertion that silently stopped testing anything.)
    assert "NotACanonicalEventName" not in ctx["corpus"], "pick a name that is genuinely not canonical"
    assert _consumes_relationship_errors(consumer, ["NotACanonicalEventName"], ctx), (
        "a consumer naming a NONEXISTENT event was accepted"
    )


def test_hostile_a_durable_write_is_not_covered_by_a_random_events_payload():
    """4(d) ALONE, isolated. Everything else about this pair is impeccable: cross-machine, both
    co-commits declared, not mutually exclusive. The only defect is that the consumer persists a
    field no consumed event's sec-5 payload carries, so a full-history replay could not reconstruct
    it - exactly AP-9's `frozen=true` situation. Exactly ONE error must be raised, and it must be the
    replay one, or this node is really testing something else."""
    g2 = _g2_state()
    ctx = _consumes_context(g2)
    owner = _synthetic("QQ-3", "`OtherEvent`", writes="`known_field`; co-commit M5 `CONFIRMED`",
                       from_to="`OPEN` → `RESOLVED`", machine="07-conflict")
    ctx = {**ctx,
           "rows_by_id": {**ctx["rows_by_id"], "QQ-3": owner},
           "owners_of": {**ctx["owners_of"], "OtherEvent": ["QQ-3"]},
           "corpus": ctx["corpus"] | {"OtherEvent"},
           "payloads": {**ctx["payloads"], "OtherEvent": {"known_field"}}}
    covered = _synthetic("QQ-4", "`CONSUMES:OtherEvent`",
                         writes="`known_field`; co-commit M7 `RESOLVED`",
                         from_to="`RECEIVED` → `CONFIRMED`", machine="05-observation")
    assert not _consumes_relationship_errors(covered, ["OtherEvent"], ctx), (
        "the covered control is rejected, so the uncovered case below would prove nothing"
    )
    uncovered = {**covered, "writes": "`unrecorded_safety_flag`; co-commit M7 `RESOLVED`"}
    errors = _consumes_relationship_errors(uncovered, ["OtherEvent"], ctx)
    assert len(errors) == 1 and "replay" in errors[0] and "unrecorded_safety_flag" in errors[0], (
        f"4(d) is not the check that bit, so it is not independently load-bearing: {errors}"
    )
    prose_only = {**covered, "writes": "the flag was set; co-commit M7 `RESOLVED`"}
    assert not _consumes_relationship_errors(prose_only, ["OtherEvent"], ctx), (
        "prose in a Writes cell was read as a field declaration - fields come from structured forms "
        "only, which is what stops a name being smuggled in inside a sentence"
    )


def test_hostile_the_retired_24_carve_out_cannot_be_bought_with_a_trailing_clause():
    """F-03, reproduced exactly as the adjudication reproduced it, then asserted to FAIL.

    The first carve-out keyed on a +/-120 character window, so one appended clause revived the
    retired figure in precisely its retired sense across the whole guarded population. The carve-out
    now requires the two tokens in ONE CLAUSE."""
    revived = "24 of the 134 transitions name no event outright, which is the non-producer population."
    bare = "24 of the 134 transitions name no event outright."
    true_sentence = ("A *producer transition* is one declared in §3 — 110 of the 134 rows; the other "
                     "24 are non-producer transitions — and completeness is GR-2 over durable writes.")
    historical = 'The retired "24 of 134" figure was never mechanically computed for transitions.'
    assert _retired_24_offenders(revived), (
        "### F-03 IS BACK: appending 'which is the non-producer population' bought amnesty for the "
        "retired figure in exactly its retired sense"
    )
    assert _retired_24_offenders(bare), "the control sentence must still be caught"
    assert not _retired_24_offenders(true_sentence), (
        "the TRUE computed non-producer sentence is rejected - the guard would force either contorted "
        "phrasing or silence, both evidence-hiding"
    )
    assert not _retired_24_offenders(historical), "a sentence labelling the figure retired is allowed"


def test_hostile_a_live_retired_status_token_is_detected():
    """F-02's guard, attacked over synthetic text so it cannot pass merely because the corpus is
    currently clean. The exact wording that was live in PHASE-OUTPUTS.md must be caught; the same
    token labelled historical must not be."""
    tokens = require_population(_audit()["retired_status_tokens"], "retired status tokens")
    names = {str(t["token"]) for t in tokens}
    assert "COUNT_NEEDS_ADJUDICATION" in names, (
        "the retired status token that caused F-02 left the record"
    )
    live = ("| **Blocked on** | The transition/event completeness finding must be adjudicated first "
            "— COUNT NEEDS ADJUDICATION, 4 classes |")
    labelled = "`COUNT_NEEDS_ADJUDICATION` was the status before the G2 adjudication and is retired."
    assert _retired_token_offenders(live, tokens), (
        "### F-02 IS BACK: the exact PHASE-OUTPUTS.md wording is not detected as a live claim"
    )
    assert not _retired_token_offenders(labelled, tokens), (
        "a token explicitly labelled retired is flagged - that would force erasing history"
    )


# ============================================================ M-4: table partition

def test_the_canonical_table_partition_is_exact_and_disjoint():
    """P3 widened the partition from three classes to five. The doctrine is unchanged: the classes
    must be PAIRWISE disjoint and must together explain EVERY canonical table, by membership and
    not by count - a same-count substitution must still fail. The counts below are asserted only
    after the membership equality, so they document the shape rather than standing in for it."""
    from freight_recon.migrations.phase2_tenant_first import (
        CANONICAL_TENANT_TABLES, TENANT_EXEMPT_TABLES,
    )
    from freight_recon.migrations.phase3_checkpoint import P3_EXEMPT_TABLES, P3_TENANT_TABLES
    from freight_recon.schema import CANONICAL_TABLES

    classes = {
        "migrated": set(CANONICAL_TENANT_TABLES),
        "already_tenant_first": {"autonomous_run_counters"},
        "exempt": set(TENANT_EXEMPT_TABLES),
        "p3_tenant": set(P3_TENANT_TABLES),
        "p3_exempt": set(P3_EXEMPT_TABLES),
    }
    for a, b in itertools.combinations(sorted(classes), 2):
        overlap = classes[a] & classes[b]
        assert not overlap, f"partition classes {a} and {b} overlap: {sorted(overlap)}"

    union = set().union(*classes.values())
    assert set(CANONICAL_TABLES) == union, (
        "the partition no longer explains every canonical table: "
        f"canonical-only={sorted(set(CANONICAL_TABLES) - union)}, "
        f"partition-only={sorted(union - set(CANONICAL_TABLES))}"
    )
    shape = {name: len(members) for name, members in classes.items()}
    assert shape == {"migrated": 7, "already_tenant_first": 1, "exempt": 3,
                     "p3_tenant": 2, "p3_exempt": 1}, f"the partition shape drifted: {shape}"

    text = read(IMPL / "CURRENT.md")
    assert "autonomous_run_counters" in text, (
        "CURRENT.md hides the eighth tenant-first table again (the rehearsal's 7+3-vs-11 finding)"
    )
    for t in sorted(union):
        assert t in text, f"CURRENT.md's partition no longer names {t}"


# ============================================================ M-4: effect-path inventory

def test_the_effect_path_inventory_is_exact_and_fully_classified():
    """M-4, re-grounded at P4. The original guard pinned the SIX live-write paths. P4 has now
    executed the REMOVE_BEFORE_ENABLE disposition on four of them (EP-6/7/9/10), so this guard is
    REPLACED (rule 20) with the post-cutover truth AND a stronger check: the four are proven GONE
    from disk, and the live-write set is pinned to the two ADAPT paths that remain. R-07 stays OPEN
    because those two (plus the two read-by-convention actuator-capable paths) are not yet cut."""
    inv = yaml.safe_load(read(IMPL / "EFFECT-PATH-INVENTORY.yaml"))
    paths = require_population(inv["paths"], "effect paths")
    ids = [p["id"] for p in paths]
    assert len(ids) == len(set(ids)), "duplicate effect-path IDs"

    REMOVED = {"EP-6", "EP-7", "EP-9", "EP-10"}
    # EP-3 left this set at P4: its browser surface is now the read-only navigator and it imports no
    # adapter, so it is no longer a production-reachable live-write path. EP-1 alone remains, and it
    # is the one whose containment is the P12-scale supervised-write integration.
    LIVE = {"EP-1"}
    for p in paths:
        for field in ("path", "external_system", "production_reachable", "enablement",
                      "authority_bypass", "classification", "containment_phase", "disposition"):
            assert field in p, f"{p['id']}: unclassified - missing {field}"
        if p["id"] not in LIVE:
            assert "excluded_from_the_six_because" in p, (
                f"{p['id']}: not a current live-write path but no reason stated"
            )

    # the P4 deletion actually happened: exact removed set, and every removed file is GONE on disk.
    removed = {p["id"] for p in paths if p["classification"] == "REMOVED_AT_P4"}
    assert removed == REMOVED, f"the P4-removed set drifted: {sorted(removed)}"
    removed_pop = require_population(
        [p for p in paths if p["id"] in REMOVED], "P4-removed effect paths"
    )
    for p in removed_pop:
        f = ROOT / p["path"]
        assert not f.exists(), (
            f"{p['id']} is classified REMOVED_AT_P4 but {p['path']} still exists on disk - "
            f"the deletion was recorded but not performed (a false green)"
        )

    # the live-write set shrank from six to exactly the two ADAPT paths still awaiting conversion.
    live = {p["id"] for p in paths if p["classification"] == "PRODUCTION_LIVE_WRITE"}
    assert live == LIVE, f"the production-reachable live-write set drifted: {sorted(live)}"

    # every import-probe candidate from the (shrunk) manifest is still adjudicated here.
    manifest = yaml.safe_load(read(IMPL / "phase-0-baseline-manifest.yaml"))
    probe_scripts = {e["script"] for e in manifest["expected_legacy_paths"]["effect_capable_by_import"]}
    inventory_scripts = {p["path"] for p in paths}
    missing = probe_scripts - inventory_scripts
    assert not missing, f"import-probe candidates left unclassified: {sorted(missing)}"
    # and the manifest no longer lists a deleted path as effect-capable-by-import.
    still_listed = {p["path"] for p in paths if p["id"] in REMOVED} & probe_scripts
    assert not still_listed, (
        f"deleted path(s) still listed as effect-capable-by-import: {sorted(still_listed)}"
    )
    ep14 = next(p for p in paths if p["id"] == "EP-14")
    assert ep14["path"] == "scripts/read_tms_browser_use.py", "the P0-F4 adjudication is gone"
    # R-07's status as this inventory RESTATES it. The canonical record is the baseline manifest;
    # this file is scoped to the live-write adjudication and must AGREE with it rather than drift.
    # Re-pointed at the R-07 closure content commit (rule 20): it asserted the literal "R-07 OPEN"
    # for the whole time that was true, and now asserts the recorded closure together with its
    # bound - because an unbounded CONTAINED in an effect-path inventory reads as enablement.
    recorded = yaml.safe_load(
        read(IMPL / "phase-0-baseline-manifest.yaml"))["expected_legacy_paths"]
    assert recorded["status"] == "CONTAINED", (
        f"the canonical R-07 record reads {recorded['status']!r}"
    )
    assert str(inv["meta"]["risk"]).strip().startswith("R-07 CONTAINED"), (
        "the inventory's meta.risk no longer agrees with the canonical R-07 CONTAINED record: "
        f"{str(inv['meta']['risk'])[:80]!r}"
    )
    assert re.search(r"NOT mean any production write is enabled",
                     " ".join(str(inv["meta"]["risk"]).split()), re.I), (
        "the inventory records R-07 CONTAINED without the bound - containment is not enablement"
    )


# ============================================================ M-1: full graph consistency

def test_the_implementation_graph_is_consistent_and_protects_the_safety_wall():
    units = yaml.safe_load(read(IMPL / "IMPLEMENTATION-REGISTRY.yaml"))["units"]
    by_id = {u["unit_id"]: u for u in units}
    ids = set(by_id)
    edges = 0
    for u in units:
        for d in u["dependencies"]:
            assert d in ids, f"{u['unit_id']} depends on unknown {d}"
            edges += 1
        assert u["unlocked_by"] == u["dependencies"], (
            f"{u['unit_id']}: unlocked_by diverged from dependencies - the derived view drifted"
        )
        expected_dependents = sorted([v["unit_id"] for v in units if u["unit_id"] in v["dependencies"]])
        assert sorted(u["blocks"]) == expected_dependents, (
            f"{u['unit_id']}: blocks {u['blocks']} != actual dependents {expected_dependents}"
        )
        assert sorted(u["next_units_unlocked"]) == expected_dependents, (
            f"{u['unit_id']}: next_units_unlocked diverged from actual dependents"
        )
    assert edges >= 16, f"only {edges} dependency edges - the graph collapsed"
    # acyclic
    state: dict[str, int] = {}
    def visit(n):
        if state.get(n) == 1:
            raise AssertionError(f"dependency cycle through {n}")
        if state.get(n) == 2:
            return
        state[n] = 1
        for d in by_id[n]["dependencies"]:
            visit(d)
        state[n] = 2
    for n in ids:
        visit(n)
    # the safety wall
    assert "U-HANDOFF-1" in by_id["P3"]["dependencies"], "P3 no longer requires the rehearsal gate"
    assert "U-REBASELINE-1" in by_id["P3"]["dependencies"], (
        "P3 no longer requires the founder rebaseline (U-HANDOFF-1D registration)"
    )
    assert by_id["P4"]["dependencies"] == ["P3"], "P4 can begin without P3"
    assert by_id["P5"]["dependencies"] == ["P4"], (
        "P5 can begin without P4 - the rehearsal's exact bypass finding (P5 deps were [P2])"
    )
    ready = [u["unit_id"] for u in units if u["status"] == "READY"]
    # P3 adjudicated COMPLETE -> P4 READY; P4 then adjudicated COMPLETE -> P5 READY. The safety
    # wall above is what makes this legal: P5 may only be selected because P4 is genuinely COMPLETE.
    assert ready == ["P5"], f"READY set drifted: {ready}"
    assert by_id["P4"]["status"] == "COMPLETE", (
        f"P5 is READY while P4 is {by_id['P4']['status']} - the containment wall is bypassed"
    )
    p4_criteria = by_id["P4"].get("acceptance_criteria")
    assert p4_criteria and sum(int(c["weight"]) for c in p4_criteria) == 100 and all(
        str(c["result"]).upper() == "PASS" for c in p4_criteria
    ), "P4 unlocked P5 without a real, full-weight, fully-PASS weighted acceptance contract"


# ============================================================ H-3 / H-4: authority

def test_registry_md_carries_no_independent_status_authority():
    text = read(IMPL / "registry.md")
    assert "INDEX ONLY — NO INDEPENDENT STATUS AUTHORITY" in text, (
        "registry.md lost its authority banner (the rehearsal found it contradicting the "
        "canonical registry on Phase 2)"
    )
    # DELEGATED at the R-01/R-02 remediation: only a SELF-LABELLING <details> block is quarantined.
    # registry.md's block labels itself "Historical status table (pre-Blocker snapshot - WRONG
    # about Phase 2; retained as evidence)", so it still exempts - by saying so, not by existing.
    sys.path.insert(0, str(ROOT / "eval"))
    from control import status_claims

    live = status_claims.strip_historical_blocks(text)
    live = "\n".join(l for l in live.split("\n") if not l.startswith(">"))  # the banner DESCRIBES the defect
    assert not re.search(r"Phase 2[^|\n]{0,40}IN PROGRESS", live), (
        "registry.md asserts Phase 2 IN PROGRESS outside the quarantined historical block"
    )
    assert not re.search(r"(begin|Blocking:)[^\n]{0,60}U2\.6B\b", live), (
        "registry.md carries live instructions to begin U2.6B"
    )


ROOT_ALLOWED_NON_AUTHORITY = {
    # tooling/config files a root scan must not flag; никаких roadmap semantics
    ".gitignore", "pyproject.toml", ".env.example", "LICENSE", "Makefile",
    "requirements.txt",
}


def test_every_root_document_is_classified_dynamically():
    """H-4: DISCOVERED, never enumerated. A new root file that smells like authority (roadmap,
    stages, product, status, agent instructions) must be classified in the authority map or fail."""
    amap = read(ROOT / "docs" / "CANONICAL-DOCUMENTS.md")
    offenders = []
    candidates = [p for p in ROOT.iterdir()
                  if p.is_file() and p.suffix in (".md", ".txt") and p.name not in ROOT_ALLOWED_NON_AUTHORITY]
    require_population(candidates, "root documents")
    for p in candidates:
        if p.name not in amap:
            offenders.append(f"{p.name}: root document unclassified by the authority map")
            continue
        text = read(p)
        for m in re.finditer(r"Stage [1-8] —|8-stage roadmap", text):
            ctx = text[max(0, m.start() - 250): m.end() + 250]
            if not re.search(r"superseded|historical|SUPERSEDED", ctx, re.I):
                offenders.append(f"{p.name}: presents the stage roadmap without marking it superseded")
                break
    assert not offenders, "unclassified or unbannered root authority (the stages.txt defect):\n  " + "\n  ".join(offenders)
    assert not (ROOT / "stages.txt").exists(), "stages.txt returned to the repository root"


# ============================================================ M-2: banners, dynamically

def _classified_from_map(cls_names: tuple[str, ...]) -> list[str]:
    amap = read(ROOT / "docs" / "CANONICAL-DOCUMENTS.md")
    out = []
    for ln in amap.split("\n"):
        if not ln.strip().startswith("|"):
            continue
        cells = [c.strip() for c in ln.strip().strip("|").split("|")]
        if len(cells) >= 2 and any(c in cells[1] for c in cls_names):
            out.extend(re.findall(r"`([A-Za-z0-9_.]+\.(?:md|txt))`", cells[0]))
    return sorted(set(out))


def test_every_superseded_or_quarantined_document_is_disarmed_in_file():
    """M-2: derived from the authority map's OWN classifications - not a hand-enumerated list.
    Classifying a new file SUPERSEDED without bannering it fails immediately."""
    names = require_population(
        _classified_from_map(("SUPERSEDED", "QUARANTINED_GUIDANCE")),
        "superseded/quarantined documents",
    )
    offenders = []
    for name in names:
        p = ROOT / "docs" / name
        if not p.exists():
            offenders.append(f"{name}: classified but missing")
            continue
        head = read(p)[:1200]
        if "DO NOT FOLLOW" not in head:
            offenders.append(f"{name}: no in-file disarming banner - a grep-first reader sees old authority")
    assert not offenders, "superseded documents without in-file banners:\n  " + "\n  ".join(offenders)


def test_no_docs_root_file_claims_to_be_the_source_of_truth_unbannered():
    offenders = []
    files = require_population(sorted((ROOT / "docs").glob("*.md")), "docs-root files")
    for p in files:
        if p.name == "CANONICAL-DOCUMENTS.md":
            continue  # the map IS the authority document
        text = read(p)
        if re.search(r"[Tt]his (is|file is|doc(ument)? is) the (canonical|single source|source of truth)", text):
            if "DO NOT FOLLOW" not in text[:1200]:
                offenders.append(p.name)
    assert not offenders, f"docs-root files self-claiming authority without a banner: {offenders}"


# ============================================================ M-3: frontmatter, separately from body

def _frontmatter(p: Path) -> str:
    text = read(p)
    m = re.match(r"---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


def test_agent_frontmatter_describes_the_current_program_not_the_stages():
    """The listing shows frontmatter WITHOUT the body's banner, so the frontmatter itself must
    be clean - the rehearsal found the steward advertising the 8-stage roadmap there."""
    files = require_population(sorted(ROOT.glob(".claude/agents/*.md")), "claude agent definitions")
    for p in files:
        fm = _frontmatter(p)
        assert fm, f"{p.name}: no frontmatter"
        assert not re.search(r"8-stage|Stage [1-8]\b|extraction proof", fm, re.I), (
            f"{p.name}: frontmatter advertises the superseded stage roadmap"
        )
    steward = _frontmatter(ROOT / ".claude/agents/roadmap-steward.md")
    assert re.search(r"P0-P14|P0–P14", steward), (
        "the steward's frontmatter no longer names the current implementation program"
    )
    assert re.search(r"CURRENT\.md", steward), (
        "the steward's frontmatter no longer names the status authority"
    )
    assert re.search(r"Phase 3 does not start automatically", steward), (
        "the steward's frontmatter lost the no-automatic-Phase-3 statement"
    )
    # codex surfaces have no frontmatter; their first visible lines must be the compat pointer
    for p in sorted(ROOT.glob(".codex/agents/*.md")):
        head = read(p)[:300]
        assert "COMPATIBILITY SURFACE" in head, f"{p.name}: stale-capable head without compat pointer"


# ============================================================ status-result truthfulness (unit level)

def test_the_finalizer_refuses_count_arguments():
    """The 1A finalizer accepted --passed on faith; the 1B one read a pre-existing artifact,
    which U-HANDOFF-1C proved forgeable. The canonical finalizer now EXECUTES everything and
    offers no count flag; the superseded script is a refusing shim, not a second route."""
    src = read(ROOT / "scripts" / "finalize_status.py")
    assert not re.search(r"add_argument\(\s*['\"]--passed", src), (
        "the finalizer accepts hand-supplied counts again"
    )
    assert "_step_run_suite" in src and "_step_run_gate" in src, (
        "the finalizer no longer executes the suite and gate itself"
    )
    shim = read(ROOT / "scripts" / "update_current_status.py")
    assert "REFUSED" in shim and "finalize_status.py" in shim, (
        "the superseded finalizer no longer refuses - a weaker second route exists"
    )


def test_the_runner_refuses_dirty_trees():
    src = read(ROOT / "scripts" / "run_canonical_suite.py")
    assert re.search(r"REFUSED.{0,80}dirty", src, re.S | re.I), (
        "the canonical runner no longer refuses dirty working trees - developer-local results "
        "could re-enter the record"
    )


def test_collection_totals_alone_cannot_satisfy_status_reality():
    """Acceptance 12: the guard must CALL the artifact validator inside the artifact-backing
    test - by AST, because a substring check was satisfied by the import line while the actual
    call had been deleted (mutation B-6 proved it)."""
    tree = ast.parse(read(ROOT / "eval" / "tests" / "test_status_reality.py"))
    fn = next((n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)
               and n.name == "test_the_status_record_is_backed_by_a_real_suite_result"), None)
    assert fn is not None, "the artifact-backing guard is gone from status-reality"
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call)
             and getattr(n.func, "id", getattr(n.func, "attr", "")) == "artifact_consistency_errors"]
    assert calls, (
        "status-reality's artifact-backing test no longer CALLS artifact_consistency_errors - "
        "collection-only verification is the exact false green the clean-clone rehearsal found"
    )
    assert "exit_status" in read(ROOT / "scripts" / "suite_result.py")


# ============================================================ authority-map family coverage

def test_every_implementation_document_is_classified_or_family_covered():
    amap = read(ROOT / "docs" / "CANONICAL-DOCUMENTS.md")
    assert "FAMILY RULE" in amap, "the review family rule left the authority map"
    offenders = []
    for p in sorted(IMPL.glob("*.md")):
        if "review" in p.name or p.name.startswith(("u2-6", "u-handoff", "phase-0-i", "phase-1", "phase-2")):
            continue  # covered by the review family rule
        if p.name not in amap:
            offenders.append(p.name)
    assert not offenders, f"implementation documents neither classified nor family-covered: {offenders}"


# ============================================================ M-4: no brittle line citations

def test_control_documents_cite_the_kb_finding_by_symbol_not_line_number():
    """The recorded citation `action_callback.py:1639` had already drifted to line 1657 when the
    rehearsal checked - a line number goes stale on any edit above it. Control documents cite the
    symbol; THIS guard verifies the actual sites still exist, mechanically."""
    for f in [ROOT / "CLAUDE.md", IMPL / "CURRENT.md", IMPL / "LEGACY-DISPOSITION.md",
              ROOT / "README.md", ROOT / "ARCHITECTURE.md"]:
        assert not re.search(r"action_callback\.py:\d+", read(f)), (
            f"{f.name} cites the KB finding by line number again - it was stale within two commits"
        )
    src = read(ROOT / "src" / "freight_recon" / "action_callback.py")
    assert 'tenant="default"' in src and "_learn_correction" in src, (
        "the KB default-tenant site moved or closed - update the finding truthfully, do not "
        "let the citation dangle"
    )
    ops = read(ROOT / "src" / "freight_recon" / "ops_control.py")
    assert ops.count('tenant="default"') == 5, (
        f"ops_control.py now has {ops.count(chr(39) + 'tenant=' + chr(39))} default-tenant sites, "
        "not the recorded 5 - update the finding truthfully"
    )


def test_handoff_10_keeps_the_rehearsal_repository_only():
    """The criterion must distinguish DESCRIBING the broad posture from OPERATING under it - a
    rehearsal that claims live external tools has broken its own evidence boundary."""
    text = read(IMPL / "U-HANDOFF-1-ACCEPTANCE.yaml")
    m = re.search(r"- id: HANDOFF-10\n(.*?)- id: HANDOFF-11", text, re.S)
    assert m, "HANDOFF-10 missing"
    body = m.group(1)
    assert re.search(r"repository-only", body), (
        "HANDOFF-10 no longer requires the rehearsal itself to remain repository-only"
    )
    assert re.search(r"WITHOUT claiming", body), (
        "HANDOFF-10 lost the describe-vs-operate distinction"
    )
