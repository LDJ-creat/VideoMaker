from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext

TASK_KEY = "material_reviewer"
SCHEMA_NAME = "material-reviewer-output"
PROMPT_RELATIVE_PATH = Path("packages") / "prompts" / "agents" / "material_reviewer.md"


def _detect_repo_root() -> Path:
    current = Path(__file__).resolve()
    return current.parents[4]


def load_prompt() -> str:
    return (_detect_repo_root() / PROMPT_RELATIVE_PATH).read_text(encoding="utf-8")


def run_material_reviewer(
    runner: AgentRunner,
    *,
    review_payload: dict[str, Any],
    context: TaskContext,
    progress: int = 68,
    generation_id: str | None = None,
) -> dict[str, Any]:
    return runner.run(
        "material_reviewer",
        task=TASK_KEY,
        schema_name=SCHEMA_NAME,
        inputs={
            "systemPrompt": load_prompt(),
            "reviewPayload": review_payload,
        },
        context=context,
        progress=progress,
        generation_id=generation_id,
    )
