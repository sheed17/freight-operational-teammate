"""Smoke tests for live-drive factory signatures."""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))


def test_run_operate_request_build_agent_accepts_prepare_only():
    script = Path(__file__).resolve().parents[2] / "scripts" / "run_operate_request.py"
    tree = ast.parse(script.read_text(encoding="utf-8"))
    factories = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "build_agent"
    ]

    assert factories
    assert any(arg.arg == "prepare_only" for factory in factories for arg in factory.args.kwonlyargs)

