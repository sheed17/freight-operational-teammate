"""Typed screen maps for TMS/browser-agent exploration.

Screen maps are the bridge between "the screen is the API" and Neyma's safety spine. They describe
what a browser agent may read, what it must never do, where a human confirmation point exists, and
how any eventual write would be verified. They are configuration artifacts, not free-form prompts.
"""

from __future__ import annotations

import json
import fnmatch
import re
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


class ScreenFieldObservation(BaseModel):
    name: str
    label_seen: str
    value_seen: str | None = None
    selector_evidence: str | None = None
    required_for_read_confirmed: bool = False


class ScreenObservation(BaseModel):
    """A single read-only observation captured from a real/reference TMS screen.

    This is intentionally evidence-shaped. It lets a human/browser-use session record what was seen,
    then promote only the matching screen metadata in the catalog. It must never carry secrets,
    cookies, credentials, or proposed writes.
    """

    screen_id: str
    observed_url: str
    status: ObservationStatus
    observed_at: str
    observer: str = "codex"
    title: str | None = None
    navigation_path_seen: list[str] = Field(default_factory=list)
    stable_selectors_seen: list[str] = Field(default_factory=list)
    field_observations: list[ScreenFieldObservation] = Field(default_factory=list)
    action_controls_seen: list[str] = Field(default_factory=list)
    forbidden_controls_seen: list[str] = Field(default_factory=list)
    screenshot_path: str | None = None
    notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def enforce_observation_contract(self) -> "ScreenObservation":
        if self.status == ObservationStatus.SEED_PENDING_OBSERVATION:
            raise ValueError("observations may only record NAV_OBSERVED or OBSERVED evidence")
        if self.status == ObservationStatus.OBSERVED:
            if not self.stable_selectors_seen:
                raise ValueError("OBSERVED screen evidence requires stable_selectors_seen")
            if not self.field_observations:
                raise ValueError("OBSERVED screen evidence requires field_observations")
        return self


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


def apply_screen_observation(
    catalog: TmsScreenMapCatalog,
    observation: ScreenObservation,
) -> TmsScreenMapCatalog:
    """Return a catalog updated with one read-only observation.

    Promotion to OBSERVED is deliberately strict:
    - observed URL must match an allowed domain;
    - all required fields on the target screen must be observed and confirmed;
    - forbidden controls seen during observation are appended to the safety boundary;
    - the resulting catalog is revalidated.
    """

    _require_allowed_url(catalog, observation.observed_url)
    updated = []
    matched = False
    for screen in catalog.screens:
        if screen.screen_id != observation.screen_id:
            updated.append(screen)
            continue
        matched = True
        _require_screen_url_match(screen, observation.observed_url)
        if observation.status == ObservationStatus.OBSERVED:
            _require_selector_overlap(screen, observation)
            _require_required_fields(screen, observation)
        evidence = _observation_evidence_lines(observation)
        forbidden = list(dict.fromkeys(screen.action_boundary.forbidden_actions + observation.forbidden_controls_seen))
        action_boundary = screen.action_boundary.model_copy(update={"forbidden_actions": forbidden})
        updates = {
            "observation_status": observation.status,
            "observation_evidence": list(dict.fromkeys(screen.observation_evidence + evidence)),
            "action_boundary": action_boundary,
        }
        if observation.stable_selectors_seen:
            updates["stable_selectors"] = list(
                dict.fromkeys(screen.stable_selectors + observation.stable_selectors_seen)
            )
        updated.append(screen.model_copy(update=updates))
    if not matched:
        raise ValueError(f"screen_id not found in catalog: {observation.screen_id}")
    return TmsScreenMapCatalog.model_validate(catalog.model_copy(update={"screens": updated}).model_dump(mode="json"))


def _require_allowed_url(catalog: TmsScreenMapCatalog, url: str) -> None:
    match = re.match(r"^https?://([^/:]+)(?::\d+)?(?:/|$)", url)
    if not match:
        raise ValueError(f"observation URL is not http(s): {url}")
    host = match.group(1).lower()
    allowed = {domain.lower() for domain in catalog.allowed_domains}
    wildcard_allowed = {
        domain[2:].lower()
        for domain in allowed
        if domain.startswith("*.")
    }
    if host in allowed or any(host == domain or host.endswith(f".{domain}") for domain in wildcard_allowed):
        return
    raise ValueError(f"observation URL host is not allowlisted: {host}")


def _require_screen_url_match(screen: ScreenMap, url: str) -> None:
    subdomain_pattern = screen.url_pattern.replace("https://ascendtms.com", "https://*.ascendtms.com")
    if not (fnmatch.fnmatch(url, screen.url_pattern) or fnmatch.fnmatch(url, subdomain_pattern)):
        raise ValueError(
            f"{screen.screen_id}: observation URL does not match screen url_pattern "
            f"{screen.url_pattern}: {url}"
        )


def _require_selector_overlap(screen: ScreenMap, observation: ScreenObservation) -> None:
    configured = [selector.lower() for selector in screen.stable_selectors]
    observed = [selector.lower() for selector in observation.stable_selectors_seen]
    if any(
        configured_selector in observed_selector or observed_selector in configured_selector
        for configured_selector in configured
        for observed_selector in observed
    ):
        return
    raise ValueError(f"{screen.screen_id}: OBSERVED evidence does not overlap configured stable selectors")


def _require_required_fields(screen: ScreenMap, observation: ScreenObservation) -> None:
    observed = {
        field.name
        for field in observation.field_observations
        if field.required_for_read_confirmed
    }
    missing = [
        field.name
        for field in screen.fields
        if field.required_for_read and field.name not in observed
    ]
    if missing:
        raise ValueError(f"{screen.screen_id}: OBSERVED evidence is missing required fields: {missing}")


def _observation_evidence_lines(observation: ScreenObservation) -> list[str]:
    lines = [
        f"{observation.observed_at}: observed {observation.title or observation.screen_id} at {observation.observed_url}",
    ]
    if observation.navigation_path_seen:
        lines.append(f"Navigation path seen: {' > '.join(observation.navigation_path_seen)}")
    if observation.stable_selectors_seen:
        lines.append(f"Stable selectors seen: {', '.join(observation.stable_selectors_seen)}")
    if observation.field_observations:
        fields = ", ".join(f"{field.name} ({field.label_seen})" for field in observation.field_observations)
        lines.append(f"Fields observed: {fields}")
    if observation.action_controls_seen:
        lines.append(f"Action controls seen: {', '.join(observation.action_controls_seen)}")
    if observation.screenshot_path:
        lines.append(f"Screenshot evidence: {observation.screenshot_path}")
    lines.extend(observation.notes)
    return lines
