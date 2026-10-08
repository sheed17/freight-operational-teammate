#!/usr/bin/env python3
"""P9 deep-end 3 mutation battery — a guard never seen to fail is a decoration (CLAUDE.md sec 6).

Each mutant reintroduces ONE real defect in the operational work engine and names the test that must
turn RED under it. Four families:

  * WHAT WORK IS. An overdue deadline read as not due; an unresolved Conflict treated as safe; the
    human-required marker dropped; a missing POD counted as satisfied; an unplaced invoice made
    quiet, guessed onto the load's only movement, raised to nobody, or matched by tidying its MC; a
    blocked load called billing-ready; work that never closes when its deadline is met; a blind
    channel reported as a late carrier; the Exception of a live cause filed as housekeeping.

  * WHAT A NEED'S IDENTITY IS. The tenant dropped from it; an identity that is new on every
    evaluation.

  * WHAT THE CANONICAL RECORD DOES. An owner's decision that settles nothing; a later statement that
    silently overwrites her; a moved appointment that leaves the old deadline being watched; a bare
    DELIVERED that never answers the arrival it implies; an Expectation left owed after its reason
    disappeared, and one M8 could not cancel dropped from the work.

  * WHAT A MODEL MAY DO. Called when the deterministic state was sufficient; an action it was not
    offered accepted; a human's need suppressed; a failed call read as advice to wait; the same
    question paid for twice.

  * THE CONTINUOUS LOAD LOOP (deep-end 4). A deadline that passes unlooked-at; an unbooked load
    called quiet; a human's confirmation that resolves nothing; a settled dispute raised again; a
    restart that forgets when the loop last looked; a
    contradiction after her decision silently lost; an overruled claim that still counts; a
    tracking record speaking as the owner; a human's decision not counted as a touch; a draft
    reported as sent; money in the picture; work on no load left off the board; a refused record
    counted twice.

  * AN OVERRULED CLAIM ANSWERS NOTHING (the CP-4 review repair). An overruled claim that still
    counts as arrival evidence; a watch it answered that is never owed again; a watch something
    else still answers reopened anyway; a watch owed again raised a third time; an overruled claim
    that still reaches a stop, still sets the stage, still starts the tracking clock; a tracking
    watch an overruled delivery report answered left answered; a picture that says the overruled
    claim satisfied something; a human act dated in the future read as authority; and the same
    rule refusing an act dated at the instant it arrived.

  * A MOVED APPOINTMENT IS STILL WATCHED (the second CP-4 review repair). A cancelled watch that
    stands in for the one owed when the appointment comes back to its window; a moved appointment
    that is then missed watched twice; an owed watch that cannot be found again under its own id;
    and a watch the truck's arrival already answered raised again beside it.

It mutates TEXT and shells out to pytest; it NEVER imports the code under test, and it NEVER uses git
to undo a mutation. Originals are held in memory and restored unconditionally; `__pycache__` is purged
around every run so a same-length restore cannot leave poisoned bytecode and a false green.

    .venv/bin/python scripts/mutate_p9_load_work.py
    .venv/bin/python scripts/mutate_p9_load_work.py "unplaced"      # only matching mutants
    .venv/bin/python -m pytest scripts/mutate_p9_load_work.py -q -p no:cacheprovider
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

FD = "src/freight_recon/freight_domain"
WORK = f"{FD}/load_work.py"
REASON = f"{FD}/work_reasoning.py"
PROJECTION = f"{FD}/projection.py"
DETECTORS = f"{FD}/detectors.py"
MODEL = f"{FD}/model.py"
MAPPING = f"{FD}/entity_mapping.py"
INTAKE = f"{FD}/intake.py"
HISTORY = f"{FD}/history.py"
LOOP = f"{FD}/load_loop.py"

T = "eval/tests/test_p9_load_work.py"
L = "eval/tests/test_p9_load_loop.py"

TIME = f"{T}::test_work_changes_when_time_passes_and_nothing_arrives"
CONFLICT = f"{T}::test_an_unresolved_conflict_is_human_attention_and_resolving_it_keeps_history"
UNPLACED = (f"{T}::test_an_invoice_no_movement_claims_is_an_owned_human_need_and_never_"
            f"reconciled")
HELD = f"{T}::test_an_unplaced_invoice_is_held_and_is_compared_against_nothing"
MC_SAME = f"{T}::test_an_mc_written_another_way_is_the_same_mc_when_its_digits_are_identical"
MC_OTHER = f"{T}::test_an_mc_with_different_or_missing_digits_is_never_matched"
MC_NEXT_DOOR = f"{T}::test_an_mc_is_never_looked_up_next_door"
MC_TWINS = f"{T}::test_one_mc_recorded_under_two_carriers_places_nothing"
POD = f"{T}::test_delivered_without_a_pod_is_work_and_a_usable_pod_closes_it"
OVERRULED = f"{L}::test_an_overruled_delivery_claim_stops_answering_the_delivery_watch"
FUTURE = f"{L}::test_a_future_dated_human_act_is_not_authority_and_silences_nothing"
RESTORED = f"{L}::test_an_appointment_put_back_after_a_wrong_window_lapsed_is_still_watched"
TWICE = f"{T}::test_evaluating_the_same_state_twice_creates_nothing"
TENANT = f"{T}::test_the_same_invoice_at_another_brokerage_cannot_be_reached"
ROUTED = f"{T}::test_the_model_is_asked_only_when_the_record_leaves_act_or_wait_open"
SUPPLIED = f"{T}::test_the_model_may_only_select_what_it_was_supplied"
SUPPRESS = f"{T}::test_the_model_cannot_suppress_a_need_a_human_must_decide"
FAILURE = f"{T}::test_a_model_failure_leaves_the_deterministic_work_standing"
REUSE = f"{T}::test_the_same_question_is_not_asked_twice"
ONE_NEED = f"{T}::test_a_need_is_one_need_however_many_rows_describe_it"
BLIND = f"{T}::test_a_blind_channel_is_never_reported_as_a_late_carrier"
MOVED = f"{T}::test_a_moved_appointment_moves_the_deadline_being_watched"
BARE = f"{T}::test_a_bare_delivered_answers_the_arrival_it_implies"
MONEY = f"{T}::test_an_invoice_discrepancy_is_never_silently_good"
MERGE = f"{T}::test_one_cause_reached_by_two_signals_is_one_need_not_two"
REBILLED = f"{T}::test_an_invoice_resent_with_different_charges_is_a_dispute_and_shows_no_money"
MOVED_RECORD = (f"{T}::test_a_wrong_load_number_is_a_humans_question_and_moving_the_record_"
                f"moves_the_work")
ORPHAN = f"{T}::test_an_expectation_that_outlives_its_cause_is_never_dropped"
OWED = f"{T}::test_an_owed_line_conflict_that_outlives_its_invoice_is_never_dropped"
RESOLVED = (f"{T}::test_a_humans_explicit_resolution_closes_the_exception_and_its_need_and_"
            f"keeps_the_history")
CURED = f"{T}::test_a_cured_exception_is_closed_only_by_a_human_and_then_is_not_housekeeping"
EXACT = f"{T}::test_a_resolution_closes_only_the_exception_it_names_on_the_load_it_names"
STANDS = f"{T}::test_closing_the_exception_does_not_finish_the_work_it_was_raised_for"
NOT_CLOSED = (f"{T}::test_customer_billing_ready_is_not_financially_closed_and_such_a_load_"
              f"is_never_quiet")
LATER = f"{T}::test_a_promise_for_later_than_our_deadline_does_not_extend_it"
AFTER = (f"{T}::test_a_promise_made_after_our_deadline_passed_does_not_turn_overdue_work_"
         f"into_a_wait")
KEPT = (f"{T}::test_a_kept_promise_leaves_nothing_behind_and_an_unusable_document_does_"
        f"not_keep_it")
WHOSE = f"{T}::test_a_carriers_document_does_not_keep_somebody_elses_promise"
WORD = f"{T}::test_a_promise_is_kept_only_by_a_word_from_the_sender_who_made_it"
ANON = (f"{T}::test_a_sender_with_no_address_keeps_no_promise_by_word_and_paper_is_another_"
        f"matter")
NOT_TEXT = f"{T}::test_an_address_the_record_does_not_carry_as_text_is_no_identity"
CONTROLS = f"{T}::test_the_control_states_are_settled_without_a_model"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    r = subprocess.run([PY, "-m", "pytest", nodeid, "-q", "-p", "no:cacheprovider"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


# (label, [(rel_path, old_anchor, new_text), ...], guard_nodeid). An anchor appears EXACTLY ONCE.
CASES = [
    # ------------------------------------------------------------------ what work is
    ("an OVERDUE deadline is read as not yet due - a promise broken an hour ago is still a wait",
     [(WORK, '    if state == "OVERDUE":\n        return NeedStatus.OVERDUE\n',
       '    if state == "OVERDUE":\n        return NeedStatus.PENDING  # MUTANT\n')],
     TIME),

    ("a deadline that passed on the asking clock is still PENDING - the wait never ends by itself",
     [(WORK,
       '    return NeedStatus.DUE if expectation["deadline_utc"] <= as_of else NeedStatus.PENDING\n',
       '    return NeedStatus.PENDING  # MUTANT\n')],
     TIME),

    ("work that never closes - a DISCHARGED Expectation still counts as owed",
     [(WORK, '    for expectation in view.owed_expectations():\n        etype = expectation['
             '"expected_type"]\n        if etype.startswith("document:"):\n',
       '    for expectation in view.expectations:  # MUTANT\n        etype = expectation['
       '"expected_type"]\n        if etype.startswith("document:"):\n')],
     TIME),

    ("an unresolved Conflict is treated as safe - two delivery windows and nobody is asked",
     [(WORK, '    view = build.view\n    for conflict in view.open_conflicts():\n        '
             'entity_kind = split_ref(conflict["entity_ref"])[0]\n',
       '    view = build.view\n    for conflict in ():  # MUTANT\n        '
       'entity_kind = split_ref(conflict["entity_ref"])[0]\n')],
     CONFLICT),

    ("an open Conflict on what a movement is owed is DROPPED once no invoice there is discrepant "
     "- the load goes quiet with an owned Conflict still open in M7",
     [(WORK, '        if outlived and f"conflict:{conflict[\'conflict_id\']}" in carried:\n',
       '        if outlived:  # MUTANT\n')],
     OWED),

    ("the human-required marker is dropped - a need only a human may decide is not marked as one",
     [(WORK, '        required = handling is Handling.HUMAN_REQUIRED if human_required is None \\\n'
             '            else human_required\n',
       '        required = False  # MUTANT\n')],
     UNPLACED),

    ("a missing POD is counted as satisfied - an OUTSTANDING requirement raises no need",
     [(WORK, '        doc_type = requirement.required_doc_type\n        if requirement.state != '
             '"OUTSTANDING":\n            continue\n',
       '        doc_type = requirement.required_doc_type\n        if True:  # MUTANT\n'
       '            continue\n')],
     POD),

    ("an unsigned POD satisfies the requirement - the paper nobody signed closes the need",
     [(PROJECTION, '            if doc_type == "POD" and document.value("signed") is not True:\n'
                   '                continue\n            if self._f.evidence_condition',
       '            if False:  # MUTANT\n'
       '                continue\n            if self._f.evidence_condition')],
     POD),

    ("an unplaced invoice is QUIET - P9-D23 again: no need is derived for an invoice on no "
     "movement",
     [(WORK, '    for payable in view.payables.values():\n        if payable.movement_id is not '
             'None:\n            continue\n        explained = explain_unattributed_invoice(view, '
             'payable)\n        raised = build.open_exceptions(',
       '    for payable in view.payables.values():\n        if True:  # MUTANT\n'
       '            continue\n        explained = explain_unattributed_invoice(view, '
       'payable)\n        raised = build.open_exceptions(')],
     UNPLACED),

    ("an unplaced invoice is raised to NOBODY - P9-D23 again: no owned Exception is created for it",
     [(DETECTORS, '    for payable in view.payables.values():\n        if payable.movement_id is '
                  'not None:\n            continue\n        explained = '
                  'explain_unattributed_invoice(view, payable)\n        out.append(RaiseException(',
       '    for payable in view.payables.values():\n        if True:  # MUTANT\n'
       '            continue\n        explained = '
       'explain_unattributed_invoice(view, payable)\n        out.append(RaiseException(')],
     UNPLACED),

    ("an invoice with no MC is GUESSED onto the load's only movement - the 1:1 assumption, and a "
     "carrier nobody named",
     [(PROJECTION, '        if not carrier_mc:\n            return None, None, '
                   '"CARRIER_NOT_STATED"\n',
       '        if not carrier_mc:\n            if len(view.movements) == 1:  # MUTANT\n'
       '                return next(iter(view.movements.values())), "MOVEMENT_KEY", None\n'
       '            return None, None, "CARRIER_NOT_STATED"\n')],
     HELD),

    ("an unplaced invoice is not HELD - it sits as merely 'received', where nothing looks",
     [(PROJECTION, '            if payable.movement_id is None:\n                '
                   'payable.lifecycle_state = "HELD"\n',
       '            if False:  # MUTANT\n                payable.lifecycle_state = "HELD"\n')],
     HELD),

    ("an MC is matched FUZZILY - a number one digit short matches the carrier it is a prefix of",
     [(PROJECTION, '            if canonical_mc_digits(m.external_id) == digits)) '
                   'if digits is not None else ()\n',
       '            if (canonical_mc_digits(m.external_id) or "").startswith(digits))) '
       'if digits is not None else ()  # MUTANT\n')],
     MC_OTHER),

    ("an MC is TIDIED too far - every non-digit is thrown away, so another prefix, a trailing "
     "letter or a split number is 'the same MC'",
     [(PROJECTION, '    match = _MC_BENIGN_FORM.fullmatch(str(value))\n'
                   '    return match.group(1) if match else None\n',
       '    return re.sub(r"[^0-9]", "", str(value)) or None  # MUTANT\n')],
     MC_OTHER),

    ("an MC is matched ONLY as the recorded string - P9-D31 undone: a carrier whose template "
     "drops the dash needs a human for every invoice",
     [(PROJECTION, '            if canonical_mc_digits(m.external_id) == digits)) '
                   'if digits is not None else ()\n',
       '            if canonical_mc_digits(m.external_id) == digits)) '
       'if False else ()  # MUTANT\n')],
     MC_SAME),

    ("an MC is looked up NEXT DOOR - the equivalence reads every brokerage's carriers",
     [(MAPPING, '            "SELECT * FROM external_entity_mappings WHERE tenant = ? AND '
                'external_system = ? "\n            "AND external_id_kind = ? AND '
                'neyma_entity_type = ? AND state = \'ACTIVE\' "\n',
       '            "SELECT * FROM external_entity_mappings WHERE ? IS NOT NULL AND '
       'external_system = ? "  # MUTANT\n            "AND external_id_kind = ? AND '
       'neyma_entity_type = ? AND state = \'ACTIVE\' "\n')],
     MC_NEXT_DOOR),

    ("one MC recorded under TWO carriers: the spelling the invoice prints wins - the exact match "
     "hides the ambiguity",
     [(PROJECTION, '        carriers = tuple(dict.fromkeys((*exact, *equivalent)))\n',
       '        carriers = exact or equivalent  # MUTANT\n')],
     MC_TWINS),

    # ------------------------------------------------------------------ P9-D30: closing an Exception
    ("an Exception a human RESOLVED in M9 is still shown as open work - her closed question never "
     "leaves the load",
     [(PROJECTION, '        return [x for x in self.exceptions if x["state"] != "RESOLVED"]\n',
       '        return list(self.exceptions)  # MUTANT\n')],
     RESOLVED),

    ("a cured Exception still OPEN in M9 is HIDDEN - neither work nor housekeeping, so the "
     "projection calls it finished while M9 still holds it",
     [(WORK, '            build.housekeeping.append(f"cured_exception:{exception_key(exception)}")\n'
             '            build.claimed_exceptions.add(exception["exception_id"])\n',
       '            build.claimed_exceptions.add(exception["exception_id"])  # MUTANT\n')],
     CURED),

    ("a resolution closes an Exception on ANOTHER load - the key is looked up across the "
     "brokerage instead of on the load the human named",
     [(INTAKE, '        named = [x for x in view.open_exceptions() '
               'if exception_key(x) == payload["exception"]]\n',
       '        named = [x for x in self.foundation.exceptions() if x["state"] != "RESOLVED"'
       '  # MUTANT\n                 and exception_key(x) == payload["exception"]]\n')],
     EXACT),

    ("an unplaced invoice goes QUIET once its Exception is closed - the need is read off the row, "
     "not the cause, so a click finishes work nobody did",
     [(WORK, '        raised = build.open_exceptions(type_="carrier_invoice_unattributed",\n'
             '                                       source_ref=payable.origin_observation_id)\n',
       '        raised = build.open_exceptions(type_="carrier_invoice_unattributed",\n'
       '                                       source_ref=payable.origin_observation_id)\n'
       '        if not raised:  # MUTANT\n            continue\n')],
     STANDS),

    # ------------------------------------------------------------------ P9-D41 / P9-D46
    ("a customer-billing-ready load is called QUIET whatever its carrier invoice says - billing "
     "ready is read as financially closed (P9-D41)",
     [(WORK, '        return not self.needs\n',
       '        return not self.needs or self.billing_ready  # MUTANT\n')],
     NOT_CLOSED),

    ("a carrier's promise turns OVERDUE work back into a wait - or into a model's question "
     "(P9-D46)",
     [(WORK, '        if own_passed:\n            continue'
             '                                  # our deadline passed: nothing defers it\n',
       '        if False:  # MUTANT\n            continue'
       '                                  # our deadline passed: nothing defers it\n')],
     AFTER),

    ("a promise for LATER than our deadline extends it - the wait runs to the time the carrier "
     "named (P9-D46)",
     [(WORK, '            horizon = min(d for d in (own_deadline, promise["due_by"]) '
             'if d is not None)\n',
       '            horizon = promise["due_by"]  # MUTANT\n')],
     LATER),

    ("a required document's deadline is never seen to have PASSED - an overdue POD is still "
     "waited on (P9-D46)",
     [(WORK, '            build.own_deadline[required.need_id] = '
             '(due_by, status is not NeedStatus.OPEN)\n',
       '            build.own_deadline[required.need_id] = (due_by, False)  # MUTANT\n')],
     AFTER),

    ("a missed arrival window or tracking cadence is not counted as a deadline of OURS - a "
     "promise holds it, and a model is asked whether it should (P9-D46)",
     [(WORK, '        if ours:\n            build.own_deadline[follow_up.need_id] = '
             '(min(ours), True)\n',
       '        if False:  # MUTANT\n            build.own_deadline[follow_up.need_id] = '
       '(min(ours), True)\n')],
     CONTROLS),

    ("a KEPT promise is still chased - the promised document does not answer the promise, so the "
     "carrier is called late for doing what they said",
     [(DETECTORS, '        if commitment["commitment_kind"] == "send_document" \\\n'
                  '                and commitment["sender_role"] in CARRIER_SIDE_ROLES:\n',
       '        if False:  # MUTANT\n')],
     KEPT),

    ("a required document keeps ANYBODY's promise - the carrier-side guard on the paper discharge "
     "is dropped, so a customer who sent nothing is recorded as having kept a promise and the "
     "load goes quiet",
     [(DETECTORS, '        if commitment["commitment_kind"] == "send_document" \\\n'
                  '                and commitment["sender_role"] in CARRIER_SIDE_ROLES:\n',
       '        if commitment["commitment_kind"] == "send_document":  # MUTANT\n')],
     WHOSE),

    ("a word from ANYBODY in the promiser's role keeps the promise - the answer is matched on the "
     "sender's role alone again, so the receiver's dock keeps the shipper's promise and the load "
     "goes quiet",
     [(DETECTORS, '            and promiser is not None and sender_identity(o["parsed"]["payload"])'
                  ' == promiser]\n',
       '            and True]  # MUTANT\n')],
     WORD),

    ("a sender with NO address is matched to another sender with none - nothing equals nothing, "
     "so a promise nobody can be identified as having made is kept by whoever wrote next",
     [(DETECTORS, '            and promiser is not None and sender_identity(o["parsed"]["payload"])'
                  ' == promiser]\n',
       '            and sender_identity(o["parsed"]["payload"]) == promiser]  # MUTANT\n')],
     ANON),

    ("a NAME stands in for an address - a sender's identity falls back to the display name, so "
     "two senders who merely share a name are one party",
     [(PROJECTION, '    return address if address.strip() else None\n',
       '    return address if address.strip() else payload["sender"]["name"]  # MUTANT\n')],
     ANON),

    ("an address that is NOT TEXT is turned into text - a null becomes the text \"None\", so two "
     "senders whose records carry no address have one identity and answer each other's promise",
     [(HISTORY, '                   "address": address if isinstance(address, str) else ""},\n',
       '                   "address": str(sender.get("address", ""))},  # MUTANT\n')],
     NOT_TEXT),

    ("a blocked load is called billing-ready",
     [(WORK, '        billing_ready=invoice is not None and invoice.lifecycle_state == "ELIGIBLE",\n',
       '        billing_ready=True,  # MUTANT\n')],
     POD),

    ("a blind channel is reported as a LATE carrier - INDETERMINATE read as overdue",
     [(WORK, '    if state == "INDETERMINATE":\n        return NeedStatus.UNVERIFIED\n',
       '    if state == "INDETERMINATE":\n        return NeedStatus.OVERDUE  # MUTANT\n')],
     BLIND),

    ("the Exception of a LIVE cause is filed as housekeeping - claimed rows are not remembered",
     [(WORK, '        rows = list(exceptions)\n        self.claimed_exceptions.update('
             'x["exception_id"] for x in rows)\n',
       '        rows = list(exceptions)  # MUTANT: nothing is remembered as claimed\n')],
     ONE_NEED),

    ("one missing POD becomes three tasks - a need for the same cause is appended, not merged",
     [(WORK, '        for index, existing in enumerate(self.needs):\n            if '
             'existing.need_id == identity:\n',
       '        for index, existing in enumerate(self.needs):\n            if False:  # MUTANT\n')],
     MERGE),

    ("money is copied into the work state - a financial Conflict shows each party's figure",
     [(WORK, '            stated = None if financial else party["stated_value"]\n',
       '            stated = party["stated_value"]  # MUTANT\n')],
     REBILLED),

    ("an Expectation whose REASON DISAPPEARED is left owed - a POD stays expected on a load whose "
     "delivery report a human moved away (P9-D2)",
     [(DETECTORS, '        if kind == "document" and doc_type in pending \\\n',
       '        if False and doc_type in pending \\\n')],
     MOVED_RECORD),

    ("an owed Expectation that no requirement explains is DROPPED - an obligation M8 could not "
     "cancel disappears from the work",
     [(WORK, '        if kind != "document" or doc_type in explained:\n            continue\n',
       '        if True:  # MUTANT\n            continue\n')],
     ORPHAN),

    # ------------------------------------------------------------------ identity
    ("the TENANT is dropped from a need's identity - the same cause at two brokerages is one need",
     [(WORK, '    return stable_id("need", tenant, kind.value, *anchor)\n',
       '    return stable_id("need", kind.value, *anchor)  # MUTANT\n')],
     TENANT),

    ("a need's identity is NEW on every evaluation - asking twice makes two pieces of work",
     [(WORK, '    return stable_id("need", tenant, kind.value, *anchor)\n',
       '    return stable_id("need", tenant, kind.value, *anchor,  # MUTANT\n'
       '                     __import__("uuid").uuid4())\n')],
     TWICE),

    # ------------------------------------------------------------------ the canonical record
    ("an owner's decision SETTLES NOTHING - the statements made before she decided still dispute "
     "her, so a resolved Conflict leaves the field conflicting",
     [(MODEL, '        if fact.received_at <= owner.received_at:\n            return True\n',
       '        if fact.received_at <= owner.received_at:\n            return False  # MUTANT\n')],
     CONFLICT),

    ("a later statement SILENTLY OVERWRITES NOTHING AND ASKS NOBODY - whatever is said after an "
     "owner decided is treated as already answered",
     [(MODEL, '        if not earlier:\n            return False\n',
       '        if not earlier:\n            return True  # MUTANT\n')],
     CONFLICT),

    ("a moved appointment leaves the OLD deadline being watched",
     [(DETECTORS, '        if stale:\n            for expectation in stale:\n',
       '        if False:  # MUTANT\n            for expectation in stale:\n')],
     MOVED),

    ("a bare DELIVERED never answers the arrival it implies - a delivered load goes on asking "
     "where the truck is",
     [(DETECTORS, '    if kind in STAGES_PAST_STOP and len(\n',
       '    if False and len(  # MUTANT\n')],
     BARE),

    # ------------------------------------------------------------------ what a model may do
    ("the model is called when the deterministic state was SUFFICIENT - every load with work is a "
     "model's question",
     [(REASON, '    if any(n.handling is Handling.MODEL_REASONING for n in state.needs):\n'
               '        return Route(task, True, "act_or_wait_not_settled_by_the_record")\n',
       '    if True:  # MUTANT\n'
       '        return Route(task, True, "act_or_wait_not_settled_by_the_record")\n')],
     ROUTED),

    ("an action the need does not offer is ACCEPTED - an invented action, or another need's",
     [(REASON, '        if item.recommended_action not in offered[item.need_id]:\n',
       '        if False:  # MUTANT\n')],
     SUPPLIED),

    ("a need the request never supplied is ACCEPTED - the model names its own work",
     [(REASON, '        if need is None:\n            refused.append("need_id_not_supplied")\n'
               '            continue\n',
       '        if need is None:\n            need = next(iter(supplied.values()))  # MUTANT\n')],
     SUPPLIED),

    ("evidence the model was never shown is accepted as support",
     [(REASON, '        if not [e for e in item.evidence_ids if e in evidence[item.need_id]]:\n',
       '        if False:  # MUTANT\n')],
     SUPPLIED),

    ("the model SUPPRESSES a human's need - the posture is taken from the picks even while a "
     "human's need is open",
     [(REASON, '    if state.human_attention:\n        return Posture.HUMAN_ATTENTION.value\n'
               '    acting = False\n',
       '    acting = False  # MUTANT: a human\'s need no longer decides the posture\n')],
     SUPPRESS),

    ("a human's need OFFERS WAIT to the model - the closed set for a Conflict includes waiting",
     [(WORK, '            actions = (ShadowAction.ASK_HUMAN_REVIEW_FINANCIAL_DISCREPANCY,)\n'
             '            why = f"Sources state different figures',
       '            actions = (ShadowAction.ASK_HUMAN_REVIEW_FINANCIAL_DISCREPANCY,\n'
       '                       ShadowAction.WAIT)  # MUTANT\n'
       '            why = f"Sources state different figures')],
     REBILLED),

    ("a FAILED call is read as advice to wait - a timeout makes an open candidate disappear",
     [(REASON, '                              posture=effective_posture(state, {}), digest=digest,\n',
       '                              posture=Posture.WAIT.value, digest=digest,  # MUTANT\n')],
     FAILURE),

    ("the same question is paid for TWICE - an unchanged load re-asks on every evaluation",
     [(REASON, '        if previous is not None and previous.digest == digest and previous.status '
               '== ADVISED:\n',
       '        if False:  # MUTANT\n')],
     REUSE),

    ("money reaches the model - a discrepancy's figures are shown in the request it is handed",
     [(WORK, '                why=f"Carrier invoice {payable.value(\'invoice_number\')} does not '
             'match what was "\n                    f"agreed: "',
       '                why=f"Carrier invoice {payable.value(\'invoice_number\')} does not '
       'match what was "\n                    f"agreed ({payable.value(\'linehaul\').display()}): "')],
     MONEY),

    # ------------------------------------------------------------------ the continuous load loop
    ("a deadline passes in silence and the loop does not look - a late pickup is first seen when "
     "the truck finally arrives and the lateness is already over",
     [(LOOP, "            if look < before:\n", "            if look < before and False:  # MUTANT\n")],
     f"{L}::test_a_deadline_that_passes_in_silence_is_a_moment_of_its_own"),

    ("a RESTART forgets when the loop last looked - a deadline that falls just after it is not a "
     "moment, and the late pickup is first seen when something else arrives",
     [(LOOP, "            intakes[history.tenant] = FreightIntake(conn, setups[history.tenant],\n"
             "                                                    interpreter=interpreter)\n",
       "            intakes[history.tenant] = FreightIntake(conn, setups[history.tenant],\n"
       "                                                    interpreter=interpreter)\n"
       "            latest.pop(history.tenant, None)  # MUTANT\n")],
     f"{L}::test_a_restart_just_before_a_deadline_still_sees_the_deadline"),

    ("a load NOBODY HAS BOOKED is called quiet - it has no needs only because covering it is "
     "outside the loop",
     [(LOOP, "        return self.state.routine_work_is_zero and self.booked\n",
       "        return self.state.routine_work_is_zero  # MUTANT\n")],
     f"{L}::test_a_load_nobody_has_booked_is_never_called_quiet"),

    ("a human's confirmation records her word and RESOLVES NOTHING - the Conflict M7 holds stays "
     "open, so the load she settled is disputed forever",
     [(INTAKE, '                    entity_ref=load_ref, field="tracking_status", human_id=human_id,\n',
       '                    entity_ref=load_ref, field="tracking_status_", human_id=human_id,\n')],
     f"{L}::test_a_disputed_load_stays_a_humans_until_a_human_settles_it"),

    ("a dispute a human SETTLED is raised again from the same two statements - her decision "
     "settles nothing that was said before it",
     [(DETECTORS, "        if later_fact.as_of <= decided_at:\n            continue\n",
       "        if False:  # MUTANT\n            continue\n")],
     f"{L}::test_a_disputed_load_stays_a_humans_until_a_human_settles_it"),

    ("a contradiction made AFTER a human's decision is silently lost - it is given the id of the "
     "dispute she already closed, so no new Conflict is ever raised",
     [(DETECTORS, '"tracking_status", *((settled,) if settled else ())),',
       '"tracking_status"),  # MUTANT')],
     f"{L}::test_a_later_contradiction_after_a_humans_decision_is_a_new_dispute"),

    ("a claim a human OVERRULED still counts - she says it has not delivered, and the driver's "
     "'delivered' goes on making the load delivered",
     [(PROJECTION, '        return [t for t in self.tracking if t.overruled_by is None]',
       '        return list(self.tracking)  # MUTANT')],
     f"{L}::test_a_human_who_says_it_has_not_delivered_overrules_the_claim"),

    ("a tracking record may SPEAK AS THE OWNER - the owner's confirmation is admitted as a signal "
     "any source can send",
     [(MODEL, '    "tracking_provider_position", "driver_assertion", "carrier_assertion", '
              '"tms_status",\n)',
       '    "tracking_provider_position", "driver_assertion", "carrier_assertion", '
       '"tms_status",\n    "owner_confirmation",  # MUTANT\n)')],
     f"{L}::test_no_source_but_a_recorded_human_can_speak_as_the_owner"),

    ("a human's decision is NOT COUNTED as a touch - every load looks as if nobody had to act",
     [(LOOP, '                if (o.get("parsed") or {}).get("kind") == "human_assertion"])',
       '                if (o.get("parsed") or {}).get("kind") == "no_such_kind"])  # MUTANT')],
     f"{L}::test_a_humans_decision_is_a_touch_and_so_is_one_still_owed"),

    ("a proposal says it was SENT - a draft is reported as an outbound message",
     [(LOOP, '                "sent": False}', '                "sent": True}  # MUTANT')],
     f"{L}::test_a_proposal_is_words_and_nothing_is_sent"),

    ("MONEY reaches the picture - a timeline sentence is quoted with its amounts intact",
     [(LOOP, '    return _BARE_AMOUNT.sub("[amount withheld]", _AMOUNT.sub("[amount withheld]", '
             'text))',
       '    return text  # MUTANT')],
     f"{L}::test_no_picture_carries_money"),

    ("work that is on NO LOAD is left off the board - every load is quiet and a refused assertion "
     "sits where nobody will see it",
     [(LOOP, "    unplaced = {tenant: evaluate_unplaced_work(",
       "    unplaced = {tenant: () and evaluate_unplaced_work(")],
     f"{L}::test_only_a_recorded_human_and_only_a_real_status_can_settle_it"),

    ("a refused record is TWO needs - the held record and the Exception raised about it are each "
     "put in front of a human",
     [(WORK, "        if item.observation_id in explained:\n", "        if False:  # MUTANT\n")],
     f"{L}::test_only_a_recorded_human_and_only_a_real_status_can_settle_it"),

    # ------------------------------------------------------------------ an overruled claim
    ("an OVERRULED claim is still arrival evidence - the driver's 'delivered' goes on answering "
     "the delivery appointment's watch after a human says he has not delivered",
     [(DETECTORS, "    standing = view.standing_tracking()\n    arrivals = [",
       "    standing = view.tracking  # MUTANT\n    arrivals = [")],
     OVERRULED),

    ("the watch an overruled claim answered is NEVER OWED AGAIN - it is raised under the id M8 "
     "already holds DISCHARGED, so the load goes quiet and the missed delivery is never late",
     [(DETECTORS, "                            if evidence\n",
       "                            if True  # MUTANT\n")],
     OVERRULED),

    ("a watch something ELSE still answers is reopened anyway - overruling one claim re-asks for "
     "an arrival the provider and the human both still evidence",
     [(DETECTORS, "                            if evidence\n",
       "                            if False  # MUTANT\n")],
     f"{L}::test_a_watch_other_standing_evidence_answers_is_not_reopened"),

    # Two things each keep an owed-again watch from being raised a third time: the stop already has
    # a live watch for this deadline, and an owed generation is returned as itself. Either alone
    # holds, so the defect needs both gone.
    ("a watch that is owed again is raised a THIRD time once it goes overdue - one missed "
     "delivery becomes two pieces of work",
     [(DETECTORS, '        if any(e["expected_type"] == expected_type and e["state"] in OWED_STATES\n',
       '        if False and any(e["expected_type"] == expected_type  # MUTANT\n'
       '                         and e["state"] in OWED_STATES\n'),
      (DETECTORS, "        if states.get(expectation_id) in (None, *OWED_STATES):\n",
       '        if states.get(expectation_id) in (None, "RAISED", "INDETERMINATE"):  # MUTANT\n')],
     OVERRULED),

    ("the picture says an overruled claim SATISFIED the watch - the load is late for delivery and "
     "its history says the delivery was answered by the driver's word",
     [(WORK, '        if state == "DISCHARGED" and answer in overruled and answer not in standing ',
       '        if False and answer in overruled and answer not in standing ')],
     OVERRULED),

    ("an overruled claim still REACHES A STOP - an unconfirmed delivery appointment stops being "
     "work because of a 'delivered' a human overruled",
     [(WORK, "    standing = view.standing_tracking()\n    if any(t.stop_key == stop_key",
       "    standing = view.tracking  # MUTANT\n    if any(t.stop_key == stop_key")],
     f"{L}::test_an_overruled_claim_reaches_no_stop"),

    ("the STAGE rests on an overruled claim - a human says the truck is on the dock and the "
     "picture goes on calling the load picked up and in transit",
     [(WORK, '    statuses = {t.value("status") for t in view.standing_tracking()}\n'
             "    if statuses & set(UNDER_WAY_STATUSES):",
       '    statuses = {t.value("status") for t in view.tracking}  # MUTANT\n'
       "    if statuses & set(UNDER_WAY_STATUSES):")],
     f"{L}::test_the_stage_of_a_load_does_not_rest_on_an_overruled_claim"),

    ("an overruled 'loaded' STARTS THE TRACKING CLOCK - a truck a human says is on the dock is "
     "watched as if it were under way",
     [(DETECTORS, "                                          for t in view.standing_tracking()):\n",
       "                                          for t in signals):  # MUTANT\n")],
     f"{L}::test_the_stage_of_a_load_does_not_rest_on_an_overruled_claim"),

    ("the tracking watch an overruled DELIVERY REPORT answered is left answered - nobody is "
     "waiting to hear from a truck a human says is still on the road",
     [(DETECTORS,
       "    return _owed_again_id(view, TRACKING_UPDATE, anchor.origin_observation_id)\n",
       '    return stable_id("exp", view.load.tenant_id, view.ref, TRACKING_UPDATE,  # MUTANT\n'
       "                     anchor.origin_observation_id)\n")],
     f"{L}::test_a_tracking_watch_an_overruled_claim_answered_is_owed_again"),

    ("a human act dated IN THE FUTURE is authority - it settles everything said until then, and "
     "the provider's later contradiction is silenced",
     [(HISTORY, '    if record.kind == "human_assertion" and (to_utc(',
       '    if False and record.kind == "human_assertion" and (to_utc(')],
     FUTURE),

    ("the future rule refuses a human act dated at the INSTANT it was received - every ordinary "
     "decision is held unreadable",
     [(HISTORY, '                                             > to_utc(record.received_at, '
                'what="received_at")):\n',
       '                                             >= to_utc(record.received_at, '
       'what="received_at")):\n')],
     FUTURE),

    # ------------------------------------------------------------------ a moved appointment
    ("a CANCELLED watch stands in for the one that is owed - the appointment comes back to the "
     "window that watch was raised for, nothing is raised, and the load goes quiet (P9-D65)",
     [(DETECTORS, "        if states.get(expectation_id) in (None, *OWED_STATES):\n",
       '        if states.get(expectation_id) in (None, *OWED_STATES, "CANCELLED"):  # MUTANT\n')],
     RESTORED),

    ("a moved appointment that is then missed is watched TWICE - the watch that followed it "
     "there, and a second one raised beside it under the new window's id (P9-D59)",
     [(DETECTORS, '        if any(e["expected_type"] == expected_type and e["state"] in OWED_STATES\n',
       '        if False and any(e["expected_type"] == expected_type  # MUTANT\n'
       '                         and e["state"] in OWED_STATES\n')],
     f"{L}::test_the_system_of_record_moving_an_appointment_earlier_and_back_is_still_watched"),

    ("an OWED watch is not found again under its own id - a tracking watch a later ping answers "
     "is looked for under its next generation, stays owed, and a pinging truck is called silent",
     [(DETECTORS, "        if states.get(expectation_id) in (None, *OWED_STATES):\n",
       "        if states.get(expectation_id) is None:  # MUTANT\n")],
     f"{L}::test_a_missed_restored_appointment_is_work_of_its_own_beside_the_tracking_cadence"),

    ("a watch the truck's arrival already answered is raised AGAIN beside it - on a moved "
     "appointment a late arrival leaves two answered watches and two Exceptions to close (P9-D59)",
     [(DETECTORS, '        if any(e["expected_type"] == expected_type and e["state"] == "DISCHARGED"\n',
       '        if False and any(e["expected_type"] == expected_type  # MUTANT\n'
       '                         and e["state"] == "DISCHARGED"\n')],
     f"{L}::test_a_moved_appointment_missed_and_then_met_is_one_watch_and_one_exception"),
]


def _run_edits(edits, guard) -> tuple[str, str]:
    originals: dict[Path, bytes] = {}
    for rel, _old, _new in edits:
        path = ROOT / rel
        if not path.exists():
            return "SETUP-FAIL", f"{rel} does not exist"
        if path not in originals:
            originals[path] = path.read_bytes()

    for rel, old, _new in edits:
        text = originals[ROOT / rel].decode("utf-8")
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


def test_the_p9_load_work_mutation_battery_catches_every_mutant():
    """THE PYTEST-COLLECTED ENTRY POINT: `python -m pytest scripts/mutate_p9_load_work.py`. Every
    mutant must be CAUGHT — guard GREEN un-mutated, RED under the reintroduced defect, GREEN again
    after a byte-for-byte in-memory restore — over a population floored so `== 0` cannot be vacuous.

    Not collected by a bare `pytest eval` (outside `testpaths`, not named `test_*.py`): a slow battery
    runs when it is named, on purpose."""
    assert len(CASES) >= 25, f"the load-work battery carries only {len(CASES)} mutants"
    assert main() == 0, "the load-work mutation battery did NOT report every mutant CAUGHT"


def main(only: str | None = None) -> int:
    """Run the battery. `only` narrows it to the mutants whose label contains that text — for
    iterating on one; the collected test above always runs every mutant."""
    cases = [c for c in CASES if only is None or only in c[0]]
    results = [(label, *_run_edits(edits, guard)) for label, edits, guard in cases]
    print("\n=========== P9 LOAD-WORK MUTATION BATTERY ===========")
    for label, verdict, detail in results:
        print(f"  [{verdict:11s}] {label}" + (f"\n               -> {detail}" if detail else ""))
    caught = sum(1 for _, verdict, _ in results if verdict == "CAUGHT")
    print(f"\n  {caught} of {len(results)} mutants CAUGHT")
    return 0 if caught == len(results) and results else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))
