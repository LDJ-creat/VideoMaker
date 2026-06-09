#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
if str(_REPO_ROOT / "services" / "shared") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "services" / "shared"))

from video.poster import extract_video_poster  # noqa: E402


def _iter_sample_videos(
    storage_root: Path,
    project_id: str | None,
    *,
    force: bool,
) -> list[tuple[Path, Path]]:
    projects_root = storage_root / "projects"
    if not projects_root.is_dir():
        return []

    targets: list[tuple[Path, Path]] = []
    project_dirs = (
        [projects_root / project_id]
        if project_id
        else sorted(projects_root.iterdir(), key=lambda path: path.name)
    )
    for project_dir in project_dirs:
        if not project_dir.is_dir():
            continue
        samples_root = project_dir / "samples"
        if not samples_root.is_dir():
            continue
        for sample_dir in sorted(samples_root.iterdir(), key=lambda path: path.name):
            if not sample_dir.is_dir():
                continue
            video_candidates = sorted(sample_dir.glob("source*"))
            video_path = next((path for path in video_candidates if path.is_file()), None)
            if video_path is None:
                continue
            poster_path = sample_dir / "poster.jpg"
            if (
                not force
                and poster_path.is_file()
                and poster_path.stat().st_size > 0
            ):
                continue
            targets.append((video_path, poster_path))
    return targets


def _iter_render_outputs(
    storage_root: Path,
    project_id: str | None,
    *,
    force: bool,
) -> list[tuple[Path, Path]]:
    projects_root = storage_root / "projects"
    if not projects_root.is_dir():
        return []

    targets: list[tuple[Path, Path]] = []
    project_dirs = (
        [projects_root / project_id]
        if project_id
        else sorted(projects_root.iterdir(), key=lambda path: path.name)
    )
    for project_dir in project_dirs:
        if not project_dir.is_dir():
            continue
        renders_root = project_dir / "renders"
        if not renders_root.is_dir():
            continue
        for render_dir in sorted(renders_root.iterdir(), key=lambda path: path.name):
            if not render_dir.is_dir():
                continue
            output_path = render_dir / "output.mp4"
            poster_path = render_dir / "poster.jpg"
            if not output_path.is_file() or output_path.stat().st_size <= 0:
                continue
            if (
                not force
                and poster_path.is_file()
                and poster_path.stat().st_size > 0
            ):
                continue
            targets.append((output_path, poster_path))
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill poster.jpg for samples and renders")
    parser.add_argument(
        "--storage-root",
        type=Path,
        default=_REPO_ROOT / "services" / "api" / "storage",
        help="VideoMaker storage root (default: services/api/storage)",
    )
    parser.add_argument("--project-id", default=None, help="Limit to one project id")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate posters even when poster.jpg already exists",
    )
    args = parser.parse_args()

    storage_root = args.storage_root.resolve()
    sample_targets = _iter_sample_videos(storage_root, args.project_id, force=args.force)
    render_targets = _iter_render_outputs(storage_root, args.project_id, force=args.force)

    print(f"storage={storage_root}")
    print(f"samples_to_backfill={len(sample_targets)} renders_to_backfill={len(render_targets)}")

    failures = 0
    for video_path, poster_path in sample_targets + render_targets:
        label = f"{video_path} -> {poster_path}"
        if args.dry_run:
            print(f"[dry-run] {label}")
            continue
        result = extract_video_poster(video_path, poster_path, force=True)
        if result.get("ok"):
            print(f"[ok] {label}")
        else:
            failures += 1
            print(f"[fail] {label} error={result.get('error')}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
