"""Synthetic inbound-email corpus: simulate documents arriving by email at full fidelity.

This is the Stage 2 proving ground. Real freight packets arrive as email threads with PDF
attachments that trickle in over time, sometimes with the wrong attachment, an unrelated document,
or a missing POD. To know we are extracting the *right* documents, we need a corpus where the truth
is hidden but known: which attachment is which document type, and which load each one actually
belongs to.

This module consumes the existing realistic corpus (loads + generated PDFs) and emits, per load:

- one or more real ``.eml`` inbound emails with the actual PDF bytes attached, and
- a hidden-truth manifest (``ground_truth/email_packets.json``) giving the true doc type and true
  linked load for every attachment, plus the required/delivered/missing document sets.

A later document classifier and load-linker are then measurable against this truth: doc-type
accuracy, mis-link rate, noise rejection, and missing-document detection.

Corpus assumption: synthetic noise attachments currently carry self-identifying filenames (they
embed the *other* load's id), so the linker catches them on filename alone. Real inbound scans are
often generically named (``DOC001.pdf``); the ingestion linker handles that by refusing to attribute
a generic-filename attachment to a packet on subject text alone (it is flagged for human review, not
counted). A future corpus variant should add generic-filename noise to exercise that path directly.
"""

from __future__ import annotations

import json
import random
import shutil
from email.message import EmailMessage as MimeMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from pydantic import BaseModel, Field

from .reconciliation import FreightLoadForReconciliation

# What a broker requires on a carrier-payables packet before a voucher can be paid (mirrors the
# mock TMS required-document checklist).
REQUIRED_DOC_TYPES = ["rate_confirmation", "carrier_invoice", "pod"]

# The fixed, deterministic scenario rotation. Each one stresses a different "right document" risk.
_SCENARIOS = [
    "single_email_complete",
    "trickle_pod_later",
    "extra_unrelated_attachment",
    "wrong_load_attachment",
    "missing_pod",
    "forwarded_thread",
]


class EmailAttachmentTruth(BaseModel):
    filename: str
    doc_type: str  # true document type, or "unrelated"
    links_to_load: str | None  # the load this attachment actually belongs to (differs for noise)
    is_noise: bool = False


class InboundEmailTruth(BaseModel):
    message_id: str
    sequence: int
    from_addr: str
    to_addr: str
    subject: str
    date: str
    eml_path: str
    attachments: list[EmailAttachmentTruth] = Field(default_factory=list)


class EmailPacketTruth(BaseModel):
    load_id: str
    carrier: str
    scenario: str
    required_doc_types: list[str]
    delivered_doc_types: list[str]
    missing_doc_types: list[str]
    has_noise: bool
    emails: list[InboundEmailTruth] = Field(default_factory=list)


class EmailCorpus(BaseModel):
    output_dir: str
    packets: list[EmailPacketTruth]


def build_email_corpus(
    loads: list[FreightLoadForReconciliation],
    *,
    corpus_dir: Path,
    output_dir: Path,
    seed: int = 42,
) -> EmailCorpus:
    """Emit a synthetic inbound-email corpus with hidden doc-type and load-linkage truth."""
    rng = random.Random(seed)
    inbound_dir = output_dir / "inbound"
    if inbound_dir.exists():
        shutil.rmtree(inbound_dir)
    inbound_dir.mkdir(parents=True, exist_ok=True)
    truth_dir = output_dir / "ground_truth"
    truth_dir.mkdir(parents=True, exist_ok=True)

    load_by_id = {load.load_id: load for load in loads}
    packets: list[EmailPacketTruth] = []
    for index, load in enumerate(loads):
        scenario = _SCENARIOS[index % len(_SCENARIOS)]
        packet = _build_packet(
            load,
            scenario=scenario,
            corpus_dir=corpus_dir,
            inbound_dir=inbound_dir,
            load_by_id=load_by_id,
            rng=rng,
        )
        packets.append(packet)

    corpus = EmailCorpus(output_dir=str(output_dir), packets=packets)
    (truth_dir / "email_packets.json").write_text(
        json.dumps([packet.model_dump(mode="json") for packet in packets], indent=2),
        encoding="utf-8",
    )
    return corpus


def _build_packet(
    load: FreightLoadForReconciliation,
    *,
    scenario: str,
    corpus_dir: Path,
    inbound_dir: Path,
    load_by_id: dict[str, FreightLoadForReconciliation],
    rng: random.Random,
) -> EmailPacketTruth:
    carrier_email = _carrier_email(load.carrier)
    to_addr = "billing@neyma-test-freight.test"

    # Which true documents (clean variants) this load can attach.
    available = _clean_doc_types(load)
    # The broker-required doc types, minus POD when the scenario withholds it.
    delivered_types = [d for d in REQUIRED_DOC_TYPES if d in available]
    if scenario == "missing_pod":
        delivered_types = [d for d in delivered_types if d != "pod"]

    emails: list[InboundEmailTruth] = []
    has_noise = False

    if scenario == "trickle_pod_later":
        first = [d for d in delivered_types if d != "pod"]
        emails.append(
            _write_email(
                load, carrier_email, to_addr, sequence=1,
                subject=f"Invoice {load.invoice_number} – Load {load.load_id}",
                doc_types=first, corpus_dir=corpus_dir, inbound_dir=inbound_dir, rng=rng,
            )
        )
        if "pod" in delivered_types:
            emails.append(
                _write_email(
                    load, carrier_email, to_addr, sequence=2,
                    subject=f"POD attached – Load {load.load_id}",
                    doc_types=["pod"], corpus_dir=corpus_dir, inbound_dir=inbound_dir, rng=rng,
                )
            )
    else:
        subject = f"Invoice {load.invoice_number} / Load {load.load_id} – docs attached"
        if scenario == "forwarded_thread":
            subject = f"Fwd: Fwd: {subject}"
        noise: list[EmailAttachmentTruth] = []
        if scenario == "extra_unrelated_attachment":
            noise = _noise_attachments(load, load_by_id, corpus_dir, inbound_dir, kind="unrelated", rng=rng)
            has_noise = bool(noise)
        elif scenario == "wrong_load_attachment":
            noise = _noise_attachments(load, load_by_id, corpus_dir, inbound_dir, kind="wrong_load", rng=rng)
            has_noise = bool(noise)
        emails.append(
            _write_email(
                load, carrier_email, to_addr, sequence=1, subject=subject,
                doc_types=delivered_types, corpus_dir=corpus_dir, inbound_dir=inbound_dir,
                rng=rng, extra_attachments=noise,
            )
        )

    delivered_set = sorted({d for d in delivered_types})
    missing = [d for d in REQUIRED_DOC_TYPES if d not in delivered_set]
    return EmailPacketTruth(
        load_id=load.load_id,
        carrier=load.carrier,
        scenario=scenario,
        required_doc_types=list(REQUIRED_DOC_TYPES),
        delivered_doc_types=delivered_set,
        missing_doc_types=missing,
        has_noise=has_noise,
        emails=emails,
    )


def _write_email(
    load: FreightLoadForReconciliation,
    from_addr: str,
    to_addr: str,
    *,
    sequence: int,
    subject: str,
    doc_types: list[str],
    corpus_dir: Path,
    inbound_dir: Path,
    rng: random.Random,
    extra_attachments: list[EmailAttachmentTruth] | None = None,
) -> InboundEmailTruth:
    mime = MimeMessage()
    message_id = make_msgid(domain="carrier.test")
    mime["Message-ID"] = message_id
    mime["From"] = from_addr
    mime["To"] = to_addr
    mime["Subject"] = subject
    mime["Date"] = formatdate(localtime=True)
    mime.set_content(
        f"Please see attached for load {load.load_id} (invoice {load.invoice_number}).\n"
        f"Carrier: {load.carrier}\n"
    )

    attachments: list[EmailAttachmentTruth] = []
    for doc_type in doc_types:
        rel = load.documents.get(doc_type)
        if not rel:
            continue
        filename = Path(rel).name
        _attach_pdf(mime, corpus_dir / rel, filename)
        attachments.append(
            EmailAttachmentTruth(filename=filename, doc_type=doc_type, links_to_load=load.load_id)
        )
    for noise in extra_attachments or []:
        attachments.append(noise)
        # Noise attachments reference another load's PDF, attached under its own filename.
        source = corpus_dir / _noise_source_rel(noise)
        if source.exists():
            _attach_pdf(mime, source, noise.filename)

    eml_path = inbound_dir / f"{load.load_id}_{sequence:02d}.eml"
    eml_path.write_text(mime.as_string(), encoding="utf-8")
    return InboundEmailTruth(
        message_id=message_id,
        sequence=sequence,
        from_addr=from_addr,
        to_addr=to_addr,
        subject=subject,
        date=mime["Date"],
        eml_path=str(eml_path),
        attachments=attachments,
    )


def _noise_attachments(
    load: FreightLoadForReconciliation,
    load_by_id: dict[str, FreightLoadForReconciliation],
    corpus_dir: Path,
    inbound_dir: Path,
    *,
    kind: str,
    rng: random.Random,
) -> list[EmailAttachmentTruth]:
    others = [other for lid, other in load_by_id.items() if lid != load.load_id and other.documents]
    if not others:
        return []
    other = rng.choice(others)
    # "wrong_load": a carrier invoice that belongs to a different load (linking must catch it).
    # "unrelated": a non-invoice doc from another load (classifier may type it, linker must not link).
    doc_type = "carrier_invoice" if kind == "wrong_load" else "bol"
    rel = other.documents.get(doc_type) or next(
        (v for k, v in other.documents.items() if not k.endswith("_dirty")), None
    )
    if not rel:
        return []
    return [
        EmailAttachmentTruth(
            filename=f"noise_{Path(rel).name}",
            doc_type=doc_type if kind == "wrong_load" else "unrelated",
            links_to_load=other.load_id,
            is_noise=True,
        )
    ]


def _noise_source_rel(noise: EmailAttachmentTruth) -> str:
    # Filename is "noise_<original>"; recover the original relative path under clean/.
    original = noise.filename[len("noise_") :] if noise.filename.startswith("noise_") else noise.filename
    return f"clean/{original}"


def _attach_pdf(mime: MimeMessage, path: Path, filename: str) -> None:
    if path.exists():
        data = path.read_bytes()
    else:  # pragma: no cover - corpus should always have the file
        data = b"%PDF-1.4 synthetic placeholder"
    mime.add_attachment(data, maintype="application", subtype="pdf", filename=filename)


def _clean_doc_types(load: FreightLoadForReconciliation) -> set[str]:
    return {doc_type for doc_type in load.documents if not doc_type.endswith("_dirty")}


def _carrier_email(carrier: str) -> str:
    slug = "".join(ch.lower() for ch in carrier if ch.isalnum())
    return f"billing+{slug}@example-carrier.test"
