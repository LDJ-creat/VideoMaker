from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def read_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def storyboard_scenes(plan: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(plan, dict):
        return []
    storyboard = plan.get("storyboard")
    if isinstance(storyboard, list):
        return [item for item in storyboard if isinstance(item, dict)]
    if isinstance(storyboard, dict):
        scenes = storyboard.get("scenes")
        if isinstance(scenes, list):
            return [item for item in scenes if isinstance(item, dict)]
    return []


def slot_match_items(matches: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(matches, dict):
        return []
    for key in ("slotMatches", "matches", "slots"):
        raw = matches.get(key)
        if isinstance(raw, list):
            return [item for item in raw if isinstance(item, dict)]
    return []


def find_generation_mp4(generation_root: Path) -> Path | None:
    for candidate in (
        generation_root / "output.mp4",
        generation_root / "render" / "output.mp4",
        generation_root / "preview" / "output.mp4",
    ):
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
    renders_root = generation_root.parent.parent / "renders" / generation_root.name / "output.mp4"
    if renders_root.is_file() and renders_root.stat().st_size > 0:
        return renders_root
    return None


def target_duration_sec(generation_root: Path) -> float | None:
    for name in ("duration-target.json", "generation-plan.json"):
        payload = read_json(generation_root / name)
        if not isinstance(payload, dict):
            continue
        for key in ("targetSec", "targetDurationSec", "durationSec"):
            if payload.get(key) is not None:
                try:
                    return float(payload[key])
                except (TypeError, ValueError):
                    continue
        timeline = payload.get("timeline")
        if isinstance(timeline, dict) and timeline.get("durationSec") is not None:
            try:
                return float(timeline["durationSec"])
            except (TypeError, ValueError):
                pass
    return None
