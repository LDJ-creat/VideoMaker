from __future__ import annotations

from typing import Any

from app.stock.stock_eligibility import normalize_query_tokens, stock_match_min_score


def _item_text(item: dict[str, Any], *, media_type: str) -> str:
    if media_type == "photo":
        return str(item.get("alt", ""))
    tags = item.get("tags") or []
    if isinstance(tags, list):
        return " ".join(str(tag) for tag in tags)
    return ""


def score_stock_candidate(
    *,
    query: str,
    item: dict[str, Any],
    media_type: str,
    target_duration_sec: float | None = None,
    orientation: str | None = None,
) -> float:
    query_tokens = normalize_query_tokens(query)
    if not query_tokens:
        return 0.0

    text_tokens = normalize_query_tokens(_item_text(item, media_type=media_type))
    if not text_tokens:
        text_tokens = query_tokens

    overlap = len(query_tokens & text_tokens)
    score = overlap / max(len(query_tokens), 1)

    if media_type == "video" and target_duration_sec is not None:
        duration = float(item.get("duration") or 0.0)
        if duration > 0:
            ratio = duration / max(target_duration_sec, 0.5)
            if 0.7 <= ratio <= 1.5:
                score += 0.15
            elif ratio < 0.5:
                score -= 0.1

    if orientation and media_type == "photo":
        width = int(item.get("width") or 0)
        height = int(item.get("height") or 0)
        if width > 0 and height > 0:
            if orientation == "portrait" and height > width:
                score += 0.05
            elif orientation == "landscape" and width >= height:
                score += 0.05
            elif orientation == "square" and abs(width - height) <= min(width, height) * 0.1:
                score += 0.05

    return min(1.0, max(0.0, score))


def pick_best_candidate(
    *,
    query: str,
    photos: list[dict[str, Any]],
    videos: list[dict[str, Any]],
    prefer_video: bool,
    target_duration_sec: float | None = None,
    orientation: str | None = None,
) -> tuple[dict[str, Any] | None, str | None, float]:
    min_score = stock_match_min_score()
    best: dict[str, Any] | None = None
    best_type: str | None = None
    best_score = 0.0

    ordered: list[tuple[str, list[dict[str, Any]]]] = []
    if prefer_video:
        ordered.append(("video", videos))
        ordered.append(("photo", photos))
    else:
        ordered.append(("photo", photos))
        ordered.append(("video", videos))

    for media_type, items in ordered:
        for item in items:
            score = score_stock_candidate(
                query=query,
                item=item,
                media_type=media_type,
                target_duration_sec=target_duration_sec,
                orientation=orientation,
            )
            if score >= min_score and score > best_score:
                best = item
                best_type = media_type
                best_score = score

    return best, best_type, best_score
