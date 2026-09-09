"""### THE P6 MACHINE POPULATION, DISCOVERED RATHER THAN LISTED.

`foundational-machine-acceptance.md` requires a `STRUCTURAL` case, `AC-MACH-000`, that *"enumerates
the transition tables FROM THE IMPLEMENTATION's declarative data and asserts a bijection with the 134
spec rows"*, with the oracle *"EXACT SET EQUALITY of transition identifiers, not a count. A count
match with different members MUST fail."*

### EVERY POPULATION HERE IS DISCOVERED, AND THAT IS THE WHOLE POINT. A guard whose denominator is a
filename list is a guard that goes quietly green on the day a machine is deleted — the list shrinks
with the tree and nothing notices. So:

  * the SPECIFICATION population is every `*.machine.md` under `docs/specifications/state-machines/`,
    and its rows are §14's table parsed out of the file;
  * the ACCEPTANCE denominators are parsed out of `foundational-machine-acceptance.md`'s own coverage
    table, so `134` is read from the authority rather than retyped into a test;
  * the IMPLEMENTATION population is every module under `src/freight_recon/` that declares a
    module-level `TRANSITIONS`, found by parsing the source, not by naming the files;
  * the three are joined by the TRANSITION-ID PREFIX each side derives for itself.

A machine, a specification or a module that silently disappears changes one of those three counts and
fails a guard. That is the property this module exists to make available."""

from __future__ import annotations

import ast
import importlib
import pathlib
import re
from dataclasses import dataclass
from enum import Enum
from types import ModuleType
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parents[2]
SPEC_DIR = ROOT / "docs" / "specifications" / "state-machines"
SRC_DIR = ROOT / "src" / "freight_recon"
ACCEPTANCE = ROOT / "docs" / "specifications" / "acceptance" / "foundational-machine-acceptance.md"

# A §14 row opens with the transition id in bold: `| **WI-1** | ... |`. Nothing else in those files
# opens a table cell with a bolded identifier of that shape.
_ROW_RE = re.compile(r"^\|\s*\*\*([A-Z]{2}-[0-9A-Za-z]+)\*\*\s*\|")
_SECTION_RE = re.compile(r"^#+\s*(\d+)\.")
# `| M1 Work Item | 14 | ...` — the acceptance file's own coverage table.
_ACCEPT_ROW_RE = re.compile(r"^\|\s*(?:\*\*)?M(\d{1,2})\b[^|]*\|\s*(?:\*\*)?(\d+)(?:\*\*)?\s*\|")
_ACCEPT_TOTAL_RE = re.compile(r"^\|\s*\*\*Total\*\*\s*\|[^|]*?(\d+)[^|]*\|")


# --------------------------------------------------------------------------- the specification side

@dataclass(frozen=True)
class CanonicalMachine:
    """One `*.machine.md`, reduced to the §14 identifiers it enumerates."""

    number: int                     # the NN of the filename — M1..M13
    prefix: str                     # WI, PL, EF, ... — derived from the rows, never assumed
    spec_path: pathlib.Path
    ids: tuple[str, ...]

    @property
    def name(self) -> str:
        return f"M{self.number}"


def _section_14(path: pathlib.Path) -> list[str]:
    """The lines of §14, bounded by the next numbered section. Raises if §14 is absent."""
    lines = path.read_text(encoding="utf-8").splitlines()
    start = None
    for i, line in enumerate(lines):
        m = _SECTION_RE.match(line)
        if m and int(m.group(1)) == 14:
            start = i
            break
    if start is None:
        raise AssertionError(
            f"{path.name} has no '## 14.' section. Every machine specification carries its transition "
            f"table at §14; a file without one cannot contribute rows to the canonical population, "
            f"and a canonical population that quietly shrinks is the failure this guard exists to "
            f"prevent.")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        m = _SECTION_RE.match(lines[i])
        if m and int(m.group(1)) > 14:
            end = i
            break
    return lines[start:end]


def parse_spec(path: pathlib.Path) -> CanonicalMachine:
    ids = tuple(m.group(1) for line in _section_14(path) if (m := _ROW_RE.match(line)))
    if not ids:
        raise AssertionError(f"{path.name} §14 yielded no transition rows — the parser or the file moved.")
    prefixes = {i.split("-", 1)[0] for i in ids}
    if len(prefixes) != 1:
        raise AssertionError(
            f"{path.name} §14 mixes transition-id prefixes {sorted(prefixes)}; one machine file owns "
            f"exactly one prefix, and the prefix is how the specification is joined to its module.")
    number = int(path.name.split("-", 1)[0])
    return CanonicalMachine(number=number, prefix=prefixes.pop(), spec_path=path, ids=ids)


def discover_specs() -> tuple[CanonicalMachine, ...]:
    """Every machine specification on disk, in file order. Discovered — not named."""
    paths = sorted(SPEC_DIR.glob("*.machine.md"))
    if not paths:
        raise AssertionError(f"no *.machine.md under {SPEC_DIR} — the specification corpus is gone.")
    return tuple(parse_spec(p) for p in paths)


def acceptance_denominators() -> tuple[dict[str, int], int]:
    """The per-machine counts and the total, PARSED OUT OF `foundational-machine-acceptance.md`.

    The 134 is the authority's number, read from the authority. Retyping it into a test would make the
    test agree with itself on the day the authority changed."""
    per: dict[str, int] = {}
    total: int | None = None
    for line in ACCEPTANCE.read_text(encoding="utf-8").splitlines():
        m = _ACCEPT_ROW_RE.match(line)
        if m:
            per[f"M{int(m.group(1))}"] = int(m.group(2))
            continue
        t = _ACCEPT_TOTAL_RE.match(line)
        if t and total is None:
            total = int(t.group(1))
    if not per or total is None:
        raise AssertionError(
            f"{ACCEPTANCE.name}'s coverage table did not parse (rows={len(per)}, total={total}). The "
            f"denominators this phase is measured against live in that table; a guard that cannot read "
            f"it is a guard measuring nothing.")
    return per, total


# ------------------------------------------------------------------------- the implementation side

@dataclass(frozen=True)
class NormalizedRow:
    """One implementation transition row, reduced to the fields every machine's table agrees on.

    The thirteen `TransitionRow` dataclasses are not identical — M13 spells a single `from_state`, M6
    a single `trigger`, and several carry machine-specific flags. Normalising here is what lets ONE
    guard read all thirteen instead of thirteen guards reading one each."""

    machine: str
    id: str
    from_states: tuple[str, ...]
    to_state: str | None
    triggers: tuple[str, ...]
    creates: bool
    illegal: bool
    delegation: bool
    fireable: bool          # independently fireable: not a delegation, not a declared refusal
    events: tuple[str, ...]  # the canonical events this row emits, however its table spells them
    # ### WHY A ROW IS NOT IN THE (state × trigger) SWEEP — READ OFF THE ROW, NEVER OFF A LIST HERE.
    # `None` means the row IS swept. Every other value is a field the machine's own table declares,
    # which is what makes this an exclusion the SPECIFICATION owns rather than a hand-maintained
    # exception population in a test. See `_sweep_exclusion`.
    excluded: str | None
    raw: Any


def _value(state: Any) -> str | None:
    if state is None:
        return None
    return state.value if isinstance(state, Enum) else str(state)


def _declared_events(row: Any) -> tuple[str, ...]:
    """The events a row emits, whichever of the three spellings its machine uses (`events`,
    `event_name`, `event`). An illegal or delegating row declares none."""
    for attr in ("events", "event_name", "event"):
        if hasattr(row, attr):
            value = getattr(row, attr)
            if value is None:
                return ()
            if isinstance(value, (tuple, list)):
                return tuple(str(v) for v in value)
            return (str(value),) if value else ()
    return ()


def _sweep_exclusion(row: Any, *, illegal: bool, delegation: bool, creates: bool,
                     triggers: tuple[Any, ...]) -> str | None:
    """Why this row cannot appear in a (state × trigger) pair — or `None` if it can.

    ### EVERY REASON IS A DECLARED FIELD OF THE ROW. `AC-MACH-000`'s companion requirement is that no
    machine keeps a hand-maintained exception population; a test that listed "except EF-2, PL-12, …"
    would BE that population. These six reasons are read off the tables:

      * `illegal`            — §14 declares the row ILLEGAL (IB-5x, PL-15x, EF-5x, CM-5x, BR-5).
      * `delegation`         — the row IS another row reached from a further state (WI-14, CF-6);
                               the delegation has already widened its target's from-set.
      * `creation`           — the row has no from-state, so no (state, trigger) pair reaches it.
      * `no declared trigger`— the row declares none (PL-12: "SAME commit as verify"), so it is not
                               a step a caller may take.
      * `kernel_path`        — M3's mint/claim/revoke/expire rows are entered through the effect
                               kernel, not through the ordinary transition path.
      * `refusal_only`       — the row emits and moves nothing (CM-1r, EF-2f)."""
    if illegal:
        return "illegal"
    if delegation:
        return "delegation"
    if creates:
        return "creation"
    if not triggers:
        return "no declared trigger"
    if getattr(row, "kernel_path", None) is not None:
        return f"kernel_path={getattr(row, 'kernel_path')!r}"
    if getattr(row, "refusal_only", False):
        return "refusal_only"
    return None


def _normalize(machine: str, row: Any) -> NormalizedRow:
    from_states = getattr(row, "from_states", None)
    if from_states is None:
        one = getattr(row, "from_state", None)
        from_states = () if one is None else (one,)
    triggers = getattr(row, "triggers", None)
    if triggers is None:
        one = getattr(row, "trigger", None)
        triggers = () if one is None else (one,)
    illegal = bool(getattr(row, "illegal", False)
                   or getattr(row, "non_producing_reason", None) is not None)
    delegation = bool(getattr(row, "delegates_to", ()) or getattr(row, "is_delegation", False))
    creates = bool(getattr(row, "creates", False)) or not from_states
    fireable = getattr(row, "independently_fireable", None)
    if fireable is None:
        fireable = not (illegal or delegation or getattr(row, "refusal_only", False))
    return NormalizedRow(
        machine=machine, id=row.id,
        from_states=tuple(str(_value(s)) for s in from_states),
        to_state=_value(getattr(row, "to_state", None)),
        triggers=tuple(str(_value(t)) for t in triggers),
        creates=creates, illegal=illegal, delegation=delegation,
        fireable=bool(fireable) and not creates, events=_declared_events(row),
        excluded=_sweep_exclusion(row, illegal=illegal, delegation=delegation, creates=creates,
                                  triggers=tuple(triggers)),
        raw=row)


@dataclass(frozen=True)
class ImplMachine:
    """One implementation module that declares a §14 table."""

    prefix: str
    module_name: str
    module: ModuleType
    rows: tuple[NormalizedRow, ...]

    @property
    def ids(self) -> tuple[str, ...]:
        return tuple(r.id for r in self.rows)


def _declares_transitions(path: pathlib.Path) -> bool:
    """Does this module assign a module-level `TRANSITIONS`? Read off the SOURCE, so discovery never
    depends on importing every module in the package to find out."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError:
        return False
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for t in targets:
            if isinstance(t, ast.Name) and t.id == "TRANSITIONS":
                return True
    return False


def discover_machine_modules() -> tuple[ImplMachine, ...]:
    """Every module under `src/freight_recon/` that declares a §14 transition table.

    ### THIS IS THE HALF THE PREVIOUS GUARD DID NOT HAVE. A brittle filename list cannot fail when a
    machine module is deleted; a discovered population loses a prefix and the bijection breaks."""
    found: list[ImplMachine] = []
    for path in sorted(SRC_DIR.glob("*.py")):
        if path.name.startswith("_") or not _declares_transitions(path):
            continue
        module = importlib.import_module(f"freight_recon.{path.stem}")
        table = getattr(module, "TRANSITIONS", ())
        if not table or not all(hasattr(r, "id") for r in table):
            continue
        prefixes = {r.id.split("-", 1)[0] for r in table}
        if len(prefixes) != 1:
            raise AssertionError(
                f"freight_recon.{path.stem}'s TRANSITIONS mixes id prefixes {sorted(prefixes)}; one "
                f"module owns exactly one machine.")
        prefix = prefixes.pop()
        found.append(ImplMachine(
            prefix=prefix, module_name=path.stem, module=module,
            rows=tuple(_normalize(prefix, r) for r in table)))
    if not found:
        raise AssertionError(f"no module under {SRC_DIR} declares a TRANSITIONS table.")
    return tuple(found)


# --------------------------------------------------------------------------------- the joined view

@dataclass(frozen=True)
class Machine:
    """One canonical machine, with both sides of it."""

    spec: CanonicalMachine
    impl: ImplMachine

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def label(self) -> str:
        return f"{self.spec.name}/{self.spec.prefix}"


def join() -> tuple[tuple[Machine, ...], dict[str, list[str]]]:
    """Join the specification and implementation populations by transition-id prefix.

    Returns the joined machines and a dict of UNJOINED prefixes on either side — a specification with
    no module, or a module with no specification. Both are failures; they are returned rather than
    raised so the guard can print the whole picture instead of the first problem it meets."""
    specs = {s.prefix: s for s in discover_specs()}
    impls = {i.prefix: i for i in discover_machine_modules()}
    orphans = {
        "spec_without_module": sorted(set(specs) - set(impls)),
        "module_without_spec": sorted(set(impls) - set(specs)),
    }
    joined = tuple(
        Machine(spec=specs[p], impl=impls[p])
        for p in sorted(set(specs) & set(impls), key=lambda p: specs[p].number))
    return joined, orphans


# ------------------------------------------------------------------ the (state × trigger) universe

def state_universe(machine: Machine) -> tuple[Any, ...]:
    """Every state this machine can be IN, derived from the machine itself.

    When the table's states are enum members the universe is the whole enum — which is stronger than
    the rows, because a state no row mentions still has to refuse every trigger. When they are plain
    strings (M13) the universe is the SMALLEST module-level `*_STATES` tuple that covers the rows, so
    it is still read off the module rather than retyped here."""
    table = machine.impl.module.TRANSITIONS
    for row in table:
        for state in (list(getattr(row, "from_states", ()) or ())
                      + [getattr(row, "from_state", None), getattr(row, "to_state", None)]):
            if isinstance(state, Enum):
                return tuple(type(state))
    named = {r for row in machine.impl.rows for r in row.from_states}
    named |= {row.to_state for row in machine.impl.rows if row.to_state is not None}
    candidates = []
    for attr in dir(machine.impl.module):
        if not attr.endswith("_STATES"):
            continue
        value = getattr(machine.impl.module, attr)
        if isinstance(value, (tuple, list, frozenset, set)) and all(isinstance(v, str) for v in value):
            if named <= set(value):
                candidates.append(tuple(value))
    if not candidates:
        raise AssertionError(
            f"{machine.label} names states {sorted(named)} but the module declares no `*_STATES` "
            f"vocabulary covering them; the sweep has no universe to sweep.")
    return min(candidates, key=len)


def trigger_universe(machine: Machine) -> tuple[Any, ...]:
    """Every trigger this machine can be OFFERED — the module's own `Trigger` enum.

    The enum is the authority, not the rows: a trigger with no legal row anywhere (M10's `TimerFired`,
    M13's `TimerFired`, M9's `AutoClose`) is exactly the kind a sweep has to offer at every state."""
    trigger_enum = getattr(machine.impl.module, "Trigger", None)
    if trigger_enum is None or not (isinstance(trigger_enum, type) and issubclass(trigger_enum, Enum)):
        raise AssertionError(
            f"{machine.label} ({machine.impl.module_name}) declares no `Trigger` enum; the sweep has "
            f"no vocabulary to offer it.")
    return tuple(trigger_enum)
