from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from composition.material_review.preview import run_review_via_worker


def test_run_review_via_worker_records_tool_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage_root = tmp_path / "storage"
    generation_root = storage_root / "projects" / "project-1" / "generations" / "gen-1"
    generation_root.mkdir(parents=True)
    preview = generation_root / "preview.mp4"
    preview.write_bytes(b"\x00" * 2048)

    monkeypatch.setenv("VM_DATABASE_PATH", str(tmp_path / "gateway.sqlite3"))
    monkeypatch.setenv("VM_STORAGE_ROOT", str(storage_root))

    fake_report = {
        "slotId": "hook",
        "generationId": "gen-1",
        "reviewedAt": "2026-06-29T12:00:00Z",
        "approved": True,
        "issues": [],
        "suggestions": [],
        "reviewInputs": {"mode": "video"},
        "trace": {"reviewRoute": "video", "modelCallId": "call-1", "agentRunId": "run-1"},
    }

    def _fake_run_slot_review(**kwargs):  # noqa: ANN003
        return fake_report

    monkeypatch.setattr(
        "app.pipelines.material_review.run_slot_review",
        _fake_run_slot_review,
    )

    gateway = MagicMock()
    result = run_review_via_worker(
        preview_path=preview,
        spec={"durationSec": 3.0},
        author_payload={
            "projectId": "project-1",
            "taskId": "task-1",
            "generationId": "gen-1",
            "generationRoot": str(generation_root),
        },
        slot_id="hook",
        generation_id="gen-1",
        generation_root=generation_root,
        gateway=gateway,
    )
    assert result["ok"] is True
    tool_runs = list((storage_root / "projects" / "project-1" / "logs" / "tool-runs").glob("*.json"))
    assert len(tool_runs) == 1
    payload = json.loads(tool_runs[0].read_text(encoding="utf-8"))
    assert payload["toolName"] == "review_material_preview"
    assert payload["output"]["modelCallId"] == "call-1"


def test_run_review_via_worker_propagates_acp_parent_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "storage"
    generation_root = storage_root / "projects" / "project-1" / "generations" / "gen-1"
    generation_root.mkdir(parents=True)
    preview = generation_root / "preview.mp4"
    preview.write_bytes(b"\x00" * 2048)

    monkeypatch.setenv("VM_STORAGE_ROOT", str(storage_root))
    monkeypatch.setenv("VM_ACP_OBSERVABILITY_RUN_ID", "acp-parent-session")

    fake_report = {
        "approved": True,
        "issues": [],
        "trace": {"reviewRoute": "video"},
    }

    monkeypatch.setattr(
        "app.pipelines.material_review.run_slot_review",
        lambda **kwargs: fake_report,
    )

    gateway = MagicMock()
    result = run_review_via_worker(
        preview_path=preview,
        spec={"durationSec": 3.0},
        author_payload={"projectId": "project-1", "taskId": "task-1"},
        slot_id="hook",
        generation_id="gen-1",
        generation_root=generation_root,
        gateway=gateway,
    )
    assert result["ok"] is True
    tool_runs = list((storage_root / "projects" / "project-1" / "logs" / "tool-runs").glob("*.json"))
    payload = json.loads(tool_runs[0].read_text(encoding="utf-8"))
    assert payload["metadata"]["parentObservabilityRunId"] == "acp-parent-session"


def test_run_review_via_worker_builds_store_from_generation_root_db_sibling(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "storage"
    generation_root = storage_root / "projects" / "project-1" / "generations" / "gen-1"
    generation_root.mkdir(parents=True)
    preview = generation_root / "preview.mp4"
    preview.write_bytes(b"\x00" * 2048)
    db_path = storage_root / "videomaker.sqlite3"
    db_path.write_bytes(b"")

    captured: dict[str, object] = {}

    def _fake_run_slot_review(**kwargs):  # noqa: ANN003
        captured["store"] = kwargs.get("store")
        return {
            "slotId": "action-slot-5",
            "generationId": "gen-1",
            "reviewedAt": "2026-07-05T06:41:00Z",
            "approved": True,
            "issues": [],
            "suggestions": [],
            "reviewInputs": {"mode": "video"},
            "trace": {"reviewRoute": "video"},
        }

    monkeypatch.setattr(
        "app.pipelines.material_review.run_slot_review",
        _fake_run_slot_review,
    )

    result = run_review_via_worker(
        preview_path=preview,
        spec={"template": "composition", "durationSec": 9.5},
        author_payload={
            "projectId": "project-1",
            "taskId": "task-1",
            "generationId": "gen-1",
            "generationRoot": str(generation_root),
        },
        slot_id="action-slot-5",
        generation_id="gen-1",
        generation_root=generation_root,
        gateway=None,
    )
    assert result["ok"] is True
    assert captured.get("store") is not None


def test_run_review_via_worker_builds_store_from_string_env_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ACP in-session review passes gateway=None; env paths must be coerced to Path."""
    storage_root = tmp_path / "storage"
    generation_root = storage_root / "projects" / "project-1" / "generations" / "gen-1"
    generation_root.mkdir(parents=True)
    preview = generation_root / "preview.mp4"
    preview.write_bytes(b"\x00" * 2048)
    db_path = tmp_path / "gateway.sqlite3"

    monkeypatch.setenv("VM_DATABASE_PATH", str(db_path))
    monkeypatch.setenv("VM_STORAGE_ROOT", str(storage_root))

    fake_report = {
        "slotId": "action-slot-5",
        "generationId": "gen-1",
        "approved": True,
        "issues": [],
        "suggestions": [],
        "reviewInputs": {"mode": "video"},
        "trace": {"reviewRoute": "video"},
    }

    monkeypatch.setattr(
        "app.pipelines.material_review.run_slot_review",
        lambda **kwargs: fake_report,
    )

    result = run_review_via_worker(
        preview_path=preview,
        spec={"template": "composition", "durationSec": 9.5},
        author_payload={
            "projectId": "project-1",
            "taskId": "task-1",
            "generationId": "gen-1",
            "generationRoot": str(generation_root),
        },
        slot_id="action-slot-5",
        generation_id="gen-1",
        generation_root=generation_root,
        gateway=None,
    )
    assert result["ok"] is True
    assert result["report"]["approved"] is True


def test_run_review_via_worker_waives_agent_run_log_observability_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_root = tmp_path / "storage"
    generation_root = storage_root / "projects" / "project-1" / "generations" / "gen-1"
    generation_root.mkdir(parents=True)
    preview = generation_root / "preview.mp4"
    preview.write_bytes(b"\x00" * 2048)

    monkeypatch.setenv("VM_STORAGE_ROOT", str(storage_root))

    def _raise_agent_run_log(**kwargs):  # noqa: ANN003
        raise ValueError(
            "Invalid AgentRunLog payload: "
            "[ValidationErrorItem(path='$.tokenUsage', message=\"Additional properties are not allowed ('total' was unexpected)\", validator='additionalProperties')]"
        )

    monkeypatch.setattr(
        "app.pipelines.material_review.run_slot_review",
        _raise_agent_run_log,
    )

    result = run_review_via_worker(
        preview_path=preview,
        spec={"durationSec": 3.97},
        author_payload={"projectId": "project-1", "taskId": "task-1"},
        slot_id="slot-3",
        generation_id="gen-1",
        generation_root=generation_root,
        gateway=MagicMock(),
    )
    assert result["ok"] is True
    assert result["report"]["approved"] is True
    assert result["report"].get("reviewUnavailable") is True
