"""Natural-language routing for the Slack delegate — so the owner talks, not memorizes commands.

An owner won't type `show unresolved` or `roi`; they'll ask "what's still unpaid?" or "how'd we do this
week?" or "invoice the Northbound load". When the deterministic command handler doesn't recognize a
message, this maps it — with a cheap model — to ONE known action:

- a READ (roi / unresolved / status / audit / know) -> re-run that command and answer;
- an OPERATE (invoicing / paying) -> the existing gated proposal path (money still fenced + approved);
- unclear -> fall back to the help.

The safety boundary is unchanged: this only runs for an already-authenticated owner in the authorized
channel, it can only map to actions that already exist, and every consequential action still goes
through the money gates. The model chooses WHICH read/operate — never an amount, never a commit.
"""

from __future__ import annotations

from freight_recon.screen_discovery import _parse_llm_json

READ_COMMANDS = ("roi", "show unresolved", "status", "audit", "know")


def interpret_slash(text: str, *, complete) -> dict:
    """Route an owner's message. Returns {"read": <command>} or {"operate": <request>} or {} (unclear)."""
    text = (text or "").strip()
    if not text:
        return {}
    try:
        parsed = _parse_llm_json(complete(_route_prompt(text)))
    except Exception:  # noqa: BLE001 - a routing miss just falls back to help
        return {}
    if not isinstance(parsed, dict):
        return {}
    action = str(parsed.get("action", "")).lower()
    if action == "read":
        cmd = str(parsed.get("read", "")).strip().lower()
        if cmd == "unresolved":
            cmd = "show unresolved"
        if cmd in READ_COMMANDS:
            return {"read": cmd}
        return {}
    if action == "operate":
        return {"operate": str(parsed.get("request") or text)}
    return {}


def _route_prompt(text: str) -> str:
    return (
        "You route a freight back-office owner's Slack message to ONE action. Decide the intent:\n"
        "READ (answer a question, changes nothing):\n"
        "  - roi: money recovered/invoiced, savings, 'how did we do', 'how much did we make/save'\n"
        "  - unresolved: what's outstanding/open/unpaid/waiting/needs attention/aging\n"
        "  - status: what is Neyma doing right now, is it running, system health\n"
        "  - audit: what did Neyma do, recent activity, show your work\n"
        "  - know: what have you learned about a carrier/customer/system\n"
        "OPERATE (do something that changes money or records): invoicing, billing, paying, recording a "
        "payable/invoice for a load or party.\n\n"
        f"MESSAGE: {text!r}\n\n"
        'Reply ONLY JSON: for a read {"action":"read","read":"roi|unresolved|status|audit|know"}; for an '
        'operation {"action":"operate","request":"<the request in plain words>"}; if neither/unclear '
        '{"action":"unknown"}.'
    )
