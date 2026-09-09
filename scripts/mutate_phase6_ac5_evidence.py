#!/usr/bin/env python3
"""P6-AC-5 evidence-closure mutation battery — the four NEW behavioural families.

Eleven `(machine, assertion)` cells of `foundational-machine-acceptance.md`'s per-machine mandatory
assertions had no evidence. They are now discharged by real behaviour tests, and a behaviour test
nobody has seen fail is a behaviour test nobody should believe. This battery removes the behaviour
each new test protects and requires the test to go RED for it.

### THE FAMILIES, AND WHAT BREAKING EACH ONE LOOKS LIKE.

  * APPEND-ONLY HISTORY (assertion 7; M3, M4) — defang the triggers that refuse an UPDATE or a
    DELETE on the event and closure rows. The history becomes rewritable and the probes must notice.
  * INBOX IDEMPOTENCY (assertion 4; M10, M11) — remove the dedup inbox's duplicate branch, so a
    redelivery is APPLIED a second time instead of being a no-op.
  * TERMINAL REFUSAL (assertion 5; M11, M12, M13) — widen a terminal state back into a transition's
    from-set (or defang the ACTIVE check), so a terminal aggregate moves again.
  * CRASH RECOVERY (assertion 8; M5, M11, M12, M13) — COMMIT THE ROW BEFORE EMITTING ITS EVENT. This
    is the real defect the tests exist to catch: the transaction is no longer atomic, so an
    interrupted transition leaves the row moved and its event missing. For M13 that mutant is a brake
    a crash can clear.

Originals are held in memory and restored unconditionally and byte-for-byte; `__pycache__` is purged
around every run; git is never used to undo a mutation (CLAUDE.md §6). An anti-vacuity control — an
unmutated guard that must stay GREEN — makes the count a measurement rather than an assertion.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

TRANSPORT = "src/freight_recon/migrations/phase5_event_transport.py"
APPROVALS_MIG = "src/freight_recon/migrations/phase6_approvals.py"
INBOX = "src/freight_recon/event_inbox.py"
OBSERVATION = "src/freight_recon/observation.py"
POLICY = "src/freight_recon/policy.py"
RULE = "src/freight_recon/rule.py"
BRAKE = "src/freight_recon/brake.py"

T_EF = "eval/tests/test_phase6_external_effect.py"
T_AP = "eval/tests/test_phase6_approval.py"
T_OB = "eval/tests/test_phase6_observation.py"
T_CM = "eval/tests/test_phase6_compensation.py"
T_PO = "eval/tests/test_phase6_policy.py"
T_RU = "eval/tests/test_phase6_rule.py"
T_BR = "eval/tests/test_phase6_brake.py"

_SENTINEL = "MUTANT"

# (label, [(rel_path, old_anchor, new_text), ...], guard_nodeid). Each anchor must appear EXACTLY
# once. Every new_text embeds the sentinel so a stranded mutation is detectable.
CASES = [
    # ---------------------------------------------------- assertion 7: append-only history
    ("M3/A7 the outbox stops refusing a DELETE of recorded history",
     [(TRANSPORT,
       "        BEFORE DELETE ON event_outbox\n        BEGIN SELECT RAISE(ABORT,",
       "        BEFORE DELETE ON event_outbox\n        BEGIN SELECT 1; END; -- MUTANT\n"
       "        SELECT RAISE(ABORT,")],
     f"{T_EF}::test_m3_a7_the_recorded_grant_history_is_append_only"),

    ("M3/A7 the outbox envelope stops being immutable",
     [(TRANSPORT,
       'BEFORE UPDATE OF {", ".join(_OUTBOX_IMMUTABLE)} ON event_outbox',
       'BEFORE UPDATE OF published_at ON event_outbox  -- MUTANT')],
     f"{T_EF}::test_m3_a7_the_recorded_grant_history_is_append_only"),

    ("M4/A7 a consumed approval stops being final at the database",
     [(APPROVALS_MIG,
       "        BEFORE UPDATE ON approvals\n        WHEN OLD.state IN ({_TERMINAL_SQL})",
       "        BEFORE UPDATE ON approvals\n        WHEN OLD.state IN ('__never__')  -- MUTANT")],
     f"{T_AP}::test_m4_a7_a_consumed_approval_and_its_history_are_append_only"),

    ("M4/A7 the approval identity stops being immutable",
     [(APPROVALS_MIG,
       "        BEFORE UPDATE OF tenant, approval_id, commit_key, action_class, gate_decision,",
       "        BEFORE UPDATE OF tenant, approval_id,  -- MUTANT dropped the identity columns")],
     f"{T_AP}::test_m4_a7_a_consumed_approval_and_its_history_are_append_only"),

    ("M4/A7 a closed approval becomes deletable",
     [(APPROVALS_MIG,
       "        BEFORE DELETE ON approvals\n        BEGIN SELECT RAISE(ABORT,",
       "        BEFORE DELETE ON approvals\n        BEGIN SELECT 1; END; -- MUTANT\n"
       "        SELECT RAISE(ABORT,")],
     f"{T_AP}::test_m4_a7_a_consumed_approval_and_its_history_are_append_only"),

    # ---------------------------------------------------- assertion 4: the inbox key
    ("M10/A4 the dedup inbox stops recognising a redelivery",
     [(INBOX,
       "                return ConsumeResult(\n"
       "                    outcome=ConsumeOutcome.DUPLICATE_NOOP, event_id=event.event_id,",
       "                return ConsumeResult(  # MUTANT\n"
       "                    outcome=ConsumeOutcome.APPLIED, event_id=event.event_id,")],
     f"{T_CM}::test_m10_a4_a_redelivered_compensation_event_is_a_no_op_on_the_inbox_key"),

    ("M11/A4 the dedup inbox stops recognising a redelivery",
     [(INBOX,
       "                return ConsumeResult(\n"
       "                    outcome=ConsumeOutcome.DUPLICATE_NOOP, event_id=event.event_id,",
       "                return ConsumeResult(  # MUTANT\n"
       "                    outcome=ConsumeOutcome.APPLIED, event_id=event.event_id,")],
     f"{T_PO}::test_m11_a4_a_redelivered_policy_event_is_a_no_op_on_the_inbox_key"),

    # ---------------------------------------------------- assertion 5: terminal refusal
    ("M11/A5 a REVOKED policy becomes revocable again",
     [(POLICY,
       '        id="PO-6", from_states=(PolicyState.ACTIVE,), to_state=PolicyState.REVOKED,',
       '        id="PO-6", from_states=(PolicyState.ACTIVE, PolicyState.REVOKED),  # MUTANT\n'
       '        to_state=PolicyState.REVOKED,')],
     f"{T_PO}::test_m11_a5_a_terminal_policy_refuses_every_trigger_in_the_vocabulary"),

    ("M12/A5 a REVOKED rule becomes revocable again",
     [(RULE,
       '        id="RU-7", from_states=(RuleState.ACTIVE,), to_state=RuleState.REVOKED,',
       '        id="RU-7", from_states=(RuleState.ACTIVE, RuleState.REVOKED),  # MUTANT\n'
       '        to_state=RuleState.REVOKED,')],
     f"{T_RU}::test_m12_a5_a_terminal_rule_refuses_every_trigger_in_the_vocabulary"),

    ("M13/A5 a RELEASED brake stops refusing lifecycle transitions",
     [(BRAKE,
       '        if row["state"] != "ACTIVE":\n'
       '            raise BrakeError(f"brake {brake_id!r} is {row[\'state\']}; '
       'only ACTIVE brakes transition")',
       '        if False:  # MUTANT\n'
       '            raise BrakeError(f"brake {brake_id!r} is {row[\'state\']}; '
       'only ACTIVE brakes transition")')],
     f"{T_BR}::test_m13_a5_a_released_brake_refuses_every_lifecycle_transition"),

    # ---------------------------------------------------- assertion 8: crash recovery (GR-2)
    ("M5/A8 the observation row commits BEFORE its event is durable",
     [(OBSERVATION,
       "            self._outbox().emit(envelope)\n            conn.commit()\n"
       "        except BaseException:\n            conn.rollback()\n            raise\n"
       "        return TransitionResult(\n            transition_id=row.id, observation=after,",
       "            conn.commit()  # MUTANT: the row is durable before the event exists\n"
       "            self._outbox().emit(envelope)\n"
       "        except BaseException:\n            conn.rollback()\n            raise\n"
       "        return TransitionResult(\n            transition_id=row.id, observation=after,")],
     f"{T_OB}::test_m5_a8_a_crash_during_a_transition_leaves_the_canonical_state"),

    ("M11/A8 the policy row commits BEFORE its event is durable",
     [(POLICY,
       "            self._outbox().emit(main)\n            event_ids = [main.event_id]",
       "            conn.commit()  # MUTANT: the row is durable before the event exists\n"
       "            self._outbox().emit(main)\n            event_ids = [main.event_id]")],
     f"{T_PO}::test_m11_a8_a_crash_during_a_transition_leaves_the_canonical_state"),

    ("M12/A8 the rule row commits BEFORE its event is durable",
     [(RULE,
       "            after = self.require(comp.rule_id)\n"
       "            envelope = self._rule_envelope(",
       "            after = self.require(comp.rule_id)\n"
       "            conn.commit()  # MUTANT: the row is durable before the event exists\n"
       "            envelope = self._rule_envelope(")],
     f"{T_RU}::test_m12_a8_a_crash_during_a_transition_leaves_the_canonical_state"),

    # ### THE ONE THAT MATTERS MOST: a brake a crash can clear.
    ("M13/A8 the brake release commits BEFORE BrakeReleased is durable",
     [(BRAKE,
       '            self._emit_f13(\n                tenant=bound, event_name="BrakeReleased", '
       'transition_id="BR-4",',
       '            self._conn.commit()  # MUTANT: the release is durable before its event exists\n'
       '            self._emit_f13(\n                tenant=bound, event_name="BrakeReleased", '
       'transition_id="BR-4",')],
     f"{T_BR}::test_m13_a8_a_crash_during_release_leaves_the_brake_engaged"),
]

# Anti-vacuity control: NOT mutated; a representative guard must be GREEN.
CONTROL_GUARD = (
    "eval/tests/test_phase6_anchor_traceability.py::"
    "test_the_unevidenced_set_is_empty_and_may_never_refill")


def purge_pycache() -> None:
    for d in ROOT.rglob("__pycache__"):
        if ".venv" not in d.parts:
            shutil.rmtree(d, ignore_errors=True)


def assert_pristine() -> None:
    targets = sorted({rel for _, edits, _ in CASES for rel, _o, _n in edits})
    poisoned = [rel for rel in targets if _SENTINEL in (ROOT / rel).read_text(encoding="utf-8")]
    if poisoned:
        print(f"### REFUSING TO MEASURE: mutation residue in {poisoned} — restore first",
              file=sys.stderr)
        raise SystemExit(2)


def run_guard(nodeid: str) -> bool:
    r = subprocess.run([PY, "-m", "pytest", nodeid, "-q", "-p", "no:cacheprovider"],
                       cwd=ROOT, capture_output=True, text=True)
    return r.returncode == 0


def _run_edits(edits, guard) -> tuple[str, str]:
    originals: dict[Path, bytes] = {}
    for rel, _old, _new in edits:
        path = ROOT / rel
        if not path.exists():
            return "SETUP-FAIL", f"{rel} does not exist"
        originals.setdefault(path, path.read_bytes())
    for rel, old, _new in edits:
        text = (ROOT / rel).read_text(encoding="utf-8")
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
        return "RESTORE-RED", "guard red after restore — investigate"
    return ("CAUGHT" if caught else "MISS"), ""


def _baseline_control() -> str:
    purge_pycache()
    return "GREEN" if run_guard(CONTROL_GUARD) else "RED"


def main() -> int:
    assert_pristine()
    results = [(label, *_run_edits(edits, guard)) for label, edits, guard in CASES]
    control = _baseline_control()

    for label, verdict, detail in results:
        mark = "PASS" if verdict == "CAUGHT" else "### MISS ###"
        line = f"{mark}  {label}"
        if detail:
            line += f"  [{verdict}: {detail}]"
        print(line)
    print(f"anti-vacuity control (unmutated guard stays GREEN): {control}")

    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    total = len(results)
    escaped = total - caught
    control_ok = control == "GREEN"
    print(f"{caught} mutations caught, {escaped} escaped")
    if caught == total and control_ok:
        return 0
    if not control_ok:
        print("### MISS ### the anti-vacuity control did not stay GREEN — the battery is vacuous",
              file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
