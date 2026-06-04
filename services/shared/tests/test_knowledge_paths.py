from __future__ import annotations

from pathlib import Path

import pytest

from knowledge.paths import resolve_storage_path


def test_resolve_storage_path_rejects_traversal(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    root.mkdir()
    with pytest.raises(ValueError, match="escapes storage root"):
        resolve_storage_path(root, "../outside.txt")


def test_resolve_storage_path_accepts_relative_uri(tmp_path: Path) -> None:
    root = tmp_path / "storage"
    target = root / "knowledge" / "ecommerce" / "entry-1" / "structure-skill.md"
    target.parent.mkdir(parents=True)
    target.write_text("ok", encoding="utf-8")
    resolved = resolve_storage_path(root, "knowledge/ecommerce/entry-1/structure-skill.md")
    assert resolved.is_file()
