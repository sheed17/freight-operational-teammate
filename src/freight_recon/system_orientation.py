"""System orientation: the agent's first day on the job — learn the TMS before doing money tasks.

A new back-office hire isn't handed a payable on minute one; they're walked around the system first —
shown where Orders, Customers, Finance, and invoicing live, and how the thing is laid out. Only then do
tasks feel easy. This gives our agents that same orientation: on first immersion in an unfamiliar TMS,
explore the main sections, understand what each is for, and write it down as SYSTEM knowledge — so the
very first real task starts from understanding, not from the deep end.

It's read-only reconnaissance (navigate + observe + summarize) — it never fills a form, never commits,
never touches money. The facts it learns feed the shared KnowledgeBase [[knowledge]] and are recalled
into every later task, so orientation happens once per system and pays off on every run after.
"""

from __future__ import annotations

# App chrome (account/AI/search/notifications) — not the operational sections a hire needs to learn.
_CHROME = {
    "ask ai", "enable ai power pack", "ai assistant", "ai power pack", "profile", "account", "logout",
    "log out", "sign out", "settings", "home", "help", "search", "notifications", "neyma", "menu",
    "toggle navigation", "skip to content",
}


def _is_operational(text: str) -> bool:
    t = " ".join((text or "").split()).strip().lower()
    return bool(t) and len(t) > 2 and not t.isdigit() and t not in _CHROME and "search" not in t


def orient_system(actuator, complete, *, sections_limit: int = 8, record_url: str | None = None) -> list[str]:
    """Walk the TMS's main OPERATIONAL navigation, learn what each section is for, and return reusable
    SYSTEM facts. When ``record_url`` is given, ALSO go a level deeper — open a real record and expand
    its action menus (an order's Billing/Transport/etc.) — which is where money actions like invoicing
    live. ``actuator`` drives the browser (observe/click); ``complete`` summarizes/identifies menus.
    Pure/injectable so it is unit-tested with fakes; read-only (no typing, no commits)."""
    facts: list[str] = []
    home = actuator.observe() or {}
    # Keep the operational sections (Orders/Customers/Finance/...), drop account/AI/search chrome + dupes.
    nav, seen_nav = [], set()
    for n in (home.get("nav") or []):
        if not (isinstance(n, dict) and _is_operational(n.get("text"))):
            continue
        key = n["text"].strip().lower()
        if key not in seen_nav:
            seen_nav.add(key)
            nav.append(n)
    sections = [n["text"] for n in nav][:sections_limit]
    if sections:
        facts.append("Main navigation sections: " + ", ".join(sections) + ".")
        facts.append("Navigation is click-driven (a SPA); open a record by clicking its row/reference, "
                     "not by guessing a URL.")

    seen: set[str] = set()
    for n in nav[:sections_limit]:
        label = n["text"].strip()
        if not label or label.lower() in seen:
            continue
        seen.add(label.lower())
        try:
            actuator.click(label)
            obs = actuator.observe() or {}
        except Exception:  # noqa: BLE001 - orientation must never crash; skip a section that won't open
            continue
        summary = _summarize_section(label, obs, complete)
        if summary:
            facts.append(summary)

    # Deeper: open a real record and learn the actions available ON it (where invoicing/dispatch live).
    if record_url:
        facts += orient_record_actions(actuator, complete, record_url=record_url)
    return facts


def orient_record_actions(actuator, complete, *, record_url: str, menus_limit: int = 5) -> list[str]:
    """Open a record and expand its action menus to learn what each offers — so the agent knows, e.g.,
    that an invoice is raised from an order's Billing menu, before it ever needs to."""
    facts: list[str] = []
    try:
        actuator.navigate(record_url)
        base = actuator.observe() or {}
    except Exception:  # noqa: BLE001
        return facts
    base_actions = set(base.get("actions") or [])
    menus = _identify_menus(base, complete)[:menus_limit]
    if menus:
        facts.append(f"On a record ({record_url.split('/')[-2] if '/' in record_url else 'detail'} view), "
                     f"the action menus are: {', '.join(menus)}.")
    for menu in menus:
        try:
            actuator.click(menu)
            opened = actuator.observe() or {}
        except Exception:  # noqa: BLE001
            continue
        revealed = [a for a in (opened.get("actions") or []) if a not in base_actions and a != menu]
        if revealed:
            facts.append(f"On a record, the '{menu}' menu offers: {', '.join(revealed[:8])}.")
    return facts


def _identify_menus(obs: dict, complete) -> list[str]:
    """Ask the model which of the record's visible buttons are action MENUS/dropdowns worth expanding
    (Billing, Transport, More, ...). Falls back to common menu labels if the model can't help."""
    from freight_recon.screen_discovery import _parse_llm_json

    actions = obs.get("actions") or []
    common = [a for a in actions if a.strip().lower() in
              ("billing", "transport", "more", "communicate", "actions", "invoice", "finance", "documents")]
    prompt = (
        "You are learning a freight TMS record page. Here are its visible buttons/links:\n"
        f"{actions}\n\n"
        "Which of these are ACTION MENUS or dropdowns that reveal MORE options when clicked (e.g. a "
        "Billing or Actions menu that would contain things like 'Raise invoice')? Reply with ONLY a JSON "
        'list of the EXACT labels, most useful first, max 5: {"menus": ["...", "..."]}'
    )
    try:
        parsed = _parse_llm_json(complete(prompt))
        menus = parsed.get("menus", []) if isinstance(parsed, dict) else []
        menus = [m for m in menus if isinstance(m, str) and m in actions]
        return menus or common
    except Exception:  # noqa: BLE001
        return common


def _summarize_section(section: str, obs: dict, complete) -> str:
    try:
        raw = complete(_orient_prompt(section, obs)) or ""
    except Exception:  # noqa: BLE001
        return ""
    line = " ".join(raw.split()).strip()[:220]
    return line if line else ""


def _orient_prompt(section: str, obs: dict) -> str:
    import json

    return (
        "You are a new freight back-office operator learning an unfamiliar TMS by walking through it. "
        f"You just opened the '{section}' area. In ONE concise sentence a teammate could reuse later, "
        "say what this section is for and the key actions/links visible here (name the buttons you see). "
        "Do not invent anything not on screen.\n\n"
        f"SCREEN:\n{json.dumps({k: obs.get(k) for k in ('headings', 'actions', 'nav')}, indent=1)[:1800]}\n\n"
        f"Reply with just the sentence, starting with '{section}:'."
    )
