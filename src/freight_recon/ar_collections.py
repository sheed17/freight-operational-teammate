"""AR collections: read the TMS /invoices list, find aged UNPAID receivables, surface them for action.

The other half of cash flow. Invoicing-on-delivery is proven; this is "get paid, all of it": an aging
read that fails CLOSED (an unparseable or paid row is skipped, never dunned by mistake) feeding a digest
the owner acts on. Outward-facing dunning is draft-then-approve — Neyma never emails a customer unasked.

Parsed by CONTENT, not header position: the live /invoices list drifts (an empty 'Custom Invoice Number'
column shifts cells; 'Paid On' is blank for unpaid rows), exactly like /loads — so trusting positions
would misread the balance. We find the money cells and the date cells wherever they land.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation

_MONEY = re.compile(r"\$?\s*\d[\d,]*\.\d{2}\b")            # $2,400.00 — not a date (dates use '/')
_DATE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")     # 07/05/2026
_ACTION_HINTS = ("view", "enter payment", "edit", "copy", "delete", "email", "print", "pay")


def _money(text: str):
    try:
        return Decimal(re.sub(r"[^\d.]", "", text))
    except (InvalidOperation, ValueError):
        return None


def _as_date(text: str):
    m = _DATE.search(text or "")
    if not m:
        return None
    mm, dd, yy = (int(x) for x in m.groups())
    try:
        return date(yy, mm, dd)
    except ValueError:
        return None


def receivables_from_invoices_table(observation: dict | None) -> list[dict]:
    """Unpaid receivables from an /invoices-table observation: ``[{invoice, customer, total,
    balance_due, invoiced_on}]`` for rows with a positive Balance Due. Fails closed — a row we can't
    read (missing money/date) is skipped, never guessed."""
    out: list[dict] = []
    for table in (observation or {}).get("tables") or []:
        headers = [str(h).strip().lower() for h in (table.get("headers") or [])]
        if not any("balance" in h for h in headers):
            continue  # not the invoices table
        for row in table.get("rows") or []:
            cells = [str(c).strip() for c in (row.get("cells") or [])]
            if not cells or cells[0].lower() == "number":
                continue  # header echoed as a row
            number = cells[0]
            if not any(ch.isdigit() for ch in number):
                continue
            monies = [m for m in (_money(c) for c in cells if _MONEY.search(c)) if m is not None]
            dates = [d for d in (_as_date(c) for c in cells) if d is not None]
            if len(monies) < 2 or not dates:
                continue  # need Total + Balance Due and an Invoiced On
            total, balance = monies[0], monies[-1]   # Total is first money cell, Balance Due the last
            if balance <= 0:
                continue  # paid in full -> not a receivable to chase
            customer = ""
            for c in cells[1:]:
                cl = c.lower()
                if _MONEY.search(c) or _as_date(c) or any(h in cl for h in _ACTION_HINTS):
                    continue
                if c:
                    customer = c
                    break
            out.append({
                "invoice": number, "customer": customer,
                "total": f"{total:.2f}", "balance_due": f"{balance:.2f}",
                "invoiced_on": dates[0].isoformat(),
            })
    return out


def aged_unpaid(receivables, *, as_of: date, min_days: int = 30) -> list[dict]:
    """The receivables aged at least ``min_days`` as of ``as_of``, each tagged with ``days_overdue``,
    worst first. ``as_of`` is injected so aging is deterministic and testable (never a hidden clock)."""
    aged = []
    for r in receivables:
        raw = r.get("invoiced_on", "")
        try:
            d = date.fromisoformat(raw)               # receivables store ISO (YYYY-MM-DD)
        except ValueError:
            d = _as_date(raw)                          # tolerate a raw MM/DD/YYYY too
        if d is None:
            continue
        days = (as_of - d).days
        if days >= min_days:
            aged.append({**r, "days_overdue": days})
    return sorted(aged, key=lambda r: r["days_overdue"], reverse=True)


def render_aging_digest(aged) -> str:
    """The owner-facing aged-AR digest. Proposes the next step (draft reminders) — never auto-sends."""
    if not aged:
        return ":white_check_mark: No aged receivables — everything billed is within terms."
    total = sum(Decimal(r["balance_due"]) for r in aged)
    plural = "s" if len(aged) != 1 else ""
    lines = [f":moneybag: *{len(aged)} unpaid invoice{plural} past due* — ${total:,.2f} outstanding"]
    for r in aged[:10]:
        lines.append(
            f"• #{r['invoice']} {r['customer']} — ${r['balance_due']} · {r['days_overdue']}d overdue"
        )
    if len(aged) > 10:
        lines.append(f"…and {len(aged) - 10} more.")
    lines.append("_Reply *draft reminders* and I'll prepare dunning notes for your approval._")
    return "\n".join(lines)
