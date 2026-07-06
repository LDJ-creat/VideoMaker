from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.material_slot_revise import (
    MATERIAL_GATE_REVISE_KEY,
    REVISE_CONTEXT_FILENAME,
    clear_acp_scratch_for_gate_revise,
    clear_material_gate_revise_context,
    prepare_material_slot_revise,
)


def test_prepare_material_slot_revise_writes_revise_context(tmp_path: Path) -> None:
    generation_root = tmp_path / "projects" / "proj" / "generations" / "gen-1"
    generated_root = generation_root / "generated"
    generated_root.mkdir(parents=True)
    action_id = "action-hook-finish"
    slot_id = "hook"
    (generated_root / action_id).mkdir(parents=True)
    (generated_root / "material-spec.json").write_text(
        json.dumps({"template": "composition", "durationSec": 3.0}),
        encoding="utf-8",
    )
    (generated_root / action_id / "material-spec.json").write_text(
        json.dumps({"template": "composition", "durationSec": 3.0}),
        encoding="utf-8",
    )
    (generated_root / f"{action_id}.mp4").write_bytes(b"\x00" * 128)
    scratch = generation_root / "acp-author" / slot_id
    scratch.mkdir(parents=True)
    (scratch / "material-spec.json").write_text("{}", encoding="utf-8")
    (scratch / "material-review-marker.json").write_text("{}", encoding="utf-8")
    plan = {
        "storyboard": [
            {
                "slotId": slot_id,
                "script": "人脉不是刻意讨好混饭局，价值对等才是长久往来的根本。",
            }
        ],
        "completionActions": [
            {
                "id": "action-hook-stock",
                "slotId": slot_id,
                "provider": "stock_media_search",
            },
            {
                "id": action_id,
                "slotId": slot_id,
                "provider": "hyperframes_material",
                "finishBrief": {
                    "compositionAuthorBrief": {
                        "authorPrompt": "beat2把「价值对等」居中放大",
                    }
                },
            },
        ],
    }
    (generation_root / "material-state.json").write_text(
        json.dumps({"videoGenQuota": {}, "completedActionIds": [action_id]}),
        encoding="utf-8",
    )

    _, slot_filter = prepare_material_slot_revise(
        generation_root=generation_root,
        plan=plan,
        slot_id=slot_id,
        instruction="请加核心文字重新生成",
    )

    context_path = generation_root / REVISE_CONTEXT_FILENAME
    assert context_path.is_file()
    context = json.loads(context_path.read_text(encoding="utf-8"))
    gate = context[MATERIAL_GATE_REVISE_KEY]
    assert gate["materialEditMode"] == "full"
    assert gate["editInstruction"] == "请加核心文字重新生成"
    assert gate["source"] == "material_gate_revise"
    assert gate["allowedDisplayCopy"]
    assert "价值对等" in gate["allowedDisplayCopy"]
    assert gate["authorContract"]["mustChangeSpec"] is True
    assert slot_filter == {slot_id}
    archive_spec = generation_root / "revise-material-archive" / slot_id / "material-spec.json"
    assert archive_spec.is_file()
    assert not (scratch / "material-spec.json").exists()
    assert not (scratch / "material-review-marker.json").exists()
    hf_action = plan["completionActions"][1]
    assert hf_action["finishBrief"]["renderPolicy"]["allowedDisplayCopy"]


def test_prepare_material_slot_revise_preserves_fork_revise_context(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen-fork"
    generation_root.mkdir(parents=True)
    (generation_root / REVISE_CONTEXT_FILENAME).write_text(
        json.dumps(
            {
                "sourceGenerationId": "gen-source",
                "materialReviewScope": "scoped",
                "materialReviewSlotIds": ["hook", "usage"],
                "affectedSlotIds": ["hook"],
                "materialScope": "scoped",
                "affectedStages": ["generating_material", "rendering"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    generated_root = generation_root / "generated"
    generated_root.mkdir()
    slot_id = "hook"
    (generated_root / "action-hook.mp4").write_bytes(b"\x00" * 128)
    plan = {
        "completionActions": [
            {"id": "action-hook", "slotId": slot_id, "provider": "hyperframes_material"},
        ]
    }

    prepare_material_slot_revise(
        generation_root=generation_root,
        plan=plan,
        slot_id=slot_id,
        instruction="更亮一点",
    )

    context = json.loads((generation_root / REVISE_CONTEXT_FILENAME).read_text(encoding="utf-8"))
    assert context["sourceGenerationId"] == "gen-source"
    assert context["materialReviewScope"] == "scoped"
    assert context["materialReviewSlotIds"] == ["hook", "usage"]
    assert context["affectedSlotIds"] == ["hook"]
    assert context[MATERIAL_GATE_REVISE_KEY]["editInstruction"] == "更亮一点"


def test_load_material_gate_revise_slot_ids(tmp_path: Path) -> None:
    from app.pipelines.material_slot_revise import load_material_gate_revise_slot_ids

    generation_root = tmp_path / "gen-gate"
    generation_root.mkdir()
    (generation_root / REVISE_CONTEXT_FILENAME).write_text(
        json.dumps(
            {
                MATERIAL_GATE_REVISE_KEY: {
                    "source": "material_gate_revise",
                    "materialEditMode": "edit",
                    "editInstruction": "居中",
                    "affectedSlotIds": ["slot-6"],
                }
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    assert load_material_gate_revise_slot_ids(generation_root) == {"slot-6"}


def test_clear_material_gate_revise_context_preserves_fork_metadata(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen-fork"
    generation_root.mkdir(parents=True)
    (generation_root / REVISE_CONTEXT_FILENAME).write_text(
        json.dumps(
            {
                "sourceGenerationId": "gen-source",
                "materialReviewScope": "scoped",
                "materialReviewSlotIds": ["hook"],
                "materialGateRevise": {
                    "source": "material_gate_revise",
                    "materialEditMode": "edit",
                    "editInstruction": "更亮",
                    "affectedSlotIds": ["hook"],
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    clear_material_gate_revise_context(generation_root)

    assert (generation_root / REVISE_CONTEXT_FILENAME).is_file()
    context = json.loads((generation_root / REVISE_CONTEXT_FILENAME).read_text(encoding="utf-8"))
    assert MATERIAL_GATE_REVISE_KEY not in context
    assert context["materialReviewScope"] == "scoped"
    assert context["sourceGenerationId"] == "gen-source"
