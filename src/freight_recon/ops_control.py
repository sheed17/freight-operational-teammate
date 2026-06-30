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
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(state, indent=2), encoding="utf-8")

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
    "Commands: `status` (what is Neyma doing) | `roi` (what Neyma recovered/did) | "
    "`audit` (show your work) | `autonomy` · `graduate <lane>` · `supervise <lane>` | "
    "`pause tms writes` | `resume tms writes` | `show unresolved` | `status <LOAD-ID>`"
)


def handle_ops_command(text: str, *, actor: str, ops_control: OpsControl, store=None, status_file=None) -> str:
    """Parse one lightweight owner command from Slack into an action + reply. Channel-neutral."""
    raw = text.strip()
    cmd = " ".join(raw.lower().split())
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
    if cmd in ("autonomy", "show autonomy", "graduations", "what is autonomous") and store is not None:
        return _render_autonomy(store)
    if store is not None and (raw_first := cmd.split(None, 1)[0]) in (
        "graduate", "autonomous", "supervise", "restrict"
    ) and len(raw.split(None, 1)) == 2:
        return _handle_graduation(store, raw_first, raw.split(None, 1)[1].strip(), actor=actor)
    if cmd in ("show unresolved", "unresolved", "show open") and store is not None:
        return _render_unresolved(store)
    if cmd.startswith("status ") and store is not None:
        return _render_load_status(store, raw.split(None, 1)[1].strip())
    return _HELP


def _graduation_for(store):
    from .lane_graduation import LaneGraduation

    return LaneGraduation(Path(store.db_path).parent / "lane_graduation.json")


def _known_lane_names() -> set[str]:
    from .operation_router import freight_lanes

    return {lane.name for lane in freight_lanes()}


def _handle_graduation(store, verb: str, lane: str, *, actor: str, tenant: str = "default") -> str:
    """Flip a lane between supervised and autonomous from Slack. Unknown lanes are refused, not created."""
    if lane not in _known_lane_names():
        known = ", ".join(sorted(_known_lane_names()))
        return f"Unknown lane `{lane}`. Known lanes: {known}."
    grad = _graduation_for(store)
    if verb in ("graduate", "autonomous"):
        grad.graduate(tenant, lane, actor=actor, reason="graduated from Slack")
        return f":rocket: Lane *{lane}* is now *AUTONOMOUS* — I'll run approved work on it unattended."
    grad.restrict(tenant, lane, actor=actor, reason="restricted from Slack")
    return f":lock: Lane *{lane}* is back to *SUPERVISED* — it will ask for your approval before running."


def _render_autonomy(store, tenant: str = "default") -> str:
    lanes = _graduation_for(store).autonomous_lanes(tenant)
    if not lanes:
        return ":lock: All lanes are *supervised* — nothing runs without your approval yet."
    rows = "\n".join(f"• {e['lane']} (by {e.get('updated_by', '?')})" for e in lanes)
    return "*Autonomous lanes* (run unattended on approved work):\n" + rows


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
