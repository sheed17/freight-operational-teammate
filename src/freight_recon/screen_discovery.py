"""Agentic screen discovery: let an internal agent understand an unknown TMS the way a human would.

This is the system-agnostic core. Instead of a hand-written screen-map per TMS, an agent reads the
live screen and *authors* the map itself:

    deterministic DOM extraction  ->  LLM reasoning (which field means what)  ->  structured field map

The split is deliberate and is what makes "operate any system" safe:
- **Extraction** (here) and **execution + verify** (the gated ledger) are deterministic — an LLM never
  decides an amount or interprets a confirmation.
- **Understanding** (mapping a never-seen form's fields to invoice concepts from their labels) is the
  one place we use the model, because that is the genuinely human, generalizable judgement.

The output (:class:`DiscoveredInvoiceForm`) is the same shape the deterministic ledger consumes, so a
freshly-discovered TMS drives the existing gated write path with no per-system code.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Callable, Protocol


class BrowserSession(Protocol):
    def navigate(self, url: str) -> None: ...
    def evaluate(self, expression: str): ...


# A model that understands prose: prompt -> completion text. Injectable so discovery is unit-testable
# with a scripted fake and swappable across providers (production-default is OpenAI).
Completer = Callable[[str], str]


@dataclass
class FieldSpec:
    selector: str          # a usable CSS selector, e.g. [name="invoice[total_charge]"]
    name: str
    field_id: str
    tag: str               # input / select / textarea
    type: str
    label: str
    required: bool
    options: list[str] = field(default_factory=list)


@dataclass
class FormSchema:
    url: str
    action: str
    fields: list[FieldSpec]
    submit_labels: list[str]

    def to_prompt_json(self) -> str:
        return json.dumps(
            {
                "url": self.url,
                "action": self.action,
                "submit_buttons": self.submit_labels,
                "fields": [
                    {
                        "selector": f.selector, "label": f.label, "name": f.name,
                        "tag": f.tag, "type": f.type, "required": f.required,
                        **({"options": f.options[:8]} if f.options else {}),
                    }
                    for f in self.fields
                ],
            },
            indent=2,
        )


@dataclass
class DiscoveredInvoiceForm:
    """An agent-authored map of an invoice-creation screen — the deterministic ledger's input."""

    url: str
    submit_label: str
    bill_to_selector: str | None
    amount_selector: str | None
    invoice_number_selector: str | None
    description_selector: str | None
    date_selector: str | None = None
    notes: list[str] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    def is_writable(self) -> bool:
        # The minimum a gated invoice write needs: who to bill, how much, and a submit.
        return bool(self.bill_to_selector and self.amount_selector and self.submit_label)


def extract_form_schema(session: BrowserSession, url: str) -> FormSchema:
    """Deterministically read the current screen's primary form into a structured schema (no LLM)."""
    session.navigate(url)
    data = session.evaluate(_EXTRACT_JS) or {}
    fields = [
        FieldSpec(
            selector=f.get("selector", ""), name=f.get("name", ""), field_id=f.get("id", ""),
            tag=f.get("tag", ""), type=f.get("type", ""), label=f.get("label", ""),
            required=bool(f.get("required")), options=f.get("options") or [],
        )
        for f in data.get("fields", [])
    ]
    return FormSchema(
        url=data.get("url", url), action=data.get("action", ""), fields=fields,
        submit_labels=data.get("submits", []),
    )


def discover_invoice_form(schema: FormSchema, *, complete: Completer) -> DiscoveredInvoiceForm:
    """Use the model to map a never-seen form's fields to invoice concepts, from labels alone."""
    raw = complete(_discovery_prompt(schema))
    parsed = _parse_llm_json(raw)
    if not isinstance(parsed, dict):
        raise ValueError("discovery model JSON must be an object")
    fields_by = {"map": parsed.get("fields", parsed)}
    m = fields_by["map"]
    return DiscoveredInvoiceForm(
        url=schema.url,
        submit_label=parsed.get("submit_label") or (schema.submit_labels[0] if schema.submit_labels else "Save"),
        bill_to_selector=_sel(m.get("bill_to")),
        amount_selector=_sel(m.get("amount")),
        invoice_number_selector=_sel(m.get("invoice_number")),
        description_selector=_sel(m.get("description")),
        date_selector=_sel(m.get("invoice_date")),
        notes=parsed.get("notes", []) if isinstance(parsed.get("notes"), list) else [],
        raw=parsed,
    )


def propose_field_repair(error: str, values: dict, *, complete: Completer) -> dict:
    """The agent reads a TMS validation error + the values it submitted and proposes corrected values.

    This is self-heal: instead of dead-ending on a rejection the discovery didn't anticipate (a field
    that must be numeric, a required field left blank), the agent reasons from the error message the
    system gave — exactly how a human recovers. Returns a partial {concept: new_value} map.

    Money invariant: ``amount`` is stripped from any proposal here and again at the ledger, so self-heal
    can fix navigation/format but can never change the human-approved figure.
    """
    safe = {k: v for k, v in values.items() if k != "amount"}
    prompt = (
        "You are operating an unfamiliar freight TMS. You submitted a customer invoice and it was "
        "REJECTED with this validation error:\n\n"
        f"  {error}\n\n"
        "These are the non-amount values you submitted (concept: value):\n"
        f"  {json.dumps(safe)}\n\n"
        "Return ONLY corrected values for the field(s) the error is about, as JSON {concept: new_value} "
        "using these concept keys: invoice_number, description, bill_to. Rules: if the error says a "
        "field must be a number, return only its digits; if it says a field can't be blank, provide a "
        "short sensible value; change as little as possible; NEVER include or change amount."
    )
    repair = _parse_llm_json(complete(prompt))
    repair = repair.get("fields", repair) if isinstance(repair, dict) else {}
    repair.pop("amount", None)
    return {k: str(v) for k, v in repair.items() if isinstance(k, str) and v not in (None, "")}


def _sel(value) -> str | None:
    if isinstance(value, dict):
        value = value.get("selector")
    if isinstance(value, str) and value.strip() and value.strip().lower() != "none":
        return value.strip()
    return None


def _discovery_prompt(schema: FormSchema) -> str:
    return (
        "You are an operations agent learning to use an unfamiliar freight TMS by looking at one of its "
        "web forms, the way a new back-office hire would. Below is the structured field list of a form "
        "you believe creates a customer invoice (accounts receivable).\n\n"
        "Map the form's fields to these invoice concepts using ONLY the field labels/names as evidence:\n"
        "  - bill_to: who the invoice is billed to (the customer / broker finder or selector)\n"
        "  - amount: the total amount charged (the money field)\n"
        "  - invoice_number: the invoice number / reference\n"
        "  - invoice_date: the invoice date\n"
        "  - description: the line/charge description (often required)\n\n"
        "For each concept, return the EXACT `selector` string from the field list (or null if absent). "
        "Also return `submit_label` (the button that saves the invoice) and a `notes` array of any "
        "constraints you can infer (e.g. a field that must be numeric, or appears required).\n\n"
        f"FORM:\n{schema.to_prompt_json()}\n\n"
        'Respond with ONLY JSON: {"fields": {"bill_to": "<selector|null>", "amount": "...", '
        '"invoice_number": "...", "invoice_date": "...", "description": "..."}, '
        '"submit_label": "...", "notes": ["..."]}'
    )


def _parse_llm_json(text: str) -> dict:
    raw = text or ""
    candidates = [_strip_markdown_fence(raw), raw]
    decoder = json.JSONDecoder()
    errors: list[str] = []
    for candidate in candidates:
        s = candidate.strip()
        index = s.find("{")
        if index == -1:
            continue
        try:
            parsed, _end = decoder.raw_decode(s[index:])
        except json.JSONDecodeError as exc:
            errors.append(str(exc))
            continue
        if not isinstance(parsed, dict):
            raise ValueError("discovery model JSON must be an object")
        return parsed
    detail = "; ".join(errors[-2:]) if errors else raw[:160]
    raise ValueError(f"discovery model did not return a valid JSON object: {detail}")


def _strip_markdown_fence(text: str) -> str:
    s = (text or "").strip()
    if not s.startswith("```"):
        return s
    first_newline = s.find("\n")
    if first_newline == -1:
        return s.strip("`")
    closing = s.rfind("```")
    if closing <= first_newline:
        return s[first_newline + 1 :]
    return s[first_newline + 1 : closing]


def openai_completer(model: str = "gpt-4.1-mini", *, temperature: float = 0.0) -> Completer:
    """Default production completer over OpenAI (the project's working discovery model)."""

    def _complete(prompt: str) -> str:
        from openai import OpenAI

        client = OpenAI()
        kwargs: dict = {"model": model, "messages": [{"role": "user", "content": prompt}]}
        # gpt-5 and the o-series only accept the default temperature; sending one 400s.
        if not any(model.startswith(p) for p in ("gpt-5", "o1", "o3", "o4")):
            kwargs["temperature"] = temperature
        resp = client.chat.completions.create(**kwargs)
        return resp.choices[0].message.content or ""

    return _complete


# Read the primary form into {url, action, submits, fields:[{selector,name,id,tag,type,label,required,options}]}.
_EXTRACT_JS = r"""
(function(){
  function labelFor(el){
    if(el.id){var l=document.querySelector('label[for="'+el.id+'"]'); if(l) return l.innerText.trim();}
    var p=el.closest('label'); if(p) return p.innerText.trim();
    var pa=el.closest('.form-group,.field,.control-group,td,tr,div');
    if(pa){var ll=pa.querySelector('label'); if(ll) return ll.innerText.trim();}
    return el.getAttribute('placeholder')||'';
  }
  function selFor(el){
    if(el.name) return '[name="'+el.name+'"]';
    if(el.id) return '#'+el.id;
    return el.tagName.toLowerCase();
  }
  var form=document.querySelector('form');
  var scope=form||document;
  var fields=[...scope.querySelectorAll('input,select,textarea')]
    .filter(function(e){return e.type!=='hidden' && e.type!=='submit' && e.type!=='button';})
    .map(function(e){
      return {selector:selFor(e), name:e.name||'', id:e.id||'',
        tag:e.tagName.toLowerCase(), type:e.type||'', label:labelFor(e).slice(0,60),
        required:!!e.required,
        options:e.tagName.toLowerCase()==='select'?[...e.options].slice(0,8).map(function(o){return o.text.trim();}):[]};
    }).slice(0,60);
  var submits=[...scope.querySelectorAll('button,input[type=submit]')]
    .map(function(b){return (b.innerText||b.value||'').trim();}).filter(Boolean).slice(0,10);
  return {url:location.href, action:form?(form.getAttribute('action')||''):'', fields:fields, submits:submits};
})()
"""
