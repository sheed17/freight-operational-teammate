"""Stage 1 extraction: PDF -> rendered images -> Instructor/Anthropic vision -> validated Pydantic.

This is the only place the LLM is touched. The Pydantic schema is built dynamically
from the YAML config so adding a field is a config edit, not a code change. Every
extraction returns an ExtractionResult — FAILED on any error, never an exception that
crashes the eval loop.

Model note: real eval should use the same production-candidate model as the runtime extractor.
Override with EVAL_MODEL for bakeoffs; otherwise this follows ANTHROPIC_MODEL and then the
runtime default.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import fitz  # PyMuPDF
import yaml
from pydantic import BaseModel, Field, create_model

DEFAULT_MODEL = os.getenv("EVAL_MODEL") or os.getenv("ANTHROPIC_MODEL") or "claude-opus-4-8"
RENDER_DPI = int(os.getenv("EVAL_DPI", "200"))

SYSTEM_PROMPT = (
    "You are a meticulous freight back-office document extraction engine. You read "
    "rendered carrier invoices and return ONLY the requested structured fields with an "
    "honest, calibrated confidence per field. You never invent values: if a field is not "
    "legibly present, set its value to null and confidence below 0.5."
)


# ----------------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------------

@dataclass
class FieldSpec:
    name: str
    type: str
    required: bool
    description: str


@dataclass
class DocConfig:
    doc_type: str
    description: str
    fields: list[FieldSpec]
    extraction_prompt: str
    confidence_threshold: float
    scalar_field_names: list[str]
    list_field_names: list[str]


def load_config(path: str | Path) -> DocConfig:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    fields = [
        FieldSpec(
            name=f["name"],
            type=f["type"],
            required=f.get("required", False),
            description=(f.get("description") or "").strip(),
        )
        for f in data["fields"]
    ]
    return DocConfig(
        doc_type=data["doc_type"],
        description=data.get("description", ""),
        fields=fields,
        extraction_prompt=data["extraction_prompt"].strip(),
        confidence_threshold=float(data.get("confidence_threshold", 0.85)),
        scalar_field_names=[f.name for f in fields if f.type != "list"],
        list_field_names=[f.name for f in fields if f.type == "list"],
    )


# ----------------------------------------------------------------------------
# Dynamic Pydantic schema
# ----------------------------------------------------------------------------

# Map config field types to the Python type used for the extracted value.
_VALUE_TYPES: dict[str, Any] = {
    "string": str,
    "decimal": float,   # JSON-friendly; ground truth is float and we compare with tolerance
    "integer": int,
    "date": str,        # ISO YYYY-MM-DD string; normalized at scoring time
}


class AccessorialItem(BaseModel):
    """One accessorial line item (detention, lumper, ...) with its own confidence."""

    name: str = Field(description="Accessorial name, lowercased, e.g. 'detention', 'lumper'.")
    amount: float = Field(description="Dollar amount of this charge.")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


def _scalar_field_model(field_name: str, value_type: Any) -> type[BaseModel]:
    """An ExtractedField: {value, confidence, extraction_note} with a concretely typed value."""
    return create_model(
        f"Field_{field_name}",
        value=(Optional[value_type], Field(default=None, description="Extracted value, or null if not found.")),
        confidence=(float, Field(default=0.0, ge=0.0, le=1.0, description="Confidence 0.0-1.0.")),
        extraction_note=(
            Optional[str],
            Field(default=None, description="Optional note on where/how the value was found or why uncertain."),
        ),
    )


_MODEL_CACHE: dict[str, type[BaseModel]] = {}


def build_extraction_model(config: DocConfig) -> type[BaseModel]:
    """Build the document extraction model dynamically from the config fields."""
    key = config.doc_type + "|" + ",".join(f.name + ":" + f.type for f in config.fields)
    if key in _MODEL_CACHE:
        return _MODEL_CACHE[key]

    definitions: dict[str, tuple] = {}
    for spec in config.fields:
        if spec.type == "list":
            definitions[spec.name] = (list[AccessorialItem], Field(default_factory=list))
        else:
            value_type = _VALUE_TYPES.get(spec.type)
            if value_type is None:
                raise ValueError(f"unsupported field type: {spec.type}")
            sub = _scalar_field_model(spec.name, value_type)
            definitions[spec.name] = (sub, Field(default_factory=sub))

    model = create_model(
        "".join(p.capitalize() for p in config.doc_type.split("_")) + "Extraction",
        __doc__=config.description,
        **definitions,
    )
    _MODEL_CACHE[key] = model
    return model


# ----------------------------------------------------------------------------
# Rendering
# ----------------------------------------------------------------------------

def render_pdf_to_pngs(pdf_path: str | Path, dpi: int = RENDER_DPI) -> list[bytes]:
    """Render every page of a PDF to PNG bytes (all pages — invoices may have attachments)."""
    pages: list[bytes] = []
    with fitz.open(pdf_path) as doc:
        for page in doc:
            pages.append(page.get_pixmap(dpi=dpi).tobytes("png"))
    return pages


# ----------------------------------------------------------------------------
# Result
# ----------------------------------------------------------------------------

@dataclass
class ExtractionResult:
    filename: str
    status: str  # "OK" | "FAILED"
    data: dict | None = None       # plain dict form of the validated model
    error: str | None = None
    pages: int = 0
    model: str = DEFAULT_MODEL

    @property
    def ok(self) -> bool:
        return self.status == "OK"


def _build_prompt(config: DocConfig) -> str:
    lines = "\n".join(
        f"  - {f.name} ({f.type}{', required' if f.required else ''}): {f.description}"
        for f in config.fields
    )
    return f"{config.extraction_prompt}\n\nFields to extract:\n{lines}"


# ----------------------------------------------------------------------------
# Real extraction (Anthropic via Instructor)
# ----------------------------------------------------------------------------

def extract_document(
    pdf_path: str | Path,
    config: DocConfig,
    model: str = DEFAULT_MODEL,
) -> ExtractionResult:
    """Render a PDF and run vision extraction. Returns a FAILED result on any error."""
    filename = Path(pdf_path).name
    try:
        pages = render_pdf_to_pngs(pdf_path)
    except Exception as exc:  # noqa: BLE001
        return ExtractionResult(filename, "FAILED", error=f"render error: {exc}", model=model)

    try:
        import instructor
        from anthropic import Anthropic

        client = instructor.from_anthropic(Anthropic())
        response_model = build_extraction_model(config)

        content: list[dict] = [{"type": "text", "text": _build_prompt(config)}]
        for png in pages:
            content.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": base64.standard_b64encode(png).decode("ascii"),
                    },
                }
            )

        obj = client.chat.completions.create(
            model=model,
            max_tokens=2048,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
            response_model=response_model,
        )
    except Exception as exc:  # noqa: BLE001 — surface as FAILED, never crash the loop
        return ExtractionResult(
            filename, "FAILED", error=f"{type(exc).__name__}: {exc}", pages=len(pages), model=model
        )

    return ExtractionResult(filename, "OK", data=obj.model_dump(), pages=len(pages), model=model)


# ----------------------------------------------------------------------------
# Mock extraction (for testing the harness itself without an API key)
# ----------------------------------------------------------------------------

def coerce_mock(filename: str, raw: dict, config: DocConfig) -> ExtractionResult:
    """Validate a hand-written extraction dict against the model (offline harness self-test)."""
    try:
        model = build_extraction_model(config)
        obj = model.model_validate(raw)
    except Exception as exc:  # noqa: BLE001
        return ExtractionResult(filename, "FAILED", error=f"mock validation: {exc}", model="mock")
    return ExtractionResult(filename, "OK", data=obj.model_dump(), pages=1, model="mock")
