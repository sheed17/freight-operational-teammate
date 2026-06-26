"""Inbound email ingestion: parse → classify → link → assemble a packet.

This is the Stage 2 document-intelligence spine. It answers the operational question "are we
extracting the *right* documents?" by turning a set of inbound emails (with PDF attachments) into a
typed, confidence-scored packet assessment, linked to a known load, with noise and missing-document
flags — *before* any extraction or money decision.

Design rules (consistent with the rest of the engine):

- Deterministic, typed, and explainable. Every attachment lands in a bucket with a confidence and a
  reason; nothing is silently attributed to a load.
- The **load linker is the safety mechanism.** An attachment is only treated as part of a packet if
  it links to that packet's load via a known identifier (load id / invoice / PRO / BOL). A
  carrier invoice for a *different* load, or an unrelated document, fails to link and is flagged —
  it cannot contaminate the packet.
- Anything low-confidence, unlinked, extraneous, or missing a required document routes to a human
  (`needs_human`), never to autonomous processing.

This V0 classifies on filename/subject signals (a stand-in for OCR/content signals). The model-based
vision classifier slots in behind the same `DocClassification` contract later, raising accuracy on
messy real-world filenames without changing the pipeline or the linker.
"""

from __future__ import annotations

import email
import hashlib
import re
from email.message import EmailMessage as MimeMessage
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, Field

from .email_corpus import REQUIRED_DOC_TYPES
from .reconciliation import FreightLoadForReconciliation

# Ordered most-specific-first so "carrier_invoice" wins over a bare "invoice".
_DOC_TOKENS: list[tuple[str, list[str]]] = [
    ("rate_confirmation", ["rate_confirmation", "rate_con", "ratecon", "rateconf", "confirmation"]),
    ("carrier_invoice", ["carrier_invoice", "invoice", "freight_bill", "freightbill"]),
    ("pod", ["pod", "proof_of_delivery", "delivery_receipt", "signed_bol"]),
    ("bol", ["bol", "bill_of_lading", "billoflading"]),
    ("lumper_receipt", ["lumper"]),
    ("fuel_receipt", ["fuel"]),
    ("manifest", ["manifest"]),
]
_STRONG_TOKENS = {"carrier_invoice", "rate_confirmation", "rate_con", "ratecon", "pod", "bol", "lumper", "fuel", "manifest"}

_LOAD_ID_RE = re.compile(r"[A-Z]{2}-\d{6}")
_INVOICE_RE = re.compile(r"INV-?\d+", re.IGNORECASE)
_PRO_RE = re.compile(r"PRO-?\w+", re.IGNORECASE)
_BOL_RE = re.compile(r"BOL-?\d+", re.IGNORECASE)

_CLASSIFICATION_THRESHOLD = 0.75
_LINK_THRESHOLD = 0.75


class ParsedAttachment(BaseModel):
    filename: str
    content_type: str
    sha256: str
    size_bytes: int
    text_hint: str = ""


class ParsedEmail(BaseModel):
    message_id: str | None = None
    from_addr: str | None = None
    to_addr: str | None = None
    date_header: str | None = None
    email_timestamp: str | None = None
    in_reply_to: str | None = None
    references: list[str] = Field(default_factory=list)
    thread_key: str | None = None
    subject: str = ""
    attachments: list[ParsedAttachment] = Field(default_factory=list)


class DocClassification(BaseModel):
    doc_type: str
    confidence: float
    reason: str


class AttachmentAssessment(BaseModel):
    filename: str
    sha256: str
    classification: DocClassification
    linked_load_id: str | None = None
    link_confidence: float = 0.0
    link_reason: str = ""
    belongs_to_packet: bool = False
    flags: list[str] = Field(default_factory=list)


class IngestedPacket(BaseModel):
    packet_load_id: str | None = None
    link_confidence: float = 0.0
    attachments: list[AttachmentAssessment] = Field(default_factory=list)
    delivered_doc_types: list[str] = Field(default_factory=list)
    missing_required: list[str] = Field(default_factory=list)
    extraneous_attachments: int = 0
    needs_human: bool = True
    flags: list[str] = Field(default_factory=list)


class LoadIndex:
    """Source-of-truth identifier index used to link attachments to a known load."""

    def __init__(self, loads: list[FreightLoadForReconciliation]) -> None:
        self.by_load_id: dict[str, str] = {}
        self.by_invoice: dict[str, str] = {}
        self.by_pro: dict[str, str] = {}
        self.by_bol: dict[str, str] = {}
        for load in loads:
            self.by_load_id[load.load_id.upper()] = load.load_id
            if load.invoice_number:
                self.by_invoice[_norm(load.invoice_number)] = load.load_id
            if load.pro_number:
                self.by_pro[_norm(load.pro_number)] = load.load_id
            if load.bol_number:
                self.by_bol[_norm(load.bol_number)] = load.load_id


AttachmentTextExtractor = Callable[[bytes, str, str], str]


def parse_eml(source: str | Path, attachment_text_extractor: AttachmentTextExtractor | None = None) -> ParsedEmail:
    """Parse a .eml file (path) or raw MIME string into a typed :class:`ParsedEmail`."""
    if _looks_like_path(source):
        mime: MimeMessage = email.message_from_bytes(Path(source).read_bytes())
    else:
        mime = email.message_from_string(str(source))
    attachments: list[ParsedAttachment] = []
    for part in mime.walk():
        if part.get_content_disposition() != "attachment":
            continue
        payload = part.get_payload(decode=True) or b""
        filename = part.get_filename() or "attachment"
        content_type = part.get_content_type()
        text_hint = _pdf_text_hint(payload, content_type, filename)
        if attachment_text_extractor is not None:
            extra_hint = attachment_text_extractor(payload, filename, content_type)
            if extra_hint:
                text_hint = f"{text_hint}\n{extra_hint}".strip()
        attachments.append(
            ParsedAttachment(
                filename=filename,
                content_type=content_type,
                sha256=hashlib.sha256(payload).hexdigest(),
                size_bytes=len(payload),
                text_hint=text_hint,
            )
        )
    return ParsedEmail(
        message_id=mime.get("Message-ID"),
        from_addr=mime.get("From"),
        to_addr=mime.get("To"),
        date_header=mime.get("Date"),
        email_timestamp=_parse_email_timestamp(mime.get("Date")),
        in_reply_to=mime.get("In-Reply-To"),
        references=_split_message_id_header(mime.get("References")),
        thread_key=_thread_key(mime),
        subject=mime.get("Subject", ""),
        attachments=attachments,
    )


def classify_attachment(filename: str, subject: str = "") -> DocClassification:
    """Classify an attachment's document type from filename/subject signals, with confidence."""
    name = filename.lower()
    for doc_type, tokens in _DOC_TOKENS:
        for token in tokens:
            if token in name:
                strong = token in _STRONG_TOKENS or token == doc_type
                return DocClassification(
                    doc_type=doc_type,
                    confidence=0.95 if strong else 0.8,
                    reason=f"filename token '{token}'",
                )
    subject_lower = subject.lower()
    for doc_type, tokens in _DOC_TOKENS:
        for token in tokens:
            if token in subject_lower:
                return DocClassification(doc_type=doc_type, confidence=0.6, reason=f"subject token '{token}'")
    return DocClassification(doc_type="unknown", confidence=0.2, reason="no document-type signal")


def link_attachment(
    filename: str,
    subject: str,
    index: LoadIndex,
    *,
    text_hint: str = "",
) -> tuple[str | None, float, str]:
    """Link an attachment to a known load via identifiers in its own filename or PDF text.

    Filename identifiers are the strongest per-attachment signal. If the filename is generic, a
    bounded PDF text hint can still link the document to a load. The ``subject`` is NOT used here:
    a subject names the email, not each attachment, so letting it bleed into per-attachment linking
    would let a generic-filename foreign document inherit the packet's load id. Subject text is
    handled separately as a packet-level hint (see :func:`subject_load_hint`).
    """
    linked = _link_from_text(filename, index)
    if linked[0]:
        return linked
    linked = _link_from_text(text_hint, index, confidence_offset=-0.07, source="PDF text")
    if linked[0]:
        return linked
    return None, 0.0, "no known identifier in filename or PDF text"


def _link_from_text(
    text: str,
    index: LoadIndex,
    *,
    confidence_offset: float = 0.0,
    source: str = "filename",
) -> tuple[str | None, float, str]:
    for match in _LOAD_ID_RE.findall(text):
        load_id = index.by_load_id.get(match.upper())
        if load_id:
            return load_id, 0.95 + confidence_offset, f"{source} load id {match}"
    for match in _INVOICE_RE.findall(text):
        load_id = index.by_invoice.get(_norm(match))
        if load_id:
            return load_id, 0.9 + confidence_offset, f"{source} invoice {match}"
    for match in _BOL_RE.findall(text):
        load_id = index.by_bol.get(_norm(match))
        if load_id:
            return load_id, 0.88 + confidence_offset, f"{source} BOL {match}"
    for match in _PRO_RE.findall(text):
        load_id = index.by_pro.get(_norm(match))
        if load_id:
            return load_id, 0.85 + confidence_offset, f"{source} PRO {match}"
    return None, 0.0, "no known identifier in filename"


def subject_load_hint(subject: str, index: LoadIndex) -> str | None:
    """Resolve a packet-level load hint from the email subject (a hint only, not per-attachment)."""
    for match in _LOAD_ID_RE.findall(subject):
        load_id = index.by_load_id.get(match.upper())
        if load_id:
            return load_id
    for match in _INVOICE_RE.findall(subject):
        load_id = index.by_invoice.get(_norm(match))
        if load_id:
            return load_id
    return None


def ingest_emails(emails: list[ParsedEmail], loads: list[FreightLoadForReconciliation]) -> IngestedPacket:
    """Assemble one packet from a set of inbound emails, linked to a known load.

    Belonging is decided by **filename** identifiers, not the email subject. An attachment with no
    identifier of its own is never silently attributed to the packet; if the subject names the
    packet load it is flagged ``linked_by_subject_only`` and routed to a human (it does not count
    toward delivered documents). This closes the contamination path where a generic-filename foreign
    document under a packet-load subject would otherwise be treated as belonging.
    """
    index = LoadIndex(loads)
    rows: list[tuple[AttachmentAssessment, str | None]] = []
    filename_votes: dict[str, int] = {}

    for parsed in emails:
        hint = subject_load_hint(parsed.subject, index)
        for attachment in parsed.attachments:
            classification = classify_attachment(attachment.filename, parsed.subject)
            linked, link_conf, link_reason = link_attachment(
                attachment.filename,
                parsed.subject,
                index,
                text_hint=attachment.text_hint,
            )
            if linked:
                filename_votes[linked] = filename_votes.get(linked, 0) + 1
            rows.append(
                (
                    AttachmentAssessment(
                        filename=attachment.filename,
                        sha256=attachment.sha256,
                        classification=classification,
                        linked_load_id=linked,
                        link_confidence=link_conf,
                        link_reason=link_reason,
                    ),
                    hint,
                )
            )

    packet_load_id, link_confidence, ambiguous_identity, subject_only_packet = _resolve_packet_load(
        filename_votes, [hint for _, hint in rows if hint]
    )

    delivered: set[str] = set()
    extraneous = 0
    subject_only = False
    for assessment, hint in rows:
        if assessment.linked_load_id:
            assessment.belongs_to_packet = bool(packet_load_id) and assessment.linked_load_id == packet_load_id
            if assessment.belongs_to_packet:
                if assessment.classification.doc_type != "unknown":
                    delivered.add(assessment.classification.doc_type)
                if assessment.classification.confidence < _CLASSIFICATION_THRESHOLD:
                    assessment.flags.append("low_confidence_classification")
            else:
                extraneous += 1
                assessment.flags.append("does_not_belong_to_packet")
        elif packet_load_id and hint == packet_load_id:
            # No identifier in the filename; the subject names the packet load. Tentative only —
            # surfaced for human confirmation, never counted toward delivered documents.
            assessment.linked_load_id = packet_load_id
            assessment.link_confidence = 0.5
            assessment.link_reason = "subject-only load id (unverified)"
            assessment.belongs_to_packet = False
            assessment.flags.append("linked_by_subject_only")
            subject_only = True
        else:
            assessment.belongs_to_packet = False
            assessment.flags.append("unlinked_attachment")

    missing = [doc for doc in REQUIRED_DOC_TYPES if doc not in delivered]
    flags: list[str] = []
    if packet_load_id is None:
        flags.append("unlinked_packet")
    if subject_only_packet:
        flags.append("subject_only_packet")
    if ambiguous_identity:
        flags.append("ambiguous_packet_load")
    if missing:
        flags.append("missing_documents")
    if extraneous:
        flags.append("extraneous_attachment")
    if subject_only:
        flags.append("unverified_subject_only_attachment")
    if link_confidence < _LINK_THRESHOLD:
        flags.append("low_link_confidence")
    if any(a.classification.doc_type == "unknown" for a, _ in rows):
        flags.append("unknown_document")

    needs_human = bool(flags)
    return IngestedPacket(
        packet_load_id=packet_load_id,
        link_confidence=round(link_confidence, 3),
        attachments=[assessment for assessment, _ in rows],
        delivered_doc_types=sorted(delivered),
        missing_required=missing,
        extraneous_attachments=extraneous,
        needs_human=needs_human,
        flags=flags,
    )


def _resolve_packet_load(
    filename_votes: dict[str, int],
    subject_hints: list[str],
) -> tuple[str | None, float, bool, bool]:
    """Pick the packet's load from filename links (authoritative), else a unanimous subject hint.

    Returns ``(packet_load_id, link_confidence, ambiguous_identity, subject_only_packet)``.
    """
    if filename_votes:
        total = sum(filename_votes.values())
        top = max(filename_votes.values())
        winners = sorted(k for k, v in filename_votes.items() if v == top)
        packet_load_id = winners[0]
        # Ambiguous when there is a tie or the top load is not a strict majority of linked attachments.
        ambiguous = len(winners) > 1 or top * 2 <= total
        return packet_load_id, top / total, ambiguous, False
    unique_hints = set(subject_hints)
    if len(unique_hints) == 1:
        # No filename links at all; fall back to a single subject hint, but flag it as weak.
        return next(iter(unique_hints)), 0.5, False, True
    return None, 0.0, len(unique_hints) > 1, False


def ingest_eml_paths(
    paths: list[str | Path],
    loads: list[FreightLoadForReconciliation],
    *,
    attachment_text_extractor: AttachmentTextExtractor | None = None,
) -> IngestedPacket:
    return ingest_emails([parse_eml(path, attachment_text_extractor=attachment_text_extractor) for path in paths], loads)


def _norm(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", value).upper()


def _looks_like_path(source: str | Path) -> bool:
    if isinstance(source, Path):
        return True
    return "\n" not in source and source.lower().endswith(".eml")


def _pdf_text_hint(payload: bytes, content_type: str, filename: str) -> str:
    if content_type != "application/pdf" and not filename.lower().endswith(".pdf"):
        return ""
    try:
        import fitz

        with fitz.open(stream=payload, filetype="pdf") as doc:
            text = "\n".join(doc[index].get_text("text") for index in range(min(len(doc), 2)))
    except Exception:
        return ""
    return text[:5000]


def _parse_email_timestamp(date_header: str | None) -> str | None:
    if not date_header:
        return None
    try:
        parsed = parsedate_to_datetime(date_header)
    except (TypeError, ValueError, IndexError, OverflowError):
        return None
    return parsed.isoformat()


def _split_message_id_header(value: str | None) -> list[str]:
    if not value:
        return []
    return re.findall(r"<[^>]+>", value)


def _thread_key(mime: MimeMessage) -> str | None:
    references = _split_message_id_header(mime.get("References"))
    if references:
        return references[0]
    in_reply_to = mime.get("In-Reply-To")
    if in_reply_to:
        ids = _split_message_id_header(in_reply_to)
        return ids[0] if ids else in_reply_to.strip()
    message_id = mime.get("Message-ID")
    if message_id:
        return message_id.strip()
    subject = mime.get("Subject", "")
    if subject:
        return f"subject:{re.sub(r'^(re|fwd?):\\s*', '', subject.strip().lower())}"
    return None
