from pathlib import Path
from typing import Any
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
    assert len(results) == 1
    assert results[0]["ok"] is True
    assert results[0]["actionId"] == "action-1"
    gateway.generate_image.assert_not_called()


def test_resume_skips_existing_artifacts_when_completed_ids_empty(tmp_path: Path) -> None:
    from app.pipelines.tts_mode import MASTER_TTS_SLOT_ID

    png = tmp_path / "generated" / "slot-1.png"
    png.parent.mkdir(parents=True, exist_ok=True)
    png.write_bytes(b"\x89PNG\r\n\x1a\n")

    tts_invoked: list[dict[str, Any]] = []
    image_called = False

    class FakeTTS:
        name = "tts"

        def execute(self, action: dict, ctx: MaterialContext) -> dict:
            tts_invoked.append(action)
            wav = ctx.generated_root / "master.wav"
            wav.write_bytes(b"RIFF----WAVE")
            return {
                "ok": True,
                "actionId": action["id"],
                "slotId": action["slotId"],
                "provider": "tts",
                "artifactRef": {"uri": str(wav)},
            }

    ctx = _make_ctx(
        tmp_path,
        completed_action_ids=set(),
        material_state_path=tmp_path / "material-state.json",
    )
    register_default_providers(ctx)
    ctx.providers["tts"] = FakeTTS()
    orig_image = ctx.providers["image_generation"]

    class TrackingImage:
        name = "image_generation"

        def execute(self, action: dict, ctx: MaterialContext) -> dict:
            nonlocal image_called
            image_called = True
            return orig_image.execute(action, ctx)

    ctx.providers["image_generation"] = TrackingImage()

    execute_completion_plan(
        [
            _action("action-slot-1", "slot-1", "image_generation"),
            _action("action-master-tts", MASTER_TTS_SLOT_ID, "tts"),
        ],
        ctx,
    )

    assert image_called is False
    assert len(tts_invoked) == 1
    state = json.loads((tmp_path / "material-state.json").read_text(encoding="utf-8"))
    assert "action-slot-1" in state["completedActionIds"]
    assert "action-master-tts" in state["completedActionIds"]


def test_apply_material_moves_video_clip_to_video_track(tmp_path: Path) -> None:
    from app.providers.completion_registry import apply_material_results_to_plan

    video_uri = str((tmp_path / "generated" / "slot-hook.mp4").resolve())
    (tmp_path / "generated").mkdir(parents=True, exist_ok=True)
    Path(video_uri).write_bytes(b"mp4")

    plan = {
        "storyboard": [],
        "completionActions": [],
        "timeline": {
            "durationSec": 5.0,
            "tracks": [
                {
                    "id": "track-text",
                    "type": "text",
                    "clips": [
                        {
                            "id": "clip-slot-hook",
                            "startSec": 0.0,
                            "endSec": 5.0,
                            "content": "placeholder",
                            "styleRef": "style://packaging/default",
                        }
                    ],
                },
                {"id": "track-video", "type": "video", "clips": []},
            ],
        },
    }
    results = [
        {
            "ok": True,
            "actionId": "action-v",
            "slotId": "slot-hook",
            "provider": "video_generation",
            "artifactRef": {"id": "a1", "type": "video", "uri": video_uri},
        }
    ]
    updated = apply_material_results_to_plan(plan, results=results)
    video_clips = updated["timeline"]["tracks"][1]["clips"]
    text_clips = updated["timeline"]["tracks"][0]["clips"]
    assert len(video_clips) == 1
    assert video_clips[0]["id"] == "clip-slot-hook"
    assert video_clips[0]["sourceRef"].endswith("slot-hook.mp4")
    assert len(text_clips) == 0


def test_video_generation_fallback_runs_image_generation(tmp_path: Path) -> None:
    png = b"\x89PNG\r\n\x1a\n"
    gateway = MagicMock()
    gateway.submit_video_job.side_effect = ToolError(
        code="video_failed",
        message="upstream error",
        retryable=False,
    )
    gateway.generate_image.return_value = png

    ctx = _make_ctx(
        tmp_path,
        gateway=gateway,
        quota=VideoGenQuota(max_slots=2, max_per_slot=1),
        storyboard=[
            {
                "id": "scene-1",
                "slotId": "slot-hook",
                "startSec": 0.0,
                "endSec": 3.0,
                "visual": "hook",
                "script": "hello",
            }
        ],
    )
    register_default_providers(ctx)

    import os

    os.environ["VIDEOMAKER_VIDEO_GEN_FALLBACK"] = "image_generation"
    try:
        results = execute_completion_plan(
            [_action("action-v", "slot-hook", "video_generation")],
            ctx,
        )
    finally:
        os.environ.pop("VIDEOMAKER_VIDEO_GEN_FALLBACK", None)

    assert len(results) == 1
    assert results[0]["ok"] is True
    assert results[0]["provider"] == "image_generation"
    assert (tmp_path / "generated" / "slot-hook.png").is_file()


def test_run_generating_material_seeds_quota_from_gap_report(tmp_path: Path) -> None:
    from app.pipelines.generation_pipeline import run_generating_material

    structure = {
        "slots": [
            {"id": "slot1", "role": "hook_visual", "requiredAssetType": ["video"]},
            {"id": "slot2", "role": "usage_scene", "requiredAssetType": ["image"]},
            {"id": "slot3", "role": "hook_text", "requiredAssetType": ["text"]},
        ]
    }
    gap_report = {
        "weakSlots": [{"slotId": "slot2"}],
        "missingSlots": [{"slotId": "slot1"}],
    }
    generation_root = tmp_path / "gen"
    generation_root.mkdir()
    plan = {"id": "gen-1", "projectId": "p1", "completionActions": [], "storyboard": []}

    gateway = MagicMock()
    gateway.generate_image.return_value = b"\x89PNG\r\n\x1a\n"

    run_generating_material(
        plan=plan,
        inventory={"assets": []},
        slot_matches=[],
        structure=structure,
        generation_root=generation_root,
        render_root=tmp_path / "render",
        gateway=gateway,
        emit_progress=lambda *_args: None,
        register_artifact=lambda t, p: {"type": t, "uri": str(p)},
        gap_report=gap_report,
    )

    state_path = generation_root / "material-state.json"
    assert state_path.is_file()
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    assert payload["videoGenQuota"]["maxSlots"] == 2


def test_apply_material_results_adds_voiceover_clip(tmp_path: Path) -> None:
    from app.pipelines.tts_mode import MASTER_TTS_SLOT_ID, VO_MASTER_CLIP_ID
    from app.providers.completion_registry import apply_material_results_to_plan

    wav_uri = str((tmp_path / "generated" / "master.wav").resolve())
    (tmp_path / "generated").mkdir(parents=True, exist_ok=True)
    Path(wav_uri).write_bytes(b"RIFF----WAVE")

    render_root = tmp_path / "renders" / "gen-1"
    plan = {
        "ttsMode": "global",
        "storyboard": [
            {
                "id": "scene-1",
                "slotId": "slot-hook",
                "startSec": 0.0,
                "endSec": 5.0,
                "visual": "hook",
                "script": "hello narration",
                "source": "text_completion",
            }
        ],
        "completionActions": [
            _action("action-master-tts", MASTER_TTS_SLOT_ID, "tts"),
        ],
        "timeline": {
            "durationSec": 5.0,
            "tracks": [
                {"id": "track-video", "type": "video", "clips": []},
                {"id": "track-text", "type": "text", "clips": []},
                {"id": "track-voiceover", "type": "voiceover", "clips": []},
            ],
        },
    }
    results = [
        {
            "ok": True,
            "actionId": "action-master-tts",
            "slotId": MASTER_TTS_SLOT_ID,
            "provider": "tts",
            "artifactRef": {"id": "a1", "type": "audio", "uri": wav_uri},
        }
    ]
    updated = apply_material_results_to_plan(plan, results=results, render_root=render_root)
    vo_track = next(t for t in updated["timeline"]["tracks"] if t["type"] == "voiceover")
    assert len(vo_track["clips"]) == 1
    assert vo_track["clips"][0]["id"] == VO_MASTER_CLIP_ID
    assert vo_track["clips"][0]["sourceRef"] == "materials/master.wav"
    assert vo_track["clips"][0]["startSec"] == 0.0
    assert (render_root / "materials" / "master.wav").is_file()
    assert updated["storyboard"][0]["source"] == "text_completion"


def test_apply_material_clamps_voiceover_end_to_wav_duration(tmp_path: Path) -> None:
    from app.pipelines.tts_mode import MASTER_TTS_SLOT_ID, VO_MASTER_CLIP_ID
    from app.providers.completion_registry import apply_material_results_to_plan
    import struct
    import wave

    wav_path = tmp_path / "generated" / "master.wav"
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav_path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(struct.pack("<h", 0) * 24000)

    render_root = tmp_path / "renders" / "gen-1"
    plan = {
        "ttsMode": "global",
        "storyboard": [
            {
                "id": "scene-1",
                "slotId": "slot-hook",
                "startSec": 0.0,
                "endSec": 10.0,
                "script": "hello",
            }
        ],
        "completionActions": [],
        "timeline": {
            "durationSec": 10.0,
            "tracks": [{"id": "track-voiceover", "type": "voiceover", "clips": []}],
        },
    }
    results = [
        {
            "ok": True,
            "actionId": "action-master-tts",
            "slotId": MASTER_TTS_SLOT_ID,
            "provider": "tts",
            "artifactRef": {"id": "a1", "type": "audio", "uri": str(wav_path.resolve())},
        }
    ]
    updated = apply_material_results_to_plan(plan, results=results, render_root=render_root)
    vo_clip = updated["timeline"]["tracks"][0]["clips"][0]
    assert vo_clip["id"] == VO_MASTER_CLIP_ID
    assert vo_clip["startSec"] == 0.0
    assert vo_clip["endSec"] == 1.0


def test_execute_tts_action(tmp_path: Path) -> None:
    from app.pipelines.tts_mode import MASTER_TTS_SLOT_ID

    wav = b"RIFF----WAVEfmt "
    gateway = MagicMock()
    gateway.config = MagicMock()
    gateway.config.tts_preferences = {}
    gateway.synthesize_speech.return_value = wav
    ctx = _make_ctx(
        tmp_path,
        gateway=gateway,
        master_narration="你好，这是口播",
        storyboard=[
            {
                "id": "scene-1",
                "slotId": "slot-hook",
                "startSec": 0.0,
                "endSec": 3.0,
                "visual": "hook",
                "script": "你好，这是口播",
                "source": "text_completion",
            }
        ],
    )
    register_default_providers(ctx)

    results = execute_completion_plan(
        [_action("action-master-tts", MASTER_TTS_SLOT_ID, "tts")],
        ctx,
    )

    assert len(results) == 1
    assert results[0]["ok"] is True
    assert results[0]["artifactRef"]["type"] == "audio"
    assert Path(results[0]["artifactRef"]["uri"]).exists()
    assert (tmp_path / "generated" / "master.wav").is_file()


def test_apply_material_global_voiceover_single_clip(tmp_path: Path) -> None:
    from app.providers.completion_registry import apply_material_results_to_plan
    import struct
    import wave

    wav_path = tmp_path / "generated" / "master.wav"
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(wav_path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(24000)
        handle.writeframes(struct.pack("<h", 0) * 48000)

    render_root = tmp_path / "renders" / "gen-1"
    plan = {
        "ttsMode": "global",
        "masterNarration": "全片口播测试。",
        "storyboard": [
            {
                "id": "scene-1",
                "slotId": "slot-hook",
                "startSec": 0.0,
                "endSec": 5.0,
                "script": "ignored in global",
            }
        ],
        "packagingPlan": {
            "styleSummary": "demo",
            "subtitle": {"preset": "clean"},
            "titleCards": [],
            "transitions": [],
        },
        "completionActions": [],
        "timeline": {
            "durationSec": 5.0,
            "tracks": [
                {"id": "track-text", "type": "text", "clips": []},
                {"id": "track-voiceover", "type": "voiceover", "clips": []},
            ],
        },
    }
    results = [
        {
            "ok": True,
            "actionId": "action-master-tts",
            "slotId": "__master__",
            "provider": "tts",
            "artifactRef": {"id": "a1", "type": "audio", "uri": str(wav_path.resolve())},
        }
    ]
    updated = apply_material_results_to_plan(plan, results=results, render_root=render_root)
    vo_track = next(t for t in updated["timeline"]["tracks"] if t["type"] == "voiceover")
    assert len(vo_track["clips"]) == 1
    assert vo_track["clips"][0]["id"] == "vo-master"
    assert vo_track["clips"][0]["endSec"] == 2.0
    assert updated.get("narrationDurationSec") == 2.0
    subtitles = [
        c
        for c in next(t for t in updated["timeline"]["tracks"] if t["type"] == "text")["clips"]
        if str(c.get("id", "")).startswith("subtitle-master")
    ]
    assert subtitles
    assert subtitles[-1]["endSec"] == 2.0
