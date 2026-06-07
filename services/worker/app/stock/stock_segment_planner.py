from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

LONG_SLOT_THRESHOLD_SEC = 18.0
MIN_SEGMENT_SEC = 4.0
MAX_SEGMENTS = 4

_SOCIAL_SCENE_MARKERS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"商务饭局"), "business dinner networking table conversation"),
    (re.compile(r"朋友聚会"), "friends party social gathering conversation"),
    (re.compile(r"家庭聚餐"), "family dinner gathering table conversation"),
]

_DEMO_SCENE_MARKERS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"接话句型|手写.*笔记|笔记画面"), "handwriting conversation tips notebook close up"),
    (re.compile(r"备忘录|话题池|手机.*界面"), "smartphone notes app typing close up lifestyle"),
    (re.compile(r"手机"), "smartphone screen close up lifestyle"),
]


@dataclass(frozen=True)
class StockSegment:
    query: str
    duration_sec: float
    label: str = ""


def _collect_marker_queries(text: str, markers: list[tuple[re.Pattern[str], str]]) -> list[str]:
    queries: list[str] = []
    for pattern, query_hint in markers:
        if pattern.search(text):
            queries.append(query_hint)
    return queries


def _even_segments(primary_query: str, *, target_duration_sec: float, count: int) -> list[StockSegment]:
    count = max(2, min(MAX_SEGMENTS, count))
    per_segment = target_duration_sec / count
    segments: list[StockSegment] = []
    for index in range(count):
        label = f"part-{index + 1}"
        query = primary_query if index == 0 else f"{primary_query} {label}"
        segments.append(
            StockSegment(
                query=query.strip(),
                duration_sec=per_segment,
                label=label,
            )
        )
    return segments


def build_stock_segments(
    *,
    slot: dict[str, Any],
    scene: dict[str, Any] | None,
    primary_query: str,
    target_duration_sec: float,
) -> list[StockSegment]:
    """Plan one or more Pexels queries for a slot, splitting long multi-scene storyboards."""
    query = str(primary_query or "").strip()
    if not query:
        query = "lifestyle b-roll footage"

    duration = max(MIN_SEGMENT_SEC, float(target_duration_sec))
    if duration < LONG_SLOT_THRESHOLD_SEC:
        return [StockSegment(query=query, duration_sec=duration)]

    visual = str((scene or {}).get("visual", ""))
    script = str((scene or {}).get("script", ""))
    text = f"{visual} {script}".strip()

    marker_queries = _collect_marker_queries(text, _SOCIAL_SCENE_MARKERS)
    if len(marker_queries) < 2:
        marker_queries = _collect_marker_queries(text, _DEMO_SCENE_MARKERS)

    if len(marker_queries) >= 2:
        per_segment = duration / len(marker_queries[:MAX_SEGMENTS])
        return [
            StockSegment(query=marker_query, duration_sec=per_segment, label=f"scene-{index + 1}")
            for index, marker_query in enumerate(marker_queries[:MAX_SEGMENTS])
        ]

    segment_count = min(MAX_SEGMENTS, max(2, int(round(duration / 15.0))))
    return _even_segments(query, target_duration_sec=duration, count=segment_count)
