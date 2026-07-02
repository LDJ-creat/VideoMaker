from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from app.agents.runner import AgentRunner
from app.gateway.model_gateway import ModelGateway
from app.pipelines.material_review import (
    build_failed_review_report,
    build_skipped_review_report,
    check_preview_hard_gates,
    material_review_enabled,
    report_matches_review_artifacts,
    resolve_material_review_route,
    run_slot_review,
    slot_needs_agent_review,
)
from app.pipelines.material_review_state import (
    ensure_material_review_state,
    load_material_review_state,
    update_slot_review_entry,
)
from app.pipelines.revise_material_edit import classify_slot_material_chain
from app.runtime.task_context import TaskContext


def _load_existing_report(generation_root: Path, slot_id: str) -> dict[str, Any] | None:
    report_path = generation_root / "material-reviews" / slot_id / "report.json"
    if not report_path.is_file():
        return None
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _slot_timing_for(
    generation_root: Path,
    slot_id: str,
    storyboard: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    from app.pipelines.revise_material_edit import (
        resolve_slot_timing_from_generation_plan,
        resolve_slot_timing_from_storyboard,
    )

    timing = resolve_slot_timing_from_generation_plan(generation_root, slot_id)
    if timing is None and storyboard:
        timing = resolve_slot_timing_from_storyboard(storyboard, slot_id)
    return timing


def _load_material_spec(generated_root: Path, action: dict[str, Any]) -> dict[str, Any] | None:
    action_id = str(action.get("id") or "")
    if not action_id:
        return None
    spec_path = generated_root / action_id / "material-spec.json"
    if not spec_path.is_file():
        return None
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _resolve_gateway_store(
    gateway: Any | None,
    task_context: TaskContext | None,
    *,
    database_path: str | Path | None = None,
    storage_root: str | Path | None = None,
) -> Any | None:
    if gateway is not None and hasattr(gateway, "store"):
        store = getattr(gateway, "store", None)
        if store is not None:
            return store
    db_path = (
        str(database_path).strip()
        if database_path is not None
        else os.environ.get("VM_DATABASE_PATH", "").strip()
    )
    root: str | None = None
    if task_context is not None:
        root = str(task_context.storage_root)
    elif storage_root is not None:
        root = str(storage_root)
    if db_path and root:
        from model_gateway.store import ModelGatewayStore

        return ModelGatewayStore(Path(db_path), Path(root))
    return None


def _prepare_material_review_observability(
    *,
    gateway: ModelGateway | Any | None,
    task_context: TaskContext | None,
    project_id: str,
    generation_id: str,
    slot_id: str,
) -> tuple[ModelGateway | None, Any | None]:
    live_gateway = gateway if isinstance(gateway, ModelGateway) else None
    if live_gateway is None or task_context is None or not project_id:
        return None, None

    from app.observability.material_review_recorder import setup_material_review_observability

    observability = getattr(live_gateway, "observability", None)
    existing_sink = getattr(observability, "sink", None) if observability is not None else None
    attached_gateway, sink = setup_material_review_observability(
        storage_root=task_context.storage_root,
        project_id=project_id,
        task_id=task_context.task_id,
        generation_id=generation_id,
        slot_id=slot_id,
        gateway=live_gateway,
        sink=existing_sink,
    )
    return attached_gateway, sink


def _build_author_payload(
    *,
    project_id: str,
    generation_id: str,
    generation_root: Path,
    task_id: str | None,
    slot_id: str,
    slot_timing: dict[str, Any] | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "projectId": project_id,
        "generationId": generation_id,
        "generationRoot": str(generation_root),
        "slotId": slot_id,
        "slot": {"id": slot_id},
    }
    if task_id:
        payload["taskId"] = task_id
    if slot_timing:
        payload["slotTiming"] = slot_timing

    task_path = generation_root / "acp-author" / slot_id / "task.json"
    if task_path.is_file():
        try:
            task_payload = json.loads(task_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            task_payload = None
        if isinstance(task_payload, dict):
            for key in (
                "slot",
                "finishBrief",
                "compositionAuthorBrief",
                "renderPolicy",
                "visualStyleBible",
                "renderTarget",
                "variantOverrides",
                "brandColors",
                "layoutDirective",
                "fieldSemantics",
                "materialEditMode",
                "editInstruction",
            ):
                if key in task_payload and task_payload[key] is not None:
                    payload[key] = task_payload[key]
    return payload


def persist_slot_material_review(
    *,
    generation_root: Path,
    generation_id: str,
    project_id: str,
    variant: str,
    action: dict[str, Any],
    plan: dict[str, Any],
    preview_path: Path,
    spec_uri: str | None,
    artifact_ref: dict[str, Any] | None,
    slot_timing: dict[str, Any] | None = None,
    storyboard: list[dict[str, Any]] | None = None,
    gateway: ModelGateway | Any | None = None,
    store: Any | None = None,
    runner: AgentRunner | None = None,
    task_context: TaskContext | None = None,
    generated_root: Path | None = None,
) -> dict[str, Any]:
    if not material_review_enabled():
        return build_skipped_review_report(
            slot_id=str(action.get("slotId") or ""),
            generation_id=generation_id,
            provider=str(action.get("provider") or action.get("strategy") or ""),
        )

    slot_id = str(action.get("slotId") or "")
    ensure_material_review_state(
        generation_root=generation_root,
        generation_id=generation_id,
        project_id=project_id,
        variant=variant,
    )
    completion_actions = list(plan.get("completionActions") or [])
    chain = classify_slot_material_chain(completion_actions, slot_id)
    provider = str(action.get("provider") or action.get("strategy") or "")
    timing = slot_timing or _slot_timing_for(generation_root, slot_id, storyboard)

    spec = None
    if generated_root is not None:
        spec = _load_material_spec(generated_root, action)

    existing = _load_existing_report(generation_root, slot_id)
    needs_agent = slot_needs_agent_review(action, slot_chain=chain)

    if (
        needs_agent
        and existing is not None
        and existing.get("approved")
        and spec is not None
        and preview_path.is_file()
        and report_matches_review_artifacts(existing, spec=spec, preview_path=preview_path)
    ):
        report = dict(existing)
        review_inputs = dict(report.get("reviewInputs") or {})
        review_inputs["videoPath"] = str(preview_path.resolve())
        review_inputs["reviewReuse"] = "in_session"
        report["reviewInputs"] = review_inputs
    elif needs_agent:
        author_payload = _build_author_payload(
            project_id=project_id,
            generation_id=generation_id,
            generation_root=generation_root,
            task_id=task_context.task_id if task_context else None,
            slot_id=slot_id,
            slot_timing=timing,
        )
        resolved_store = store or _resolve_gateway_store(gateway, task_context)
        live_gateway, review_sink = _prepare_material_review_observability(
            gateway=gateway,
            task_context=task_context,
            project_id=project_id,
            generation_id=generation_id,
            slot_id=slot_id,
        )
        if preview_path.is_file() and spec is not None and (live_gateway is not None or (runner and task_context)):
            planned_route = resolve_material_review_route(store=resolved_store, preview_path=preview_path)
            try:
                report = run_slot_review(
                    runner=runner,
                    context=task_context,
                    gateway=live_gateway,
                    store=resolved_store,
                    preview_path=preview_path,
                    spec=spec,
                    author_payload=author_payload,
                    slot_id=slot_id,
                    generation_id=generation_id,
                    generation_root=generation_root,
                    provider=provider,
                    observability_sink=review_sink,
                )
            except Exception as exc:
                expected = float(timing.get("durationSec") or 0.0) if timing else None
                hard_errors = check_preview_hard_gates(preview_path, expected_duration_sec=expected)
                if hard_errors:
                    report = build_skipped_review_report(
                        slot_id=slot_id,
                        generation_id=generation_id,
                        provider=provider,
                        approved=False,
                    )
                    report["hardGateFailed"] = True
                    report["issues"] = hard_errors
                else:
                    report = build_failed_review_report(
                        slot_id=slot_id,
                        generation_id=generation_id,
                        provider=provider,
                        error_message=f"Material review failed: {exc}",
                        route=planned_route,
                        gateway=live_gateway,
                    )
        else:
            expected = float(timing.get("durationSec") or 0.0) if timing else None
            hard_errors = check_preview_hard_gates(preview_path, expected_duration_sec=expected)
            report = build_skipped_review_report(
                slot_id=slot_id,
                generation_id=generation_id,
                provider=provider,
                approved=not hard_errors,
            )
            if hard_errors:
                report["hardGateFailed"] = True
                report["issues"] = hard_errors
    else:
        expected = float(timing.get("durationSec") or 0.0) if timing else None
        hard_errors = check_preview_hard_gates(preview_path, expected_duration_sec=expected)
        report = build_skipped_review_report(
            slot_id=slot_id,
            generation_id=generation_id,
            provider=provider,
            approved=not hard_errors,
        )
        if hard_errors:
            report["hardGateFailed"] = True
            report["issues"] = hard_errors

    report_dir = generation_root / "material-reviews" / slot_id
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    update_slot_review_entry(
        generation_root,
        slot_id=slot_id,
        report=report,
        spec_uri=spec_uri,
        preview_artifact_ref=artifact_ref,
    )
    return report


def finalize_visual_material_reviews(
    *,
    generation_root: Path,
    plan: dict[str, Any],
    project_id: str,
    variant: str,
    structure: dict[str, Any],
    storyboard: list[dict[str, Any]],
    generated_root: Path,
    gateway: Any | None = None,
    runner: AgentRunner | None = None,
    task_context: TaskContext | None = None,
    store: Any | None = None,
    database_path: str | Path | None = None,
    storage_root: str | Path | None = None,
) -> None:
    if not material_review_enabled():
        return

    from app.pipelines.tts_mode import MASTER_TTS_SLOT_ID
    from app.providers.completion_registry import (
        expected_output_path,
        filter_aigc_completion_actions,
        order_completion_actions,
    )

    actions = filter_aigc_completion_actions(list(plan.get("completionActions") or []))
    ordered = order_completion_actions(actions, structure=structure)
    terminal_by_slot: dict[str, dict[str, Any]] = {}
    for action in ordered:
        slot_id = str(action.get("slotId") or "")
        if slot_id and slot_id != MASTER_TTS_SLOT_ID:
            terminal_by_slot[slot_id] = action

    resolved_store = store or _resolve_gateway_store(
        gateway,
        task_context,
        database_path=database_path,
        storage_root=storage_root or (task_context.storage_root if task_context else None),
    )

    for slot_id, action in terminal_by_slot.items():
        state = load_material_review_state(generation_root)
        slots_state = state.get("slots") if isinstance(state, dict) else None
        if isinstance(slots_state, dict) and isinstance(slots_state.get(slot_id), dict):
            if slots_state[slot_id].get("latestReportUri"):
                continue
        preview_path = expected_output_path(action, generated_root)
        if not preview_path.is_file():
            continue
        action_id = str(action.get("id") or f"action-{slot_id}")
        artifact_ref = action.get("artifactRef") if isinstance(action.get("artifactRef"), dict) else None
        persist_slot_material_review(
            generation_root=generation_root,
            generation_id=str(plan.get("id") or generation_root.name),
            project_id=project_id,
            variant=variant,
            action=action,
            plan=plan,
            preview_path=preview_path,
            spec_uri=f"generated/{action_id}/material-spec.json",
            artifact_ref=artifact_ref,
            slot_timing=_slot_timing_for(generation_root, slot_id, storyboard),
            storyboard=storyboard,
            gateway=gateway,
            store=resolved_store,
            runner=runner,
            task_context=task_context,
            generated_root=generated_root,
        )


def all_visual_slots_ready(generation_root: Path, plan: dict[str, Any]) -> bool:
    from material_disk import material_review_approvable

    state = load_material_review_state(generation_root)
    if not isinstance(state, dict):
        return False
    approvable, _reason = material_review_approvable(
        state=state,
        completion_actions=list(plan.get("completionActions") or []),
    )
    return approvable
