"""IMAP/Gmail intake bridge for Neyma's controlled mailbox contract.

This pulls real email bytes into the same local ``.eml`` inbox directory used by
``mailbox_intake``. It does not classify, send, delete, or make money decisions.
By default it uses ``BODY.PEEK[]`` and does not mark messages as read.
"""

from __future__ import annotations

import hashlib
import imaplib
import re
from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

from pydantic import BaseModel, Field


class ImapPullResult(BaseModel):
    host: str
    mailbox: str
    query: str
    dry_run: bool
    matched: int
    fetched: int = 0
    written: int = 0
    skipped_existing: int = 0
    output_dir: str
    message_ids: list[str] = Field(default_factory=list)
    files: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class ImapCredentials:
    host: str
    username: str
    password: str
    port: int = 993


def pull_imap_messages(
    *,
    credentials: ImapCredentials,
    output_dir: str | Path,
    mailbox: str = "INBOX",
    query: str = "UNSEEN",
    limit: int = 10,
    dry_run: bool = False,
) -> ImapPullResult:
    """Fetch matching messages as raw ``.eml`` files into ``output_dir``.

    ``query`` is an IMAP SEARCH expression such as ``UNSEEN`` or ``ALL``. Fetching
    uses ``BODY.PEEK[]`` so providers should not mark messages as read.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    with imaplib.IMAP4_SSL(credentials.host, credentials.port) as client:
        client.login(credentials.username, credentials.password)
        _ok(client.select(mailbox, readonly=True), "select mailbox")
        typ, data = client.search(None, *query.split())
        _ok((typ, data), "search mailbox")
        ids = (data[0].split() if data and data[0] else [])[: max(limit, 0)]
        result = ImapPullResult(
            host=credentials.host,
            mailbox=mailbox,
            query=query,
            dry_run=dry_run,
            matched=len(ids),
            output_dir=str(out),
        )
        if dry_run:
            return result
        for message_id in ids:
            typ, fetch_data = client.fetch(message_id, "(BODY.PEEK[])")
            _ok((typ, fetch_data), f"fetch message {message_id.decode('ascii', 'ignore')}")
            raw = _raw_message_bytes(fetch_data)
            if raw is None:
                continue
            result.fetched += 1
            filename = _filename_for_message(raw, fallback_id=message_id.decode("ascii", "ignore"))
            path = out / filename
            result.message_ids.append(_header_message_id(raw) or message_id.decode("ascii", "ignore"))
            if path.exists():
                result.skipped_existing += 1
                continue
            path.write_bytes(raw)
            result.written += 1
            result.files.append(str(path))
        return result


def _ok(response, action: str) -> None:
    typ, data = response
    if typ != "OK":
        raise RuntimeError(f"IMAP {action} failed: {data!r}")


def _raw_message_bytes(fetch_data) -> bytes | None:
    for item in fetch_data:
        if isinstance(item, tuple) and len(item) >= 2 and isinstance(item[1], bytes):
            return item[1]
    return None


def _filename_for_message(raw: bytes, *, fallback_id: str) -> str:
    digest = hashlib.sha256(raw).hexdigest()[:16]
    subject = _header(raw, "subject") or fallback_id or "message"
    subject = re.sub(r"[^A-Za-z0-9._-]+", "_", subject).strip("_")[:80] or "message"
    return f"{digest}_{subject}.eml"


def _header_message_id(raw: bytes) -> str | None:
    return _header(raw, "message-id")


def _header(raw: bytes, name: str) -> str | None:
    message = BytesParser(policy=default).parsebytes(raw)
    value = message.get(name)
    return str(value) if value else None
