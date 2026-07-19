#!/usr/bin/env python3
"""Fail-fast environment check. Run BEFORE installing anything.

THE BOOTSTRAP CORRECTION (U-HANDOFF-1B, H-1). The repository requires the Python named in
pyproject.toml's `requires-python`, but nothing enforced it before dependency resolution - so on
an old interpreter, pip backtracked for twenty minutes before surfacing an incomprehensible
resolver error. This check reads the requirement from pyproject.toml (never a hardcoded version,
so a future floor change needs no edit here) and exits immediately with the exact detected and
required versions.

Usage:  python3 scripts/check_env.py     (any Python >= 3.6 can RUN the check itself)
Exit:   0 = compliant interpreter; 1 = non-compliant, with a message that says what to do.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PYPROJECT = Path(__file__).resolve().parents[1] / "pyproject.toml"


def required_floor(pyproject_text: str) -> tuple[int, int]:
    m = re.search(r'requires-python\s*=\s*"\s*>=\s*(\d+)\.(\d+)\s*"', pyproject_text)
    if not m:
        raise SystemExit("ERROR: could not parse requires-python from pyproject.toml")
    return int(m.group(1)), int(m.group(2))


def check(version: tuple[int, int] | None = None) -> int:
    floor = required_floor(PYPROJECT.read_text(encoding="utf-8"))
    detected = version if version is not None else sys.version_info[:2]
    if detected < floor:
        sys.stderr.write(
            f"ERROR: Python {detected[0]}.{detected[1]} detected, but this repository requires "
            f">= {floor[0]}.{floor[1]} (pyproject.toml requires-python).\n"
            f"Create the venv with a compliant interpreter, e.g.:\n"
            f"    python{floor[0]}.{floor[1]} -m venv .venv   (or any newer Python)\n"
            f"then re-run this check inside it BEFORE `pip install`.\n"
        )
        return 1
    print(f"OK: Python {detected[0]}.{detected[1]} satisfies >= {floor[0]}.{floor[1]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(check())
