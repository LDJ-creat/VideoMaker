from __future__ import annotations

from typing import Any

from app.validation.schema_loader import validate_contract


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

    bible: dict[str, Any] = {"summary": summary[:800]}
    for key in ("palette", "avoid"):
        items = _string_list(raw.get(key))
        if items:
            bible[key] = items
    for key in ("lighting", "cameraGrammar", "mood"):
        text = str(raw.get(key) or "").strip()
        if text:
            bible[key] = text[:200]
    derived = raw.get("derivedFrom")
    if isinstance(derived, dict) and derived:
        cleaned = {
            k: str(v)
            for k, v in derived.items()
            if k in {"structureId", "knowledgeEntryId"} and str(v).strip()
        }
        if cleaned:
            bible["derivedFrom"] = cleaned
    elif structure and structure.get("id"):
        bible.setdefault(
            "derivedFrom",
            {"structureId": str(structure["id"])},
        )
    if knowledge_entry_id:
        derived_from = dict(bible.get("derivedFrom") or {})
        derived_from["knowledgeEntryId"] = knowledge_entry_id
        bible["derivedFrom"] = derived_from

    validation = validate_contract("visual-style-bible", bible)
    if not validation.valid:
        return derive_visual_style_bible_from_structure(
            structure,
            knowledge_entry_id=knowledge_entry_id,
        )
    return bible


def knowledge_entry_id_from_context(knowledge_context: dict[str, Any] | None) -> str | None:
    if not isinstance(knowledge_context, dict):
        return None
    primary = knowledge_context.get("primary")
    if isinstance(primary, dict) and primary.get("entryId"):
        return str(primary["entryId"])
    return None


def format_visual_style_bible_for_prompt(bible: dict[str, Any] | None) -> str:
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
    if bible.get("avoid"):
        lines.append(f"Avoid: {', '.join(str(x) for x in bible['avoid'])}")
    lines.append("Keep this look consistent across all generated visuals unless the scene explicitly requires a deliberate shift.")
    return "\n".join(lines)


def augment_slot_generation_prompt(base: str, bible: dict[str, Any] | None) -> str:
    prefix = format_visual_style_bible_for_prompt(bible)
    body = str(base or "").strip()
    if not prefix:
        return body or "Generate visual content for this slot."
    if not body:
        return prefix
    return f"{prefix}\n\nSlot direction: {body}"
