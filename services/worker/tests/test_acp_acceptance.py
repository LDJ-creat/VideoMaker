from __future__ import annotations

import json
import time
from pathlib import Path

from app.composition.acp.acceptance import accept_acp_author_result
from app.pipelines.material_review import material_spec_content_hash
from app.pipelines.material_slot_revise import clear_acp_scratch_for_gate_revise


def test_clear_acp_scratch_removes_spec_and_marker(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    scratch = generation_root / "acp-author" / "slot-5"
    scratch.mkdir(parents=True)
    for name in (
        "material-spec.json",
        "material-spec.lint-passed",
        "material-review-marker.json",
        "_draft_spec.json",
    ):
        (scratch / name).write_text("{}", encoding="utf-8")

    clear_acp_scratch_for_gate_revise(generation_root, "slot-5")

    assert not (scratch / "material-spec.json").exists()
    assert not (scratch / "material-review-marker.json").exists()
    assert scratch.is_dir()


def test_accept_acp_author_result_rejects_unchanged_spec_hash(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    spec = {"template": "composition", "durationSec": 3.0, "composition": {"bodyHtml": "<div>x</div>"}}
    spec_path = scratch / "material-spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    (scratch / "material-spec.lint-passed").write_text("ok\n", encoding="utf-8")
    started = time.time()
    spec_hash = material_spec_content_hash(spec)
    ok, errors, hints = accept_acp_author_result(
        spec=spec,
        scratch_dir=scratch,
        author_started=started,
        author_payload={
            "materialGateRevise": {"source": "material_gate_revise"},
            "authorContract": {"mustChangeSpec": True},
            "existingSpecHash": spec_hash,
        },
        agent_diagnostics={"agentExitCode": 0},
    )
    assert not ok
    assert "regression_unchanged_spec" in hints
    assert errors


def test_accept_acp_author_result_rejects_stale_spec(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    spec = {"template": "composition", "durationSec": 3.0, "composition": {"bodyHtml": "<div>new</div>"}}
    spec_path = scratch / "material-spec.json"
    spec_path.write_text(json.dumps(spec), encoding="utf-8")
    old = time.time() - 60
    import os

    os.utime(spec_path, (old, old))
    (scratch / "material-spec.lint-passed").write_text("ok\n", encoding="utf-8")
    ok, _, hints = accept_acp_author_result(
        spec=spec,
        scratch_dir=scratch,
        author_started=time.time(),
        author_payload={},
        agent_diagnostics={"agentExitCode": 0},
    )
    assert not ok
    assert "stale_spec_harvest" in hints


def test_clear_acp_scratch_removes_invoke_mcp(tmp_path: Path) -> None:
    generation_root = tmp_path / "gen"
    scratch = generation_root / "acp-author" / "slot-5"
    scratch.mkdir(parents=True)
    (scratch / "_invoke_mcp.py").write_text("print('bad')\n", encoding="utf-8")
    (scratch / "_invoke_mcp_helper.py").write_text("print('bad')\n", encoding="utf-8")

    clear_acp_scratch_for_gate_revise(generation_root, "slot-5")

    assert not (scratch / "_invoke_mcp.py").exists()
    assert not (scratch / "_invoke_mcp_helper.py").exists()


def test_accept_acp_author_result_rejects_invoke_mcp_script(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    spec = {"template": "composition", "durationSec": 3.0, "composition": {"bodyHtml": "<div>x</div>"}}
    (scratch / "material-spec.json").write_text(json.dumps(spec), encoding="utf-8")
    (scratch / "material-spec.lint-passed").write_text("ok\n", encoding="utf-8")
    (scratch / "_invoke_mcp.py").write_text("bad\n", encoding="utf-8")
    ok, errors, hints = accept_acp_author_result(
        spec=spec,
        scratch_dir=scratch,
        author_started=time.time(),
        author_payload={},
        agent_diagnostics={"agentExitCode": 0},
        session_lint_passed=True,
    )
    assert not ok
    assert "forbidden_helper_script" in hints
    assert any("Forbidden helper scripts" in item for item in errors)
