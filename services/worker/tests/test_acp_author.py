from __future__ import annotations

import json
import time
from pathlib import Path

from unittest.mock import MagicMock

import pytest

from app.composition.acp.agent_registry import fake_agent_command
from app.composition.acp.author import (
    _build_prompt_text,
    _harvest_material_spec,
    _resolve_template_mode,
    acp_timeout_sec,
    author_material_spec_via_acp,
)
from app.composition.acp.fs_bridge import FsBridge, PathConfinementError
from app.composition.acp.trace import AcpAuthorTraceRecorder
from app.observability.acp_author_recorder import AcpAuthorObservabilityContext
from app.observability.sink import LocalFileSink
from app.runtime.agent_run_store import AgentRunStore
from composition.paths import detect_repo_root
from composition.types import AuthorRequest


@pytest.fixture
def repo_root() -> Path:
    return detect_repo_root()


def test_acp_timeout_default_by_template(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIDEOMAKER_COMPOSITION_ACP_TIMEOUT_SEC", raising=False)
    assert acp_timeout_sec(composition_template=True) == 1800.0
    assert acp_timeout_sec(composition_template=False) == 600.0
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_TIMEOUT_SEC", "900")
    assert acp_timeout_sec(composition_template=True) == 900.0


def test_resolve_template_mode_from_composition_brief() -> None:
    payload = {"compositionAuthorBrief": {"authorPrompt": "motion only"}}
    assert _resolve_template_mode(payload) == "composition"


def test_acp_prompt_includes_execution_discipline(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_ACP_SMOKE_SIMPLE", "false")
    monkeypatch.setenv("VIDEOMAKER_ACP_SMOKE_FORCE_TEMPLATE", "composition")
    monkeypatch.delenv("VIDEOMAKER_COMPOSITION_ACP_AGENT", raising=False)
    system, user, composition_template = _build_prompt_text(
        AuthorRequest(
            project_id="proj-acp",
            generation_id="gen-1",
            slot={"role": "hook_visual"},
            aspect_ratio="9:16",
            slot_timing={"durationSec": 5},
        ),
        repo_root,
        scratch_dir=repo_root / "storage" / "scratch" / "pytest-acp-prompt",
    )
    assert composition_template is True
    assert "ACP execution" in system
    assert "Forbidden: exploring repo source" in system
    assert "Workflow: required skill_view" in user
    assert "terminal lint-spec only" not in user  # default agent, not codex
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_AGENT", "codex")
    _, user_codex, _ = _build_prompt_text(
        AuthorRequest(
            project_id="proj-acp",
            generation_id="gen-1",
            slot={"role": "hook_visual"},
            aspect_ratio="9:16",
            slot_timing={"durationSec": 5},
        ),
        repo_root,
        scratch_dir=repo_root / "storage" / "scratch" / "pytest-acp-prompt",
    )
    assert "terminal lint-spec only" in user_codex


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


def test_harvest_material_spec_from_fallback(tmp_path: Path, repo_root: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    fallback = repo_root / "storage" / "scratch" / "pytest-acp-fallback"
    fallback.mkdir(parents=True, exist_ok=True)
    payload = {"template": "benefit-card", "durationSec": 8, "params": {"title": "Harvest"}}
    (fallback / "material-spec.json").write_text(json.dumps(payload), encoding="utf-8")
    found = _harvest_material_spec(scratch, repo_root, not_before=time.time() - 30)
    assert found is not None
    assert found == scratch / "material-spec.json"
    assert json.loads(found.read_text(encoding="utf-8"))["durationSec"] == 8


def test_author_material_spec_via_acp_fake_agent(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_TIMEOUT_SEC", "120")
    monkeypatch.setenv("VM_ACP_FIXTURE_LINT", "1")
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_LINT_CACHE", "true")
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


def test_author_material_spec_via_acp_records_observability_tool_runs(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_TIMEOUT_SEC", "120")
    monkeypatch.setenv("VM_ACP_FIXTURE_LINT", "1")
    scratch = tmp_path / "scratch"
    storage_root = tmp_path / "storage"
    sink = LocalFileSink(AgentRunStore(storage_root))
    trace = AcpAuthorTraceRecorder.create(
        storage_root,
        project_id="proj-acp",
        acp_agent="fake",
        task_id="task-1",
        generation_id="gen-1",
    )
    observability = AcpAuthorObservabilityContext.from_trace(
        sink=sink,
        trace_dir=trace.trace_dir,
        project_id="proj-acp",
        task_id="task-1",
        generation_id="gen-1",
        slot_id="slot-benefit",
        acp_agent="fake",
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
    author_material_spec_via_acp(
        request,
        repo_root=repo_root,
        scratch_dir=scratch,
        agent_command=fake_agent_command(),
        trace=trace,
        observability=observability,
    )

    tool_dir = storage_root / "projects" / "proj-acp" / "logs" / "tool-runs"
    tool_names = {
        json.loads(path.read_text(encoding="utf-8"))["toolName"]
        for path in tool_dir.glob("acp-*.json")
    }
    assert "acp_session_start" in tool_names
    assert "acp_lint_gate" in tool_names
    assert "acp_session_end" in tool_names
    session_payload = json.loads((trace.trace_dir / "session.json").read_text(encoding="utf-8"))
    assert session_payload.get("observabilityRunId") == trace.run_id


def test_acp_lint_repair_retries_after_post_turn_failure(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.composition.acp import author as author_module

    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_TIMEOUT_SEC", "120")
    monkeypatch.setenv("VM_ACP_FIXTURE_LINT", "1")
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_LINT_REPAIR_MAX", "1")
    scratch = tmp_path / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    spec_payload = {
        "template": "benefit-card",
        "durationSec": 8,
        "params": {
            "title": "Retry",
            "bullets": ["A"],
            "colors": {"primary": "#2563eb", "background": "#0f172a", "text": "#ffffff"},
        },
    }
    (scratch / "material-spec.json").write_text(json.dumps(spec_payload), encoding="utf-8")

    session_calls: list[int] = []

    async def fake_run_session(**kwargs: object) -> None:
        _ = kwargs
        session_calls.append(1)

    lint_calls = {"n": 0}

    def fake_lint_after_turn(*args: object, **kwargs: object) -> tuple[list[str], bool]:
        _ = args, kwargs
        lint_calls["n"] += 1
        if lint_calls["n"] == 1:
            return ["simulated lint failure"], False
        return [], False

    monkeypatch.setattr(author_module, "_run_acp_session", fake_run_session)
    monkeypatch.setattr(author_module, "_harvest_material_spec", lambda *_a, **_k: scratch / "material-spec.json")
    monkeypatch.setattr(author_module, "_lint_spec_after_turn", fake_lint_after_turn)

    storage_root = tmp_path / "storage"
    sink = LocalFileSink(AgentRunStore(storage_root))
    trace = AcpAuthorTraceRecorder.create(
        storage_root,
        project_id="proj-acp",
        acp_agent="fake",
        generation_id="gen-1",
    )
    observability = AcpAuthorObservabilityContext.from_trace(
        sink=sink,
        trace_dir=trace.trace_dir,
        project_id="proj-acp",
        task_id=None,
        generation_id="gen-1",
        slot_id="slot-1",
        acp_agent="fake",
    )

    spec = author_material_spec_via_acp(
        AuthorRequest(
            project_id="proj-acp",
            generation_id="gen-1",
            slot={"role": "benefit_card"},
            aspect_ratio="9:16",
        ),
        repo_root=repo_root,
        scratch_dir=scratch,
        agent_command=fake_agent_command(),
        observability=observability,
    )
    assert spec["params"]["title"] == "Retry"
    assert len(session_calls) == 2

    payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (storage_root / "projects" / "proj-acp" / "logs" / "tool-runs").glob("*.json")
    ]
    end_payload = next(item for item in payloads if item["toolName"] == "acp_session_end")
    assert end_payload["metadata"]["repairAttempt"] == 1
