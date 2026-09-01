#!/usr/bin/env python3
"""M10 mutation battery — a guard never seen to fail is a decoration (CLAUDE.md §6).

Each mutant reintroduces a specific real defect the Compensation machine exists to prevent — a
compensation from an unknown outcome, a caller flag deciding eligibility, a model-inferred invalidation,
an unresolved decision_ref, an ownerless or cross-tenant obligation, a dropped or zeroed exposure, a
float exposure, a seventh state, an expiry column, a cancellation transition, a timer that moves
COMPENSATION_FAILED, an auto-retry, a model approving, a wrong-commit-key or cross-tenant approval, a
bypassed pipeline or checkpoint, a reused or derived commit key, a completion without readback, a
completion while unknown, a brake M10 reaches for, a bulk grant, a replay that mints an effect, a
dropped tenant from the uniqueness index, a duplicate active compensation, a dropped transactional event,
a second RealityEstablished contract, a minted CorrectionInvalidatedAnEffect, and — the anti-vacuity
control — the machine relocated behind a re-export shim so every corpus-scanning negative assertion must
turn red, proving it was scanning something. Each names the guard that must turn RED under it. A mutant
that no test catches is a hole with a passing status; a mutant that does not reintroduce the real defect
proves nothing.

It mutates TEXT and shells out to pytest; it NEVER imports the compensation machine, and it NEVER uses
git to undo a mutation. Originals are held in memory and restored unconditionally; `__pycache__` is purged
around every run so a same-length restore cannot leave poisoned bytecode and a false green.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

M10 = "src/freight_recon/compensation.py"
MIG = "src/freight_recon/migrations/phase6_compensations.py"
SCHEMA = "src/freight_recon/schema.py"
T = "eval/tests/test_phase6_compensation.py"
SHADOW = "src/freight_recon/compensation_shadow.py"


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
    ("permit creation from UNKNOWN_OUTCOME — the M-33 guard is disabled and a compensation is created "
     "against an effect nobody can prove happened",
     [(M10, "        if original.state == ORIGINAL_UNKNOWN:",
       '        if original.state == "___NEVER___":  # MUTANT'),
      (M10, "        if original.state != ORIGINAL_VERIFIED:",
       "        if original.state not in (ORIGINAL_VERIFIED, ORIGINAL_UNKNOWN):  # MUTANT")],
     f"{T}::test_ac_mach_1002_cm_cannot_compensate_unknown"),

    ("permit creation from a FAILED original — the VERIFIED-only guard is widened, so a compensation is "
     "raised for an effect that provably did not happen (### M10-AQ-10)",
     [(M10, "        if original.state != ORIGINAL_VERIFIED:",
       '        if original.state not in (ORIGINAL_VERIFIED, "FAILED"):  # MUTANT')],
     f"{T}::test_ac_rec_001_other_six_original_states_create_no_compensation_and_no_variant"),

    ("read eligibility from a caller-controlled value instead of the ledger — the original's state is "
     "always read as VERIFIED, so the effect_grants row no longer decides (requirement 1)",
     [(M10,
       '            "SELECT grant_id, state, target_system, target_resource_id, target_operation, action_class "',
       "            \"SELECT grant_id, 'VERIFIED' AS state, target_system, target_resource_id, target_operation, action_class \"  # MUTANT")],
     f"{T}::test_ac_rec_001_cm1_reads_the_ledger_not_a_flag"),

    ("permit a MODEL_INFERRED invalidation — M1's resolver call is bypassed, so a human-decision event "
     "recorded by automation (ER-11) closes the correction (GR-8)",
     [(M10, "            resolve_decision_ref(self._conn, tenant=self._tenant, ref=ref, kind=kind)",
       "            ref  # MUTANT non-null only")],
     f"{T}::test_an_automation_emitted_human_decision_event_is_refused"),

    ("accept a decision_ref without resolving it — the invalidating resolution is skipped entirely, so a "
     "bare string that references nothing raises the compensation (K-1)",
     [(M10,
       '        self._require_resolving_decision_ref(decision_ref, decision_ref_kind, context="the invalidating")',
       "        pass  # MUTANT no invalidating decision_ref resolution")],
     f"{T}::test_the_invalidating_decision_ref_must_resolve"),

    ("drop the owner NOT NULL from creation — an ownerless Compensation becomes insertable (entity §16, "
     "I1, AC-SAFE-028)",
     [(MIG, "            owner_id TEXT NOT NULL,", "            owner_id TEXT,  -- MUTANT")],
     f"{T}::test_owner_required_from_creation_and_ownerless_is_impossible"),

    ("permit a cross-tenant owner — the tenant predicate on the named-human guard is widened to "
     "always-true ([C-1])",
     [(M10,
       '            "SELECT state FROM tenant_humans WHERE tenant = ? AND human_id = ?",',
       '            "SELECT state FROM tenant_humans WHERE (tenant = ? OR 1=1) AND human_id = ?",  # MUTANT')],
     f"{T}::test_cross_tenant_owner_fails_closed"),

    ("drop the exposure requirement — the exposure NOT NULL AND its typeof-integer CHECK are dropped, so "
     "a Compensation with no dollar amount at stake becomes insertable (entity §10/§42, K-4)",
     [(MIG, "            exposure_amount_minor INTEGER NOT NULL,",
       "            exposure_amount_minor INTEGER,  -- MUTANT"),
      (MIG, "            CHECK (typeof(exposure_amount_minor) = 'integer'),",
       "            -- MUTANT dropped exposure typeof CHECK")],
     f"{T}::test_db_exposure_columns_are_not_null"),

    ("accept a float exposure — the canonical-Money guard coerces a float instead of refusing it, so "
     "2850.00 and 2850.0 become the same insertable money (K-4)",
     [(M10, "    if isinstance(value, Money):\n        return value\n    raise MalformedCompensation(",
       '    if isinstance(value, Money):\n        return value\n    if isinstance(value, float):\n'
       '        return Money(int(value), "GBP")  # MUTANT\n    raise MalformedCompensation(')],
     f"{T}::test_a_float_exposure_is_refused"),

    ("zero the exposure on COMPENSATION_FAILED — the identity trigger stops protecting the exposure and "
     "CM-4f writes it to 0, the exact forgetting the loud states exist to prevent (entity §42)",
     [(MIG,
       "        BEFORE UPDATE OF tenant, compensation_id, original_effect_id, commit_key, owner_id,\n"
       "                         exposure_amount_minor, exposure_currency, reason, created_at",
       "        BEFORE UPDATE OF tenant, compensation_id, original_effect_id, commit_key, owner_id,\n"
       "                         reason, created_at  -- MUTANT dropped exposure protection"),
      (M10,
       '                comp, "CM-4f", CmState.COMPENSATION_FAILED, event_name="CompensationFailed",\n'
       '                payload={"exposure": comp.exposure.canonical()}, consequential=False, pins=None,\n'
       '                actor_type="system", actor_id=actor_id, writes="", write_args=(),',
       '                comp, "CM-4f", CmState.COMPENSATION_FAILED, event_name="CompensationFailed",\n'
       '                payload={"exposure": comp.exposure.canonical()}, consequential=False, pins=None,\n'
       '                actor_type="system", actor_id=actor_id, writes="exposure_amount_minor = 0", write_args=(),  # MUTANT')],
     f"{T}::test_exposure_survives_into_compensation_failed_and_not_possible"),

    ("add a seventh lifecycle state — CANCELLED joins the frozen six, and entity §25/§26/machine §14 say "
     "none exists (registry §4)",
     [(MIG,
       '    "REQUIRED", "APPROVED", "EXECUTING", "COMPLETED", "COMPENSATION_FAILED", "NOT_POSSIBLE",',
       '    "REQUIRED", "APPROVED", "EXECUTING", "COMPLETED", "COMPENSATION_FAILED", "NOT_POSSIBLE", "CANCELLED",  # MUTANT')],
     f"{T}::test_the_six_canonical_states_and_no_seventh"),

    ("add an expiry column — an exposure that ages out, and entity §26 says an exposure NEVER expires",
     [(MIG, "            reality_decision_ref TEXT,",
       "            reality_decision_ref TEXT,\n            expires_at TEXT,  -- MUTANT")],
     f"{T}::test_no_expiry_column"),

    ("add a cancellation transition — a tenth CM-* row for cancelling a compensation, and §14 has exactly "
     "nine (a cancelled compensation is money you decided to stop tracking, entity §25)",
     [(M10, "        illegal=True,\n    ),\n)",
       "        illegal=True,\n    ),\n    TransitionRow(id=\"CM-CANCEL\", from_states=(CmState.REQUIRED,),\n"
       "                 to_state=None, triggers=(), trigger_types=(\"H\",), kind=RowKind.PRODUCER),  # MUTANT\n)")],
     f"{T}::test_ac_mach_000_transition_table_is_the_nine_canonical_rows"),

    ("let a timer move COMPENSATION_FAILED — CM-5x is made a legal producer row, so TimerFired acquires a "
     "legal transition (machine §15/§20, GR-6, AC-REC-004)",
     [(M10,
       '        triggers=(Trigger.TIMER_FIRED,), trigger_types=("T",), kind=RowKind.NON_PRODUCING,\n'
       "        illegal=True,",
       '        triggers=(Trigger.TIMER_FIRED,), trigger_types=("T",), kind=RowKind.PRODUCER,\n'
       "        illegal=False,  # MUTANT")],
     f"{T}::test_ac_mach_000_timer_fired_has_no_legal_row_at_any_state"),

    ("add an automatic retry from COMPENSATION_FAILED — a retry method beside the human resolution, and "
     "machine §20 says a failed compensation is NOT auto-retried; a human decides",
     [(M10, "    def handle_timer_fired(",
       "    def retry_failed(self, compensation_id: str):  # MUTANT auto-retry\n"
       "        return self.observe_pipeline(compensation_id)\n\n    def handle_timer_fired(")],
     f"{T}::test_ac_rec_004_compensation_failed_never_auto_resolves"),

    ("allow a model to approve — the CM-2 authenticated-human guard is disabled, so a model approves the "
     "reversal at any confidence (ADR-003, GR-8)",
     [(M10,
       "        if str(actor_kind).upper() != HUMAN:\n"
       "            self._refuse_illegal(comp.compensation_id, Trigger.HUMAN_APPROVED, actor_id=actor_id)",
       "        if False and str(actor_kind).upper() != HUMAN:  # MUTANT\n"
       "            self._refuse_illegal(comp.compensation_id, Trigger.HUMAN_APPROVED, actor_id=actor_id)")],
     f"{T}::test_a_model_cannot_approve_a_compensation"),

    ("accept a wrong-commit-key approval — the confused-deputy check is disabled, so an approval for one "
     "effect authorises another (ADR-005, entity §22)",
     [(M10, '        if row["commit_key"] != commit_key:',
       '        if False and row["commit_key"] != commit_key:  # MUTANT')],
     f"{T}::test_a_stale_or_wrong_commit_key_approval_is_refused"),

    ("accept a cross-tenant approval — the tenant-consistent approval foreign key is dropped, so the "
     "binding is no longer tenant-scoped ([C-1], entity §18)",
     [(MIG, "            FOREIGN KEY (tenant, approval_id) REFERENCES approvals (tenant, approval_id),",
       "            -- MUTANT dropped approval FK")],
     f"{T}::test_readiness_is_clean_on_a_fresh_canonical_database"),

    ("bypass the M2 pipeline — the EXECUTING-requires-a-bound-pipeline CHECK is widened to always-true, so "
     "a compensation executes with no gated attempt (entity §16)",
     [(MIG, "            CHECK (state <> 'EXECUTING' OR pipeline_instance_id IS NOT NULL),",
       "            CHECK (1=1 OR state <> 'EXECUTING' OR pipeline_instance_id IS NOT NULL),  -- MUTANT")],
     f"{T}::test_executing_requires_a_bound_pipeline_instance_id"),

    ("bypass the checkpoint/readback — CM-4 completes regardless of the pipeline state, so a compensation "
     "COMPLETES before the credit note is verified (CM-4, ADR-006)",
     [(M10, "        if pipeline_state in POST_READBACK_PIPELINE_STATES:",
       "        if True or pipeline_state in POST_READBACK_PIPELINE_STATES:  # MUTANT")],
     f"{T}::test_ac_rec_005_and_ac_race_013_crash_and_timeout_reach_compensation_failed"),

    ("reuse the original effect's commit key — the compensation stores the original's commit key, so the "
     "compensating effect's identity is a function of the thing it undoes (entity §9/§17)",
     [(M10, "        commit_key = effect.key()", '        commit_key = "ck-orig-" + original_effect_id  # MUTANT')],
     f"{T}::test_the_compensating_effect_has_its_own_commit_key"),

    ("derive the commit key from the original — the canonical occurrence is the original grant id, so two "
     "different compensations of one effect collide on one key (entity §17, ADR-009)",
     [(M10, '        occurrence = CanonicalOccurrence(entity="Compensation", occurrence_id=compensation_id)',
       '        occurrence = CanonicalOccurrence(entity="Compensation", occurrence_id=original.grant_id)  # MUTANT')],
     f"{T}::test_the_compensating_effect_has_its_own_commit_key"),

    ("complete on adapter success without readback — EXECUTED joins the post-readback set, so 'the API "
     "returned 200' completes a compensation (CM-4, ADR-006)",
     [(M10, 'POST_READBACK_PIPELINE_STATES: frozenset[str] = frozenset(\n    ("VERIFIED", "RECORDED", "PROJECTED", "CLOSED"))',
       'POST_READBACK_PIPELINE_STATES: frozenset[str] = frozenset(\n    ("VERIFIED", "RECORDED", "PROJECTED", "CLOSED", "EXECUTED"))  # MUTANT')],
     f"{T}::test_post_readback_pipeline_states_exclude_pre_readback"),

    ("complete while the M3 outcome is unknown — NEEDS_VERIFICATION joins the post-readback set, so a "
     "timed-out compensating write COMPLETES instead of failing loud (CM-4f, AC-RACE-013)",
     [(M10, 'POST_READBACK_PIPELINE_STATES: frozenset[str] = frozenset(\n    ("VERIFIED", "RECORDED", "PROJECTED", "CLOSED"))',
       'POST_READBACK_PIPELINE_STATES: frozenset[str] = frozenset(\n    ("VERIFIED", "RECORDED", "PROJECTED", "CLOSED", "NEEDS_VERIFICATION"))  # MUTANT')],
     f"{T}::test_ac_rec_005_and_ac_race_013_crash_and_timeout_reach_compensation_failed"),

    ("let M10 reach for the brake — it imports BrakeStore, crossing the boundary that the brake is the "
     "checkpoint's, and M10 engages/narrows none (spec §21.5, CLAUDE.md rule 17)",
     [(M10, "from .commit_key import (", "from .brake import BrakeStore  # MUTANT\nfrom .commit_key import (")],
     f"{T}::test_m10_engages_no_brake_and_mints_no_gate"),

    ("issue one bulk key for N effects — every compensation in a tenant shares one commit key, so N "
     "reversals become one bulk reservation (AC-REC-003, entity §43)",
     [(M10, "        commit_key = effect.key()", '        commit_key = "bulk-" + self._tenant  # MUTANT')],
     f"{T}::test_ac_rec_003_no_bulk_undo_n_individually_gated"),

    ("emit an effect during replay — the rebuild reports a produced external effect, and GR-11/ER-2 say "
     "replay produces zero effects",
     [(M10, "        return ReconstructedCompensation(compensation_id=compensation_id, state=state)",
       "        return ReconstructedCompensation(compensation_id=compensation_id, state=state, external_effects=1)  # MUTANT")],
     f"{T}::test_replay_reconstructs_state_only_and_mints_nothing"),

    ("drop tenant from the one-active-per-effect index — one invalidated effect coalesces across tenants "
     "([C-1], entity §17)",
     [(MIG, "        \"ON compensations (tenant, original_effect_id) WHERE state != 'NOT_POSSIBLE'\",",
       "        \"ON compensations (original_effect_id) WHERE state != 'NOT_POSSIBLE'\",  # MUTANT")],
     f"{T}::test_the_uniqueness_predicate_excludes_not_possible_exactly_as_written"),

    ("permit a duplicate active compensation — the one-active index loses UNIQUE, so a second active "
     "compensation for one invalidated effect is insertable (entity §17)",
     [(MIG, '        "CREATE UNIQUE INDEX ix_compensations_one_active_per_effect "',
       '        "CREATE INDEX ix_compensations_one_active_per_effect "  # MUTANT')],
     f"{T}::test_one_active_compensation_per_invalidated_effect"),

    ("drop the transactional event write — CM-1 creates the row but emits no CompensationRequired, a state "
     "without its event (GR-2)",
     [(M10,
       "            self._outbox().emit(envelope)\n            conn.commit()\n        except BaseException:\n"
       "            if conn.in_transaction:\n                conn.rollback()\n            raise\n"
       "        return TransitionResult(\n            transition_id=\"CM-1\", compensation=created, from_state=None, to_state=CmState.REQUIRED,",
       "            pass  # MUTANT no event\n            conn.commit()\n        except BaseException:\n"
       "            if conn.in_transaction:\n                conn.rollback()\n            raise\n"
       "        return TransitionResult(\n            transition_id=\"CM-1\", compensation=created, from_state=None, to_state=CmState.REQUIRED,")],
     f"{T}::test_state_and_event_co_commit"),

    ("mint a second RealityEstablished under F10 — CM-5 emits on the compensation aggregate, an F10-local "
     "RealityEstablished the registry does not carry (rule 17, ### M10-AQ-5)",
     [(M10, 'REALITY_AGGREGATE_TYPE = "effect_grant"', 'REALITY_AGGREGATE_TYPE = "compensation"  # MUTANT')],
     f"{T}::test_cm5_emits_the_shared_f3_realityestablished_with_subject_compensation"),

    ("mint CorrectionInvalidatedAnEffect — CM-1 emits the unregistered name entity §32 lists, and it is "
     "absent from all 118 contracts (### M10-AQ-1)",
     [(M10, '                event_name="CompensationRequired", transition_id="CM-1", compensation=created,',
       '                event_name="CorrectionInvalidatedAnEffect", transition_id="CM-1", compensation=created,  # MUTANT')],
     f"{T}::test_ac_mach_1001_cm_required_from_verified_effect"),
]

# ### THE ANTI-VACUITY CONTROL (mutation 33). The machine is relocated behind a re-export shim: its real
# content moves to a shadow module and `compensation.py` becomes `from .compensation_shadow import *`.
# Imports still resolve, so a scan that only imports the machine passes — but every corpus-scanning
# negative assertion that reads `compensation.py`'s SOURCE now reads the tiny shim and its population
# proof (`assert found`) turns RED, proving it was scanning real content.
SHIM_GUARD = f"{T}::test_no_unregistered_compensation_event_name_in_the_machine"
SHIM_TEXT = ('"""M10 relocated behind a re-export shim (MUTANT anti-vacuity control)."""\n'
             "from .compensation_shadow import *  # noqa: F401,F403\n")


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


def _run_shim() -> tuple[str, str]:
    """The re-export-shim mutation. Restores byte-for-byte from memory; never git."""
    m10_path = ROOT / M10
    shadow_path = ROOT / SHADOW
    original = m10_path.read_bytes()
    if shadow_path.exists():
        return "SETUP-FAIL", "compensation_shadow.py already exists"
    purge_pycache()
    if not run_guard(SHIM_GUARD):
        return "SETUP-FAIL", "guard already RED before mutation"
    try:
        shadow_path.write_bytes(original)              # the real content, relocated
        m10_path.write_text(SHIM_TEXT, encoding="utf-8")  # compensation.py is now a shim
        purge_pycache()
        caught = not run_guard(SHIM_GUARD)
    finally:
        m10_path.write_bytes(original)
        if shadow_path.exists():
            shadow_path.unlink()
        purge_pycache()
    if m10_path.read_bytes() != original:
        return "RESTORE-RED", "byte-for-byte restore FAILED for compensation.py"
    if shadow_path.exists():
        return "RESTORE-RED", "the shadow module was not removed"
    if not run_guard(SHIM_GUARD):
        return "RESTORE-RED", "guard red after restore - investigate"
    return ("CAUGHT" if caught else "MISS"), ""


def main() -> int:
    results = [(label, *_run_edits(edits, guard)) for label, edits, guard in CASES]
    results.append(("the machine is relocated behind a re-export shim — every corpus-scanning negative "
                    "assertion must turn red, proving it was scanning real content (anti-vacuity control)",
                    *_run_shim()))
    print("\n=========== P6 M10 COMPENSATION MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    print("  NOTE: written by the session that implemented the unit - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
