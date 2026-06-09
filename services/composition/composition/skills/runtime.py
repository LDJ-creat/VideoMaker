from __future__ import annotations

import os
import re
from pathlib import Path

from composition.paths import detect_repo_root, resolve_storage_path


class SkillRuntime:
    def __init__(
        self,
        *,
        repo_root: Path | None = None,
        storage_root: Path | None = None,
        max_chars_per_view: int | None = None,
        max_total_chars: int | None = None,
    ) -> None:
        self.repo_root = (repo_root or detect_repo_root()).resolve()
        self.storage_root = storage_root.resolve() if storage_root else None
        self.max_chars_per_view = max_chars_per_view or int(
            os.getenv("VIDEOMAKER_SKILL_VIEW_MAX_CHARS", "8192")
        )
        self.max_total_chars = max_total_chars or int(
            os.getenv("VIDEOMAKER_SKILL_VIEW_TOKEN_CAP", "6000")
        ) * 4
        self._viewed_chars = 0

    def _resolve_location(self, location: str) -> Path:
        normalized = location.strip().replace("\\", "/")
        if normalized.startswith("knowledge/") or normalized.startswith("projects/"):
            if self.storage_root is None:
                raise ValueError("storage_root required for knowledge paths")
            return resolve_storage_path(self.storage_root, normalized)
        candidate = (self.repo_root / normalized).resolve()
        if not candidate.is_relative_to(self.repo_root):
            raise ValueError("skill location escapes repo root")
        return candidate

    def _extract_section(self, text: str, section: str | None) -> str:
        if not section:
            return text
        marker = section if section.startswith("#") else f"## {section}"
        if marker not in text and section.startswith("##"):
            marker = section
        start = text.find(marker)
        if start < 0:
            return text
        rest = text[start + len(marker) :]
        next_heading = re.search(r"\n##\s+", rest)
        body = rest[: next_heading.start()] if next_heading else rest
        return f"{marker}{body}".strip()

    def skill_view(self, location: str, *, section: str | None = None) -> str:
        path = self._resolve_location(location)
        if not path.is_file():
            raise FileNotFoundError(f"skill file not found: {location}")
        text = path.read_text(encoding="utf-8")
        text = self._extract_section(text, section)
        if len(text) > self.max_chars_per_view:
            text = text[: self.max_chars_per_view - 3] + "..."
        if self._viewed_chars + len(text) > self.max_total_chars:
            raise ValueError("skill_view token cap exceeded")
        self._viewed_chars += len(text)
        return text
