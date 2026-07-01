"""Vision extraction: rendered pages -> structured, confidence-scored output.

This is one of the two points where intelligence is concentrated (the other is
the bounded TMS agent). Everything here funnels through Instructor + Pydantic so
the LLM's output is *always* a validated object — never free text we have to
parse. The provider (Anthropic vs. OpenAI) is config/env-driven so the empirical
Claude-vs-GPT bake-off the spec calls for is a flag flip, not a rewrite.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel

from .config import DocTypeConfig
from .models import build_extraction_model
from .render import PageImage, render_pdf

SYSTEM_PROMPT = (
    "You are a meticulous freight back-office document extraction engine. You read "
    "scanned/rendered carrier documents and return STRICTLY the requested structured "
    "fields. You never guess: if a value is not legible or not present, you set it to "
    "null with confidence 0. Money values are returned as plain numbers (no $ or commas). "
    "Confidence is calibrated to how clearly the value appears on the page."
)


@dataclass
class ExtractionResult:
    """Outcome of an extraction attempt."""

    doc_type: str
    provider: str
    model: str
    extraction: BaseModel | None
    raw_pages: int
    error: str | None = None
    low_confidence_fields: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.error is None and self.extraction is not None


# ----------------------------------------------------------------------------
# Provider plumbing — kept behind a tiny interface so providers are swappable.
# ----------------------------------------------------------------------------

def _resolve_provider(provider: str | None) -> str:
    provider = (provider or os.getenv("EXTRACTION_PROVIDER") or "anthropic").lower()
    if provider not in ("anthropic", "openai"):
        raise ValueError(f"unsupported EXTRACTION_PROVIDER: {provider!r}")
    return provider


def _resolve_model(provider: str, model: str | None) -> str:
    if model:
        return model
    if provider == "anthropic":
        return os.getenv("ANTHROPIC_MODEL", "claude-opus-4-8")
    return os.getenv("OPENAI_MODEL", "gpt-4o")


def _build_user_prompt(config: DocTypeConfig) -> str:
    field_lines = "\n".join(
        f"  - {f.name} ({f.type.value}{', required' if f.required else ''})"
        f"{': ' + f.description if f.description else ''}"
        for f in config.fields
    )
    return (
        f"{config.extraction_prompt.strip()}\n\n"
        f"Fields to extract:\n{field_lines}\n\n"
        "Return every field. For any field not present on the document, use a null value "
        "and confidence 0."
    )


def _extract_anthropic(model_name: str, response_model, prompt: str, pages: list[PageImage]):
    import instructor
    from anthropic import Anthropic

    client = instructor.from_anthropic(Anthropic())
    content: list[dict] = [{"type": "text", "text": prompt}]
    for page in pages:
        content.append(
            {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": page.base64},
            }
        )
    return client.chat.completions.create(
        model=model_name,
        max_tokens=2048,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": content}],
        response_model=response_model,
    )


def _extract_openai(model_name: str, response_model, prompt: str, pages: list[PageImage]):
    import instructor
    from openai import OpenAI

    client = instructor.from_openai(OpenAI())
    content: list[dict] = [{"type": "text", "text": prompt}]
    for page in pages:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{page.base64}"},
            }
        )
    # gpt-5 / o-series reject `max_tokens` (they require `max_completion_tokens`); older models want
    # `max_tokens`. Pick the right one so a top-quality model can be used for extraction.
    token_kw = (
        {"max_completion_tokens": 2048}
        if any(model_name.startswith(p) for p in ("gpt-5", "o1", "o3", "o4"))
        else {"max_tokens": 2048}
    )
    return client.chat.completions.create(
        model=model_name,
        **token_kw,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        response_model=response_model,
    )


# ----------------------------------------------------------------------------
# Public API
# ----------------------------------------------------------------------------

def extract_from_pages(
    pages: list[PageImage],
    config: DocTypeConfig,
    provider: str | None = None,
    model: str | None = None,
) -> ExtractionResult:
    """Run vision extraction over already-rendered pages."""
    provider = _resolve_provider(provider)
    model_name = _resolve_model(provider, model)
    response_model = build_extraction_model(config)
    prompt = _build_user_prompt(config)

    try:
        if provider == "anthropic":
            obj = _extract_anthropic(model_name, response_model, prompt, pages)
        else:
            obj = _extract_openai(model_name, response_model, prompt, pages)
    except Exception as exc:  # noqa: BLE001 — surface any provider/parse failure as FAILED
        return ExtractionResult(
            doc_type=config.doc_type,
            provider=provider,
            model=model_name,
            extraction=None,
            raw_pages=len(pages),
            error=f"{type(exc).__name__}: {exc}",
        )

    return ExtractionResult(
        doc_type=config.doc_type,
        provider=provider,
        model=model_name,
        extraction=obj,
        raw_pages=len(pages),
        low_confidence_fields=_low_confidence_fields(obj, config.confidence_threshold),
    )


def extract_from_pdf(
    pdf_path: str | Path,
    config: DocTypeConfig,
    provider: str | None = None,
    model: str | None = None,
    dpi: int = 200,
    max_pages: int | None = 3,
) -> ExtractionResult:
    """Render a PDF and run vision extraction in one call."""
    pages = render_pdf(pdf_path, dpi=dpi, max_pages=max_pages)
    return extract_from_pages(pages, config, provider=provider, model=model)


def _low_confidence_fields(obj: BaseModel, threshold: float) -> list[str]:
    """Return names of scalar fields whose confidence is below the threshold."""
    flagged: list[str] = []
    for name, value in obj:
        conf = getattr(value, "confidence", None)
        if isinstance(conf, (int, float)) and conf < threshold:
            flagged.append(name)
    return flagged
