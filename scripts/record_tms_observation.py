"""Record a read-only TMS screen observation and optionally update a screen-map catalog."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from freight_recon.screen_mapping import (  # noqa: E402
    ScreenObservation,
    apply_screen_observation,
    load_screen_map_catalog,
    summarize_observation,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAP = ROOT / "configs" / "tms" / "ascendtms_screen_map.json"
DEFAULT_OUT = ROOT / "data" / "active_workspace" / "ascendtms_observations"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("observation", help="Path to a ScreenObservation JSON file")
    parser.add_argument("--map", default=str(DEFAULT_MAP), help="Screen-map catalog to validate/update")
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT), help="Directory to store validated observations")
    parser.add_argument("--apply", action="store_true", help="Apply the observation to the screen-map catalog")
    parser.add_argument("--text", action="store_true")
    args = parser.parse_args()

    observation_path = Path(args.observation)
    observation = ScreenObservation.model_validate(json.loads(observation_path.read_text(encoding="utf-8")))
    catalog_path = Path(args.map)
    catalog = load_screen_map_catalog(catalog_path)
    updated = apply_screen_observation(catalog, observation)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamped = out_dir / f"{_safe_slug(observation.screen_id)}_{_timestamp_slug()}.json"
    stamped.write_text(observation.model_dump_json(indent=2), encoding="utf-8")

    if args.apply:
        catalog_path.write_text(
            json.dumps(updated.model_dump(mode="json"), indent=2) + "\n",
            encoding="utf-8",
        )

    summary = summarize_observation(updated)
    result = {
        "ok": True,
        "observation_saved": str(stamped),
        "catalog_updated": bool(args.apply),
        "screen_id": observation.screen_id,
        "status": observation.status.value,
        "adapter_ready_read_only": summary.adapter_ready_read_only,
        "blocked_for_real_adapter": summary.blocked_for_real_adapter,
    }
    if args.text:
        print()
        print("TMS Observation")
        print(f"Screen: {result['screen_id']}")
        print(f"Status: {result['status']}")
        print(f"Saved: {result['observation_saved']}")
        print(f"Catalog updated: {result['catalog_updated']}")
        print(f"Adapter-ready read-only: {', '.join(result['adapter_ready_read_only']) or '-'}")
        print(f"Still blocked: {', '.join(result['blocked_for_real_adapter']) or '-'}")
    else:
        print(json.dumps(result, indent=2))
    return 0


def _safe_slug(value: str) -> str:
    return "".join(char if char.isalnum() or char in "-_" else "_" for char in value) or "screen"


def _timestamp_slug() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


if __name__ == "__main__":
    raise SystemExit(main())
