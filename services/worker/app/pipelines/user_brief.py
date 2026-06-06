from __future__ import annotations

from typing import Any

VALID_CONTENT_CATEGORIES = frozenset(
    {
        "product_commerce",
        "education",
        "vlog_lifestyle",
        "brand_story",
        "tutorial",
        "entertainment",
        "news_commentary",
        "general",
    }
)


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def infer_content_category(raw: dict[str, Any]) -> str:
    category = raw.get("contentCategory")
    if isinstance(category, str) and category in VALID_CONTENT_CATEGORIES:
        return category
    product_name = str(raw.get("productName") or raw.get("subjectName") or "").strip()
    selling_points = _as_string_list(raw.get("sellingPoints"))
    key_points = _as_string_list(raw.get("keyPoints"))
    if product_name or selling_points or key_points:
        return "product_commerce"
    return "general"


def normalize_user_brief(raw: dict[str, Any] | None) -> dict[str, Any]:
    source = dict(raw or {})
    subject_name = str(source.get("subjectName") or source.get("productName") or "").strip()
    key_points = _as_string_list(source.get("keyPoints"))
    selling_points = _as_string_list(source.get("sellingPoints"))
    if not key_points and selling_points:
        key_points = list(selling_points)
    if not selling_points and key_points:
        selling_points = list(key_points)

    normalized: dict[str, Any] = {
        "contentCategory": infer_content_category(source),
        "sellingPoints": selling_points,
        "mustMention": _as_string_list(source.get("mustMention")),
        "avoidMention": _as_string_list(source.get("avoidMention")),
    }

    topic = str(source.get("topic") or "").strip()
    if topic:
        normalized["topic"] = topic
    creative_goal = str(source.get("creativeGoal") or "").strip()
    if creative_goal:
        normalized["creativeGoal"] = creative_goal
    if subject_name:
        normalized["subjectName"] = subject_name
        normalized["productName"] = subject_name
    if key_points:
        normalized["keyPoints"] = key_points
    target_audience = str(source.get("targetAudience") or "").strip()
    if target_audience:
        normalized["targetAudience"] = target_audience
    tone = str(source.get("tone") or "").strip()
    if tone:
        normalized["tone"] = tone
    supplemental = str(source.get("supplementalNotes") or "").strip()
    if supplemental:
        normalized["supplementalNotes"] = supplemental
    return normalized


def build_baseline_extracted_facts(brief: dict[str, Any]) -> list[dict[str, Any]]:
    extracted_facts: list[dict[str, Any]] = []
    fact_index = 1

    key_points = _as_string_list(brief.get("keyPoints") or brief.get("sellingPoints"))
    seen_texts: set[tuple[str, str]] = set()

    for point in key_points:
        key = ("key_message", point)
        if key in seen_texts:
            continue
        seen_texts.add(key)
        extracted_facts.append(
            {
                "id": f"fact-{fact_index}",
                "kind": "key_message",
                "text": point,
                "source": "brief.keyPoints",
            }
        )
        fact_index += 1

    for point in _as_string_list(brief.get("sellingPoints")):
        key = ("selling_point", point)
        if key in seen_texts:
            continue
        if ("key_message", point) in seen_texts:
            continue
        seen_texts.add(key)
        extracted_facts.append(
            {
                "id": f"fact-{fact_index}",
                "kind": "selling_point",
                "text": point,
                "source": "brief.sellingPoints",
            }
        )
        fact_index += 1

    creative_goal = str(brief.get("creativeGoal") or "").strip()
    if creative_goal:
        extracted_facts.append(
            {
                "id": f"fact-{fact_index}",
                "kind": "goal",
                "text": creative_goal,
                "source": "brief.creativeGoal",
            }
        )
        fact_index += 1

    if brief.get("targetAudience"):
        extracted_facts.append(
            {
                "id": f"fact-{fact_index}",
                "kind": "audience",
                "text": str(brief["targetAudience"]),
                "source": "brief.targetAudience",
            }
        )
        fact_index += 1

    for text in _as_string_list(brief.get("mustMention")):
        extracted_facts.append(
            {
                "id": f"fact-{fact_index}",
                "kind": "constraint",
                "text": text,
                "source": "brief.mustMention",
            }
        )
        fact_index += 1

    for text in _as_string_list(brief.get("avoidMention")):
        extracted_facts.append(
            {
                "id": f"fact-{fact_index}",
                "kind": "constraint",
                "text": text,
                "source": "brief.avoidMention",
            }
        )
        fact_index += 1

    supplemental = str(brief.get("supplementalNotes") or "").strip()
    if supplemental:
        extracted_facts.append(
            {
                "id": f"fact-{fact_index}",
                "kind": "other",
                "text": supplemental,
                "source": "brief.supplementalNotes",
            }
        )

    return extracted_facts
