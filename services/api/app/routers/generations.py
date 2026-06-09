from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.services.agent_runs import list_agent_runs_for_generation
from app.services.generation_responses import build_generation_plan_response
from app.services.pipeline_runner import PipelineRunner
from app.services.project_store import ProjectStore
from app.services.task_events import TaskEventService

router = APIRouter(prefix="/api/generations", tags=["generations"])

MAX_REVISE_INSTRUCTION_LEN = 2000


class ReviseGenerationRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=MAX_REVISE_INSTRUCTION_LEN)


class ScriptDraftUpdateRequest(BaseModel):
    masterNarration: str | None = None
    storyboard: list[dict[str, Any]] | None = None


def _generation_root(storage_root: Path, project_id: str, generation_id: str) -> Path:
    return storage_root / "projects" / project_id / "generations" / generation_id


def _project_store(request: Request) -> ProjectStore:
    return ProjectStore(request.app.state.db)


def _task_events(request: Request) -> TaskEventService:
    return TaskEventService(request.app.state.db)


def _pipeline_runner(request: Request) -> PipelineRunner:
    return request.app.state.pipeline_runner


def _load_source_plan(storage_root: Path, project_id: str, generation_id: str) -> dict[str, Any]:
    plan_path = (
        storage_root
        / "projects"
        / project_id
        / "generations"
        / generation_id
        / "generation-plan.json"
    )
    if not plan_path.is_file():
        raise FileNotFoundError("generation-plan.json not found on disk")
    return json.loads(plan_path.read_text(encoding="utf-8"))


def _persist_edit_intent(
    storage_root: Path,
    project_id: str,
    generation_id: str,
    intents: list[dict[str, Any]],
    *,
    instruction: str,
    source_generation_id: str,
) -> None:
    generation_root = storage_root / "projects" / project_id / "generations" / generation_id
    generation_root.mkdir(parents=True, exist_ok=True)
    (generation_root / "edit-intent.json").write_text(
        json.dumps({"intents": intents}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    revise_context_path = generation_root / "revise-context.json"
    if not revise_context_path.is_file():
        revise_context_path.write_text(
            json.dumps(
                {
                    "sourceGenerationId": source_generation_id,
                    "instruction": instruction,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )


@router.get("/{generation_id}/agent-runs")
def get_generation_agent_runs(generation_id: str, request: Request) -> dict[str, Any]:
    record = _project_store(request).get_generation(generation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Generation not found")

    storage_root: Path = request.app.state.storage_root
    runs = list_agent_runs_for_generation(
        storage_root,
        project_id=str(record["projectId"]),
        generation_id=generation_id,
    )
    return {"runs": runs}


@router.get("/{generation_id}/composition-patterns")
def list_composition_patterns(generation_id: str, request: Request) -> dict[str, Any]:
    store = _project_store(request)
    record = store.get_generation(generation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    from app.services.knowledge_store import KnowledgeStore

    knowledge = KnowledgeStore(request.app.state.db, request.app.state.storage_root)
    patterns = knowledge.list_composition_pattern_candidates(
        project_id=str(record["projectId"]),
        generation_id=generation_id,
    )
    return {"generationId": generation_id, "patterns": patterns}


@router.get("/{generation_id}")
def get_generation(generation_id: str, request: Request) -> dict[str, Any]:
    record = _project_store(request).get_generation(generation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Generation not found")

    return build_generation_plan_response(
        record,
        storage_root=request.app.state.storage_root,
    )


@router.get("/{generation_id}/script-draft")
def get_script_draft(generation_id: str, request: Request) -> dict[str, Any]:
    from app.services.script_draft_service import load_script_draft

    store = _project_store(request)
    record = store.get_generation(generation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    storage_root: Path = request.app.state.storage_root
    project_id = str(record["projectId"])
    try:
        draft = load_script_draft(storage_root, project_id, generation_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Script draft not found") from exc
    task = _task_events(request).get_task(str(record["taskId"]))
    return {
        "draft": draft,
        "taskStatus": task.get("status") if task else None,
        "taskStage": task.get("stage") if task else None,
    }


@router.put("/{generation_id}/script-draft")
def update_script_draft(
    generation_id: str,
    payload: ScriptDraftUpdateRequest,
    request: Request,
) -> dict[str, Any]:
    from app.services.script_draft_service import load_script_draft, save_script_draft

    store = _project_store(request)
    record = store.get_generation(generation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    storage_root: Path = request.app.state.storage_root
    project_id = str(record["projectId"])
    try:
        draft = load_script_draft(storage_root, project_id, generation_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Script draft not found") from exc

    if payload.masterNarration is not None:
        if draft.get("masterNarrationStatus") == "approved":
            raise HTTPException(status_code=400, detail="Master narration already approved")
        draft["masterNarration"] = payload.masterNarration
    if payload.storyboard is not None:
        if draft.get("storyboardStatus") == "approved":
            raise HTTPException(status_code=400, detail="Storyboard already approved")
        draft["storyboard"] = payload.storyboard

    try:
        saved = save_script_draft(storage_root, project_id, generation_id, draft)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"draft": saved}


@router.post("/{generation_id}/approve-master", status_code=status.HTTP_202_ACCEPTED)
def approve_master_script(generation_id: str, request: Request) -> dict[str, Any]:
    from app.services.script_draft_service import (
        approve_master_draft,
        load_script_draft,
        save_script_draft,
    )

    store = _project_store(request)
    record = store.get_generation(generation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    storage_root: Path = request.app.state.storage_root
    project_id = str(record["projectId"])
    task_id = str(record["taskId"])
    try:
        draft = load_script_draft(storage_root, project_id, generation_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Script draft not found") from exc
    try:
        approved = approve_master_draft(draft)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    save_script_draft(storage_root, project_id, generation_id, approved)
    checkpoint_path = _generation_root(storage_root, project_id, generation_id) / "checkpoint.json"
    if checkpoint_path.is_file():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if isinstance(checkpoint, dict):
            checkpoint["awaitingGate"] = None
            checkpoint_path.write_text(
                json.dumps(checkpoint, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    try:
        _pipeline_runner(request).retry_task(task_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"generationId": generation_id, "taskId": task_id, "draft": approved}


@router.post("/{generation_id}/approve-storyboard", status_code=status.HTTP_202_ACCEPTED)
def approve_storyboard_script(generation_id: str, request: Request) -> dict[str, Any]:
    from app.services.script_draft_service import (
        approve_storyboard_draft,
        load_script_draft,
        save_script_draft,
    )

    store = _project_store(request)
    record = store.get_generation(generation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    storage_root: Path = request.app.state.storage_root
    project_id = str(record["projectId"])
    task_id = str(record["taskId"])
    try:
        draft = load_script_draft(storage_root, project_id, generation_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Script draft not found") from exc
    try:
        approved = approve_storyboard_draft(draft)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    save_script_draft(storage_root, project_id, generation_id, approved)
    checkpoint_path = _generation_root(storage_root, project_id, generation_id) / "checkpoint.json"
    if checkpoint_path.is_file():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if isinstance(checkpoint, dict):
            checkpoint["awaitingGate"] = None
            checkpoint_path.write_text(
                json.dumps(checkpoint, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    try:
        _pipeline_runner(request).retry_task(task_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"generationId": generation_id, "taskId": task_id, "draft": approved}


@router.post("/{generation_id}/revise", status_code=status.HTTP_202_ACCEPTED)
def revise_generation(
    generation_id: str,
    payload: ReviseGenerationRequest,
    request: Request,
) -> dict[str, Any]:
    store = _project_store(request)
    source = store.get_generation(generation_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Generation not found")

    if str(source.get("status")) != "succeeded":
        raise HTTPException(
            status_code=400,
            detail="Source generation must be succeeded before revise",
        )

    project_id = str(source["projectId"])
    storage_root: Path = request.app.state.storage_root
    runner = _pipeline_runner(request)

    source_plan = source.get("plan")
    if not isinstance(source_plan, dict):
        try:
            source_plan = _load_source_plan(storage_root, project_id, generation_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=400,
                detail="Source generation has no plan artifacts for revise",
            ) from exc

    try:
        intents = runner.parse_edit_intent(
            project_id=project_id,
            instruction=payload.instruction,
            source_plan=source_plan,
        )
        runner._validate_edit_intents(intents)  # noqa: SLF001
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    structure = store.get_latest_sample_structure(project_id)
    if structure is None:
        raise HTTPException(
            status_code=400,
            detail="No analyzed sample structure for project. Complete sample analysis first.",
        )

    brief = store.get_brief(project_id) or {
        "topic": "Demo topic",
        "sellingPoints": [],
        "mustMention": [],
        "avoidMention": [],
    }
    assets = store.list_assets(project_id)
    variant = str(source.get("variant") or source_plan.get("variant") or "default")

    task = _task_events(request).create_task(
        project_id,
        stage="parsing_edit_intent",
        message="Queued generation revise",
    )
    new_generation = store.create_generation(
        project_id=project_id,
        task_id=task["taskId"],
        status="queued",
        variant=variant,
    )
    _persist_edit_intent(
        storage_root,
        project_id,
        new_generation["id"],
        intents,
        instruction=payload.instruction,
        source_generation_id=generation_id,
    )

    runner.start_revise(
        project_id=project_id,
        source_generation_id=generation_id,
        generation_id=new_generation["id"],
        task_id=task["taskId"],
        instruction=payload.instruction,
        intents=intents,
        structure=structure,
        user_brief=brief,
        assets=assets,
        variant=variant,
    )

    return {
        "sourceGenerationId": generation_id,
        "generationId": new_generation["id"],
        "taskId": task["taskId"],
        "intents": intents,
    }
