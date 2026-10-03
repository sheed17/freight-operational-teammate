"""Provider and model selection for the inference gateway, and the versioned price table.

    NEYMA_INFERENCE_PROVIDER          default: openai   (the only provider implemented)
    NEYMA_INFERENCE_MODEL             default: gpt-6-luna
    NEYMA_INFERENCE_REASONING_EFFORT  default: low

### THIS BOUNDARY HAS ITS OWN MODEL SETTING, ON PURPOSE. `OPENAI_MODEL` selects the model for the
legacy vision-extraction surface. The gateway does not read it: a setting made for scanned-document
extraction must not silently choose — and price — the model that reads every message.

### A PRICE IS METADATA, NOT LOGIC. Nothing in the application branches on a dollar figure. The price
table is a dated, versioned config file read only to print an ESTIMATE next to the token counts; an
unlisted model has no estimate rather than a guessed one.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import Usage

DEFAULT_PROVIDER = "openai"
DEFAULT_MODEL = "gpt-6-luna"
DEFAULT_REASONING_EFFORT = "low"
SUPPORTED_PROVIDERS: tuple[str, ...] = ("openai",)

PRICING_PATH = Path(__file__).resolve().parents[3] / "configs" / "inference_pricing.json"


class UnsupportedProvider(ValueError):
    """A provider nobody has implemented behind the gateway was configured."""


@dataclass(frozen=True)
class InferenceSettings:
    provider: str
    model: str
    reasoning_effort: str | None
    model_source: str                 # which variable (or default) the model name came from

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> "InferenceSettings":
        env = dict(os.environ) if env is None else env
        provider = (env.get("NEYMA_INFERENCE_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise UnsupportedProvider(
                f"NEYMA_INFERENCE_PROVIDER={provider!r}: only {list(SUPPORTED_PROVIDERS)} is "
                f"implemented behind the inference gateway.")
        if (env.get("NEYMA_INFERENCE_MODEL") or "").strip():
            model, source = env["NEYMA_INFERENCE_MODEL"].strip(), "NEYMA_INFERENCE_MODEL"
        else:
            model, source = DEFAULT_MODEL, "default"
        effort = (env.get("NEYMA_INFERENCE_REASONING_EFFORT") or DEFAULT_REASONING_EFFORT).strip()
        return cls(provider=provider, model=model,
                   reasoning_effort=None if effort.lower() == "default" else effort,
                   model_source=source)


@dataclass(frozen=True)
class PriceTable:
    version: str
    as_of: str
    source: str
    models: dict[str, dict[str, float]]

    def estimate_usd(self, model: str, usage: Usage) -> float | None:
        """An estimate from token counts, or None for a model the table does not list. Cached input
        tokens are billed at the cached rate and are a subset of the input tokens."""
        price = self.models.get(model)
        if price is None:
            return None
        fresh = max(usage.input_tokens - usage.cached_input_tokens, 0)
        return round((fresh * price["input_per_mtok_usd"]
                      + usage.cached_input_tokens * price["cached_input_per_mtok_usd"]
                      + usage.output_tokens * price["output_per_mtok_usd"]) / 1_000_000, 6)


def load_price_table(path: Path = PRICING_PATH) -> PriceTable:
    document: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    return PriceTable(version=document["version"], as_of=document["as_of"],
                      source=document["source"], models=dict(document["models"]))
