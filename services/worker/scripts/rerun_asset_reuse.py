#!/usr/bin/env python3
"""Re-run asset_reuse completion actions for one generation and refresh render materials.

Does not re-run the full agent pipeline (mapping, image gen, etc.).

Example (high_conversion generation on local API storage):

    cd services/worker
    ..\\.venv\\Scripts\\python.exe scripts/rerun_asset_reuse.py ^
      --project-id 065c5165-f0d8-4e1e-acbb-59c92778391a ^
      --generation-id 11098d90-6d3d-43ae-94ef-5d196349ca25

Requires: ffmpeg on PATH; repo-root ``npm install`` for HyperFrames render (unless --skip-render).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

# Allow ``python scripts/rerun_asset_reuse.py`` from services/worker.
_WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKER_ROOT))

from app.providers.asset_reuse_provider import AssetReuseProvider
from app.providers.completion_registry import (
    apply_material_results_to_plan,
    execute_completion_plan,
    expected_output_path,
    filter_material_completion_actions,
    load_material_state,
    save_material_state,
)
from app.providers.material_types import MaterialContext
from app.render.backend import RenderOptions
from app.render.hyperframes_backend import HyperFramesRenderBackend
from app.runtime.video_gen_quota import VideoGenQuota
from app.tools.ffmpeg_tool import FFmpegTool


def _default_storage_root() -> Path:
    env = os.getenv("VIDEOMAKER_STORAGE_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    return (_WORKER_ROOT.parent / "api" / "storage").resolve()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _structure_from_plan(plan: dict[str, Any]) -> dict[str, Any]:
    slots: list[dict[str, Any]] = []
    seen: set[str] = set()
    for scene in plan.get("storyboard", []):
        if not isinstance(scene, dict):
            continue
        slot_id = str(scene.get("slotId", "")).strip()
        if slot_id and slot_id not in seen:
            seen.add(slot_id)
            slots.append({"id": slot_id, "importance": "must_have"})
    return {"slots": slots}


def _register_artifact(artifact_type: str, path: str | Path) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "type": artifact_type,
        "uri": str(Path(path).resolve()),
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def _asset_reuse_actions(plan: dict[str, Any]) -> list[dict[str, Any]]:
    actions = filter_material_completion_actions(plan.get("completionActions", []))
    return [
        action
        for action in actions
        if str(action.get("provider") or action.get("strategy")) == "asset_reuse"
    ]


def _purge_reuse_outputs(actions: list[dict[str, Any]], *, generated_root: Path, render_root: Path) -> None:
    for action in actions:
        output = expected_output_path(action, generated_root)
        if output.is_file():
            output.unlink()
        name = output.name
        material = render_root / "materials" / name
        if material.is_file():
            material.unlink()


def _copy_materials_force(results: list[dict[str, Any]], *, generated_root: Path, render_root: Path) -> None:
    """Always overwrite render materials/ from generated/ (registry skips existing non-empty files)."""
    dest_dir = render_root / "materials"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for result in results:
        if not result.get("ok"):
            continue
        artifact = result.get("artifactRef") or {}
        uri = artifact.get("uri")
        if not uri:
            continue
        src = Path(str(uri))
        if not src.is_file():
            src = generated_root / src.name
        if src.is_file():
            shutil.copy2(src, dest_dir / src.name)


def _probe_duration(path: Path) -> float | None:
    probe = FFmpegTool().probe(path)
    if probe.get("code"):
        return None
    try:
        return float(probe.get("durationSec", 0))
    except (TypeError, ValueError):
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--generation-id", required=True)
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=None,
        help="API storage root (default: VIDEOMAKER_STORAGE_ROOT or services/api/storage)",
    )
    parser.add_argument(
        "--skip-render",
        action="store_true",
        help="Only regenerate slot*-reuse.mp4 and materials/; do not run HyperFrames render",
    )
    args = parser.parse_args()

    storage_root = (args.storage_root or _default_storage_root()).resolve()
    project_id = args.project_id
    generation_id = args.generation_id

    generation_root = storage_root / "projects" / project_id / "generations" / generation_id
    render_root = storage_root / "projects" / project_id / "renders" / generation_id
    generated_root = generation_root / "generated"
    generated_root.mkdir(parents=True, exist_ok=True)
    render_root.mkdir(parents=True, exist_ok=True)

    plan_path = generation_root / "generation-plan.json"
    plan = _load_json(plan_path)
    inventory = _load_json(generation_root / "asset-inventory.json")

    slot_matches_path = generation_root / "slot-matches.json"
    if slot_matches_path.is_file():
        slot_matches = list(_load_json(slot_matches_path).get("slotMatches", []))
    else:
        gap_report = _load_json(generation_root / "gap-report.json")
        slot_matches = list(gap_report.get("slotMatches", []))

    reuse_actions = _asset_reuse_actions(plan)
    if not reuse_actions:
        print("No asset_reuse actions in generation-plan.json; nothing to do.")
        return 0

    material_state_path = generation_root / "material-state.json"
    quota, completed_ids = load_material_state(material_state_path)
    reuse_action_ids = {str(action["id"]) for action in reuse_actions}
    completed_ids -= reuse_action_ids

    print(f"Storage root:     {storage_root}")
    print(f"Generation root:  {generation_root}")
    print(f"Render root:      {render_root}")
    print(f"Re-running {len(reuse_actions)} asset_reuse action(s): {sorted(reuse_action_ids)}")

    _purge_reuse_outputs(reuse_actions, generated_root=generated_root, render_root=render_root)

    ctx = MaterialContext(
        project_id=project_id,
        generation_id=generation_id,
        render_root=render_root,
        generated_root=generated_root,
        gateway=None,  # type: ignore[arg-type]
        quota=quota or VideoGenQuota(),
        inventory=inventory,
        slot_matches=slot_matches,
        storyboard=list(plan.get("storyboard", [])),
        structure=_structure_from_plan(plan),
        emit_progress=lambda stage, message: print(f"  [{stage}] {message}"),
        register_artifact=_register_artifact,
        completed_action_ids=completed_ids,
        providers={"asset_reuse": AssetReuseProvider()},
    )

    results = execute_completion_plan(reuse_actions, ctx, fail_fast=True)
    failed = next((item for item in results if not item.get("ok")), None)
    if failed is not None:
        error = failed.get("error") or {}
        print(
            "asset_reuse failed:",
            error.get("code", "unknown"),
            error.get("message", failed),
            file=sys.stderr,
        )
        return 1

    plan = apply_material_results_to_plan(plan, results=results, render_root=render_root)
    _copy_materials_force(results, generated_root=generated_root, render_root=render_root)

    for result in results:
        slot_id = result.get("slotId")
        output = expected_output_path(
            next(a for a in reuse_actions if a.get("slotId") == slot_id),
            generated_root,
        )
        duration = _probe_duration(output) if output.is_file() else None
        print(f"  OK {slot_id}: {output.name} duration={duration}s")

    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    save_material_state(
        material_state_path,
        quota=ctx.quota,
        completed_action_ids=ctx.completed_action_ids,
    )
    print(f"Updated {plan_path}")

    if args.skip_render:
        print("Skipped HyperFrames render (--skip-render).")
        return 0

    print("Rendering HyperFrames composition -> output.mp4 ...")

    def render_progress(stage: str) -> None:
        print(f"  [render] {stage}")

    backend = HyperFramesRenderBackend()
    render_output = backend.render(
        RenderOptions(
            project_id=project_id,
            generation_id=generation_id,
            timeline=plan["timeline"],
            storage_root=storage_root,
            emit_progress=render_progress,
        )
    )

    if render_output.error:
        print(
            "Render finished with error:",
            render_output.error.get("code"),
            render_output.error.get("message"),
            file=sys.stderr,
        )
        log_path = render_root / "render-log.json"
        if log_path.is_file():
            print(f"See {log_path}")
        return 2 if not render_output.artifact_refs else 0

    output_mp4 = render_root / "output.mp4"
    if output_mp4.is_file():
        print(f"Wrote {output_mp4} ({output_mp4.stat().st_size} bytes)")
    else:
        print(f"Preview artifacts updated under {render_root} (no output.mp4)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
