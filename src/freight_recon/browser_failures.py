"""In-run browser failure taxonomy: classify the ACTUAL page state, respond deterministically.

The agent used to rely on the model to *notice* it was stuck — on a login screen, a rejected form, a
permission wall. That's model-dependent and slow. This module reads the observation deterministically
and names the failure, so the runtime can escalate with a precise, categorized reason (or recover)
instead of flailing. It only fires on HIGH-CONFIDENCE signals — a false "session expired" that stops a
healthy run is worse than missing one, so ambiguous states are left to the model + the safety gates.

This is separate from :mod:`run_diagnostics` (a post-run post-mortem over the whole step history); this
one runs live, each step.
"""

from __future__ import annotations

from enum import Enum


class FailureClass(str, Enum):
    NONE = "none"
    SESSION_EXPIRED = "session_expired"    # dumped to a login screen — needs a human to log in
    PERMISSION_DENIED = "permission_denied"  # the account can't do this action
    VALIDATION_ERROR = "validation_error"  # the form was rejected with a visible error


# Recovery disposition: SESSION/PERMISSION are terminal-for-the-agent (escalate, a human must act);
# VALIDATION is escalate-with-the-error (the human decides how to fix). None recover silently here —
# silent recovery on a money screen is exactly what we don't want.
ESCALATING = {FailureClass.SESSION_EXPIRED, FailureClass.PERMISSION_DENIED, FailureClass.VALIDATION_ERROR}

_LOGIN_URL = ("/login", "/signin", "/sign_in", "/sessions/new", "/users/sign_in", "/auth")
_LOGIN_TEXT = ("session has expired", "session expired", "session has timed out", "please sign in",
               "please log in", "sign in to your account", "log in to continue")
_PERMISSION_TEXT = ("permission denied", "not authorized", "access denied", "you are not allowed",
                    "you do not have permission", "403 forbidden", "not permitted")


def classify_page(observation: dict | None) -> tuple[FailureClass, str]:
    """Classify a page-level failure from the observation. Returns (class, human reason). NONE if healthy.

    High-confidence only:
    - SESSION_EXPIRED: a login URL, or expiry text, corroborated by a password field (so a page that
      merely links to "sign in" doesn't trip it).
    - PERMISSION_DENIED: an explicit not-authorized message.
    - VALIDATION_ERROR: the observation surfaced form error banners (``errors``).
    """
    obs = observation or {}
    url = str(obs.get("url") or "").lower()
    text = (str(obs.get("body_text") or "") + " " + " ".join(str(h) for h in (obs.get("headings") or []))).lower()
    has_password = any(str((f or {}).get("type", "")).lower() == "password" for f in (obs.get("inputs") or []))

    on_login_url = any(k in url for k in _LOGIN_URL)
    expiry_text = any(k in text for k in _LOGIN_TEXT)
    if (on_login_url and has_password) or (expiry_text and has_password) or (expiry_text and on_login_url):
        return (FailureClass.SESSION_EXPIRED,
                "the TMS is showing a login screen — the session has expired. Please log in and retry; "
                "I will not enter credentials.")

    if any(k in text for k in _PERMISSION_TEXT):
        return (FailureClass.PERMISSION_DENIED,
                "the TMS says this account is not authorized for this action — a human needs to grant "
                "access or do it.")

    errors = [str(e).strip() for e in (obs.get("errors") or []) if str(e).strip()]
    if errors:
        return (FailureClass.VALIDATION_ERROR,
                "the form was rejected: " + "; ".join(e[:100] for e in errors[:3]))

    return FailureClass.NONE, ""
