from __future__ import annotations

from typing import Any


def normalize_chat_usage(raw: dict[str, Any] | None) -> dict[str, float] | None:
    """Normalize vendor-specific chat usage to prompt/completion/total."""
    if not isinstance(raw, dict):
        return None

    prompt = raw.get("prompt_tokens")
    if prompt is None:
        prompt = raw.get("input_tokens")
    if prompt is None:
        prompt = raw.get("prompt")

    completion = raw.get("completion_tokens")
    if completion is None:
        completion = raw.get("output_tokens")
    if completion is None:
        completion = raw.get("completion")

    total = raw.get("total_tokens")
    if total is None:
        total = raw.get("total")

    if prompt is None and completion is None and total is None:
        return None

    result: dict[str, float] = {}
    if prompt is not None:
        result["prompt"] = float(prompt)
    if completion is not None:
        result["completion"] = float(completion)
    if total is not None:
        result["total"] = float(total)
    elif "prompt" in result and "completion" in result:
        result["total"] = result["prompt"] + result["completion"]

    if "prompt" not in result and "completion" not in result:
        return None
    return result


def usage_units_from_tokens(usage: dict[str, float] | None) -> dict[str, Any] | None:
    if not usage:
        return None
    payload: dict[str, Any] = {"kind": "tokens"}
    if "prompt" in usage:
        payload["prompt"] = usage["prompt"]
    if "completion" in usage:
        payload["completion"] = usage["completion"]
    if "total" in usage:
        payload["total"] = usage["total"]
    return payload


def usage_units_chars(char_count: int) -> dict[str, Any]:
    return {"kind": "chars", "chars": float(char_count), "calls": 1.0}


def usage_units_images(count: int = 1) -> dict[str, Any]:
    return {"kind": "images", "images": float(count), "calls": float(count)}


def usage_units_video_seconds(
    *,
    requested: float | None = None,
    actual: float | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"kind": "video_seconds", "calls": 1.0}
    if requested is not None:
        payload["requestedDurationSec"] = float(requested)
    if actual is not None:
        payload["actualDurationSec"] = float(actual)
    return payload
