"""P7 — the identity / lineage / conflict / correction slice — acceptance and hostile battery.

  * AC-7  — evidence/claim lineage is traversable, and fails closed on a missing link.
  * AC-8  — the deterministic linker: the model READS but never DECIDES the binding.
  * AC-9  — an OWNER_ASSERTED binding survives relink/replay; weak/ambiguous fails closed.
  * AC-10 — Conflict is first-class and blocking, and closes ONLY via a registered rule or a human.
  * AC-11 — correction vs supersession, with retained attributable history.
  * F14   — a refused R-P2 strengthening emits the registered ProvenanceStrengtheningAttempted.

Each rule has a refusal AND a positive control. Several node ids are the guards
`scripts/mutate_phase7_identity.py` turns RED.
"""

from __future__ import annotations

import ast
import sqlite3
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "freight_recon"

from freight_recon import lineage as LG  # noqa: E402
from freight_recon import linker as L  # noqa: E402
from freight_recon import provenance as P  # noqa: E402
from freight_recon.checkpoint import ProvenanceClass  # noqa: E402
from freight_recon.evidence import EvidenceStore  # noqa: E402
from freight_recon.migrations.phase6_conflicts import TERMINAL_CONFLICT_STATES  # noqa: E402
from freight_recon.migrations.phase6_identity_binding_claims import (  # noqa: E402
    CONFIRMED_ALLOWED_PROVENANCE,
    MATCH_METHODS,
    PROVENANCE_BY_METHOD,
)
from freight_recon.schema import create_canonical_schema, enable_and_verify_foreign_keys  # noqa: E402

T_A = "acme-brokerage"
NOW = "2026-09-09T12:00:00.000Z"


def require_population(items, what: str):
    assert items, f"no {what} to assert over - this test would pass vacuously"
    return items


def _evidence_store_with_span():
    tmp = Path(tempfile.mkdtemp(prefix="p7id-test-"))
    conn = sqlite3.connect(str(tmp / "e.db"))
    conn.row_factory = sqlite3.Row
    enable_and_verify_foreign_keys(conn)
    create_canonical_schema(conn)
    enable_and_verify_foreign_keys(conn)
    conn.execute(
        "INSERT INTO observations (tenant, observation_id, source_system, external_id, content_digest, "
        "raw_value, as_of, received_at, state, version, provenance_class, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?, 'RECEIVED', 1, 'SYSTEM_IMPORTED', ?, ?)",
        (T_A, "obs-1", "tms", "L-1", "d1", "loads page", NOW, NOW, NOW, NOW))
    conn.commit()
    store = EvidenceStore(conn)
    ev = store.retain(T_A, content=b"POD load 4471", media_type="application/pdf",
                      source_observation_id="obs-1", now=NOW)
    store.attach_span(T_A, ev, locator="page 1", now=NOW, extracted_text="4471")
    return store, ev


# =============================================================== AC-8: the model reads, the linker decides


def test_a_model_inferred_binding_is_never_committed_as_authority():
    """AC-8: a MODEL_INFER guess routes to AMBIGUOUS and gets a human, at confidence 1.0 as at 0.5 —
    it is never committed as a binding. Positive control: a deterministic EXACT_ID match confirms."""
    for conf in (0.5, 0.99, 1.0):
        out = L.link("pod-1", [L.Signal("MODEL_INFER", "load-4471", confidence=conf)])
        assert out.status is L.LinkStatus.AMBIGUOUS and out.reason == L.REASON_MODEL_INFERRED
        assert out.bound_identifier is None
    confirmed = L.link("pod-1", [L.Signal("EXACT_ID", "load-4471", source="tms")])
    assert confirmed.is_binding and confirmed.provenance_class is ProvenanceClass.LINKER_INFERRED


def test_model_extraction_re_enters_the_deterministic_linker():
    """AC-8: MODEL_EXTRACT does not itself confirm — the extracted identifier re-enters as an EXACT_ID
    candidate and the deterministic linker decides (the model finds the string; the linker binds)."""
    out = L.link("pod-1", [L.Signal("MODEL_EXTRACT", "load-4471", source="ocr")])
    assert out.is_binding
    assert out.provenance_class is ProvenanceClass.LINKER_INFERRED  # NOT MODEL_EXTRACTED
    assert out.match_method == "EXACT_ID"


def test_the_binding_order_vocabulary_is_the_one_m6_authority():
    """AC-8: the six methods and the SD-6 mapping are M6's — the linker reuses them, it does not
    restate a second vocabulary. Only LINKER_INFERRED / RECONCILED / OWNER_ASSERTED may confirm."""
    assert len(MATCH_METHODS) == 6
    assert set(PROVENANCE_BY_METHOD) == set(MATCH_METHODS)
    assert set(CONFIRMED_ALLOWED_PROVENANCE) == {"LINKER_INFERRED", "RECONCILED", "OWNER_ASSERTED"}
    # MODEL_EXTRACTED and MODEL_INFERRED are not confirming classes.
    assert "MODEL_INFERRED" not in CONFIRMED_ALLOWED_PROVENANCE
    assert "MODEL_EXTRACTED" not in CONFIRMED_ALLOWED_PROVENANCE


def test_ambiguous_or_weak_candidates_fail_closed():
    """AC-8/AC-9: an unauthenticated HUMAN signal, and no deterministic candidate at all, both fail
    closed to a human — the linker never guesses a bind. Positive control: an authenticated human binds."""
    assert L.link("pod-1", [L.Signal("HUMAN", "load-4471")]).status is L.LinkStatus.AMBIGUOUS
    assert L.link("pod-1", []).status is L.LinkStatus.AMBIGUOUS
    authed = L.link("pod-1", [L.Signal("HUMAN", "load-4471")], authenticated_human=True)
    assert authed.is_binding and authed.provenance_class is ProvenanceClass.OWNER_ASSERTED


# =============================================================== AC-9: owner binding persists


def test_owner_asserted_binding_survives_relink_and_replay():
    """AC-9: re-running the linker over an OWNER_ASSERTED binding is refused (R-P3) and the owner's
    value is preserved byte-identical; a full replay/rebuild preserves it too. Proved over a
    population PROVEN NON-EMPTY. Positive control: a non-owner binding IS supersedable by a relink."""
    owner = P.ProvenanceRecord(value="load-4471", provenance_class="OWNER_ASSERTED")
    with pytest.raises(P.OwnerAssertedRecompute):
        L.relink(owner, "pod-1", [L.Signal("EXACT_ID", "load-4718", source="tms")])
    assert owner.value == "load-4471"
    bindings = require_population(
        [owner, P.ProvenanceRecord(value="load-9000", provenance_class="OWNER_ASSERTED")],
        "OWNER_ASSERTED bindings")
    assert L.owner_binding_survives_replay(bindings) is True
    # positive control: a LINKER_INFERRED binding is not owner-asserted, so a relink supersedes it.
    inferred = P.ProvenanceRecord(value="load-1", provenance_class="LINKER_INFERRED")
    relinked = L.relink(inferred, "pod-2", [L.Signal("EXACT_ID", "load-2", source="tms")])
    assert relinked.value == "load-2"


# =============================================================== AC-10: conflict blocks, two ways only


def test_conflict_is_first_class_and_blocks_while_open():
    """AC-10: two mutually exclusive confirming candidates on one subject become a first-class
    Conflict, and an open Conflict blocks; a terminal one does not."""
    out = L.link("pod-1", [L.Signal("EXACT_ID", "load-4471", source="a"),
                           L.Signal("EXACT_ID", "load-4718", source="b")])
    assert out.status is L.LinkStatus.CONFLICT
    assert set(out.conflict_parties) == {"load-4471", "load-4718"}
    for open_state in ("RAISED", "OPEN", "ESCALATED"):
        assert L.conflict_blocks(open_state) is True
    for terminal in TERMINAL_CONFLICT_STATES:
        assert L.conflict_blocks(terminal) is False


def test_a_conflict_closes_only_via_a_registered_rule_or_a_human_decision():
    """AC-10: a Conflict closes EXACTLY TWO WAYS — a registered rule id or a human decision_ref — and
    no third: not a model, not recency, not a timeout, not last-write-wins."""
    assert L.close_conflict(rule_id="R-12") == "RESOLVED_BY_RULE"
    assert L.close_conflict(decision_ref="dec-9") == "RESOLVED_BY_HUMAN"
    assert "RESOLVED_BY_RULE" in TERMINAL_CONFLICT_STATES  # one authority: M7's vocabulary
    assert "RESOLVED_BY_HUMAN" in TERMINAL_CONFLICT_STATES
    with pytest.raises(L.ConflictClosureRefused):
        L.close_conflict()  # neither — a timeout / model / recency cannot close it
    with pytest.raises(L.ConflictClosureRefused):
        L.close_conflict(rule_id="R-12", decision_ref="dec-9")  # not both at once


# =============================================================== AC-11: correction != supersession


def test_correction_and_supersession_are_distinct_with_retained_attributable_history():
    """AC-11: supersession replaces a claim that was TRUE WHEN MADE — prior retained, no downstream
    obligation. Correction declares a claim WRONG — prior retained and attributable, a ClaimCorrected
    event carrying the decision_ref, and a downstream remediation obligation. Conflating them loses
    money."""
    prior = L.Claim("c1", "pod-1", "load-4471", "OWNER_ASSERTED")

    superseded = L.supersede(prior, "load-4471-v2", "SYSTEM_IMPORTED")
    assert superseded.kind == "supersession"
    assert superseded.retained == (prior,) and superseded.downstream_obligation is False
    assert superseded.corrected_event is None

    corrected = L.correct(prior, "load-4718", decision_ref="dec-1", new_provenance="OWNER_ASSERTED")
    assert corrected.kind == "correction"
    assert corrected.retained == (prior,)                # prior retained, not erased
    assert corrected.downstream_obligation is True       # a correction propagates
    assert corrected.corrected_event["event"] == "ClaimCorrected"
    assert corrected.corrected_event["prior"] == "c1" and corrected.corrected_event["decision_ref"] == "dec-1"
    # a correction is a human decision — it requires a decision_ref.
    with pytest.raises(L.LinkerError):
        L.correct(prior, "load-4718", decision_ref="", new_provenance="OWNER_ASSERTED")


# =============================================================== AC-7: lineage traversal


def test_a_canonical_claim_traces_to_its_complete_evidence_chain():
    """AC-7: a MODEL_EXTRACTED claim walks to its Evidence, spans and source Observation in one query;
    rule- and human-backed claims terminate in a rule_id / decision_ref. The chain never dangles."""
    store, ev = _evidence_store_with_span()
    chain = LG.trace(store, T_A, LG.CanonicalClaim("pod_load", "MODEL_EXTRACTED", evidence_id=ev))
    assert chain["terminates_in"] == "evidence"
    assert require_population(chain["spans"], "spans on the traced claim")
    assert chain["source_observation_id"] == "obs-1"
    assert LG.trace(store, T_A, LG.CanonicalClaim("x", "LINKER_INFERRED", rule_id="R-1"))["terminates_in"] == "rule_id"
    assert LG.trace(store, T_A, LG.CanonicalClaim("y", "OWNER_ASSERTED", decision_ref="dec-1"))["terminates_in"] == "decision_ref"


def test_lineage_fails_closed_on_a_missing_or_inferred_link():
    """AC-7: a claim we cannot walk to a terminating justification BLOCKS. A MODEL_EXTRACTED claim with
    no span, a MODEL_INFERRED claim (no artifact), and a claim whose Evidence is absent all fail closed."""
    store, _ = _evidence_store_with_span()
    naked = store.retain(T_A, content=b"no span here", media_type="text/plain",
                         source_observation_id="obs-1", now=NOW)
    with pytest.raises(LG.LineageIncomplete):
        LG.trace(store, T_A, LG.CanonicalClaim("z", "MODEL_EXTRACTED", evidence_id=naked))
    assert LG.is_defensible(store, T_A, LG.CanonicalClaim("g", "MODEL_INFERRED")) is False
    assert LG.is_defensible(store, T_A, LG.CanonicalClaim("a", "MODEL_EXTRACTED", evidence_id="nope")) is False
    # positive control: a well-formed evidence-backed claim IS defensible.
    store2, ev = _evidence_store_with_span()
    assert LG.is_defensible(store2, T_A, LG.CanonicalClaim("ok", "MODEL_EXTRACTED", evidence_id=ev)) is True


# =============================================================== F14: the R-P2 audit emission


def test_a_refused_strengthening_emits_the_registered_f14_event():
    """The R-P2 refusal now carries its audit trail: a refused strengthening hands the registered F14
    ProvenanceStrengtheningAttempted event to the caller's sink. Positive control: a legal weakening
    emits nothing."""
    events: list[dict] = []
    with pytest.raises(P.ProvenanceLaundering):
        P.reassign("MODEL_INFERRED", "LINKER_INFERRED", on_strengthening_attempt=events.append)
    assert len(events) == 1
    assert events[0]["event"] == "ProvenanceStrengtheningAttempted"
    assert events[0]["from_class"] == "MODEL_INFERRED" and events[0]["to_class"] == "LINKER_INFERRED"
    # positive control: weakening is legal and emits no security event.
    quiet: list[dict] = []
    P.reassign("OWNER_ASSERTED", "MODEL_INFERRED", on_strengthening_attempt=quiet.append)
    assert quiet == []


def test_the_f14_event_name_is_the_registered_contract_and_no_synonym():
    """The emitted name is the registered F14 contract, not an invented synonym (the frozen registry
    is untouched)."""
    assert P.F14_PROVENANCE_STRENGTHENING == "ProvenanceStrengtheningAttempted"
    registry = (ROOT / "docs" / "specifications" / "events" / "registry.md").read_text(encoding="utf-8")
    assert "ProvenanceStrengtheningAttempted" in registry, "the emitted name is not a registered contract"


# =============================================================== ships dark


def test_the_identity_and_lineage_modules_ship_dark():
    """P7 ships dark: nothing in production imports the linker or lineage modules. Discovered by AST
    with the denominator printed."""
    targets = {"linker", "lineage"}
    importers = []
    inspected = 0
    for path in require_population(sorted(SRC.rglob("*.py")), "src modules"):
        if path.stem in targets:
            continue
        inspected += 1
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[-1] in targets:
                importers.append(f"{path.name} -> {node.module}")
            if isinstance(node, ast.ImportFrom) and not node.module:
                for a in node.names:
                    if a.name in targets:
                        importers.append(f"{path.name} -> {a.name}")
    print(f"AC-15 (identity/lineage): inspected {inspected} src modules for a production importer")
    assert inspected > 0
    assert not importers, f"the identity/lineage modules have production importer(s): {importers}"
