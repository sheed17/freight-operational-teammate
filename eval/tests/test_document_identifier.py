"""Tests for vision document identifier fail-closed behavior."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from freight_recon.document_identifier import extract_pdf_identifiers  # noqa: E402


def test_extract_pdf_identifiers_bad_pdf_returns_error_not_exception(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"not a pdf")

    result = extract_pdf_identifiers(bad, provider="openai", model="gpt-4o")

    assert result.ok is False
    assert result.extraction is None
    assert result.error
