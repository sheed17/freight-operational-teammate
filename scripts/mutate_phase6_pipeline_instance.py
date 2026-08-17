#!/usr/bin/env python3
"""Safe in-memory mutation battery for P6 M2 — the Pipeline Instance.

Doctrine (CLAUDE.md §9), identical to the P3/P4/P5/M1 batteries:
  * original bytes are held IN MEMORY — never `git checkout/restore/stash/clean`
  * __pycache__ is purged around every mutation
  * a guard that does NOT fail on the mutant proves nothing and is reported as a MISS
  * restoration is verified byte-for-byte, and the guard must be GREEN again before moving on
  * every case states the REAL defect it reintroduces

### WHAT THIS BATTERY IS FOR. M2's claim is that a broker cannot be billed twice, cannot have an
attempt vanish, and cannot have "we do not know whether it happened" quietly become "it failed".
Each of those is a mechanism, and a mechanism is worth exactly as much as the demonstration that
its guard can go red. Several cases below reintroduce defects THIS BUILD ACTUALLY HAD and its own
battery caught — P1b, P8b and P9a in particular.

### THIS IS NOT AN INDEPENDENT REVIEW. It was written by the session that implemented the unit.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv/bin/python"

PL = "src/freight_recon/pipeline_instance.py"
MIG = "src/freight_recon/migrations/phase6_pipeline_instances.py"
CKPT = "src/freight_recon/checkpoint.py"
# P5's transport is in range for the ordering cases only, and only for the exemption M2's own
# defect required. The mutants below attack THAT exemption; nothing else in the module is touched.
P5T = "src/freight_recon/migrations/phase5_event_transport.py"
SCHEMA = "src/freight_recon/schema.py"

T = "eval/tests/test_phase6_pipeline_instance.py"
T3 = "eval/tests/test_phase3_claim_cas.py"
T5 = "eval/tests/test_phase5_event_transport.py"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    r = subprocess.run([str(PY), "-m", "pytest", nodeid, "-q", "-p", "no:randomly"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


TEXT_CASES = [
    # ---- one attempt, one effect: the duplicate-invoice defence -------------------------------
    ("P1  the Layer-1 reservation stops being UNIQUE: two live attempts at one logical effect both "
     "insert, and a broker is billed twice for load 4471",
     MIG,
     '        "CREATE UNIQUE INDEX ix_pipeline_instances_live_reservation "',
     '        "CREATE INDEX ix_pipeline_instances_live_reservation "  # MUTANT',
     f"{T}::test_the_reservation_is_a_database_constraint_not_a_read_then_write"),

    ("P1a the reservation predicate stops excluding the terminal states, so a FINISHED attempt "
     "keeps holding the key and §20's retry becomes impossible — the failure that looks like "
     "safety and is actually a stuck obligation",
     MIG,
     '"ON pipeline_instances (tenant, commit_key) WHERE state NOT IN (" + _TERMINAL_SQL + ")"',
     '"ON pipeline_instances (tenant, commit_key) WHERE state IS NOT NULL"  # MUTANT',
     f"{T}::test_a_terminal_attempt_releases_the_reservation_and_a_live_one_does_not"),

    ("P1b PL-1b attaches its evidence WITHOUT advancing the holder's version — the reading this "
     "build actually shipped first. `DuplicateProposalAbsorbed` is an F2 contract and F2 is "
     "strictly ordered, so the event collides with the transition that owns that version and the "
     "absorption aborts: the duplicate is neither absorbed nor recorded",
     PL,
     "            new_version = holder.version + 1\n"
     "            cursor = self._conn.execute(",
     "            new_version = holder.version  # MUTANT: no durable evidence write\n"
     "            cursor = self._conn.execute(",
     f"{T}::test_pl_1b_a_second_proposal_for_one_effect_is_absorbed_not_raced"),

    ("P1c the absorbed-proposal identity drops the ABSORBED reference, so every duplicate proposal "
     "against one holder claims one identity: the second distinct duplicate is refused as a "
     "transport error and an operator counting 'how often does this happen' reads 1 forever",
     PL,
     '            holder.pipeline_instance_id, holder.commit_key, "PL-1b",\n'
     '            "DuplicateProposalAbsorbed", text,',
     '            holder.pipeline_instance_id, holder.commit_key, "PL-1b",\n'
     '            "DuplicateProposalAbsorbed",  # MUTANT: the attempt identity is gone',
     f"{T}::test_pl_1b_the_same_duplicate_absorbed_twice_is_one_record_two_duplicates_are_two"),

    ("P2  a retry may supersede an attempt that has NOT finished: the effect is attempted a second "
     "time while the first may still have touched the outside world (§20)",
     PL,
     "        if not superseded.is_terminal:",
     "        if False:  # MUTANT",
     f"{T}::test_needs_verification_never_auto_resolves_and_holds_the_reservation"),

    # ---- §41(a): GRANTED unreachable without a witness -----------------------------------------
    ("P3  the post-checkpoint trigger stops demanding a witness and a grant, so GRANTED is "
     "reachable by writing the word — an effect authorized by nobody",
     MIG,
     "        CREATE TRIGGER trg_pipeline_instances_post_checkpoint_carries_its_witness_update\n"
     "        BEFORE UPDATE ON pipeline_instances\n"
     "        WHEN NEW.state IN ({_POST_CHECKPOINT_SQL})",
     "        CREATE TRIGGER trg_pipeline_instances_post_checkpoint_carries_its_witness_update\n"
     "        BEFORE UPDATE ON pipeline_instances\n"
     "        WHEN 0 AND NEW.state IN ({_POST_CHECKPOINT_SQL})  -- MUTANT",
     f"{T}::test_granted_is_unreachable_without_a_witness_at_the_database"),

    ("P3a the witness/grant binding becomes rebindable, so a claimed effect can borrow another "
     "decision's authority: the ledger says CLAIMED for grant A while the attempt points at B",
     MIG,
     "        WHEN (OLD.checkpoint_id IS NOT NULL AND NEW.checkpoint_id IS NOT OLD.checkpoint_id)\n"
     "          OR (OLD.grant_id IS NOT NULL AND NEW.grant_id IS NOT OLD.grant_id)",
     "        WHEN 0  # MUTANT",
     f"{T}::test_the_witness_binding_is_write_once"),

    ("P3b terminal stops being terminal: retry-in-place becomes reachable, which §15 lists as "
     "ILLEGAL because the attempt being mutated may already have moved money",
     MIG,
     "        WHEN OLD.state IN ({_TERMINAL_SQL})\n"
     "        BEGIN SELECT RAISE(ABORT, '{TERMINAL_ABORT}'); END",
     "        WHEN 0\n"
     "        BEGIN SELECT RAISE(ABORT, '{TERMINAL_ABORT}'); END  # MUTANT",
     f"{T}::test_retry_in_place_is_impossible_at_the_database"),

    ("P3c the version counter may stand still, so two events claim one aggregate version on a "
     "STRICTLY ORDERED family and a lost update is invisible (GR-3)",
     MIG,
     "        WHEN NEW.version <> OLD.version + 1",
     "        WHEN 0  # MUTANT",
     f"{T}::test_the_version_counter_advances_by_exactly_one_and_the_database_says_so"),

    ("P3d an attempt's identity becomes editable: the commit key can be repointed, which retargets "
     "an authorization granted for a DIFFERENT effect at a row an audit would still read as "
     "internally consistent",
     MIG,
     "        BEFORE UPDATE OF tenant, pipeline_instance_id, work_item_id, commit_key, action_class,",
     "        BEFORE UPDATE OF gate_reason,  -- MUTANT: identity columns no longer guarded\n"
     "                         action_class,",
     f"{T}::test_the_identity_of_an_attempt_is_immutable"),

    # ---- GR-5 / GR-6: the money-losing distinction ---------------------------------------------
    ("P4  FAILED stops requiring a proof at the guard: a timeout becomes 'nothing happened', the "
     "attempt terminates, the reservation frees, and the retry pays the invoice a second time",
     PL,
     '            if not (facts.failure_proof or "").strip():\n'
     '                return (\n'
     '                    "PL-10f requires a `failure_proof`',
     '            if False:  # MUTANT\n'
     '                return (\n'
     '                    "PL-10f requires a `failure_proof`',
     f"{T}::test_pl_10f_failed_requires_affirmative_proof_of_non_occurrence"),

    ("P4a FAILED stops requiring a proof at the DATABASE, so a write around the machine reaches the "
     "same double-pay state (GR-5 held against a connection)",
     MIG,
     "        WHEN NEW.state = 'FAILED'\n"
     "         AND (NEW.failure_proof IS NULL OR trim(NEW.failure_proof) = '')",
     "        WHEN 0  # MUTANT",
     f"{T}::test_failed_without_a_proof_is_unwritable_at_the_database"),

    ("P4b PL-15 may close an UNKNOWN OUTCOME as FAILED on a human's opinion rather than on "
     "affirmative evidence — the guess this state exists to prevent, with a decision_ref attached "
     "to make it look rigorous",
     PL,
     '            if stated == PipelineState.FAILED.value and not (facts.failure_proof or "").strip():',
     "            if False:  # MUTANT",
     f"{T}::test_pl_15_may_only_conclude_FAILED_on_affirmative_evidence"),

    ("P4c PL-15's target state comes from the CALLER instead of from the establishing event, so an "
     "unreadable outcome resolves to a default — GR-6's exact prohibition",
     PL,
     "        raise GuardNotSatisfied(\n"
     '            f"{row.id} reaches {row.to_state.value if row.to_state else \'?\'} or "',
     "        return row.to_state  # MUTANT: an unreadable outcome defaults\n"
     "        raise GuardNotSatisfied(\n"
     '            f"{row.id} reaches {row.to_state.value if row.to_state else \'?\'} or "',
     f"{T}::test_pl_15_target_state_comes_from_the_event_never_from_the_caller"),

    ("P5  a timer may move NEEDS_VERIFICATION: GR-6's named merge-gating anchor (AC-MACH-215x) "
     "becomes expressible, and an unknown outcome auto-resolves on a deadline",
     PL,
     '        id="PL-15x", from_states=(PipelineState.NEEDS_VERIFICATION,), to_state=None,\n'
     "        triggers=(Trigger.TIMER_FIRED,), trigger_types=(\"T\",),\n"
     "        kind=RowKind.NON_PRODUCING, illegal=True,",
     '        id="PL-15x", from_states=(PipelineState.NEEDS_VERIFICATION,),\n'
     "        to_state=PipelineState.VERIFIED,  # MUTANT\n"
     "        triggers=(Trigger.TIMER_FIRED,), trigger_types=(\"T\",),\n"
     "        kind=RowKind.NON_PRODUCING, illegal=False,",
     f"{T}::test_ac_mach_215x_no_timer_moves_needs_verification"),

    # ---- GR-1: the security record -------------------------------------------------------------
    ("P6  the illegal-attempt identity drops the ATTEMPT component — M1's rejected defect, "
     "reintroduced on M2: several DISTINCT hostile attempts against one attempt at one version "
     "collide, only the first is ever recorded, and the rest surface as transport errors",
     PL,
     '            item.pipeline_instance_id, str(item.version), ILLEGAL_TRANSITION_PRODUCER,\n'
     '            "IllegalTransitionAttempted", text,',
     '            item.pipeline_instance_id, str(item.version), ILLEGAL_TRANSITION_PRODUCER,\n'
     '            "IllegalTransitionAttempted",  # MUTANT: the attempt identity is gone',
     f"{T}::test_gr1_every_omitted_pair_is_illegal_persists_nothing_and_is_recorded"),

    ("P6a the security half of [C-4] stops being written, so the audit backbone knows about a "
     "hostile attempt that the surface an operator is PAGED FROM does not",
     PL,
     '            (self._tenant, next_id, "IllegalTransitionAttempted", actor_id,',
     '            (self._tenant, next_id, "NotASecurityEvent",  # MUTANT\n'
     "             actor_id,",
     f"{T}::test_ac_mach_215x_no_timer_moves_needs_verification"),

    ("P6b the strict-ordering exemption for order-tolerant families is withdrawn, restoring the "
     "state this build shipped first: `IllegalTransitionAttempted` — an F14 contract §8 declares "
     "ORDER-TOLERANT — becomes uninsertable on a strict aggregate, so the refusal works and its "
     "EVIDENCE cannot be written at all",
     P5T,
     "        WHEN NEW.aggregate_type IN ({_STRICT_SQL_LIST})\n"
     "         AND NEW.event_name IN ({_STRICT_EVENTS_SQL})",
     "        WHEN NEW.aggregate_type IN ({_STRICT_SQL_LIST})  # MUTANT",
     f"{T}::test_gr1_every_omitted_pair_is_illegal_persists_nothing_and_is_recorded"),

    ("P6c the strict-ordering trigger is exempted for EVERYTHING (an empty strict-event set), so "
     "the rule §8 requires stops being enforced for the families that DO need it — the opposite "
     "failure, and the one a relaxation is most likely to cause by accident",
     P5T,
     '_STRICT_FAMILIES: frozenset[str] = frozenset({"F2", "F3", "F4", "F11", "F13"})',
     '_STRICT_FAMILIES: frozenset[str] = frozenset({"F2", "F3", "F4", "F11", "F13"})\n'
     "# MUTANT below narrows the derived set to a family nothing rides on\n"
     '_STRICT_FAMILIES = frozenset({"F99"})',
     f"{T5}::test_two_different_transitions_cannot_claim_one_strict_version"),

    # ---- §30 / §17: never both, never neither ---------------------------------------------------
    ("P7  PL-9 commits the pipeline's own write in a SEPARATE transaction from the CAS, so a brake "
     "engaged between them produces a claimed grant with an unclaimed attempt — §30's 'both'",
     PL,
     "            pending = claim_grant_cas_locked(kernel, handle, params, now=self._clock())\n"
     "            if pending.outcome.claimed:",
     "            conn.rollback()  # MUTANT: the CAS gets its own transaction\n"
     "            from .checkpoint import claim_grant_cas_locked_outside_a_transaction\n"
     "            pending = claim_grant_cas_locked_outside_a_transaction(\n"
     "                kernel, handle, params, now=self._clock())\n"
     "            conn.execute(\"BEGIN IMMEDIATE\")\n"
     "            if pending.outcome.claimed:",
     f"{T}::test_pl_9_rolls_the_claim_back_when_its_own_row_write_fails"),

    ("P7a the claim CAS's WHERE clause loses its brake revalidation, so a brake engaged between "
     "the checkpoint and the claim does NOT stop the effect — CLAUDE.md §11's explicit prohibition",
     CKPT,
     "             WHERE tenant = ? AND grant_id = ? AND state = 'GRANTED'\n"
     "               AND expires_at > ? AND brake_version = ? AND policy_version = ?",
     "             WHERE tenant = ? AND grant_id = ? AND state = 'GRANTED'\n"
     "               AND expires_at > ? AND ? IS NOT NULL AND policy_version = ?  -- MUTANT",
     f"{T}::test_a_brake_engaged_between_checkpoint_and_claim_stops_both_halves"),

    ("P7b PL-9 stops checking that the handle names THIS attempt's grant, so an attempt can claim "
     "a capability minted for a different decision (the confused deputy, one layer above the CAS)",
     PL,
     "        if item.grant_id and handle.grant_id != item.grant_id:",
     "        if False:  # MUTANT",
     f"{T}::test_pl_9_refuses_a_grant_this_attempt_does_not_hold"),

    # ---- §4: the checkpoint co-commit -----------------------------------------------------------
    ("P8  PL-8 commits the checkpoint in its own transaction and writes the pipeline row after it, "
     "so a crash in between leaves a witness and a grant for an attempt that never reached GRANTED "
     "— an authorization nobody is accountable for",
     PL,
     "            outcome = run_checkpoint_locked(kernel, request, inputs, now=self._clock())\n"
     "            if isinstance(outcome, CheckpointAuthorized):",
     "            from .checkpoint import run_checkpoint as _rc  # MUTANT: separate transactions\n"
     "            conn.rollback()\n"
     "            outcome = _rc(kernel, request, inputs)\n"
     "            conn.execute(\"BEGIN IMMEDIATE\")\n"
     "            if isinstance(outcome, CheckpointAuthorized):",
     f"{T}::test_pl_8_rolls_the_witness_and_the_grant_back_when_its_own_row_write_fails"),

    ("P8a the checkpoint request takes its effect from CALLER-SUPPLIED facts instead of from the "
     "row, so one attempt can be validated for one effect and authorized for another",
     PL,
     "            effect=item.effect, actor=actor_id, accountable_owner=item.owner_id,",
     "            effect=facts.extra.get(\"effect\", item.effect),  # MUTANT\n"
     "            actor=actor_id, accountable_owner=item.owner_id,",
     f"{T}::test_the_checkpoint_request_is_built_from_the_row_not_from_the_caller"),

    ("P8b `CheckpointPassed` pins the decision context from a fresh read instead of from the "
     "WITNESS, so an audit reconstructs why the effect was allowed using today's beliefs "
     "(ER-13's exact failure)",
     PL,
     "            entity_versions=dict(witness.entity_versions),\n"
     "            policy_version=witness.policy_version, brake_version=witness.brake_version,",
     "            entity_versions={\"mutant\": 1},  # MUTANT\n"
     "            policy_version=witness.policy_version, brake_version=witness.brake_version,",
     f"{T}::test_pl_8_co_commits_the_witness_the_grant_and_this_row"),

    # ---- ownership and authority ----------------------------------------------------------------
    ("P9  the attempt's owner is taken from the caller instead of from the Work Item, so an attempt "
     "is accountable to somebody other than the human who owes the work (§5, rule 13)",
     MIG,
     "        BEFORE UPDATE OF owner_id ON pipeline_instances\n"
     "        WHEN NEW.owner_id IS NOT (SELECT owner_id FROM work_items",
     "        BEFORE UPDATE OF owner_id ON pipeline_instances\n"
     "        WHEN 0 AND NEW.owner_id IS NOT (SELECT owner_id FROM work_items  -- MUTANT",
     f"{T}::test_the_owner_must_be_the_work_items_owner_and_the_database_enforces_it"),

    ("P9d the SAME §5 rule on the way IN: an attempt may be CREATED accountable to somebody who "
     "does not own the Work Item, so the whole creation path is open even while the update path "
     "is guarded",
     MIG,
     "        BEFORE INSERT ON pipeline_instances\n"
     "        WHEN NEW.owner_id IS NOT (SELECT owner_id FROM work_items",
     "        BEFORE INSERT ON pipeline_instances\n"
     "        WHEN 0 AND NEW.owner_id IS NOT (SELECT owner_id FROM work_items  -- MUTANT",
     f"{T}::test_an_attempt_cannot_be_INSERTED_for_a_human_who_does_not_own_the_work_item"),

    ("P9a a consumed event for an attempt that does not exist parks with a NULL accountable owner "
     "— rule 13's one exception, created by the method whose contract promises otherwise (M1's "
     "F-02, reintroduced on M2)",
     PL,
     "        raise OwnershipRefused(\n"
     '            f"{envelope.event_name} references Pipeline Instance',
     "        return None  # MUTANT: park it on nobody\n"
     "        raise OwnershipRefused(\n"
     '            f"{envelope.event_name} references Pipeline Instance',
     f"{T}::test_a_consumption_that_can_establish_no_accountable_human_refuses_and_writes_nothing"),

    ("P9b a model may drive the machine: C-6/GR-7/§40 stop being enforced and an inferred fact "
     "becomes an authorized attempt",
     PL,
     "        if actor_type not in PERMITTED_ACTOR_TYPES:",
     "        if False:  # MUTANT",
     f"{T}::test_a_model_may_never_drive_this_machine"),

    ("P9c PL-7b stops requiring an authenticated HUMAN actor, so automation binds the approval that "
     "authorizes the effect — authority broadened by a machine (§7)",
     PL,
     '        if "H" in row.trigger_types and len(row.trigger_types) == 1:',
     "        if False:  # MUTANT",
     f"{T}::test_pl_7b_is_an_H_transition_and_refuses_a_system_actor"),

    # ---- policy, validation and projection -------------------------------------------------------
    ("P10 PL-2 admits a MODEL_INFERRED material fact, so an inference gates a consequential "
     "transition — GR-8, at any confidence",
     PL,
     "            if facts.model_inferred_material_fact is not False:",
     "            if False:  # MUTANT",
     f"{T}::test_pl_2_refuses_a_null_gate_and_a_model_inferred_material_fact"),

    ("P10a PL-2 admits a NULL gate decision: F-20's 'a gate expressible as an absence is not a "
     "gate', restored",
     PL,
     "            gate = _gate_value(facts.gate_decision)\n"
     "            if not gate:",
     "            gate = _gate_value(facts.gate_decision)\n"
     "            if False:  # MUTANT",
     f"{T}::test_pl_2_refuses_a_null_gate_and_a_model_inferred_material_fact"),

    ("P10b PL-4 stops requiring the fences to have been RUN, so an unstated check is read as a "
     "passed one and an intent is validated on evidence nobody looked at",
     PL,
     "                if value is not True:",
     "                if False:  # MUTANT",
     f"{T}::test_pl_4_will_not_infer_a_fence_it_did_not_run"),

    ("P10c PL-7a admits autonomously with a BREACHED cap, so a cap becomes a suggestion",
     PL,
     "            breached = sorted(k for k, v in caps.items() if v is not True)",
     "            breached = []  # MUTANT",
     f"{T}::test_pl_7a_refuses_an_autonomous_admission_with_a_breached_or_unevaluated_cap"),

    ("P10d PL-11 accepts a readback that does NOT match the approved fingerprint, so 'verified' "
     "stops meaning 'the world holds what the human approved'",
     PL,
     "            if facts.matched_fingerprint != approved:",
     "            if False:  # MUTANT",
     f"{T}::test_pl_11_requires_the_readback_to_match_the_APPROVED_fingerprint"),

    ("P10e PL-13 projects from ANY effect id, so one effect's readback can be projected onto "
     "another's entity — a projection stating something nobody observed (M-2)",
     PL,
     "            if facts.from_effect_id != item.grant_id:",
     "            if False:  # MUTANT",
     f"{T}::test_pl_13_projects_only_from_this_attempts_verified_evidence"),

    ("P10f verify and record stop sharing a commit: PL-12 no longer follows PL-11, so a crash "
     "between them loses the record of a verified effect (acceptance item (f))",
     PL,
     "        follower = next(\n"
     "            (r for r in TRANSITIONS if r.co_commits_with == row.id), None)",
     "        follower = None  # MUTANT",
     f"{T}::test_acceptance_f_verify_and_record_are_one_commit"),

    # ---- containment ------------------------------------------------------------------------------
    ("P11 the second-ledger guard stops requiring a table that reserves a commit key to be "
     "answerable to `effect_grants`, so a genuinely independent second effect ledger passes "
     "readiness (CLAUDE.md rule 17)",
     SCHEMA,
     '        if "effect_grants" not in referents:',
     "        if False:  # MUTANT",
     f"{T}::test_a_table_that_reserves_a_commit_key_without_answering_to_the_ledger_is_refused"),

    ("P12 the M2 migration restates the gate vocabulary literally instead of deriving it from P3's "
     "witness table, re-creating the second copy of ADR-010's ladder that "
     "`test_phase0_null_gate.py` exists to notice",
     MIG,
     "GATE_DECISIONS: tuple[str, ...] = _gate_decisions_from_the_witness_table()",
     "GATE_DECISIONS: tuple[str, ...] = (  # MUTANT\n"
     '    "HUMAN_APPROVAL_REQUIRED", "AUTONOMOUS_WITHIN_CAPS",\n'
     '    "PERMANENT_HUMAN_ASSERTION_REQUIRED", "FORBIDDEN")',
     f"{T}::test_the_gate_vocabulary_is_derived_from_p3_and_not_restated"),
]


# ### THE POSITIVE CONTROL FOR THE SWEEP ITSELF.
# Every case above shows a guard going red. This one shows the OPPOSITE risk: that the sweep's
# population is what makes it work. Shrinking the transition table by one row must be caught by
# AC-MACH-000's set equality — if it is not, every "exhaustive" claim in the battery is over a set
# somebody could quietly shrink.
STRUCTURAL_CASES = [
    ("P13 one §14 row is deleted from the implementation's table: AC-MACH-000's bijection must "
     "notice, because a count-based oracle would not",
     PL,
     '    TransitionRow(\n        id="PL-11d", from_states=(PipelineState.EXECUTED,), '
     "to_state=PipelineState.EXECUTED,\n"
     "        triggers=(Trigger.READBACK_DEFERRED,), trigger_types=(\"X\",),\n"
     '        kind=RowKind.PRODUCER, event_name="VerificationDeferred",\n'
     '        emits_on_foreign_aggregate="effect_grant",\n    ),\n',
     "",
     f"{T}::test_ac_mach_000_transition_identifiers_are_a_bijection_with_the_specification"),
]

# ==================================================================================================
# F-01 — CLAIMED WITHOUT A CAS, AND THE CONSUMED KERNEL TRIGGER. The defects the first independent
# review of this unit REJECTED the candidate on. Each mutant below removes one part of the
# structural refusal and must make a guard go red; a guard that survives its own removal is the
# decoration §9 exists to catch.
# ==================================================================================================
F01_CASES = [
    ("K1  the ordinary guard path stops refusing kernel-owned rows — THE REJECTED CANDIDATE'S "
     "DEFECT EXACTLY. A contract-valid canonical `GrantClaimed` consumed through the public API "
     "moves GRANTED -> CLAIMED with no CAS, no grant handle, no kernel and a grant ledger still "
     "reading GRANTED: the pipeline says the effect is claimed and the ledger says nobody claimed "
     "it, which is how one authorization pays an invoice twice",
     PL,
     "        if row.id in KERNEL_OWNED_ROW_IDS:\n            return (",
     "        if False and row.id in KERNEL_OWNED_ROW_IDS:  # MUTANT\n            return (",
     f"{T}::test_a_consumed_grant_claimed_cannot_reach_claimed_without_the_cas"),

    ("K1a the same refusal removed, proved against the CHECKPOINT half: a consumed CHECKPOINT_RUN "
     "selects PL-8f by precedence, cannot satisfy the kernel's `{step, reason}` payload, and raises "
     "INSIDE the inbox transaction — the receipt rolls back and the event is redelivered forever",
     PL,
     "        if row.id in KERNEL_OWNED_ROW_IDS:\n            return (",
     "        if False and row.id in KERNEL_OWNED_ROW_IDS:  # MUTANT\n            return (",
     f"{T}::test_a_consumed_checkpoint_run_cannot_invoke_the_kernel_and_does_not_poison_the_inbox"),

    ("K2  the kernel-owned population stops taking its (state, trigger) closure, so PL-8f — the "
     "checkpoint's failure branch, whose payload only the kernel can supply — becomes reachable "
     "from the ordinary path again while PL-8 and PL-9 stay refused",
     PL,
     "        if row.consequential\n"
     "        or any((state, trig) in pairs for state in row.from_states for trig in row.triggers)",
     "        if row.consequential  # MUTANT: the closure is dropped",
     f"{T}::test_the_kernel_owned_population_is_derived_and_covers_every_consequential_row"),

    ("K3  the §15 classification degrades to an ordinary guard failure, so an attempt to reach "
     "CLAIMED without a CAS leaves NO `IllegalTransitionAttempted` in the audit backbone or "
     "`security_events` — the refusal still holds and the evidence of the attempt is gone, which "
     "is the quiet half of the same defect",
     PL,
     "            if all(row.id in KERNEL_OWNED_ROW_IDS for row in candidates):",
     "            if False:  # MUTANT",
     f"{T}::test_a_kernel_bypass_attempt_is_recorded_as_illegal_not_as_a_guard_failure"),

    ("K4  `apply`'s kernel dispatch stops being derived and falls through to the ordinary path for "
     "a consequential row whose executor is missing — the silent route by which a NEW consequential "
     "transition would acquire an unguarded execution path",
     PL,
     "            if entry is None:\n                raise AuthorityRefused(",
     "            if entry is None and False:  # MUTANT\n                raise AuthorityRefused(",
     f"{T}::test_a_consequential_row_without_an_executor_fails_closed"),

    ("K5  PL-9 is un-declared as consequential, so the derivation empties by one row and the claim "
     "CAS is no longer the only way into CLAIMED",
     PL,
     'kind=RowKind.CONSUMES, consumes=("GrantClaimed",), consequential="claim",',
     'kind=RowKind.CONSUMES, consumes=("GrantClaimed",),  # MUTANT',
     f"{T}::test_a_consumed_grant_claimed_cannot_reach_claimed_without_the_cas"),
]

# ==================================================================================================
# F-02 — THE FALSE-GREEN DARK-SURFACE GUARD. The original enumerated adapter names by hand and
# recognised two of Python's import spellings. Each mutant introduces a REAL reachability path (or a
# real population change) and the corrected guard must go red on every one of them.
# ==================================================================================================
IMPORT_PROBE = "eval/phase0/import_probe.py"
TENANT = "src/freight_recon/tenant.py"
SURFACE = "docs/implementation/IMPLEMENTATION-SURFACE.yaml"
_UTC = "def _utc_now() -> datetime:\n    return datetime.now(timezone.utc)"
DARK = f"{T}::test_m2_cannot_reach_an_effect_capable_adapter"

F02_CASES = [
    ("D1  `pipeline_instance` gains a DIRECT absolute from-import of an effect-capable adapter — "
     "the spelling the old walker could not see at all, and the dominant spelling in this package",
     PL, _UTC,
     "def _utc_now() -> datetime:\n"
     "    from freight_recon.discovered_write import DiscoveredFormWriter  # MUTANT\n"
     "    return datetime.now(timezone.utc)",
     DARK),

    ("D2  the leak is spelled as a dotted module import instead", PL, _UTC,
     "def _utc_now() -> datetime:\n"
     "    import freight_recon.discovered_write as _dw  # MUTANT\n"
     "    return datetime.now(timezone.utc)",
     DARK),

    ("D3  the leak is spelled `from . import x` — the form ALREADY in live use at "
     "`governed_write_route.py:359` and `action_callback.py:629`, so this is not hypothetical "
     "syntax; the old walker was blind to it",
     PL, _UTC,
     "def _utc_now() -> datetime:\n"
     "    from . import discovered_write  # MUTANT\n"
     "    return datetime.now(timezone.utc)",
     DARK),

    ("D4  the leak is spelled `importlib.import_module` with a literal — statically resolvable, and "
     "invisible to a walker that only reads import statements",
     PL, _UTC,
     "def _utc_now() -> datetime:\n"
     "    importlib.import_module('freight_recon.discovered_write')  # MUTANT\n"
     "    return datetime.now(timezone.utc)",
     DARK),

    ("D5  the leak is TRANSITIVE: `tenant`, two hops inside M2's closure, gains the adapter import. "
     "M2 itself imports nothing new, which is exactly the shape a closure walk exists to catch",
     TENANT,
     "FORBIDDEN_TENANTS = frozenset({",
     "from freight_recon.discovered_write import DiscoveredFormWriter  # MUTANT\n\n"
     "FORBIDDEN_TENANTS = frozenset({",
     DARK),

    ("D6  ### THE HAND-LIST DEFECT ITSELF. A module already inside M2's closure is classified "
     "effect-capable in the CANONICAL population, and nothing in the M2 test is touched. The old "
     "guard could not have noticed; the derived one must go red on the same commit",
     IMPORT_PROBE,
     'EFFECT_CAPABLE_ADAPTERS = {\n    "cdp_actuator", "browser_tms_adapter",',
     'EFFECT_CAPABLE_ADAPTERS = {\n    "reconciliation",  # MUTANT\n'
     '    "cdp_actuator", "browser_tms_adapter",',
     DARK),

    ("D7  the recorded M2 surface stops naming the Pipeline Instance entity, so the guard can no "
     "longer derive its roots from repository authority — it must REFUSE rather than fall back to "
     "a name typed into the test",
     SURFACE,
     "  - name: Pipeline Instance",
     "  - name: Pipeline Instance Renamed  # MUTANT",
     DARK),

    ("D8  the closure walk stops following relative imports, which is how the previous walker lost "
     "every hop inside `migrations/` and every module using the relative form",
     IMPORT_PROBE,
     "            if node.level:\n                base = _ascend(package, node.level)",
     "            if node.level and False:  # MUTANT\n                base = _ascend(package, node.level)",
     f"{T}::test_the_dark_surface_guard_can_actually_fire"),

    ("D9  the walk stops expanding its frontier, so the 'closure' is the roots and nothing else. "
     "The M-9 false-green: a walk that inspected almost nothing reporting no leak. The denominator "
     "guard is what must catch it",
     IMPORT_PROBE,
     "            if target in modules and target not in seen:\n                frontier.append(target)",
     "            if target in modules and target not in seen and False:  # MUTANT\n"
     "                frontier.append(target)",
     DARK),
]


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


def _run_text_case(case) -> tuple[str, str]:
    _, rel, old, new, guard = case
    return _run_edits(((rel, old, new),), guard)


def main() -> int:
    cases = TEXT_CASES + STRUCTURAL_CASES + F01_CASES + F02_CASES
    results = [(c[0], *_run_text_case(c)) for c in cases]
    print("\n=========== P6 M2 PIPELINE INSTANCE MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    print("  NOTE: written by the session that implemented the unit - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
