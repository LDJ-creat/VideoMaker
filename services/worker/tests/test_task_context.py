from __future__ import annotations

from pathlib import Path

from app.runtime.task_context import TaskContext


def test_emit_progress_reuses_last_progress() -> None:
    context = TaskContext(
        project_id="proj-1",
        task_id="task-1",
        storage_root=Path("/tmp/storage"),
        api_base_url=None,
    )
    context.emit_event(stage="synthesizing_narration_preview", progress=48, message="start")
    context.emit_progress("generating_tts", "Synthesizing speech")

    assert context.emitted_events[-1]["stage"] == "generating_tts"
    assert context.emitted_events[-1]["progress"] == 48
    assert context.emitted_events[-1]["message"] == "Synthesizing speech"


def test_emit_progress_accepts_explicit_progress() -> None:
    context = TaskContext(
        project_id="proj-1",
        task_id="task-1",
        storage_root=Path("/tmp/storage"),
        api_base_url=None,
    )
    context.emit_progress("generating_material", "Completing slot hook", progress=65)

    assert context.emitted_events[-1]["progress"] == 65
