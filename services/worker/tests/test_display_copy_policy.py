from __future__ import annotations

from app.pipelines.display_copy_policy import (
    build_author_contract,
    derive_allowed_display_copy,
    infer_material_edit_mode_for_gate_revise,
)


def test_derive_allowed_display_copy_from_storyboard_script() -> None:
    allowed = derive_allowed_display_copy(
        finish_brief={},
        edit_instruction="请加核心文字重新生成该分镜",
        storyboard_scene={
            "script": "人脉不是刻意讨好混饭局，价值对等才是长久往来的根本。",
        },
        composition_author_brief={
            "authorPrompt": "beat2把「价值对等」「长久往来」居中放大",
        },
    )
    assert "人脉不是刻意讨好混饭局，价值对等才是长久往来的根本。" in allowed
    assert "价值对等" in allowed
    assert "长久往来" in allowed


def test_infer_material_edit_mode_for_gate_revise_full() -> None:
    assert (
        infer_material_edit_mode_for_gate_revise("当前分镜没有核心文字，请重新生成")
        == "full"
    )
    assert infer_material_edit_mode_for_gate_revise("标题更大一点") == "edit"


def test_build_author_contract_allowed_list() -> None:
    contract = build_author_contract(
        allowed_display_copy=["价值对等"],
        material_edit_mode="full",
        must_change_spec=True,
    )
    assert contract["displayCopyMode"] == "allowed_list"
    assert contract["allowedDisplayCopy"] == ["价值对等"]
    assert contract["mustChangeSpec"] is True
