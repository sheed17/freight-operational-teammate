"""Where the frozen corpus and the live repository actually are.

One place, so a moved file fails loudly here rather than turning every probe into a silent no-op.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "freight_recon"
SCRIPTS = ROOT / "scripts"
TESTS = ROOT / "eval" / "tests"
IMPLEMENTATION = ROOT / "docs" / "implementation"
ACCEPTANCE = ROOT / "docs" / "specifications" / "acceptance"
SPECIFICATIONS = ROOT / "docs" / "specifications"
ARCHITECTURE = ROOT / "docs" / "architecture"
MANIFEST = IMPLEMENTATION / "phase-0-baseline-manifest.yaml"


def require(path: Path) -> Path:
    """A source that has moved must break the probe, not empty it."""
    if not path.exists():
        raise FileNotFoundError(
            f"Phase-0 probe source is missing: {path}\n"
            f"A probe whose source has moved would evaluate zero records and report green. "
            f"Fix the path or adjudicate the removal in the baseline manifest."
        )
    return path


def python_files(*roots: Path) -> list[Path]:
    out: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        out += [
            p for p in sorted(root.rglob("*.py"))
            if "__pycache__" not in p.parts and ".venv" not in p.parts
        ]
    return out


def rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)
