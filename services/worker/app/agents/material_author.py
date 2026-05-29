from __future__ import annotations

from pathlib import Path
from typing import Any, TYPE_CHECKING

from app.tools.llm_tool import LLMTool

if TYPE_CHECKING:
    from app.agents.runner import AgentRunner
    from app.runtime.task_context import TaskContext

TASK_KEY = "material_author"
SCHEMA_NAME = "material-spec"
PROMPT_RELATIVE_PATH = Path("packages") / "prompts" / "agents" / "material_author.md"


def _detect_repo_root() -> Path:
    current = Path(__file__).resolve()
    return current.parents[4]


def load_prompt() -> str:
    prompt_path = _detect_repo_root() / PROMPT_RELATIVE_PATH
    return prompt_path.read_text(encoding="utf-8")


def run_material_author(
    llm: LLMTool,
    *,
    slot: dict[str, Any],
    variant_overrides: dict[str, Any] | None = None,
    brand_colors: dict[str, Any] | None = None,
    asset_refs: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "systemPrompt": load_prompt(),
        "slot": slot,
        "variantOverrides": variant_overrides or {},
        "brandColors": brand_colors or {},
    }
    if asset_refs:
        inputs["assetRefs"] = asset_refs
    return llm.generate_json(TASK_KEY, inputs, SCHEMA_NAME)


def run_material_author_with_runner(
    runner: AgentRunner,
    *,
    slot: dict[str, Any],
    context: TaskContext,
    variant_overrides: dict[str, Any] | None = None,
    brand_colors: dict[str, Any] | None = None,
    asset_refs: list[dict[str, Any]] | None = None,
    progress: int = 58,
    generation_id: str | None = None,
) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "slot": slot,
        "variantOverrides": variant_overrides or {},
        "brandColors": brand_colors or {},
    }
    if asset_refs:
        inputs["assetRefs"] = asset_refs
    return runner.run(
        "material_author",
        task=TASK_KEY,
        schema_name=SCHEMA_NAME,
        inputs=inputs,
        context=context,
        progress=progress,
        generation_id=generation_id,
    )
