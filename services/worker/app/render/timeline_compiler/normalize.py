from __future__ import annotations

from app.render.render_timeline_to_hyperframes import _normalize_timeline

__all__ = ["normalize_timeline"]


def normalize_timeline(timeline: dict) -> dict:
    return _normalize_timeline(timeline)
