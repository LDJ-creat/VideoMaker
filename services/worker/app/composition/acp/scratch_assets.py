from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from app.composition.acp.base_video_normalize import (
    BaseVideoDiagnostics,
    prepare_base_video_for_scratch,
)
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


def _completion_mode_from_request(request: AuthorRequest) -> str:
    finish = request.finish_brief if isinstance(request.finish_brief, dict) else {}
    mode = str(finish.get("completionMode") or "").strip().lower()
    if mode:
        return mode
    cab = finish.get("compositionAuthorBrief")
    if isinstance(cab, dict):
        brief_mode = str(cab.get("mode") or "").strip().lower()
        if brief_mode:
            return brief_mode
    return ""


def _should_normalize_staged_videos(request: AuthorRequest) -> bool:
    return _completion_mode_from_request(request) == "source_then_polish"


def normalize_asset_ref_uri(
    uri: str,
    *,
    generated_root: Path | None,
    scratch_dir: Path,
    normalize_video: bool = False,
) -> tuple[dict[str, str] | None, BaseVideoDiagnostics | None]:
    source = _resolve_source_path(uri, generated_root=generated_root)
    if source is None:
        basename = Path(uri.replace("\\", "/")).name
        if (scratch_dir / basename).is_file():
            return {"uri": basename}, None
        return None, None
    if normalize_video and source.suffix.lower() in {".mp4", ".webm", ".mov", ".mkv"}:
        staged_path, diagnostics = prepare_base_video_for_scratch(source, scratch_dir)
        return {"uri": staged_path.name}, diagnostics
    basename = _stage_file(source, scratch_dir)
    return {"uri": basename}, None


def stage_asset_refs_into_scratch(
    asset_refs: list[dict[str, Any]] | None,
    *,
    scratch_dir: Path,
    generated_root: Path | None,
    normalize_video: bool = False,
) -> tuple[list[dict[str, Any]] | None, BaseVideoDiagnostics | None]:
    if not asset_refs:
        return None, None
    staged: list[dict[str, Any]] = []
    diagnostics: BaseVideoDiagnostics | None = None
    for ref in asset_refs:
        if not isinstance(ref, dict):
            continue
        uri = str(ref.get("uri", "")).strip()
        if not uri:
            continue
        normalized, diag = normalize_asset_ref_uri(
            uri,
            generated_root=generated_root,
            scratch_dir=scratch_dir,
            normalize_video=normalize_video,
        )
        if normalized is None:
            staged.append(dict(ref))
            continue
        if diag is not None:
            diagnostics = diag
        merged = dict(ref)
        merged["uri"] = normalized["uri"]
        staged.append(merged)
    return (staged or None), diagnostics


def prepare_author_request_for_scratch(
    request: AuthorRequest,
    *,
    scratch_dir: Path,
    generated_root: Path | None,
) -> tuple[AuthorRequest, dict[str, Any] | None]:
    normalize_video = _should_normalize_staged_videos(request)
    staged_refs, diagnostics = stage_asset_refs_into_scratch(
        request.asset_refs,
        scratch_dir=scratch_dir,
        generated_root=generated_root,
        normalize_video=normalize_video,
    )
    diagnostics_payload = diagnostics.to_dict() if diagnostics is not None else None
    if staged_refs == request.asset_refs:
        return request, diagnostics_payload
    return (
        AuthorRequest(
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
        ),
        diagnostics_payload,
    )
