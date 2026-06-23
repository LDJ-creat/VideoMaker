from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from composition.types import AuthorRequest

_MEDIA_SUFFIXES = {".mp4", ".webm", ".mov", ".mkv", ".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}


def list_scratch_media(scratch_dir: Path) -> list[str]:
    names: list[str] = []
    if not scratch_dir.is_dir():
        return names
    for path in sorted(scratch_dir.iterdir()):
        if path.is_file() and path.suffix.lower() in _MEDIA_SUFFIXES and path.stat().st_size > 0:
            names.append(path.name)
    return names


def _resolve_source_path(uri: str, *, generated_root: Path | None) -> Path | None:
    cleaned = uri.strip().replace("\\", "/")
    if not cleaned:
        return None
    candidate = Path(cleaned)
    if candidate.is_file():
        return candidate.resolve()
    if generated_root is not None:
        from_generated = (generated_root / cleaned).resolve()
        if from_generated.is_file():
            return from_generated
        by_name = (generated_root / Path(cleaned).name).resolve()
        if by_name.is_file():
            return by_name
    return None


def _stage_file(source: Path, scratch_dir: Path) -> str:
    scratch_dir.mkdir(parents=True, exist_ok=True)
    dest = scratch_dir / source.name
    if source.resolve() != dest.resolve():
        shutil.copy2(source, dest)
    return dest.name


def normalize_asset_ref_uri(uri: str, *, generated_root: Path | None, scratch_dir: Path) -> dict[str, str] | None:
    source = _resolve_source_path(uri, generated_root=generated_root)
    if source is None:
        basename = Path(uri.replace("\\", "/")).name
        if (scratch_dir / basename).is_file():
            return {"uri": basename}
        return None
    basename = _stage_file(source, scratch_dir)
    return {"uri": basename}


def stage_asset_refs_into_scratch(
    asset_refs: list[dict[str, Any]] | None,
    *,
    scratch_dir: Path,
    generated_root: Path | None,
) -> list[dict[str, Any]] | None:
    if not asset_refs:
        return None
    staged: list[dict[str, Any]] = []
    for ref in asset_refs:
        if not isinstance(ref, dict):
            continue
        uri = str(ref.get("uri", "")).strip()
        if not uri:
            continue
        normalized = normalize_asset_ref_uri(uri, generated_root=generated_root, scratch_dir=scratch_dir)
        if normalized is None:
            staged.append(dict(ref))
            continue
        merged = dict(ref)
        merged["uri"] = normalized["uri"]
        staged.append(merged)
    return staged or None


def prepare_author_request_for_scratch(
    request: AuthorRequest,
    *,
    scratch_dir: Path,
    generated_root: Path | None,
) -> AuthorRequest:
    staged_refs = stage_asset_refs_into_scratch(
        request.asset_refs,
        scratch_dir=scratch_dir,
        generated_root=generated_root,
    )
    if staged_refs == request.asset_refs:
        return request
    return AuthorRequest(
        project_id=request.project_id,
        slot=request.slot,
        brand_colors=request.brand_colors,
        variant_overrides=request.variant_overrides,
        asset_refs=staged_refs,
        aspect_ratio=request.aspect_ratio,
        slot_timing=request.slot_timing,
        visual_style_bible=request.visual_style_bible,
        finish_brief=request.finish_brief,
        validation_errors=request.validation_errors,
        generation_id=request.generation_id,
        task_id=request.task_id,
        pattern_l0=request.pattern_l0,
        react_trace=request.react_trace,
    )
