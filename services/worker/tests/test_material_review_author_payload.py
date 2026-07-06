from __future__ import annotations

import json
from pathlib import Path

from app.pipelines.material_review_finalize import _build_author_payload
from composition.author.payload import build_material_author_user_payload
from composition.types import AuthorRequest


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


def test_gate_revise_payload_includes_author_contract() -> None:
    payload = build_material_author_user_payload(
        AuthorRequest(
            slot={"role": "proof", "scriptIntent": "quote"},
            finish_brief={
                "renderPolicy": {"allowedDisplayCopy": ["价值对等"]},
            },
            material_edit_mode="full",
            edit_instruction="请加核心文字重新生成",
            existing_spec_hash="abc123",
            author_contract={
                "displayCopyMode": "allowed_list",
                "allowedDisplayCopy": ["价值对等"],
                "materialEditMode": "full",
                "mustChangeSpec": True,
            },
            existing_material_spec={"template": "composition", "durationSec": 3.0},
        )
    )
    assert payload["authorContract"]["mustChangeSpec"] is True
    assert payload["existingSpecHash"] == "abc123"
    assert "existingMaterialSpec" not in payload
