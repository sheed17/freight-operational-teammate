"""Typed screen maps for TMS/browser-agent exploration.

Screen maps are the bridge between "the screen is the API" and Neyma's safety spine. They describe
what a browser agent may read, what it must never do, where a human confirmation point exists, and
how any eventual write would be verified. They are configuration artifacts, not free-form prompts.
"""

from __future__ import annotations

import json
from enum import Enum
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator


class ScreenRisk(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AutomationMode(str, Enum):
    READ_ONLY = "READ_ONLY"
    PREPARE_ONLY = "PREPARE_ONLY"
    APPROVED_WRITE = "APPROVED_WRITE"


class ObservationStatus(str, Enum):
    OBSERVED = "OBSERVED"
    NAV_OBSERVED = "NAV_OBSERVED"
    SEED_PENDING_OBSERVATION = "SEED_PENDING_OBSERVATION"


class ScreenField(BaseModel):
    name: str
    label: str
    selector_hint: str | None = None
    required_for_read: bool = False
    may_prepare_write: bool = False
    notes: str | None = None


class ScreenActionBoundary(BaseModel):
    allowed_actions: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    human_confirmation_point: str | None = None
    readback_verification_point: str | None = None

    @model_validator(mode="after")
    def require_forbidden_actions(self) -> "ScreenActionBoundary":
        if not self.forbidden_actions:
            raise ValueError("screen maps must list forbidden actions")
        return self


class ScreenMap(BaseModel):
    screen_id: str
    name: str
    url_pattern: str
    navigation_path: list[str]
    purpose: str
    risk: ScreenRisk = ScreenRisk.LOW
    automation_mode: AutomationMode = AutomationMode.READ_ONLY
    stable_selectors: list[str] = Field(default_factory=list)
    fields: list[ScreenField] = Field(default_factory=list)
    action_boundary: ScreenActionBoundary
    failure_modes: list[str] = Field(default_factory=list)
    mock_tms_alignment: str | None = None
    observation_status: ObservationStatus = ObservationStatus.SEED_PENDING_OBSERVATION
    observation_evidence: list[str] = Field(default_factory=list)

    @field_validator("screen_id")
    @classmethod
    def screen_id_slug(cls, value: str) -> str:
        if not value.replace("_", "").replace("-", "").isalnum():
            raise ValueError("screen_id must be a simple slug")
        return value

    @model_validator(mode="after")
    def enforce_safety_contract(self) -> "ScreenMap":
        if not self.navigation_path:
            raise ValueError(f"{self.screen_id}: navigation_path is required")
        if not self.stable_selectors:
            raise ValueError(f"{self.screen_id}: stable_selectors are required")
        if not self.fields:
            raise ValueError(f"{self.screen_id}: fields are required")
        if not self.failure_modes:
            raise ValueError(f"{self.screen_id}: failure_modes are required")
        if self.observation_status != ObservationStatus.SEED_PENDING_OBSERVATION and not self.observation_evidence:
            raise ValueError(f"{self.screen_id}: observed screens require observation evidence")
        if self.automation_mode != AutomationMode.READ_ONLY:
            if not self.action_boundary.human_confirmation_point:
                raise ValueError(f"{self.screen_id}: write-capable screens require human confirmation")
            if not self.action_boundary.readback_verification_point:
                raise ValueError(f"{self.screen_id}: write-capable screens require readback verification")
        if self.automation_mode == AutomationMode.READ_ONLY:
            write_fields = [field.name for field in self.fields if field.may_prepare_write]
            if write_fields:
                raise ValueError(f"{self.screen_id}: read-only screens cannot mark write fields: {write_fields}")
        return self


class TmsScreenMapCatalog(BaseModel):
    tms_name: str
    environment: str
    source: str
    default_automation_mode: AutomationMode = AutomationMode.READ_ONLY
    allowed_domains: list[str]
    prohibited_global_actions: list[str]
    screens: list[ScreenMap]

    @model_validator(mode="after")
    def enforce_catalog_contract(self) -> "TmsScreenMapCatalog":
        if not self.allowed_domains:
            raise ValueError("allowed_domains is required")
        if not self.prohibited_global_actions:
            raise ValueError("prohibited_global_actions is required")
        if len({screen.screen_id for screen in self.screens}) != len(self.screens):
            raise ValueError("screen_id values must be unique")
        if self.default_automation_mode != AutomationMode.READ_ONLY:
            raise ValueError("new TMS catalogs must default to READ_ONLY")
        return self


class ObservationSummary(BaseModel):
    tms_name: str
    total_screens: int
    observed: list[str]
    nav_observed: list[str]
    seed_pending_observation: list[str]
    adapter_ready_read_only: list[str]
    blocked_for_real_adapter: list[str]


def load_screen_map_catalog(path: str | Path) -> TmsScreenMapCatalog:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return TmsScreenMapCatalog.model_validate(data)


def validate_screen_map_catalog(path: str | Path) -> tuple[bool, str]:
    try:
        catalog = load_screen_map_catalog(path)
    except (OSError, json.JSONDecodeError, ValidationError, ValueError) as exc:
        return False, str(exc)
    return True, f"{catalog.tms_name}: {len(catalog.screens)} screens valid"


def summarize_observation(catalog: TmsScreenMapCatalog) -> ObservationSummary:
    """Summarize which screens are ready for real read-only adapters.

    Only fully observed, read-only screens are adapter-ready. Navigation-only and seed screens are
    intentionally blocked from real browser-use targeting until their internals are observed.
    """
    observed = [screen.screen_id for screen in catalog.screens if screen.observation_status == ObservationStatus.OBSERVED]
    nav_observed = [
        screen.screen_id for screen in catalog.screens if screen.observation_status == ObservationStatus.NAV_OBSERVED
    ]
    seed_pending = [
        screen.screen_id
        for screen in catalog.screens
        if screen.observation_status == ObservationStatus.SEED_PENDING_OBSERVATION
    ]
    adapter_ready = [
        screen.screen_id
        for screen in catalog.screens
        if screen.observation_status == ObservationStatus.OBSERVED
        and screen.automation_mode == AutomationMode.READ_ONLY
    ]
    blocked = [
        screen.screen_id
        for screen in catalog.screens
        if screen.screen_id not in set(adapter_ready)
    ]
    return ObservationSummary(
        tms_name=catalog.tms_name,
        total_screens=len(catalog.screens),
        observed=observed,
        nav_observed=nav_observed,
        seed_pending_observation=seed_pending,
        adapter_ready_read_only=adapter_ready,
        blocked_for_real_adapter=blocked,
    )
