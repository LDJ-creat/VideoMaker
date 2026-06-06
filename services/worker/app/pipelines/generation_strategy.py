from __future__ import annotations

import os

from app.pipelines.duration_target import short_form_max_sec


def resolve_generation_strategy(target_sec: float) -> str:
    threshold = short_form_max_sec()
    if float(target_sec) <= threshold:
        return "short_form_direct"
    return "long_form_composed"


def is_short_form_strategy(strategy: str | None) -> bool:
    return strategy == "short_form_direct"


def short_form_video_gen_enabled() -> bool:
    return os.getenv("VIDEOMAKER_SHORT_FORM_VIDEO_GEN", "1").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
