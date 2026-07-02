from __future__ import annotations

import os


def _parse_timeout_env(name: str, default: float) -> float:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        return max(30.0, float(raw))
    except ValueError:
        return default


def chat_timeout_sec(profile: str) -> float:
    """HTTP read/write timeout (seconds) for OpenAI-compatible chat by gateway profile."""
    if profile == "video_understanding":
        return _parse_timeout_env("VIDEOMAKER_GATEWAY_VIDEO_UNDERSTANDING_TIMEOUT_SEC", 300.0)
    if profile == "vision":
        return _parse_timeout_env("VIDEOMAKER_GATEWAY_VISION_TIMEOUT_SEC", 240.0)
    return _parse_timeout_env("VIDEOMAKER_GATEWAY_CHAT_TIMEOUT_SEC", 120.0)


def httpx_timeout_for_profile(profile: str) -> float:
    """Alias kept for tests; returns total read budget used by httpx.Timeout.read."""
    return chat_timeout_sec(profile)
