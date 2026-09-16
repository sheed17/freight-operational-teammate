#!/usr/bin/env python3
"""U8.1 mutation battery — a guard never seen to fail is a decoration (CLAUDE.md §6).

Each mutant reintroduces a SPECIFIC real defect the P8 policy admission kernel exists to prevent:
the `_DEFAULT` gate fallback that made forgetting survivable (F-20), binding the governing row's
own `policy_version` instead of the tenant's monotonic maximum (the UNDER-VOIDING defect, which
makes a policy change in another scope invisible to the claim), a tenant policy broadening the
product ceiling, a Permanent Product Truth overridden from below, an allow-on-error policy read,
a registration completeness check that passes over an incomplete or empty population, a claim CAS
that loses its `policy_version` predicate, a claim that compares the grant against itself, the
`PERMANENT_HUMAN_ASSERTION_REQUIRED`/`HUMAN_APPROVAL_REQUIRED` collapse, and a brake that depends
on the policy engine. Each names the guard that must turn RED under it.

The ANTI-VACUITY CONTROL is a NO-MUTATION baseline: the same battery target run with the tree
untouched must be GREEN. If it is red before any mutation, the count below is an assertion, not a
measurement.

It mutates TEXT and shells out to pytest; it NEVER imports the policy admission layer, and it
NEVER uses git to undo a mutation. Originals are held in memory and restored unconditionally;
`__pycache__` is purged around every run so a same-length restore cannot leave poisoned bytecode
and a false green.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

CKPT = "src/freight_recon/checkpoint.py"
ADMIT = "src/freight_recon/policy_admission.py"
PROD = "src/freight_recon/product_policy.py"
BRAKE = "src/freight_recon/brake.py"
T = "eval/tests/test_p8_policy_admission.py"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    r = subprocess.run([PY, "-m", "pytest", nodeid, "-q", "-p", "no:cacheprovider",
                        "-p", "no:randomly"], cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


# (label, [(rel_path, old_anchor, new_text), ...], guard_nodeid). Anchors must be UNIQUE.
CASES = [
    # ---------------------------------------------------------------- F-20: the default returns
    ("### THE `_DEFAULT` FALLBACK RETURNS — an unclassified action class silently resolves to "
     "HUMAN_APPROVAL_REQUIRED again, so forgetting to classify a class becomes survivable (F-20)",
     [(CKPT,
       "        entry = self._entries.get(name)\n        if entry is None:\n"
       "            raise UnclassifiedActionClass(",
       "        entry = self._entries.get(name)\n"
       "        if entry is None:\n"
       "            return GateEntry(gate=GateDecision.HUMAN_APPROVAL_REQUIRED)  # MUTANT\n"
       "        if False:\n"
       "            raise UnclassifiedActionClass(")],
     f"{T}::test_f20_the_gate_registry_NO_LONGER_resolves_an_unregistered_class_to_a_default"),

    ("the `_DEFAULT` fallback returns — and an UNCLASSIFIED action class reaches the mint end to "
     "end instead of refusing at step 6",
     [(CKPT,
       "        entry = self._entries.get(name)\n        if entry is None:\n"
       "            raise UnclassifiedActionClass(",
       "        entry = self._entries.get(name)\n"
       "        if entry is None:\n"
       "            return GateEntry(gate=GateDecision.HUMAN_APPROVAL_REQUIRED)  # MUTANT\n"
       "        if False:\n"
       "            raise UnclassifiedActionClass("),
      (ADMIT,
       "        return resolve_ceiling(action_class)",
       "        try:\n"
       "            return resolve_ceiling(action_class)\n"
       "        except Exception:  # MUTANT\n"
       "            return GateDecision.HUMAN_APPROVAL_REQUIRED")],
     f"{T}::test_e2e_an_unclassified_action_class_refuses_at_step_6_and_mints_nothing"),

    # ------------------------------------------------- the UNDER-VOIDING defect (the real one)
    ("### THE UNDER-VOIDING DEFECT — the decision binds the GOVERNING ROW's own policy_version "
     "instead of the tenant's monotonic MAX, so a policy change in ANOTHER scope moves nothing "
     "the claim CAS can see",
     [(ADMIT,
       "        bound_version = self.current_policy_version()",
       "        bound_version = tenant_decision.policy_version  # MUTANT")],
     f"{T}::test_the_bound_version_is_the_TENANT_MONOTONIC_MAX_not_the_governing_rows_own_version"),

    ("the under-voiding defect, END TO END — a grant minted under a superseded policy version is "
     "CLAIMED, and the effect executes on a policy that no longer exists",
     [(CKPT,
       "            current_policy_version = kernel.policy_version()",
       "            current_policy_version = row[\"policy_version\"]  # MUTANT")],
     f"{T}::test_e2e_a_policy_change_between_checkpoint_and_claim_makes_the_claim_FAIL_CLOSED"),

    ("### THE CLAIM CAS LOSES ITS `policy_version` PREDICATE — the WHERE clause stops "
     "revalidating the policy, so a stale grant is claimable",
     [(CKPT,
       "               AND expires_at > ? AND brake_version = ? AND policy_version = ?\n",
       "               AND expires_at > ? AND brake_version = ? AND ? IS NOT NULL\n")],
     f"{T}::test_the_three_kernel_invariants_claude_md_10_protects_still_hold"),

    # ------------------------------------------------------- tenant broadening / permanent truth
    ("### A TENANT POLICY BROADENS THE PRODUCT CEILING — the rank comparison is disabled, so an "
     "ACTIVE row above the ceiling DECIDES instead of being refused",
     [(ADMIT,
       "        if gate_rank(tenant_gate) > gate_rank(ceiling):",
       "        if False and gate_rank(tenant_gate) > gate_rank(ceiling):  # MUTANT")],
     f"{T}::test_a_tenant_policy_may_NEVER_broaden_the_product_ceiling_and_the_refusal_is_ATTRIBUTABLE"),

    ("a tenant policy broadens the product ceiling, END TO END — the broader gate authorizes an "
     "effect the product ceiling forbids",
     [(ADMIT,
       "        if gate_rank(tenant_gate) > gate_rank(ceiling):",
       "        if False and gate_rank(tenant_gate) > gate_rank(ceiling):  # MUTANT")],
     f"{T}::test_e2e_a_broadening_tenant_policy_cannot_authorize_anything"),

    ("### A PERMANENT PRODUCT TRUTH IS OVERRIDDEN FROM BELOW — `resolve_ceiling` prefers product "
     "policy over the permanent truth, so layer 2 stops being above layer 4",
     [(ADMIT,
       "    return permanent if gate_rank(product) > gate_rank(permanent) else product",
       "    return product  # MUTANT")],
     f"{T}::test_a_permanent_product_truth_CANNOT_be_overridden_from_below"),

    # ---------------------------------------------------------- registration completeness / M-9
    ("### THE REGISTRATION COMPLETENESS CHECK STOPS CHECKING — an action class with no gate no "
     "longer fails startup, which is F-20 at configuration time",
     [(PROD,
       "    unclassified = sorted(pop - set(pol))\n    if unclassified:",
       "    unclassified = sorted(pop - set(pol))\n    if False and unclassified:  # MUTANT")],
     f"{T}::test_u81_an_unclassified_action_class_FAILS_CLOSED_at_configuration_time"),

    ("### THE M-9 ZERO-ROW FALSE GREEN — the completeness check accepts an EMPTY population and "
     "reports a classification that verified nothing as complete",
     [(PROD,
       "    if not pop:\n        raise IncompleteProductPolicy(",
       "    if False:  # MUTANT\n        raise IncompleteProductPolicy(")],
     f"{T}::test_u81_an_EMPTY_population_is_refused_rather_than_passing_vacuously"),

    # ------------------------------------------------------------------- allow-on-error at claim
    ("### ALLOW ON ERROR — an unreadable policy store is treated as 'policy unchanged' at claim "
     "time, so the money fence dies quietly (ADR-010 §11)",
     [(CKPT,
       "        except Exception as exc:  # noqa: BLE001 — any policy-store failure is a refusal\n"
       "            settle(False)",
       "        except Exception as exc:  # MUTANT\n"
       "            current_policy_version = row[\"policy_version\"]\n"
       "        if False:\n"
       "            settle(False)")],
     f"{T}::test_e2e_an_unreadable_policy_store_refuses_and_never_means_unchanged"),

    # ------------------------------------------------------------------- the constitutional pairs
    ("### `PERMANENT_HUMAN_ASSERTION_REQUIRED` IS COLLAPSED INTO `HUMAN_APPROVAL_REQUIRED` — the "
     "distinction between a PERMANENT TRUTH and CURRENT POLICY is destroyed, and the "
     "Authorization Assertion becomes graduatable (ADR-003, catastrophic)",
     [(CKPT,
       "    GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED: 1,",
       "    GateDecision.PERMANENT_HUMAN_ASSERTION_REQUIRED: 2,  # MUTANT")],
     f"{T}::test_permanent_human_assertion_required_is_NOT_collapsed_into_human_approval_required"),

    ("### `FORBIDDEN` IS COLLAPSED INTO `PERMANENT_HUMAN_ASSERTION_REQUIRED` — 'nobody may ever "
     "do this' and 'only a human may ever do this' become the same sentence (ADR-010 A4, the "
     "latent defect its own Amendment Record reports)",
     [(CKPT,
       "    GateDecision.FORBIDDEN: 0,",
       "    GateDecision.FORBIDDEN: 1,  # MUTANT")],
     f"{T}::test_forbidden_is_NOT_collapsed_into_permanent_human_assertion_required"),

    # -------------------------------------------------- the authority reads the store's connection
    ("### THE POLICY AUTHORITY IS BOUND TO A DIFFERENT CONNECTION — the kernel stops requiring the "
     "authority to read the store's own connection, so the claim CAS re-read is no longer atomic "
     "with the CAS (ADR-011 §8.2) and a policy change on another connection is invisible: "
     "under-voiding",
     [(CKPT,
       "            authority_conn = getattr(policy_authority, \"conn\", None)\n"
       "            if authority_conn is not None and authority_conn is not store.conn:",
       "            authority_conn = getattr(policy_authority, \"conn\", None)\n"
       "            if False and authority_conn is not None and authority_conn is not store.conn:  # MUTANT")],
     f"{T}::test_a_policy_authority_on_a_DIFFERENT_connection_is_REFUSED_at_construction"),

    # ------------------------------------------------------------------ the brake's independence
    ("### THE BRAKE DEPENDS ON THE POLICY ENGINE — `brake.py` imports the very subsystem the "
     "brake exists to overrule, so it would not work in the moment it is needed (ADR-011 §0)",
     [(BRAKE,
       "from .event_contracts import CONTRACTS",
       "from .policy import gate_rank  # MUTANT\nfrom .event_contracts import CONTRACTS")],
     f"{T}::test_the_brake_does_NOT_depend_on_the_policy_engine"),
]


def _run_edits(edits, guard) -> tuple[str, str]:
    originals = {ROOT / rel: (ROOT / rel).read_bytes() for rel, _o, _n in edits}
    for rel, old, _new in edits:
        text = (ROOT / rel).read_text(encoding="utf-8")
        if text.count(old) != 1:
            return "SETUP-FAIL", f"anchor appears {text.count(old)}x in {rel} (need exactly 1)"

    purge_pycache()
    if not run_guard(guard):
        return "SETUP-FAIL", "guard already RED before mutation"

    try:
        mutated = {path: blob.decode("utf-8") for path, blob in originals.items()}
        for rel, old, new in edits:
            path = ROOT / rel
            before = mutated[path]
            mutated[path] = before.replace(old, new, 1)
            if mutated[path] == before:
                raise RuntimeError(f"mutation was a no-op in {rel}")
        for path, text in mutated.items():
            path.write_text(text, encoding="utf-8")
        purge_pycache()
        caught = not run_guard(guard)
    except RuntimeError as exc:
        for path, blob in originals.items():
            path.write_bytes(blob)
        purge_pycache()
        return "SETUP-FAIL", str(exc)
    finally:
        for path, blob in originals.items():
            path.write_bytes(blob)
        purge_pycache()
    for path, blob in originals.items():
        if path.read_bytes() != blob:
            return "RESTORE-RED", f"byte-for-byte restore FAILED for {path}"
    if not run_guard(guard):
        return "RESTORE-RED", "guard red after restore - investigate"
    return ("CAUGHT" if caught else "MISS"), ""


def _baseline_control() -> tuple[str, str]:
    """### THE ANTI-VACUITY CONTROL: the tree is NOT mutated, and a representative guard must be
    GREEN. A battery whose target is already red would report every mutation 'caught' while
    proving nothing. Expected outcome: GREEN."""
    purge_pycache()
    green = run_guard(f"{T}::test_e2e_a_durable_tenant_policy_PERMITS_and_the_exact_version_is_BOUND")
    return ("GREEN" if green else "RED"), ""


def main() -> int:
    results = [(label, *_run_edits(edits, guard)) for label, edits, guard in CASES]
    control_verdict, _ = _baseline_control()

    print("\n=========== U8.1 POLICY ADMISSION MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    control_mark = "PASS" if control_verdict == "GREEN" else "### MISS ###"
    print(f"  [{control_mark:>12}] anti-vacuity control: the un-mutated tree is GREEN "
          f"(expected GREEN, got {control_verdict})")

    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    total = len(results)
    escaped = total - caught
    control_ok = control_verdict == "GREEN"
    print(f"\n  {caught}/{total} mutants caught")
    print(f"  {caught} mutations caught, {escaped} escaped")
    print(f"  anti-vacuity control: {'GREEN as expected' if control_ok else 'FAILED — target already red'}")
    print("  NOTE: written by the session that implemented the unit - evidence, not adjudication.")
    return 0 if (caught == total and control_ok) else 1


def test_the_p8_admission_mutation_battery_catches_every_mutant():
    """### THE PYTEST-COLLECTED ENTRY POINT (CLAUDE.md §6): the standard runner OPERATES this battery
    directly — `pytest scripts/mutate_p8_policy_admission.py` — and reads its exit status, not only
    the `__main__` CLI. An unmeasured guard is not a passing guard; a battery only a hand-run command
    exercises is one the runner cannot measure.

    `main()` runs EVERY mutant (each reintroduces a real defect and must be CAUGHT — including the
    connection-identity guard added by this slice) and the anti-vacuity control (the un-mutated tree
    must be GREEN), restoring every source file byte-for-byte from memory and never with git. It
    returns 0 only if every mutant is caught AND the control is green, so `== 0` is the whole battery,
    measured — over a non-empty, >=15 population, so it cannot pass vacuously (M-9).

    This file is deliberately NOT collected by a bare `pytest eval` (it is outside `testpaths` and is
    not named `test_*.py`); it runs only when named explicitly, which is exactly how a slow mutation
    battery should be operated — on purpose, never by accident sweeping the whole suite.
    """
    assert len(CASES) >= 15, (
        f"the battery carries {len(CASES)} mutants; it must carry all of them (>=15, including the "
        f"connection-identity guard) for 'every mutant caught' to mean anything (M-9).")
    assert main() == 0, (
        "the P8 admission mutation battery did NOT report every mutant CAUGHT with a GREEN "
        "anti-vacuity control; a guard that cannot be shown to fire is unverified. See the report.")


if __name__ == "__main__":
    raise SystemExit(main())
