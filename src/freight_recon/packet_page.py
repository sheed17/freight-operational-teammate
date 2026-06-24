"""Static packet detail pages for the internal dogfood pilot."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from html import escape
import shutil
from pathlib import Path

from .reconciliation import FreightLoadForReconciliation
from .review import ReviewPayload
from .workflow import WorkflowRun, WorkflowStore


@dataclass(frozen=True)
class PacketPageResult:
    run_id: int
    load_id: str
    path: Path
    url_path: str


def build_packet_site(
    *,
    output_dir: Path,
    corpus_dir: Path,
    store: WorkflowStore,
    loads: dict[str, FreightLoadForReconciliation],
    payloads: list[ReviewPayload],
) -> list[PacketPageResult]:
    """Build local static packet pages and evidence links."""
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "packets").mkdir(exist_ok=True)
    (output_dir / "evidence").mkdir(exist_ok=True)
    _write_css(output_dir / "styles.css")
    (output_dir / "favicon.ico").write_bytes(b"")

    results: list[PacketPageResult] = []
    for payload in payloads:
        run = store.get_run(payload.run_id)
        if run is None:
            raise ValueError(f"workflow run not found for payload: {payload.run_id}")
        packet_dir = output_dir / "packets" / str(payload.run_id)
        packet_dir.mkdir(parents=True, exist_ok=True)
        page = packet_dir / "index.html"
        load = loads.get(payload.load_id)
        if load is None:
            page.write_text(_render_unlinked_packet_page(run, payload, store.audit_events(run.id)), encoding="utf-8")
        else:
            _copy_evidence(output_dir, corpus_dir, load)
            page.write_text(_render_packet_page(run, load, payload, store.audit_events(run.id)), encoding="utf-8")
        results.append(
            PacketPageResult(
                run_id=payload.run_id,
                load_id=payload.load_id,
                path=page,
                url_path=f"/packets/{payload.run_id}/",
            )
        )

    _write_index(output_dir / "index.html", results)
    return results


def _render_packet_page(
    run: WorkflowRun,
    load: FreightLoadForReconciliation,
    payload: ReviewPayload,
    audit_events: list[dict],
) -> str:
    expected_total = _expected_total(load)
    invoice_total = _invoice_total(load)
    delta = invoice_total - expected_total
    invoice_src = _site_doc_path(load, "carrier_invoice")
    rate_src = _site_doc_path(load, "rate_confirmation")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(payload.load_id)} Packet</title>
  <link rel="stylesheet" href="../../styles.css">
</head>
<body>
  <header class="topbar">
    <div>
      <p class="eyebrow">{escape(payload.client.company_name)} · {escape(payload.client.operator_role)}</p>
      <h1>{escape(payload.load_id)} · {escape(payload.invoice_number)}</h1>
    </div>
    <div class="status {payload.severity.value.lower()}">{escape(payload.severity.value)}</div>
  </header>

  <main class="page">
    <section class="summary-band">
      <div>
        <p class="label">Carrier</p>
        <p>{escape(payload.carrier)}</p>
      </div>
      <div>
        <p class="label">Outcome</p>
        <p>{escape(payload.outcome.value)}</p>
      </div>
      <div>
        <p class="label">Route</p>
        <p>{escape(payload.routing.route.value)}</p>
      </div>
      <div>
        <p class="label">Flagged</p>
        <p>${escape(payload.found_money.flagged_amount)}</p>
      </div>
      <div>
        <p class="label">Age</p>
        <p>{payload.aging.age_hours}h{", overdue" if payload.aging.is_overdue else ""}</p>
      </div>
    </section>

    <section class="reason-row">
      <div>
        <h2>Decision Needed</h2>
        <p>{escape(payload.summary)}</p>
        {_reason_list(payload.reasons)}
      </div>
      <div>
        <h2>Actions</h2>
        <div class="actions">{_action_buttons(payload)}</div>
      </div>
    </section>

    <section class="documents">
      <div>
        <div class="section-heading">
          <h2>Carrier Invoice</h2>
          <a href="{escape(invoice_src)}" target="_blank">Open PDF</a>
        </div>
        <iframe src="{escape(invoice_src)}" title="Carrier invoice"></iframe>
      </div>
      <div>
        <div class="section-heading">
          <h2>Rate Confirmation</h2>
          <a href="{escape(rate_src)}" target="_blank">Open PDF</a>
        </div>
        <iframe src="{escape(rate_src)}" title="Rate confirmation"></iframe>
      </div>
    </section>

    <section class="grid-two">
      <div>
        <h2>Reconciliation Math</h2>
        <table>
          <tbody>
            <tr><th>Expected payable</th><td>${_money(expected_total)}</td></tr>
            <tr><th>Invoice total</th><td>${_money(invoice_total)}</td></tr>
            <tr><th>Difference</th><td class="delta">${_money(delta)}</td></tr>
          </tbody>
        </table>
      </div>
      <div>
        <h2>Extracted Fields</h2>
        <table>
          <thead><tr><th>Field</th><th>Invoice</th><th>Expected</th><th>Status</th></tr></thead>
          <tbody>{_field_rows(payload)}</tbody>
        </table>
      </div>
    </section>

    <section>
      <h2>Evidence</h2>
      <div class="evidence-list">{_evidence_links(load)}</div>
    </section>

    <section class="grid-two">
      <div>
        <h2>Draft Follow-Up</h2>
        <pre>{escape(_draft_preview(payload, load))}</pre>
      </div>
      <div>
        <h2>Audit History</h2>
        <ol class="audit">{_audit_items(audit_events)}</ol>
      </div>
    </section>
  </main>
</body>
</html>
"""


def _write_index(path: Path, pages: list[PacketPageResult]) -> None:
    links = "\n".join(
        f'<li><a href="{escape(page.url_path)}">{escape(page.load_id)} · run {page.run_id}</a></li>'
        for page in pages
    )
    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Neyma Packet Pages</title>
  <link rel="stylesheet" href="/styles.css">
</head>
<body>
  <header class="topbar"><div><p class="eyebrow">Neyma Test Freight LLC</p><h1>Packet Detail Pages</h1></div></header>
  <main class="page">
    <section><h2>Operator Console</h2><p><a href="operator/">Open dogfood operator console</a></p></section>
    <section><h2>Needs Review</h2><ul class="index-list">{links}</ul></section>
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )


def _render_unlinked_packet_page(
    run: WorkflowRun,
    payload: ReviewPayload,
    audit_events: list[dict],
) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Unlinked Packet</title>
  <link rel="stylesheet" href="../../styles.css">
</head>
<body>
  <header class="topbar">
    <div>
      <p class="eyebrow">{escape(payload.client.company_name)} · unlinked inbox work</p>
      <h1>{escape(payload.title)}</h1>
    </div>
    <div class="status {payload.severity.value.lower()}">{escape(payload.severity.value)}</div>
  </header>
  <main class="page">
    <section class="reason-row">
      <div>
        <h2>Decision Needed</h2>
        <p>{escape(payload.summary)}</p>
        {_reason_list(payload.reasons)}
      </div>
      <div>
        <h2>Workflow State</h2>
        <table><tbody>
          <tr><th>Run</th><td>{run.id}</td></tr>
          <tr><th>State</th><td>{escape(run.state.value)}</td></tr>
          <tr><th>Sender</th><td>{escape(payload.carrier)}</td></tr>
        </tbody></table>
      </div>
    </section>
    <section>
      <h2>Received Evidence</h2>
      <div class="evidence-list">{_payload_evidence_links(payload)}</div>
    </section>
    <section>
      <h2>Audit History</h2>
      <ol class="audit">{_audit_items(audit_events)}</ol>
    </section>
  </main>
</body>
</html>
"""


def _write_css(path: Path) -> None:
    path.write_text(
        """
:root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
body { margin: 0; background: #f6f7f9; color: #172026; }
.topbar { min-height: 88px; display: flex; justify-content: space-between; align-items: center; padding: 20px 28px; background: #ffffff; border-bottom: 1px solid #d8dee6; }
.eyebrow, .label { margin: 0 0 4px; color: #657282; font-size: 12px; text-transform: uppercase; letter-spacing: 0; font-weight: 700; }
h1 { margin: 0; font-size: 28px; line-height: 1.15; }
h2 { margin: 0 0 12px; font-size: 17px; }
.page { max-width: 1440px; margin: 0 auto; padding: 20px; display: grid; gap: 16px; }
section, .reason-row > div, .grid-two > div { background: #ffffff; border: 1px solid #d8dee6; border-radius: 8px; padding: 16px; }
.summary-band { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 12px; }
.summary-band p { margin: 0; overflow-wrap: anywhere; }
.status { border-radius: 999px; padding: 8px 12px; font-weight: 800; font-size: 13px; }
.status.critical { background: #ffe5e2; color: #9d1c12; }
.status.warning { background: #fff1c7; color: #7a4b00; }
.status.info { background: #e6f0ff; color: #16437e; }
.reason-row, .grid-two, .documents { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); gap: 16px; }
.documents iframe { width: 100%; height: 620px; border: 1px solid #c8d0da; border-radius: 6px; background: #f3f5f8; }
.section-heading { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 10px; }
a { color: #0b5cad; font-weight: 700; text-decoration: none; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; border-bottom: 1px solid #edf0f3; padding: 8px; vertical-align: top; }
th { color: #526170; font-size: 12px; text-transform: uppercase; letter-spacing: 0; }
.delta { font-weight: 800; }
.actions { display: grid; gap: 8px; }
.action { border: 1px solid #aeb9c6; border-radius: 6px; padding: 10px 12px; background: #f8fafc; }
.action strong { display: block; margin-bottom: 4px; }
.evidence-list { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 8px; }
.evidence-list a { display: block; border: 1px solid #d8dee6; border-radius: 6px; padding: 10px; background: #fafbfc; overflow-wrap: anywhere; }
pre { white-space: pre-wrap; margin: 0; background: #f6f7f9; border: 1px solid #d8dee6; border-radius: 6px; padding: 12px; line-height: 1.45; }
.audit { margin: 0; padding-left: 22px; display: grid; gap: 8px; }
.audit li { padding-bottom: 8px; border-bottom: 1px solid #edf0f3; }
.index-list { font-size: 16px; display: grid; gap: 10px; }
.operator-card-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 12px; }
.operator-card { border: 1px solid #d8dee6; border-radius: 8px; padding: 14px; display: grid; gap: 8px; background: #fafbfc; }
.operator-card h3 { margin: 0; font-size: 16px; line-height: 1.25; }
.operator-card p { margin: 0; overflow-wrap: anywhere; }
@media (max-width: 900px) { .summary-band, .reason-row, .grid-two, .documents { grid-template-columns: 1fr; } .documents iframe { height: 480px; } }
""",
        encoding="utf-8",
    )


def _copy_evidence(output_dir: Path, corpus_dir: Path, load: FreightLoadForReconciliation) -> None:
    target_dir = output_dir / "evidence" / load.load_id
    target_dir.mkdir(parents=True, exist_ok=True)
    for doc_type, rel in load.documents.items():
        source = corpus_dir / rel
        if source.exists():
            shutil.copyfile(source, target_dir / f"{doc_type}.pdf")


def _site_doc_path(load: FreightLoadForReconciliation, doc_type: str) -> str:
    if doc_type not in load.documents:
        return "about:blank"
    return f"../../evidence/{load.load_id}/{doc_type}.pdf"


def _evidence_links(load: FreightLoadForReconciliation) -> str:
    return "\n".join(
        f'<a href="../../evidence/{escape(load.load_id)}/{escape(doc_type)}.pdf" target="_blank">{escape(doc_type.replace("_", " ").title())}</a>'
        for doc_type in sorted(load.documents)
    )


def _payload_evidence_links(payload: ReviewPayload) -> str:
    return "\n".join(
        f'<a href="{escape(link.path)}" target="_blank">{escape(link.label)}</a>'
        for link in payload.evidence_links
    )


def _reason_list(reasons: list[str]) -> str:
    if not reasons:
        return ""
    return "<ul>" + "".join(f"<li>{escape(reason)}</li>" for reason in reasons) + "</ul>"


def _action_buttons(payload: ReviewPayload) -> str:
    return "\n".join(
        f'<div class="action"><strong>{escape(action.label)}</strong><span>{escape(action.consequence)}</span></div>'
        for action in payload.action_options
    )


def _field_rows(payload: ReviewPayload) -> str:
    return "\n".join(
        "<tr>"
        f"<td>{escape(field.label)}</td>"
        f"<td>{escape(field.invoice_value or '')}</td>"
        f"<td>{escape(field.expected_value or '')}</td>"
        f"<td>{escape(field.status)}</td>"
        "</tr>"
        for field in payload.fields
    )


def _audit_items(events: list[dict]) -> str:
    return "\n".join(
        f"<li><strong>{escape(event['event_type'])}</strong> · {escape(event['created_at'])}<br>{escape(str(event.get('to_state') or event.get('actor') or ''))}</li>"
        for event in events
    )


def _draft_preview(payload: ReviewPayload, load: FreightLoadForReconciliation) -> str:
    if payload.outcome.value == "VARIANCE":
        return (
            f"Subject: Invoice {payload.invoice_number} variance on load {payload.load_id}\n\n"
            f"Please review invoice {payload.invoice_number}. Our records show an expected payable "
            f"of ${_money(_expected_total(load))}, but the invoice totals ${_money(_invoice_total(load))}.\n\n"
            f"Reason: {'; '.join(payload.reasons)}\n\n"
            "Please send revised invoice or backup for the variance."
        )
    if payload.outcome.value == "NEEDS_REVIEW":
        return (
            f"Subject: Backup needed for invoice {payload.invoice_number}\n\n"
            f"Please send the missing backup for load {payload.load_id}.\n\n"
            f"Reason: {'; '.join(payload.reasons)}"
        )
    if payload.outcome.value == "DUPLICATE":
        return (
            f"Subject: Duplicate invoice check for {payload.invoice_number}\n\n"
            f"We received invoice {payload.invoice_number} more than once for {payload.carrier}. "
            "Please confirm which packet should be processed."
        )
    return "No draft needed."


def _invoice_total(load: FreightLoadForReconciliation) -> Decimal:
    return load.invoice_linehaul + load.invoice_fuel + sum(line.amount for line in load.invoice_accessorials)


def _expected_total(load: FreightLoadForReconciliation) -> Decimal:
    return load.rate_linehaul + load.rate_fuel + sum(line.amount for line in load.rate_accessorials)


def _money(value: Decimal) -> str:
    return f"{value:.2f}"
