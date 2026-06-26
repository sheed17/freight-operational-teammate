"""Tests for real inbox freight candidate discovery."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.inbox_discovery import score_message  # noqa: E402


def _message(subject: str, *, filename: str | None = None, sender: str = "carrier@example.test") -> bytes:
    lines = [
        "Message-ID: <m@example.test>",
        f"From: {sender}",
        "To: billing@neyma.test",
        f"Subject: {subject}",
        "MIME-Version: 1.0",
    ]
    if filename is None:
        lines.extend(["Content-Type: text/plain", "", "hello"])
    else:
        lines.extend(
            [
                "Content-Type: multipart/mixed; boundary=x",
                "",
                "--x",
                "Content-Type: text/plain",
                "",
                "Attached.",
                "--x",
                "Content-Type: application/pdf",
                f"Content-Disposition: attachment; filename=\"{filename}\"",
                "Content-Transfer-Encoding: base64",
                "",
                "JVBERi0xLjQKJUVPRgo=",
                "--x--",
                "",
            ]
        )
    return "\n".join(lines).encode()


def _message_with_body(subject: str, body: str, *, filename: str = "scan.pdf") -> bytes:
    return "\n".join(
        [
            "Message-ID: <body-only@example.test>",
            "From: carrier@example.test",
            "To: billing@neyma.test",
            f"Subject: {subject}",
            "MIME-Version: 1.0",
            "Content-Type: multipart/mixed; boundary=x",
            "",
            "--x",
            "Content-Type: text/plain",
            "",
            body,
            "--x",
            "Content-Type: application/pdf",
            f"Content-Disposition: attachment; filename=\"{filename}\"",
            "Content-Transfer-Encoding: base64",
            "",
            "JVBERi0xLjQKJUVPRgo=",
            "--x--",
            "",
        ]
    ).encode()


def test_score_message_accepts_freight_pdf_candidate():
    candidate = score_message(_message("Invoice INV-2026003 / Load LD-560003", filename="carrier_invoice.pdf"))

    assert candidate.score >= 0.45
    assert any("PDF" in reason for reason in candidate.reasons)
    assert any("identifier" in reason for reason in candidate.reasons)


def test_score_message_rejects_obvious_non_freight_noise():
    candidate = score_message(_message("Registration Confirmation", filename="waiver.pdf"))

    assert candidate.score < 0.45
    assert any("negative term" in reason for reason in candidate.reasons)


def test_score_message_accepts_body_only_load_identifier_with_generic_pdf():
    candidate = score_message(
        _message_with_body(
            "docs attached",
            "Please process attached POD and invoice for Load LD-560003 / Invoice INV-2026003.",
        )
    )

    assert candidate.score >= 0.45
    assert any("identifier" in reason for reason in candidate.reasons)
