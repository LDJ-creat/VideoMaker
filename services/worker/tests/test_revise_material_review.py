from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.pipelines.intent_applier import ReviseContext, apply_intents_to_context
from app.pipelines.material_review import (
    material_review_on_revise_enabled,
    use_material_review_gate,
)
from app.pipelines.material_review_revise import (
    load_material_review_revise_context,
    reset_material_review_for_revise_fork,
)
from app.pipelines.revise_pipeline import is_revise_generation, seed_revise_generation


def test_use_material_review_gate_first_generation_requires_human_review(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true")
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ON_REVISE", "true")
    assert use_material_review_gate(human_review=True, revise_context=None) is True
    assert use_material_review_gate(human_review=False, revise_context=None) is False


def test_use_material_review_gate_revise_fork_material_regen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true")
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ON_REVISE", "true")
    ctx = ReviseContext(
        material_scope="scoped",
        affected_slot_ids=["slot-6"],
        affected_pipeline_stages=["generating_material", "building_timeline", "rendering"],
    )
    assert use_material_review_gate(human_review=False, revise_context=ctx) is True


def test_use_material_review_gate_revise_packaging_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true")
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ON_REVISE", "true")
    ctx = ReviseContext(
        material_scope="none",
        affected_pipeline_stages=["planning_completion", "building_timeline", "rendering"],
    )
    assert use_material_review_gate(human_review=False, revise_context=ctx) is False


def test_use_material_review_gate_revise_disabled_by_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true")
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ON_REVISE", "false")
    ctx = ReviseContext(
        material_scope="scoped",
        affected_slot_ids=["slot-1"],
        affected_pipeline_stages=["generating_material", "rendering"],
    )
    assert use_material_review_gate(human_review=False, revise_context=ctx) is False
    assert material_review_on_revise_enabled() is False


def test_material_review_revise_context_payload_skips_when_on_revise_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true")
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ON_REVISE", "false")
    from app.pipelines.material_review_revise import material_review_revise_context_payload

    ctx = ReviseContext(
        material_scope="scoped",
        affected_slot_ids=["slot-6"],
        affected_pipeline_stages=["generating_material", "rendering"],
    )
    assert material_review_revise_context_payload(
        source_generation_id="gen-src",
        revise_context=ctx,
    ) == {}


def test_reset_material_review_for_revise_fork_scoped(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen-target"
    generation_root.mkdir(parents=True)
    state = {
        "generationId": "gen-target",
        "projectId": "proj-1",
        "variant": "high_click",
        "status": "approved",
        "humanOverride": True,
        "overriddenSlotIds": ["slot-6"],
        "slots": {
            "slot-1": {
                "status": "agent_passed",
                "latestReportUri": "material-reviews/slot-1/report.json",
            },
            "slot-6": {
                "status": "agent_passed",
                "latestReportUri": "material-reviews/slot-6/report.json",
            },
        },
    }
    (generation_root / "material-review-state.json").write_text(
        json.dumps(state, indent=2),
        encoding="utf-8",
    )
    for slot_id in ("slot-1", "slot-6"):
        report_dir = generation_root / "material-reviews" / slot_id
        report_dir.mkdir(parents=True)
        (report_dir / "report.json").write_text('{"approved": true}', encoding="utf-8")

    reset_material_review_for_revise_fork(generation_root, {"slot-6"})

    updated = json.loads((generation_root / "material-review-state.json").read_text(encoding="utf-8"))
    assert updated["status"] == "draft"
    assert "humanOverride" not in updated
    assert "overriddenSlotIds" not in updated
    assert updated["slots"]["slot-1"]["status"] == "agent_passed"
    assert updated["slots"]["slot-1"]["latestReportUri"] == "material-reviews/slot-1/report.json"
    assert updated["slots"]["slot-6"]["status"] == "pending"
    assert "latestReportUri" not in updated["slots"]["slot-6"]
    assert not (generation_root / "material-reviews" / "slot-6").exists()
    assert (generation_root / "material-reviews" / "slot-1" / "report.json").is_file()


def test_reset_material_review_for_revise_fork_full_reset(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen-target"
    generation_root.mkdir(parents=True)
    state = {
        "generationId": "gen-target",
        "projectId": "proj-1",
        "variant": "high_click",
        "status": "approved",
        "slots": {
            "slot-1": {"status": "agent_passed", "latestReportUri": "material-reviews/slot-1/report.json"},
            "slot-6": {"status": "agent_passed", "latestReportUri": "material-reviews/slot-6/report.json"},
        },
    }
    (generation_root / "material-review-state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    for slot_id in ("slot-1", "slot-6"):
        report_dir = generation_root / "material-reviews" / slot_id
        report_dir.mkdir(parents=True)
        (report_dir / "report.json").write_text('{"approved": true}', encoding="utf-8")

    reset_material_review_for_revise_fork(generation_root, set(), full_reset=True)

    updated = json.loads((generation_root / "material-review-state.json").read_text(encoding="utf-8"))
    assert updated["status"] == "draft"
    assert "humanOverride" not in updated
    assert updated["slots"] == {}
    assert not (generation_root / "material-reviews").exists()


def test_seed_revise_generation_writes_material_review_context(tmp_path: Path) -> None:
    project_id = "project-1"
    source_id = "gen-source"
    target_id = "gen-target"
    project_root = tmp_path / "projects" / project_id
    source_root = project_root / "generations" / source_id
    source_root.mkdir(parents=True)
    (source_root / "generation-plan.json").write_text(
        json.dumps(
            {
                "id": source_id,
                "storyboard": [{"id": "scene-6", "slotId": "slot-6", "startSec": 0, "endSec": 5}],
                "completionActions": [
                    {
                        "id": "action-slot-6",
                        "slotId": "slot-6",
                        "provider": "hyperframes_material",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (source_root / "checkpoint.json").write_text(
        json.dumps({"version": "p0-v1", "generationId": source_id, "completedStages": ["rendering"]}),
        encoding="utf-8",
    )
    (source_root / "material-review-state.json").write_text(
        json.dumps(
            {
                "generationId": source_id,
                "projectId": project_id,
                "variant": "high_click",
                "status": "approved",
                "slots": {
                    "slot-6": {"status": "agent_passed", "latestReportUri": "material-reviews/slot-6/report.json"}
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    generated = source_root / "generated"
    generated.mkdir()
    (generated / "action-slot-6.mp4").write_bytes(b"video")

    intents = [
        {
            "target": "generation_plan.storyboard",
            "operation": "change_packaging_style",
            "executionTool": "material_regen",
            "scope": "scene",
            "sceneIds": ["scene-6"],
            "slotIds": ["slot-6"],
            "params": {
                "sceneId": "scene-6",
                "slotId": "slot-6",
                "materialEditMode": "full",
                "editInstruction": "更明快",
                "requiresMaterialRegen": True,
            },
        }
    ]
    plan = json.loads((source_root / "generation-plan.json").read_text(encoding="utf-8"))
    context = apply_intents_to_context(intents, source_plan=plan)

    seed_revise_generation(
        project_root=project_root,
        source_generation_id=source_id,
        target_generation_id=target_id,
        intents=intents,
        revise_context=context,
    )

    target_root = project_root / "generations" / target_id
    revise_context = json.loads((target_root / "revise-context.json").read_text(encoding="utf-8"))
    assert revise_context["materialReviewScope"] == "scoped"
    assert revise_context["materialReviewSlotIds"] == ["slot-6"]
    assert revise_context["sourceGenerationId"] == source_id

    state = json.loads((target_root / "material-review-state.json").read_text(encoding="utf-8"))
    assert state["status"] == "draft"
    assert state["slots"]["slot-6"]["status"] == "pending"

    loaded = load_material_review_revise_context(target_root)
    assert loaded == {
        "scope": "scoped",
        "sourceGenerationId": source_id,
        "affectedSlotIds": ["slot-6"],
    }


def test_seed_revise_generation_omits_material_review_metadata_when_on_revise_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true")
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ON_REVISE", "false")
    project_id = "project-1"
    source_id = "gen-source"
    target_id = "gen-target"
    project_root = tmp_path / "projects" / project_id
    source_root = project_root / "generations" / source_id
    source_root.mkdir(parents=True)
    (source_root / "generation-plan.json").write_text(
        json.dumps(
            {
                "id": source_id,
                "storyboard": [{"id": "scene-6", "slotId": "slot-6", "startSec": 0, "endSec": 5}],
                "completionActions": [
                    {"id": "action-slot-6", "slotId": "slot-6", "provider": "hyperframes_material"},
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (source_root / "checkpoint.json").write_text(
        json.dumps({"version": "p0-v1", "generationId": source_id, "completedStages": ["rendering"]}),
        encoding="utf-8",
    )
    intents = [
        {
            "target": "generation_plan.storyboard",
            "operation": "change_packaging_style",
            "executionTool": "material_regen",
            "scope": "scene",
            "sceneIds": ["scene-6"],
            "slotIds": ["slot-6"],
            "params": {"sceneId": "scene-6", "slotId": "slot-6", "requiresMaterialRegen": True},
        }
    ]
    plan = json.loads((source_root / "generation-plan.json").read_text(encoding="utf-8"))
    context = apply_intents_to_context(intents, source_plan=plan)
    seed_revise_generation(
        project_root=project_root,
        source_generation_id=source_id,
        target_generation_id=target_id,
        intents=intents,
        revise_context=context,
    )
    revise_context = json.loads(
        (project_root / "generations" / target_id / "revise-context.json").read_text(encoding="utf-8")
    )
    assert "materialReviewScope" not in revise_context


def test_is_revise_generation_uses_edit_intent_marker(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen-fork"
    generation_root.mkdir()
    (generation_root / "edit-intent.json").write_text('{"intents": []}', encoding="utf-8")
    assert is_revise_generation(generation_root) is True
