from __future__ import annotations

import pytest

from app.pipelines.generation_strategy import (
    infer_tts_mode_from_plan,
    normalize_generation_plan,
    normalize_generation_strategy,
    resolve_generation_strategy,
)


def test_resolve_generation_strategy_always_long_form() -> None:
    assert resolve_generation_strategy(30) == "long_form_composed"
    assert resolve_generation_strategy(60) == "long_form_composed"
    assert resolve_generation_strategy(120) == "long_form_composed"
    assert resolve_generation_strategy(None) == "long_form_composed"


def test_normalize_generation_strategy_maps_legacy_short_form() -> None:
    assert normalize_generation_strategy("short_form_direct") == "long_form_composed"
    assert normalize_generation_strategy("long_form_composed") == "long_form_composed"
    assert normalize_generation_strategy(None) == "long_form_composed"
    assert normalize_generation_strategy("") == "long_form_composed"


def test_normalize_generation_strategy_falls_back_for_unknown_values() -> None:
    assert normalize_generation_strategy("foo") == "long_form_composed"
    assert normalize_generation_strategy("legacy_mode") == "long_form_composed"


def test_normalize_generation_plan_coerces_legacy_plans_to_global() -> None:
    plan = {
        "generationStrategy": "short_form_direct",
        "completionActions": [
            {
                "id": "action-slot-a-tts",
                "slotId": "slot-a",
                "provider": "tts",
                "strategy": "tts",
            }
        ],
        "masterNarration": "hello",
    }
    normalized = normalize_generation_plan(plan)
    assert normalized["generationStrategy"] == "long_form_composed"
    assert normalized["ttsMode"] == "global"
    assert infer_tts_mode_from_plan(normalized) == "global"


def test_normalize_generation_plan_always_global() -> None:
    plan = {
        "generationStrategy": "short_form_direct",
        "ttsMode": "per_scene",
        "completionActions": [
            {
                "id": "action-slot-a-tts",
                "slotId": "slot-a",
                "provider": "tts",
            }
        ],
    }
    normalized = normalize_generation_plan(plan)
    assert normalized["generationStrategy"] == "long_form_composed"
    assert normalized["ttsMode"] == "global"


def test_normalize_generation_plan_defaults_global_for_new_style_plan() -> None:
    plan = {
        "generationStrategy": "long_form_composed",
        "masterNarration": "全片口播",
        "completionActions": [
            {
                "id": "action-master-tts",
                "slotId": "__master__",
                "provider": "tts",
            }
        ],
    }
    normalized = normalize_generation_plan(plan)
    assert normalized["ttsMode"] == "global"
