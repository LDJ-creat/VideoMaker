#!/usr/bin/env python3
"""Re-run TTS + subtitle timeline patch + final render for an existing generation.

Reuses storyboard.script and existing slot*.mp4 under materials/; does not call LLM or video APIs.

Example:

    cd services/worker
    python scripts/rerun_tts_subtitle_render.py ^
      --project-id 065c5165-f0d8-4e1e-acbb-59c92778391a ^
      --generation-id 7ebb8a6f-da2b-47c2-82fa-e9ebb99e9684
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

_WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKER_ROOT))

_REPO_ROOT = _WORKER_ROOT.parent.parent
_SHARED_ROOT = _REPO_ROOT / "services" / "shared"
if _SHARED_ROOT.is_dir() and str(_SHARED_ROOT) not in sys.path:
    sys.path.insert(0, str(_SHARED_ROOT))

from app.gateway.config import GatewayConfig
from app.gateway.model_gateway import ModelGateway
from app.pipelines.generation_pipeline import build_narration_actions
from app.pipelines.narration_alignment import align_subtitles_to_voiceover
from app.pipelines.narration_timeline import sync_timeline_to_narration
from app.pipelines.tts_mode import resolve_tts_mode
from app.providers.completion_registry import (
    apply_material_results_to_plan,
    execute_completion_plan,
    expected_output_path,
    filter_material_completion_actions,
    load_material_state,
    register_default_providers,
    save_material_state,
)
from app.providers.material_types import MaterialContext
from app.providers.tts_provider import TTSProvider
from app.render.backend import RenderOptions
from app.render.resolve_render_backend import build_render_backend
from app.runtime.video_gen_quota import VideoGenQuota
from app.tools.tts_tool import TTSTool
from model_gateway.store import ModelGatewayStore


def _default_storage_root() -> Path:
    env = os.getenv("VIDEOMAKER_STORAGE_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    return (_WORKER_ROOT.parent / "api" / "storage").resolve()


def _default_database_path(storage_root: Path) -> Path:
    return storage_root / "videomaker.sqlite3"


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Missing artifact: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _register_artifact(artifact_type: str, path: str | Path) -> dict[str, Any]:
    return {
        "id": str(uuid4()),
        "type": artifact_type,
        "uri": str(Path(path).resolve()),
        "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


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


def _ensure_video_materials(*, generated_root: Path, render_root: Path) -> None:
    """Copy existing generated slot mp4 into render materials/ if missing."""
    dest = render_root / "materials"
    dest.mkdir(parents=True, exist_ok=True)
    for src in generated_root.glob("slot*.mp4"):
        target = dest / src.name
        if not target.is_file() or target.stat().st_size == 0:
            shutil.copy2(src, target)
            print(f"  Copied {src.name} -> materials/")


def _patch_timeline_video_refs(plan: dict[str, Any]) -> dict[str, Any]:
    storyboard = list(plan.get("storyboard", []))
    timeline = plan.get("timeline")
    if not isinstance(timeline, dict):
        timeline = {"durationSec": 0.0, "tracks": []}

    tracks = timeline.get("tracks", [])
    if isinstance(tracks, list):
        for track in tracks:
            if not isinstance(track, dict) or track.get("type") != "video":
                continue
            for clip in track.get("clips", []):
                if not isinstance(clip, dict):
                    continue
                ref = str(clip.get("sourceRef", ""))
                if ref and not ref.startswith("materials/"):
                    name = Path(ref).name
                    if name.endswith(".mp4"):
                        clip["sourceRef"] = f"materials/{name}"

    scene_ends = [
        float(scene.get("endSec", 0))
        for scene in storyboard
        if isinstance(scene, dict)
    ]
    timeline["durationSec"] = max(scene_ends, default=float(timeline.get("durationSec", 0) or 0))
    if scene_ends and timeline["durationSec"] > 3600:
        timeline["durationSec"] = max(scene_ends[:-1], default=scene_ends[-1])
    plan["timeline"] = timeline
    return plan


def _finalize_narration_timeline(
    plan: dict[str, Any],
    *,
    render_root: Path,
) -> dict[str, Any]:
    tts_mode = str(plan.get("ttsMode") or resolve_tts_mode(plan))
    plan = sync_timeline_to_narration(plan, render_root=render_root)
    packaging = dict(plan.get("packagingPlan") or {})
    plan["timeline"] = align_subtitles_to_voiceover(
        plan.get("timeline", {}),
        list(plan.get("storyboard", [])),
        packaging,
        render_root=render_root,
        master_narration=str(plan.get("masterNarration") or ""),
        tts_mode=tts_mode,
    )
    return plan


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--generation-id", required=True)
    parser.add_argument("--storage-root", type=Path, default=None)
    parser.add_argument("--database-path", type=Path, default=None)
    parser.add_argument(
        "--skip-tts",
        action="store_true",
        help="Only patch timeline and render (requires existing slot*.wav)",
    )
    parser.add_argument(
        "--render-backend",
        choices=("ffmpeg", "hyperframes"),
        default=None,
        help="Override VIDEOMAKER_RENDER_BACKEND for this run",
    )
    args = parser.parse_args()

    if args.render_backend:
        os.environ["VIDEOMAKER_RENDER_BACKEND"] = args.render_backend

    storage_root = (args.storage_root or _default_storage_root()).resolve()
    database_path = (args.database_path or _default_database_path(storage_root)).resolve()
    project_id = args.project_id
    generation_id = args.generation_id

    generation_root = storage_root / "projects" / project_id / "generations" / generation_id
    render_root = storage_root / "projects" / project_id / "renders" / generation_id
    generated_root = generation_root / "generated"
    generated_root.mkdir(parents=True, exist_ok=True)
    render_root.mkdir(parents=True, exist_ok=True)

    plan_path = generation_root / "generation-plan.json"
    plan = _load_json(plan_path)
    inventory_path = generation_root / "asset-inventory.json"
    inventory = _load_json(inventory_path) if inventory_path.is_file() else {"assets": []}

    slot_matches_path = generation_root / "slot-matches.json"
    if slot_matches_path.is_file():
        slot_matches = list(_load_json(slot_matches_path).get("slotMatches", []))
    else:
        gap_report = _load_json(generation_root / "gap-report.json")
        slot_matches = list(gap_report.get("slotMatches", []))

    print(f"Storage root:    {storage_root}")
    print(f"Generation root: {generation_root}")
    print(f"Render root:     {render_root}")

    _ensure_video_materials(generated_root=generated_root, render_root=render_root)

    visual_actions = [
        action
        for action in filter_material_completion_actions(plan.get("completionActions", []))
        if str(action.get("provider") or action.get("strategy")) != "tts"
    ]
    tts_from_gap = {
        str(action["slotId"])
        for action in visual_actions
        if str(action.get("provider") or action.get("strategy")) == "tts"
    }
    narration_actions = build_narration_actions(
        list(plan.get("storyboard", [])),
        skip_slot_ids=tts_from_gap,
        master_narration=str(plan.get("masterNarration") or ""),
        tts_mode=str(plan.get("ttsMode") or resolve_tts_mode(plan)),
    )
    plan["completionActions"] = visual_actions + narration_actions
    plan = _patch_timeline_video_refs(plan)

    material_state_path = generation_root / "material-state.json"
    quota, completed_ids = load_material_state(material_state_path)
    tts_action_ids = {str(action["id"]) for action in narration_actions}
    completed_ids -= tts_action_ids

    for action in narration_actions:
        wav_path = expected_output_path(action, generated_root)
        if wav_path.is_file():
            wav_path.unlink()
        material_wav = render_root / "materials" / wav_path.name
        if material_wav.is_file():
            material_wav.unlink()

    if not args.skip_tts and narration_actions:
        store = ModelGatewayStore(database_path, storage_root)
        gateway = ModelGateway(config=GatewayConfig.from_store(store))
        def emit_progress(stage: str, message: str) -> None:
            print(f"  [{stage}] {message}")

        ctx = MaterialContext(
            project_id=project_id,
            generation_id=generation_id,
            render_root=render_root,
            generated_root=generated_root,
            gateway=gateway,  # type: ignore[arg-type]
            quota=quota or VideoGenQuota(),
            inventory=inventory,
            slot_matches=slot_matches,
            storyboard=list(plan.get("storyboard", [])),
            structure=_structure_from_plan(plan),
            emit_progress=emit_progress,
            register_artifact=_register_artifact,
            completed_action_ids=completed_ids,
            master_narration=str(plan.get("masterNarration") or ""),
            providers={
                "tts": TTSProvider(
                    TTSTool(gateway=gateway, emit_progress=emit_progress),
                ),
            },
        )
        print(f"Running {len(narration_actions)} TTS action(s) with model gateway...")
        results = execute_completion_plan(narration_actions, ctx, fail_fast=True)
        failed = next((item for item in results if not item.get("ok")), None)
        if failed is not None:
            error = failed.get("error") or {}
            print(
                "TTS failed:",
                error.get("code", "unknown"),
                error.get("message", failed),
                file=sys.stderr,
            )
            return 1
        plan = apply_material_results_to_plan(plan, results=results, render_root=render_root)
        save_material_state(
            material_state_path,
            quota=ctx.quota,
            completed_action_ids=ctx.completed_action_ids,
        )
        for result in results:
            if result.get("ok"):
                print(f"  OK TTS {result.get('slotId')}: {result.get('artifactRef', {}).get('uri')}")
    else:
        print("Skipped TTS (--skip-tts or no narration actions).")
        plan = _finalize_narration_timeline(plan, render_root=render_root)

    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {plan_path}")

    vo_track = next(
        (t for t in plan["timeline"]["tracks"] if t.get("type") == "voiceover"),
        {"clips": []},
    )
    text_track = next(
        (t for t in plan["timeline"]["tracks"] if t.get("type") == "text"),
        {"clips": []},
    )
    print(f"Voiceover clips: {len(vo_track.get('clips', []))}")
    print(f"Subtitle clips: {sum(1 for c in text_track.get('clips', []) if str(c.get('id','')).startswith('subtitle-'))}")

    preview_path = render_root / "preview.html"
    output_mp4 = render_root / "output.mp4"
    if preview_path.is_file():
        preview_path.unlink()
    if output_mp4.is_file():
        output_mp4.unlink()

    print("Rendering timeline -> output.mp4 ...")

    def render_progress(stage: str) -> None:
        print(f"  [render] {stage}")

    backend = build_render_backend(plan["timeline"], plan=plan)
    render_output = backend.render(
        RenderOptions(
            project_id=project_id,
            generation_id=generation_id,
            timeline=plan["timeline"],
            storage_root=storage_root,
            emit_progress=render_progress,
            tts_mode=str(plan.get("ttsMode") or "") or None,
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

    if output_mp4.is_file():
        print(f"Wrote {output_mp4} ({output_mp4.stat().st_size} bytes)")
    else:
        print(f"Preview updated under {render_root} (no output.mp4)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
