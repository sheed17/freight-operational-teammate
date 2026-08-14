"""P5 U5.4+U5.5+U5.6 — the golden corpus, the inert replay, and audit reconstruction.

### WHY THESE ARE ONE FILE AND ONE UNIT, NOT THREE. The acceptance spec makes the coupling
mechanical rather than a matter of taste: `AC-EVT-007`'s oracle is *"replay `GC-1` ⇒ 0 witnesses,
0 grants, 0 adapter calls"* and `AC-EVT-008`'s is *"`GC-1` ⇒ the SAME projection DIGEST"*. The
corpus cannot be validated without a replay, the replay cannot be tested without the corpus, and
`AC-AUD-002` folds the same history per-effect. Three historical labels; one capability:

    state changes → canonical facts → durable transport → replay → reconstructed state
                                                                 → auditable explanation

THE PROPERTY THIS FILE EXISTS TO DEFEND

Replay reconstructs truth; it does not repeat real-world actions. M-27 requires that
STRUCTURALLY — *"replay performs no live revalidation ⇒ it cannot construct a `CheckpointPassed` ⇒
it cannot mint an Effect Grant ⇒ it cannot act"* — so the load-bearing node here is not the one
that counts zero grants after a replay. It is `test_replay_cannot_reach_an_effect_capable_module`,
which asserts the import CLOSURE: a module that cannot reach the capability cannot use it.

### THAT CLAIM WAS ONCE FALSE HERE, WHICH IS WHY IT IS STATED CAREFULLY NOW. The walk originally
saw only RELATIVE from-imports, so an absolute `from freight_recon.effect_boundary import ...`
passed it silently. It now covers every spelling Python offers, and section 9 parametrizes over
each — but the honest form of the claim is "no edit in any spelling this walk knows", not "no edit".

DISCIPLINE, as everywhere in this suite: discover, never enumerate; exact sets, not counts; a
proven population before every negative assertion; and no node may pass by measuring nothing.
"""

from __future__ import annotations

import ast
import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for entry in (str(ROOT / "src"), str(ROOT / "eval"), str(ROOT / "scripts")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from phase5_kit import (  # noqa: E402
    T_A,
    T_B,
    RecordingHandler,
    make_canonical_envelope,
    make_envelope,
    make_inbox,
    make_store,
)

from freight_recon.event_audit import (  # noqa: E402
    EIGHTEEN_FIELDS,
    UNRECONSTRUCTIBLE,
    AuditError,
    chain_for,
    explain,
)
from freight_recon.event_contracts import (  # noqa: E402
    CONTRACTS,
    CanonicalContract,
    FieldSpec,
    UpcasterRegistry,
    contract_for,
)
from freight_recon.event_envelope import EventEnvelope  # noqa: E402
from freight_recon.event_outbox import transactional_emit  # noqa: E402
from freight_recon.event_replay import (  # noqa: E402
    ReplayError,
    ReplayTenantViolation,
    compare_to_live,
    corpus_digest,
    from_outbox,
    load_corpus,
    replay,
)

import build_gc1_corpus as builder  # noqa: E402

FIXTURES = ROOT / "eval" / "fixtures"
CORPUS_PATH = FIXTURES / "gc1-corpus.json"
PIN_PATH = FIXTURES / "gc1-pinned-digests.json"

GC1 = load_corpus(CORPUS_PATH)
PINS = json.loads(PIN_PATH.read_text(encoding="utf-8"))


def require_population(population, *, at_least: int, what: str):
    assert len(population) >= at_least, (
        f"{what}: expected at least {at_least}, found {len(population)}. A case that iterates an "
        f"empty population proves nothing while reporting success."
    )
    return population


# ============================================================ 1. GC-1 is what it says it is

def test_the_committed_corpus_and_its_pins_are_exactly_what_the_builder_derives():
    """### THE ANTI-DRIFT NODE FOR THE FIXTURE ITSELF. GC-1 is the artifact whose entire job is to
    be trustworthy forever; a corpus that drifted from its builder would be a golden fixture nobody
    generated."""
    events = builder.duplicate_delivery(builder.build())
    assert CORPUS_PATH.read_text(encoding="utf-8") == builder.render_corpus(events), (
        "eval/fixtures/gc1-corpus.json is STALE. Rebuilding it RE-PINS the digest, which the "
        "acceptance oracle says a human must explain — run scripts/build_gc1_corpus.py knowingly."
    )
    assert PIN_PATH.read_text(encoding="utf-8") == builder.render_pins(events)


def test_gc1_spans_every_condition_the_acceptance_spec_requires():
    """The spec lists eight spans. Seven are asserted from the CORPUS, not from its own manifest —
    a fixture that certified itself would be worth nothing."""
    names = [e.event_name for e in GC1]
    tenants = {e.tenant_id for e in GC1}
    ids = [e.event_id for e in GC1]

    assert len(tenants) >= 2, tenants
    assert "ClaimCorrected" in names, "no correction"
    # the correction's PROPAGATION: an event caused by the correction
    correction = next(e for e in GC1 if e.event_name == "ClaimCorrected")
    assert any(e.causation_id == correction.event_id for e in GC1), "correction did not propagate"
    assert "OutcomeUnknown" in names
    assert any(n.startswith("Compensation") for n in names)
    assert {"BrakeEngaged", "BrakeReleased"} <= set(names), "no brake episode"
    # a dangling reference: an event naming an aggregate the corpus creates LATER
    bound = next(e for e in GC1 if e.event_name == "ObservationBound")
    referenced = bound.payload["bound_entity_ref"].split(":", 1)[1]
    creator = next((i for i, e in enumerate(GC1) if e.aggregate_id == referenced), None)
    assert creator is not None and creator > GC1.index(bound), "the reference is not dangling"
    # a duplicate delivery: the SAME event_id twice, byte-identical
    duplicated = [i for i in set(ids) if ids.count(i) > 1]
    assert duplicated, "no duplicate delivery"
    for dup in duplicated:
        copies = [e for e in GC1 if e.event_id == dup]
        assert len({e.digest() for e in copies}) == 1, "a 'duplicate' that is not byte-identical"


def test_the_schema_version_span_is_genuinely_deferred_and_not_merely_unwritten():
    """### THE PREMISE MUST NOT OUTLIVE ITS OWN TRUTH. GC-1 does not span a schema version change
    INLINE because every canonical contract is at v1 and minting a v2 is a specification amendment
    under founder/architect authority. This node asserts that premise. The day a real v2 exists it
    goes red — the signal that GC-1 now owes the span inline rather than through section 8's
    test-only fixture, which is where `AC-EVT-009` is proven today.
    """
    versioned = {n: c.current_version for n, c in CONTRACTS.items() if c.current_version != 1}
    assert versioned == {}, (
        f"{sorted(versioned)} are no longer v1 — GC-1 must now span a schema version change and "
        f"AC-EVT-009 (v1+v2+v3 in one corpus) has become executable"
    )
    document = json.loads(CORPUS_PATH.read_text(encoding="utf-8"))
    assert document["_spans"]["schema_version_change"] is False
    assert "AC-EVT-009" in document["_schema_version_change"], (
        "the corpus must record WHERE the version span is proven, not merely that it is absent"
    )


def test_every_event_in_the_corpus_is_a_canonical_fact():
    """A golden corpus of events the runtime would refuse to emit would test the wrong system."""
    from freight_recon.event_contracts import ValidationMode, validate

    require_population(GC1, at_least=20, what="GC-1 events")
    for event in GC1:
        validate(event, mode=ValidationMode.PRODUCER)


# ================================================== 2. AC-EVT-008 — the pinned rebuild digest

def test_rebuilding_gc1_reproduces_the_pinned_digest():
    """### THE CORPUS ORACLE. `rebuild(GC-1) → D`, and D is pinned. Every build, forever, the same
    D. A changed digest is a FAILING build until a human explains why."""
    result = replay(GC1)
    assert result.digest() == PINS["rebuild_digest"], (
        "the GC-1 rebuild digest CHANGED. Either the corpus moved or the fold did. A rebuild that "
        "'looks right' is not a pass — explain the change, then re-pin deliberately."
    )
    assert corpus_digest(GC1) == PINS["corpus_digest"]
    assert PINS["event_count"] == len(GC1)
    assert result.events_folded + result.duplicates_ignored == len(GC1)
    assert len(result.aggregates) == PINS["aggregate_count"]


def test_the_rebuild_is_deterministic_under_delivery_ORDER():
    """### NONDETERMINISTIC RECONSTRUCTION — the defect this caught in its own implementation.

    §8 gives NO global order, so the same history can legitimately arrive in different orders: a
    relay leasing aggregates differently, or a recovery after a crash. An earlier fold applied
    fields in ARRIVAL order, so a shuffled corpus rebuilt to a different digest — and the pinned
    oracle would have been pinning a property of one delivery rather than of the history.
    """
    baseline = replay(GC1).digest()
    for seed in (1, 7, 42, 99, 1234):
        shuffled = GC1[:]
        random.Random(seed).shuffle(shuffled)
        assert replay(shuffled).digest() == baseline, f"shuffle seed {seed} rebuilt differently"
    # And twice in a row, which is the weaker property but the one M-25's rebuild test needs.
    assert replay(GC1).digest() == baseline


def test_a_duplicate_delivery_folds_to_the_same_state():
    """AC-EVT-004 at the REBUILD layer. The inbox makes a redelivery a no-op in the live path; a
    rebuild reads history where the duplicate is simply present, and must fold it identically."""
    ids = [e.event_id for e in GC1]
    duplicated = require_population([i for i in set(ids) if ids.count(i) > 1],
                                    at_least=1, what="duplicated event ids in GC-1")
    deduped, seen = [], set()
    for event in GC1:
        if event.event_id not in seen:
            seen.add(event.event_id)
            deduped.append(event)
    assert len(deduped) < len(GC1), "the corpus carries no duplicate to remove"
    assert replay(deduped).digest() == replay(GC1).digest(), (
        f"folding {duplicated} twice changed the reconstruction — a redelivered fact is the same "
        f"fact, and a rebuild that double-counts it reconstructs a history that never happened"
    )


# ============================================ 3. AC-EVT-007 — replay is side-effect free

def test_replay_cannot_reach_an_effect_capable_module():
    """### THE LOAD-BEARING NODE OF THIS UNIT. M-27 says structurally, so this asserts the import
    CLOSURE rather than counting zeros afterwards. A module that cannot reach the capability cannot
    use it, and no future edit can make replay act without first making this guard red.
    """
    forbidden = {
        "effect_boundary", "checkpoint", "cdp_actuator", "cdp_session", "tms_write",
        "truckingoffice_write", "discovered_write", "multistep_write", "browser_use_write",
        "browser_use_adapter", "slack_adapter", "email_adapter", "workflow", "brake",
    }
    src = ROOT / "src" / "freight_recon"

    def reached_by(tree: ast.AST) -> list[str]:
        """### EVERY WAY A MODULE CAN ENTER A NAMESPACE — not just the one spelling.

        An earlier version tested `isinstance(node, ast.ImportFrom) and node.level`, so it saw only
        RELATIVE from-imports. `from freight_recon.effect_boundary import execute_effect` has
        `level == 0` and walked straight past it — and this package contains 26 absolute imports in
        that style, so a future edit written in the package's OTHER prevailing style would have
        passed the guard that is the sole control over `effect_boundary` and `checkpoint`.

        `eval/phase0/import_probe._module_name` had already solved this and its docstring says why:
        "The guard could be bypassed by changing import style, which is exactly the 'effect path
        hidden behind an alias' case it exists to catch." CLAUDE.md §9 lists this blind spot as a
        four-time repeat offender in this repository. This is the fifth.
        """
        found: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:                      # from [.]freight_recon.X import y  /  from .X import y
                    found.append(node.module.split(".")[-1])
                for alias in node.names:             # from freight_recon import X  /  from . import X
                    found.append(alias.name.split(".")[-1])
            elif isinstance(node, ast.Import):       # import freight_recon.X [as y]
                for alias in node.names:
                    found.append(alias.name.split(".")[-1])
            elif isinstance(node, ast.Call):         # importlib.import_module("...") / __import__("...")
                target = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
                if target in {"import_module", "__import__"}:
                    for argument in node.args:
                        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                            found.append(argument.value.split(".")[-1])
        return found

    seen: set[str] = set()
    frontier = ["event_replay", "event_audit"]
    while frontier:
        module = frontier.pop()
        if module in seen:
            continue
        seen.add(module)
        path = src / f"{module}.py"
        if not path.exists():
            continue
        frontier.extend(reached_by(ast.parse(path.read_text(encoding="utf-8"))))

    assert "event_replay" in seen and "event_audit" in seen, "the closure walk inspected nothing"
    reached = sorted(seen & forbidden)
    assert not reached, (
        f"the replay/audit import closure reaches {reached}. M-27's guarantee is that replay "
        f"CANNOT act, not that it does not — an effect-capable module inside the closure turns a "
        f"structural property back into a discipline. Closure walked: {sorted(seen)}"
    )


def test_replaying_the_whole_corpus_mints_nothing(tmp_path):
    """AC-EVT-007's measured oracle, against REAL tables: 0 witnesses, 0 grants — and the state
    digest of every durable surface is unchanged, so replay wrote nothing anywhere."""
    store = make_store(tmp_path)
    before = {
        table: store.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in ("checkpoint_witnesses", "effect_grants", "event_outbox", "event_inbox",
                      "pending_references", "brakes")
    }
    result = replay(GC1)
    assert result.events_folded > 0, "the replay folded nothing — a vacuous assertion below"
    after = {
        table: store.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in before
    }
    assert after == before, f"replay wrote to durable state: {before} -> {after}"
    assert (result.witnesses_minted, result.grants_minted,
            result.adapter_calls, result.consumer_emissions) == (0, 0, 0, 0)
    store.close()


def test_replay_takes_no_connection_and_offers_no_write_surface():
    """The API shape IS the guarantee: `replay()` accepts a source and returns a value. A signature
    that accepted a connection would make "it writes nothing" a promise about the body instead."""
    import inspect

    signature = inspect.signature(replay)
    assert set(signature.parameters) == {"events", "tenant", "upcasters", "strict",
                                         "contracts"}, signature
    # `contracts` is a READ seam. The emit path must never grow one — that is what keeps it a
    # reconstruction override rather than a validation bypass.
    import inspect as _inspect

    from freight_recon import event_outbox

    assert "contracts" not in _inspect.signature(
        event_outbox.TransactionalOutbox.emit).parameters, (
        "the outbox emit path gained a contract-set parameter — a rebuild may read history through "
        "an explicit contract set, but nothing may WIDEN what becomes durable history"
    )
    source = inspect.getsource(replay)
    for forbidden in ("commit(", "INSERT", "UPDATE", "DELETE", "execute("):
        assert forbidden not in source, f"replay() contains {forbidden!r}"


# ================================================================ 4. the real failure modes

def test_replay_survives_a_restart_by_reading_the_durable_transport(tmp_path):
    """### REPLAY AFTER RESTART. The corpus is emitted through the REAL transactional outbox, the
    store is closed and reopened — a genuine process restart — and the rebuild from the reopened
    database is byte-identical to the rebuild from the fixture.
    """
    store = make_store(tmp_path, tenant=T_A)
    tenant_events = [e for e in GC1 if e.tenant_id == "brokerage-northwind"]
    require_population(tenant_events, at_least=10, what="tenant-A events in GC-1")

    store_a = make_store(tmp_path, tenant="brokerage-northwind", name="restart.db")
    seen: set[str] = set()
    for event in tenant_events:
        if event.event_id in seen:            # the outbox refuses a genuine duplicate emission
            continue
        seen.add(event.event_id)
        with transactional_emit(store_a.conn, tenant="brokerage-northwind") as session:
            session.emit(event)
    from_live = replay(from_outbox(store_a.conn, tenant="brokerage-northwind")).digest()
    store_a.close()

    reopened = make_store(tmp_path, tenant="brokerage-northwind", name="restart.db")
    after_restart = replay(from_outbox(reopened.conn, tenant="brokerage-northwind")).digest()
    reopened.close()
    store.close()

    assert after_restart == from_live, "the rebuild changed across a restart"
    assert after_restart == replay(tenant_events).digest(), (
        "rebuilding from the durable transport disagreed with rebuilding from the corpus — the "
        "outbox refuses a second emission of one event_id, and the fold ignores a redelivery, so "
        "the two readings of one history must agree"
    )


def test_a_missing_event_produces_a_visibly_partial_history_not_a_silent_one():
    """### MISSING EVENTS / PARTIAL HISTORY. A gap must change the reconstruction — a fold that
    produced the same digest with a fact removed would mean the fact never mattered."""
    full = replay(GC1)
    for drop in ("OutcomeUnknown", "ApprovalGranted", "ClaimCorrected"):
        partial_events = [e for e in GC1 if e.event_name != drop]
        assert len(partial_events) < len(GC1)
        partial = replay(partial_events)
        assert partial.digest() != full.digest(), (
            f"removing every {drop} left the rebuild digest unchanged — the fact is not "
            f"contributing to reconstructed truth"
        )
        assert partial.events_folded < full.events_folded


def test_a_corrupted_payload_is_refused_and_never_folded():
    """### CORRUPTED EVENT PAYLOAD. Strict (the default) RAISES — history that cannot be read is
    not something to quietly reconstruct 90% of. Non-strict RECORDS the refusal and continues,
    which a forensic rebuild of a known-damaged corpus needs, and it is reported rather than silent.
    """
    target = next(e for e in GC1 if e.event_name == "CheckpointPassed")
    corrupted = EventEnvelope.from_document(
        {**target.as_document(), "payload": {"checkpoint_id": "cp-7701"}})   # required fields gone
    damaged = [corrupted if e.event_id == target.event_id else e for e in GC1]

    with pytest.raises(ReplayError, match="not a canonical fact"):
        replay(damaged)

    forensic = replay(damaged, strict=False)
    assert forensic.rejected, "a damaged corpus rebuilt with no refusal recorded"
    assert corrupted.event_id in {eid for eid, _ in forensic.rejected}
    assert forensic.events_folded == replay(GC1).events_folded - 1


def test_an_unsupported_historical_version_is_refused_rather_than_reinterpreted():
    """### INCOMPATIBLE HISTORICAL VERSION. A fact stamped at a version this binary's contract does
    not define is refused (§6). Reading it anyway would reinterpret an old fact under new
    assumptions — silently, and in a rebuild that then gets pinned."""
    target = next(e for e in GC1 if e.event_name == "PipelineStarted")
    future = EventEnvelope.from_document({**target.as_document(), "event_version": 4})
    damaged = [future if e.event_id == target.event_id else e for e in GC1]
    with pytest.raises(ReplayError):
        replay(damaged)


def test_upcasting_happens_during_replay_and_is_deterministic():
    """§6's "applied on read", exercised through the rebuild path. Every canonical contract is at
    v1 today, so this asserts the composition: every folded event emerges at its contract's CURRENT
    version, and two rebuilds agree."""
    result = replay(GC1)
    require_population(result.aggregates, at_least=5, what="rebuilt aggregates")
    for state in result.aggregates.values():
        for name in state.event_names:
            assert contract_for(name).current_version == 1
    assert replay(GC1).digest() == result.digest()


def test_a_foreign_tenant_event_stops_a_bound_rebuild(tmp_path):
    """### TENANT CONTAMINATION. A rebuild bound to one tenant REFUSES a foreign fact — it does not
    filter it out. Filtering would make the answer depend on what happened to be in the source, and
    [C-1] enforced by a filter is one `if` away from not being enforced."""
    with pytest.raises(ReplayTenantViolation, match="does not filter"):
        replay(GC1, tenant="brokerage-northwind")

    only_a = [e for e in GC1 if e.tenant_id == "brokerage-northwind"]
    bound = replay(only_a, tenant="brokerage-northwind")
    assert bound.tenants == ("brokerage-northwind",)
    assert {k[0] for k in bound.aggregates} == {"brokerage-northwind"}


def test_two_tenants_reconstruct_disjoint_state_from_one_corpus():
    """The keys are tenant-FIRST, so two brokerages can never share an aggregate even when their
    aggregate ids collide."""
    whole = replay(GC1)
    keys_by_tenant: dict[str, set] = {}
    for tenant, agg_type, agg_id in whole.aggregates:
        keys_by_tenant.setdefault(tenant, set()).add((agg_type, agg_id))
    require_population(keys_by_tenant, at_least=2, what="tenants in GC-1")
    for tenant, keys in keys_by_tenant.items():
        alone = replay([e for e in GC1 if e.tenant_id == tenant], tenant=tenant)
        assert {(t, i) for _, t, i in alone.aggregates} == keys, (
            f"rebuilding {tenant} alone disagreed with its slice of the whole-corpus rebuild"
        )


def test_an_invalid_aggregate_reconstruction_is_impossible_because_state_is_keyed_by_identity():
    """### INVALID AGGREGATE RECONSTRUCTION. Two aggregates of DIFFERENT types sharing an id must
    never merge — a `brake` and a `work_item` both called `x-1` are two things."""
    a = make_canonical_envelope("WorkItemCreated", tenant=T_A, aggregate_id="x-1", seed="agg-a")
    b = make_canonical_envelope("BrakeEngaged", tenant=T_A, aggregate_id="x-1", seed="agg-b")
    result = replay([a, b])
    assert len(result.aggregates) == 2, result.aggregates
    assert {k[1] for k in result.aggregates} == {"work_item", "brake"}


def test_a_payload_rider_is_carried_by_the_transport_but_never_folded_into_truth():
    """§6 says a CONSUMER ignores an additive field. A rebuild must not fold one either:
    reconstructed truth is what the CONTRACT says the fact was, not whatever a producer attached."""
    contract = contract_for("PipelineStarted")
    clean = make_canonical_envelope("PipelineStarted", tenant=T_A, aggregate_id="pi-rider",
                                    seed="rider-clean")
    riddled = EventEnvelope.from_document(
        {**clean.as_document(), "payload": {**clean.payload, "injected_truth": "OWNER_ASSERTED"}})
    assert replay([riddled]).digest() == replay([clean]).digest(), (
        "an undeclared payload field changed reconstructed state"
    )
    folded = next(iter(replay([riddled]).aggregates.values()))
    assert "injected_truth" not in folded.fields
    assert set(folded.fields) <= contract.declared_field_names


# ================================================== 5. AC-EVT-015 — divergence, and its restraint

def test_a_divergence_between_rebuild_and_live_projection_is_reported_field_by_field():
    result = replay(GC1)
    key = next(k for k in sorted(result.aggregates) if result.aggregates[k].fields)
    field_name = sorted(result.aggregates[key].fields)[0]
    # The live projection AGREES everywhere except the one tampered field — otherwise every other
    # aggregate reports a divergence too and the assertion below could pass on the wrong finding.
    live = {k: dict(s.fields) for k, s in result.aggregates.items()}
    live[key][field_name] = "TAMPERED"
    findings = compare_to_live(result, live)
    assert findings, "an injected divergence was not detected"
    hit = next(f for f in findings if f.field == field_name)
    assert hit.live == "TAMPERED"
    assert hit.rebuilt == result.aggregates[key].fields[field_name]
    assert set(hit.as_payload()) == {"entity_ref", "field", "live", "rebuilt"}, (
        "the finding must be shaped to the ProjectionRebuildDiverged contract"
    )


def test_no_divergence_is_reported_when_the_projection_agrees():
    """The positive anchor: a detector that always fires detects nothing."""
    result = replay(GC1)
    live = {k: dict(s.fields) for k, s in result.aggregates.items()}
    assert compare_to_live(result, live) == []


def test_divergence_detection_engages_no_brake_and_emits_no_event():
    """### THE RESTRAINT THAT KEEPS REPLAY INERT. §11 requires `ProjectionRebuildDiverged` to
    auto-engage a tenant brake, and F14's cross-cutting rule requires that REPLAYING a security
    event never re-engages one — "the auto-action fired once, at the original occurrence". A
    detector that acted from inside a rebuild could not tell those apart, so it RETURNS findings,
    exactly as P4's orphan-effect detective sweep returns rather than acts.
    """
    import inspect

    from freight_recon import event_replay

    # ### THE BODY, NOT THE DOCSTRING. A substring scan over the whole function fires on its own
    # explanation of what it refuses to do — CLAUDE.md §9's "substring guards fire on their own
    # assertion text", caught here by this very check.
    function = next(n for n in ast.walk(ast.parse(inspect.getsource(event_replay)))
                    if isinstance(n, ast.FunctionDef) and n.name == "compare_to_live")
    body = [n for n in function.body if not (isinstance(n, ast.Expr)
                                             and isinstance(n.value, ast.Constant))]
    rendered = "\n".join(ast.unparse(n) for n in body)
    for forbidden in ("engage", "BrakeStore", "emit", "INSERT", "execute"):
        assert forbidden not in rendered, (
            f"compare_to_live's BODY contains {forbidden!r} — it must report a finding, not act"
        )
    assert "ProjectionRebuildDiverged" in inspect.getsource(event_replay), (
        "the F14 contract this finding is shaped to is not even named"
    )


# ============================================================== 6. AC-AUD — the eighteen fields

def _tenant_a_chain():
    return chain_for(GC1, tenant="brokerage-northwind",
                     aggregate_type="effect_grant", aggregate_id="eg-5501")


def test_explain_answers_all_eighteen_fields():
    """AC-AUD-001: a field-by-field assertion. Every key present, none silently dropped."""
    chain = require_population(_tenant_a_chain(), at_least=4, what="the eg-5501 causal chain")
    answer = explain(chain, subject="eg-5501", tenant="brokerage-northwind")
    assert tuple(answer.fields) == EIGHTEEN_FIELDS
    # ### AN EXACT SET, NOT A THRESHOLD. `at_least=12` was tuned to what the build then achieved,
    # so a six-field hole read as a pass. These three are HONEST absences in this chain — it has no
    # conflict, no verification (it ends in an UNKNOWN_OUTCOME), and its provenance-carrying claims
    # belong to the other tenant. Everything else must be reconstructed.
    assert set(answer.unreconstructible) == {
        "what_conflicted", "what_verification_proved", "provenance_of_material_facts",
    }, answer.unreconstructible


def test_an_unknown_outcome_is_explainable_AS_an_unknown():
    """AC-AUD-006: the reason, the exposure, and what was tried — not a blank."""
    answer = explain(_tenant_a_chain(), subject="eg-5501", tenant="brokerage-northwind")
    unknown = answer["what_was_unknown"]
    assert unknown != UNRECONSTRUCTIBLE, "an UNKNOWN_OUTCOME chain explained its unknown as absent"
    assert any(u["reason"] == "UNKNOWN_OUTCOME" for u in unknown), unknown
    assert any(u["exposure"] not in (None, UNRECONSTRUCTIBLE) for u in unknown)
    assert answer["adapter_operation_ran"] != UNRECONSTRUCTIBLE, "what was tried is unrecoverable"


def test_explanation_uses_the_beliefs_of_that_day_not_current_state():
    """### AC-AUD-002, THE RULE THAT DECIDES THE WHOLE DESIGN. Change the world today; the
    explanation of a 90-day-old decision must not move. It cannot, because `explain` reads only the
    events — the pins travelled WITH the fact, which is what §5 exists for.
    """
    before = explain(_tenant_a_chain(), subject="eg-5501", tenant="brokerage-northwind")

    # ### THE WORLD ACTUALLY MOVES HERE. An earlier version of this node built a newer
    # `PolicyActivated` and DISCARDED it, then compared two identical calls on one list — it could
    # not fail. Now the later facts are appended to the CORPUS and the chain is re-derived from it,
    # so if `explain` consulted anything but the chain's own pinned values the answer would shift.
    today = [
        make_envelope(tenant="brokerage-northwind", event_name="PolicyActivated",
                      aggregate_id="po-9999", aggregate_version=1, seed="today-policy",
                      payload={"policy_version": "policy-2026-12", "activated_by": "cfo-jo",
                               "effective_from": "2026-12-01T00:00:00.000Z",
                               "gate_decision": "HUMAN_APPROVAL_REQUIRED"}),
        make_envelope(tenant="brokerage-northwind", event_name="BrakeEngaged",
                      aggregate_id="br-99", aggregate_version=1, seed="today-brake",
                      payload={"scope": {"tenant": "brokerage-northwind"}, "actor": "detector-x",
                               "reason": "unrelated later incident", "brake_version": "brake-99"}),
    ]
    moved_world = [*GC1, *today]
    after = explain(
        chain_for(moved_world, tenant="brokerage-northwind",
                  aggregate_type="effect_grant", aggregate_id="eg-5501"),
        subject="eg-5501", tenant="brokerage-northwind")

    assert after.fields == before.fields, (
        "the explanation moved when the world moved — beliefs-of-that-day became beliefs-of-today"
    )
    assert before["policy_version_applied"] == "policy-2026-04"
    assert before["brake_version_applied"] == "brake-7"


def test_explain_reads_no_store_and_takes_no_connection():
    """The mechanism behind AC-AUD-002: if it cannot look anything up, it cannot look up TODAY's."""
    import inspect

    from freight_recon import event_audit

    signature = inspect.signature(explain)
    assert set(signature.parameters) == {"events", "subject", "tenant"}, signature
    source = inspect.getsource(event_audit)
    for forbidden in ("sqlite3", "execute(", "WorkflowStore", "requests", "urllib"):
        assert forbidden not in source, f"event_audit reaches {forbidden!r}"


def test_an_absent_fact_is_reported_as_unreconstructible_never_invented():
    """### A PLAUSIBLE ANSWER IS WORSE THAN A STATED ABSENCE. "We have no evidence of an approval"
    and "there was no approval" are different findings; rendering them identically makes the audit
    untrustworthy about the second."""
    lonely = [make_canonical_envelope("WorkStarted", tenant=T_A, aggregate_id="wi-lonely",
                                      seed="lonely")]
    answer = explain(lonely, subject="wi-lonely", tenant=T_A)
    assert answer["what_approval_existed"] == UNRECONSTRUCTIBLE
    # The envelope-PIN fields too, which are the ones `_last` answers — a chain with no
    # consequential event pinned no policy, no brake and no fingerprint, and each must SAY so.
    for pinned in ("policy_version_applied", "brake_version_applied",
                   "material_facts_fingerprint", "entity_versions_pinned", "accountable_owner",
                   "commit_key_held"):
        assert answer[pinned] == UNRECONSTRUCTIBLE, (
            f"{pinned} answered {answer[pinned]!r} for a chain that pinned nothing — an invented "
            f"answer is worse than a stated absence"
        )
    assert answer["why_the_work_item_closed_or_stayed_open"]["state"] == "STILL_OPEN", (
        "a chain with no closure event must say the obligation is STILL OPEN, not stay silent"
    )


def test_the_audit_answer_agrees_with_the_reconstructed_state():
    """### AUDIT RESULT DISAGREEING WITH RECONSTRUCTED STATE — the failure mode where two readings
    of one history diverge and nobody notices. The facts `explain` reports as known must be the
    facts the rebuild folded."""
    chain = _tenant_a_chain()
    answer = explain(chain, subject="eg-5501", tenant="brokerage-northwind")
    rebuilt = replay(chain).aggregates
    grant_state = next(s for k, s in rebuilt.items() if k[2] == "eg-5501")
    known = answer["what_was_known"]["effect_grant:eg-5501"]
    require_population(grant_state.fields, at_least=1, what="folded fields on eg-5501")
    for name, value in grant_state.fields.items():
        assert name in known, f"the rebuild folded {name!r} and the explanation does not know it"
        assert known[name] == value, f"{name}: audit says {known[name]!r}, rebuild says {value!r}"
    # And the reverse: every aggregate the chain touches is reported, none silently merged.
    assert set(answer["what_was_known"]) == {f"{k[1]}:{k[2]}" for k in rebuilt}
    assert set(answer.trace) == {e.event_id for e in chain}


def test_explain_refuses_to_cross_a_tenant_boundary():
    chain = [*_tenant_a_chain(),
             make_canonical_envelope("WorkItemCreated", tenant=T_B, aggregate_id="wi-foreign",
                                     seed="foreign")]
    with pytest.raises(AuditError, match=r"\[C-1\]"):
        explain(chain, subject="eg-5501", tenant="brokerage-northwind")


def test_explain_refuses_an_empty_chain():
    with pytest.raises(AuditError, match="no events"):
        explain([], subject="nothing", tenant=T_A)


def test_the_causal_chain_follows_causation_transitively_within_one_tenant():
    chain = _tenant_a_chain()
    ids = {e.event_id for e in chain}
    grant = next(e for e in GC1 if e.event_name == "EffectGranted")
    assert grant.event_id in ids
    # OutcomeUnknown is caused by EffectAttempted, which is caused by GrantClaimed — three hops.
    assert any(e.event_name == "OutcomeUnknown" for e in chain), "the walk stopped short"
    assert all(e.tenant_id == "brokerage-northwind" for e in chain)


# ============================================================ 7. the transport still agrees

def test_a_replayed_corpus_still_consumes_normally_through_the_live_inbox(tmp_path):
    """Replay reading history must not change how the live path treats the same facts — the two
    are different readings of one corpus, and a rebuild is not a substitute for consumption."""
    store = make_store(tmp_path, tenant="brokerage-cascade")
    inbox = make_inbox(store, tenant="brokerage-cascade")
    handler = RecordingHandler(store.conn)
    tenant_b = [e for e in GC1 if e.tenant_id == "brokerage-cascade"]
    require_population(tenant_b, at_least=4, what="tenant-B events")
    applied = sum(1 for e in tenant_b if inbox.consume(e, handler).applied)
    assert applied == len(tenant_b), (
        f"the live inbox applied {applied} of {len(tenant_b)} facts the rebuild accepted"
    )
    store.close()


# ====================================== 8. AC-EVT-009 — v1 → v2 → v3 through the real replay path

# ### WHY THIS FIXTURE IS SYNTHETIC, AND WHY THAT IS THE CORRECT ANSWER RATHER THAN A CONCESSION.
#
# `AC-EVT-009`'s oracle is "v1+v2+v3 in one corpus ⇒ one digest; run twice ⇒ identical", and GC-1
# is required to span ">=1 schema version change". Every one of the 118 canonical contracts is at
# v1: a schema version change requires a BREAKING change to a canonical contract plus a registered
# upcaster (§6), which is a specification amendment under founder/architect authority — the same
# authority that minted 98 → 105.
#
# Neither the oracle nor the span says the versioned contract must be one of the 105. GC-1 is
# labelled "(immutable fixture)". So the chain is proven with a TEST-ONLY contract through the REAL
# replay path — the smallest thing that proves the mechanism without inventing production history
# that never happened. GC-1 itself stays purely canonical, which is what makes IT trustworthy.
#
# The seam this uses (`replay(..., contracts=...)`) changes what a REBUILD accepts and can never
# change what may be EMITTED; the node above asserts the emit path has no such parameter.

_SYNTHETIC_NAME = "SyntheticVersionedFact"


def _versioned_contract(version: int) -> dict:
    """A test-only contract at `version`. v3 declares `total_minor`; v1 declared `amount`."""
    return {
        _SYNTHETIC_NAME: CanonicalContract(
            name=_SYNTHETIC_NAME, family="F2", source="(test-only)", current_version=version,
            producers=("PL-1",), coordination=False, aggregate_type="pipeline_instance",
            emitted_corpus=True, consequential=False, strict_order=True, human_only=False,
            consequential_conditional=False,
            fields=(FieldSpec("total_minor", True, False, None, None),), one_of=(),
        )
    }


def _versioned_corpus() -> list:
    """One aggregate, three facts, stamped v1, v2 and v3 — a genuinely mixed-version history."""
    events = []
    for index, (version, payload) in enumerate((
        (1, {"amount": 100}),                      # v1's shape
        (2, {"amount_minor": 20000}),              # v2's shape
        (3, {"total_minor": 30000}),               # v3's shape — the current one
    ), start=1):
        base = make_envelope(event_name="PipelineStarted", aggregate_id="pi-versioned",
                             aggregate_version=index, seed=f"versioned-{index}")
        events.append(EventEnvelope.from_document({
            **base.as_document(), "event_name": _SYNTHETIC_NAME,
            "event_version": version, "payload": payload,
        }))
    return events


def _versioned_upcasters():
    registry = UpcasterRegistry(_versioned_contract(3))
    # v1 → v2: the field was renamed and re-denominated into minor units.
    registry.register(_SYNTHETIC_NAME, 1,
                      lambda p: {"amount_minor": int(p["amount"]) * 100})
    # v2 → v3: renamed again.
    registry.register(_SYNTHETIC_NAME, 2,
                      lambda p: {"total_minor": p["amount_minor"]})
    return registry


def test_a_mixed_version_corpus_upcasts_to_one_digest_deterministically():
    """AC-EVT-009, through the REAL replay path rather than against the registry in isolation."""
    contracts, corpus = _versioned_contract(3), _versioned_corpus()
    assert {e.event_version for e in corpus} == {1, 2, 3}, "the corpus is not mixed-version"

    first = replay(corpus, contracts=contracts, upcasters=_versioned_upcasters())
    second = replay(corpus, contracts=contracts, upcasters=_versioned_upcasters())
    assert first.digest() == second.digest(), "two rebuilds of one corpus disagreed"
    assert first.events_folded == 3

    # Every historical version emerged at the CURRENT one, and the v1 fact's value survived BOTH
    # hops — 100 → 20000? no: 100 * 100 = 10000, then renamed. The arithmetic is the upcaster's.
    state = next(iter(first.aggregates.values()))
    assert set(state.fields) == {"total_minor"}, state.fields
    assert state.version == 3

    # And shuffling still yields the same digest, so upcasting has not reintroduced order-dependence.
    for seed in (3, 11):
        shuffled = corpus[:]
        random.Random(seed).shuffle(shuffled)
        assert replay(shuffled, contracts=contracts,
                      upcasters=_versioned_upcasters()).digest() == first.digest()


def test_the_v1_fact_is_upcast_through_every_hop_not_skipped():
    """A v1 body read as v3 would carry two versions of assumptions the reader cannot see. Each hop
    must run, in order, and the value must show it."""
    contracts = _versioned_contract(3)
    v1_only = [_versioned_corpus()[0]]
    result = replay(v1_only, contracts=contracts, upcasters=_versioned_upcasters())
    state = next(iter(result.aggregates.values()))
    assert state.fields == {"total_minor": 10000}, (
        f"expected 100 → (×100) 10000 → renamed; got {state.fields}"
    )


def test_a_missing_upcaster_hop_stops_the_rebuild_rather_than_guessing():
    """M-25: no historical event may become unreadable because current code changed — and the
    honest answer to a missing link is to say so, never to fold the body as-is."""
    contracts = _versioned_contract(3)
    broken = UpcasterRegistry(contracts)
    broken.register(_SYNTHETIC_NAME, 2, lambda p: {"total_minor": p["amount_minor"]})
    with pytest.raises(ReplayError):
        replay([_versioned_corpus()[0]], contracts=contracts, upcasters=broken)


def test_the_reconstruction_seam_cannot_widen_what_may_be_emitted(tmp_path):
    """### THE SEAM'S SAFETY PROPERTY, ASSERTED RATHER THAN ARGUED. A rebuild may read history
    through an explicit contract set; the outbox still refuses the same event, because its gate
    resolves through the canonical registry and takes no contract parameter."""
    from freight_recon.event_contracts import UnknownEventName

    store = make_store(tmp_path)
    synthetic = _versioned_corpus()[2]
    with pytest.raises(UnknownEventName):
        with transactional_emit(store.conn, tenant=T_A) as session:
            session.emit(synthetic)
    store.close()


# ============================ 9. regressions for the five defects an independent review found

def test_the_causal_chain_collects_ANCESTORS_not_only_descendants():
    """### B-4. An effect's explanation lives mostly in what came BEFORE it. A descendants-only
    walk returned an `eg-5501` chain with no `CheckpointPassed`, no `ApprovalGranted` and no
    `WorkItemCreated`, so six of the eighteen came back UNRECONSTRUCTIBLE against facts sitting in
    the same corpus."""
    chain = _tenant_a_chain()
    names = {e.event_name for e in chain}
    for ancestor in ("CheckpointPassed", "ApprovalGranted", "ApprovalRequested",
                     "PolicyEvaluated", "PipelineStarted", "WorkItemCreated"):
        assert ancestor in names, f"{ancestor} causes part of this chain and is not in it"
    answer = explain(chain, subject="eg-5501", tenant="brokerage-northwind")
    assert answer["why_the_checkpoint_passed_or_failed"] != UNRECONSTRUCTIBLE
    assert answer["accountable_owner"] == "dispatcher-amy"
    assert "human:controller-dana" in answer["who_acted"], (
        "the human who approved the money action is missing from who acted"
    )


def test_the_pins_come_from_the_subjects_own_aggregate():
    """### B-2. Taking the last pin across a multi-aggregate chain reported the COMPENSATION's
    SD-3 set as the EFFECT's — and was green only because a redelivered event happened to sit last
    in corpus order, so a fixture's arrangement was holding up a correctness assertion."""
    chain = _tenant_a_chain()
    answer = explain(chain, subject="eg-5501", tenant="brokerage-northwind")
    granted = next(e for e in chain if e.event_name == "EffectGranted")
    assert answer["entity_versions_pinned"] == granted.entity_versions, (
        f"the effect's SD-3 set is {granted.entity_versions}; the audit reported "
        f"{answer['entity_versions_pinned']}"
    )
    # Invariant to unrelated later aggregates being appended to the chain.
    extra = make_canonical_envelope("CompensationApproved", tenant="brokerage-northwind",
                                    aggregate_id="cm-9999", seed="later-comp",
                                    entity_versions={"compensation:cm-9999": 1})
    assert explain([*chain, extra], subject="eg-5501",
                   tenant="brokerage-northwind")["entity_versions_pinned"] == \
        granted.entity_versions


def test_explain_is_invariant_to_a_redelivered_fact():
    """### B-3. An audit reporting one grant claimed TWICE is materially misleading —
    `GrantDoubleClaimAttempted` is a real F14 security event. And `as_of` must be a TIME, not the
    last position in corpus order."""
    chain = _tenant_a_chain()
    once = explain(chain, subject="eg-5501", tenant="brokerage-northwind")
    twice = explain([*chain, chain[0], chain[-1]], subject="eg-5501",
                    tenant="brokerage-northwind")
    assert once.fields == twice.fields, "a redelivered fact changed the explanation"
    assert once.trace == twice.trace
    assert len(set(once.trace)) == len(once.trace), "the trace lists an event twice"
    # ### THE CHAIN IS DELIBERATELY OUT OF TIME ORDER HERE. Handed in corpus order the two answers
    # coincide, so the mutant that reverts to `ordered[-1]` is invisible — the case only bites when
    # the last POSITION is not the latest INSTANT, which is exactly what an out-of-order delivery
    # produces and what `as_of` must survive.
    shuffled = sorted(chain, key=lambda e: e.event_id)
    assert shuffled[-1].occurred_at != max(e.occurred_at for e in chain), (
        "the fixture no longer exercises a corpus order that differs from time order"
    )
    out_of_order = explain(shuffled, subject="eg-5501", tenant="brokerage-northwind")
    assert out_of_order.as_of == max(e.occurred_at for e in chain), "as_of is corpus order, not time"
    assert out_of_order.fields == once.fields, "the explanation depends on corpus order"


def test_two_different_facts_sharing_one_event_id_are_refused():
    """### B-5. Dedup must PROVE identity, not assume it. §1 makes `event_id` globally unique, so
    two different bodies under one id is corpus corruption — and first-wins-by-arrival made the
    rebuild order-dependent again (same set, two orders, two digests) while swallowing it."""
    target = next(e for e in GC1 if e.event_name == "OutcomeUnknown")
    forged = EventEnvelope.from_document(
        {**target.as_document(),
         "payload": {**target.payload, "exposure": {"amount_minor": 999999, "currency": "USD"}}})
    with pytest.raises(ReplayError, match="DIFFERENT bodies"):
        replay([*GC1, forged])
    forensic = replay([*GC1, forged], strict=False)
    assert any("DIFFERENT bodies" in reason for _, reason in forensic.rejected)
    # A genuine redelivery — byte-identical — is still a harmless no-op.
    assert replay([*GC1, target]).digest() == replay(GC1).digest()


@pytest.mark.parametrize("spelling,source", [
    ("absolute from-import", "from freight_recon.effect_boundary import execute_effect"),
    ("relative bare import", "from . import checkpoint"),
    ("absolute import", "import freight_recon.brake"),
    ("dynamic import", "importlib.import_module('freight_recon.workflow')"),
])
def test_the_import_closure_walk_sees_every_import_spelling(spelling, source):
    """### B-1, THE MOST SERIOUS FINDING. The walk tested `node.level`, so it saw only RELATIVE
    from-imports — and `from freight_recon.effect_boundary import execute_effect` has `level == 0`.
    This package contains 26 absolute imports in that style, and for `effect_boundary` and
    `checkpoint` this walk is the SOLE control (the P4 gate covers only effect-capable ADAPTERS).
    `import_probe._module_name` had already solved it, and CLAUDE.md §9 lists this blind spot as a
    repeat offender. The mandated M-27 proof was being proven against one spelling in four.
    """
    import inspect

    # ### THE BODY, NOT THE DOCSTRING — and this check caught itself doing it. A plain substring
    # scan fired on its own explanation of the defect, which is CLAUDE.md §9's "substring guards
    # fire on their own assertion text" happening live, in the guard written to prevent it.
    walker = next(
        n for n in ast.walk(ast.parse(inspect.getsource(
            test_replay_cannot_reach_an_effect_capable_module)))
        if isinstance(n, ast.FunctionDef) and n.name == "reached_by")
    body = [n for n in walker.body
            if not (isinstance(n, ast.Expr) and isinstance(n.value, ast.Constant))]
    assert "node.level" not in "\n".join(ast.unparse(n) for n in body), (
        "the closure walk is gated on `node.level` again — absolute imports become invisible"
    )
    tree = ast.parse(source)
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module:
                found.append(node.module.split(".")[-1])
            for alias in node.names:
                found.append(alias.name.split(".")[-1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.append(alias.name.split(".")[-1])
        elif isinstance(node, ast.Call):
            target = getattr(node.func, "attr", None) or getattr(node.func, "id", None)
            if target in {"import_module", "__import__"}:
                for argument in node.args:
                    if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                        found.append(argument.value.split(".")[-1])
    forbidden = {"effect_boundary", "checkpoint", "brake", "workflow"}
    assert set(found) & forbidden, f"{spelling} was invisible to the closure walk: {found}"
