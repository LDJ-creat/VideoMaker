from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.pipelines.revise_material_edit import (
    SlotChainKind,
    apply_narration_preview_to_storyboard,
    archive_slot_material,
    build_edit_finish_brief,
    classify_slot_material_chain,
    collect_seed_invalidate_plan,
    load_archived_material_spec,
    normalize_plan_storyboard_timing,
    normalize_scene_start_end,
    persist_material_spec_after_render,
    rebind_plan_to_generation,
    resolve_preserve_action_ids,
    resolve_slot_timing_for_revise,
    restore_archived_upstream_media,
    should_degrade_edit_to_full,
)
from app.providers.completion_registry import (
    expected_output_path,
    invalidate_material_for_slots,
    load_material_state,
)


def test_classify_slot_chains() -> None:
    actions = [
        {"id": "stock-1", "slotId": "slot-a", "provider": "stock_media_search"},
        {"id": "finish-1", "slotId": "slot-a", "provider": "hyperframes_material"},
        {"id": "hf-1", "slotId": "slot-b", "provider": "hyperframes_material"},
        {"id": "img-1", "slotId": "slot-c", "provider": "image_generation"},
    ]
    assert classify_slot_material_chain(actions, "slot-a") == SlotChainKind.STOCK_THEN_HF
    assert classify_slot_material_chain(actions, "slot-b") == SlotChainKind.HF_ONLY
    assert classify_slot_material_chain(actions, "slot-c") == SlotChainKind.IMAGE_ONLY


def test_should_degrade_edit_to_full() -> None:
    assert should_degrade_edit_to_full(SlotChainKind.IMAGE_ONLY) is True
    assert should_degrade_edit_to_full(SlotChainKind.HF_ONLY) is False


def test_resolve_preserve_action_ids_edit_stock_chain() -> None:
    actions = [
        {"id": "stock-1", "slotId": "slot-a", "provider": "stock_media_search"},
        {"id": "finish-1", "slotId": "slot-a", "provider": "hyperframes_material"},
    ]
    preserved = resolve_preserve_action_ids(actions, "slot-a", "edit")
    assert preserved == {"stock-1"}


def test_resolve_preserve_action_ids_full_clears_all() -> None:
    actions = [
        {"id": "stock-1", "slotId": "slot-a", "provider": "stock_media_search"},
        {"id": "finish-1", "slotId": "slot-a", "provider": "hyperframes_material"},
    ]
    assert resolve_preserve_action_ids(actions, "slot-a", "full") == set()


def test_collect_seed_invalidate_plan_full_clears_stock_query() -> None:
    actions = [
        {
            "id": "stock-1",
            "slotId": "slot-a",
            "provider": "stock_media_search",
            "stockSearchQuery": {"primaryQuery": "city night"},
        },
        {"id": "finish-1", "slotId": "slot-a", "provider": "hyperframes_material"},
    ]
    preserve_ids, chain_kinds = collect_seed_invalidate_plan(
        actions=actions,
        slot_ids={"slot-a"},
        material_edit_mode="full",
    )
    assert preserve_ids == set()
    assert chain_kinds["slot-a"] == SlotChainKind.STOCK_THEN_HF.value
    assert "stockSearchQuery" not in actions[0]


def test_build_edit_finish_brief_center_and_prompt() -> None:
    brief = build_edit_finish_brief(
        {"compositionAuthorBrief": {"authorPrompt": "原有说明"}},
        instruction="字幕居中",
    )
    assert brief["editInstruction"] == "字幕居中"
    assert brief["layoutDirective"]
    assert brief["compositionAuthorBrief"]["layoutAnchor"] == "center"
    assert "修改要求" in brief["compositionAuthorBrief"]["authorPrompt"]

    center_brief = build_edit_finish_brief(None, instruction="移到中心")
    assert center_brief["layoutDirective"]
    assert "修改要求：移到中心" in center_brief["compositionAuthorBrief"]["authorPrompt"]


def test_invalidate_preserves_stock_file(tmp_path: Path) -> None:
    generated_root = tmp_path / "generated"
    generated_root.mkdir(parents=True)
    stock_action = {
        "id": "stock-1",
        "slotId": "slot-6",
        "provider": "stock_media_search",
    }
    finish_action = {
        "id": "finish-6",
        "slotId": "slot-6",
        "provider": "hyperframes_material",
    }
    stock_path = generated_root / "slot-6-stock.mp4"
    stock_path.write_bytes(b"stock")
    finish_path = expected_output_path(finish_action, generated_root)
    finish_path.parent.mkdir(parents=True, exist_ok=True)
    finish_path.write_bytes(b"finish")
    hf_dir = generated_root / "finish-6" / "composition"
    hf_dir.mkdir(parents=True)
    (hf_dir / "index.html").write_text("<html></html>", encoding="utf-8")

    state_path = tmp_path / "material-state.json"
    state_path.write_text(
        '{"videoGenQuota": {}, "completedActionIds": ["stock-1", "finish-6"]}',
        encoding="utf-8",
    )

    invalidate_material_for_slots(
        actions=[stock_action, finish_action],
        generated_root=generated_root,
        slot_ids={"slot-6"},
        material_state_path=state_path,
        preserve_action_ids={"stock-1"},
    )

    assert stock_path.is_file()
    assert not finish_path.is_file()
    assert not (generated_root / "finish-6").exists()
    _, completed = load_material_state(state_path)
    assert "stock-1" in completed
    assert "finish-6" not in completed


def test_archive_and_restore_stock(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generated_root = generation_root / "generated"
    generated_root.mkdir(parents=True)
    actions = [
        {"id": "stock-1", "slotId": "slot-1", "provider": "stock_media_search"},
        {"id": "finish-1", "slotId": "slot-1", "provider": "hyperframes_material"},
    ]
    spec = {"template": "composition", "durationSec": 3.0}
    persist_material_spec_after_render(
        spec=spec,
        generated_root=generated_root,
        action_id="finish-1",
    )
    stock_path = generated_root / "slot-1-stock.mp4"
    stock_path.write_bytes(b"stock-bytes")

    archive_dir = archive_slot_material(
        generation_root=generation_root,
        generated_root=generated_root,
        actions=actions,
        slot_id="slot-1",
    )
    assert archive_dir is not None
    assert load_archived_material_spec(generation_root, "slot-1") == spec

    stock_path.unlink()
    restored = restore_archived_upstream_media(
        generation_root=generation_root,
        generated_root=generated_root,
        slot_id="slot-1",
    )
    assert restored is True
    assert stock_path.read_bytes() == b"stock-bytes"


def test_normalize_scene_start_end_swaps_inverted_values() -> None:
    start, end, duration = normalize_scene_start_end(41.325, 34.316)
    assert start == 34.316
    assert end == 41.325
    assert duration == pytest.approx(7.009, abs=0.001)


def test_resolve_slot_timing_prefers_narration_preview(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generation_root.mkdir()
    preview_path = generation_root / "narration-preview.json"
    preview_path.write_text(
        json.dumps(
            {
                "sceneTiming": [
                    {"slotId": "slot-6", "startSec": 34.316, "endSec": 37.078},
                ]
            }
        ),
        encoding="utf-8",
    )
    storyboard = [{"slotId": "slot-6", "startSec": 41.325, "endSec": 34.316}]
    timing = resolve_slot_timing_for_revise(generation_root, storyboard, "slot-6")
    assert timing["durationSec"] == pytest.approx(2.762, abs=0.001)


def test_rebind_plan_to_generation_rewrites_ids_and_paths() -> None:
    source_id = "gen-old"
    target_id = "gen-new"
    plan = {
        "id": source_id,
        "completionActions": [
            {
                "outputRef": f"storage/projects/demo/generations/{source_id}/generated/finish-6/output.mp4",
            }
        ],
    }
    rebound = rebind_plan_to_generation(
        plan,
        source_generation_id=source_id,
        target_generation_id=target_id,
    )
    assert rebound["id"] == target_id
    assert target_id in rebound["completionActions"][0]["outputRef"]
    assert source_id not in rebound["completionActions"][0]["outputRef"]


def test_archive_discovers_acp_author_spec(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generated_root = generation_root / "generated"
    generated_root.mkdir(parents=True)
    actions = [{"id": "finish-6", "slotId": "slot-6", "provider": "hyperframes_material"}]
    spec = {"template": "composition", "durationSec": 2.762, "composition": {"bodyHtml": "<div/>"}}
    acp_dir = generation_root / "acp-author" / "slot-6"
    acp_dir.mkdir(parents=True)
    (acp_dir / "material-spec.json").write_text(json.dumps(spec), encoding="utf-8")
    composition_dir = generated_root / "finish-6" / "composition"
    composition_dir.mkdir(parents=True)
    (composition_dir / "index.html").write_text("<html></html>", encoding="utf-8")

    archive_dir = archive_slot_material(
        generation_root=generation_root,
        generated_root=generated_root,
        actions=actions,
        slot_id="slot-6",
    )
    assert archive_dir is not None
    archived = load_archived_material_spec(generation_root, "slot-6")
    assert archived == spec


def test_normalize_plan_storyboard_timing_and_preview(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generation_root.mkdir()
    (generation_root / "narration-preview.json").write_text(
        json.dumps(
            {
                "sceneTiming": [
                    {"slotId": "slot-6", "startSec": 1.0, "endSec": 3.5},
                ]
            }
        ),
        encoding="utf-8",
    )
    plan = {
        "storyboard": [
            {"slotId": "slot-6", "startSec": 9.0, "endSec": 1.0},
            {"slotId": "slot-7", "startSec": 10.0, "endSec": 8.0},
        ]
    }
    apply_narration_preview_to_storyboard(generation_root, plan, {"slot-6"})
    normalize_plan_storyboard_timing(plan, {"slot-7"})
    assert plan["storyboard"][0]["startSec"] == 1.0
    assert plan["storyboard"][0]["endSec"] == 3.5
    assert plan["storyboard"][1]["startSec"] == 8.0
    assert plan["storyboard"][1]["endSec"] == 10.0


def test_resolve_material_edit_author_state_uses_generation_root(tmp_path: Path) -> None:
    from unittest.mock import MagicMock

    from app.providers.hyperframes_material_provider import _resolve_material_edit_author_state
    from app.providers.material_types import MaterialContext

    generation_root = tmp_path / "projects" / "proj" / "generations" / "gen-fork"
    generated_root = generation_root / "generated"
    generated_root.mkdir(parents=True)
    (generation_root / "revise-context.json").write_text(
        json.dumps(
            {
                "materialEditMode": "edit",
                "editInstruction": "overlay居中",
                "slotChainKinds": {"slot-6": "hf_only"},
            }
        ),
        encoding="utf-8",
    )
    archive_dir = generation_root / "revise-material-archive" / "slot-6"
    archive_dir.mkdir(parents=True)
    (archive_dir / "material-spec.json").write_text(
        json.dumps(
            {
                "template": "composition",
                "durationSec": 2.7,
                "composition": {"bodyHtml": "<div/>"},
            }
        ),
        encoding="utf-8",
    )
    render_root = tmp_path / "projects" / "proj" / "renders" / "gen-fork"
    render_root.mkdir(parents=True)

    ctx = MaterialContext(
        project_id="proj",
        generation_id="gen-fork",
        render_root=render_root,
        generated_root=generated_root,
        storage_root=tmp_path,
        gateway=MagicMock(),
        quota=MagicMock(),
        inventory={"assets": []},
        slot_matches=[],
        storyboard=[],
        structure={"slots": [{"id": "slot-6", "role": "cta"}]},
        emit_progress=lambda *_args, **_kwargs: None,
        register_artifact=lambda *_args, **_kwargs: {},
    )

    mode, instruction, existing_spec, warning = _resolve_material_edit_author_state(ctx, "slot-6")

    assert mode == "edit"
    assert "居中" in instruction
    assert existing_spec is not None
    assert existing_spec["durationSec"] == 2.7
    assert warning is None
