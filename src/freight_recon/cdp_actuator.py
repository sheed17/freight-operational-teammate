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

from freight_recon.cdp_session import CdpBrowserSession

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


class CdpActuator:
    def __init__(self, session: CdpBrowserSession, *, settle_seconds: float = 1.2) -> None:
        self.session = session
        self.settle = settle_seconds

    def observe(self) -> dict:
        return self.session.evaluate(_OBSERVE_JS) or {"url": "", "interactive": [], "errors": [], "headings": []}

    def navigate(self, url: str) -> bool:
        self.session.navigate(url)
        return True

    def click(self, target: str) -> bool:
        ok = self.session.evaluate(
            "(function(t){"
            "var el=null; try{el=document.querySelector(t);}catch(e){}"
            "if(!el){var tl=t.toLowerCase(); el=[...document.querySelectorAll('button,a,[role=button],input[type=submit]')]"
            ".find(e=>((e.innerText||e.value||'').trim().toLowerCase()).indexOf(tl)>=0);}"
            "if(!el)return false; el.scrollIntoView({block:'center'}); el.click(); return true;"
            "})(" + json.dumps(target) + ")"
        )
        time.sleep(self.settle)
        return bool(ok)

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

    def read(self, target: str) -> str:
        val = self.session.evaluate(
            _FIND_INPUT + "(function(t){var el=__findInput(t); if(el)return (el.value!==undefined?el.value:el.innerText)||'';"
            "try{var s=document.querySelector(t); if(s)return s.innerText||'';}catch(e){} return '';})("
            + json.dumps(target) + ")"
        )
        return val or ""


_OBSERVE_JS = r"""
(function(){
  function lbl(el){
    if(el.id){var l=document.querySelector('label[for="'+el.id+'"]'); if(l) return l.innerText.trim();}
    var p=el.closest('.form-group,.field,td,tr,div'); if(p){var ll=p.querySelector('label'); if(ll) return ll.innerText.trim();}
    return el.getAttribute('placeholder')||el.getAttribute('aria-label')||el.name||'';
  }
  var inputs=[...document.querySelectorAll('input,select,textarea')].filter(e=>e.type!=='hidden').slice(0,40)
    .map(e=>({kind:e.tagName.toLowerCase(), type:e.type||'', label:lbl(e).slice(0,40), name:e.name||'', value:(e.value||'').slice(0,40)}));
  var actions=[...document.querySelectorAll('button,a[href],[role=button],input[type=submit]')]
    .map(e=>((e.innerText||e.value||'').trim())).filter(Boolean).filter((v,i,a)=>a.indexOf(v)===i).slice(0,30);
  // Navigation targets (text -> url) so the agent can NAVIGATE directly instead of fumbling clicks.
  var navSeen={}, nav=[];
  [...document.querySelectorAll('a[href]')].forEach(function(a){
    var t=(a.innerText||'').trim(), h=a.getAttribute('href')||'';
    if(t && h && h.indexOf('#')!==0 && h.indexOf('javascript:')!==0 && !navSeen[h]){ navSeen[h]=1; nav.push({text:t.slice(0,40), url:h}); }
  });
  var errors=[...document.querySelectorAll('.alert-danger,.error,.invalid-feedback,.is-invalid,.field_with_errors')]
    .map(e=>e.innerText.trim()).filter(Boolean).slice(0,6);
  return {url:location.href, headings:[...document.querySelectorAll('h1,h2,h3')].map(e=>e.innerText.trim()).filter(Boolean).slice(0,6),
          inputs:inputs, actions:actions, nav:nav.slice(0,30), errors:errors};
})()
"""
