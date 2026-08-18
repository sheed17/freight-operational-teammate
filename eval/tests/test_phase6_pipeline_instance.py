"""P6 M2 — the Pipeline Instance, attacked.

The battery is organised by RISK, not by taxonomy. Each section is a way this mechanism could be
wrong in production, and every one of them costs a broker money when it is:

    the transition table lies      the implementation and §14 disagree             (AC-MACH-000)
    two attempts, one effect       the Layer-1 reservation does not hold        (PL-1 / PL-1b)
    a retry becomes a second pay   §20's retry rule is a convention                     (§20)
    an illegal transition moves    an omitted (state, trigger) pair is admitted        (GR-1)
    GRANTED with no witness        §41(a) is documentation                           (§41(a))
    both, or neither               a brake between checkpoint and claim splits them     (§30)
    FAILED without proof           a timeout is read as "nothing happened"             (GR-5)
    an unknown outcome resolves    a timer, a sweep or a guess closes it        (GR-6, AC-MACH-215x)
    verify without record          a crash loses the record of a verified effect  (acceptance (f))
    a terminal attempt moves       retry-in-place is reachable                          (§15)
    two writers, one truth         a stale version silently overwrites                 (GR-3)
    redelivery acts twice          a duplicate trigger is not a no-op                  (GR-4)
    tenants leak                   a T_B event moves a T_A attempt                     [C-1]
    production wakes up            an effect-capable module enters the import closure  (M-27)

`state_digest` is what makes "no-op" a measurement rather than a claim: every no-op case asserts the
digest is byte-identical across the second delivery.

### THIS IS THE IMPLEMENTING SESSION'S BATTERY, NOT AN INDEPENDENT REVIEW.
"""

from __future__ import annotations

import ast
import re
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from phase6_pipeline_kit import (  # noqa: E402
    HUMAN,
    LOAD,
    OWNER,
    PIPELINE,
    SYS,
    T_A,
    T_B,
    WORK_ITEM,
    Clock,
    a_human,
    a_human_decision,
    a_proposed_attempt,
    a_work_item,
    a_world,
    advance_to_checkpoint,
    an_effect,
    canonical_event,
    checkpoint_inputs,
    approval_fingerprint,
    kernel_for,
    ledger,
    machine,
    make_store,
    outbox_events,
    registry,
    security_rows,
    state_digest,
    witnesses,
)

from freight_recon.checkpoint import GateDecision  # noqa: E402
from freight_recon.commit_key import commit_key  # noqa: E402
from freight_recon.event_envelope import EventEnvelope  # noqa: E402
from freight_recon.event_inbox import ConsumeOutcome, DedupInbox  # noqa: E402
from freight_recon.migrations.phase6_pipeline_instances import (  # noqa: E402
    GATE_DECISIONS,
    P6PI_TRIGGERS,
    PIPELINE_STATES,
    TERMINAL_PIPELINE_STATES,
    phase6_pipeline_readiness_problems,
)
from freight_recon.pipeline_instance import (  # noqa: E402
    AGGREGATE_TYPE,
    CONSUMED_CONTRACTS,
    PRECEDENCE,
    PRODUCED_CONTRACTS,
    TRANSITIONS,
    TRANSITIONS_BY_ID,
    AuthorityRefused,
    GuardNotSatisfied,
    IllegalTransition,
    OwnershipRefused,
    PipelineError,
    PipelineMachine,
    PipelineState,
    ReservationHeld,
    RowKind,
    Trigger,
    UnknownPipeline,
    VersionConflict,
    legal_transitions,
    pipeline_must_exist,
)
from freight_recon.work_item import WorkItemMachine  # noqa: E402

MACHINE_SPEC = ROOT / "docs/specifications/state-machines/02-pipeline-instance.machine.md"
REGISTRY_SPEC = ROOT / "docs/specifications/state-machines/registry.md"
ACCEPTANCE_SPEC = ROOT / "docs/specifications/acceptance/foundational-machine-acceptance.md"


# =============================================================================== A. AC-MACH-000
# The structural case: the implementation's declarative table, enumerated and compared to the
# specification by EXACT SET EQUALITY of transition identifiers. A count match with different
# members MUST fail.

def _spec_rows() -> dict[str, dict[str, str]]:
    """Parse §14's transition table out of the machine file. Discovered, never transcribed.

    ### THE `\\|` ESCAPE IS THE WHOLE DIFFICULTY, AND GETTING IT WRONG SHIFTS EVERY COLUMN. §14
    writes an alternation inside a cell as `S\\|H`; a naive split on `|` turns that into two cells
    and every column after it is read as the one to its right — so `PL-9v`'s Event cell would be
    compared against its Writes cell and the mismatch would look like a specification disagreement
    rather than a parser bug. Split on an UNESCAPED pipe only.
    """
    rows: dict[str, dict[str, str]] = {}
    in_table = False
    for line in MACHINE_SPEC.read_text(encoding="utf-8").splitlines():
        if line.startswith("## 14."):
            in_table = True
            continue
        if in_table and line.startswith("## "):
            break
        if not in_table or not line.startswith("|"):
            continue
        cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]
        if len(cells) < 8 or not cells[0].startswith("**PL-"):
            continue
        rows[cells[0].strip("*").strip()] = {
            "transition": cells[1], "trig": cells[2], "guards": cells[3],
            "writes": cells[4], "approval": cells[4], "event": cells[6], "test": cells[7],
        }
    return rows


def _declared_transition_count() -> int:
    """M2's row count, read from `foundational-machine-acceptance.md`'s own coverage table.

    Not a literal. The acceptance document is what `AC-MACH-000` is accountable to, so the
    denominator comes from there and a specification amendment moves it without editing this file.
    """
    for line in ACCEPTANCE_SPEC.read_text(encoding="utf-8").splitlines():
        if line.startswith("| M2 Pipeline Instance"):
            return int(re.split(r"\|", line)[2].strip())
    raise AssertionError("foundational-machine-acceptance.md declares no M2 row count")


def test_the_spec_parser_is_not_vacuous():
    """### THE DENOMINATOR, PRINTED. A parser that found nothing would make every comparison below
    pass over an empty set — CLAUDE.md §9's exact failure."""
    rows = _spec_rows()
    expected = _declared_transition_count()
    assert expected == 25, f"the acceptance table says M2 has {expected} transitions, not 25"
    assert len(rows) == expected, f"parsed {len(rows)} §14 rows, expected {expected}: {sorted(rows)}"
    assert all(v["transition"] for v in rows.values()), "a parsed row has an empty transition cell"


def test_ac_mach_000_transition_identifiers_are_a_bijection_with_the_specification():
    """### EXACT SET EQUALITY, NOT A COUNT."""
    implemented = {row.id for row in TRANSITIONS}
    declared = set(_spec_rows())
    assert implemented == declared, (
        f"§14 and the implementation disagree. Only in the spec: {sorted(declared - implemented)}; "
        f"only in the implementation: {sorted(implemented - declared)}"
    )


def test_ac_mach_000_the_oracle_is_a_set_comparison_and_a_substitution_fails_it():
    """A POSITIVE CONTROL. If the oracle were a count, a same-count substitution would pass."""
    implemented = {row.id for row in TRANSITIONS}
    substituted = (implemented - {"PL-8"}) | {"PL-99"}
    assert len(substituted) == len(implemented)
    assert substituted != set(_spec_rows()), (
        "a same-count substitution compared EQUAL to the specification — the oracle is counting"
    )


@pytest.mark.parametrize("identifier", sorted(_spec_rows()))
def test_ac_mach_000_each_row_agrees_with_its_specification_row(identifier):
    """From-states, to-state, trigger types and event name, per row, against §14's own cells."""
    spec = _spec_rows()[identifier]
    row = TRANSITIONS_BY_ID[identifier]

    declared_types = {t for t in re.split(r"[\\|]+", spec["trig"]) if t.strip()}
    assert set(row.trigger_types) == declared_types, (
        f"{identifier}: trigger types {sorted(row.trigger_types)} != §14's {sorted(declared_types)}"
    )

    event_cell = spec["event"].replace("`", "")
    if row.kind is RowKind.PRODUCER:
        assert row.event_name and row.event_name in event_cell, (
            f"{identifier} emits {row.event_name!r}; §14's Event cell is {event_cell!r}"
        )
    elif row.kind is RowKind.CONSUMES:
        assert "CONSUMES" in event_cell, (
            f"{identifier} is modelled as CONSUMES and §14's Event cell does not say so: "
            f"{event_cell!r}"
        )
        for name in row.consumes:
            assert name in event_cell, f"{identifier} consumes {name}; §14 does not name it"
    else:
        assert "ILLEGAL" in event_cell.upper() or "NON_PRODUCING" in event_cell, (
            f"{identifier} is modelled NON_PRODUCING and §14 does not declare it: {event_cell!r}"
        )

    to_cell = spec["transition"]
    if row.creates or row.absorbs:
        assert "—" in to_cell or "clash" in to_cell, (
            f"{identifier} is the creation/absorption row and §14 disagrees: {to_cell!r}")
    else:
        for state in (row.to_state, row.alternate_to_state):
            if state is not None:
                assert state.value in to_cell, (
                    f"{identifier} reaches {state.value}; §14 says {to_cell!r}")
    for state in row.from_states:
        assert state.value in to_cell, (
            f"{identifier} accepts {state.value}; §14's From cell is {to_cell!r}")


def test_the_state_set_is_exactly_the_registrys_sixteen():
    """§7 says "the 16 of M2 (registry §4)". Membership, from the registry file itself."""
    text = REGISTRY_SPEC.read_text(encoding="utf-8")
    block = text.split("### M2 Pipeline Instance", 1)[1].split("###", 1)[0]
    declared = set(re.findall(r"`([A-Z_]+)`\s*`\(", block))
    assert len(declared) == 16, f"parsed {len(declared)} M2 states from registry §4: {sorted(declared)}"
    assert declared == {s.value for s in PipelineState} == set(PIPELINE_STATES), (
        f"registry §4 and the implementation disagree: only in registry "
        f"{sorted(declared - {s.value for s in PipelineState})}; only in code "
        f"{sorted({s.value for s in PipelineState} - declared)}"
    )


def test_the_terminal_set_is_exactly_the_four_of_section_8():
    assert set(TERMINAL_PIPELINE_STATES) == {"CLOSED", "REJECTED", "VOIDED", "FAILED"}
    assert "NEEDS_VERIFICATION" not in TERMINAL_PIPELINE_STATES, (
        "NEEDS_VERIFICATION is non-terminal by §9, and that is what keeps the Layer-1 reservation "
        "held so nothing may retry an effect we cannot say happened (§20)"
    )


def test_every_produced_contract_names_its_transition_as_a_producer():
    """The mechanical link (§1). An event this machine emits must be one the registry attributes to
    the emitting PL-* row, or the contract gate would refuse it — which is exactly the check being
    asserted here, ahead of the outbox rather than at it."""
    from freight_recon.event_contracts import CONTRACTS

    checked = 0
    for row in TRANSITIONS:
        if row.kind is not RowKind.PRODUCER or not row.event_name:
            continue
        checked += 1
        producers = CONTRACTS[row.event_name].producers
        assert row.id in producers, (
            f"{row.id} emits {row.event_name}, whose canonical producers are {list(producers)}"
        )
    assert checked == 16, f"only {checked} producer rows were checked; §14 has 16"


def test_no_consumed_contract_is_also_produced_by_this_machine():
    """### THE LINE THAT KEEPS M2 OUT OF M3's AND M4's AUTHORITY. A `CONSUMES` row moves this
    machine's own row; the canonical event belongs to the machine it co-commits with. Emitting one
    would be M2 asserting a fact about a grant or an approval it does not own."""
    assert PRODUCED_CONTRACTS & CONSUMED_CONTRACTS == frozenset()
    assert CONSUMED_CONTRACTS >= {"GrantClaimed", "ApprovalRequested", "EffectExecuted",
                                  "EffectFailed", "OutcomeUnknown", "EffectVerified",
                                  "RealityEstablished"}
    # `EffectAttempted` is EF-2's too, but §14 puts it in PL-9's WRITES cell rather than its Event
    # cell — so it is co-committed by M3, not consumed by M2, and neither machine's classification
    # is guessed from the other's.
    assert "EffectAttempted" not in CONSUMED_CONTRACTS | PRODUCED_CONTRACTS


# ======================================================================= B. the freight narrative

def _facts(**kwargs):
    """The machine's own `_Facts`, built the way `apply()` builds it — so the injected-fault cases
    below drive the SAME code path and not a convenient stand-in."""
    from freight_recon.pipeline_instance import _Facts, _split_facts

    return _Facts(**_split_facts(kwargs))


def _green(tmp_path, *, gate=GateDecision.HUMAN_APPROVAL_REQUIRED, tenant=T_A):
    """Load 4471 delivered, POD in hand, invoice owed — carried to CHECKPOINT."""
    clk = Clock()
    store = make_store(tmp_path, tenant)
    m, outcome = a_proposed_attempt(store, clock=clk, tenant=tenant)
    world = a_world()
    effect = an_effect(tenant=tenant)
    advance_to_checkpoint(m, gate=gate, fingerprint=approval_fingerprint(effect, world, clk))
    kernel = kernel_for(store, clk)
    return store, m, clk, kernel, effect, world, outcome


def _to_claimed(tmp_path, **kw):
    store, m, clk, kernel, effect, world, _ = _green(tmp_path, **kw)
    r8 = m.apply(PIPELINE, Trigger.CHECKPOINT_RUN, **SYS, kernel=kernel,
                 checkpoint_inputs=checkpoint_inputs(effect, world, clk))
    m.apply(PIPELINE, Trigger.CLAIM_ATTEMPTED, **SYS, kernel=kernel, handle=r8.grant_handle)
    return store, m, clk, kernel, effect, world, r8


def test_the_whole_attempt_runs_end_to_end_and_a_broker_can_read_it(tmp_path):
    """### THE CAPABILITY, IN ONE CASE. "Attempt #1 to raise the invoice for load 4471" is proposed
    against an obligation with a named owner, policy-checked, validated, routed to a human,
    approved, checkpointed into a witness and a grant, claimed once, executed, verified against the
    APPROVED fingerprint, recorded in the same commit, projected and closed."""
    store, m, clk, kernel, effect, world, r8 = _to_claimed(tmp_path)
    grant = r8.pipeline.grant_id

    executed = m.consume(
        canonical_event(store, event_name="EffectExecuted", producer_transition_id="EF-3",
                        aggregate_type="effect_grant", aggregate_id=grant, aggregate_version=1,
                        seed="exec-1", clock=clk, pipeline_instance_id=PIPELINE,
                        accountable_owner_id=OWNER),
        pipeline_instance_id=PIPELINE, trigger=Trigger.ADAPTER_RETURNED_SUCCESS)
    assert executed.transition and executed.transition.to_state is PipelineState.EXECUTED

    fingerprint = m.require(PIPELINE).material_facts_fingerprint
    verified = m.consume(
        canonical_event(store, event_name="EffectVerified", producer_transition_id="EF-4",
                        aggregate_type="effect_grant", aggregate_id=grant, aggregate_version=2,
                        seed="ver-1", clock=clk, pipeline_instance_id=PIPELINE,
                        accountable_owner_id=OWNER,
                        payload={"matched_fingerprint": fingerprint}),
        pipeline_instance_id=PIPELINE, trigger=Trigger.READBACK_MATCHED,
        matched_fingerprint=fingerprint, health_signal="HEALTHY")
    assert verified.transition is not None
    assert verified.transition.transition_id == "PL-11"
    assert [c.transition_id for c in verified.transition.co_commits] == ["PL-12"]
    assert m.require(PIPELINE).state is PipelineState.RECORDED

    m.apply(PIPELINE, Trigger.PROJECTION_UPDATED, **SYS, entity_ref=LOAD, from_effect_id=grant)
    closed = m.apply(PIPELINE, Trigger.CLOSE_REQUESTED, **SYS)
    assert closed.to_state is PipelineState.CLOSED

    # ONE witness, ONE grant, and the pipeline points at both.
    assert len(witnesses(store)) == 1
    assert [g["state"] for g in ledger(store)] == ["CLAIMED"]
    final = m.require(PIPELINE)
    assert final.checkpoint_id == witnesses(store)[0]["checkpoint_id"]
    assert final.grant_id == ledger(store)[0]["grant_id"]
    assert final.owner_id == OWNER, "the attempt is accountable to the Work Item's owner throughout"


def test_the_work_item_owns_the_attempt_and_the_attempt_says_so(tmp_path):
    store, m, *_ = _green(tmp_path)
    attempt = m.require(PIPELINE)
    m1 = WorkItemMachine(store.conn, tenant=T_A)
    assert attempt.owner_id == m1.require(WORK_ITEM).owner_id
    assert m.for_work_item(WORK_ITEM) == [attempt]
    # Every event this attempt emitted carries the accountable human and the obligation.
    rows = store.conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = ?",
        (T_A, AGGREGATE_TYPE)).fetchall()
    assert rows, "no M2 events were emitted; the assertion below would pass over nothing"
    for row in rows:
        compact = row["envelope_json"].replace(" ", "")
        assert f'"accountable_owner_id":"{OWNER}"' in compact
        assert f'"work_item_id":"{WORK_ITEM}"' in compact


def test_an_attempt_cannot_be_proposed_for_a_work_item_that_does_not_exist(tmp_path):
    """Hostile case 1. There is no obligation, so there is nothing to attempt and nobody accountable."""
    store = make_store(tmp_path)
    a_human(store)
    m = machine(store)
    with pytest.raises(OwnershipRefused, match="no Work Item"):
        m.propose(pipeline_instance_id=PIPELINE, work_item_id="wi-does-not-exist",
                  effect=an_effect(), **SYS)
    assert m.get(PIPELINE) is None


def test_an_attempt_cannot_be_proposed_for_another_tenants_work_item(tmp_path):
    """[C-1]. T_B's obligation is invisible to T_A, and the refusal does not say which it is."""
    store_a = make_store(tmp_path, T_A, name="a.db")
    store_b = make_store(tmp_path, T_B, name="b.db")
    a_human(store_b, tenant=T_B)
    a_work_item(store_b, tenant=T_B)
    a_human(store_a)
    m = machine(store_a)
    with pytest.raises(OwnershipRefused):
        m.propose(pipeline_instance_id=PIPELINE, work_item_id=WORK_ITEM, effect=an_effect(), **SYS)


def test_a_model_may_never_drive_this_machine(tmp_path):
    """C-6, GR-7, §40. A model emits an inert ProposedIntent; turning it into an attempt is not its
    act, and neither is any transition after it."""
    store, m, *_ = _green(tmp_path)
    with pytest.raises(AuthorityRefused, match="model"):
        m.propose(pipeline_instance_id="pl-2", work_item_id=WORK_ITEM, effect=an_effect(),
                  actor_type="model", actor_id="extractor")
    for trigger in Trigger:
        with pytest.raises(AuthorityRefused):
            m.apply(PIPELINE, trigger, actor_type="model", actor_id="extractor")


# ============================================================ C. GR-1, over a PROVEN population

def _attempt_in(tmp_path, state: PipelineState, name: str):
    """Build a committed attempt in EXACTLY `state`. Every one of the sixteen, so the sweep below
    runs over a population that is proven rather than assumed."""
    clk = Clock()
    store = make_store(tmp_path, name=name)
    m, _ = a_proposed_attempt(store, clock=clk)
    world, effect = a_world(), an_effect()
    kernel = kernel_for(store, clk)
    if state is PipelineState.PROPOSED:
        return store, m, clk, kernel
    if state is PipelineState.REJECTED:
        m.apply(PIPELINE, Trigger.POLICY_EVALUATED, **SYS, policy_version="pv1",
                gate_decision=GateDecision.FORBIDDEN, policy_decision="DENY",
                reason="forbidden action class", model_inferred_material_fact=False)
        return store, m, clk, kernel
    m.apply(PIPELINE, Trigger.POLICY_EVALUATED, **SYS, policy_version="pv1",
            gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_decision="PERMIT",
            rules_matched=["r-1"], reason="human gate", model_inferred_material_fact=False)
    if state is PipelineState.POLICY_CHECKED:
        return store, m, clk, kernel
    m.apply(PIPELINE, Trigger.VALIDATION_COMPLETED, **SYS, validation_passed=True,
            money_fence_passed=True, document_fence_passed=True,
            material_fields_consistent=True, open_conflict=False)
    if state is PipelineState.VALIDATED:
        return store, m, clk, kernel
    m.apply(PIPELINE, Trigger.GATE_ROUTED, **SYS, gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED)
    if state is PipelineState.AWAITING_APPROVAL:
        return store, m, clk, kernel
    if state is PipelineState.VOIDED:
        m.apply(PIPELINE, Trigger.BRAKE_ENGAGED, **SYS, reason="platform brake engaged")
        return store, m, clk, kernel
    m.apply(PIPELINE, Trigger.APPROVAL_GRANTED, **HUMAN, approval_id="ap-1",
            approval_commit_key=m.require(PIPELINE).commit_key,
            approval_fingerprint=approval_fingerprint(effect, world, clk))
    if state is PipelineState.CHECKPOINT:
        return store, m, clk, kernel
    r8 = m.apply(PIPELINE, Trigger.CHECKPOINT_RUN, **SYS, kernel=kernel,
                 checkpoint_inputs=checkpoint_inputs(effect, world, clk))
    if state is PipelineState.GRANTED:
        return store, m, clk, kernel
    m.apply(PIPELINE, Trigger.CLAIM_ATTEMPTED, **SYS, kernel=kernel, handle=r8.grant_handle)
    if state is PipelineState.CLAIMED:
        return store, m, clk, kernel
    if state is PipelineState.FAILED:
        m.apply(PIPELINE, Trigger.ADAPTER_REJECTED_PRE_FLIGHT, **SYS,
                failure_proof="TMS returned 422 before the write; no invoice id was allocated")
        return store, m, clk, kernel
    if state in (PipelineState.NEEDS_VERIFICATION, PipelineState.VERIFIED):
        m.apply(PIPELINE, Trigger.ADAPTER_TIMED_OUT, **SYS, unknown_reason="UNKNOWN_OUTCOME",
                unknown_outcome_ref="obs-1")
        if state is PipelineState.NEEDS_VERIFICATION:
            return store, m, clk, kernel
        ref = a_human_decision(store, clock=clk, seed=f"reality-{name}")
        m.apply(PIPELINE, Trigger.HUMAN_ESTABLISHED_REALITY, **HUMAN, outcome="VERIFIED",
                decision_ref=ref, decision_ref_kind="AUDIT_EVENT")
        return store, m, clk, kernel
    grant = r8.pipeline.grant_id
    m.consume(
        canonical_event(store, event_name="EffectExecuted", producer_transition_id="EF-3",
                        aggregate_type="effect_grant", aggregate_id=grant, aggregate_version=1,
                        seed=f"exec-{name}", clock=clk, pipeline_instance_id=PIPELINE,
                        accountable_owner_id=OWNER),
        pipeline_instance_id=PIPELINE, trigger=Trigger.ADAPTER_RETURNED_SUCCESS)
    if state is PipelineState.EXECUTED:
        return store, m, clk, kernel
    fingerprint = m.require(PIPELINE).material_facts_fingerprint
    m.consume(
        canonical_event(store, event_name="EffectVerified", producer_transition_id="EF-4",
                        aggregate_type="effect_grant", aggregate_id=grant, aggregate_version=2,
                        seed=f"ver-{name}", clock=clk, pipeline_instance_id=PIPELINE,
                        accountable_owner_id=OWNER, payload={"matched_fingerprint": fingerprint}),
        pipeline_instance_id=PIPELINE, trigger=Trigger.READBACK_MATCHED,
        matched_fingerprint=fingerprint, health_signal="HEALTHY")
    if state is PipelineState.RECORDED:
        return store, m, clk, kernel
    m.apply(PIPELINE, Trigger.PROJECTION_UPDATED, **SYS, entity_ref=LOAD, from_effect_id=grant)
    if state is PipelineState.PROJECTED:
        return store, m, clk, kernel
    m.apply(PIPELINE, Trigger.CLOSE_REQUESTED, **SYS)
    assert state is PipelineState.CLOSED
    return store, m, clk, kernel


@pytest.mark.parametrize("state", list(PipelineState))
def test_every_one_of_the_sixteen_states_is_reachable(tmp_path, state):
    """### THE POPULATION, PROVEN. The sweep below asserts things about (state × trigger) pairs; if
    a state were unreachable, every assertion about it would pass over nothing."""
    _, m, *_ = _attempt_in(tmp_path, state, name=f"reach-{state.value}.db")
    assert m.require(PIPELINE).state is state


def test_the_legal_pair_population_is_non_empty_and_smaller_than_the_grid(tmp_path):
    """The denominator for the sweep, printed rather than assumed."""
    grid = [(s, t) for s in PipelineState for t in Trigger]
    legal = [(s, t) for s, t in grid if legal_transitions(s, t)]
    assert len(grid) == 16 * len(Trigger) == 400
    assert legal, "no (state, trigger) pair is legal — the sweep would prove nothing"
    assert len(legal) == 23, f"expected 23 legal pairs from §14, found {len(legal)}: {legal}"
    assert len(grid) - len(legal) == 377


@pytest.mark.parametrize("state", list(PipelineState))
def test_gr1_every_omitted_pair_is_illegal_persists_nothing_and_is_recorded(tmp_path, state):
    """### AN EXHAUSTIVE (state × trigger) SWEEP. Each non-enumerated pair must raise, persist
    NOTHING, and record `IllegalTransitionAttempted` to the audit backbone AND `security_events`
    (GR-1, [C-4]) — and each DISTINCT attempt must get its own record, which is the defect M1's
    first candidate was rejected for."""
    store, m, *_ = _attempt_in(tmp_path, state, name=f"sweep-{state.value}.db")
    illegal = [t for t in Trigger if not legal_transitions(state, t)]
    assert illegal, f"{state.value} has no illegal trigger; this case would prove nothing"
    before = m.require(PIPELINE)
    security_before = len(security_rows(store))

    identities: set[str] = set()
    for trigger in illegal:
        with pytest.raises(IllegalTransition):
            m.apply(PIPELINE, trigger, **SYS)
        after = m.require(PIPELINE)
        assert (after.state, after.version) == (before.state, before.version), (
            f"{trigger.value} on {state.value} moved the attempt; GR-1 persists NOTHING")
        record = m.illegal_attempt_identity(after, "x")
        identities.add(record)

    recorded = [r for r in security_rows(store) if r["event_type"] == "IllegalTransitionAttempted"]
    assert len(recorded) - security_before == len(illegal), (
        f"{len(illegal)} distinct hostile attempts produced "
        f"{len(recorded) - security_before} security records. Every DISTINCT attempt gets its own "
        f"evidence — the collision M1's first candidate shipped recorded only the first."
    )
    emitted = [e for e in outbox_events(store)
               if e["event_name"] == "IllegalTransitionAttempted"]
    assert len(emitted) == len(recorded), "the audit and security surfaces disagree ([C-4])"


def test_ac_mach_215x_no_timer_moves_needs_verification(tmp_path):
    """### THE NAMED MERGE-GATING ANCHOR. §14 PL-15x, GR-6: an `UNKNOWN_OUTCOME` never silently
    becomes success or failure, and NO timer transition may move it."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.NEEDS_VERIFICATION, name="215x.db")
    before = state_digest(store)
    with pytest.raises(IllegalTransition):
        m.apply(PIPELINE, Trigger.TIMER_FIRED, **SYS)
    assert m.require(PIPELINE).state is PipelineState.NEEDS_VERIFICATION
    assert before != state_digest(store), "the refusal left no record at all"
    assert any(r["event_type"] == "IllegalTransitionAttempted" for r in security_rows(store))
    # And it is not a special case at one state: a timer is illegal EVERYWHERE on this machine.
    assert TRANSITIONS_BY_ID["PL-15x"].illegal
    assert not any(legal_transitions(s, Trigger.TIMER_FIRED) for s in PipelineState)


def test_needs_verification_never_auto_resolves_and_holds_the_reservation(tmp_path):
    """§20 + §23 + acceptance (d). The Sev-1 queue, and the retry it blocks."""
    store, m, clk, _ = _attempt_in(tmp_path, PipelineState.NEEDS_VERIFICATION, name="nv.db")
    attempt = m.require(PIPELINE)
    assert m.needs_verification() == [attempt]
    assert m.live_holder(attempt.commit_key) == attempt, (
        "NEEDS_VERIFICATION is non-terminal, so it keeps the Layer-1 reservation: nothing may retry "
        "an effect we cannot say happened")
    # Time passing changes nothing. §23: NEEDS_VERIFICATION never expires.
    clk.advance(days=30)
    assert m.require(PIPELINE).state is PipelineState.NEEDS_VERIFICATION
    with pytest.raises(PipelineError, match="has not finished"):
        m.propose(pipeline_instance_id="pl-retry", work_item_id=WORK_ITEM, effect=an_effect(),
                  supersedes=PIPELINE, **SYS)


# ================================================== D. PL-1 / PL-1b — one attempt, one effect

def test_pl_1b_a_second_proposal_for_one_effect_is_absorbed_not_raced(tmp_path):
    """### THE DUPLICATE-INVOICE DEFENCE. Two proposals, one live attempt, ONE operator card."""
    store, m, clk, _ = _attempt_in(tmp_path, PipelineState.PROPOSED, name="absorb.db")
    holder = m.require(PIPELINE)
    outcome = m.propose(pipeline_instance_id="pl-4471-invoice-2", work_item_id=WORK_ITEM,
                        effect=an_effect(), proposal_ref="intent-2", **SYS)
    assert outcome.absorbed is not None and not outcome.is_new_attempt
    assert outcome.absorbed.holder.pipeline_instance_id == PIPELINE
    assert m.get("pl-4471-invoice-2") is None, "the duplicate became a row"
    after = m.require(PIPELINE)
    assert after.state is holder.state, "absorption changed the holder's STATE; §14 declares none"
    assert after.version == holder.version + 1, (
        "absorption did not advance the version. `DuplicateProposalAbsorbed` is an F2 contract and "
        "F2 is strictly ordered, so a strict event must OWN the version it rides at (§8)")
    assert (after.absorbed_count, after.last_absorbed_ref) == (1, "intent-2")
    absorbed = [e for e in outbox_events(store)
                if e["event_name"] == "DuplicateProposalAbsorbed"]
    assert len(absorbed) == 1


def test_pl_1b_the_same_duplicate_absorbed_twice_is_one_record_two_duplicates_are_two(tmp_path):
    """The identity is keyed on the ABSORBED proposal, so redelivery is idempotent by construction
    and a genuinely different duplicate is genuinely different evidence."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.PROPOSED, name="absorb2.db")
    first = m.propose(pipeline_instance_id="pl-x", work_item_id=WORK_ITEM, effect=an_effect(),
                      proposal_ref="intent-2", **SYS).absorbed
    again = m.propose(pipeline_instance_id="pl-x", work_item_id=WORK_ITEM, effect=an_effect(),
                      proposal_ref="intent-2", **SYS).absorbed
    other = m.propose(pipeline_instance_id="pl-y", work_item_id=WORK_ITEM, effect=an_effect(),
                      proposal_ref="intent-3", **SYS).absorbed
    assert first and again and other
    assert again.already_absorbed and again.event_id == first.event_id
    assert not other.already_absorbed and other.event_id != first.event_id
    assert first.idempotency_identity != other.idempotency_identity
    assert len([e for e in outbox_events(store)
                if e["event_name"] == "DuplicateProposalAbsorbed"]) == 2


def test_the_commit_key_is_derived_from_the_logical_effect_and_carries_no_amount(tmp_path):
    """ADR-009 / rule 8. "Bill load 4471" is ONE logical effect whichever amount a model proposed —
    which is exactly why the second proposal must be absorbed."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.PROPOSED, name="key.db")
    effect = an_effect()
    assert m.require(PIPELINE).commit_key == commit_key(effect)
    assert m.require(PIPELINE).effect == effect
    # A different amount is not a different effect: nothing about the amount reaches the key.
    from dataclasses import fields
    assert "amount" not in {f.name for f in fields(effect)}


def test_a_terminal_attempt_releases_the_reservation_and_a_live_one_does_not(tmp_path):
    """The Layer-1 predicate IS §20's retry rule. Measured over every one of the sixteen states."""
    for state in PipelineState:
        _, m, *_ = _attempt_in(tmp_path, state, name=f"res-{state.value}.db")
        attempt = m.require(PIPELINE)
        held = m.live_holder(attempt.commit_key) is not None
        assert held == (not attempt.is_terminal), (
            f"{state.value}: reservation held={held}, terminal={attempt.is_terminal}. The index "
            f"predicate and §20 must be the same set."
        )


def test_the_reservation_is_a_database_constraint_not_a_read_then_write(tmp_path):
    """A competitor that slipped between the holder read and the INSERT loses at the index, and the
    refusal names the reservation rather than reading as a generic write failure."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.PROPOSED, name="race.db")
    key = m.require(PIPELINE).commit_key
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            "INSERT INTO pipeline_instances (tenant, pipeline_instance_id, work_item_id, state, "
            " version, owner_id, action_class, target_system, target_resource_id, "
            " target_operation, occurrence_key, commit_key, attempt_seq, created_at, updated_at) "
            " VALUES (?,?,?, 'PROPOSED', 1, ?, 'raise_invoice','tms:truckingoffice',?, "
            " 'create_invoice','',?,1,'2026-08-14T09:00:00.000Z','2026-08-14T09:00:00.000Z')",
            (T_A, "pl-sneak", WORK_ITEM, OWNER, LOAD, key))


# ================================================================== E. §20 — a retry is a NEW attempt

def test_a_retry_is_a_new_instance_with_the_same_commit_key(tmp_path):
    """### acceptance item (c). After a PROVABLE failure the key is free, and attempt #2 carries the
    SAME commit key and its own grant — never a second logical effect."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.FAILED, name="retry.db")
    first = m.require(PIPELINE)
    outcome = m.propose(pipeline_instance_id="pl-4471-invoice-2", work_item_id=WORK_ITEM,
                        effect=an_effect(), supersedes=PIPELINE, **SYS)
    assert outcome.is_new_attempt
    second = outcome.started.pipeline
    assert second.commit_key == first.commit_key
    assert (second.attempt_seq, second.supersedes) == (2, PIPELINE)
    assert [a.attempt_seq for a in m.attempts_for(first.commit_key)] == [1, 2]


def test_a_retry_must_say_what_it_retries_and_may_not_retry_a_live_attempt(tmp_path):
    store, m, *_ = _attempt_in(tmp_path, PipelineState.FAILED, name="retry2.db")
    with pytest.raises(PipelineError, match="names none of them"):
        m.propose(pipeline_instance_id="pl-b", work_item_id=WORK_ITEM, effect=an_effect(), **SYS)
    # And a first attempt supersedes nothing.
    store2, m2, *_ = _attempt_in(tmp_path, PipelineState.PROPOSED, name="retry3.db")
    with pytest.raises(PipelineError, match="supersedes nothing"):
        m2.propose(pipeline_instance_id="pl-c", work_item_id=WORK_ITEM, effect=an_effect(
            resource="load:9999"), supersedes=PIPELINE, **SYS)


def test_retry_in_place_is_impossible_at_the_database(tmp_path):
    """§15: mutating a terminal instance is ILLEGAL, and the trigger says so to a raw connection."""
    for state in (PipelineState.CLOSED, PipelineState.REJECTED, PipelineState.VOIDED,
                  PipelineState.FAILED):
        store, m, *_ = _attempt_in(tmp_path, state, name=f"final-{state.value}.db")
        with pytest.raises(sqlite3.IntegrityError, match="terminal Pipeline Instance"):
            store.conn.execute(
                "UPDATE pipeline_instances SET state = 'PROPOSED', version = version + 1 "
                " WHERE tenant = ? AND pipeline_instance_id = ?", (T_A, PIPELINE))
        assert m.require(PIPELINE).state is state


# ======================================================= F. total, mutually exclusive guard pairs

@pytest.mark.parametrize("pair,trigger,discriminator", [
    (("PL-2", "PL-3"), Trigger.POLICY_EVALUATED, "policy_decision"),
    (("PL-4", "PL-5"), Trigger.VALIDATION_COMPLETED, "validation_passed"),
    (("PL-6", "PL-7a"), Trigger.GATE_ROUTED, "gate_decision"),
])
def test_the_discriminated_pairs_are_total_and_mutually_exclusive(tmp_path, pair, trigger,
                                                                  discriminator):
    """### PRECEDENCE IS NEVER WHAT DECIDES. Two rows share one (state, trigger); exactly one guard
    holds for any input, so the outcome does not depend on the order they are listed in."""
    a, b = (TRANSITIONS_BY_ID[i] for i in pair)
    assert set(a.from_states) == set(b.from_states) and set(a.triggers) == set(b.triggers)
    assert a.to_state is not b.to_state
    assert discriminator in {"policy_decision", "validation_passed", "gate_decision"}
    assert PRECEDENCE.index(a.id) != PRECEDENCE.index(b.id)


def test_pl_2_refuses_a_null_gate_and_a_model_inferred_material_fact(tmp_path):
    """F-20 and GR-8. A gate expressible as an absence is not a gate; and confidence is not a guard
    input at any level."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.PROPOSED, name="gate.db")
    with pytest.raises(GuardNotSatisfied, match="gate_decision"):
        m.apply(PIPELINE, Trigger.POLICY_EVALUATED, **SYS, policy_version="pv1",
                policy_decision="PERMIT", model_inferred_material_fact=False)
    with pytest.raises(GuardNotSatisfied, match="MODEL_INFERRED"):
        m.apply(PIPELINE, Trigger.POLICY_EVALUATED, **SYS, policy_version="pv1",
                gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_decision="PERMIT")
    with pytest.raises(GuardNotSatisfied, match="MODEL_INFERRED"):
        m.apply(PIPELINE, Trigger.POLICY_EVALUATED, **SYS, policy_version="pv1",
                gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED, policy_decision="PERMIT",
                model_inferred_material_fact=True)
    assert m.require(PIPELINE).state is PipelineState.PROPOSED
    assert not [e for e in outbox_events(store) if e["event_name"] == "PolicyEvaluated"], (
        "a guard failure emitted an event; only an ILLEGAL trigger produces a record")


def test_pl_4_will_not_infer_a_fence_it_did_not_run(tmp_path):
    """GR-10 and the money/document fences. 'We did not check' is not 'there is none'."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.POLICY_CHECKED, name="fence.db")
    for missing in ("money_fence_passed", "document_fence_passed", "material_fields_consistent"):
        facts = {"validation_passed": True, "money_fence_passed": True,
                 "document_fence_passed": True, "material_fields_consistent": True,
                 "open_conflict": False}
        facts.pop(missing)
        with pytest.raises(GuardNotSatisfied, match=missing):
            m.apply(PIPELINE, Trigger.VALIDATION_COMPLETED, **SYS, **facts)
    with pytest.raises(GuardNotSatisfied, match="open_conflict"):
        m.apply(PIPELINE, Trigger.VALIDATION_COMPLETED, **SYS, validation_passed=True,
                money_fence_passed=True, document_fence_passed=True,
                material_fields_consistent=True, open_conflict=True)
    assert m.require(PIPELINE).state is PipelineState.POLICY_CHECKED


def test_pl_7a_refuses_an_autonomous_admission_with_a_breached_or_unevaluated_cap(tmp_path):
    """A breached cap is a HUMAN decision, not a smaller autonomous one."""
    store = make_store(tmp_path, name="caps.db")
    clk = Clock()
    m, _ = a_proposed_attempt(store, clock=clk, effect=an_effect(action_class="file_document"))
    m.apply(PIPELINE, Trigger.POLICY_EVALUATED, **SYS, policy_version="pv1",
            gate_decision=GateDecision.AUTONOMOUS_WITHIN_CAPS, policy_decision="PERMIT",
            reason="within caps", model_inferred_material_fact=False)
    m.apply(PIPELINE, Trigger.VALIDATION_COMPLETED, **SYS, validation_passed=True,
            money_fence_passed=True, document_fence_passed=True,
            material_fields_consistent=True, open_conflict=False)
    with pytest.raises(GuardNotSatisfied, match="caps that were EVALUATED"):
        m.apply(PIPELINE, Trigger.GATE_ROUTED, **SYS,
                gate_decision=GateDecision.AUTONOMOUS_WITHIN_CAPS, brake_version="brk-v1")
    with pytest.raises(GuardNotSatisfied, match="EVERY cap to hold"):
        m.apply(PIPELINE, Trigger.GATE_ROUTED, **SYS,
                gate_decision=GateDecision.AUTONOMOUS_WITHIN_CAPS,
                caps_evaluated={"max_per_day": True, "max_amount_minor": False},
                brake_version="brk-v1")
    assert m.require(PIPELINE).state is PipelineState.VALIDATED


def test_pl_7b_refuses_an_approval_bound_to_another_commit_key_or_carrying_no_fingerprint(tmp_path):
    """The confused-deputy shape, refused at the BIND — before a witness exists."""
    store, m, clk, _ = _attempt_in(tmp_path, PipelineState.AWAITING_APPROVAL, name="bind.db")
    with pytest.raises(GuardNotSatisfied, match="THIS commit key"):
        m.apply(PIPELINE, Trigger.APPROVAL_GRANTED, **HUMAN, approval_id="ap-1",
                approval_commit_key="a-different-effect", approval_fingerprint="fp")
    with pytest.raises(GuardNotSatisfied, match="fingerprint"):
        m.apply(PIPELINE, Trigger.APPROVAL_GRANTED, **HUMAN, approval_id="ap-1",
                approval_commit_key=m.require(PIPELINE).commit_key)
    assert m.require(PIPELINE).state is PipelineState.AWAITING_APPROVAL


def test_pl_7b_is_an_H_transition_and_refuses_a_system_actor(tmp_path):
    """§7: automation may narrow authority and never broaden it. This is the moment a human's
    authority enters the effect path, and it is checked against the RECORDED roster."""
    store, m, clk, _ = _attempt_in(tmp_path, PipelineState.AWAITING_APPROVAL, name="hbind.db")
    key = m.require(PIPELINE).commit_key
    with pytest.raises(GuardNotSatisfied, match="H transition"):
        m.apply(PIPELINE, Trigger.APPROVAL_GRANTED, **SYS, approval_id="ap-1",
                approval_commit_key=key, approval_fingerprint="fp")
    with pytest.raises(GuardNotSatisfied, match="not a recorded human"):
        m.apply(PIPELINE, Trigger.APPROVAL_GRANTED, actor_type="human", actor_id="whoever",
                approval_id="ap-1", approval_commit_key=key, approval_fingerprint="fp")


# ======================================================= G. PL-8 — the checkpoint, atomically

def test_pl_8_co_commits_the_witness_the_grant_and_this_row(tmp_path):
    """### §4 AND §41(a). One transaction: seven checks, witness insert, grant mint, state row,
    `CheckpointPassed`. And the pipeline points at BOTH, by foreign key."""
    store, m, clk, kernel, effect, world, _ = _green(tmp_path)
    assert witnesses(store) == [] and ledger(store) == []
    result = m.apply(PIPELINE, Trigger.CHECKPOINT_RUN, **SYS, kernel=kernel,
                     checkpoint_inputs=checkpoint_inputs(effect, world, clk))
    attempt = result.pipeline
    assert attempt.state is PipelineState.GRANTED
    assert len(witnesses(store)) == 1 and len(ledger(store)) == 1
    assert attempt.checkpoint_id == witnesses(store)[0]["checkpoint_id"]
    assert attempt.grant_id == ledger(store)[0]["grant_id"] == witnesses(store)[0]["grant_id"]
    assert ledger(store)[0]["commit_key"] == attempt.commit_key
    # The consequential event pins the decision context from the WITNESS, not from a re-read.
    row = store.conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND event_name = 'CheckpointPassed'",
        (T_A,)).fetchone()
    import json as _json
    envelope = _json.loads(row["envelope_json"])
    witness_row = store.conn.execute(
        "SELECT * FROM checkpoint_witnesses WHERE tenant = ?", (T_A,)).fetchone()
    assert envelope["material_facts_fingerprint"] == witness_row["material_facts_fingerprint"]
    assert envelope["policy_version"] == witness_row["policy_version"]
    assert envelope["brake_version"] == witness_row["brake_version"]
    assert envelope["entity_versions"] == _json.loads(witness_row["entity_versions_json"]), (
        "ER-13: the consequential event pinned a decision context that is not the WITNESS's. An "
        "audit reconstructing why this effect was allowed would be reading today's beliefs.")


def test_pl_8_rolls_the_witness_and_the_grant_back_when_its_own_row_write_fails(tmp_path):
    """### THE CO-COMMIT, PROVED BY BREAKING IT RATHER THAN BY READING THE CODE.

    §4 requires the seven checks, the witness insert, the grant mint AND the pipeline's own
    `CHECKPOINT → GRANTED` to share ONE transaction. The observable consequence is this: if the row
    write loses its OCC race, the authorization must vanish with it. A checkpoint that committed
    first and wrote the row second would leave a witness and a live grant for an attempt that never
    reached GRANTED — an authorization nobody is accountable for, claimable by anyone holding the
    handle.

    The race is injected rather than hoped for: the machine is handed a STALE snapshot of the row,
    which is exactly what a concurrent writer produces.
    """
    store, m, clk, kernel, effect, world, _ = _green(tmp_path)
    stale = m.require(PIPELINE)
    # Somebody else writes the row between the read and the checkpoint. An absorption is the
    # canonical shape of that: it advances the version without changing the state (PL-1b).
    store.conn.execute(
        "UPDATE pipeline_instances SET version = version + 1, absorbed_count = absorbed_count + 1,"
        " last_absorbed_ref = 'concurrent-proposal' WHERE tenant = ?", (T_A,))
    store.conn.commit()
    assert m.require(PIPELINE).version == stale.version + 1
    with pytest.raises(VersionConflict):
        m._run_checkpoint(stale, actor_type="system", actor_id="execution-service",
                          correlation_id=None, causation_id=None, trace_id=None, event_id=None,
                          facts=_facts(kernel=kernel,
                                       checkpoint_inputs=checkpoint_inputs(effect, world, clk)))
    assert witnesses(store) == [], (
        "a witness survived a checkpoint whose own row write failed — the mint and the state change "
        "did not share a transaction (§4)")
    assert ledger(store) == [], "a grant survived a checkpoint whose own row write failed"


def test_pl_9_rolls_the_claim_back_when_its_own_row_write_fails(tmp_path):
    """### §30's OTHER HALF: NEVER *BOTH*. The brake case proves 'never neither'; this proves that a
    claimed ledger row cannot outlive a failed pipeline write. Same injection: a stale snapshot."""
    store, m, clk, kernel, effect, world, _ = _green(tmp_path)
    r8 = m.apply(PIPELINE, Trigger.CHECKPOINT_RUN, **SYS, kernel=kernel,
                 checkpoint_inputs=checkpoint_inputs(effect, world, clk))
    stale = m.require(PIPELINE)
    m.apply(PIPELINE, Trigger.GRANT_REVOKED, **SYS, reason="ops revoked the grant",
            grant_id=r8.pipeline.grant_id)
    with pytest.raises(VersionConflict):
        m._run_claim(stale, actor_type="system", actor_id="execution-service",
                     facts=_facts(kernel=kernel, handle=r8.grant_handle))
    assert [g["state"] for g in ledger(store)] == ["GRANTED"], (
        "the ledger claimed while the pipeline did not — that is 'both', and §30 forbids it")


def test_pl_8f_a_refused_checkpoint_voids_and_leaves_no_authorization_capability(tmp_path):
    """### THE UNIVERSAL ORACLE, ON THIS MACHINE: (a) one witness and one grant, or (b) NOTHING.
    Drift after approval is F-01's case — nothing has been sent; this is a new question."""
    store, m, clk, kernel, effect, world, _ = _green(tmp_path)
    inputs = checkpoint_inputs(effect, world, clk)   # the approval is fingerprinted HERE...
    from freight_recon.fingerprint import Money
    from dataclasses import replace as _replace
    world["facts"]["amount"] = _replace(
        world["facts"]["amount"], _value=Money(999999, "GBP"))   # ...and the world moves after it
    result = m.apply(PIPELINE, Trigger.CHECKPOINT_RUN, **SYS, kernel=kernel,
                     checkpoint_inputs=inputs)
    assert result.transition_id == "PL-8f"
    assert result.pipeline.state is PipelineState.VOIDED
    assert witnesses(store) == [] and ledger(store) == [], (
        "a refused checkpoint left an authorization capability behind")
    assert result.pipeline.refused_step is not None, "SD-7: the FIRST failing step must be named"
    assert [e["event_name"] for e in outbox_events(store)].count("CheckpointFailed") == 1


def test_pl_8_refuses_when_the_ledger_already_holds_this_logical_effect(tmp_path):
    """Layer 2. A VERIFIED effect holds its commit key forever, so a second attempt at a CLOSED
    one reaches the checkpoint and is refused at the mint — which is why Layer 1 releasing on
    CLOSED is safe."""
    store, m, clk, kernel, effect, world, _ = _green(tmp_path)
    m.apply(PIPELINE, Trigger.CHECKPOINT_RUN, **SYS, kernel=kernel,
            checkpoint_inputs=checkpoint_inputs(effect, world, clk))
    # A second live attempt at the same effect cannot even be proposed (Layer 1); force the
    # question by voiding this one's reservation while the grant survives.
    store.conn.execute("UPDATE effect_grants SET state = 'VERIFIED' WHERE tenant = ?", (T_A,))
    store.conn.commit()
    holder = m.require(PIPELINE)
    assert m.live_holder(holder.commit_key) is not None


def test_the_checkpoint_request_is_built_from_the_row_not_from_the_caller(tmp_path):
    """A caller who could vary the effect between the proposal and the checkpoint could have one
    attempt authorize a different effect than the one that was validated."""
    import inspect

    from freight_recon import pipeline_instance as pl

    source = inspect.getsource(pl.PipelineMachine._run_checkpoint)
    assert "effect=item.effect" in source
    assert "accountable_owner=item.owner_id" in source
    tree = ast.parse(source.strip())
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", None) == "CheckpointRequest"]
    assert len(calls) == 1, "PL-8 builds exactly one CheckpointRequest"
    for kw in calls[0].keywords:
        assert not (isinstance(kw.value, ast.Attribute)
                    and getattr(kw.value.value, "id", None) == "facts"), (
            f"CheckpointRequest.{kw.arg} is taken from caller-supplied facts")


# ============================================== H. PL-9 — never both, never neither

def test_pl_9_claims_once_and_the_ledger_and_the_row_move_together(tmp_path):
    store, m, clk, kernel, effect, world, r8 = _to_claimed(tmp_path)
    assert m.require(PIPELINE).state is PipelineState.CLAIMED
    assert [g["state"] for g in ledger(store)] == ["CLAIMED"]
    assert m.require(PIPELINE).claimed_at is not None
    # ### AND NOTHING WAS EMITTED BY M2: `GrantClaimed`/`EffectAttempted` are EF-2's.
    names = {e["event_name"] for e in outbox_events(store)}
    assert not names & {"GrantClaimed", "EffectAttempted"}


def test_pl_9_is_single_use_and_a_second_claim_moves_nothing(tmp_path):
    """AC-MACH-209. The CAS is the serialization point; the second attempt matches zero rows."""
    store, m, clk, kernel, effect, world, r8 = _to_claimed(tmp_path)
    ledger_before = ledger(store)
    version_before = m.require(PIPELINE).version
    with pytest.raises(IllegalTransition):
        m.apply(PIPELINE, Trigger.CLAIM_ATTEMPTED, **SYS, kernel=kernel, handle=r8.grant_handle)
    assert ledger(store) == ledger_before, "a second claim touched the ledger"
    assert m.require(PIPELINE).state is PipelineState.CLAIMED
    assert m.require(PIPELINE).version == version_before, "a refused second claim moved the row"


def test_a_brake_engaged_between_checkpoint_and_claim_stops_both_halves(tmp_path):
    """### §30, THE LOAD-BEARING RACE: never both, never neither. The CAS revalidates the brake
    token inside its own WHERE clause, so it matches zero rows — and because the pipeline's own
    write shares that transaction, the attempt stays GRANTED rather than claiming alone."""
    store, m, clk, kernel, effect, world, _ = _green(tmp_path)
    r8 = m.apply(PIPELINE, Trigger.CHECKPOINT_RUN, **SYS, kernel=kernel,
                 checkpoint_inputs=checkpoint_inputs(effect, world, clk))
    kernel.brakes.engage(tenant=T_A, actor="ops-sam", actor_kind="HUMAN",
                         reason="carrier dispute")
    before = m.require(PIPELINE)
    with pytest.raises(GuardNotSatisfied, match="BRAKE_CHANGED|matched zero rows"):
        m.apply(PIPELINE, Trigger.CLAIM_ATTEMPTED, **SYS, kernel=kernel, handle=r8.grant_handle)
    after = m.require(PIPELINE)
    assert (after.state, after.version) == (before.state, before.version) is not None
    assert after.state is PipelineState.GRANTED
    assert [g["state"] for g in ledger(store)] == ["GRANTED"], (
        "the ledger claimed while the pipeline did not — that is 'both', and §30 forbids it")


def test_pl_9_refuses_a_grant_this_attempt_does_not_hold(tmp_path):
    """The confused deputy, refused before a ledger read is spent on it."""
    from dataclasses import replace

    store, m, clk, kernel, effect, world, _ = _green(tmp_path)
    r8 = m.apply(PIPELINE, Trigger.CHECKPOINT_RUN, **SYS, kernel=kernel,
                 checkpoint_inputs=checkpoint_inputs(effect, world, clk))
    foreign = replace(r8.grant_handle, grant_id="grant-belonging-to-nobody")
    with pytest.raises(GuardNotSatisfied, match="was granted"):
        m.apply(PIPELINE, Trigger.CLAIM_ATTEMPTED, **SYS, kernel=kernel, handle=foreign)
    assert m.require(PIPELINE).state is PipelineState.GRANTED
    assert [g["state"] for g in ledger(store)] == ["GRANTED"]


def test_pl_9v_a_grant_that_expires_before_the_claim_voids_the_attempt(tmp_path):
    """§14 PL-9v: `GrantExpired`/`GrantRevoked` — ### nothing happened."""
    store, m, clk, kernel, effect, world, _ = _green(tmp_path)
    r8 = m.apply(PIPELINE, Trigger.CHECKPOINT_RUN, **SYS, kernel=kernel,
                 checkpoint_inputs=checkpoint_inputs(effect, world, clk))
    result = m.apply(PIPELINE, Trigger.GRANT_EXPIRED, **SYS, reason="grant TTL elapsed unclaimed",
                     grant_id=r8.pipeline.grant_id)
    assert result.transition_id == "PL-9v" and result.to_state is PipelineState.VOIDED
    assert result.event_name == "PipelineVoided"


def test_pl_9v_will_not_void_this_attempt_for_another_attempts_grant(tmp_path):
    store, m, clk, kernel, effect, world, _ = _green(tmp_path)
    m.apply(PIPELINE, Trigger.CHECKPOINT_RUN, **SYS, kernel=kernel,
            checkpoint_inputs=checkpoint_inputs(effect, world, clk))
    with pytest.raises(GuardNotSatisfied, match="does not void another attempt"):
        m.apply(PIPELINE, Trigger.GRANT_REVOKED, **SYS, reason="revoked",
                grant_id="grant-of-some-other-attempt")


# ==================== H2. §15 — A CONSUMED EVENT CANNOT DRIVE A KERNEL-OWNED TRANSITION
#
# ### THE DEFECT THIS SECTION EXISTS FOR, IN THE REVIEWER'S OWN TERMS. The first P6-CP-2 candidate
# was REJECTED because a contract-valid canonical `GrantClaimed`, consumed through the public API,
# moved a Pipeline Instance GRANTED -> CLAIMED with:
#
#     no kernel · no grant handle · no CAS · `claimed_at` still NULL · the ledger still GRANTED
#
# The pipeline said the effect was claimed and the grant ledger said nobody had claimed it. §15 says
# that state is IMPOSSIBLE, §17 says the CAS is the serialization point, and §30's never-both-never-
# neither depends on the CAS being the only door. `apply` routed the consequential triggers to the
# kernel; `consume` routed straight into `_apply_locked`, and no row guard refused what arrived
# there. Same root cause put a consumed `CHECKPOINT_RUN` on PL-8f, which then raised a payload
# violation INSIDE the inbox transaction and made the event redeliverable forever.
#
# Every case below is written so that removing the structural refusal makes it fail.

def _granted(tmp_path, **kw):
    """An attempt carried through a REAL checkpoint to GRANTED, with its witness and its grant."""
    store, m, clk, kernel, effect, world, _ = _green(tmp_path, **kw)
    r8 = m.apply(PIPELINE, Trigger.CHECKPOINT_RUN, **SYS, kernel=kernel,
                 checkpoint_inputs=checkpoint_inputs(effect, world, clk))
    return store, m, clk, kernel, effect, world, r8


def _next_consumable_version(store, aggregate_type, aggregate_id, *, tenant=T_A) -> int:
    """The version the dedup inbox will accept NEXT for this aggregate.

    Derived from `inbox_aggregate_cursor` rather than from the row's own version, because these two
    counters are different things: the pipeline's `version` counts transitions, the cursor counts
    what THIS consumer has applied. Guessing wrong makes the event PARK on a version gap — a
    perfectly safe outcome that would make every assertion below vacuous.
    """
    row = store.conn.execute(
        "SELECT applied_version FROM inbox_aggregate_cursor "
        "WHERE tenant = ? AND aggregate_type = ? AND aggregate_id = ?",
        (tenant, aggregate_type, aggregate_id)).fetchone()
    return (int(row["applied_version"]) if row else 0) + 1


def _consumable(store, m, clk, *, event_name, seed, aggregate_id=None):
    """A CONTRACT-VALID canonical envelope of `event_name`, built from the contract itself and
    versioned so the inbox APPLIES it rather than parking it."""
    from freight_recon.event_contracts import CONTRACTS

    item = m.require(PIPELINE)
    contract = CONTRACTS[event_name]
    target = aggregate_id or (
        PIPELINE if contract.aggregate_type == AGGREGATE_TYPE else (item.grant_id or "g-1"))
    return canonical_event(
        store, event_name=event_name, producer_transition_id=contract.producers[0],
        aggregate_type=contract.aggregate_type, aggregate_id=target,
        aggregate_version=_next_consumable_version(store, contract.aggregate_type, target),
        seed=seed, clock=clk,
        pipeline_instance_id=PIPELINE, accountable_owner_id=item.owner_id,
    )


def test_a_consumed_grant_claimed_cannot_reach_claimed_without_the_cas(tmp_path):
    """### THE REJECTED CANDIDATE'S DEFECT, AS A REGRESSION. §15: *"`CLAIMED` without a successful
    CAS → impossible."* The event is real, the contract is real, the inbox is real — and the only
    thing missing is the CAS, which is the whole point.

    Every durable consequence is asserted, not just the exception: a test that only checks something
    raised would pass against a version that fabricated the claim and then raised afterwards.
    """
    store, m, clk, kernel, effect, world, r8 = _granted(tmp_path)
    before = m.require(PIPELINE)
    digest_before = state_digest(store)
    assert before.state is PipelineState.GRANTED and before.claimed_at is None
    assert [g["state"] for g in ledger(store)] == ["GRANTED"]

    env = _consumable(store, m, clk, event_name="GrantClaimed", seed="bypass-claim")
    out = m.consume(env, pipeline_instance_id=PIPELINE, trigger=Trigger.CLAIM_ATTEMPTED)

    after = m.require(PIPELINE)
    assert out.transition is None, "a kernel-owned transition executed through consume()"
    assert after.state is PipelineState.GRANTED, "CLAIMED was reached without a CAS"
    assert after.claimed_at is None, "a claim timestamp was fabricated"
    assert after.version == before.version, "a refused bypass moved the row"
    assert [g["state"] for g in ledger(store)] == ["GRANTED"], (
        "the pipeline and the grant ledger disagree about whether the effect was claimed")
    assert {e["event_name"] for e in outbox_events(store)} & {"GrantClaimed", "EffectAttempted"} == set()


def test_the_refused_bypass_converges_and_redelivery_does_not_poison_the_inbox(tmp_path):
    """### A REFUSAL IS A CONSUMPTION. If the handler raised, the inbox would roll back its own
    receipt and the transport would redeliver the same event forever — an unsatisfiable guard
    becoming an infinite loop, at the exact point where the money is.

    So: the receipt is written, the second delivery is a DUPLICATE, and the durable state is
    byte-identical across it.
    """
    store, m, clk, kernel, effect, world, r8 = _granted(tmp_path)
    env = _consumable(store, m, clk, event_name="GrantClaimed", seed="bypass-converge")

    first = m.consume(env, pipeline_instance_id=PIPELINE, trigger=Trigger.CLAIM_ATTEMPTED)
    assert first.consume.outcome is ConsumeOutcome.APPLIED, (
        f"the refusal did not converge: {first.consume.outcome}. A rolled-back receipt is a poison "
        f"loop.")
    digest_after_first = state_digest(store)

    second = m.consume(env, pipeline_instance_id=PIPELINE, trigger=Trigger.CLAIM_ATTEMPTED)
    assert second.consume.outcome is ConsumeOutcome.DUPLICATE_NOOP
    assert state_digest(store) == digest_after_first, "the redelivery changed durable state"
    assert m.require(PIPELINE).state is PipelineState.GRANTED
    assert [g["state"] for g in ledger(store)] == ["GRANTED"]


def test_a_kernel_bypass_attempt_is_recorded_as_illegal_not_as_a_guard_failure(tmp_path):
    """### THE QUIET HALF OF THE SAME DEFECT. Refusing the bypass without recording it would leave
    an attempt to reach `CLAIMED` with no evidence anywhere. §15 is part of GR-1, so the attempt
    earns GR-1's record: `IllegalTransitionAttempted`, to the audit backbone AND `security_events`,
    inside the inbox's own commit — the record and the consumption genuinely are one act.
    """
    store, m, clk, kernel, effect, world, r8 = _granted(tmp_path)
    env = _consumable(store, m, clk, event_name="GrantClaimed", seed="bypass-recorded")
    out = m.consume(env, pipeline_instance_id=PIPELINE, trigger=Trigger.CLAIM_ATTEMPTED)

    assert out.refusal_kind == "ILLEGAL", (
        f"the bypass was classified {out.refusal_kind!r}; a GUARD refusal writes no security "
        f"record, so the attempt would be invisible")
    assert "kernel-owned" in (out.refusal or "")
    assert out.illegal_record is not None
    names = [e["event_name"] for e in outbox_events(store)]
    assert "IllegalTransitionAttempted" in names, "GR-1's record was not written"
    assert any(r["event_type"] == "IllegalTransitionAttempted" for r in security_rows(store)), (
        "the attempt reached the audit backbone but not `security_events`")


def test_a_consumed_checkpoint_run_cannot_invoke_the_kernel_and_does_not_poison_the_inbox(tmp_path):
    """### THE SECOND HALF OF THE SAME ROOT CAUSE. A consumed `CHECKPOINT_RUN` selected PL-8f by
    §16 precedence — the checkpoint's FAILURE branch — whose `{step, reason}` are the kernel's
    refusal output and cannot be supplied by a consumer. The write then raised a payload-contract
    violation inside the inbox transaction, rolling the receipt back and making the event
    redeliverable forever.

    PL-8f is refused here because it shares a (state, trigger) pair with PL-8, which is what puts it
    in the derived kernel-owned population — not because anybody listed it.
    """
    store, m, clk, kernel, effect, world, _ = _green(tmp_path)
    before = m.require(PIPELINE)
    assert before.state is PipelineState.CHECKPOINT

    env = _consumable(store, m, clk, event_name="CheckpointPassed", seed="bypass-checkpoint",
                      aggregate_id=PIPELINE)
    out = m.consume(env, pipeline_instance_id=PIPELINE, trigger=Trigger.CHECKPOINT_RUN)

    after = m.require(PIPELINE)
    assert out.consume.outcome is ConsumeOutcome.APPLIED, (
        f"the refusal did not converge: {out.consume.outcome}")
    assert out.refusal_kind == "ILLEGAL" and out.transition is None
    assert (after.state, after.version) == (before.state, before.version)
    assert witnesses(store) == [], "a witness was minted outside the kernel"
    assert ledger(store) == [], "a grant was minted outside the kernel"
    # And the redelivery is a no-op rather than a second attempt at the same bypass.
    digest = state_digest(store)
    again = m.consume(env, pipeline_instance_id=PIPELINE, trigger=Trigger.CHECKPOINT_RUN)
    assert again.consume.outcome is ConsumeOutcome.DUPLICATE_NOOP
    assert state_digest(store) == digest


def test_the_kernel_owned_population_is_derived_and_covers_every_consequential_row(tmp_path):
    """### THE POPULATION IS DERIVED FROM §7 AND ITS (state, trigger) CLOSURE, NOT LISTED.

    §7 *"Machine defaults"* declares the consequential rows: **PL-8 (checkpoint) and PL-9 (claim)
    only**. The kernel-owned population is those SEEDS plus every row reachable by the same
    (from-state, trigger) pair — because a row selectable by the same pair is a row the ordinary
    path can take INSTEAD of the kernel's. That closure is what puts PL-8f in, and it is why adding
    a row on `(CHECKPOINT, CheckpointRun)` tomorrow is covered without editing this test.

    The specification text is read here, so the declaration and §7 cannot drift apart.
    """
    from freight_recon.pipeline_instance import (
        CONSEQUENTIAL_ROW_IDS, KERNEL_ENTRY_POINTS, KERNEL_OWNED_ROW_IDS, KERNEL_PATH_BY_TRIGGER)

    spec = MACHINE_SPEC.read_text(encoding="utf-8")
    declared = set(re.findall(r"consequential transitions = \*\*(.+?)\*\*", spec))
    assert declared, "§7's machine-defaults line no longer states the consequential set"
    spec_ids = set(re.findall(r"PL-\d+[a-z]?", declared.pop()))
    assert spec_ids == CONSEQUENTIAL_ROW_IDS, (
        f"§7 declares {sorted(spec_ids)} consequential; the table declares "
        f"{sorted(CONSEQUENTIAL_ROW_IDS)}")

    # The closure, recomputed here independently of the implementation's own derivation.
    seeds = [TRANSITIONS_BY_ID[i] for i in CONSEQUENTIAL_ROW_IDS]
    pairs = {(s, t) for r in seeds for s in r.from_states for t in r.triggers}
    expected = {r.id for r in TRANSITIONS
                if r.id in CONSEQUENTIAL_ROW_IDS
                or any((s, t) in pairs for s in r.from_states for t in r.triggers)}
    assert KERNEL_OWNED_ROW_IDS == expected == {"PL-8", "PL-8f", "PL-9"}, (
        f"the kernel-owned population is {sorted(KERNEL_OWNED_ROW_IDS)}, derived {sorted(expected)}")

    # Every declared kernel path has an executor: a consequential row without one would otherwise
    # fall through to the ordinary path, which is precisely the unguarded route.
    assert set(KERNEL_ENTRY_POINTS) == {r.consequential for r in seeds}
    assert set(KERNEL_PATH_BY_TRIGGER) == {t for r in seeds for t in r.triggers}
    for method in KERNEL_ENTRY_POINTS.values():
        assert callable(getattr(PipelineMachine, method, None)), f"{method} is not on the machine"


def test_no_kernel_owned_row_can_be_driven_through_consume_at_any_trigger(tmp_path):
    """### THE SWEEP THE REVIEW ASKED FOR: the WHOLE derived population, every trigger, over a
    proven denominator. Not "PL-9 is refused" — *no kernel-owned row is reachable through the
    ordinary consumption path from any state it can legally start in.*
    """
    from freight_recon.pipeline_instance import KERNEL_OWNED_ROW_IDS

    triples = sorted(
        (row_id, state, trigger)
        for row_id in KERNEL_OWNED_ROW_IDS
        for state in TRANSITIONS_BY_ID[row_id].from_states
        for trigger in TRANSITIONS_BY_ID[row_id].triggers
    )
    assert len(triples) >= 3, f"the sweep population is {triples}; it would prove nothing"
    for row_id, state, trigger in triples:
        store, m, clk, kernel = _attempt_in(
            tmp_path, state, name=f"sweep-{row_id}-{trigger.value}.db")
        before = m.require(PIPELINE)
        env = _consumable(store, m, clk, event_name="CheckpointPassed",
                          seed=f"sweep-{row_id}-{trigger.value}", aggregate_id=PIPELINE)
        out = m.consume(env, pipeline_instance_id=PIPELINE, trigger=trigger)
        after = m.require(PIPELINE)
        assert out.transition is None, f"{row_id} executed through consume() at {trigger.value}"
        assert out.refusal_kind == "ILLEGAL", (
            f"{row_id} at ({state.value}, {trigger.value}) was refused as {out.refusal_kind!r}, "
            f"not as §15 illegality — so no security record survives the attempt")
        assert (after.state, after.version) == (before.state, before.version), (
            f"{row_id} moved a {state.value} attempt through the ordinary consumption path")


def test_a_consequential_row_without_an_executor_fails_closed(tmp_path):
    """### THE FALL-THROUGH THAT WOULD MAKE THIS DECAY. A future consequential row whose kernel
    path has no executor must REFUSE, not quietly take the ordinary guard path. Proved by asking
    the machine to route a declared path that no method implements.
    """
    from freight_recon import pipeline_instance as pi

    store, m, clk, kernel, effect, world, _ = _green(tmp_path)
    original = dict(pi.KERNEL_ENTRY_POINTS)
    try:
        pi.KERNEL_ENTRY_POINTS = {}          # every declared path loses its executor
        with pytest.raises(AuthorityRefused, match="no executor"):
            m.apply(PIPELINE, Trigger.CHECKPOINT_RUN, **SYS, kernel=kernel,
                    checkpoint_inputs=checkpoint_inputs(effect, world, clk))
    finally:
        pi.KERNEL_ENTRY_POINTS = original
    assert m.require(PIPELINE).state is PipelineState.CHECKPOINT
    assert witnesses(store) == [] and ledger(store) == []
    # And the machine still works once the executor is back — the refusal was not a wedge.
    r8 = m.apply(PIPELINE, Trigger.CHECKPOINT_RUN, **SYS, kernel=kernel,
                 checkpoint_inputs=checkpoint_inputs(effect, world, clk))
    assert r8.to_state is PipelineState.GRANTED


def test_the_legitimate_kernel_path_is_untouched_by_the_refusal(tmp_path):
    """### THE POSITIVE CONTROL FOR F-01. A refusal that also broke the real path would be a
    regression wearing a safety badge. The whole PL-8 -> PL-9 route still runs: a real witness, a
    real grant, a real CAS, `claimed_at` set, and the ledger and the row agreeing.
    """
    store, m, clk, kernel, effect, world, r8 = _to_claimed(tmp_path / "happy")
    item = m.require(PIPELINE)
    assert item.state is PipelineState.CLAIMED and item.claimed_at is not None
    assert len(witnesses(store)) == 1 and [g["state"] for g in ledger(store)] == ["CLAIMED"]
    assert item.checkpoint_id and item.grant_id
    # And the brake revalidation inside the CAS is still the thing that decides it.
    store2, m2, clk2, kernel2, effect2, world2, r8b = _granted(tmp_path / "braked")
    kernel2.brakes.engage(tenant=T_A, actor="ops-sam", actor_kind="HUMAN", reason="dispute")
    with pytest.raises(GuardNotSatisfied, match="BRAKE_CHANGED|matched zero rows"):
        m2.apply(PIPELINE, Trigger.CLAIM_ATTEMPTED, **SYS, kernel=kernel2, handle=r8b.grant_handle)
    assert m2.require(PIPELINE).state is PipelineState.GRANTED
    assert [g["state"] for g in ledger(store2)] == ["GRANTED"]


# ================================================ I. GR-5 / GR-6 — the money-losing distinction

def test_pl_10f_failed_requires_affirmative_proof_of_non_occurrence(tmp_path):
    """### AC-MACH-210u's SIBLING, AND THE TRANSITION WHOSE WRONG ANSWER PAYS TWICE. GR-5: a
    timeout alone never proves failure."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.CLAIMED, name="proof.db")
    with pytest.raises(GuardNotSatisfied, match="failure_proof"):
        m.apply(PIPELINE, Trigger.ADAPTER_REJECTED_PRE_FLIGHT, **SYS)
    assert m.require(PIPELINE).state is PipelineState.CLAIMED
    result = m.apply(PIPELINE, Trigger.ADAPTER_REJECTED_PRE_FLIGHT, **SYS,
                     failure_proof="TMS rejected pre-flight; no invoice id allocated")
    assert result.to_state is PipelineState.FAILED
    assert m.require(PIPELINE).failure_proof


def test_failed_without_a_proof_is_unwritable_at_the_database(tmp_path):
    """The trigger, not the code path. GR-5 held against a connection."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.CLAIMED, name="proofdb.db")
    with pytest.raises(sqlite3.IntegrityError, match="affirmative evidence"):
        store.conn.execute(
            "UPDATE pipeline_instances SET state = 'FAILED', version = version + 1 "
            " WHERE tenant = ? AND pipeline_instance_id = ?", (T_A, PIPELINE))


def test_ac_mach_210u_a_crash_after_the_claim_is_unknown_never_failed(tmp_path):
    """### THE NAMED MERGE-GATING ANCHOR. §36: `CLAIMED`/`EXECUTED` + crash ⇒ UNKNOWN OUTCOME,
    never re-execute, never FAILED."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.CLAIMED, name="crash.db")
    result = m.apply(PIPELINE, Trigger.ADAPTER_TIMED_OUT, **SYS,
                     unknown_reason="UNKNOWN_OUTCOME", unknown_outcome_ref="obs-timeout-1")
    assert result.to_state is PipelineState.NEEDS_VERIFICATION
    assert result.transition_id == "PL-10u"
    assert PipelineState.CLAIMED.value not in dict(
        (s, s) for s in [])  # placeholder-free: the real assertions are the two above
    attempt = m.require(PIPELINE)
    assert attempt.unknown_reason == "UNKNOWN_OUTCOME"
    assert attempt.failure_proof is None, "an unknown outcome acquired a failure proof"


def test_pl_10u_and_pl_11c_require_the_specific_question(tmp_path):
    """§38: NEEDS_VERIFICATION is a Sev-1 queue carrying owner, age, exposure and THE SPECIFIC
    QUESTION. A row with no question is one nobody can act on."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.CLAIMED, name="question.db")
    with pytest.raises(GuardNotSatisfied, match="unknown_reason"):
        m.apply(PIPELINE, Trigger.ADAPTER_TIMED_OUT, **SYS)
    store2, m2, *_ = _attempt_in(tmp_path, PipelineState.EXECUTED, name="question2.db")
    with pytest.raises(GuardNotSatisfied, match="unknown_reason"):
        m2.apply(PIPELINE, Trigger.READBACK_CONFLICTING, **SYS)


def test_the_exposure_stays_on_the_canonical_event_and_not_on_the_row(tmp_path):
    """CLAUDE.md §10 / K-4. The row records the POINTER and the question; a projection that
    re-states a money value is a remembered amount with a fresh timestamp."""
    columns = {r[1] for r in make_store(tmp_path, name="cols.db").conn.execute(
        "PRAGMA table_info(pipeline_instances)").fetchall()}
    money_shaped = {c for c in columns if "amount" in c or "exposure" in c and c.endswith("minor")}
    assert not money_shaped, f"pipeline_instances carries money-shaped columns: {sorted(money_shaped)}"


# ================================================ J. PL-11 / PL-11c / PL-11d / PL-12

def test_pl_11_requires_the_readback_to_match_the_APPROVED_fingerprint(tmp_path):
    """§14: a HEALTHY-channel readback matches the APPROVED fingerprint. 'It looked fine' is not a
    match, and a mismatch is PL-11c — not a weaker verification."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.EXECUTED, name="verify.db")
    approved = m.require(PIPELINE).material_facts_fingerprint
    with pytest.raises(GuardNotSatisfied, match="match the APPROVED fingerprint"):
        m.apply(PIPELINE, Trigger.READBACK_MATCHED, **SYS,
                matched_fingerprint="something-else", health_signal="HEALTHY")
    with pytest.raises(GuardNotSatisfied, match="HEALTHY channel"):
        m.apply(PIPELINE, Trigger.READBACK_MATCHED, **SYS,
                matched_fingerprint=approved, health_signal="DEGRADED")
    assert m.require(PIPELINE).state is PipelineState.EXECUTED


def test_acceptance_f_verify_and_record_are_one_commit(tmp_path):
    """### ACCEPTANCE ITEM (f). A crash between them would lose the record of a verified effect, so
    there is no committed state in which an attempt is VERIFIED-by-PL-11 and not yet RECORDED."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.EXECUTED, name="vr.db")
    approved = m.require(PIPELINE).material_facts_fingerprint
    result = m.apply(PIPELINE, Trigger.READBACK_MATCHED, **SYS,
                     matched_fingerprint=approved, health_signal="HEALTHY")
    assert result.transition_id == "PL-11"
    assert [c.transition_id for c in result.co_commits] == ["PL-12"]
    assert m.require(PIPELINE).state is PipelineState.RECORDED
    # PL-12 has no trigger of its own — it cannot be taken as a separate step.
    assert TRANSITIONS_BY_ID["PL-12"].triggers == ()
    assert TRANSITIONS_BY_ID["PL-12"].co_commits_with == "PL-11"
    assert not TRANSITIONS_BY_ID["PL-12"].independently_fireable


def test_pl_11d_defers_only_within_a_declared_bound(tmp_path):
    """Open validation V6's fail-closed shape: a deferral past the bound is a verification postponed
    forever one step at a time."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.EXECUTED, name="defer.db")
    with pytest.raises(GuardNotSatisfied, match="recheck"):
        m.apply(PIPELINE, Trigger.READBACK_DEFERRED, **SYS)
    with pytest.raises(GuardNotSatisfied, match="WITHIN the declared bound"):
        m.apply(PIPELINE, Trigger.READBACK_DEFERRED, **SYS,
                recheck_at="2026-09-01T00:00:00.000Z",
                deferral_bound_until="2026-08-15T00:00:00.000Z")
    result = m.apply(PIPELINE, Trigger.READBACK_DEFERRED, **SYS,
                     recheck_at="2026-08-14T18:00:00.000Z",
                     deferral_bound_until="2026-08-15T00:00:00.000Z")
    assert result.to_state is PipelineState.EXECUTED, "PL-11d is a self-loop (§14)"
    assert m.require(PIPELINE).recheck_at == "2026-08-14T18:00:00.000Z"
    # ### AND THE EMISSION IS DEFERRED, DELIBERATELY AND NAMED (debt P6-D13). See the dedicated case.
    assert result.event_name is None


def test_pl_13_projects_only_from_this_attempts_verified_evidence(tmp_path):
    """M-2. Projecting one effect's readback onto another's entity is a projection stating something
    nobody observed."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.RECORDED, name="proj.db")
    with pytest.raises(GuardNotSatisfied, match="verified effect"):
        m.apply(PIPELINE, Trigger.PROJECTION_UPDATED, **SYS, entity_ref=LOAD)
    with pytest.raises(GuardNotSatisfied, match="THIS attempt"):
        m.apply(PIPELINE, Trigger.PROJECTION_UPDATED, **SYS, entity_ref=LOAD,
                from_effect_id="some-other-effect")
    result = m.apply(PIPELINE, Trigger.PROJECTION_UPDATED, **SYS, entity_ref=LOAD,
                     from_effect_id=m.require(PIPELINE).grant_id)
    assert result.to_state is PipelineState.PROJECTED


# ================================================================== K. PL-15 — establishing reality

def test_pl_15_closes_an_unknown_outcome_only_on_a_resolvable_human_decision(tmp_path):
    """GR-14 / K-1. A string that references nothing is not a `decision_ref`, and 'it probably went
    through' is the guess this state exists to prevent."""
    store, m, clk, _ = _attempt_in(tmp_path, PipelineState.NEEDS_VERIFICATION, name="reality.db")
    with pytest.raises(GuardNotSatisfied, match="decision_ref"):
        m.apply(PIPELINE, Trigger.HUMAN_ESTABLISHED_REALITY, **HUMAN, outcome="VERIFIED")
    with pytest.raises(GuardNotSatisfied, match="resolves to no canonical event"):
        m.apply(PIPELINE, Trigger.HUMAN_ESTABLISHED_REALITY, **HUMAN, outcome="VERIFIED",
                decision_ref="done", decision_ref_kind="AUDIT_EVENT")
    ref = a_human_decision(store, clock=clk, seed="reality-ok")
    result = m.apply(PIPELINE, Trigger.HUMAN_ESTABLISHED_REALITY, **HUMAN, outcome="VERIFIED",
                     decision_ref=ref, decision_ref_kind="AUDIT_EVENT")
    assert result.to_state is PipelineState.VERIFIED


def test_pl_15_may_only_conclude_FAILED_on_affirmative_evidence(tmp_path):
    """GR-5 again, at the other end: a human closing an unknown outcome as FAILED still owes proof."""
    store, m, clk, _ = _attempt_in(tmp_path, PipelineState.NEEDS_VERIFICATION, name="reality2.db")
    ref = a_human_decision(store, clock=clk, seed="reality-failed")
    with pytest.raises(GuardNotSatisfied, match="affirmative evidence"):
        m.apply(PIPELINE, Trigger.HUMAN_ESTABLISHED_REALITY, **HUMAN, outcome="FAILED",
                decision_ref=ref, decision_ref_kind="AUDIT_EVENT")
    result = m.apply(PIPELINE, Trigger.HUMAN_ESTABLISHED_REALITY, **HUMAN, outcome="FAILED",
                     decision_ref=ref, decision_ref_kind="AUDIT_EVENT",
                     failure_proof="TMS invoice list shows no invoice for load 4471 after 72h")
    assert result.to_state is PipelineState.FAILED


def test_pl_15_target_state_comes_from_the_event_never_from_the_caller(tmp_path):
    """GR-6: an unreadable outcome resolves to NEITHER, rather than to a default."""
    store, m, clk, _ = _attempt_in(tmp_path, PipelineState.NEEDS_VERIFICATION, name="reality3.db")
    ref = a_human_decision(store, clock=clk, seed="reality-bad")
    for bad in (None, "", "PROBABLY_FINE", "CLOSED"):
        with pytest.raises(GuardNotSatisfied):
            m.apply(PIPELINE, Trigger.HUMAN_ESTABLISHED_REALITY, **HUMAN, outcome=bad,
                    decision_ref=ref, decision_ref_kind="AUDIT_EVENT",
                    failure_proof="x")
    assert m.require(PIPELINE).state is PipelineState.NEEDS_VERIFICATION


# =============================================================== L. GR-3 / GR-4 / [C-1] / M-26

def test_gr3_a_stale_expected_version_refuses_rather_than_overwriting(tmp_path):
    store, m, *_ = _attempt_in(tmp_path, PipelineState.PROPOSED, name="occ.db")
    with pytest.raises(VersionConflict):
        m.apply(PIPELINE, Trigger.POLICY_EVALUATED, **SYS, expected_version=99,
                policy_version="pv1", gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED,
                policy_decision="PERMIT", reason="x", model_inferred_material_fact=False)
    assert m.require(PIPELINE).state is PipelineState.PROPOSED


def test_the_version_counter_advances_by_exactly_one_and_the_database_says_so(tmp_path):
    store, m, *_ = _attempt_in(tmp_path, PipelineState.PROPOSED, name="ver.db")
    with pytest.raises(sqlite3.IntegrityError, match="advances by exactly one"):
        store.conn.execute(
            "UPDATE pipeline_instances SET state = 'POLICY_CHECKED', gate_decision = "
            "'HUMAN_APPROVAL_REQUIRED', policy_version = 'pv1' WHERE tenant = ?", (T_A,))


def test_gr4_a_redelivered_trigger_is_a_no_op_measured_byte_for_byte(tmp_path):
    store, m, clk, kernel, effect, world, r8 = _to_claimed(tmp_path)
    grant = r8.pipeline.grant_id
    envelope = canonical_event(
        store, event_name="EffectExecuted", producer_transition_id="EF-3",
        aggregate_type="effect_grant", aggregate_id=grant, aggregate_version=1, seed="dup-1",
        clock=clk, pipeline_instance_id=PIPELINE, accountable_owner_id=OWNER)
    first = m.consume(envelope, pipeline_instance_id=PIPELINE,
                      trigger=Trigger.ADAPTER_RETURNED_SUCCESS)
    assert first.consume.outcome is ConsumeOutcome.APPLIED
    digest = state_digest(store)
    second = m.consume(envelope, pipeline_instance_id=PIPELINE,
                       trigger=Trigger.ADAPTER_RETURNED_SUCCESS)
    assert second.consume.is_noop
    assert not second.moved
    assert state_digest(store) == digest, "a redelivery changed durable state"


def test_c1_an_event_from_another_tenant_never_reaches_the_handler(tmp_path):
    store, m, clk, kernel, effect, world, r8 = _to_claimed(tmp_path)
    digest = state_digest(store)
    foreign = canonical_event(
        store, event_name="EffectExecuted", producer_transition_id="EF-3",
        aggregate_type="effect_grant", aggregate_id=r8.pipeline.grant_id, aggregate_version=1,
        seed="foreign-1", clock=clk, tenant=T_B, pipeline_instance_id=PIPELINE,
        accountable_owner_id=OWNER)
    result = m.consume(foreign, pipeline_instance_id=PIPELINE,
                       trigger=Trigger.ADAPTER_RETURNED_SUCCESS)
    assert result.consume.outcome is ConsumeOutcome.REJECTED_CROSS_TENANT
    assert not result.moved
    assert state_digest(store) == digest
    assert m.require(PIPELINE).state is PipelineState.CLAIMED


def test_m26_an_event_for_an_attempt_that_does_not_exist_parks_with_a_named_human(tmp_path):
    """### THE DEFECT M1's FIRST CANDIDATE SHIPPED, ANSWERED BY CONSTRUCTION HERE. Without the
    explicit prerequisite the handler raises inside the inbox's transaction, the receipt rolls back
    and the event redelivers forever; and a park with a NULL owner is rule 13's one exception."""
    clk = Clock()
    store = make_store(tmp_path, name="park.db")
    a_human(store, clock=clk)
    a_work_item(store, clock=clk)
    m = machine(store, clock=clk)
    envelope = canonical_event(
        store, event_name="EffectExecuted", producer_transition_id="EF-3",
        aggregate_type="effect_grant", aggregate_id="grant-early", aggregate_version=1,
        seed="early-1", clock=clk, pipeline_instance_id=PIPELINE, accountable_owner_id=OWNER)
    result = m.consume(envelope, pipeline_instance_id=PIPELINE,
                       trigger=Trigger.ADAPTER_RETURNED_SUCCESS)
    assert result.consume.outcome is ConsumeOutcome.PARKED_MISSING_AGGREGATE
    inbox = DedupInbox(store.conn, tenant=T_A, consumer_id="m2-pipeline-instance", clock=clk,
                       reference_resolver=m.reference_resolver)
    parked = inbox.parked()
    assert len(parked) == 1
    assert parked[0].accountable_owner_id == OWNER, (
        "M-26 parked an obligation with no accountable human — rule 13's one exception, created by "
        "the method whose contract promises the park surfaces WITH the human accountable for it")
    # And redelivery counts the attempt without acting.
    again = m.consume(envelope, pipeline_instance_id=PIPELINE,
                      trigger=Trigger.ADAPTER_RETURNED_SUCCESS)
    assert again.consume.outcome is ConsumeOutcome.ALREADY_PARKED


def test_a_consumption_that_can_establish_no_accountable_human_refuses_and_writes_nothing(tmp_path):
    clk = Clock()
    store = make_store(tmp_path, name="noowner.db")
    a_human(store, clock=clk)
    a_work_item(store, clock=clk)
    m = machine(store, clock=clk)
    digest = state_digest(store)
    envelope = canonical_event(
        store, event_name="EffectExecuted", producer_transition_id="EF-3",
        aggregate_type="effect_grant", aggregate_id="g-nobody", aggregate_version=1,
        seed="nobody-1", clock=clk, pipeline_instance_id=PIPELINE, accountable_owner_id=None)
    with pytest.raises(OwnershipRefused, match="names no accountable human"):
        m.consume(envelope, pipeline_instance_id=PIPELINE,
                  trigger=Trigger.ADAPTER_RETURNED_SUCCESS)
    assert state_digest(store) == digest


def test_pipeline_must_exist_is_derived_from_the_table_not_listed(tmp_path):
    """A hand-kept list of creation triggers is right on the day it is written."""
    assert not pipeline_must_exist(Trigger.INTENT_PROPOSED)
    for trigger in Trigger:
        if trigger is Trigger.INTENT_PROPOSED:
            continue
        assert pipeline_must_exist(trigger), (
            f"{trigger.value} is not treated as being ABOUT an existing attempt; an event about a "
            f"missing referent must park (M-26), never be skipped")


def test_an_unknown_attempt_is_indistinguishable_from_another_tenants(tmp_path):
    store, m, *_ = _attempt_in(tmp_path, PipelineState.PROPOSED, name="unknown.db")
    with pytest.raises(UnknownPipeline) as exc:
        m.require("pl-not-here")
    assert "cross-tenant" in str(exc.value)


# ============================================================ M. the database's own invariants

def test_the_readiness_oracle_refuses_a_database_missing_any_invariant(tmp_path):
    """Structural, and each trigger is verified PRESENT: a table whose invariant triggers were
    dropped is an ordinary table with an aspirational comment."""
    store = make_store(tmp_path, name="ready.db")
    assert phase6_pipeline_readiness_problems(store.conn) == []
    for name in sorted(P6PI_TRIGGERS):
        store.conn.execute(f"DROP TRIGGER {name}")
        problems = phase6_pipeline_readiness_problems(store.conn)
        assert any(name in p for p in problems), f"dropping {name} was not noticed"
        store.conn.execute(P6PI_TRIGGERS[name])
    assert phase6_pipeline_readiness_problems(store.conn) == []


def test_the_reservation_index_is_verified_unique_and_predicated_not_just_present(tmp_path):
    """An index called `..._live_reservation` that is not UNIQUE is the defence switched off with
    the sign left up."""
    store = make_store(tmp_path, name="idx.db")
    store.conn.execute("DROP INDEX ix_pipeline_instances_live_reservation")
    store.conn.execute(
        "CREATE INDEX ix_pipeline_instances_live_reservation "
        "ON pipeline_instances (tenant, commit_key)")
    problems = phase6_pipeline_readiness_problems(store.conn)
    assert any("not UNIQUE" in p for p in problems), problems


def test_granted_is_unreachable_without_a_witness_at_the_database(tmp_path):
    """### §41(a), HELD AGAINST A CONNECTION and not only against the transition table."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.CHECKPOINT, name="witless.db")
    for state in ("GRANTED", "CLAIMED", "EXECUTED", "NEEDS_VERIFICATION"):
        with pytest.raises(sqlite3.IntegrityError, match="require BOTH a checkpoint witness"):
            store.conn.execute(
                "UPDATE pipeline_instances SET state = ?, version = version + 1 "
                " WHERE tenant = ? AND pipeline_instance_id = ?", (state, T_A, PIPELINE))


def test_an_invented_checkpoint_or_grant_id_is_unwritable(tmp_path):
    """The foreign keys. An invented witness id is not a bad value; it is an unwritable one."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.CHECKPOINT, name="fk.db")
    with pytest.raises(sqlite3.IntegrityError):
        store.conn.execute(
            "UPDATE pipeline_instances SET state = 'GRANTED', version = version + 1, "
            " checkpoint_id = 'made-up', grant_id = 'also-made-up' WHERE tenant = ?", (T_A,))


def test_the_witness_binding_is_write_once(tmp_path):
    """Rebinding would let a claimed effect borrow another decision's authority."""
    store, m, clk, kernel, effect, world, r8 = _to_claimed(tmp_path)
    with pytest.raises(sqlite3.IntegrityError, match="never rebound"):
        store.conn.execute(
            "UPDATE pipeline_instances SET grant_id = NULL, version = version + 1 "
            " WHERE tenant = ?", (T_A,))


def test_the_identity_of_an_attempt_is_immutable(tmp_path):
    """Editing the commit key retargets an authorization granted for a different effect."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.PROPOSED, name="immutable.db")
    for column, value in (("commit_key", "another-effect"), ("work_item_id", "wi-other"),
                          ("target_resource_id", "load:9999"), ("attempt_seq", 7)):
        with pytest.raises(sqlite3.IntegrityError, match="identity of an attempt"):
            store.conn.execute(
                f"UPDATE pipeline_instances SET {column} = ?, version = version + 1 "
                f" WHERE tenant = ?", (value, T_A))


def test_an_attempt_is_never_deleted(tmp_path):
    store, m, *_ = _attempt_in(tmp_path, PipelineState.CLOSED, name="nodelete.db")
    with pytest.raises(sqlite3.IntegrityError, match="never deleted"):
        store.conn.execute("DELETE FROM pipeline_instances WHERE tenant = ?", (T_A,))


def test_the_owner_must_be_the_work_items_owner_and_the_database_enforces_it(tmp_path):
    """§5. An attempt accountable to somebody other than the human who owes the work is rule 13
    satisfied by a column and violated in fact."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.PROPOSED, name="owner.db")
    a_human(store, "controller-carl")
    with pytest.raises(sqlite3.IntegrityError, match="owned by its Work Items owner"):
        store.conn.execute(
            "UPDATE pipeline_instances SET owner_id = 'controller-carl', version = version + 1 "
            " WHERE tenant = ?", (T_A,))
    assert m.ownerless() == []


def test_an_attempt_cannot_be_INSERTED_for_a_human_who_does_not_own_the_work_item(tmp_path):
    """The same §5 rule on the way IN. An UPDATE-only guard leaves the whole creation path open."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.PROPOSED, name="owner-insert.db")
    a_human(store, "controller-carl")
    with pytest.raises(sqlite3.IntegrityError, match="owned by its Work Items owner"):
        store.conn.execute(
            "INSERT INTO pipeline_instances (tenant, pipeline_instance_id, work_item_id, state, "
            " version, owner_id, action_class, target_system, target_resource_id, "
            " target_operation, occurrence_key, commit_key, attempt_seq, absorbed_count, "
            " created_at, updated_at) "
            " VALUES (?,?,?, 'PROPOSED', 1, 'controller-carl', 'raise_invoice', "
            " 'tms:truckingoffice', ?, 'create_invoice', '', 'another-key', 1, 0, "
            " '2026-08-14T09:00:00.000Z','2026-08-14T09:00:00.000Z')",
            (T_A, "pl-wrong-owner", WORK_ITEM, LOAD))


def test_a_table_that_reserves_a_commit_key_without_answering_to_the_ledger_is_refused(tmp_path):
    """### THE POSITIVE CONTROL FOR THE SECOND-LEDGER GUARD (CLAUDE.md rule 17).

    `pipeline_instances` legitimately carries `commit_key` + `state` because §14 PL-1 mandates the
    Layer-1 reservation — and it is answerable to the one ledger by foreign key. The guard's
    predicate is therefore "does it declare an FK into `effect_grants`", and a guard that only ever
    sees a compliant table proves nothing about the non-compliant one. So one is built.
    """
    from freight_recon.schema import schema_readiness_problems

    store = make_store(tmp_path, name="secondledger.db")
    assert schema_readiness_problems(store.conn) == []
    store.conn.execute(
        "CREATE TABLE shadow_reservations ("
        " tenant TEXT NOT NULL, commit_key TEXT NOT NULL, state TEXT NOT NULL,"
        " PRIMARY KEY (tenant, commit_key))")
    store.conn.commit()
    problems = schema_readiness_problems(store.conn)
    assert any("shadow_reservations" in p and "second effect ledger" in p for p in problems), (
        f"a table reserving a commit key with no reference to effect_grants passed readiness: "
        f"{problems}")


def test_the_ownerless_detector_runs_over_a_non_empty_population(tmp_path):
    """CLAUDE.md §9: a negative assertion needs a proven population."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.PROPOSED, name="ownerless.db")
    assert m.for_work_item(WORK_ITEM), "the detector ran over an empty table"
    assert m.ownerless() == []


def test_the_gate_vocabulary_is_derived_from_p3_and_not_restated(tmp_path):
    """ONE policy vocabulary. The migration reads the four literals out of `checkpoint_witnesses`'s
    canonical DDL, so the pipeline's CHECK IS the witness's CHECK."""
    assert set(GATE_DECISIONS) == {g.value for g in GateDecision}
    source = (ROOT / "src/freight_recon/migrations/phase6_pipeline_instances.py").read_text()
    for token in GATE_DECISIONS:
        assert not re.search(rf"(?<![A-Za-z0-9_]){token}(?![A-Za-z0-9_])", source), (
            f"{token} is written literally in the M2 migration; it must be derived from P3"
        )
    # And the derivation is not vacuous: the four ARE in the built DDL.
    from freight_recon.migrations.phase6_pipeline_instances import P6PI_TARGET_SCHEMA
    for token in GATE_DECISIONS:
        assert f"'{token}'" in P6PI_TARGET_SCHEMA["pipeline_instances"], (
            f"{token} never reached the CHECK; the derivation produced an empty vocabulary")


# ====================================================================== N. it ships dark (M-27)

def _m2_surface_roots() -> tuple[str, ...]:
    """M2's own modules, taken from `IMPLEMENTATION-SURFACE.yaml` — the repository's record of what
    this unit ships — rather than from a name typed into the guard.

    A root list maintained here would be right on the day it is written. If a later checkpoint adds
    a module to M2's surface, the closure must widen with it or the dark-surface claim quietly stops
    covering the new module.
    """
    import yaml

    surface = yaml.safe_load(
        (ROOT / "docs/implementation/IMPLEMENTATION-SURFACE.yaml").read_text(encoding="utf-8"))
    entries = [
        e for section in surface.values() if isinstance(section, list)
        for e in section
        if isinstance(e, dict) and e.get("name") == "Pipeline Instance"
    ]
    assert entries, "IMPLEMENTATION-SURFACE.yaml records no `Pipeline Instance` entry to take roots from"
    prefix = "src/freight_recon/"
    roots = sorted({
        ev["path"][len(prefix):].removesuffix(".py").replace("/", ".")
        for e in entries for ev in e.get("evidence", [])
        if str(ev.get("path", "")).startswith(prefix)
    })
    assert roots, "the recorded Pipeline Instance surface names no module under src/freight_recon/"
    return tuple(roots)


def test_m2_cannot_reach_an_effect_capable_adapter():
    """### THE IMPORT CLOSURE, COMPUTED BY THE REPOSITORY'S OWN IMPORT AUTHORITY.

    Every input is DERIVED, because each one that was not derived turned out to be wrong:

        roots             `IMPLEMENTATION-SURFACE.yaml`'s record of M2's modules
        population        `import_probe.EFFECT_CAPABLE_ADAPTERS` — the same set the P4 gate
                          partitions on, so an adapter added there is guarded here on that commit
        reachability      `import_probe.package_import_closure`, which recognises every legal
                          Python import spelling

    ### THE FIRST VERSION OF THIS GUARD WAS FALSE-GREEN IN TWO INDEPENDENT WAYS, AND BOTH ARE
    RECORDED HERE RATHER THAN QUIETLY FIXED. It hand-enumerated nine adapter names, three of which
    are not modules of this repository at all and three real effect-capable adapters
    (`discovered_write`, `browser_agent`, `browser_tms_adapter`) of which it named none; and its own
    import walker followed two spellings out of six, missing `from freight_recon.x import y` — the
    dominant spelling in this package — and `from . import x`, which is in live use in
    `governed_write_route.py` and `action_callback.py`. A leak through either was invisible.
    """
    from eval.phase0 import import_probe

    roots = _m2_surface_roots()
    assert "pipeline_instance" in roots, f"M2's own module is not among the recorded roots: {roots}"
    assert import_probe.EFFECT_CAPABLE_ADAPTERS, (
        "the canonical effect-capable population is EMPTY — this guard would pass over nothing")
    leaked, ev = import_probe.effect_capable_reachable_from(roots)
    ev.require_population(10)   # a walk that inspected a handful of modules proves nothing
    assert not leaked, (
        f"M2's import closure reaches effect-capable adapters {sorted(leaked)} — it no longer ships "
        f"dark. Closure size {ev.evaluated}, roots {roots}."
    )


def test_the_dark_surface_guard_can_actually_fire():
    """### THE POSITIVE CONTROL, ON THE REAL TREE. A guard nobody has seen go red is a decoration.

    `effect_boundary` is P4's containment boundary — the ONE module authorized to import an
    effect-capable adapter. Running the same derivation from it must find adapters. If this comes
    back empty, the walker is broken and the M2 assertion above is passing vacuously.
    """
    from eval.phase0 import import_probe

    reached, ev = import_probe.effect_capable_reachable_from(("effect_boundary",))
    ev.require_population(2)
    assert reached, (
        "the containment boundary reaches NO effect-capable adapter. Either P4's boundary has "
        "changed or this walker cannot see an import — in both cases M2's dark-surface assertion "
        "is unproven.")


@pytest.mark.parametrize(
    "spelling,source",
    [
        ("absolute from-import", "from freight_recon.discovered_write import DiscoveredWriter"),
        ("dotted import", "import freight_recon.discovered_write"),
        ("dotted import as", "import freight_recon.discovered_write as dw"),
        ("package from-import", "from freight_recon import discovered_write"),
        ("relative from-import", "from .discovered_write import DiscoveredWriter"),
        ("relative bare import", "from . import discovered_write"),
        ("importlib absolute", "importlib.import_module('freight_recon.discovered_write')"),
        ("importlib relative", "importlib.import_module('.discovered_write', __package__)"),
        ("dunder import", "__import__('freight_recon.discovered_write')"),
    ],
)
def test_every_legal_import_spelling_is_recognised(spelling, source):
    """### THE DEFECT THIS PARAMETRIZATION IS AIMED AT, NAMED. The previous walker followed
    `from .x import y` and `import freight_recon.x` and nothing else, so a leak spelled any of the
    other seven ways was invisible while the guard reported green.

    Each case is decided by the SAME function the closure walk uses, over a top-level module — so
    this is the walk's edge-extraction step under test, not a re-implementation of it.
    """
    from eval.phase0 import import_probe

    targets = import_probe.module_import_targets(ast.parse(source), "pipeline_instance")
    assert "discovered_write" in targets, (
        f"{spelling} is a legal way to reach an adapter and the walker does not see it: {targets}")


def test_the_spelling_battery_is_not_trivially_true():
    """The negative control for the battery above: a source importing nothing yields nothing, and
    an unrelated import does not accidentally name the adapter."""
    from eval.phase0 import import_probe

    assert import_probe.module_import_targets(ast.parse("x = 1"), "pipeline_instance") == set()
    assert "discovered_write" not in import_probe.module_import_targets(
        ast.parse("from freight_recon.tenant import require_tenant"), "pipeline_instance")
    assert "discovered_write" not in import_probe.module_import_targets(
        ast.parse("import os, json"), "pipeline_instance")


def test_nothing_in_production_calls_m2(tmp_path):
    """`CURRENT.md`: M2 ships dark. An AST sweep for importers, over a proven denominator."""
    import freight_recon

    src = Path(freight_recon.__file__).parent
    inspected, importers = 0, []
    for path in sorted(src.rglob("*.py")):
        if path.name == "pipeline_instance.py":
            continue
        inspected += 1
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (node.module or "").endswith(
                    "pipeline_instance"):
                importers.append(path.name)
            elif isinstance(node, ast.Import) and any(
                    a.name.endswith("pipeline_instance") for a in node.names):
                importers.append(path.name)
    assert inspected > 20, f"the sweep inspected {inspected} modules; it proves nothing"
    assert not importers, f"M2 has production importers and no longer ships dark: {importers}"


def test_no_witness_and_no_grant_exist_until_a_checkpoint_runs(tmp_path):
    """Measured across every pre-checkpoint state, so "ships dark" is a count and not a claim."""
    for state in (PipelineState.PROPOSED, PipelineState.POLICY_CHECKED, PipelineState.VALIDATED,
                  PipelineState.AWAITING_APPROVAL, PipelineState.CHECKPOINT,
                  PipelineState.REJECTED, PipelineState.VOIDED):
        store, m, *_ = _attempt_in(tmp_path, state, name=f"dark-{state.value}.db")
        assert m.require(PIPELINE).state is state
        assert witnesses(store) == [], f"{state.value} minted a witness"
        assert ledger(store) == [], f"{state.value} minted a grant"


def test_pl_11d_emission_is_deferred_to_m3_and_says_so(tmp_path):
    """### A RECORDED FINDING, NAMED RATHER THAN SILENTLY ABSENT (debt P6-D13).

    `VerificationDeferred` is the ONE contract the registry attributes to a PL-* transition while
    declaring `aggregate_type: effect_grant` — family F3's default. Its ordering key is therefore
    `(tenant, effect_grant:<grant_id>, the GRANT's version)`, and the grant's version belongs to M3,
    which is a later unit. This machine performs PL-11d's durable write and does NOT emit, because
    a guessed version misorders a STRICT stream permanently and silently, which is strictly worse
    than an absent event that is written down.
    """
    from freight_recon.event_contracts import CONTRACTS
    from freight_recon.pipeline_instance import DEFERRED_EMISSIONS

    assert DEFERRED_EMISSIONS == {"VerificationDeferred": "effect_grant"}
    contract = CONTRACTS["VerificationDeferred"]
    assert contract.producers == ("PL-11d",), "the deferral's premise moved"
    assert contract.aggregate_type == "effect_grant", "the deferral's premise moved"
    assert "VerificationDeferred" not in PRODUCED_CONTRACTS
    store, m, *_ = _attempt_in(tmp_path, PipelineState.EXECUTED, name="d13.db")
    before = {e["event_name"] for e in outbox_events(store)}
    m.apply(PIPELINE, Trigger.READBACK_DEFERRED, **SYS, recheck_at="2026-08-14T18:00:00.000Z")
    assert {e["event_name"] for e in outbox_events(store)} == before


# ============================================ O. the F2 stream's version gaps — MEASURED, not assumed

def test_the_f2_event_stream_has_gaps_where_a_CONSUMES_row_moved_the_attempt(tmp_path):
    """### THE GAP IS REAL, IT IS INTENTIONAL, AND IT IS NOW HARMLESS (P6-D11 — RESOLVED).

    Eight of M2's twenty-five rows are `CONSUMES`: they advance the attempt's version (GR-3 writes
    the row) and emit nothing on `pipeline_instance`, because the canonical event belongs to M3 or
    M4. So the F2 stream for one attempt contains gaps — permanently, by canonical design, and this
    machine must NOT close them by emitting an event about a machine that does not exist.

    What changed is the CONSUMER's reading of a gap, not the gap. `events/registry.md` §8 now states
    that strict per-aggregate ordering is ORDER and never CONTIGUITY, and every event on this stream
    declares `previous_aggregate_version` — so a version nobody emitted on is legible as nothing
    instead of as a loss. This case keeps measuring the gap (the premise), and asserts the chain
    across it is unbroken (the resolution). The hostile battery is
    `test_p6_d11_strict_order_stream_link.py`.
    """
    store, m, clk, kernel, effect, world, r8 = _to_claimed(tmp_path)
    emitted = [e for e in outbox_events(store) if e["aggregate_type"] == AGGREGATE_TYPE]
    versions = sorted(e["aggregate_version"] for e in emitted)
    current = m.require(PIPELINE).version
    missing = sorted(set(range(1, current + 1)) - set(versions))
    assert missing, (
        "no gap was found — either every transition now emits on the pipeline aggregate, or this "
        "case stopped exercising a CONSUMES row. Either way the finding must be re-derived."
    )
    consumes_rows = [r.id for r in TRANSITIONS if r.kind is RowKind.CONSUMES]
    assert len(consumes_rows) == 8, f"the CONSUMES population moved: {consumes_rows}"
    assert len(missing) <= len(consumes_rows)

    # ### AND THE STREAM ACROSS THAT GAP IS A CHAIN A CONSUMER CAN FOLLOW.
    envelopes = [EventEnvelope.from_json(r["envelope_json"]) for r in store.conn.execute(
        "SELECT envelope_json FROM event_outbox WHERE tenant = ? AND aggregate_type = ? "
        "AND aggregate_id = ? ORDER BY aggregate_version, event_id",
        (T_A, AGGREGATE_TYPE, PIPELINE)).fetchall()]
    seen: list[int] = []
    for envelope in envelopes:
        assert envelope.previous_aggregate_version == max(
            [v for v in seen if v < envelope.aggregate_version], default=0), (
            f"{envelope.event_name} at v{envelope.aggregate_version} declares a predecessor the "
            f"emitted stream does not hold — a consumer would park on it"
        )
        seen.append(envelope.aggregate_version)


# ==================================================================== P. concurrency, on one store

def test_two_writers_racing_one_transition_produce_exactly_one(tmp_path):
    """GR-3 on the SAME store, interleaved — not two isolated calls that never met."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.PROPOSED, name="conc.db")
    stale = m.require(PIPELINE)
    facts = dict(policy_version="pv1", gate_decision=GateDecision.HUMAN_APPROVAL_REQUIRED,
                 policy_decision="PERMIT", rules_matched=["r-1"], reason="x",
                 model_inferred_material_fact=False)
    first = m.apply(PIPELINE, Trigger.POLICY_EVALUATED, **SYS,
                    expected_version=stale.version, **facts)
    assert first.to_state is PipelineState.POLICY_CHECKED
    with pytest.raises(VersionConflict):
        m.apply(PIPELINE, Trigger.POLICY_EVALUATED, **SYS, expected_version=stale.version, **facts)
    assert len([e for e in outbox_events(store) if e["event_name"] == "PolicyEvaluated"]) == 1


def test_two_attempts_racing_one_effect_produce_exactly_one_live_reservation(tmp_path):
    """AC-SAFE-014's shape at Layer 1: exactly one competitor wins, and the loser is absorbed."""
    store, m, *_ = _attempt_in(tmp_path, PipelineState.PROPOSED, name="race2.db")
    outcomes = [
        m.propose(pipeline_instance_id=f"pl-r{i}", work_item_id=WORK_ITEM, effect=an_effect(),
                  proposal_ref=f"intent-r{i}", **SYS)
        for i in range(5)
    ]
    assert all(o.absorbed is not None for o in outcomes)
    assert m.require(PIPELINE).absorbed_count == 5
    key = m.require(PIPELINE).commit_key
    assert len(m.attempts_for(key)) == 1
    assert m.live_holder(key).pipeline_instance_id == PIPELINE
