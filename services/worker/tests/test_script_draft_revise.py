from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.prompt_loader import PromptLoader
from app.agents.runner import AgentRunner
from app.observability.sink import LocalFileSink
from app.pipelines.script_draft_revise import revise_script_draft
from app.runtime.agent_run_store import AgentRunStore
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool, load_agent_fixtures


def _fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "agents"


def _minimal_structure() -> dict:
    return {
        "id": "vs-1",
        "projectId": "project-1",
        "version": "p1-v3",
        "metadata": {"durationSec": 30.0},
        "slots": [
            {
                "id": "seg-hook-hook_visual-1",
                "startSec": 0.0,
                "endSec": 3.0,
                "visualIntent": "hook visual",
            },
            {
                "id": "seg-hook-hook_text-2",
                "startSec": 0.0,
                "endSec": 3.0,
                "visualIntent": "hook text",
            },
            {
                "id": "seg-2-benefit_card-1",
                "startSec": 3.0,
                "endSec": 10.5,
                "visualIntent": "benefit",
            },
            {
                "id": "seg-3-proof-1",
                "startSec": 10.5,
                "endSec": 22.5,
                "visualIntent": "proof",
            },
            {
                "id": "seg-cta-cta-1",
                "startSec": 25.5,
                "endSec": 30.0,
                "visualIntent": "cta",
            },
        ],
    }


def _write_generation_artifacts(
    tmp_path: Path,
    *,
    project_id: str,
    generation_id: str,
    master_status: str = "draft",
    storyboard_status: str = "draft",
) -> Path:
    generation_root = tmp_path / "projects" / project_id / "generations" / generation_id
    generation_root.mkdir(parents=True, exist_ok=True)
    draft = {
        "generationId": generation_id,
        "projectId": project_id,
        "variant": "high_click",
        "masterNarration": "旧版总脚本口播",
        "masterNarrationStatus": master_status,
        "storyboard": [
            {
                "id": "scene-1",
                "slotId": "seg-hook-hook_visual-1",
                "startSec": 0.0,
                "endSec": 3.0,
                "visual": "旧画面",
                "script": "还在担心出门效率低？",
                "source": "text_completion",
            }
        ],
        "storyboardStatus": storyboard_status,
        "durationTargetSec": 30.0,
        "generationStrategy": "short_form_direct",
    }
    (generation_root / "script-draft.json").write_text(
        json.dumps(draft, ensure_ascii=False),
        encoding="utf-8",
    )
    (generation_root / "structure-scaled.json").write_text(
        json.dumps(_minimal_structure(), ensure_ascii=False),
        encoding="utf-8",
    )
    (generation_root / "asset-inventory.json").write_text(
        json.dumps({"projectId": project_id, "assets": []}, ensure_ascii=False),
        encoding="utf-8",
    )
    (generation_root / "gap-report.json").write_text(json.dumps({"gaps": []}, ensure_ascii=False), encoding="utf-8")
    (generation_root / "duration-target.json").write_text(
        json.dumps({"targetSec": 30.0}, ensure_ascii=False),
        encoding="utf-8",
    )
    return generation_root


def _build_runner(tmp_path: Path) -> AgentRunner:
    return AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=load_agent_fixtures(_fixtures_dir())),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
        model_name="fixture",
    )


def test_revise_master_updates_draft_and_writes_artifacts(tmp_path: Path) -> None:
    project_id = "project-1"
    generation_id = "gen-1"
    generation_root = _write_generation_artifacts(
        tmp_path,
        project_id=project_id,
        generation_id=generation_id,
    )
    runner = _build_runner(tmp_path)
    context = TaskContext(project_id=project_id, task_id="task-1", storage_root=tmp_path)

    result = revise_script_draft(
        runner,
        project_id=project_id,
        generation_id=generation_id,
        scope="master",
        instruction="开头更抓人",
        context=context,
    )

    assert result["ok"] is True
    assert result["revisionId"]
    saved = json.loads((generation_root / "script-draft.json").read_text(encoding="utf-8"))
    assert "便携果汁机" in saved["masterNarration"]
    assert saved["masterNarrationStatus"] == "draft"

    revision_dir = generation_root / "script-nl-revisions" / result["revisionId"]
    assert (revision_dir / "meta.json").is_file()
    assert (revision_dir / "inputs.json").is_file()
    assert (revision_dir / "raw-output.json").is_file() or (revision_dir / "raw-output.txt").is_file()
    assert (revision_dir / "normalized.json").is_file()
    assert (generation_root / "script-nl-revisions" / "index.jsonl").is_file()

    log_dir = tmp_path / "projects" / project_id / "logs" / "agent-runs"
    assert any(log_dir.glob("*.json"))


def test_revise_storyboard_requires_approved_master(tmp_path: Path) -> None:
    project_id = "project-1"
    generation_id = "gen-2"
    _write_generation_artifacts(
        tmp_path,
        project_id=project_id,
        generation_id=generation_id,
        master_status="draft",
    )
    runner = _build_runner(tmp_path)
    context = TaskContext(project_id=project_id, task_id="task-1", storage_root=tmp_path)

    with pytest.raises(ValueError, match="Master narration must be approved"):
        revise_script_draft(
            runner,
            project_id=project_id,
            generation_id=generation_id,
            scope="storyboard",
            instruction="第二镜改成户外",
            context=context,
        )


def test_revise_storyboard_updates_scenes(tmp_path: Path) -> None:
    project_id = "project-1"
    generation_id = "gen-3"
    generation_root = _write_generation_artifacts(
        tmp_path,
        project_id=project_id,
        generation_id=generation_id,
        master_status="approved",
        storyboard_status="draft",
    )
    draft = json.loads((generation_root / "script-draft.json").read_text(encoding="utf-8"))
    draft["masterNarration"] = (
        "还在担心出门效率低？便携果汁机让你随时喝鲜榨。"
        "真实场景对比，效率提升看得见。现在下单，点击购买。"
    )
    (generation_root / "script-draft.json").write_text(
        json.dumps(draft, ensure_ascii=False),
        encoding="utf-8",
    )

    runner = _build_runner(tmp_path)
    context = TaskContext(project_id=project_id, task_id="task-1", storage_root=tmp_path)

    result = revise_script_draft(
        runner,
        project_id=project_id,
        generation_id=generation_id,
        scope="storyboard",
        instruction="强化产品特写画面",
        context=context,
    )

    assert result["ok"] is True
    saved = json.loads((generation_root / "script-draft.json").read_text(encoding="utf-8"))
    assert isinstance(saved["storyboard"], list)
    assert len(saved["storyboard"]) >= 1
    assert saved["storyboardStatus"] == "draft"
