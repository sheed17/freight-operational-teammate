#!/usr/bin/env python3
"""M11 mutation battery — a guard never seen to fail is a decoration (CLAUDE.md §6).

Each mutant reintroduces a specific real defect the Policy machine exists to prevent — a model or
automation activating, inbound content authoring, a tenant broadening the product ceiling, a null or
invented gate, allow-on-error evaluation, a MODEL_INFERRED or confidence predicate, non-deterministic
evaluation, a consequential event that drops its policy_version pin, a version that does not advance the
tenant scalar (so a policy change voids nothing), a hidden admin path, a version overwritten in place, a
deleted or edited superseded row, two active policies for one scope, a cross-tenant uniqueness collision,
a cross-tenant activator, a broadening policy carrying an expiry, a broadening revocation by automation,
PolicyProposed collapsed into PolicySubmitted, PolicyApproved treated as activation, a string ceiling
compare, M11 reaching for the brake, M11 minting a gate decision, replay minting authority, strict order
weakened, a reused policy_version, supersession skipped (retroactivity), a dropped required payload field,
PolicyEvaluated minted by M11, an unregistered ninth event, the Policy Owner singularity dropped, and the
singularity coupling two tenants. Each names the guard that must turn RED under it.

The ANTI-VACUITY CONTROL is a NO-MUTATION baseline: the same battery target run with the tree untouched
must be GREEN. If it is red before any mutation, the count below is an assertion, not a measurement.

It mutates TEXT and shells out to pytest; it NEVER imports the policy machine, and it NEVER uses git to
undo a mutation. Originals are held in memory and restored unconditionally; `__pycache__` is purged around
every run so a same-length restore cannot leave poisoned bytecode and a false green.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

M11 = "src/freight_recon/policy.py"
MIG = "src/freight_recon/migrations/phase6_policies.py"
SCHEMA = "src/freight_recon/schema.py"
T = "eval/tests/test_phase6_policy.py"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    r = subprocess.run([PY, "-m", "pytest", nodeid, "-q", "-p", "no:cacheprovider",
                        "-p", "no:randomly"], cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


# (label, [(rel_path, old_anchor, new_text), ...], guard_nodeid). Each anchor must appear EXACTLY ONCE.
CASES = [
    ("a model or automation activates — the PO-4 authenticated-human guard is disabled, so a model "
     "activates a policy at any confidence (ER-11, GR-7)",
     [(M11,
       "        if str(actor_kind).upper() != HUMAN:\n"
       "            self._record_unauthorized_activation(",
       "        if False and str(actor_kind).upper() != HUMAN:  # MUTANT\n"
       "            self._record_unauthorized_activation(")],
     f"{T}::test_a_model_cannot_activate_a_policy"),

    ("an unauthorized activation goes unrecorded — the dedicated F14 tripwire is dropped, so a model "
     "attempt is refused but leaves no security record (entity §31, F14)",
     [(M11,
       "            self._record_unauthorized_activation(comp.policy_id, actor_type=self._actor_type(actor_kind),\n"
       "                                                 actor_id=actor_id or str(actor_kind))",
       "            pass  # MUTANT no F14 record")],
     f"{T}::test_a_model_cannot_activate_a_policy"),

    ("inbound content authors a policy — the PO-1 human-author guard is disabled, so a model/email/"
     "counterparty authors a policy row (entity §35, ER-9)",
     [(M11,
       '        if str(actor_kind).upper() != HUMAN:\n'
       '            raise IllegalTransition(\n'
       '                f"PO-1 authors a policy row and requires an authenticated human',
       '        if False and str(actor_kind).upper() != HUMAN:  # MUTANT\n'
       '            raise IllegalTransition(\n'
       '                f"PO-1 authors a policy row and requires an authenticated human')],
     f"{T}::test_inbound_content_and_a_model_cannot_author_a_policy"),

    ("a tenant policy broadens the product ceiling — the PO-2 narrowing guard is disabled, so a tenant "
     "sets AUTONOMOUS above a HUMAN_APPROVAL ceiling (ADR-010 §3.1/§8, ### M11-AQ-5)",
     [(M11, "        if not narrows_or_holds(comp.gate_decision, self._ceiling):",
       "        if False and not narrows_or_holds(comp.gate_decision, self._ceiling):  # MUTANT")],
     f"{T}::test_ac_safe_027_a_tenant_policy_cannot_broaden_the_product_ceiling"),

    ("the ceiling comparison becomes a raw string compare — AUTONOMOUS_WITHIN_CAPS sorts before "
     "HUMAN_APPROVAL_REQUIRED, so the most dangerous broadening reads as a narrowing (ADR-010 §3.1)",
     [(M11, "    return gate_rank(new) <= gate_rank(ceiling)",
       "    return str(new.value) <= str(ceiling.value)  # MUTANT string compare")],
     f"{T}::test_the_ceiling_order_is_total_over_the_four_members_and_not_a_string_compare"),

    ("the never-null gate CHECK is dropped — a null or invented gate_decision becomes insertable (F-20)",
     [(MIG, "            gate_decision TEXT NOT NULL CHECK (gate_decision IN (%(gates)s)),",
       "            gate_decision TEXT,  -- MUTANT")],
     f"{T}::test_null_and_invented_gate_decisions_are_refused_by_the_database"),

    ("allow-on-error evaluation — a MODEL_INFERRED fact at eval time is swallowed and PERMITted instead "
     "of failing closed (spec §11: no allow-on-error default)",
     [(M11,
       "        try:\n"
       "            preconditions_hold = evaluate_predicate(active.predicate, inputs)\n"
       "        except GateReadOfInferredFact as exc:\n"
       "            # A compiled predicate handed a MODEL_INFERRED fact at runtime: fail closed, never decide on it.\n"
       "            raise PolicyEngineUnavailable(\n"
       '                f"policy {active.policy_id!r} could not be evaluated deterministically: {exc}. A guess "\n'
       '                f"cannot gate a consequential action at any confidence (GR-8); no decision is produced.") from exc',
       "        try:\n"
       "            preconditions_hold = evaluate_predicate(active.predicate, inputs)\n"
       "        except GateReadOfInferredFact:\n"
       "            preconditions_hold = True  # MUTANT allow on error")],
     f"{T}::test_the_policy_engine_fails_closed_and_has_no_allow_on_error_default"),

    ("a predicate branches on a MODEL_INFERRED value — the compile-time refusal is disabled, so a guess "
     "becomes a gate (M-49, GR-8, ADR-010 §5.1)",
     [(M11, "            if _as_provenance(declared) is ProvenanceClass.MODEL_INFERRED:",
       "            if False and _as_provenance(declared) is ProvenanceClass.MODEL_INFERRED:  # MUTANT")],
     f"{T}::test_ac_safe_015_a_predicate_on_model_inferred_fails_to_compile"),

    ("confidence becomes an input — a `confidence` field is added to the evaluator input type, so a "
     "predicate can read a guess's certainty (ADR-010 §5.1 corollary: confidence is structurally absent)",
     [(M11, "    applicable_caps: Mapping[str, Any] = dataclass_field(default_factory=dict)",
       "    applicable_caps: Mapping[str, Any] = dataclass_field(default_factory=dict)\n"
       "    confidence: float = 1.0  # MUTANT")],
     f"{T}::test_the_evaluator_input_type_has_no_confidence_field"),

    ("evaluation is non-deterministic — a uuid enters the reason, so the same inputs and policy_version "
     "no longer produce a byte-identical PolicyDecision (M-50)",
     [(M11,
       '            f"{\'hold\' if preconditions_hold else \'do NOT hold\'} ⇒ {decision}.")',
       '            f"{\'hold\' if preconditions_hold else \'do NOT hold\'} ⇒ {decision}." + str(uuid.uuid4()))  # MUTANT')],
     f"{T}::test_ac_policy_evaluation_is_byte_identical_reproducible"),

    ("a consequential event drops its policy_version pin — PolicyApproved/PolicyActivated/VersionChanged "
     "no longer pin the decision context (§5, ER-13)",
     [(M11, "            policy_version=(pinset.get(\"policy_version\") if consequential else None),",
       "            policy_version=None,  # MUTANT")],
     f"{T}::test_policyapproved_carries_the_diff_fingerprint_and_does_not_activate"),

    ("the tenant version scalar does not advance — current_policy_version always returns 1, so a policy "
     "change voids no in-flight approval (### M11-AQ-6)",
     [(M11, '            "SELECT COALESCE(MAX(policy_version), 0) FROM policies WHERE tenant = ?",',
       '            "SELECT 1 FROM policies WHERE tenant = ? LIMIT 1",  # MUTANT')],
     f"{T}::test_ac_safe_010_a_policy_change_voids_an_in_flight_m4_approval"),

    ("a hidden admin path to ACTIVE — the governed-states CHECK is dropped, so a direct UPDATE activates "
     "a policy with no M4 approval and no diff fingerprint (ADR-010 §4, no admin path)",
     [(MIG,
       "            CHECK (state NOT IN (%(governed)s) OR (approval_id IS NOT NULL AND diff_fingerprint IS NOT NULL)),",
       "            -- MUTANT dropped no-admin-path CHECK")],
     f"{T}::test_ac_mach_1103_no_admin_path_to_approved"),

    ("a version overwritten in place — the OCC version-advances trigger is defused, so a state change that "
     "leaves the row version standing overwrites another transition (GR-3)",
     [(MIG, "        WHEN NEW.state <> OLD.state AND NEW.version <> OLD.version + 1\n"
       "        BEGIN SELECT RAISE(ABORT, '{VERSION_ABORT}'); END",
       "        WHEN 0  -- MUTANT\n        BEGIN SELECT RAISE(ABORT, '{VERSION_ABORT}'); END")],
     f"{T}::test_occ_version_advances_by_one_per_transition"),

    ("a superseded version is deletable — the no-delete trigger is removed, so a policy version is erased "
     "and the effects judged under it lose their explanation (entity §28/§29, C-9)",
     [(MIG, "    \"trg_policies_no_delete\": f\"\"\"\n"
       "        CREATE TRIGGER trg_policies_no_delete\n"
       "        BEFORE DELETE ON policies\n"
       "        BEGIN SELECT RAISE(ABORT, '{DELETE_ABORT}'); END\"\"\",",
       "    # MUTANT dropped no-delete trigger")],
     f"{T}::test_retention_supersession_is_permanent_and_immutable_and_undeletable"),

    ("two active policies for one scope — the one-active partial index loses UNIQUE (entity §17)",
     [(MIG, '        "CREATE UNIQUE INDEX ix_policies_one_active_per_scope "',
       '        "CREATE INDEX ix_policies_one_active_per_scope "  # MUTANT')],
     f"{T}::test_one_active_policy_per_scope_and_a_version_is_never_reused"),

    ("a cross-tenant uniqueness collision — the one-active index drops tenant, so the SAME scope cannot be "
     "active in two brokerages ([C-1], entity §17)",
     [(MIG, "        \"ON policies (tenant, scope) WHERE state = 'ACTIVE'\",",
       "        \"ON policies (scope) WHERE state = 'ACTIVE'\",  # MUTANT")],
     f"{T}::test_the_same_scope_is_active_in_two_tenants_without_collision"),

    ("a policy_version is reused within a tenant — the tenant-version index loses UNIQUE, so scope-local "
     "numbering becomes possible (### M11-AQ-6)",
     [(MIG, '        "CREATE UNIQUE INDEX ix_policies_tenant_version ON policies (tenant, policy_version)",',
       '        "CREATE INDEX ix_policies_tenant_version ON policies (tenant, policy_version)",  # MUTANT')],
     f"{T}::test_one_active_policy_per_scope_and_a_version_is_never_reused"),

    ("a cross-tenant author — BOTH the machine's tenant predicate AND the author FK are dropped (the "
     "defect is defended in depth, so both must fall for it to reappear), so another tenant's human "
     "authors a policy ([C-1], entity §18)",
     [(M11, '            "SELECT state FROM tenant_humans WHERE tenant = ? AND human_id = ?",',
       '            "SELECT state FROM tenant_humans WHERE (tenant = ? OR 1=1) AND human_id = ?",  # MUTANT'),
      (MIG, "            FOREIGN KEY (tenant, authored_by) REFERENCES tenant_humans (tenant, human_id),",
       "            -- MUTANT dropped authored_by FK")],
     f"{T}::test_a_cross_tenant_activator_or_author_fails_closed"),

    ("a broadening policy carries an expiry — the narrowing-only-expiry CHECK is dropped, so an expiry can "
     "auto-broaden authority when it fires (entity §26, ADR-010 §4.1)",
     [(MIG, "            CHECK (expires_at IS NULL OR change_direction = 'narrow'),",
       "            -- MUTANT dropped narrowing-only expiry CHECK")],
     f"{T}::test_only_a_narrowing_policy_may_carry_an_expiry"),

    ("a broadening revocation by automation — the broaden-needs-owner guard is disabled, so automation "
     "removes a tightening (ER-12)",
     [(M11,
       "            if str(actor_kind).upper() != HUMAN:\n"
       "                self._refuse_illegal(comp.policy_id, Trigger.REVOKED, actor_id=actor_id,\n"
       '                                     reason="a broadening revocation by automation")',
       "            if False and str(actor_kind).upper() != HUMAN:  # MUTANT\n"
       "                self._refuse_illegal(comp.policy_id, Trigger.REVOKED, actor_id=actor_id,\n"
       '                                     reason="a broadening revocation by automation")')],
     f"{T}::test_a_narrowing_revocation_is_immediate_and_a_broadening_one_needs_the_owner"),

    ("PolicyProposed is collapsed into PolicySubmitted — PO-1 emits PolicySubmitted, rewriting the meaning "
     "of every historical PolicyProposed (S8/ER-7)",
     [(M11, '                event_name="PolicyProposed", transition_id="PO-1", policy=created,',
       '                event_name="PolicySubmitted", transition_id="PO-1", policy=created,  # MUTANT')],
     f"{T}::test_policysubmitted_is_not_a_rename_of_policyproposed"),

    ("PolicyApproved is treated as activation — PO-3 transitions straight to ACTIVE, collapsing the "
     "human activation PO-4 owns (entity §31)",
     [(M11, '            comp, "PO-3", PolicyState.APPROVED, event_name="PolicyApproved",',
       '            comp, "PO-3", PolicyState.ACTIVE, event_name="PolicyApproved",  # MUTANT')],
     f"{T}::test_policyapproved_carries_the_diff_fingerprint_and_does_not_activate"),

    ("M11 reaches for the brake — policy.py imports BrakeStore, crossing the boundary that the brake is "
     "the checkpoint's; M11 engages/narrows none (spec §20.7, CLAUDE.md rule 17)",
     [(M11, "from .tenant import require_tenant",
       "from .brake import BrakeStore  # MUTANT\nfrom .tenant import require_tenant")],
     f"{T}::test_m11_engages_no_brake_and_imports_no_brakestore"),

    ("M11 mints its own gate decision — policy.py constructs a GateRegistry, becoming a second gate "
     "authority outside the checkpoint kernel (ADR-010; the §3.7 mint boundary)",
     [(M11, "from .checkpoint import (\n    GateDecision,",
       "from .checkpoint import (\n    GateEntry,\n    GateRegistry,\n    GateDecision,"),
      (M11, "DEFAULT_PRODUCT_CEILING = GateDecision.HUMAN_APPROVAL_REQUIRED",
       "DEFAULT_PRODUCT_CEILING = GateDecision.HUMAN_APPROVAL_REQUIRED\n"
       '_LEAK = GateRegistry({"raise_invoice": GateEntry(gate=GateDecision.FORBIDDEN)}, policy_version="pv1")  # MUTANT')],
     f"{T}::test_only_the_checkpoint_kernel_mints_a_gate_decision"),

    ("replay mints authority — rebuild reports minted authority, and GR-11/ER-2 say replay creates none",
     [(M11, "        return ReconstructedPolicy(policy_id=policy_id, state=state)",
       "        return ReconstructedPolicy(policy_id=policy_id, state=state, authority_minted=1)  # MUTANT")],
     f"{T}::test_replay_reconstructs_state_only_and_mints_no_authority"),

    ("strict order is weakened — the successor stops declaring its predecessor, so ORDER is no longer "
     "enforced across the policy aggregate (registry §8, P6-D11)",
     [(M11, "            aggregate_version=version, previous_aggregate_version=previous, causation_id=causation_id,",
       "            aggregate_version=version, previous_aggregate_version=None, causation_id=causation_id,  # MUTANT")],
     f"{T}::test_the_policy_aggregate_is_strict_order_and_events_carry_a_predecessor_link"),

    ("supersession is skipped on activation — PO-4 leaves the prior version ACTIVE, so a new policy is "
     "applied without retaining/superseding the old one, and the unique index collides (entity §24)",
     [(M11, "            superseded_ids = self._supersede_active_in_scope(comp.scope, by=comp.policy_id, now=now)",
       "            superseded_ids = []  # MUTANT no supersession")],
     f"{T}::test_a_policy_is_never_retroactive_the_old_version_keeps_its_own_version"),

    ("a required payload field is dropped — PolicyApproved omits diff_fingerprint, the no-admin-path "
     "evidence (registry §5, a producer may not drop a required field)",
     [(M11, '                     "diff_fingerprint": diff, "approved_by": approver,',
       '                     "approved_by": approver,  # MUTANT dropped diff_fingerprint')],
     f"{T}::test_policyapproved_carries_the_diff_fingerprint_and_does_not_activate"),

    ("M11 mints PolicyEvaluated — PO-4 emits the F2/M2 coordination contract as if it were M11's "
     "(rule 17 duplication)",
     [(M11, 'event_name="PolicyActivated", transition_id="PO-4", policy=after,',
       'event_name="PolicyEvaluated", transition_id="PO-4", policy=after,  # MUTANT')],
     f"{T}::test_m11_emits_no_policyevaluated_and_only_registered_event_names"),

    ("an unregistered ninth event name — PO-5 emits PolicyNarrowed, absent from the eight F11 contracts "
     "(registry §3)",
     [(M11, 'event_name="PolicySuperseded", transition_id="PO-5", policy=after,',
       'event_name="PolicyNarrowed", transition_id="PO-5", policy=after,  # MUTANT')],
     f"{T}::test_no_unregistered_policy_event_name_in_the_machine"),

    ("the Policy Owner singularity is dropped — the tenant_humans partial index loses UNIQUE, so two "
     "ACTIVE POLICY_OWNER rows become insertable (### M11-AQ-7 / P6-D72)",
     [(MIG, '        "CREATE UNIQUE INDEX ix_tenant_humans_one_active_policy_owner "',
       '        "CREATE INDEX ix_tenant_humans_one_active_policy_owner "  # MUTANT')],
     f"{T}::test_ac_safe_a_second_active_policy_owner_in_one_tenant_is_refused"),

    ("the Policy Owner singularity couples two tenants — the index drops tenant, so one POLICY_OWNER is "
     "unique GLOBALLY and a second brokerage cannot name its own (### M11-AQ-7, [C-1])",
     [(MIG, "        \"ON tenant_humans (tenant) WHERE authority_role = 'POLICY_OWNER' AND state = 'ACTIVE'\"",
       "        \"ON tenant_humans (authority_role) WHERE authority_role = 'POLICY_OWNER' AND state = 'ACTIVE'\"  # MUTANT")],
     f"{T}::test_the_policy_owner_singularity_does_not_couple_tenants"),

    ("M11 is production-enabled — a production module (schema.py) imports the policy machine, so M11 no "
     "longer ships dark (R-07, U8.1)",
     [(SCHEMA, "TENANT_COLUMN = \"tenant\"",
       "from .policy import M11Machine  # MUTANT\nTENANT_COLUMN = \"tenant\"")],
     f"{T}::test_m11_ships_dark_no_production_importer"),
]


def _run_edits(edits, guard) -> tuple[str, str]:
    originals: dict[Path, bytes] = {}
    for rel, old, new in edits:
        path = ROOT / rel
        if not path.exists():
            return "SETUP-FAIL", f"{rel} does not exist"
        if path not in originals:
            originals[path] = path.read_bytes()

    for rel, old, new in edits:
        path = ROOT / rel
        text = originals[path].decode("utf-8")
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
    """### THE ANTI-VACUITY CONTROL: the tree is NOT mutated, and a representative guard must be GREEN.
    A battery whose target is already red would report every mutation 'caught' while proving nothing.
    Expected outcome: NOT caught (green). If this is 'caught', the count is an assertion, not a
    measurement."""
    purge_pycache()
    green = run_guard(f"{T}::test_readiness_is_clean_on_a_fresh_canonical_database")
    return ("GREEN" if green else "RED"), ""


def main() -> int:
    results = [(label, *_run_edits(edits, guard)) for label, edits, guard in CASES]
    control_verdict, _ = _baseline_control()

    print("\n=========== P6 M11 POLICY MUTATION BATTERY ===========")
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


if __name__ == "__main__":
    raise SystemExit(main())
