#!/usr/bin/env python3
"""P9 deep-end 1 mutation battery — a guard never seen to fail is a decoration (CLAUDE.md sec 6).

Each mutant reintroduces ONE real defect and names the test that must turn RED under it. Two families:

  * THE FREIGHT BEHAVIOUR. A reference lookup that leaks across brokerages; a POD force-bound to the
    nearer of two loads; an ambiguous PO resolved to the first candidate; a driver's text taking the
    provenance of its binding; a guess allowed to gate; a conversational rate left un-weakened; a
    counterparty's "it was approved" treated as an authorization; a non-owner authorization made
    constructible; content allowed to declare its own provenance; delivered treated as POD-on-file;
    a POD treated as billing-ready; half a POD accepted; a duplicate re-processed; a quoted promise
    raised again; a conflict flattened to the latest value; a blind channel recorded as healthy; a
    facility window read in the wrong timezone; a billed mismatch quietly dropped; a mapping made
    deletable; a model-originated mapping made storable; a detector that never stops asking.

  * THE SHIPS-DARK GUARDS P9 REPLACED. Eleven guards now admit one P9 module by exact path. For each,
    a SECOND importer is added — in the subpackage spelling three of the old guards could not see —
    and the guard must fire. Plus the P9 guards themselves: an outside module importing the spine, a
    path to an effect-capable adapter, a gate constructed, a model SDK imported, a review claimed.

It mutates TEXT and shells out to pytest; it NEVER imports the code under test, and it NEVER uses git
to undo a mutation. Originals are held in memory and restored unconditionally; `__pycache__` is purged
around every run so a same-length restore cannot leave poisoned bytecode and a false green.

    .venv/bin/python scripts/mutate_p9_freight_domain.py
    .venv/bin/python -m pytest scripts/mutate_p9_freight_domain.py -q -p no:cacheprovider
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

FD = "src/freight_recon/freight_domain"
MAPPING = f"{FD}/entity_mapping.py"
INTAKE = f"{FD}/intake.py"
PROJECTION = f"{FD}/projection.py"
MODEL = f"{FD}/model.py"
FINANCIAL = f"{FD}/financial.py"
FOUNDATION = f"{FD}/foundation.py"
DETECTORS = f"{FD}/detectors.py"
TIMELINE = f"{FD}/timeline.py"
MIGRATION = "src/freight_recon/migrations/phase9_external_entity_mappings.py"
M8 = "src/freight_recon/expectation.py"
OUTSIDE = "src/freight_recon/render.py"
REGISTRY = "docs/implementation/IMPLEMENTATION-REGISTRY.yaml"

T = "eval/tests/test_p9_freight_histories.py"
D = "eval/tests/test_p9_freight_domain_ships_dark.py"

#: An edit whose `old` is this sentinel APPENDS `new` to the file instead of replacing an anchor.
APPEND = None


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    r = subprocess.run([PY, "-m", "pytest", nodeid, "-q", "-p", "no:cacheprovider"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


def _second_importer(statement: str) -> list[tuple[str, str | None, str]]:
    """A second production importer of a foundational machine, inside the P9 package and in the
    SUBPACKAGE spelling. The function is never called: only its presence is the defect."""
    return [(MODEL, APPEND, f"\n\ndef _mutant_second_importer():\n    {statement}  # MUTANT\n")]


# (label, [(rel_path, old_anchor | APPEND, new_text), ...], guard_nodeid). An anchor appears EXACTLY ONCE.
CASES = [
    # ------------------------------------------------------------------ freight behaviour
    ("the reference lookup leaks across brokerages — the tenant predicate is widened to always-true, "
     "so one tenant's LD-48219 resolves against another tenant's mapping ([C-1], CD-19)",
     [(MAPPING,
       'sql = ("SELECT * FROM external_entity_mappings WHERE tenant = ? AND external_system = ? "',
       'sql = ("SELECT * FROM external_entity_mappings WHERE (tenant = ? OR 1=1) AND external_system = ? "')],
     f"{T}::test_the_same_load_number_in_two_tenants_cannot_cross_bind"),

    ("a POD whose references name DIFFERENT loads is force-bound to the first — the wrong-load "
     "document is silently attached (CD-6, GR-8)",
     [(INTAKE, "            resolution.exact = sorted(merged.items())\n",
       "            resolution.exact = sorted(merged.items())[:1]  # MUTANT\n")],
     f"{T}::test_a_pod_cannot_silently_bind_to_the_wrong_load"),

    ("a reference that names SEVERAL loads is resolved to the first candidate instead of staying "
     "ambiguous (GR-8: a guess never binds)",
     [(INTAKE, "            resolution.exact = [(ref, merged[ref]) for ref in sorted(common)]\n",
       "            resolution.exact = [(ref, merged[ref]) for ref in sorted(common)][:1]  # MUTANT\n")],
     f"{T}::test_an_ambiguous_load_reference_stays_ambiguous"),

    ("a fact takes the provenance of its BINDING — the M5 row's column is read instead of how the "
     "record was acquired, so a driver's text bound by exact id reads LINKER_INFERRED (R-P2)",
     [(PROJECTION, "value=value, provenance_class=provenance or assigned,",
       'value=value, provenance_class=provenance or observation["provenance_class"],')],
     f"{T}::test_binding_an_artifact_does_not_strengthen_what_it_says"),

    ("a MODEL_INFERRED fact may gate — the consequential-read predicate is short-circuited, so a "
     "guess can stand in for an agreement (AC-SAFE-015)",
     [(MODEL, "        return may_gate_consequential_action(self.provenance_class)",
       "        return True  # MUTANT")],
     f"{T}::test_a_conversational_rate_never_becomes_the_buy_rate"),

    ("a rate said in conversation is NOT weakened to a guess — it is retained at MODEL_EXTRACTED and "
     "becomes readable as a buy figure (V-14 interim behaviour)",
     [(PROJECTION,
       'observation, parsed, carrier_owed(item["amount_minor"], item["currency"]),\n'
       "                        provenance=MODEL_INFERRED))",
       'observation, parsed, carrier_owed(item["amount_minor"], item["currency"])))')],
     f"{T}::test_a_conversational_rate_never_becomes_the_buy_rate"),

    ("an accessorial with NO recorded human authorization is reported AUTHORIZED — the carrier's "
     "line is waved through (CD-5, V-15)",
     [(FINANCIAL, 'return "UNRESOLVED", ("no recorded human authorization exists',
       'return "AUTHORIZED", ("no recorded human authorization exists')],
     f"{T}::test_an_accessorial_mention_does_not_become_a_human_authorization"),

    ("an Accessorial Authorization is constructible with non-owner provenance — a model or a "
     "counterparty can create the right to pay (CD-5, ADR-003)",
     [(MODEL, '        if self.provenance_class != "OWNER_ASSERTED":\n            raise DomainModelError(\n'
              '                f"an Accessorial Authorization must be OWNER_ASSERTED;',
       '        if False:  # MUTANT\n            raise DomainModelError(\n'
       '                f"an Accessorial Authorization must be OWNER_ASSERTED;')],
     f"{T}::test_an_accessorial_mention_does_not_become_a_human_authorization"),

    ("inbound content may DECLARE ITS OWN PROVENANCE at depth — the nested refusal is skipped (R-P1)",
     [(FOUNDATION, "        _reject_nested_provenance(content)\n        provenance = assign_at_runtime",
       "        provenance = assign_at_runtime")],
     f"{T}::test_all_twenty_histories_run_and_every_labeled_outcome_holds"),

    ("delivered IMPLIES the POD is on file — a reported delivery satisfies the document requirement "
     "(CD-8)",
     [(PROJECTION, "            if document is not None:\n                state, reason = \"SATISFIED\"",
       "            if document is not None or delivered:  # MUTANT\n                state, reason = \"SATISFIED\"")],
     f"{T}::test_delivered_does_not_imply_pod_received"),

    ("a POD on file IMPLIES billing-ready — the delivery guard is dropped from invoice eligibility "
     "(CD-9)",
     [(PROJECTION, "        if not view.delivered_claims():\n            blockers.append(",
       "        if False:  # MUTANT\n            blockers.append(")],
     f"{T}::test_pod_received_does_not_imply_billing_ready"),

    ("half a POD satisfies the requirement — the page-completeness check is dropped (CD-3)",
     [(PROJECTION,
       '            if pages.get("present", 0) < pages.get("expected", 1):\n                continue\n'
       '            if doc_type == "POD"',
       '            if doc_type == "POD"')],
     f"{T}::test_an_unusable_document_does_not_satisfy_a_requirement"),

    ("a QUOTED promise is a new promise — a forwarded email raises a second Expectation",
     [(DETECTORS, '        if commitment["in_quoted_text"]:\n            continue\n',
       '        if False:  # MUTANT\n            continue\n')],
     f"{T}::test_duplicate_inbound_evidence_does_not_create_duplicate_canonical_work"),

    ("a DUPLICATE is re-processed — an identical re-delivery no longer stops at the confirmation",
     [(INTAKE, "        if observed.duplicate:\n", "        if False:  # MUTANT\n")],
     f"{T}::test_duplicate_inbound_evidence_does_not_create_duplicate_canonical_work"),

    ("a conflict is FLATTENED — disagreeing sources are never a dispute, so the latest statement "
     "silently wins (CD-20)",
     [(MODEL, "        if not self.contested:\n            return []",
       "        if True:  # MUTANT\n            return []")],
     f"{T}::test_conflicting_appointment_facts_do_not_flatten_into_one_guessed_value"),

    ("a BLIND channel is recorded as HEALTHY — a down tracking feed makes the carrier 'late' (CD-14)",
     [(INTAKE, 'health=str(payload["health"]), probe_source=record.source_system)',
       'health="HEALTHY", probe_source=record.source_system)  # MUTANT')],
     f"{T}::test_tracking_unavailable_does_not_mean_late"),

    ("a facility appointment is read in UTC — an 11:00 Detroit window becomes 11:00 UTC (F-25)",
     [(DETECTORS,
       '            originating_timezone=window["timezone"],\n'
       '            appointment_local=datetime.fromisoformat(window["end_local"])))',
       '            originating_timezone="UTC",\n'
       '            appointment_local=datetime.fromisoformat(window["end_local"])))')],
     f"{T}::test_a_facility_appointment_deadline_is_evaluated_in_the_facilitys_timezone"),

    ("a billed LINEHAUL mismatch is silently dropped — the invoice reconciles against a rate "
     "confirmation it disagrees with (CD-4, CD-16)",
     [(FINANCIAL, "                if exp.amount_minor != act.amount_minor:\n                    discrepancies.append(Discrepancy(\n                        code=code,",
       "                if False:  # MUTANT\n                    discrepancies.append(Discrepancy(\n                        code=code,")],
     f"{T}::test_an_invoice_discrepancy_remains_visible"),

    ("a mapping can be DELETED — the no-delete trigger is disarmed, so the history a correction is "
     "explained against can be removed (CD-7)",
     [(MIGRATION,
       "BEFORE DELETE ON external_entity_mappings\n"
       "        BEGIN SELECT RAISE(ABORT, '{MAPPING_DELETE_ABORT}'); END",
       "BEFORE DELETE ON external_entity_mappings\n"
       "        BEGIN SELECT 1; END")],
     f"{T}::test_a_correction_supersedes_without_deleting_history"),

    ("a retired mapping can be EDITED back to ACTIVE — the immutability trigger no longer refuses a "
     "non-ACTIVE row (CD-6)",
     [(MIGRATION, "        WHEN OLD.state <> 'ACTIVE'\n          OR NEW.state = 'ACTIVE'\n",
       "        WHEN 0\n")],
     f"{T}::test_a_correction_supersedes_without_deleting_history"),

    ("a MODEL-originated mapping can be stored — the model classes are admitted to the table an exact "
     "lookup reads",
     [(MIGRATION, '    "SYSTEM_IMPORTED", "OWNER_ASSERTED", "LINKER_INFERRED", "RECONCILED",\n)',
       '    "SYSTEM_IMPORTED", "OWNER_ASSERTED", "LINKER_INFERRED", "RECONCILED", "MODEL_INFERRED",\n)')],
     f"{T}::test_a_correction_supersedes_without_deleting_history"),

    ("the detectors never stop asking — an owed document is expected again on every pass, so the "
     "settled picture is not a fixed point and replay is not inert",
     [(DETECTORS, "        if _has_owed(view, expected_type):\n            continue\n",
       "        if False:  # MUTANT\n            continue\n")],
     f"{T}::test_the_settled_picture_owes_nothing_new"),

    ("M8 lets a broader HEALTHY reading outvote an outage inside it — a DOWN window recorded within "
     "a HEALTHY month is ruled OVERDUE, converting our blindness into a counterparty's fault (I8, M-32)",
     [(M8, "        if contradicting:\n            return (contradicting[0][\"health\"], "
           "contradicting[0][\"coverage_id\"])",
       "        if False:  # MUTANT\n            return (contradicting[0][\"health\"], "
       "contradicting[0][\"coverage_id\"])")],
     f"{T}::test_an_outage_inside_a_healthy_window_is_blindness_not_lateness"),

    ("the timeline is narrated in ARRIVAL order — a stale snapshot is told as the latest news",
     [(TIMELINE,
       "    in_business_time = sorted(view.observations,\n"
       '                              key=lambda o: (o["as_of"], o["received_at"], o["observation_id"]))',
       "    in_business_time = list(view.observations)  # MUTANT")],
     f"{T}::test_a_late_record_binds_when_its_load_arrives_and_stale_news_does_not_regress"),

    # ------------------------------------------------------------------ the replaced ships-dark guards
    ("M5 gains a SECOND production importer",
     _second_importer("from ..observation import M5Machine"),
     "eval/tests/test_phase6_observation.py::test_m5_ships_dark"),
    ("M6 gains a SECOND production importer",
     _second_importer("from ..identity_binding_claim import M6Machine"),
     "eval/tests/test_phase6_identity_binding_claim.py::test_m6_ships_dark"),
    ("M7 gains a THIRD production importer",
     _second_importer("from ..conflict import M7Machine"),
     "eval/tests/test_phase6_conflict.py::test_ships_dark_no_production_importer"),
    ("M8 gains a SECOND production importer, in the subpackage spelling the old substring guard "
     "could not see",
     _second_importer("from ..expectation import M8Machine"),
     "eval/tests/test_phase6_expectation.py::test_m8_ships_dark_no_production_importer"),
    ("M9 gains a THIRD production importer",
     _second_importer("from ..exception import M9Machine"),
     "eval/tests/test_phase6_exception.py::test_m9_ships_dark_no_production_importer"),
    ("M1 gains a production importer outside the entity layer and the one P9 module",
     _second_importer("from ..work_item import WorkItemMachine"),
     "eval/tests/test_phase6_work_item.py::test_nothing_in_production_calls_this_machine_yet"),
    ("the Evidence store gains a SECOND outside importer, in the relative spelling the old guard "
     "could not see",
     _second_importer("from ..evidence import EvidenceStore"),
     "eval/tests/test_phase7_evidence.py::test_the_evidence_store_ships_dark_with_no_production_importer"),
    ("the provenance module gains a SECOND outside importer, in the relative spelling the old guard "
     "could not see",
     _second_importer("from ..provenance import as_class"),
     "eval/tests/test_phase7_provenance.py::test_the_provenance_module_ships_dark_with_no_production_importer"),
    ("the linker gains a SECOND production importer",
     _second_importer("from ..linker import link"),
     "eval/tests/test_phase7_identity.py::test_the_identity_and_lineage_modules_ship_dark"),
    ("the lineage walker gains a production importer",
     _second_importer("from ..lineage import trace"),
     "eval/tests/test_phase7_ships_dark.py::test_no_production_module_imports_any_p7_surface"),
    ("a SECOND module escalates a missed deadline through the U8.4 consumer",
     [(OUTSIDE, APPEND, "\n\ndef _mutant_second_caller(m9, envelope):\n"
                        "    return m9.consume_source_escalation(envelope)  # MUTANT\n")],
     "eval/tests/test_p8_u84_seams.py::test_u84_ships_dark_no_production_module_invokes_the_consumer"),

    # ------------------------------------------------------------------ P9's own darkness
    ("a second freight_domain module imports a foundational machine directly, around the "
     "composition module",
     _second_importer("from ..conflict import M7Machine"),
     f"{D}::test_foundation_is_the_only_freight_domain_module_that_imports_a_foundational_machine"),
    ("a production module OUTSIDE the package imports the freight spine — it is no longer dark",
     [(OUTSIDE, APPEND, "\n\ndef _mutant_live_caller():\n"
                        "    from .freight_domain import intake  # MUTANT\n    return intake\n")],
     f"{D}::test_nothing_outside_the_package_imports_the_freight_domain_except_its_one_harness"),
    ("the freight spine can REACH an effect-capable adapter",
     [(MODEL, APPEND, "\n\ndef _mutant_reaches_an_adapter():\n"
                      "    from ..tms_write import enter_approved_payable  # MUTANT\n"
                      "    return enter_approved_payable\n")],
     f"{D}::test_the_freight_domain_import_closure_reaches_nothing_effect_capable"),
    ("the freight spine constructs a gate registry — a second gate authority",
     [(TIMELINE, APPEND, "\n\ndef _mutant_mints_a_gate():\n    return GateRegistry()  # MUTANT\n")],
     f"{D}::test_the_freight_domain_constructs_no_gate_and_imports_no_model_or_network_client"),
    ("the freight spine imports a model SDK",
     [(TIMELINE, APPEND, "\n\ndef _mutant_asks_a_model():\n    import anthropic  # MUTANT\n"
                         "    return anthropic\n")],
     f"{D}::test_the_freight_domain_constructs_no_gate_and_imports_no_model_or_network_client"),
    ("the registry CLAIMS an independent review of P9-CP-1 that has not happened",
     [(REGISTRY, "        independent_review_report: null\n        independent_review_note: >-\n"
                 "          NO INDEPENDENT REVIEW HAS BEEN PERFORMED.",
       "        independent_review_report: docs/implementation/p9-review.md\n"
       "        independent_review_note: >-\n          NO INDEPENDENT REVIEW HAS BEEN PERFORMED.")],
     f"{D}::test_p9_is_recorded_in_progress_and_unreviewed_and_p10_is_still_blocked"),
    ("the registry promotes P10 out of BLOCKED",
     [(REGISTRY, "  - unit_id: P10\n    name: Delivered Load Closure - shadow slice\n    status: BLOCKED",
       "  - unit_id: P10\n    name: Delivered Load Closure - shadow slice\n    status: READY")],
     f"{D}::test_p9_is_recorded_in_progress_and_unreviewed_and_p10_is_still_blocked"),
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
        if old is APPEND:
            continue
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
            mutated[path] = before + new if old is APPEND else before.replace(old, new, 1)
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


def test_the_p9_freight_domain_mutation_battery_catches_every_mutant():
    """THE PYTEST-COLLECTED ENTRY POINT: `python -m pytest scripts/mutate_p9_freight_domain.py`. Every
    mutant must be CAUGHT — guard GREEN un-mutated, RED under the reintroduced defect, GREEN again
    after a byte-for-byte in-memory restore — over a population floored so `== 0` cannot be vacuous.

    Not collected by a bare `pytest eval` (outside `testpaths`, not named `test_*.py`): a slow battery
    runs when it is named, on purpose."""
    assert len(CASES) >= 40, f"the P9 battery carries only {len(CASES)} mutants"
    assert main() == 0, "the P9 mutation battery did NOT report every mutant CAUGHT"


def main(only: str | None = None) -> int:
    """Run the battery. `only` narrows it to the mutants whose label contains that text — for
    iterating on one; the collected test above always runs every mutant."""
    cases = [c for c in CASES if only is None or only in c[0]]
    results = [(label, *_run_edits(edits, guard)) for label, edits, guard in cases]
    print("\n=========== P9 FREIGHT-DOMAIN MUTATION BATTERY ===========")
    for label, verdict, detail in results:
        print(f"  [{verdict:11s}] {label}" + (f"\n               -> {detail}" if detail else ""))
    caught = sum(1 for _, verdict, _ in results if verdict == "CAUGHT")
    print(f"\n  {caught} of {len(results)} mutants CAUGHT")
    return 0 if caught == len(results) and results else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))
