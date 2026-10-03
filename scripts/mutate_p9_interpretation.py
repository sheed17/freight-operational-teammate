#!/usr/bin/env python3
"""P9 deep-end 2 mutation battery — a guard never seen to fail is a decoration (CLAUDE.md sec 6).

Each mutant reintroduces ONE real defect in model-backed interpretation and names the test that must
turn RED under it. Three families:

  * WHAT A READING MAY BECOME. Evidence no longer required; an amount that is not in the message; a
    stop guessed when none was stated; a quoted promise read as new (by structure, and by the
    reader's own flag); a deadline run from receipt, or accepted in the past; a counterparty's
    sentence confirming an appointment; two parties in one inbox collapsed into one source; an
    assumed currency left un-weakened; a claimed approval dropped; a counterparty's correction that
    asks nobody; a failed reading that tells nobody; half an invoice extracted; spans not retained.

  * WHAT A MODEL MAY NOT DO TO IDENTITY. An id the request never supplied accepted; a candidate with
    no evidence accepted; a single clearly-supported candidate bound; a model candidate recorded as
    an exact match; another brokerage's id accepted.

  * THE BOUNDARY ITSELF. A model called without a route; a structured record sent to a model; an
    exact link that still asks; a rejection retried; the retry bound lifted; the budget unenforced;
    a recording ignored, or replayed against a different prompt; a live gateway constructible by
    default; the SDK retrying behind the gateway; a key or message content reaching telemetry; the
    live switch not required; a second SDK importer; a second caller of a gateway task; the freight
    domain able to build its own gateway; an authority field in the output vocabulary; production
    code or a third script reaching the spine through the eval corpus.

It mutates TEXT and shells out to pytest; it NEVER imports the code under test, and it NEVER uses git
to undo a mutation. Originals are held in memory and restored unconditionally; `__pycache__` is purged
around every run so a same-length restore cannot leave poisoned bytecode and a false green.

    .venv/bin/python scripts/mutate_p9_interpretation.py
    .venv/bin/python scripts/mutate_p9_interpretation.py "quoted"     # only matching mutants
    .venv/bin/python -m pytest scripts/mutate_p9_interpretation.py -q -p no:cacheprovider
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

FD = "src/freight_recon/freight_domain"
INF = "src/freight_recon/inference"
INTERP = f"{FD}/interpretation.py"
INTAKE = f"{FD}/intake.py"
PROJECTION = f"{FD}/projection.py"
FOUNDATION = f"{FD}/foundation.py"
DETECTORS = f"{FD}/detectors.py"
MODEL = f"{FD}/model.py"
GATEWAY = f"{INF}/gateway.py"
OPENAI = f"{INF}/openai_responses.py"
LEDGER = f"{INF}/ledger.py"
RECORDING = f"{INF}/recording.py"
CONTRACTS = f"{INF}/contracts.py"
OUTSIDE = "src/freight_recon/render.py"
OTHER_SCRIPT = "scripts/check_env.py"
REGISTRY = "docs/implementation/IMPLEMENTATION-REGISTRY.yaml"
EVAL_SCRIPT = "scripts/run_freight_interpretation_eval.py"

I = "eval/tests/test_p9_freight_interpretation.py"  # noqa: E741
G = "eval/tests/test_p9_inference_gateway.py"
D = "eval/tests/test_p9_freight_domain_ships_dark.py"

#: An edit whose `old` is this sentinel APPENDS `new` to the file instead of replacing an anchor.
APPEND = None

INVENTED = f"{I}::test_the_model_cannot_invent_a_candidate_load_id"
NEVER_BINDS = f"{I}::test_a_model_proposed_candidate_never_binds_however_clearly_it_is_supported"
QUOTED = f"{I}::test_a_quoted_or_forwarded_promise_creates_no_second_obligation"
EVIDENCE = f"{I}::test_an_item_whose_evidence_is_not_in_the_message_is_not_extracted"
APPOINTMENTS = (f"{I}::test_conflicting_appointment_messages_raise_a_conflict_not_a_guessed_"
                f"overwrite")
SDK = f"{G}::test_one_module_in_the_inference_boundary_imports_a_model_sdk"
LEAK = f"{G}::test_the_openai_adapter_classifies_failures_and_never_leaks_a_key"


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def run_guard(nodeid: str) -> bool:
    r = subprocess.run([PY, "-m", "pytest", nodeid, "-q", "-p", "no:cacheprovider"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


# (label, [(rel_path, old_anchor | APPEND, new_text), ...], guard_nodeid). An anchor appears EXACTLY ONCE.
CASES = [
    # ------------------------------------------------------------------ what a reading may become
    ("an item is extracted WITHOUT evidence — a quote that is not in the message no longer drops "
     "the item (evidence-first extraction)",
     [(INTERP,
       '            result.drop(kind, "evidence_not_in_content")\n            return None\n',
       '            span = Span("body", 0, 0, "")  # MUTANT\n')],
     EVIDENCE),

    ("an amount that is NOT in the message is accepted — the model's digits are parsed without "
     "being checked against the content (the model never chooses an amount)",
     [(INTERP,
       '    if not amount_text or not _contains(amount_text.strip().lstrip("$").strip(),\n'
       '                                        body + "\\n" + subject):\n        return None\n',
       '    if not amount_text:  # MUTANT\n        return None\n')],
     EVIDENCE),

    ("an arrival with NO stated stop is placed at the pickup — the deterministic layer guesses "
     "which facility a bare 'checked in' means",
     [(INTERP, '    ("LOADED", "PICKUP"): ("LOADED", "PICKUP"),\n',
       '    ("LOADED", "PICKUP"): ("LOADED", "PICKUP"),\n'
       '    ("ARRIVED", "UNSPECIFIED"): ("AT_PICKUP", "PICKUP"),  # MUTANT\n')],
     f"{I}::test_the_labeled_eval_covers_what_it_claims_and_its_scorer_can_fail"),

    ("a promise inside FORWARDED material is read as new — the structural quote detection is "
     "dropped and only the reader's own flag is trusted",
     [(INTERP,
       '        quoted = bool(getattr(item, "in_quoted_text", False)) or _in_regions(span, regions)\n',
       '        quoted = bool(getattr(item, "in_quoted_text", False))  # MUTANT\n')],
     QUOTED),

    ("the reader's own 'this is quoted' is ignored — a quotation with no structural marker is "
     "treated as a new statement",
     [(INTERP,
       '        quoted = bool(getattr(item, "in_quoted_text", False)) or _in_regions(span, regions)\n',
       '        quoted = _in_regions(span, regions)  # MUTANT\n')],
     QUOTED),

    ("a promise's deadline runs from when the message was RECEIVED, not when it was said",
     [(INTAKE, "        reading = self._read_content(record, parsed, observation_id, as_of)\n",
       "        reading = self._read_content(record, parsed, observation_id, received_at)  # MUTANT\n")],
     f"{I}::test_a_raw_promise_becomes_an_existing_expectation_with_a_deterministic_deadline"),

    ("a deadline that is NOT after the message is accepted — 'by 8' misread as 08:00 becomes an "
     "Expectation already overdue when it is raised",
     [(INTERP, "    if due <= sent or due - sent > MAX_COMMITMENT_HORIZON:\n        return None\n",
       "    if False:  # MUTANT\n        return None\n")],
     f"{I}::test_a_deadline_is_arithmetic_on_what_was_read_never_a_date_the_model_chose"),

    ("a counterparty's sentence CONFIRMS an appointment — the status a message claims is observed "
     "on the Appointment (CD-13: REQUESTED is not CONFIRMED)",
     [(PROJECTION,
       '            "end_local": f"{day}T{item[\'end_time\'] or item[\'start_time\']}", "timezone": zone,\n'
       '            "status": None}\n',
       '            "end_local": f"{day}T{item[\'end_time\'] or item[\'start_time\']}", "timezone": zone,\n'
       '            "status": "CONFIRMED"}  # MUTANT\n')],
     APPOINTMENTS),

    ("two parties writing to one inbox are ONE source — a later message silently supersedes "
     "another party's statement instead of disputing it",
     [(PROJECTION, "        speaker = claim_source(observation, payload)\n",
       "        speaker = None  # MUTANT\n")],
     APPOINTMENTS),

    ("an amount whose currency was ASSUMED is not weakened — it stays MODEL_EXTRACTED and can "
     "dispute and gate (debt P9-D12)",
     [(PROJECTION,
       '    return carrier_owed(item["amount_minor"], assumed), MODEL_INFERRED\n',
       '    return carrier_owed(item["amount_minor"], assumed), None  # MUTANT\n')],
     f"{I}::test_an_amount_with_no_stated_currency_is_retained_as_a_guess"),

    ("a claimed approval is DROPPED — 'per approval from Mike' is no longer recorded as the fraud "
     "signal on the charge (CD-5, ADR-003)",
     [(INTERP, '            "claims_authorization": bool(accessorial.asserts_prior_approval),\n',
       '            "claims_authorization": False,  # MUTANT\n')],
     f"{I}::test_an_accessorial_statement_never_creates_an_authorization"),

    ("a counterparty's 'that was the wrong load number' asks NOBODY — the correction is read and "
     "no human is told",
     [(DETECTORS, "    intents.extend(_reference_correction_exceptions(view, setup))\n",
       "    pass  # MUTANT\n")],
     f"{I}::test_a_counterparty_correction_rebinds_nothing_and_a_humans_correction_keeps_history"),

    ("a FAILED reading tells nobody — a timeout or malformed reply leaves the message silently "
     "unread",
     [(INTAKE, "        if reading is not None and reading.status == FAILED:\n",
       "        if False:  # MUTANT\n")],
     f"{I}::test_a_failed_reading_routes_to_a_human_and_corrupts_nothing"),

    ("HALF an invoice is extracted — a charge line the document does not support no longer makes "
     "the reading unusable",
     [(INTERP, "    if result.problems:\n        return result\n\n    extracted: dict[str, Any] = {",
       "    if False:  # MUTANT\n        return result\n\n    extracted: dict[str, Any] = {")],
     f"{I}::test_a_document_reading_is_all_or_nothing"),

    ("a value read off a document points at NOTHING — the evidence spans are not retained",
     [(INTAKE, "        if spans:\n            self.foundation.attach_field_spans(evidence_id, spans)\n",
       "        if False:  # MUTANT\n            self.foundation.attach_field_spans(evidence_id, spans)\n")],
     f"{I}::test_values_read_off_a_document_point_at_spans_of_the_retained_artifact"),

    # ------------------------------------------------------------------ what a model may not do to identity
    ("an INVENTED candidate id is accepted — an id the request never supplied becomes a candidate",
     [(INTERP,
       '        if candidate.candidate_id not in supplied:\n'
       '            refused.append("candidate_id_not_supplied")\n            continue\n',
       '        if False:  # MUTANT\n'
       '            refused.append("candidate_id_not_supplied")\n            continue\n')],
     INVENTED),

    ("ANOTHER BROKERAGE's canonical id is accepted — the same defect, seen from the tenant "
     "boundary ([C-1], CD-19)",
     [(INTERP,
       '        if candidate.candidate_id not in supplied:\n'
       '            refused.append("candidate_id_not_supplied")\n            continue\n',
       '        if False:  # MUTANT\n'
       '            refused.append("candidate_id_not_supplied")\n            continue\n')],
     f"{I}::test_the_same_load_number_at_two_brokerages_cannot_cross_bind"),

    ("a candidate with NO evidence in the record is accepted",
     [(INTERP,
       '        if found is None:\n            refused.append("evidence_not_in_content")\n'
       '            continue\n',
       '        if found is None:\n            found = (0, 0)  # MUTANT\n')],
     INVENTED),

    ("a single clearly-supported model candidate is BOUND — 'highest confidence wins' (GR-8)",
     [(INTAKE,
       '        source = f"model:{self.interpreter.gateway.provider}/{self.interpreter.gateway.model}"\n',
       '        if len(reading.candidates) == 1:  # MUTANT\n'
       '            chosen = reading.candidates[0]["candidate_id"]\n'
       '            self.foundation.bind_exact(observation_id, chosen)\n'
       '            return RecordOutcome(label, BOUND, observation_id=observation_id,\n'
       '                                 load_id=split_ref(chosen)[1])\n'
       '        source = f"model:{self.interpreter.gateway.provider}/{self.interpreter.gateway.model}"\n')],
     NEVER_BINDS),

    ("a model-proposed candidate is recorded as an EXACT match — a guess laundered into a "
     "LINKER_INFERRED claim M6 will confirm (R-P2)",
     [(FOUNDATION,
       "                match_method=MatchMethod.MODEL_INFER, candidate_count=max(len(distinct), 1),\n",
       "                match_method=MatchMethod.EXACT_ID, candidate_count=max(len(distinct), 1),\n")],
     NEVER_BINDS),

    # ------------------------------------------------------------------ the boundary itself
    ("a model is called WITHOUT a route — the gateway no longer checks that routing sent the work",
     [(GATEWAY, "        if route.task is not task or not route.model_needed:\n",
       "        if False:  # MUTANT\n")],
     f"{G}::test_a_model_is_never_called_without_a_route_that_says_one_is_needed"),

    ("a record someone already STRUCTURED is sent to a model anyway",
     [(INTERP,
       '        if "asserts" in payload:\n            return Route(task, False, "pre_structured")\n',
       '        if False:  # MUTANT\n            return Route(task, False, "pre_structured")\n')],
     f"{I}::test_a_record_someone_already_structured_never_reaches_a_model"),

    ("an EXACT link still asks a model — deterministic resolution no longer comes first",
     [(INTERP, '    if bound_exactly:\n        return Route(task, False, "exact_reference")\n',
       '    if False:  # MUTANT\n        return Route(task, False, "exact_reference")\n')],
     f"{I}::test_an_exact_reference_binds_without_asking_a_model"),

    ("a provider REJECTION is retried — retries are no longer only for transport or schema failure",
     [(GATEWAY,
       '    """The provider refused the request or the model refused the task. A retry would not '
       'help."""\n',
       '    """The provider refused the request or the model refused the task. A retry would not '
       'help."""\n\n    retryable = True  # MUTANT\n')],
     f"{G}::test_retries_are_bounded_and_only_for_transport_or_schema_failure"),

    ("the retry BOUND is lifted — a gateway may be built to attempt fifty times",
     [(GATEWAY, "        if max_attempts < 1 or max_attempts > 3:\n",
       "        if max_attempts < 1:  # MUTANT\n")],
     f"{G}::test_retries_are_bounded_and_only_for_transport_or_schema_failure"),

    ("the run BUDGET is not enforced — an exhausted budget still admits a call",
     [(LEDGER, "        if self.exhausted:\n            return False\n",
       "        if False:  # MUTANT\n            return False\n")],
     f"{G}::test_the_run_budget_stops_calls_and_counts_retries"),

    ("a recorded reading is IGNORED — every replay pays again",
     [(GATEWAY,
       "        recorded = self.recording.get(key) if self.recording is not None else None\n",
       "        recorded = None  # MUTANT\n")],
     f"{G}::test_a_recorded_reading_replays_without_any_provider"),

    ("a recording is replayed against a DIFFERENT PROMPT — the prompt version left the key",
     [(RECORDING, '        "schema_version": schema_version, "prompt_version": prompt_version,\n',
       '        "schema_version": schema_version,  # MUTANT\n')],
     f"{G}::test_a_recording_is_never_replayed_against_a_different_question"),

    ("a LIVE gateway is constructible by default — no explicit opt-in is needed to spend",
     [(OPENAI, "        if client is None and not allow_live:\n", "        if False:  # MUTANT\n")],
     f"{G}::test_a_live_gateway_cannot_be_constructed_without_the_explicit_opt_in"),

    ("the SDK retries BEHIND the gateway — uncounted, unbudgeted attempts",
     [(OPENAI, "max_retries=0,", "max_retries=2,")],
     f"{G}::test_the_sdk_client_is_built_without_hidden_retries_and_the_key_is_not_kept"),

    ("a provider's ERROR TEXT becomes the failure code — and with it, part of a key reaches "
     "telemetry",
     [(OPENAI,
       '    label = f"{type(exc).__name__}" + (f":{status}" if status else "") + '
       '(f":{code}" if code else "")\n',
       "    label = str(exc)  # MUTANT\n")],
     LEAK),

    ("key-shaped text is NOT redacted from the message handed back to the caller",
     [(GATEWAY, '    return _SECRET.sub("[redacted-key]", str(text))[:limit]\n',
       "    return str(text)[:limit]  # MUTANT\n")],
     LEAK),

    ("telemetry stores the MESSAGE — the rendered input is recorded where its digest belongs",
     [(GATEWAY,
       "            correlation_id=request.correlation_id, content_digest=digest, request_digest=key,\n",
       "            correlation_id=request.correlation_id, content_digest=call.rendered_input,"
       " request_digest=key,\n")],
     f"{G}::test_every_call_is_recorded_with_tokens_and_no_content"),

    ("the eval script spends on ONE switch — the environment opt-in is no longer required",
     [(EVAL_SCRIPT, '        if os.environ.get(LIVE_ENV) != "1":\n',
       "        if False:  # MUTANT\n")],
     f"{G}::test_only_the_eval_script_opts_in_to_live_inference_and_it_needs_two_switches"),

    ("a SECOND module in the inference boundary imports the provider SDK",
     [(LEDGER, APPEND, "\n\ndef _mutant_second_sdk_importer():\n    import openai  # MUTANT\n"
                       "    return openai\n")],
     SDK),

    ("the freight domain can BUILD its own live gateway — it imports the provider module instead "
     "of being handed a gateway",
     [(MODEL, APPEND,
       "\n\ndef _mutant_builds_a_gateway():\n"
       "    from ..inference.openai_responses import OpenAIResponsesGateway  # MUTANT\n"
       "    return OpenAIResponsesGateway\n")],
     SDK),

    ("a SECOND production module calls a gateway task — interpretation enters somewhere unreviewed",
     [(OUTSIDE, APPEND,
       "\n\ndef _mutant_asks_a_model(gateway, request):\n"
       "    return gateway.interpret_message(request)  # MUTANT\n")],
     f"{G}::test_only_the_freight_interpreter_calls_a_gateway_task"),

    ("the output vocabulary gains an AUTHORITY field — a model can now say a charge is approved",
     [(CONTRACTS, "    asserts_prior_approval: bool\n",
       "    asserts_prior_approval: bool\n    approved: bool  # MUTANT\n")],
     f"{G}::test_no_output_model_has_a_field_that_could_carry_authority"),

    ("the registry CLAIMS an independent review of P9-CP-2 that has not happened",
     [(REGISTRY,
       "        independent_review_report: null\n        independent_review_note: >-\n"
       "          NO INDEPENDENT REVIEW HAS BEEN PERFORMED. This checkpoint touches tier-1 "
       "surfaces\n          (CLAUDE.md sec 7): one ships-dark guard REPLACED",
       "        independent_review_report: docs/implementation/p9-de2-review.md\n"
       "        independent_review_note: >-\n"
       "          NO INDEPENDENT REVIEW HAS BEEN PERFORMED. This checkpoint touches tier-1 "
       "surfaces\n          (CLAUDE.md sec 7): one ships-dark guard REPLACED")],
     f"{D}::test_p9_is_recorded_in_progress_and_unreviewed_and_p10_is_still_blocked"),

    ("PRODUCTION code imports the eval corpus — and through it, runs the spine",
     [(OUTSIDE, APPEND,
       "\n\ndef _mutant_runs_the_corpus():\n    import freight_corpus.histories  # MUTANT\n")],
     f"{D}::test_nothing_outside_the_package_reaches_the_freight_domain_except_its_two_harnesses"),

    ("a THIRD script reaches the spine through the eval corpus without naming freight_domain — "
     "the indirect route the direct-import guard could not see",
     [(OTHER_SCRIPT, APPEND,
       "\n\ndef _mutant_third_harness():\n    from freight_corpus import raw  # MUTANT\n"
       "    return raw\n")],
     f"{D}::test_nothing_outside_the_package_reaches_the_freight_domain_except_its_two_harnesses"),
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


def test_the_p9_interpretation_mutation_battery_catches_every_mutant():
    """THE PYTEST-COLLECTED ENTRY POINT: `python -m pytest scripts/mutate_p9_interpretation.py`. Every
    mutant must be CAUGHT — guard GREEN un-mutated, RED under the reintroduced defect, GREEN again
    after a byte-for-byte in-memory restore — over a population floored so `== 0` cannot be vacuous.

    Not collected by a bare `pytest eval` (outside `testpaths`, not named `test_*.py`): a slow battery
    runs when it is named, on purpose."""
    assert len(CASES) >= 35, f"the interpretation battery carries only {len(CASES)} mutants"
    assert main() == 0, "the interpretation mutation battery did NOT report every mutant CAUGHT"


def main(only: str | None = None) -> int:
    """Run the battery. `only` narrows it to the mutants whose label contains that text — for
    iterating on one; the collected test above always runs every mutant."""
    cases = [c for c in CASES if only is None or only in c[0]]
    results = [(label, *_run_edits(edits, guard)) for label, edits, guard in cases]
    print("\n=========== P9 INTERPRETATION MUTATION BATTERY ===========")
    for label, verdict, detail in results:
        print(f"  [{verdict:11s}] {label}" + (f"\n               -> {detail}" if detail else ""))
    caught = sum(1 for _, verdict, _ in results if verdict == "CAUGHT")
    print(f"\n  {caught} of {len(results)} mutants CAUGHT")
    return 0 if caught == len(results) and results else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else None))
