"""Tests for typed TMS screen-map catalogs."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from freight_recon.screen_mapping import (
    AutomationMode,
    ObservationStatus,
    ScreenActionBoundary,
    ScreenField,
    ScreenMap,
    TmsScreenMapCatalog,
    load_screen_map_catalog,
    summarize_observation,
    validate_screen_map_catalog,
)

ROOT = Path(__file__).resolve().parents[2]
ASCENDTMS_MAP = ROOT / "configs" / "tms" / "ascendtms_screen_map.json"


def test_ascendtms_screen_map_catalog_is_valid_and_read_only():
    catalog = load_screen_map_catalog(ASCENDTMS_MAP)

    assert catalog.tms_name == "AscendTMS"
    assert catalog.environment == "reference_trial_sandbox"
    assert catalog.source == "reference_ui_mixed_live_observation_and_seed_pending_deeper_screen_mapping"
    assert catalog.default_automation_mode == AutomationMode.READ_ONLY
    assert "ascendtms.com" in catalog.allowed_domains
    assert {screen.screen_id for screen in catalog.screens} >= {
        "organization_settings",
        "load_board",
        "load_detail",
        "document_management",
        "carrier_profile",
        "accounting_payables",
    }
    assert all(screen.automation_mode == AutomationMode.READ_ONLY for screen in catalog.screens)
    assert all(screen.action_boundary.forbidden_actions for screen in catalog.screens)
    assert any(screen.risk.value == "HIGH" for screen in catalog.screens)
    observed = {screen.screen_id: screen for screen in catalog.screens}
    assert observed["organization_settings"].observation_status == ObservationStatus.OBSERVED
    assert observed["organization_settings"].observation_evidence
    assert observed["load_board"].observation_status == ObservationStatus.NAV_OBSERVED
    assert observed["load_detail"].observation_status == ObservationStatus.SEED_PENDING_OBSERVATION


def test_validate_screen_map_catalog_reports_success():
    ok, message = validate_screen_map_catalog(ASCENDTMS_MAP)

    assert ok is True
    assert message == "AscendTMS: 6 screens valid"


def test_observation_summary_blocks_unobserved_screens_from_real_adapter():
    catalog = load_screen_map_catalog(ASCENDTMS_MAP)
    summary = summarize_observation(catalog)

    assert summary.total_screens == 6
    assert summary.adapter_ready_read_only == ["organization_settings"]
    assert "load_board" in summary.nav_observed
    assert "load_detail" in summary.seed_pending_observation
    assert set(summary.blocked_for_real_adapter) == {
        "load_board",
        "load_detail",
        "document_management",
        "carrier_profile",
        "accounting_payables",
    }


def test_read_only_screen_cannot_declare_write_fields():
    with pytest.raises(ValidationError, match="read-only screens cannot mark write fields"):
        ScreenMap(
            screen_id="payables",
            name="Payables",
            url_pattern="https://example.test/payables",
            navigation_path=["Accounting"],
            purpose="Read payables",
            automation_mode=AutomationMode.READ_ONLY,
            stable_selectors=["payables table"],
            fields=[
                ScreenField(
                    name="amount",
                    label="Amount",
                    required_for_read=True,
                    may_prepare_write=True,
                )
            ],
            action_boundary=ScreenActionBoundary(
                allowed_actions=["read"],
                forbidden_actions=["submit payable"],
            ),
            failure_modes=["submit button adjacent to read-only rows"],
        )


def test_observed_screen_requires_evidence():
    with pytest.raises(ValidationError, match="observed screens require observation evidence"):
        ScreenMap(
            screen_id="loads",
            name="Loads",
            url_pattern="https://example.test/loads",
            navigation_path=["Loads"],
            purpose="Read loads",
            automation_mode=AutomationMode.READ_ONLY,
            stable_selectors=["loads table"],
            fields=[ScreenField(name="load_id", label="Load ID", required_for_read=True)],
            action_boundary=ScreenActionBoundary(
                allowed_actions=["read"],
                forbidden_actions=["create load"],
            ),
            failure_modes=["load not found"],
            observation_status=ObservationStatus.OBSERVED,
        )


def test_write_capable_screen_requires_confirmation_and_readback():
    with pytest.raises(ValidationError, match="write-capable screens require human confirmation"):
        ScreenMap(
            screen_id="payables",
            name="Payables",
            url_pattern="https://example.test/payables",
            navigation_path=["Accounting"],
            purpose="Prepare payables",
            automation_mode=AutomationMode.PREPARE_ONLY,
            stable_selectors=["payables table"],
            fields=[ScreenField(name="amount", label="Amount", may_prepare_write=True)],
            action_boundary=ScreenActionBoundary(
                allowed_actions=["prepare payable"],
                forbidden_actions=["submit payable"],
            ),
            failure_modes=["readback mismatch"],
        )


def test_prepare_only_screen_valid_with_confirmation_and_readback():
    screen = ScreenMap(
        screen_id="payable_prepare",
        name="Payable Prepare",
        url_pattern="https://example.test/payables/prepare",
        navigation_path=["Accounting", "Carrier Payables", "Prepare"],
        purpose="Prepare a payable amount without submitting it",
        automation_mode=AutomationMode.PREPARE_ONLY,
        stable_selectors=["payable amount input", "prepare button", "preview diff panel"],
        fields=[
            ScreenField(name="load_id", label="Load ID", required_for_read=True),
            ScreenField(name="approved_amount", label="Approved Amount", may_prepare_write=True),
        ],
        action_boundary=ScreenActionBoundary(
            allowed_actions=["fill approved amount into prepare form", "open preview diff"],
            forbidden_actions=["submit payable", "pay carrier", "send remittance"],
            human_confirmation_point="human reviews preview diff before any submit action",
            readback_verification_point="read prepared payable preview values before submit",
        ),
        failure_modes=["preview amount differs from approved amount", "session expires"],
        observation_status=ObservationStatus.OBSERVED,
        observation_evidence=["test fixture observed prepare controls"],
    )

    assert screen.automation_mode == AutomationMode.PREPARE_ONLY
    assert screen.action_boundary.human_confirmation_point
    assert screen.action_boundary.readback_verification_point


def test_approved_write_screen_valid_with_confirmation_and_readback():
    screen = ScreenMap(
        screen_id="payable_submit",
        name="Payable Submit",
        url_pattern="https://example.test/payables/submit",
        navigation_path=["Accounting", "Carrier Payables", "Submit"],
        purpose="Submit an already prepared payable after explicit approval",
        automation_mode=AutomationMode.APPROVED_WRITE,
        stable_selectors=["submit payable button", "confirmation modal", "payable status"],
        fields=[
            ScreenField(name="load_id", label="Load ID", required_for_read=True),
            ScreenField(name="payable_status", label="Payable Status", required_for_read=True),
        ],
        action_boundary=ScreenActionBoundary(
            allowed_actions=["click submit only after explicit approval", "read resulting status"],
            forbidden_actions=["change amount", "pay carrier without approval", "export payment file"],
            human_confirmation_point="explicit human approval recorded on the workflow action",
            readback_verification_point="payable status and amount read back after submit",
        ),
        failure_modes=["confirmation modal changes amount", "readback mismatch", "duplicate warning"],
        observation_status=ObservationStatus.OBSERVED,
        observation_evidence=["test fixture observed submit controls"],
    )

    assert screen.automation_mode == AutomationMode.APPROVED_WRITE


def test_catalog_must_default_to_read_only():
    valid_screen = ScreenMap(
        screen_id="loads",
        name="Loads",
        url_pattern="https://example.test/loads",
        navigation_path=["Loads"],
        purpose="Read loads",
        automation_mode=AutomationMode.READ_ONLY,
        stable_selectors=["loads table"],
        fields=[ScreenField(name="load_id", label="Load ID", required_for_read=True)],
        action_boundary=ScreenActionBoundary(
            allowed_actions=["read"],
            forbidden_actions=["create load"],
        ),
        failure_modes=["load not found"],
    )

    with pytest.raises(ValidationError, match="new TMS catalogs must default to READ_ONLY"):
        TmsScreenMapCatalog(
            tms_name="ExampleTMS",
            environment="sandbox",
            source="test",
            default_automation_mode=AutomationMode.APPROVED_WRITE,
            allowed_domains=["example.test"],
            prohibited_global_actions=["submit payment"],
            screens=[valid_screen],
        )
