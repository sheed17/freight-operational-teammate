"""Tests for Phase A mailbox intake: the agent waits where inbound work arrives."""

import json
import shutil
from pathlib import Path
import subprocess
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from generate_realistic_corpus import generate  # noqa: E402
from freight_recon.email_corpus import build_email_corpus  # noqa: E402
from freight_recon.mailbox_intake import load_mailbox_state, run_mailbox_intake  # noqa: E402
from freight_recon.reconciliation import FreightLoadForReconciliation  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def _email_corpus(tmp_path, count=12):
    corpus = tmp_path / "corpus"
    generate(corpus, count, seed=42)
    raw = json.loads((corpus / "ground_truth" / "loads_and_scenarios.json").read_text())
    loads = [FreightLoadForReconciliation.from_mapping(item) for item in raw.values()]
    email_out = tmp_path / "email_packets"
    result = build_email_corpus(loads, corpus_dir=corpus, output_dir=email_out, seed=42)
    return corpus, loads, result


def test_mailbox_intake_preserves_new_messages_and_builds_packets(tmp_path):
    _, loads, email_corpus = _email_corpus(tmp_path, count=8)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    packet = next(p for p in email_corpus.packets if p.scenario == "single_email_complete")
    for email in packet.emails:
        shutil.copy2(email.eml_path, inbox / Path(email.eml_path).name)

    result = run_mailbox_intake(
        inbox_dir=inbox,
        preserve_dir=tmp_path / "mailbox",
        state_path=tmp_path / "mailbox" / "mailbox_state.json",
        loads=loads,
    )

    assert result.scanned == len(packet.emails)
    assert len(result.new_messages) == len(packet.emails)
    assert not result.duplicates
    assert all(Path(record.preserved_path).exists() for record in result.new_messages)
    assert all(record.date_header for record in result.new_messages)
    assert all(record.email_timestamp for record in result.new_messages)
    assert all(record.thread_key for record in result.new_messages)
    run = next(p for p in result.packet_runs if p.load_id == packet.load_id)
    assert run.packet.packet_load_id == packet.load_id
    assert run.packet.missing_required == []
    assert run.packet.needs_human is False


def _write_eml(path: Path, subject: str, from_addr: str = "sender@example.com") -> None:
    path.write_text(
        f"From: {from_addr}\nTo: ap@broker.com\nSubject: {subject}\n"
        f"Message-ID: <{abs(hash(subject))}@example.com>\nDate: Mon, 22 Jun 2026 09:00:00 +0000\n\n"
        "body\n",
        encoding="utf-8",
    )


def test_mailbox_intake_triage_ignores_noise_and_processes_freight(tmp_path):
    _, loads, _ = _email_corpus(tmp_path, count=8)
    known = loads[0].load_id
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    # A freight email naming a known load (links deterministically) and a newsletter (noise).
    _write_eml(inbox / "freight.eml", f"Carrier invoice for {known}", from_addr="ap@redline.com")
    _write_eml(inbox / "newsletter.eml", "Logistics Weekly top stories", from_addr="news@logisticsweekly.com")

    # The model is only consulted for the message with no identifier (the newsletter); it calls it noise.
    def triage_model(_prompt: str) -> str:
        return json.dumps({"relevance": "noise", "load_id": None, "confidence": 0.96, "reason": "newsletter"})

    result = run_mailbox_intake(
        inbox_dir=inbox,
        preserve_dir=tmp_path / "mailbox",
        state_path=tmp_path / "mailbox" / "mailbox_state.json",
        loads=loads,
        triage_completer=triage_model,
    )

    # Noise is recorded and excluded from packet assembly; it never becomes work.
    assert len(result.noise_ignored) == 1
    assert result.noise_ignored[0].subject.startswith("Logistics Weekly")
    assert result.noise_ignored[0].triage_route == "ignore"
    # The freight email linked to its known load and produced a packet run.
    assert any(run.load_id == known for run in result.packet_runs)
    # The freight message was routed to processing (identifier link), not ignored.
    freight = next(m for m in result.new_messages if m.packet_load_id == known)
    assert freight.triage_route == "process"


def test_mailbox_intake_dedupes_by_message_id_and_hash(tmp_path):
    _, loads, email_corpus = _email_corpus(tmp_path, count=8)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    packet = next(p for p in email_corpus.packets if p.emails)
    source = Path(packet.emails[0].eml_path)
    shutil.copy2(source, inbox / source.name)

    state_path = tmp_path / "mailbox" / "mailbox_state.json"
    first = run_mailbox_intake(
        inbox_dir=inbox,
        preserve_dir=tmp_path / "mailbox",
        state_path=state_path,
        loads=loads,
    )
    second = run_mailbox_intake(
        inbox_dir=inbox,
        preserve_dir=tmp_path / "mailbox",
        state_path=state_path,
        loads=loads,
    )

    assert len(first.new_messages) == 1
    assert len(second.new_messages) == 0
    assert len(second.duplicates) == 1
    state = load_mailbox_state(state_path)
    assert len(state.messages) == 1


def test_mailbox_intake_trickle_email_updates_existing_packet(tmp_path):
    _, loads, email_corpus = _email_corpus(tmp_path, count=12)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    packet = next(p for p in email_corpus.packets if p.scenario == "trickle_pod_later" and len(p.emails) >= 2)
    state_path = tmp_path / "mailbox" / "mailbox_state.json"

    first_email = Path(packet.emails[0].eml_path)
    shutil.copy2(first_email, inbox / first_email.name)
    first = run_mailbox_intake(
        inbox_dir=inbox,
        preserve_dir=tmp_path / "mailbox",
        state_path=state_path,
        loads=loads,
    )
    first_run = next(p for p in first.packet_runs if p.load_id == packet.load_id)
    assert "pod" in first_run.packet.missing_required
    assert first_run.packet.needs_human is True

    second_email = Path(packet.emails[1].eml_path)
    shutil.copy2(second_email, inbox / second_email.name)
    second = run_mailbox_intake(
        inbox_dir=inbox,
        preserve_dir=tmp_path / "mailbox",
        state_path=state_path,
        loads=loads,
    )
    second_run = next(p for p in second.packet_runs if p.load_id == packet.load_id)
    assert "pod" not in second_run.packet.missing_required
    assert second_run.source_message_count == 2


def test_mailbox_intake_noise_attachment_does_not_spawn_noise_load_packet(tmp_path):
    _, loads, email_corpus = _email_corpus(tmp_path, count=12)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    packet = next(p for p in email_corpus.packets if p.has_noise)
    noise_load_ids = {
        attachment.links_to_load
        for email in packet.emails
        for attachment in email.attachments
        if attachment.is_noise and attachment.links_to_load
    }
    assert noise_load_ids and packet.load_id not in noise_load_ids
    for email in packet.emails:
        source = Path(email.eml_path)
        shutil.copy2(source, inbox / source.name)

    result = run_mailbox_intake(
        inbox_dir=inbox,
        preserve_dir=tmp_path / "mailbox",
        state_path=tmp_path / "mailbox" / "mailbox_state.json",
        loads=loads,
    )

    packet_run_ids = {run.load_id for run in result.packet_runs}
    assert packet.load_id in packet_run_ids
    assert packet_run_ids.isdisjoint(noise_load_ids)
    packet_run = next(run for run in result.packet_runs if run.load_id == packet.load_id)
    assert packet_run.packet.extraneous_attachments >= 1
    assert "extraneous_attachment" in packet_run.packet.flags


def test_mailbox_intake_cli_smoke(tmp_path):
    corpus, loads, email_corpus = _email_corpus(tmp_path, count=8)
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    packet = next(p for p in email_corpus.packets if p.emails)
    source = Path(packet.emails[0].eml_path)
    shutil.copy2(source, inbox / source.name)

    result = subprocess.run(
        [
            str(ROOT / ".venv" / "bin" / "python"),
            str(ROOT / "scripts" / "run_mailbox_intake.py"),
            "--corpus",
            str(corpus),
            "--inbox",
            str(inbox),
            "--preserve-dir",
            str(tmp_path / "mailbox"),
            "--state",
            str(tmp_path / "mailbox" / "mailbox_state.json"),
            "--out",
            str(tmp_path / "mailbox" / "report.json"),
            "--text",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Mailbox Intake" in result.stdout
    assert "New messages: 1" in result.stdout
    assert (tmp_path / "mailbox" / "report.json").exists()
