"""The activity timeline: a plain-language, owner-readable record of what Neyma actually did.

Trust in an autonomous teammate comes from being able to check its work, so this turns the audit and
security event logs the safety spine already writes into a "show your work" timeline a controller can
read at a glance — every consequential action, who/what triggered it, and the verifiable artifact.

It is read-only and curated: it surfaces the events an owner cares about (operations run, payables
written + verified, decisions applied, approvals rejected, disputes flagged, documents received) and
omits internal state-machine noise. The raw logs remain the source of truth for a deep audit.
"""

from __future__ import annotations

from dataclasses import dataclass

from .workflow import WorkflowStore


@dataclass
class ActivityEvent:
    at: str
    icon: str
    summary: str
    actor: str | None = None
    ref: str | None = None  # load id / invoice id when known


def _ref(payload: dict) -> str | None:
    for key in ("load_id", "load_ref", "invoice_number", "lane"):
        val = payload.get(key)
        if val:
            return str(val)
    return None


def _op_applied(p: dict) -> tuple[str, str]:
    lane = p.get("lane") or "operation"
    status = p.get("status", "")
    amt = f" · ${p['approved_amount']}" if p.get("approved_amount") else ""
    return "🤖", f"Ran {lane} — {status}{amt}"


def _op_failed(p: dict) -> tuple[str, str]:
    return "⚠️", f"Operation failed: {p.get('summary') or p.get('error', 'see audit')}"


def _op_rejected(p: dict) -> tuple[str, str]:
    return "🚫", f"Rejected an approval ({p.get('failure', 'invalid')})"


def _decision_applied(p: dict) -> tuple[str, str]:
    return "👤", f"Applied your decision ({p.get('decision', 'review action')})"


# event_type -> (renderer). Only owner-relevant, consequential events are surfaced.
_RENDERERS = {
    "slack_operation_applied": _op_applied,
    "slack_operation_failed": _op_failed,
    "slack_operation_rejected": _op_rejected,
    "delivery_action_applied": _decision_applied,
    "entry_done": lambda p: ("✅", "Wrote and verified a payable"),
    "entry_confirmed": lambda p: ("✅", "Confirmed a payable entry"),
    "review_disputed": lambda p: ("⚠️", "Flagged a dispute for review"),
    "document_received": lambda p: ("📥", "Received a document"),
}


def build_activity(store: WorkflowStore, *, limit: int = 20) -> list[ActivityEvent]:
    """Merge audit + security events into a curated, newest-first owner timeline."""
    raw = list(store.audit_events()) + list(store.security_events())
    events: list[ActivityEvent] = []
    for e in raw:
        render = _RENDERERS.get(e["event_type"])
        if render is None:
            continue
        payload = e.get("payload") or {}
        icon, summary = render(payload)
        events.append(ActivityEvent(
            at=e.get("created_at", ""), icon=icon, summary=summary,
            actor=e.get("actor"), ref=_ref(payload),
        ))
    events.sort(key=lambda ev: ev.at, reverse=True)
    return events[:limit]


def render_activity(events: list[ActivityEvent]) -> str:
    """Render the timeline for Slack — short, scannable, proof-bearing."""
    if not events:
        return ":sparkles: No activity to show yet."
    lines = ["*What Neyma did* (most recent first):"]
    for ev in events:
        ref = f" — {ev.ref}" if ev.ref else ""
        when = ev.at[:16].replace("T", " ") if ev.at else ""
        stamp = f"  _{when}_" if when else ""
        lines.append(f"{ev.icon} {ev.summary}{ref}{stamp}")
    return "\n".join(lines)
