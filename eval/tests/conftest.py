"""Make the standalone eval modules importable from the tests, and share fixtures."""

import json
import sys
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EVAL_DIR))

from extraction import coerce_mock, load_config  # noqa: E402

CONFIG_PATH = EVAL_DIR / "configs" / "carrier_invoice.yaml"
GOLDEN = EVAL_DIR / "golden_set"


@pytest.fixture(scope="session")
def config():
    return load_config(CONFIG_PATH)


@pytest.fixture(scope="session")
def ground_truth():
    return json.loads((GOLDEN / "ground_truth.json").read_text())


@pytest.fixture(scope="session")
def mock_v1():
    return json.loads((GOLDEN / "mock_v1.json").read_text())


@pytest.fixture(scope="session")
def mock_v2():
    return json.loads((GOLDEN / "mock_v2.json").read_text())


@pytest.fixture
def results_from_mock(config):
    """Build ExtractionResults from a {filename: raw-extraction} mapping."""
    def _build(mock: dict):
        return [coerce_mock(name, raw, config) for name, raw in mock.items()]
    return _build
