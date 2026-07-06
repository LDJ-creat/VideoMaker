from __future__ import annotations

from typing import Any


def normalize_token_usage(usage: Any) -> dict[str, float] | None:
    """Return AgentRunLog-safe tokenUsage (prompt + completion only)."""
    if not isinstance(usage, dict):
        return None
    prompt = usage.get("prompt")
    if prompt is None:
        prompt = usage.get("prompt_tokens")
    if prompt is None:
        prompt = usage.get("input_tokens")
    completion = usage.get("completion")
    if completion is None:
        completion = usage.get("completion_tokens")
    if completion is None:
        completion = usage.get("output_tokens")
    if prompt is None or completion is None:
        return None
    return {"prompt": float(prompt), "completion": float(completion)}


def latest_token_usage_from_llm(llm: Any) -> dict[str, float] | None:
    gateway = getattr(llm, "gateway", None)
    if gateway is None:
        return None
    return normalize_token_usage(getattr(gateway, "last_token_usage", None))
