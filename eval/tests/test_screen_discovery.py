"""Tests for agentic screen discovery: deterministic extraction + injectable LLM reasoning."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.screen_discovery import (  # noqa: E402
    DiscoveredInvoiceForm,
    discover_invoice_form,
    extract_form_schema,
)


# A fake session returns a canned DOM extraction (what the deterministic _EXTRACT_JS would yield on a
# TruckingOffice-like invoice form) without a browser.
_TO_FORM = {
    "url": "https://example-tms.test/no_load_invoice/new",
    "action": "/no_load_invoice",
    "submits": ["Create Customer", "Save"],
    "fields": [
        {"selector": "[name=\"customer_finder_field\"]", "name": "customer_finder_field", "id": "customer_finder",
         "tag": "input", "type": "text", "label": "Customer", "required": True, "options": []},
        {"selector": "[name=\"invoice[invoice_number]\"]", "name": "invoice[invoice_number]", "id": "",
         "tag": "input", "type": "text", "label": "Invoice Number", "required": False, "options": []},
        {"selector": "[name=\"invoice[invoiced_on]\"]", "name": "invoice[invoiced_on]", "id": "",
         "tag": "input", "type": "text", "label": "Invoice Date", "required": False, "options": []},
        {"selector": "[name=\"invoice[charge_description]\"]", "name": "invoice[charge_description]", "id": "",
         "tag": "textarea", "type": "textarea", "label": "Charge Description", "required": False, "options": []},
        {"selector": "[name=\"invoice[total_charge]\"]", "name": "invoice[total_charge]", "id": "",
         "tag": "input", "type": "text", "label": "Total Charge", "required": False, "options": []},
    ],
}


class FakeSession:
    def __init__(self, extract_result):
        self.extract_result = extract_result
        self.navigated = []

    def navigate(self, url):
        self.navigated.append(url)

    def evaluate(self, expression):
        return self.extract_result


def test_extract_form_schema_builds_field_specs():
    s = FakeSession(_TO_FORM)
    schema = extract_form_schema(s, "https://example-tms.test/no_load_invoice/new")
    assert s.navigated == ["https://example-tms.test/no_load_invoice/new"]
    labels = {f.label for f in schema.fields}
    assert {"Customer", "Total Charge", "Invoice Number", "Charge Description"} <= labels
    assert "Save" in schema.submit_labels
    # The prompt JSON carries selectors + labels so the model can reason from them.
    assert "Total Charge" in schema.to_prompt_json()


def test_discover_invoice_form_maps_concepts_from_model_output():
    schema = extract_form_schema(FakeSession(_TO_FORM), "https://example-tms.test/no_load_invoice/new")

    # A fake "agent" that reasoned over the labels and returned the mapping (no real model call).
    def fake_complete(prompt: str) -> str:
        assert "Total Charge" in prompt and "Customer" in prompt  # it was shown the real fields
        return json.dumps({
            "fields": {
                "bill_to": "[name=\"customer_finder_field\"]",
                "amount": "[name=\"invoice[total_charge]\"]",
                "invoice_number": "[name=\"invoice[invoice_number]\"]",
                "invoice_date": "[name=\"invoice[invoiced_on]\"]",
                "description": "[name=\"invoice[charge_description]\"]",
            },
            "submit_label": "Save",
            "notes": ["Customer appears required"],
        })

    disc = discover_invoice_form(schema, complete=fake_complete)
    assert isinstance(disc, DiscoveredInvoiceForm)
    assert disc.amount_selector == "[name=\"invoice[total_charge]\"]"
    assert disc.bill_to_selector == "[name=\"customer_finder_field\"]"
    assert disc.invoice_number_selector == "[name=\"invoice[invoice_number]\"]"
    assert disc.submit_label == "Save"
    assert disc.is_writable()


def test_discover_handles_fenced_json_and_dict_selectors():
    schema = extract_form_schema(FakeSession(_TO_FORM), "u")

    def fenced(prompt):  # model wraps JSON in a ```json fence and uses {selector: ...} objects
        return "```json\n" + json.dumps({
            "fields": {"bill_to": {"selector": "[name=\"customer_finder_field\"]"},
                       "amount": {"selector": "[name=\"invoice[total_charge]\"]"}},
            "submit_label": "Save",
        }) + "\n```"

    disc = discover_invoice_form(schema, complete=fenced)
    assert disc.amount_selector == "[name=\"invoice[total_charge]\"]"
    assert disc.is_writable()


def test_not_writable_when_amount_or_bill_to_missing():
    schema = extract_form_schema(FakeSession(_TO_FORM), "u")
    disc = discover_invoice_form(schema, complete=lambda p: json.dumps({"fields": {"amount": None, "bill_to": None}}))
    assert not disc.is_writable()
