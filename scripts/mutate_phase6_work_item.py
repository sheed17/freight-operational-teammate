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

T = "eval/tests/test_phase6_work_item.py"


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
]


def _run_text_case(case) -> tuple[str, str]:
    label, rel, old, new, guard = case
    path = ROOT / rel
    if not path.exists():
        return "SETUP-FAIL", f"{rel} does not exist"
    original = path.read_bytes()
    text = original.decode("utf-8")
    if text.count(old) != 1:
        return "SETUP-FAIL", f"anchor appears {text.count(old)}x in {rel} (need exactly 1)"

    purge_pycache()
    if not run_guard(guard):
        return "SETUP-FAIL", "guard already RED before mutation"

    mutated = text.replace(old, new, 1)
    if mutated == text:
        return "SETUP-FAIL", "mutation was a no-op"

    try:
        path.write_text(mutated, encoding="utf-8")
        purge_pycache()
        caught = not run_guard(guard)
    finally:
        path.write_bytes(original)
        purge_pycache()
    if path.read_bytes() != original:
        return "RESTORE-RED", f"byte-for-byte restore FAILED for {rel}"
    if not run_guard(guard):
        return "RESTORE-RED", "guard red after restore - investigate"
    return ("CAUGHT" if caught else "MISS"), ""


def main() -> int:
    results = [(c[0], *_run_text_case(c)) for c in TEXT_CASES]
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
