from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.composition.acp.agent_registry import fake_agent_command
from app.composition.acp.author import author_material_spec_via_acp
from app.composition.acp.fs_bridge import FsBridge, PathConfinementError
from app.composition.acp.trace import AcpAuthorTraceRecorder
from composition.paths import detect_repo_root
from composition.types import AuthorRequest


@pytest.fixture
def repo_root() -> Path:
    return detect_repo_root()


def test_fs_bridge_rejects_escape(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    bridge = FsBridge(allowed_roots=[allowed])
    inside = allowed / "ok.txt"
    bridge.write_text(str(inside), "hello")
    assert bridge.read_text(str(inside)) == "hello"
    outside = tmp_path / "outside.txt"
    with pytest.raises(PathConfinementError):
        bridge.read_text(str(outside))


def test_author_material_spec_via_acp_fake_agent(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_TIMEOUT_SEC", "120")
    monkeypatch.setenv("VM_ACP_FIXTURE_LINT", "1")
    scratch = tmp_path / "scratch"
    storage_root = tmp_path / "storage"
    trace = AcpAuthorTraceRecorder.create(
        storage_root,
        project_id="proj-acp",
        acp_agent="fake",
        task_id="task-1",
        generation_id="gen-1",
    )
    request = AuthorRequest(
        project_id="proj-acp",
        generation_id="gen-1",
        task_id="task-1",
        slot={
            "role": "benefit_card",
            "scriptIntent": "show benefits",
            "visualIntent": "card motion",
        },
        aspect_ratio="9:16",
    )
    spec = author_material_spec_via_acp(
        request,
        repo_root=repo_root,
        scratch_dir=scratch,
        agent_command=fake_agent_command(),
        trace=trace,
    )
    assert spec["template"] == "benefit-card"
    assert (scratch / "material-spec.json").is_file()
    outcome = json.loads((trace.trace_dir / "outcome.json").read_text(encoding="utf-8"))
    assert outcome["valid"] is True
    assert outcome["backend"] == "acp"
