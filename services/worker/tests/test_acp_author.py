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
    assert "acp_turn_lint_gate" in tool_names
    assert "acp_session_end" in tool_names
    session_payload = json.loads((trace.trace_dir / "session.json").read_text(encoding="utf-8"))
    assert session_payload.get("observabilityRunId") == trace.run_id


def test_acp_prompt_default_not_smoke_simple(
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("VIDEOMAKER_ACP_SMOKE_SIMPLE", raising=False)
    _, user, _ = _build_prompt_text(
        AuthorRequest(
            project_id="proj-acp",
            generation_id="gen-1",
            slot={"role": "hook_visual"},
            aspect_ratio="9:16",
        ),
        repo_root,
        scratch_dir=repo_root / "storage" / "scratch" / "pytest-acp-default",
    )
    assert "Pass this spec_json verbatim" not in user


def test_acp_turn_loop_retries_in_same_session(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import asynccontextmanager

    from app.composition.acp import author as author_module

    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_TIMEOUT_SEC", "120")
    monkeypatch.setenv("VM_ACP_FIXTURE_LINT", "1")
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_MAX_TURNS", "5")
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

    counters = {"sessions": 0, "prompts": 0}
    lint_calls = {"n": 0}

    class _Session:
        session_id = "turn-loop-session"

    class _Conn:
        async def initialize(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def new_session(self, **_kwargs: object) -> _Session:
            counters["sessions"] += 1
            return _Session()

        async def prompt(self, *_args: object, **_kwargs: object) -> object:
            counters["prompts"] += 1
            return None

        async def close_session(self, *_args: object, **_kwargs: object) -> None:
            return None

    @asynccontextmanager
    async def fake_spawn(*_args: object, **_kwargs: object):
        yield _Conn(), None

    def fake_lint_after_turn(*_args: object, **_kwargs: object) -> tuple[list[str], bool]:
        lint_calls["n"] += 1
        if lint_calls["n"] == 1:
            return ["Path escapes project sandbox: generated/foo.mp4"], False
        return [], False

    monkeypatch.setattr(author_module, "spawn_agent_process", fake_spawn)
    monkeypatch.setattr(author_module, "_harvest_material_spec", lambda *_a, **_k: scratch / "material-spec.json")
    monkeypatch.setattr(author_module, "_lint_spec_after_turn", fake_lint_after_turn)

    storage_root = tmp_path / "storage"
    observability = AcpAuthorObservabilityContext.from_trace(
        sink=LocalFileSink(AgentRunStore(storage_root)),
        trace_dir=AcpAuthorTraceRecorder.create(
            storage_root,
            project_id="proj-acp",
            acp_agent="fake",
            generation_id="gen-1",
        ).trace_dir,
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
    assert counters["sessions"] == 1
    assert counters["prompts"] == 2

    payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (storage_root / "projects" / "proj-acp" / "logs" / "tool-runs").glob("*.json")
    ]
    end_payload = next(item for item in payloads if item["toolName"] == "acp_session_end")
    assert end_payload["metadata"]["repairAttempt"] == 1
    assert "acp_turn_lint_gate" in {item["toolName"] for item in payloads}


def test_acp_turn_loop_exhausted_raises(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import asynccontextmanager

    from app.composition.acp import author as author_module

    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_MAX_TURNS", "1")
    scratch = tmp_path / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    (scratch / "material-spec.json").write_text(
        json.dumps({"template": "benefit-card", "durationSec": 3, "params": {"title": "X"}}),
        encoding="utf-8",
    )

    class _Session:
        session_id = "exhausted"

    class _Conn:
        async def initialize(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def new_session(self, **_kwargs: object) -> _Session:
            return _Session()

        async def prompt(self, *_args: object, **_kwargs: object) -> object:
            return None

        async def close_session(self, *_args: object, **_kwargs: object) -> None:
            return None

    @asynccontextmanager
    async def fake_spawn(*_args: object, **_kwargs: object):
        yield _Conn(), None

    monkeypatch.setattr(author_module, "spawn_agent_process", fake_spawn)
    monkeypatch.setattr(author_module, "_harvest_material_spec", lambda *_a, **_k: scratch / "material-spec.json")
    monkeypatch.setattr(
        author_module,
        "_lint_spec_after_turn",
        lambda *_a, **_k: (["simulated lint failure"], False),
    )

    with pytest.raises(RuntimeError, match="acp_author_spec_invalid"):
        author_material_spec_via_acp(
            AuthorRequest(
                project_id="proj-acp",
                generation_id="gen-1",
                slot={"role": "benefit_card"},
                aspect_ratio="9:16",
            ),
            repo_root=repo_root,
            scratch_dir=scratch,
            agent_command=fake_agent_command(),
        )


def test_in_session_followup_includes_sandbox_recipe(
    repo_root: Path,
    tmp_path: Path,
) -> None:
    from app.composition.acp.author import _build_in_session_followup

    scratch = tmp_path / "scratch"
    scratch.mkdir()
    (scratch / "slot-1-stock.mp4").write_bytes(b"video")
    text = _build_in_session_followup(
        ["Path escapes project sandbox: generated/slot-1-stock.mp4"],
        1,
        scratch_dir=scratch,
        repo_root=repo_root,
    )
    assert "IN_SESSION_REPAIR" in text
    assert "sandbox_path" in text
    assert "slot-1-stock.mp4" in text


def test_acp_lint_repair_retries_after_post_turn_failure(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backward-compatible alias for turn-loop in-session repair."""
    test_acp_turn_loop_retries_in_same_session(tmp_path, repo_root, monkeypatch)
