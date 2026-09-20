"""P8 / U8.6 — the CommandIntent-authority guard: no consequential consumer trusts raw CommandIntent.

The invariant U8.6 protects is architectural: `CommandIntent` is an interpretation/input DTO; the
consequential machinery consumes the canonical structured proposal (`ProposedIntent`) or the M2
entry boundary (`LogicalEffect` via `PipelineMachine.propose`), NEVER a free-form `CommandIntent`.

This guard is machine-checkable and its population is DISCOVERED, not hand-enumerated: it AST-walks
every module under `src/freight_recon/` and reports the denominator it scanned and every function
that references `CommandIntent`. It then asserts the canonical consequential entry points are
CommandIntent-free, and proves — with a positive control that reintroduces the exact defect — that
the detector actually fires. A guard nobody has seen go red is a decoration (CLAUDE.md §6).

It does NOT ban the `CommandIntent` class: interpretation and UI/rendering boundaries legitimately
use it. It bans AUTHORITATIVE CONSEQUENTIAL consumption — a CommandIntent reaching the proposal →
attempt boundary, the M2 command, or the checkpoint kernel.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "freight_recon"
sys.path.insert(0, str(ROOT / "src"))

# The canonical consequential entry points. A CommandIntent reaching any of these is the defect: the
# proposal → attempt seam, the one M2 command, and the two kernel-owned executors.
_CONSEQUENTIAL_ENTRY_POINTS = frozenset({
    "open_pipeline_for_proposal",   # proposal → M2 seam (pipeline_instance.py)
    "propose",                      # PipelineMachine.propose — the IntentProposed / PL-1 path
    "_run_checkpoint",              # PL-8 kernel executor
    "_run_claim",                   # PL-9 kernel executor
})


def _src_modules() -> list[Path]:
    mods = [p for p in SRC.rglob("*.py") if "__pycache__" not in p.parts]
    assert len(mods) > 40, f"the module walk found only {len(mods)} modules; the scan is not vacuous?"
    return mods


def _iter_functions(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text))


def _annotations(func) -> list[ast.AST]:
    """Every annotation in a function's signature (incl. forward-ref STRING annotations) + locals."""
    a = func.args
    out: list[ast.AST] = []
    for arg in a.posonlyargs + a.args + a.kwonlyargs + [x for x in (a.vararg, a.kwarg) if x]:
        if arg.annotation is not None:
            out.append(arg.annotation)
    if func.returns is not None:
        out.append(func.returns)
    for node in ast.walk(func):
        if isinstance(node, ast.AnnAssign) and node.annotation is not None:
            out.append(node.annotation)
    return out


def _def_references(func: ast.AST, name: str) -> bool:
    """True iff this function's SIGNATURE or BODY references the given name — a `Name`/attribute
    load OR an annotation, including a forward-ref STRING annotation (`intent: "CommandIntent"`).
    Whole-token (AST + tokenised annotation), never a raw substring."""
    for ann in _annotations(func):
        if name in _tokens(ast.unparse(ann)):
            return True
    for node in ast.walk(func):
        if isinstance(node, ast.Name) and node.id == name:
            return True
        if isinstance(node, ast.Attribute) and node.attr == name:
            return True
    return False


def _command_intent_ledger() -> dict[str, list[str]]:
    """DISCOVER, do not enumerate: {module: [functions that reference CommandIntent]} across src/."""
    ledger: dict[str, list[str]] = {}
    for path in _src_modules():
        tree = ast.parse(path.read_text(), filename=str(path))
        hits = [fn.name for fn in _iter_functions(tree) if _def_references(fn, "CommandIntent")]
        if hits:
            ledger[path.name] = sorted(hits)
    return ledger


def _find_function(module: str, name: str) -> ast.AST:
    tree = ast.parse((SRC / module).read_text(), filename=module)
    for fn in _iter_functions(tree):
        if fn.name == name:
            return fn
    raise AssertionError(f"{name} not found in {module}")


# ============================================================ the ledger (discovered, non-vacuous)

def test_the_command_intent_population_is_discovered_and_printed():
    """The population is found by AST across the whole src tree, with its denominator, so a later
    module that starts consuming CommandIntent cannot escape this guard by not being listed."""
    ledger = _command_intent_ledger()
    total = sum(len(v) for v in ledger.values())
    print(f"\nCommandIntent consumer ledger — {len(_src_modules())} modules scanned, "
          f"{len(ledger)} modules reference CommandIntent, {total} functions:")
    for module in sorted(ledger):
        print(f"  {module}: {ledger[module]}")
    # non-vacuous: the interpretation/proposal boundaries legitimately reference CommandIntent.
    assert total > 0, "the scan found no CommandIntent references; it parsed nothing"
    assert "slack_delegate.py" in ledger, "the interpretation DTO's own module was not discovered"
    assert "proposal.py" in ledger, "the CommandIntent → Proposal boundary was not discovered"


def test_no_consequential_entry_point_references_command_intent():
    """### THE CORE CLAIM. None of the canonical consequential entry points reference CommandIntent —
    they consume a ProposedIntent / LogicalEffect / CheckpointRequest instead. Discovered from the
    ledger, so a new consequential consumer of CommandIntent breaks the build here."""
    ledger = _command_intent_ledger()
    offenders = {
        f"{module}::{fn}"
        for module, fns in ledger.items() for fn in fns
        if fn in _CONSEQUENTIAL_ENTRY_POINTS
    }
    assert not offenders, (
        f"a consequential entry point consumes a raw CommandIntent: {sorted(offenders)}. It must "
        f"consume the canonical structured proposal / LogicalEffect instead (U8.6)."
    )


def test_open_pipeline_for_proposal_takes_a_proposal_not_a_command_intent():
    fn = _find_function("pipeline_instance.py", "open_pipeline_for_proposal")
    assert not _def_references(fn, "CommandIntent")
    params = {a.arg for a in fn.args.args}
    assert "proposal" in params, "the seam must take a `proposal` (ProposedIntent), not an intent"


def test_m2_propose_takes_a_logical_effect_not_a_command_intent():
    fn = _find_function("pipeline_instance.py", "propose")
    assert not _def_references(fn, "CommandIntent")
    # the effect (and therefore the commit key) is a LogicalEffect argument
    assert any(a.arg == "effect" for a in fn.args.kwonlyargs + fn.args.args)


def test_the_slack_token_authority_is_a_proposal_field_not_a_bare_command_intent():
    """The signed token carries the canonical proposal as its authoritative field; `intent` is a
    derived @property (a view), not a stored CommandIntent field — there is one authority, not two."""
    tree = ast.parse((SRC / "action_callback.py").read_text(), filename="action_callback.py")
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "SlackOperationApproval")
    field_names = {n.target.id for n in cls.body
                   if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)}
    assert "proposal" in field_names, "the token must carry a `proposal` field (the authority)"
    assert "intent" not in field_names, (
        "the token must NOT store a bare CommandIntent field — that would be a second authority. "
        "`intent` may exist only as a derived @property view over the proposal."
    )
    # ...and `intent`, if present, is a property (a method), never a stored field.
    methods = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert "intent" in methods, "the derived `intent` view is missing"


# ============================================================ the positive control (it can fire)

_HOSTILE_SEAM = '''
def open_pipeline_for_proposal(machine, intent: "CommandIntent", *, pipeline_instance_id):
    # REINTRODUCED DEFECT: derive the effect directly from a free-form CommandIntent and drive M2.
    effect = derive_effect_from(intent.params)
    return machine.propose(pipeline_instance_id=pipeline_instance_id, effect=effect)
'''


def test_the_detector_actually_fires_on_a_reintroduced_defect():
    """### THE POSITIVE CONTROL. Feed the SAME detector a seam that reintroduces the exact defect —
    a CommandIntent driving the proposal → attempt boundary — and prove it is flagged. A detector
    that cannot go red proves nothing about the tree it passed on."""
    tree = ast.parse(_HOSTILE_SEAM)
    fn = next(f for f in _iter_functions(tree) if f.name == "open_pipeline_for_proposal")
    assert _def_references(fn, "CommandIntent"), (
        "the detector failed to flag a CommandIntent reintroduced into the consequential seam — it "
        "is blind, so its green on the real tree is meaningless."
    )
    # And the ledger classifier would flag it as an offending consequential entry point:
    offenders = {fn.name} & _CONSEQUENTIAL_ENTRY_POINTS
    assert offenders == {"open_pipeline_for_proposal"}
