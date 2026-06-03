from __future__ import annotations

import json
import hashlib
from pathlib import Path
from typing import Any

import pytest

from app.pipelines.p0_demo_pipeline import P0DemoPipeline
from app.pipelines.revise_pipeline import seed_revise_generation
from app.pipelines.intent_applier import apply_intents_to_context
from app.tools.llm_tool import LLMTool, load_agent_fixtures


def _load_structure_fixture() -> dict[str, Any]:
    fixture_path = Path(__file__).parent / "fixtures" / "structures" / "sample-structure.json"
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _write_completed_generation(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
    variant: str = "high_click",
) -> dict[str, Any]:
    generation_root = storage_root / "projects" / project_id / "generations" / generation_id
    generation_root.mkdir(parents=True, exist_ok=True)
    plan = {
        "id": generation_id,
        "projectId": project_id,
        "structureId": "video-structure-project-1",
        "inventoryId": "inventory-project-1",
        "gapReportId": "gap-project-1",
        "variant": variant,
        "masterNarration": "s",
        "storyboard": [{"id": "scene-1", "slotId": "slot-1", "startSec": 0, "endSec": 3, "visual": "v", "script": "s", "source": "user_asset"}],
        "timeline": {"durationSec": 10.0, "tracks": [{"id": "v1", "type": "video", "clips": []}]},
        "packagingPlan": {
            "styleSummary": "demo",
            "subtitle": {"density": "medium"},
            "titleCards": [],
            "transitions": [],
        },
        "completionActions": [],
    }
    inventory = {
        "id": "inventory-project-1",
        "projectId": project_id,
        "userBrief": {"topic": "果汁机", "sellingPoints": ["便携"], "mustMention": [], "avoidMention": []},
        "assets": [
            {
                "id": "asset-1",
                "type": "text",
                "uri": "storage://caption.txt",
                "description": "caption",
                "tags": ["卖点"],
            }
        ],
        "extractedFacts": [],
        "candidateMoments": [],
    }
    gap_report = {
        "id": "gap-project-1",
        "projectId": project_id,
        "structureId": plan["structureId"],
        "inventoryId": inventory["id"],
        "slotMatches": [],
        "missingSlots": [],
        "weakSlots": [],
        "summary": "ok",
    }
    (generation_root / "generation-plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    (generation_root / "asset-inventory.json").write_text(json.dumps(inventory, indent=2), encoding="utf-8")
    (generation_root / "gap-report.json").write_text(json.dumps(gap_report, indent=2), encoding="utf-8")
    (generation_root / "slot-matches.json").write_text(
        json.dumps({"slotMatches": []}, indent=2),
        encoding="utf-8",
    )
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
                    "rendering",
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return plan


def test_seed_revise_generation_copies_source_and_writes_edit_intent(tmp_path: Path) -> None:
    project_id = "project-1"
    source_id = "gen-source"
    target_id = "gen-target"
    _write_completed_generation(tmp_path, project_id=project_id, generation_id=source_id)
    source_bytes = (tmp_path / "projects" / project_id / "generations" / source_id / "generation-plan.json").read_bytes()

    intents = [
        {
            "target": "generation_plan.packaging",
            "operation": "reduce_subtitles",
            "params": {},
            "rationale": "less subtitles",
        }
    ]
    context = apply_intents_to_context(intents, source_plan={}, source_timeline={})
    seed_revise_generation(
        project_root=tmp_path / "projects" / project_id,
        source_generation_id=source_id,
        target_generation_id=target_id,
        intents=intents,
        revise_context=context,
    )

    source_after = (
        tmp_path / "projects" / project_id / "generations" / source_id / "generation-plan.json"
    ).read_bytes()
    assert source_after == source_bytes

    target_root = tmp_path / "projects" / project_id / "generations" / target_id
    edit_intent = json.loads((target_root / "edit-intent.json").read_text(encoding="utf-8"))
    assert edit_intent["intents"] == intents
    checkpoint = json.loads((target_root / "checkpoint.json").read_text(encoding="utf-8"))
    assert checkpoint["completedStages"] == ["analyzing_assets", "mapping_slots"]


def test_run_revise_reexecutes_storyboard_and_packaging_stages(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_render_material(self, spec, **kwargs):  # noqa: ANN001
        output_clip = kwargs["output_clip"]
        output_clip.parent.mkdir(parents=True, exist_ok=True)
        output_clip.write_bytes(b"mock-mp4")
        return {
            "ok": True,
            "artifactPath": str(output_clip),
            "durationSec": float(spec.get("durationSec", 3)),
        }

    monkeypatch.setattr(
        "app.tools.hyperframes_material_tool.HyperFramesMaterialTool.render_material",
        _fake_render_material,
    )

    project_id = "project-1"
    source_id = "gen-source"
    target_id = "gen-target"
    _write_completed_generation(tmp_path, project_id=project_id, generation_id=source_id)
    source_hash = hashlib.sha256(
        (tmp_path / "projects" / project_id / "generations" / source_id / "generation-plan.json").read_bytes()
    ).hexdigest()

    fixtures = load_agent_fixtures(Path(__file__).parent / "fixtures" / "agents")
    pipeline = P0DemoPipeline(tmp_path, llm=LLMTool(fixture_mode=True, fixtures=fixtures))
    events: list[dict[str, Any]] = []

    def emit(**kwargs: Any) -> dict[str, Any]:
        events.append(kwargs)
        return kwargs

    structure = _load_structure_fixture()
    result = pipeline.run_revise(
        project_id=project_id,
        task_id="task-revise",
        source_generation_id=source_id,
        generation_id=target_id,
        instruction="开头更抓人一些，字幕少一点",
        structure=structure,
        user_brief={"topic": "果汁机", "sellingPoints": ["便携"], "mustMention": [], "avoidMention": []},
        assets=[
            {
                "id": "asset-1",
                "type": "text",
                "uri": "storage://caption.txt",
                "description": "caption",
                "tags": ["卖点"],
            }
        ],
        emit=emit,
        intents=[
            {
                "target": "generation_plan.storyboard",
                "operation": "adjust_hook",
                "params": {"strength": "high"},
                "rationale": "用户希望开头更抓人",
            },
            {
                "target": "generation_plan.packaging",
                "operation": "reduce_subtitles",
                "params": {},
                "rationale": "用户希望减少字幕",
            },
        ],
    )

    assert result["ok"] is True
    assert result["sourceGenerationId"] == source_id
    assert len(result["intents"]) == 2

    stages = [event["stage"] for event in events]
    assert "parsing_edit_intent" in stages
    assert "applying_edit_intent" in stages
    assert "mapping_slots" in stages
    assert "planning_completion" in stages

    source_hash_after = hashlib.sha256(
        (tmp_path / "projects" / project_id / "generations" / source_id / "generation-plan.json").read_bytes()
    ).hexdigest()
    assert source_hash_after == source_hash

    target_plan_path = tmp_path / "projects" / project_id / "generations" / target_id / "generation-plan.json"
    assert target_plan_path.is_file()
    assert target_id != source_id
