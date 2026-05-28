from __future__ import annotations

import pytest

from app.tools.llm_tool import LLMTool, LLMToolConfigError, LLMToolValidationError


def test_llm_tool_fixture_mode_returns_validated_payload() -> None:
    tool = LLMTool(
        fixture_mode=True,
        fixtures={
            "structure": {
                "id": "v1",
                "projectId": "project-1",
                "sourceVideoId": "source-1",
                "version": "p0",
                "metadata": {"durationSec": 10},
                "narrative": {"summary": "ok", "segments": []},
                "rhythm": {
                    "totalDurationSec": 10,
                    "shotCount": 0,
                    "avgShotDurationSec": 0,
                    "tempo": "slow",
                    "beatPoints": [],
                    "shotBoundaries": []
                },
                "packaging": {
                    "titleCards": [],
                    "stickers": [],
                    "transitions": [],
                    "visualDensity": "low"
                },
                "slots": [],
                "evidence": [],
                "confidence": 0.8
            }
        },
    )

    output = tool.generate_json(
        task="structure",
        inputs={"sample": "fixture"},
        schema_name="video-structure",
    )
    assert output["id"] == "v1"
    assert tool.last_raw_output is not None


def test_llm_tool_raises_when_api_mode_without_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    tool = LLMTool(fixture_mode=False)
    with pytest.raises(LLMToolConfigError):
        tool.generate_json(task="anything", inputs={}, schema_name="video-structure")


def test_llm_tool_reports_validation_error_in_fixture_mode() -> None:
    tool = LLMTool(
        fixture_mode=True,
        fixtures={"bad-task": {"id": "bad-only-id"}},
    )
    with pytest.raises(LLMToolValidationError) as exc_info:
        tool.generate_json(task="bad-task", inputs={}, schema_name="video-structure")

    assert exc_info.value.validation_errors
    assert exc_info.value.raw_output is not None

