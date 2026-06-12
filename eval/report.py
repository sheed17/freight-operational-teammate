"""Terminal report rendering for the Stage 1 eval, using Rich.

Pure formatting over an EvalReport. Six sections: summary, per-field accuracy,
confidence calibration, failure-mode breakdown, actionable recommendations, and
document-level results. Plus a compare view for two saved runs.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table
from rich.text import Text

from evaluator import (
    GATE_HIGH_CONF_BUCKET_ACCURACY,
    GATE_OVERALL_ACCURACY,
    GATE_REQUIRED_FIELD_ACCURACY,
    REQUIRED_FIELDS,
    EvalReport,
)

console = Console()


def _field_status(accuracy: float) -> Text:
    if accuracy >= 0.90:
        return Text("✓ SOLID", style="green")
    if accuracy >= 0.80:
        return Text("⚠ TUNE", style="yellow")
    return Text("✗ NEEDS WORK", style="red")


def _calib_status(n: int, accuracy: float, lo: float) -> Text:
    if n == 0:
        return Text("— (no data)", style="dim")
    # For the top buckets we expect accuracy to roughly track the floor of the bucket.
    expected = lo
    if accuracy + 1e-9 >= expected:
        return Text("✓ GOOD", style="green")
    if accuracy >= expected - 0.15:
        return Text("✓ ACCEPTABLE", style="yellow")
    return Text("✗ OVERCONFIDENT", style="red")


def render(report: EvalReport) -> None:
    _section_summary(report)
    _section_per_field(report)
    _section_calibration(report)
    _section_failure_modes(report)
    _section_recommendations(report)
    _section_doc_results(report)


def _section_summary(report: EvalReport) -> None:
    console.rule("[bold]SECTION 1 — Overall Summary")
    fail_n = len(report.extraction_failures)
    console.print(f"  Documents processed:  {report.docs_processed}")
    console.print(f"  Extraction failures:  {fail_n}"
                  + (f"  ({'; '.join(report.extraction_failures)})" if fail_n else ""))
    console.print(f"  Fields evaluated:     {report.fields_evaluated}")
    acc = report.overall_accuracy
    acc_style = "green" if acc >= GATE_OVERALL_ACCURACY else "red"
    console.print(f"\n  OVERALL ACCURACY:     [{acc_style}]{acc*100:.1f}%[/{acc_style}]")
    ready = report.production_ready()
    console.print(f"  PRODUCTION READY:     "
                  + ("[green]YES[/green]" if ready else "[red]NO[/red] — see breakdown below"))
    console.print()


def _section_per_field(report: EvalReport) -> None:
    console.rule("[bold]SECTION 2 — Per-Field Accuracy")
    table = Table(show_header=True, header_style="bold")
    for col in ("Field", "Correct", "Wrong", "Missing", "Accuracy", "Avg Conf", "Status"):
        table.add_column(col, justify="left" if col == "Field" else "right")
    for name, stat in report.field_stats.items():
        req = " *" if name in REQUIRED_FIELDS else ""
        table.add_row(
            name + req, str(stat.correct), str(stat.wrong), str(stat.missing),
            f"{stat.accuracy*100:.1f}%", f"{stat.avg_conf:.2f}", _field_status(stat.accuracy),
        )
    console.print(table)
    console.print("  [dim]* required field (gate: ≥90% to advance to Stage 2)[/dim]\n")


def _section_calibration(report: EvalReport) -> None:
    console.rule("[bold]SECTION 3 — Confidence Calibration")
    table = Table(show_header=True, header_style="bold")
    for col in ("Confidence Bucket", "Predictions", "Actual Accuracy", "Calibration"):
        table.add_column(col, justify="left" if col == "Confidence Bucket" else "right")
    for b in report.buckets:
        table.add_row(
            b.label, str(b.n), f"{b.accuracy*100:.1f}%" if b.n else "—",
            _calib_status(b.n, b.accuracy, b.lo),
        )
    console.print(table)

    if report.overconfidence:
        console.print(f"\n  [red]⚠ OVERCONFIDENCE ALERT:[/red] {len(report.overconfidence)} case(s) where "
                      "confidence ≥0.85 but extraction was WRONG")
        for o in report.overconfidence:
            tag = " [red](REQUIRED FIELD)[/red]" if o["field"] in REQUIRED_FIELDS else ""
            console.print(f"    → {o['filename']}: {o['field']} — confidence {o['confidence']}, "
                          f"extracted {o['extracted']!r} (correct: {o['truth']!r}){tag}")
    else:
        console.print("\n  [green]✓ No overconfidence (no conf ≥0.85 wrong predictions).[/green]")
    console.print()


def _section_failure_modes(report: EvalReport) -> None:
    console.rule("[bold]SECTION 4 — Failure Mode Breakdown")
    if not report.failure_modes:
        console.print("  [green]No failures to categorize.[/green]\n")
        return
    table = Table(show_header=True, header_style="bold")
    table.add_column("Failure Mode")
    table.add_column("Count", justify="right")
    table.add_column("Fields Affected")
    rows = sorted(report.failure_modes.items(), key=lambda kv: -sum(kv[1].values()))
    for mode, fields in rows:
        count = sum(fields.values())
        affected = ", ".join(f"{f} ({n})" for f, n in sorted(fields.items(), key=lambda kv: -kv[1]))
        table.add_row(mode, str(count), affected)
    console.print(table)
    console.print()


def _section_recommendations(report: EvalReport) -> None:
    console.rule("[bold]SECTION 5 — Actionable Recommendations")
    recs: list[str] = []
    # Weakest fields first
    weak = sorted(
        [(n, s) for n, s in report.field_stats.items() if s.accuracy < 0.90 and s.total],
        key=lambda kv: kv[1].accuracy,
    )
    for name, stat in weak:
        modes = {m: f.get(name, 0) for m, f in report.failure_modes.items() if f.get(name)}
        mode_str = ", ".join(f"{n}× {m}" for m, n in sorted(modes.items(), key=lambda kv: -kv[1])) or "mixed"
        recs.append(f"{name} ({stat.accuracy*100:.0f}%): {mode_str}. "
                    f"Tune the prompt/label hints for this field, then re-eval.")
    if report.dangerous_overconfidence():
        recs.append(f"OVERCONFIDENCE on required fields ({len(report.dangerous_overconfidence())} case(s)): "
                    "the model is confidently wrong on money/PRO fields. Lower the auto-approve "
                    "threshold for numeric fields and/or strengthen the 'be honest about confidence' prompt.")
    if not recs:
        recs.append("No tuning needed — all fields ≥90% and calibration clean.")
    for i, r in enumerate(recs, 1):
        console.print(f"  {i}. {r}")

    console.print("\n  [bold]PRODUCTION READINESS:[/bold]")
    req = report.required_field_pass()
    req_ok = all(req.values()) if req else False
    console.print(f"    Required fields (load_or_pro, linehaul, total) ≥{GATE_REQUIRED_FIELD_ACCURACY*100:.0f}%: "
                  + _passfail(req_ok)
                  + "  " + ", ".join(f"{k}={'✓' if v else '✗'}" for k, v in req.items()))
    overconf_ok = len(report.dangerous_overconfidence()) == 0
    console.print(f"    No dangerous overconfidence on required fields: " + _passfail(overconf_ok))
    overall_ok = report.overall_accuracy >= GATE_OVERALL_ACCURACY
    console.print(f"    Overall accuracy ≥{GATE_OVERALL_ACCURACY*100:.0f}% "
                  f"(={report.overall_accuracy*100:.1f}%): " + _passfail(overall_ok))
    top = report.high_conf_bucket()
    calib_ok = (top is None) or (top.n == 0) or (top.accuracy >= GATE_HIGH_CONF_BUCKET_ACCURACY)
    console.print(f"    High-confidence bucket ≥{GATE_HIGH_CONF_BUCKET_ACCURACY*100:.0f}% accurate: " + _passfail(calib_ok))
    console.print("    → " + ("[green]GATE PASSED — ready for Stage 2.[/green]" if report.production_ready()
                              else "[red]GATE NOT PASSED — tune and re-eval before Stage 2.[/red]"))
    console.print()


def _section_doc_results(report: EvalReport) -> None:
    console.rule("[bold]SECTION 6 — Document-Level Results")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Document")
    table.add_column("Status")
    table.add_column("Fields", justify="right")
    table.add_column("Failures")
    for d in report.doc_results:
        status = "[green]OK[/green]" if d["status"] == "OK" else "[red]FAILED[/red]"
        fields = f"{d['correct']}/{d['total']}"
        fail = ", ".join(d["failures"]) if d["failures"] else "—"
        table.add_row(d["filename"], status, fields, fail)
    console.print(table)
    console.print()


def _passfail(ok: bool) -> str:
    return "[green]✓ PASS[/green]" if ok else "[red]✗ FAIL[/red]"


# ----------------------------------------------------------------------------
# Compare two saved runs
# ----------------------------------------------------------------------------

def render_compare(old: dict, new: dict, old_name: str, new_name: str) -> None:
    console.rule(f"[bold]COMPARE — {old_name}  →  {new_name}")
    table = Table(show_header=True, header_style="bold")
    table.add_column("Field")
    table.add_column(f"{old_name} acc", justify="right")
    table.add_column(f"{new_name} acc", justify="right")
    table.add_column("Δ", justify="right")

    old_fs, new_fs = old.get("field_stats", {}), new.get("field_stats", {})
    for name in sorted(set(old_fs) | set(new_fs)):
        o = old_fs.get(name, {}).get("accuracy", 0.0)
        n = new_fs.get(name, {}).get("accuracy", 0.0)
        delta = n - o
        style = "green" if delta > 0 else ("red" if delta < 0 else "dim")
        arrow = "▲" if delta > 0 else ("▼" if delta < 0 else "—")
        table.add_row(name, f"{o*100:.1f}%", f"{n*100:.1f}%",
                      Text(f"{arrow} {delta*100:+.1f}", style=style))
    console.print(table)

    o_acc = old.get("overall_accuracy", 0.0)
    n_acc = new.get("overall_accuracy", 0.0)
    d = n_acc - o_acc
    style = "green" if d > 0 else ("red" if d < 0 else "dim")
    console.print(f"\n  Overall: {o_acc*100:.1f}% → {n_acc*100:.1f}%  "
                  f"([{style}]{d*100:+.1f} pts[/{style}])")
    console.print(f"  Production ready: {old.get('production_ready')} → {new.get('production_ready')}\n")
