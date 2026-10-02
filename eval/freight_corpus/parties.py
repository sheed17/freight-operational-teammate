"""The brokerages, customers and carriers of the hostile freight corpus. SYNTHETIC — every name,
number and address is invented.

Three small brokerages, deliberately configured differently, because what a brokerage requires is
configuration and never a constant:

  * Northline Freight — requires a POD before invoicing, expects it by email within a configured
    number of hours of delivery, and has a tracking provider it expects arrivals on.
  * Cedar Ridge Logistics — requires a POD but has configured NO deadline and NO channel for it, so
    an outstanding POD there is visible without an invented clock on it.
  * Harbor Point Brokerage — has configured NO document requirement at all, so what its loads need
    before billing is `unknown`.

Northline and Cedar Ridge run the same TMS product and share a carrier, so the same outside
identifiers legitimately appear under both.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from freight_recon.freight_domain.history import (  # noqa: E402
    DocumentRequirementConfig,
    TenantSetup,
)

NORTHLINE = "northline-freight"
CEDAR = "cedar-ridge-logistics"
HARBOR = "harbor-point-brokerage"

NORTHLINE_OPS = "email:ops@northline.example"
NORTHLINE_PODS = "email:pods@northline.example"
NORTHLINE_SMS = "sms:northline-dispatch-line"
CEDAR_OPS = "email:dispatch@cedarridge.example"
HARBOR_OPS = "email:ops@harborpoint.example"

SETUPS: dict[str, TenantSetup] = {
    NORTHLINE: TenantSetup(
        tenant=NORTHLINE, legal_name="Northline Freight Brokerage LLC",
        humans=(
            {"human_id": "dana.ortiz", "display_name": "Dana Ortiz (operations lead)"},
            {"human_id": "marcus.reid", "display_name": "Marcus Reid (carrier payables)"},
            {"human_id": "priya.nair", "display_name": "Priya Nair (inbound triage)"},
        ),
        load_owner="dana.ortiz", intake_owner="priya.nair", recorded_by="dana.ortiz",
        document_requirements=(DocumentRequirementConfig(
            gate="RAISE_INVOICE", required_doc_type="POD", expected_channel=NORTHLINE_PODS,
            expected_within_hours=24),),
        arrival_tracking_channel="tracking:macropoint"),
    CEDAR: TenantSetup(
        tenant=CEDAR, legal_name="Cedar Ridge Logistics Inc",
        humans=(
            {"human_id": "lee.tran", "display_name": "Lee Tran (owner-operator)"},
            {"human_id": "sam.okafor", "display_name": "Sam Okafor (dispatch)"},
        ),
        load_owner="sam.okafor", intake_owner="lee.tran", recorded_by="lee.tran",
        document_requirements=(DocumentRequirementConfig(
            gate="RAISE_INVOICE", required_doc_type="POD"),)),
    HARBOR: TenantSetup(
        tenant=HARBOR, legal_name="Harbor Point Brokerage Co",
        humans=({"human_id": "rosa.medina", "display_name": "Rosa Medina (owner)"},),
        load_owner="rosa.medina", intake_owner="rosa.medina", recorded_by="rosa.medina"),
}

CUSTOMERS = {
    "midwest_paper": {"id": "C-204", "name": "Midwest Paper Supply Co", "contacts": [
        {"name": "Alan Brooks", "email": "abrooks@midwestpaper.example", "role": "logistics"}]},
    "great_lakes_bev": {"id": "C-311", "name": "Great Lakes Beverage Dist", "contacts": [
        {"name": "Nina Patel", "email": "npatel@greatlakesbev.example", "role": "traffic"}]},
    "prairie_ag": {"id": "C-118", "name": "Prairie Ag Inputs LLC", "contacts": [
        {"name": "Tom Weller", "email": "tweller@prairieag.example", "role": "shipping"}]},
    "cedar_building": {"id": "C-204", "name": "Ozark Building Products", "contacts": [
        {"name": "Jo Hart", "email": "jhart@ozarkbuilding.example", "role": "shipping"}]},
    "harbor_seafood": {"id": "C-9", "name": "Bayline Seafood Packers", "contacts": [
        {"name": "Vic Amato", "email": "vamato@bayline.example", "role": "shipping"}]},
}

CARRIERS = {
    "redbird": {
        "mc": "MC-482915", "dot": "DOT-2917744", "name": "Redbird Transport LLC",
        "dispatcher": {"name": "Carla Mendez", "email": "dispatch@redbirdtransport.example",
                       "phone": "+1-555-0141", "role": "dispatcher"},
        "driver": {"name": "Ray Dalton", "phone": "+1-555-0177"}},
    "ironwood": {
        "mc": "MC-771203", "dot": "DOT-3310982", "name": "Ironwood Hauling Inc",
        "dispatcher": {"name": "Pete Vogel", "email": "pete@ironwoodhauling.example",
                       "phone": "+1-555-0162", "role": "dispatcher"},
        "driver": {"name": "Luis Ortega", "phone": "+1-555-0190"}},
    "bluegrass": {
        "mc": "MC-659440", "dot": "DOT-2204518", "name": "Bluegrass Carriers Co",
        "dispatcher": {"name": "Mae Sutter", "email": "mae@bluegrasscarriers.example",
                       "phone": "+1-555-0113", "role": "dispatcher"},
        "driver": {"name": "Hank Rollins", "phone": "+1-555-0128"}},
    "summit": {
        "mc": "MC-905118", "dot": "DOT-3498801", "name": "Summit Line Freight",
        "dispatcher": {"name": "Ines Kovac", "email": "ops@summitline.example",
                       "phone": "+1-555-0155", "role": "dispatcher"},
        "driver": {"name": "Dwayne Pruitt", "phone": "+1-555-0184"}},
}


def dispatcher(carrier: str) -> tuple[str, str, str]:
    contact = CARRIERS[carrier]["dispatcher"]
    return ("carrier_contact", contact["name"], contact["email"])


def driver(carrier: str) -> tuple[str, str, str]:
    contact = CARRIERS[carrier]["driver"]
    return ("driver", contact["name"], contact["phone"])


def customer_contact(customer: str) -> tuple[str, str, str]:
    contact = CUSTOMERS[customer]["contacts"][0]
    return ("customer_contact", contact["name"], contact["email"])
