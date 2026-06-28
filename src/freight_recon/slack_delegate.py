"""Slack as Neyma's two-way delegate: the owner converses/commands, Neyma interprets and acts (gated).

This is the reactive half of the Slack Operating Surface (the proactive half — digests, exception
cards, approvals — already exists). The owner types natural language ("what's outstanding over 30
days?", "invoice today's delivered loads", "dispute the detention on LD-560004"); Neyma classifies the
intent and routes it.

Two boundaries are STRUCTURAL here, not optional (see docs/CODEX_HANDOFF.md):
1. **Authorization / injection boundary.** Commands are accepted ONLY from the authenticated owner in
   the authorized Slack channel. Untrusted content (emails, documents) never reaches this intake — it
   flows through the workflow pipeline as DATA, never as instructions. `authorize_command` is the gate.
2. **Brain proposes, gates dispose.** A read-only QUERY can be answered immediately. A consequential
   OPERATE command is never auto-executed off a chat message — it is planned and surfaced for human
   approval, then runs through the money gates. Typing "pay it" does not pay anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Callable

from freight_recon.screen_discovery import _parse_llm_json  # hardened JSON extraction (reused)

Completer = Callable[[str], str]


class CommandKind(str, Enum):
    QUERY = "QUERY"        # read-only ("what's outstanding?", "what needs review?") -> answer now
    OPERATE = "OPERATE"    # consequential ("invoice today's loads", "dispute X") -> plan + approval
    CONTROL = "CONTROL"    # runtime control ("pause tms writes", "status")
    UNKNOWN = "UNKNOWN"    # unclear -> ask for clarification, never guess


@dataclass
class CommandIntent:
    kind: CommandKind
    summary: str = ""
    params: dict = field(default_factory=dict)


@dataclass
class DelegateResponse:
    text: str
    authorized: bool
    kind: CommandKind | None = None
    requires_approval: bool = False


def authorize_command(user_id: str | None, channel_id: str | None, *, allowed_users, allowed_channel) -> tuple[bool, str]:
    """Only the verified owner/controller in the authorized channel may command Neyma.

    This is the injection boundary: if a command did not arrive through this authenticated path it is
    refused, so content the agent merely *reads* (email/docs) can never become a command it *obeys*.
    """
    allowed = {u for u in (allowed_users or ()) if u}
    if allowed_channel and channel_id != allowed_channel:
        return False, "command came from a non-authorized channel"
    if allowed and user_id not in allowed:
        return False, "command came from a non-authorized user"
    if not allowed and not allowed_channel:
        return False, "no authorized users or channel configured; refusing all commands fail-closed"
    return True, "authorized"


def interpret_command(text: str, *, complete: Completer) -> CommandIntent:
    """Classify a natural-language owner command into a typed intent (injectable LLM)."""
    prompt = (
        "You are the command interpreter for a freight back-office assistant. Classify the owner's "
        "message into one of: QUERY (read-only question about data/status), OPERATE (an action that "
        "changes a system or money: invoicing, paying, disputing, creating records), CONTROL (runtime "
        "control like pause/resume/status), or UNKNOWN (unclear).\n\n"
        f"Message: {text!r}\n\n"
        'Respond ONLY with JSON: {"kind": "QUERY|OPERATE|CONTROL|UNKNOWN", "summary": "<short>", '
        '"params": {}}'
    )
    try:
        parsed = _parse_llm_json(complete(prompt))
    except ValueError:
        return CommandIntent(kind=CommandKind.UNKNOWN, summary="could not parse intent")
    raw = parsed.get("kind") if isinstance(parsed, dict) else None
    kind = CommandKind(raw) if raw in CommandKind._value2member_map_ else CommandKind.UNKNOWN
    return CommandIntent(
        kind=kind,
        summary=str(parsed.get("summary", "")) if isinstance(parsed, dict) else "",
        params=parsed.get("params", {}) if isinstance(parsed, dict) and isinstance(parsed.get("params"), dict) else {},
    )


def handle_owner_command(
    text: str,
    *,
    user_id: str | None,
    channel_id: str | None,
    allowed_users=None,
    allowed_channel: str | None = None,
    interpret: Callable[[str], CommandIntent],
    on_query: Callable[[CommandIntent], str],
    on_operate: Callable[[CommandIntent], str],
    on_control: Callable[[CommandIntent], str],
) -> DelegateResponse:
    """Authorize -> interpret -> route. Consequential OPERATE never auto-executes; it returns a proposal
    that the caller surfaces for approval (requires_approval=True)."""
    ok, reason = authorize_command(user_id, channel_id, allowed_users=allowed_users, allowed_channel=allowed_channel)
    if not ok:
        return DelegateResponse(text=f"Not authorized: {reason}.", authorized=False)

    intent = interpret(text)
    if intent.kind == CommandKind.QUERY:
        return DelegateResponse(text=on_query(intent), authorized=True, kind=CommandKind.QUERY)
    if intent.kind == CommandKind.CONTROL:
        return DelegateResponse(text=on_control(intent), authorized=True, kind=CommandKind.CONTROL)
    if intent.kind == CommandKind.OPERATE:
        # Plan/propose only — the actual consequential action runs through the gates + approval.
        return DelegateResponse(text=on_operate(intent), authorized=True, kind=CommandKind.OPERATE,
                                requires_approval=True)
    return DelegateResponse(
        text="I didn't understand that. Try a question (e.g. \"what's outstanding over 30 days?\") or an "
             "action (e.g. \"invoice today's delivered loads\").",
        authorized=True, kind=CommandKind.UNKNOWN,
    )
