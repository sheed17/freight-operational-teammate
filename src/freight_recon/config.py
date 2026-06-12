"""Config system: YAML -> validated Pydantic config.

A document-type config (fields / prompt / reconciliation rules) is reusable
across clients. A client overlay (entry_mapping, TMS access method, thresholds)
is merged on top. New doc type or new client = new config, not new code.

The on-disk YAML mirrors the format in the build spec exactly, including the
heterogeneous ``reconciliation_rules`` list (a mix of directive dicts and
comparison-expression strings). The loader normalizes that messy list into the
typed :class:`ReconciliationConfig` so the rest of the code gets clean access.
"""

from __future__ import annotations

from decimal import Decimal
from enum import Enum
from pathlib import Path

import yaml
from pydantic import BaseModel, Field, field_validator

# Repository-relative config locations.
CONFIG_ROOT = Path(__file__).resolve().parents[2] / "configs"
DOC_TYPES_DIR = CONFIG_ROOT / "doc_types"
CLIENTS_DIR = CONFIG_ROOT / "clients"


class FieldType(str, Enum):
    """Field value types supported by the dynamic extraction model builder."""

    STRING = "string"
    DECIMAL = "decimal"
    INTEGER = "integer"
    DATE = "date"
    LIST = "list"  # currently mapped to a list of charge line items


class FieldSpec(BaseModel):
    """One field the vision model must extract, with a per-field confidence."""

    name: str
    type: FieldType
    required: bool = False
    description: str | None = None


class ReconciliationConfig(BaseModel):
    """Deterministic invoice<->rate-con comparison rules (Phase 3 consumes this)."""

    match_key: str = "load_or_pro"
    comparisons: list[str] = Field(default_factory=list)
    flag_variance_threshold: Decimal = Decimal("0.00")


class DocTypeConfig(BaseModel):
    """A complete, validated document-type config."""

    doc_type: str
    description: str = ""
    fields: list[FieldSpec]
    extraction_prompt: str
    reconciliation: ReconciliationConfig = Field(default_factory=ReconciliationConfig)
    confidence_threshold: float = 0.85
    entry_mapping: dict[str, str] = Field(default_factory=dict)

    @field_validator("fields")
    @classmethod
    def _non_empty_fields(cls, v: list[FieldSpec]) -> list[FieldSpec]:
        if not v:
            raise ValueError("doc type config must declare at least one field")
        return v

    def field(self, name: str) -> FieldSpec | None:
        return next((f for f in self.fields if f.name == name), None)


def _normalize_reconciliation_rules(raw: list | None) -> dict:
    """Turn the spec's heterogeneous ``reconciliation_rules`` list into a dict.

    The list mixes single-key directive dicts (``{match_key: ...}``,
    ``{flag_variance_threshold: ...}``) with plain comparison-expression strings.
    We pull the directives out and collect the strings as ``comparisons``.
    """
    out: dict = {"comparisons": []}
    for item in raw or []:
        if isinstance(item, str):
            out["comparisons"].append(item)
        elif isinstance(item, dict):
            for key, value in item.items():
                out[key] = value
        else:
            raise ValueError(f"unsupported reconciliation rule entry: {item!r}")
    return out


def _read_yaml(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"config file not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"config file {path} must contain a YAML mapping")
    return data


def _build_doc_type_config(data: dict) -> DocTypeConfig:
    data = dict(data)  # shallow copy; we mutate the reconciliation key
    if "reconciliation_rules" in data:
        data["reconciliation"] = _normalize_reconciliation_rules(
            data.pop("reconciliation_rules")
        )
    return DocTypeConfig.model_validate(data)


def load_doc_type_config(doc_type: str, doc_types_dir: Path | None = None) -> DocTypeConfig:
    """Load and validate a document-type config by name (e.g. ``carrier_invoice``)."""
    base = doc_types_dir or DOC_TYPES_DIR
    return _build_doc_type_config(_read_yaml(base / f"{doc_type}.yaml"))


def _deep_merge(base: dict, overlay: dict) -> dict:
    """Recursively merge ``overlay`` onto ``base`` (overlay wins on conflicts)."""
    merged = dict(base)
    for key, value in overlay.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_config(
    doc_type: str,
    client: str | None = None,
    doc_types_dir: Path | None = None,
    clients_dir: Path | None = None,
) -> DocTypeConfig:
    """Load a doc-type config, optionally with a per-client overlay merged on top.

    The client overlay is a YAML mapping of doc_type -> partial config (e.g.
    ``entry_mapping``, ``confidence_threshold``). Absent overlay == doc-type only.
    """
    raw = _read_yaml((doc_types_dir or DOC_TYPES_DIR) / f"{doc_type}.yaml")

    if client:
        cbase = clients_dir or CLIENTS_DIR
        client_data = _read_yaml(cbase / f"{client}.yaml")
        overlay = (client_data.get("doc_types") or {}).get(doc_type, {})
        raw = _deep_merge(raw, overlay)

    return _build_doc_type_config(raw)
