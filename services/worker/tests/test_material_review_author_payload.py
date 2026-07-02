from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.material_review_finalize import _build_author_payload


def test_build_author_payload_merges_acp_task_json(tmp_path: Path) -> None:
    generation_root = tmp_path / "generations" / "gen-1"
    slot_id = "slot-2"
    task_dir = generation_root / "acp-author" / slot_id
    task_dir.mkdir(parents=True)
    task_dir.joinpath("task.json").write_text(
        json.dumps(
            {
                "slot": {"role": "proof", "creativeDirection": {"visualGoal": "centered quote"}},
                "finishBrief": {"finishIntent": "center quote card"},
                "compositionAuthorBrief": {"authorPrompt": "HF motion only"},
                "renderPolicy": {"allowedDisplayCopy": ["认知差"]},
                "visualStyleBible": {"mood": "warm"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = _build_author_payload(
        project_id="project-1",
        generation_id="gen-1",
        generation_root=generation_root,
        task_id="task-1",
        slot_id=slot_id,
        slot_timing={"durationSec": 4.8},
    )

    assert payload["finishBrief"]["finishIntent"] == "center quote card"
    assert payload["compositionAuthorBrief"]["authorPrompt"] == "HF motion only"
    assert payload["renderPolicy"]["allowedDisplayCopy"] == ["认知差"]
    assert payload["slot"]["role"] == "proof"
