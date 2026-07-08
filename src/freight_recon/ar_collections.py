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


def aged_unpaid(receivables, *, as_of: date, min_days: int = 0, terms_days: int | None = None) -> list[dict]:
    """Unpaid receivables whose invoice is at least ``min_days`` old as of ``as_of``, each tagged with
    ``days_outstanding`` (days since invoiced — NOT a claim of lateness), worst first. If ``terms_days``
    is given (e.g. Net-30), a receivable is also tagged ``past_due=True`` only when it is genuinely
    beyond terms; without terms we make NO past-due claim. ``as_of`` is injected so it's deterministic."""
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
            past_due = terms_days is not None and days > terms_days
            aged.append({**r, "days_outstanding": days, "past_due": past_due})
    return sorted(aged, key=lambda r: r["days_outstanding"], reverse=True)


def receivables_by_customer(aged) -> list[dict]:
    """Group outstanding receivables by customer, biggest debtor first — the chief-of-staff answer to
    "who owes us the most?". Each entry: {customer, total, count, oldest_days, past_due_total}. Pure and
    deterministic (built from an already-aged list, so terms/past-due tagging carries through)."""
    groups: dict[str, dict] = {}
    for r in aged:
        key = r.get("customer") or "(unknown customer)"
        g = groups.setdefault(key, {"customer": key, "total": Decimal("0"), "count": 0,
                                    "oldest_days": 0, "past_due_total": Decimal("0")})
        g["total"] += Decimal(r["balance_due"])
        g["count"] += 1
        g["oldest_days"] = max(g["oldest_days"], int(r.get("days_outstanding", 0)))
        if r.get("past_due"):
            g["past_due_total"] += Decimal(r["balance_due"])
    out = sorted(groups.values(), key=lambda g: g["total"], reverse=True)
    return [{**g, "total": f"{g['total']:.2f}", "past_due_total": f"{g['past_due_total']:.2f}"} for g in out]


def render_top_debtors(aged, *, limit: int = 5) -> str:
    """Owner-facing "who owes us the most": customers ranked by outstanding balance. Only claims
    "past due" for amounts genuinely beyond configured terms; otherwise says "within terms"."""
    groups = receivables_by_customer(aged)
    if not groups:
        return ":information_source: No outstanding receivables — every invoice is paid in full."
    lines = [":trophy: *Who owes us the most:*"]
    for g in groups[:limit]:
        n = g["count"]
        detail = f"{n} invoice{'s' if n != 1 else ''}, oldest {g['oldest_days']}d"
        pd = Decimal(g["past_due_total"])
        status = f" — ${pd:,.2f} past due" if pd > 0 else " — within terms" if Decimal(g["total"]) > 0 else ""
        lines.append(f"• *{g['customer']}* — ${Decimal(g['total']):,.2f} ({detail}){status}")
    if len(groups) > limit:
        rest = sum(Decimal(g["total"]) for g in groups[limit:])
        lines.append(f"…and {len(groups) - limit} more customers (${rest:,.2f}).")
    return "\n".join(lines)


def render_aging_digest(aged) -> str:
    """The owner-facing outstanding-AR digest. Uses NEUTRAL language ("outstanding / N days since
    invoiced") — it only says "past due" for invoices tagged genuinely beyond terms, never for merely
    recent ones. Proposes the next step (draft reminders) but never auto-sends."""
    if not aged:
        return ":information_source: No outstanding receivables — every invoice is paid in full."
    total = sum(Decimal(r["balance_due"]) for r in aged)
    past_due = [r for r in aged if r.get("past_due")]
    plural = "s" if len(aged) != 1 else ""
    head = f":moneybag: *{len(aged)} unpaid invoice{plural} outstanding* — ${total:,.2f}"
    if past_due:
        pd_total = sum(Decimal(r["balance_due"]) for r in past_due)
        head += f"  ·  {len(past_due)} past due (${pd_total:,.2f})"
    lines = [head]
    for r in aged[:10]:
        flag = " ⚠️ past due" if r.get("past_due") else ""
        lines.append(
            f"• #{r['invoice']} {r['customer']} — ${r['balance_due']} · {r['days_outstanding']}d since invoiced{flag}"
        )
    if len(aged) > 10:
        lines.append(f"…and {len(aged) - 10} more.")
    lines.append("_Reply *draft reminders* and I'll prepare dunning notes for your approval._")
    return "\n".join(lines)
