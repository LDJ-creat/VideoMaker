#!/usr/bin/env python3
"""Upgrade worker structure fixtures to p1-v3 via coerce (no LLM)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services" / "worker"))

from app.validation.structure_coercer import coerce_video_structure  # noqa: E402

FIXTURES = [
    ROOT / "services/worker/tests/fixtures/structures/sample-structure.json",
    ROOT / "services/worker/tests/fixtures/agents/structure_analyst.json",
    ROOT / "services/worker/tests/fixtures/agents/video_structure_analyst.json",
    ROOT / "services/worker/tests/fixtures/agents/structure_compiler.json",
]
ANALYSIS = ROOT / "services/worker/tests/fixtures/sample_analysis.json"


def main() -> None:
    analysis = json.loads(ANALYSIS.read_text(encoding="utf-8"))
    for path in FIXTURES:
        raw = json.loads(path.read_text(encoding="utf-8"))
        coerced = coerce_video_structure(
            raw,
            project_id=str(raw.get("projectId") or "project-1"),
            source_video_id=str(raw.get("sourceVideoId") or "sample-1"),
            analysis=analysis,
        )
        path.write_text(json.dumps(coerced, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"upgraded {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
