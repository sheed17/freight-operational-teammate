"""Static local operator console for dogfood artifact inspection.

This is a developer/dogfood inspection page, not the product UI. Slack remains the human review
surface; this page helps us see the local pilot spine without opening five JSON files.
"""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from .delivery import DeliveryMessage
from .review import ReviewPayload


def build_operator_console(
    *,
    output_dir: Path,
    report: dict[str, Any],
    payloads: list[ReviewPayload],
    delivery_messages: list[DeliveryMessage],
    run_states: dict[int, str] | None = None,
) -> Path:
    """Write ``site/operator/index.html`` for local dogfood inspection."""
    operator_dir = output_dir / "operator"
    operator_dir.mkdir(parents=True, exist_ok=True)
    page = operator_dir / "index.html"
    page.write_text(_render_console(report, payloads, delivery_messages, run_states or {}), encoding="utf-8")
    return page


def _render_console(
    report: dict[str, Any],
    payloads: list[ReviewPayload],
    delivery_messages: list[DeliveryMessage],
    run_states: dict[int, str],
) -> str:
    mailbox = report.get("mailbox_workflow") or {}
    safety = report.get("mailbox_safety") or {}
    states = report.get("workflow_states") or {}
    artifacts = report.get("artifacts") or {}
    summary = report.get("daily_summary_text") or ""
    cards = "\n".join(_review_card(payload, run_states.get(payload.run_id, payload.state.value)) for payload in payloads)
    messages = "\n".join(_message_row(message) for message in delivery_messages)
    gates = _gate_list(report)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Neyma Dogfood Operator Console</title>
  <link rel="stylesheet" href="../styles.css">
</head>
<body>
  <header class="topbar">
    <div>
      <p class="eyebrow">{escape(str(report.get("company", "Neyma")))} · {escape(str(report.get("role", "operator")))}</p>
      <h1>Dogfood Operator Console</h1>
    </div>
    <div class="status info">{escape(str(report.get("operator", "Rasheed")))}</div>
  </header>

  <main class="page">
    <section class="summary-band">
      {_metric("Loads", report.get("loads_generated"))}
      {_metric("Inbox emails", mailbox.get("scanned"))}
      {_metric("Packet runs", mailbox.get("packet_runs"))}
      {_metric("Needs review", report.get("review_payloads"))}
      {_metric("Done", states.get("DONE", 0))}
    </section>

    <section class="grid-two">
      <div>
        <h2>Mailbox Workflow</h2>
        <table><tbody>
          {_row("New messages", mailbox.get("new_messages"))}
          {_row("Duplicates", mailbox.get("duplicates"))}
          {_row("Unlinked messages", mailbox.get("unlinked_messages"))}
          {_row("Workflow runs touched", mailbox.get("workflow_runs_touched"))}
          {_row("Delivery messages", mailbox.get("delivery_messages"))}
        </tbody></table>
      </div>
      <div>
        <h2>Safety Cases</h2>
        <table><tbody>
          {_row("Missing docs reviewed", safety.get("missing_required_reviews"))}
          {_row("Wrong-load/extraneous reviewed", safety.get("extraneous_reviews"))}
          {_row("Duplicate invoices reviewed", safety.get("duplicate_reviews"))}
          {_row("Unlinked reviewed", safety.get("unlinked_reviews"))}
          {_row("Mock TMS write verified", report.get("mock_tms_write_verified"))}
        </tbody></table>
      </div>
    </section>

    <section>
      <h2>Review Work</h2>
      <div class="operator-card-grid">{cards}</div>
    </section>

    <section class="grid-two">
      <div>
        <h2>Signed Delivery Messages</h2>
        <table>
          <thead><tr><th>Run</th><th>Route</th><th>Actions</th></tr></thead>
          <tbody>{messages}</tbody>
        </table>
      </div>
      <div>
        <h2>Daily Summary</h2>
        <pre>{escape(summary)}</pre>
      </div>
    </section>

    <section class="grid-two">
      <div>
        <h2>Pilot Gates</h2>
        <ul>{gates}</ul>
      </div>
      <div>
        <h2>Artifacts</h2>
        <div class="evidence-list">
          {_artifact_link("Pilot report", artifacts.get("pilot_report"))}
          {_artifact_link("Mailbox workflow", artifacts.get("mailbox_workflow"))}
          {_artifact_link("Delivery messages", artifacts.get("delivery_messages"))}
          {_artifact_link("Daily summary", artifacts.get("daily_summary"))}
          {_artifact_link("Mock TMS", artifacts.get("mock_tms"))}
        </div>
      </div>
    </section>
  </main>
</body>
</html>
"""


def _metric(label: str, value: Any) -> str:
    return f"<div><p class=\"label\">{escape(label)}</p><p>{escape(_display(value))}</p></div>"


def _row(label: str, value: Any) -> str:
    return f"<tr><th>{escape(label)}</th><td>{escape(_display(value))}</td></tr>"


def _review_card(payload: ReviewPayload, current_state: str) -> str:
    reasons = "; ".join(payload.reasons[:2])
    if current_state == "NEEDS_REVIEW":
        action_text = ", ".join(option.label for option in payload.action_options)
    else:
        action_text = f"No active review actions; current state is {current_state}"
    return (
        '<article class="operator-card">'
        f'<div class="status {payload.severity.value.lower()}">{escape(payload.severity.value)}</div>'
        f"<h3>{escape(payload.load_id)} · {escape(payload.carrier)}</h3>"
        f"<p>{escape(payload.summary)}</p>"
        f"<p><strong>Current state:</strong> {escape(current_state)}</p>"
        f"<p><strong>Reason:</strong> {escape(reasons)}</p>"
        f"<p><strong>Actions:</strong> {escape(action_text)}</p>"
        f'<a href="../packets/{payload.run_id}/">Open packet</a>'
        "</article>"
    )


def _message_row(message: DeliveryMessage) -> str:
    actions = ", ".join(action.label for action in message.actions)
    return (
        "<tr>"
        f"<td>{message.run_id}</td>"
        f"<td>{escape(message.route.value)}{' / ping' if message.ping else ''}</td>"
        f"<td>{escape(actions)}</td>"
        "</tr>"
    )


def _gate_list(report: dict[str, Any]) -> str:
    gates = {
        "Signed action applied": report.get("signed_action_applied"),
        "Callback action applied": report.get("local_callback_action_applied"),
        "TMS readback verified": report.get("tms_readback_verified"),
        "Mock TMS write verified": report.get("mock_tms_write_verified"),
        "No real TMS write": not (report.get("sample_tms_write_drill") or {}).get("real_tms_write", True),
    }
    return "".join(
        f"<li><strong>{escape(name)}</strong>: {'pass' if passed else 'fail'}</li>"
        for name, passed in gates.items()
    )


def _artifact_link(label: str, path: Any) -> str:
    if not path:
        return f"<span>{escape(label)} unavailable</span>"
    return f'<a href="{escape(_artifact_href(str(path)))}" target="_blank">{escape(label)}</a>'


def _artifact_href(path: str) -> str:
    artifact = Path(path)
    if artifact.is_dir():
        return "../" + artifact.name + "/"
    return "../../" + artifact.name


def _display(value: Any) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    if value is None:
        return "0"
    return str(value)
