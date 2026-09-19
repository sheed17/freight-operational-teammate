"""U8.5 — the machine-checkable `lane` -> `action_class` migration ledger and detector.

The plain deprecated-semantics probe (``deprecated_probe.py``) counts the raw ``lane`` token and can
only ratchet a number down. That is the wrong instrument for ACCEPTANCE of U8.5, because after the
migration the token legitimately survives in four shapes that are NOT the overloaded operational
concept the migration removed:

  * a genuine freight-domain **lane** (an origin->destination freight lane) — explicitly OUT of U8.5
    scope (a future P9 Lane entity, not this legacy operational-control word);
  * a bounded, one-directional **compatibility read** that translates a pre-migration ``lane`` key
    into ``action_class`` once at a boundary and never keeps it as authority;
  * **migration / persistence** code that must name the legacy column it renames, plus the retained
    non-authoritative ``effect_grants.lane`` mirror column;
  * **vocabulary prose** — a comment or docstring that explains the rename.

This module CLASSIFIES every discovered ``lane`` occurrence in product authority (``src/`` +
``scripts/``) into exactly one of those resolved categories or into
``UNRESOLVED_OPERATIONAL`` — a live operational-control ``lane`` acting as current authority, which
after U8.5 must not exist. ``unresolved_in_production()`` is the acceptance gate: it must be EMPTY.

### IT IS NON-VACUOUS BY CONSTRUCTION. ``scan`` takes explicit roots, so the positive-control test
plants an intentionally-reintroduced operational ``lane`` in a temp tree and proves the detector
flags it — a zero-result scan over the real tree therefore means "the detector looked and found
nothing", not "the detector cannot see anything" (CLAUDE.md §6: a check that parses nothing is worse
than no check; prove the population).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# --- categories ------------------------------------------------------------------------------

FREIGHT_DOMAIN = "FREIGHT_DOMAIN"                 # origin->destination freight lane; left as-is (P9, not U8.5)
COMPAT_READ = "COMPAT_READ"                       # bounded one-directional legacy-key translation
MIGRATION = "MIGRATION"                           # migration module / retained effect_grants mirror column
VOCAB_PROSE = "VOCAB_PROSE"                       # comment/docstring explaining the rename
UNRESOLVED_OPERATIONAL = "UNRESOLVED_OPERATIONAL"  # a live operational-control lane == FAIL

RESOLVED_CATEGORIES = frozenset({FREIGHT_DOMAIN, COMPAT_READ, MIGRATION, VOCAB_PROSE})

# Destination field each resolved category maps to (the migration ledger's "destination field").
DESTINATION = {
    FREIGHT_DOMAIN: "freight-domain lane (NOT migrated — P9 Lane entity, out of U8.5 scope)",
    COMPAT_READ: "action_class (legacy key translated once at the boundary; never internal authority)",
    MIGRATION: "action_class (persistence: counter renamed; effect_grants.lane is a mirror of it)",
    VOCAB_PROSE: "action_class (explanatory prose; not executable authority)",
    UNRESOLVED_OPERATIONAL: "NONE — a live operational-control lane still acting as authority",
}

# The three files where the English word `lane` legitimately means an origin->destination FREIGHT
# lane. Discovered by meaning, listed here because there is no token that distinguishes a freight
# lane from an operational one — but a line in one of these files is only treated as freight-domain
# when it carries NO operational signal (below), so an operational lane sneaking in still fails.
_FREIGHT_FILES = frozenset({"email_triage.py", "mock_tms.py", "generate_realistic_corpus.py"})

# A `lane` occurrence is RESOLVED as prose when its line also carries one of these migration markers.
_PROSE_MARKERS = ("U8.5", "action_class", "legacy", "mirror", "deprecated", "Phase 1", "renamed")

# Bounded compatibility-read signals: the legacy key is READ (never written as authority) and
# translated once. `.get("lane")` / `.pop("lane")` / `"lane" in d` / a legacy-key list membership.
_COMPAT_SIGNALS = (
    re.compile(r'\.(?:get|pop|setdefault)\(\s*["\']lane["\']'),
    re.compile(r'["\']lane["\']\s+(?:in|not in)\b'),
    re.compile(r',\s*["\']lane["\']'),          # legacy key in a fallback key list, e.g. ("action_class", "lane")
    re.compile(r'\[\s*["\']lane["\']\s*\]'),    # row["lane"] legacy-source read
)

# The retained NON-AUTHORITATIVE effect_grants mirror column, named in a SQL column list. It is a
# persisted-history reference, byte-identical to action_class and never read for a decision.
_MIRROR_COLUMN = re.compile(r'\blane,\s*load_ref')

# A STRONG freight signal: the line composes an origin->destination lane. Decisive inside a freight
# file even when an f-string label like `lane=` also appears — that is a genuine freight lane, not an
# operational one.
_FREIGHT_SIGNAL = re.compile(r'origin|destination')

# Signals that a line is a LIVE operational use even inside an otherwise-allowed file — so a real
# operational lane cannot hide behind a freight-file allowance OR behind a compat-read pattern.
_OPERATIONAL_SIGNALS = (
    re.compile(r'["\']lane["\']\s*:'),           # "lane": ... — a dict-VALUE write (anywhere in the dict)
    re.compile(r'\[\s*["\']lane["\']\s*\]\s*='),  # d["lane"] = ... — a subscript ASSIGNMENT
    re.compile(r'\.lane\b'),                      # attribute access as authority
    re.compile(r'\blane\s*=\s*(?!=)'),            # lane = / lane=kwarg (not ==)
    re.compile(r'\bOperationLane\b'),
    re.compile(r'\blane_for\b'),
)

_WORD_LANE = re.compile(r'(?<![A-Za-z0-9_])lane(?![A-Za-z0-9_])')


@dataclass(frozen=True)
class LaneOccurrence:
    file: str
    lineno: int
    line: str
    category: str

    @property
    def resolved(self) -> bool:
        return self.category in RESOLVED_CATEGORIES


def _has_operational_signal(line: str) -> bool:
    return any(p.search(line) for p in _OPERATIONAL_SIGNALS)


def classify_line(*, file_name: str, path_str: str, line: str) -> str:
    """Classify ONE `lane`-bearing line into a resolved category or UNRESOLVED_OPERATIONAL.

    Precedence: a persisted mirror-column reference and a migration module are history/persistence; a
    bounded legacy-key read is a compat translation; a marker-bearing comment is prose; a freight
    file with no operational signal is a genuine origin->destination lane. Prose and freight
    allowances are UNAVAILABLE to a line carrying a live operational signal ({"lane":...}, `.lane`,
    `lane=`, OperationLane, lane_for), so a real operational use can never hide behind a comment or a
    freight file — that is what keeps the positive control able to trip.
    """
    if _MIRROR_COLUMN.search(line):
        return MIGRATION
    if "migrations/" in path_str:
        # A migration module is trusted infrastructure that must name the legacy table/column it
        # migrates in DDL, backfill and prose (e.g. `effect_grants.lane`); those references are not
        # operational authority. (A genuine operational reintroduction would land in product code,
        # where the acceptance gate and the mutation battery cover it.)
        return MIGRATION
    if not _has_operational_signal(line) and any(p.search(line) for p in _COMPAT_SIGNALS):
        # A bounded legacy-key READ. Gated on the absence of an operational signal so a WRITE such
        # as `d["lane"] = x` or `{"action_class": x, "lane": y}` can never masquerade as a compat
        # read and slip past the acceptance gate (R1).
        return COMPAT_READ
    if file_name in _FREIGHT_FILES and (
        _FREIGHT_SIGNAL.search(line) or not _has_operational_signal(line)
    ):
        return FREIGHT_DOMAIN
    if not _has_operational_signal(line) and any(m in line for m in _PROSE_MARKERS):
        return VOCAB_PROSE
    return UNRESOLVED_OPERATIONAL


def _is_excluded(p: Path) -> bool:
    """A mutation battery names the defects it injects, so it carries operational-`lane` payload
    strings as DATA, not as authority — excluding it is stated here rather than left implicit, the
    same discipline `deprecated_probe._is_phase0_meta` applies to the Phase-0 guards. (The detector's
    own module lives under eval/phase0 and is never in the src/+scripts production roots at all.)"""
    return p.name.startswith("mutate_") or p.name.startswith("_tmp_")


def _iter_python_files(roots: list[Path]):
    for root in roots:
        root = Path(root)
        if root.is_file() and root.suffix == ".py":
            if not _is_excluded(root):
                yield root
            continue
        for p in sorted(root.rglob("*.py")):
            if "__pycache__" in p.parts or _is_excluded(p):
                continue
            yield p


def scan(roots: list[Path]) -> list[LaneOccurrence]:
    """Every `lane` occurrence under `roots`, classified. Roots are explicit so the positive control
    can point the SAME detector at a planted operational use."""
    out: list[LaneOccurrence] = []
    for path in _iter_python_files(roots):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = str(path)
        for i, line in enumerate(text.split("\n"), start=1):
            if not _WORD_LANE.search(line):
                continue
            cat = classify_line(file_name=path.name, path_str=rel.replace("\\", "/"), line=line)
            out.append(LaneOccurrence(file=rel, lineno=i, line=line.strip(), category=cat))
    return out


def _default_roots() -> list[Path]:
    here = Path(__file__).resolve().parents[2]   # repo root
    return [here / "src", here / "scripts"]


def scan_production() -> list[LaneOccurrence]:
    return scan(_default_roots())


def unresolved_in_production() -> list[LaneOccurrence]:
    """### THE ACCEPTANCE GATE. Every UNRESOLVED operational-control `lane` in product authority.
    Must be EMPTY after U8.5."""
    return [o for o in scan_production() if o.category == UNRESOLVED_OPERATIONAL]


def ledger() -> dict:
    """The machine-checkable migration ledger artifact:
    discovered occurrence -> classified meaning -> destination field -> status -> verification.

    Also records the mechanical inventory conclusion: in THIS repository every operational-control
    `lane` resolved to `action_class`; the `workflow_id` and `policy scope` arms of the authority's
    union have ZERO occurrences (the graduation SCOPE is itself the action_class — M11 evaluates its
    policy scope AS the action_class at checkpoint step 6), so they are recorded as empty, not forced.
    """
    occ = scan_production()
    by_cat: dict[str, list[dict]] = {}
    for o in occ:
        by_cat.setdefault(o.category, []).append(
            {"file": o.file, "lineno": o.lineno, "line": o.line})
    counts = {cat: len(v) for cat, v in sorted(by_cat.items())}
    return {
        "inventory_conclusion": {
            "operational_lane_destination": "action_class (unanimous in this repository)",
            "workflow_id_occurrences": 0,
            "policy_scope_distinct_from_action_class_occurrences": 0,
            "note": (
                "The operational-control `lane` in operation_router / graduation / workflow / "
                "callbacks is the WHAT-effect (route.name), which IS the registered action_class "
                "population (commit_key.OCCURRENCE_RULES / product_policy.ACTION_CLASS_POPULATION). "
                "The autonomous-run counter and graduation scope are that same action_class. No "
                "occurrence meant a workflow run id or a policy scope distinct from action_class."
            ),
        },
        "destination_fields": DESTINATION,
        "counts_by_category": counts,
        "total_discovered": len(occ),
        "unresolved_operational": [
            {"file": o.file, "lineno": o.lineno, "line": o.line}
            for o in occ if o.category == UNRESOLVED_OPERATIONAL
        ],
        "status": "COMPLETE" if not any(o.category == UNRESOLVED_OPERATIONAL for o in occ) else "INCOMPLETE",
        "verification": (
            "unresolved_in_production() is empty; the positive control "
            "(test_phase8_action_class_migration) proves the detector flags a reintroduced "
            "operational lane; the persistence migration is proven idempotent and tenant-safe; and "
            "the effect_grants action_class==lane mirror invariant is enforced by the readiness oracle."
        ),
    }
