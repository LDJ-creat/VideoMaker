from __future__ import annotations

import json

import pytest

from composition.author.react_agent import author_material_spec
from composition.skills.usage_requirements import (
    REQUIRED_PRIVATE_SKILL_PATHS,
    REQUIRED_VISUAL_CRAFT_REFERENCE_PATHS,
    VISUAL_BIBLE_EXTRA_READ_PATHS,
)
from composition.types import AuthorRequest


def _skill_view_call(location: str, *, call_id: str) -> dict:
    return {
        "tool_calls": [
            {
                "id": call_id,
                "name": "skill_view",
                "arguments": {"location": location},
            }
        ]
    }


def _submit_call() -> dict:
    return {
        "tool_calls": [
            {
                "id": "submit-1",
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


class _SequencedGateway:
    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self.calls = 0
        self.submit_rejections = 0

    def complete_with_tools(self, messages, tools, *, task: str) -> dict:
        _ = tools, task
        self.calls += 1
        if not self._responses:
            return {"tool_calls": [], "content": None}
        response = self._responses.pop(0)
        if response.get("tool_calls"):
            first = response["tool_calls"][0]
            if first.get("name") == "submit_material_spec" and self.calls == 1:
                self.submit_rejections += 1
        return response

    def complete_json(self, task, inputs, schema_name):
        raise AssertionError("complete_json should not be called")


def test_react_rejects_submit_until_required_skill_views(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_AGENT_MODE", "react")
    reads = [
        _submit_call(),
        *[
            _skill_view_call(path, call_id=f"read-{index}")
            for index, path in enumerate(
                (
                    *REQUIRED_PRIVATE_SKILL_PATHS,
                    *REQUIRED_VISUAL_CRAFT_REFERENCE_PATHS,
                ),
                start=1,
            )
        ],
        _submit_call(),
        {"tool_calls": [], "content": None},
    ]
    gateway = _SequencedGateway(reads)
    spec = author_material_spec(
        AuthorRequest(slot={"role": "benefit_card", "scriptIntent": "a", "visualIntent": "b"}),
        gateway,
        fixture_spec=None,
    )
    assert gateway.submit_rejections >= 1
    assert spec["template"] == "benefit-card"


def test_react_with_bible_requires_palette_reference(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_AGENT_MODE", "react")
    minimum_reads = (
        *REQUIRED_PRIVATE_SKILL_PATHS,
        *REQUIRED_VISUAL_CRAFT_REFERENCE_PATHS,
    )
    reads = [
        _submit_call(),
        *[_skill_view_call(path, call_id=f"min-{index}") for index, path in enumerate(minimum_reads, start=1)],
        _submit_call(),
        _skill_view_call(VISUAL_BIBLE_EXTRA_READ_PATHS[0], call_id="palette"),
        _submit_call(),
        {"tool_calls": [], "content": None},
    ]
    gateway = _SequencedGateway(reads)
    spec = author_material_spec(
        AuthorRequest(
            slot={"role": "benefit_card", "scriptIntent": "a", "visualIntent": "b"},
            visual_style_bible={"summary": "暖色生活感"},
        ),
        gateway,
        fixture_spec=None,
    )
    assert spec["template"] == "benefit-card"
