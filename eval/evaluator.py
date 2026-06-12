"""Scoring + confidence calibration + failure categorization.

Pure functions over (extraction result, ground truth). No LLM, no I/O. Produces an
EvalReport that report.py renders and run_eval.py serializes for --save / --compare.

Scoring rules (from the spec):
  - numeric fields: tolerance $0.01
  - date fields: normalized to YYYY-MM-DD before comparing
  - string fields: stripped + lowercased; near-matches count as correct, flagged
  - accessorials (list): matched by name regardless of order, amount within tolerance
"""

from __future__ import annotations

import datetime as _dt
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from typing import Any

from extraction import DocConfig, ExtractionResult

# Field-level outcomes
CORRECT = "CORRECT"
INCORRECT = "INCORRECT"
MISSING = "MISSING"   # model returned null but ground truth has a value
EXTRA = "EXTRA"       # model returned a value but ground truth is null

# Failure categories
LABEL_VARIATION = "LABEL_VARIATION"
NOT_FOUND = "NOT_FOUND"
WRONG_VALUE = "WRONG_VALUE"
FORMAT_ERROR = "FORMAT_ERROR"
LAYOUT_UNUSUAL = "LAYOUT_UNUSUAL"
MULTI_PAGE_MISS = "MULTI_PAGE_MISS"
MODEL_ERROR = "MODEL_ERROR"

REQUIRED_FIELDS = ("load_or_pro_number", "linehaul_amount", "total_amount")
# Identifier-like string fields must match exactly (after whitespace/case normalization).
# A truncated or partial reference number is a real error, not a near-match — substring
# similarity would wrongly pass "L-449" against "L-44982". Descriptive strings (carrier
# name) still allow near-matches like "Swift Transport" vs "Swift Transport LLC".
IDENTIFIER_FIELDS = ("load_or_pro_number", "invoice_number")
NUMERIC_TOLERANCE = 0.01

# Production-readiness gates (Stage 1 → Stage 2)
GATE_REQUIRED_FIELD_ACCURACY = 0.90
GATE_OVERALL_ACCURACY = 0.85
GATE_HIGH_CONF_BUCKET_ACCURACY = 0.85
HIGH_CONF = 0.85


# ----------------------------------------------------------------------------
# Value normalization / comparison
# ----------------------------------------------------------------------------

def parse_number(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^\d.\-]", "", str(value))
    if text in ("", "-", ".", "-."):
        return None
    try:
        return float(text)
    except ValueError:
        return None


_DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%m-%d-%Y", "%m/%d/%y", "%B %d, %Y", "%b %d, %Y", "%d %b %Y")


def normalize_date(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return _dt.datetime.strptime(s, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _norm_str(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def string_match(a: Any, b: Any) -> str:
    """Return 'exact' | 'near' | 'no'."""
    na, nb = _norm_str(a), _norm_str(b)
    if na == nb:
        return "exact"
    if na and nb and (na in nb or nb in na):
        return "near"
    if na and nb and SequenceMatcher(None, na, nb).ratio() >= 0.85:
        return "near"
    return "no"


def _present(value: Any) -> bool:
    """A value counts as present if it's not None and not an empty string. 0.0 is present."""
    if value is None:
        return False
    if isinstance(value, str) and value.strip() == "":
        return False
    return True


# ----------------------------------------------------------------------------
# Per-field scoring
# ----------------------------------------------------------------------------

@dataclass
class FieldScore:
    filename: str
    field: str
    outcome: str
    confidence: float
    truth: Any
    extracted: Any
    category: str | None = None
    note: str | None = None
    asserted: bool = False  # model returned a non-null value (a real prediction)


def _categorize(field_type: str, outcome: str, extracted: Any, extraction_note: str | None) -> str | None:
    if outcome == CORRECT:
        return None
    note = (extraction_note or "").lower()

    if outcome == MISSING:
        if any(k in note for k in ("page", "attachment", "second page")):
            return MULTI_PAGE_MISS
        return NOT_FOUND

    # INCORRECT or EXTRA
    if field_type in ("decimal", "integer") and parse_number(extracted) is None and _present(extracted):
        return FORMAT_ERROR
    if field_type == "date" and normalize_date(extracted) is None and _present(extracted):
        return FORMAT_ERROR
    if any(k in note for k in ("label", "assumed", "guess", "non-standard", "unclear")):
        return LABEL_VARIATION
    if any(k in note for k in ("layout", "unusual", "format of")):
        return LAYOUT_UNUSUAL
    if any(k in note for k in ("page", "attachment")):
        return MULTI_PAGE_MISS
    return WRONG_VALUE


def score_scalar(filename: str, spec_type: str, field_name: str, extracted_field: dict | None, truth: Any) -> FieldScore:
    extracted_field = extracted_field or {}
    extracted = extracted_field.get("value")
    confidence = float(extracted_field.get("confidence") or 0.0)
    note = extracted_field.get("extraction_note")

    t_present, e_present = _present(truth), _present(extracted)

    if not t_present and not e_present:
        outcome = CORRECT
    elif t_present and not e_present:
        outcome = MISSING
    elif not t_present and e_present:
        outcome = EXTRA
    else:
        if spec_type in ("decimal", "integer"):
            tn, en = parse_number(truth), parse_number(extracted)
            match = tn is not None and en is not None and abs(tn - en) <= NUMERIC_TOLERANCE
            outcome = CORRECT if match else INCORRECT
        elif spec_type == "date":
            outcome = CORRECT if normalize_date(truth) == normalize_date(extracted) else INCORRECT
        elif field_name in IDENTIFIER_FIELDS:
            outcome = CORRECT if string_match(truth, extracted) == "exact" else INCORRECT
        else:
            m = string_match(truth, extracted)
            outcome = CORRECT if m in ("exact", "near") else INCORRECT
            if m == "near":
                note = (note + " | " if note else "") + "near-match"

    return FieldScore(
        filename=filename,
        field=field_name,
        outcome=outcome,
        confidence=confidence,
        truth=truth,
        extracted=extracted,
        category=_categorize(spec_type, outcome, extracted, note),
        note=note,
        asserted=e_present,
    )


@dataclass
class AccessorialPrediction:
    confidence: float
    correct: bool


def score_accessorials(filename: str, extracted_list: list[dict] | None, truth_list: list[dict] | None):
    """Match accessorials by name regardless of order. Returns (FieldScore, [AccessorialPrediction])."""
    extracted_list = extracted_list or []
    truth_list = truth_list or []

    remaining = list(extracted_list)
    found, missing = [], []
    item_predictions: list[AccessorialPrediction] = []

    for t in truth_list:
        t_name, t_amt = _norm_str(t.get("name", "")), parse_number(t.get("amount"))
        hit = None
        for e in remaining:
            if string_match(e.get("name", ""), t_name) in ("exact", "near"):
                e_amt = parse_number(e.get("amount"))
                if t_amt is not None and e_amt is not None and abs(t_amt - e_amt) <= NUMERIC_TOLERANCE:
                    hit = e
                    break
        if hit is not None:
            remaining.remove(hit)
            found.append(t)
            item_predictions.append(AccessorialPrediction(float(hit.get("confidence") or 0.0), True))
        else:
            missing.append(t)

    extra = remaining
    for e in extra:  # asserted-but-wrong accessorials are overconfidence candidates
        item_predictions.append(AccessorialPrediction(float(e.get("confidence") or 0.0), False))

    if not truth_list and not extracted_list:
        outcome = CORRECT
    elif truth_list and not extracted_list:
        outcome = MISSING
    elif len(found) == len(truth_list) and not extra:
        outcome = CORRECT
    else:
        outcome = INCORRECT

    detail = f"found {len(found)}/{len(truth_list)}"
    if extra:
        detail += f", {len(extra)} extra"
    category = None
    if outcome == MISSING:
        category = NOT_FOUND
    elif outcome == INCORRECT:
        category = LAYOUT_UNUSUAL if missing and not extra else WRONG_VALUE

    fs = FieldScore(
        filename=filename,
        field="accessorials",
        outcome=outcome,
        confidence=0.0,
        truth=truth_list,
        extracted=extracted_list,
        category=category,
        note=detail,
        asserted=bool(extracted_list),
    )
    return fs, item_predictions


# ----------------------------------------------------------------------------
# Aggregation
# ----------------------------------------------------------------------------

@dataclass
class FieldStat:
    correct: int = 0
    wrong: int = 0
    missing: int = 0
    total: int = 0
    conf_sum: float = 0.0
    conf_n: int = 0

    @property
    def accuracy(self) -> float:
        return self.correct / self.total if self.total else 0.0

    @property
    def avg_conf(self) -> float:
        return self.conf_sum / self.conf_n if self.conf_n else 0.0


@dataclass
class Bucket:
    label: str
    lo: float
    hi: float
    n: int = 0
    correct: int = 0

    @property
    def accuracy(self) -> float:
        return self.correct / self.n if self.n else 0.0


@dataclass
class EvalReport:
    docs_processed: int = 0
    extraction_failures: list[str] = field(default_factory=list)
    fields_evaluated: int = 0
    overall_correct: int = 0
    field_stats: dict[str, FieldStat] = field(default_factory=dict)
    buckets: list[Bucket] = field(default_factory=list)
    overconfidence: list[dict] = field(default_factory=list)
    failure_modes: dict[str, dict[str, int]] = field(default_factory=dict)  # category -> {field: count}
    doc_results: list[dict] = field(default_factory=list)
    field_scores: list[FieldScore] = field(default_factory=list)

    @property
    def overall_accuracy(self) -> float:
        return self.overall_correct / self.fields_evaluated if self.fields_evaluated else 0.0

    # --- production-readiness gates ---
    def required_field_pass(self) -> dict[str, bool]:
        return {
            f: (self.field_stats[f].accuracy >= GATE_REQUIRED_FIELD_ACCURACY)
            for f in REQUIRED_FIELDS
            if f in self.field_stats
        }

    def dangerous_overconfidence(self) -> list[dict]:
        return [o for o in self.overconfidence if o["field"] in REQUIRED_FIELDS]

    def high_conf_bucket(self) -> Bucket | None:
        # The single >= 0.85 bucket is the top bucket (0.90-1.00) plus the slice of
        # 0.85; we report calibration via the standard buckets and gate on >=0.85.
        return next((b for b in self.buckets if b.lo >= 0.90), None)

    def production_ready(self) -> bool:
        req_ok = all(self.required_field_pass().values()) if self.required_field_pass() else False
        overall_ok = self.overall_accuracy >= GATE_OVERALL_ACCURACY
        overconf_ok = len(self.dangerous_overconfidence()) == 0
        top = self.high_conf_bucket()
        calib_ok = (top is None) or (top.n == 0) or (top.accuracy >= GATE_HIGH_CONF_BUCKET_ACCURACY)
        return req_ok and overall_ok and overconf_ok and calib_ok

    def to_dict(self) -> dict:
        return {
            "docs_processed": self.docs_processed,
            "extraction_failures": self.extraction_failures,
            "fields_evaluated": self.fields_evaluated,
            "overall_accuracy": round(self.overall_accuracy, 4),
            "field_stats": {
                k: {"correct": v.correct, "wrong": v.wrong, "missing": v.missing,
                    "total": v.total, "accuracy": round(v.accuracy, 4), "avg_conf": round(v.avg_conf, 4)}
                for k, v in self.field_stats.items()
            },
            "buckets": [{"label": b.label, "n": b.n, "accuracy": round(b.accuracy, 4)} for b in self.buckets],
            "overconfidence": self.overconfidence,
            "failure_modes": self.failure_modes,
            "production_ready": self.production_ready(),
            "doc_results": self.doc_results,
        }


def _new_buckets() -> list[Bucket]:
    return [
        Bucket("0.90 - 1.00", 0.90, 1.01),
        Bucket("0.70 - 0.89", 0.70, 0.90),
        Bucket("0.50 - 0.69", 0.50, 0.70),
        Bucket("0.00 - 0.49", 0.0, 0.50),
    ]


def _bucket_for(buckets: list[Bucket], conf: float) -> Bucket:
    for b in buckets:
        if b.lo <= conf < b.hi:
            return b
    return buckets[-1]


def evaluate(results: list[ExtractionResult], ground_truth: dict, config: DocConfig) -> EvalReport:
    report = EvalReport(buckets=_new_buckets())
    report.field_stats = {f.name: FieldStat() for f in config.fields}
    failure_modes: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for result in results:
        report.docs_processed += 1
        truth = ground_truth.get(result.filename, {})
        doc_scores: list[FieldScore] = []

        if not result.ok:
            report.extraction_failures.append(f"{result.filename}: {result.error}")
            # Every required field is a model-error miss; still count fields as evaluated.
            for spec in config.fields:
                fs = FieldScore(result.filename, spec.name, MISSING, 0.0,
                                truth.get(spec.name), None, category=MODEL_ERROR, note="extraction failed")
                doc_scores.append(fs)
        else:
            data = result.data or {}
            for spec in config.fields:
                if spec.type == "list":
                    fs, item_preds = score_accessorials(
                        result.filename, data.get(spec.name), truth.get(spec.name)
                    )
                    for ip in item_preds:
                        b = _bucket_for(report.buckets, ip.confidence)
                        b.n += 1
                        b.correct += int(ip.correct)
                    doc_scores.append(fs)
                else:
                    fs = score_scalar(result.filename, spec.type, spec.name, data.get(spec.name), truth.get(spec.name))
                    doc_scores.append(fs)
                    if fs.asserted:
                        b = _bucket_for(report.buckets, fs.confidence)
                        b.n += 1
                        b.correct += int(fs.outcome == CORRECT)
                        if fs.confidence >= HIGH_CONF and fs.outcome != CORRECT:
                            report.overconfidence.append({
                                "filename": result.filename, "field": fs.field,
                                "confidence": round(fs.confidence, 2),
                                "extracted": fs.extracted, "truth": fs.truth,
                            })

        # Fold doc scores into aggregates
        doc_correct = 0
        for fs in doc_scores:
            report.field_scores.append(fs)
            report.fields_evaluated += 1
            stat = report.field_stats[fs.field]
            stat.total += 1
            if fs.outcome == CORRECT:
                stat.correct += 1
                report.overall_correct += 1
                doc_correct += 1
            elif fs.outcome == MISSING:
                stat.missing += 1
            else:  # INCORRECT or EXTRA
                stat.wrong += 1
            if fs.asserted:
                stat.conf_sum += fs.confidence
                stat.conf_n += 1
            if fs.category:
                failure_modes[fs.category][fs.field] += 1

        report.doc_results.append({
            "filename": result.filename,
            "status": result.status,
            "correct": doc_correct,
            "total": len(doc_scores),
            "failures": [f"{fs.field}:{fs.category}" for fs in doc_scores if fs.category],
        })

    report.failure_modes = {k: dict(v) for k, v in failure_modes.items()}
    return report
