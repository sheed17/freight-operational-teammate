"""What a module DOES about typed gates, separated from what a module SAYS about them.

### THE DEFECT THIS MODULE EXISTS TO REMOVE.

Three P0 guards defend the ADR-010 gate boundary, and all three measured it by reading raw file
text. Raw text cannot tell `if gate is HUMAN_APPROVAL_REQUIRED:` apart from a docstring that says
"this machine mints NO gate decision" — so a module that DOCUMENTS its non-participation was
scored as a participant. P6/M10 is exactly that module: `compensation.py` and
`phase6_compensations.py` contain six gate-token occurrences between them and **zero** are
executable — five are Python docstrings/comments and one is an SQL `--` comment inside a DDL
string. The guards fired on prose, and a guard that fires on its own subject's explanatory text is
one people learn to suppress.

`test_only_the_checkpoint_kernel_may_MINT_a_gate_decision` had already reached this conclusion and
said so in as many words — *"`GateEntry` inside a docstring or an error message is prose"* — and
went AST-based for that reason. This module is that same correction, extracted so the remaining
text-scanning guards share ONE statement of it instead of drifting into three.

### THE ARCHITECTURAL STATEMENT THE GUARDS ENFORCE (ADR-010, and §14 of the M2 machine spec).

  * `checkpoint.py` **MINTS** gate decisions, and nothing else may. A decision comes into existence
    only by constructing a `GateEntry` or a `GateRegistry`.
  * `phase3_checkpoint.py` **PERSISTS** the vocabulary as DDL `CHECK` literals.
  * `pipeline_instance.py` (machine M2) **CARRIES AND ROUTES** an already-minted decision — PL-2
    writes it and refuses NULL, PL-3 rejects on `FORBIDDEN`, PL-6 routes to a human, PL-7a admits
    autonomously only on `AUTONOMOUS_WITHIN_CAPS`. A machine that could not NAME a decision could
    not route on one.
  * Every other module **DOES NEITHER**, and may still describe the boundary in prose. Describing
    it is not participating in it.

Nothing here widens any allowlist. `executable_source` narrows what the guards read to what the
interpreter and SQLite actually execute; the kernel allowlists stay exactly as they were, and a
module that starts genuinely evaluating policy still lands in the offender list.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize

__all__ = [
    "GATE_RUNTIME_MODULES",
    "GATE_TOKENS",
    "require_gate_runtime_modules",
    "executable_source",
    "gate_token_sites",
    "gate_registration_sites",
]

# The four typed gate decisions of the ADR-010 §3.1-A3 ladder.
GATE_TOKENS: tuple[str, ...] = (
    "HUMAN_APPROVAL_REQUIRED",
    "AUTONOMOUS_WITHIN_CAPS",
    "PERMANENT_HUMAN_ASSERTION_REQUIRED",
    "FORBIDDEN",
)

# The two ways an action class can acquire a typed gate in production. Deliberately NOT
# `GateEntry`: the kernel's `GateRegistry._DEFAULT = GateEntry(HUMAN_APPROVAL_REQUIRED)` is the
# fail-closed fallback every UNregistered class resolves to, so counting it would report the
# absence of registration as its presence. Minting is guarded separately and with its own kernel
# allowlist by `test_only_the_checkpoint_kernel_may_MINT_a_gate_decision`.
_REGISTRY_CALLS = frozenset({"GateRegistry"})
_REGISTERING_CALLS = frozenset({"register_gate"})


# ### THE GATE-RUNTIME BOUNDARY, STATED EXACTLY ONCE.
#
# FIXED-SPECIFICATION: these are the modules ADR-010 and `02-pipeline-instance.machine.md` §14
# entitle to name a typed gate decision in EXECUTABLE code. It is a policy boundary the
# architecture states, not a population to be discovered — discovering it would mean asking the
# code which modules currently touch gates, which is the question, not the answer.
#
#   `checkpoint.py`        MINTS the decisions (ADR-010 puts gate evaluation at one boundary).
#   `phase3_checkpoint.py` PERSISTS the vocabulary as the `checkpoint_witnesses` DDL CHECK.
#   `pipeline_instance.py` CARRIES and ROUTES one already minted — §14 PL-2 writes `gate_decision`
#                          and refuses NULL, PL-3 rejects on FORBIDDEN, PL-6 routes to a human,
#                          PL-7a admits autonomously only on AUTONOMOUS_WITHIN_CAPS.
#   `policy.py`            IS checkpoint step 6's posture (M11, ADR-010): a policy's whole content is
#                          a `gate_decision`, so the machine NAMES the four members to hold, compare
#                          (the narrowing total order) and evaluate them. A machine that could not
#                          NAME a gate decision could not hold one.
#   `phase6_policies.py`   PERSISTS the policy vocabulary as the `policies.gate_decision` DDL CHECK.
#
# ### `policy.py` AND `phase6_policies.py` JOINED THIS SET AT P6-CP-11, AND IT IS A WIDENING WITH A
# NARROWING ATTACHED, exactly as `pipeline_instance.py` was at P6-CP-2. The narrowing is NOT
# negotiable and is asserted separately: `test_only_the_checkpoint_kernel_may_MINT_a_gate_decision`
# proves by AST that NEITHER new module constructs a `GateEntry` or a `GateRegistry` — CARRYING a
# decision and MINTING one are different acts, and only `checkpoint.py` mints. A second gate
# authority is the same defect as no gate authority; M11 supplies the posture step 6 reads, and the
# kernel still mints. The production `GateRegistry` population stays EMPTY (AC-CKPT-6-missing, U8.1).
#
# It lives here, in one place, because two guards need it and a boundary stated twice is a boundary
# that will eventually be stated differently. `test_..._confined_to_the_checkpoint_kernel` uses it
# as the ALLOWLIST (who MAY carry gate vocabulary) and
# `test_typed_policy_runtime_exists_only_with_its_canonical_authority` uses it as the expected
# CARRIER POPULATION (who actually does). Those are different claims, and asserting that the
# observed set equals the permitted set is a real cross-check rather than a restatement.
GATE_RUNTIME_MODULES: frozenset[str] = frozenset({
    "checkpoint.py", "phase3_checkpoint.py", "pipeline_instance.py",
    "policy.py", "phase6_policies.py",
})


def require_gate_runtime_modules(src) -> set[str]:
    """The boundary above, with every member verified to EXIST on disk.

    A renamed module would silently empty the allowlist and make every confinement assertion that
    reads it pass over nothing — the vacuous-guard failure these probes exist to prevent. So the
    set is never used raw; it is used through this.
    """
    present = {p.name for p in src.rglob("*.py")}
    missing = sorted(GATE_RUNTIME_MODULES - present)
    if missing:
        raise AssertionError(
            f"the gate-runtime boundary names {missing}, which no longer exist on disk - the "
            "boundary drifted and every guard reading it would have confined nothing"
        )
    return set(GATE_RUNTIME_MODULES)


def _blank(lines: list[str], sl: int, sc: int, el: int, ec: int) -> None:
    """Overwrite a source span with spaces IN PLACE, preserving every line and column.

    Deleting the span would renumber the file and every reported line number with it. Blanking
    keeps `lineno` truthful, which is what makes a failure message point at real code.
    """
    for i in range(sl - 1, min(el, len(lines))):
        start = sc if i == sl - 1 else 0
        end = ec if i == el - 1 else len(lines[i])
        start, end = max(0, min(start, len(lines[i]))), max(0, min(end, len(lines[i])))
        if end > start:
            lines[i] = lines[i][:start] + " " * (end - start) + lines[i][end:]


def executable_source(text: str) -> str:
    """`text` with everything the interpreter and SQLite ignore blanked out.

    Removed: Python comments, module/class/function docstrings, and whole-line SQL `--` comments
    inside string literals (which is how this repository's DDL is annotated). Retained: every
    string that is not a docstring, because a DDL `CHECK` literal and an error message are both
    real executable content and a guard is entitled to see them.

    Line and column geometry is preserved exactly, so a match's line number still points at the
    line it came from. A file that does not parse is returned unchanged — an unparseable module is
    a louder problem than a mis-scanned one, and silently emptying it would be the vacuous-guard
    failure these probes exist to prevent.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return text

    lines = text.splitlines()

    try:
        for tok in tokenize.generate_tokens(io.StringIO(text).readline):
            if tok.type == tokenize.COMMENT:
                _blank(lines, tok.start[0], tok.start[1], tok.end[0], tok.end[1])
    except (tokenize.TokenError, IndentationError):  # pragma: no cover - parsed above, so rare
        pass

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if ast.get_docstring(node, clean=False) is None or not node.body:
            continue
        doc = node.body[0]
        if doc.end_lineno is not None:
            _blank(lines, doc.lineno, doc.col_offset, doc.end_lineno, doc.end_col_offset)

    # SQL `--` comments, but ONLY inside a string constant and ONLY when the comment is the whole
    # line. A trailing `--` after SQL on the same line is left alone deliberately: this is the
    # conservative direction, since failing to blank a comment can only make a guard STRICTER.
    in_string: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.end_lineno:
            in_string.update(range(node.lineno, node.end_lineno + 1))
    for i, line in enumerate(lines):
        if (i + 1) in in_string and line.lstrip().startswith("--"):
            lines[i] = " " * len(line)

    return "\n".join(lines)


def gate_token_sites(text: str, tokens: tuple[str, ...] = GATE_TOKENS) -> list[tuple[int, str]]:
    """Every WHOLE-TOKEN gate-decision occurrence in the EXECUTABLE part of `text`.

    Whole-token, not substring: `FORBIDDEN_TENANTS` (U2.6A's sentinel list) is not a policy gate,
    and a substring scan reported that typed policy had arrived because of it.
    """
    executable = executable_source(text)
    sites: list[tuple[int, str]] = []
    for token in tokens:
        for m in re.finditer(rf"(?<![A-Za-z0-9_]){token}(?![A-Za-z0-9_])", executable):
            sites.append((executable[: m.start()].count("\n") + 1, token))
    return sorted(sites)


def _registers_nothing(node: ast.Call) -> bool:
    """True when this `GateRegistry(...)` provably registers ZERO action classes.

    `GateRegistry({}, policy_version=...)` is a registry over an empty literal mapping: every
    action class then resolves to `GateRegistry._DEFAULT`, i.e. `HUMAN_APPROVAL_REQUIRED`. That is
    not "a gate was registered" — it is the *proof* that none was, which is precisely what the
    R-07 record and the AC-CKPT-6-missing deferral both assert. Anything not provably empty (a
    non-empty literal, a variable, a call, a comprehension) counts as population: the guard may
    only discount what it can SEE to be empty.
    """
    if node.keywords and any(kw.arg is None for kw in node.keywords):  # **kwargs — unknowable
        return False
    entries = node.args[0] if node.args else next(
        (kw.value for kw in node.keywords if kw.arg == "entries"), None)
    return isinstance(entries, ast.Dict) and not entries.keys


def gate_registration_sites(text: str, *, label: str = "") -> list[str]:
    """Every site that actually REGISTERS a typed gate.

    The subject is registration, not the class's existence: a construction that registers nothing
    is not a registration, and this is what lets a probe PROVE the money action class falls to
    `HUMAN_APPROVAL_REQUIRED` with an empty registry without that proof reading as the very
    population it disproves. A real registration — anywhere, including inside that same probe —
    is still reported.

    AST-only. Textual matching would fire on the class definition, on kernel type assertions and
    on the deferral comments.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return [f"{label}:0: UNPARSEABLE"]
    sites: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", None)
        if name in _REGISTERING_CALLS:
            sites.append(f"{label}:{node.lineno}: {name}")
        elif name in _REGISTRY_CALLS and not _registers_nothing(node):
            sites.append(f"{label}:{node.lineno}: {name}")
    return sites
