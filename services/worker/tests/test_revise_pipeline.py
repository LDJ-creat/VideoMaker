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
                "humanReviewMode": False,
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
    assert checkpoint["completedStages"] == [
        "analyzing_assets",
        "mapping_slots",
        "drafting_master_script",
        "drafting_storyboard",
    ]


def test_seed_revise_preserves_gap_report_when_restarting_from_planning_completion(
    tmp_path: Path,
) -> None:
    project_id = "project-1"
    source_id = "gen-source"
    target_id = "gen-target"
    _write_completed_generation(tmp_path, project_id=project_id, generation_id=source_id)

    intents = [
        {
            "target": "generation_plan.packaging",
            "operation": "change_packaging_style",
            "params": {"style": "solid dark background"},
            "rationale": "用户希望调整包装风格",
            "executionTool": "packaging_agent",
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

    target_root = tmp_path / "projects" / project_id / "generations" / target_id
    assert (target_root / "gap-report.json").is_file()
    assert not (target_root / "generation-plan.json").is_file()
    checkpoint = json.loads((target_root / "checkpoint.json").read_text(encoding="utf-8"))
    assert "mapping_slots" in checkpoint["completedStages"]
    assert "planning_completion" not in checkpoint["completedStages"]


def test_seed_revise_preserves_generated_for_packaging_only_fork(tmp_path: Path) -> None:
    project_id = "project-1"
    source_id = "gen-source"
    target_id = "gen-target"
    _write_completed_generation(tmp_path, project_id=project_id, generation_id=source_id)
    source_root = tmp_path / "projects" / project_id / "generations" / source_id
    generated_root = source_root / "generated"
    generated_root.mkdir(parents=True, exist_ok=True)
    marker = generated_root / "slot-1.png"
    marker.write_bytes(b"png")

    intents = [
        {
            "target": "generation_plan.packaging",
            "operation": "change_packaging_style",
            "params": {"style": "minimal"},
            "rationale": "全片包装",
            "executionTool": "packaging_agent",
        }
    ]
    context = apply_intents_to_context(
        intents,
        source_plan=json.loads((source_root / "generation-plan.json").read_text(encoding="utf-8")),
    )
    assert context.material_scope == "none"
    seed_revise_generation(
        project_root=tmp_path / "projects" / project_id,
        source_generation_id=source_id,
        target_generation_id=target_id,
        intents=intents,
        revise_context=context,
    )

    target_generated = tmp_path / "projects" / project_id / "generations" / target_id / "generated"
    assert marker.name in {path.name for path in target_generated.iterdir()}
    assert not (tmp_path / "projects" / project_id / "generations" / target_id / "generation-plan.json").is_file()


def test_seed_revise_generation_disables_human_review(tmp_path: Path) -> None:
    project_id = "project-1"
    source_id = "gen-source"
    target_id = "gen-target"
    _write_completed_generation(tmp_path, project_id=project_id, generation_id=source_id)
    source_root = tmp_path / "projects" / project_id / "generations" / source_id
    checkpoint_path = source_root / "checkpoint.json"
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    checkpoint["humanReviewMode"] = True
    checkpoint_path.write_text(json.dumps(checkpoint, indent=2), encoding="utf-8")

    intents = [
        {
            "target": "generation_plan.storyboard",
            "operation": "adjust_hook",
            "params": {"strength": "high"},
            "rationale": "hook",
        }
    ]
    context = apply_intents_to_context(
        intents,
        source_plan=json.loads((source_root / "generation-plan.json").read_text(encoding="utf-8")),
    )
    seed_revise_generation(
        project_root=tmp_path / "projects" / project_id,
        source_generation_id=source_id,
        target_generation_id=target_id,
        intents=intents,
        revise_context=context,
    )

    target_checkpoint = json.loads(
        (
            tmp_path / "projects" / project_id / "generations" / target_id / "checkpoint.json"
        ).read_text(encoding="utf-8")
    )
    assert target_checkpoint["humanReviewMode"] is False


def test_mapping_slots_skip_requires_gap_report_artifact(tmp_path: Path) -> None:
    from app.runtime.checkpoint import GenerationCheckpoint, should_skip_mapping_slots_resumable

    generation_root = tmp_path / "gen"
    generation_root.mkdir()
    (generation_root / "slot-matches.json").write_text('{"slotMatches": []}', encoding="utf-8")
    checkpoint = GenerationCheckpoint(
        version="p0-v1",
        generationId="gen-1",
        completedStages=["mapping_slots"],
    )
    assert should_skip_mapping_slots_resumable(
        checkpoint,
        generation_root,
        resume=True,
    ) is False

    (generation_root / "gap-report.json").write_text('{"id": "gap-1"}', encoding="utf-8")
    assert should_skip_mapping_slots_resumable(
        checkpoint,
        generation_root,
        resume=True,
    ) is True


def _mock_successful_render(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.render.backend import RenderOutput, RenderOptions

    class _FakeRenderBackend:
        def render(self, options: RenderOptions) -> RenderOutput:
            render_root = (
                options.storage_root
                / "projects"
                / options.project_id
                / "generations"
                / options.generation_id
                / "renders"
            )
            render_root.mkdir(parents=True, exist_ok=True)
            output_path = render_root / "preview.mp4"
            output_path.write_bytes(b"mock-mp4")
            return RenderOutput(artifact_refs=[{"type": "video", "uri": str(output_path)}])

    monkeypatch.setattr(
        "app.pipelines.p0_demo_pipeline.build_render_backend",
        lambda *args, **kwargs: _FakeRenderBackend(),
    )


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
    monkeypatch.setattr(
        "app.pipelines.p0_demo_pipeline.run_generating_material",
        lambda **kwargs: (kwargs["plan"], []),
    )
    _mock_successful_render(monkeypatch)

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


def test_seed_revise_scoped_persists_invalidated_plan(tmp_path: Path) -> None:
    project_id = "project-1"
    source_id = "gen-source"
    target_id = "gen-target"
    _write_completed_generation(tmp_path, project_id=project_id, generation_id=source_id)
    source_root = tmp_path / "projects" / project_id / "generations" / source_id
    plan = json.loads((source_root / "generation-plan.json").read_text(encoding="utf-8"))
    plan["completionActions"] = [
        {
            "id": "action-slot-1",
            "slotId": "slot-1",
            "provider": "hyperframes_material",
            "artifactRef": {"uri": "generated/slot-1.mp4"},
        },
        {
            "id": "action-slot-6",
            "slotId": "slot-6",
            "provider": "hyperframes_material",
            "artifactRef": {"uri": "generated/slot-6.mp4"},
        },
    ]
    (source_root / "generation-plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")
    generated_root = source_root / "generated"
    generated_root.mkdir(parents=True, exist_ok=True)
    (generated_root / "action-slot-1.mp4").write_bytes(b"keep")
    (generated_root / "action-slot-6.mp4").write_bytes(b"drop")

    intents = [
        {
            "target": "generation_plan.storyboard",
            "operation": "change_packaging_style",
            "params": {"requiresMaterialRegen": True, "sceneId": "scene-6", "slotId": "slot-6"},
            "rationale": "单镜重生成",
            "executionTool": "material_regen",
            "sceneIds": ["scene-6"],
            "slotIds": ["slot-6"],
        }
    ]
    context = apply_intents_to_context(intents, source_plan=plan)
    seed_revise_generation(
        project_root=tmp_path / "projects" / project_id,
        source_generation_id=source_id,
        target_generation_id=target_id,
        intents=intents,
        revise_context=context,
    )

    target_plan_path = tmp_path / "projects" / project_id / "generations" / target_id / "generation-plan.json"
    assert target_plan_path.is_file()
    target_plan = json.loads(target_plan_path.read_text(encoding="utf-8"))
    actions_by_slot = {str(item.get("slotId")): item for item in target_plan.get("completionActions", [])}
    assert "artifactRef" in actions_by_slot["slot-1"]
    assert "artifactRef" not in actions_by_slot["slot-6"]
    assert not (tmp_path / "projects" / project_id / "generations" / target_id / "generated" / "action-slot-6.mp4").is_file()
    assert (tmp_path / "projects" / project_id / "generations" / target_id / "generated" / "action-slot-1.mp4").is_file()


def test_packaging_only_material_scope_skips_regen_when_actions_satisfied(tmp_path: Path) -> None:
    from app.pipelines.generation_pipeline import is_material_stage_done

    project_id = "project-1"
    source_id = "gen-source"
    plan = _write_completed_generation(tmp_path, project_id=project_id, generation_id=source_id)
    generation_root = tmp_path / "projects" / project_id / "generations" / source_id
    intents = [
        {
            "target": "generation_plan.packaging",
            "operation": "change_packaging_style",
            "params": {"style": "minimal"},
            "rationale": "全片包装",
            "executionTool": "packaging_agent",
        }
    ]
    context = apply_intents_to_context(intents, source_plan=plan)
    assert context.material_scope == "none"
    assert is_material_stage_done(generation_root, plan) is True
    slot_filter = set(context.affected_slot_ids) if context.material_scope == "scoped" else None
    assert slot_filter is None
