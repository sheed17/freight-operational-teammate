#!/usr/bin/env python3
"""SUPERSEDED SHIM - refuses to run. Use scripts/finalize_status.py.

This script was the U-HANDOFF-1B finalizer: it VALIDATED a pre-existing SUITE-RESULT.json and
recorded status from it. The hostile handoff-readiness review (U-HANDOFF-1C, H-1) proved that
model unsound: a handwritten, structurally perfect artifact with correctly recomputed hashes
passed validation without a single test running. Validating evidence is not producing it.

The canonical finalizer is now scripts/finalize_status.py, which EXECUTES the complete suite,
the clean-clone gate and the acceptance gates itself and records only what it observed. This
shim exists so that any stale instruction, script or habit that invokes the old path gets an
explicit refusal instead of a second, weaker finalization route - a permanent dual finalization
system would be the same defect as a permanent dual effect-authority system.
"""

from __future__ import annotations

import sys

# Kept for import compatibility: the guard suite imports the metadata file set from the
# CANONICAL finalizer; anything still importing it from here gets the same single source.
from finalize_status import STATUS_METADATA_FILES  # noqa: F401


def main() -> int:
    sys.stderr.write(
        "REFUSED: scripts/update_current_status.py is superseded (U-HANDOFF-1C, H-1).\n"
        "It recorded status from a pre-existing artifact, which a hostile reviewer forged.\n"
        "Run the end-to-end finalizer instead - it executes everything it attests to:\n"
        "    .venv/bin/python scripts/finalize_status.py\n"
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
