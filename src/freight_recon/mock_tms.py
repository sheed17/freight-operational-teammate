"""Mock TMS data and local UI generation.

This is the first TMS surface Neyma is allowed to touch. It mirrors the generated freight
world closely enough for browser-read and browser-write adapters to prove selectors,
permissioning, readback, and audit behavior before any real TMS is involved.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from decimal import Decimal
from html import escape
from pathlib import Path

from pydantic import BaseModel, Field

from .reconciliation import FreightLoadForReconciliation
from .workflow import WorkflowRun, WorkflowStore

# Documents a broker typically requires on a carrier-payables packet before a voucher can be paid.
_REQUIRED_DOC_TYPES = {
    "rate_confirmation": "Rate confirmation",
    "bol": "BOL",
    "pod": "POD",
}
_LUMPER_KEYS = {"lumper", "lumper_fee"}


class MockTmsCharge(BaseModel):
    name: str
    rate_amount: str | None = None
    invoice_amount: str | None = None
    authorized: bool = True
    backup_document: str | None = None
    terms: str | None = None


class MockTmsDocument(BaseModel):
    doc_type: str
    label: str
    url: str
    present: bool = True


class MockTmsRequiredDoc(BaseModel):
    name: str
    present: bool


class MockTmsRecord(BaseModel):
    load_id: str
    pro_number: str | None = None
    invoice_number: str
    customer: str | None = None
    carrier: str
    carrier_mc: str | None = None
    carrier_dot: str | None = None
    carrier_scac: str | None = None
    shipper: str | None = None
    consignee: str | None = None
    origin: str | None = None
    destination: str | None = None
    pickup_date: str | None = None
    delivery_date: str | None = None
    equipment: str | None = None
    commodity: str | None = None
    rate_total: str
    invoice_total: str
    payable_status: str
    settlement_number: str | None = None
    settlement_status: str | None = None
    payment_terms: str | None = None
    fuel_basis: str | None = None
    expected_outcome: str | None = None
    workflow_run_id: int | None = None
    workflow_state: str | None = None
    workflow_outcome: str | None = None
    workflow_reason: str | None = None
    packet_detail_url: str | None = None
    charges: list[MockTmsCharge] = Field(default_factory=list)
    documents: list[MockTmsDocument] = Field(default_factory=list)
    required_documents: list[MockTmsRequiredDoc] = Field(default_factory=list)


class MockTmsSite(BaseModel):
    output_dir: str
    records: list[MockTmsRecord]


def build_mock_tms_site(
    *,
    output_dir: Path,
    corpus_dir: Path,
    loads: list[FreightLoadForReconciliation],
    store: WorkflowStore | None = None,
) -> MockTmsSite:
    """Write a local mock TMS UI plus machine-readable data for browser-adapter tests."""
    if output_dir.exists():
        shutil.rmtree(output_dir)
    (output_dir / "loads").mkdir(parents=True, exist_ok=True)

    run_by_load = _runs_by_load(store) if store is not None else {}
    records = [
        build_mock_tms_record(load, corpus_dir=corpus_dir, run=run_by_load.get(load.load_id))
        for load in loads
    ]

    (output_dir / "data.json").write_text(
        json.dumps([record.model_dump(mode="json") for record in records], indent=2),
        encoding="utf-8",
    )
    (output_dir / "styles.css").write_text(_styles(), encoding="utf-8")
    (output_dir / "index.html").write_text(_index_html(records), encoding="utf-8")
    (output_dir / "payables.html").write_text(_payables_html(records), encoding="utf-8")
    for record in records:
        (output_dir / "loads" / f"{record.load_id}.html").write_text(
            _load_html(record), encoding="utf-8"
        )
    return MockTmsSite(output_dir=str(output_dir), records=records)


def build_mock_tms_record(
    load: FreightLoadForReconciliation,
    *,
    corpus_dir: Path,
    run: WorkflowRun | None = None,
) -> MockTmsRecord:
    expected_total = _money(
        load.rate_linehaul + load.rate_fuel + sum(c.amount for c in load.rate_accessorials)
    )
    invoice_total = _money(
        load.invoice_linehaul + load.invoice_fuel + sum(c.amount for c in load.invoice_accessorials)
    )
    return MockTmsRecord(
        load_id=load.load_id,
        pro_number=load.pro_number,
        invoice_number=load.invoice_number,
        customer=load.customer,
        carrier=load.carrier,
        carrier_mc=load.carrier_mc or _synth_mc(load.carrier),
        carrier_dot=_synth_dot(load.carrier),
        carrier_scac=_synth_scac(load.carrier),
        shipper=load.shipper,
        consignee=load.consignee,
        origin=load.origin,
        destination=load.destination,
        pickup_date=load.pickup_date,
        delivery_date=load.delivery_date,
        equipment=load.equipment,
        commodity=load.commodity,
        rate_total=expected_total,
        invoice_total=invoice_total,
        payable_status=_payable_status(run),
        settlement_number=_settlement_number(load.load_id),
        settlement_status=_settlement_status(run),
        payment_terms=_payment_terms(load.carrier),
        fuel_basis=_fuel_basis(load.load_id),
        expected_outcome=load.expected_outcome,
        workflow_run_id=run.id if run else None,
        workflow_state=run.state.value if run else None,
        workflow_outcome=run.outcome if run else None,
        workflow_reason=run.reason if run else None,
        packet_detail_url=f"../../packets/{run.id}/" if run else None,
        charges=_charges(load),
        documents=_documents(load, corpus_dir),
        required_documents=_required_documents(load),
    )


def _carrier_hash(carrier: str) -> int:
    return int(hashlib.sha256(carrier.encode("utf-8")).hexdigest(), 16)


def _synth_mc(carrier: str) -> str:
    return f"MC-{_carrier_hash(carrier) % 900000 + 100000}"


def _synth_dot(carrier: str) -> str:
    return f"USDOT {_carrier_hash(carrier + 'dot') % 9000000 + 1000000}"


def _synth_scac(carrier: str) -> str:
    letters = [ch for ch in carrier.upper() if ch.isalpha()]
    scac = "".join(letters[:4])
    return (scac + "XXXX")[:4]


def _settlement_number(load_id: str) -> str:
    digits = "".join(ch for ch in load_id if ch.isdigit()) or "000000"
    return f"STL-{digits}"


def _settlement_status(run: WorkflowRun | None) -> str:
    """Map workflow state to a realistic carrier-settlement (AP voucher) status."""
    if run is None:
        return "PENDING"
    state = run.state.value
    if state == "DONE":
        return "PAID"
    if state == "APPROVED":
        return "APPROVED"
    if state == "DISPUTED":
        return "SHORT_PAY"
    if state in {"NEEDS_REVIEW", "REQUESTED_BACKUP"}:
        return "ON_HOLD"
    return "PENDING"


def _payment_terms(carrier: str) -> str:
    options = ["Quick Pay (1.5% fee, 2 days)", "Standard (Net 30)", "Factored (assigned)"]
    return options[_carrier_hash(carrier + "terms") % len(options)]


def _fuel_basis(load_id: str) -> str:
    options = ["DOE national avg index", "% of linehaul", "flat per-mile FSC"]
    return options[_carrier_hash(load_id + "fuel") % len(options)]


def _required_documents(load: FreightLoadForReconciliation) -> list[MockTmsRequiredDoc]:
    present_types = {doc_type.removesuffix("_dirty") for doc_type in load.documents}
    docs = [
        MockTmsRequiredDoc(name=label, present=doc_type in present_types)
        for doc_type, label in _REQUIRED_DOC_TYPES.items()
    ]
    if any(line.key in _LUMPER_KEYS for line in load.invoice_accessorials):
        docs.append(MockTmsRequiredDoc(name="Lumper receipt", present="lumper_receipt" in present_types))
    return docs


def _runs_by_load(store: WorkflowStore) -> dict[str, WorkflowRun]:
    return {run.load_id: run for run in store.list_runs()}


def _payable_status(run: WorkflowRun | None) -> str:
    if run is None:
        return "NOT_STARTED"
    if run.state.value == "DONE":
        return "AUTO_CLEARED"
    if run.state.value == "APPROVED":
        return "APPROVED_FOR_ENTRY"
    if run.state.value in {"NEEDS_REVIEW", "DISPUTED", "REQUESTED_BACKUP"}:
        return run.state.value
    return "IN_PROGRESS"


def _charges(load: FreightLoadForReconciliation) -> list[MockTmsCharge]:
    charge_names = {line.key: line.name for line in load.rate_accessorials + load.invoice_accessorials}
    rate_by_key = {line.key: line for line in load.rate_accessorials}
    invoice_by_key = {line.key: line for line in load.invoice_accessorials}
    rows = [
        MockTmsCharge(name="linehaul", rate_amount=_money(load.rate_linehaul), invoice_amount=_money(load.invoice_linehaul)),
        MockTmsCharge(
            name="fuel surcharge",
            rate_amount=_money(load.rate_fuel),
            invoice_amount=_money(load.invoice_fuel),
            terms=_fuel_basis(load.load_id),
        ),
    ]
    for key in sorted(charge_names):
        rate = rate_by_key.get(key)
        invoice = invoice_by_key.get(key)
        rows.append(
            MockTmsCharge(
                name=charge_names[key],
                rate_amount=_money(rate.amount) if rate else None,
                invoice_amount=_money(invoice.amount) if invoice else None,
                authorized=rate is not None,
                backup_document=(invoice.backup_document if invoice else rate.backup_document if rate else None),
                terms=_charge_terms(key),
            )
        )
    return rows


def _charge_terms(key: str) -> str | None:
    if "detention" in key:
        return "2 hrs free, then $50/hr"
    if key in _LUMPER_KEYS:
        return "receipt required"
    if "layover" in key:
        return "pre-authorization required"
    if "tonu" in key:
        return "truck ordered not used"
    return None


def _documents(load: FreightLoadForReconciliation, corpus_dir: Path) -> list[MockTmsDocument]:
    docs = []
    for doc_type, rel_path in sorted(load.documents.items()):
        if doc_type.endswith("_dirty"):
            continue
        docs.append(
            MockTmsDocument(
                doc_type=doc_type,
                label=doc_type.replace("_", " ").title(),
                url=str((corpus_dir / rel_path).resolve()),
            )
        )
    return docs


def _index_html(records: list[MockTmsRecord]) -> str:
    rows = "\n".join(
        f"""
        <tr data-load-id="{escape(record.load_id)}" data-invoice="{escape(record.invoice_number)}"
            data-payable-status="{escape(record.payable_status)}">
          <td><a href="loads/{escape(record.load_id)}.html">{escape(record.load_id)}</a></td>
          <td>{escape(record.pro_number or '')}</td>
          <td>{escape(record.customer or '')}</td>
          <td>{escape(record.carrier)}</td>
          <td>{escape(record.origin or '')} → {escape(record.destination or '')}</td>
          <td>{escape(record.pickup_date or '')}</td>
          <td>${escape(record.rate_total)}</td>
          <td>${escape(record.invoice_total)}</td>
          <td><span class="status">{escape(record.payable_status)}</span></td>
        </tr>
        """
        for record in records
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Neyma Mock TMS</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  {_shell_header(active="loads", depth=0)}
  <div class="workspace">
    {_sidebar(active="loads", depth=0)}
    <main>
      <section class="page-title">
        <div>
          <p class="eyebrow">Dispatch</p>
          <h1>Load Board</h1>
          <p class="subtle">Source-of-truth loads, status, payables, and document packet links.</p>
        </div>
        <a class="button secondary" href="data.json">Open Data JSON</a>
      </section>
      <section class="toolbar" aria-label="TMS controls">
        <input id="load-search" name="load-search" data-tms-control="global-search"
          aria-label="Search loads" placeholder="Search load, PRO, invoice, carrier" />
        <button type="button" data-tms-action="filter-exceptions">Exceptions</button>
        <button type="button" data-tms-action="filter-delivered">Delivered</button>
      </section>
      <table aria-label="Mock TMS loads" data-tms-table="loads">
        <thead>
          <tr>
            <th>Load</th><th>PRO</th><th>Customer</th><th>Carrier</th><th>Lane</th>
            <th>Pickup</th><th>Rate</th><th>Invoice</th><th>Payable</th>
          </tr>
        </thead>
        <tbody>
          {rows}
        </tbody>
      </table>
    </main>
  </div>
</body>
</html>
"""


def _payables_html(records: list[MockTmsRecord]) -> str:
    rows = "\n".join(
        f"""
        <tr data-load-id="{escape(record.load_id)}" data-invoice="{escape(record.invoice_number)}"
            data-payable-status="{escape(record.payable_status)}">
          <td><input type="checkbox" aria-label="Select {escape(record.load_id)}"></td>
          <td><a href="loads/{escape(record.load_id)}.html">{escape(record.invoice_number)}</a></td>
          <td>{escape(record.load_id)}</td>
          <td>{escape(record.carrier)}</td>
          <td>${escape(record.rate_total)}</td>
          <td>${escape(record.invoice_total)}</td>
          <td><span class="status">{escape(record.payable_status)}</span></td>
          <td><button type="button" data-tms-action="open-payable" data-load-id="{escape(record.load_id)}">Review</button></td>
        </tr>
        """
        for record in records
        if record.payable_status != "AUTO_CLEARED"
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Carrier Payables · Neyma Mock TMS</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  {_shell_header(active="payables", depth=0)}
  <div class="workspace">
    {_sidebar(active="payables", depth=0)}
    <main>
      <section class="page-title">
        <div>
          <p class="eyebrow">Accounting</p>
          <h1>Carrier Payables</h1>
          <p class="subtle">Queue for invoice review, backup requests, disputes, and approved entries.</p>
        </div>
      </section>
      <section class="toolbar" aria-label="Payables controls">
        <input id="payable-search" name="payable-search" data-tms-control="payable-search"
          aria-label="Search payables" placeholder="Search invoice, load, carrier" />
        <button type="button" data-tms-action="batch-approve">Approve Selected</button>
        <button type="button" data-tms-action="export-payables">Export</button>
      </section>
      <table aria-label="Carrier payable queue" data-tms-table="payables">
        <thead>
          <tr>
            <th></th><th>Invoice</th><th>Load</th><th>Carrier</th><th>Expected</th>
            <th>Billed</th><th>Status</th><th>Action</th>
          </tr>
        </thead>
        <tbody>{rows}</tbody>
      </table>
    </main>
  </div>
</body>
</html>
"""


def _load_html(record: MockTmsRecord) -> str:
    charge_rows = "\n".join(
        f"""
        <tr data-charge-name="{escape(charge.name)}">
          <td>{escape(charge.name.title())}</td>
          <td>{('$' + escape(charge.rate_amount)) if charge.rate_amount else '—'}</td>
          <td>{('$' + escape(charge.invoice_amount)) if charge.invoice_amount else '—'}</td>
          <td>{'Yes' if charge.authorized else 'No'}</td>
          <td>{escape(charge.backup_document or '')}</td>
          <td>{escape(charge.terms or '')}</td>
        </tr>
        """
        for charge in record.charges
    )
    doc_links = "\n".join(
        f'<li data-doc-type="{escape(doc.doc_type)}"><a href="{escape(doc.url)}">{escape(doc.label)}</a></li>'
        for doc in record.documents
    )
    required_rows = "\n".join(
        f"""
        <tr data-required-doc="{escape(doc.name)}">
          <td>{escape(doc.name)}</td>
          <td>{'✓ on file' if doc.present else '✗ missing'}</td>
        </tr>
        """
        for doc in record.required_documents
    )
    packet = (
        f'<a class="button" href="{escape(record.packet_detail_url)}">Open Neyma Packet</a>'
        if record.packet_detail_url
        else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(record.load_id)} · Neyma Mock TMS</title>
  <link rel="stylesheet" href="../styles.css">
</head>
<body>
  {_shell_header(active="loads", depth=1)}
  <div class="workspace">
    {_sidebar(active="loads", depth=1)}
    <main data-load-id="{escape(record.load_id)}">
      <section class="page-title">
        <div>
          <p class="eyebrow">Load Detail</p>
          <h1>{escape(record.load_id)}</h1>
          <p class="subtle">{escape(record.origin or '')} → {escape(record.destination or '')}</p>
        </div>
        <div class="actions compact">
          <a class="button secondary" href="../index.html">Back to Loads</a>
          {packet}
        </div>
      </section>

      <nav class="tabs" aria-label="Load detail tabs">
        <a href="#overview">Overview</a>
        <a href="#accounting">Accounting</a>
        <a href="#documents">Documents</a>
        <a href="#notes">Notes</a>
      </nav>

      <section id="overview" class="summary-grid">
      <div><span>PRO</span><strong data-field="pro_number">{escape(record.pro_number or '')}</strong></div>
      <div><span>Invoice</span><strong data-field="invoice_number">{escape(record.invoice_number)}</strong></div>
      <div><span>Carrier</span><strong data-field="carrier">{escape(record.carrier)}</strong></div>
      <div><span>Customer</span><strong data-field="customer">{escape(record.customer or '')}</strong></div>
      <div><span>Pickup</span><strong data-field="pickup_date">{escape(record.pickup_date or '')}</strong></div>
      <div><span>Delivery</span><strong data-field="delivery_date">{escape(record.delivery_date or '')}</strong></div>
      <div><span>Equipment</span><strong data-field="equipment">{escape(record.equipment or '')}</strong></div>
      <div><span>Commodity</span><strong data-field="commodity">{escape(record.commodity or '')}</strong></div>
    </section>

    <section id="carrier">
      <h2>Carrier &amp; Authority</h2>
      <section class="summary-grid mini">
      <div><span>MC #</span><strong data-field="carrier_mc">{escape(record.carrier_mc or '')}</strong></div>
      <div><span>DOT #</span><strong data-field="carrier_dot">{escape(record.carrier_dot or '')}</strong></div>
      <div><span>SCAC</span><strong data-field="carrier_scac">{escape(record.carrier_scac or '')}</strong></div>
      <div><span>Payment terms</span><strong data-field="payment_terms">{escape(record.payment_terms or '')}</strong></div>
      </section>
    </section>

    <section id="accounting">
      <h2>Accounting &amp; Settlement</h2>
      <section class="summary-grid mini">
      <div><span>Rate total</span><strong data-field="rate_total">${escape(record.rate_total)}</strong></div>
      <div><span>Invoice total</span><strong data-field="invoice_total">${escape(record.invoice_total)}</strong></div>
      <div><span>Payable status</span><strong data-field="payable_status">{escape(record.payable_status)}</strong></div>
      <div><span>Workflow state</span><strong data-field="workflow_state">{escape(record.workflow_state or '')}</strong></div>
      <div><span>Settlement #</span><strong data-field="settlement_number">{escape(record.settlement_number or '')}</strong></div>
      <div><span>Settlement status</span><strong data-field="settlement_status">{escape(record.settlement_status or '')}</strong></div>
      <div><span>Fuel basis</span><strong data-field="fuel_basis">{escape(record.fuel_basis or '')}</strong></div>
      </section>
      <h3>Charge Lines</h3>
      <table aria-label="Charge lines">
        <thead><tr><th>Charge</th><th>Rate</th><th>Invoice</th><th>Authorized</th><th>Backup</th><th>Terms</th></tr></thead>
        <tbody>{charge_rows}</tbody>
      </table>
    </section>

    <section id="required-docs">
      <h2>Required Documents</h2>
      <table aria-label="Required documents">
        <thead><tr><th>Document</th><th>Status</th></tr></thead>
        <tbody>{required_rows}</tbody>
      </table>
    </section>

    <section id="documents" class="grid-two">
      <div>
        <h2>Documents On File</h2>
        <ul>{doc_links}</ul>
      </div>
      <div id="notes">
        <h2>Workflow Note</h2>
        <p data-field="workflow_reason">{escape(record.workflow_reason or 'No exception recorded.')}</p>
      </div>
    </section>
  </main>
  </div>
</body>
</html>
"""


def _shell_header(*, active: str, depth: int) -> str:
    prefix = "../" if depth else ""
    return f"""
  <header class="topbar">
    <div>
      <strong>Neyma Test Freight LLC</strong>
      <span>Brokerage Operations</span>
    </div>
    <nav aria-label="Top navigation">
      <a class="{_active(active, 'loads')}" href="{prefix}index.html">Loads</a>
      <a class="{_active(active, 'payables')}" href="{prefix}payables.html">Payables</a>
      <a href="{prefix}data.json">Data</a>
    </nav>
  </header>
"""


def _sidebar(*, active: str, depth: int) -> str:
    prefix = "../" if depth else ""
    return f"""
    <aside class="sidebar" aria-label="TMS modules">
      <a class="{_active(active, 'loads')}" href="{prefix}index.html">Load Management</a>
      <a>Dispatch Board</a>
      <a>Tracking</a>
      <a>Documents</a>
      <a class="{_active(active, 'payables')}" href="{prefix}payables.html">Carrier Payables</a>
      <a>Customer Billing</a>
      <a>Carriers</a>
      <a>Reports</a>
    </aside>
"""


def _active(active: str, target: str) -> str:
    return "active" if active == target else ""


def _styles() -> str:
    return """
:root { color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #172033; background: #f6f7f9; }
body { margin: 0; }
.topbar { height: 56px; display: flex; justify-content: space-between; align-items: center; padding: 0 22px; background: #162237; color: white; }
.topbar span { color: #bac5d4; margin-left: 10px; font-size: 13px; }
.topbar a { color: #dbe5f1; text-decoration: none; margin-left: 14px; font-weight: 700; font-size: 14px; }
.topbar a.active { color: white; border-bottom: 2px solid #63b3ed; padding-bottom: 4px; }
.workspace { display: grid; grid-template-columns: 220px minmax(0, 1fr); min-height: calc(100vh - 56px); }
.sidebar { background: #ffffff; border-right: 1px solid #d7dde6; padding: 18px 12px; }
.sidebar a { display: block; padding: 10px 12px; color: #2d3b50; text-decoration: none; border-radius: 6px; font-weight: 700; font-size: 14px; }
.sidebar a.active { background: #e8f1fb; color: #174d7e; }
main { max-width: 1220px; width: 100%; box-sizing: border-box; padding: 24px; }
.page-title { display: flex; justify-content: space-between; gap: 16px; align-items: flex-start; margin-bottom: 18px; }
h1 { margin: 4px 0 6px; font-size: 32px; line-height: 1.1; letter-spacing: 0; }
h2 { font-size: 18px; margin: 26px 0 10px; letter-spacing: 0; }
.eyebrow { margin: 0; color: #596780; font-weight: 700; text-transform: uppercase; font-size: 12px; letter-spacing: .08em; }
.subtle { color: #596780; margin: 0; }
.toolbar, .actions { display: flex; gap: 12px; align-items: center; margin: 0 0 16px; flex-wrap: wrap; }
.actions.compact { justify-content: flex-end; }
input { min-width: 280px; border: 1px solid #bfcad8; border-radius: 6px; padding: 10px 12px; font: inherit; background: white; }
button, .button { display: inline-flex; align-items: center; min-height: 38px; padding: 0 12px; border: 1px solid #172033; border-radius: 6px; background: #172033; color: white; text-decoration: none; font: inherit; font-weight: 700; }
.button.secondary, button.secondary { background: white; color: #172033; }
table { width: 100%; border-collapse: collapse; background: white; border: 1px solid #d7dde6; }
th, td { padding: 11px 12px; border-bottom: 1px solid #e4e8ee; text-align: left; vertical-align: top; }
th { background: #edf1f5; color: #303b4d; font-size: 13px; }
a { color: #1c5f9f; }
.status { font-weight: 700; }
.summary-grid, .grid-two { display: grid; gap: 14px; grid-template-columns: repeat(2, minmax(0, 1fr)); }
.summary-grid div, .grid-two > div { background: white; border: 1px solid #d7dde6; border-radius: 6px; padding: 14px; }
.summary-grid.mini { margin-bottom: 14px; grid-template-columns: repeat(4, minmax(0, 1fr)); }
.summary-grid span { display: block; color: #596780; font-size: 12px; font-weight: 700; text-transform: uppercase; margin-bottom: 6px; }
.summary-grid strong { font-size: 18px; }
.tabs { display: flex; gap: 8px; margin: 0 0 16px; border-bottom: 1px solid #d7dde6; }
.tabs a { padding: 10px 12px; text-decoration: none; color: #2d3b50; font-weight: 700; }
.tabs a:first-child { border-bottom: 3px solid #174d7e; color: #174d7e; }
ul { margin: 0; padding-left: 20px; }
@media (max-width: 900px) { .workspace { grid-template-columns: 1fr; } .sidebar { display: none; } .page-title { display: block; } .summary-grid, .summary-grid.mini, .grid-two { grid-template-columns: 1fr; } table { font-size: 14px; } }
"""


def _money(value: Decimal) -> str:
    return f"{value:.2f}"
