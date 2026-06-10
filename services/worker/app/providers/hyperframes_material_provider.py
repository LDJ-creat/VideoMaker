from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from app.agents.material_author import run_material_author_with_runner
from app.composition.engine_factory import create_composition_engine
from app.composition.gateway_adapter import ModelGatewayToolAdapter
from app.providers.base_media_resolver import is_finish_action, resolve_slot_base_media
from app.providers.finish_brief import build_finish_brief_for_action
from app.providers.material_types import MaterialContext, MaterialResult
from app.runtime.agent_run_store import AgentRunLog
from app.tools.hyperframes_material_tool import HyperFramesMaterialTool
from composition.author.coercer import build_author_fallback_spec
from composition.types import AuthorRequest, PatternDepositContext

LOGGER = logging.getLogger(__name__)

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
    for scene in ctx.storyboard:
        if isinstance(scene, dict) and scene.get("slotId") == slot_id:
            return max(0.5, float(scene["endSec"]) - float(scene["startSec"]))
    return 4.0


def _slot_timing_for_slot(ctx: MaterialContext, slot_id: str) -> dict[str, float]:
    for scene in ctx.storyboard:
        if isinstance(scene, dict) and scene.get("slotId") == slot_id:
            start = float(scene.get("startSec", 0.0))
            end = float(scene.get("endSec", start))
            duration = max(0.5, end - start)
            return {
                "startSec": round(start, 3),
                "endSec": round(end, 3),
                "durationSec": round(duration, 3),
            }
    duration = 4.0
    return {"startSec": 0.0, "endSec": duration, "durationSec": duration}


def _enforce_spec_duration(spec: dict[str, Any], duration_sec: float) -> dict[str, Any]:
    merged = dict(spec)
    merged["durationSec"] = round(max(0.5, float(duration_sec)), 3)
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
    base = resolve_slot_base_media(slot_id, ctx.generated_root)
    if base is None:
        return None
    return [base]


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
    }
    if trace_dir:
        summary["reactTraceDir"] = trace_dir
    payload = AgentRunLog(
        agent_name="material_author",
        prompt_version="composition-react-bootstrap",
        model=ctx.runner.model_name,
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
) -> dict[str, Any]:
    author_slot = _material_author_slot(slot)
    slot_timing = _slot_timing_for_slot(ctx, str(slot.get("id", "")))
    target_duration = float(slot_timing["durationSec"])
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
                    finish_brief=finish_brief,
                    aspect_ratio=ctx.aspect_ratio,
                    slot_timing=slot_timing,
                ),
                target_duration,
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
                        finish_brief=finish_brief,
                        task_id=ctx.task_context.task_id if ctx.task_context else None,
                        generation_id=ctx.generation_id,
                        react_trace=react_trace,
                    )
                ),
                target_duration,
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
    max_attempts: int = 2,
) -> dict[str, Any]:
    last_exc: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return _author_spec(ctx, slot, asset_refs, finish_brief=finish_brief)
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

        finish_brief: dict[str, Any] | None = None
        if finish_action or isinstance(action.get("finishBrief"), dict):
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
                    author = _author_spec_with_retry if finish_action else _author_spec
                    spec = author(ctx, slot, asset_refs, finish_brief=finish_brief)
                except Exception:
                    LOGGER.warning(
                        "material_author failed for action %s; falling back to legacy spec",
                        action_id,
                        exc_info=True,
                    )
                    spec = _legacy_fallback_spec(
                        slot,
                        asset_refs,
                        duration_sec=_duration_for_slot(ctx, slot_id),
                    )

        output_dir = ctx.generated_root / action_id / "composition"
        output_clip = expected_hyperframes_output(action, ctx.generated_root)
        log_path = ctx.generated_root / f"{action_id}-render-log.json"
        lint_log_path = ctx.generated_root / f"{action_id}-render-log-lint.json"
        ctx.generated_root.mkdir(parents=True, exist_ok=True)

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

        registered = ctx.register_artifact("video", output_clip)
        ctx.emit_progress(
            "rendering_material",
            f"HyperFrames material ready for slot {slot_id}",
        )

        lint_passed = bool(render_result.get("lintPassed"))
        lint_skipped = bool(render_result.get("lintSkipped"))
        composition_dir = render_result.get("compositionDir")
        resolved_lint_log = render_result.get("lintLogPath") or str(lint_log_path)

        if (
            _composition_mode() != "legacy"
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

        return {
            "ok": True,
            "actionId": action_id,
            "slotId": slot_id,
            "provider": self.name,
            "artifactRef": registered,
            "clipDurationSec": float(render_result.get("durationSec", spec.get("durationSec", 0))),
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
