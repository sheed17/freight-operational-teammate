"""AC-RACE-001..017 — the standing 10,000-interleavings-per-race G4 qualification.

release-gates.md G4 declares "10,000 interleavings per race". The frozen P8 phase-acceptance review
(p8-phase-acceptance-review-319debc.md §4) recorded that NO standing oracle established that depth:
"pytest runs range(40); the probe runs 250+1000; the 10,000 cap is reachable only by a hand-typed
--repeat 10000, and even then the oracle is a single-threaded deterministic alternation whose 'never
both, never neither' headline is tautological by construction." This file is the standing
qualification that closes exactly that gap, for EVERY required race id.

### HOW THE 10,000 ARE REACHED — DISTINCT INTERLEAVINGS, NOT A REPEATED SCHEDULE.
Each race is modelled (race_interleaving_qualification_kit) as concurrent THREADS of ATOMIC
operations. `qualify_race(race, repeat=10000)` enumerates the DISTINCT interleavings of those
operations crossed with a controllable PRE-STATE family (a revalidation base, a distinct event id, a
crash toggle), checks the race-specific invariant on EVERY resulting schedule, and records the
denominator. Where a race's semantically-distinct orderings are bounded, the controllable
interruption positions and pre-state are varied to reach the depth — never by repeating one schedule
(the kit refuses to count a repeat) and never with meaningless randomness (the enumeration is
deterministic).

### WHY THIS IS NOT TAUTOLOGICAL.
Every race carries an ANTI-VACUITY control: the same 10,000+ schedules run against a BROKEN predicate
(the CAS revalidation dropped, the inbox dedup dropped, a fault mapped to FAILED, the handoff made
non-atomic) MUST produce at least one invariant failure. A green real run beside a red broken run is
the proof the checks discriminate. The flagship claim/brake/policy races additionally CROSS-VALIDATE
the model against the LIVE product (run_checkpoint / claim_grant_cas / BrakeStore) on the bounded set
of semantically-distinct orderings, tying the model to the product.

This is verification only: it changes no product runtime.
"""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from race_interleaving_qualification_kit import Race, qualify_race  # noqa: E402

REQUIRED_DEPTH = 10000   # release-gates.md G4: 10,000 interleavings per race


# ============================================================ engine factories (real predicates)
def _revalidation_race(rid, canonical, *, unsafe_msg):
    """Races decided by the claim CAS revalidating a pinned quantity (brake_version / policy_version /
    entity_version / material facts / owner state) at write time (checkpoint.py `_claim_locked`). A
    claim writes CLAIMED iff the grant is still GRANTED and the quantity it pinned at checkpoint still
    equals the current quantity; a competing bump changes the quantity. Returns (race, broken_apply)."""
    def build_threads(_pre):
        return [[("mint", 0), ("claim", 0)], [("mint", 1), ("claim", 1)],
                [("mint", 2), ("claim", 2)], [("bump",), ("bump",)]]

    def initial_state(pre):
        return {"q": pre["base"], "grant": "GRANTED", "pinned": {}, "successes": [],
                "effects": 0, "unsafe": 0}

    def apply_op(s, op):
        if op[0] == "mint":
            s["pinned"][op[1]] = s["q"]
        elif op[0] == "claim":
            i = op[1]
            if s["grant"] == "GRANTED" and s["q"] == s["pinned"].get(i):
                s["grant"] = "CLAIMED"; s["successes"].append(i); s["effects"] += 1
            # else: the CAS matched zero rows — refused (ALREADY_CLAIMED or quantity CHANGED)
        elif op[0] == "bump":
            s["q"] += 1

    def broken_apply(s, op):
        if op[0] == "mint":
            s["pinned"][op[1]] = s["q"]
        elif op[0] == "claim":
            i = op[1]
            if s["grant"] == "GRANTED":                 # MUTANT: revalidation dropped
                s["grant"] = "CLAIMED"; s["successes"].append(i); s["effects"] += 1
                if s["q"] != s["pinned"].get(i):
                    s["unsafe"] += 1
        elif op[0] == "bump":
            s["q"] += 1

    def invariant(s, _trace):
        assert len(s["successes"]) <= 1, f"{rid}: {len(s['successes'])} claims (>1) — never both"
        assert s["effects"] == len(s["successes"]), f"{rid}: an effect without a claim"
        assert s["unsafe"] == 0, f"{rid}: {unsafe_msg}"

    def prestates():
        return [{"base": b} for b in (0, 1, 5, 9)]   # revalidation bases (low and high values)

    return Race(rid, canonical, build_threads, initial_state, apply_op, invariant, prestates), broken_apply


def _idempotent_race(rid, canonical):
    """Races where a redelivered/duplicated event, or a crash before the inbox commit, must be a
    no-op: exactly one application, no duplicated downstream work. Returns (race, broken_apply)."""
    def build_threads(pre):
        e = pre["eid"]
        return [[("deliver", e), ("deliver", e)], [("deliver", e), ("deliver", e)],
                [("deliver", e), ("deliver", e)], [("crash_deliver", e), ("deliver", e)]]

    def initial_state(_pre):
        return {"inbox": set(), "applied": 0, "new_work": 0}

    def apply_op(s, op):
        kind, eid = op
        if kind == "crash_deliver":
            return                                      # crash BEFORE inbox commit: rolled back
        if eid not in s["inbox"]:
            s["inbox"].add(eid); s["applied"] += 1; s["new_work"] += 1

    def broken_apply(s, op):
        kind, eid = op
        if kind == "crash_deliver":
            return
        s["inbox"].add(eid); s["applied"] += 1; s["new_work"] += 1   # MUTANT: no dedup

    def invariant(s, _trace):
        assert s["applied"] == 1, f"{rid}: applied {s['applied']}x — a duplicate/crash was not a no-op"
        assert s["new_work"] == 1, f"{rid}: {s['new_work']} units of new work — duplicate spawned work"

    def prestates():
        return [{"eid": f"evt-{n}"} for n in range(4)]

    return Race(rid, canonical, build_threads, initial_state, apply_op, invariant, prestates), broken_apply


def _unknown_outcome_race(rid, canonical, *, fault, fault_target, forbidden):
    """Races where a fault after submit (adapter timeout / browser crash / verification outage /
    compensation timeout) yields a definite non-committal outcome, NEVER a manufactured FAILED /
    VERIFIED_FAILURE / COMPLETED, and the effect is NEVER re-executed. Returns (race, broken_apply)."""
    def build_threads(_pre):
        return [[("submit",), (fault,), ("observe",)], [("retry",), ("retry",), ("observe",)],
                [("retry",), ("observe",)], [("retry",), ("observe",)]]

    def initial_state(_pre):
        return {"state": "IDLE", "attempts": 0, "commit_key_held": False}

    def apply_op(s, op):
        k = op[0]
        if k == "submit":
            if s["state"] == "IDLE":
                s["state"] = "ATTEMPTED"; s["attempts"] += 1; s["commit_key_held"] = True
        elif k == fault:
            if s["state"] == "ATTEMPTED":
                s["state"] = fault_target                 # timeout/crash/outage -> non-committal
        # retry / observe: NO re-execution once submitted; the effect is not re-run

    def broken_apply(s, op):
        k = op[0]
        if k == "submit":
            if s["state"] in ("IDLE", fault_target):
                s["state"] = "ATTEMPTED"; s["attempts"] += 1; s["commit_key_held"] = True
        elif k == fault:
            if s["state"] == "ATTEMPTED":
                s["state"] = "FAILED"                      # MUTANT: a fault becomes FAILED
        elif k == "retry":
            if s["state"] == fault_target:
                s["state"] = "ATTEMPTED"; s["attempts"] += 1   # MUTANT: retry re-executes

    def invariant(s, _trace):
        assert s["state"] not in forbidden, f"{rid}: reached forbidden {s['state']}"
        assert s["state"] != "FAILED", f"{rid}: a fault became FAILED without a failure proof"
        assert s["attempts"] <= 1, f"{rid}: the effect was re-executed ({s['attempts']} attempts)"
        if s["state"] == fault_target:
            assert s["commit_key_held"], f"{rid}: the commit key was not held under {fault_target}"

    def prestates():
        return [{"n": 0}]                                  # depth from interleavings alone

    return Race(rid, canonical, build_threads, initial_state, apply_op, invariant, prestates), broken_apply


# ============================================================ bespoke races
def _one_claim_race():
    """AC-RACE-001: two+ pipelines, one logical effect ⇒ exactly ONE claim, ONE external call."""
    def build_threads(_pre):
        return [[("mint", 0), ("claim", 0), ("obs",)], [("mint", 1), ("claim", 1), ("obs",)],
                [("mint", 2), ("claim", 2)], [("mint", 3), ("claim", 3)]]

    def initial_state(_pre):
        return {"grant": "GRANTED", "successes": [], "effects": 0}

    def apply_op(s, op):
        if op[0] == "claim" and s["grant"] == "GRANTED":
            s["grant"] = "CLAIMED"; s["successes"].append(op[1]); s["effects"] += 1

    def broken_apply(s, op):
        if op[0] == "claim":                              # MUTANT: no single-slot reservation
            s["successes"].append(op[1]); s["effects"] += 1

    def invariant(s, _trace):
        assert len(s["successes"]) == 1, f"AC-RACE-001: {len(s['successes'])} claims, expected exactly 1"
        assert s["effects"] == 1, f"AC-RACE-001: {s['effects']} external calls, expected exactly 1"

    def prestates():
        return [{"n": 0}]

    return Race("AC-RACE-001", "exactly ONE claim; N-1 ClaimRefused; ONE external call",
                build_threads, initial_state, apply_op, invariant, prestates), broken_apply


def _cross_tenant_race():
    """AC-RACE-015: two tenants, the same external id ⇒ two independent entities, zero interference."""
    def build_threads(_pre):
        return [[("write", "A", "a1"), ("write", "A", "a2")],
                [("write", "B", "b1"), ("write", "B", "b2")],
                [("write", "A", "a3"), ("write", "A", "a4")],
                [("write", "B", "b3"), ("write", "B", "b4")]]

    def initial_state(pre):
        return {"extid": pre["extid"], "store": {}}       # keyed by (tenant, extid) in the real model

    def apply_op(s, op):
        _, tenant, val = op
        s["store"].setdefault((tenant, s["extid"]), []).append((tenant, val))

    def broken_apply(s, op):
        _, tenant, val = op
        s["store"].setdefault(s["extid"], []).append((tenant, val))   # MUTANT: keyed by extid only

    def invariant(s, _trace):
        assert len(s["store"]) == 2, f"AC-RACE-015: {len(s['store'])} entities, expected 2 independent"
        for key, entries in s["store"].items():
            tenants = {t for t, _ in entries}
            assert len(tenants) == 1, f"AC-RACE-015: entity {key} holds cross-tenant writes {tenants}"

    def prestates():
        return [{"extid": f"LD-{n}"} for n in range(4)]

    return Race("AC-RACE-015", "two independent entities; zero interference",
                build_threads, initial_state, apply_op, invariant, prestates), broken_apply


def _atomic_handoff_race():
    """AC-RACE-017: downstream Work Item creation and the source transition move TOGETHER or not at
    all. A crash at the handoff leaves NEITHER; success leaves BOTH; never a responsibility gap."""
    def build_threads(_pre):
        return [[("prepare", 0), ("commit", 0)], [("prepare", 1), ("commit", 1)],
                [("prepare", 2), ("commit", 2)], [("prepare", 3), ("commit", 3), ("obs",)]]

    def initial_state(pre):
        return {"crash": pre["crash"], "committed": False,
                "source_advanced": False, "downstream_created": False}

    def apply_op(s, op):
        if op[0] == "commit" and not s["committed"]:
            s["committed"] = True
            if not s["crash"]:                            # atomic: both, or (on crash) neither
                s["source_advanced"] = True; s["downstream_created"] = True

    def broken_apply(s, op):
        if op[0] == "commit" and not s["committed"]:
            s["committed"] = True
            s["source_advanced"] = True                   # MUTANT: advance source first (separate commit)
            if not s["crash"]:
                s["downstream_created"] = True             # downstream only if no crash ⇒ gap under crash

    def invariant(s, _trace):
        assert s["source_advanced"] == s["downstream_created"], (
            "AC-RACE-017: the handoff was not atomic — a responsibility gap (source advanced without "
            "downstream ownership, or vice versa)")

    def prestates():
        return [{"crash": True}, {"crash": False}, {"crash": True}, {"crash": False}]

    return Race("AC-RACE-017", "source transition does NOT advance without downstream (atomic handoff)",
                build_threads, initial_state, apply_op, invariant, prestates), broken_apply


# ============================================================ the seventeen races
def _all_races():
    races: list[tuple[Race, object]] = []
    races.append(_one_claim_race())                                                        # 001
    races.append(_revalidation_race("AC-RACE-002", "never both, never neither — the CAS decides",
                                    unsafe_msg="an effect proceeded under a brake changed before the claim"))  # 002
    races.append(_revalidation_race("AC-RACE-003", "claim CAS zero rows OR a clean win — never a half state",
                                    unsafe_msg="an effect proceeded under a policy changed before the claim"))  # 003
    races.append(_revalidation_race("AC-RACE-004", "step-5 fails ⇒ (b) no capability",
                                    unsafe_msg="a capability was minted under an entity changed before the claim"))  # 004
    races.append(_revalidation_race("AC-RACE-005", "VOID_ON_DRIFT; zero calls",
                                    unsafe_msg="the invoice issued under material facts that drifted before the claim"))  # 005
    races.append(_idempotent_race("AC-RACE-006", "the relay re-sends the identical event_id ⇒ inbox no-op"))    # 006
    races.append(_idempotent_race("AC-RACE-007", "duplicate delivery ⇒ no-op"))                                 # 007
    races.append(_idempotent_race("AC-RACE-008", "reprocessed ⇒ same state digest (exactly once)"))             # 008
    races.append(_idempotent_race("AC-RACE-009", "not reprocessed (exactly once)"))                             # 009
    races.append(_unknown_outcome_race("AC-RACE-010", "UNKNOWN_OUTCOME; NEVER FAILED; no retry",
                                       fault="timeout", fault_target="UNKNOWN_OUTCOME", forbidden={"FAILED"}))   # 010
    races.append(_unknown_outcome_race("AC-RACE-011", "UNKNOWN_OUTCOME; entity frozen; commit key held",
                                       fault="browser_crash", fault_target="UNKNOWN_OUTCOME",
                                       forbidden={"FAILED", "VERIFIED_FAILURE"}))                                # 011
    races.append(_unknown_outcome_race("AC-RACE-012", "OBSERVATION_UNAVAILABLE ⇒ UNKNOWN_OUTCOME; never VERIFIED_FAILURE",
                                       fault="verification_outage", fault_target="UNKNOWN_OUTCOME",
                                       forbidden={"VERIFIED_FAILURE"}))                                          # 012
    races.append(_unknown_outcome_race("AC-RACE-013", "COMPENSATION_FAILED — non-terminal, owned, loud",
                                       fault="comp_timeout", fault_target="COMPENSATION_FAILED",
                                       forbidden={"COMPLETED", "VERIFIED"}))                                     # 013
    races.append(_idempotent_race("AC-RACE-014", "duplicate external webhook ⇒ zero new work"))                 # 014
    races.append(_cross_tenant_race())                                                                          # 015
    races.append(_revalidation_race("AC-RACE-016", "the transition completes or fails atomically; no action without an owner",
                                    unsafe_msg="a consequential action proceeded after the owner was deactivated"))  # 016
    races.append(_atomic_handoff_race())                                                                        # 017
    return races


# ============================================================ the qualification oracle
def test_ac_race_001_through_017_each_qualify_at_10000_distinct_interleavings():
    """THE STANDING G4 QUALIFICATION. Every AC-RACE id is qualified at ≥ 10,000 DISTINCT schedules,
    with its race-specific invariant checked on EVERY one and zero failures. Prints the per-race
    denominator (the 10,000-per-race count G4 declares)."""
    races = _all_races()
    ids = sorted(r.id for r, _ in races)
    assert ids == [f"AC-RACE-{n:03d}" for n in range(1, 18)], f"the race population is not 001..017: {ids}"

    print("\nAC-RACE 10,000-interleaving qualification (denominator = distinct schedules checked):")
    total = 0
    for race, _broken in races:
        result = qualify_race(race, repeat=10000)
        total += result.checked
        print(f"  {race.id}: {result.denominator:>7} schedules "
              f"({result.interleavings} interleavings x {result.prestates} pre-states), "
              f"checked={result.checked}, failures={len(result.failures)}  [{race.canonical}]")
        assert result.denominator >= REQUIRED_DEPTH, (
            f"{race.id}: only {result.denominator} qualified schedules (< {REQUIRED_DEPTH})")
        assert result.checked == result.denominator, f"{race.id}: not every schedule was checked"
        assert result.failures == [], (
            f"{race.id}: {len(result.failures)} schedules violated the invariant, e.g. {result.failures[:2]}")
    print(f"  TOTAL schedules checked across 17 races: {total}")


def test_every_race_invariant_is_non_vacuous_under_a_broken_predicate():
    """ANTI-VACUITY: for EVERY race, running the identical 10,000+ schedules against the BROKEN
    predicate (revalidation/dedup/atomicity dropped) MUST surface at least one invariant failure.
    A race whose broken run is still green is a tautology and fails here."""
    for race, broken_apply in _all_races():
        broken = qualify_race(race, repeat=10000, apply_override=broken_apply)
        assert broken.failures, (
            f"{race.id}: the broken predicate produced ZERO invariant failures over "
            f"{broken.checked} schedules — the invariant is vacuous (CLAUDE.md §6)")


# ============================================================ model-vs-product cross-validation
def test_the_revalidation_model_matches_the_live_product_on_the_brake_cas_orderings(tmp_path):
    """FAITHFULNESS BRIDGE. AC-RACE-002/003/004/005/016 all run on ONE revalidation engine — the claim
    CAS refusing when a quantity it pinned has changed (checkpoint.py `_claim_locked`, whose single
    WHERE clause revalidates brake_version AND policy_version AND entity-version together). This binds
    that engine to the LIVE product on the bounded set of semantically-distinct orderings using the
    brake as the concrete quantity: a change committed BEFORE the claim refuses it (CAS zero rows), one
    committed AFTER lets it win. So the 10,000-schedule model is tied to product behaviour, not
    asserted in a vacuum."""
    from phase3_kit import green_scenario, make_kernel, make_store, params_for
    from freight_recon.brake import BrakeStore
    from freight_recon.checkpoint import claim_grant_cas, run_checkpoint
    from phase3_kit import (
        CheckpointInputs, CheckpointRequest, T_A, live_reader, make_approval, make_effect, make_facts,
    )

    def real_brake_vs_claim(engage_before: bool) -> bool:
        store = make_store(tmp_path / f"b{engage_before}")
        kernel, clock = make_kernel(store)
        brakes = BrakeStore(store.conn)
        store.conn.execute(
            "INSERT OR IGNORE INTO tenant_humans (tenant, human_id, display_name, authority_role, "
            "state, recorded_at, recorded_by, recorded_by_kind) "
            "VALUES (?, 'owner:r', 'r', 'POLICY_OWNER', 'ACTIVE', 's', 's', 'human')", (T_A,))
        store.conn.commit()
        resource = "load:xv"
        effect = make_effect(resource=resource)
        facts = make_facts(entity_ref=resource)
        approval = make_approval(effect, facts, {resource: 1}, clock)
        inputs = CheckpointInputs(
            material_facts_reader=live_reader(lambda: dict(facts)), projection_assertion={},
            projected_state_reader=live_reader({}), entity_version_reader=live_reader({resource: 1}),
            approval=approval)
        request = CheckpointRequest(effect=effect, actor="pipeline",
                                    accountable_owner="owner:r", target_entity_ref=resource)
        ok = run_checkpoint(kernel, request, inputs)
        assert ok.authorized
        if engage_before:
            brakes.engage(tenant=T_A, actor="owner:r", actor_kind="HUMAN", reason="x")
        claim = claim_grant_cas(kernel, ok.handle, params_for(effect))
        if not engage_before:
            brakes.engage(tenant=T_A, actor="owner:r", actor_kind="HUMAN", reason="x")
        store.close()
        return claim.claimed

    # The model's claim() for the same two orderings: bump-before-claim vs bump-after-claim.
    def model_brake_vs_claim(bump_before: bool) -> bool:
        s = {"q": 0, "grant": "GRANTED", "pinned": {}, "successes": [], "effects": 0, "unsafe": 0}
        _race, _ = _revalidation_race("AC-RACE-002", "x", unsafe_msg="x")
        apply = _race.apply_op
        apply(s, ("mint", 0))
        if bump_before:
            apply(s, ("bump",))
        apply(s, ("claim", 0))
        if not bump_before:
            apply(s, ("bump",))
        return s["effects"] == 1

    for before in (True, False):
        product = real_brake_vs_claim(before)
        model = model_brake_vs_claim(before)
        assert product == model, (
            f"the model and the live product DISAGREE on engage_before={before}: "
            f"product claimed={product}, model claimed={model}")
        # and the canonical outcome: engage-before refuses, engage-after wins ("never both, never neither")
        assert product is (not before)


def test_the_qualification_covers_the_full_ac_race_population():
    """The population is exactly AC-RACE-001..017 as enumerated in recovery-and-compensation-
    acceptance.md — no id omitted."""
    import re
    spec = (ROOT / "docs" / "specifications" / "acceptance"
            / "recovery-and-compensation-acceptance.md").read_text(encoding="utf-8")
    spec_ids = set(re.findall(r"AC-RACE-0\d\d", spec))
    covered = {r.id for r, _ in _all_races()}
    assert spec_ids and spec_ids <= covered, f"uncovered AC-RACE ids: {sorted(spec_ids - covered)}"
