"""The real Actuator: gives the embedded Operator Agent human-like hands on a live browser via CDP.

Implements the ``Actuator`` protocol (observe/navigate/click/type/select/read) the agent loop drives.
The critical capability over plain value-setting is **real keyboard input** via the CDP Input domain
(focus the field, select its contents, ``Input.insertText``), which is what makes JS-SPA TMSs like
transporters.io actually register a typed value — the wall hand-driving hit. Elements are resolved by
label / placeholder / name / button text (or a raw CSS selector), so the agent can refer to fields the
way a human would ("Customer name", "Total Charge", "Save").
"""

from __future__ import annotations

import json
import time

from freight_recon.cdp_session import CdpBrowserSession, CdpError

# F2: the READ scripts have ONE source of truth, and it is the read-only surface. This module is
# write-capable and may import from the read-only one; the reverse is forbidden and guarded, so the
# two surfaces cannot observe the page differently and drift apart.
from freight_recon.cdp_readonly import (
    IS_SUBMIT_FN,
    MONEY_FIELDS_FN,
    OBSERVE_FN,
    READ_FN,
)

_OBSERVE_JS = "(" + OBSERVE_FN + ")()"
_MONEY_FIELDS_JS = "(" + MONEY_FIELDS_FN + ")()"
_IS_SUBMIT_JS = "(" + IS_SUBMIT_FN + ")"
_READ_JS = "(" + READ_FN + ")"

# Shared JS: resolve an input/select/textarea by selector, label, placeholder, name, or aria-label.
_FIND_INPUT = r"""
function __findInput(t){
  // Prefer VISIBLE, interactable fields — never a hidden template/computed mirror field (the
  // transporters.io trap: a hidden unit_price shadowing the visible order_row_price).
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
  return pick(all.filter(vis)) || pick(all);  // visible first, hidden only as fallback
}
"""


# Universal click resolver: click the element that reads like `t`, wherever it lives — a button, link,
# menu/option, or a TABLE ROW / list item / cell (the common "open this record" case that a
# buttons-only resolver misses). Tries a raw selector, then a clickable element whose own text matches
# (exact before contains), then any visible leaf containing the text walked UP to its nearest clickable
# ancestor or its row. Nothing here is TMS-specific — it's generic DOM interaction.
_CLICK_JS = r"""
(function(t){
  function vis(e){ return e && e.offsetParent!==null; }
  function fire(e){ if(!e) return false; e.scrollIntoView({block:'center'}); e.click(); return true; }
  function clean(s){ return ((s||'').replace(/\s+/g,' ').trim()).toLowerCase(); }
  function text(e){ return clean(e.innerText||e.value||e.getAttribute('aria-label')||e.getAttribute('title')||''); }
  function clickRowAction(rowNeedle, actionNeedle){
    var rn=clean(rowNeedle), an=clean(actionNeedle);
    if(!rn || !an) return false;
    var CLICKABLE='a,button,[role=button],[role=link],[role=option],[role=menuitem],[role=tab],'
      +'input[type=submit],input[type=button],[onclick],summary,label';
    var rows=[...document.querySelectorAll('tr,[role=row],li,[class*=row],[class*=Row]')].filter(vis);
    var row=rows.find(function(r){ return text(r).indexOf(rn)>=0; });
    if(!row) return false;
    var actions=[...row.querySelectorAll(CLICKABLE)].filter(vis);
    var exact=actions.find(function(a){ return text(a)===an; });
    if(exact) return fire(exact);
    var contains=actions.find(function(a){ return text(a).indexOf(an)>=0; });
    if(contains) return fire(contains);
    return false;
  }
  try{ var s=document.querySelector(t); if(s) return fire(s); }catch(e){}
  var arrow=(t||'').split(/\s*(?:->|=>|::)\s*/);
  if(arrow.length>=2 && clickRowAction(arrow[0], arrow.slice(1).join(' -> '))) return true;
  var tl=clean(t);
  if(!tl) return false;
  var CLICKABLE='a,button,[role=button],[role=link],[role=option],[role=menuitem],[role=tab],[role=row],'
    +'input[type=submit],input[type=button],[onclick],summary,label';
  var clickables=[...document.querySelectorAll(CLICKABLE)].filter(vis);
  var exact=clickables.find(function(e){ return text(e)===tl; });
  if(exact) return fire(exact);
  var contains=clickables.find(function(e){ return text(e).indexOf(tl)>=0; });
  if(contains) return fire(contains);
  // Text lives in a non-clickable node (e.g. a cell in a row): find the smallest leaf that contains it,
  // then click the nearest clickable ancestor, else the enclosing row/list item.
  var leaves=[...document.querySelectorAll('body *')].filter(function(e){
    return vis(e) && e.children.length===0 && (e.innerText||'').trim().toLowerCase().indexOf(tl)>=0;
  });
  if(leaves.length){
    var leaf=leaves[0];
    var host=leaf.closest(CLICKABLE)
      || leaf.closest('tr,li,[role=row],[class*=row],[class*=Row],[class*=item],[class*=Item]') || leaf;
    return fire(host);
  }
  return false;
})
"""


_CLICK_ROW_ACTION_JS = r"""
(function(rowNeedle, actionNeedle){
  function vis(e){ return e && e.offsetParent!==null; }
  function fire(e){ if(!e) return false; e.scrollIntoView({block:'center'}); e.click(); return true; }
  function clean(s){ return ((s||'').replace(/\s+/g,' ').trim()).toLowerCase(); }
  function text(e){ return clean(e.innerText||e.value||e.getAttribute('aria-label')||e.getAttribute('title')||''); }
  var rn=clean(rowNeedle), an=clean(actionNeedle);
  if(!rn || !an) return false;
  var rows=[...document.querySelectorAll('tr,[role=row],li,[class*=row],[class*=Row]')].filter(vis);
  var row=rows.find(function(r){ return text(r).indexOf(rn)>=0; });
  if(!row) return false;
  var CLICKABLE='a,button,[role=button],[role=link],[role=option],[role=menuitem],[role=tab],'
    +'input[type=submit],input[type=button],[onclick],summary,label';
  var actions=[...row.querySelectorAll(CLICKABLE)].filter(vis);
  var exact=actions.find(function(a){ return text(a)===an; });
  if(exact) return fire(exact);
  var contains=actions.find(function(a){ return text(a).indexOf(an)>=0; });
  if(contains) return fire(contains);
  return false;
})
"""


# Would clicking this target SUBMIT a form (i.e. commit)? Resolves the same element CLICK would, then
# reports whether it is a submit control. This is the label-independent commit signal: a row action
# like an <a> "Create Invoice" that OPENS a form is not a submit, while the form's "Create Invoice"
# submit button is — so the same visible text is gated in one place and not the other, correctly.


# Money-labelled visible text inputs and their current values — so the runtime can reconcile a
# DEFAULTED amount (a TMS that pre-fills the payment/invoice amount) against the human-approved amount
# before committing. Returns the field NAME as ``target`` (which __findInput resolves).


class CdpActuator:
    def __init__(self, session: CdpBrowserSession, *, settle_seconds: float = 1.2) -> None:
        self.session = session
        self.settle = settle_seconds

    def observe(self) -> dict:
        return self.session.evaluate(_OBSERVE_JS) or {"url": "", "interactive": [], "errors": [], "headings": []}

    def navigate(self, url: str) -> bool:
        try:
            self.session.navigate(url)   # raises CdpError if off the TMS domain allowlist
        except CdpError:
            return False  # off-allowlist or nav failure -> a failed action; the agent adapts/escalates
        self._settle_until_ready()  # wait for the SPA to actually render, not just for a fixed sleep
        return True

    def click(self, target: str) -> bool:
        ok = self.session.evaluate(_CLICK_JS + "(" + json.dumps(target) + ")")
        self._settle_until_ready()  # a click often triggers an SPA transition — wait for it to render
        return bool(ok)

    def click_row_action(self, row_contains: str, action_text: str) -> bool:
        ok = self.session.evaluate(
            _CLICK_ROW_ACTION_JS + "(" + json.dumps(row_contains) + "," + json.dumps(action_text) + ")"
        )
        self._settle_until_ready()
        return bool(ok)

    def money_field_values(self) -> list[dict]:
        """Visible money-labelled text inputs on the current form, with their current values, as
        [{target, value}]. Used by the agent to reconcile a TMS-DEFAULTED amount against the approved
        amount before committing. ``target`` is the field name (which __findInput resolves), so the
        agent can re-set the field if needed."""
        try:
            return self.session.evaluate(_MONEY_FIELDS_JS) or []
        except Exception:  # noqa: BLE001
            return []

    def capture_screenshot(self, path) -> str:
        """Save a PNG of the current screen (passthrough to the session) — used for escalation evidence."""
        return self.session.capture_screenshot(path)

    def is_submit_target(self, target: str) -> bool:
        """True if clicking this target would SUBMIT a form (commit). Used by the agent's consequential
        gate so a form's save button is gated even when its label ("Create Invoice") collides with a
        non-committing link elsewhere. Best-effort: any error resolves to False (fail-open on detection,
        but the keyword gate and verify-before-DONE still apply)."""
        try:
            return bool(self.session.evaluate(_IS_SUBMIT_JS + "(" + json.dumps(target) + ")"))
        except Exception:  # noqa: BLE001
            return False

    def _settle_until_ready(self, timeout: float = 8.0) -> None:
        """Wait until the page has STOPPED rendering, so observe() never catches a mid-render screen.

        A plain 'has >=3 controls' check is useless here: the persistent nav chrome (Dashboard, Loads,
        Invoices...) satisfies it instantly, so after a navigating click it returned before the actual
        FORM/CONTENT rendered — the agent then saw a 'blank' page. Instead we wait for the page to
        stabilize: ``readyState==='complete'`` AND the URL + interactive-element count unchanged across
        consecutive polls. That catches a full navigation (URL/count change, then settle) and an async
        SPA render (count grows, then settles) alike. A short initial wait lets a transition kick off
        before we start sampling."""
        time.sleep(0.4)  # let a navigation / SPA transition begin before we sample stability
        deadline = time.time() + timeout
        last_sig = None
        stable = 0
        while time.time() < deadline:
            try:
                sig = self.session.evaluate(
                    "(function(){return document.readyState+'|'+location.href+'|'+"
                    "document.querySelectorAll('a,button,input,select,textarea,[role=button]').length;})()"
                )
            except Exception:  # noqa: BLE001
                sig = None
            ready = bool(sig) and str(sig).split("|", 1)[0] == "complete"
            if ready and sig == last_sig:
                stable += 1
                if stable >= 2:  # loaded and unchanged across polls -> rendered
                    time.sleep(self.settle * 0.4)  # a touch more for late JS
                    return
            else:
                stable = 0
            last_sig = sig
            time.sleep(0.35)

    def type(self, target: str, value: str) -> bool:
        # 1) focus the field and select its current contents (so real typing replaces them)
        focused = self.session.evaluate(
            _FIND_INPUT + "(function(t){var el=__findInput(t); if(!el)return false;"
            "el.scrollIntoView({block:'center'}); el.focus(); try{el.select();}catch(e){} return true;})("
            + json.dumps(target) + ")"
        )
        if not focused:
            return False
        # 2) REAL keyboard input — the SPA-registering step plain value-setting can't do
        self.session.command("Input.insertText", {"text": str(value)})
        # 3) fire input/change/blur so framework + computed fields update, and confirm
        result = self.session.evaluate(
            _FIND_INPUT + "(function(t){var el=__findInput(t); if(!el)return null;"
            "el.dispatchEvent(new Event('input',{bubbles:true})); el.dispatchEvent(new Event('change',{bubbles:true}));"
            "el.blur(); return el.value;})(" + json.dumps(target) + ")"
        )
        time.sleep(self.settle)
        return result is not None

    def select(self, target: str, option: str) -> bool:
        ok = self.session.evaluate(
            _FIND_INPUT + "(function(t,opt){var el=__findInput(t); if(!el||el.tagName!=='SELECT')return false;"
            "var o=[...el.options].find(o=>o.text.trim().toLowerCase().indexOf(opt.toLowerCase())>=0); if(!o)return false;"
            "el.value=o.value; el.dispatchEvent(new Event('change',{bubbles:true})); return true;})("
            + json.dumps(target) + "," + json.dumps(option) + ")"
        )
        time.sleep(self.settle)
        return bool(ok)

    def upload_file(self, file_path: str, target: str = "") -> bool:
        """Attach a local file to a file-input on the current form (POD / BOL / rate-con upload).

        The file is supplied by the RUNTIME, never chosen by the model — the same fence as money
        amounts. Returns False (a soft-failed action) if the file is missing or there is no file-input
        on the page, so a missing artifact fails CLOSED and the lane escalates instead of "attaching"
        nothing."""
        ok = self.session.set_file_input(file_path, target=target)
        if ok:
            self._settle_until_ready()  # the upload often triggers an async preview/render
        return bool(ok)

    def read(self, target: str) -> str:
        """Read a value back for verification — from a form field OR from DISPLAYED text.

        A readback usually happens on a saved-record page where the value (e.g. "Balance Due: $0.00",
        an invoice total, a status) is rendered TEXT, not an input. Reading only input fields returned
        empty there — so the agent couldn't confirm a write it had actually made. This resolves, in
        order: the input value, then the smallest visible element mentioning the target that also
        carries a number, then the target's table row / adjacent value."""
        val = self.session.evaluate(_READ_JS + "(" + json.dumps(target) + ")")
        return val or ""


