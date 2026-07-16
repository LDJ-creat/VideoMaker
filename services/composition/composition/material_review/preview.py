from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def _should_waive_review_infrastructure_error(message: str) -> bool:
    """Local guard so observability schema drift never blocks material review."""
    lowered = str(message or "").lower()
    return "invalid agentrunlog" in lowered or (
        "tokenusage" in lowered and "additional properties" in lowered
    )


def render_material_preview_spec(
    spec: dict[str, Any],
    *,
    scratch_dir: Path,
    repo_root: Path,
    aspect_ratio: str = "9:16",
    asset_root: Path | None = None,
    engine: Any | None = None,
    preview_profile: str = "full",
) -> dict[str, Any]:
    from composition.api import CompositionEngine
    from composition.types import RenderPaths

    scratch_dir.mkdir(parents=True, exist_ok=True)
    output_dir = scratch_dir / "preview-composition"
    output_clip = scratch_dir / "preview.mp4"
    log_path = scratch_dir / "preview-render-log.json"
    composition_engine = engine or CompositionEngine(repo_root=repo_root)
    result = composition_engine.render_clip(
        spec,
        RenderPaths(
            project_root=repo_root,
            output_dir=output_dir,
            output_clip=output_clip,
            log_path=log_path,
            asset_root=asset_root,
            aspect_ratio=aspect_ratio,
            preview_profile=preview_profile if preview_profile in {"full", "fast"} else "full",
        ),
    )
    if not result.ok:
        error = result.error or {}
        return {
            "ok": False,
            "error": {
                "code": str(error.get("code", "preview_render_failed")),
                "message": str(error.get("message", "preview render failed")),
            },
        }
    duration = float(spec.get("durationSec") or 0.0)
    return {
        "ok": True,
        "previewPath": str(output_clip.resolve()),
        "durationSec": duration,
    }


def run_review_via_worker(
    *,
    preview_path: Path,
    spec: dict[str, Any],
    author_payload: dict[str, Any],
    slot_id: str,
    generation_id: str,
    generation_root: Path | None = None,
    agent_review_round: int = 1,
    gateway: Any | None = None,
) -> dict[str, Any]:
    try:
        from app.pipelines.material_review import run_slot_review
        from app.runtime.task_context import TaskContext
        from app.observability.material_review_recorder import (
            acp_parent_observability_run_id,
            build_material_review_runner,
            record_material_review_tool_run,
            setup_material_review_observability,
        )
    except ImportError as exc:
        return {
            "ok": False,
            "error": {"code": "review_worker_unavailable", "message": str(exc)},
        }

    if generation_root is not None:
        generation_root = Path(generation_root)

    from app.pipelines.material_review_finalize import (
        _resolve_gateway_store,
        resolve_database_path,
        resolve_storage_root_path,
    )

    store = None
    runner = None
    sink = None
    storage_root_path = resolve_storage_root_path(
        os.environ.get("VM_STORAGE_ROOT", "").strip() or None,
        generation_root=generation_root,
    )
    if storage_root_path is None:
        storage_root_path = Path(".")
    database_path = resolve_database_path(
        os.environ.get("VM_DATABASE_PATH", "").strip() or None,
        storage_root=storage_root_path,
    )
    project_id = str(author_payload.get("projectId") or "")
    task_id = str(author_payload.get("taskId") or "mcp-review")
    context = TaskContext(
        task_id=task_id,
        project_id=project_id,
        storage_root=storage_root_path,
    )
    if gateway is None:
        store = _resolve_gateway_store(
            None,
            context,
            database_path=database_path,
            storage_root=storage_root_path,
            generation_root=generation_root,
        )
        if store is not None:
            from app.gateway.model_gateway import ModelGateway

            gateway = ModelGateway.from_store(store)
    elif store is None:
        store = _resolve_gateway_store(
            gateway,
            context,
            database_path=database_path,
            storage_root=storage_root_path,
            generation_root=generation_root,
        )

    if gateway is not None and project_id:
        gateway, sink = setup_material_review_observability(
            storage_root=storage_root_path,
            project_id=project_id,
            task_id=task_id,
            generation_id=generation_id,
            slot_id=slot_id,
            gateway=gateway,
        )
        if sink is not None and runner is None:
            runner = build_material_review_runner(gateway=gateway, sink=sink)

    started = time.perf_counter()
    try:
        report = run_slot_review(
            runner=runner,
            context=context,
            gateway=gateway,
            store=store,
            preview_path=preview_path,
            spec=spec,
            author_payload=author_payload,
            slot_id=slot_id,
            generation_id=generation_id,
            generation_root=generation_root,
            agent_review_round=agent_review_round,
            observability_sink=sink,
        )
        if sink is not None and project_id:
            record_material_review_tool_run(
                sink=sink,
                project_id=project_id,
                task_id=task_id,
                generation_id=generation_id,
                slot_id=slot_id,
                preview_path=preview_path,
                ok=True,
                report=report,
                parent_observability_run_id=acp_parent_observability_run_id(),
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        return {"ok": True, "report": report}
    except Exception as exc:
        message = str(exc)
        if sink is not None and project_id:
            try:
                record_material_review_tool_run(
                    sink=sink,
                    project_id=project_id,
                    task_id=task_id,
                    generation_id=generation_id,
                    slot_id=slot_id,
                    preview_path=preview_path,
                    ok=False,
                    error={"code": "review_failed", "message": message},
                    parent_observability_run_id=acp_parent_observability_run_id(),
                    latency_ms=(time.perf_counter() - started) * 1000,
                )
            except Exception:
                pass
        from app.pipelines.material_review import (
            build_failed_review_report,
            is_review_infrastructure_error,
        )

        if (
            _should_waive_review_infrastructure_error(message)
            or is_review_infrastructure_error(message)
        ):
            report = build_failed_review_report(
                slot_id=slot_id,
                generation_id=generation_id,
                provider="hyperframes_material",
                error_message=message,
            )
            return {"ok": True, "report": report}
        return {"ok": False, "error": {"code": "review_failed", "message": message}}


def review_material_preview_tool(
    *,
    spec_json: dict[str, Any],
    scratch_dir: Path,
    repo_root: Path,
    author_payload: dict[str, Any],
    aspect_ratio: str,
    asset_root: Path | None,
    review_gateway: Any | None = None,
) -> str:
    from composition.material_review.session import marker_path, validate_review_marker

    if validate_review_marker(scratch_dir, spec_json) is None:
        try:
            marker_payload = json.loads(marker_path(scratch_dir).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            marker_payload = None
        cached_report = (
            marker_payload.get("report")
            if isinstance(marker_payload, dict) and isinstance(marker_payload.get("report"), dict)
            else None
        )
        if isinstance(cached_report, dict) and cached_report.get("approved"):
            return json.dumps(
                {"ok": True, "report": cached_report, "cached": True},
                ensure_ascii=False,
            )

    preview_path = scratch_dir / "preview.mp4"
    if not preview_path.is_file():
        render_result = render_material_preview_spec(
            spec_json,
            scratch_dir=scratch_dir,
            repo_root=repo_root,
            aspect_ratio=aspect_ratio,
            asset_root=asset_root,
        )
        if not render_result.get("ok"):
            return json.dumps(render_result, ensure_ascii=False)
        preview_path = Path(str(render_result["previewPath"]))

    slot = author_payload.get("slot") if isinstance(author_payload.get("slot"), dict) else {}
    slot_id = str(slot.get("id") or author_payload.get("slotId") or "slot")
    generation_id = str(author_payload.get("generationId") or "generation")
    generation_root_raw = author_payload.get("generationRoot")
    generation_root = Path(generation_root_raw) if generation_root_raw else None

    review_result = run_review_via_worker(
        preview_path=preview_path,
        spec=spec_json,
        author_payload=author_payload,
        slot_id=slot_id,
        generation_id=generation_id,
        generation_root=generation_root,
        gateway=review_gateway,
    )
    return json.dumps(review_result, ensure_ascii=False)
