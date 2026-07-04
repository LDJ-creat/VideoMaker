from __future__ import annotations

import json

import pytest


def test_validate_review_marker_requires_approved_spec_hash(tmp_path):
    from composition.material_review.session import validate_review_marker, write_review_marker

    spec = {"template": "benefit-card", "durationSec": 3, "params": {"title": "A"}}
    write_review_marker(
        tmp_path,
        spec=spec,
        report={"approved": True, "issues": [], "suggestions": []},
    )
    assert validate_review_marker(tmp_path, spec) is None
    mutated = {**spec, "durationSec": 4}
    assert validate_review_marker(tmp_path, mutated) is not None


def test_write_material_spec_rejects_without_review_marker(tmp_path, monkeypatch):
    monkeypatch.setenv("VIDEOMAKER_MCP_WRITE_SKIP_LINT", "true")
    from composition.mcp.context import McpSessionContext
    from composition.mcp.handlers import handle_write_material_spec

    ctx = McpSessionContext(
        scratch_dir=tmp_path,
        repo_root=tmp_path,
        author_payload={
            "slot": {"id": "hook", "role": "hook_visual", "scriptIntent": "", "visualIntent": ""},
            "renderPolicy": {"forbidVoiceoverText": True, "forbidBriefVerbatim": True, "allowedDisplayCopy": []},
        },
        aspect_ratio="9:16",
        asset_root=None,
    )
    spec = {"template": "benefit-card", "durationSec": 3, "params": {"title": "", "bullets": []}}
    payload = json.loads(handle_write_material_spec(ctx, spec_json=spec))
    assert payload["ok"] is False
    assert any("review_material_preview" in str(item) for item in payload.get("errors", []))
