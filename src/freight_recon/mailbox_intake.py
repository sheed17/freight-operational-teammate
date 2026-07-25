"""Mailbox intake worker for the Phase A "agent waits in the inbox" gate.

This module is deliberately transport-shaped but local-first. A real Gmail/IMAP/API watcher can
feed the same :class:`MailboxMessageRecord` contract later; the controlled dogfood path watches a
directory of ``.eml`` files, preserves raw messages, dedupes them durably, and reassembles touched
load packets through the existing ingestion pipeline.

Email is inbound intake only. This module never sends email and never makes money decisions.
"""

from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from .email_triage import ROUTE_IGNORE, ROUTE_PROCESS, Completer, triage_email
from .ingestion import (
    AttachmentTextExtractor,
    IngestedPacket,
    LoadIndex,
    ParsedEmail,
    ingest_emails,
    link_attachment,
    parse_eml,
    subject_load_hint,
)
from .reconciliation import FreightLoadForReconciliation


class MailboxMessageRecord(BaseModel):
    """A preserved inbound email and the identifiers needed to dedupe and reprocess it."""

    source_path: str
    preserved_path: str
    sha256: str
    message_id: str | None = None
    from_addr: str | None = None
    to_addr: str | None = None
    subject: str = ""
    date_header: str | None = None
    email_timestamp: str | None = None
    in_reply_to: str | None = None
    references: list[str] = Field(default_factory=list)
    thread_key: str | None = None
    received_at: str
    attachment_count: int = 0
    attachment_names: list[str] = Field(default_factory=list)
    hinted_load_id: str | None = None
    linked_load_ids: list[str] = Field(default_factory=list)
    packet_load_id: str | None = None
    duplicate_of: str | None = None
    # Set only when a triage completer is supplied (the relevance gate for a real inbox).
    triage_route: str | None = None       # process | ask | ignore
    triage_relevance: str | None = None   # freight_ops | noise | uncertain
    triage_reason: str | None = None


class MailboxState(BaseModel):
    """Durable mailbox watcher state.

    ``processed_keys`` stores both content hashes and message ids, so repeated files or forwarded
    replays with the same ``Message-ID`` are not processed twice.
    """

    processed_keys: list[str] = Field(default_factory=list)
    messages: list[MailboxMessageRecord] = Field(default_factory=list)


class MailboxPacketRun(BaseModel):
    load_id: str
    source_message_count: int
    packet: IngestedPacket


class MailboxPollResult(BaseModel):
    inbox_dir: str
    preserve_dir: str
    state_path: str
    scanned: int
    new_messages: list[MailboxMessageRecord] = Field(default_factory=list)
    duplicates: list[MailboxMessageRecord] = Field(default_factory=list)
    packet_runs: list[MailboxPacketRun] = Field(default_factory=list)
    unlinked_messages: list[MailboxMessageRecord] = Field(default_factory=list)
    noise_ignored: list[MailboxMessageRecord] = Field(default_factory=list)


def run_mailbox_intake(
    *,
    inbox_dir: str | Path,
    preserve_dir: str | Path,
    state_path: str | Path,
    loads: list[FreightLoadForReconciliation],
    attachment_text_extractor: AttachmentTextExtractor | None = None,
    triage_completer: Completer | None = None,
) -> MailboxPollResult:
    """Poll a controlled inbound mailbox directory and reprocess touched packet groups.

    The worker scans ``*.eml`` files, preserves new raw messages under ``preserve_dir/messages``,
    updates durable state, then groups all preserved messages by linked load and runs the existing
    packet ingestion over each group. Reprocessing all preserved messages for a touched load lets
    trickle-in documents update an existing packet without losing context.

    When ``triage_completer`` is supplied, every new message passes through the email-triage relevance
    gate (see :mod:`freight_recon.email_triage`): noise is recorded and excluded from packet assembly,
    and a confident model fuzzy-link fills ``packet_load_id`` for a freight email that carried no clean
    identifier. Without it, behavior is unchanged (deterministic identifier linking only).
    """

    inbox = Path(inbox_dir)
    preserve = Path(preserve_dir)
    state_file = Path(state_path)
    messages_dir = preserve / "messages"
    messages_dir.mkdir(parents=True, exist_ok=True)
    state_file.parent.mkdir(parents=True, exist_ok=True)

    state = load_mailbox_state(state_file)
    processed = set(state.processed_keys)
    index = LoadIndex(loads)

    new_records: list[MailboxMessageRecord] = []
    duplicates: list[MailboxMessageRecord] = []
    eml_paths = sorted(inbox.glob("*.eml"))
    for source in eml_paths:
        raw = source.read_bytes()
        sha = _sha256(raw)
        parsed = parse_eml(source, attachment_text_extractor=attachment_text_extractor)
        keys = _message_keys(sha, parsed.message_id)
        if processed.intersection(keys):
            duplicates.append(
                _record_for_message(
                    source=source,
                    preserved_path=_existing_preserved_path(state, sha) or "",
                    sha256=sha,
                    parsed=parsed,
                    index=index,
                    duplicate_of=next((key for key in keys if key in processed), None),
                )
            )
            continue

        preserved_path = messages_dir / f"{_safe_stem(source.stem)}_{sha[:12]}.eml"
        shutil.copy2(source, preserved_path)
        record = _record_for_message(
            source=source,
            preserved_path=preserved_path,
            sha256=sha,
            parsed=parsed,
            index=index,
        )
        if triage_completer is not None:
            _apply_triage(record, parsed, index, loads, triage_completer)
        state.messages.append(record)
        new_records.append(record)
        processed.update(keys)

    state.processed_keys = sorted(processed)
    state_file.write_text(json.dumps(state.model_dump(mode="json"), indent=2), encoding="utf-8")

    packet_runs, unlinked, noise = _assemble_packets(
        state.messages,
        loads,
        attachment_text_extractor=attachment_text_extractor,
    )
    return MailboxPollResult(
        inbox_dir=str(inbox),
        preserve_dir=str(preserve),
        state_path=str(state_file),
        scanned=len(eml_paths),
        new_messages=new_records,
        duplicates=duplicates,
        packet_runs=packet_runs,
        unlinked_messages=unlinked,
        noise_ignored=noise,
    )


def load_mailbox_state(path: str | Path) -> MailboxState:
    state_path = Path(path)
    if not state_path.exists():
        return MailboxState()
    return MailboxState.model_validate(json.loads(state_path.read_text(encoding="utf-8")))


def _assemble_packets(
    records: list[MailboxMessageRecord],
    loads: list[FreightLoadForReconciliation],
    attachment_text_extractor: AttachmentTextExtractor | None = None,
) -> tuple[list[MailboxPacketRun], list[MailboxMessageRecord], list[MailboxMessageRecord]]:
    by_load: dict[str, list[MailboxMessageRecord]] = {}
    unlinked: list[MailboxMessageRecord] = []
    noise: list[MailboxMessageRecord] = []
    for record in records:
        # Triage noise never enters packet assembly — it is recorded (audit) and dropped, not acted on.
        if record.triage_route == ROUTE_IGNORE:
            noise.append(record)
            continue
        load_id = record.packet_load_id
        if not load_id:
            unlinked.append(record)
            continue
        by_load.setdefault(load_id, []).append(record)

    packets: list[MailboxPacketRun] = []
    for load_id, grouped in sorted(by_load.items()):
        parsed: list[ParsedEmail] = []
        for record in grouped:
            preserved = Path(record.preserved_path)
            if preserved.exists():
                parsed.append(parse_eml(preserved, attachment_text_extractor=attachment_text_extractor))
        if not parsed:
            continue
        packets.append(
            MailboxPacketRun(
                load_id=load_id,
                source_message_count=len(parsed),
                packet=ingest_emails(parsed, loads),
            )
        )
    return packets, unlinked, noise


def _apply_triage(
    record: MailboxMessageRecord,
    parsed: ParsedEmail,
    index: LoadIndex,
    loads: list[FreightLoadForReconciliation],
    complete: Completer,
) -> None:
    """Run the relevance gate on one message and fold its verdict into the record (mutates in place)."""
    decision = triage_email(parsed, index, loads, complete=complete)
    record.triage_route = decision.route
    record.triage_relevance = decision.relevance
    record.triage_reason = decision.reason
    # A confident model fuzzy-link supplies the load a clean identifier could not (the whole point of
    # the layer). The deterministic identifier link, when present, is never overridden.
    if decision.route == ROUTE_PROCESS and not record.packet_load_id and decision.load_id:
        record.packet_load_id = decision.load_id


def _record_for_message(
    *,
    source: Path,
    preserved_path: str | Path,
    sha256: str,
    parsed: ParsedEmail,
    index: LoadIndex,
    duplicate_of: str | None = None,
) -> MailboxMessageRecord:
    linked_ids: set[str] = set()
    for attachment in parsed.attachments:
        linked, _, _ = link_attachment(
            attachment.filename,
            parsed.subject,
            index,
            text_hint=attachment.text_hint,
        )
        if linked:
            linked_ids.add(linked)
    hint = subject_load_hint(parsed.subject, index)
    return MailboxMessageRecord(
        source_path=str(source),
        preserved_path=str(preserved_path),
        sha256=sha256,
        message_id=parsed.message_id,
        from_addr=parsed.from_addr,
        to_addr=parsed.to_addr,
        subject=parsed.subject,
        date_header=parsed.date_header,
        email_timestamp=parsed.email_timestamp,
        in_reply_to=parsed.in_reply_to,
        references=parsed.references,
        thread_key=parsed.thread_key,
        received_at=datetime.now(timezone.utc).isoformat(),
        attachment_count=len(parsed.attachments),
        attachment_names=[attachment.filename for attachment in parsed.attachments],
        hinted_load_id=hint,
        linked_load_ids=sorted(linked_ids),
        packet_load_id=_packet_load_for_message(hint, linked_ids),
        duplicate_of=duplicate_of,
    )


def _packet_load_for_message(hint: str | None, linked_ids: set[str]) -> str | None:
    """Choose the packet owner for a whole email.

    A single inbound email is usually about one load; wrong-load/noise attachments inside it must
    be flagged by the packet ingestion step, not used to spawn separate packet runs. Prefer the
    subject/load hint when present, otherwise use a unanimous attachment-linked load. Ambiguous
    multi-load emails without a subject hint stay unlinked for human review.
    """
    if hint:
        return hint
    if len(linked_ids) == 1:
        return next(iter(linked_ids))
    return None


def _message_keys(sha256: str, message_id: str | None) -> set[str]:
    keys = {f"sha256:{sha256}"}
    if message_id:
        keys.add(f"message_id:{message_id.strip()}")
    return keys


def _existing_preserved_path(state: MailboxState, sha256: str) -> str | None:
    for record in state.messages:
        if record.sha256 == sha256:
            return record.preserved_path
    return None


def _sha256(raw: bytes) -> str:
    import hashlib

    return hashlib.sha256(raw).hexdigest()


def _safe_stem(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "_" for ch in value)
    return cleaned[:80] or "message"
