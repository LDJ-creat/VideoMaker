from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any, Callable


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _normalize_tokens(text: str) -> set[str]:
    if not text:
        return set()
    parts = re.findall(r"[\u4e00-\u9fff]+|[a-zA-Z0-9]+", text.lower())
    return {part for part in parts if part}


def _brief_text(brief: dict[str, Any]) -> str:
    chunks = [
        str(brief.get("topic", "")),
        str(brief.get("productName", "")),
        str(brief.get("targetAudience", "")),
        str(brief.get("tone", "")),
        " ".join(str(item) for item in brief.get("sellingPoints", []) if item),
    ]
    return " ".join(chunk for chunk in chunks if chunk).strip()


def _tone_to_tempo(tone: str) -> str | None:
    lowered = tone.lower()
    if any(token in lowered for token in ("快", "fast", "节奏", "高能")):
        return "fast"
    if any(token in lowered for token in ("慢", "slow", "质感", "电影")):
        return "slow"
    if any(token in lowered for token in ("标准", "medium", "自然")):
        return "medium"
    return None


def score_entry_against_brief(
    entry: dict[str, Any],
    *,
    brief: dict[str, Any],
    structure: dict[str, Any] | None = None,
    source_project_id: str | None = None,
) -> tuple[float, list[str]]:
    reasons: list[str] = []
    score = 0.0

    brief_tokens = _normalize_tokens(_brief_text(brief))
    entry_tokens = _normalize_tokens(
        " ".join(
            [
                str(entry.get("category", "")),
                str(entry.get("style", "")),
                str(entry.get("summary", "")),
                str(entry.get("title", "")),
            ]
        )
    )
    overlap = brief_tokens & entry_tokens
    if overlap:
        overlap_score = min(0.45, 0.08 * len(overlap))
        score += overlap_score
        reasons.append(f"主题关键词匹配: {', '.join(sorted(list(overlap))[:3])}")

    tone = str(brief.get("tone", "") or "")
    tempo_hint = _tone_to_tempo(tone)
    entry_tempo = entry.get("tempo")
    if tempo_hint and entry_tempo == tempo_hint:
        score += 0.2
        reasons.append(f"节奏气质匹配 ({tempo_hint})")

    selling_points = brief.get("sellingPoints") if isinstance(brief.get("sellingPoints"), list) else []
    slot_pattern = str(entry.get("slotPattern", ""))
    if len(selling_points) >= 3 and any(role in slot_pattern for role in ("benefit", "proof")):
        score += 0.1
        reasons.append("多卖点 brief 适配 benefit/proof 结构")

    if structure is not None:
        from knowledge.index_builder import extract_slot_pattern

        sample_pattern = extract_slot_pattern(structure)
        if sample_pattern != "unknown" and sample_pattern == slot_pattern:
            score += 0.15
            reasons.append("与样例结构模式一致")

    if source_project_id and entry.get("sourceProjectId") == source_project_id:
        score -= 0.2
        reasons.append("同源项目降权")

    score = max(0.0, min(1.0, score))
    if not reasons:
        reasons.append("通用结构模板")
    return score, reasons


def rank_knowledge_entries(
    entries: list[dict[str, Any]],
    *,
    brief: dict[str, Any],
    structure: dict[str, Any] | None = None,
    project_id: str | None = None,
    limit: int = 5,
) -> list[dict[str, Any]]:
    scored: list[tuple[float, dict[str, Any], list[str]]] = []
    for entry in entries:
        if entry.get("status") != "published":
            continue
        score, reasons = score_entry_against_brief(
            entry,
            brief=brief,
            structure=structure,
            source_project_id=project_id,
        )
        scored.append((score, entry, reasons))

    scored.sort(key=lambda item: item[0], reverse=True)
    candidates: list[dict[str, Any]] = []
    for score, entry, reasons in scored[:limit]:
        candidates.append(
            {
                "entryId": entry["id"],
                "score": round(score, 3),
                "reasons": reasons,
                "entry": entry,
            }
        )
    return candidates


def build_recommendation(
    *,
    project_id: str,
    entries: list[dict[str, Any]],
    brief: dict[str, Any],
    structure: dict[str, Any] | None = None,
    ranked_entry_ids: list[str] | None = None,
) -> dict[str, Any]:
    candidates = rank_knowledge_entries(
        entries,
        brief=brief,
        structure=structure,
        project_id=project_id,
    )
    if ranked_entry_ids:
        order = {entry_id: index for index, entry_id in enumerate(ranked_entry_ids)}
        candidates.sort(key=lambda item: order.get(item["entryId"], 999))

    suggested = candidates[0]["entryId"] if candidates else ""
    if ranked_entry_ids:
        for entry_id in ranked_entry_ids:
            if any(item["entryId"] == entry_id for item in candidates):
                suggested = entry_id
                break

    return {
        "projectId": project_id,
        "candidates": candidates,
        "suggestedPrimaryId": suggested,
        "computedAt": _utc_now_iso(),
    }


KnowledgeSelectorFn = Callable[
    [dict[str, Any], list[dict[str, Any]]],
    list[str],
]
