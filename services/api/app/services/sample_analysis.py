from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_sample_analysis_artifact(
    storage_root: Path,
    *,
    project_id: str,
    sample_id: str,
) -> dict[str, Any] | None:
    path = (
        storage_root
        / "projects"
        / project_id
        / "samples"
        / sample_id
        / "analysis"
        / "sample-analysis.json"
    )
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None
