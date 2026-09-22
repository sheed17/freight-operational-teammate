#!/usr/bin/env python3
"""Safe in-memory mutation battery for P8 / U8.6 — CommandIntent → Proposal.

Doctrine (CLAUDE.md §6/§9), identical to the P3/P4/P5/M1/M2 batteries:
  * original bytes are held IN MEMORY — never `git checkout/restore/stash/clean`
  * __pycache__ is purged around every mutation
  * a guard that does NOT fail on the mutant proves nothing and is reported as a MISS
  * restoration is verified byte-for-byte, and the guard must be GREEN again before moving on
  * every case states the REAL defect it reintroduces

### WHAT THIS BATTERY IS FOR. U8.6's load-bearing new seams are: the inert proposal
(registered-only action class; canonical minor-unit money; no MODEL_INFERRED promotion; fail-closed
identity), the proposal → M2 boundary (accountable owner; no CommandIntent authority), and the
signed-token authority (a proposal, not a bare CommandIntent), and — since the CI #52 correction —
the ONE Commit Key / ONE occurrence authority (no proposal-side key derivation; no caller-, wire- or
model-supplied occurrence entering identity). Each mutant removes one part of one of those and a
guard must go red.

### INTERPRETER-HERMETIC. Every guard runs under `sys.executable` — the interpreter that launched this
battery — so it runs identically from a local venv, a CI runner's setup-python, or any other
environment. CI #52: a hard-coded `ROOT/.venv/bin/python` does not exist on a fresh checkout.

### THIS IS NOT AN INDEPENDENT REVIEW. It was written by the session that implemented the unit.
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PROP = "src/freight_recon/proposal.py"
PL = "src/freight_recon/pipeline_instance.py"
AC = "src/freight_recon/action_callback.py"

TP = "eval/tests/test_phase8_proposal.py"
TG = "eval/tests/test_phase8_command_intent_to_proposal.py"
TAC = "eval/tests/test_phase8_action_class_registered.py"
TP1 = "eval/tests/test_phase1_structural_guards.py"

# The one line that hands the canonically derived occurrence to the LogicalEffect.
_OCC_KW = "            occurrence_key=occurrence,\n"
_OCC_CALL = ("        occurrence = occurrence_key_for(\n"
             "            self.action_class, resolved=resolved,\n"
             "            document_digest=self.document_digest, target_status=self.target_status,\n"
             "        )\n")


# M16 injects a second NAMED Commit Key derivation into proposal.py. The unchanged P1 guard reads
# src/ AND scripts/ line by line for a definition whose name contains the canonical one, so writing
# that definition literally here would report THIS fixture as a second derivation. The name is
# assembled at runtime instead; once written into proposal.py it is a real definition, and the guard
# must catch it there.
_SECOND_KEY_DEF = "    def " + "commit" + "_key(self) -> str:  # MUTANT: a second named Commit Key surface\n"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    # sys.executable is read at CALL time: the guard runs under whatever launched the battery.
    r = subprocess.run([sys.executable, "-m", "pytest", nodeid, "-q", "-p", "no:cacheprovider"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


TEXT_CASES = [
    ("M1  proposal construction stops rejecting an UNREGISTERED action class, so a model can invent "
     "a new kind of effect (e.g. `wire_money`) and have it accepted as a proposal — and a tampered "
     "wire form naming an unregistered class is accepted too",
     PROP,
     "        if self.action_class not in ACTION_CLASS_POPULATION:",
     "        if False and self.action_class not in ACTION_CLASS_POPULATION:  # MUTANT",
     f"{TAC}::test_an_unregistered_action_class_is_refused_not_invented_at_construction"),

    ("M10 a MISSING action class is INVENTED (defaulted) instead of refused, so a request that never "
     "said what kind of effect it proposes is silently built as a raise_invoice — the 'a model may "
     "not invent a field to make the proposal executable' prohibition, realized",
     PROP,
     '    action_class = params.get("action_class")',
     '    action_class = params.get("action_class") or "raise_invoice"  # MUTANT: invent a default',
     f"{TAC}::test_a_missing_action_class_is_refused_not_invented_at_construction"),

    ("M2  a MODEL_INFERRED material fact becomes gate-readable, so a guess can gate a consequential "
     "action (GR-8 / AC-SAFE-015, at any confidence) — and it is no longer excluded from a gate's "
     "readable facts",
     PROP,
     "        return self.provenance not in _GATE_FORBIDDEN",
     "        return True  # MUTANT: a guess may gate",
     f"{TP}::test_a_model_inferred_material_fact_is_carried_but_never_gate_readable"),

    ("M3  a proposed money fact stops refusing a binary float, so money enters a proposal as a float "
     "instead of canonical minor units (P1 malformed-input)",
     PROP,
     "        if isinstance(amount, bool) or isinstance(amount, float):",
     "        if False and (isinstance(amount, bool) or isinstance(amount, float)):  # MUTANT",
     f"{TP}::test_a_float_money_amount_is_refused"),

    ("M4  the proposal → M2 seam stops requiring an accountable Work Item, so a proposal with no "
     "owner context is driven into the pipeline (rule 13, §5) — the ownerless-obligation defect",
     PL,
     "    if proposal.work_item_id is None:",
     "    if False and proposal.work_item_id is None:  # MUTANT",
     f"{TP}::test_a_proposal_with_no_work_item_cannot_become_an_attempt"),

    ("M5  the proposal stops validating its identity eagerly, so an IMMATURE proposal (unknown "
     "target) no longer fails closed at the boundary — a model's incomplete guess could be carried "
     "toward an attempt instead of asking for clarification",
     PROP,
     "        effect.key()  # validate eagerly: an empty required field raises UnidentifiableEffect here,",
     "        pass  # MUTANT: skip eager identity validation",
     f"{TP}::test_an_immature_proposal_fails_closed_at_the_identity_boundary"),

    ("M6  the proposal → M2 seam reintroduces a direct CommandIntent into the consequential path — "
     "the exact authority defect U8.6 removes. The discovery guard's AST detector must flag it",
     PL,
     "    effect = proposal.logical_effect()   # UnidentifiableEffect if the proposal is immature",
     "    _reintroduced: CommandIntent = None  # MUTANT: a free-form CommandIntent in the seam\n"
     "    effect = proposal.logical_effect()   # UnidentifiableEffect if the proposal is immature",
     f"{TG}::test_open_pipeline_for_proposal_takes_a_proposal_not_a_command_intent"),

    ("M7  the signed token re-adds a stored bare CommandIntent field beside the proposal — a SECOND "
     "(free-form) proposal authority, which is exactly what the migration removed",
     AC,
     "    proposal: dict\n",
     "    proposal: dict\n    intent: \"CommandIntent\"  # MUTANT: a second free-form authority\n",
     f"{TG}::test_the_slack_token_authority_is_a_proposal_field_not_a_bare_command_intent"),

    # ---- P0/P1 risk: a proposal token TREATED AS APPROVAL (a forged token accepted) --------------
    ("M8  the signed operation-approval token's HMAC check is disabled, so a FORGED token (any "
     "signature over a valid body) verifies — 'generating a token is approval', the exact thing the "
     "single-use signed tap exists to prevent",
     AC,
     "    if not hmac.compare_digest(expected, signature):",
     "    if False and not hmac.compare_digest(expected, signature):  # MUTANT",
     f"{TP}::test_a_tampered_token_is_refused"),

    # ---- P0/P1 risk: a PROPOSED pipeline AUTO-ADVANCED beyond policy by the seam -----------------
    ("M9  the proposal → M2 seam auto-advances the new PROPOSED attempt past policy (drives PL-2 "
     "with a fabricated PERMIT), i.e. proposal construction evaluates/mints a gate instead of "
     "stopping at PROPOSED for the canonical policy step",
     PL,
     "    return machine.propose(\n"
     "        pipeline_instance_id=pipeline_instance_id,\n"
     "        work_item_id=proposal.work_item_id,\n"
     "        effect=effect,\n"
     "        actor_type=actor_type,\n"
     "        actor_id=actor_id,\n"
     "        proposal_ref=proposal_ref or pipeline_instance_id,\n"
     "        supersedes=supersedes,\n"
     "        correlation_id=correlation_id,\n"
     "        causation_id=causation_id,\n"
     "        trace_id=trace_id,\n"
     "        event_id=event_id,\n"
     "    )",
     "    _o = machine.propose(  # MUTANT: proposal construction auto-advances past policy\n"
     "        pipeline_instance_id=pipeline_instance_id, work_item_id=proposal.work_item_id,\n"
     "        effect=effect, actor_type=actor_type, actor_id=actor_id,\n"
     "        proposal_ref=proposal_ref or pipeline_instance_id, supersedes=supersedes,\n"
     "        correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id,\n"
     "        event_id=event_id)\n"
     "    if _o.is_new_attempt:\n"
     "        machine.apply(pipeline_instance_id, Trigger.POLICY_EVALUATED, actor_type=actor_type,\n"
     "                      actor_id=actor_id, policy_version='pv-mutant',\n"
     "                      gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED,\n"
     "                      policy_decision='PERMIT', model_inferred_material_fact=False)\n"
     "    return _o",
     f"{TP}::test_a_mature_proposal_opens_exactly_one_proposed_instance"),

    # ---- CI #52: ONE Commit Key authority, ONE occurrence authority ------------------------------
    ("M11 a caller-authored occurrence string enters the proposal's identity (the P1 escape hatch, "
     "via material_params): a retry that varies it mints a second logical effect — two invoices",
     PROP, _OCC_KW,
     '            occurrence_key=str(self.material_params.get("occurrence_key") or occurrence),  # MUTANT\n',
     f"{TP}::test_two_retries_cannot_vary_an_occurrence_string_into_two_commit_keys"),

    ("M12 an occurrence the canonical authority REFUSED is invented as '' instead of failing closed, "
     "so an unresolved record_payment/adjust_invoice/check_call proposal becomes mature and opens an "
     "M2 attempt with no proven occurrence",
     PROP, _OCC_CALL,
     "        try:  # MUTANT: invent an occurrence instead of failing closed\n"
     "            occurrence = occurrence_key_for(\n"
     "                self.action_class, resolved=resolved,\n"
     "                document_digest=self.document_digest, target_status=self.target_status,\n"
     "            )\n"
     "        except UnidentifiableEffect:\n"
     '            occurrence = ""\n',
     f"{TP}::test_an_unresolved_canonical_occurrence_fails_closed"),

    ("M13 a typed derivation input splits a SINGLE effect's identity: raise_invoice re-proposed with a "
     "different target_status/document_digest becomes a second logical effect — two invoices",
     PROP, _OCC_KW,
     '            occurrence_key=occurrence or str(self.target_status or self.document_digest or ""),'
     '  # MUTANT\n',
     f"{TP}::test_single_action_class_identity_converges"),

    ("M14 the validating deserializer silently accepts a wire form that DECLARES its own occurrence / "
     "commit key / resolved occurrence (a form construction refuses) — a tampered or stale payload is "
     "half-accepted instead of detected",
     PROP, "        if unknown:\n", "        if False and unknown:  # MUTANT\n",
     f"{TP}::test_a_wire_payload_cannot_declare_its_own_occurrence"),

    ("M15 an untyped look-alike (not a resolved CanonicalOccurrence) is accepted as the canonical "
     "occurrence, so occurrence identity enters from an object any caller can build",
     PROP,
     "        if resolved is not None and not isinstance(resolved, CanonicalOccurrence):\n",
     "        if False and resolved is not None and not isinstance(resolved, CanonicalOccurrence):"
     "  # MUTANT\n",
     f"{TP}::test_an_untyped_occurrence_stand_in_is_refused"),

    ("M16 a second NAMED Commit Key derivation surface returns on ProposedIntent (the exact CI #52 "
     "Category-A regression) — the unchanged P1 guard must catch it",
     PROP,
     "    def gate_readable_facts(self) -> tuple[ProposedFact, ...]:\n",
     _SECOND_KEY_DEF +
     "        return self.logical_effect().key()\n\n"
     "    def gate_readable_facts(self) -> tuple[ProposedFact, ...]:\n",
     f"{TP1}::test_the_canonical_derivation_is_the_only_one"),

    ("M17 the free-form occurrence read returns to proposal.py (the exact CI #52 Category-B "
     "regression, M11's edit) — the unchanged P1 AST guard must catch it",
     PROP, _OCC_KW,
     '            occurrence_key=str(self.material_params.get("occurrence_key") or occurrence),  # MUTANT\n',
     f"{TP1}::test_no_free_form_occurrence_key_is_readable_from_the_request_payload"),

    ("M18 proposal.py grows a SECOND occurrence resolver dispatching on the rule table itself. "
     "Behaviour-identical today; the defect is two resolvers that can drift apart — the structural "
     "single-authority guard must catch it",
     PROP, _OCC_CALL,
     "        from .commit_key import OCCURRENCE_RULES  # MUTANT: a second occurrence resolver\n"
     '        occurrence = "" if OCCURRENCE_RULES.get(self.action_class) == "SINGLE" else occurrence_key_for(\n'
     "            self.action_class, resolved=resolved,\n"
     "            document_digest=self.document_digest, target_status=self.target_status,\n"
     "        )\n",
     f"{TP}::test_the_proposal_module_has_one_occurrence_source_and_no_second_resolver"),
]

# Covered by a STRONGER existing mutant, stated rather than duplicated (CLAUDE.md §9):
#   * "M2 Layer-1 reservation bypassed on a duplicate" — mutate_phase6_pipeline_instance.py P1/P1b
#     attack the reservation index and PL-1b directly; U8.6's seam only delegates to that machinery
#     and test_a_redelivered_equivalent_proposal_is_absorbed_as_one_attempt rides on it.


def _run_edits(edits, guard) -> tuple[str, str]:
    originals: dict[Path, bytes] = {}
    for rel, old, new in edits:
        path = ROOT / rel
        if not path.exists():
            return "SETUP-FAIL", f"{rel} does not exist"
        text = path.read_bytes().decode("utf-8")
        if text.count(old) != 1:
            return "SETUP-FAIL", f"anchor appears {text.count(old)}x in {rel} (need exactly 1)"
        if text.replace(old, new, 1) == text:
            return "SETUP-FAIL", f"mutation was a no-op in {rel}"

    purge_pycache()
    if not run_guard(guard):
        return "SETUP-FAIL", "guard already RED before mutation"

    try:
        for rel, old, new in edits:
            path = ROOT / rel
            originals[path] = path.read_bytes()
            path.write_text(originals[path].decode("utf-8").replace(old, new, 1), encoding="utf-8")
        purge_pycache()
        caught = not run_guard(guard)
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


def main() -> int:
    results = [(c[0], *_run_edits(((c[1], c[2], c[3]),), c[4])) for c in TEXT_CASES]
    print("\n=========== P8 / U8.6 PROPOSAL MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    # A stable, per-mutant machine-readable line, so a pytest wrapper (and the Product Driver's own
    # runner) can OBSERVE that each NAMED mutant — M1/M10 (unregistered/missing action_class
    # accepted), M2 (MODEL_INFERRED promoted), M8 (forged token as approval), M9 (PROPOSED
    # auto-advanced), M11–M18 (a second Commit Key / occurrence authority) — actually reintroduced
    # its defect and was caught.
    for label, verdict, _ in results:
        print(f"MUTANT {label.split()[0]}: {verdict}")
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    # A stable line CI can grep for, mirroring the M3/M13 batteries' "N mutations caught, 0 escaped".
    print(f"{caught} mutants caught, {len(results) - caught} escaped")
    print("  NOTE: written by the session that implemented the unit - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
