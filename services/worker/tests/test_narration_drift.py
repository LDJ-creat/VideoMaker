from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

from app.pipelines.narration_drift import (
    build_drift_report,
    run_narration_drift_resolution,
    save_estimated_snapshot,
)
from app.pipelines.script_draft import empty_script_draft, save_script_draft
from app.runtime.task_context import TaskContext


def _structure() -> dict:
    return {
        "slots": [
            {"id": "slot-1", "role": "hook"},
            {"id": "slot-2", "role": "usage_scene"},
        ]
    }


def test_build_drift_report_flags_word_count_high() -> None:
    storyboard = [
        {"slotId": "slot-1", "startSec": 0.0, "endSec": 2.0, "script": "这是一段明显偏长的口播文案" * 5},
        {"slotId": "slot-2", "startSec": 2.0, "endSec": 5.0, "script": "正常长度"},
    ]
    estimated = {"slot-1": 4.0, "slot-2": 3.0}
    timing = {
        "durationSec": 5.0,
        "sceneTiming": [
            {"slotId": "slot-1", "startSec": 0.0, "endSec": 1.0},
            {"slotId": "slot-2", "startSec": 1.0, "endSec": 5.0},
        ],
    }
    draft = {"durationTargetSec": 30.0, "storyboard": storyboard}
    report = build_drift_report(
        generation_id="gen-1",
        content_hash="sha256:test",
        draft=draft,
        structure=_structure(),
        timing=timing,
        estimated_by_slot=estimated,
    )
    slot1 = next(item for item in report["slots"] if item["slotId"] == "slot-1")
    assert slot1["rootCause"] == "word_count_high"
    assert "drift_warn" in slot1["warnings"] or "drift_strong" in slot1["warnings"]


def test_build_drift_report_flags_duration_target_overrun() -> None:
    report = build_drift_report(
        generation_id="gen-1",
        content_hash="hash",
        draft={
            "durationTargetSec": 20.0,
            "storyboard": [
                {
                    "slotId": "slot-1",
                    "script": "这是一段明显偏长的口播文案" * 8,
                    "startSec": 0.0,
                    "endSec": 25.0,
                }
            ],
        },
        structure=_structure(),
        timing={
            "durationSec": 25.0,
            "sceneTiming": [{"slotId": "slot-1", "startSec": 0.0, "endSec": 25.0}],
        },
        estimated_by_slot={"slot-1": 10.0},
    )
    assert report["totalDurationOverTarget"] is True
    assert report["overTargetSec"] == 25.0 - 20.0
    slot1 = next(item for item in report["slots"] if item["slotId"] == "slot-1")
    assert slot1["rootCause"] == "word_count_high"


def test_run_narration_drift_resolution_writes_drift_report(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    generation_root.mkdir()
    draft = empty_script_draft(
        generation_id="gen-1",
        project_id="proj-1",
        variant="high_click",
        duration_target_sec=30.0,
    )
    draft["masterNarration"] = "master"
    draft["masterNarrationStatus"] = "approved"
    draft["storyboardStatus"] = "approved"
    draft["storyboard"] = [
        {
            "id": "scene-1",
            "slotId": "slot-2",
            "startSec": 0.0,
            "endSec": 6.0,
            "script": "正常口播长度",
            "visual": "visual",
            "source": "text_completion",
            "compositionAuthorBrief": {
                "mode": "hf_native",
                "authorPrompt": "base prompt",
            },
        }
    ]
    save_script_draft(generation_root, draft)
    save_estimated_snapshot(
        generation_root,
        [{"slotId": "slot-2", "startSec": 0.0, "endSec": 2.0, "script": "old"}],
    )
    timing = {
        "durationSec": 6.0,
        "contentHash": "sha256:test",
        "sceneTiming": [{"slotId": "slot-2", "startSec": 0.0, "endSec": 6.0}],
    }
    context = TaskContext(
        task_id="task-1",
        project_id="proj-1",
        storage_root=tmp_path,
    )
    report = run_narration_drift_resolution(
        generation_root=generation_root,
        structure=_structure(),
        timing=timing,
        context=context,
        generation_id="gen-1",
    )
    assert (generation_root / "narration" / "drift-report.json").is_file()
    slot2 = next(item for item in report["slots"] if item["slotId"] == "slot-2")
    assert slot2["resolutionPath"] == "visual_adapt"
    draft_after = json.loads((generation_root / "script-draft.json").read_text(encoding="utf-8"))
    brief = draft_after["storyboard"][0]["compositionAuthorBrief"]
    assert "timingContext" in brief
