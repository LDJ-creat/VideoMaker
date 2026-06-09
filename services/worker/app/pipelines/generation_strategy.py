from __future__ import annotations

from typing import Any

from app.pipelines.tts_mode import MASTER_TTS_SLOT_ID, resolve_tts_mode

DEFAULT_GENERATION_STRATEGY = "long_form_composed"
VALID_GENERATION_STRATEGIES = frozenset({"long_form_composed", "short_form_direct"})


def resolve_generation_strategy(_target_sec: float | None = None) -> str:
    return DEFAULT_GENERATION_STRATEGY


def normalize_generation_strategy(strategy: str | None) -> str:
    normalized = str(strategy or "").strip()
    if normalized == DEFAULT_GENERATION_STRATEGY:
        return DEFAULT_GENERATION_STRATEGY
    if normalized == "short_form_direct":
        return DEFAULT_GENERATION_STRATEGY
    if normalized in VALID_GENERATION_STRATEGIES:
        return normalized
    return DEFAULT_GENERATION_STRATEGY


def _tts_completion_actions(plan: dict[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for action in plan.get("completionActions") or []:
        if not isinstance(action, dict):
            continue
        provider = str(action.get("provider") or action.get("strategy") or "")
        if provider == "tts":
            actions.append(action)
    return actions


def infer_tts_mode_from_plan(plan: dict[str, Any]) -> str:
    tts_actions = _tts_completion_actions(plan)
    if any(str(action.get("slotId") or "") == MASTER_TTS_SLOT_ID for action in tts_actions):
        return "global"
    if tts_actions:
        return "per_scene"
    return resolve_tts_mode(plan)


def normalize_generation_plan(plan: dict[str, Any]) -> dict[str, Any]:
    """Normalize strategy and reconcile ttsMode for legacy/in-flight artifacts."""
    normalized = dict(plan)
    normalized["generationStrategy"] = normalize_generation_strategy(
        str(plan.get("generationStrategy") or "")
    )
    explicit = str(plan.get("ttsMode") or "").strip()
    if explicit in {"global", "per_scene"}:
        normalized["ttsMode"] = explicit
    else:
        normalized["ttsMode"] = infer_tts_mode_from_plan(normalized)
    return normalized
