from app.render.aspect_ratio import (
    default_aspect_ratio_for_duration,
    pexels_orientation,
    render_dimensions,
    resolve_aspect_ratio,
    subtitle_layout,
)


def test_default_aspect_ratio_by_duration() -> None:
    assert default_aspect_ratio_for_duration(45) == "9:16"
    assert default_aspect_ratio_for_duration(60) == "9:16"
    assert default_aspect_ratio_for_duration(61) == "16:9"
    assert default_aspect_ratio_for_duration(179) == "16:9"


def test_resolve_aspect_ratio_prefers_brief_override() -> None:
    assert (
        resolve_aspect_ratio(
            {"aspectRatio": "1:1"},
            target_sec=180,
        )
        == "1:1"
    )


def test_resolve_aspect_ratio_falls_back_to_duration_default() -> None:
    assert resolve_aspect_ratio({}, target_sec=30) == "9:16"
    assert resolve_aspect_ratio(None, target_sec=120) == "16:9"


def test_render_dimensions_and_pexels_orientation() -> None:
    assert render_dimensions("9:16") == (1080, 1920)
    assert render_dimensions("16:9") == (1920, 1080)
    assert render_dimensions("1:1") == (1080, 1080)
    assert pexels_orientation("16:9") == "landscape"
    assert pexels_orientation("9:16") == "portrait"


def test_subtitle_layout_varies_by_aspect() -> None:
    portrait = subtitle_layout("9:16")
    landscape = subtitle_layout("16:9")
    assert portrait["bottomPaddingPx"] > landscape["bottomPaddingPx"]
