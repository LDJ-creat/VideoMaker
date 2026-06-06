from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.prompt_loader import PromptLoader
from app.agents.runner import AgentRunner
from app.gateway.model_gateway import ModelGateway
from app.observability.sink import LocalFileSink
from app.pipelines.asset_understanding import run_asset_understanding
from app.pipelines.direct_asset_understanding import (
    PackedMediaItem,
    merge_asset_inventories,
    pack_asset_media_items,
    split_media_batches,
)
from app.pipelines.generation_pipeline import build_asset_inventory
from app.pipelines.user_brief import normalize_user_brief
from app.runtime.agent_run_store import AgentRunStore
from app.runtime.task_context import TaskContext
from app.tools.llm_tool import LLMTool, load_agent_fixtures
from app.validation.schema_loader import validate_contract


def _fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "agents"


def test_merge_asset_inventories_deduplicates_facts() -> None:
    baseline = {
        "id": "inventory-1",
        "projectId": "project-1",
        "userBrief": normalize_user_brief(
            {"sellingPoints": ["A"], "mustMention": [], "avoidMention": []}
        ),
        "assets": [{"id": "asset-1", "type": "text", "uri": "x", "description": "", "tags": []}],
        "extractedFacts": [
            {
                "id": "fact-1",
                "kind": "key_message",
                "text": "A",
                "source": "brief.keyPoints",
            }
        ],
        "candidateMoments": [],
    }
    partial = {
        "extractedFacts": [
            {
                "id": "fact-agent-1",
                "kind": "scene",
                "text": "厨房场景",
                "source": "asset:asset-1",
            },
            {
                "id": "fact-agent-dup",
                "kind": "key_message",
                "text": "A",
                "source": "agent",
            },
        ],
        "candidateMoments": [
            {
                "id": "moment-1",
                "assetId": "asset-1",
                "startSec": 0.0,
                "endSec": 1.0,
                "description": "文案开头",
                "tags": ["intro"],
            }
        ],
        "assets": [{"id": "asset-1", "tags": ["intro"]}],
    }
    merged = merge_asset_inventories(
        baseline,
        [partial],
        route="direct_multimodal",
    )
    assert merged["assetUnderstandingRoute"] == "direct_multimodal"
    assert len(merged["extractedFacts"]) == 2
    assert len(merged["candidateMoments"]) == 1


def test_split_media_batches_keeps_text_in_each_batch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    video_a = tmp_path / "a.mp4"
    video_b = tmp_path / "b.mp4"
    video_a.write_bytes(b"x" * 1024)
    video_b.write_bytes(b"y" * 1024)
    text_item = PackedMediaItem(
        asset_id="text-1",
        asset_type="text",
        path=None,
        text_content="hello",
    )
    media_a = PackedMediaItem(
        asset_id="video-a",
        asset_type="video",
        path=video_a,
        duration_sec=3.0,
    )
    media_b = PackedMediaItem(
        asset_id="video-b",
        asset_type="video",
        path=video_b,
        duration_sec=3.0,
    )

    monkeypatch.setenv("VIDEOMAKER_ASSET_UNDERSTANDING_MAX_MEDIA_COUNT", "1")
    batches = split_media_batches([text_item, media_a, media_b])
    assert len(batches) == 2
    assert all(any(item.asset_id == "text-1" for item in batch) for batch in batches)


def test_run_asset_understanding_direct_fixture(tmp_path: Path) -> None:
    project_id = "project-1"
    asset_id = "asset-video-1"
    asset_path = tmp_path / "projects" / project_id / "assets" / asset_id / "source.mp4"
    asset_path.parent.mkdir(parents=True)
    asset_path.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 128)

    fixtures = load_agent_fixtures(_fixtures_dir())
    runner = AgentRunner(
        llm=LLMTool(fixture_mode=True, fixtures=fixtures),
        prompt_loader=PromptLoader(),
        observability_sink=LocalFileSink(AgentRunStore(tmp_path)),
    )
    context = TaskContext(project_id=project_id, task_id="task-1", storage_root=tmp_path)

    class _RouteStore:
        def get_status(self) -> dict:
            return {
                "preferences": {"directMultimodalAnalysisEnabled": True},
                "providers": {
                    "videoUnderstanding": {"configured": True, "hasApiKey": True},
                },
            }

    baseline = build_asset_inventory(
        project_id=project_id,
        user_brief={
            "contentCategory": "product_commerce",
            "topic": "果汁机",
            "keyPoints": ["便携"],
            "mustMention": [],
            "avoidMention": [],
        },
        assets=[
            {
                "id": asset_id,
                "type": "video",
                "uri": str(asset_path),
                "description": "demo",
                "tags": [],
                "durationSec": 3.0,
            }
        ],
    )

    inventory = run_asset_understanding(
        runner,
        inventory=baseline,
        context=context,
        generation_id="gen-1",
        gateway_store=_RouteStore(),
    )
    validation = validate_contract("asset-inventory", inventory)
    assert validation.valid
    assert inventory["assetUnderstandingRoute"] in {
        "direct_multimodal",
        "direct_multimodal_batched",
    }
    assert inventory["candidateMoments"]


def test_build_asset_inventory_messages_includes_media_parts() -> None:
    messages = ModelGateway.build_asset_inventory_messages(
        system_prompt="analyze",
        text_message={"userBrief": {"topic": "x"}},
        media_parts=[
            {
                "type": "image_url",
                "image_url": {"url": "data:image/jpeg;base64,abc"},
            }
        ],
    )
    user_content = messages[1]["content"]
    assert isinstance(user_content, list)
    assert len(user_content) == 2


def test_pack_asset_media_items_reads_text(tmp_path: Path) -> None:
    project_id = "project-1"
    text_path = tmp_path / "projects" / project_id / "assets" / "text-1" / "source.txt"
    text_path.parent.mkdir(parents=True)
    text_path.write_text("脚本文案", encoding="utf-8")
    items = pack_asset_media_items(
        storage_root=tmp_path,
        project_id=project_id,
        assets=[
            {
                "id": "text-1",
                "type": "text",
                "uri": str(text_path),
                "description": "",
                "tags": [],
            }
        ],
    )
    assert items[0].text_content == "脚本文案"


def test_read_text_asset_content_rejects_non_utf8(tmp_path: Path) -> None:
    from app.pipelines.direct_asset_understanding import read_text_asset_content

    bad_path = tmp_path / "bad.txt"
    bad_path.write_bytes(b"\xff\xfe")
    with pytest.raises(ValueError, match="not valid UTF-8"):
        read_text_asset_content(bad_path)

