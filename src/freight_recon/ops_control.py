"""Owner-reachable operational switches, persisted and audited.

The first switch is the TMS-writes **brake**: an owner can pause all payable entry from Slack the
moment something looks wrong, and resume it later — no config edit, no redeploy. The executor reads
this before entering any payable, so a pause holds APPROVED runs in place rather than failing them.

Backed by a small JSON file (one per workspace) so a Slack command can flip it and the gated write
path can read it. Every flip appends an audit entry (who, when, why).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .atomic_io import atomic_write_json


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class OpsControl:
    """Persisted, audited operational switches for one workspace."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def _read(self) -> dict:
        if self.path.exists():
            try:
                return json.loads(self.path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {"tms_writes_paused": False, "paused_by": None, "paused_at": None, "reason": None, "log": []}

    def _write(self, state: dict) -> None:
        atomic_write_json(self.path, state, indent=2, sort_keys=False)

    # --- TMS-writes brake -------------------------------------------------

    def is_tms_writes_paused(self) -> bool:
        return bool(self._read().get("tms_writes_paused"))

    def pause_tms_writes(self, *, actor: str, reason: str = "") -> dict:
        state = self._read()
        if not state.get("tms_writes_paused"):
            state["log"] = [*state.get("log", []), {"action": "pause", "actor": actor, "reason": reason, "at": _now()}]
        state.update({"tms_writes_paused": True, "paused_by": actor, "paused_at": _now(), "reason": reason})
        self._write(state)
        return state

    def resume_tms_writes(self, *, actor: str) -> dict:
        state = self._read()
        if state.get("tms_writes_paused"):
            state["log"] = [*state.get("log", []), {"action": "resume", "actor": actor, "at": _now()}]
        state.update({"tms_writes_paused": False, "paused_by": None, "paused_at": None, "reason": None})
        self._write(state)
        return state

    def status(self) -> dict:
        state = self._read()
        return {
            "tms_writes_paused": bool(state.get("tms_writes_paused")),
            "paused_by": state.get("paused_by"),
            "paused_at": state.get("paused_at"),
            "reason": state.get("reason"),
        }


class TmsWritesPausedError(Exception):
    """Raised when a payable entry is attempted while the TMS-writes brake is engaged."""


# Run states an owner still needs to deal with (for "show unresolved").
_OPEN_STATES = {"NEEDS_REVIEW", "DISPUTED", "FAILED", "WAITING_FOR_SESSION", "REQUESTED_BACKUP"}

_HELP = (
    "Commands:\n"
    "• `status` — what Neyma is doing right now (health, the TMS brake, what's waiting on you)\n"
    "• `roi` — what Neyma recovered/invoiced and the hours it saved\n"
    "• `audit` — a timeline of what Neyma actually did\n"
    "• `know` / `know about <X>` — what Neyma has learned (a carrier, customer, or the system)\n"
    "• `learn <fact>` — teach it a fact, e.g. `learn Northbound is order #1002`\n"
    "• `sop <procedure>` — add a company procedure, e.g. `sop raise_invoice: always include the load reference`\n"
    "• `forget <id or words>` — correct or remove something it learned\n"
    "• `autonomy` — which lanes run unattended, and their limits\n"
    "• `graduate <lane> [$amount]` / `supervise <lane>` — full-auto a lane / put it back to staged\n"
    "• `pause tms writes` / `resume tms writes` — the brake\n"
    "• `show unresolved` — open items waiting on you  ·  `status <LOAD-ID>` — one load's status"
)


def handle_ops_command(text: str, *, actor: str, ops_control: OpsControl, store=None, status_file=None) -> str:
    """Parse one lightweight owner command from Slack into an action + reply. Channel-neutral."""
    raw = text.strip()
    cmd = " ".join(raw.lower().split())
    if cmd in ("", "help", "commands", "command", "?", "menu", "what can you do", "what can i do"):
        return _HELP
    if cmd in ("pause", "pause tms writes", "pause writes", "pause tms"):
        ops_control.pause_tms_writes(actor=actor, reason="paused from Slack")
        return f":lock: TMS writes *PAUSED* by {actor}. No payables will be entered until resumed."
    if cmd in ("resume", "resume tms writes", "resume writes", "resume tms"):
        ops_control.resume_tms_writes(actor=actor)
        return f":unlock: TMS writes *RESUMED* by {actor}."
    if cmd in ("status", "ops status", "health", "what is neyma doing", "whats neyma doing", "what's neyma doing"):
        return _render_operational_status(ops_control, store=store, status_file=status_file)
    if cmd in ("roi", "value", "what have you done", "what neyma did", "savings") and store is not None:
        from .roi_ledger import build_value_digest, render_value_digest

        return render_value_digest(build_value_digest(store), period="so far")
    if cmd in ("audit", "activity", "log", "show your work", "what did you do") and store is not None:
        from .activity_log import build_activity, render_activity

        return render_activity(build_activity(store))
    if cmd in ("know", "knowledge", "what do you know", "what have you learned") and store is not None:
        return _knowledge_for(store).render(tenant="default")
    if store is not None and cmd.startswith("know ") and len(raw.split(None, 1)) == 2:
        q = raw.split(None, 1)[1].strip()
        ql = q.lower()
        if ql == "about":            # "know about" with no subject -> show everything
            q = ""
        elif ql.startswith("about "):
            q = q[6:].strip()
        return _knowledge_for(store).render(tenant="default", query=q)
    if store is not None and raw.strip().lower().startswith("learn ") and len(raw.split(None, 1)) == 2:
        from .knowledge import FactKind

        fact = raw.split(None, 1)[1].strip()
        _knowledge_for(store).learn(fact, tenant="default", kind=FactKind.BUSINESS, source="owner")
        return f":brain: Got it — I'll remember that: {fact}"
    if store is not None and raw.strip().lower().startswith("sop ") and len(raw.split(None, 1)) == 2:
        from .knowledge import FactKind

        # An SOP scoped to a task: "sop raise_invoice: always include the load reference" -> subject=raise_invoice.
        body = raw.split(None, 1)[1].strip()
        subject = None
        if ":" in body and len(body.split(":", 1)[0].split()) <= 3:
            subject, body = body.split(":", 1)[0].strip(), body.split(":", 1)[1].strip()
        _knowledge_for(store).learn(body, tenant="default", kind=FactKind.PROCEDURE, subject=subject, source="onboarding")
        scope = f" for *{subject}*" if subject else ""
        return f":clipboard: Noted the procedure{scope}: {body}"
    if store is not None and raw.strip().lower().startswith("forget ") and len(raw.split(None, 1)) == 2:
        n = _knowledge_for(store).forget(raw.split(None, 1)[1].strip(), tenant="default")
        return f":wastebasket: Forgot {n} fact(s)." if n else "Nothing matched — try `know` to see what I've learned."
    if cmd in ("autonomy", "show autonomy", "graduations", "what is autonomous") and store is not None:
        return _render_autonomy(store)
    parts = raw.split(None, 1)  # guard: empty text ("/neyma" with no args) must not IndexError
    if store is not None and len(parts) == 2 and parts[0].lower() in (
        "graduate", "autonomous", "supervise", "restrict"
    ):
        return _handle_graduation(store, parts[0].lower(), parts[1].strip(), actor=actor)
    if cmd in ("show unresolved", "unresolved", "show open") and store is not None:
        return _render_unresolved(store)
    if cmd.startswith("status ") and store is not None:
        return _render_load_status(store, raw.split(None, 1)[1].strip())
    return _HELP


def _graduation_for(store):
    from .lane_graduation import LaneGraduation

    return LaneGraduation(Path(store.db_path).parent / "lane_graduation.json")


def _knowledge_for(store):
    from .knowledge import KnowledgeBase

    # Same file the driving agent writes SYSTEM facts to, so Slack + the agent share one memory.
    return KnowledgeBase(Path(store.db_path).parent / "agent_memory.json")


def _known_lane_names() -> set[str]:
    from .operation_router import freight_lanes

    return {lane.name for lane in freight_lanes()}


def _handle_graduation(store, verb: str, arg: str, *, actor: str, tenant: str = "default") -> str:
    """Flip a lane between supervised and autonomous from Slack, optionally with a dollar ceiling:
    `graduate raise_invoice 2500`. Unknown lanes are refused, not created."""
    parts = arg.split()
    lane = parts[0] if parts else ""
    if lane not in _known_lane_names():
        known = ", ".join(sorted(_known_lane_names()))
        return f"Unknown lane `{lane}`. Known lanes: {known}."
    grad = _graduation_for(store)
    if verb in ("graduate", "autonomous"):
        ceiling = parts[1].lstrip("$") if len(parts) > 1 else None
        grad.graduate(tenant, lane, actor=actor, reason="graduated from Slack", max_amount=ceiling)
        cap = f" up to ${ceiling}/run" if ceiling else " (no dollar ceiling set — consider adding one)"
        return f":rocket: Lane *{lane}* is now *AUTONOMOUS*{cap} — I'll run approved work on it unattended."
    grad.restrict(tenant, lane, actor=actor, reason="restricted from Slack")
    return f":lock: Lane *{lane}* is back to *SUPERVISED* — it will ask for your approval before running."


def _render_autonomy(store, tenant: str = "default") -> str:
    grad = _graduation_for(store)
    lanes = grad.autonomous_lanes(tenant)
    if not lanes:
        return ":lock: All lanes are *supervised* — nothing runs without your approval yet."
    rows = []
    for e in lanes:
        limits = []
        if e.get("max_amount"):
            limits.append(f"≤ ${e['max_amount']}/run")
        if e.get("allowed_parties"):
            limits.append(f"{len(e['allowed_parties'])} allowed parties")
        if e.get("daily_cap") is not None:
            limits.append(f"≤ {e['daily_cap']}/day")
        suffix = f" — {', '.join(limits)}" if limits else " — no limits set"
        rows.append(f"• {e['lane']}{suffix}")
    return "*Autonomous lanes* (run unattended on approved work):\n" + "\n".join(rows)


def _render_operational_status(ops_control: OpsControl, *, store=None, status_file=None) -> str:
    """The owner's one-glance answer to 'what is Neyma doing right now?': service health + the TMS
    brake + how much is waiting on them."""
    parts: list[str] = []
    if status_file is not None:
        from .teammate_health import read_loop_health, render_health

        parts.append(render_health(read_loop_health(status_file)))
    brake = ops_control.status()
    if brake["tms_writes_paused"]:
        reason = f", {brake['reason']}" if brake.get("reason") else ""
        parts.append(f":lock: TMS writes are *PAUSED* (by {brake['paused_by']}{reason}).")
    else:
        parts.append(":white_check_mark: TMS writes are *ACTIVE*.")
    if store is not None:
        open_count = sum(1 for run in store.list_runs() if _state_of(run) in _OPEN_STATES)
        parts.append(f":memo: {open_count} item(s) waiting on you." if open_count else ":sparkles: Nothing waiting on you.")
    return "\n".join(parts)


def _state_of(run) -> str:
    return run.state.value if hasattr(run.state, "value") else str(run.state)


def _render_unresolved(store) -> str:
    rows = []
    for run in store.list_runs():
        state = _state_of(run)
        if state in _OPEN_STATES:
            tail = f" — {run.reason[:60]}" if getattr(run, "reason", None) else ""
            rows.append(f"• {run.load_id} — {state}{tail}")
    if not rows:
        return ":white_check_mark: No unresolved items."
    return "*Unresolved items:*\n" + "\n".join(rows[:25])


def _render_load_status(store, load_id: str) -> str:
    matches = [r for r in store.list_runs() if str(r.load_id).upper() == load_id.upper()]
    if not matches:
        return f"No run found for {load_id}."
    run = matches[-1]
    tail = f" — {run.reason}" if getattr(run, "reason", None) else ""
    return f"*{run.load_id}* — {_state_of(run)}{tail}"
