from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.pipelines.generation_pipeline import run_generating_material


def test_run_generating_material_visual_only_calls_finalize_without_legacy_kwargs(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true")
    generation_root = tmp_path / "gen"
    generated_root = generation_root / "generated"
    generated_root.mkdir(parents=True)
    slot_id = "usage"
    action_id = "action-usage-stock"
    (generated_root / f"{slot_id}-stock.mp4").write_bytes(b"\x00" * 120_000)
    plan = {
        "id": "gen-1",
        "projectId": "proj",
        "variant": "high_click",
        "storyboard": [{"slotId": slot_id, "startSec": 0, "endSec": 4}],
        "completionActions": [
            {"id": action_id, "slotId": slot_id, "provider": "stock_media_search"},
        ],
    }
    structure = {"slots": [{"id": slot_id, "role": "usage_scene"}]}
    inventory: dict = {}
    slot_matches: list = []

    captured: dict = {}

    def _capture_finalize(**kwargs):  # noqa: ANN003
        captured.update(kwargs)

    with patch(
        "app.pipelines.material_review_finalize.finalize_visual_material_reviews",
        side_effect=_capture_finalize,
    ):
        run_generating_material(
            plan=plan,
            inventory=inventory,
            slot_matches=slot_matches,
            structure=structure,
            generation_root=generation_root,
            render_root=generation_root,
            gateway=MagicMock(),
            emit_progress=lambda *_args, **_kwargs: None,
            register_artifact=lambda *_args, **_kwargs: {},
            visual_only=True,
        )

    assert captured
    assert captured["generation_root"] == generation_root
    assert captured["generated_root"] == generated_root
    assert "gateway" not in captured
    assert "runner" not in captured
    assert "store" not in captured
