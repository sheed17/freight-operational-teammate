"""Tests for the real-TMS read-only observation harness."""

from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from drive_real_tms import build_observation_task, _redact_sensitive, _validate_task, _validate_observation_target  # noqa: E402
from freight_recon.screen_mapping import ObservationStatus, load_screen_map_catalog  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
ASCENDTMS_MAP = ROOT / "configs" / "tms" / "ascendtms_screen_map.json"


def test_real_tms_observation_task_contains_read_only_guard():
    catalog = load_screen_map_catalog(ASCENDTMS_MAP)
    screen = next(screen for screen in catalog.screens if screen.screen_id == "load_board")

    task = build_observation_task(screen, "Read visible headings and fields.")

    assert "READ-ONLY OBSERVATION ONLY" in task
    assert "Do NOT click Save" in task
    assert "Return ONLY valid JSON" in task
    assert "Load ID" in task


@pytest.mark.parametrize("bad_task", ["submit a payable", "save this load", "upload the POD", "delete the carrier"])
def test_real_tms_observation_rejects_risky_task_verbs(bad_task):
    with pytest.raises(SystemExit, match="blocked action verb"):
        _validate_task(bad_task)


def test_seed_pending_screen_requires_explicit_observation_flag():
    catalog = load_screen_map_catalog(ASCENDTMS_MAP)
    screen = next(screen for screen in catalog.screens if screen.observation_status == ObservationStatus.SEED_PENDING_OBSERVATION)

    with pytest.raises(SystemExit, match="SEED_PENDING_OBSERVATION"):
        _validate_observation_target(screen, allow_seed=False)

    _validate_observation_target(screen, allow_seed=True)


def test_observation_artifact_redacts_sensitive_strings():
    redacted = _redact_sensitive("token: abc123\nAuthorization: Bearer secret\napi_key=sk-test")

    assert "abc123" not in redacted
    assert "Bearer secret" not in redacted
    assert "sk-test" not in redacted
    assert "[redacted]" in redacted
