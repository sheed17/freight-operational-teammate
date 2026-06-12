"""Confidence-scored extraction models.

Every extracted field carries a ``{value, confidence}`` pair so downstream
routing (auto-approve vs. NEEDS_REVIEW) can reason about per-field certainty,
not just a single document-level score. The concrete extraction model for a
document type is built *from config* via :func:`build_extraction_model` so a new
field is a YAML edit, not a code change.
"""

from __future__ import annotations

import datetime as _dt
from decimal import Decimal
from typing import Generic, Optional, TypeVar

from pydantic import BaseModel, Field, create_model

from .config import DocTypeConfig, FieldType

T = TypeVar("T")


class Confident(BaseModel, Generic[T]):
    """An extracted value paired with the model's confidence in it."""

    value: Optional[T] = Field(
        default=None, description="The extracted value, or null if not present on the document."
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Calibrated confidence in this value, 0-1."
    )


class AccessorialCharge(BaseModel):
    """A single accessorial line item on a freight invoice (detention, lumper, ...)."""

    name: str = Field(description="Name of the accessorial charge, e.g. 'detention', 'lumper'.")
    amount: Decimal = Field(description="Dollar amount of this charge.")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


# Maps a config FieldType to the Python type used inside Confident[...].
_SCALAR_TYPES: dict[FieldType, type] = {
    FieldType.STRING: str,
    FieldType.DECIMAL: Decimal,
    FieldType.INTEGER: int,
    FieldType.DATE: _dt.date,
}


def _field_annotation(field_type: FieldType):
    """Return the (type, default) tuple for a config field used by create_model."""
    if field_type is FieldType.LIST:
        # Lists are charge line items; each line carries its own confidence.
        return (list[AccessorialCharge], Field(default_factory=list))
    scalar = _SCALAR_TYPES.get(field_type)
    if scalar is None:
        raise ValueError(f"unsupported field type: {field_type}")
    return (Confident[scalar], Field(default_factory=Confident))


_MODEL_CACHE: dict[str, type[BaseModel]] = {}


def build_extraction_model(config: DocTypeConfig) -> type[BaseModel]:
    """Dynamically build a Pydantic extraction model from a doc-type config.

    Each scalar field becomes a ``Confident[...]`` sub-object; list fields become
    a list of :class:`AccessorialCharge`. The resulting model is what Instructor
    coerces the vision model's output into.
    """
    cache_key = f"{config.doc_type}:{','.join(f.name for f in config.fields)}"
    if cache_key in _MODEL_CACHE:
        return _MODEL_CACHE[cache_key]

    field_defs: dict[str, tuple] = {}
    for spec in config.fields:
        annotation, default = _field_annotation(spec.type)
        field_defs[spec.name] = (annotation, default)

    model_name = "".join(part.capitalize() for part in config.doc_type.split("_")) + "Extraction"
    model = create_model(model_name, __doc__=config.description, **field_defs)
    _MODEL_CACHE[cache_key] = model
    return model
