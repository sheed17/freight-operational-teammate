"""F2 — THE GENUINELY READ-ONLY CDP SURFACE (P4 adapter containment, R-07 scope).

The P4 containment checkpoint recorded finding F2 and deferred it: `cdp_session.evaluate()`,
`.command()` and `.set_file_input()` are actuation primitives, so the import gate's exemption of
`cdp_session` as a "read substrate" was not sound. A tool that only wants to LOOK at a TMS had to
hold an object that can type, click, upload and submit. "Read-only by convention" is not a
mechanism, and one edit away from a convention is not containment.

This module is the mechanism. It is the read substrate; `cdp_session` is not.

THREE INDEPENDENT BARRIERS, because any one of them alone is a convention:

  1. NO MUTATION API EXISTS HERE. There is no `evaluate`, no `command`, no `set_file_input`, no
     `navigate`, `click`, `type`, `select` or `upload_file`. A caller holding a
     `ReadOnlyCdpObserver` cannot express a mutation — not "must not", CANNOT.

  2. CALLER DATA IS NEVER CODE. Every observation runs a FIXED function declaration from the frozen
     registry below, and caller-supplied targets/selectors travel as `Runtime.callFunctionOn`
     `arguments` — JSON-encoded DATA the protocol hands to the function as a parameter. Nothing in
     this module concatenates, interpolates or formats caller input into JavaScript source. The
     older `SCRIPT + "(" + json.dumps(t) + ")"` shape was safe by escaping; this is safe by
     construction, and an AST guard proves no such concatenation returns.

  3. THE CHANNEL REFUSES ANYTHING ELSE. `_ReadOnlyChannel` allowlists the CDP methods it will send
     AND requires every `functionDeclaration` to be a member of `VETTED_READ_SCRIPTS` by exact
     value. An arbitrary script cannot be smuggled through the transport even by a caller that
     reaches the private channel: the transport rejects it before it is sent.

WRITE-CAPABLE CDP BEHAVIOUR IS NOT REMOVED AND NOT WEAKENED. It stays exactly where it was, in
`cdp_session.CdpBrowserSession` / `cdp_actuator.CdpActuator`, reachable only behind the authorized
adapter and effect boundary. This module does not import either of them — the dependency runs the
other way (the actuator imports these vetted scripts, so there is ONE source of truth for what the
read scripts do and the two surfaces cannot drift apart).

Honest scope: Python has no private state, so `observer._ReadOnlyCdpObserver__channel` is reachable
by a caller determined to subvert it. That is why barrier 3 exists (the channel still refuses) and
why the import gate proves the read-side CALLERS never reference an actuator at all. The claim made
here is not "unreachable by a hostile in-process attacker"; it is "a read-side caller cannot
actuate through this surface, cannot do so by accident, and cannot do so without an obvious,
guard-detected edit."
"""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.request
from pathlib import Path

import websocket  # websocket-client

from .browser_session_health import url_matches_filter


class ReadOnlyCdpError(RuntimeError):
    """A read-only session/observation failure, or a refused non-read operation."""


# --------------------------------------------------------------------------------------------
# The vetted read-only scripts. Each is a FUNCTION DECLARATION invoked via Runtime.callFunctionOn
# with caller data passed as `arguments`. None of them mutates the page: no click(), no focus(),
# no value assignment, no dispatchEvent, no form submission, no navigation.
# --------------------------------------------------------------------------------------------

OBSERVE_FN = r"""
function(){
  function vis(e){ return e && e.offsetParent!==null; }
  function clean(s){ return ((s||'').replace(/\s+/g,' ').trim()).trim(); }
  function txt(e){ return clean(e.innerText||e.value||e.getAttribute('aria-label')||e.getAttribute('title')||''); }
  function lbl(el){
    if(el.id){var l=document.querySelector('label[for="'+el.id+'"]'); if(l) return l.innerText.trim();}
    var p=el.closest('.form-group,.field,td,tr,div'); if(p){var ll=p.querySelector('label'); if(ll) return ll.innerText.trim();}
    return el.getAttribute('placeholder')||el.getAttribute('aria-label')||el.name||'';
  }
  var inputs=[...document.querySelectorAll('input,select,textarea')].filter(e=>e.type!=='hidden').slice(0,40)
    .map(e=>({kind:e.tagName.toLowerCase(), type:e.type||'', label:lbl(e).slice(0,40), name:e.name||'', value:(e.value||'').slice(0,40)}));
  var actionEls=[...document.querySelectorAll('button,a[href],[role=button],input[type=submit],input[type=button],[onclick]')].filter(vis);
  var actions=actionEls.map(e=>txt(e)).filter(Boolean).filter((v,i,a)=>a.indexOf(v)===i).slice(0,40);
  var interactive=inputs.map(function(i){ return {kind:i.kind, label:i.label, name:i.name, value:i.value}; })
    .concat(actions.map(function(a){ return {kind:'action', label:a}; })).slice(0,80);
  var navSeen={}, nav=[];
  [...document.querySelectorAll('a[href]')].forEach(function(a){
    var t=(a.innerText||'').trim(), h=a.getAttribute('href')||'';
    if(t && h && h.indexOf('#')!==0 && h.indexOf('javascript:')!==0 && !navSeen[h]){ navSeen[h]=1; nav.push({text:t.slice(0,40), url:h}); }
  });
  var errors=[...document.querySelectorAll('.alert-danger,.error,.invalid-feedback,.is-invalid,.field_with_errors')]
    .map(e=>e.innerText.trim()).filter(Boolean).slice(0,6);
  function rowActions(row){
    return [...row.querySelectorAll('a,button,[role=button],input[type=submit],input[type=button],[onclick]')]
      .filter(vis).map(e=>txt(e)).filter(Boolean).slice(0,8);
  }
  var tables=[...document.querySelectorAll('table')].filter(vis).slice(0,8).map(function(table){
    var headers=[...table.querySelectorAll('thead th, thead td, tr:first-child th')]
      .map(e=>clean(e.innerText)).filter(Boolean).slice(0,12);
    var rows=[...table.querySelectorAll('tbody tr, tr')].filter(vis).slice(0,20).map(function(row){
      var cells=[...row.children].map(e=>clean(e.innerText)).filter(Boolean).slice(0,12);
      return {text:clean(row.innerText).slice(0,240), cells:cells, actions:rowActions(row)};
    }).filter(r=>r.text);
    return {caption:clean((table.caption&&table.caption.innerText)||''), headers:headers, rows:rows};
  }).filter(t=>t.rows.length);
  var rowLike=[...document.querySelectorAll('[role=row],li,[class*=row],[class*=Row]')].filter(vis).slice(0,30)
    .map(function(row){ return {text:clean(row.innerText).slice(0,240), actions:rowActions(row)}; })
    .filter(r=>r.text && r.actions.length);
  var frames=[...document.querySelectorAll('iframe')].slice(0,10).map(function(f,i){
    var info={index:i, src:(f.getAttribute('src')||'').slice(0,120), accessible:false, actions:[], text:''};
    try{
      var d=f.contentDocument;
      if(d){
        info.accessible=true;
        info.actions=[...d.querySelectorAll('a,button,[role=button],input[type=submit],input[type=button]')]
          .map(e=>clean(e.innerText||e.value||'')).filter(Boolean).slice(0,20);
        info.text=clean(d.body ? d.body.innerText : '').slice(0,300);
      }
    }catch(e){ info.error=String(e).slice(0,80); }
    return info;
  });
  return {url:location.href, headings:[...document.querySelectorAll('h1,h2,h3')].map(e=>e.innerText.trim()).filter(Boolean).slice(0,6),
          inputs:inputs, actions:actions, interactive:interactive, nav:nav.slice(0,30), tables:tables,
          rows:rowLike, iframes:frames, body_text:clean(document.body ? document.body.innerText : '').slice(0,900),
          errors:errors};
}
"""


# Resolve an input/select/textarea by selector, label, placeholder, name or aria-label. READ ONLY:
# it returns the element, it never focuses, clicks or writes to it.
_FIND_INPUT_SRC = r"""
  function __findInput(t){
    function vis(e){ return e.offsetParent!==null && !e.disabled; }
    function pick(els){
      var tl=(t||'').toLowerCase();
      try{ var s=document.querySelector(t); if(s && /^(INPUT|SELECT|TEXTAREA)$/.test(s.tagName) && els.indexOf(s)>=0) return s; }catch(e){}
      for(var e of els){ if(e.id){var l=document.querySelector('label[for="'+e.id+'"]'); if(l && l.innerText.toLowerCase().indexOf(tl)>=0) return e; } }
      for(var e of els){ var hay=((e.getAttribute('placeholder')||'')+' '+(e.name||'')+' '+(e.getAttribute('aria-label')||'')).toLowerCase(); if(tl && hay.indexOf(tl)>=0) return e; }
      for(var e of els){ var p=e.closest('.form-group,.field,td,tr,div'); if(p){var ll=p.querySelector('label'); if(ll && ll.innerText.toLowerCase().indexOf(tl)>=0) return e; } }
      return null;
    }
    var all=[...document.querySelectorAll('input,select,textarea')].filter(e=>e.type!=='hidden');
    return pick(all.filter(vis)) || pick(all);
  }
"""

READ_FN = r"""
function(t){
""" + _FIND_INPUT_SRC + r"""
  function vis(e){return e && e.offsetParent!==null;}
  function clean(s){return ((s||'').replace(/\s+/g,' ').trim());}
  var needle=clean(t).toLowerCase();
  if(!needle) return '';
  try{ var inp=__findInput(t); if(inp){ var v=clean(inp.value!==undefined?inp.value:inp.innerText); if(v) return v; } }catch(e){}
  var cands=[...document.querySelectorAll('td,th,dd,dt,label,span,div,p,li,strong,b,h1,h2,h3')].filter(vis)
    .map(function(e){return {e:e, txt:clean(e.innerText)};})
    .filter(function(o){return o.txt && o.txt.length<=200 && o.txt.toLowerCase().indexOf(needle)>=0;})
    .sort(function(a,b){return a.txt.length-b.txt.length;});
  for(var i=0;i<cands.length;i++){
    var o=cands[i];
    if(/\d/.test(o.txt)) return o.txt.slice(0,160);
    var row=o.e.closest('tr'); if(row){var c=[...row.children].map(x=>clean(x.innerText)).filter(Boolean); if(c.length>1) return c.join(' | ').slice(0,160);}
    var sib=o.e.nextElementSibling; if(sib&&vis(sib)){var sv=clean(sib.innerText); if(sv) return (o.txt+': '+sv).slice(0,160);}
  }
  return '';
}
"""

MONEY_FIELDS_FN = r"""
function(){
  function vis(e){ return e.offsetParent!==null && !e.disabled; }
  function clean(s){ return ((s||'').replace(/\s+/g,' ').trim()); }
  var moneyRe=/(amount|price|total|charge|\brate\b|linehaul|line.haul|freight|settlement|balance|cost|payment|\bpay\b)/i;
  var out=[];
  document.querySelectorAll('input').forEach(function(e){
    if(['hidden','checkbox','radio','submit','button','image'].indexOf(e.type)>=0||!vis(e)) return;
    var lab='';
    if(e.id){var l=document.querySelector('label[for="'+e.id+'"]'); if(l) lab=l.innerText;}
    if(!lab){var p=e.closest('.form-group,.field,td,tr,div'); if(p){var ll=p.querySelector('label'); if(ll) lab=ll.innerText;}}
    var hay=(e.name||'')+' '+lab+' '+(e.getAttribute('placeholder')||'');
    if(!moneyRe.test(hay)) return;
    out.push({target:(e.name||clean(lab)||e.getAttribute('placeholder')||''), value:clean(e.value)});
  });
  return out;
}
"""

IS_SUBMIT_FN = r"""
function(t){
  function vis(e){ return e && e.offsetParent!==null; }
  function clean(s){ return ((s||'').replace(/\s+/g,' ').trim()).toLowerCase(); }
  function text(e){ return clean(e.innerText||e.value||e.getAttribute('aria-label')||e.getAttribute('title')||''); }
  function isSubmit(e){
    if(!e) return false;
    var tag=e.tagName, type=(e.getAttribute('type')||'').toLowerCase();
    if((tag==='INPUT'||tag==='BUTTON') && (type==='submit'||type==='image')) return true;
    if(tag==='BUTTON' && !type && e.closest('form')) return true;
    return false;
  }
  var el=null;
  try{ el=document.querySelector(t); }catch(e){}
  if(!el){
    var tl=clean(t);
    var CLICKABLE='a,button,[role=button],input[type=submit],input[type=button],[onclick]';
    var cs=[...document.querySelectorAll(CLICKABLE)].filter(vis);
    el=cs.find(function(e){return text(e)===tl;}) || cs.find(function(e){return text(e).indexOf(tl)>=0;});
  }
  return isSubmit(el);
}
"""

PAGE_SIGNATURE_FN = r"""
function(){
  return document.readyState+'|'+location.href+'|'+
    document.querySelectorAll('a,button,input,select,textarea,[role=button]').length;
}
"""

CURRENT_URL_FN = r"""
function(){ return location.href; }
"""


#: Exactly the scripts this surface may ever run. Membership is by VALUE, so a caller cannot pass a
#: lookalike, a superset, or a script with an appended payload.
VETTED_READ_SCRIPTS: frozenset[str] = frozenset(
    {OBSERVE_FN, READ_FN, MONEY_FIELDS_FN, IS_SUBMIT_FN, PAGE_SIGNATURE_FN, CURRENT_URL_FN}
)

#: The only CDP methods the read-only channel will transmit. `Runtime.evaluate` is deliberately
#: ABSENT: it is the arbitrary-JavaScript primitive, and admitting it would reinstate F2. That is
#: also why this surface binds scripts to an EXECUTION CONTEXT rather than to the global object —
#: the ordinary way to obtain the global is `Runtime.evaluate("window")`, and taking that shortcut
#: would have put the arbitrary-JavaScript primitive back on the allowlist to serve a bootstrap.
READ_ONLY_CDP_METHODS: frozenset[str] = frozenset(
    {"Page.enable", "Runtime.enable", "Runtime.callFunctionOn", "Page.captureScreenshot"}
)

#: Named here so a guard can assert they never appear on this surface.
FORBIDDEN_PRIMITIVES: tuple[str, ...] = (
    "evaluate", "command", "set_file_input", "navigate", "click", "click_row_action",
    "type", "select", "upload_file",
)


class _ReadOnlyChannel:
    """The transport. Refuses any CDP method or script outside the vetted sets — barrier 3.

    Holds the websocket privately. Every send is checked, so even a caller that reaches this object
    cannot transmit an actuation: the refusal happens here, before anything reaches the browser.
    """

    __slots__ = ("__weakref__", "_ws", "_id", "_timeout", "_events")

    def __init__(self, ws, timeout: int) -> None:
        self._ws = ws
        self._id = 0
        self._timeout = timeout
        self._events: list[dict] = []

    def send(self, method: str, params: dict | None = None) -> dict:
        if method not in READ_ONLY_CDP_METHODS:
            raise ReadOnlyCdpError(
                f"refused: {method!r} is not a read-only CDP method. This surface transmits only "
                f"{sorted(READ_ONLY_CDP_METHODS)}. Write-capable CDP lives behind the adapter and "
                "effect boundary (cdp_session.CdpBrowserSession), never here."
            )
        params = params or {}
        if method == "Runtime.callFunctionOn":
            declaration = params.get("functionDeclaration")
            if declaration not in VETTED_READ_SCRIPTS:
                raise ReadOnlyCdpError(
                    "refused: functionDeclaration is not one of the vetted read-only scripts. "
                    "Caller-supplied JavaScript cannot be executed through this surface."
                )
        if self._ws is None:
            raise ReadOnlyCdpError("read-only session is not connected")
        self._id += 1
        mid = self._id
        self._ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            msg = json.loads(self._ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise ReadOnlyCdpError(f"{method} failed: {msg['error']}")
                return msg
            if msg.get("method"):
                self._events.append(msg)

    def await_event(self, name: str, *, timeout: float = 5.0) -> dict | None:
        """Return the first buffered (or subsequently arriving) event called `name`.

        Events are protocol notifications, never a way to run anything; buffering them costs no
        authority. `Runtime.executionContextCreated` usually lands during `Runtime.enable`, so the
        buffer is normally already holding it.
        """
        for event in self._events:
            if event.get("method") == name:
                return event
        if self._ws is None:
            return None
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msg = json.loads(self._ws.recv())
            except (websocket.WebSocketException, OSError, ValueError):
                return None
            if msg.get("method"):
                self._events.append(msg)
                if msg.get("method") == name:
                    return msg
        return None

    def close(self) -> None:
        if self._ws is not None:
            try:
                self._ws.close()
            finally:
                self._ws = None


class ReadOnlyCdpObserver:
    """A CDP surface that can look at a page and nothing else.

    Every method here is an observation. There is no mutation primitive to call, no way to hand a
    caller an actuator, and no path by which caller data becomes executable JavaScript.
    """

    # `__channel`/`__context_id` are name-mangled by the compiler in __slots__ exactly as they are
    # in the method bodies, so the private state has no public alias to reach it by.
    __slots__ = ("__weakref__", "cdp_url", "url_filter", "timeout", "__channel", "__context_id")

    def __init__(
        self,
        *,
        cdp_url: str = "http://localhost:9222",
        url_filter: str | None = None,
        timeout: int = 20,
    ) -> None:
        self.cdp_url = cdp_url.rstrip("/")
        self.url_filter = url_filter
        self.timeout = timeout
        self.__channel: _ReadOnlyChannel | None = None
        self.__context_id: int | None = None

    # -- lifecycle ---------------------------------------------------------------------------

    def __enter__(self) -> "ReadOnlyCdpObserver":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def connect(self, *, attempts: int = 3) -> None:
        last: Exception | None = None
        for i in range(max(1, attempts)):
            try:
                self._connect_once()
                return
            except (websocket.WebSocketException, OSError, urllib.error.URLError) as exc:
                last = exc
                self.close()
                time.sleep(0.6 * (i + 1))
        raise ReadOnlyCdpError(
            f"could not connect read-only to CDP at {self.cdp_url} after {attempts} tries: {last}"
        )

    def _connect_once(self) -> None:
        tabs = json.load(urllib.request.urlopen(f"{self.cdp_url}/json", timeout=self.timeout))
        pages = [t for t in tabs if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
        if self.url_filter:
            pages = [t for t in pages if url_matches_filter(t.get("url") or "", self.url_filter)]
        if not pages:
            raise ReadOnlyCdpError(f"no attachable page tab at {self.cdp_url}")
        ws = websocket.create_connection(
            pages[0]["webSocketDebuggerUrl"], timeout=self.timeout, max_size=None,
            suppress_origin=True,
        )
        self.__channel = _ReadOnlyChannel(ws, self.timeout)
        self.__channel.send("Page.enable")
        self.__channel.send("Runtime.enable")
        event = self.__channel.await_event("Runtime.executionContextCreated", timeout=self.timeout)
        context = ((event or {}).get("params") or {}).get("context") or {}
        self.__context_id = context.get("id")
        if self.__context_id is None:
            raise ReadOnlyCdpError(
                "no execution context was announced; refusing to fall back to Runtime.evaluate "
                "(the arbitrary-JavaScript primitive this surface exists to exclude)"
            )

    def close(self) -> None:
        if self.__channel is not None:
            try:
                self.__channel.close()
            finally:
                self.__channel = None
                self.__context_id = None

    # -- the only way anything runs --------------------------------------------------------

    def _call(self, function_declaration: str, *args):
        """Run one VETTED script, passing caller data as protocol `arguments` — never as source.

        `Runtime.callFunctionOn` receives the arguments as JSON values and binds them to the
        function's parameters. The function body is a fixed constant; the caller's target is data
        the function reads. There is no string in this method into which caller input is spliced.
        """
        if self.__channel is None or self.__context_id is None:
            raise ReadOnlyCdpError("read-only session is not connected")
        result = self.__channel.send(
            "Runtime.callFunctionOn",
            {
                "functionDeclaration": function_declaration,
                "executionContextId": self.__context_id,
                "arguments": [{"value": a} for a in args],
                "returnByValue": True,
            },
        )
        return result.get("result", {}).get("result", {}).get("value")

    # -- observations ------------------------------------------------------------------------

    def observe(self) -> dict:
        """The full fixed page observation. No caller input at all."""
        return self._call(OBSERVE_FN) or {
            "url": "", "interactive": [], "errors": [], "headings": []
        }

    def read(self, target: str) -> str:
        """Read a displayed value or field value. `target` travels as DATA."""
        return self._call(READ_FN, str(target)) or ""

    def money_field_values(self) -> list[dict]:
        """Visible money-labelled inputs and their current values."""
        try:
            return self._call(MONEY_FIELDS_FN) or []
        except ReadOnlyCdpError:
            return []

    def is_submit_target(self, target: str) -> bool:
        """Would clicking this target submit a form? An observation, not a click."""
        try:
            return bool(self._call(IS_SUBMIT_FN, str(target)))
        except ReadOnlyCdpError:
            return False

    def page_signature(self) -> str:
        """readyState|url|control-count — for settle/stability polling without mutating."""
        return str(self._call(PAGE_SIGNATURE_FN) or "")

    def current_url(self) -> str:
        return str(self._call(CURRENT_URL_FN) or "")

    def capture_screenshot(self, path: str | Path, *, full_page: bool = False) -> str:
        """PNG to disk. Reading pixels is observation; it changes nothing in the page."""
        if self.__channel is None:
            raise ReadOnlyCdpError("read-only session is not connected")
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        result = self.__channel.send(
            "Page.captureScreenshot",
            {"format": "png", "captureBeyondViewport": bool(full_page)},
        )
        data = result.get("result", {}).get("data")
        if not data:
            raise ReadOnlyCdpError("Page.captureScreenshot returned no data")
        target.write_bytes(base64.b64decode(data))
        return str(target)


# =============================================================================================
# DOCUMENT NAVIGATION — the read-only traversal surface (P4 EP-3, R-07 scope).
#
# EP-3 reads a TMS loads list, then must open each load's DETAIL page to learn whether a POD is
# attached before any invoice button is posted. It previously did that with
# `cdp_session.evaluate("location.href=...")` — F2's exact defect, caller data interpolated into
# JavaScript source — with a `cdp_actuator.click(load_ref)` fallback.
#
# WHY NAVIGATION IS NOT A HOLE IN F2, stated as a reduction rather than a promise:
#
#   * A click DISPATCHES AN EVENT. On a SPA, an `onclick` handler can POST an invoice while being
#     no kind of form submit target, so no structural test on the element (tag, type, label,
#     selector, is_submit_target) can classify a click as safe. `Page.navigate` does not run that
#     handler at all — it is a document GET. Replacing the click with a navigation strictly REMOVES
#     reachable behaviour; it does not add any.
#   * `follow()` accepts only a URL THE PAGE ITSELF PUBLISHED as an `<a href>` in the observation it
#     is handed. A caller-composed target is refused, so the reachable set is exactly the links the
#     TMS rendered — the same set a human reading the page could click.
#   * Scheme and host are allowlisted. `javascript:`, `data:`, `file:` and `vbscript:` are refused
#     outright (a `javascript:` URL would be arbitrary-JavaScript execution wearing a URL's
#     clothing), and the target must stay on the configured TMS domain.
#   * There is still NO evaluate, command, click, type, select, upload or set_file_input here.
#
# This class COMPOSES `ReadOnlyCdpObserver` rather than extending it. The observer stays exactly
# what F2 certified — observation-only, with its own channel that cannot transmit `Page.navigate` —
# so nothing here widens that surface or invalidates its mutation proofs. A caller typed as an
# observer can never be a navigator.
# =============================================================================================

#: The only CDP methods the navigation transport will send. `Runtime.*` is absent entirely: this
#: channel runs no script of any kind, vetted or otherwise.
NAVIGATION_CDP_METHODS: frozenset[str] = frozenset({"Page.enable", "Page.navigate"})

#: Schemes that are code or local-resource access rather than a document fetch.
_REFUSED_SCHEMES: tuple[str, ...] = ("javascript:", "data:", "file:", "vbscript:", "blob:")


class _NavigationChannel:
    """Transport for document navigation ONLY — the navigator's barrier 3.

    Separate from `_ReadOnlyChannel` and deliberately narrower: it allowlists two methods and has
    no script-running path at all, so there is no script argument to smuggle a payload into.
    """

    __slots__ = ("__weakref__", "_ws", "_id", "_timeout")

    def __init__(self, ws, timeout: int) -> None:
        self._ws = ws
        self._id = 0
        self._timeout = timeout

    def send(self, method: str, params: dict | None = None) -> dict:
        if method not in NAVIGATION_CDP_METHODS:
            raise ReadOnlyCdpError(
                f"refused: {method!r} is not a navigation method. This surface transmits only "
                f"{sorted(NAVIGATION_CDP_METHODS)}. Actuation lives behind the adapter and effect "
                "boundary (cdp_session/cdp_actuator), never here."
            )
        if self._ws is None:
            raise ReadOnlyCdpError("navigation session is not connected")
        self._id += 1
        mid = self._id
        self._ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self._ws.recv())
            if msg.get("id") == mid:
                if "error" in msg:
                    raise ReadOnlyCdpError(f"{method} failed: {msg['error']}")
                return msg

    def close(self) -> None:
        if self._ws is not None:
            try:
                self._ws.close()
            finally:
                self._ws = None


def navigation_target_is_allowed(url: str, url_filter: str | None) -> tuple[bool, str]:
    """Is `url` a document this surface may fetch? Returns (allowed, reason).

    Pure and total, so the decision is unit-testable without a browser and the refusal reason is
    part of the contract rather than a log line.
    """
    u = (url or "").strip()
    if not u:
        return False, "empty navigation target"
    if u.lower().startswith(_REFUSED_SCHEMES):
        return False, f"refused scheme in {u[:60]!r} — that is code or local-resource access, not a document"
    if u[0] in "/?#":
        return True, "relative target stays on the current, already-allowed origin"
    if not url_matches_filter(u, url_filter):
        return False, f"{u[:80]!r} is not on the configured TMS domain ({url_filter!r})"
    return True, "on the TMS domain allowlist"


class ReadOnlyCdpNavigator:
    """Observation plus DOCUMENT NAVIGATION — and nothing else.

    Reading is delegated in full to a contained `ReadOnlyCdpObserver`, so every observation still
    runs a vetted script over that observer's own channel. This class adds exactly one capability:
    fetching a document. See the module section above for why that is a reduction in reachable
    behaviour rather than a widening of F2.
    """

    __slots__ = ("__weakref__", "cdp_url", "url_filter", "timeout", "settle_seconds",
                 "observer", "__channel")

    def __init__(
        self,
        *,
        cdp_url: str = "http://localhost:9222",
        url_filter: str | None = None,
        timeout: int = 20,
        settle_seconds: float = 2.5,
    ) -> None:
        self.cdp_url = cdp_url.rstrip("/")
        self.url_filter = url_filter
        self.timeout = timeout
        self.settle_seconds = settle_seconds
        self.observer = ReadOnlyCdpObserver(cdp_url=cdp_url, url_filter=url_filter, timeout=timeout)
        self.__channel: _NavigationChannel | None = None

    # -- lifecycle ---------------------------------------------------------------------------

    def __enter__(self) -> "ReadOnlyCdpNavigator":
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def connect(self, *, attempts: int = 3) -> None:
        self.observer.connect(attempts=attempts)
        last: Exception | None = None
        for i in range(max(1, attempts)):
            try:
                self._connect_once()
                return
            except (websocket.WebSocketException, OSError, urllib.error.URLError) as exc:
                last = exc
                time.sleep(0.6 * (i + 1))
        self.close()
        raise ReadOnlyCdpError(
            f"could not open a navigation channel to CDP at {self.cdp_url}: {last}"
        )

    def _connect_once(self) -> None:
        tabs = json.load(urllib.request.urlopen(f"{self.cdp_url}/json", timeout=self.timeout))
        pages = [t for t in tabs if t.get("type") == "page" and t.get("webSocketDebuggerUrl")]
        if self.url_filter:
            pages = [t for t in pages if url_matches_filter(t.get("url") or "", self.url_filter)]
        if not pages:
            raise ReadOnlyCdpError(f"no attachable page tab at {self.cdp_url}")
        ws = websocket.create_connection(
            pages[0]["webSocketDebuggerUrl"], timeout=self.timeout, max_size=None,
            suppress_origin=True,
        )
        self.__channel = _NavigationChannel(ws, self.timeout)
        self.__channel.send("Page.enable")

    def close(self) -> None:
        try:
            if self.__channel is not None:
                self.__channel.close()
        finally:
            self.__channel = None
            self.observer.close()

    # -- observation (delegated, unchanged) ---------------------------------------------------

    def observe(self) -> dict:
        return self.observer.observe()

    def read(self, target: str) -> str:
        return self.observer.read(target)

    def current_url(self) -> str:
        return self.observer.current_url()

    def page_signature(self) -> str:
        return self.observer.page_signature()

    # -- the one added capability -------------------------------------------------------------

    def visit(self, url: str) -> bool:
        """Fetch an OPERATOR-CONFIGURED entry document (e.g. the loads page from `--loads-url`).

        Scheme- and host-checked. This is the only entry by a target the page did not itself
        publish, because a run has to start somewhere; it is configuration, never model output.
        """
        return self._navigate(url, origin="operator-configured entry URL")

    def follow(self, observation: dict | None, url: str) -> bool:
        """Fetch a document THE PAGE ITSELF published as an `<a href>` in `observation`.

        The target is checked for membership in the observation's own `nav` set, so a caller cannot
        compose a URL the TMS never rendered. This is the traversal EP-3 needs, and it is strictly
        narrower than clicking: no `onclick` handler runs.
        """
        published = {str(n.get("url") or "") for n in ((observation or {}).get("nav") or [])
                     if isinstance(n, dict)}
        if url not in published or not str(url).strip():
            raise ReadOnlyCdpError(
                f"refused: {str(url)[:80]!r} was not published as a link by the observed page. This "
                "surface follows only links the page rendered; it does not accept a composed target."
            )
        return self._navigate(url, origin="page-published link")

    def _navigate(self, url: str, *, origin: str) -> bool:
        allowed, reason = navigation_target_is_allowed(url, self.url_filter)
        if not allowed:
            raise ReadOnlyCdpError(f"refused navigation ({origin}): {reason}")
        if self.__channel is None:
            raise ReadOnlyCdpError("navigation session is not connected")
        self.__channel.send("Page.navigate", {"url": url})
        time.sleep(self.settle_seconds)
        return True
