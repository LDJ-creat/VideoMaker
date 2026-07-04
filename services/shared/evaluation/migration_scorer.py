from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from evaluation.artifacts import read_json, slot_match_items, storyboard_scenes

_QUANTITY_HOOK_RE = re.compile(r"\d+\s*句")
_PROGRESSIVE_LIST_RE = re.compile(r"第[一二三四五六七八九十\d]+句")
_TEMPLATE_QUANTITY_KEYWORDS = ("数量", "限定", "数字", "几句", "N句", "句")


def _token_set(text: str) -> set[str]:
    return {t for t in re.findall(r"[\u4e00-\u9fff]+|[a-z0-9]+", text.lower()) if len(t) > 1}


def _literal_overlap(left: str, right: str) -> float:
    """Token overlap ratio; used for content-copy risk, not structure scoring."""
    a = _token_set(left)
    b = _token_set(right)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _slot_role_map(ref_slots: list[dict[str, Any]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for slot in ref_slots:
        if not isinstance(slot, dict):
            continue
        slot_id = slot.get("id")
        role = slot.get("role")
        if slot_id and role:
            mapping[str(slot_id)] = str(role)
    return mapping


def _plan_roles(scenes: list[dict[str, Any]], slot_role_map: dict[str, str]) -> set[str]:
    roles: set[str] = set()
    for scene in scenes:
        if not isinstance(scene, dict):
            continue
        if scene.get("role"):
            roles.add(str(scene["role"]))
        slot_id = scene.get("slotId")
        if slot_id is not None:
            resolved = slot_role_map.get(str(slot_id))
            if resolved:
                roles.add(resolved)
    return roles


def _segment_to_slot_ids(ref_slots: list[dict[str, Any]]) -> dict[str, set[str]]:
    mapping: dict[str, set[str]] = {}
    for slot in ref_slots:
        if not isinstance(slot, dict):
            continue
        segment_id = slot.get("segmentId")
        slot_id = slot.get("id")
        if segment_id and slot_id:
            mapping.setdefault(str(segment_id), set()).add(str(slot_id))
    return mapping


def _evidence_binding(
    evidence: list[Any],
    segment_to_slots: dict[str, set[str]],
    plan_slot_ids: set[str],
) -> float:
    if not evidence:
        return 0.0
    bound = 0
    for item in evidence:
        if not isinstance(item, dict):
            continue
        target_id = str(item.get("targetId") or item.get("slotId") or "")
        candidate_slots = set(segment_to_slots.get(target_id, set()))
        if target_id in plan_slot_ids:
            candidate_slots.add(target_id)
        if candidate_slots & plan_slot_ids:
            bound += 1
    return bound / len(evidence)


def _sample_hook_text(reference_structure: dict[str, Any]) -> str:
    narrative = reference_structure.get("narrative")
    if isinstance(narrative, dict):
        segments = narrative.get("segments")
        if isinstance(segments, list):
            for segment in segments:
                if not isinstance(segment, dict):
                    continue
                if segment.get("role") == "hook":
                    excerpt = segment.get("transcriptExcerpt") or segment.get("scriptSummary")
                    if excerpt:
                        return str(excerpt)
            if segments and isinstance(segments[0], dict):
                first = segments[0].get("transcriptExcerpt") or segments[0].get("scriptSummary")
                if first:
                    return str(first)

    for item in reference_structure.get("evidence") or []:
        if not isinstance(item, dict):
            continue
        if item.get("source") == "asr" and item.get("excerpt"):
            return str(item["excerpt"])
    return ""


def _generated_hook_text(master_text: str) -> str:
    text = master_text.strip()
    if not text:
        return ""
    for delimiter in ("。", "！", "？", ".", "!", "?"):
        if delimiter in text:
            return text.split(delimiter, 1)[0] + delimiter
    return text[:80]


def _has_quantity_hook(text: str) -> bool:
    return bool(_QUANTITY_HOOK_RE.search(text))


def _has_progressive_list(text: str) -> bool:
    return bool(_PROGRESSIVE_LIST_RE.search(text))


def _opens_with_question(text: str) -> bool:
    trimmed = text.strip()
    if not trimmed:
        return False
    first = trimmed.split("。", 1)[0]
    return "？" in first or "?" in first


def _template_implies_quantity(hook_template: str) -> bool:
    return any(keyword in hook_template for keyword in _TEMPLATE_QUANTITY_KEYWORDS)


def _hook_pattern_preservation(
    reference_structure: dict[str, Any],
    master_text: str,
) -> tuple[float, float]:
    """
    Returns (hookPatternPreservation, contentCopyRisk).

    Pattern score rewards structural hook migration (quantity hooks, list progression).
    contentCopyRisk is literal overlap with the sample hook — high values suggest copying.
    """
    if not master_text.strip():
        return 0.0, 0.0

    verbal = reference_structure.get("verbal")
    hook_template = ""
    if isinstance(verbal, dict):
        hook_template = str(verbal.get("hookTemplate") or "")

    sample_hook = _sample_hook_text(reference_structure)
    generated_hook = _generated_hook_text(master_text)

    pattern = 0.0
    sample_quantity = _has_quantity_hook(sample_hook)
    generated_quantity = _has_quantity_hook(generated_hook)

    if sample_quantity and generated_quantity:
        pattern += 0.35
    elif sample_quantity or generated_quantity:
        pattern += 0.15

    if _has_progressive_list(master_text) and (sample_quantity or _template_implies_quantity(hook_template)):
        pattern += 0.30

    if sample_hook and generated_hook:
        if _opens_with_question(sample_hook) == _opens_with_question(generated_hook):
            pattern += 0.15
        else:
            pattern += 0.05

    if hook_template and _template_implies_quantity(hook_template) and generated_quantity:
        pattern += 0.20

    pattern = min(1.0, pattern)
    content_copy = _literal_overlap(sample_hook, generated_hook) if sample_hook and generated_hook else 0.0
    return pattern, content_copy


def score_migration(generation_root: Path, reference_structure: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(reference_structure, dict):
        return {"score": 0.0, "issues": ["missing_reference_structure"]}

    ref_slots = [slot for slot in (reference_structure.get("slots") or []) if isinstance(slot, dict)]
    plan = read_json(generation_root / "generation-plan.json") or {}
    matches = read_json(generation_root / "slot-matches.json") or {}

    matched_ids = {
        str(item["slotId"])
        for item in slot_match_items(matches)
        if item.get("slotId")
    }

    scenes = storyboard_scenes(plan)
    plan_slot_ids = {
        str(scene.get("slotId"))
        for scene in scenes
        if scene.get("slotId")
    }

    ref_ids = {str(slot.get("id")) for slot in ref_slots if slot.get("id")}
    covered = ref_ids & (matched_ids | plan_slot_ids)
    slot_coverage = len(covered) / len(ref_ids) if ref_ids else 1.0

    slot_role_map = _slot_role_map(ref_slots)
    ref_roles = {role for role in slot_role_map.values()}
    plan_roles = _plan_roles(scenes, slot_role_map)
    role_preservation = len(ref_roles & plan_roles) / len(ref_roles) if ref_roles else 1.0

    master = read_json(generation_root / "script-draft.json") or {}
    if not master.get("masterNarration") and not master.get("masterScript"):
        master = plan
    master_text = str(master.get("masterNarration") or master.get("masterScript") or "")

    hook_pattern, content_copy_risk = _hook_pattern_preservation(reference_structure, master_text)

    evidence = list(reference_structure.get("evidence") or [])
    segment_to_slots = _segment_to_slot_ids(ref_slots)
    evidence_binding = _evidence_binding(evidence, segment_to_slots, plan_slot_ids)

    weighted = (
        slot_coverage * 0.35
        + role_preservation * 0.25
        + hook_pattern * 0.20
        + evidence_binding * 0.20
    ) * 100.0

    issues: list[str] = []
    if slot_coverage < 0.8:
        issues.append(f"low_slot_coverage:{slot_coverage:.2f}")
    if role_preservation < 0.6:
        issues.append(f"low_role_preservation:{role_preservation:.2f}")
    if hook_pattern < 0.4:
        issues.append(f"low_hook_pattern:{hook_pattern:.2f}")
    if content_copy_risk >= 0.5:
        issues.append(f"high_content_copy_risk:{content_copy_risk:.2f}")

    return {
        "weighted": round(weighted, 1),
        "slotCoverage": round(slot_coverage, 3),
        "rolePreservation": round(role_preservation, 3),
        "hookPreservation": round(hook_pattern, 3),
        "hookPatternPreservation": round(hook_pattern, 3),
        "contentCopyRisk": round(content_copy_risk, 3),
        "evidenceBinding": round(evidence_binding, 3),
        "issues": issues,
    }
