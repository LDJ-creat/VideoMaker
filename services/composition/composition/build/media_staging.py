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


def _resolve_media_source(
    ref: str,
    *,
    composition_dir: Path,
    asset_root: Path | None,
) -> Path | None:
    normalized = ref.replace("{{asset_root}}", "").replace("\\", "/").strip()
    if not normalized or normalized.startswith(("http://", "https://", "data:")):
        return None
    if normalized.startswith("assets/"):
        candidate = (composition_dir / normalized).resolve()
    else:
        candidate = (composition_dir / Path(normalized).name).resolve()
    if candidate.is_file() and candidate.stat().st_size > 0:
        return candidate

    if asset_root is None:
        return None

    root = asset_root.resolve()
    basename = Path(normalized).name
    source = (root / basename).resolve()
    if not source.is_file() or source.stat().st_size <= 0:
        return None
    if not source.is_relative_to(root):
        return None

    destination = composition_dir / basename
    if source.resolve() != destination.resolve():
        shutil.copy2(source, destination)
    return destination


def _strip_unresolved_video_tags(html: str, *, composition_dir: Path, asset_root: Path | None) -> str:
    def _replace_video(match: re.Match[str]) -> str:
        tag = match.group(0)
        src_match = _MEDIA_SRC_PATTERN.search(tag)
        if src_match is None:
            return tag
        resolved = _resolve_media_source(
            src_match.group(2),
            composition_dir=composition_dir,
            asset_root=asset_root,
        )
        if resolved is not None:
            return tag
        return ""

    return _VIDEO_TAG_PATTERN.sub(_replace_video, html)


def normalize_and_stage_composition_media(
    composition_dir: Path,
    *,
    asset_root: Path | None,
    html: str,
) -> str:
    """Copy referenced media into composition_dir and drop broken <video> tags."""
    composition_dir = composition_dir.resolve()
    composition_dir.mkdir(parents=True, exist_ok=True)

    normalized_html = normalize_video_tags_for_lint(html.replace("{{asset_root}}", ""))
    for match in _MEDIA_SRC_PATTERN.finditer(normalized_html):
        _resolve_media_source(
            match.group(2),
            composition_dir=composition_dir,
            asset_root=asset_root,
        )

    return _strip_unresolved_video_tags(
        normalized_html,
        composition_dir=composition_dir,
        asset_root=asset_root,
    )
