from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.agents.runner import AgentRunner
from app.agents.segment_analyst import run_segment_analyst
from app.gateway.model_gateway import ModelGateway
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool


def test_segment_analyst_skips_keyframes_when_digests_cover_segment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    analysis_root = tmp_path / "analysis"
    analysis_root.mkdir()
    segment = {"id": "seg-1", "startSec": 0.0, "endSec": 20.0}
    analysis = {
        "metadata": {"durationSec": 60.0},
        "shots": [{"startSec": 0.0, "endSec": 20.0, "confidence": 0.8}],
        "keyframes": [
            {
                "shotId": "shot-0",
                "timeSec": 5.0,
                "path": "keyframes/frame-000.jpg",
                "score": 0.9,
            }
        ],
        "transcript": {"segments": [{"startSec": 0.0, "endSec": 20.0, "text": "hello"}]},
        "keyframeBatchDigests": [
            {
                "batchIndex": 0,
                "startSec": 0.0,
                "endSec": 30.0,
                "frames": [],
                "visualFacts": "talking head",
                "onScreenTextFacts": [],
            }
        ],
        "analysisDepth": "standard",
        "locale": "zh",
    }

    captured: dict[str, object] = {"keyframes": "unset"}

    def _build_messages(*, system_prompt: str, text_payload: dict, keyframes=None):
        captured["keyframes"] = keyframes
        return [{"role": "user", "content": "payload"}]

    monkeypatch.setattr(ModelGateway, "build_structure_messages", staticmethod(_build_messages))

    gateway = MagicMock(spec=ModelGateway)
    gateway.complete_json_messages.return_value = {
        "segmentId": "seg-1",
        "transcriptExcerpt": "hello",
        "rhetoricalDevices": ["陈述"],
        "emotionTone": "中性",
        "voStyle": {"pace": "适中", "energy": "中等", "persona": "讲述者"},
        "visualSpec": {
            "framing": "中景",
            "subject": "讲述者",
            "cameraMove": "静态",
            "onScreenText": [],
            "colorMood": "自然",
            "density": "medium",
        },
        "onScreenTextFacts": [],
        "localEvidence": [
            {
                "targetId": "seg-1",
                "source": "asr",
                "summary": "hello",
                "confidence": 0.8,
            }
        ],
    }

    runner = AgentRunner(
        llm=LLMTool(fixture_mode=False, gateway=gateway),
        prompt_loader=MagicMock(load=MagicMock(return_value="prompt")),
        observability_sink=MagicMock(),
        model_name="mock",
    )

    run_segment_analyst(
        runner,
        segment=segment,
        segment_analysis_seed=None,
        analysis=analysis,
        analysis_root=analysis_root,
        context=TaskContext(project_id="p1", task_id="t1", storage_root=tmp_path),
    )

    assert captured["keyframes"] is None
    assert gateway.complete_json_messages.call_args.kwargs["profile"] == "text"
