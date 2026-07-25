"""Real inbox discovery for freight document candidates.

This is the first pass at letting Neyma look beyond a manually curated label.
It uses Gmail/IMAP search to find emails likely to contain freight PDFs, scores
them deterministically, and writes only candidate `.eml` files into the controlled
mailbox intake directory. It does not send, delete, mark read, or make money
decisions.
"""

from __future__ import annotations

import hashlib
import imaplib
import re
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

from pydantic import BaseModel, Field

from .imap_mailbox import ImapCredentials
from .ingestion import parse_eml


DEFAULT_GMAIL_QUERY = "has:attachment filename:pdf (invoice OR rate confirmation OR pod OR bol OR freight OR load)"

_POSITIVE_TERMS = {
    "invoice": 0.14,
    "rate confirmation": 0.22,
    "rate con": 0.2,
    "pod": 0.18,
    "proof of delivery": 0.18,
    "bol": 0.18,
    "bill of lading": 0.18,
    "freight": 0.16,
    "carrier": 0.14,
    "load": 0.14,
    "detention": 0.12,
    "lumper": 0.12,
}
_NEGATIVE_TERMS = {
    "receipt from apple",
    "applecare",
    "proof of coverage",
    "registration confirmation",
    "departure packet",
    "account access",
    "new hire",
    "inspection checklist",
    "linux tv",
    "security alert",
    "password",
    "newsletter",
    "promotion",
    "sale",
}


class DiscoveryCandidate(BaseModel):
    message_id: str | None = None
    subject: str = ""
    from_addr: str | None = None
    attachment_names: list[str] = Field(default_factory=list)
    score: float
    reasons: list[str] = Field(default_factory=list)
    written_path: str | None = None
    skipped_existing: bool = False


class DiscoveryResult(BaseModel):
    host: str
    mailbox: str
    gmail_query: str
    dry_run: bool
    searched: int
    candidates: int
    written: int
    skipped_existing: int
    output_dir: str
    rows: list[DiscoveryCandidate] = Field(default_factory=list)


def discover_freight_messages(
    *,
    credentials: ImapCredentials,
    output_dir: str | Path,
    mailbox: str = "INBOX",
    gmail_query: str = DEFAULT_GMAIL_QUERY,
    limit: int = 25,
    min_score: float = 0.45,
    dry_run: bool = False,
) -> DiscoveryResult:
    """Search Gmail via IMAP and write freight candidate messages as `.eml` files."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rows: list[DiscoveryCandidate] = []
    written = 0
    skipped = 0
    with imaplib.IMAP4_SSL(credentials.host, credentials.port) as client:
        client.login(credentials.username, credentials.password)
        _ok(client.select(mailbox, readonly=True), "select mailbox")
        typ, data = client.search(None, "X-GM-RAW", _quote_gmail_query(gmail_query))
        _ok((typ, data), "gmail raw search")
        ids = (data[0].split() if data and data[0] else [])[: max(limit, 0)]
        for message_id in ids:
            typ, fetch_data = client.fetch(message_id, "(BODY.PEEK[])")
            _ok((typ, fetch_data), f"fetch message {message_id.decode('ascii', 'ignore')}")
            raw = _raw_message_bytes(fetch_data)
            if raw is None:
                continue
            candidate = score_message(raw, min_score=min_score)
            if candidate.score < min_score:
                continue
            if not dry_run:
                path = out / _filename_for_message(raw, fallback_id=message_id.decode("ascii", "ignore"))
                if path.exists():
                    candidate.skipped_existing = True
                    skipped += 1
                else:
                    path.write_bytes(raw)
                    candidate.written_path = str(path)
                    written += 1
            rows.append(candidate)
    return DiscoveryResult(
        host=credentials.host,
        mailbox=mailbox,
        gmail_query=gmail_query,
        dry_run=dry_run,
        searched=len(ids),
        candidates=len(rows),
        written=written,
        skipped_existing=skipped,
        output_dir=str(out),
        rows=rows,
    )


def score_message(raw: bytes, *, min_score: float = 0.45) -> DiscoveryCandidate:
    parsed = parse_eml(raw.decode("utf-8", "replace"))
    body_hint = _body_text_hint(raw)
    text = " ".join(
        [
            parsed.subject,
            parsed.from_addr or "",
            " ".join(a.filename for a in parsed.attachments),
            body_hint,
        ]
    ).lower()
    score = 0.0
    reasons: list[str] = []
    pdfs = [a.filename for a in parsed.attachments if a.filename.lower().endswith(".pdf")]
    if pdfs:
        score += 0.18
        reasons.append(f"{len(pdfs)} PDF attachment(s)")
    for term, weight in _POSITIVE_TERMS.items():
        if term in text:
            score += weight
            reasons.append(f"freight term: {term}")
    for term in _NEGATIVE_TERMS:
        if term in text:
            score -= 0.4
            reasons.append(f"negative term: {term}")
    if re.search(r"\b(LD-\d{6}|INV-?\d+|PRO[-\s]?\d{4,}|BOL[-\s]?\d+)\b", text, re.IGNORECASE):
        score += 0.3
        reasons.append("known freight identifier pattern")
    score = max(0.0, min(round(score, 3), 1.0))
    return DiscoveryCandidate(
        message_id=parsed.message_id,
        subject=parsed.subject,
        from_addr=parsed.from_addr,
        attachment_names=[a.filename for a in parsed.attachments],
        score=score,
        reasons=reasons or ["no freight signals"],
    )


def _ok(response, action: str) -> None:
    typ, data = response
    if typ != "OK":
        raise RuntimeError(f"IMAP {action} failed: {data!r}")


def _raw_message_bytes(fetch_data) -> bytes | None:
    for item in fetch_data:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
            return item[1]
    return None


def _quote_gmail_query(query: str) -> str:
    return '"' + query.replace("\\", "\\\\").replace('"', "") + '"'


def _body_text_hint(raw: bytes, *, limit: int = 3000) -> str:
    try:
        message = BytesParser(policy=default).parsebytes(raw)
    except Exception:
        return ""
    chunks: list[str] = []
    if message.is_multipart():
        for part in message.walk():
            if part.get_content_disposition() == "attachment":
                continue
            if part.get_content_type() != "text/plain":
                continue
            try:
                chunks.append(part.get_content())
            except Exception:
                continue
    elif message.get_content_type() == "text/plain":
        try:
            chunks.append(message.get_content())
        except Exception:
            return ""
    return "\n".join(chunks)[:limit]


def _filename_for_message(raw: bytes, *, fallback_id: str) -> str:
    message = BytesParser(policy=default).parsebytes(raw)
    subject = str(message.get("subject") or fallback_id or "message")
    digest = hashlib.sha256(raw).hexdigest()[:16]
    safe_subject = re.sub(r"[^A-Za-z0-9._-]+", "_", subject).strip("_")[:80] or "message"
    return f"{digest}_{safe_subject}.eml"
