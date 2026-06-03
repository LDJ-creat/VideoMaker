"""Resolve pluggable video driver from stored settings and base URL."""

from __future__ import annotations

DEFAULT_DASHSCOPE_T2V_MODEL = "wan2.6-t2v"
DEFAULT_DASHSCOPE_I2V_MODEL = "wan2.6-i2v-flash"

_LEGACY_T2V_MODELS = frozenset(
    {
        "wan2.1-t2v-plus",
        "wan2.1-t2v-turbo",
        "wan2.2-t2v-plus",
        "wan2.5-t2v-preview",
    }
)


def is_dashscope_host(base_url: str) -> bool:
    return "dashscope" in (base_url or "").lower()


def resolve_effective_video_driver(driver: str, base_url: str) -> str:
    """Pick the runtime video driver."""
    normalized = (driver or "").strip().lower()
    if normalized in {"dashscope_wan", "dashscope"}:
        return "dashscope_wan"
    if is_dashscope_host(base_url):
        return "dashscope_wan"
    if normalized == "generic_job":
        return "generic_job"
    return normalized or "generic_job"


def normalize_video_model(model: str, *, base_url: str) -> str:
    """Map stored video model names to DashScope Wan identifiers."""
    trimmed = (model or "").strip()
    if not is_dashscope_host(base_url):
        return trimmed
    if not trimmed:
        return DEFAULT_DASHSCOPE_T2V_MODEL
    lowered = trimmed.lower()
    if "image" in lowered and "i2v" not in lowered and "t2v" not in lowered:
        return DEFAULT_DASHSCOPE_T2V_MODEL
    if lowered in _LEGACY_T2V_MODELS:
        return DEFAULT_DASHSCOPE_T2V_MODEL
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
        if "t2v" in lowered and "i2v" not in lowered:
            return DEFAULT_DASHSCOPE_I2V_MODEL
        return trimmed
    if "i2v" in lowered and "t2v" not in lowered:
        return DEFAULT_DASHSCOPE_T2V_MODEL
    if lowered in _LEGACY_T2V_MODELS:
        return DEFAULT_DASHSCOPE_T2V_MODEL
    return trimmed
