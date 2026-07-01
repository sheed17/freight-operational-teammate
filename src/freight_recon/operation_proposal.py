"""The bridge that closes the loop: an inbound proposal -> a Slack Approve button -> the live browser.

This is the last wire of "email arrives -> Neyma asks in Slack -> you tap -> the agent executes". The
Inbox Brain decides an inbound item is actionable on a bounded lane (e.g. READY_TO_BILL -> raise_invoice);
this builds the Slack message that proposes it, carrying a **signed operation-approval token** as the
button value. When the owner taps it, the action callback verifies the signature + authorization, then
runs the OperationRouter (the money-fenced, gated live agent). Nothing executes from the email itself —
only the owner's signed tap.

Two safety properties are inherited, not re-implemented:
- the amount on the button is one the caller supplies from a deterministic source (the reconciliation /
  rate con), never a model-chosen number — the tap is the human approving THAT figure;
- the token is single-use, channel/thread-bound, and TTL-limited (``build_slack_operation_approval_value``).

Pure: it returns the Slack message dict; posting it is the caller's job (inject a poster).
"""

from __future__ import annotations

from .action_callback import build_slack_operation_approval_value
from .delivery import DeliverySigner
from .inbox_brain import InboxAssessment
from .slack_delegate import CommandIntent, CommandKind

# Slack block action_id for the approve button. The discriminator the callback actually keys on is the
# signed token in the button's VALUE, not this id, so a constant is fine.
APPROVE_ACTION_ID = "approve_operation"


def build_operation_proposal_message(
    intent: CommandIntent,
    signer: DeliverySigner,
    *,
    approved_amount: str | None,
    channel_id: str,
    thread_ts: str | None = None,
    action_id: str | None = None,
    headline: str | None = None,
) -> dict:
    """Build a Slack message proposing a bounded operation, with a signed Approve button.

    The button's value is a signed operation-approval token bound to this channel/thread and amount; the
    callback re-verifies and runs the OperationRouter only on the owner's authenticated tap.
    """
    if intent.kind != CommandKind.OPERATE:
        raise ValueError("an operation proposal requires an OPERATE intent")
    value = build_slack_operation_approval_value(
        intent,
        signer,
        approved_amount=approved_amount,
        expected_channel_id=channel_id,
        expected_thread_ts=thread_ts,
        action_id=action_id,
    )
    text = headline or (intent.summary or "Ready to run this operation")
    amount_line = f"\nAmount to approve: *${approved_amount}*" if approved_amount else ""
    return {
        "channel": channel_id,
        "text": text,  # fallback text for notifications/clients without block rendering
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": f"{text}{amount_line}"}},
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "action_id": APPROVE_ACTION_ID,
                        "style": "primary",
                        "text": {"type": "plain_text", "text": "Approve & run"},
                        "value": value,
                    }
                ],
            },
        ],
    }


def proposal_from_assessment(
    assessment: InboxAssessment,
    signer: DeliverySigner,
    *,
    channel_id: str,
    approved_amount: str | None,
    params: dict | None = None,
    thread_ts: str | None = None,
    action_id: str | None = None,
) -> dict | None:
    """Turn an actionable Inbox Brain assessment into a Slack operation-proposal message.

    Returns ``None`` when the assessment has no bounded lane to run (e.g. MISSING_BACKUP -> chase a doc,
    DISPUTE_REPLY -> human path): those surface as plain FYIs elsewhere, not as an Approve-and-run button.
    A money lane with no ``approved_amount`` also returns ``None`` — we never post a run button without a
    human-approvable figure on it.
    """
    if not assessment.actionable or not assessment.suggested_lane:
        return None
    if approved_amount in (None, ""):
        return None
    merged = dict(params or {})
    merged.setdefault("lane", assessment.suggested_lane)
    if assessment.load_ref:
        merged.setdefault("load_ref", assessment.load_ref)
    intent = CommandIntent(kind=CommandKind.OPERATE, summary=assessment.suggested_action, params=merged)
    return build_operation_proposal_message(
        intent, signer, approved_amount=approved_amount, channel_id=channel_id,
        thread_ts=thread_ts, action_id=action_id, headline=assessment.suggested_action,
    )


def proposals_for_clean_matches(
    packet_results,
    loads_by_id: dict,
    *,
    signer: DeliverySigner,
    channel_id: str,
    amount_for_load,
) -> list[dict]:
    """Auto-emit a 'record payable' Approve button for each CLEANLY MATCHED carrier invoice.

    This is the hands-off half: when a carrier invoice reconciles clean (outcome MATCHED), Neyma can
    propose entering the payable unattended-pending-tap. Fail-safe and conservative:
    - ONLY clean matches — a variance/overbilling never gets a run button (it goes to human review);
    - the amount comes from ``amount_for_load`` (the deterministic rate-con total); if it returns None
      no button is posted (we never bind a money button to an amount we can't stand behind).
    """
    proposals: list[dict] = []
    for pr in packet_results:
        if getattr(pr, "outcome", None) != "MATCHED":
            continue
        load = loads_by_id.get(getattr(pr, "load_id", None))
        if load is None:
            continue
        amount = amount_for_load(load)
        if amount in (None, ""):
            continue
        carrier = getattr(load, "carrier", None) or "the carrier"
        load_ref = getattr(load, "load_id", None)
        intent = CommandIntent(
            kind=CommandKind.OPERATE,
            summary=f"Record the agreed payable to {carrier}" + (f" for {load_ref}" if load_ref else ""),
            params={"lane": "record_payable", "carrier": carrier, "load_ref": load_ref},
        )
        message = build_operation_proposal_message(
            intent, signer, approved_amount=str(amount), channel_id=channel_id,
        )
        message["load_ref"] = load_ref  # for dedup/audit by the caller (ignored when posting to Slack)
        proposals.append(message)
    return proposals


def post_operation_proposal(message: dict, *, poster) -> "object":
    """Post a built proposal message (with its Approve button) to Slack via an injected poster.

    ``poster`` is anything with ``post_message(channel, payload)`` (e.g. ``SlackApiPoster``); the button
    survives because it travels in the message's ``blocks``. Returns the poster's result.
    """
    return poster.post_message(
        channel=message["channel"],
        payload={"text": message["text"], "blocks": message["blocks"]},
    )
