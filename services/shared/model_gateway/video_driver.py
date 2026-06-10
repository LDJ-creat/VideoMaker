"""Resolve pluggable video driver from stored settings and base URL."""

from __future__ import annotations

DEFAULT_DASHSCOPE_T2V_MODEL = "wan2.7-t2v"
DEFAULT_DASHSCOPE_I2V_MODEL = "wan2.6-i2v-flash"
DEFAULT_SEEDDANCE_MODEL = "doubao-seedance-2-0-260128"

_LEGACY_T2V_MODELS = frozenset(
    {
        "wan2.1-t2v-plus",
        "wan2.1-t2v-turbo",
        "wan2.2-t2v-plus",
        "wan2.5-t2v-preview",
    }
)

_SEEDDANCE_RATIOS = frozenset({"16:9", "9:16", "4:3", "3:4", "21:9", "1:1", "adaptive"})
_SEEDDANCE_MIN_DURATION = 4
_SEEDDANCE_MAX_DURATION = 15


def is_dashscope_host(base_url: str) -> bool:
    return "dashscope" in (base_url or "").lower()


def is_volcengine_ark_host(base_url: str) -> bool:
    return "volces.com" in (base_url or "").lower()


def _is_wan_model_name(model: str) -> bool:
    lowered = (model or "").strip().lower()
    if not lowered:
        return False
    if lowered.startswith("wan"):
        return True
    return lowered in _LEGACY_T2V_MODELS


def resolve_effective_video_driver(driver: str, base_url: str) -> str:
    """Pick the runtime video driver."""
    normalized = (driver or "").strip().lower()
    if normalized in {"dashscope_wan", "dashscope"}:
        return "dashscope_wan"
    if normalized in {"volcengine_seeddance", "seeddance", "ark_seeddance"}:
        return "volcengine_seeddance"
    if is_dashscope_host(base_url):
        return "dashscope_wan"
    if is_volcengine_ark_host(base_url):
        return "volcengine_seeddance"
    if normalized == "generic_job":
        return "generic_job"
    return normalized or "generic_job"


def normalize_video_model(model: str, *, base_url: str) -> str:
    """Map stored video model names to provider-specific identifiers."""
    trimmed = (model or "").strip()
    if is_dashscope_host(base_url):
        if not trimmed:
            return DEFAULT_DASHSCOPE_T2V_MODEL
        lowered = trimmed.lower()
        if "image" in lowered and "i2v" not in lowered and "t2v" not in lowered:
            return DEFAULT_DASHSCOPE_T2V_MODEL
        if lowered in _LEGACY_T2V_MODELS:
            return DEFAULT_DASHSCOPE_T2V_MODEL
        return trimmed
    if is_volcengine_ark_host(base_url):
        if not trimmed or _is_wan_model_name(trimmed):
            return DEFAULT_SEEDDANCE_MODEL
        lowered = trimmed.lower()
        if "image" in lowered and "seedance" not in lowered:
            return DEFAULT_SEEDDANCE_MODEL
        return trimmed
    return trimmed


def normalize_wan_model_for_mode(model: str, *, mode: str) -> str:
    """Pick t2v/i2v model at call time when a single store model is shared."""
    trimmed = (model or "").strip()
    normalized_mode = (mode or "t2v").lower()
    if not trimmed:
        return (
            DEFAULT_DASHSCOPE_I2V_MODEL
            if normalized_mode == "i2v"
            else DEFAULT_DASHSCOPE_T2V_MODEL
        )
    lowered = trimmed.lower()
    if normalized_mode == "i2v":
        if "r2v" in lowered:
            return DEFAULT_DASHSCOPE_I2V_MODEL
        if "t2v" in lowered and "i2v" not in lowered:
            return DEFAULT_DASHSCOPE_I2V_MODEL
        return trimmed
    if "r2v" in lowered:
        return DEFAULT_DASHSCOPE_T2V_MODEL
    if "i2v" in lowered and "t2v" not in lowered:
        return DEFAULT_DASHSCOPE_T2V_MODEL
    if lowered in _LEGACY_T2V_MODELS:
        return DEFAULT_DASHSCOPE_T2V_MODEL
    return trimmed


def map_seeddance_duration(duration_sec: float) -> int:
    """Map storyboard duration to SeedDance-supported integer seconds (4-15)."""
    if duration_sec <= 0:
        return _SEEDDANCE_MIN_DURATION
    target = int(duration_sec + 0.999)
    return max(_SEEDDANCE_MIN_DURATION, min(target, _SEEDDANCE_MAX_DURATION))


def map_seeddance_resolution(resolution: str) -> str:
    """Map project resolution tier to SeedDance lowercase values."""
    tier = (resolution or "720P").strip().upper()
    if tier in {"480P", "720P", "1080P", "2K"}:
        return tier.lower()
    return "720p"


def map_seeddance_ratio(aspect_ratio: str) -> str:
    """Map project aspect ratio to SeedDance ratio parameter."""
    normalized = (aspect_ratio or "").strip()
    if normalized in _SEEDDANCE_RATIOS:
        return normalized
    return "16:9"
