"""Phase-1 structural guards: the defective Commit Key model must be unrestorable.

Phase 1 is FORWARD-ONLY. Rollback may disable a capability; it may never bring back an identity
algorithm that mixed the approved amount into the identity of an effect, or handed a consequential
effect no identity at all. These guards inspect the ACTUAL call sites and fail on an empty
population — a guard that evaluated nothing has proven nothing.
"""

import ast
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from freight_recon.commit_key import OCCURRENCE_RULES
from freight_recon.operation_router import freight_lanes
from phase0.evaluation import Evaluation
from phase0.sources import SCRIPTS, SRC, python_files, rel

COMMIT_KEY_MODULE = SRC / "commit_key.py"
ROUTER = SRC / "operation_router.py"
WORKFLOW = SRC / "workflow.py"

# Values that are attempt-scoped or mutable. An identity built from any of them makes every retry a
# NEW logical effect, which is the double-commit defect with better manners.
FORBIDDEN_IN_IDENTITY = (
    "approved_amount", "amount", "rate", "line_item", "confidence", "model_output",
    "retry", "attempt", "request_id", "approval_id", "timestamp", "uuid4", "policy_result",
)


def test_the_canonical_derivation_is_the_only_one():
    """No second permanent Commit Key implementation may exist.

    Two identity algorithms means two namespaces, and two namespaces can each authorise the same
    effect independently — which is exactly the hole Phase 1 closes.
    """
    ev = Evaluation(name="phase1.key_derivations")
    pattern = re.compile(r"def\s+(\w*commit_key\w*|\w*commit_identity\w*)\s*\(")
    for path in python_files(SRC, SCRIPTS):
        ev.sources_inspected.append(rel(path))
        for i, line in enumerate(path.read_text(encoding="utf-8").split("\n"), 1):
            m = pattern.search(line)
            if m:
                ev.candidates.append(f"{rel(path)}:{i}")
                ev.parsed.append(m.group(1))
                ev.accepted.append(f"{rel(path)}:{i}:{m.group(1)}")
    ev.require_population(minimum=1)
    derivations = [a for a in ev.accepted if "commit_key.py" not in a]
    assert not derivations, (
        f"a second Commit Key derivation exists outside the canonical module: {derivations}\n{ev.report()}"
    )


def test_the_deleted_amount_keyed_derivation_never_returns():
    text = WORKFLOW.read_text(encoding="utf-8")
    assert "def operation_commit_key(" not in text, (
        "the amount-keyed derivation has been restored. Phase 1 is forward-only: approving GBP 2,850 "
        "and then GBP 3,100 for one invoice would raise two invoices again."
    )
    assert "was DELETED in Phase 1" in text, "the deletion's reasoning was removed from the record"


def test_no_mutable_or_attempt_scoped_value_appears_in_the_identity_type():
    """The identity type's FIELDS are the contract. Inspect them, not the prose around them."""
    tree = ast.parse(COMMIT_KEY_MODULE.read_text(encoding="utf-8"))
    cls = next(n for n in ast.walk(tree)
               if isinstance(n, ast.ClassDef) and n.name == "LogicalEffect")
    fields = [n.target.id for n in cls.body if isinstance(n, ast.AnnAssign)]
    assert fields == ["tenant", "action_class", "target_system", "target_resource_id",
                      "target_operation", "occurrence_key"], f"the identity's shape changed: {fields}"
    for banned in FORBIDDEN_IN_IDENTITY:
        assert not any(banned in f for f in fields), f"{banned!r} entered the effect's identity"


def test_the_derivation_cannot_accept_an_amount_by_signature():
    """U1.1's completion oracle: the amount is not a parameter, so it cannot be passed."""
    import inspect

    from freight_recon.commit_key import commit_key, occurrence_key_for

    for fn in (commit_key, occurrence_key_for):
        params = str(inspect.signature(fn)).lower()
        for banned in ("amount", "rate", "retry", "timestamp", "request_id", "approval_id"):
            assert banned not in params, f"{fn.__name__} accepts {banned!r}"


def test_the_identity_hash_is_built_only_from_identity_fields():
    """Read the derivation itself: every hashed component must come from LogicalEffect."""
    tree = ast.parse(COMMIT_KEY_MODULE.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "commit_key")
    referenced = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
    allowed = {"tenant", "action_class", "target_system", "target_resource_id",
               "target_operation", "occurrence_key"}
    leaked = {r for r in referenced if r in FORBIDDEN_IN_IDENTITY}
    assert not leaked, f"the derivation reads mutable state: {leaked}"
    assert referenced & allowed, "the derivation reads no identity fields at all"


def test_every_consequential_lane_declares_an_occurrence_rule():
    """A new consequential operation with no Commit Key obligation fails here, before it can run."""
    ev = Evaluation(name="phase1.lane_occurrence_rules", sources_inspected=[rel(ROUTER)])
    for lane in freight_lanes():
        ev.candidates.append(lane.name)
        ev.parsed.append(lane.name)
        ev.accepted.append(lane.name)
    ev.require_population(minimum=8)
    undeclared = [l.name for l in freight_lanes() if l.name not in OCCURRENCE_RULES]
    assert not undeclared, (
        f"consequential lane(s) with no occurrence rule: {undeclared}\n"
        f"Every action class must state whether repetition is legitimate BEFORE it may run."
    )


def test_no_consequential_path_can_return_a_null_identity():
    """DEF-2 must not return: the producer raises, it does not hand back None."""
    text = ROUTER.read_text(encoding="utf-8")
    assert "if not amount:\n        return None" not in text
    assert "def _commit_identity(" not in text, "the nullable producer was restored"
    tree = ast.parse(text)
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_commit_reservation")
    returns_none = [n for n in ast.walk(fn)
                    if isinstance(n, ast.Return) and isinstance(n.value, ast.Constant)
                    and n.value.value is None]
    assert not returns_none, "_commit_reservation can return None for a consequential effect"


def test_non_money_effects_are_actually_reserved_not_merely_keyed():
    """A key nothing reserves with is a decoration. `will_commit` must cover non-money effects."""
    text = ROUTER.read_text(encoding="utf-8")
    assert "will_commit = not prepare_only" in text, (
        "will_commit excludes non-money effects again, so their Commit Key is never used and the "
        "same POD can be filed twice (AC-SAFE-013)"
    )
    assert "will_commit = lane.requires_amount" not in text


def test_the_legacy_bridge_has_no_claim_authority():
    """The compatibility bridge may BLOCK. It may never authorise."""
    tree = ast.parse(WORKFLOW.read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "legacy_commit_rows")
    body = ast.dump(fn)
    for writer in ("INSERT", "UPDATE", "DELETE"):
        assert writer not in body, f"the legacy bridge performs a {writer}: it has claim authority"
    assert "SELECT" in body


def test_the_legacy_bridge_declares_its_scope_and_removal():
    """No indefinite compatibility bridge. It states where it ends."""
    text = WORKFLOW.read_text(encoding="utf-8")
    start = text.index("def legacy_commit_rows")
    doc = text[start:start + 2000]
    assert "Removal: Phase 2" in doc, "the bridge names no removal phase"
    assert "Deletion condition:" in doc, "the bridge names no deletion condition"
    assert "never infers success" in doc


def test_the_amount_survives_as_a_material_fact():
    """Removing the amount from IDENTITY must not mean discarding it. Drift must stay detectable."""
    text = ROUTER.read_text(encoding="utf-8")
    assert '"approved_amount": normalize_money_amount(amount) if amount else ""' in text, (
        "the approved amount is no longer preserved alongside the reservation; drift would become "
        "invisible and Phase 3's fingerprint would have nothing to compare"
    )
    assert "approved_amount TEXT NOT NULL" in WORKFLOW.read_text(encoding="utf-8"), (
        "the schema changed - Phase 1 must not touch it"
    )


def test_the_router_call_sites_all_use_the_canonical_reservation():
    """Inspect the real call sites; fail on zero candidates."""
    ev = Evaluation(name="phase1.router_call_sites", sources_inspected=[rel(ROUTER)])
    for i, line in enumerate(ROUTER.read_text(encoding="utf-8").split("\n"), 1):
        if "commit_store." in line:
            ev.candidates.append(f"{i}")
            ev.parsed.append(line.strip())
            ev.accepted.append(line.strip())
    ev.require_population(minimum=4)
    legacy = [c for c in ev.accepted if "**commit_identity" in c]
    assert not legacy, f"a call site still splats the old identity dict: {legacy}"
