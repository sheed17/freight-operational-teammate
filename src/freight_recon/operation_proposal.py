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

import re

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


# A load is ready to BILL only once it is delivered (or otherwise marked billable) and not yet
# invoiced. We require a POSITIVE billable signal — never "anything that isn't invoiced" — so an
# in-transit / dispatched load is never proposed for billing. Fail-closed: no status => not proposed.
_BILLABLE_STATUS_HINTS = ("delivered", "completed", "ready to bill", "ready to invoice", "to invoice", "uninvoiced")
# Currency-shaped cell: a '$' amount, or a bare decimal with 2 places / comma-thousands. Dates like
# 07/14/2026 use '/', so they never match the '.dd' or '$' shapes — they won't be mistaken for money.
_MONEY_CELL = re.compile(r"\$\s*\d|\d[\d,]*\.\d{2}\b")


def _is_billable_status(status: str) -> bool:
    s = (status or "").lower()
    if not s or "invoiced" in s:  # empty (unknown) or already billed -> not billable
        return False
    return any(h in s for h in _BILLABLE_STATUS_HINTS)


def _row_amount(cells: list, i_total: int | None) -> str | None:
    """The load Total, robust to column drift. Some TMS loads tables render the amount one column off
    from the 'Total' header (the header cell holds the row's action links instead). So we don't trust
    the header position blindly: we find the currency-shaped cell nearest the Total column and use it.
    """
    money_idx = [i for i, c in enumerate(cells) if _MONEY_CELL.search(str(c))]
    if not money_idx:
        return None
    anchor = i_total if i_total is not None else len(cells)
    best = min(money_idx, key=lambda i: (abs(i - anchor), -i))  # nearest to Total; tie -> rightmost
    return str(cells[best]).replace("$", "").replace(",", "").strip()


def ready_to_bill_from_loads_table(observation: dict | None) -> list[dict]:
    """Extract ready-to-bill loads from a TMS 'loads' table observation — the REAL-TMS trigger source.

    Finds the loads table by its Customer + Total (and Load/Status) columns, maps cells by header, and
    returns ``[{load_ref, customer, amount}]`` for rows whose status is NOT already 'invoiced'. The Total
    column supplies the deterministic bill amount (in TruckingOffice the invoice amount derives from the
    load = its Total), so no amount is ever guessed. TMS-shaped but header-driven, not position-hardcoded.
    """
    out: list[dict] = []
    seen: set = set()
    for table in (observation or {}).get("tables") or []:
        headers = [str(h).strip().lower() for h in (table.get("headers") or [])]
        if not headers:
            continue

        def col(opts, hs=headers):
            for i, h in enumerate(hs):
                if any(o in h for o in opts):
                    return i
            return None

        i_load, i_status = col(["load #", "load#", "load"]), col(["status"])
        i_cust, i_total = col(["customer"]), col(["total", "amount"])
        i_doc = col(["pod", "proof of delivery"])  # POD evidence; BOL/docs alone are not enough to bill
        if i_load is None or i_cust is None or i_total is None:
            continue  # not a loads table
        need = max(i for i in (i_load, i_status, i_cust, i_total) if i is not None)
        for row in table.get("rows") or []:
            cells = row.get("cells") or []
            if len(cells) <= need:
                continue
            load_ref = str(cells[i_load]).strip()
            if not load_ref or load_ref.lower() in ("load #", "load", "load#"):  # header echoed as a row
                continue
            status = str(cells[i_status]).strip() if i_status is not None else ""
            if not _is_billable_status(status):  # only delivered-and-not-invoiced loads are ready to bill
                continue
            amount = _row_amount(cells, i_total)  # currency cell nearest Total (robust to column drift)
            if not amount or not any(c.isdigit() for c in amount):
                continue
            # TMS list views truncate long names with a trailing ellipsis ("Echo Global L..."). Strip it
            # so the bill-to step gets a clean search prefix (a contains-match still finds the customer);
            # the invoice is anchored to the load anyway, so the TMS auto-carries the exact bill-to.
            customer = re.sub(r"[.…]+$", "", str(cells[i_cust]).strip()).strip()
            key = (load_ref, customer)
            if key in seen:
                continue
            seen.add(key)
            # POD/delivery-document present? Tri-state: True/False when the list shows a paperwork column,
            # None when it doesn't (can't tell from the list — a POD gate would need the load detail page).
            has_pod = None
            if i_doc is not None and len(cells) > i_doc:
                doc_cell = str(cells[i_doc]).strip()
                # Some TMS tables drift: the money cell can render under a BOL/POD-looking header. A
                # currency value is not proof of paperwork, so leave it unknown and fail closed when a
                # POD gate is required.
                has_pod = None if _MONEY_CELL.search(doc_cell) else bool(doc_cell)
            out.append({"load_ref": load_ref, "customer": customer, "amount": amount, "has_pod": has_pod})
    return out


def loads_missing_pod(observation: dict | None) -> list[dict]:
    """Delivered-but-not-invoiced loads whose delivery paperwork (POD/BOL) is NOT attached — the ones a
    POD-gated biller must NOT invoice yet. Enforces the owner SOP 'always attach the POD before billing a
    customer': these become an exception ('attach the POD first'), never a money button. Only loads the
    list can PROVE lack paperwork (has_pod is False) count; unknown (no paperwork column) is not flagged."""
    return [r for r in ready_to_bill_from_loads_table(observation) if r.get("has_pod") is False]


def loads_unknown_pod(observation: dict | None) -> list[dict]:
    """Ready-to-bill candidates where the list view cannot prove POD status. These should not get AR
    money buttons when POD is required; the operator needs a document-tab/detail-page check first."""
    return [r for r in ready_to_bill_from_loads_table(observation) if r.get("has_pod") is None]


# When the loads LIST can't show POD (has_pod is None), the detail page's document area resolves it.
# On TruckingOffice, docs live in FileSafe at /loads/<id>/attachments; the attach categories are Rate
# Con and (signed) BOL — there is no native "POD" type, and a signed BOL at delivery IS the proof of
# delivery. So delivery proof = a POD or a BOL attachment; a rate con alone is the booking agreement,
# NOT proof the freight was delivered, so it never satisfies the billing gate.
_POD_DOC_HINTS = ("pod", "proof of delivery", "proof-of-delivery", "delivery receipt", "signed", "bol",
                  "bill of lading", "delivered")
_RATE_CON_HINTS = ("rate con", "rate confirmation", "ratecon", "rate-con")


def _is_rate_con(label: str) -> bool:
    return any(h in label for h in _RATE_CON_HINTS)


def pod_present_in_attachments(doc_labels) -> bool:
    """Pure decision: does this load's attachment set include delivery proof (a POD or signed BOL)?
    Separated from browser I/O so the rule is unit-tested. A rate con alone does NOT count — it's the
    booking agreement, not proof of delivery. Empty attachment set => no proof => False."""
    for label in doc_labels or []:
        text = " ".join(str(label).split()).lower()
        if not text or _is_rate_con(text):
            continue  # a rate con is not delivery proof
        if any(hint in text for hint in _POD_DOC_HINTS):
            return True
    return False


def has_pod_from_detail(doc_labels, *, page_readable: bool = True) -> bool | None:
    """Resolve the tri-state POD signal from a load's detail/attachments page. ``page_readable`` is
    False when the detail page couldn't be read (nav failed / not the right page) -> stay unknown (None)
    and fail closed under a POD gate, rather than fabricate a False that would greenlight billing."""
    if not page_readable:
        return None
    return pod_present_in_attachments(doc_labels)


def proposals_from_tms_loads(observation: dict | None, *, signer: DeliverySigner, channel_id: str,
                             require_pod: bool = False) -> list[dict]:
    """The AR trigger, end to end from the REAL TMS: read ready-to-bill loads off a loads-table
    observation and build a raise_invoice Approve button for each, at that load's Total. This is what
    makes the proposed load_ref match a WRITABLE TMS record (vs the synthetic corpus).

    ``require_pod`` enforces the owner SOP 'always attach the POD before billing': a delivered load whose
    delivery paperwork isn't attached gets no money button (surface it via :func:`loads_missing_pod`)."""
    from types import SimpleNamespace

    ready = ready_to_bill_from_loads_table(observation)
    if require_pod:
        ready = [r for r in ready if r.get("has_pod")]  # only loads with delivery paperwork attached
    if not ready:
        return []
    loads = [SimpleNamespace(load_id=r["load_ref"], customer=r["customer"], delivery_date="ready") for r in ready]
    amounts = {r["load_ref"]: r["amount"] for r in ready}
    return proposals_for_ready_to_bill(
        loads, signer=signer, channel_id=channel_id, amount_for_load=lambda load: amounts.get(load.load_id),
    )


def _delivered_and_billable(load) -> bool:
    """Default 'ready to bill' signal: the load has been delivered (has a delivery date). Callers that
    know the TMS/workflow state (e.g. POD present, not yet invoiced) should pass a stricter predicate."""
    return bool(getattr(load, "delivery_date", None))


def proposals_for_ready_to_bill(
    loads,
    *,
    signer: DeliverySigner,
    channel_id: str,
    amount_for_load,
    is_ready=None,
) -> list[dict]:
    """Auto-emit a 'raise invoice' Approve button for each DELIVERED, ready-to-bill load — the AR mirror
    of :func:`proposals_for_clean_matches`. This is the cash-flow half: when a load is delivered (POD in,
    not yet invoiced), Neyma proposes invoicing the customer unattended-pending-tap.

    Conservative, same as the AP side: ``amount_for_load`` supplies the deterministic agreed amount (the
    customer rate); None -> no button (never bind a money button to an amount we can't stand behind).
    ``is_ready`` decides which loads are billable (default: delivered) — the caller can pass the real
    TMS/workflow signal (delivered + POD present + no existing invoice).
    """
    ready = is_ready or _delivered_and_billable
    proposals: list[dict] = []
    for load in loads:
        if not ready(load):
            continue
        amount = amount_for_load(load)
        if amount in (None, ""):
            continue
        customer = getattr(load, "customer", None) or "the customer"
        load_ref = getattr(load, "load_id", None)
        intent = CommandIntent(
            kind=CommandKind.OPERATE,
            summary=f"Invoice {customer}" + (f" for {load_ref}" if load_ref else ""),
            params={"lane": "raise_invoice", "customer": customer, "load_ref": load_ref},
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
