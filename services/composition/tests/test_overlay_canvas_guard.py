from __future__ import annotations

from composition.author.overlay_canvas_guard import (
    check_hf_native_no_external_base_video,
    check_source_then_polish_overlay_composition,
)

_HF_NATIVE_PAYLOAD = {
    "finishBrief": {"completionMode": "hf_native"},
    "compositionAuthorBrief": {"mode": "hf_native"},
}

_OVERLAY_PAYLOAD = {
    "finishBrief": {"completionMode": "source_then_polish"},
}


def test_hf_native_rejects_external_base_video_mp4() -> None:
    spec = {
        "template": "composition",
        "composition": {
            "bodyHtml": '<video id="base-video" src="clip.mp4"></video>',
            "styles": "",
            "timelineScript": "",
        },
    }
    errors = check_hf_native_no_external_base_video(spec, _HF_NATIVE_PAYLOAD)
    assert errors


def test_source_then_polish_requires_base_video_tag() -> None:
    spec = {
        "template": "composition",
        "composition": {
            "bodyHtml": '<div class="vm-overlay">text</div>',
            "styles": "",
            "timelineScript": "",
        },
    }
    errors = check_source_then_polish_overlay_composition(spec, _OVERLAY_PAYLOAD)
    assert any("base-video" in item for item in errors)


def test_source_then_polish_rejects_fullscreen_black_scrim() -> None:
    spec = {
        "template": "composition",
        "composition": {
            "bodyHtml": '<video id="base-video" src="clip.mp4"></video><div class="vm-scrim"></div>',
            "styles": ".vm-scrim { background: #000; }",
            "timelineScript": "",
        },
    }
    errors = check_source_then_polish_overlay_composition(spec, _OVERLAY_PAYLOAD)
    assert any("opaque black scrim" in item for item in errors)
