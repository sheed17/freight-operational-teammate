"""Tests for wiring real extraction into the reconciliation loop (with an injected fake extractor)."""

import json
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.extraction_bridge import apply_extraction_to_load  # noqa: E402
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402
from freight_recon.workflow import WorkflowState, WorkflowStore, process_load_packet  # noqa: E402


def _loads(tmp_path, count=8):
    corpus = tmp_path / "corpus"
    generate(corpus, count, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    return corpus, loads


def _c(value, confidence=0.99):
    return SimpleNamespace(value=value, confidence=confidence)


def _fake_obj(load, *, linehaul=None, fuel=None, accessorials=None, load_or_pro=None, linehaul_conf=0.99):
    """An extraction object shaped like the validated Confident[...] model. Defaults to a clean
    match (extracted invoice side == the rate side), so each test perturbs exactly one thing."""
    return SimpleNamespace(
        invoice_number=_c(load.invoice_number),
        carrier_name=_c(load.carrier),
        load_or_pro=_c(load_or_pro if load_or_pro is not None else load.load_id),
        linehaul_amount=_c(load.rate_linehaul if linehaul is None else linehaul, linehaul_conf),
        fuel_surcharge=_c(load.rate_fuel if fuel is None else fuel),
        total_amount=_c(load.rate_linehaul + load.rate_fuel),
        invoice_date=_c("2026-05-05"),
        accessorials=accessorials or [],
    )


def _extractor_for(obj, *, model="gpt-4o", error=None):
    return lambda _path: SimpleNamespace(extraction=obj, model=model, error=error)


# ---- bridge unit tests -------------------------------------------------------

def test_bridge_overlays_invoice_side_and_links(tmp_path):
    _, loads = _loads(tmp_path)
    load = loads[0]
    obj = _fake_obj(load, linehaul=999, accessorials=[SimpleNamespace(name="detention", amount=300)])

    recon_load, low_conf, link_ok = apply_extraction_to_load(load, obj)

    assert recon_load.invoice_linehaul == 999            # invoice side = extracted
    assert recon_load.rate_linehaul == load.rate_linehaul  # rate side untouched (source of truth)
    assert [c.name for c in recon_load.invoice_accessorials] == ["detention"]
    assert low_conf == [] and link_ok is True


def test_bridge_flags_low_confidence_required_field(tmp_path):
    _, loads = _loads(tmp_path)
    obj = _fake_obj(loads[0], linehaul_conf=0.4)
    _, low_conf, _ = apply_extraction_to_load(loads[0], obj)
    assert "linehaul_amount" in low_conf


def test_bridge_detects_load_link_mismatch(tmp_path):
    _, loads = _loads(tmp_path)
    obj = _fake_obj(loads[0], load_or_pro="LD-999999")
    _, _, link_ok = apply_extraction_to_load(loads[0], obj)
    assert link_ok is False


# ---- process_load_packet real-extraction path --------------------------------

def _process(tmp_path, load, corpus, extractor):
    store = WorkflowStore(tmp_path / "wf.sqlite3")
    run = process_load_packet(
        store, load,
        primary_document_path=corpus / load.documents["carrier_invoice"],
        seen_invoice_keys=set(),
        extractor=extractor,
    )
    return store, run


def test_clean_extraction_matches_and_records_vision_source(tmp_path):
    corpus, loads = _loads(tmp_path)
    load = loads[0]
    store, run = _process(tmp_path, load, corpus, _extractor_for(_fake_obj(load)))  # extracted == rate
    assert run.state == WorkflowState.DONE
    events = store.audit_events(run.id)
    extracted = next(e for e in events if e["event_type"] == "extraction_recorded")
    assert extracted["payload"]["source"] == "vision_extraction"
    assert extracted["payload"]["model"] == "gpt-4o"
    store.close()


def test_extracted_variance_routes_to_review(tmp_path):
    corpus, loads = _loads(tmp_path)
    load = loads[0]
    obj = _fake_obj(load, linehaul=load.rate_linehaul + 250)  # carrier billed $250 over the rate
    store, run = _process(tmp_path, load, corpus, _extractor_for(obj))
    assert run.state == WorkflowState.NEEDS_REVIEW
    assert run.outcome == "VARIANCE"
    store.close()


def test_low_confidence_forces_review_even_when_math_matches(tmp_path):
    corpus, loads = _loads(tmp_path)
    load = loads[0]
    obj = _fake_obj(load, linehaul_conf=0.4)  # amounts match the rate, but the read is unsure
    store, run = _process(tmp_path, load, corpus, _extractor_for(obj))
    assert run.state == WorkflowState.NEEDS_REVIEW  # confidence gate fires regardless of the math
    assert any("low-confidence" in r for r in (run.reason or "").split(";"))
    store.close()


def test_load_link_mismatch_forces_review(tmp_path):
    corpus, loads = _loads(tmp_path)
    load = loads[0]
    obj = _fake_obj(load, load_or_pro="LD-999999")
    store, run = _process(tmp_path, load, corpus, _extractor_for(obj))
    assert run.state == WorkflowState.NEEDS_REVIEW
    assert "does not match" in (run.reason or "")
    store.close()


def test_extraction_failure_routes_to_review_not_crash(tmp_path):
    corpus, loads = _loads(tmp_path)
    load = loads[0]
    failing = lambda _p: SimpleNamespace(extraction=None, model="gpt-4o", error="rate limit")  # noqa: E731
    store, run = _process(tmp_path, load, corpus, failing)
    assert run.state == WorkflowState.NEEDS_REVIEW
    assert "extraction failed" in (run.reason or "")
    store.close()
