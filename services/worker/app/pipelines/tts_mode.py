from __future__ import annotations

from typing import Any, Literal

TtsMode = Literal["global"]

MASTER_TTS_SLOT_ID = "__master__"
VO_MASTER_CLIP_ID = "vo-master"
MASTER_TTS_WAV_NAME = "master.wav"


def resolve_tts_mode(plan: dict[str, Any] | None = None) -> TtsMode:
    """Global master narration TTS is the only supported synthesis mode."""
    _ = plan
    return "global"


def is_global_tts_mode(mode: str | None) -> bool:
    return True


def global_tts_eligible(plan: dict[str, Any], *, mode: TtsMode | None = None) -> bool:
    _ = mode
    return bool(str(plan.get("masterNarration") or "").strip())
