#!/usr/bin/env python3
"""Repair slot visuals + re-render FFmpeg output for an existing generation.

Syncs stock/HyperFrames artifacts into generation-plan timeline, re-stages broken
HF compositions (missing stock copy), re-renders tiny HF clips, then compiles MP4.

Example::

    cd services/worker
    python scripts/rerender_generation_visuals.py \\
      --project-id 54fa9e10-98ef-48a4-8e63-5c93d28d06d2 \\
      --generation-id aacfcdd4-baea-4368-a05e-3c2b55eb1041
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any

_WORKER_ROOT = Path(__file__).resolve().parents[1]
if str(_WORKER_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKER_ROOT))

_REPO_ROOT = _WORKER_ROOT.parent.parent
_COMPOSITION_ROOT = _REPO_ROOT / "services" / "composition"
if _COMPOSITION_ROOT.is_dir() and str(_COMPOSITION_ROOT) not in sys.path:
    sys.path.insert(0, str(_COMPOSITION_ROOT))

from app.providers.completion_registry import (  # noqa: E402
    _composition_needs_tailwind_rebuild,
    _min_video_bytes_for_path,
    apply_material_results_to_plan,
    expected_output_path,
    synthesize_material_results_from_disk,
)
from app.render.backend import RenderOptions  # noqa: E402
from app.render.resolve_render_backend import build_render_backend  # noqa: E402
from composition.build.media_staging import normalize_and_stage_composition_media
from composition.build.tailwind_runtime import ensure_tailwind_runtime_in_index  # noqa: E402
from composition.render.hyperframes_cli import HyperFramesCli  # noqa: E402

_BODY_PATTERN = re.compile(r"<body[^>]*>(.*)</body>", re.IGNORECASE | re.DOTALL)


def _default_storage_root() -> Path:
    env = os.getenv("VIDEOMAKER_STORAGE_ROOT", "").strip()
    if env:
        return Path(env).resolve()
    return (_WORKER_ROOT.parent / "api" / "storage").resolve()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _repair_composition_html(
    *,
    composition_dir: Path,
    generated_root: Path,
) -> bool:
    index_path = composition_dir / "index.html"
    if not index_path.is_file():
        return False
    html = index_path.read_text(encoding="utf-8")
    body_match = _BODY_PATTERN.search(html)
    if body_match is None:
        return False
    body_inner = body_match.group(1)
    root_match = re.search(
        r'(<div[^>]*id="root"[^>]*>)(.*?)(</div>\s*<script>)',
        body_inner,
        re.DOTALL,
    )
    if root_match is None:
        return False
    fragment = root_match.group(2)
    normalized = normalize_and_stage_composition_media(
        composition_dir,
        asset_root=generated_root,
        html=fragment,
    )
    if normalized == fragment:
        return False
    new_body = (
        body_inner[: root_match.start(2)]
        + normalized
        + body_inner[root_match.end(2) :]
    )
    new_html = html[: body_match.start(1)] + new_body + html[body_match.end(1) :]
    index_path.write_text(new_html, encoding="utf-8")
    return True


def _rerender_hyperframes_clip(
    *,
    action: dict[str, Any],
    generated_root: Path,
    cli: HyperFramesCli,
) -> bool:
    action_id = str(action.get("id") or "")
    output = expected_output_path(action, generated_root)
    composition_dir = generated_root / action_id / "composition"
    if not composition_dir.is_dir():
        return False
    _repair_composition_html(composition_dir=composition_dir, generated_root=generated_root)
    index_path = composition_dir / "index.html"
    if index_path.is_file():
        ensure_tailwind_runtime_in_index(index_path)
    log_path = generated_root.parent / f"{action_id}-render-log.json"
    if output.is_file():
        output.unlink()
    result = cli.render(composition_dir, output, log_path)
    ok = bool(result.get("ok", True)) and output.is_file()
    if ok and output.stat().st_size < _min_video_bytes_for_path(output):
        return False
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-id", required=True)
    parser.add_argument("--generation-id", required=True)
    parser.add_argument("--storage-root", type=Path, default=None)
    args = parser.parse_args()

    storage_root = (args.storage_root or _default_storage_root()).resolve()
    project_id = args.project_id
    generation_id = args.generation_id
    generation_root = storage_root / "projects" / project_id / "generations" / generation_id
    generated_root = generation_root / "generated"
    render_root = storage_root / "projects" / project_id / "renders" / generation_id
    plan_path = generation_root / "generation-plan.json"
    if not plan_path.is_file():
        print(f"Missing {plan_path}", file=sys.stderr)
        return 1

    plan = _load_json(plan_path)
    actions = [a for a in plan.get("completionActions", []) if isinstance(a, dict)]

    print("Syncing material artifacts into plan timeline...")
    sync_results = synthesize_material_results_from_disk(actions, generated_root=generated_root)
    plan = apply_material_results_to_plan(
        plan,
        results=sync_results,
        render_root=render_root,
        generated_root=generated_root,
    )

    cli = HyperFramesCli(repo_root=_REPO_ROOT)
    hf_actions = [
        a
        for a in actions
        if str(a.get("provider") or a.get("strategy")) == "hyperframes_material"
    ]
    rerendered = 0
    for action in hf_actions:
        output = expected_output_path(action, generated_root)
        needs_rerender = (
            not output.is_file()
            or output.stat().st_size < _min_video_bytes_for_path(output)
            or _composition_needs_tailwind_rebuild(action, generated_root)
        )
        if not needs_rerender:
            continue
        action_id = str(action.get("id"))
        print(f"  Re-rendering {action_id} ...")
        if _rerender_hyperframes_clip(action=action, generated_root=generated_root, cli=cli):
            rerendered += 1
            print(f"    OK -> {output.name} ({output.stat().st_size} bytes)")
        else:
            print(f"    FAILED {action_id}", file=sys.stderr)

    if rerendered:
        sync_results = synthesize_material_results_from_disk(actions, generated_root=generated_root)
        plan = apply_material_results_to_plan(
            plan,
            results=sync_results,
            render_root=render_root,
            generated_root=generated_root,
        )

    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Updated {plan_path}")

    # Force plan sync to refresh materials/ copies after HF re-render.
    plan = apply_material_results_to_plan(
        plan,
        results=synthesize_material_results_from_disk(actions, generated_root=generated_root),
        render_root=render_root,
        generated_root=generated_root,
    )
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")

    staging_dir = render_root / "ffmpeg-staging"
    if staging_dir.is_dir():
        shutil.rmtree(staging_dir)

    video_clips = 0
    with_ref = 0
    for track in plan.get("timeline", {}).get("tracks", []):
        if not isinstance(track, dict) or track.get("type") != "video":
            continue
        for clip in track.get("clips", []):
            if not isinstance(clip, dict):
                continue
            video_clips += 1
            if clip.get("sourceRef"):
                with_ref += 1
    print(f"Timeline video clips with sourceRef: {with_ref}/{video_clips}")

    output_mp4 = render_root / "output.mp4"
    preview_path = render_root / "preview.html"
    for path in (preview_path,):
        if path.is_file():
            try:
                path.unlink()
            except OSError:
                pass

    print("Compiling timeline -> output.mp4 ...")
    backend = build_render_backend(plan["timeline"], plan=plan)

    def render_progress(stage: str) -> None:
        print(f"  [render] {stage}")

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
            "Render error:",
            render_output.error.get("code"),
            render_output.error.get("message"),
            file=sys.stderr,
        )
        return 2
    if output_mp4.is_file():
        print(f"Wrote {output_mp4} ({output_mp4.stat().st_size} bytes)")
        return 0
    print("Render finished without output.mp4", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
