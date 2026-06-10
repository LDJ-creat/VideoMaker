from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.pipelines.narration_alignment import align_subtitles_to_voiceover, wav_duration_sec
from app.pipelines.narration_timeline import sync_timeline_to_narration
from app.pipelines.tts_mode import (
    MASTER_TTS_SLOT_ID,
    VO_MASTER_CLIP_ID,
    is_global_tts_mode,
    resolve_tts_mode,
)

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

# Stock / reuse mp4 below this size are treated as failed downloads.
MIN_STOCK_VIDEO_BYTES = 100_000
# HyperFrames text-card clips can be smaller but sub-15KB outputs are near-black failures.
MIN_HYPERFRAMES_VIDEO_BYTES = 15_000
MIN_VISUAL_VIDEO_BYTES = MIN_STOCK_VIDEO_BYTES


def _min_video_bytes_for_path(path: Path) -> int:
    name = path.name.lower()
    if name.startswith("action-slot-"):
        return MIN_HYPERFRAMES_VIDEO_BYTES
    if "-stock" in name or name.endswith("-reuse.mp4"):
        return MIN_STOCK_VIDEO_BYTES
    return MIN_STOCK_VIDEO_BYTES


def _is_valid_visual_artifact(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size <= 0:
        return False
    if path.suffix.lower() in {".mp4", ".webm", ".mov", ".mkv"}:
        return path.stat().st_size >= _min_video_bytes_for_path(path)
    return True


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
        if slot_id == MASTER_TTS_SLOT_ID:
            from app.pipelines.tts_mode import MASTER_TTS_WAV_NAME

            return generated_root / MASTER_TTS_WAV_NAME
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


def _visual_artifact_path(result_or_action: dict[str, Any], generated_root: Path | None = None) -> Path | None:
    artifact_ref = result_or_action.get("artifactRef")
    if isinstance(artifact_ref, dict):
        uri = str(artifact_ref.get("uri", "")).strip()
        if uri:
            path = Path(uri)
            if path.is_file() and _is_valid_visual_artifact(path):
                return path
    if generated_root is not None and "slotId" in result_or_action:
        output = expected_output_path(result_or_action, generated_root)
        if _is_valid_visual_artifact(output):
            return output
    return None


def _hyperframes_composition_dir(action: dict[str, Any], generated_root: Path) -> Path | None:
    action_id = str(action.get("id") or "")
    if not action_id:
        return None
    candidate = generated_root / action_id / "composition"
    return candidate if candidate.is_dir() else None


def _composition_needs_tailwind_rebuild(action: dict[str, Any], generated_root: Path) -> bool:
    provider = str(action.get("provider") or action.get("strategy") or "")
    if provider != "hyperframes_material":
        return False
    composition_dir = _hyperframes_composition_dir(action, generated_root)
    if composition_dir is None:
        return False
    index_path = composition_dir / "index.html"
    if not index_path.is_file():
        return False
    html = index_path.read_text(encoding="utf-8")
    from composition.build.tailwind_runtime import html_uses_tailwind_classes

    return html_uses_tailwind_classes(html) and "window.__tailwindReady" not in html


def action_artifact_satisfied(action: dict[str, Any], generated_root: Path) -> bool:
    if _composition_needs_tailwind_rebuild(action, generated_root):
        return False
    path = _visual_artifact_path(action, generated_root)
    if path is None:
        return False
    return _is_valid_visual_artifact(path)


def material_action_done(action: dict[str, Any], generated_root: Path) -> bool:
    """True when the action output already exists on disk (resume-safe)."""
    return action_artifact_satisfied(action, generated_root)


def action_needs_plan_material_sync(action: dict[str, Any], generated_root: Path) -> bool:
    """True when a usable disk output exists but the plan action lacks artifactRef."""
    usable = _visual_artifact_path(action, generated_root)
    if usable is None:
        return False
    artifact_ref = action.get("artifactRef")
    if isinstance(artifact_ref, dict) and str(artifact_ref.get("uri", "")).strip():
        existing = Path(str(artifact_ref["uri"]))
        if (
            existing.is_file()
            and _is_valid_visual_artifact(existing)
            and existing.resolve() == usable.resolve()
        ):
            return False
    return True


def synthesize_material_results_from_disk(
    actions: list[dict[str, Any]],
    *,
    generated_root: Path,
) -> list[MaterialResult]:
    """Rebuild MaterialResult rows for completed actions missing plan artifactRef."""
    from datetime import datetime, timezone

    results: list[MaterialResult] = []
    for action in actions:
        if not action_needs_plan_material_sync(action, generated_root):
            continue
        output = expected_output_path(action, generated_root)
        if not _is_valid_visual_artifact(output):
            continue
        action_id = str(action.get("id") or "")
        slot_id = str(action.get("slotId") or "")
        provider = str(action.get("provider") or action.get("strategy") or "")
        suffix = output.suffix.lower()
        artifact_type = "video" if suffix in {".mp4", ".webm", ".mov", ".mkv"} else "image"
        results.append(
            {
                "ok": True,
                "actionId": action_id,
                "slotId": slot_id,
                "provider": provider,
                "artifactRef": {
                    "id": action_id or slot_id,
                    "type": artifact_type,
                    "uri": str(output.resolve()),
                    "createdAt": datetime.now(timezone.utc)
                    .isoformat()
                    .replace("+00:00", "Z"),
                },
            }
        )
    return results


def _visual_result_priority(result: MaterialResult) -> tuple[int, int, int]:
    action_id = str(result.get("actionId") or "")
    score = 0
    artifact = result.get("artifactRef") or {}
    uri = str(artifact.get("uri", "")).strip()
    path = Path(uri) if uri else None
    size = path.stat().st_size if path is not None and path.is_file() else 0
    min_bytes = _min_video_bytes_for_path(path) if path is not None else MIN_STOCK_VIDEO_BYTES
    if size >= min_bytes:
        score += 20
    elif size > 0:
        score -= 50
    if action_id.endswith("-finish") and size >= min_bytes:
        score += 10
    elif str(artifact.get("uri", "")).strip():
        score += 5
    return (score, size, len(action_id))


def _prefer_visual_result(candidate: MaterialResult, current: MaterialResult | None) -> bool:
    if current is None:
        return True
    return _visual_result_priority(candidate) > _visual_result_priority(current)


def _persist_material_state(ctx: MaterialContext) -> None:
    if ctx.material_state_path is None:
        return
    save_material_state(
        ctx.material_state_path,
        quota=ctx.quota,
        completed_action_ids=ctx.completed_action_ids,
    )


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

    def sort_key(action: dict[str, Any]) -> tuple[int, str, int]:
        slot_id = str(action.get("slotId", ""))
        importance = importance_by_slot.get(slot_id, "nice_to_have")
        action_id = str(action.get("id") or "")
        chain_rank = 0
        if action_id.endswith("-finish") or action_id.endswith("-ken-burns"):
            chain_rank = 99
        elif "-chain-" in action_id:
            try:
                chain_rank = int(action_id.rsplit("-chain-", 1)[-1])
            except ValueError:
                chain_rank = 50
        return (0 if importance == "must_have" else 1, slot_id, chain_rank)

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
        if material_action_done(action, ctx.generated_root):
            ctx.completed_action_ids.add(action_id)
            _persist_material_state(ctx)
            disk_results = synthesize_material_results_from_disk([action], generated_root=ctx.generated_root)
            if disk_results:
                results.extend(disk_results)
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
        _persist_material_state(ctx)
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


def _voiceover_end_sec(
    *,
    start_sec: float,
    storyboard_end_sec: float,
    wav_path: Path | None,
    clamp_to_storyboard: bool = True,
) -> float:
    """Resolve voiceover clip end from wav length and optional storyboard clamp."""
    if wav_path is not None and wav_path.is_file():
        duration = wav_duration_sec(wav_path)
        if duration is not None and duration > 0:
            wav_end = start_sec + duration
            if clamp_to_storyboard:
                return max(start_sec, min(storyboard_end_sec, wav_end))
            return wav_end
    if clamp_to_storyboard:
        return max(start_sec, storyboard_end_sec)
    return start_sec


def _merge_material_results(
    primary: list[MaterialResult],
    supplemental: list[MaterialResult],
) -> list[MaterialResult]:
    merged: dict[str, MaterialResult] = {}
    for result in primary + supplemental:
        action_id = str(result.get("actionId") or "")
        if not action_id:
            continue
        merged[action_id] = result
    return list(merged.values())


def _collect_visual_results(
    results: list[MaterialResult],
    *,
    actions: list[dict[str, Any]],
    generated_root: Path | None,
) -> list[MaterialResult]:
    merged = _merge_material_results(
        results,
        synthesize_material_results_from_disk(actions, generated_root=generated_root)
        if generated_root is not None
        else [],
    )
    visual_by_slot: dict[str, MaterialResult] = {}
    ordered: list[MaterialResult] = []
    for result in merged:
        if not result.get("ok") or not result.get("slotId"):
            continue
        provider = str(result.get("provider", ""))
        if provider == "tts":
            ordered.append(result)
            continue
        if provider not in VISUAL_MATERIAL_PROVIDERS:
            continue
        slot_id = str(result["slotId"])
        if _prefer_visual_result(result, visual_by_slot.get(slot_id)):
            visual_by_slot[slot_id] = result
    for result in merged:
        if result in ordered or str(result.get("provider", "")) in VISUAL_MATERIAL_PROVIDERS:
            if result not in ordered and result.get("actionId") not in {
                str(item.get("actionId")) for item in visual_by_slot.values()
            }:
                if str(result.get("provider", "")) not in VISUAL_MATERIAL_PROVIDERS:
                    ordered.append(result)
    # Return all results but timeline uses visual_by_slot built from merged list
    return merged


def apply_material_results_to_plan(
    plan: dict[str, Any],
    *,
    results: list[MaterialResult],
    render_root: Path | None = None,
    generated_root: Path | None = None,
) -> dict[str, Any]:
    actions = [
        action for action in plan.get("completionActions", []) if isinstance(action, dict)
    ]
    merged_results = _collect_visual_results(
        results,
        actions=actions,
        generated_root=generated_root,
    )
    results_by_action = {
        str(item.get("actionId")): item for item in merged_results if item.get("actionId")
    }
    visual_by_slot: dict[str, MaterialResult] = {}
    tts_by_slot: dict[str, MaterialResult] = {}
    for result in merged_results:
        if not result.get("ok") or not result.get("slotId"):
            continue
        slot_id = str(result["slotId"])
        provider = str(result.get("provider", ""))
        if provider == "tts":
            tts_by_slot[slot_id] = result
        elif provider in VISUAL_MATERIAL_PROVIDERS:
            if _prefer_visual_result(result, visual_by_slot.get(slot_id)):
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

    tts_mode = str(plan.get("ttsMode") or resolve_tts_mode(plan))
    plan["timeline"] = _apply_generated_sources_to_timeline(
        plan.get("timeline", {}),
        results=merged_results,
        render_root=render_root,
        storyboard=plan.get("storyboard", []),
        tts_mode=tts_mode,
    )
    plan = sync_timeline_to_narration(plan, render_root=render_root)
    packaging = plan.get("packagingPlan") if isinstance(plan.get("packagingPlan"), dict) else {}
    plan["timeline"] = align_subtitles_to_voiceover(
        plan.get("timeline", {}),
        list(plan.get("storyboard", [])),
        packaging,
        render_root=render_root,
        master_narration=str(plan.get("masterNarration") or ""),
        tts_mode=tts_mode,
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
    if path.is_file():
        source_size = path.stat().st_size
        if not dest.is_file() or dest.stat().st_size < source_size:
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
    tts_mode: str | None = None,
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
            if _prefer_visual_result(result, visual_by_slot.get(slot_id)):
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

    global_mode = is_global_tts_mode(tts_mode)
    if global_mode:
        vo_clips[:] = [
            clip
            for clip in vo_clips
            if isinstance(clip, dict) and not str(clip.get("id", "")).startswith("vo-")
        ]
        vo_by_id = {
            str(clip.get("id", "")): clip
            for clip in vo_clips
            if isinstance(clip, dict)
        }

    for slot_id, result in tts_by_slot.items():
        if slot_id != MASTER_TTS_SLOT_ID:
            continue
        artifact = result.get("artifactRef") or {}
        uri = str(artifact.get("uri", "")).strip()
        if not uri:
            continue
        source_ref = _material_source_ref(uri, render_root=render_root)
        wav_path: Path | None = None
        if render_root is not None:
            material_candidate = render_root / source_ref
            if material_candidate.is_file():
                wav_path = material_candidate
        if wav_path is None:
            uri_path = Path(uri)
            if uri_path.is_file():
                wav_path = uri_path

        start_sec = 0.0
        storyboard_end_sec = 0.0
        end_sec = _voiceover_end_sec(
            start_sec=start_sec,
            storyboard_end_sec=storyboard_end_sec,
            wav_path=wav_path,
            clamp_to_storyboard=False,
        )
        vo_id = VO_MASTER_CLIP_ID

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
