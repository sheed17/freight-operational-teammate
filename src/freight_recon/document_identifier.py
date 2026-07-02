"""Vision identifier extraction for routing freight documents.

This is deliberately narrower than invoice extraction: it only finds identifiers
needed to link a document to the right load/thread. It must not make money
decisions.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, Field

from .render import PageImage, render_pdf


IDENTIFIER_SYSTEM_PROMPT = (
    "You are a freight document routing assistant. Extract only routing identifiers "
    "from scanned freight documents. Do not infer money decisions. If a value is not "
    "visible, return null and low confidence."
)


class DocumentIdentifierExtraction(BaseModel):
    doc_type: str | None = Field(
        default=None,
        description="One of carrier_invoice, rate_confirmation, pod, bol, lumper_receipt, fuel_receipt, manifest, or unknown.",
    )
    load_id: str | None = None
    invoice_number: str | None = None
    pro_number: str | None = None
    bol_number: str | None = None
    carrier_name: str | None = None
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


class DocumentIdentifierResult(BaseModel):
    provider: str
    model: str
    extraction: DocumentIdentifierExtraction | None
    raw_pages: int
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and self.extraction is not None

    def as_link_text(self, *, min_confidence: float = 0.65) -> str:
        if not self.extraction or self.extraction.confidence < min_confidence:
            return ""
        parts = [
            self.extraction.doc_type,
            self.extraction.load_id,
            self.extraction.invoice_number,
            self.extraction.pro_number,
            self.extraction.bol_number,
            self.extraction.carrier_name,
        ]
        return " ".join(str(part) for part in parts if part)


def extract_pdf_identifiers(
    pdf_path: str | Path,
    *,
    provider: str | None = None,
    model: str | None = None,
    dpi: int = 200,
    max_pages: int = 2,
) -> DocumentIdentifierResult:
    try:
        pages = render_pdf(pdf_path, dpi=dpi, max_pages=max_pages)
    except Exception as exc:  # noqa: BLE001 - bad scans/PDFs must fail closed into unlinked review
        return DocumentIdentifierResult(
            provider=provider or os.getenv("EXTRACTION_PROVIDER") or "openai",
            model=model or os.getenv("OPENAI_IDENTIFIER_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5.4",
            extraction=None,
            raw_pages=0,
            error=f"{type(exc).__name__}: {exc}",
        )
    return extract_identifiers_from_pages(pages, provider=provider, model=model)


def extract_identifiers_from_pages(
    pages: list[PageImage],
    *,
    provider: str | None = None,
    model: str | None = None,
) -> DocumentIdentifierResult:
    resolved_provider = (provider or os.getenv("EXTRACTION_PROVIDER") or "openai").lower()
    if resolved_provider != "openai":
        return DocumentIdentifierResult(
            provider=resolved_provider,
            model=model or "",
            extraction=None,
            raw_pages=len(pages),
            error="document identifier vision currently supports provider=openai",
        )
    model_name = model or os.getenv("OPENAI_IDENTIFIER_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-5.4"
    try:
        obj = _extract_openai(model_name, pages)
    except Exception as exc:  # noqa: BLE001 - caller routes failures to safe unlinked review
        return DocumentIdentifierResult(
            provider=resolved_provider,
            model=model_name,
            extraction=None,
            raw_pages=len(pages),
            error=f"{type(exc).__name__}: {exc}",
        )
    return DocumentIdentifierResult(
        provider=resolved_provider,
        model=model_name,
        extraction=obj,
        raw_pages=len(pages),
    )


def _extract_openai(model_name: str, pages: list[PageImage]) -> DocumentIdentifierExtraction:
    import instructor
    from openai import OpenAI

    client = instructor.from_openai(OpenAI())
    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "Identify the freight document type and any visible load ID, invoice number, "
                "PRO number, BOL number, and carrier name. Return null for missing values. "
                "Only return identifiers visible on the document."
            ),
        }
    ]
    for page in pages:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{page.base64}"},
            }
        )
    # gpt-5 / o-series need `max_completion_tokens`; older models use `max_tokens`.
    token_kw = (
        {"max_completion_tokens": 1024}
        if any(model_name.startswith(p) for p in ("gpt-5", "o1", "o3", "o4"))
        else {"max_tokens": 1024}
    )
    return client.chat.completions.create(
        model=model_name,
        **token_kw,
        messages=[
            {"role": "system", "content": IDENTIFIER_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_model=DocumentIdentifierExtraction,
    )
