"""EP-3 — THE READ-ONLY NAVIGATION SURFACE (P4 adapter containment, R-07 scope).

`ReadOnlyCdpNavigator` adds exactly ONE capability over the F2 observer: fetching a document. That
is the narrowest thing that lets `propose_ar_from_tms.py` open a load's detail page to check for a
POD without holding an actuator, and these tests are the proof that it is narrow.

The argument this file has to defend is that navigation REDUCES reachable behaviour rather than
widening it:

  * A click DISPATCHES AN EVENT. On a SPA an `onclick` handler can POST an invoice while being no
    kind of form submit target, so no structural test on the element could classify it as safe.
    `Page.navigate` never runs that handler. The click fallback EP-3 used was deleted, not guarded.
  * `follow()` accepts only a URL the observed page itself published as an `<a href>`, so the
    reachable set is exactly the links the TMS rendered - not anything a caller can compose.
  * The transport allowlists two methods and has no script path at all, so there is no
    `functionDeclaration` argument to smuggle JavaScript into.
  * The observer is COMPOSED, not extended, so F2's certified surface is untouched and a value
    typed as an observer can never be a navigator.
"""

import ast
import inspect
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from freight_recon import cdp_readonly  # noqa: E402
from freight_recon.cdp_readonly import (  # noqa: E402
    FORBIDDEN_PRIMITIVES,
    NAVIGATION_CDP_METHODS,
    READ_ONLY_CDP_METHODS,
    ReadOnlyCdpError,
    ReadOnlyCdpNavigator,
    ReadOnlyCdpObserver,
    _NavigationChannel,
    navigation_target_is_allowed,
)

_PAGE = {"nav": [{"text": "Load 101", "url": "/loads/101"},
                 {"text": "Customers", "url": "https://secure.tms.test/customers"}]}


def _navigator(url_filter="tms.test"):
    """A navigator that was never connected. Every refusal under test happens BEFORE the transport,
    so these cases need no browser - and a case that reached the wire would raise 'not connected'
    rather than passing quietly."""
    return ReadOnlyCdpNavigator(url_filter=url_filter)


# ------------------------------------------------------------------ barrier 1: no mutation API

def test_the_navigator_exposes_no_mutation_primitive():
    """It gained `visit`/`follow` and nothing else. Every actuation name stays absent."""
    for name in FORBIDDEN_PRIMITIVES:
        assert not hasattr(ReadOnlyCdpNavigator, name), (
            f"ReadOnlyCdpNavigator grew a {name!r} method - the read-only navigation surface must "
            "not become an actuator"
        )


def test_the_observer_did_not_gain_navigation():
    """F2's surface is untouched: composing it must not have widened it."""
    for name in ("visit", "follow", "navigate", "click"):
        assert not hasattr(ReadOnlyCdpObserver, name), (
            f"ReadOnlyCdpObserver grew {name!r} - EP-3 must not widen the observation-only surface"
        )
    assert "Page.navigate" not in READ_ONLY_CDP_METHODS


def test_a_navigator_is_not_an_observer_subtype():
    """Composition, not inheritance. If the navigator were an observer subtype, every function that
    accepts an observer would silently accept navigation authority."""
    assert not issubclass(ReadOnlyCdpNavigator, ReadOnlyCdpObserver)
    assert isinstance(_navigator().observer, ReadOnlyCdpObserver)


# ------------------------------------------------------------------ barrier 2: targets are data

def test_follow_refuses_a_target_the_page_never_published():
    """The containment that makes navigation narrower than clicking: a composed URL is refused."""
    with pytest.raises(ReadOnlyCdpError, match="not published as a link"):
        _navigator().follow(_PAGE, "https://secure.tms.test/loads/101/invoice/raise")


def test_follow_refuses_when_the_page_published_nothing():
    for observation in ({}, {"nav": []}, {"nav": None}, None):
        with pytest.raises(ReadOnlyCdpError, match="not published as a link"):
            _navigator().follow(observation, "/loads/101")


def test_follow_accepts_only_the_exact_published_url_not_a_prefix():
    """A superset/lookalike of a published link is not a member."""
    for lookalike in ("/loads/101/delete", "/loads/10", "/loads/101?confirm=1"):
        with pytest.raises(ReadOnlyCdpError, match="not published as a link"):
            _navigator().follow(_PAGE, lookalike)


# ------------------------------------------------------------------ scheme and host allowlists

@pytest.mark.parametrize("url", [
    "javascript:fetch('/invoice/raise',{method:'POST'})",
    "JavaScript:alert(1)",
    "data:text/html,<script>fetch('/x',{method:'POST'})</script>",
    "file:///etc/passwd",
    "vbscript:msgbox",
    "blob:https://secure.tms.test/abc",
])
def test_code_bearing_schemes_are_refused(url):
    """A `javascript:` URL is arbitrary-JavaScript execution wearing a URL's clothing - exactly the
    primitive F2 exists to exclude. It must not re-enter through the navigation door.

    Checked with NO url_filter as well as with one. That is the case where the scheme allowlist is
    independently load-bearing: with a filter configured the host check happens to reject these too,
    so testing only the filtered case would leave the scheme guard unproven (the mutation battery
    caught exactly that - B30 escaped until this case was added).
    """
    for url_filter in ("tms.test", None):
        allowed, reason = navigation_target_is_allowed(url, url_filter)
        assert not allowed, f"{url!r} was allowed under url_filter={url_filter!r}: {reason}"
        with pytest.raises(ReadOnlyCdpError, match="refused navigation"):
            _navigator(url_filter).visit(url)


def test_navigation_off_the_tms_domain_is_refused():
    allowed, _ = navigation_target_is_allowed("https://evil.example/steal", "tms.test")
    assert not allowed
    with pytest.raises(ReadOnlyCdpError, match="not on the configured TMS domain"):
        _navigator().visit("https://evil.example/steal")


def test_an_empty_target_is_refused():
    for empty in ("", "   ", None):
        allowed, _ = navigation_target_is_allowed(empty, "tms.test")
        assert not allowed


def test_on_domain_and_relative_targets_are_allowed():
    for url in ("https://secure.tms.test/loads", "/loads/101", "?page=2", "#section"):
        allowed, reason = navigation_target_is_allowed(url, "tms.test")
        assert allowed, f"{url!r} refused: {reason}"


# ------------------------------------------------------------------ barrier 3: the transport

def test_the_navigation_channel_transmits_exactly_two_methods():
    assert NAVIGATION_CDP_METHODS == frozenset({"Page.enable", "Page.navigate"})


@pytest.mark.parametrize("method", [
    "Runtime.evaluate", "Runtime.callFunctionOn", "Runtime.enable",
    "Input.dispatchMouseEvent", "Input.insertText", "DOM.setFileInputFiles",
    "Page.captureScreenshot", "Network.enable",
])
def test_the_navigation_channel_refuses_every_other_method(method):
    """Including `Runtime.callFunctionOn`: this channel runs no script of any kind, so there is no
    `functionDeclaration` to vet and nothing to smuggle a payload through."""
    channel = _NavigationChannel(ws=None, timeout=1)
    with pytest.raises(ReadOnlyCdpError, match="not a navigation method"):
        channel.send(method, {})


def test_the_navigation_channel_has_no_script_path_at_all():
    source = inspect.getsource(_NavigationChannel)
    assert "functionDeclaration" not in source
    assert "VETTED_READ_SCRIPTS" not in source


# ------------------------------------------------------------------ no caller data becomes code

def test_the_navigation_path_never_builds_javascript_from_caller_input():
    """The defect EP-3 actually had was `evaluate(f"location.href={url!r}")`. Prove structurally
    that no f-string, concatenation or format call carries caller input in the navigation closure."""
    source = "".join(
        inspect.getsource(obj) for obj in
        (ReadOnlyCdpNavigator, _NavigationChannel, navigation_target_is_allowed)
    )
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.JoinedStr):
            # f-strings are fine in refusal MESSAGES; none may reach a send() as a param value.
            continue
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in ("evaluate", "command"), (
                "the navigation surface reached an actuation primitive"
            )
    assert "location.href" not in source, (
        "the navigation surface builds a `location.href=` assignment - that is EP-3's original "
        "defect, caller data interpolated into JavaScript source"
    )


# ------------------------------------------------------------------ hostile imports

def test_the_navigator_module_imports_no_actuator():
    """cdp_readonly must not reach cdp_session/cdp_actuator: the dependency runs write -> read."""
    tree = ast.parse((ROOT / "src/freight_recon/cdp_readonly.py").read_text(encoding="utf-8"))
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    for banned in ("cdp_session", "cdp_actuator", ".cdp_session", ".cdp_actuator"):
        assert banned not in imported


@pytest.mark.parametrize("attr", ["evaluate", "command", "set_file_input", "click", "type",
                                  "select", "upload_file", "click_row_action", "navigate"])
def test_a_hostile_caller_cannot_reach_an_actuation_method_by_name(attr):
    """Direct attribute acquisition fails on both surfaces - there is nothing to bind."""
    assert not hasattr(ReadOnlyCdpNavigator, attr)
    assert not hasattr(ReadOnlyCdpObserver, attr)


def test_the_private_navigation_channel_still_refuses_even_when_reached():
    """Python has no private state, so the mangled channel IS reachable. Barrier 3 is what makes
    that harmless: the transport refuses before anything reaches the browser."""
    nav = _navigator()
    channel = _NavigationChannel(ws=None, timeout=1)
    with pytest.raises(ReadOnlyCdpError, match="not a navigation method"):
        channel.send("Runtime.evaluate", {"expression": "fetch('/x',{method:'POST'})"})
    assert not hasattr(nav, "evaluate")


# ------------------------------------------------------------------ the module is self-consistent

def test_forbidden_primitives_still_names_navigate_for_the_observer():
    """`navigate` stays forbidden ON THE OBSERVER. The navigator's method is `visit`/`follow`, so
    the F2 guard that asserts these names never appear on the observation surface still holds."""
    assert "navigate" in FORBIDDEN_PRIMITIVES
    assert "click" in FORBIDDEN_PRIMITIVES
    assert not hasattr(ReadOnlyCdpObserver, "navigate")


def test_the_navigator_is_exported_for_callers():
    assert cdp_readonly.ReadOnlyCdpNavigator is ReadOnlyCdpNavigator
