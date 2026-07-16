from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from app.agents.runner import AgentRunner
    from app.gateway.model_gateway import ModelGateway
    from app.runtime.task_context import TaskContext

from app.pipelines.material_gate_promote import (
    FinalSource,
    marker_report_for_finalize,
)
from app.pipelines.material_review import (
    build_failed_review_report,
    build_skipped_review_report,
    check_preview_hard_gates,
    is_review_infrastructure_error,
    load_gate_author_payload,
    material_review_enabled,
    material_review_gate_llm_enabled,
    report_matches_review_artifacts,
    run_slot_review,
    slot_needs_agent_review,
)
from app.pipelines.material_review_state import (
    ensure_material_review_state,
    load_material_review_state,
    update_slot_review_entry,
)
from app.pipelines.revise_material_edit import classify_slot_material_chain


def _load_existing_report(generation_root: Path, slot_id: str) -> dict[str, Any] | None:
    report_path = generation_root / "material-reviews" / slot_id / "report.json"
    if not report_path.is_file():
        return None
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _load_material_spec(generated_root: Path, action: dict[str, Any]) -> dict[str, Any] | None:
    action_id = str(action.get("id") or "")
    if not action_id:
        return None
    spec_path = generated_root / action_id / "material-spec.json"
    if not spec_path.is_file():
        return None
    payload = json.loads(spec_path.read_text(encoding="utf-8"))
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


def _should_skip_finalize(
    *,
    generation_root: Path,
    slot_id: str,
    spec: dict[str, Any] | None,
    preview_path: Path,
    existing: dict[str, Any] | None,
) -> bool:
    if existing is None or spec is None or not preview_path.is_file():
        return False
    return report_matches_review_artifacts(existing, spec=spec, preview_path=preview_path)


def _maybe_run_gate_llm_review(
    report: dict[str, Any],
    *,
    generation_root: Path,
    generation_id: str,
    project_id: str,
    slot_id: str,
    preview_path: Path,
    spec: dict[str, Any],
    provider: str,
    slot_timing: dict[str, Any] | None,
    final_source: FinalSource | None,
    runner: AgentRunner | None = None,
    context: TaskContext | None = None,
    gateway: ModelGateway | None = None,
    observability_sink: Any | None = None,
) -> dict[str, Any]:
    # Only orphan paths (no in-session marker) may run Gate LLM. Promoted markers
    # (approved or failed-exhausted) must never trigger a second non-feedback review.
    if report.get("reviewPhase") == "promoted" and report.get("reviewBypass") != "no_in_session_marker":
        return report
    if str((report.get("trace") or {}).get("reviewRoute") or "") == "promoted":
        if report.get("reviewBypass") != "no_in_session_marker":
            return report
    if report.get("reviewBypass") != "no_in_session_marker":
        return report
    if not material_review_gate_llm_enabled():
        return report
    if gateway is None:
        return report

    author_payload = load_gate_author_payload(
        generation_root,
        slot_id,
        slot_timing=slot_timing,
        project_id=project_id,
        generation_id=generation_id,
    )
    try:
        reviewed = run_slot_review(
            runner=runner,
            context=context,
            gateway=gateway,
            store=None,
            preview_path=preview_path,
            spec=spec,
            author_payload=author_payload,
            slot_id=slot_id,
            generation_id=generation_id,
            generation_root=generation_root,
            agent_review_round=1,
            provider=provider,
            observability_sink=observability_sink,
        )
    except Exception as exc:
        reviewed = build_failed_review_report(
            slot_id=slot_id,
            generation_id=generation_id,
            provider=provider,
            error_message=str(exc),
            gateway=gateway,
        )
        if is_review_infrastructure_error(str(exc)):
            reviewed["reviewUnavailable"] = True
            reviewed["approved"] = True
            reviewed["issues"] = []

    reviewed["reviewPhase"] = "gate_finalize"
    if final_source:
        reviewed["finalSource"] = final_source
    trace = dict(reviewed.get("trace") or {})
    trace["reviewRoute"] = "gate_finalize"
    reviewed["trace"] = trace
    return reviewed


def finalize_slot_material_gate(
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
    generated_root: Path | None = None,
    final_source: FinalSource | None = None,
    partial_harvest: bool = False,
    runner: AgentRunner | None = None,
    context: TaskContext | None = None,
    gateway: ModelGateway | None = None,
    observability_sink: Any | None = None,
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

    if _should_skip_finalize(
        generation_root=generation_root,
        slot_id=slot_id,
        spec=spec,
        preview_path=preview_path,
        existing=existing,
    ):
        report = dict(existing)  # type: ignore[arg-type]
        review_inputs = dict(report.get("reviewInputs") or {})
        review_inputs["videoPath"] = str(preview_path.resolve())
        review_inputs["reviewReuse"] = "report_reused"
        report["reviewInputs"] = review_inputs
    elif not preview_path.is_file() or preview_path.stat().st_size <= 0:
        report = build_skipped_review_report(
            slot_id=slot_id,
            generation_id=generation_id,
            provider=provider,
            approved=False,
        )
        report["hardGateFailed"] = True
        report["issues"] = ["preview_missing_or_empty"]
        report["reviewPhase"] = "promoted"
        if final_source:
            report["finalSource"] = final_source
    else:
        expected = float(timing.get("durationSec") or 0.0) if timing else None
        if needs_agent and isinstance(spec, dict):
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
                report["reviewPhase"] = "promoted"
                if final_source:
                    report["finalSource"] = final_source
            else:
                resolved_source: FinalSource = final_source or "render"
                report = marker_report_for_finalize(
                    generation_root=generation_root,
                    slot_id=slot_id,
                    spec=spec,
                    final_preview_path=preview_path,
                    generation_id=generation_id,
                    provider=provider,
                    final_source=resolved_source,
                    partial_harvest=partial_harvest,
                )
                report = _maybe_run_gate_llm_review(
                    report,
                    generation_root=generation_root,
                    generation_id=generation_id,
                    project_id=project_id,
                    slot_id=slot_id,
                    preview_path=preview_path,
                    spec=spec,
                    provider=provider,
                    slot_timing=timing,
                    final_source=resolved_source,
                    runner=runner,
                    context=context,
                    gateway=gateway,
                    observability_sink=observability_sink,
                )
        elif not needs_agent:
            from material_disk import is_valid_visual_artifact

            if not is_valid_visual_artifact(preview_path):
                report = build_skipped_review_report(
                    slot_id=slot_id,
                    generation_id=generation_id,
                    provider=provider,
                    approved=False,
                )
                report["hardGateFailed"] = True
                report["issues"] = ["preview_missing_or_invalid"]
                report["reviewPhase"] = "promoted"
            else:
                report = build_skipped_review_report(
                    slot_id=slot_id,
                    generation_id=generation_id,
                    provider=provider,
                    approved=True,
                )
                report["reviewInputs"]["mode"] = "skipped"
                report["reviewPhase"] = "promoted"
                if final_source:
                    report["finalSource"] = final_source
        else:
            report = build_skipped_review_report(
                slot_id=slot_id,
                generation_id=generation_id,
                provider=provider,
                approved=False,
            )
            report["hardGateFailed"] = True
            report["issues"] = ["material_spec_missing"]
            report["reviewPhase"] = "promoted"

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


def finalize_visual_material_gate(
    *,
    generation_root: Path,
    plan: dict[str, Any],
    project_id: str,
    variant: str,
    structure: dict[str, Any],
    storyboard: list[dict[str, Any]],
    generated_root: Path,
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

    for slot_id, action in terminal_by_slot.items():
        preview_path = expected_output_path(action, generated_root)
        if not preview_path.is_file():
            continue
        action_id = str(action.get("id") or f"action-{slot_id}")
        artifact_ref = action.get("artifactRef") if isinstance(action.get("artifactRef"), dict) else None
        spec = _load_material_spec(generated_root, action)
        existing = _load_existing_report(generation_root, slot_id)
        if _should_skip_finalize(
            generation_root=generation_root,
            slot_id=slot_id,
            spec=spec,
            preview_path=preview_path,
            existing=existing,
        ):
            continue
        finalize_slot_material_gate(
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
            generated_root=generated_root,
        )


def all_visual_slots_ready(generation_root: Path, plan: dict[str, Any]) -> bool:
    from material_disk import material_review_approvable

    state = load_material_review_state(generation_root)
    if not isinstance(state, dict):
        return False
    generated_root = generation_root / "generated"
    approvable, _reason = material_review_approvable(
        state=state,
        completion_actions=list(plan.get("completionActions") or []),
        generated_root=generated_root if generated_root.is_dir() else None,
    )
    return approvable


# Backward-compatible aliases
persist_slot_material_review = finalize_slot_material_gate
finalize_visual_material_reviews = finalize_visual_material_gate
