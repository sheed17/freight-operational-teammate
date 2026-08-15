#!/usr/bin/env python3
"""Safe in-memory mutation battery for P6 U1 — the Work Item and accountable human ownership.

Doctrine (CLAUDE.md sec 9), identical to the P3/P4/P5 batteries:
  * original bytes are held IN MEMORY - never `git checkout/restore/stash/clean`
  * __pycache__ is purged around every mutation
  * a guard that does NOT fail on the mutant proves nothing and is reported as a MISS
  * restoration is verified byte-for-byte, and the guard must be GREEN again before moving on
  * every case states the REAL defect it reintroduces

### THE UNIT'S MUTATION REQUIREMENT IS `required` IN THE REGISTRY, AND THIS IS WHAT IT IS FOR.
The claim P6-U1 makes is that ownership is STRUCTURAL rather than documented. A structural claim is
worth exactly as much as the demonstration that its guards can go red. Cases W1-W8 are that
demonstration: each one turns a mechanism back into a convention and the battery shows which test
notices.

Case W3 reintroduces a defect THIS BUILD ACTUALLY SHIPPED and its own battery caught: the
`IllegalTransitionAttempted` record was written inside the transaction it was about to abandon, so
the refusal worked and the evidence of it was rolled back with everything else.

### THIS IS NOT AN INDEPENDENT REVIEW. It was written by the session that implemented the unit.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = ROOT / ".venv/bin/python"

WI = "src/freight_recon/work_item.py"
MIG = "src/freight_recon/migrations/phase6_work_items.py"
SCHEMA = "src/freight_recon/schema.py"
# P5's inbox is in range for W29* only, and only for the affordance this unit's defect required.
# The mutants below attack THAT affordance; nothing else in the module is touched.
EI = "src/freight_recon/event_inbox.py"

T = "eval/tests/test_phase6_work_item.py"
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
    # ---- ownership: the unit's whole claim ---------------------------------------------------
    ("W1  the owner is no longer resolved against the recorded roster: any string becomes an owner",
     WI,
     '        found = human_authority(self._conn, tenant=self._tenant, human_id=text)\n'
     '        if found is None:',
     '        found = human_authority(self._conn, tenant=self._tenant, human_id=text)\n'
     '        if False:  # MUTANT',
     f"{T}::test_creation_without_a_recorded_owner_fails_and_writes_nothing"),

    ("W2  an OFFBOARDED human may be given work again: point 36 becomes a comment",
     WI,
     "        if not found.is_active:",
     "        if False:  # MUTANT",
     f"{T}::test_an_offboarded_human_cannot_be_given_work"),

    ("W3  the illegal-transition record is written inside the transaction it abandons "
     "(the real shipped defect)",
     WI,
     "            self._conn.rollback()\n"
     "            self._conn.execute(\"BEGIN IMMEDIATE\")\n"
     "            try:\n"
     "                self._record_illegal_locked(",
     "            self._conn.execute(\"SELECT 1\")  # MUTANT: no rollback-then-record\n"
     "            self._conn.rollback()\n"
     "            try:\n"
     "                self._record_illegal_locked(",
     f"{T}::test_the_illegal_record_survives_the_refusal"),

    ("W4  offboarding stops checking for open work: an owner walks out and the work stays theirs",
     WI,
     "    if outstanding:",
     "    if False:  # MUTANT",
     f"{T}::test_offboarding_refuses_while_open_work_is_owned_and_names_it"),

    ("W5  a model may drive the machine: C-6/GR-7 stop being enforced",
     WI,
     'PERMITTED_ACTOR_TYPES: frozenset[str] = frozenset({"human", "system", "detector"})',
     'PERMITTED_ACTOR_TYPES: frozenset[str] = frozenset('
     '{"human", "system", "detector", "model"})  # MUTANT',
     f"{T}::test_a_model_can_never_drive_this_machine"),

    ("W6  a non-human identity becomes recordable: owner_id='system' is writable again",
     MIG,
     '            CHECK (lower(trim(human_id)) NOT IN (%(non_human)s)),\n',
     '',
     f"{T}::test_a_non_human_identity_cannot_be_recorded_as_an_authority"),

    ("W7  a MODEL may record a human authority: the roster becomes model-authored",
     MIG,
     "            CHECK (recorded_by_kind = 'human'),\n",
     '',
     f"{T}::test_only_a_human_may_record_an_authority"),

    ("W8  the ownership foreign key is dropped: owner_id becomes a text column",
     MIG,
     "            FOREIGN KEY (tenant, owner_id) REFERENCES tenant_humans(tenant, human_id),\n",
     '',
     f"{T}::test_an_ownerless_row_is_unwritable_even_by_raw_sql"),

    # ---- closure: I11 and K-1 ------------------------------------------------------------------
    ("W9  decision_ref becomes a non-null check: 'closed with the string done' returns",
     WI,
     "    ).fetchone()\n    if row is None:",
     "    ).fetchone()\n    if False:  # MUTANT",
     f"{T}::test_closed_with_the_string_done_is_refused"),

    ("W10 the decision event's actor is no longer required human: authority laundering returns",
     WI,
     '    if envelope.actor_type != "human":',
     "    if False:  # MUTANT",
     f"{T}::test_a_system_emitted_human_decision_event_does_not_resolve"
     "[HumanDecided-work_item-wi-other-WI-9]"),

    ("W11 any canonical event becomes a decision_ref: a PipelineClosed closes the obligation",
     WI,
     "    if event_name not in HUMAN_DECISION_EVENTS:",
     "    if False:  # MUTANT",
     f"{T}::test_a_non_decision_event_does_not_resolve"),

    ("W12 a RULE decision_ref is accepted on trust, against a rules table that does not exist",
     WI,
     '    if kind == "RULE":',
     "    if False:  # MUTANT",
     f"{T}::test_a_rule_kind_decision_ref_fails_closed_today"),

    ("W13 WI-3 infers the obligation is satisfied: a finishing Pipeline auto-closes the item",
     WI,
     "            if facts.obligation_satisfied is not True:",
     "            if False:  # MUTANT",
     f"{T}::test_ac_mach_103d_a_finishing_pipeline_does_not_auto_close_the_item"),

    # ---- terminality, history and the counter --------------------------------------------------
    ("W14 a CLOSED row may be reopened without a new phase: reopening stops being a new phase",
     MIG,
     "         AND NOT (OLD.state = 'CLOSED' AND NEW.state = 'IN_PROGRESS'\n"
     "                  AND NEW.phase_seq = OLD.phase_seq + 1)",
     "         AND NOT (OLD.state = 'CLOSED' AND NEW.state = 'IN_PROGRESS')  -- MUTANT",
     f"{T}::test_a_closed_row_may_only_leave_through_a_new_phase"),

    ("W15 the version counter may stand still: two transitions can claim one aggregate version",
     MIG,
     "        WHEN NEW.version <> OLD.version + 1",
     "        WHEN NEW.version < OLD.version  -- MUTANT",
     f"{T}::test_the_version_counter_cannot_stand_still"),

    ("W16 a terminal row may shed its decision reference on the way in",
     MIG,
     "        WHEN NEW.state IN ({_TERMINAL_SQL})\n"
     "         AND (NEW.closure_decision_ref IS NULL OR trim(NEW.closure_decision_ref) = ''\n"
     "              OR NEW.closure_decision_ref_kind IS NULL)",
     "        WHEN 0  -- MUTANT",
     f"{T}::test_a_terminal_row_cannot_shed_its_decision_reference"),

    ("W17 a recorded authority becomes editable: who admitted whom can be rewritten",
     MIG,
     '    "trg_tenant_humans_identity_immutable": f"""',
     '    "trg_tenant_humans_identity_immutable_disabled": f"""  # MUTANT',
     f"{T}::test_a_recorded_authority_is_append_only"),

    ("W18 the OCC WHERE clause loses its version predicate: a stale writer overwrites silently",
     WI,
     '            f" WHERE tenant = ? AND work_item_id = ? AND version = ? AND state = ?",\n'
     "            (*params, self._tenant, item.work_item_id, item.version, item.state.value),",
     '            f" WHERE tenant = ? AND work_item_id = ? AND state = ?",  # MUTANT\n'
     "            (*params, self._tenant, item.work_item_id, item.state.value),",
     f"{T}::test_the_occ_where_clause_carries_the_version_predicate"),

    # ---- the transition table itself -------------------------------------------------------------
    ("W19 a transition is renamed: the same COUNT of rows with a different member",
     WI,
     '        id="WI-7", from_states=(WorkItemState.OPEN, WorkItemState.IN_PROGRESS),',
     '        id="WI-77", from_states=(WorkItemState.OPEN, WorkItemState.IN_PROGRESS),  # MUTANT',
     f"{T}::test_ac_mach_000_transition_identifiers_are_a_bijection_with_the_specification"),

    ("W20 an ordinary transition starts moving the owner: accountability moves as a side effect",
     WI,
     '        id="WI-2", from_states=(WorkItemState.OPEN,), to_state=WorkItemState.IN_PROGRESS,\n'
     "        triggers=(Trigger.PIPELINE_STARTED,), trigger_types=(\"S\",),\n"
     '        event_name="WorkStarted", owner_after=OwnerAfter.UNCHANGED,',
     '        id="WI-2", from_states=(WorkItemState.OPEN,), to_state=WorkItemState.IN_PROGRESS,\n'
     "        triggers=(Trigger.PIPELINE_STARTED,), trigger_types=(\"S\",),\n"
     '        event_name="WorkStarted", owner_after=OwnerAfter.NEW_OWNER,  # MUTANT',
     f"{T}::test_ownership_moves_on_exactly_three_transitions"),

    ("W21 WI-14's delegation is dropped: an ESCALATED item can no longer close or block",
     WI,
     '        delegates_to=("WI-5", "WI-6", "WI-7", "WI-3", "WI-12"),',
     '        delegates_to=("WI-5", "WI-6", "WI-7"),  # MUTANT',
     f"{T}::test_wi_14_delegation_is_derived_and_not_hand_copied"),

    ("W22 an illegal (state, trigger) pair silently becomes legal: GR-1 stops being exhaustive",
     WI,
     "        if not row.is_delegation and not row.creates\n"
     "        and state in row.from_states and trigger in row.triggers",
     "        if not row.is_delegation and not row.creates  # MUTANT\n"
     "        and (state in row.from_states or state is WorkItemState.CLOSED)"
     " and trigger in row.triggers",
     f"{T}::test_the_illegal_sweep_has_a_proven_population"),

    # ---- WI-10: a timer, not a sweep --------------------------------------------------------------
    ("W23 WI-10 stops resolving the timer at all: an age ASSERTION becomes a sweep again",
     WI,
     "        row = self._conn.execute(\n"
     "            \"SELECT aggregate_type, aggregate_id, state, timer_kind FROM durable_timers \"",
     "        row = None if True else self._conn.execute(  # MUTANT\n"
     "            \"SELECT aggregate_type, aggregate_id, state, timer_kind FROM durable_timers \"",
     f"{T}::test_wi_10_refuses_every_way_of_escalating_without_a_fired_timer"),

    ("W24 WI-10 accepts a SCHEDULED timer: escalation before the deadline",
     WI,
     '        if row["state"] != "FIRED":',
     "        if False:  # MUTANT",
     f"{T}::test_wi_10_refuses_every_way_of_escalating_without_a_fired_timer"),

    ("W24a WI-10 accepts another item's fired timer: one item aging escalates another",
     WI,
     '        if row["aggregate_type"] != AGGREGATE_TYPE or row["aggregate_id"] != item.work_item_id:',
     "        if False:  # MUTANT",
     f"{T}::test_wi_10_refuses_every_way_of_escalating_without_a_fired_timer"),

    # ---- the dark posture ---------------------------------------------------------------------
    ("W25 M1 gains a direct import of the effect boundary",
     WI,
     "from .event_contracts import CONTRACTS",
     "from .effect_boundary import execute_effect  # MUTANT\n"
     "from .event_contracts import CONTRACTS",
     f"{T}::test_the_work_item_import_closure_reaches_nothing_effect_capable"),

    # ### W26 WAS FIRST AIMED AT THE P6 READINESS GUARD AND REPORTED A MISS — CORRECTLY. Removing
    # the P6 tables from `CANONICAL_TABLES` does NOT stop a fresh database building them, because
    # `create_canonical_schema` calls `create_phase6_schema` explicitly. The mutant reintroduced no
    # defect that guard could see, so believing the MISS would have been believing a bad probe
    # (CLAUDE.md §9). Re-aimed at the guard whose oracle this actually is: the canonical table
    # partition, which must explain EVERY canonical table by membership.
    ("W26 the P6 tables leave the canonical table list: the partition stops explaining the schema",
     SCHEMA,
     "    *P6_TENANT_TABLES,\n    *P6_EXEMPT_TABLES,\n)",
     ")  # MUTANT",
     "eval/tests/test_bootstrap_hermeticity.py"
     "::test_the_canonical_table_partition_is_exact_and_disjoint"),

    # ---- THE TWO DEFECTS AN INDEPENDENT REVIEW REJECTED THIS CANDIDATE FOR --------------------
    #
    # ### THE REJECTED CANDIDATE *IS* W27 + W28, AND THE OLD SUITE WAS GREEN ON IT. That is the
    # only reason these five cases exist, and it is the whole point of them: a battery that cannot
    # go red on the exact tree a reviewer rejected is a battery that certified the defect. Each
    # case restores one piece of the rejected behaviour and names the regression that must notice.

    ("W27 IllegalTransitionAttempted goes back to the TRANSITION-NATURAL identity: an illegal "
     "transition does not advance the version, so two hostile attempts collide (F-01)",
     WI,
     "            trace_id=trace_id, event_id=event_id, now=now,\n"
     "            idempotency_identity=identity,\n",
     "            trace_id=trace_id, event_id=event_id, now=now,  # MUTANT: identity collides\n",
     f"{T}::test_two_distinct_illegal_attempts_at_one_version_are_independently_auditable"),

    ("W27a the transport's DuplicateEmission escapes the refusal API again, and inside "
     "DedupInbox.consume that is an infinite redelivery loop (F-01)",
     WI,
     "            repeat = self._recorded_illegal_attempt(identity)\n"
     "            if repeat is None:\n"
     "                raise WorkItemError(",
     "            repeat = self._recorded_illegal_attempt(identity)\n"
     "            if repeat is None:\n"
     "                raise exc  # MUTANT: the outbox error escapes instead of refusing\n"
     "            if repeat is None:\n"
     "                raise WorkItemError(",
     f"{T}::test_a_refusal_that_cannot_be_recorded_fails_as_this_machines_error_not_the_transports"),

    ("W28 the structural owner requirement leaves consume(): a park can be created with "
     "accountable_owner_id NULL again (F-02)",
     WI,
     "            self._accountable_owner_for(box, envelope, work_item_id, accountable_owner_id)\n"
     "            if work_item_must_exist(trigger) else accountable_owner_id",
     "            accountable_owner_id  # MUTANT: the ownerless park returns\n"
     "            if work_item_must_exist(trigger) else accountable_owner_id",
     f"{T}::test_consume_refuses_rather_than_parking_an_obligation_nobody_owns"),

    ("W28a the refusal is bought off with a fabricated owner instead: 'system' owns the parked "
     "obligation (F-02)",
     WI,
     "        raise OwnershipRefused(\n"
     '            f"{envelope.event_name} references Work Item {work_item_id!r}, which does not '
     'exist "',
     '        return "system"  # MUTANT: a fabricated owner nobody agreed to be\n'
     "        raise OwnershipRefused(\n"
     '            f"{envelope.event_name} references Work Item {work_item_id!r}, which does not '
     'exist "',
     f"{T}::test_consume_refuses_rather_than_parking_an_obligation_nobody_owns"),

    ("W28b the park owner stops being checked against the recorded roster: any string becomes the "
     "accountable human (F-02)",
     WI,
     '        if str(accountable_owner_id or "").strip():\n'
     "            return self._require_active_human(\n"
     '                accountable_owner_id, what="the accountable owner of a consumed '
     'trigger").human_id',
     '        if str(accountable_owner_id or "").strip():\n'
     "            return accountable_owner_id  # MUTANT: an owner nobody recorded",
     f"{T}::test_a_park_owner_is_never_a_fabricated_or_unrecorded_identity"),

    # ---- THE DEFECT THE SECOND INDEPENDENT REVIEW REJECTED THIS CANDIDATE FOR (F-03) ----------
    #
    # ### F-03 WAS TWO FAULTS MEETING, SO IT TAKES THREE MUTANTS TO HOLD IT DOWN. The inbox
    # skipped an explicitly required self-aggregate reference (W29); M1's handler demanded that a
    # CREATION event's product already exist (W30); and a park nothing can drain is a drop with a
    # deadline (W29b). Each one alone reproduces a shipped, review-rejected behaviour.

    # ### THIS MUTANT'S SYMPTOM IS NOT THE LOOP, AND SAYING SO IS THE POINT. With M1's handler
    # still corrected, the evaporated requirement lands as a `NOT_CONSUMABLE` refusal: the
    # canonical human decision is CONSUMED AND DISCARDED, receipt written, nothing parked, nothing
    # emitted. That is M-26's other forbidden outcome — dropped rather than failed — and it is
    # strictly harder to notice than the loop was. W29c is where the loop itself comes back.
    ("W29 DedupInbox skips an EXPLICITLY required self-aggregate reference again: M1's demand "
     "evaporates and a canonical HumanDecided for an item that has not landed is silently DROPPED "
     "instead of parked — no park, no owner, no TTL, no second chance (F-03)",
     EI,
     "        for aggregate_type, aggregate_id in requires_existing:\n",
     "        for aggregate_type, aggregate_id in requires_existing:\n"
     "            if (aggregate_type, aggregate_id) == (event.aggregate_type, "
     "event.aggregate_id):\n"
     "                continue  # MUTANT: the explicit prerequisite evaporates again (F-03)\n",
     f"{T}::test_every_trigger_has_a_converging_missing_work_item_outcome"),

    ("W29a the same skip, watched by the P5 regression rather than the population sweep: the "
     "shared primitive's own guard must notice its own affordance being neutered (F-03)",
     EI,
     "        for aggregate_type, aggregate_id in requires_existing:\n",
     "        for aggregate_type, aggregate_id in requires_existing:\n"
     "            if (aggregate_type, aggregate_id) == (event.aggregate_type, "
     "event.aggregate_id):\n"
     "                continue  # MUTANT: the explicit prerequisite evaporates again (F-03)\n",
     f"{T5}::test_an_explicitly_required_own_aggregate_is_evaluated"
     "_where_an_implicit_one_is_skipped"),

    ("W29b a park on an explicit prerequisite stops draining on redelivery: nothing this consumer "
     "applies can seed its drain, so the held human decision is guaranteed to reach TTL instead "
     "of being applied — a drop with a deadline (F-03)",
     EI,
     "                released = bool(requires_existing) and self._first_unresolved_reference(",
     "                released = False and self._first_unresolved_reference(  # MUTANT: no drain",
     f"{T}::test_a_human_decision_for_a_work_item_that_has_not_landed_parks_and_then_drains"),

    ("W30 M1's handler unconditionally requires the Work Item again, including for the creation "
     "event whose whole job is to bring it into existence: WorkItemCreated raises "
     "UnknownWorkItem, the receipt rolls back with it, and it redelivers forever (F-03)",
     WI,
     "            item = self.get(work_item_id)\n"
     "            if item is None:",
     "            item = self.require(work_item_id)  # MUTANT: WI-1 waits for its own product\n"
     "            if item is None:",
     f"{T}::test_a_creation_event_never_waits_for_the_work_item_it_creates"),

    # ---- F-04 / F-05: the two defects the fresh targeted independent review REJECTED ----------
    # Each of these restores the REAL rejected behaviour rather than merely breaking something the
    # new tests happen to watch. W31/W31a reproduce a wrong-trigger CONSUMPTION signature — a parked
    # event reaching APPLIED through another event's semantics, with its own transition never fired.
    # W32/W32a reproduce the durable lie — the API answers PARKED while the row says DRAINED and
    # neither `parked()` nor `expire_overdue()` can find the event again.

    ("W31 the post-apply drain cascades through the CURRENT invocation's handler again: a parked "
     "cross-aggregate PipelineClosed is replayed through a HumanDecided closure, so WI-3 never "
     "fires, the Work Item does not close, the event still reaches APPLIED, its park becomes "
     "DRAINED, the later genuine retry is a DUPLICATE_NOOP and a fabricated "
     "IllegalTransitionAttempted is recorded against the wrong interpretation (F-04)",
     EI,
     "        if drain_handler_for is None:\n"
     "            # No factory, no cascade. The caller has not told us how to derive semantics for\n"
     "            # somebody else's parked envelope, and guessing is precisely F-04.\n"
     "            return result\n"
     "        drained, limited = self._drain_for(event, drain_handler_for)",
     "        drained, limited = self._drain_for(\n"
     "            event, lambda _parked: handler)  # MUTANT: the drain's seeder interprets everyone",
     f"{T}::test_heterogeneous_parked_triggers_in_one_store"
     "_are_each_consumed_by_their_own_semantics"),

    ("W31a the factory is consulted with the SEEDING event instead of the parked one, so a caller "
     "that DID opt in still gets every held event interpreted as whatever woke the cascade — the "
     "same wrong-trigger consumption, one layer down, and invisible to any caller whose handler "
     "happens to be event-agnostic (F-04)",
     EI,
     "                        park.envelope, drain_handler_for(park.envelope), requires=(),",
     "                        park.envelope, drain_handler_for(event), requires=(),  # MUTANT",
     f"{T5}::test_the_drain_derives_each_parked_events_handler_from_that_event"),

    ("W32 the park is stamped DRAINED the moment the explicit prerequisite resolves, BEFORE the "
     "remaining blockers are checked: the event re-parks, ON CONFLICT DO UPDATE refreshes only "
     "attempts, and the row stays DRAINED with resolved_at set while the API answers PARKED — "
     "parked() cannot see it, expiry cannot see it, and the event is silently unreachable (F-05)",
     EI,
     "                released = True\n",
     "                self._resolve_park_locked(  # MUTANT: DRAINED before eligibility is proven\n"
     "                    event.event_id, state=\"DRAINED\", now=now_text)\n"
     "                released = True\n",
     f"{T5}::test_a_repark_after_partial_prerequisite_resolution_stays_truthfully_parked"),

    ("W32a the same premature DRAINED stamp, watched by the TTL path instead of by the row: M-26's "
     "owner-bearing exception is what turns a permanently dangling reference into a named human's "
     "problem, and a park durable storage calls DRAINED can never reach it (F-05)",
     EI,
     "                released = True\n",
     "                self._resolve_park_locked(  # MUTANT: DRAINED before eligibility is proven\n"
     "                    event.event_id, state=\"DRAINED\", now=now_text)\n"
     "                released = True\n",
     f"{T5}::test_a_partially_blocked_park_still_expires_onto_its_accountable_human"),
]


# ### ONE CASE NEEDS TWO FILES AT ONCE, AND PRETENDING OTHERWISE WOULD WEAKEN IT.
# F-03's rejected behaviour was the INTERSECTION of two faults. Restore only the inbox skip and
# M1's corrected handler absorbs the fallout as a `NOT_CONSUMABLE` refusal — a silent DROP of a
# recorded human decision, which is its own M-26 violation and is caught, but it is not the loop
# the reviewer saw. Restore only the handler and the decision still parks. The loop needs both, so
# W29c applies both and the guard must still notice.
MULTI_CASES = [
    ("W29c both halves of F-03 at once — the EXACT rejected tree: the inbox skips M1's explicit "
     "prerequisite AND the handler requires the Work Item unconditionally, so a canonical "
     "HumanDecided for an item that has not landed raises inside the inbox's one transaction and "
     "redelivers forever with inbox=0 parks=0 outbox=0 security=0",
     (
         (EI,
          "        for aggregate_type, aggregate_id in requires_existing:\n",
          "        for aggregate_type, aggregate_id in requires_existing:\n"
          "            if (aggregate_type, aggregate_id) == (event.aggregate_type,"
          " event.aggregate_id):\n"
          "                continue  # MUTANT\n"),
         (WI,
          "            item = self.get(work_item_id)\n            if item is None:",
          "            item = self.require(work_item_id)  # MUTANT\n            if item is None:"),
     ),
     f"{T}::test_every_trigger_has_a_converging_missing_work_item_outcome"),
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
    results = [(c[0], *_run_text_case(c)) for c in TEXT_CASES]
    results += [(c[0], *_run_edits(c[1], c[2])) for c in MULTI_CASES]
    print("\n=========== P6 U1 WORK ITEM / OWNERSHIP MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    print("  NOTE: written by the session that implemented the unit - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
