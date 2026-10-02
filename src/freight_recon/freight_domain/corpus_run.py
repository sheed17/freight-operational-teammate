"""P9 — run freight histories through the spine and measure what came out.

`run_corpus` feeds every history, in order, into ONE database shared by every brokerage in the corpus
— so tenant isolation is exercised where it actually has to hold, not in separate files — and returns
the canonical projections, the per-record outcomes and a machine-readable report.

### THE REPORT COUNTS; IT DOES NOT GRADE. Every figure is a count of canonical rows or of labeled
outcomes. There is no accuracy percentage: a percentage needs a labeled denominator, and where a
history carries a labeled expectation it is CHECKED, one by one, and the mismatches are listed.

### NO MONEY VALUES ARE REPORTED. The report carries counts and discrepancy codes. Amounts stay in the
canonical records and on the rendered timeline.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from .financial import blocking_discrepancies
from .history import FreightHistory, TenantSetup
from .intake import FreightIntake, RecordOutcome
from .projection import FreightProjection, LoadView
from .timeline import render_timeline

REPORT_VERSION = "p9-freight-corpus-report-1"


@dataclass
class HistoryResult:
    history: FreightHistory
    outcomes: list[RecordOutcome]
    load_ids: tuple[str, ...]
    mismatches: list[str] = field(default_factory=list)
    checks: int = 0


@dataclass
class CorpusResult:
    intakes: dict[str, FreightIntake]
    projections: dict[str, FreightProjection]
    histories: list[HistoryResult]
    report: dict[str, Any]

    def view(self, tenant: str, load_ref: str) -> LoadView:
        view = self.projections[tenant].view_by_load_ref(load_ref)
        if view is None:
            raise KeyError(f"{tenant} has no load currently numbered {load_ref!r}")
        return view

    def history(self, history_id: str) -> HistoryResult:
        return next(h for h in self.histories if h.history.history_id == history_id)

    def outcome(self, history_id: str, label: str) -> RecordOutcome:
        return next(o for o in self.history(history_id).outcomes if o.label == label)


# --------------------------------------------------------------------------- cross-tenant audit

def cross_tenant_violations(conn: sqlite3.Connection) -> list[str]:
    """Every way a binding or a mapping could reach across brokerages, checked over the WHOLE
    database. This is the one deliberately un-scoped read in the package: it is the audit that the
    tenant-scoped code could not perform on itself.

    A load id belongs to the tenant whose mappings define it. A violation is a CONFIRMED binding
    whose entity belongs to another tenant, a binding whose subject Observation is another tenant's,
    or a mapping read from another tenant's Observation."""
    violations: list[str] = []
    owner: dict[str, set[str]] = {}
    for row in conn.execute(
            "SELECT tenant, neyma_entity_type, neyma_entity_id FROM external_entity_mappings"):
        owner.setdefault(f"{row[1]}:{row[2]}", set()).add(row[0])
    for ref, tenants in sorted(owner.items()):
        if len(tenants) > 1:
            violations.append(f"entity {ref} is mapped under several tenants {sorted(tenants)}")
    for row in conn.execute(
            "SELECT tenant, binding_claim_id, subject_ref, entity_ref FROM identity_binding_claims "
            "WHERE state = 'CONFIRMED'"):
        tenants = owner.get(row[3])
        if tenants is not None and row[0] not in tenants:
            violations.append(
                f"claim {row[1]} of tenant {row[0]} binds to {row[3]}, an entity of {sorted(tenants)}")
    for row in conn.execute(
            "SELECT c.tenant, c.binding_claim_id FROM identity_binding_claims c WHERE NOT EXISTS "
            "(SELECT 1 FROM observations o WHERE o.tenant = c.tenant "
            "AND o.observation_id = c.subject_ref)"):
        # The composite foreign key makes this unreachable; it is queried so that is MEASURED.
        violations.append(f"claim {row[1]} of {row[0]} has a subject that is not its own")
    for row in conn.execute(
            "SELECT m.tenant, m.mapping_id FROM external_entity_mappings m WHERE NOT EXISTS "
            "(SELECT 1 FROM observations o WHERE o.tenant = m.tenant "
            "AND o.observation_id = m.source_observation_id)"):
        violations.append(f"mapping {row[1]} of {row[0]} cites an observation that is not its own")
    return violations


def shared_reference_population(conn: sqlite3.Connection) -> int:
    """How many outside references appear under MORE than one tenant. The cross-tenant audit is a
    negative assertion; this is the population that makes it mean something."""
    return int(conn.execute(
        "SELECT COUNT(*) FROM (SELECT external_system, external_id_kind, external_id "
        "FROM external_entity_mappings GROUP BY external_system, external_id_kind, external_id "
        "HAVING COUNT(DISTINCT tenant) > 1)").fetchone()[0])


# --------------------------------------------------------------------------- labeled expectations

def _check(result: HistoryResult, what: str, actual: Any, expected: Any) -> None:
    result.checks += 1
    if actual != expected:
        result.mismatches.append(f"{what}: expected {expected!r}, got {actual!r}")


def check_expected(result: HistoryResult, projection: FreightProjection) -> None:
    """Assert a history's labeled expected outcomes, one by one, against what Neyma produced. Only
    what a history LABELS is checked — an unlabeled outcome is measured, never graded."""
    expected = result.history.expected
    outcomes = {o.label: o for o in result.outcomes}
    hid = result.history.history_id

    for label, want in (expected.get("records") or {}).items():
        outcome = outcomes.get(label)
        if outcome is None:
            result.checks += 1
            result.mismatches.append(f"{hid}/{label}: no such record was ingested")
            continue
        _check(result, f"{hid}/{label} disposition", outcome.disposition, want["disposition"])
        if "load" in want:
            view = projection.view_by_load_ref(want["load"])
            _check(result, f"{hid}/{label} bound load", outcome.load_id,
                   view.load_id if view else f"<no load {want['load']}>")
        if "candidates" in want:
            wanted = sorted(
                v.load_id for v in (projection.view_by_load_ref(r) for r in want["candidates"])
                if v is not None)
            _check(result, f"{hid}/{label} candidate loads",
                   sorted(outcome.candidate_load_ids), wanted)
        if "ambiguity" in want:
            _check(result, f"{hid}/{label} ambiguity", outcome.ambiguity, want["ambiguity"])

    for load_ref, want in (expected.get("loads") or {}).items():
        view = projection.view_by_load_ref(load_ref)
        result.checks += 1
        if view is None:
            result.mismatches.append(f"{hid}: no canonical load is numbered {load_ref}")
            continue
        where = f"{hid}/{load_ref}"
        if "movements" in want:
            _check(result, f"{where} movements", len(view.movements), want["movements"])
        if "reported_status" in want:
            _check(result, f"{where} reported status", view.load.value("reported_status"),
                   want["reported_status"])
        if "delivered_claimed" in want:
            _check(result, f"{where} delivery reported", bool(view.delivered_claims()),
                   want["delivered_claimed"])
        if "documents" in want:
            counts: dict[str, int] = {}
            for document in view.documents.values():
                kind = str(document.value("doc_type"))
                counts[kind] = counts.get(kind, 0) + 1
            _check(result, f"{where} documents", counts, dict(want["documents"]))
        if "payables" in want:
            _check(result, f"{where} payables", len(view.payables), want["payables"])
        if "duplicate_invoices" in want:
            _check(result, f"{where} duplicate invoices",
                   sum(len(p.duplicate_observation_ids) for p in view.payables.values()),
                   want["duplicate_invoices"])
        if "duplicate_evidence" in want:
            _check(result, f"{where} duplicate evidence", len(view.duplicate_evidence_arrivals),
                   want["duplicate_evidence"])
        if "requirements" in want:
            _check(result, f"{where} document requirements",
                   {r.required_doc_type: r.state for r in view.requirements},
                   dict(want["requirements"]))
        if "expectations" in want:
            latest: dict[str, str] = {}
            for expectation in view.expectations:
                latest[expectation["expected_type"]] = expectation["state"]
            _check(result, f"{where} expectations", latest, dict(want["expectations"]))
        if "conflict_fields" in want:
            _check(result, f"{where} conflicts",
                   sorted(c["field"] for c in view.conflicts), sorted(want["conflict_fields"]))
        if "exception_types" in want:
            _check(result, f"{where} exceptions",
                   sorted({x["type"] for x in view.exceptions}), sorted(want["exception_types"]))
        if "reconciliation" in want:
            _check(result, f"{where} reconciliation",
                   sorted(r.status for r in view.reconciliations), sorted(want["reconciliation"]))
        if "discrepancy_codes" in want:
            _check(result, f"{where} discrepancies",
                   sorted(d.code for r in view.reconciliations for d in blocking_discrepancies(r)),
                   sorted(want["discrepancy_codes"]))
        if "invoice_eligible" in want:
            _check(result, f"{where} invoice eligibility",
                   view.invoice is not None and view.invoice.lifecycle_state == "ELIGIBLE",
                   want["invoice_eligible"])
        if "accessorials" in want:
            _check(result, f"{where} accessorials",
                   {k: v.lifecycle_state for k, v in view.accessorials.items()},
                   dict(want["accessorials"]))
        if "authorizations" in want:
            _check(result, f"{where} authorizations", len(view.authorizations),
                   want["authorizations"])
        if "needs_human" in want:
            _check(result, f"{where} needs a human", bool(view.attention), want["needs_human"])
        if "retired_references" in want:
            _check(result, f"{where} retired references",
                   sorted(m.external_id for m in view.mappings if m.state != "ACTIVE"),
                   sorted(want["retired_references"]))
        if "appointment_conditions" in want:
            _check(result, f"{where} appointment windows",
                   {k: a.condition("window") for k, a in view.appointments.items()},
                   dict(want["appointment_conditions"]))
        if "timeline_kinds" in want:
            kinds = {t.kind for t in view.timeline}
            for kind in want["timeline_kinds"]:
                _check(result, f"{where} timeline has {kind}", kind in kinds, True)

    if "unbound" in expected:
        labels = {o.observation_id: o.label for o in result.outcomes if o.observation_id}
        mine = sorted(labels[u.observation_id] for u in projection.unbound
                      if u.observation_id in labels)
        _check(result, f"{hid} unbound at the end", mine, sorted(expected["unbound"]))


# --------------------------------------------------------------------------- the run

def run_corpus(conn: sqlite3.Connection, setups: Mapping[str, TenantSetup],
               histories: Sequence[FreightHistory]) -> CorpusResult:
    """Run every history through its brokerage's intake, on one shared database."""
    intakes: dict[str, FreightIntake] = {}
    results: list[HistoryResult] = []
    for history in histories:
        intake = intakes.get(history.tenant)
        if intake is None:
            intake = FreightIntake(conn, setups[history.tenant])
            intakes[history.tenant] = intake
        outcomes = intake.run(history)
        results.append(HistoryResult(
            history=history, outcomes=outcomes,
            load_ids=tuple(dict.fromkeys(o.load_id for o in outcomes if o.load_id))))
    projections = {tenant: intake.projection() for tenant, intake in intakes.items()}
    for result in results:
        check_expected(result, projections[result.history.tenant])
    report = build_report(conn, intakes, projections, results)
    return CorpusResult(intakes=intakes, projections=projections, histories=results, report=report)


def build_report(conn: sqlite3.Connection, intakes: Mapping[str, FreightIntake],
                 projections: Mapping[str, FreightProjection],
                 results: Sequence[HistoryResult]) -> dict[str, Any]:
    views = [view for projection in projections.values() for view in projection.loads.values()]
    unbound = [item for projection in projections.values() for item in projection.unbound]
    stats: dict[str, int] = {}
    for intake in intakes.values():
        for key, value in intake.stats.as_document().items():
            stats[key] = stats.get(key, 0) + value
    reconciliations = [r for view in views for r in view.reconciliations]
    discrepancies = [d for r in reconciliations for d in blocking_discrepancies(r)]
    mismatch_codes: dict[str, int] = {}
    for discrepancy in discrepancies:
        mismatch_codes[discrepancy.code] = mismatch_codes.get(discrepancy.code, 0) + 1
    expectations = [e for view in views for e in view.expectations]
    requirements = [r for view in views for r in view.requirements]
    effects = {tenant: intake.foundation.effect_surface_counts()
               for tenant, intake in sorted(intakes.items())}
    violations = cross_tenant_violations(conn)

    metrics = {
        "histories_processed": len(results),
        "records_received": stats.get("records_received", 0),
        "observations_created": stats.get("observations_created", 0),
        "canonical_loads_produced": len(views),
        "external_entity_mappings_recorded": sum(len(p.mappings) for p in projections.values()),
        "exact_external_mappings_resolved": stats.get("exact_bindings", 0),
        "late_bindings_after_mapping_arrived": stats.get("late_bindings", 0),
        "human_asserted_bindings": stats.get("human_bindings", 0),
        "ambiguous_mappings": stats.get("ambiguous_bindings", 0),
        "ambiguous_mappings_still_unresolved": len([u for u in unbound if u.reason == "ambiguous"]),
        "unresolved_references": len([u for u in unbound if u.reason == "absent"]),
        "unparseable_records": stats.get("unparseable", 0),
        "refused_records": stats.get("refused", 0),
        "wrong_cross_tenant_mappings": len(violations),
        "references_shared_across_tenants": shared_reference_population(conn),
        "duplicate_inputs_suppressed": stats.get("duplicates_suppressed", 0),
        "duplicate_evidence_recognized": sum(len(v.duplicate_evidence_arrivals) for v in views),
        "duplicate_invoices_recognized": sum(
            len(p.duplicate_observation_ids) for v in views for p in v.payables.values()),
        "conflicts_raised": sum(len(v.conflicts) for v in views),
        "conflicts_open": sum(len(v.open_conflicts()) for v in views),
        "expectations_raised": len(expectations),
        "expectations_discharged": len([e for e in expectations if e["state"] == "DISCHARGED"]),
        "expectations_discharged_late": len([e for e in expectations if e["late"]]),
        "overdue_expectations": len([e for e in expectations if e["state"] == "OVERDUE"]),
        "indeterminate_expectations": len(
            [e for e in expectations if e["state"] == "INDETERMINATE"]),
        "unresolved_document_requirements": len(
            [r for r in requirements if r.state in ("OUTSTANDING", "UNKNOWN")]),
        "document_requirements_unknown": len([r for r in requirements if r.state == "UNKNOWN"]),
        "reconciliations_computed": len(reconciliations),
        "reconciliations_reconciled": len([r for r in reconciliations if r.status == "RECONCILED"]),
        "reconciliations_discrepant": len([r for r in reconciliations if r.status == "DISCREPANT"]),
        "reconciliation_discrepancies": len(
            [d for d in discrepancies if d.code != "EXPECTED_BUY_UNESTABLISHED"]),
        "reconciliations_without_an_established_buy": mismatch_codes.get(
            "EXPECTED_BUY_UNESTABLISHED", 0),
        "exceptions_raised": sum(len(i.foundation.exceptions()) for i in intakes.values()),
        "open_exceptions_for_cured_expectations": sum(len(v.housekeeping) for v in views),
        "loads_requiring_human_attention": len([v for v in views if v.attention]),
        "human_attention_required": (len([v for v in views if v.attention]) + len(unbound)),
        "external_effect_rows": sum(sum(c.values()) for c in effects.values()),
        "labeled_expectations_checked": sum(r.checks for r in results),
        "labeled_expectations_failed": sum(len(r.mismatches) for r in results),
    }
    return {
        "report_version": REPORT_VERSION,
        "note": ("Synthetic development corpus. Nothing here is design-partner evidence, and no "
                 "freight rule is validated by appearing in it."),
        "metrics": metrics,
        "discrepancy_codes": dict(sorted(mismatch_codes.items())),
        "cross_tenant_violations": violations,
        "effect_surface_rows": effects,
        "histories": [{
            "history_id": r.history.history_id,
            "title": r.history.title,
            "tenant": r.history.tenant,
            "hostile": list(r.history.hostile),
            "records": len(r.history.records),
            "dispositions": _tally(o.disposition for o in r.outcomes),
            "loads": len(r.load_ids),
            "labeled_checks": r.checks,
            "labeled_mismatches": list(r.mismatches),
        } for r in results],
    }


def _tally(items: Any) -> dict[str, int]:
    out: dict[str, int] = {}
    for item in items:
        out[item] = out.get(item, 0) + 1
    return dict(sorted(out.items()))


def render_corpus(result: CorpusResult) -> str:
    """Every history's operational timeline, for a human watching the corpus go through."""
    blocks: list[str] = []
    for item in result.histories:
        history = item.history
        projection = result.projections[history.tenant]
        blocks.append(f"=== {history.history_id} - {history.title}")
        blocks.append(f"    hostile: {', '.join(history.hostile) or 'none'}")
        for load_id in item.load_ids:
            view = projection.loads[load_id]
            blocks.append(render_timeline(view))
            if view.invoice is not None:
                blocks.append(f"  invoice eligibility: {view.invoice.lifecycle_state}"
                              + ("" if not view.invoice.blockers
                                 else " - " + "; ".join(view.invoice.blockers)))
            if view.attention:
                blocks.append("  needs a human: " + ", ".join(view.attention))
        held = [o for o in item.outcomes if o.disposition in ("AMBIGUOUS", "UNBOUND",
                                                                "UNPARSEABLE", "REFUSED")]
        for outcome in held:
            blocks.append(f"  held [{outcome.disposition}] {outcome.label}: "
                          f"{outcome.ambiguity or outcome.detail}")
        if item.mismatches:
            blocks.extend(f"  !! {m}" for m in item.mismatches)
        blocks.append("")
    return "\n".join(blocks)
