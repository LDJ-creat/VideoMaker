from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any


def render_material_preview_spec(
    spec: dict[str, Any],
    *,
    scratch_dir: Path,
    repo_root: Path,
    aspect_ratio: str = "9:16",
    asset_root: Path | None = None,
    engine: Any | None = None,
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

    database_path = os.environ.get("VM_DATABASE_PATH", "").strip()
    storage_root = os.environ.get("VM_STORAGE_ROOT", "").strip()
    store = None
    runner = None
    sink = None
    if not storage_root:
        if generation_root is not None and len(generation_root.parents) >= 3:
            storage_root = str(generation_root.parents[2])
        elif generation_root is not None:
            storage_root = str(generation_root.parents[1])
        else:
            storage_root = "."
    storage_root_path = Path(storage_root)
    project_id = str(author_payload.get("projectId") or "")
    task_id = str(author_payload.get("taskId") or "mcp-review")
    if database_path and storage_root and gateway is None:
        from model_gateway.store import ModelGatewayStore

        from app.gateway.model_gateway import ModelGateway

        store = ModelGatewayStore(Path(database_path), storage_root_path)
        gateway = ModelGateway.from_store(store)

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

    context = TaskContext(
        task_id=task_id,
        project_id=project_id,
        storage_root=storage_root_path,
    )

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
        if sink is not None and project_id:
            record_material_review_tool_run(
                sink=sink,
                project_id=project_id,
                task_id=task_id,
                generation_id=generation_id,
                slot_id=slot_id,
                preview_path=preview_path,
                ok=False,
                error={"code": "review_failed", "message": str(exc)},
                parent_observability_run_id=acp_parent_observability_run_id(),
                latency_ms=(time.perf_counter() - started) * 1000,
            )
        return {"ok": False, "error": {"code": "review_failed", "message": str(exc)}}


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
