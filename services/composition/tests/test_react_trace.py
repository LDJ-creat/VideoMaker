from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from composition.author.react_agent import author_material_spec
from composition.author.react_trace import FileReactTraceRecorder
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


def test_react_trace_persists_turn_files(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_AGENT_MODE", "react")
    trace = FileReactTraceRecorder.create(
        tmp_path,
        project_id="project-1",
        task_id="task-1",
        generation_id="gen-1",
        model="test-model",
    )
    gateway = _FakeGateway(
        [
            {
                "tool_calls": [
                    {
                        "id": "call-1",
                        "name": "skill_view",
                        "arguments": {"location": "skills/public/hyperframes/SKILL.md"},
                    }
                ]
            },
            {
                "tool_calls": [
                    {
                        "id": "call-2",
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
    spec = author_material_spec(
        AuthorRequest(slot={"role": "benefit_card", "scriptIntent": "a", "visualIntent": "b"}),
        gateway,
        react_trace=trace,
    )
    assert spec["template"] == "benefit-card"
    assert (trace.trace_dir / "turn-001-response.json").is_file()
    assert (trace.trace_dir / "turn-001-tool-skill_view.json").is_file()
    assert (trace.trace_dir / "material-author-react-summary.json").is_file()
    summary = (trace.trace_dir / "material-author-react-summary.json").read_text(encoding="utf-8")
    assert "outputValid" in summary
