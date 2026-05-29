from pathlib import Path
from unittest.mock import MagicMock
import json

import pytest

from app.providers.completion_registry import (
    MaterialContext,
    action_artifact_satisfied,
    execute_completion_plan,
    register_default_providers,
    save_material_state,
)
from app.providers.hyperframes_material_provider import HyperFramesMaterialProvider
from app.runtime.video_gen_quota import VideoGenQuota
from app.tools.hyperframes_tool import CommandResult, HyperFramesTool
from app.tools.hyperframes_material_tool import HyperFramesMaterialTool
from app.tools.image_gen_tool import ToolError


def _action(action_id: str, slot_id: str, provider: str) -> dict:
    return {
        "id": action_id,
        "slotId": slot_id,
        "strategy": provider,
        "provider": provider,
        "reason": "test gap",
        "outputRef": f"completion://{slot_id}/{provider}",
    }


def _make_ctx(tmp_path: Path, **overrides) -> MaterialContext:
    generated_root = tmp_path / "generated"
    generated_root.mkdir(parents=True, exist_ok=True)
    defaults = {
        "project_id": "project-1",
        "generation_id": "gen-1",
        "render_root": tmp_path / "renders" / "gen-1",
        "generated_root": generated_root,
        "gateway": MagicMock(),
        "quota": VideoGenQuota(max_calls=1),
        "inventory": {"assets": []},
        "slot_matches": [],
        "storyboard": [],
        "structure": {"slots": []},
        "emit_progress": lambda *_args, **_kwargs: None,
        "register_artifact": lambda artifact_type, path: {
            "id": "art-1",
            "type": artifact_type,
            "uri": str(Path(path).resolve()),
            "createdAt": "2026-05-29T00:00:00Z",
        },
    }
    defaults.update(overrides)
    return MaterialContext(**defaults)


def test_execute_image_generation_action(tmp_path: Path) -> None:
    png = b"\x89PNG\r\n\x1a\n"
    gateway = MagicMock()
    gateway.generate_image.return_value = png
    ctx = _make_ctx(
        tmp_path,
        gateway=gateway,
        storyboard=[
            {
                "id": "scene-1",
                "slotId": "slot-hook",
                "startSec": 0.0,
                "endSec": 3.0,
                "visual": "hook",
                "script": "hello",
                "source": "text_completion",
            }
        ],
        structure={
            "slots": [
                {
                    "id": "slot-hook",
                    "importance": "must_have",
                    "role": "hook_visual",
                    "requiredAssetType": ["image"],
                }
            ]
        },
    )
    register_default_providers(ctx)

    results = execute_completion_plan(
        [_action("action-1", "slot-hook", "image_generation")],
        ctx,
    )

    assert len(results) == 1
    assert results[0]["ok"] is True
    assert results[0]["artifactRef"]["type"] == "image"
    assert Path(results[0]["artifactRef"]["uri"]).exists()


def test_apply_material_results_updates_storyboard(tmp_path: Path) -> None:
    from app.providers.completion_registry import apply_material_results_to_plan

    plan = {
        "storyboard": [
            {
                "id": "scene-1",
                "slotId": "slot-hook",
                "startSec": 0.0,
                "endSec": 3.0,
                "visual": "hook",
                "script": "hello",
                "source": "text_completion",
            }
        ],
        "completionActions": [_action("action-1", "slot-hook", "image_generation")],
        "timeline": {"durationSec": 3.0, "tracks": []},
    }
    artifact_uri = str((tmp_path / "generated" / "slot-hook.png").resolve())
    results = [
        {
            "ok": True,
            "actionId": "action-1",
            "slotId": "slot-hook",
            "provider": "image_generation",
            "artifactRef": {"id": "a1", "type": "image", "uri": artifact_uri},
        }
    ]
    updated = apply_material_results_to_plan(plan, results=results)
    assert updated["storyboard"][0]["source"] == "generated"
    assert updated["storyboard"][0]["visual"] == artifact_uri


def test_second_video_generation_raises_quota_error(tmp_path: Path) -> None:
    video_bytes = b"fake-mp4"
    gateway = MagicMock()
    gateway.submit_video_job.return_value = "job-1"
    poll_result = MagicMock()
    poll_result.video_bytes = video_bytes
    gateway.poll_video_job.return_value = poll_result

    ctx = _make_ctx(tmp_path, gateway=gateway)
    register_default_providers(ctx)
    actions = [
        _action("action-v1", "slot-a", "video_generation"),
        _action("action-v2", "slot-b", "video_generation"),
    ]

    results = execute_completion_plan(actions, ctx)
    assert results[0]["ok"] is True
    assert results[1]["ok"] is False
    assert results[1]["error"]["code"] == "video_quota_exceeded"
    assert ctx.quota.used == 1


def test_execute_hyperframes_material_action(tmp_path: Path) -> None:
    structure = {
        "slots": [
            {
                "id": "seg-2-benefit_card-1",
                "role": "benefit_card",
                "scriptIntent": "highlight benefits",
                "visualIntent": "card",
                "importance": "must_have",
                "requiredAssetType": ["packaging"],
            }
        ]
    }
    project_root = tmp_path / "projects" / "project-1"
    generated_root = project_root / "generations" / "gen-1" / "generated"
    render_root = project_root / "renders" / "gen-1"
    generated_root.mkdir(parents=True, exist_ok=True)
    render_root.mkdir(parents=True, exist_ok=True)

    def cli_runner(command: list[str], cwd: Path) -> CommandResult:
        if "render" in command:
            output_index = command.index("--output") + 1
            Path(command[output_index]).write_bytes(b"mock-mp4")
        return CommandResult(returncode=0, stdout="ok", stderr="")

    ctx = _make_ctx(
        tmp_path,
        structure=structure,
        render_root=render_root,
        generated_root=generated_root,
    )
    register_default_providers(ctx)
    ctx.providers["hyperframes_material"] = HyperFramesMaterialProvider(
        HyperFramesMaterialTool(hyperframes_tool=HyperFramesTool(command_runner=cli_runner))
    )

    spec_path = Path(__file__).parent / "fixtures" / "material_specs" / "benefit_card.json"
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    action = {
        "id": "action-hf",
        "slotId": "seg-2-benefit_card-1",
        "provider": "hyperframes_material",
        "strategy": "hyperframes_material",
        "reason": "card",
        "outputRef": "completion://seg-2-benefit_card-1/hyperframes_material",
        "materialSpec": spec,
    }

    results = execute_completion_plan([action], ctx)

    assert len(results) == 1
    assert results[0]["ok"] is True
    assert (generated_root / "action-hf.mp4").exists()


def test_unimplemented_provider_fails_without_fallback(tmp_path: Path) -> None:
    ctx = _make_ctx(tmp_path)
    register_default_providers(ctx)

    with pytest.raises(ToolError) as exc_info:
        execute_completion_plan(
            [_action("action-text", "slot-x", "text_completion")],
            ctx,
            only_aigc=False,
        )

    assert exc_info.value.code == "provider_not_registered"
    assert exc_info.value.retryable is False


def test_resume_reruns_when_marked_complete_but_file_missing(tmp_path: Path) -> None:
    png = b"\x89PNG\r\n\x1a\n"
    gateway = MagicMock()
    gateway.generate_image.return_value = png
    ctx = _make_ctx(
        tmp_path,
        gateway=gateway,
        completed_action_ids={"action-1"},
        storyboard=[
            {
                "id": "scene-1",
                "slotId": "slot-hook",
                "startSec": 0.0,
                "endSec": 3.0,
                "visual": "hook",
                "script": "hello",
                "source": "text_completion",
            }
        ],
    )
    register_default_providers(ctx)
    action = _action("action-1", "slot-hook", "image_generation")
    assert not action_artifact_satisfied(action, ctx.generated_root)

    results = execute_completion_plan([action], ctx)
    assert len(results) == 1
    assert results[0]["ok"] is True


def test_resume_skips_when_artifact_file_exists(tmp_path: Path) -> None:
    gateway = MagicMock()
    output = tmp_path / "generated" / "slot-hook.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(b"\x89PNG\r\n\x1a\n")
    ctx = _make_ctx(
        tmp_path,
        gateway=gateway,
        completed_action_ids={"action-1"},
    )
    register_default_providers(ctx)
    action = _action("action-1", "slot-hook", "image_generation")
    assert action_artifact_satisfied(action, ctx.generated_root)

    results = execute_completion_plan([action], ctx)
    assert results == []
    gateway.generate_image.assert_not_called()
