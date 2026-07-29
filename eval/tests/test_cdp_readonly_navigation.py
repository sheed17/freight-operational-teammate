"""EP-3 — THE READ-ONLY NAVIGATION SURFACE (P4 adapter containment, R-07 scope).

`ReadOnlyCdpNavigator` adds exactly ONE capability over the F2 observer: fetching a document. That
is the narrowest thing that lets `propose_ar_from_tms.py` open a load's detail page to check for a
POD without holding an actuator, and these tests are the proof that it is narrow.

The argument this file has to defend is that navigation REDUCES reachable behaviour rather than
widening it:

  * A click DISPATCHES AN EVENT. On a SPA an `onclick` handler can POST an invoice while being no
    kind of form submit target, so no structural test on the element could classify it as safe.
    `Page.navigate` never runs that handler. The click fallback EP-3 used was deleted, not guarded.
  * The transport allowlists two methods and has no script path at all, so there is no
    `functionDeclaration` argument to smuggle JavaScript into.
  * The observer is COMPOSED, not extended, so F2's certified surface is untouched and a value
    typed as an observer can never be a navigator.

AND THE PART THE HOSTILE REVIEW OBLIGATION ADDS. An earlier cut of this surface accepted any URL the
observed page published as an `<a href>`. That is NOT sufficient, and the reviewer premise is right:

    "A same-origin, page-published href is not inherently read-only. Legacy systems may expose
     state-changing GET routes."

`/loads/101/delete`, `/invoices/9/approve`, `/logout` and Rails-style
`<a href="/loads/101" data-method="delete">` are all same-origin anchors a TMS really does render. A
generic follower of any observed anchor reaches every one of them. So the surface no longer accepts
a URL at all: it accepts a PROVENANCE RECORD binding the observed row, the observed load identity,
the exact href and the observation context — re-derived from the live page at follow time. The
`test_the_navigator_refuses_*` block below is the mechanical proof, one case per hostile shape the
obligation names.
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
    ACTION_ROUTE_TOKENS,
    FORBIDDEN_PRIMITIVES,
    NAVIGATION_CDP_METHODS,
    READ_ONLY_CDP_METHODS,
    ObservedLoadLink,
    ReadOnlyCdpError,
    ReadOnlyCdpNavigator,
    ReadOnlyCdpObserver,
    _NavigationChannel,
    anchor_is_plain_document_link,
    href_route_is_observational,
    navigation_target_is_allowed,
    select_load_detail_link,
)

HOST = "https://secure.tms.test"


def _navigator(url_filter="tms.test", allowed_origin=HOST):
    """A navigator that was never connected. Every refusal under test happens BEFORE the transport,
    so these cases need no browser - and a case that reached the wire would raise 'not connected'
    rather than passing quietly.

    `allowed_origin` is the ESTABLISHED ORIGIN (F-02). It is passed explicitly, exactly as the
    production entry points now pin it from their operator-configured URL, so these cases exercise
    the same fail-closed policy the product runs."""
    return ReadOnlyCdpNavigator(url_filter=url_filter, allowed_origin=allowed_origin)


def _anchor(text, href, *, attrs=None, in_menu=False, resolved=None):
    """One anchor as `LOAD_ROW_LINKS_FN` reports it."""
    return {
        "text": text,
        "href": href,
        "resolved": resolved if resolved is not None else (HOST + href if href.startswith("/") else href),
        "attrs": dict(attrs or {}),
        "in_menu": in_menu,
    }


def _payload(*links, cells=("L-101", "Acme Freight", "Delivered", "$1,450.00"), index=3):
    """The observation payload for ONE matched row carrying those anchors."""
    return {"load_id": "L-101",
            "rows": [{"index": index, "match": "cell-exact", "cells": list(cells),
                      "links": list(links)}]}


def _select(*links, load_id="L-101", context_seq=0, established_origin=HOST, url_filter=None, **kw):
    return select_load_detail_link(_payload(*links, **kw), load_id, context_seq=context_seq,
                                   established_origin=established_origin, url_filter=url_filter)


#: The one legitimate shape: the row's own anchor whose visible text IS the load identifier.
GOOD = _anchor("L-101", "/loads/101")


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
    for name in ("visit", "follow", "navigate", "click", "detail_link_for_load"):
        assert not hasattr(ReadOnlyCdpObserver, name), (
            f"ReadOnlyCdpObserver grew {name!r} - EP-3 must not widen the observation-only surface"
        )
    assert "Page.navigate" not in READ_ONLY_CDP_METHODS


def test_a_navigator_is_not_an_observer_subtype():
    """Composition, not inheritance. If the navigator were an observer subtype, every function that
    accepts an observer would silently accept navigation authority."""
    assert not issubclass(ReadOnlyCdpNavigator, ReadOnlyCdpObserver)
    assert isinstance(_navigator().observer, ReadOnlyCdpObserver)


def test_the_provenance_observation_is_a_vetted_read_script():
    """`load_row_links` is an OBSERVATION, so it runs through the same vetted registry as every
    other read - it is not a side channel that escapes barrier 3."""
    assert cdp_readonly.LOAD_ROW_LINKS_FN in cdp_readonly.VETTED_READ_SCRIPTS
    assert hasattr(ReadOnlyCdpObserver, "load_row_links")


# ============================================================================================
# THE HOSTILE REVIEW OBLIGATION: a same-origin page-published href is not inherently read-only.
#
# Each case below is a link a real legacy TMS renders IN THE LOAD'S OWN ROW. Every one of them
# would have been followed by a generic "any observed anchor" follower. Every one is refused.
# ============================================================================================

@pytest.mark.parametrize("label,link", [
    # -- state-changing GET routes, same origin, genuinely rendered by the page -----------------
    ("logout",              _anchor("Log out", "/logout")),
    ("session destroy",     _anchor("L-101", "/session/destroy")),
    ("delete",              _anchor("Delete", "/loads/101/delete")),
    ("destroy",             _anchor("L-101", "/loads/101/destroy")),
    ("remove",              _anchor("Remove", "/loads/101/remove")),
    ("cancel",              _anchor("Cancel", "/loads/101/cancel")),
    ("void",                _anchor("Void", "/loads/101/void")),
    ("approve",             _anchor("Approve", "/loads/101/approve")),
    ("release",             _anchor("Release", "/loads/101/release")),
    ("pay",                 _anchor("Pay", "/loads/101/pay")),
    ("post invoice",        _anchor("Invoice", "/loads/101/invoice")),
    ("send email",          _anchor("Email", "/loads/101/email")),
    ("export",              _anchor("Export", "/loads/101/export")),
    ("download",            _anchor("Download", "/loads/101/download")),
    ("edit",                _anchor("Edit", "/loads/101/edit")),
    # -- an action route wearing the load's own identifier as its link text ---------------------
    ("action text-bound",   _anchor("L-101", "/loads/101/approve")),
    # -- HTTP-verb smuggling: a link by tag, a DELETE by behaviour -------------------------------
    ("rails data-method",   _anchor("L-101", "/loads/101", attrs={"data-method": "delete"})),
    ("turbo data-method",   _anchor("L-101", "/loads/101", attrs={"data-turbo-method": "post"})),
    ("_method override",    _anchor("L-101", "/loads/101?_method=DELETE")),
    ("cmd query",           _anchor("L-101", "/loads/101?cmd=approve")),
    ("destructive query",   _anchor("L-101", "/loads/101?confirm=cancel")),
    # -- action-menu routes and controls ---------------------------------------------------------
    ("inside action menu",  _anchor("L-101", "/loads/101", in_menu=True)),
    ("role=button",         _anchor("L-101", "/loads/101", attrs={"role": "button"})),
    ("role=menuitem",       _anchor("L-101", "/loads/101", attrs={"role": "menuitem"})),
    ("aria-haspopup",       _anchor("L-101", "/loads/101", attrs={"aria-haspopup": "true"})),
    ("onclick handler",     _anchor("L-101", "/loads/101", attrs={"onclick": "postInvoice()"})),
    ("data-confirm",        _anchor("L-101", "/loads/101", attrs={"data-confirm": "Are you sure?"})),
    ("data-remote",         _anchor("L-101", "/loads/101", attrs={"data-remote": "true"})),
    ("download attribute",  _anchor("L-101", "/loads/101", attrs={"download": "pod.pdf"})),
    ("formaction",          _anchor("L-101", "/loads/101", attrs={"formaction": "/loads/101/pay"})),
    # -- a different load / an unrelated document, both inside the right row ---------------------
    ("a different load",    _anchor("L-104", "/loads/104")),
    ("unrelated document",  _anchor("Customer", "/customers/44")),
    ("unrelated report",    _anchor("Report", "/reports/monthly")),
    # -- code wearing a URL's clothing -----------------------------------------------------------
    ("javascript: url",     _anchor("L-101", "javascript:fetch('/x',{method:'POST'})")),
    ("data: url",           _anchor("L-101", "data:text/html,<script>1</script>")),
    # -- a `<base>` tag makes a benign attribute resolve onto an action route --------------------
    ("base-tag redirect",   _anchor("L-101", "/loads/101", resolved=HOST + "/loads/101/approve")),
])
def test_the_navigator_refuses_every_hostile_link_in_the_loads_own_row(label, link):
    """Every one of these is a same-origin anchor the page really published, inside the row for the
    load being billed. Row containment is necessary provenance and is NOT sufficient authority."""
    chosen, reason = _select(link)
    assert chosen is None, (
        f"{label}: {link['href']!r} was ADMITTED as a load-detail document. A same-origin, "
        f"page-published href is not inherently read-only, and this one is consequential."
    )
    assert reason, f"{label}: refused without stating why - a refusal reason is part of the contract"


def test_no_hostile_shape_in_the_loads_own_row_is_ever_followed():
    """The parametrized cases above, as ONE assertion over the whole hostile set.

    It exists so the mutation battery has a single stable node to aim at: a mutant that reopens any
    barrier (route family, anchor shape, identity binding, scheme) turns this red, and the report
    names which shapes escaped rather than a bare parametrized id.
    """
    hostile = {
        "state-changing GET": _anchor("L-101", "/loads/101/delete"),
        "approve route": _anchor("L-101", "/loads/101/approve"),
        "logout": _anchor("Log out", "/logout"),
        "verb smuggling": _anchor("L-101", "/loads/101", attrs={"data-method": "delete"}),
        "method override": _anchor("L-101", "/loads/101?_method=DELETE"),
        "action menu": _anchor("L-101", "/loads/101", in_menu=True),
        "control role": _anchor("L-101", "/loads/101", attrs={"role": "button"}),
        "onclick": _anchor("L-101", "/loads/101", attrs={"onclick": "post()"}),
        "a different load": _anchor("L-104", "/loads/104"),
        "unrelated export": _anchor("Export", "/loads/101/export"),
        "code as a url": _anchor("L-101", "javascript:fetch('/x',{method:'POST'})"),
        "base-tag redirect": _anchor("L-101", "/loads/101", resolved=HOST + "/loads/101/approve"),
    }
    escaped = [label for label, link in hostile.items() if _select(link)[0] is not None]
    assert not escaped, (
        f"these hostile shapes were admitted as load-detail documents: {escaped}. A same-origin, "
        "page-published href is not inherently read-only."
    )


def test_the_legitimate_detail_link_is_still_admitted():
    """A guard that refuses everything contains nothing: it just breaks the feature. The one shape
    EP-3 actually needs must survive, or POD reads never happen and the money path never opens."""
    chosen, reason = _select(GOOD)
    assert chosen is not None, f"the load's own detail link was refused: {reason}"
    assert chosen.href == "/loads/101"
    assert chosen.load_id == "L-101"
    assert chosen.bound_by == "link-text"
    assert chosen.row_index == 3
    assert "L-101" in chosen.row_cells


def test_a_detail_subresource_bound_by_path_segment_is_admitted():
    """The documents/POD sub-page is the other legitimate shape: bound by an exact PATH SEGMENT."""
    chosen, _ = _select(_anchor("Documents", "/loads/L-101/documents"))
    assert chosen is not None
    assert chosen.bound_by == "path-segment"


# ------------------------------------------------------------------ identity binding is exact

@pytest.mark.parametrize("text,href", [
    ("Delete L-101", "/loads/9/purge_all"),      # identifier appears, but as a substring of a label
    ("L-1010", "/loads/1010"),                   # a LONGER identifier that contains the needle
    ("XL-101", "/loads/x101"),                   # a longer identifier the needle is a suffix of
])
def test_identity_binding_never_decides_by_substring(text, href):
    """The obligation is explicit: do not rely on brittle substring matching. `L-101` must not
    select a link merely because the characters `L-101` occur somewhere in its text or URL."""
    chosen, reason = _select(_anchor(text, href))
    assert chosen is None, f"{text!r} -> {href!r} was selected for L-101 by substring: {reason}"


def test_row_containment_alone_is_not_provenance():
    """An anchor in the right row, on a harmless route, that is not identified BY the load."""
    chosen, reason = _select(_anchor("Notes", "/notes/77"))
    assert chosen is None
    assert "not identified BY the load" in reason


def test_two_candidate_documents_are_ambiguous_and_none_is_followed():
    """If the page offers two different identity-bound documents, this surface does not guess."""
    chosen, reason = _select(_anchor("L-101", "/loads/101"), _anchor("L-101", "/loads/101/summary"))
    assert chosen is None
    assert "ambiguous" in reason


def test_an_identifier_matching_two_rows_is_ambiguous():
    """Two rows carrying one identifier means no row can be said to BE the load's row."""
    payload = {"rows": [
        {"index": 3, "cells": ["L-101"], "links": [GOOD]},
        {"index": 9, "cells": ["L-101"], "links": [_anchor("L-101", "/loads/9101")]},
    ]}
    chosen, reason = select_load_detail_link(payload, "L-101", context_seq=0,
                                             established_origin=HOST)
    assert chosen is None
    assert "ambiguous provenance" in reason


def test_an_unobserved_row_yields_nothing():
    for payload in ({}, None, {"rows": []}, {"rows": None}):
        chosen, reason = select_load_detail_link(payload, "L-101", context_seq=0,
                                                 established_origin=HOST)
        assert chosen is None
        assert reason


def test_an_empty_load_identifier_is_refused():
    for load_id in ("", "   ", None):
        chosen, _ = _select(GOOD, load_id=load_id)
        assert chosen is None


# ------------------------------------------------------------------ forged / stale provenance

def test_follow_refuses_anything_that_is_not_a_minted_provenance_record():
    """A URL is not accepted. There is no generic 'follow this link' capability to reach."""
    for forged in ("/loads/101", HOST + "/loads/101", {"href": "/loads/101"}, None, 42,
                   ["/loads/101"]):
        with pytest.raises(ReadOnlyCdpError, match="ObservedLoadLink"):
            _navigator().follow(forged)


def test_follow_refuses_a_hand_composed_lookalike_record():
    """`ObservedLoadLink` is a plain value object with NO authority: constructing one proves
    nothing, because follow() re-derives the authorized record from the live page. This case stops
    before that (stale context), and the re-derivation case below covers a context-correct forgery."""
    forged = ObservedLoadLink(load_id="L-101", href="/loads/101/approve",
                              resolved_href=HOST + "/loads/101/approve", row_index=3,
                              row_cells=("L-101",), link_text="L-101", bound_by="link-text",
                              context_seq=7)
    with pytest.raises(ReadOnlyCdpError, match="stale provenance"):
        _navigator().follow(forged)


def test_a_record_minted_before_a_navigation_is_stale():
    """Replay protection: every successful fetch advances the observation context, so a record
    minted against the previous document cannot be presented afterwards."""
    nav = _navigator()
    minted, _ = _select(GOOD, context_seq=nav.context_seq)
    assert minted is not None
    object.__setattr__(nav, "_ReadOnlyCdpNavigator__context_seq", nav.context_seq + 1)
    with pytest.raises(ReadOnlyCdpError, match="stale provenance"):
        nav.follow(minted)


class _StubObserver:
    """Stands in for the contained observer so the re-derivation logic can be driven without a
    browser. It answers the provenance observation and nothing else - a stub that could actuate
    would be testing something other than the surface under test."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def load_row_links(self, load_id):
        self.calls.append(load_id)
        return self.payload


def _navigator_seeing(payload):
    """A navigator whose observation of the page is `payload`. `observer` is an ordinary slot, so
    replacing it needs no patching machinery."""
    nav = _navigator()
    nav.observer = _StubObserver(payload)
    return nav


def test_follow_re_derives_the_record_from_the_live_page():
    """The forgery case that matters: a well-formed record with the CURRENT context, naming a
    document the page does not actually publish for that load. It must still be refused, because
    the authorized record is re-read from the page rather than taken from the caller."""
    nav = _navigator_seeing(_payload(GOOD))
    forged = ObservedLoadLink(load_id="L-101", href="/loads/101/approve",
                              resolved_href=HOST + "/loads/101/approve", row_index=3,
                              row_cells=("L-101",), link_text="L-101", bound_by="link-text",
                              context_seq=nav.context_seq)
    with pytest.raises(ReadOnlyCdpError, match="does not match the record the page currently"):
        nav.follow(forged)
    assert nav.observer.calls == ["L-101"], "follow() did not re-read the page before deciding"


def test_follow_refuses_when_the_page_no_longer_publishes_the_load():
    nav = _navigator_seeing({"rows": []})
    genuine, _ = _select(GOOD, context_seq=nav.context_seq)
    with pytest.raises(ReadOnlyCdpError, match="publishes no provenance-bound detail link"):
        nav.follow(genuine)


def test_detail_link_for_load_records_why_it_refused():
    """The caller treats None as POD-unknown (which blocks the money button); the reason is kept so
    a refusal is diagnosable rather than silent."""
    nav = _navigator_seeing(_payload(_anchor("Delete", "/loads/101/delete")))
    assert nav.detail_link_for_load("L-101") is None
    assert "delete" in nav.last_refusal.lower()


def test_a_genuine_record_survives_re_derivation_and_reaches_the_transport():
    """The positive control for the whole chain: a legitimate record passes every provenance check
    and is refused only by the ABSENT TRANSPORT. Without this, every test above would still pass if
    follow() refused unconditionally, and the feature would be silently dead."""
    nav = _navigator_seeing(_payload(GOOD))
    genuine = nav.detail_link_for_load("L-101")
    assert genuine is not None and nav.last_refusal == ""
    with pytest.raises(ReadOnlyCdpError, match="not connected"):
        nav.follow(genuine)


# ------------------------------------------------------------------ the route classifier itself

@pytest.mark.parametrize("route", [
    "/logout", "/loads/101/delete", "/loads/101/approve", "/loads/101/pay", "/invoices/9/submit",
    "/loads/101/edit", "/loads/new", "/loads/101/archive", "/loads/101/send", "/exports/all",
])
def test_action_routes_are_refused_by_the_classifier(route):
    allowed, reason = href_route_is_observational(route)
    assert not allowed, f"{route!r} classified observational: {reason}"


@pytest.mark.parametrize("route", [
    "/loads/101", "/loads/L-101/documents", "/loads/101/attachments", "/loads/101?tab=paperwork",
    HOST + "/loads/101", "/shipments/2024/101/pod",
])
def test_observational_routes_are_admitted_by_the_classifier(route):
    allowed, reason = href_route_is_observational(route)
    assert allowed, f"{route!r} refused: {reason}"


@pytest.mark.parametrize("route", ["", "   ", "#anchor", "/", "mailto:ops@tms.test",
                                   "tel:+15551234567", "javascript:1"])
def test_the_classifier_fails_closed_on_non_documents(route):
    allowed, _ = href_route_is_observational(route)
    assert not allowed


def test_the_action_vocabulary_is_matched_as_whole_tokens_not_substrings():
    """`/loads/undeleted-archive-report` must not be refused by containing `delete`, and
    `/paydays` must not be refused by containing `pay` - and the real verbs must still fire."""
    assert href_route_is_observational("/loads/undeleted")[0]
    assert href_route_is_observational("/paydays/101")[0]
    assert not href_route_is_observational("/loads/101/delete")[0]
    assert not href_route_is_observational("/loads/101/pay")[0]


def test_the_action_vocabulary_covers_the_obligations_named_routes():
    """The obligation names these explicitly; a vocabulary that quietly lost one would leave a
    named hostile route reachable."""
    for verb in ("logout", "delete", "remove", "cancel", "approve", "release", "pay", "export",
                 "download"):
        assert verb in ACTION_ROUTE_TOKENS


def test_the_anchor_classifier_admits_a_plain_link():
    """The classifier must not be vacuous: a bare `<a href>` with no action attributes passes."""
    ok, _ = anchor_is_plain_document_link(_anchor("L-101", "/loads/101"))
    assert ok
    ok, _ = anchor_is_plain_document_link(_anchor("L-101", "/loads/101",
                                                  attrs={"data-method": "get"}))
    assert ok, "an explicit data-method=get is still a document GET"


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
        allowed, reason = navigation_target_is_allowed(url, url_filter, established_origin=HOST)
        assert not allowed, f"{url!r} was allowed under url_filter={url_filter!r}: {reason}"
        with pytest.raises(ReadOnlyCdpError, match="refused navigation"):
            _navigator(url_filter).visit(url)


def test_navigation_off_the_tms_domain_is_refused():
    allowed, _ = navigation_target_is_allowed("https://evil.example/steal", "tms.test",
                                              established_origin=HOST)
    assert not allowed
    with pytest.raises(ReadOnlyCdpError, match="cross-origin navigation refused"):
        _navigator().visit("https://evil.example/steal")


def test_an_empty_target_is_refused():
    for empty in ("", "   ", None):
        allowed, _ = navigation_target_is_allowed(empty, "tms.test", established_origin=HOST)
        assert not allowed


def test_on_domain_and_relative_targets_are_allowed():
    for url in ("https://secure.tms.test/loads", "/loads/101", "?page=2", "#section"):
        allowed, reason = navigation_target_is_allowed(url, "tms.test", established_origin=HOST)
        assert allowed, f"{url!r} refused: {reason}"


def test_the_operator_configured_entry_url_is_route_checked_too():
    """`visit()` is the one entry by a target the page did not publish, so configuration cannot be
    pointed at an action route either."""
    for bad in ("https://secure.tms.test/logout", "https://secure.tms.test/loads/101/delete"):
        with pytest.raises(ReadOnlyCdpError, match="refused navigation"):
            _navigator().visit(bad)


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
        (ReadOnlyCdpNavigator, _NavigationChannel, navigation_target_is_allowed,
         select_load_detail_link, href_route_is_observational, anchor_is_plain_document_link)
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


def test_the_provenance_script_runs_no_mutation_and_takes_its_target_as_data():
    """`LOAD_ROW_LINKS_FN` reads structure. It must not click, focus, submit or write anything, and
    the load identifier must arrive as a PARAMETER, never spliced into the source."""
    js = cdp_readonly.LOAD_ROW_LINKS_FN
    assert js.lstrip().startswith("function(loadId)"), "the target must be a function parameter"
    for mutation in (".click(", ".focus(", ".submit(", "dispatchEvent", ".innerHTML=",
                     "document.write", ".setAttribute(", "location="):
        assert mutation not in js.replace(" ", ""), f"the provenance script contains {mutation!r}"


# ------------------------------------------------------------------ hostile imports

def test_the_navigator_module_imports_no_actuator():
    """cdp_readonly must not reach cdp_session/cdp_actuator: the dependency runs write -> read."""
    tree = ast.parse((ROOT / "src/freight_recon/cdp_readonly.py").read_text(encoding="utf-8"))
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    # POPULATION PROOF. The claim below is a negative over a parsed corpus: an
    # empty `imported` would satisfy it while proving nothing. websocket is the
    # transport the read surface cannot work without, so its absence means the
    # parse failed rather than that the module is clean.
    assert "websocket" in imported, (
        "cdp_readonly does not import websocket - the parse is degenerate, so the actuator "
        "assertions below would be vacuously true"
    )
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


# ============================================================================================
# F-02 (INDEPENDENT HOSTILE REVIEW) — THE ORIGIN RESTRICTION MUST FAIL CLOSED.
#
# The reviewer's finding, exactly: `--operation-url-filter` defaults to "", `url_matches_filter`
# returns True for falsy input, `select_load_detail_link` performed NO independent origin check, so
# a page-published cross-origin link was selectable AND the allow-reason falsely claimed the target
# was "on the TMS domain allowlist" when no allowlist had run.
#
# The safe default is DENIAL. Origin safety may not depend on an optional textual filter.
# ============================================================================================

EVIL = "https://evil.example"


def _origin_corpus_is_real():
    """POPULATION PROOF for the negatives below. Every refusal case in this section asserts that
    something is NOT selected; all of them would pass vacuously if the legitimate shape were also
    unselectable (a broken payload builder, a renamed field, an over-strict guard). This anchors the
    negatives on a POSITIVE that must hold: the good link IS selected under the same helper."""
    chosen, reason = _select(GOOD)
    assert chosen is not None, (
        "the legitimate same-origin detail link is not selectable, so every cross-origin refusal "
        "below would pass vacuously — the corpus is degenerate, not safe"
    )
    return chosen, reason


def test_the_origin_corpus_is_non_empty():
    chosen, reason = _origin_corpus_is_real()
    assert chosen.href == "/loads/101"
    assert reason


# ---------------------------------------------------------------- 1 & 2: the reviewer's own cases

@pytest.mark.parametrize("url_filter,label", [("", "empty filter"), (None, "absent filter")])
def test_a_cross_origin_link_is_refused_with_an_empty_or_absent_filter(url_filter, label):
    """THE F-02 REACHABLE PATH. `--operation-url-filter` defaults to "", and that used to mean
    'allow everything'. It must now mean 'the parsed-origin policy decides', and the policy refuses
    a foreign origin."""
    _origin_corpus_is_real()
    chosen, reason = _select(
        _anchor("L-101", EVIL + "/loads/L-101", resolved=EVIL + "/loads/L-101"),
        url_filter=url_filter)
    assert chosen is None, f"a cross-origin link was SELECTED under {label}: {reason}"
    assert "cross-origin" in reason, reason
    # and the navigator refuses to fetch it too, under the same configuration
    allowed, why = navigation_target_is_allowed(EVIL + "/loads/L-101", url_filter,
                                                established_origin=HOST)
    assert not allowed and "cross-origin" in why


def test_no_established_origin_refuses_everything_rather_than_allowing_everything():
    """The structural core of F-02: absent origin configuration FAILS CLOSED. Previously an empty
    filter made `url_matches_filter` return True for every input."""
    for origin in ("", None):
        allowed, reason = navigation_target_is_allowed(HOST + "/loads/101", None,
                                                       established_origin=origin)
        assert not allowed, f"an unconfigured origin allowed navigation: {reason}"
        assert "no established origin" in reason
        chosen, why = _select(GOOD, established_origin=origin)
        assert chosen is None, f"a link was selected with no established origin: {why}"


def test_a_malformed_origin_configuration_is_refused_at_construction():
    """A malformed allowlist/origin must not silently degrade to 'allow all'."""
    for bad in ("not a url", "javascript:alert(1)", "https://", "https://tms..test", "://x"):
        with pytest.raises(ReadOnlyCdpError, match="fails CLOSED"):
            ReadOnlyCdpNavigator(allowed_origin=bad)


# ---------------------------------------------------------------- 3: same text, foreign href

def test_a_link_whose_text_matches_the_load_but_whose_href_is_foreign_is_refused():
    """Identity binding is satisfied (the visible text IS the load id) and the route is otherwise
    observational. ONLY the origin check stops this one — which is why it must exist independently
    of the identity and route barriers."""
    _origin_corpus_is_real()
    chosen, reason = _select(
        _anchor("L-101", EVIL + "/loads/L-101", resolved=EVIL + "/loads/L-101"))
    assert chosen is None
    assert "cross-origin" in reason


def test_a_foreign_href_is_refused_even_when_the_identifier_is_a_path_segment():
    """The other identity binding — path-segment — must not be a second way in."""
    _origin_corpus_is_real()
    chosen, reason = _select(
        _anchor("details", EVIL + "/loads/L-101/pod", resolved=EVIL + "/loads/L-101/pod"))
    assert chosen is None
    assert "cross-origin" in reason or "origin policy" in reason


# ---------------------------------------------------------------- 4: scheme-relative

def test_a_scheme_relative_cross_origin_target_is_not_treated_as_relative():
    """`//evil.example/path` starts with '/' and the OLD rule said 'starts with / => relative =>
    same origin => allowed'. It is scheme-relative: it changes the host."""
    allowed, reason = navigation_target_is_allowed("//evil.example/path", None,
                                                   established_origin=HOST)
    assert not allowed, f"//evil.example/path was allowed: {reason}"
    _origin_corpus_is_real()
    chosen, why = _select(_anchor("L-101", "//evil.example/loads/L-101",
                                  resolved="//evil.example/loads/L-101"))
    assert chosen is None, f"a scheme-relative cross-origin link was selected: {why}"


# ---------------------------------------------------------------- 5: userinfo trick

@pytest.mark.parametrize("url", [
    "https://secure.tms.test@evil.example/loads/L-101",
    "https://secure.tms.test:pass@evil.example/loads/L-101",
    "https://evil.example@secure.tms.test/loads/L-101",
])
def test_credential_userinfo_urls_are_refused(url):
    """`https://trusted.example@evil.example/path` fetches from evil.example; a reader's eye stops
    at the trusted-looking prefix. The shape is refused outright, in both directions."""
    allowed, reason = navigation_target_is_allowed(url, None, established_origin=HOST)
    assert not allowed, f"{url!r} was allowed: {reason}"
    assert cdp_readonly.parse_origin(url) is None
    _origin_corpus_is_real()
    chosen, why = _select(_anchor("L-101", url, resolved=url))
    assert chosen is None, f"a userinfo URL was selected: {why}"


# ---------------------------------------------------------------- 6: same host, unsafe scheme

@pytest.mark.parametrize("url", [
    "ftp://secure.tms.test/loads/101",
    "ws://secure.tms.test/loads/101",
    "javascript:location='/loads/101'",
    "data:text/html,<a href=/loads/101>",
    "file://secure.tms.test/loads/101",
])
def test_the_same_hostname_under_an_unsafe_scheme_is_refused(url):
    """Host equality is not origin equality: the scheme is part of the origin, and a scheme outside
    http/https is not a document fetch at all."""
    allowed, reason = navigation_target_is_allowed(url, "tms.test", established_origin=HOST)
    assert not allowed, f"{url!r} was allowed: {reason}"


def test_http_and_https_on_one_host_are_different_origins():
    """A downgrade to plaintext on the same hostname is a different origin, and the authenticated
    session must not be steered onto it."""
    allowed, reason = navigation_target_is_allowed("http://secure.tms.test/loads/101", None,
                                                   established_origin=HOST)
    assert not allowed, f"an http downgrade was allowed: {reason}"
    assert "cross-origin" in reason


# ---------------------------------------------------------------- 7: disallowed port

@pytest.mark.parametrize("url,allowed_expected", [
    ("https://secure.tms.test:8443/loads/101", False),
    ("https://secure.tms.test:80/loads/101", False),
    ("https://secure.tms.test:443/loads/101", True),   # the scheme's default, stated explicitly
    ("https://secure.tms.test/loads/101", True),
])
def test_the_effective_port_is_part_of_the_origin(url, allowed_expected):
    """Ports are normalized (https => 443) and then compared as integers, so `:443` and an omitted
    port are ONE origin while `:8443` is a different one."""
    allowed, reason = navigation_target_is_allowed(url, None, established_origin=HOST)
    assert allowed is allowed_expected, f"{url!r} -> {allowed} ({reason})"


# ---------------------------------------------------------------- 8 & 9: the ALLOWED shapes

def test_a_relative_safe_detail_route_is_allowed():
    """The intended policy for relative URLs, stated explicitly: a reference with no host component
    resolves against the established origin and is allowed."""
    for url in ("/loads/101", "/loads/101/pod", "?page=2", "#section"):
        allowed, reason = navigation_target_is_allowed(url, None, established_origin=HOST)
        assert allowed, f"{url!r} refused: {reason}"
        assert "relative" in reason and "established origin" in reason


def test_a_valid_same_origin_absolute_detail_route_is_allowed():
    """The intended policy for same-origin ABSOLUTE URLs, stated explicitly: allowed, and the reason
    names the origin comparison that admitted it."""
    allowed, reason = navigation_target_is_allowed(HOST + "/loads/101", None,
                                                   established_origin=HOST)
    assert allowed, reason
    assert "same-origin" in reason
    chosen, why = _select(_anchor("L-101", HOST + "/loads/101", resolved=HOST + "/loads/101"))
    assert chosen is not None, why


# ---------------------------------------------------------------- 10: the reason must be true

def test_the_allow_reason_never_claims_an_allowlist_that_was_not_configured():
    """F-02 item 7. The old code answered a cross-origin ALLOW with the reason 'on the TMS domain
    allowlist' when no allowlist existed at all. A reason that describes a check which did not run
    is evidence of a control that does not exist."""
    _, reason = navigation_target_is_allowed(HOST + "/loads/101", None, established_origin=HOST)
    assert "domain filter" not in reason, (
        f"the reason claims a domain filter with none configured: {reason!r}")
    assert "same-origin" in reason

    _, filtered = navigation_target_is_allowed(HOST + "/loads/101", "tms.test",
                                               established_origin=HOST)
    assert "domain filter" in filtered, (
        f"a configured filter DID run but the reason does not say so: {filtered!r}")

    chosen, select_reason = _select(GOOD)
    assert chosen is not None
    assert "no additional TMS domain filter configured" in select_reason, select_reason
    assert "same-origin as the established" in select_reason, select_reason


def test_every_refusal_reason_names_the_check_that_actually_ran():
    """A refusal whose reason is generic cannot be audited. Each hostile shape must be refused FOR
    the property it violates."""
    cases = [
        (EVIL + "/loads/101", "cross-origin"),
        ("//evil.example/loads/101", "cross-origin"),
        ("https://secure.tms.test@evil.example/x", "embedded credentials"),
        ("ftp://secure.tms.test/loads/101", "not an http(s) document fetch"),
        ("https://tms..test/loads/101", "malformed host"),
        ("javascript:alert(1)", "refused scheme"),
        ("", "empty navigation target"),
    ]
    for url, expected in cases:
        allowed, reason = navigation_target_is_allowed(url, None, established_origin=HOST)
        assert not allowed, f"{url!r} was allowed"
        assert expected in reason, f"{url!r} refused with the wrong reason: {reason!r}"


# ---------------------------------------------------------------- encoded off-origin redirects

@pytest.mark.parametrize("href", [
    "/loads/101?next=https://evil.example/steal",
    "/loads/101?return_to=//evil.example/steal",
    "/loads/101?u=javascript:alert(1)",
])
def test_an_off_origin_redirect_encoded_in_a_parameter_is_refused(href):
    """The navigation target itself is same-origin, so the origin check alone cannot see this. An
    absolute foreign URL riding in a query parameter is the ordinary open-redirect handoff."""
    _origin_corpus_is_real()
    chosen, reason = _select(_anchor("L-101", href, resolved=HOST + href))
    assert chosen is None, f"an encoded off-origin redirect was selected: {reason}"


def test_a_parameter_naming_the_established_origin_is_not_refused():
    """The rule targets FOREIGN targets, not absolute URLs as such — otherwise it would be a
    different guard wearing this one's name."""
    chosen, reason = _select(_anchor("L-101", "/loads/101?back=" + HOST + "/loads",
                                     resolved=HOST + "/loads/101?back=" + HOST + "/loads"))
    assert chosen is not None, reason


# ---------------------------------------------------------------- the destructive protections hold

def test_the_origin_policy_did_not_displace_the_destructive_link_protections():
    """F-02 item 8: these must all still refuse, ON THE ESTABLISHED ORIGIN, where the origin check
    passes and only the pre-existing barrier can refuse them."""
    hostile = [
        ("delete route",     _anchor("L-101", "/loads/101/delete")),
        ("purge route",      _anchor("L-101", "/loads/101/purge")),
        ("data-method",      _anchor("L-101", "/loads/101", attrs={"data-method": "delete"})),
        ("_method override", _anchor("L-101", "/loads/101?_method=delete")),
        ("base redirect",    _anchor("L-101", "/loads/101",
                                     resolved=HOST + "/loads/101/delete")),
        ("javascript:",      _anchor("L-101", "javascript:fetch('/x',{method:'POST'})")),
    ]
    _origin_corpus_is_real()
    for label, link in hostile:
        chosen, reason = _select(link)
        assert chosen is None, f"{label} was selected despite the origin policy: {reason}"


def test_the_origin_check_is_load_bearing_not_decorative():
    """FALSE-GREEN GUARD. If the origin decision were removed from select_load_detail_link, the
    cross-origin case would go green again. Prove the check is the thing refusing it: the SAME
    anchor, moved to the established origin, IS selected."""
    foreign = _anchor("L-101", EVIL + "/loads/L-101", resolved=EVIL + "/loads/L-101")
    native = _anchor("L-101", HOST + "/loads/L-101", resolved=HOST + "/loads/L-101")
    refused, _ = _select(foreign)
    admitted, why = _select(native)
    assert refused is None, "the cross-origin anchor was selected"
    assert admitted is not None, (
        f"the SAME anchor on the established origin was also refused ({why}) — the refusal above is "
        "not evidence about origin, it is some other barrier firing"
    )
