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
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

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


# The PROVENANCE observation (EP-3). Given a load identifier as DATA, it reports the leaf rows whose
# own CELLS carry that identifier, and — for each such row — the anchors THAT ROW contains, with the
# attributes needed to tell a plain document link from an action control. It reads structure; it
# clicks nothing, focuses nothing and submits nothing.
#
# Why the DOM does the binding: a document-wide `nav` list says a link exists SOMEWHERE on the page.
# It cannot say the link belongs to the load being billed. Row containment is the page's own
# statement of that relationship, and it is the relationship EP-3 has to rely on.
LOAD_ROW_LINKS_FN = r"""
function(loadId){
  function clean(s){ return ((s||'').replace(/\s+/g,' ').trim()); }
  function norm(s){ return clean(s).toLowerCase(); }
  var needle = norm(loadId);
  if(!needle) return {load_id:'', rows:[]};
  function cellMatch(t){
    var c = norm(t);
    if(c === needle) return 'cell-exact';
    var toks = c.split(/[^a-z0-9._-]+/).filter(Boolean);
    return toks.indexOf(needle) >= 0 ? 'cell-token' : '';
  }
  var ATTRS = ['data-method','data-turbo-method','data-remote','data-confirm','data-turbo-confirm',
               'onclick','role','download','aria-haspopup','formaction'];
  function anchorInfo(a){
    var attrs = {};
    for (var i=0;i<ATTRS.length;i++){
      var v = a.getAttribute(ATTRS[i]);
      if (v !== null) attrs[ATTRS[i]] = String(v).slice(0,60);
    }
    var menu = null;
    try { menu = a.closest('[role=menu],[role=menubar],[role=menuitem],.dropdown-menu,.action-menu'); } catch(e){}
    return {
      text: clean(a.innerText || a.getAttribute('aria-label') || a.getAttribute('title') || '').slice(0,80),
      href: String(a.getAttribute('href') || '').slice(0,400),
      resolved: String(a.href || '').slice(0,400),
      attrs: attrs,
      in_menu: !!menu
    };
  }
  var out = [];
  var rows = [...document.querySelectorAll('tr,[role=row]')];
  for (var r=0; r<rows.length && out.length<12; r++){
    var row = rows[r];
    if (row.querySelector('tr,[role=row]')) continue;      // only leaf rows carry one record
    var cells = [...row.children].map(function(e){ return clean(e.innerText); });
    var kind = '';
    for (var c=0;c<cells.length;c++){ var k = cellMatch(cells[c]); if(k && !kind) kind = k; }
    if(!kind) continue;
    out.push({
      index: r,
      match: kind,
      cells: cells.slice(0,16).map(function(t){ return t.slice(0,120); }),
      links: [...row.querySelectorAll('a[href]')].slice(0,20).map(anchorInfo)
    });
  }
  return {load_id: clean(loadId), rows: out};
}
"""


#: Exactly the scripts this surface may ever run. Membership is by VALUE, so a caller cannot pass a
#: lookalike, a superset, or a script with an appended payload.
VETTED_READ_SCRIPTS: frozenset[str] = frozenset(
    {OBSERVE_FN, READ_FN, MONEY_FIELDS_FN, IS_SUBMIT_FN, PAGE_SIGNATURE_FN, CURRENT_URL_FN,
     LOAD_ROW_LINKS_FN}
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

    def load_row_links(self, load_id: str) -> dict:
        """Rows whose own cells carry `load_id`, and the anchors each such row contains.

        The provenance observation EP-3 binds navigation to. `load_id` travels as DATA, like every
        other target on this surface. Returning structure is not a capability: nothing here can act
        on what it found.
        """
        payload = self._call(LOAD_ROW_LINKS_FN, str(load_id))
        return payload if isinstance(payload, dict) else {"load_id": str(load_id), "rows": []}

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

# ---------------------------------------------------------------------------------------------
# THE HOSTILE PREMISE THIS SECTION ANSWERS (EP-3 review obligation).
#
# "A same-origin, page-published href is not inherently read-only." That is correct, and it is why
# membership in the page's document-wide link list is NOT sufficient authority to fetch a document.
# Legacy freight systems routinely expose state-changing GET routes: `/loads/101/delete`,
# `/invoices/9/approve`, `/logout`, and Rails-style `<a href="/loads/101" data-method="delete">`,
# which looks like a plain link and issues a DELETE. A generic follower of any observed anchor would
# reach all of them.
#
# So navigation is bound to a STRUCTURED PROVENANCE RECORD rather than to a URL. Four independent
# barriers, each of which alone would be a convention:
#
#   1. ROW PROVENANCE. The target must be an anchor contained by the one observed ROW whose own
#      CELLS carry the load identifier. A link from a different row, a page-level nav link, an
#      unrelated export, or a link the page never rendered is not in the candidate set at all —
#      it is not reachable by composing a string, because the candidate set is read from the DOM.
#   2. IDENTITY BINDING. Among that row's anchors, the target must be identified BY THE LOAD: its
#      visible text equals the load identifier exactly, or the identifier appears as a whole PATH
#      SEGMENT of its href. Both are exact matches on a delimited token. No substring test decides
#      anything here — `L-10` must not select `L-104`, and "Delete L-101" must not select by
#      containing "L-101".
#   3. ROUTE FAMILY. The href's path may carry no consequential action token, its query may carry
#      no destructive token or method-override key, and BOTH the raw attribute and the browser's
#      resolved URL must pass (so a `<base>` tag cannot make a benign-looking attribute resolve
#      somewhere else).
#   4. ANCHOR SHAPE. The anchor must be a plain document link: no `data-method`/`data-turbo-method`
#      other than GET, no `data-confirm`, no `onclick`, no `download`, no `role=button`/`menuitem`,
#      no `aria-haspopup`, and not inside an action menu.
#
# Then, at follow time, the record is re-derived from the live page and must match EXACTLY, and the
# observation context must be the current one — so a forged, composed, lookalike or stale record is
# refused even if it was well-formed. After the fetch, the landed URL is re-checked, so a redirect
# out of the observational route family fails closed rather than being observed as if it were fine.
#
# None of this reopens F2: there is still no evaluate, no command, no click, no caller-authored
# JavaScript and no generic traversal method anywhere on this surface.
# ---------------------------------------------------------------------------------------------

#: Whole PATH segments that name a consequential action rather than a record to look at. Matched as
#: delimited tokens, never as substrings.
ACTION_ROUTE_TOKENS: frozenset[str] = frozenset({
    "logout", "signout", "logoff", "login", "signin", "session", "sessions",
    "delete", "destroy", "remove", "drop", "purge", "cancel", "void", "reverse", "revoke",
    "approve", "approval", "release", "reject", "deny",
    "pay", "payment", "payments", "settle", "settlement", "remit", "transfer", "refund",
    "invoice", "invoices", "bill", "billing", "charge", "charges",
    "submit", "post", "send", "email", "mail", "notify", "dispatch",
    "create", "new", "edit", "update", "upsert", "upload", "import", "merge", "clone", "duplicate",
    "archive", "unarchive", "restore", "close", "reopen", "complete", "finalize",
    "confirm", "execute", "run", "apply", "perform", "trigger",
    "assign", "unassign", "activate", "deactivate", "disable", "enable",
    "export", "download",
})

#: Query tokens (keys or values) that mark a consequential request even on an innocuous path.
DESTRUCTIVE_QUERY_TOKENS: frozenset[str] = frozenset({
    "delete", "destroy", "remove", "cancel", "void", "approve", "release", "pay", "submit",
    "confirm", "execute", "logout", "signout", "archive", "send", "post", "put", "patch",
})

#: Query KEYS that let a GET declare a different HTTP verb or a server-side command.
METHOD_OVERRIDE_KEYS: frozenset[str] = frozenset({"_method", "method", "action", "do", "cmd", "op", "verb"})

#: Anchor attributes whose mere presence means the element is not a plain document link.
UNSAFE_ANCHOR_ATTRS: tuple[str, ...] = (
    "onclick", "data-confirm", "data-turbo-confirm", "data-remote", "download", "formaction",
)

#: `role` values that make an anchor a control rather than a link.
_CONTROL_ROLES: frozenset[str] = frozenset({"button", "menuitem", "menuitemcheckbox", "tab", "switch"})

_TOKEN_SPLIT = re.compile(r"[^A-Za-z0-9]+")


def _tokens(text: object) -> set[str]:
    """Lowercased, delimiter-split tokens. Substring containment never decides anything."""
    return {t for t in _TOKEN_SPLIT.split(str(text or "").lower()) if t}


def _is_action_token(token: str, vocabulary: frozenset[str]) -> bool:
    """Whole-token membership, with a plural collapsed to its singular.

    `/exports/all` and `/export/all` are the same route family, and a vocabulary that caught only
    one of them would be a spelling test rather than a guard. This stays a WHOLE-TOKEN rule: the
    plural fold is applied to a complete delimiter-bounded token, never to a substring, so
    `undeleted` still does not match `delete`.
    """
    if token in vocabulary:
        return True
    return len(token) > 3 and token.endswith("s") and token[:-1] in vocabulary


def _norm(text: object) -> str:
    return " ".join(str(text or "").split()).strip().lower()


def _path_segments(href: object) -> list[str]:
    return [s for s in urlsplit(str(href or "")).path.split("/") if s]


def scheme_refusal_reason(href: str) -> str:
    """"" when `href`'s scheme is an ordinary document fetch, else the reason it is refused.

    TWO DELIBERATELY OVERLAPPING RULES, expressed as ONE decision:

      * a DENYLIST of schemes that are code or local-resource access (`javascript:`, `data:`,
        `file:`, `vbscript:`, `blob:`), and
      * a positive ALLOWLIST of `http`/`https`, which refuses any scheme nobody anticipated.

    Either rule alone already refuses `javascript:`. That redundancy is intentional — a scheme the
    denylist never heard of is still refused — but it also means removing ONE of them reintroduces
    no defect and proves nothing. They live in one function so the mutation battery can remove the
    whole decision at once and see the guard fire (B30a); a mutant that cannot reintroduce a defect
    is not evidence, it is decoration.
    """
    u = str(href or "").strip()
    if u.lower().startswith(_REFUSED_SCHEMES):
        return f"refused scheme in {u[:60]!r} — that is code or local-resource access, not a document"
    scheme = urlsplit(u).scheme
    if scheme and scheme.lower() not in ("http", "https"):
        return f"scheme {scheme!r} is not a document fetch"
    return ""


def href_route_is_observational(href: str) -> tuple[bool, str]:
    """Is `href` a route that LOOKS AT a record, rather than one that acts on it? (allowed, reason).

    Pure and total, so the classification is unit-testable without a browser and every refusal
    reason is part of the contract. Fails closed: an href it cannot parse or classify is refused,
    and a refusal only ever costs a POD read — which blocks the money button, the safe direction.
    """
    u = str(href or "").strip()
    if not u:
        return False, "empty href"
    try:
        refusal = scheme_refusal_reason(u)
    except ValueError as exc:
        return False, f"unparseable href {u[:60]!r}: {exc}"
    if refusal:
        return False, refusal
    if u.startswith("#"):
        return False, "fragment-only target addresses no document"
    parts = urlsplit(u)
    segments = _path_segments(u)
    if not segments:
        return False, f"{u[:60]!r} addresses no path — it is not a load detail document"
    path_tokens: set[str] = set()
    for segment in segments:
        path_tokens |= _tokens(segment)
    hits = sorted(t for t in path_tokens if _is_action_token(t, ACTION_ROUTE_TOKENS))
    if hits:
        return False, (
            f"route {u[:80]!r} carries consequential action token(s) {hits} — a same-origin GET is "
            "not evidence of read-only behaviour, so an action-shaped route is refused"
        )
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if _norm(key) in METHOD_OVERRIDE_KEYS:
            return False, (
                f"query parameter {key!r} can declare a different HTTP verb or a server-side "
                "command — refused"
            )
        bad = sorted(t for t in (_tokens(key) | _tokens(value))
                     if _is_action_token(t, DESTRUCTIVE_QUERY_TOKENS))
        if bad:
            return False, f"query carries consequential token(s) {bad}"
    return True, "observational route family"


def anchor_is_plain_document_link(link: dict) -> tuple[bool, str]:
    """Is this anchor a plain link, or an action control wearing an `<a href>`? (allowed, reason).

    The case that motivates it: `<a href="/loads/101" data-method="delete">Delete</a>` is a link by
    tag, a DELETE by behaviour, and indistinguishable from a detail link by URL alone.
    """
    attrs = {str(k).strip().lower(): str(v) for k, v in ((link or {}).get("attrs") or {}).items()}
    for name in UNSAFE_ANCHOR_ATTRS:
        if name in attrs:
            return False, f"anchor carries {name!r} — an action control, not a plain document link"
    for name in ("data-method", "data-turbo-method"):
        if name in attrs and _norm(attrs[name]) not in ("", "get"):
            return False, (
                f"anchor declares {name}={attrs[name]!r} — following it would issue a "
                f"{attrs[name].upper()} request, not a document GET"
            )
    role = _norm(attrs.get("role", ""))
    if role in _CONTROL_ROLES:
        return False, f"anchor declares role={role!r} — it is a control, not a link"
    if "aria-haspopup" in attrs:
        return False, "anchor opens a menu — it is an action-menu trigger"
    if (link or {}).get("in_menu"):
        return False, "anchor lives inside an action menu"
    return True, "plain document link"


@dataclass(frozen=True)
class ObservedLoadLink:
    """Structured provenance for ONE load-detail navigation.

    Carries the whole relationship the page asserted — which row, which load identity, which exact
    href, and in which observation context — because any one of those alone can be forged or can go
    stale. It is a value object with no authority of its own: presenting one proves nothing, since
    `follow()` re-derives the authorized record from the live page and demands an exact match.
    """

    load_id: str
    href: str
    resolved_href: str
    row_index: int
    row_cells: tuple[str, ...]
    link_text: str
    bound_by: str          # "link-text" | "path-segment" — WHICH identity binding admitted it
    context_seq: int       # the navigator's observation context this was minted in


def select_load_detail_link(
    payload: dict | None, load_id: str, *, context_seq: int
) -> tuple[ObservedLoadLink | None, str]:
    """Choose the one provenance-bound detail link for `load_id`, or refuse with a reason.

    Pure: it decides from an observation payload, so every hostile case (an action-menu row, a
    sibling row, a lookalike identifier, a `data-method` anchor, a redirect-shaped route) is
    unit-testable with no browser at all. Ambiguity is a REFUSAL, never a pick — if the page offers
    two different documents for one load, this surface does not get to guess which one is safe.
    """
    lid = _norm(load_id)
    if not lid:
        return None, "no load identifier was supplied"
    rows = list((payload or {}).get("rows") or [])
    if not rows:
        return None, f"the observed page published no row whose cells carry {load_id!r}"
    if len(rows) > 1:
        return None, (
            f"{load_id!r} matched {len(rows)} rows — ambiguous provenance, so no row can be said to "
            "be THE row for this load"
        )
    row = rows[0] or {}
    candidates: list[ObservedLoadLink] = []
    last_reason = "the load's row published no plain, identity-bound, observational link"
    for link in list(row.get("links") or []):
        if not isinstance(link, dict):
            continue
        href = str(link.get("href") or "").strip()
        resolved = str(link.get("resolved") or "").strip()
        ok, reason = anchor_is_plain_document_link(link)
        if not ok:
            last_reason = reason
            continue
        ok, reason = href_route_is_observational(href)
        if not ok:
            last_reason = reason
            continue
        if resolved:
            # The attribute is what the page WROTE; `resolved` is the absolute URL the browser would
            # actually fetch (a `<base>` tag can make those differ). BOTH are classified, and the
            # navigator fetches the resolved one, so the URL that is checked is the URL that is used.
            ok, reason = href_route_is_observational(resolved)
            if not ok:
                last_reason = f"the anchor's href {href!r} resolves to {resolved!r}, which is refused ({reason})"
                continue
        text_bound = _norm(link.get("text")) == lid
        segments = {_norm(s) for s in _path_segments(href)} | {_norm(s) for s in _path_segments(resolved)}
        path_bound = lid in segments
        if not (text_bound or path_bound):
            last_reason = (
                f"anchor {str(link.get('text'))[:40]!r} -> {href[:60]!r} is in the load's row but is "
                "not identified BY the load (its text is not the load identifier and the identifier "
                "is not a path segment) — row containment alone is not provenance"
            )
            continue
        candidates.append(ObservedLoadLink(
            load_id=str(load_id),
            href=href,
            resolved_href=resolved,
            row_index=int(row.get("index") or 0),
            row_cells=tuple(str(c) for c in (row.get("cells") or [])),
            link_text=str(link.get("text") or ""),
            bound_by="link-text" if text_bound else "path-segment",
            context_seq=int(context_seq),
        ))
    if not candidates:
        return None, last_reason
    preferred = [c for c in candidates if c.bound_by == "link-text"] or candidates
    distinct = {c.href for c in preferred}
    if len(distinct) > 1:
        return None, (
            f"the load's row publishes {len(distinct)} different identity-bound documents "
            f"({sorted(distinct)[:3]}) — ambiguous, so none is followed"
        )
    return preferred[0], "provenance-bound load-detail link"


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
                 "observer", "__channel", "__context_seq", "last_refusal")

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
        # Bumped by every successful fetch. A provenance record minted against an earlier document
        # is STALE by construction, so it cannot be replayed after the page underneath it changed.
        self.__context_seq: int = 0
        self.last_refusal: str = ""

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

    @property
    def context_seq(self) -> int:
        """The current observation context. Every successful fetch advances it."""
        return self.__context_seq

    def detail_link_for_load(self, load_id: str) -> ObservedLoadLink | None:
        """Mint the provenance record for ONE load's detail document, or None with a recorded reason.

        Returning None is the ordinary outcome for every hostile shape — an action-menu anchor, a
        `data-method="delete"` link, a sibling row's href, an ambiguous identifier — and the caller
        treats it as "POD unknown", which blocks the money path. There is no variant of this method
        that returns a link for a route it could not bind.
        """
        payload = self.observer.load_row_links(str(load_id))
        link, reason = select_load_detail_link(payload, load_id, context_seq=self.__context_seq)
        self.last_refusal = "" if link is not None else reason
        return link

    def follow(self, link: ObservedLoadLink) -> bool:
        """Fetch the load-detail document named by a provenance record minted from the CURRENT page.

        A URL is not accepted here, and neither is a record on its own: the authorized record is
        RE-DERIVED from the live page and must match exactly. So a forged, composed, lookalike or
        stale record is refused even when it is well-formed, and a record that was legitimate before
        the document changed underneath it is refused as stale.
        """
        if not isinstance(link, ObservedLoadLink):
            raise ReadOnlyCdpError(
                "refused: follow() takes an ObservedLoadLink minted by detail_link_for_load(), not "
                f"a {type(link).__name__}. This surface has no generic 'follow any observed link' "
                "capability: a same-origin, page-published href is not evidence of read-only "
                "behaviour, so navigation is bound to an observed row and load identity."
            )
        if link.context_seq != self.__context_seq:
            raise ReadOnlyCdpError(
                f"refused: stale provenance — the record was minted in observation context "
                f"{link.context_seq}, and the current context is {self.__context_seq}. The document "
                "it was derived from is no longer the document on screen."
            )
        current, reason = select_load_detail_link(
            self.observer.load_row_links(link.load_id), link.load_id, context_seq=self.__context_seq
        )
        if current is None:
            raise ReadOnlyCdpError(
                f"refused: the page publishes no provenance-bound detail link for "
                f"{link.load_id!r} ({reason})"
            )
        if current != link:
            raise ReadOnlyCdpError(
                "refused: the presented record does not match the record the page currently "
                "publishes for that load — forged, composed, lookalike or stale provenance."
            )
        # Fetch the URL the browser itself resolved, so the target that was CLASSIFIED is the target
        # that is FETCHED even if the document carries a `<base>` tag.
        target = link.resolved_href or link.href
        followed = self._navigate(target, origin="provenance-bound load-detail link")
        landed = self.current_url()
        if landed:
            allowed, why = navigation_target_is_allowed(landed, self.url_filter)
            if not allowed:
                raise ReadOnlyCdpError(f"refused after navigation: landed on {landed[:80]!r} — {why}")
            observational, why = href_route_is_observational(landed)
            if not observational:
                raise ReadOnlyCdpError(
                    f"redirected out of the observational route family: {landed[:80]!r} — {why}"
                )
        return followed

    def _navigate(self, url: str, *, origin: str) -> bool:
        allowed, reason = navigation_target_is_allowed(url, self.url_filter)
        if not allowed:
            raise ReadOnlyCdpError(f"refused navigation ({origin}): {reason}")
        observational, why = href_route_is_observational(url)
        if not observational:
            raise ReadOnlyCdpError(f"refused navigation ({origin}): {why}")
        if self.__channel is None:
            raise ReadOnlyCdpError("navigation session is not connected")
        self.__channel.send("Page.navigate", {"url": url})
        self.__context_seq += 1
        time.sleep(self.settle_seconds)
        return True
