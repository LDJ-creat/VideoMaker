from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class ArtifactStore:
    def __init__(self, storage_root: Path, project_id: str) -> None:
        self._storage_root = Path(storage_root).resolve()
        self._project_id = project_id
        self._project_root = self._storage_root / "projects" / project_id

    @property
    def project_root(self) -> Path:
        return self._project_root

    def resolve(self, relative_path: str | Path) -> Path:
        candidate = (self._project_root / relative_path).resolve()
        if not candidate.is_relative_to(self._project_root):
            raise ValueError("artifact path escapes project scope")
        return candidate

    def write_json(self, relative_path: str | Path, payload: Any) -> Path:
        output_path = self.resolve(relative_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_path

    def write_text(self, relative_path: str | Path, text: str) -> Path:
        output_path = self.resolve(relative_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
        return output_path
