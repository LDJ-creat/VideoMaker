from __future__ import annotations

import os
from typing import Any, Literal

TtsMode = Literal["global", "per_scene"]

MASTER_TTS_SLOT_ID = "__master__"
VO_MASTER_CLIP_ID = "vo-master"
MASTER_TTS_WAV_NAME = "master.wav"


def resolve_tts_mode(plan: dict[str, Any]) -> TtsMode:
    """Resolve TTS synthesis mode from env override or default global master narration."""
    env = os.getenv("VIDEOMAKER_TTS_MODE", "").strip().lower()
    if env in {"global", "per_scene"}:
        return env  # type: ignore[return-value]
    return "global"


def is_global_tts_mode(mode: str | None) -> bool:
    return str(mode or "").strip() == "global"


def global_tts_eligible(plan: dict[str, Any], *, mode: TtsMode | None = None) -> bool:
    resolved = mode or resolve_tts_mode(plan)
    if not is_global_tts_mode(resolved):
        return False
    return bool(str(plan.get("masterNarration") or "").strip())
