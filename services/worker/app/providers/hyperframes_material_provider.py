from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any, Literal

from app.agents.material_author import run_material_author_with_runner
from app.observability.acp_author_recorder import (
    AcpAuthorObservabilityContext,
    resolve_acp_model_label,
)
from app.composition.engine_factory import create_composition_engine
from app.composition.gateway_adapter import ModelGatewayToolAdapter
from app.providers.base_media_resolver import is_finish_action, resolve_slot_base_media
from app.providers.finish_brief import build_finish_brief_for_action
from app.providers.material_types import MaterialContext, MaterialResult
from app.runtime.agent_run_store import AgentRunLog
from app.tools.hyperframes_material_tool import HyperFramesMaterialTool
from composition.author.coercer import build_author_fallback_spec, build_video_composition_fallback
from composition.author.payload import has_video_asset_refs
from composition.types import AuthorRequest, PatternDepositContext

LOGGER = logging.getLogger(__name__)

MaterialEditMode = Literal["edit", "full"]


def _generation_root(ctx: MaterialContext) -> Path:
    return ctx.generated_root.parent


def _should_defer_pattern_deposit(ctx: MaterialContext) -> bool:
    """Do not block material/revise hot path on optional pattern deposit."""
    if (_generation_root(ctx) / "revise-context.json").is_file():
        return True
    raw = os.getenv("VIDEOMAKER_DEFER_PATTERN_DEPOSIT", "true").strip().lower()
    return raw in {"1", "true", "yes", "on"}


def _resolve_material_edit_author_state(
    ctx: MaterialContext,
    slot_id: str,
) -> tuple[MaterialEditMode, str, dict[str, Any] | None, str | None]:
    from app.pipelines.revise_material_edit import (
        SlotChainKind,
        edit_instruction_from_context,
        load_archived_material_spec,
        load_revise_material_edit_context,
        material_edit_mode_for_slot,
        restore_archived_upstream_media,
        should_degrade_edit_to_full,
    )

    generation_root = _generation_root(ctx)
    from app.pipelines.revise_material_edit import material_edit_context_applies_to_slot

    revise_context = load_revise_material_edit_context(generation_root)
    if revise_context is None or not material_edit_context_applies_to_slot(revise_context, slot_id):
        return "full", "", None, None

    requested_mode = str(revise_context.get("materialEditMode") or "full")
    effective_mode = material_edit_mode_for_slot(revise_context, slot_id)
    instruction = edit_instruction_from_context(revise_context)

    chain_kinds = revise_context.get("slotChainKinds")
    chain_kind = SlotChainKind.UNKNOWN
    if isinstance(chain_kinds, dict):
        try:
            chain_kind = SlotChainKind(str(chain_kinds.get(slot_id) or SlotChainKind.UNKNOWN.value))
        except ValueError:
            chain_kind = SlotChainKind.UNKNOWN

    warning: str | None = None
    if requested_mode == "edit" and effective_mode == "full" and should_degrade_edit_to_full(chain_kind):
        warning = f"槽位 {slot_id} 无 HF spec 可微调，已按完全重生成处理"
    elif requested_mode == "edit" and effective_mode == "edit":
        restore_archived_upstream_media(
            generation_root=generation_root,
            generated_root=ctx.generated_root,
            slot_id=slot_id,
        )

    existing_spec: dict[str, Any] | None = None
    if effective_mode == "edit":
        existing_spec = load_archived_material_spec(generation_root, slot_id)
        if existing_spec is None:
            effective_mode = "full"
            warning = warning or f"槽位 {slot_id} 缺少归档 spec，已按完全重生成处理"

    return effective_mode, instruction, existing_spec, warning

def _legacy_fallback_spec(
    slot: dict[str, Any],
    asset_refs: list[dict[str, Any]] | None,
    *,
    duration_sec: float,
) -> dict[str, Any]:
    return build_author_fallback_spec(
        slot,
        asset_refs=asset_refs,
        duration_sec=duration_sec,
    )


def _tiered_author_fallback(
    action: dict[str, Any],
    slot: dict[str, Any],
    asset_refs: list[dict[str, Any]] | None,
    *,
    duration_sec: float,
    finish_action: bool,
) -> tuple[dict[str, Any], str | None]:
    refs = [ref for ref in (asset_refs or []) if isinstance(ref, dict)]
    strategy = str(action.get("strategy") or "").strip().lower()
    source_provider = str(action.get("sourceProvider") or "").strip().lower()

    if finish_action or strategy == "source_then_polish" or source_provider == "stock_media_search":
        if has_video_asset_refs(refs):
            try:
                return build_video_composition_fallback(slot, refs, duration_sec=duration_sec), None
            except ValueError:
                pass

    if refs:
        return _legacy_fallback_spec(slot, refs, duration_sec=duration_sec), None

    return (
        _legacy_fallback_spec(slot, None, duration_sec=duration_sec),
        "ACP 作者失败，已降级为占位素材",
    )


def _slot_by_id(structure: dict[str, Any], slot_id: str) -> dict[str, Any]:
    for slot in structure.get("slots", []):
        if isinstance(slot, dict) and slot.get("id") == slot_id:
            return slot
    raise ValueError(f"Structure slot not found: {slot_id}")


def _material_author_slot(slot: dict[str, Any]) -> dict[str, Any]:
    from composition.author.forbidden_copy_guard import normalize_author_slot

    return normalize_author_slot(
        {
            "role": slot.get("role"),
            "scriptIntent": slot.get("scriptIntent", ""),
            "visualIntent": slot.get("visualIntent", ""),
            "importance": slot.get("importance"),
            "requiredAssetType": list(slot.get("requiredAssetType") or []),
        }
    )


def _duration_for_slot(ctx: MaterialContext, slot_id: str) -> float:
    return float(_slot_timing_for_slot(ctx, slot_id)["durationSec"])


def _slot_timing_for_slot(ctx: MaterialContext, slot_id: str) -> dict[str, float]:
    from app.pipelines.revise_material_edit import resolve_slot_timing_for_material_author

    generation_root = _generation_root(ctx)
    return resolve_slot_timing_for_material_author(
        generation_root,
        slot_id,
        storyboard_fallback=list(ctx.storyboard),
    )


def _enforce_spec_duration(
    spec: dict[str, Any],
    duration_sec: float,
    *,
    prefer_duration_sec: float | None = None,
) -> dict[str, Any]:
    from app.pipelines.revise_material_edit import resolve_spec_duration_sec

    merged = dict(spec)
    merged["durationSec"] = resolve_spec_duration_sec(
        spec,
        duration_sec,
        prefer_duration_sec=prefer_duration_sec,
    )
    return merged


def _resolve_material_asset_refs(
    action: dict[str, Any],
    ctx: MaterialContext,
    *,
    slot_id: str,
) -> list[dict[str, Any]] | None:
    refs = action.get("assetRefs")
    if isinstance(refs, list) and refs:
        return refs

    generation_root = _generation_root(ctx)
    from app.pipelines.revise_material_edit import SlotChainKind, load_revise_material_edit_context

    revise_context = load_revise_material_edit_context(generation_root)
    completion_mode = str(action.get("completionMode") or "").strip().lower()
    if revise_context and isinstance(revise_context.get("slotChainKinds"), dict):
        raw_kind = revise_context["slotChainKinds"].get(slot_id)
        try:
            chain_kind = SlotChainKind(str(raw_kind)) if raw_kind else SlotChainKind.UNKNOWN
        except ValueError:
            chain_kind = SlotChainKind.UNKNOWN
        if chain_kind == SlotChainKind.HF_ONLY and completion_mode == "hf_native":
            return None

    base = resolve_slot_base_media(slot_id, ctx.generated_root)
    if base is None:
        return None
    return [base]


def _try_harvest_acp_partial_spec(ctx: MaterialContext, slot_id: str) -> dict[str, Any] | None:
    generation_root = _generation_root(ctx)
    scratch = generation_root / "acp-author" / slot_id
    spec_path = scratch / "material-spec.json"
    lint_marker = scratch / "material-spec.lint-passed"
    if not spec_path.is_file() or not lint_marker.is_file():
        return None
    try:
        payload = json.loads(spec_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if str(payload.get("template") or "") != "composition":
        return None
    composition = payload.get("composition")
    if not isinstance(composition, dict) or not str(composition.get("bodyHtml") or "").strip():
        return None
    return payload


def _relative_asset_ref(base_media: dict[str, Any], generated_root: Path) -> dict[str, Any]:
    uri = str(base_media.get("uri", ""))
    path = Path(uri)
    if path.is_file():
        try:
            rel = path.relative_to(generated_root.resolve())
            return {
                **base_media,
                "uri": rel.as_posix(),
            }
        except ValueError:
            pass
    return base_media


def expected_hyperframes_output(action: dict[str, Any], generated_root: Path) -> Path:
    slot_id = str(action["slotId"])
    action_id = str(action.get("id") or f"action-{slot_id}")
    return generated_root / f"{action_id}.mp4"


def _author_backend() -> str:
    return os.getenv("VIDEOMAKER_COMPOSITION_AUTHOR_BACKEND", "react").strip().lower()


def _composition_mode() -> str:
    return os.getenv("VIDEOMAKER_COMPOSITION_MODE", "hybrid").strip().lower()


def _agent_mode_label() -> str:
    return os.getenv("VIDEOMAKER_COMPOSITION_AGENT_MODE", "react").strip().lower()


def _record_material_author_run(
    ctx: MaterialContext,
    *,
    slot: dict[str, Any],
    valid: bool,
    latency_ms: float,
    errors: list[str],
    trace_dir: str | None = None,
) -> None:
    if ctx.runner is None or ctx.task_context is None:
        return
    summary: dict[str, Any] = {
        "mode": _agent_mode_label(),
        "compositionMode": _composition_mode(),
        "slotRole": slot.get("role"),
        "slotId": slot.get("id"),
    }
    backend = _author_backend()
    model_name = ctx.runner.model_name
    if backend == "acp":
        summary["backend"] = "acp"
        from app.composition.acp.author import resolve_acp_agent_label

        summary["acpAgent"] = resolve_acp_agent_label()
        model_name = resolve_acp_model_label()
    if trace_dir:
        key = "acpTraceDir" if backend == "acp" else "reactTraceDir"
        summary[key] = trace_dir
    prompt_version = "composition-acp-v1" if backend == "acp" else "composition-react-bootstrap"
    payload = AgentRunLog(
        agent_name="material_author",
        prompt_version=prompt_version,
        model=model_name,
        task="material_author",
        input_summary=json.dumps(summary, ensure_ascii=False)[:500],
        output_valid=valid,
        latency_ms=latency_ms,
        task_id=ctx.task_context.task_id,
        generation_id=ctx.generation_id,
        validation_errors=errors,
    ).to_payload()
    payload["projectId"] = ctx.project_id
    ctx.runner.observability_sink.record_agent_run(payload)


def _author_spec(
    ctx: MaterialContext,
    slot: dict[str, Any],
    asset_refs: list[dict[str, Any]] | None,
    *,
    finish_brief: dict[str, Any] | None = None,
    material_edit_mode: MaterialEditMode = "full",
    edit_instruction: str = "",
    existing_material_spec: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from app.pipelines.revise_material_edit import (
        build_edit_finish_brief,
        resolve_slot_timing_for_revise,
    )

    author_slot = _material_author_slot(slot)
    slot_id = str(slot.get("id", ""))
    author_finish_brief = finish_brief
    if material_edit_mode == "edit" and edit_instruction:
        author_finish_brief = build_edit_finish_brief(finish_brief, instruction=edit_instruction)
    elif material_edit_mode == "full" and edit_instruction:
        author_finish_brief = build_edit_finish_brief(finish_brief, instruction=edit_instruction)

    generation_root = _generation_root(ctx)
    slot_timing = resolve_slot_timing_for_revise(
        generation_root,
        list(ctx.storyboard),
        slot_id,
        existing_spec=existing_material_spec,
        finish_brief=author_finish_brief,
    )
    target_duration = float(slot_timing["durationSec"])
    prefer_duration: float | None = None
    if material_edit_mode == "edit":
        if isinstance(existing_material_spec, dict) and existing_material_spec.get("durationSec") is not None:
            prefer_duration = float(existing_material_spec["durationSec"])
        elif isinstance(author_finish_brief, dict) and author_finish_brief.get("durationSec") is not None:
            prefer_duration = float(author_finish_brief["durationSec"])
        if prefer_duration is not None:
            target_duration = min(prefer_duration, float(slot_timing["durationSec"]))
    started = time.perf_counter()
    errors: list[str] = []
    trace_dir: str | None = None
    try:
        if _composition_mode() == "legacy" or ctx.runner is None or ctx.task_context is None:
            if ctx.runner is None or ctx.task_context is None:
                raise RuntimeError("material author unavailable")
            spec = _enforce_spec_duration(
                run_material_author_with_runner(
                    ctx.runner,
                    slot=author_slot,
                    context=ctx.task_context,
                    variant_overrides=ctx.variant_overrides,
                    brand_colors=ctx.brand_colors,
                    asset_refs=asset_refs,
                    visual_style_bible=ctx.visual_style_bible,
                    generation_id=ctx.generation_id,
                    finish_brief=author_finish_brief,
                    aspect_ratio=ctx.aspect_ratio,
                    slot_timing=slot_timing,
                    material_edit_mode=material_edit_mode,
                    edit_instruction=edit_instruction or None,
                    existing_material_spec=existing_material_spec,
                ),
                target_duration,
                prefer_duration_sec=prefer_duration,
            )
        else:
            backend = _author_backend()
            if backend == "acp":
                from app.composition.acp.author import (
                    AcpAuthorUnavailableError,
                    author_material_spec_via_acp,
                    ensure_acp_dependencies,
                    resolve_acp_agent_label,
                )
                from app.composition.acp.trace import AcpAuthorTraceRecorder

                try:
                    ensure_acp_dependencies()
                except AcpAuthorUnavailableError as exc:
                    raise RuntimeError(str(exc)) from exc

                acp_trace = None
                acp_observability = None
                if ctx.task_context is not None and ctx.project_id:
                    acp_trace = AcpAuthorTraceRecorder.create(
                        ctx.storage_root,
                        project_id=ctx.project_id,
                        acp_agent=resolve_acp_agent_label(),
                        task_id=ctx.task_context.task_id,
                        generation_id=ctx.generation_id,
                    )
                    trace_dir = str(acp_trace.trace_dir)
                    if ctx.runner is not None:
                        acp_observability = AcpAuthorObservabilityContext.from_trace(
                            sink=ctx.runner.observability_sink,
                            trace_dir=acp_trace.trace_dir,
                            project_id=ctx.project_id,
                            task_id=ctx.task_context.task_id,
                            generation_id=ctx.generation_id,
                            slot_id=str(slot.get("id", "")),
                            acp_agent=resolve_acp_agent_label(),
                        )
                spec = _enforce_spec_duration(
                    author_material_spec_via_acp(
                        AuthorRequest(
                            project_id=ctx.project_id,
                            slot=author_slot,
                            brand_colors=ctx.brand_colors,
                            variant_overrides=ctx.variant_overrides,
                            asset_refs=asset_refs,
                            aspect_ratio=ctx.aspect_ratio,
                            slot_timing=slot_timing,
                            visual_style_bible=ctx.visual_style_bible,
                            finish_brief=author_finish_brief,
                            task_id=ctx.task_context.task_id if ctx.task_context else None,
                            generation_id=ctx.generation_id,
                            generation_root=_generation_root(ctx),
                            material_edit_mode=material_edit_mode,
                            edit_instruction=edit_instruction or None,
                            existing_material_spec=existing_material_spec,
                        ),
                        storage_root=ctx.storage_root,
                        generated_root=ctx.generated_root,
                        slot_id=str(slot.get("id", "")),
                        trace=acp_trace,
                        observability=acp_observability,
                    ),
                    target_duration,
                    prefer_duration_sec=prefer_duration,
                )
            else:
                from composition.author.react_trace import FileReactTraceRecorder

                react_trace = None
                if ctx.task_context is not None and ctx.project_id:
                    react_trace = FileReactTraceRecorder.create(
                        ctx.storage_root,
                        project_id=ctx.project_id,
                        task_id=ctx.task_context.task_id,
                        generation_id=ctx.generation_id,
                        model=ctx.runner.model_name if ctx.runner is not None else None,
                    )
                    trace_dir = str(react_trace.trace_dir)
                engine = create_composition_engine(
                    gateway=ModelGatewayToolAdapter(ctx.gateway),
                    storage_root=ctx.storage_root,
                    emit_progress=ctx.emit_progress,
                )
                spec = _enforce_spec_duration(
                    engine.author_material_spec(
                        AuthorRequest(
                            project_id=ctx.project_id,
                            slot=author_slot,
                            brand_colors=ctx.brand_colors,
                            variant_overrides=ctx.variant_overrides,
                            asset_refs=asset_refs,
                            aspect_ratio=ctx.aspect_ratio,
                            slot_timing=slot_timing,
                            visual_style_bible=ctx.visual_style_bible,
                            finish_brief=author_finish_brief,
                            task_id=ctx.task_context.task_id if ctx.task_context else None,
                            generation_id=ctx.generation_id,
                            generation_root=_generation_root(ctx),
                            react_trace=react_trace,
                            material_edit_mode=material_edit_mode,
                            edit_instruction=edit_instruction or None,
                            existing_material_spec=existing_material_spec,
                            review_gateway=ctx.gateway,
                        )
                    ),
                    target_duration,
                    prefer_duration_sec=prefer_duration,
                )
        _record_material_author_run(
            ctx,
            slot=slot,
            valid=True,
            latency_ms=(time.perf_counter() - started) * 1000,
            errors=[],
            trace_dir=trace_dir,
        )
        return spec
    except Exception as exc:
        errors = [str(exc)]
        _record_material_author_run(
            ctx,
            slot=slot,
            valid=False,
            latency_ms=(time.perf_counter() - started) * 1000,
            errors=errors,
            trace_dir=trace_dir,
        )
        raise


def _author_spec_with_retry(
    ctx: MaterialContext,
    slot: dict[str, Any],
    asset_refs: list[dict[str, Any]] | None,
    *,
    finish_brief: dict[str, Any] | None = None,
    material_edit_mode: MaterialEditMode = "full",
    edit_instruction: str = "",
    existing_material_spec: dict[str, Any] | None = None,
    max_attempts: int = 2,
) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return _author_spec(
                ctx,
                slot,
                asset_refs,
                finish_brief=finish_brief,
                material_edit_mode=material_edit_mode,
                edit_instruction=edit_instruction,
                existing_material_spec=existing_material_spec,
            )
        except Exception as exc:
            last_exc = exc
            if attempt >= max_attempts:
                break
            LOGGER.warning(
                "material_author attempt %s/%s failed for slot %s: %s",
                attempt,
                max_attempts,
                slot.get("id"),
                exc,
            )
    assert last_exc is not None
    raise last_exc


class HyperFramesMaterialProvider:
    name = "hyperframes_material"

    def __init__(self, tool: HyperFramesMaterialTool | None = None) -> None:
        self._tool = tool

    def execute(self, action: dict[str, Any], ctx: MaterialContext) -> MaterialResult:
        slot_id = str(action["slotId"])
        action_id = str(action.get("id") or f"action-{slot_id}")
        try:
            slot = _slot_by_id(ctx.structure, slot_id)
        except ValueError as exc:
            return _failure(action, slot_id, code="slot_not_found", message=str(exc))

        slot_role = str(slot.get("role") or "")
        finish_action = is_finish_action(action_id)
        base_media = resolve_slot_base_media(slot_id, ctx.generated_root)
        asset_refs = _resolve_material_asset_refs(action, ctx, slot_id=slot_id)
        if asset_refs and base_media:
            asset_refs = [_relative_asset_ref(ref, ctx.generated_root) for ref in asset_refs]

        finish_brief = build_finish_brief_for_action(
            action=action,
            slot=slot,
            storyboard=list(ctx.storyboard),
            gap_item=None,
            base_media=_relative_asset_ref(base_media, ctx.generated_root) if base_media else None,
            packaging_plan=ctx.packaging_plan,
            source_provider=str(action.get("sourceProvider") or ""),
            duration_sec=_duration_for_slot(ctx, slot_id),
        )

        material_edit_mode, edit_instruction, existing_material_spec, edit_warning = (
            _resolve_material_edit_author_state(ctx, slot_id)
        )
        if edit_instruction:
            from app.pipelines.revise_material_edit import build_edit_finish_brief

            finish_brief = build_edit_finish_brief(finish_brief, instruction=edit_instruction)
        if edit_warning:
            ctx.emit_progress("rendering_material", edit_warning)

        partial_harvest = False
        spec = action.get("materialSpec")
        if spec is None:
            if ctx.runner is None or ctx.task_context is None:
                if asset_refs:
                    spec = _legacy_fallback_spec(
                        slot,
                        asset_refs,
                        duration_sec=_duration_for_slot(ctx, slot_id),
                    )
                else:
                    return _failure(
                        action,
                        slot_id,
                        code="material_author_unavailable",
                        message="materialSpec missing and AgentRunner/TaskContext not configured",
                        retryable=False,
                    )
            else:
                try:
                    author = _author_spec_with_retry
                    spec = author(
                        ctx,
                        slot,
                        asset_refs,
                        finish_brief=finish_brief,
                        material_edit_mode=material_edit_mode,
                        edit_instruction=edit_instruction,
                        existing_material_spec=existing_material_spec,
                    )
                except Exception:
                    LOGGER.warning(
                        "material_author failed for action %s; falling back to legacy spec",
                        action_id,
                        exc_info=True,
                    )
                    partial_spec = _try_harvest_acp_partial_spec(ctx, slot_id)
                    if partial_spec is not None:
                        spec = partial_spec
                        partial_harvest = True
                        ctx.emit_progress(
                            "rendering_material",
                            f"槽位 {slot_id} ACP 未完整结束，已采用 lint 通过的 composition spec",
                        )
                    else:
                        spec, fallback_warning = _tiered_author_fallback(
                            action,
                            slot,
                            asset_refs,
                            duration_sec=_duration_for_slot(ctx, slot_id),
                            finish_action=finish_action,
                        )
                        if fallback_warning:
                            ctx.emit_progress(
                                "rendering_material",
                                f"槽位 {slot_id}: {fallback_warning}",
                            )

        if isinstance(spec, dict):
            slot_timing = _slot_timing_for_slot(ctx, slot_id)
            from app.pipelines.composition_validator import validate_material_spec_duration

            spec = _enforce_spec_duration(
                spec,
                float(slot_timing["durationSec"]),
                prefer_duration_sec=float(slot_timing["durationSec"]),
            )
            duration_errors = validate_material_spec_duration(
                spec=spec,
                slot_timing=slot_timing,
            )
            if duration_errors:
                return _failure(
                    action,
                    slot_id,
                    code="material_spec_duration_exceeded",
                    message=duration_errors[0],
                    retryable=False,
                )

        generation_root = _generation_root(ctx)
        scratch_dir = generation_root / "acp-author" / slot_id
        force_render = material_edit_mode == "edit"
        from app.pipelines.material_gate_promote import (
            materialize_final_to_generated,
            should_materialize_final,
        )

        materialize_mode = should_materialize_final(
            scratch_dir=scratch_dir,
            spec=spec if isinstance(spec, dict) else None,
            force_render=force_render,
        )

        output_dir = ctx.generated_root / action_id / "composition"
        output_clip = expected_hyperframes_output(action, ctx.generated_root)
        log_path = ctx.generated_root / f"{action_id}-render-log.json"
        lint_log_path = ctx.generated_root / f"{action_id}-render-log-lint.json"
        ctx.generated_root.mkdir(parents=True, exist_ok=True)

        from composition.build.media_staging import ensure_base_video_aliases_in_asset_root

        composition = spec.get("composition") if isinstance(spec, dict) else None
        if isinstance(composition, dict):
            body_html = str(composition.get("bodyHtml") or "")
            if body_html.strip():
                ensure_base_video_aliases_in_asset_root(body_html, ctx.generated_root)

        final_source: str | None = None
        skipped_render = False
        render_result: dict[str, Any] = {}

        if materialize_mode == "copy_preview":
            mat_result = materialize_final_to_generated(
                scratch_dir=scratch_dir,
                generated_root=ctx.generated_root,
                action_id=action_id,
                spec=spec if isinstance(spec, dict) else None,
                mode=materialize_mode,
            )
            if mat_result.ok and mat_result.final_path is not None:
                output_clip = mat_result.final_path
                final_source = mat_result.final_source
                skipped_render = True
            else:
                materialize_mode = "render"

        if not skipped_render:
            if materialize_mode == "skip":
                return _failure(
                    action,
                    slot_id,
                    code="material_render_failed",
                    message="No preview or spec available to materialize slot output",
                    retryable=False,
                )
            tool = self._tool or HyperFramesMaterialTool(emit_progress=ctx.emit_progress)
            render_result = tool.render_material(
                spec,
                project_root=ctx.project_root,
                output_dir=output_dir,
                output_clip=output_clip,
                log_path=log_path,
                asset_root=ctx.generated_root,
                aspect_ratio=ctx.aspect_ratio,
            )
            if not render_result.get("ok"):
                error = render_result.get("error") or {}
                return {
                    "ok": False,
                    "actionId": action_id,
                    "slotId": slot_id,
                    "provider": self.name,
                    "error": {
                        "code": str(error.get("code", "material_render_failed")),
                        "message": str(error.get("message", "HyperFrames material render failed")),
                        "retryable": bool(error.get("retryable", False)),
                    },
                }
            final_source = "render"

        registered = ctx.register_artifact("video", output_clip)
        ctx.emit_progress(
            "rendering_material",
            f"HyperFrames material ready for slot {slot_id}",
        )

        lint_passed = bool(render_result.get("lintPassed")) if not skipped_render else True
        lint_skipped = bool(render_result.get("lintSkipped")) if not skipped_render else True
        composition_dir = render_result.get("compositionDir") if not skipped_render else str(output_dir)
        resolved_lint_log = (
            render_result.get("lintLogPath") or str(lint_log_path) if not skipped_render else ""
        )

        if (
            not _should_defer_pattern_deposit(ctx)
            and _composition_mode() != "legacy"
            and composition_dir
            and lint_passed
            and not lint_skipped
        ):
            try:
                engine = create_composition_engine(storage_root=ctx.storage_root)
                engine.deposit_pattern_candidate(
                    PatternDepositContext(
                        storage_root=ctx.storage_root,
                        project_id=ctx.project_id,
                        generation_id=ctx.generation_id,
                        slot_id=slot_id,
                        slot_role=slot_role,
                        spec=spec,
                        composition_dir=Path(str(composition_dir)),
                        lint_passed=True,
                        render_passed=True,
                        lint_log_path=Path(resolved_lint_log) if resolved_lint_log else None,
                    )
                )
            except ValueError as exc:
                LOGGER.info("composition pattern deposit skipped: %s", exc)
            except Exception:
                LOGGER.exception("composition pattern deposit failed")

        from app.pipelines.revise_material_edit import persist_material_spec_after_render

        persist_material_spec_after_render(
            spec=spec,
            generated_root=ctx.generated_root,
            action_id=action_id,
        )

        from app.pipelines.material_gate_finalize import finalize_slot_material_gate
        from app.pipelines.revise_material_edit import (
            resolve_slot_timing_from_generation_plan,
            resolve_slot_timing_from_storyboard,
        )

        plan_path = generation_root / "generation-plan.json"
        plan_payload: dict[str, Any] = {"completionActions": []}
        if plan_path.is_file():
            loaded = json.loads(plan_path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                plan_payload = loaded
        plan_storyboard = plan_payload.get("storyboard")
        storyboard_source = (
            list(plan_storyboard) if isinstance(plan_storyboard, list) else list(ctx.storyboard)
        )
        slot_timing = resolve_slot_timing_from_generation_plan(generation_root, slot_id)
        if slot_timing is None:
            slot_timing = resolve_slot_timing_from_storyboard(storyboard_source, slot_id)
        finalize_slot_material_gate(
            generation_root=generation_root,
            generation_id=ctx.generation_id,
            project_id=ctx.project_id,
            variant=str(plan_payload.get("variant") or "default"),
            action=action,
            plan=plan_payload,
            preview_path=output_clip,
            spec_uri=f"generated/{action_id}/material-spec.json",
            artifact_ref=registered if isinstance(registered, dict) else None,
            slot_timing=slot_timing,
            storyboard=list(plan_payload.get("storyboard") or ctx.storyboard),
            generated_root=ctx.generated_root,
            final_source=final_source,  # type: ignore[arg-type]
            partial_harvest=partial_harvest,
        )
        ctx.emit_progress(
            "reviewing_material",
            f"Material preview ready for slot {slot_id}",
        )

        return {
            "ok": True,
            "actionId": action_id,
            "slotId": slot_id,
            "provider": self.name,
            "artifactRef": registered,
            "clipDurationSec": float(
                render_result.get("durationSec", spec.get("durationSec", 0) if isinstance(spec, dict) else 0)
            ),
        }


def _failure(
    action: dict[str, Any],
    slot_id: str,
    *,
    code: str,
    message: str,
    retryable: bool = False,
) -> MaterialResult:
    return {
        "ok": False,
        "actionId": str(action.get("id", "")),
        "slotId": slot_id,
        "provider": "hyperframes_material",
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
        },
    }
