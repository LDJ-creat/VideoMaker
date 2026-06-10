from __future__ import annotations

from typing import Any

from app.validation.schema_loader import validate_contract

VISUAL_BIBLE_ALLOWED_KEYS: frozenset[str] = frozenset(
    {"summary", "palette", "lighting", "cameraGrammar", "mood", "avoid", "derivedFrom"}
)

DEFAULT_VISUAL_AVOID: tuple[str, ...] = (
    "紫粉或蓝紫对角渐变背景",
    "圆角卡片配彩色左边框",
    "emoji 图标",
    "假数据与假 logo",
    "全场相同 fade/blur 入场",
)


def _merge_default_avoid(existing: list[str] | None) -> list[str]:
    merged = list(DEFAULT_VISUAL_AVOID)
    for item in existing or []:
        text = str(item).strip()
        if text and text not in merged:
            merged.append(text)
    return merged[:8]


def _sanitize_visual_style_bible(bible: dict[str, Any]) -> dict[str, Any]:
    cleaned: dict[str, Any] = {}
    for key in VISUAL_BIBLE_ALLOWED_KEYS:
        if key not in bible:
            continue
        value = bible[key]
        if key == "summary":
            text = str(value or "").strip()
            if text:
                cleaned["summary"] = text[:800]
        elif key in {"lighting", "cameraGrammar", "mood"}:
            text = str(value or "").strip()
            if text:
                cleaned[key] = text[:200]
        elif key == "palette":
            items = _string_list(value)
            if items:
                cleaned["palette"] = items
        elif key == "avoid":
            cleaned["avoid"] = _merge_default_avoid(_string_list(value))
        elif key == "derivedFrom" and isinstance(value, dict):
            derived = {
                k: str(v)
                for k, v in value.items()
                if k in {"structureId", "knowledgeEntryId"} and str(v).strip()
            }
            if derived:
                cleaned["derivedFrom"] = derived
    if "summary" not in cleaned:
        return cleaned
    if "avoid" not in cleaned:
        cleaned["avoid"] = _merge_default_avoid(None)
    return cleaned


def _string_list(value: Any, *, max_items: int = 8) -> list[str] | None:
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    if not isinstance(value, list):
        return None
    items = [str(item).strip() for item in value if str(item).strip()]
    if not items:
        return None
    return items[:max_items]


def derive_visual_style_bible_from_structure(
    structure: dict[str, Any] | None,
    *,
    knowledge_entry_id: str | None = None,
) -> dict[str, Any]:
    """Deterministic fallback when the LLM omits visualStyleBible."""
    structure = structure if isinstance(structure, dict) else {}
    visual = structure.get("visual") if isinstance(structure.get("visual"), dict) else {}
    packaging = visual.get("packagingSpec") if isinstance(visual.get("packagingSpec"), dict) else {}
    metadata = structure.get("metadata") if isinstance(structure.get("metadata"), dict) else {}

    palette: list[str] = []
    moods: list[str] = []
    for slot in structure.get("slots") or []:
        if not isinstance(slot, dict):
            continue
        spec = slot.get("visualSpec")
        if isinstance(spec, dict):
            color_mood = str(spec.get("colorMood") or "").strip()
            if color_mood and color_mood not in moods:
                moods.append(color_mood)
            if color_mood and color_mood not in palette:
                palette.append(color_mood)

    width = metadata.get("width")
    height = metadata.get("height")
    aspect_hint = "竖屏9:16" if isinstance(height, (int, float)) and isinstance(width, (int, float)) and height > width else "横屏16:9"

    packaging_summary = str(packaging.get("summary") or packaging.get("visualDensity") or "").strip()
    mood_text = "、".join(moods[:3]) if moods else "清晰可信"
    summary_parts = [aspect_hint, mood_text]
    if packaging_summary:
        summary_parts.append(packaging_summary)
    summary = "；".join(part for part in summary_parts if part)

    bible: dict[str, Any] = {"summary": summary[:800]}
    if palette:
        bible["palette"] = palette[:8]
    if moods:
        bible["mood"] = moods[0][:200]
    bible["lighting"] = "自然光，柔和阴影，避免极端冷暖冲突"
    bible["cameraGrammar"] = f"{aspect_hint}；近景与中景结合，稳定手持或轻推"
    derived: dict[str, str] = {}
    if structure.get("id"):
        derived["structureId"] = str(structure["id"])
    if knowledge_entry_id:
        derived["knowledgeEntryId"] = knowledge_entry_id
    if derived:
        bible["derivedFrom"] = derived
    bible["avoid"] = _merge_default_avoid(None)
    return bible


def normalize_visual_style_bible(
    payload: dict[str, Any] | None,
    *,
    structure: dict[str, Any] | None = None,
    knowledge_entry_id: str | None = None,
) -> dict[str, Any]:
    raw = payload if isinstance(payload, dict) else {}
    summary = str(raw.get("summary") or "").strip()
    if not summary:
        return derive_visual_style_bible_from_structure(
            structure,
            knowledge_entry_id=knowledge_entry_id,
        )

    bible = _sanitize_visual_style_bible({**raw, "summary": summary})
    if structure and structure.get("id"):
        bible.setdefault("derivedFrom", {"structureId": str(structure["id"])})
    if knowledge_entry_id:
        derived_from = dict(bible.get("derivedFrom") or {})
        derived_from["knowledgeEntryId"] = knowledge_entry_id
        bible["derivedFrom"] = derived_from

    validation = validate_contract("visual-style-bible", bible)
    if validation.valid:
        return bible

    fallback = derive_visual_style_bible_from_structure(
        structure,
        knowledge_entry_id=knowledge_entry_id,
    )
    fallback["summary"] = summary[:800]
    if bible.get("palette"):
        fallback["palette"] = bible["palette"]
    if bible.get("lighting"):
        fallback["lighting"] = bible["lighting"]
    if bible.get("cameraGrammar"):
        fallback["cameraGrammar"] = bible["cameraGrammar"]
    if bible.get("mood"):
        fallback["mood"] = bible["mood"]
    fallback["avoid"] = bible.get("avoid") or _merge_default_avoid(None)
    fallback_validation = validate_contract("visual-style-bible", fallback)
    if fallback_validation.valid:
        return fallback
    return derive_visual_style_bible_from_structure(
        structure,
        knowledge_entry_id=knowledge_entry_id,
    )


def knowledge_entry_id_from_context(knowledge_context: dict[str, Any] | None) -> str | None:
    if not isinstance(knowledge_context, dict):
        return None
    primary = knowledge_context.get("primary")
    if isinstance(primary, dict) and primary.get("entryId"):
        return str(primary["entryId"])
    return None


def _aigc_layout_avoid_hint() -> str:
    return (
        "Layout quality: avoid generic AI slide tropes (purple-pink diagonal gradient backgrounds, "
        "left-border accent cards, emoji icons). Brand accent colors from the palette are OK when used sparingly."
    )


def format_visual_style_bible_for_prompt(
    bible: dict[str, Any] | None,
    *,
    for_aigc: bool = False,
) -> str:
    if not isinstance(bible, dict) or not str(bible.get("summary") or "").strip():
        return ""
    lines = [f"Global visual style bible: {str(bible['summary']).strip()}"]
    if bible.get("palette"):
        lines.append(f"Palette: {', '.join(str(x) for x in bible['palette'])}")
    if bible.get("lighting"):
        lines.append(f"Lighting: {bible['lighting']}")
    if bible.get("cameraGrammar"):
        lines.append(f"Camera: {bible['cameraGrammar']}")
    if bible.get("mood"):
        lines.append(f"Mood: {bible['mood']}")
    if for_aigc:
        lines.append(_aigc_layout_avoid_hint())
    elif bible.get("avoid"):
        lines.append(f"Avoid: {', '.join(str(x) for x in bible['avoid'])}")
    lines.append("Keep this look consistent across all generated visuals unless the scene explicitly requires a deliberate shift.")
    return "\n".join(lines)


def augment_slot_generation_prompt(base: str, bible: dict[str, Any] | None) -> str:
    prefix = format_visual_style_bible_for_prompt(bible, for_aigc=True)
    body = str(base or "").strip()
    if not prefix:
        return body or "Generate visual content for this slot."
    if not body:
        return prefix
    return f"{prefix}\n\nSlot direction: {body}"
