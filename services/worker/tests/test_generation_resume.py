from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.pipelines.p0_demo_pipeline import P0DemoPipeline, _generation_inputs_hash


def test_run_generation_resume_skips_inventory_and_planning(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_FIXTURE_MODE", "true")
    project_id = "project-1"
    generation_id = "gen-1"
    generation_root = tmp_path / "projects" / project_id / "generations" / generation_id
    generation_root.mkdir(parents=True, exist_ok=True)

    inventory = {
        "id": "inventory-1",
        "projectId": project_id,
        "userBrief": {"topic": "果汁机"},
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
        "storyboard": [],
        "timeline": {"durationSec": 10.0, "tracks": [{"id": "v1", "type": "video", "clips": []}]},
        "packagingPlan": {
            "styleSummary": "fake",
            "subtitle": {},
            "titleCards": [],
            "transitions": [],
        },
        "completionActions": [],
    }
    (generation_root / "asset-inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
    (generation_root / "slot-matches.json").write_text(
        json.dumps({"slotMatches": []}),
        encoding="utf-8",
    )
    (generation_root / "gap-report.json").write_text(json.dumps(gap_report), encoding="utf-8")
    (generation_root / "generation-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    user_brief = {"topic": "果汁机", "sellingPoints": ["便携"], "mustMention": [], "avoidMention": []}
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
                    "building_timeline",
                ],
                "inputsHash": inputs_hash,
            }
        ),
        encoding="utf-8",
    )

    render_root = tmp_path / "projects" / project_id / "renders" / generation_id
    render_root.mkdir(parents=True, exist_ok=True)
    (render_root / "preview.html").write_text("<html></html>", encoding="utf-8")

    pipeline = P0DemoPipeline(tmp_path)
    events: list[dict[str, Any]] = []

    def emit(**kwargs: Any) -> dict[str, Any]:
        events.append(kwargs)
        return kwargs

    structure = {
        "id": "structure-1",
        "projectId": project_id,
        "sourceVideoId": "sample-1",
        "version": "p0-v1",
        "metadata": {"durationSec": 10.0},
        "narrative": {"summary": "fake", "segments": []},
        "rhythm": {
            "totalDurationSec": 10.0,
            "shotCount": 1,
            "avgShotDurationSec": 10.0,
            "tempo": "medium",
            "beatPoints": [],
            "shotBoundaries": [],
        },
        "packaging": {"visualDensity": "medium"},
        "slots": [],
        "evidence": [],
        "confidence": 0.5,
    }

    result = pipeline.run_generation(
        project_id=project_id,
        task_id="task-gen",
        generation_id=generation_id,
        structure=structure,
        user_brief=user_brief,
        assets=assets,
        emit=emit,
        resume=True,
    )

    assert result["ok"] is True
    resumed_messages = [event["message"] for event in events if "(resumed)" in event["message"]]
    assert any("asset inventory" in message for message in resumed_messages)
    assert any("generation plan" in message for message in resumed_messages)
    assert events[-1]["status"] == "succeeded"


def test_run_generation_resume_normalizes_legacy_short_form_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_FIXTURE_MODE", "true")
    project_id = "project-1"
    generation_id = "gen-legacy"
    generation_root = tmp_path / "projects" / project_id / "generations" / generation_id
    generation_root.mkdir(parents=True, exist_ok=True)

    inventory = {
        "id": "inventory-1",
        "projectId": project_id,
        "userBrief": {"topic": "果汁机"},
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
        "generationStrategy": "short_form_direct",
        "masterNarration": "legacy narration",
        "storyboard": [
            {
                "id": "scene-1",
                "slotId": "slot-a",
                "startSec": 0.0,
                "endSec": 5.0,
                "visual": "v",
                "script": "hello",
                "source": "generated",
            }
        ],
        "timeline": {"durationSec": 5.0, "tracks": [{"id": "v1", "type": "video", "clips": []}]},
        "packagingPlan": {
            "styleSummary": "fake",
            "subtitle": {},
            "titleCards": [],
            "transitions": [],
        },
        "completionActions": [
            {
                "id": "action-slot-a-tts",
                "slotId": "slot-a",
                "provider": "tts",
                "strategy": "tts",
                "outputRef": "completion://slot-a/tts",
            }
        ],
    }
    generated_root = generation_root / "generated"
    generated_root.mkdir(parents=True, exist_ok=True)
    (generated_root / "slot-a.wav").write_bytes(b"RIFF----WAVE")
    (generation_root / "asset-inventory.json").write_text(json.dumps(inventory), encoding="utf-8")
    (generation_root / "slot-matches.json").write_text(
        json.dumps({"slotMatches": []}),
        encoding="utf-8",
    )
    (generation_root / "gap-report.json").write_text(json.dumps(gap_report), encoding="utf-8")
    (generation_root / "generation-plan.json").write_text(json.dumps(plan), encoding="utf-8")
    user_brief = {"topic": "果汁机", "sellingPoints": ["便携"], "mustMention": [], "avoidMention": []}
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
                    "building_timeline",
                ],
                "inputsHash": inputs_hash,
            }
        ),
        encoding="utf-8",
    )

    render_root = tmp_path / "projects" / project_id / "renders" / generation_id
    render_root.mkdir(parents=True, exist_ok=True)
    (render_root / "preview.html").write_text("<html></html>", encoding="utf-8")

    pipeline = P0DemoPipeline(tmp_path)
    events: list[dict[str, Any]] = []

    def emit(**kwargs: Any) -> dict[str, Any]:
        events.append(kwargs)
        return kwargs

    structure = {
        "id": "structure-1",
        "projectId": project_id,
        "sourceVideoId": "sample-1",
        "version": "p0-v1",
        "metadata": {"durationSec": 10.0},
        "narrative": {"summary": "fake", "segments": []},
        "rhythm": {
            "totalDurationSec": 10.0,
            "shotCount": 1,
            "avgShotDurationSec": 10.0,
            "tempo": "medium",
            "beatPoints": [],
            "shotBoundaries": [],
        },
        "packaging": {"visualDensity": "medium"},
        "slots": [],
        "evidence": [],
        "confidence": 0.5,
    }

    result = pipeline.run_generation(
        project_id=project_id,
        task_id="task-gen-legacy",
        generation_id=generation_id,
        structure=structure,
        user_brief=user_brief,
        assets=assets,
        emit=emit,
        resume=True,
    )

    assert result["ok"] is True
    persisted = json.loads((generation_root / "generation-plan.json").read_text(encoding="utf-8"))
    assert persisted["generationStrategy"] == "long_form_composed"
    assert persisted["ttsMode"] == "per_scene"
    assert persisted["completionActions"][0]["slotId"] == "slot-a"
