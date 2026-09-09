"""### THE `P6-AC-5` TRACEABILITY REGISTER: CANONICAL ID -> THE EVIDENCE THAT ACTUALLY PROVES IT.

`foundational-machine-acceptance.md` ends with two obligations that are not transition rows:

  * *"Per-machine mandatory assertions (every machine, every case)"* — ten numbered assertions; and
  * *"The named anchors (merge-gating)"* — seven `AC-MACH-*` ids, each with a one-line claim.

### THE BEHAVIOUR EXISTED AND THE IDS DID NOT. `AC-MACH-208`, `AC-MACH-605x` and `AC-MACH-1305`
appeared nowhere under `eval/` or `scripts/`, and `AC-MACH-903` appeared only in a probe's prose. The
checkpoint IS atomic, the relinker IS refused, no timer DOES release a brake and an exception close
DOES require a decision — but nothing mechanical connected the canonical name to the thing that proves
it, so "is `AC-MACH-1305` verified?" could only be answered by a person reading tests.

### THIS FILE IS THE SMALLEST THING THAT FIXES THAT, AND IT INVENTS NOTHING. Every entry points at a
test that ALREADY EXISTED and already passed. No duplicate behaviour test was written to make an id
appear; where an assertion has no evidence, it is recorded as a GAP rather than papered over — see
`UNEVIDENCED` below and the ratchet that keeps it from growing.

`test_phase6_anchor_traceability.py` proves, for every entry: the id is required by the authority, the
target exists, pytest COLLECTS it, and — for the seven anchors — the evidence site NAMES its own
anchor, so the trace works from either end."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Anchor:
    """One merge-gating anchor, its canonical transition, and the evidence that proves it."""

    anchor: str
    transition: str          # the §14 row the id encodes: AC-MACH-<machine number><row suffix>
    claim: str               # the acceptance file's own words
    evidence: tuple[str, ...]  # `<test file>::<test function>` node ids


# ### THE SEVEN MERGE-GATING ANCHORS. The `transition` column is not decoration: the guard derives
# `AC-MACH-<n><suffix>` from it and checks the derivation reproduces the anchor id, which is what makes
# `AC-MACH-605x` provably "M6's IB-5x" rather than a string somebody typed.
ANCHORS: tuple[Anchor, ...] = (
    Anchor(
        anchor="AC-MACH-208", transition="PL-8",
        claim="the checkpoint transition (all seven, atomic)",
        evidence=(
            "test_phase6_pipeline_instance.py::test_pl_8_co_commits_the_witness_the_grant_and_this_row",
            "test_phase6_pipeline_instance.py::test_pl_8_rolls_the_witness_and_the_grant_back_when_its_own_row_write_fails",
        )),
    Anchor(
        anchor="AC-MACH-209", transition="PL-9",
        claim="the claim CAS (single-use)",
        evidence=(
            "test_phase6_pipeline_instance.py::test_pl_9_is_single_use_and_a_second_claim_moves_nothing",
        )),
    Anchor(
        anchor="AC-MACH-210u", transition="PL-10u",
        claim="CLAIMED + crash => NEEDS_VERIFICATION, never FAILED",
        evidence=(
            "test_phase6_pipeline_instance.py::test_ac_mach_210u_a_crash_after_the_claim_is_unknown_never_failed",
        )),
    Anchor(
        anchor="AC-MACH-215x", transition="PL-15x",
        claim="no timer moves NEEDS_VERIFICATION (ILLEGAL)",
        evidence=(
            "test_phase6_pipeline_instance.py::test_ac_mach_215x_no_timer_moves_needs_verification",
            "test_phase6_transition_sweep.py::test_ac_mach_215x_no_timer_moves_needs_verification",
        )),
    Anchor(
        anchor="AC-MACH-605x", transition="IB-5x",
        claim="OWNER_ASSERTED + RecomputedByInferrer => ILLEGAL (the B3 regression)",
        evidence=(
            "test_phase6_identity_binding_claim.py::test_owner_binding_survives_relinker",
            "test_phase6_identity_binding_claim.py::test_ib5x_is_declared_illegal_and_changes_no_legality",
        )),
    Anchor(
        anchor="AC-MACH-903", transition="EC-3",
        claim="Exception close requires a resolving decision_ref",
        evidence=(
            "test_phase6_exception.py::test_ec_close_requires_valid_decision_ref",
        )),
    Anchor(
        anchor="AC-MACH-1305", transition="BR-5",
        claim="no timer releases a brake",
        evidence=(
            "test_phase6_brake.py::test_no_timer_can_move_a_brake",
            "test_phase6_brake.py::test_a_brake_never_auto_expires",
            "test_phase6_transition_sweep.py::test_ac_mach_1305_no_timer_releases_a_brake",
        )),
)


# --------------------------------------------------------------- the ten per-machine assertions

@dataclass(frozen=True)
class Assertion:
    """One of the ten, with the machines the AUTHORITY's own wording applies it to."""

    number: int
    text: str
    # `None` = every machine. A tuple = the machines the acceptance file's own sentence names, and
    # the reason is carried in `restriction` so a narrowing is read rather than assumed.
    applies_to: tuple[str, ...] | None
    restriction: str = ""


ASSERTIONS: tuple[Assertion, ...] = (
    Assertion(1, "every legal transition succeeds under its EXACT guards, and fails when any guard "
                 "is relaxed by one condition (a guard-mutation probe)", None),
    Assertion(2, "every omitted transition is ILLEGAL — an exhaustive (state x trigger) sweep", None),
    Assertion(3, "version conflicts fail deterministically — a stale expected_version => zero rows "
                 "=> raise", None),
    Assertion(4, "duplicate triggers are idempotent — the inbox key makes redelivery a no-op", None),
    Assertion(5, "terminal states have NO prohibited outgoing transitions", None),
    Assertion(6, "reopening creates a new phase or linked Work Item; the prior closure event is "
                 "byte-identical afterward",
              ("M1",),
              "the assertion names the reopen as `WI-13`, and WI-13 is M1's only; no other machine "
              "has a reopen row in its §14 table."),
    Assertion(7, "historical transitions are NEVER rewritten — an append-only probe", None),
    Assertion(8, "crash recovery reaches the canonical state", None),
    Assertion(9, "ownership remains valid — no transition leaves a Work Item/Exception ownerless",
              ("M1", "M9"),
              "the assertion names the Work Item and the Exception; M1 and M9 are those machines. "
              "Other machines' accountability invariants are asserted by their own batteries but are "
              "not what this sentence requires."),
    Assertion(10, "tenant isolation intact — every case runs T_A/T_B", None),
)

# The thirteen machines' acceptance modules, keyed the way `phase6_machine_population_kit` labels
# them. The guard cross-checks these keys against the DISCOVERED population, so a machine that
# disappears cannot quietly drop out of this register either.
MACHINE_FILES: dict[str, str] = {
    "M1": "test_phase6_work_item.py",
    "M2": "test_phase6_pipeline_instance.py",
    "M3": "test_phase6_external_effect.py",
    "M4": "test_phase6_approval.py",
    "M5": "test_phase6_observation.py",
    "M6": "test_phase6_identity_binding_claim.py",
    "M7": "test_phase6_conflict.py",
    "M8": "test_phase6_expectation.py",
    "M9": "test_phase6_exception.py",
    "M10": "test_phase6_compensation.py",
    "M11": "test_phase6_policy.py",
    "M12": "test_phase6_rule.py",
    "M13": "test_phase6_brake.py",
}

# Assertion 1's evidence is the same shape for all thirteen and is a PROBE, not a test: the
# guard-mutation battery each unit ships. Named here so the guard can check the file exists.
MUTATION_PROBES: dict[str, str] = {
    "M1": "scripts/mutate_phase6_work_item.py",
    "M2": "scripts/mutate_phase6_pipeline_instance.py",
    "M3": "scripts/mutate_phase6_external_effect.py",
    "M4": "scripts/mutate_phase6_approval.py",
    "M5": "scripts/mutate_phase6_observation.py",
    "M6": "scripts/mutate_phase6_identity_binding_claim.py",
    "M7": "scripts/mutate_phase6_conflict.py",
    "M8": "scripts/mutate_phase6_expectation.py",
    "M9": "scripts/mutate_phase6_exception.py",
    "M10": "scripts/mutate_phase6_compensation.py",
    "M11": "scripts/mutate_phase6_policy.py",
    "M12": "scripts/mutate_phase6_rule.py",
    "M13": "scripts/mutate_phase6_brake.py",
}

# ### THE REGISTER. `(machine, assertion number) -> node ids`, every one of which already existed.
# Assertion 1 is served by MUTATION_PROBES and assertion 2 additionally by the phase-wide sweep, so
# neither is repeated per machine here.
EVIDENCE: dict[tuple[str, int], tuple[str, ...]] = {
    # ---- M1 Work Item
    ("M1", 2): ("test_gr1_every_omitted_pair_is_illegal_and_recorded",
                "test_the_illegal_sweep_has_a_proven_population"),
    ("M1", 3): ("test_a_stale_expected_version_fails_deterministically",
                "test_the_occ_where_clause_carries_the_version_predicate"),
    ("M1", 4): ("test_a_redelivered_trigger_is_a_no_op_and_the_digest_is_byte_identical",),
    ("M1", 5): ("test_a_terminal_item_refuses_everything",
                "test_a_terminal_row_cannot_be_moved_by_raw_sql"),
    ("M1", 6): ("test_reopening_preserves_the_prior_closure_event_byte_identically",
                "test_a_closed_row_may_only_leave_through_a_new_phase"),
    ("M1", 7): ("test_a_recorded_authority_is_append_only",),
    ("M1", 8): ("test_a_trigger_for_a_work_item_that_does_not_exist_yet_is_parked_not_looped",),
    ("M1", 9): ("test_no_transition_leaves_a_work_item_ownerless",
                "test_the_ownerless_detector_runs_over_a_proven_population"),
    ("M1", 10): ("test_a_tenant_b_trigger_never_moves_a_tenant_a_machine",),
    # ---- M2 Pipeline Instance
    ("M2", 2): ("test_gr1_every_omitted_pair_is_illegal_persists_nothing_and_is_recorded",),
    ("M2", 3): ("test_gr3_a_stale_expected_version_refuses_rather_than_overwriting",),
    ("M2", 4): ("test_gr4_a_redelivered_trigger_is_a_no_op_measured_byte_for_byte",),
    ("M2", 5): ("test_the_terminal_set_is_exactly_the_four_of_section_8",
                "test_a_terminal_attempt_releases_the_reservation_and_a_live_one_does_not"),
    ("M2", 7): ("test_the_identity_of_an_attempt_is_immutable", "test_an_attempt_is_never_deleted"),
    ("M2", 8): ("test_ac_mach_210u_a_crash_after_the_claim_is_unknown_never_failed",),
    ("M2", 10): ("test_c1_an_event_from_another_tenant_never_reaches_the_handler",
                 "test_an_attempt_cannot_be_proposed_for_another_tenants_work_item"),
    # ---- M3 External Effect / Grant
    ("M3", 2): ("test_an_illegal_transition_marker_riding_the_stream_is_consumed_not_skipped",
                "test_no_timer_moves_an_UNKNOWN_OUTCOME"),
    ("M3", 3): ("test_a_replayed_handle_second_claim_matches_zero_rows",),
    ("M3", 4): ("test_redelivery_of_a_consumed_event_is_idempotent",),
    ("M3", 5): ("test_the_terminal_set_is_exactly_the_four_and_unknown_is_not_among_them",),
    ("M3", 8): ("test_a_restart_after_the_claim_re_executes_nothing_exactly_one_EffectAttempted",
                "test_a_timeout_crash_or_lost_response_is_UNKNOWN_never_FAILED"),
    ("M3", 10): ("test_a_claim_never_transitions_another_tenants_grant",
                 "test_a_grant_cannot_be_minted_across_a_tenant"),
    # ---- M4 Approval
    ("M4", 2): ("test_terminal_states_are_final_by_trigger",),
    ("M4", 3): ("test_replayed_transport_token_is_refused",),
    ("M4", 4): ("test_double_tap_is_idempotent_not_an_error",),
    ("M4", 5): ("test_a_terminal_approval_stays_terminal",),
    ("M4", 8): ("test_approval_after_unknown_attempt_is_not_reusable",
                "test_frozen_reconstructed_from_positive_evidence"),
    ("M4", 10): ("test_tenant_isolation_no_cross_tenant_read",),
    # ---- M5 Observation
    ("M5", 2): ("test_illegal_transition_is_recorded_to_audit_and_security",),
    ("M5", 3): ("test_occ_on_processing_status_refuses_lost_update",),
    ("M5", 4): ("test_inbox_redelivery_is_a_no_op",
                "test_duplicate_observation_is_one_row_one_confirmation_zero_work"),
    ("M5", 5): ("test_bound_can_be_superseded_but_supersession_is_terminal",),
    ("M5", 7): ("test_raw_value_is_immutable", "test_no_deletion_of_an_observation",
                "test_superseded_observation_is_retained"),
    ("M5", 10): ("test_cross_tenant_same_external_id_no_collision",
                 "test_a_natural_key_is_scoped_to_its_tenant"),
    # ---- M6 Identity Binding Claim
    ("M6", 2): ("test_illegal_transition_is_recorded_to_audit_and_security",
                "test_ib5x_is_declared_illegal_and_changes_no_legality"),
    ("M6", 3): ("test_occ_on_claim_version_refuses_a_lost_update",),
    ("M6", 4): ("test_redelivered_proposal_is_a_no_op",),
    ("M6", 5): ("test_linker_inferred_may_be_recomputed_and_the_old_row_is_retained",),
    ("M6", 7): ("test_correction_is_append_only_and_correction_of_correction_is_supported",
                "test_replay_preserves_owner_asserted_byte_identical"),
    ("M6", 8): ("test_replay_preserves_owner_asserted_byte_identical",),
    ("M6", 10): ("test_provenance_class_cannot_be_edited",),
    # ---- M7 Conflict
    ("M7", 2): ("test_auto_resolve_is_illegal", "test_a_timer_transition_to_resolved_is_illegal"),
    ("M7", 3): ("test_occ_refuses_a_lost_update",),
    ("M7", 4): ("test_redelivered_detection_is_a_no_op",),
    ("M7", 5): ("test_a_resolved_conflict_is_retained_and_a_delete_is_refused",),
    ("M7", 7): ("test_a_resolved_conflict_is_retained_and_a_delete_is_refused",),
    ("M7", 8): ("test_a_crash_mid_workflow_recovers_to_the_canonical_state",
                "test_restart_preserves_the_open_conflict"),
    ("M7", 10): ("test_tenant_predicate_isolates_the_open_conflict_lookup",),
    # ---- M8 Expectation
    ("M8", 2): ("test_forcing_overdue_without_healthy_coverage_is_illegal",
                "test_cancelling_an_indeterminate_expectation_is_illegal",
                "test_a_window_evaluated_in_utc_is_illegal"),
    ("M8", 3): ("test_occ_refuses_a_stale_version",),
    ("M8", 4): ("test_inbox_idempotency_a_redelivered_event_is_a_no_op",
                "test_a_redelivered_timer_is_a_no_op"),
    ("M8", 5): ("test_a_cancelled_expectation_cannot_be_deleted",),
    ("M8", 7): ("test_deadline_history_is_retained",
                "test_a_cancelled_expectation_cannot_be_deleted"),
    ("M8", 8): ("test_restart_re_fires_the_deadline_timer_and_reaches_the_canonical_state",),
    ("M8", 10): ("test_the_same_key_in_two_tenants_are_two_isolated_expectations",
                 "test_wrong_tenant_observation_cannot_discharge"),
    # ---- M9 Exception
    ("M9", 2): ("test_resolved_is_the_only_terminal_state_and_nothing_moves_it",),
    ("M9", 3): ("test_occ_refuses_a_stale_version",),
    ("M9", 4): ("test_a_redelivered_timer_is_a_no_op",),
    ("M9", 5): ("test_resolved_is_the_only_terminal_state_and_nothing_moves_it",),
    ("M9", 7): ("test_a_resolved_exception_is_retained_never_deleted",
                "test_an_exception_never_expires_and_no_sweep_deletes_it"),
    ("M9", 8): ("test_restart_re_fires_the_ageing_timer_and_preserves_open",),
    ("M9", 9): ("test_ownerless_exception_impossible", "test_ec_raise_requires_owner"),
    ("M9", 10): ("test_the_same_source_in_two_tenants_are_two_isolated_exceptions",
                 "test_cross_tenant_owner_fails_closed"),
    # ---- M10 Compensation
    ("M10", 2): ("test_ac_mach_1007_cm_failed_non_terminal",),
    ("M10", 3): ("test_a_stale_or_wrong_commit_key_approval_is_refused",),
    ("M10", 5): ("test_completed_is_the_only_terminal_state",),
    ("M10", 7): ("test_a_compensation_row_cannot_be_deleted",
                 "test_exposure_survives_into_compensation_failed_and_not_possible"),
    ("M10", 8): ("test_ac_rec_005_and_ac_race_013_crash_and_timeout_reach_compensation_failed",),
    ("M10", 10): ("test_cross_tenant_owner_fails_closed", "test_a_cross_tenant_approval_is_refused"),
    # ---- M11 Policy
    ("M11", 2): ("test_automation_and_retry_and_timer_cannot_activate_a_policy",),
    ("M11", 3): ("test_occ_version_advances_by_one_per_transition",
                 "test_a_stale_policy_version_grant_claim_is_refused"),
    ("M11", 7): ("test_retention_supersession_is_permanent_and_immutable_and_undeletable",
                 "test_a_policy_is_never_retroactive_the_old_version_keeps_its_own_version"),
    ("M11", 10): ("test_the_same_scope_is_active_in_two_tenants_without_collision",
                  "test_a_cross_tenant_activator_or_author_fails_closed"),
    # ---- M12 Rule
    ("M12", 2): ("test_model_cannot_activate_a_rule", "test_a_model_cannot_confirm_a_rule"),
    ("M12", 3): ("test_occ_version_advances_by_one_per_transition",),
    ("M12", 4): ("test_re_activating_an_active_version_is_a_no_op",),
    ("M12", 7): ("test_retention_is_permanent_and_immutable_and_undeletable",
                 "test_a_compiled_predicate_is_frozen_after_it_leaves_proposed"),
    ("M12", 10): ("test_the_same_scope_and_kind_is_active_in_two_tenants_without_collision",
                  "test_a_cross_tenant_activator_or_author_fails_closed"),
    # ---- M13 Brake
    ("M13", 2): ("test_no_timer_can_move_a_brake", "test_a_model_may_never_engage_narrow_or_release"),
    ("M13", 3): ("test_stale_grant_after_release_is_refused",),
    ("M13", 4): ("test_the_signal_count_rises_on_repeated_engagement_by_row",),
    ("M13", 7): ("test_a_brake_row_is_never_deleted", "test_the_platform_brake_row_is_never_deleted"),
    ("M13", 10): ("test_a_releaser_from_another_tenant_is_refused", "test_brakes_is_tenant_first"),
}

# ### THE GAP, NAMED RATHER THAN HIDDEN. These `(machine, assertion)` cells are required by the
# authority and have NO existing evidence this register could honestly point at. Writing a test to
# make the id appear is exactly what the acceptance review forbids, so they are recorded instead, and
# `test_the_unevidenced_set_never_grows` makes this a RATCHET: a cell may leave this set when real
# evidence lands, and nothing may join it.
UNEVIDENCED: frozenset[tuple[str, int]] = frozenset({
    ("M3", 7),    # no append-only probe on the grant ledger's history rows.
    ("M4", 7),    # no append-only probe on the approval/closure rows.
    ("M5", 8),    # M5 has replay idempotency but no crash-recovery case.
    ("M10", 4),   # no inbox-key redelivery no-op case for M10.
    ("M11", 4),   # no inbox-key redelivery no-op case for M11.
    ("M11", 5),   # no "terminal policy version refuses every trigger" case.
    ("M11", 8),   # replay is covered; crash recovery to the canonical state is not.
    ("M12", 5),   # no "terminal rule version refuses every trigger" case.
    ("M12", 8),   # replay is covered; crash recovery to the canonical state is not.
    ("M13", 5),   # no "RELEASED refuses every trigger" case.
    ("M13", 8),   # no crash-recovery case for the brake row.
})
