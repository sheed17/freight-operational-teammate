#!/usr/bin/env python3
"""M7 mutation battery — a guard never seen to fail is a decoration (CLAUDE.md §6).

Each mutant reintroduces a specific real defect the Conflict machine exists to prevent — an AutoResolve
that closes on nothing, a timer that resolves, a confidence threshold or a recency heuristic that
picks a winner, an unregistered rule that resolves, a resolved conflict with no basis, an ownerless
conflict, a raise and a freeze that split into two commits, a partial unique index that lets two open
conflicts fit one field, a second detection that raises a new conflict instead of attaching, a
ConflictPartyAttached that is never emitted (a stale party set on replay), a party provenance that gets
strengthened, a dropped tenant predicate that coalesces across tenants, a CF-6 resolution attributed by
position instead of target state, and an open conflict that stops blocking — and names the guard that
must turn RED under it. A mutant that no test catches is a hole with a passing status; a mutant that
does not reintroduce the real defect proves nothing.

It mutates TEXT and shells out to pytest; it NEVER imports the conflict machine, and it NEVER uses git
to undo a mutation. Originals are held in memory and restored unconditionally; `__pycache__` is purged
around every run so a same-length restore cannot leave poisoned bytecode and a false green.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable

M7 = "src/freight_recon/conflict.py"
MIG = "src/freight_recon/migrations/phase6_conflicts.py"
T = "eval/tests/test_phase6_conflict.py"


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
    ("AutoResolve is accepted — the neither-basis branch SILENTLY RESOLVES the conflict to "
     "RESOLVED_BY_RULE on a synthesized `auto:silent` basis instead of refusing, so a conflict closes "
     "on nothing (ADR-007 §5.3, machine §15)",
     [(M7,
       "        if not has_rule and not has_decision:\n            self._refuse_illegal(conflict.conflict_id, Trigger.AUTO_RESOLVE, actor_id=actor_id)",
       "        if not has_rule and not has_decision:\n            return self._advance(conflict, \"CF-3\", CfState.RESOLVED_BY_RULE, event_name=\"ConflictResolved\", payload={\"rule_id\": \"auto:silent\"}, event_producer=\"CF-3\", actor_type=\"system\", actor_id=actor_id, writes=\"rule_id = ?\", write_args=(\"auto:silent\",), correlation_id=correlation_id, causation_id=causation_id, trace_id=trace_id, event_id=event_id)  # MUTANT AutoResolve\n            self._refuse_illegal(conflict.conflict_id, Trigger.AUTO_RESOLVE, actor_id=actor_id)")],
     f"{T}::test_auto_resolve_is_illegal"),

    ("a TimerFired transition to a resolved state is allowed — CF-5 is widened so a timer can close a "
     "conflict (machine §15: a clock knows nothing about freight)",
     [(M7,
       "        if trigger.timer_kind != TIMER_KIND_AGE_THRESHOLD:",
       "        if False and trigger.timer_kind != TIMER_KIND_AGE_THRESHOLD:  # MUTANT")],
     f"{T}::test_a_timer_transition_to_resolved_is_illegal"),

    ("a confidence threshold resolves — a `confidence:` pseudo-rule is accepted off the registry, the "
     "defeat ADR-007 §8 names by hand (GR-8: confidence gates nothing)",
     [(M7,
       "        if rule_id not in self._registered_rules:",
       "        if rule_id not in self._registered_rules and not rule_id.startswith('confidence:'):  # MUTANT")],
     f"{T}::test_confidence_never_resolves_at_1_0"),

    ("the newest source wins — a `recency:` pseudo-rule is accepted off the registry, recency as an "
     "ambient resolution default (ADR-007 §5.3)",
     [(M7,
       "        if rule_id not in self._registered_rules:",
       "        if rule_id not in self._registered_rules and not rule_id.startswith('recency:'):  # MUTANT")],
     f"{T}::test_recency_never_resolves"),

    ("an unregistered rule resolves — the CF-3 registry lookup is dropped, so any rule id closes a "
     "conflict (ADR-007 §5.3)",
     [(M7,
       "        if rule_id not in self._registered_rules:",
       "        if False and rule_id not in self._registered_rules:  # MUTANT")],
     f"{T}::test_cf_rule_resolution_requires_registered_rule_id"),

    ("a resolved conflict with NO basis is insertable — the entity §16 rule_id CHECK is widened to "
     "always-true, so a RESOLVED_BY_RULE with no rule_id fits",
     [(MIG,
       "            CHECK (state <> 'RESOLVED_BY_RULE' OR rule_id IS NOT NULL),",
       "            CHECK (1 = 1 OR state <> 'RESOLVED_BY_RULE' OR rule_id IS NOT NULL),  -- MUTANT")],
     f"{T}::test_db_refuses_a_resolved_conflict_with_no_basis"),

    ("an ownerless conflict is insertable — the owner_id NOT NULL is dropped, so a Conflict with no "
     "accountable human fits (entity §37)",
     [(MIG,
       "            owner_id TEXT NOT NULL,",
       "            owner_id TEXT,  -- MUTANT")],
     f"{T}::test_ownerless_conflict_impossible"),

    ("the raise and the freeze split into two commits — the conflict row is committed before the "
     "parties and the event, so a mid-raise failure leaves a frozen field with no history (entity §15)",
     [(M7,
       "            for seq, party in enumerate(party_list, start=1):",
       "            conn.commit()  # MUTANT split the atomic raise\n            for seq, party in enumerate(party_list, start=1):")],
     f"{T}::test_raise_and_freeze_are_one_transaction"),

    ("the one-open-conflict-per-field index loses UNIQUE — two OPEN conflicts for one field become "
     "insertable (entity §17)",
     [(MIG,
       '        "CREATE UNIQUE INDEX ix_conflicts_one_open_per_field "',
       '        "CREATE INDEX ix_conflicts_one_open_per_field "')],
     f"{T}::test_partial_unique_index_refuses_two_open_conflicts_per_field"),

    ("the partial index loses its WHERE clause — every conflict (resolved history included) competes "
     "for uniqueness, and the coalescing that attaches a second detection breaks (entity §17/§24)",
     [(MIG,
       '        "ON conflicts (tenant, entity_ref, field) WHERE state IN (%(open)s)" % {"open": _OPEN_SQL},',
       '        "ON conflicts (tenant, entity_ref, field)",  # MUTANT dropped WHERE')],
     f"{T}::test_new_evidence_after_resolution_raises_a_new_conflict"),

    ("a second detection is not coalesced into an attach — the open-conflict lookup returns None, so "
     "the redetection re-raises instead of attaching its party (entity §33)",
     [(M7,
       "                existing = self.open_conflict_for(entity, field_name)\n                if existing is None:",
       "                existing = None  # MUTANT\n                if existing is None:")],
     f"{T}::test_second_detection_attaches_rather_than_raising_a_second_conflict"),

    ("ConflictPartyAttached is never emitted — the attach commits the party row but emits no event, so "
     "a full-history rebuild reproduces a STALE party set (F7, AC-EVT-008)",
     [(M7,
       "            self._outbox().emit(envelope)\n            conn.commit()\n        except BaseException:\n"
       "            if conn.in_transaction:\n                conn.rollback()\n            raise\n"
       "        return TransitionResult(\n            transition_id=\"CF-7\", conflict=after,",
       "            conn.commit()  # MUTANT no attach event\n        except BaseException:\n"
       "            if conn.in_transaction:\n                conn.rollback()\n            raise\n"
       "        return TransitionResult(\n            transition_id=\"CF-7\", conflict=after,")],
     f"{T}::test_conflict_party_attached_rebuilds_the_full_party_set"),

    ("an attached party's provenance is strengthened — a MODEL_INFERRED party is stored as RECONCILED, "
     "a laundered guess (ER-14, R-P2)",
     [(M7,
       "             party.party_kind, claim_ref, observation_ref, party.provenance_class,",
       "             party.party_kind, claim_ref, observation_ref, ('RECONCILED' if party.provenance_class == 'MODEL_INFERRED' else party.provenance_class),  # MUTANT")],
     f"{T}::test_party_provenance_is_carried_never_strengthened"),

    ("the tenant predicate is dropped from the open-conflict lookup — one tenant's field reads as "
     "frozen by another tenant's conflict, cross-tenant coalescing ([C-1])",
     [(M7,
       '            "SELECT * FROM conflicts WHERE tenant = ? AND entity_ref = ? AND field = ? "',
       '            "SELECT * FROM conflicts WHERE (tenant = ? OR 1=1) AND entity_ref = ? AND field = ? "  # MUTANT')],
     f"{T}::test_tenant_predicate_isolates_the_open_conflict_lookup"),

    ("a CF-6 human resolution is attributed by POSITION — it emits producer CF-3 instead of CF-4, "
     "resolving by ordinal rather than by target state (machine §14 CF-6)",
     [(M7,
       '            payload={"decision_ref": decision_ref}, event_producer="CF-4", actor_type="human",',
       '            payload={"decision_ref": decision_ref}, event_producer="CF-3", actor_type="human",  # MUTANT')],
     f"{T}::test_cf6_resolution_is_by_target_state_not_ordinal_position"),

    ("an open conflict stops blocking — the native projection reports conflicting=False, so the GR-10 "
     "freeze the checkpoint reads is switched off (entity §36, GR-10)",
     [(M7,
       "        conflicting = self.is_open\n        return NativeConflictProjection(",
       "        conflicting = False  # MUTANT\n        return NativeConflictProjection(")],
     f"{T}::test_open_conflict_blocks_all_consequential_actions"),
]


def _run_edits(edits, guard) -> tuple[str, str]:
    originals: dict[Path, bytes] = {}
    for rel, old, new in edits:
        path = ROOT / rel
        if not path.exists():
            return "SETUP-FAIL", f"{rel} does not exist"
        if path not in originals:
            originals[path] = path.read_bytes()
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


def main() -> int:
    results = [(label, *_run_edits(edits, guard)) for label, edits, guard in CASES]
    print("\n=========== P6 M7 CONFLICT MUTATION BATTERY ===========")
    for label, verdict, note in results:
        mark = {"CAUGHT": "PASS", "MISS": "### MISS ###"}.get(verdict, verdict)
        print(f"  [{mark:>12}] {label}" + (f"  ({note})" if note else ""))
    caught = sum(1 for _, v, _ in results if v == "CAUGHT")
    print(f"\n  {caught}/{len(results)} mutants caught")
    print("  NOTE: written by the session that implemented the unit - evidence, not adjudication.")
    return 0 if caught == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
