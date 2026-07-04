from __future__ import annotations

import json
import time
from pathlib import Path

from unittest.mock import MagicMock

import pytest

from app.composition.acp.agent_registry import fake_agent_command
from app.composition.acp.author import (
    _acp_in_session_review_enabled,
    _build_in_session_followup,
    _build_prompt_text,
    _build_review_followup,
    _harvest_material_spec,
    _is_session_level_failure,
    _load_revise_context_for_payload,
    _resolve_generation_root_for_revise,
    _resolve_template_mode,
    _review_errors_from_report,
    _review_spec_after_turn,
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


def test_acp_in_session_review_disabled_for_revise_gate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true")
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION_REVISE", "false")
    payload = {
        "materialGateRevise": {"affectedSlotIds": ["slot-5"]},
        "materialEditMode": "full",
    }
    assert _acp_in_session_review_enabled(payload) is False


def test_acp_in_session_review_enabled_for_first_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true")
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION", "true")
    assert _acp_in_session_review_enabled({}) is True


def test_acp_timeout_default_by_template(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("VIDEOMAKER_COMPOSITION_ACP_TIMEOUT_SEC", raising=False)
    assert acp_timeout_sec(composition_template=True) == 1800.0
    assert acp_timeout_sec(composition_template=False) == 600.0
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_TIMEOUT_SEC", "900")
    assert acp_timeout_sec(composition_template=True) == 900.0


def test_resolve_template_mode_from_composition_brief() -> None:
    payload = {"compositionAuthorBrief": {"authorPrompt": "motion only"}}
    assert _resolve_template_mode(payload) == "composition"


def test_load_revise_context_for_payload_reads_generation_root_not_generated(tmp_path: Path) -> None:
    generation_root = tmp_path / "generations" / "gen-1"
    generated_root = generation_root / "generated"
    generated_root.mkdir(parents=True)
    (generation_root / "revise-context.json").write_text(
        json.dumps(
            {
                "materialGateRevise": {
                    "source": "material_gate_revise",
                    "materialEditMode": "edit",
                    "editInstruction": "背景改为暖白色",
                    "affectedSlotIds": ["slot-6"],
                    "slotChainKinds": {"slot-6": "hf_only"},
                }
            }
        ),
        encoding="utf-8",
    )

    assert _load_revise_context_for_payload(generated_root) is None

    snippet = _load_revise_context_for_payload(generation_root)

    assert snippet is not None
    assert snippet["materialEditMode"] == "edit"
    assert snippet["editInstruction"] == "背景改为暖白色"
    assert snippet["materialGateRevise"]["affectedSlotIds"] == ["slot-6"]


def test_resolve_generation_root_for_revise_prefers_request_path(tmp_path: Path) -> None:
    generation_root = tmp_path / "generations" / "gen-1"
    generated_root = generation_root / "generated"
    generated_root.mkdir(parents=True)

    resolved = _resolve_generation_root_for_revise(
        request=AuthorRequest(
            slot={"id": "slot-6"},
            generation_root=generation_root,
        ),
        generated_root=generated_root,
    )

    assert resolved == generation_root.resolve()


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
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION", "false")
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
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION", "false")
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
    monkeypatch.setattr(
        author_module,
        "_review_spec_after_turn",
        lambda *_a, **_k: ({"approved": True, "hardGateFailed": False, "issues": []}, []),
    )

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


def test_review_errors_from_report_hard_gate_and_not_approved() -> None:
    hard = {
        "hardGateFailed": True,
        "issues": ["preview_duration_drift:5.70s vs 7.15s"],
    }
    assert _review_errors_from_report(hard) == ["preview_duration_drift:5.70s vs 7.15s"]

    llm_fail = {
        "approved": False,
        "issues": ["copy on screen"],
        "suggestions": ["Remove verbatim text"],
    }
    assert _review_errors_from_report(llm_fail) == ["copy on screen", "Remove verbatim text"]


def test_build_review_followup_includes_report(repo_root: Path, tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    text = _build_review_followup(
        {
            "approved": False,
            "hardGateFailed": True,
            "issues": ["preview_duration_drift:5.70s vs 7.15s"],
            "suggestions": ["Fix preview render before creative review."],
            "trace": {"reviewRoute": "hard_gate"},
        },
        1,
        scratch_dir=scratch,
        repo_root=repo_root,
    )
    assert "IN_SESSION_REPAIR" in text
    assert "preview_duration_drift" in text
    assert "hard_gate" in text
    assert "review_material_preview" in text


def test_acp_turn_loop_retries_on_hard_gate_review(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import asynccontextmanager

    from app.composition.acp import author as author_module

    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_TIMEOUT_SEC", "120")
    monkeypatch.setenv("VM_ACP_FIXTURE_LINT", "1")
    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_MAX_TURNS", "5")
    monkeypatch.setenv("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true")
    scratch = tmp_path / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    spec_payload = {
        "template": "benefit-card",
        "durationSec": 7.15,
        "params": {
            "title": "Duration fix",
            "bullets": ["A"],
            "colors": {"primary": "#2563eb", "background": "#0f172a", "text": "#ffffff"},
        },
    }
    (scratch / "material-spec.json").write_text(json.dumps(spec_payload), encoding="utf-8")

    counters = {"prompts": 0}
    review_calls = {"n": 0}

    class _Session:
        session_id = "review-loop-session"

    class _Conn:
        async def initialize(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def new_session(self, **_kwargs: object) -> _Session:
            return _Session()

        async def prompt(self, *_args: object, **_kwargs: object) -> object:
            counters["prompts"] += 1
            return None

        async def close_session(self, *_args: object, **_kwargs: object) -> None:
            return None

    @asynccontextmanager
    async def fake_spawn(*_args: object, **_kwargs: object):
        yield _Conn(), None

    def fake_review(*_args: object, **_kwargs: object) -> tuple[dict[str, object], list[str]]:
        review_calls["n"] += 1
        if review_calls["n"] == 1:
            return (
                {
                    "approved": False,
                    "hardGateFailed": True,
                    "issues": ["preview_duration_drift:5.70s vs 7.15s"],
                    "suggestions": ["Fix preview render before creative review."],
                    "trace": {"reviewRoute": "hard_gate"},
                },
                ["preview_duration_drift:5.70s vs 7.15s"],
            )
        return ({"approved": True, "hardGateFailed": False, "issues": []}, [])

    monkeypatch.setattr(author_module, "spawn_agent_process", fake_spawn)
    monkeypatch.setattr(author_module, "_harvest_material_spec", lambda *_a, **_k: scratch / "material-spec.json")
    monkeypatch.setattr(author_module, "_lint_spec_after_turn", lambda *_a, **_k: ([], False))
    monkeypatch.setattr(author_module, "_review_spec_after_turn", fake_review)

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
            slot={"role": "benefit_card", "id": "slot-3"},
            aspect_ratio="9:16",
            slot_timing={"durationSec": 7.15},
        ),
        repo_root=repo_root,
        scratch_dir=scratch,
        agent_command=fake_agent_command(),
        observability=observability,
    )
    assert spec["durationSec"] == 7.15
    assert counters["prompts"] == 2
    assert review_calls["n"] == 2

    payloads = [
        json.loads(path.read_text(encoding="utf-8"))
        for path in (storage_root / "projects" / "proj-acp" / "logs" / "tool-runs").glob("*.json")
    ]
    tool_names = {item["toolName"] for item in payloads}
    assert "acp_turn_review_gate" in tool_names
    failed_review = next(
        item
        for item in payloads
        if item["toolName"] == "acp_turn_review_gate" and item["metadata"].get("outputValid") is False
    )
    assert failed_review["metadata"]["hardGateFailed"] is True
    end_payload = next(item for item in payloads if item["toolName"] == "acp_session_end")
    assert end_payload["metadata"]["repairAttempt"] == 1


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


def test_is_session_level_failure_includes_internal_error() -> None:
    assert _is_session_level_failure(RuntimeError("Internal error")) is True
    assert _is_session_level_failure(RuntimeError("connection closed")) is True
    assert _is_session_level_failure(RuntimeError("acp_author_spec_invalid: lint")) is False


def test_acp_failure_records_agent_diagnostics_in_outcome(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from contextlib import asynccontextmanager

    from app.composition.acp import author as author_module

    monkeypatch.setenv("VIDEOMAKER_COMPOSITION_ACP_MAX_TURNS", "1")

    class _FakeProcess:
        returncode = 1
        stderr = None

    class _Session:
        session_id = "diag-fail"

    class _Conn:
        async def initialize(self, *_args: object, **_kwargs: object) -> None:
            return None

        async def new_session(self, **_kwargs: object) -> _Session:
            return _Session()

        async def prompt(self, *_args: object, **_kwargs: object) -> object:
            raise RuntimeError("Internal error")

        async def close_session(self, *_args: object, **_kwargs: object) -> None:
            return None

    @asynccontextmanager
    async def fake_spawn(*_args: object, **_kwargs: object):
        yield _Conn(), _FakeProcess()

    async def fake_collect(process: object) -> dict[str, object]:
        assert process is not None
        return {"agentExitCode": 1, "agentStderrTail": "You've hit your usage limit. Upgrade your plan."}

    scratch = tmp_path / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    storage_root = tmp_path / "storage"
    trace = AcpAuthorTraceRecorder.create(
        storage_root,
        project_id="proj-acp",
        acp_agent="cursor",
        generation_id="gen-1",
    )

    monkeypatch.setattr(author_module, "spawn_agent_process", fake_spawn)
    monkeypatch.setattr(author_module, "_collect_agent_diagnostics", fake_collect)
    monkeypatch.setattr(author_module, "_harvest_material_spec", lambda *_a, **_k: None)

    with pytest.raises(RuntimeError, match="Internal error"):
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
            trace=trace,
        )

    outcome = json.loads((trace.trace_dir / "outcome.json").read_text(encoding="utf-8"))
    assert outcome["valid"] is False
    assert outcome["agentDiagnostics"]["agentExitCode"] == 1
    assert "usage limit" in outcome["agentDiagnostics"]["agentStderrTail"]


def test_acp_lint_repair_retries_after_post_turn_failure(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Backward-compatible alias for turn-loop in-session repair."""
    test_acp_turn_loop_retries_in_same_session(tmp_path, repo_root, monkeypatch)


def test_review_spec_after_turn_uses_run_review_via_worker(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    preview = scratch / "preview.mp4"
    preview.write_bytes(b"preview")
    spec = {"template": "composition", "durationSec": 9.5, "composition": {"bodyHtml": "<div/>"}}
    author_payload = {
        "projectId": "proj-1",
        "generationId": "gen-1",
        "generationRoot": str(tmp_path / "gen"),
        "slotId": "slot-5",
        "slot": {"id": "slot-5"},
        "slotTiming": {"durationSec": 9.5},
    }
    calls: dict[str, int] = {"render": 0, "review": 0}

    def fake_render(*_args: object, **_kwargs: object) -> dict[str, object]:
        calls["render"] += 1
        return {"ok": True, "previewPath": str(preview), "durationSec": 9.5}

    def fake_review(**kwargs: object) -> dict[str, object]:
        calls["review"] += 1
        assert kwargs["preview_path"] == preview
        assert kwargs["generation_root"] == Path(author_payload["generationRoot"])
        return {
            "ok": True,
            "report": {
                "approved": False,
                "issues": ["empty preview"],
                "suggestions": ["Add visible copy"],
            },
        }

    monkeypatch.setattr(
        "composition.material_review.preview.render_material_preview_spec",
        fake_render,
    )
    monkeypatch.setattr(
        "composition.material_review.preview.run_review_via_worker",
        fake_review,
    )
    marker_written: dict[str, bool] = {"ok": False}

    def fake_marker(*_args: object, **_kwargs: object) -> None:
        marker_written["ok"] = True

    monkeypatch.setattr(
        "composition.material_review.session.write_review_marker",
        fake_marker,
    )

    report, errors = _review_spec_after_turn(
        spec,
        scratch_dir=scratch,
        repo_root=repo_root,
        author_payload=author_payload,
        aspect_ratio="9:16",
        asset_root=None,
    )
    assert calls["render"] == 1
    assert calls["review"] == 1
    assert report is not None
    assert errors == ["empty preview", "Add visible copy"]
    assert marker_written["ok"] is True
