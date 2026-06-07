from __future__ import annotations

import json
import wave
from pathlib import Path
from typing import Any

from app.providers.asset_reuse_provider import AssetReuseProvider
from app.providers.hyperframes_material_provider import HyperFramesMaterialProvider
from app.providers.image_generation_provider import ImageGenerationProvider
from app.providers.material_types import (
    ArtifactRegistrar,
    CompletionStrategyProvider,
    MaterialContext,
    MaterialResult,
    ProgressEmitter,
)
from app.providers.stock_media_provider import StockMediaProvider
from app.providers.tts_provider import TTSProvider
from app.providers.video_generation_provider import VideoGenerationProvider
from app.runtime.video_gen_quota import VideoGenQuota
from app.tools.hyperframes_material_tool import HyperFramesMaterialTool
from app.tools.hyperframes_tool import build_fixture_hyperframes_tool
from app.tools.image_gen_tool import ImageGenTool, ToolError
from app.tools.pexels_tool import PexelsTool
from app.tools.tts_tool import TTSTool
from app.tools.video_gen_tool import VideoGenTool

# Executable material providers (AIGC + HyperFrames clip generation + stock search).
MATERIAL_PROVIDERS = frozenset(
    {
        "asset_reuse",
        "stock_media_search",
        "image_generation",
        "video_generation",
        "tts",
        "hyperframes_material",
    }
)
AIGC_PROVIDERS = frozenset({"asset_reuse", "image_generation", "video_generation", "tts"})
SKIPPED_PROVIDERS = frozenset({"text_completion", "packaging_completion"})


def filter_material_completion_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for action in actions:
        provider = str(action.get("provider") or action.get("strategy", ""))
        if provider in MATERIAL_PROVIDERS:
            filtered.append(action)
    return filtered


def filter_aigc_completion_actions(actions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Backward-compatible alias; prefer ``filter_material_completion_actions``."""
    return filter_material_completion_actions(actions)


def expected_output_path(action: dict[str, Any], generated_root: Path) -> Path:
    slot_id = str(action["slotId"])
    provider = str(action.get("provider") or action.get("strategy", ""))
    if provider == "image_generation":
        return generated_root / f"{slot_id}.png"
    if provider == "video_generation":
        return generated_root / f"{slot_id}.mp4"
    if provider == "tts":
        return generated_root / f"{slot_id}.wav"
    if provider == "asset_reuse":
        return generated_root / f"{slot_id}-reuse.mp4"
    if provider == "stock_media_search":
        for suffix in (".mp4", ".jpg", ".png"):
            candidate = generated_root / f"{slot_id}-stock{suffix}"
            if candidate.is_file():
                return candidate
        return generated_root / f"{slot_id}-stock.mp4"
    if provider == "hyperframes_material":
        action_id = str(action.get("id") or f"action-{slot_id}")
        return generated_root / f"{action_id}.mp4"
    return generated_root / f"{slot_id}.bin"


def action_artifact_satisfied(action: dict[str, Any], generated_root: Path) -> bool:
    artifact_ref = action.get("artifactRef")
    if isinstance(artifact_ref, dict) and artifact_ref.get("uri"):
        path = Path(str(artifact_ref["uri"]))
        if path.is_file() and path.stat().st_size > 0:
            return True
    output = expected_output_path(action, generated_root)
    return output.is_file() and output.stat().st_size > 0


def register_default_providers(ctx: MaterialContext) -> None:
    from app.pipelines.generation_pipeline import is_fixture_material_gateway

    hf_material_tool = HyperFramesMaterialTool()
    if is_fixture_material_gateway(ctx.gateway):
        hf_material_tool = HyperFramesMaterialTool(
            hyperframes_tool=build_fixture_hyperframes_tool(),
        )
    ctx.providers = {
        "image_generation": ImageGenerationProvider(
            ImageGenTool(gateway=ctx.gateway, emit_progress=ctx.emit_progress)
        ),
        "video_generation": VideoGenerationProvider(
            VideoGenTool(gateway=ctx.gateway, emit_progress=ctx.emit_progress)
        ),
        "tts": TTSProvider(
            TTSTool(gateway=ctx.gateway, emit_progress=ctx.emit_progress)
        ),
        "asset_reuse": AssetReuseProvider(),
        "stock_media_search": StockMediaProvider(pexels_tool=PexelsTool()),
        "hyperframes_material": HyperFramesMaterialProvider(hf_material_tool),
    }


def order_completion_actions(
    actions: list[dict[str, Any]],
    *,
    structure: dict[str, Any],
) -> list[dict[str, Any]]:
    importance_by_slot = {
        slot["id"]: slot.get("importance", "nice_to_have")
        for slot in structure.get("slots", [])
        if isinstance(slot, dict) and slot.get("id")
    }

    def sort_key(action: dict[str, Any]) -> tuple[int, str]:
        slot_id = str(action.get("slotId", ""))
        importance = importance_by_slot.get(slot_id, "nice_to_have")
        return (0 if importance == "must_have" else 1, slot_id)

    return sorted(actions, key=sort_key)


def execute_completion_plan(
    actions: list[dict[str, Any]],
    ctx: MaterialContext,
    *,
    fail_fast: bool = True,
    only_aigc: bool = True,
) -> list[MaterialResult]:
    """Execute completion actions via registered providers.

    When ``only_aigc`` is True (pipeline default), providers in ``SKIPPED_PROVIDERS``
    are ignored. Registered providers in ``MATERIAL_PROVIDERS`` execute, including
    ``hyperframes_material``.
    When False, unknown providers raise ``ToolError`` (used in unit tests).
    """
    results: list[MaterialResult] = []
    for action in order_completion_actions(actions, structure=ctx.structure):
        provider_name = str(action.get("provider") or action.get("strategy", ""))
        if only_aigc and provider_name in SKIPPED_PROVIDERS:
            continue
        if only_aigc and provider_name not in MATERIAL_PROVIDERS:
            continue
        if provider_name not in MATERIAL_PROVIDERS:
            raise ToolError(
                code="provider_not_registered",
                message=f"No completion provider registered for {provider_name}",
                retryable=False,
            )
        action_id = str(action["id"])
        if action_id.endswith("-ken-burns"):
            stock_video = ctx.generated_root / f"{action['slotId']}-stock.mp4"
            if stock_video.is_file() and stock_video.stat().st_size > 0:
                ctx.completed_action_ids.add(action_id)
                continue
        if action_id in ctx.completed_action_ids and action_artifact_satisfied(action, ctx.generated_root):
            continue
        provider = ctx.providers.get(provider_name)
        if provider is None:
            raise ToolError(
                code="provider_not_registered",
                message=f"Provider {provider_name} is not registered",
                retryable=False,
            )
        ctx.emit_progress("generating_material", f"Completing slot {action.get('slotId')}")
        result = provider.execute(action, ctx)
        if not result.get("ok"):
            fallback = str((result.get("error") or {}).get("fallbackProvider", "")).strip()
            if fallback in MATERIAL_PROVIDERS and fallback != provider_name:
                fallback_impl = ctx.providers.get(fallback)
                if fallback_impl is not None:
                    fallback_action = {**action, "provider": fallback, "strategy": fallback}
                    ctx.emit_progress(
                        "generating_material",
                        f"Fallback {fallback} for slot {action.get('slotId')}",
                    )
                    result = fallback_impl.execute(fallback_action, ctx)
        results.append(result)
        if not result.get("ok"):
            if fail_fast:
                return results
            continue
        ctx.completed_action_ids.add(str(action["id"]))
    return results


def load_material_state(path: Path) -> tuple[VideoGenQuota, set[str]]:
    if not path.is_file():
        return VideoGenQuota(), set()
    data = json.loads(path.read_text(encoding="utf-8"))
    quota = VideoGenQuota.from_checkpoint(data.get("videoGenQuota"))
    completed = set(data.get("completedActionIds", []))
    return quota, completed


def save_material_state(
    path: Path,
    *,
    quota: VideoGenQuota,
    completed_action_ids: set[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "videoGenQuota": quota.to_checkpoint(),
        "completedActionIds": sorted(completed_action_ids),
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


VISUAL_MATERIAL_PROVIDERS = frozenset(
    {
        "asset_reuse",
        "stock_media_search",
        "image_generation",
        "video_generation",
        "hyperframes_material",
    }
)


def _voiceover_track(tracks: list[dict[str, Any]]) -> dict[str, Any]:
    for track in tracks:
        if isinstance(track, dict) and track.get("type") == "voiceover":
            return track
    voiceover_track = {"id": "track-voiceover", "type": "voiceover", "clips": []}
    tracks.append(voiceover_track)
    return voiceover_track


def _scene_timing_by_slot(storyboard: list[Any]) -> dict[str, tuple[float, float]]:
    timing: dict[str, tuple[float, float]] = {}
    for scene in storyboard:
        if not isinstance(scene, dict):
            continue
        slot_id = str(scene.get("slotId", ""))
        if not slot_id:
            continue
        timing[slot_id] = (float(scene["startSec"]), float(scene["endSec"]))
    return timing


def _wav_duration_sec(path: Path) -> float | None:
    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate()
            if rate <= 0:
                return None
            return handle.getnframes() / float(rate)
    except (OSError, wave.Error):
        return None


def _voiceover_end_sec(
    *,
    start_sec: float,
    storyboard_end_sec: float,
    wav_path: Path | None,
) -> float:
    """Clamp voiceover clip end to storyboard window and actual wav length when shorter."""
    end_sec = storyboard_end_sec
    if wav_path is not None and wav_path.is_file():
        duration = _wav_duration_sec(wav_path)
        if duration is not None and duration > 0:
            end_sec = min(end_sec, start_sec + duration)
    return max(start_sec, end_sec)


def apply_material_results_to_plan(
    plan: dict[str, Any],
    *,
    results: list[MaterialResult],
    render_root: Path | None = None,
) -> dict[str, Any]:
    results_by_action = {str(item.get("actionId")): item for item in results if item.get("actionId")}
    visual_by_slot: dict[str, MaterialResult] = {}
    tts_by_slot: dict[str, MaterialResult] = {}
    for result in results:
        if not result.get("ok") or not result.get("slotId"):
            continue
        slot_id = str(result["slotId"])
        provider = str(result.get("provider", ""))
        if provider == "tts":
            tts_by_slot[slot_id] = result
        elif provider in VISUAL_MATERIAL_PROVIDERS:
            visual_by_slot[slot_id] = result

    updated_actions: list[dict[str, Any]] = []
    for action in plan.get("completionActions", []):
        merged = dict(action)
        result = results_by_action.get(str(action.get("id")))
        if result and result.get("ok") and result.get("artifactRef"):
            merged["artifactRef"] = result["artifactRef"]
            merged["outputRef"] = result["artifactRef"]["uri"]
        if result and result.get("stockAttribution"):
            merged["stockAttribution"] = result["stockAttribution"]
        if result and result.get("stockSearchQuery"):
            merged["stockSearchQuery"] = result["stockSearchQuery"]
        updated_actions.append(merged)
    plan["completionActions"] = updated_actions

    storyboard = plan.get("storyboard", [])
    if isinstance(storyboard, list):
        updated_storyboard: list[dict[str, Any]] = []
        for scene in storyboard:
            if not isinstance(scene, dict):
                updated_storyboard.append(scene)
                continue
            merged_scene = dict(scene)
            slot_id = str(scene.get("slotId", ""))
            result = visual_by_slot.get(slot_id)
            if result and result.get("ok"):
                merged_scene["source"] = "generated"
                artifact = result.get("artifactRef") or {}
                if artifact.get("uri"):
                    merged_scene["visual"] = _material_source_ref(
                        str(artifact.get("uri")),
                        render_root=render_root,
                    )
            updated_storyboard.append(merged_scene)
        plan["storyboard"] = updated_storyboard

    plan["timeline"] = _apply_generated_sources_to_timeline(
        plan.get("timeline", {}),
        results=results,
        render_root=render_root,
        storyboard=plan.get("storyboard", []),
    )
    return plan


def _generated_by_from_result(result: MaterialResult) -> dict[str, Any]:
    generated = result.get("generatedBy")
    if isinstance(generated, dict):
        return dict(generated)
    provider = str(result.get("provider", ""))
    payload: dict[str, Any] = {"provider": provider}
    attribution = result.get("stockAttribution")
    if isinstance(attribution, dict):
        payload["source"] = attribution.get("source", "pexels")
        payload["photographer"] = attribution.get("photographer")
        payload["pageUrl"] = attribution.get("pageUrl")
    return payload


def _material_source_ref(uri: str, *, render_root: Path | None) -> str:
    if render_root is None:
        return uri
    path = Path(uri)
    if not path.is_file():
        return uri
    dest_dir = render_root / "materials"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / path.name
    if not dest.exists() or dest.stat().st_size == 0:
        dest.write_bytes(path.read_bytes())
    return f"materials/{path.name}"


def _is_video_artifact(artifact: dict[str, Any], uri: str) -> bool:
    if str(artifact.get("type", "")).lower() == "video":
        return True
    return uri.lower().endswith((".mp4", ".webm", ".mov", ".mkv"))


def _video_track(tracks: list[dict[str, Any]]) -> dict[str, Any]:
    for track in tracks:
        if isinstance(track, dict) and track.get("type") == "video":
            return track
    video_track = {"id": "track-video", "type": "video", "clips": []}
    tracks.append(video_track)
    return video_track


def _find_clip_for_slot(tracks: list[Any], slot_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    clip_id = f"clip-{slot_id}"
    for track in tracks:
        if not isinstance(track, dict):
            continue
        clips = track.get("clips")
        if not isinstance(clips, list):
            continue
        for index, clip in enumerate(clips):
            if isinstance(clip, dict) and str(clip.get("id", "")) == clip_id:
                return track, clips.pop(index)
    return None


def _apply_generated_sources_to_timeline(
    timeline: dict[str, Any],
    *,
    results: list[MaterialResult],
    render_root: Path | None = None,
    storyboard: list[Any] | None = None,
) -> dict[str, Any]:
    visual_by_slot: dict[str, MaterialResult] = {}
    tts_by_slot: dict[str, MaterialResult] = {}
    for result in results:
        if not result.get("ok") or not result.get("slotId"):
            continue
        slot_id = str(result["slotId"])
        provider = str(result.get("provider", ""))
        if provider == "tts":
            tts_by_slot[slot_id] = result
        elif provider in VISUAL_MATERIAL_PROVIDERS:
            visual_by_slot[slot_id] = result

    tracks = timeline.get("tracks", [])
    if not isinstance(tracks, list):
        return timeline

    video_track = _video_track(tracks)
    scene_timing = _scene_timing_by_slot(storyboard or [])

    for slot_id, result in visual_by_slot.items():
        artifact = result.get("artifactRef") or {}
        uri = str(artifact.get("uri", "")).strip()
        if not uri:
            continue
        source_ref = _material_source_ref(uri, render_root=render_root)
        is_video = _is_video_artifact(artifact, source_ref)

        located = _find_clip_for_slot(tracks, slot_id)
        if located is not None:
            track, clip = located
            clip["sourceRef"] = source_ref
            clip["generatedBy"] = _generated_by_from_result(result)
            clip.pop("content", None)
            clip.pop("styleRef", None)
            if is_video and track.get("type") != "video":
                video_track["clips"].append(clip)
            elif track.get("type") == "video" or not is_video:
                track.setdefault("clips", []).append(clip)
            continue

        for track in tracks:
            if not isinstance(track, dict):
                continue
            for clip in track.get("clips", []):
                if not isinstance(clip, dict):
                    continue
                clip_id = str(clip.get("id", ""))
                derived_slot = clip_id.removeprefix("clip-") if clip_id.startswith("clip-") else ""
                if derived_slot != slot_id:
                    continue
                clip["sourceRef"] = source_ref
                clip["generatedBy"] = _generated_by_from_result(result)
                if track.get("type") == "text" and artifact.get("type") in {"image", "video"}:
                    clip.pop("content", None)
                    clip.pop("styleRef", None)
                if is_video and track.get("type") != "video":
                    track["clips"] = [
                        item
                        for item in track.get("clips", [])
                        if not (isinstance(item, dict) and item is clip)
                    ]
                    video_track["clips"].append(clip)
                break

    voiceover_track = _voiceover_track(tracks)
    vo_clips = voiceover_track.setdefault("clips", [])
    vo_by_id = {
        str(clip.get("id", "")): clip
        for clip in vo_clips
        if isinstance(clip, dict)
    }

    for slot_id, result in tts_by_slot.items():
        artifact = result.get("artifactRef") or {}
        uri = str(artifact.get("uri", "")).strip()
        if not uri:
            continue
        source_ref = _material_source_ref(uri, render_root=render_root)
        start_sec, storyboard_end_sec = scene_timing.get(slot_id, (0.0, 0.0))
        wav_path: Path | None = None
        if render_root is not None:
            material_candidate = render_root / source_ref
            if material_candidate.is_file():
                wav_path = material_candidate
        if wav_path is None:
            uri_path = Path(uri)
            if uri_path.is_file():
                wav_path = uri_path
        end_sec = _voiceover_end_sec(
            start_sec=start_sec,
            storyboard_end_sec=storyboard_end_sec,
            wav_path=wav_path,
        )
        vo_id = f"vo-{slot_id}"
        vo_clip = vo_by_id.get(vo_id) or {
            "id": vo_id,
            "startSec": start_sec,
            "endSec": end_sec,
        }
        vo_clip["startSec"] = start_sec
        vo_clip["endSec"] = end_sec
        vo_clip["sourceRef"] = source_ref
        vo_clip["generatedBy"] = {"provider": "tts"}
        if vo_id not in vo_by_id:
            vo_clips.append(vo_clip)
            vo_by_id[vo_id] = vo_clip

    return timeline
