from __future__ import annotations

import hashlib
import re
from pathlib import Path


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
    return storage_root / "knowledge" / category_slug / entry_id


def rel_uri(storage_root: Path, absolute: Path) -> str:
    return absolute.resolve().relative_to(storage_root.resolve()).as_posix()


def resolve_storage_path(storage_root: Path, relative_uri: str) -> Path:
    """Resolve a storage-relative URI and reject path traversal."""
    root = storage_root.resolve()
    candidate = (root / relative_uri).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Storage path escapes storage root")
    return candidate
