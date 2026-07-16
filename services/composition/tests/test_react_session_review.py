"""Author-session review orchestration for ReAct."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest

from composition.author.react_agent import author_material_spec
from composition.types import AuthorRequest


class _SubmitGateway:
    """First turn: submit a minimal valid composition-like benefit-card via tools."""

    def __init__(self) -> None:
        self.calls = 0
        self.messages_history: list[list[dict]] = []

    def complete_with_tools(self, messages, tools, *, task: str) -> dict:
        _ = tools, task
        self.calls += 1
        self.messages_history.append([dict(m) for m in messages])
        if self.calls == 1:
            return {
                "tool_calls": [
                    {
                        "id": "call-read",
                        "name": "skill_view",
                        "arguments": {
                            "location": "skills/private/videomaker-composition/SKILL.md"
                        },
                    }
                ]
            }
        # After skills required — tests monkeypatch requirement to empty
        return {
            "tool_calls": [
                {
                    "id": "call-submit",
                    "name": "submit_material_spec",
                    "arguments": {
                        "spec_json": {
                            "template": "benefit-card",
                            "durationSec": 3.5,
                            "params": {"title": "测试标题", "bullets": []},
                        }
                    },
                }
            ]
        }

    def complete_json(self, task, inputs, schema_name):
        raise AssertionError("complete_json should not be called")


def test_react_session_review_approved_returns_spec(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_AGENT_MODE", "react")
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_REACT_IN_SESSION", "true")
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_MAX_ROUNDS", "1")
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_REQUIRE_BEFORE_SUBMIT", "false")
    monkeypatch.setattr(
        "composition.author.react_agent.skill_view_requirement_error",
        lambda *a, **k: None,
    )

    gen_root = tmp_path / "generations" / "g1"
    gen_root.mkdir(parents=True)
    scratch = gen_root / "react-author" / "slot-4"

    def _fake_review(**kwargs):
        from composition.author.react_review import ReactSessionReviewResult
        from composition.material_review.session import write_review_marker

        write_review_marker(
            kwargs["scratch_dir"],
            spec=kwargs["spec"],
            report={"approved": True, "issues": [], "suggestions": []},
        )
        return ReactSessionReviewResult(
            approved=True,
            report={"approved": True, "issues": [], "suggestions": []},
            vision_billed=True,
        )

    monkeypatch.setattr(
        "composition.author.react_agent.run_react_session_review",
        _fake_review,
    )
    # skip real skill file reads
    monkeypatch.setattr(
        "composition.author.tools.SkillRuntime.skill_view",
        lambda self, location, section=None: "# skill",
    )

    gateway = _SubmitGateway()
    # Need enough skill views then submit — simplify gateway to submit on call 1
    class _OneShotSubmit(_SubmitGateway):
        def complete_with_tools(self, messages, tools, *, task: str) -> dict:
            self.calls += 1
            self.messages_history.append([dict(m) for m in messages])
            return {
                "tool_calls": [
                    {
                        "id": "call-submit",
                        "name": "submit_material_spec",
                        "arguments": {
                            "spec_json": {
                                "template": "benefit-card",
                                "durationSec": 3.5,
                                "params": {"title": "测试标题", "bullets": []},
                            }
                        },
                    }
                ]
            }

    gateway = _OneShotSubmit()
    spec = author_material_spec(
        AuthorRequest(
            slot={"id": "slot-4", "role": "proof", "scriptIntent": "a", "visualIntent": "b"},
            generation_id="g1",
            generation_root=gen_root,
            slot_timing={"durationSec": 3.5, "startSec": 0, "endSec": 3.5},
        ),
        gateway,
        lint_scratch_dir=scratch,
        hyperframes_cli=MagicMock(),
    )
    assert spec["template"] == "benefit-card"
    assert float(spec["durationSec"]) == 3.5
    assert (scratch / "material-review-marker.json").is_file()
    marker = json.loads((scratch / "material-review-marker.json").read_text(encoding="utf-8"))
    assert marker.get("approved") is True


def test_react_session_review_reject_then_repair(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_AGENT_MODE", "react")
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_REACT_IN_SESSION", "true")
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_MAX_ROUNDS", "2")
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_REPAIR_FOLLOWUP_MAX", "1")
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_REQUIRE_BEFORE_SUBMIT", "false")
    monkeypatch.setattr(
        "composition.author.react_agent.skill_view_requirement_error",
        lambda *a, **k: None,
    )
    monkeypatch.setattr(
        "composition.author.tools.SkillRuntime.skill_view",
        lambda self, location, section=None: "# skill",
    )

    gen_root = tmp_path / "generations" / "g1"
    gen_root.mkdir(parents=True)
    scratch = gen_root / "react-author" / "slot-4"
    review_calls = {"n": 0}

    def _fake_review(**kwargs):
        from composition.author.react_review import ReactSessionReviewResult
        from composition.material_review.session import write_review_marker

        review_calls["n"] += 1
        approved = review_calls["n"] >= 2
        report = {
            "approved": approved,
            "issues": [] if approved else ["text overflow"],
            "suggestions": [] if approved else ["widen container"],
        }
        write_review_marker(kwargs["scratch_dir"], spec=kwargs["spec"], report=report)
        return ReactSessionReviewResult(
            approved=approved,
            report=report,
            vision_billed=True,
            repair_feedback=None if approved else "Apply these review fixes: widen container",
        )

    monkeypatch.setattr(
        "composition.author.react_agent.run_react_session_review",
        _fake_review,
    )

    class _TwoSubmitGateway:
        def __init__(self) -> None:
            self.calls = 0
            self.saw_repair = False

        def complete_with_tools(self, messages, tools, *, task: str) -> dict:
            self.calls += 1
            for m in messages:
                if m.get("role") == "user" and "repairFeedback" in str(m.get("content")):
                    self.saw_repair = True
            return {
                "tool_calls": [
                    {
                        "id": f"submit-{self.calls}",
                        "name": "submit_material_spec",
                        "arguments": {
                            "spec_json": {
                                "template": "benefit-card",
                                "durationSec": 4.0,
                                "params": {
                                    "title": "fixed" if self.calls > 1 else "broken",
                                    "bullets": [],
                                },
                            }
                        },
                    }
                ]
            }

        def complete_json(self, task, inputs, schema_name):
            raise AssertionError("no complete_json")

    gateway = _TwoSubmitGateway()
    spec = author_material_spec(
        AuthorRequest(
            slot={"id": "slot-4", "role": "proof"},
            generation_root=gen_root,
            slot_timing={"durationSec": 4.0},
        ),
        gateway,
        lint_scratch_dir=scratch,
        hyperframes_cli=MagicMock(),
    )
    assert gateway.saw_repair is True
    assert review_calls["n"] == 2
    assert spec["params"]["title"] == "fixed"
