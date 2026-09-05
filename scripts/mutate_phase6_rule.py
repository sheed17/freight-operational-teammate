#!/usr/bin/env python3
"""M12 mutation battery — a guard never seen to fail is a decoration (CLAUDE.md §6).

Each mutant reintroduces a specific real defect the Rule machine exists to prevent — a MODEL_INFERRED or
unmodelled field compiling, confidence added to the compiler input, non-deterministic compilation, a
model confirming or activating, the F14 tripwire dropped, a nullable/ghost activator, a cross-tenant
author, a reply claiming enforcement with no active rule id, an honest refusal that loses "not a rule",
RuleNotEnforceable dropping `missing`, test vectors omitted before confirmation, RuleConfirmed treated as
activation, two conflicting rules auto-merged, the narrower-scope precedence inverted, a local conflict
mechanism, an M12-minted ConflictRaised, tenant dropped from an index, uniqueness made global, a reused
rule_version, a deleted or edited superseded row, a reactivation counted twice, a narrowing rule
auto-expiring into broader authority, a broadening revocation by automation, a rule overriding a higher
precedence layer, a GateEntry constructed in M12, an allow-on-rule-error path, an unregistered Rule*
event, a consumed fact minted as an event, PolicyOverridden minted, replay minting authority, a false
uniqueness on a multi-rule scope, and a production importer appearing. Each names the guard that must
turn RED under it.

The ANTI-VACUITY CONTROL is a NO-MUTATION baseline: the same battery target run with the tree untouched
must be GREEN. If it is red before any mutation, the count below is an assertion, not a measurement. The
expected count is DERIVED from the case list, never hard-coded.

It mutates TEXT and shells out to pytest; it NEVER imports the rule machine, and it NEVER uses git to
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

M12 = "src/freight_recon/rule.py"
MIG = "src/freight_recon/migrations/phase6_rules.py"
SCHEMA = "src/freight_recon/schema.py"
T = "eval/tests/test_phase6_rule.py"


_MUTATION_SENTINEL = "MUTANT"  # every mutation's replacement text carries this; a pristine tree has none


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def assert_pristine() -> None:
    """### A KILLED RUN MUST NOT SILENTLY MISCOUNT (§6: visible success is not correctness). The restore
    lives in a `finally`, but SIGKILL (a foreground timeout, a Ctrl-C storm) bypasses `finally`, stranding
    one mutation in a target file. Every downstream guard then measures a tree that is ALREADY broken, and
    the battery reports escapes that are really pre-existing corruption — a false measurement. Refuse to
    run, and name the poisoned files, rather than count against a tree that is not clean. Detection is by
    the mutation sentinel the battery itself writes; it NEVER uses git to detect or to undo (§6)."""
    targets = sorted({rel for _, edits, _ in CASES for rel, _old, _new in edits})
    poisoned = [rel for rel in targets if _MUTATION_SENTINEL in (ROOT / rel).read_text(encoding="utf-8")]
    if poisoned:
        print(f"### REFUSING TO MEASURE: mutation residue ({_MUTATION_SENTINEL!r}) found in {poisoned} — a "
              f"prior battery run was interrupted mid-mutation and its in-memory restore did not complete. "
              f"Those files are stranded in a mutated state; restore them before measuring, or every count "
              f"below is a false green.", file=sys.stderr)
        raise SystemExit(2)


def run_guard(nodeid: str) -> bool:
    r = subprocess.run([PY, "-m", "pytest", nodeid, "-q", "-p", "no:cacheprovider",
                        "-p", "no:randomly"], cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


# (label, [(rel_path, old_anchor, new_text), ...], guard_nodeid). Each anchor must appear EXACTLY ONCE.
CASES = [
    ("a MODEL_INFERRED field compiles — the compile-time guess-guard is disabled, so a rule branches on "
     "a guess at any confidence (M-49, GR-8)",
     [(M12, '    if pc == "MODEL_INFERRED":', '    if False and pc == "MODEL_INFERRED":  # MUTANT')],
     f"{T}::test_ru_compile_requires_modelled_non_inferred_fields"),

    ("confidence becomes an input — a `confidence` field is added to the compiler input type, so a "
     "predicate can read a guess's certainty (confidence is structurally absent)",
     [(M12, "    modelled: bool = True\n    # ### NO confidence FIELD. Structurally absent.",
       "    modelled: bool = True\n    confidence: float = 1.0  # MUTANT\n    # ### NO confidence FIELD.")],
     f"{T}::test_the_compiler_input_type_has_no_confidence_field"),

    ("an unmodelled field compiles — the modelled-field guard is disabled, so 'do not use Carrier X for "
     "produce' would compile against an unmodelled commodity (M-49)",
     [(M12, "    if not inp.modelled:", "    if False and not inp.modelled:  # MUTANT")],
     f"{T}::test_an_unmodelled_field_and_an_invented_provenance_class_fail_to_compile"),

    ("compilation is non-deterministic — a nonce enters the compiled predicate JSON, so the same "
     "candidate no longer compiles byte-identically (M-50)",
     [(M12, '        return {"status": "COMPILED", "kind": self.kind, "effect": self.effect,',
       '        return {"status": "COMPILED", "nonce": str(__import__("uuid").uuid4()), "kind": self.kind, "effect": self.effect,  # MUTANT')],
     f"{T}::test_compilation_is_byte_identical_reproducible"),

    ("a model confirms — the RU-4 human-confirmation guard is disabled, so a model confirms a rule "
     "(ADR-010 §6; entity §35)",
     [(M12,
       "        self._require_legal(comp, Trigger.HUMAN_CONFIRMED, actor_id=actor_id or confirmed_by)\n"
       '        if str(actor_kind).strip().lower() != "human":',
       "        self._require_legal(comp, Trigger.HUMAN_CONFIRMED, actor_id=actor_id or confirmed_by)\n"
       '        if False and str(actor_kind).strip().lower() != "human":  # MUTANT')],
     f"{T}::test_a_model_cannot_confirm_a_rule"),

    ("a model activates — the RU-5 authenticated-human guard is disabled, so a model activates a rule at "
     "any confidence (ER-11, GR-7)",
     [(M12,
       '        if str(actor_kind).strip().lower() != "human":\n'
       "            self._record_unauthorized_activation(",
       '        if False and str(actor_kind).strip().lower() != "human":  # MUTANT\n'
       "            self._record_unauthorized_activation(")],
     f"{T}::test_model_cannot_activate_a_rule"),

    ("an unauthorized activation goes unrecorded — the dedicated F14 tripwire is dropped, so a model "
     "attempt is refused but leaves no security record (entity §31, F14)",
     [(M12,
       "            self._record_unauthorized_activation(\n"
       "                comp.rule_id, actor_type=self._actor_type(actor_kind), actor_id=actor_id or str(actor_kind))",
       "            pass  # MUTANT no F14 record")],
     f"{T}::test_model_cannot_activate_a_rule"),

    ("the never-null activator CHECK is dropped — an ACTIVE rule with no activator becomes insertable "
     "(entity §16)",
     [(MIG, "            CHECK (state <> 'ACTIVE' OR activated_by IS NOT NULL),",
       "            -- MUTANT dropped ACTIVE-requires-activator CHECK")],
     f"{T}::test_active_requires_a_non_null_activated_by_fk_backed"),

    ("a cross-tenant author — BOTH the machine's tenant predicate AND the author FK are dropped (the "
     "defect is defended in depth, so both must fall), so another tenant's human authors a rule ([C-1])",
     [(M12, '            "SELECT state FROM tenant_humans WHERE tenant = ? AND human_id = ?",',
       '            "SELECT state FROM tenant_humans WHERE (tenant = ? OR 1=1) AND human_id = ?",  # MUTANT'),
      (MIG, "            FOREIGN KEY (tenant, authored_by) REFERENCES tenant_humans (tenant, human_id),",
       "            -- MUTANT dropped authored_by FK")],
     f"{T}::test_a_cross_tenant_activator_or_author_fails_closed"),

    ("a reply claims enforcement with no active rule id — the L-C guard is disabled, so 'Noted the "
     "procedure' is accepted with no rule backing it (M-52, M-64, T16)",
     [(M12, "    if reply_claims_enforcement(text) and not backed:",
       "    if False and reply_claims_enforcement(text) and not backed:  # MUTANT")],
     f"{T}::test_uncompilable_instruction_reply_does_not_claim_a_rule_was_installed"),

    ("the honest refusal loses its 'not a rule' sentence — the owner is no longer told it is not a rule "
     "(ADR-010 §6)",
     [(M12, "so this is NOT a rule and it will NOT stop ", "so this is and it will NOT stop ")],
     f"{T}::test_ru_uncompilable_reply_does_not_claim_enforcement"),

    ("RuleNotEnforceable drops `missing` — the owner is not told WHAT is missing (registry §5, RU-2f)",
     [(M12, '            missing = exc.missing or ("<unspecified>",)', "            missing = ()  # MUTANT")],
     f"{T}::test_ru_compile_requires_modelled_non_inferred_fields"),

    ("test vectors omitted before confirmation — a compiled rule ships with no vectors, so the owner "
     "confirms what they cannot see (entity §42, ADR-010 §6.2)",
     [(M12, "        vectors = generate_test_vectors(compiled)", "        vectors = []  # MUTANT")],
     f"{T}::test_ru_confirm_shows_test_vectors"),

    ("RuleConfirmed is treated as activation — RU-4 emits RuleActivated, collapsing the human activation "
     "RU-5 owns (entity §31)",
     [(M12, '            comp, "RU-4", RuleState.CONFIRMED, event_name="RuleConfirmed", payload={},',
       '            comp, "RU-4", RuleState.CONFIRMED, event_name="RuleActivated", payload={},  # MUTANT')],
     f"{T}::test_ruleconfirmed_does_not_activate"),

    ("two conflicting rules auto-merge — detect_conflict always takes the narrower/precedence branch and "
     "raises no conflict (GR-15)",
     [(M12, "        if narrower:\n            # ### THE NARROWER SCOPE WINS",
       "        if True:  # MUTANT auto-merge\n            # ### THE NARROWER SCOPE WINS")],
     f"{T}::test_two_conflicting_rules_fail_closed"),

    ("the narrower-scope precedence rule is inverted — a strictly narrower rule is treated as a conflict "
     "instead of precedence (ADR-010 §8)",
     [(M12, "        if narrower:\n            # ### THE NARROWER SCOPE WINS, AND THAT IS NOT A CONFLICT",
       "        if False and narrower:  # MUTANT invert precedence\n            # ### THE NARROWER SCOPE WINS, AND THAT IS NOT A CONFLICT")],
     f"{T}::test_two_conflicting_rules_fail_closed"),

    # ### M12 now CALLS M7 (imports M7Machine) by design, so the old "imports the conflict machine" defect
    # is correct behaviour. The real remaining defect the guard protects is a SECOND conflict MACHINE
    # defined in rule.py beside M7 — a duplicate authority. Reintroduce THAT and prove it is caught.
    ("M12 builds a second conflict system — rule.py defines its own conflict MACHINE beside M7, "
     "duplicating the authority M7 already owns (rule 17, ### M12-AQ-2)",
     [(M12, 'RULE_EFFECTS: tuple[str, ...] = ("DENY", "REQUIRE_HUMAN_APPROVAL", "PERMIT", "BIND", "RESOLVE")',
       "class RuleConflictMachine:  # MUTANT a second conflict machine\n    pass\n\n\n"
       'RULE_EFFECTS: tuple[str, ...] = ("DENY", "REQUIRE_HUMAN_APPROVAL", "PERMIT", "BIND", "RESOLVE")')],
     f"{T}::test_m12_calls_m7_but_builds_no_second_conflict_system"),

    ("M12 mints its own ConflictRaised — the RU-3 row emits ConflictRaised, duplicating F7's contract "
     "(### M12-AQ-2, rule 17)",
     [(M12, "        triggers=(Trigger.CONFLICT_DETECTED,), trigger_types=(\"S\",), kind=RowKind.PRODUCER,\n"
       "        events=(), blocked=True,",
       "        triggers=(Trigger.CONFLICT_DETECTED,), trigger_types=(\"S\",), kind=RowKind.PRODUCER,\n"
       "        events=(\"ConflictRaised\",), blocked=True,  # MUTANT")],
     f"{T}::test_conflictraised_is_f7_and_m12_mints_none"),

    ("tenant dropped from the one-active index — the SAME scope+kind cannot be active in two brokerages "
     "([C-1], entity §17)",
     [(MIG, '        "ON rules (tenant, scope, kind) "', '        "ON rules (scope, kind) "  # MUTANT')],
     f"{T}::test_the_same_scope_and_kind_is_active_in_two_tenants_without_collision"),

    ("uniqueness made global across tenants — the tenant-version index drops tenant, so a second tenant "
     "cannot hold version 1 (### M12-AQ-4b, [C-1])",
     [(MIG, '        "CREATE UNIQUE INDEX ix_rules_tenant_version ON rules (tenant, rule_version)",',
       '        "CREATE UNIQUE INDEX ix_rules_tenant_version ON rules (rule_version)",  # MUTANT')],
     f"{T}::test_the_same_scope_and_kind_is_active_in_two_tenants_without_collision"),

    ("a rule_version is reused within a tenant — the tenant-version index loses UNIQUE, so scope-local "
     "numbering becomes possible (### M12-AQ-4b)",
     [(MIG, '        "CREATE UNIQUE INDEX ix_rules_tenant_version ON rules (tenant, rule_version)",',
       '        "CREATE INDEX ix_rules_tenant_version ON rules (tenant, rule_version)",  # MUTANT')],
     f"{T}::test_a_rule_version_is_never_reused_within_a_tenant"),

    ("a superseded version is deletable — the no-delete trigger is removed, so a rule version is erased "
     "and the effects judged under it lose their explanation (entity §28/§29, C-9)",
     [(MIG, "    \"trg_rules_no_delete\": f\"\"\"\n"
       "        CREATE TRIGGER trg_rules_no_delete\n"
       "        BEFORE DELETE ON rules\n"
       "        BEGIN SELECT RAISE(ABORT, '{DELETE_ABORT}'); END\"\"\",",
       "    # MUTANT dropped no-delete trigger")],
     f"{T}::test_retention_is_permanent_and_immutable_and_undeletable"),

    ("history is edited in place — the identity-immutable trigger loses source_instruction, so a rule's "
     "sentence can be rewritten under it (entity §15/§24)",
     [(MIG, "        BEFORE UPDATE OF tenant, rule_id, rule_version, scope, kind, source_instruction,\n"
       "                         authored_by, change_direction, created_at",
       "        BEFORE UPDATE OF tenant, rule_id, rule_version, scope, kind,\n"
       "                         authored_by, change_direction, created_at  -- MUTANT dropped source_instruction")],
     f"{T}::test_retention_is_permanent_and_immutable_and_undeletable"),

    ("a reactivation is counted as a second activation — the no-op guard is disabled, so re-activating an "
     "ACTIVE version bumps the version and re-emits (GR-4)",
     [(M12, "        if comp.state is RuleState.ACTIVE:\n            return TransitionResult(\n"
       '                transition_id="RU-5", rule=comp, from_state=RuleState.ACTIVE, to_state=RuleState.ACTIVE,',
       "        if False and comp.state is RuleState.ACTIVE:  # MUTANT\n            return TransitionResult(\n"
       '                transition_id="RU-5", rule=comp, from_state=RuleState.ACTIVE, to_state=RuleState.ACTIVE,')],
     f"{T}::test_re_activating_an_active_version_is_a_no_op"),

    ("a narrowing rule auto-expires into broader authority — RU-8 drops the human-confirmation escalation, "
     "so the clock broadens with no human (ADR-010 §4.1)",
     [(M12, "            event_producer=result.event_producer, escalation=raised)",
       "            event_producer=result.event_producer, escalation=None)  # MUTANT")],
     f"{T}::test_ru_narrowing_expiry_needs_human"),

    ("a broadening revocation by automation — the broaden-needs-owner guard is disabled, so automation "
     "removes a tightening (ER-12)",
     [(M12,
       '        if dir_norm == "broaden":\n'
       '            if str(actor_kind).strip().lower() != "human":',
       '        if dir_norm == "broaden":\n'
       '            if False and str(actor_kind).strip().lower() != "human":  # MUTANT')],
     f"{T}::test_ru_revoke_direction"),

    ("a rule overrides a higher precedence layer — assert_within_precedence stops refusing, so a rule can "
     "claim a layer above STANDING_RULE (ADR-010 §8)",
     [(M12, "    if idx < PRECEDENCE_LAYER:",
       "    if False and idx < PRECEDENCE_LAYER:  # MUTANT")],
     f"{T}::test_a_rule_never_overrides_a_higher_layer"),

    ("M12 mints its own gate decision — rule.py constructs a GateRegistry, becoming a second gate "
     "authority outside the checkpoint kernel (ADR-010; the §3.7 mint boundary)",
     [(M12, "from .checkpoint import GateReadOfInferredFact, ProvenancedFact",
       "from .checkpoint import GateReadOfInferredFact, ProvenancedFact, GateEntry, GateRegistry"),
      (M12, 'RULE_EFFECTS: tuple[str, ...] = ("DENY", "REQUIRE_HUMAN_APPROVAL", "PERMIT", "BIND", "RESOLVE")',
       'RULE_EFFECTS: tuple[str, ...] = ("DENY", "REQUIRE_HUMAN_APPROVAL", "PERMIT", "BIND", "RESOLVE")\n'
       '_LEAK = GateRegistry({"raise_invoice": GateEntry(gate=__import__("freight_recon.checkpoint", fromlist=["GateDecision"]).GateDecision.FORBIDDEN)}, policy_version="pv1")  # MUTANT')],
     f"{T}::test_only_the_checkpoint_kernel_mints_a_gate_decision"),

    ("allow-on-rule-error — a MODEL_INFERRED fact at eval time is swallowed and treated as satisfied "
     "instead of failing closed (spec §11: no allow-on-error default)",
     [(M12,
       "        except GateReadOfInferredFact as exc:\n"
       "            raise RuleEngineUnavailable(",
       "        except GateReadOfInferredFact as exc:\n"
       "            results.append(True); continue  # MUTANT allow on error\n"
       "            raise RuleEngineUnavailable(")],
     f"{T}::test_the_rule_engine_fails_closed_no_allow_on_error"),

    ("an unregistered ninth event name — RU-6 emits RuleNarrowed, absent from the eight F12 contracts "
     "(registry §3)",
     [(M12, 'event_name="RuleSuperseded", transition_id="RU-6", rule=after,',
       'event_name="RuleNarrowed", transition_id="RU-6", rule=after,  # MUTANT')],
     f"{T}::test_no_unregistered_rule_event_name_in_the_machine"),

    ("a consumed fact is minted as an event — RU-8 emits TimerFired, minting a driving fact (### the "
     "consumed-fact invariant)",
     [(M12, '            comp, "RU-8", RuleState.EXPIRED, event_name="RuleExpired",',
       '            comp, "RU-8", RuleState.EXPIRED, event_name="TimerFired",  # MUTANT consumed fact minted')],
     f"{T}::test_m12_emits_only_registered_event_names_and_no_consumed_fact"),

    ("PolicyOverridden is minted — RU-7 emits the unregistered override contract (### M12-AQ-7 / P6-D71)",
     [(M12, '            comp, "RU-7", RuleState.REVOKED, event_name="RuleRevoked",',
       '            comp, "RU-7", RuleState.REVOKED, event_name="PolicyOverridden",  # MUTANT')],
     f"{T}::test_policyoverridden_is_unregistered_and_m12_mints_none"),

    ("replay mints authority — rebuild reports minted authority, and GR-11/ER-2 say replay creates none",
     [(M12, "        return ReconstructedRule(rule_id=rule_id, state=state)",
       "        return ReconstructedRule(rule_id=rule_id, state=state, authority_minted=1)  # MUTANT")],
     f"{T}::test_replay_reconstructs_state_only_and_mints_no_authority"),

    ("a false uniqueness on a multi-rule scope — the single-admitting set becomes the whole vocabulary, so "
     "a legitimate second rule on a multi-admitting scope is refused (### M12-AQ-4)",
     [(MIG, 'P6RU_SINGLE_ACTIVE_SCOPES: tuple[str, ...] = ("subject_type",)',
       "P6RU_SINGLE_ACTIVE_SCOPES: tuple[str, ...] = P6RU_SCOPE_FORMS  # MUTANT")],
     f"{T}::test_one_active_rule_where_the_scope_admits_one_and_many_where_it_does_not"),

    ("M12 is production-enabled — a production module (schema.py) imports the rule machine, so M12 no "
     "longer ships dark (R-07, U8.2)",
     [(SCHEMA, "TENANT_COLUMN = \"tenant\"",
       "from .rule import M12Machine  # MUTANT\nTENANT_COLUMN = \"tenant\"")],
     f"{T}::test_m12_ships_dark_no_production_importer"),
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
    Expected outcome: GREEN. If this is RED, the count is an assertion, not a measurement."""
    purge_pycache()
    green = run_guard(f"{T}::test_readiness_is_clean_on_a_fresh_canonical_database")
    return ("GREEN" if green else "RED"), ""


def main() -> int:
    assert_pristine()  # measure only a clean tree; a stranded mutation makes every count below a lie
    results = [(label, *_run_edits(edits, guard)) for label, edits, guard in CASES]
    control_verdict, _ = _baseline_control()

    print("\n=========== P6 M12 RULE MUTATION BATTERY ===========")
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
