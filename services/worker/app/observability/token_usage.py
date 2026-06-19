from __future__ import annotations

from typing import Any


def latest_token_usage_from_llm(llm: Any) -> dict[str, float] | None:
    gateway = getattr(llm, "gateway", None)
    if gateway is None:
        return None
    usage = getattr(gateway, "last_token_usage", None)
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("prompt")
    completion = usage.get("completion")
    if prompt is None or completion is None:
        return None
    return {"prompt": float(prompt), "completion": float(completion)}
