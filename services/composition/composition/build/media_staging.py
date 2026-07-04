from __future__ import annotations

import re
import shutil
from pathlib import Path

_MEDIA_SRC_PATTERN = re.compile(r"""src=(["'])([^"']+)\1""", re.IGNORECASE)
_VIDEO_TAG_PATTERN = re.compile(r"<video\b[^>]*>.*?</video>", re.IGNORECASE | re.DOTALL)
_VIDEO_OPEN_TAG_PATTERN = re.compile(r"<video\b([^>]*)(/?)>", re.IGNORECASE)
_HAS_AUDIBLE_VIDEO_PATTERN = re.compile(
    r"""\bdata-has-audio\s*=\s*(["'])true\1""",
    re.IGNORECASE,
)


class MediaStagingError(Exception):
    """Raised when a local base video reference cannot be resolved during build."""


def normalize_video_tags_for_lint(html: str) -> str:
    """Ensure <video> tags satisfy HyperFrames audio lint (muted unless audible)."""

    def _patch_open_tag(match: re.Match[str]) -> str:
        attrs = match.group(1)
        trailing_slash = match.group(2)
        if _HAS_AUDIBLE_VIDEO_PATTERN.search(attrs):
            return match.group(0)
        patched = attrs
        if not re.search(r"\bmuted\b", patched, re.IGNORECASE):
            patched = f"{patched.rstrip()} muted"
        if not re.search(r"\bplaysinline\b", patched, re.IGNORECASE):
            patched = f"{patched.rstrip()} playsinline"
        return f"<video{patched}{trailing_slash}>"

    return _VIDEO_OPEN_TAG_PATTERN.sub(_patch_open_tag, html)


def _is_remote_or_data_src(ref: str) -> bool:
    normalized = ref.replace("\\", "/").strip()
    return not normalized or normalized.startswith(("http://", "https://", "data:"))


def _media_fallback_basenames(basename: str) -> list[str]:
    """Return basename plus canonical fallbacks (e.g. *-normalized.mp4 → *.mp4)."""
    ordered: list[str] = []
    seen: set[str] = set()
    for name in (basename,):
        if name not in seen:
            seen.add(name)
            ordered.append(name)
    if basename.endswith("-normalized.mp4"):
        canonical = f"{basename[: -len('-normalized.mp4')]}.mp4"
        if canonical not in seen:
            seen.add(canonical)
            ordered.append(canonical)
    return ordered


def _stage_file_to_composition(
    source: Path,
    *,
    composition_dir: Path,
    requested_name: str,
) -> Path:
    dest = (composition_dir / requested_name).resolve()
    composition_dir.mkdir(parents=True, exist_ok=True)
    if source.resolve() != dest:
        shutil.copy2(source, dest)
    return dest


def _resolve_media_source(
    ref: str,
    *,
    composition_dir: Path,
    asset_root: Path | None,
) -> Path | None:
    normalized = ref.replace("{{asset_root}}", "").replace("\\", "/").strip()
    if _is_remote_or_data_src(normalized):
        return None

    if normalized.startswith("assets/"):
        candidate = (composition_dir / normalized).resolve()
        if candidate.is_file() and candidate.stat().st_size > 0:
            return candidate
        if asset_root is None:
            return None
        root = asset_root.resolve()
        source = (root / normalized).resolve()
        if source.is_file() and source.stat().st_size > 0 and source.is_relative_to(root):
            dest = composition_dir / Path(normalized).name
            if source.resolve() != dest.resolve():
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, dest)
            return dest
        return None

    requested_name = Path(normalized).name
    for basename in _media_fallback_basenames(requested_name):
        candidate = (composition_dir / basename).resolve()
        if candidate.is_file() and candidate.stat().st_size > 0:
            return _stage_file_to_composition(
                candidate,
                composition_dir=composition_dir,
                requested_name=requested_name,
            )

        if asset_root is None:
            continue

        root = asset_root.resolve()
        source = (root / basename).resolve()
        if not source.is_file() or source.stat().st_size <= 0:
            continue
        if not source.is_relative_to(root):
            continue
        return _stage_file_to_composition(
            source,
            composition_dir=composition_dir,
            requested_name=requested_name,
        )

    return None


def _finalize_video_tags(
    html: str,
    *,
    composition_dir: Path,
    asset_root: Path | None,
) -> str:
    def _replace_video(match: re.Match[str]) -> str:
        tag = match.group(0)
        src_match = _MEDIA_SRC_PATTERN.search(tag)
        if src_match is None:
            return tag
        src = src_match.group(2)
        if _is_remote_or_data_src(src.replace("{{asset_root}}", "")):
            return tag
        resolved = _resolve_media_source(
            src,
            composition_dir=composition_dir,
            asset_root=asset_root,
        )
        if resolved is not None:
            return tag
        if asset_root is not None:
            raise MediaStagingError(
                f"Unresolved local video src={src!r}; no matching media under {asset_root.resolve()}"
            )
        return ""

    return _VIDEO_TAG_PATTERN.sub(_replace_video, html)


def ensure_base_video_aliases_in_asset_root(html: str, asset_root: Path) -> None:
    """Copy canonical stock/base files to -normalized aliases expected by authored specs."""
    root = asset_root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    for match in _MEDIA_SRC_PATTERN.finditer(html):
        ref = match.group(2)
        if _is_remote_or_data_src(ref.replace("{{asset_root}}", "")):
            continue
        requested_name = Path(ref.replace("{{asset_root}}", "").replace("\\", "/").strip()).name
        if not requested_name:
            continue
        dest = root / requested_name
        if dest.is_file() and dest.stat().st_size > 0:
            continue
        for basename in _media_fallback_basenames(requested_name)[1:]:
            source = root / basename
            if source.is_file() and source.stat().st_size > 0:
                shutil.copy2(source, dest)
                break


def normalize_and_stage_composition_media(
    composition_dir: Path,
    *,
    asset_root: Path | None,
    html: str,
) -> str:
    """Copy referenced media into composition_dir; fail if local base video is missing."""
    composition_dir = composition_dir.resolve()
    composition_dir.mkdir(parents=True, exist_ok=True)

    normalized_html = normalize_video_tags_for_lint(html.replace("{{asset_root}}", ""))
    for match in _MEDIA_SRC_PATTERN.finditer(normalized_html):
        ref = match.group(2)
        if _is_remote_or_data_src(ref):
            continue
        _resolve_media_source(
            ref,
            composition_dir=composition_dir,
            asset_root=asset_root,
        )

    return _finalize_video_tags(
        normalized_html,
        composition_dir=composition_dir,
        asset_root=asset_root,
    )
