from __future__ import annotations

VALID_ASPECT_RATIOS = frozenset({"9:16", "16:9", "1:1"})


def render_dimensions(aspect_ratio: str) -> tuple[int, int]:
    if aspect_ratio == "16:9":
        return 1920, 1080
    if aspect_ratio == "1:1":
        return 1080, 1080
    return 1080, 1920
