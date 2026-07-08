"""CLI coverage for scripts/run_diagnostics.py."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_run_diagnostics_cli_renders_failure(tmp_path):
    trace = tmp_path / "trace.json"
    trace.write_text(
        json.dumps({
            "status": "FAILED",
            "note": "did not finish within 20 steps",
            "steps": [{"action": "CLICK", "target": "LD-1", "ok": False}] * 2,
        }),
        encoding="utf-8",
    )
    res = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_diagnostics.py"), str(trace)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert res.returncode == 1
    assert "Why:" in res.stdout
    assert "LD-1" in res.stdout


def test_run_diagnostics_cli_missing_file_exits_nonzero(tmp_path):
    res = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_diagnostics.py"), str(tmp_path / "missing.json")],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert res.returncode == 2
    assert "not found" in res.stderr
