"""Generate a realistic synthetic freight document corpus.

The corpus is inspired by public freight templates and sample forms, but every value is
synthetic. It creates an internally consistent freight world: loads, rate confirmations,
carrier invoices, BOLs, PODs, lumper/fuel docs, manifests, deliberate variance scenarios, and
dirty scan variants.

Usage:
    .venv/bin/python scripts/generate_realistic_corpus.py
    .venv/bin/python scripts/generate_realistic_corpus.py --loads 20 --seed 7
"""

from __future__ import annotations

import argparse
import io
import json
import math
import random
from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import fitz
from PIL import Image, ImageEnhance, ImageFilter
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas

MONEY = Decimal("0.01")

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUT = ROOT / "data" / "synthetic_corpus"


@dataclass
class Charge:
    name: str
    amount: str
    authorized: bool = True
    backup_document: str | None = None


@dataclass
class LoadRecord:
    load_id: str
    invoice_number: str
    pro_number: str
    bol_number: str
    manifest_number: str
    customer: str
    shipper: str
    consignee: str
    origin: str
    destination: str
    carrier: str
    carrier_mc: str
    equipment: str
    commodity: str
    pickup_date: str
    delivery_date: str
    rate_linehaul: str
    rate_fuel: str
    invoice_linehaul: str
    invoice_fuel: str
    rate_accessorials: list[Charge]
    invoice_accessorials: list[Charge]
    scenario: str
    expected_outcome: str
    variance_reasons: list[str]
    documents: dict[str, str] = field(default_factory=dict)

    @property
    def rate_total(self) -> str:
        return money(
            d(self.rate_linehaul)
            + d(self.rate_fuel)
            + sum(d(c.amount) for c in self.rate_accessorials)
        )

    @property
    def invoice_total(self) -> str:
        return money(
            d(self.invoice_linehaul)
            + d(self.invoice_fuel)
            + sum(d(c.amount) for c in self.invoice_accessorials)
        )


def d(value: str | int | float | Decimal) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def money(value: Decimal) -> str:
    return str(value.quantize(MONEY, rounding=ROUND_HALF_UP))


def dollars(value: str | Decimal) -> str:
    return f"${float(d(value)):,.2f}"


def date(day: int) -> str:
    return f"2026-05-{day:02d}"


CARRIERS = [
    ("Blue Ridge Transport LLC", "MC-742018"),
    ("Prairie Line Carriers Inc", "MC-884120"),
    ("Cactus Trail Freight LLC", "MC-663219"),
    ("Great Lakes Drayage Co", "MC-531972"),
    ("Summit Valley Trucking", "MC-902144"),
    ("Iron Horse Logistics LLC", "MC-778431"),
]

CUSTOMERS = [
    "FreshField Foods",
    "Northstar Retail Distribution",
    "Cobalt Home Goods",
    "Evergreen Packaging",
    "Metro Industrial Supply",
    "Harbor Appliance Group",
]

LOCATIONS = [
    ("Fresno, CA", "Phoenix, AZ"),
    ("Dallas, TX", "Atlanta, GA"),
    ("Chicago, IL", "Columbus, OH"),
    ("Madera, CA", "Reno, NV"),
    ("Memphis, TN", "Orlando, FL"),
    ("Kansas City, MO", "Denver, CO"),
    ("Stockton, CA", "Portland, OR"),
    ("Charlotte, NC", "Nashville, TN"),
]

COMMODITIES = [
    "packaged food products",
    "retail dry goods",
    "paper packaging",
    "consumer appliances",
    "palletized hardware",
    "beverage containers",
]

SCENARIOS = [
    "clean_match",
    "clean_match",
    "unauthorized_detention",
    "fuel_mismatch",
    "linehaul_mismatch",
    "missing_lumper_backup",
    "duplicate_invoice",
    "missing_pod",
    "extra_stopoff",
]


def build_loads(count: int, seed: int) -> list[LoadRecord]:
    rng = random.Random(seed)
    loads: list[LoadRecord] = []
    for i in range(1, count + 1):
        carrier, mc = rng.choice(CARRIERS)
        origin, dest = rng.choice(LOCATIONS)
        rate_linehaul = d(rng.randrange(1150, 4200, 25))
        rate_fuel = d(rate_linehaul * Decimal(str(rng.choice([0.12, 0.14, 0.16, 0.18]))))
        scenario = SCENARIOS[(i - 1) % len(SCENARIOS)]

        load = LoadRecord(
            load_id=f"LD-{560000 + i:06d}",
            invoice_number=f"INV-{2026000 + i}",
            pro_number=f"PRO-{9200000 + i * 137}",
            bol_number=f"BOL-{33000 + i}",
            manifest_number=f"MAN-{8100 + i}",
            customer=rng.choice(CUSTOMERS),
            shipper=f"{rng.choice(CUSTOMERS)} Warehouse",
            consignee=f"{rng.choice(CUSTOMERS)} DC",
            origin=origin,
            destination=dest,
            carrier=carrier,
            carrier_mc=mc,
            equipment=rng.choice(["53' Dry Van", "Reefer", "Flatbed", "26' Box Truck"]),
            commodity=rng.choice(COMMODITIES),
            pickup_date=date(2 + i),
            delivery_date=date(4 + i),
            rate_linehaul=money(rate_linehaul),
            rate_fuel=money(rate_fuel),
            invoice_linehaul=money(rate_linehaul),
            invoice_fuel=money(rate_fuel),
            rate_accessorials=[],
            invoice_accessorials=[],
            scenario=scenario,
            expected_outcome="MATCHED",
            variance_reasons=[],
        )

        if scenario == "unauthorized_detention":
            load.invoice_accessorials.append(Charge("detention", "300.00", authorized=False))
            load.expected_outcome = "VARIANCE"
            load.variance_reasons.append("invoice includes unauthorized detention not on rate confirmation")
        elif scenario == "fuel_mismatch":
            load.invoice_fuel = money(d(load.rate_fuel) + Decimal("125.00"))
            load.expected_outcome = "VARIANCE"
            load.variance_reasons.append("invoice fuel surcharge is $125.00 higher than expected")
        elif scenario == "linehaul_mismatch":
            load.invoice_linehaul = money(d(load.rate_linehaul) + Decimal("200.00"))
            load.expected_outcome = "VARIANCE"
            load.variance_reasons.append("invoice linehaul is $200.00 higher than rate confirmation")
        elif scenario == "missing_lumper_backup":
            lumper = Charge("lumper", "175.00", authorized=True, backup_document=None)
            load.rate_accessorials.append(lumper)
            load.invoice_accessorials.append(lumper)
            load.expected_outcome = "NEEDS_REVIEW"
            load.variance_reasons.append("lumper charge present but no lumper receipt generated")
        elif scenario == "missing_pod":
            load.expected_outcome = "NEEDS_REVIEW"
            load.variance_reasons.append("POD missing from packet")
        elif scenario == "extra_stopoff":
            stop = Charge("stop-off", "125.00", authorized=True, backup_document="rate_confirmation")
            load.rate_accessorials.append(stop)
            load.invoice_accessorials.append(stop)
        else:
            if i % 3 == 0:
                det = Charge("detention", "150.00", authorized=True, backup_document="rate_confirmation")
                load.rate_accessorials.append(det)
                load.invoice_accessorials.append(det)

        if scenario == "duplicate_invoice" and loads:
            source = loads[-1]
            load.invoice_accessorials = list(source.invoice_accessorials)
            load.rate_linehaul = source.rate_linehaul
            load.rate_fuel = source.rate_fuel
            load.invoice_linehaul = source.invoice_linehaul
            load.invoice_fuel = source.invoice_fuel
            load.invoice_number = source.invoice_number
            load.carrier = source.carrier
            load.carrier_mc = source.carrier_mc
            load.expected_outcome = "DUPLICATE"
            load.variance_reasons.append(f"invoice number duplicates {source.load_id}")

        loads.append(load)
    return loads


def draw_box(c: canvas.Canvas, x: float, y: float, w: float, h: float, label: str = "") -> None:
    c.setStrokeColor(colors.black)
    c.rect(x, y, w, h, stroke=1, fill=0)
    if label:
        c.setFont("Helvetica-Bold", 7)
        c.drawString(x + 4, y + h - 10, label)


def label_value(c: canvas.Canvas, x: float, y: float, label: str, value: str, size: int = 9) -> None:
    c.setFont("Helvetica-Bold", size)
    c.drawString(x, y, f"{label}:")
    c.setFont("Helvetica", size)
    c.drawString(x + 92, y, value)


def new_canvas(path: Path) -> canvas.Canvas:
    return canvas.Canvas(str(path), pagesize=LETTER)


def draw_rate_confirmation(path: Path, load: LoadRecord) -> None:
    c = new_canvas(path)
    w, h = LETTER
    margin = 0.55 * inch
    y = h - 0.55 * inch

    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, "REDWOOD FREIGHT BROKERAGE")
    c.setFont("Helvetica-Bold", 14)
    c.drawRightString(w - margin, y, "CARRIER RATE CONFIRMATION")
    y -= 0.25 * inch
    c.setFont("Helvetica", 8.5)
    c.drawString(margin, y, "MC-1182043 | operations@redwoodfreight.example | 559-555-0138")
    y -= 0.33 * inch

    draw_box(c, margin, y - 0.85 * inch, w - 2 * margin, 0.85 * inch, "LOAD DETAILS")
    label_value(c, margin + 10, y - 18, "Load #", load.load_id)
    label_value(c, margin + 220, y - 18, "Date", load.pickup_date)
    label_value(c, margin + 10, y - 38, "Carrier", load.carrier)
    label_value(c, margin + 220, y - 38, "MC #", load.carrier_mc)
    label_value(c, margin + 10, y - 58, "Equipment", load.equipment)
    label_value(c, margin + 220, y - 58, "Commodity", load.commodity)
    y -= 1.05 * inch

    draw_box(c, margin, y - 1.05 * inch, (w - 2 * margin) / 2 - 5, 1.05 * inch, "PICKUP")
    label_value(c, margin + 10, y - 22, "Shipper", load.shipper)
    label_value(c, margin + 10, y - 42, "City/ST", load.origin)
    label_value(c, margin + 10, y - 62, "Date", load.pickup_date)

    x2 = margin + (w - 2 * margin) / 2 + 5
    draw_box(c, x2, y - 1.05 * inch, (w - 2 * margin) / 2 - 5, 1.05 * inch, "DELIVERY")
    label_value(c, x2 + 10, y - 22, "Consignee", load.consignee)
    label_value(c, x2 + 10, y - 42, "City/ST", load.destination)
    label_value(c, x2 + 10, y - 62, "Date", load.delivery_date)
    y -= 1.35 * inch

    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, y, "AGREED CHARGES")
    c.drawRightString(w - margin, y, "AMOUNT")
    y -= 8
    c.line(margin, y, w - margin, y)
    y -= 18
    c.setFont("Helvetica", 9.5)
    rows = [("Linehaul", load.rate_linehaul), ("Fuel surcharge", load.rate_fuel)]
    rows.extend((charge.name.title(), charge.amount) for charge in load.rate_accessorials)
    for desc, amount in rows:
        c.drawString(margin, y, desc)
        c.drawRightString(w - margin, y, dollars(amount))
        y -= 18
    c.line(margin, y, w - margin, y)
    y -= 20
    c.setFont("Helvetica-Bold", 11)
    c.drawString(margin, y, "TOTAL AGREED RATE")
    c.drawRightString(w - margin, y, dollars(load.rate_total))

    y -= 0.45 * inch
    c.setFont("Helvetica", 8)
    c.drawString(margin, y, "Carrier must submit invoice, signed POD/BOL, and approved accessorial receipts.")
    y -= 14
    c.drawString(margin, y, "Detention/lumper/accessorials must be authorized in writing or supported by signed backup.")
    y -= 28
    c.setFont("Helvetica-Bold", 9)
    c.drawString(margin, y, "Carrier Signature: ______________________________   Date: ____________")
    c.showPage()
    c.save()


def draw_carrier_invoice(path: Path, load: LoadRecord) -> None:
    c = new_canvas(path)
    w, h = LETTER
    margin = 0.65 * inch
    y = h - 0.75 * inch

    c.setFont("Helvetica-Bold", 17)
    c.drawString(margin, y, load.carrier)
    c.setFont("Helvetica-Bold", 22)
    c.drawRightString(w - margin, y, "FREIGHT BILL")
    y -= 0.22 * inch
    c.setFont("Helvetica", 9)
    c.drawString(margin, y, f"{load.carrier_mc} | billing@{slug(load.carrier)}.example | Remit to: PO Box 1188")
    y -= 0.45 * inch

    label_value(c, margin, y, "Invoice #", load.invoice_number, 10)
    label_value(c, margin + 240, y, "Invoice Date", load.delivery_date, 10)
    y -= 22
    label_value(c, margin, y, "Load / PRO #", load.load_id, 10)
    label_value(c, margin + 240, y, "BOL #", load.bol_number, 10)
    y -= 24
    c.setFont("Helvetica", 9.5)
    c.drawString(margin, y, f"Bill To: Redwood Freight Brokerage | Lane: {load.origin} -> {load.destination}")
    y -= 0.38 * inch

    c.setFont("Helvetica-Bold", 10)
    c.drawString(margin, y, "DESCRIPTION")
    c.drawRightString(w - margin, y, "AMOUNT")
    y -= 8
    c.line(margin, y, w - margin, y)
    y -= 20
    c.setFont("Helvetica", 10)
    rows = [(f"Linehaul - {load.equipment}", load.invoice_linehaul), ("Fuel Surcharge", load.invoice_fuel)]
    rows.extend((f"Accessorial - {charge.name.title()}", charge.amount) for charge in load.invoice_accessorials)
    for desc, amount in rows:
        c.drawString(margin, y, desc)
        c.drawRightString(w - margin, y, dollars(amount))
        y -= 22
    c.line(margin, y, w - margin, y)
    y -= 24
    c.setFont("Helvetica-Bold", 13)
    c.drawString(margin, y, "TOTAL DUE")
    c.drawRightString(w - margin, y, dollars(load.invoice_total))
    y -= 0.45 * inch
    c.setFont("Helvetica-Oblique", 8)
    c.drawString(margin, y, "Please reference invoice number and load number on payment. Terms Net 30.")
    c.showPage()
    c.save()


def draw_bol(path: Path, load: LoadRecord) -> None:
    c = new_canvas(path)
    w, h = LETTER
    margin = 0.45 * inch
    y = h - 0.45 * inch
    c.setFont("Helvetica-Bold", 15)
    c.drawString(margin, y, "BILL OF LADING - SHORT FORM - NOT NEGOTIABLE")
    c.setFont("Helvetica", 8)
    c.drawRightString(w - margin, y, f"BOL #: {load.bol_number}")
    y -= 0.35 * inch

    col_w = (w - 2 * margin) / 2 - 5
    draw_box(c, margin, y - 1.25 * inch, col_w, 1.25 * inch, "SHIP FROM")
    label_value(c, margin + 10, y - 22, "Name", load.shipper)
    label_value(c, margin + 10, y - 42, "City/ST", load.origin)
    label_value(c, margin + 10, y - 62, "SID #", f"SID-{load.load_id[-4:]}")
    label_value(c, margin + 10, y - 82, "Pickup", load.pickup_date)
    x2 = margin + col_w + 10
    draw_box(c, x2, y - 1.25 * inch, col_w, 1.25 * inch, "SHIP TO")
    label_value(c, x2 + 10, y - 22, "Name", load.consignee)
    label_value(c, x2 + 10, y - 42, "City/ST", load.destination)
    label_value(c, x2 + 10, y - 62, "CID #", f"CID-{load.pro_number[-4:]}")
    label_value(c, x2 + 10, y - 82, "Delivery", load.delivery_date)
    y -= 1.55 * inch

    draw_box(c, margin, y - 0.8 * inch, w - 2 * margin, 0.8 * inch, "CARRIER / THIRD PARTY FREIGHT CHARGES")
    label_value(c, margin + 10, y - 22, "Carrier", load.carrier)
    label_value(c, margin + 240, y - 22, "PRO", load.pro_number)
    label_value(c, margin + 10, y - 44, "Trailer", f"TR-{random_digits(load.load_id, 5)}")
    label_value(c, margin + 240, y - 44, "SCAC", slug(load.carrier)[:4].upper())
    y -= 1.05 * inch

    c.setFont("Helvetica-Bold", 8.5)
    headers = ["Customer Order No.", "Packages", "Weight", "Commodity Description"]
    xs = [margin, margin + 145, margin + 235, margin + 325]
    for x, head in zip(xs, headers):
        c.drawString(x, y, head)
    y -= 8
    c.line(margin, y, w - margin, y)
    y -= 22
    c.setFont("Helvetica", 9)
    c.drawString(xs[0], y, f"PO-{random_digits(load.customer, 6)}")
    c.drawString(xs[1], y, str(12 + int(load.load_id[-2:]) % 18))
    c.drawString(xs[2], y, f"{18000 + int(load.load_id[-2:]) * 170:,} lbs")
    c.drawString(xs[3], y, load.commodity.title())
    y -= 0.75 * inch
    c.setFont("Helvetica", 8)
    c.drawString(margin, y, "Shipper signature: __________________________  Driver signature: __________________________")
    c.showPage()
    c.save()


def draw_pod(path: Path, load: LoadRecord) -> None:
    c = new_canvas(path)
    w, h = LETTER
    margin = 0.65 * inch
    y = h - 0.75 * inch
    c.setFont("Helvetica-Bold", 20)
    c.drawString(margin, y, "PROOF OF DELIVERY")
    y -= 0.45 * inch
    label_value(c, margin, y, "Load #", load.load_id, 10)
    label_value(c, margin + 260, y, "BOL #", load.bol_number, 10)
    y -= 24
    label_value(c, margin, y, "Delivered To", load.consignee, 10)
    label_value(c, margin + 260, y, "Date", load.delivery_date, 10)
    y -= 24
    label_value(c, margin, y, "Location", load.destination, 10)
    label_value(c, margin + 260, y, "Time", "14:35", 10)
    y -= 0.45 * inch
    c.setFont("Helvetica", 9)
    c.drawString(margin, y, "Shipment received in apparent good order unless exceptions are noted below.")
    y -= 36
    draw_box(c, margin, y - 1.1 * inch, w - 2 * margin, 1.1 * inch, "EXCEPTIONS / NOTES")
    y -= 1.35 * inch
    c.drawString(margin, y, "Received by: Jordan Lee")
    y -= 28
    c.setFont("Helvetica-Oblique", 13)
    c.drawString(margin, y, "J. Lee")
    c.setFont("Helvetica", 8)
    c.drawString(margin + 140, y, "Recipient Signature")
    c.showPage()
    c.save()


def draw_lumper_receipt(path: Path, load: LoadRecord, amount: str) -> None:
    c = new_canvas(path)
    w, h = LETTER
    margin = 0.9 * inch
    y = h - 0.85 * inch
    c.setFont("Helvetica-Bold", 18)
    c.drawString(margin, y, "WAREHOUSE LUMPER RECEIPT")
    y -= 0.5 * inch
    label_value(c, margin, y, "Receipt #", f"LMP-{load.load_id[-5:]}", 10)
    y -= 24
    label_value(c, margin, y, "Load #", load.load_id, 10)
    y -= 24
    label_value(c, margin, y, "Carrier", load.carrier, 10)
    y -= 24
    label_value(c, margin, y, "Facility", load.consignee, 10)
    y -= 24
    label_value(c, margin, y, "Service", "Unload / breakdown pallets", 10)
    y -= 24
    label_value(c, margin, y, "Amount Paid", dollars(amount), 10)
    y -= 50
    c.drawString(margin, y, "Approved by warehouse clerk: ____________________")
    c.showPage()
    c.save()


def draw_fuel_receipt(path: Path, load: LoadRecord) -> None:
    c = new_canvas(path)
    w, h = LETTER
    margin = 1.05 * inch
    y = h - 0.9 * inch
    gallons = Decimal("64.2") + Decimal(int(load.load_id[-2:]) % 15)
    price = Decimal("4.18")
    total = money(gallons * price)
    c.setFont("Courier-Bold", 16)
    c.drawCentredString(w / 2, y, "TRAVEL PLAZA FUEL RECEIPT")
    y -= 0.45 * inch
    c.setFont("Courier", 10)
    lines = [
        f"DATE: {load.pickup_date}        TIME: 06:42",
        f"LOAD REF: {load.load_id}",
        f"CARRIER: {load.carrier}",
        f"DIESEL GALLONS: {gallons}",
        f"PRICE/GAL: $4.18",
        f"TOTAL: {dollars(total)}",
        "THANK YOU",
    ]
    for line in lines:
        c.drawString(margin, y, line)
        y -= 20
    c.showPage()
    c.save()


def draw_manifest(path: Path, loads: list[LoadRecord], manifest_id: str) -> None:
    c = new_canvas(path)
    w, h = LETTER
    margin = 0.45 * inch
    y = h - 0.55 * inch
    c.setFont("Helvetica-Bold", 16)
    c.drawString(margin, y, "LOAD MANIFEST")
    c.drawRightString(w - margin, y, manifest_id)
    y -= 0.4 * inch
    c.setFont("Helvetica-Bold", 8)
    cols = [margin, margin + 75, margin + 150, margin + 250, margin + 365, margin + 455]
    for x, head in zip(cols, ["Load", "BOL", "Carrier", "Origin", "Destination", "Total"]):
        c.drawString(x, y, head)
    y -= 8
    c.line(margin, y, w - margin, y)
    y -= 17
    c.setFont("Helvetica", 7.8)
    for load in loads:
        c.drawString(cols[0], y, load.load_id)
        c.drawString(cols[1], y, load.bol_number)
        c.drawString(cols[2], y, load.carrier[:22])
        c.drawString(cols[3], y, load.origin[:20])
        c.drawString(cols[4], y, load.destination[:20])
        c.drawRightString(w - margin, y, dollars(load.invoice_total))
        y -= 15
    c.showPage()
    c.save()


def slug(text: str) -> str:
    return "".join(ch.lower() for ch in text if ch.isalnum())[:18]


def random_digits(seed: str, n: int) -> str:
    rng = random.Random(seed)
    return "".join(str(rng.randrange(10)) for _ in range(n))


def dirty_pdf(clean_pdf: Path, dirty_pdf_path: Path, seed: int) -> None:
    rng = random.Random(seed)
    src = fitz.open(clean_pdf)
    out = fitz.open()
    for page in src:
        zoom = rng.choice([1.15, 1.3, 1.45])
        pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
        image = Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")
        if rng.random() < 0.75:
            image = image.convert("L").convert("RGB")
        image = image.rotate(rng.uniform(-2.2, 2.2), expand=True, fillcolor=(245, 245, 245))
        image = ImageEnhance.Contrast(image).enhance(rng.uniform(0.82, 1.25))
        image = ImageEnhance.Brightness(image).enhance(rng.uniform(0.86, 1.08))
        if rng.random() < 0.8:
            image = image.filter(ImageFilter.GaussianBlur(radius=rng.uniform(0.25, 0.9)))
        if rng.random() < 0.65:
            w, h = image.size
            image = image.resize((max(1, int(w * 0.72)), max(1, int(h * 0.72))))
            image = image.resize((w, h))
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=rng.randrange(42, 72))
        rect = fitz.Rect(0, 0, LETTER[0], LETTER[1])
        page_out = out.new_page(width=LETTER[0], height=LETTER[1])
        page_out.insert_image(rect, stream=buf.getvalue())
    out.save(dirty_pdf_path)
    out.close()
    src.close()


def carrier_invoice_truth(load: LoadRecord) -> dict:
    return {
        "invoice_number": load.invoice_number,
        "carrier_name": load.carrier,
        "load_or_pro_number": load.load_id,
        "linehaul_amount": float(d(load.invoice_linehaul)),
        "fuel_surcharge": float(d(load.invoice_fuel)),
        "accessorials": [
            {"name": charge.name, "amount": float(d(charge.amount))}
            for charge in load.invoice_accessorials
        ],
        "total_amount": float(d(load.invoice_total)),
        "invoice_date": load.delivery_date,
    }


def generate(out_dir: Path, loads_count: int, seed: int) -> None:
    clean_dir = out_dir / "clean"
    dirty_dir = out_dir / "dirty"
    truth_dir = out_dir / "ground_truth"
    for path in (clean_dir, dirty_dir, truth_dir):
        path.mkdir(parents=True, exist_ok=True)

    loads = build_loads(loads_count, seed)
    invoice_truth: dict[str, dict] = {}
    load_truth: dict[str, dict] = {}

    for idx, load in enumerate(loads, start=1):
        stem = f"{idx:03d}_{load.load_id}"
        docs = {
            "rate_confirmation": clean_dir / f"{stem}_rate_confirmation.pdf",
            "carrier_invoice": clean_dir / f"{stem}_carrier_invoice.pdf",
            "bol": clean_dir / f"{stem}_bol.pdf",
            "pod": clean_dir / f"{stem}_pod.pdf",
        }
        draw_rate_confirmation(docs["rate_confirmation"], load)
        draw_carrier_invoice(docs["carrier_invoice"], load)
        draw_bol(docs["bol"], load)
        if load.scenario != "missing_pod":
            draw_pod(docs["pod"], load)
        else:
            docs.pop("pod")

        if any(c.name == "lumper" and c.backup_document for c in load.invoice_accessorials):
            lumper_path = clean_dir / f"{stem}_lumper_receipt.pdf"
            draw_lumper_receipt(lumper_path, load, next(c.amount for c in load.invoice_accessorials if c.name == "lumper"))
            docs["lumper_receipt"] = lumper_path

        if idx % 4 == 0:
            fuel_path = clean_dir / f"{stem}_fuel_receipt.pdf"
            draw_fuel_receipt(fuel_path, load)
            docs["fuel_receipt"] = fuel_path

        for doc_type, pdf_path in docs.items():
            dirty_path = dirty_dir / pdf_path.name.replace(".pdf", "_dirty.pdf")
            dirty_pdf(pdf_path, dirty_path, seed + idx * 31 + len(doc_type))
            load.documents[doc_type] = str(pdf_path.relative_to(out_dir))
            load.documents[f"{doc_type}_dirty"] = str(dirty_path.relative_to(out_dir))

        inv_clean_name = docs["carrier_invoice"].name
        inv_dirty_name = docs["carrier_invoice"].name.replace(".pdf", "_dirty.pdf")
        invoice_truth[inv_clean_name] = carrier_invoice_truth(load)
        invoice_truth[inv_dirty_name] = carrier_invoice_truth(load)
        load_truth[load.load_id] = asdict(load)

    for chunk_start in range(0, len(loads), 5):
        group = loads[chunk_start:chunk_start + 5]
        manifest_id = f"MAN-BATCH-{chunk_start // 5 + 1:02d}"
        manifest_path = clean_dir / f"{manifest_id.lower()}_manifest.pdf"
        draw_manifest(manifest_path, group, manifest_id)
        dirty_pdf(manifest_path, dirty_dir / f"{manifest_id.lower()}_manifest_dirty.pdf", seed + chunk_start + 997)

    (truth_dir / "carrier_invoice_extraction.json").write_text(
        json.dumps(invoice_truth, indent=2), encoding="utf-8"
    )
    (truth_dir / "loads_and_scenarios.json").write_text(
        json.dumps(load_truth, indent=2), encoding="utf-8"
    )
    (out_dir / "README.md").write_text(corpus_readme(loads_count), encoding="utf-8")

    print(f"Wrote synthetic freight corpus to {out_dir}")
    print(f"Clean PDFs: {len(list(clean_dir.glob('*.pdf')))}")
    print(f"Dirty PDFs: {len(list(dirty_dir.glob('*.pdf')))}")
    print(f"Carrier invoice eval truth: {truth_dir / 'carrier_invoice_extraction.json'}")


def corpus_readme(loads_count: int) -> str:
    return f"""# Synthetic Freight Corpus

Generated by `scripts/generate_realistic_corpus.py`.

This corpus uses public freight-template structure patterns, but all business data is synthetic.
It contains {loads_count} internally consistent fictional loads plus deliberate variance
scenarios and dirty scan variants.

Folders:

- `clean/`: clean generated PDFs.
- `dirty/`: degraded scan-like PDF variants.
- `ground_truth/carrier_invoice_extraction.json`: invoice extraction labels.
- `ground_truth/loads_and_scenarios.json`: load-level truth, document map, and expected outcomes.

Do not edit generated files by hand. Regenerate instead.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(DEFAULT_OUT), help="Output corpus directory")
    parser.add_argument("--loads", type=int, default=18, help="Number of synthetic loads")
    parser.add_argument("--seed", type=int, default=42, help="Deterministic random seed")
    args = parser.parse_args()

    generate(Path(args.out), args.loads, args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
