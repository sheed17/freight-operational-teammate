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


def orient_system(actuator, complete, *, sections_limit: int = 8) -> list[str]:
    """Walk the TMS's main OPERATIONAL navigation, learn what each section is for, and return reusable
    SYSTEM facts. ``actuator`` drives the browser (observe/click); ``complete`` summarizes a screen.
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
    return facts


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
