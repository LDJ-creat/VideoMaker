from __future__ import annotations

import json
from unittest.mock import MagicMock

import pytest

from composition.author.react_agent import author_material_spec
from composition.types import AuthorRequest


class _FakeGateway:
    def __init__(self, responses: list[dict]):
        self._responses = list(responses)
        self.calls = 0

    def complete_with_tools(self, messages, tools, *, task: str) -> dict:
        _ = messages, tools, task
        self.calls += 1
        if not self._responses:
            return {"tool_calls": [], "content": None}
        return self._responses.pop(0)

    def complete_json(self, task, inputs, schema_name):
        raise AssertionError("complete_json should not be called in react test")


def test_react_requires_skill_view_before_submit(monkeypatch: pytest.MonkeyPatch) -> None:
    from composition.skills.usage_requirements import (
        REQUIRED_PRIVATE_SKILL_PATHS,
        REQUIRED_VISUAL_CRAFT_REFERENCE_PATHS,
    )

    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_AGENT_MODE", "react")
    responses: list[dict] = [
        {
            "tool_calls": [
                {
                    "id": "call-submit-early",
                    "name": "submit_material_spec",
                    "arguments": {
                        "spec_json": {
                            "template": "benefit-card",
                            "durationSec": 3,
                            "params": {"title": "x"},
                        }
                    },
                }
            ]
        }
    ]
    for index, path in enumerate(
        (*REQUIRED_PRIVATE_SKILL_PATHS, *REQUIRED_VISUAL_CRAFT_REFERENCE_PATHS),
        start=1,
    ):
        responses.append(
            {
                "tool_calls": [
                    {
                        "id": f"call-read-{index}",
                        "name": "skill_view",
                        "arguments": {"location": path},
                    }
                ]
            }
        )
    responses.extend(
        [
            {
                "tool_calls": [
                    {
                        "id": "call-submit-final",
                        "name": "submit_material_spec",
                        "arguments": {
                            "spec_json": {
                                "template": "benefit-card",
                                "durationSec": 3,
                                "params": {"title": "x"},
                            }
                        },
                    }
                ]
            },
            {"tool_calls": [], "content": None},
        ]
    )
    gateway = _FakeGateway(responses)
    spec = author_material_spec(
        AuthorRequest(slot={"role": "benefit_card", "scriptIntent": "a", "visualIntent": "b"}),
        gateway,
        fixture_spec=None,
    )
    assert gateway.calls >= 2
    assert spec["template"] == "benefit-card"


class _ExhaustedGateway:
    def __init__(self) -> None:
        self.calls = 0

    def complete_with_tools(self, messages, tools, *, task: str) -> dict:
        _ = tools, task
        self.calls += 1
        if self.calls == 1:
            user_payload = messages[1]["content"]
            assert "videoLintChecklist" in user_payload
        return {
            "tool_calls": [
                {
                    "id": "call-1",
                    "name": "skill_view",
                    "arguments": {"location": "skills/private/videomaker-composition/SKILL.md"},
                }
            ]
        }

    def complete_json(self, task, inputs, schema_name):
        raise AssertionError("complete_json should not be called in react test")


def test_react_exhausted_turns_falls_back_to_video_composition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_AGENT_MODE", "react")
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_REACT_MAX_TURNS", "1")
    gateway = _ExhaustedGateway()
    spec = author_material_spec(
        AuthorRequest(
            slot={
                "role": "hook_visual",
                "scriptIntent": "下班回家",
                "visualIntent": "刷手机",
            },
            asset_refs=[{"type": "video", "uri": "slot-1-stock.mp4"}],
        ),
        gateway,
        fixture_spec=None,
        hyperframes_cli=MagicMock(),
    )
    assert spec["template"] == "composition"
    assert 'id="base-video"' in spec["composition"]["bodyHtml"]
