"""Validate a TMS screen-map catalog."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from freight_recon.screen_mapping import load_screen_map_catalog, summarize_observation, validate_screen_map_catalog  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MAP = ROOT / "configs" / "tms" / "ascendtms_screen_map.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--map", default=str(DEFAULT_MAP), help="Path to a JSON TMS screen-map catalog")
    parser.add_argument("--summary", action="store_true", help="Print observed/nav/seed mapping readiness")
    args = parser.parse_args()

    ok, message = validate_screen_map_catalog(args.map)
    print(message)
    if ok and args.summary:
        summary = summarize_observation(load_screen_map_catalog(args.map))
        print(summary.model_dump_json(indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
