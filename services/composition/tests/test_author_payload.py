from __future__ import annotations

from composition.author.payload import build_material_author_user_payload
from composition.types import AuthorRequest


def test_build_material_author_user_payload_includes_render_target_and_slot_timing() -> None:
    payload = build_material_author_user_payload(
        AuthorRequest(
            slot={"id": "slot-1", "role": "hook_visual"},
            aspect_ratio="9:16",
            slot_timing={"startSec": 0.0, "endSec": 5.2, "durationSec": 5.2},
        )
    )
    assert payload["renderTarget"] == {
        "aspectRatio": "9:16",
        "width": 1080,
        "height": 1920,
    }
    assert payload["slotTiming"]["durationSec"] == 5.2


def test_build_material_author_user_payload_16_9_dimensions() -> None:
    payload = build_material_author_user_payload(
        AuthorRequest(slot={"id": "slot-1"}, aspect_ratio="16:9")
    )
    assert payload["renderTarget"]["width"] == 1920
    assert payload["renderTarget"]["height"] == 1080
