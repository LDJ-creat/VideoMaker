from __future__ import annotations


def normalize_scene_start_end(start_sec: float, end_sec: float) -> tuple[float, float, float]:
    start = float(start_sec)
    end = float(end_sec)
    if end < start:
        start, end = end, start
    duration = max(0.5, end - start)
    return round(start, 3), round(end, 3), round(duration, 3)
