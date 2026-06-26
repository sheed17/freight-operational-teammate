"""Capture READ-ONLY observations from a human-established real TMS browser session.

This is an observation harness, not an execution adapter. It attaches to a Chrome session the human
already logged into via CDP, runs a bounded read-only browser-use task, and stores an evidence
artifact that can later be converted into a typed screen-map observation.

No credentials are stored. No write tasks are allowed. Do not use this for payable entry.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # pragma: no cover
    pass

from freight_recon.screen_mapping import (  # noqa: E402
    ObservationStatus,
    ScreenMap,
    load_screen_map_catalog,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAP = ROOT / "configs" / "tms" / "ascendtms_screen_map.json"
DEFAULT_OUT = ROOT / "data" / "active_workspace" / "ascendtms_observations"

READONLY_GUARD = (
    "READ-ONLY OBSERVATION ONLY. Do NOT click Save, Submit, Approve, Send, Delete, Create, Edit, "
    "Upload, Pay, Export, Dispatch, or change any field or value. Only navigate, open existing "
    "pages, and read visible labels/values."
)

RISKY_TASK_RE = re.compile(
    r"\b(save|submit|approve|send|delete|create|edit|upload|pay|export|dispatch|change|modify|enter payable)\b",
    re.IGNORECASE,
)


async def _run(args: argparse.Namespace) -> dict:
    catalog = load_screen_map_catalog(args.map)
    screen = _screen_by_id(catalog.screens, args.screen_id)
    _validate_observation_target(screen, allow_seed=args.allow_seed_observation)
    _validate_task(args.task)

    from browser_use.beta import Agent, BrowserProfile
    from browser_use import ChatOpenAI

    task = build_observation_task(screen, args.task)
    agent = Agent(
        task=task,
        llm=ChatOpenAI(model=args.model),
        browser_profile=BrowserProfile(
            cdp_url=args.cdp_url,
            allowed_domains=list(catalog.allowed_domains),
        ),
    )
    history = await agent.run(max_steps=args.max_steps)
    final = history.final_result() or ""
    artifact = build_observation_artifact(
        screen=screen,
        cdp_url=args.cdp_url,
        allowed_domains=list(catalog.allowed_domains),
        task=task,
        final_result=str(final),
        model=args.model,
    )
    out_path = _write_artifact(args.out_dir, artifact)
    artifact["artifact_path"] = str(out_path)
    return artifact


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--screen-id", required=True, help="Screen id from the TMS screen-map catalog")
    parser.add_argument(
        "--task",
        default=(
            "Observe this screen and return JSON with current_url, page_title, visible_headings, "
            "stable_labels, visible_fields, nearby_action_controls, and notes. If the screen is not "
            "available or there is no sandbox/fake data, say so."
        ),
        help="Read-only observation task. Write/action verbs are rejected.",
    )
    parser.add_argument("--map", default=str(DEFAULT_MAP), help="TMS screen-map catalog")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT), help="Where observation artifacts are stored")
    parser.add_argument("--cdp-url", default="http://localhost:9222", help="CDP URL of human-logged-in Chrome")
    parser.add_argument("--model", default="gpt-4.1-mini")
    parser.add_argument("--max-steps", type=int, default=15)
    parser.add_argument(
        "--allow-seed-observation",
        action="store_true",
        help="Allow observing a screen still marked SEED_PENDING_OBSERVATION. This does not make it adapter-ready.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    artifact = asyncio.run(_run(args))
    if args.json:
        print(json.dumps(artifact, indent=2))
    else:
        print()
        print("AscendTMS Observation")
        print(f"Screen: {artifact['screen_id']}")
        print(f"Status before observation: {artifact['screen_status_before']}")
        print(f"Artifact: {artifact['artifact_path']}")
        print("Result:")
        print(artifact["final_result"])
    return 0


def build_observation_task(screen: ScreenMap, user_task: str) -> str:
    field_labels = ", ".join(field.label for field in screen.fields)
    forbidden = ", ".join(screen.action_boundary.forbidden_actions)
    return f"""
Screen-map target: {screen.screen_id} - {screen.name}
Expected navigation path: {' > '.join(screen.navigation_path)}
Expected URL pattern: {screen.url_pattern}
Fields to observe if visible: {field_labels}
Forbidden controls/actions for this screen: {forbidden}

{READONLY_GUARD}

Task:
{user_task.strip()}

Return ONLY valid JSON. Do not include passwords, cookies, session tokens, local storage, or secrets.
"""


def build_observation_artifact(
    *,
    screen: ScreenMap,
    cdp_url: str,
    allowed_domains: list[str],
    task: str,
    final_result: str,
    model: str,
) -> dict:
    return {
        "screen_id": screen.screen_id,
        "screen_name": screen.name,
        "screen_status_before": screen.observation_status.value,
        "automation_mode": screen.automation_mode.value,
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "model": model,
        "cdp_url": _redact_url(cdp_url),
        "allowed_domains": allowed_domains,
        "read_only_guard": READONLY_GUARD,
        "task": task,
        "final_result": _redact_sensitive(final_result),
        "next_step": "Convert this artifact into a ScreenObservation JSON, then run scripts/record_tms_observation.py.",
    }


def _screen_by_id(screens: list[ScreenMap], screen_id: str) -> ScreenMap:
    for screen in screens:
        if screen.screen_id == screen_id:
            return screen
    raise SystemExit(f"screen_id not found in catalog: {screen_id}")


def _validate_observation_target(screen: ScreenMap, *, allow_seed: bool) -> None:
    if screen.automation_mode.value != "READ_ONLY":
        raise SystemExit(f"{screen.screen_id} is not READ_ONLY; real-TMS observation blocked")
    if screen.observation_status == ObservationStatus.SEED_PENDING_OBSERVATION and not allow_seed:
        raise SystemExit(
            f"{screen.screen_id} is SEED_PENDING_OBSERVATION. "
            "Pass --allow-seed-observation only for read-only evidence capture."
        )


def _validate_task(task: str) -> None:
    match = RISKY_TASK_RE.search(task)
    if match:
        raise SystemExit(f"real-TMS observation task contains blocked action verb: {match.group(1)}")


def _write_artifact(out_dir: str | Path, artifact: dict) -> Path:
    target = Path(out_dir)
    target.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = target / f"{artifact['screen_id']}_{stamp}.json"
    path.write_text(json.dumps(artifact, indent=2), encoding="utf-8")
    return path


def _redact_sensitive(text: str) -> str:
    text = re.sub(r"(?i)(password|token|secret|cookie|authorization)\s*[:=]\s*[^\n\r,;]+", r"\1: [redacted]", text)
    text = re.sub(r"(?i)(api[_-]?key)\s*[:=]\s*[^\n\r,;]+", r"\1: [redacted]", text)
    return text


def _redact_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.username or parsed.password:
        return parsed._replace(netloc=parsed.hostname or "").geturl()
    return url


if __name__ == "__main__":
    raise SystemExit(main())
