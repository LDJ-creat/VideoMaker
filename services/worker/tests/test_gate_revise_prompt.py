from __future__ import annotations

import json
from pathlib import Path

from app.composition.acp.gate_revise_prompt import (
    build_gate_revise_prompt_user_payload,
    is_gate_revise_author_payload,
)
from composition.author.payload import build_material_author_user_payload
from composition.types import AuthorRequest


def test_is_gate_revise_author_payload() -> None:
    assert is_gate_revise_author_payload(
        {"materialGateRevise": {"source": "material_gate_revise"}}
    )
    assert is_gate_revise_author_payload(
        {"authorContract": {"mustChangeSpec": True}}
    )
    assert not is_gate_revise_author_payload({"slotId": "slot-1"})


def test_gate_revise_prompt_omits_existing_material_spec(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    reviews = generation_root / "material-reviews" / "slot-5"
    reviews.mkdir(parents=True)
    (reviews / "report.json").write_text(
        json.dumps(
            {
                "approved": False,
                "issues": ["层级混乱"],
                "suggestions": ["加大标题"],
            }
        ),
        encoding="utf-8",
    )
    huge_spec = {
        "template": "composition",
        "durationSec": 8,
        "composition": {"bodyHtml": "x" * 5000, "styles": "", "timelineScript": ""},
    }
    request = AuthorRequest(
        project_id="proj",
        generation_id="gen",
        generation_root=str(generation_root),
        slot={"id": "slot-5", "role": "usage_scene"},
        aspect_ratio="9:16",
        material_edit_mode="full",
        edit_instruction="加入金句",
        existing_spec_hash="abc123",
        existing_material_spec=huge_spec,
        author_contract={"mustChangeSpec": True, "allowedDisplayCopy": ["金句"]},
    )
    full = build_material_author_user_payload(request)
    slim = build_gate_revise_prompt_user_payload(full, generation_root=generation_root)
    slim_text = json.dumps(slim, ensure_ascii=False)
    assert "existingMaterialSpec" not in slim
    assert len(slim_text) < len(json.dumps(full, ensure_ascii=False)) / 2
    assert slim.get("priorReviewSummary", {}).get("issues") == ["层级混乱"]
    assert slim.get("editInstruction") == "加入金句"
