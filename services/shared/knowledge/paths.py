from __future__ import annotations

import hashlib
import re
from pathlib import Path

_STORAGE_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


def validate_storage_segment(value: str, *, field: str) -> str:
    """Reject path traversal and unsafe characters in storage path segments."""
    segment = str(value or "").strip()
    if not segment or len(segment) > 128:
        raise ValueError(f"invalid_{field}")
    if segment in {".", ".."} or ".." in segment:
        raise ValueError(f"invalid_{field}")
    if "/" in segment or "\\" in segment:
        raise ValueError(f"invalid_{field}")
    if not _STORAGE_SEGMENT.fullmatch(segment):
        raise ValueError(f"invalid_{field}")
    return segment


def assert_under_storage_root(path: Path, storage_root: Path) -> Path:
    root = storage_root.resolve()
    resolved = path.resolve()
    if not resolved.is_relative_to(root):
        raise ValueError("path_escape_storage_root")
    return resolved


def category_slug(category: str) -> str:
    slug = category.strip().lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    if slug:
        return slug[:64]
    digest = hashlib.sha256(category.encode("utf-8")).hexdigest()[:8]
    return f"cat-{digest}"


def draft_dir(storage_root: Path, project_id: str, sample_id: str) -> Path:
    return (
        storage_root
        / "projects"
        / project_id
        / "knowledge"
        / "drafts"
        / sample_id
    )


def published_entry_dir(storage_root: Path, category_slug: str, entry_id: str) -> Path:
    slug = validate_storage_segment(category_slug, field="category_slug")
    entry = validate_storage_segment(entry_id, field="entry_id")
    path = storage_root / "knowledge" / slug / entry
    return assert_under_storage_root(path, storage_root)


def rel_uri(storage_root: Path, absolute: Path) -> str:
    return absolute.resolve().relative_to(storage_root.resolve()).as_posix()


def resolve_storage_path(storage_root: Path, relative_uri: str) -> Path:
    """Resolve a storage-relative URI and reject path traversal."""
    root = storage_root.resolve()
    candidate = (root / relative_uri).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Storage path escapes storage root")
    return candidate
