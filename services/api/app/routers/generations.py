from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request, status
from knowledge.paths import validate_storage_segment
from material_disk import (
    expected_output_path,
    infer_completed_slot_ids,
    is_valid_visual_artifact,
    material_review_approvable,
    terminal_visual_action_by_slot,
)
from material_review_revise_context import load_material_review_revise_context
from pydantic import BaseModel, Field, model_validator

from app.services.agent_runs import list_agent_runs_for_generation
from app.services.model_calls import list_model_calls_for_generation
from app.services.generation_responses import build_generation_plan_response
from app.services.pipeline_runner import PipelineRunner
from app.services.project_store import ProjectStore
from app.services.task_events import TaskEventService

router = APIRouter(prefix="/api/generations", tags=["generations"])

MAX_REVISE_INSTRUCTION_LEN = 2000


class ReviseGenerationRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=MAX_REVISE_INSTRUCTION_LEN)


class SceneReviseStructured(BaseModel):
    sceneId: str = Field(min_length=1)
    slotId: str = Field(min_length=1)
    mode: Literal["edit", "full"]
    instruction: str = Field(min_length=1, max_length=500)


class RevisePlanRequest(BaseModel):
    instruction: str | None = Field(default=None, max_length=MAX_REVISE_INSTRUCTION_LEN)
    structured: SceneReviseStructured | None = None
    newSession: bool = False

    @model_validator(mode="after")
    def _exactly_one_plan_input(self) -> RevisePlanRequest:
        has_instruction = bool((self.instruction or "").strip())
        has_structured = self.structured is not None
        if has_instruction == has_structured:
            raise ValueError("Provide exactly one of instruction or structured")
        if has_instruction and len(self.instruction or "") < 1:
            raise ValueError("instruction must not be empty")
        return self


class ReviseExecuteRequest(BaseModel):
    planId: str = Field(min_length=1)


class ReviseCancelRequest(BaseModel):
    planId: str | None = None


class ScriptDraftUpdateRequest(BaseModel):
    masterNarration: str | None = None
    storyboard: list[dict[str, Any]] | None = None


class ScriptDraftNlReviseRequest(BaseModel):
    scope: Literal["master", "storyboard"]
    instruction: str = Field(min_length=1, max_length=MAX_REVISE_INSTRUCTION_LEN)


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


@router.get("/{generation_id}/migration-snapshot")
def get_migration_snapshot(generation_id: str, request: Request) -> dict[str, Any]:
    store = _project_store(request)
    record = store.get_generation(generation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Generation not found")

    storage_root: Path = request.app.state.storage_root
    project_id = str(record["projectId"])
    generation_root = _generation_root(storage_root, project_id, generation_id)

    slot_matches: list[Any] = []
    slot_matches_path = generation_root / "slot-matches.json"
    if slot_matches_path.is_file():
        slot_payload = json.loads(slot_matches_path.read_text(encoding="utf-8"))
        if isinstance(slot_payload, dict):
            raw_matches = slot_payload.get("slotMatches")
            if isinstance(raw_matches, list):
                slot_matches = raw_matches

    gap_report: dict[str, Any] | None = None
    gap_report_path = generation_root / "gap-report.json"
    if gap_report_path.is_file():
        gap_payload = json.loads(gap_report_path.read_text(encoding="utf-8"))
        if isinstance(gap_payload, dict):
            gap_report = gap_payload

    completion_actions: list[Any] = []
    plan_path = generation_root / "generation-plan.json"
    if plan_path.is_file():
        plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
        if isinstance(plan_payload, dict):
            raw_actions = plan_payload.get("completionActions")
            if isinstance(raw_actions, list):
                completion_actions = raw_actions

    material_state: dict[str, Any] | None = None
    material_state_path = generation_root / "material-state.json"
    if material_state_path.is_file():
        material_payload = json.loads(material_state_path.read_text(encoding="utf-8"))
        if isinstance(material_payload, dict):
            raw_completed = material_payload.get("completedActionIds")
            if isinstance(raw_completed, list):
                material_state = {
                    "completedActionIds": [
                        str(item) for item in raw_completed if str(item).strip()
                    ],
                }

    completed_slot_ids = infer_completed_slot_ids(
        completion_actions,
        generation_root / "generated",
    )

    return {
        "slotMatches": slot_matches,
        "gapReport": gap_report,
        "completionActions": completion_actions,
        "materialState": material_state,
        "completedSlotIds": completed_slot_ids,
    }


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


@router.get("/{generation_id}/model-calls")
def get_generation_model_calls(
    generation_id: str,
    request: Request,
    kind: str | None = None,
) -> dict[str, Any]:
    record = _project_store(request).get_generation(generation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Generation not found")

    storage_root: Path = request.app.state.storage_root
    calls = list_model_calls_for_generation(
        storage_root,
        project_id=str(record["projectId"]),
        generation_id=generation_id,
        kind=kind,
    )
    return {"calls": calls}


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
        if str(payload.masterNarration).strip() != str(draft.get("masterNarration") or "").strip():
            from app.services.script_draft_service import clear_narration_preview_artifacts

            clear_narration_preview_artifacts(storage_root, project_id, generation_id)
            draft.pop("narrationPreviewDurationSec", None)
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


@router.post("/{generation_id}/script-draft/nl-revise")
def nl_revise_script_draft(
    generation_id: str,
    payload: ScriptDraftNlReviseRequest,
    request: Request,
) -> dict[str, Any]:
    from app.services.script_draft_service import (
        load_script_draft,
        validate_nl_revise_gate,
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

    task = _task_events(request).get_task(task_id)
    task_stage = str(task.get("stage")) if task and task.get("stage") else None
    try:
        validate_nl_revise_gate(
            scope=payload.scope,
            draft=draft,
            task_stage=task_stage,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    structure = store.get_latest_sample_structure(project_id)
    runner = _pipeline_runner(request)
    try:
        result = runner.revise_script_draft(
            project_id=project_id,
            generation_id=generation_id,
            task_id=task_id,
            scope=payload.scope,
            instruction=payload.instruction,
            structure=structure,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    if not result.get("ok"):
        raise HTTPException(status_code=502, detail="Script NL revise failed")

    response: dict[str, Any] = {
        "draft": result.get("draft"),
        "revisionId": result.get("revisionId"),
    }
    if result.get("summary"):
        response["summary"] = result["summary"]
    return response


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


class MaterialSlotReviseRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=MAX_REVISE_INSTRUCTION_LEN)


def _material_review_gate_active(generation_root: Path) -> bool:
    checkpoint_path = generation_root / "checkpoint.json"
    if not checkpoint_path.is_file():
        return False
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    return isinstance(checkpoint, dict) and checkpoint.get("awaitingGate") == "material_review"


def _load_material_review_revise_context(generation_root: Path) -> dict[str, Any] | None:
    return load_material_review_revise_context(generation_root)


def _require_material_review_task_awaiting(request: Request, task_id: str) -> None:
    task = _task_events(request).get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    status = str(task.get("status") or "")
    stage = str(task.get("stage") or "")
    if status != "awaiting_review" or stage != "awaiting_material_review":
        raise HTTPException(
            status_code=400,
            detail="Task is not awaiting material review",
        )


def _slot_preview_media_url(
    project_id: str,
    generation_id: str,
    generation_relative_path: str,
    *,
    cache_version: str | None = None,
) -> str:
    from urllib.parse import quote, urlencode

    segments = "/".join(
        quote(part, safe="")
        for part in ("generations", generation_id, *generation_relative_path.split("/"))
    )
    url = f"/api/projects/{project_id}/media/file/{segments}"
    if cache_version:
        url = f"{url}?{urlencode({'v': cache_version})}"
    return url


def _preview_cache_version(
    preview_path: Path,
    slot_entry: Any,
) -> str | None:
    if isinstance(slot_entry, dict):
        ref = slot_entry.get("previewArtifactRef")
        if isinstance(ref, dict):
            created_at = ref.get("createdAt")
            if isinstance(created_at, str) and created_at.strip():
                return created_at.strip()
    if preview_path.is_file():
        return str(int(preview_path.stat().st_mtime))
    return None


def _preview_path_from_slot_state(
    generation_root: Path,
    slot_entry: Any,
) -> Path | None:
    if not isinstance(slot_entry, dict):
        return None
    ref = slot_entry.get("previewArtifactRef")
    if not isinstance(ref, dict):
        return None
    uri = ref.get("uri")
    if not isinstance(uri, str) or not uri.strip():
        return None
    path = Path(uri)
    if path.is_file():
        try:
            path.resolve().relative_to(generation_root.resolve())
            return path
        except ValueError:
            pass
    candidate = generation_root / "generated" / path.name
    if candidate.is_file():
        return candidate
    return None


def _resolve_slot_preview_urls(
    *,
    storage_root: Path,
    project_id: str,
    generation_id: str,
    state: dict[str, Any],
) -> dict[str, str]:
    previews: dict[str, str] = {}
    slots = state.get("slots")
    if not isinstance(slots, dict):
        return previews
    generation_root = _generation_root(storage_root, project_id, generation_id)
    plan_path = generation_root / "generation-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.is_file() else {}
    actions = plan.get("completionActions") if isinstance(plan, dict) else []
    terminal_by_slot = terminal_visual_action_by_slot(actions if isinstance(actions, list) else [])
    generated_root = generation_root / "generated"
    for slot_id in slots:
        try:
            validate_storage_segment(str(slot_id), field="slot_id")
        except ValueError:
            continue
        action = terminal_by_slot.get(str(slot_id))
        if not action:
            continue
        preview_path = expected_output_path(action, generated_root)
        if not is_valid_visual_artifact(preview_path):
            preview_path = _preview_path_from_slot_state(
                generation_root,
                slots.get(str(slot_id)),
            ) or preview_path
        if not is_valid_visual_artifact(preview_path):
            continue
        try:
            relative_path = preview_path.relative_to(generation_root).as_posix()
        except ValueError:
            continue
        slot_entry = slots.get(str(slot_id))
        cache_version = _preview_cache_version(preview_path, slot_entry)
        previews[str(slot_id)] = _slot_preview_media_url(
            project_id,
            generation_id,
            relative_path,
            cache_version=cache_version,
        )
    return previews


@router.get("/resolve/by-task/{task_id}")
def resolve_generation_by_task(task_id: str, request: Request) -> dict[str, str]:
    record = _project_store(request).get_generation_by_task_id(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Generation not found for task")
    return {
        "generationId": str(record["id"]),
        "projectId": str(record["projectId"]),
    }


@router.get("/{generation_id}/material-review")
def get_material_review(generation_id: str, request: Request) -> dict[str, Any]:
    store = _project_store(request)
    record = store.get_generation(generation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    storage_root: Path = request.app.state.storage_root
    project_id = str(record["projectId"])
    generation_root = _generation_root(storage_root, project_id, generation_id)
    state_path = generation_root / "material-review-state.json"
    if not state_path.is_file():
        raise HTTPException(status_code=404, detail="Material review state not found")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    reports: dict[str, Any] = {}
    if isinstance(state, dict):
        slots = state.get("slots")
        if isinstance(slots, dict):
            for slot_id in slots:
                try:
                    validate_storage_segment(str(slot_id), field="slot_id")
                except ValueError:
                    continue
                report_path = generation_root / "material-reviews" / str(slot_id) / "report.json"
                if report_path.is_file():
                    reports[str(slot_id)] = json.loads(report_path.read_text(encoding="utf-8"))
    slot_preview_urls = _resolve_slot_preview_urls(
        storage_root=storage_root,
        project_id=project_id,
        generation_id=generation_id,
        state=state if isinstance(state, dict) else {},
    )
    revise_context = _load_material_review_revise_context(generation_root)
    payload: dict[str, Any] = {
        "state": state,
        "reports": reports,
        "slotPreviewUrls": slot_preview_urls,
    }
    if revise_context is not None:
        payload["reviseContext"] = revise_context
    return payload


@router.post("/{generation_id}/material-slots/{slot_id}/revise", status_code=status.HTTP_202_ACCEPTED)
def revise_material_slot(
    generation_id: str,
    slot_id: str,
    payload: MaterialSlotReviseRequest,
    request: Request,
) -> dict[str, Any]:
    validate_storage_segment(slot_id, field="slot_id")
    store = _project_store(request)
    record = store.get_generation(generation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    storage_root: Path = request.app.state.storage_root
    project_id = str(record["projectId"])
    task_id = str(record["taskId"])
    generation_root = _generation_root(storage_root, project_id, generation_id)
    state_path = generation_root / "material-review-state.json"
    if not state_path.is_file():
        raise HTTPException(status_code=404, detail="Material review state not found")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(state, dict) or state.get("status") == "approved":
        raise HTTPException(status_code=400, detail="Material review already approved")
    if not _material_review_gate_active(generation_root):
        raise HTTPException(status_code=400, detail="Generation is not awaiting material review")
    _require_material_review_task_awaiting(request, task_id)
    queue_payload = {
        "generationId": generation_id,
        "slotId": slot_id,
        "instruction": payload.instruction.strip(),
        "requestedBy": "user",
        "status": "pending",
    }
    queue_path = generation_root / "material-slot-revise-queue.json"
    queue_path.write_text(json.dumps(queue_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        _pipeline_runner(request).retry_task(task_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"generationId": generation_id, "taskId": task_id, "slotId": slot_id, "queued": True}


@router.post("/{generation_id}/approve-material", status_code=status.HTTP_202_ACCEPTED)
def approve_material(generation_id: str, request: Request) -> dict[str, Any]:
    store = _project_store(request)
    record = store.get_generation(generation_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    storage_root: Path = request.app.state.storage_root
    project_id = str(record["projectId"])
    task_id = str(record["taskId"])
    generation_root = _generation_root(storage_root, project_id, generation_id)
    state_path = generation_root / "material-review-state.json"
    if not state_path.is_file():
        raise HTTPException(status_code=404, detail="Material review state not found")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if not isinstance(state, dict):
        raise HTTPException(status_code=400, detail="Invalid material review state")
    if state.get("status") == "approved":
        return {"generationId": generation_id, "taskId": task_id, "state": state}
    if not _material_review_gate_active(generation_root):
        raise HTTPException(status_code=400, detail="Generation is not awaiting material review")
    _require_material_review_task_awaiting(request, task_id)
    plan_path = generation_root / "generation-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8")) if plan_path.is_file() else {}
    completion_actions = plan.get("completionActions") if isinstance(plan, dict) else []
    approvable, reason = material_review_approvable(
        state=state,
        completion_actions=completion_actions if isinstance(completion_actions, list) else [],
    )
    if not approvable:
        raise HTTPException(status_code=400, detail=reason)
    state["status"] = "approved"
    from datetime import UTC, datetime

    state["approvedAt"] = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    state["approvedBy"] = "user"
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    checkpoint_path = generation_root / "checkpoint.json"
    if checkpoint_path.is_file():
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        if isinstance(checkpoint, dict):
            checkpoint["awaitingGate"] = None
            checkpoint_path.write_text(
                json.dumps(checkpoint, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
    queue_path = generation_root / "material-slot-revise-queue.json"
    if queue_path.is_file():
        queue_path.unlink()
    try:
        _pipeline_runner(request).retry_task(task_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"generationId": generation_id, "taskId": task_id, "state": state}


def _get_generation_or_404(request: Request, generation_id: str) -> tuple[Any, str]:
    store = _project_store(request)
    source = store.get_generation(generation_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    return store, str(source["projectId"])


def _load_revise_source_context(
    request: Request,
    generation_id: str,
) -> tuple[Any, str, dict[str, Any], dict[str, Any], list[dict[str, Any]], dict[str, Any], str]:
    store, project_id = _get_generation_or_404(request, generation_id)
    source = store.get_generation(generation_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Generation not found")
    if str(source.get("status")) != "succeeded":
        raise HTTPException(
            status_code=400,
            detail="Source generation must be succeeded before revise",
        )
    storage_root: Path = request.app.state.storage_root
    source_plan = source.get("plan")
    if not isinstance(source_plan, dict):
        try:
            source_plan = _load_source_plan(storage_root, project_id, generation_id)
        except FileNotFoundError as exc:
            raise HTTPException(
                status_code=400,
                detail="Source generation has no plan artifacts for revise",
            ) from exc
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
    return store, project_id, source_plan, structure, assets, brief, variant


@router.get("/{generation_id}/revise/session")
def get_revise_session(generation_id: str, request: Request) -> dict[str, Any]:
    from app.services.revise_plan_service import (
        find_latest_draft_plan,
        list_recent_plans,
        load_session,
    )

    _, project_id = _get_generation_or_404(request, generation_id)
    storage_root: Path = request.app.state.storage_root
    session = load_session(storage_root, project_id, generation_id)
    if session is None:
        return {"session": None, "plans": [], "pendingPlan": None}
    plans = list_recent_plans(storage_root, project_id, generation_id, session)
    pending_plan = find_latest_draft_plan(storage_root, project_id, generation_id, session)
    return {"session": session, "plans": plans, "pendingPlan": pending_plan}


@router.post("/{generation_id}/revise/plan")
def plan_revise_generation(
    generation_id: str,
    payload: RevisePlanRequest,
    request: Request,
) -> dict[str, Any]:
    import uuid

    from app.services.revise_plan_service import (
        append_session_turn,
        create_or_load_session,
        save_plan,
        save_session,
        supersede_draft_plans,
    )

    store, project_id, source_plan, *_ = _load_revise_source_context(request, generation_id)
    storage_root: Path = request.app.state.storage_root
    runner = _pipeline_runner(request)

    session = create_or_load_session(
        storage_root,
        project_id,
        generation_id,
        new_session=payload.newSession,
    )
    supersede_draft_plans(storage_root, project_id, generation_id, session)

    try:
        if payload.structured is not None:
            planner_output = runner.build_scene_revise_planner_output(
                payload.structured.model_dump(),
                source_plan=source_plan,
            )
            plan_instruction = str(planner_output.get("conversationSummary") or planner_output.get("summary") or "")
        else:
            plan_instruction = str(payload.instruction or "").strip()
            planner_output = runner.plan_revise_generation(
                project_id=project_id,
                generation_id=generation_id,
                instruction=plan_instruction,
                source_plan=source_plan,
                session=session,
            )
        runner._validate_edit_intents(list(planner_output.get("intents") or []))  # noqa: SLF001
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    turn_id = str(uuid.uuid4())
    plan = runner.enrich_revise_plan(
        planner_output,
        source_generation_id=generation_id,
        instruction=plan_instruction,
        session_id=str(session["sessionId"]),
        turn_id=turn_id,
        source_plan=source_plan,
    )
    try:
        runner._validate_revise_plan(plan)  # noqa: SLF001
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    save_plan(storage_root, project_id, generation_id, plan)
    append_session_turn(
        session,
        {
            "turnId": turn_id,
            "instruction": plan_instruction,
            "planId": plan["planId"],
            "planSummary": plan.get("summary"),
            "costTier": plan.get("costTier"),
            "status": "planned",
            "createdAt": plan["createdAt"],
        },
    )
    if planner_output.get("conversationSummary"):
        session["conversationSummary"] = str(planner_output["conversationSummary"])
    save_session(storage_root, project_id, generation_id, session)

    return {"plan": plan, "sessionId": session["sessionId"]}


@router.post("/{generation_id}/revise/execute", status_code=status.HTTP_202_ACCEPTED)
def execute_revise_plan(
    generation_id: str,
    payload: ReviseExecuteRequest,
    request: Request,
) -> dict[str, Any]:
    from app.services.revise_plan_service import (
        load_plan,
        mark_plan_executing,
        write_revise_patch_context,
    )

    store, project_id, source_plan, structure, assets, brief, variant = _load_revise_source_context(
        request, generation_id,
    )
    storage_root: Path = request.app.state.storage_root
    runner = _pipeline_runner(request)

    try:
        plan = load_plan(storage_root, project_id, generation_id, payload.planId)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if plan is None:
        raise HTTPException(status_code=404, detail="Revise plan not found")
    if str(plan.get("status")) != "draft":
        raise HTTPException(status_code=400, detail="Revise plan is not in draft status")

    intents = list(plan.get("intents") or [])
    instruction = str(plan.get("instruction") or "")
    execution_mode = str(plan.get("executionMode") or "fork")
    plan_id = str(plan["planId"])

    if execution_mode == "in_place":
        task = _task_events(request).create_task(
            project_id,
            stage="applying_revise_patch",
            message="Queued in-place revise patch",
        )
        store.update_generation(generation_id, status="queued", task_id=task["taskId"])
        write_revise_patch_context(
            storage_root,
            project_id,
            generation_id,
            plan_id=plan_id,
            task_id=task["taskId"],
        )
        plan = mark_plan_executing(
            storage_root,
            project_id,
            generation_id,
            plan,
            task_id=task["taskId"],
            result_generation_id=generation_id,
        )
        runner.start_revise_patch(
            project_id=project_id,
            generation_id=generation_id,
            task_id=task["taskId"],
            plan=plan,
        )
        return {
            "sourceGenerationId": generation_id,
            "generationId": generation_id,
            "taskId": task["taskId"],
            "executionMode": "in_place",
            "plan": plan,
        }

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
        instruction=instruction,
        source_generation_id=generation_id,
    )
    plan = mark_plan_executing(
        storage_root,
        project_id,
        generation_id,
        plan,
        task_id=task["taskId"],
        result_generation_id=new_generation["id"],
    )
    runner.start_revise(
        project_id=project_id,
        source_generation_id=generation_id,
        generation_id=new_generation["id"],
        task_id=task["taskId"],
        instruction=instruction,
        intents=intents,
        structure=structure,
        user_brief=brief,
        assets=assets,
        variant=variant,
        finalize_plan_id=plan_id,
    )

    return {
        "sourceGenerationId": generation_id,
        "generationId": new_generation["id"],
        "taskId": task["taskId"],
        "executionMode": "fork",
        "plan": plan,
    }


@router.post("/{generation_id}/revise/cancel")
def cancel_revise_plan(
    generation_id: str,
    payload: ReviseCancelRequest,
    request: Request,
) -> dict[str, Any]:
    from app.services.revise_plan_service import load_plan, load_session, save_plan, save_session

    _, project_id = _get_generation_or_404(request, generation_id)
    storage_root: Path = request.app.state.storage_root
    session = load_session(storage_root, project_id, generation_id)
    if session is None:
        return {"cancelled": False, "cancelledPlanIds": []}

    cancelled_ids: list[str] = []
    for turn in session.get("turns") or []:
        if not isinstance(turn, dict):
            continue
        plan_id = str(turn.get("planId") or "")
        if payload.planId:
            try:
                target_plan_id = validate_storage_segment(payload.planId, field="plan_id")
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc
            if plan_id != target_plan_id:
                continue
        if turn.get("status") != "planned":
            continue
        try:
            plan = load_plan(storage_root, project_id, generation_id, plan_id)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if plan is None or plan.get("status") != "draft":
            continue
        plan["status"] = "cancelled"
        save_plan(storage_root, project_id, generation_id, plan)
        turn["status"] = "cancelled"
        cancelled_ids.append(plan_id)

    save_session(storage_root, project_id, generation_id, session)
    return {"cancelled": bool(cancelled_ids), "planIds": cancelled_ids}


@router.post("/{generation_id}/revise", status_code=status.HTTP_202_ACCEPTED)
def revise_generation(
    generation_id: str,
    payload: ReviseGenerationRequest,
    request: Request,
) -> dict[str, Any]:
    plan_response = plan_revise_generation(
        generation_id,
        RevisePlanRequest(instruction=payload.instruction),
        request,
    )
    plan = plan_response["plan"]
    execute_response = execute_revise_plan(
        generation_id,
        ReviseExecuteRequest(planId=str(plan["planId"])),
        request,
    )
    return {
        "sourceGenerationId": generation_id,
        "generationId": execute_response["generationId"],
        "taskId": execute_response["taskId"],
        "intents": plan.get("intents") or [],
        "plan": plan,
        "executionMode": execute_response.get("executionMode"),
    }
