"""In-thread reactivity: an escalation becomes a conversation the owner can resolve by replying.

When an operation escalates ("🤚 I need you — ..."), it is fully recorded in the audit log with its
thread, intent, and approved amount. If the owner then replies IN THAT THREAD, this turns the reply
into a resume: the reply is added as operator guidance, the operation re-runs (money-fenced + gated),
and a fresh receipt goes back in-thread. So the login/missing-field escalation you hit becomes: you
reply "I'm logged in, proceed" (or "it's Acme Corp") and the agent continues.

Structural safety (unchanged):
- Only the AUTHENTICATED owner in the AUTHORIZED channel can resume — a thread reply is a *trusted*
  command, exactly like a slash command. Untrusted email/document content still never commands anything.
- The reply is guidance, NOT money: it can unblock navigation or supply a name, but the amount stays the
  human-approved figure the original operation carried; the money fence and consequential gate still hold.
"""

from __future__ import annotations

from .slack_delegate import CommandIntent, CommandKind
from .workflow import normalize_money_amount

APPLIED_EVENT = "slack_operation_applied"


RESUMABLE_STATUSES = ("ESCALATED", "FAILED", "PREPARED")


def find_resumable_operation(store, thread_ts: str | None, *, action_id: str | None = None) -> dict | None:
    """The most recent unfinished operation in this Slack thread (ESCALATED or FAILED), or None.

    Reads the same audit log the callback writes — the run recorded its thread, summary, params, and
    approved amount, which is everything needed to resume it. FAILED is resumable too so the owner can
    reply "try again" (e.g. after a fix) and re-run; a DONE run is not resumable.
    """
    if not thread_ts:
        return None
    found: dict | None = None
    found_action_ids: set[str] = set()
    for event in store.security_events():
        if event["event_type"] != APPLIED_EVENT:
            continue
        payload = event.get("payload") or {}
        if payload.get("thread_ts") == thread_ts and payload.get("status") in RESUMABLE_STATUSES:
            payload_action_id = payload.get("action_id")
            if action_id is not None and payload_action_id != action_id:
                continue
            if _payload_already_committed(payload):
                continue
            verified_amount = store.operation_token_amount(payload.get("token_fingerprint"))
            if verified_amount and verified_amount == normalize_money_amount(str(payload.get("approved_amount"))):
                if payload_action_id:
                    found_action_ids.add(str(payload_action_id))
                found = {**payload, "approved_amount": verified_amount}  # keep scanning; newest verified match wins
    if action_id is None and len(found_action_ids) > 1:
        return None
    return found


def intent_from_resumable(payload: dict, reply_text: str) -> CommandIntent:
    """Rebuild the operation's intent, adding the owner's reply as guidance (never as an amount).

    A reply is the owner actively directing the run, so it authorizes COMMIT (``commit``): resuming a
    staged/escalated op from a thread reply completes it rather than re-staging.
    """
    params = dict(payload.get("params") or {})
    params["operator_guidance"] = reply_text
    if _payload_already_committed(payload):
        params["verify_only"] = True
        params["commit"] = False
    else:
        params["commit"] = True
    if payload.get("approved_amount"):
        params.setdefault("approved_amount", payload["approved_amount"])
    return CommandIntent(kind=CommandKind.OPERATE, summary=str(payload.get("summary", "")), params=params)


def _payload_already_committed(payload: dict) -> bool:
    if payload.get("committed") is True:
        return True
    for step in payload.get("steps") or []:
        if isinstance(step, dict) and step.get("committed") is True:
            return True
    return False


def handle_thread_reply(
    store,
    *,
    thread_ts: str | None,
    reply_text: str,
    authorized: bool,
    run_operation,
):
    """Resume an escalated operation from an owner's thread reply.

    ``run_operation(intent) -> result`` executes the (money-fenced, gated) operation. Returns the result,
    or ``None`` when there is nothing to resume / the reply isn't authorized (so the caller stays quiet
    rather than acting). Authorization is decided by the caller (owner + channel) and passed in.
    """
    if not authorized or not (reply_text or "").strip():
        return None
    resumable = find_resumable_operation(store, thread_ts)
    if resumable is None:
        return None  # a thread reply not tied to any escalated operation — ignore
    intent = intent_from_resumable(resumable, reply_text)
    return run_operation(intent)
