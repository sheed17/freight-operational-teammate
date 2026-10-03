"""Record / replay of model readings, so a development eval is paid for once.

A reading is keyed by a SHA-256 over the provider, the model, the task, the output schema version,
the prompt version, the reasoning effort and the normalized rendered input. Any of those changing is
a different question, and a different key: a recording is never replayed against a prompt it was not
an answer to.

What is stored is the VALIDATED structured reply and the token counts the provider reported for it.
The rendered input is not stored — only its digest.

### A RECORDING IS A DEVELOPMENT OPTIMIZATION, NOT AUTHORITY. A replayed reading is exactly as
authoritative as a live one, which is not at all: it is a model interpretation, it re-enters the same
deterministic checks, and it carries the same provenance. Nothing consequential may read this store.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .contracts import SCHEMA_VERSION, Task, Usage

RECORDING_FORMAT = "neyma-inference-recording-1"


def normalize_input(text: str) -> str:
    """Line endings unified and trailing whitespace dropped: the differences that must not make the
    same content a different question."""
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    return "\n".join(line.rstrip() for line in lines).strip()


def content_digest(text: str) -> str:
    return hashlib.sha256(normalize_input(text).encode("utf-8")).hexdigest()


def request_key(*, provider: str, model: str, task: Task, prompt_version: str,
                reasoning_effort: str | None, rendered_input: str,
                schema_version: str = SCHEMA_VERSION) -> str:
    material = json.dumps({
        "provider": provider, "model": model, "task": task.value,
        "schema_version": schema_version, "prompt_version": prompt_version,
        "reasoning_effort": reasoning_effort or "", "input": normalize_input(rendered_input),
    }, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


class RecordingStore:
    """One JSON file of recorded readings. Loaded whole, written whole and atomically."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._entries: dict[str, dict[str, Any]] = {}
        if self.path.exists():
            document = json.loads(self.path.read_text(encoding="utf-8"))
            if document.get("format") != RECORDING_FORMAT:
                raise ValueError(
                    f"{self.path} is not a {RECORDING_FORMAT} file (format="
                    f"{document.get('format')!r}). Refusing to replay it.")
            self._entries = dict(document.get("entries") or {})

    def __len__(self) -> int:
        return len(self._entries)

    def get(self, key: str) -> dict[str, Any] | None:
        return self._entries.get(key)

    def put(self, key: str, *, task: Task, provider: str, model: str, payload: dict[str, Any],
            usage: Usage, recorded_at: str, input_digest: str) -> None:
        self._entries[key] = {
            "task": task.value, "provider": provider, "model": model,
            "schema_version": SCHEMA_VERSION, "payload": payload, "usage": asdict(usage),
            "recorded_at": recorded_at, "input_digest": input_digest,
        }
        self._flush()

    def _flush(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        scratch = self.path.with_suffix(self.path.suffix + ".tmp")
        document = {"format": RECORDING_FORMAT,
                    "note": ("Recorded model readings of a SYNTHETIC development corpus. A "
                             "development/eval optimization: never business authority."),
                    "entries": {k: self._entries[k] for k in sorted(self._entries)}}
        scratch.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n",
                           encoding="utf-8")
        os.replace(scratch, self.path)
