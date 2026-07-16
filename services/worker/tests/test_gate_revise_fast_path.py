from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.pipelines.videomaker_pipeline import VideoMakerPipeline, _generation_inputs_hash


def _minimal_structure(project_id: str) -> dict[str, Any]:
    return {
        "id": "structure-1",
        "projectId": project_id,
        "sourceVideoId": "sample-1",
        "version": "p1-v3",
        "metadata": {"durationSec": 30.0},
        "narrative": {"summary": "fake", "segments": []},
        "rhythm": {
            "totalDurationSec": 30.0,
            "shotCount": 1,
            "avgShotDurationSec": 30.0,
            "tempo": "medium",
            "beatPoints": [],
            "shotBoundaries": [],
        },
        "packaging": {"visualDensity": "medium"},
        "slots": [],
        "evidence": [],
        "confidence": 0.5,
    }


def _write_gate_revise_fixture(
    tmp_path: Path,
    *,
    project_id: str = "project-1",
    generation_id: str = "gen-gate",
    slot_id: str = "slot-5",
    instruction: str = "加入金句",
) -> Path:
    generation_root = tmp_path / "projects" / project_id / "generations" / generation_id
    generation_root.mkdir(parents=True, exist_ok=True)
    inventory = {
        "id": "inventory-1",
        "projectId": project_id,
        "userBrief": {"topic": "测试"},
        "assets": [],
        "extractedFacts": [],
        "candidateMoments": [],
    }
    gap_report = {
        "id": "gap-1",
        "projectId": project_id,
        "structureId": "structure-1",
        "inventoryId": inventory["id"],
        "slotMatches": [],
        "missingSlots": [],
        "weakSlots": [],
        "summary": "ok",
    }
    plan = {
        "id": generation_id,
        "projectId": project_id,
        "structureId": "structure-1",
        "inventoryId": inventory["id"],
        "gapReportId": gap_report["id"],
        "variant": "default",
        "storyboard": [{"slotId": slot_id, "script": "test"}],
        "timeline": {"durationSec": 30.0, "tracks": [{"id": "v1", "type": "video", "clips": []}]},
        "packagingPlan": {
            "styleSummary": "fake",
            "subtitle": {},
            "titleCards": [],
            "transitions": [],
        },
        "completionActions": [
            {
                "id": f"action-{slot_id}-finish",
                "slotId": slot_id,
                "provider": "hyperframes_material",
                "finishBrief": {"compositionAuthorBrief": {"authorPrompt": "test"}},
            }
        ],
    }
    (generation_root / "asset-inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
    (generation_root / "slot-matches.json").write_text(
        json.dumps({"slotMatches": []}),
        encoding="utf-8",
    )
    (generation_root / "gap-report.json").write_text(json.dumps(gap_report), encoding="utf-8")
    (generation_root / "generation-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    (generation_root / "material-review-state.json").write_text(
        json.dumps({"status": "pending", "slots": {}}),
        encoding="utf-8",
    )
    (generation_root / "material-slot-revise-queue.json").write_text(
        json.dumps(
            {
                "generationId": generation_id,
                "slotId": slot_id,
                "instruction": instruction,
                "requestedBy": "user",
                "status": "pending",
            }
        ),
        encoding="utf-8",
    )
    user_brief = {"topic": "测试", "sellingPoints": [], "mustMention": [], "avoidMention": []}
    assets: list[dict[str, Any]] = []
    inputs_hash = _generation_inputs_hash(user_brief, assets)
    (generation_root / "checkpoint.json").write_text(
        json.dumps(
            {
                "version": "p0-v1",
                "generationId": generation_id,
                "completedStages": [
                    "analyzing_assets",
                    "mapping_slots",
                    "planning_completion",
                    "generating_material",
                ],
                "inputsHash": inputs_hash,
                "humanReviewMode": True,
                "awaitingGate": "material_review",
            }
        ),
        encoding="utf-8",
    )
    (generation_root / "script-draft.json").write_text(
        json.dumps(
            {
                "generationId": generation_id,
                "masterStatus": "approved",
                "storyboardStatus": "approved",
                "masterNarration": "test",
                "storyboard": plan["storyboard"],
                "durationTargetSec": 30.0,
            }
        ),
        encoding="utf-8",
    )
    return generation_root


def test_gate_revise_resume_skips_producing_media(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true")
    monkeypatch.setenv("VIDEOMAKER_HUMAN_REVIEW_MODE", "true")
    monkeypatch.setenv("VIDEOMAKER_FIXTURE_MODE", "true")
    project_id = "project-1"
    generation_id = "gen-gate"
    _write_gate_revise_fixture(tmp_path, project_id=project_id, generation_id=generation_id)

    pipeline = VideoMakerPipeline(tmp_path)
    events: list[dict[str, Any]] = []

    def emit(**kwargs: Any) -> dict[str, Any]:
        events.append(kwargs)
        return kwargs

    planning_called = False

    def _fake_planning(*args: Any, **kwargs: Any) -> Any:
        nonlocal planning_called
        planning_called = True
        raise AssertionError("run_planning_from_script_draft should not run on gate revise fast path")

    def _fake_generating_material(**kwargs: Any) -> tuple[dict[str, Any], list[Any]]:
        plan = kwargs["plan"]
        slot_filter = kwargs.get("slot_filter")
        assert slot_filter == {"slot-5"}
        return plan, []

    monkeypatch.setattr(
        "app.pipelines.videomaker_pipeline.run_planning_from_script_draft",
        _fake_planning,
    )
    monkeypatch.setattr(
        "app.pipelines.videomaker_pipeline.run_generating_material",
        _fake_generating_material,
    )

    user_brief = {"topic": "测试", "sellingPoints": [], "mustMention": [], "avoidMention": []}
    result = pipeline.run_generation(
        project_id=project_id,
        task_id="task-gate",
        generation_id=generation_id,
        structure=_minimal_structure(project_id),
        user_brief=user_brief,
        assets=[],
        emit=emit,
        resume=True,
        human_review_mode=True,
    )

    assert result.get("ok") is not False
    assert planning_called is False
    stages = [event.get("stage") for event in events]
    assert "producing_media" not in stages
    assert "generating_material" in stages
    assert any("(resumed) generation plan ready" in event.get("message", "") for event in events)
