from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from app.pipelines.visual_style_bible import (
    DEFAULT_VISUAL_AVOID,
    augment_slot_generation_prompt,
    derive_visual_style_bible_from_structure,
    normalize_visual_style_bible,
)
from app.providers.image_generation_provider import _prompt_for_slot
from app.providers.material_types import MaterialContext
from app.runtime.video_gen_quota import VideoGenQuota


def test_derive_visual_style_bible_includes_default_avoid() -> None:
    bible = derive_visual_style_bible_from_structure({"slots": [], "metadata": {"width": 1080, "height": 1920}})
    assert bible["avoid"][: len(DEFAULT_VISUAL_AVOID)] == list(DEFAULT_VISUAL_AVOID)


def test_normalize_visual_style_bible_merges_custom_avoid() -> None:
    bible = normalize_visual_style_bible(
        {
            "summary": "冷色科技风",
            "avoid": ["霓虹描边"],
        },
        structure={"id": "vs-3", "slots": []},
    )
    assert "霓虹描边" in bible["avoid"]
    assert "紫粉或蓝紫对角渐变背景" in bible["avoid"]


def test_derive_visual_style_bible_from_structure_uses_slot_color_mood() -> None:
    structure = {
        "id": "vs-1",
        "metadata": {"width": 1080, "height": 1920},
        "visual": {"packagingSpec": {"summary": "轻包装字幕"}},
        "slots": [
            {"id": "s1", "visualSpec": {"colorMood": "暖白"}},
            {"id": "s2", "visualSpec": {"colorMood": "珊瑚橙"}},
        ],
    }
    bible = derive_visual_style_bible_from_structure(structure, knowledge_entry_id="k-1")
    assert "竖屏9:16" in bible["summary"]
    assert bible["palette"] == ["暖白", "珊瑚橙"]
    assert bible["derivedFrom"]["knowledgeEntryId"] == "k-1"


def test_normalize_visual_style_bible_falls_back_when_summary_missing() -> None:
    structure = {"id": "vs-2", "slots": [], "metadata": {"width": 1920, "height": 1080}}
    bible = normalize_visual_style_bible({}, structure=structure)
    assert bible["summary"]
    assert "横屏16:9" in bible["summary"]


def test_augment_slot_generation_prompt_prefixes_bible() -> None:
    bible = {
        "summary": "暖色自然光；竖屏9:16",
        "palette": ["暖白"],
        "avoid": ["紫粉或蓝紫对角渐变背景"],
    }
    prompt = augment_slot_generation_prompt("产品特写", bible)
    assert prompt.startswith("Global visual style bible:")
    assert "Slot direction: 产品特写" in prompt
    assert "Layout quality:" in prompt
    assert "Avoid: 紫粉" not in prompt


def test_normalize_visual_style_bible_preserves_summary_on_extra_fields() -> None:
    bible = normalize_visual_style_bible(
        {
            "summary": "用户定制的电影感暖调",
            "palette": ["暖白"],
            "unexpectedField": "drop-me",
        },
        structure={"id": "vs-4", "slots": []},
    )
    assert bible["summary"] == "用户定制的电影感暖调"
    assert bible["palette"] == ["暖白"]
    assert "unexpectedField" not in bible


def test_image_generation_prompt_for_slot_includes_bible(tmp_path: Path) -> None:
    generated_root = tmp_path / "generated"
    generated_root.mkdir(parents=True, exist_ok=True)
    ctx = MaterialContext(
        project_id="project-1",
        generation_id="gen-1",
        render_root=tmp_path / "renders" / "gen-1",
        generated_root=generated_root,
        gateway=MagicMock(),
        quota=VideoGenQuota(max_calls=1),
        inventory={"assets": []},
        slot_matches=[],
        structure={"slots": []},
        storyboard=[
            {
                "slotId": "slot-hook",
                "visual": "手持产品特写",
                "script": "还在担心出门效率低？",
            }
        ],
        emit_progress=lambda *_args, **_kwargs: None,
        register_artifact=lambda artifact_type, path: {"type": artifact_type, "uri": str(path)},
        visual_style_bible={"summary": "暖色自然光；竖屏9:16"},
    )
    prompt = _prompt_for_slot(ctx, "slot-hook")
    assert "Global visual style bible" in prompt
    assert "手持产品特写" in prompt
