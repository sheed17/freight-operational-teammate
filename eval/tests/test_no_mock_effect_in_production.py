"""Regression guard: no PRODUCTION entry point may execute a financial effect against a mock.

The repository baseline audit (docs/architecture/repository-baseline-audit.md, finding R-01) found that
the supervised production runner passed ``--auto-enter-approved-mock-tms`` **by default**, which routed a
human-APPROVED payable into ``MockTmsWriteLedger`` — running the whole gated write path (approved-amount
binding, idempotency, verify-by-readback) against a JSON file, driving the workflow to an
externally-completed state, and telling the owner the payable was entered. **Nothing happened in reality.**

That is the archetype of the defect the architecture exists to prevent: a verified, audited,
"complete"-reported effect that never touched the world (violates R10 and I10 simultaneously).

These tests fail closed: they assert the path is *structurally* gone, not merely disabled by a default.
Mock ledgers remain available to tests (that is what they are for); they must never be reachable from a
production entry point via a flag, env var, config value, fallback, or default.
"""

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))


def test_production_hook_module_no_longer_exists():
    """The post-approval mock-execution hook is deleted, not merely disabled."""
    assert not (ROOT / "src" / "freight_recon" / "post_approval_execution.py").exists()
    with pytest.raises(ModuleNotFoundError):
        import freight_recon.post_approval_execution  # noqa: F401


def test_production_callback_server_exposes_no_mock_flag():
    """The production entry point cannot SELECT a mock financial adapter from its CLI."""
    source = (ROOT / "scripts" / "run_action_callback_server.py").read_text()
    assert "--auto-enter-approved-mock-tms" not in source
    assert "--mock-tms-ledger" not in source
    assert "MockTmsWriteLedger" not in source
    assert "MockTmsAutoEntryConfig" not in source


def test_production_callback_server_help_offers_no_mock_option():
    """Prove it at the real CLI surface, not just in the source text."""
    out = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "run_action_callback_server.py"), "--help"],
        capture_output=True, text=True, timeout=60,
    ).stdout
    assert "auto-enter-approved-mock-tms" not in out
    assert "mock-tms-ledger" not in out


def test_supervisor_never_passes_a_mock_financial_flag():
    """The supervised runner previously enabled the mock write path BY DEFAULT. It must never do so."""
    from run_teammate import build_process_commands

    cmds = build_process_commands(workspace="/tmp/ws", client_config="c")
    for name, argv in cmds.items():
        joined = " ".join(argv) if isinstance(argv, list) else str(argv)
        assert "mock" not in joined.lower(), f"{name} passes a mock flag: {joined}"


def test_production_runtime_cannot_construct_a_mock_financial_adapter():
    """No production module may import or construct MockTmsWriteLedger.

    ``tms_write`` still legitimately holds the gated write DRIVER (``enter_approved_payable``) — the
    production safety spine, which the live TruckingOffice writer drops into with a REAL ledger (audit
    finding R-03). What must not exist is a *production* path that selects the MOCK adapter.
    """
    production_modules = [
        ROOT / "scripts" / "run_action_callback_server.py",
        ROOT / "scripts" / "run_teammate.py",
        ROOT / "src" / "freight_recon" / "action_callback.py",
        ROOT / "src" / "freight_recon" / "operation_router.py",
    ]
    for mod in production_modules:
        text = mod.read_text()
        assert "MockTmsWriteLedger" not in text, f"{mod.name} can construct a mock financial adapter"


def test_mock_ledger_is_still_available_to_tests():
    """Mock adapters remain usable in explicitly test-scoped code. That is their only home."""
    from freight_recon.tms_write import MockTmsWriteLedger

    assert MockTmsWriteLedger is not None


def test_the_gated_write_driver_survives():
    """R-03: deleting tms_write.py wholesale would have removed PRODUCTION safety behaviour.

    ``enter_approved_payable`` is the gated write driver (approved-amount binding, idempotency, the
    APPROVED->...->DONE state machine, verify-by-readback). It is the spine, not the mock.
    """
    from freight_recon.tms_write import enter_approved_payable

    assert callable(enter_approved_payable)
