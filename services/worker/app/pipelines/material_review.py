from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.agents.material_reviewer import load_prompt, run_material_reviewer
from app.agents.runner import AgentRunner
from app.gateway.model_gateway import ModelGateway
from app.observability.material_review_recorder import (
    MaterialReviewLlmSession,
    acp_parent_observability_run_id,
    build_material_review_trace,
    read_last_model_call_id,
    resolve_material_reviewer_prompt_version,
    set_material_review_slot_context,
)
from app.pipelines.revise_material_edit import (
    SlotChainKind,
    classify_slot_material_chain,
)
from app.providers.base_media_resolver import is_finish_action
from app.runtime.task_context import TaskContext
from app.tools.ffmpeg_tool import FFmpegTool
from app.tools.llm_tool import LLMToolConfigError, LLMToolValidationError
from app.validation.schema_loader import validate_contract

MaterialReviewRoute = Literal["video", "vision", "text_only"]
BeatSource = Literal["spec_timeline", "spec_html", "ratio_fill"]

logger = logging.getLogger(__name__)

_TIMELINE_NUM_RE = re.compile(r"tl\.(?:to|from|set)\(\s*([0-9]+(?:\.[0-9]+)?)")
_DATA_START_RE = re.compile(r'data-start="([0-9.]+)"', re.IGNORECASE)
_DATA_DURATION_RE = re.compile(r'data-duration="([0-9.]+)"', re.IGNORECASE)
_RATIO_FILL = [0.05, 0.35, 0.65, 0.95]


def preview_content_hash(preview_path: Path) -> str:
    return hashlib.sha256(preview_path.read_bytes()).hexdigest()


def material_spec_content_hash(spec: dict[str, Any]) -> str:
    from composition.material_review.session import material_spec_content_hash as _hash

    return _hash(spec)


def enrich_material_review_report(
    report: dict[str, Any],
    *,
    spec: dict[str, Any],
    preview_path: Path,
) -> dict[str, Any]:
    enriched = dict(report)
    enriched["specHash"] = material_spec_content_hash(spec)
    if preview_path.is_file():
        enriched["previewSha256"] = preview_content_hash(preview_path)
    return enriched


def report_matches_review_artifacts(
    report: dict[str, Any],
    *,
    spec: dict[str, Any],
    preview_path: Path,
) -> bool:
    if not report.get("approved"):
        return False
    if str(report.get("specHash") or "") != material_spec_content_hash(spec):
        return False
    stored_preview = str(report.get("previewSha256") or "")
    if stored_preview and preview_path.is_file():
        return stored_preview == preview_content_hash(preview_path)
    return bool(stored_preview or str(report.get("specHash") or ""))


def material_review_enabled() -> bool:
    from material_review_revise_context import material_review_enabled as _enabled

    return _enabled()


def material_review_on_revise_enabled() -> bool:
    from material_review_revise_context import material_review_on_revise_enabled as _enabled

    return _enabled()


def use_material_review_gate(
    *,
    human_review: bool,
    revise_context: Any | None,
) -> bool:
    if not material_review_enabled():
        return False
    if human_review:
        return True
    if not material_review_on_revise_enabled() or revise_context is None:
        return False
    if str(getattr(revise_context, "material_scope", "") or "") == "none":
        return False
    stages = getattr(revise_context, "affected_pipeline_stages", None) or []
    return "generating_material" in stages


def material_review_max_rounds() -> int:
    raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_MAX_ROUNDS", "1").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


def material_review_repair_followup_max() -> int:
    raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_REPAIR_FOLLOWUP_MAX", "1").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 1


def material_review_acp_in_session_enabled(*, revise: bool = False) -> bool:
    """Worker post-turn vision for ACP author (first generation vs revise paths)."""
    if revise:
        raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION_REVISE", "true").strip().lower()
    else:
        raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_ACP_IN_SESSION", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def material_review_gate_llm_enabled() -> bool:
    """Run material_reviewer LLM at gate finalize when no in-session marker exists."""
    raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_GATE_LLM", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def load_gate_author_payload(
    generation_root: Path,
    slot_id: str,
    *,
    slot_timing: dict[str, Any] | None,
    project_id: str,
    generation_id: str,
) -> dict[str, Any]:
    scratch = generation_root / "acp-author" / slot_id
    task_path = scratch / "task.json"
    if task_path.is_file():
        try:
            payload = json.loads(task_path.read_text(encoding="utf-8"))
            if isinstance(payload, dict):
                payload.setdefault("projectId", project_id)
                payload.setdefault("generationId", generation_id)
                payload.setdefault("slotId", slot_id)
                if slot_timing and not payload.get("slotTiming"):
                    payload["slotTiming"] = slot_timing
                return payload
        except (OSError, json.JSONDecodeError):
            pass

    payload: dict[str, Any] = {
        "slotId": slot_id,
        "projectId": project_id,
        "generationId": generation_id,
    }
    if slot_timing:
        payload["slotTiming"] = slot_timing

    revise_path = generation_root / "revise-context.json"
    if revise_path.is_file():
        try:
            revise_context = json.loads(revise_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            revise_context = None
        if isinstance(revise_context, dict):
            payload["reviseContext"] = revise_context
            gate = revise_context.get("materialGateRevise")
            if isinstance(gate, dict):
                payload["materialGateRevise"] = gate
                contract = gate.get("authorContract")
                if isinstance(contract, dict):
                    payload["authorContract"] = contract
                edit = gate.get("editInstruction")
                if edit and not payload.get("editInstruction"):
                    payload["editInstruction"] = edit
    return payload


def material_review_max_frames() -> int:
    raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_MAX_FRAMES", "4").strip()
    try:
        return max(1, min(8, int(raw)))
    except ValueError:
        return 4


def material_review_video_max_sec() -> float:
    raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_VIDEO_MAX_SEC", "30").strip()
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 30.0


def material_review_video_max_mb() -> float:
    raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_VIDEO_MAX_MB", "50").strip()
    try:
        return max(1.0, float(raw))
    except ValueError:
        return 50.0


def material_preview_profile() -> str:
    raw = os.getenv("VIDEOMAKER_MATERIAL_PREVIEW_PROFILE", "full").strip().lower()
    return raw if raw in {"full", "fast"} else "full"


def material_review_provider_allowlist() -> set[str]:
    raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_PROVIDERS", "hyperframes_material").strip()
    return {item.strip() for item in raw.split(",") if item.strip()}


def slot_needs_agent_review(
    action: dict[str, Any],
    *,
    slot_chain: SlotChainKind,
    completion_actions: list[dict[str, Any]] | None = None,
) -> bool:
    provider = str(action.get("provider") or action.get("strategy") or "")
    if provider not in material_review_provider_allowlist():
        return False
    if provider != "hyperframes_material":
        return False
    if slot_chain in {
        SlotChainKind.HF_ONLY,
        SlotChainKind.STOCK_THEN_HF,
        SlotChainKind.REUSE_THEN_HF,
        SlotChainKind.IMAGE_THEN_HF,
    }:
        return True
    action_id = str(action.get("id") or "")
    if is_finish_action(action_id):
        return True
    if completion_actions is not None:
        slot_id = str(action.get("slotId") or "")
        chain = classify_slot_material_chain(completion_actions, slot_id)
        return slot_needs_agent_review(action, slot_chain=chain)
    return False


def extract_spec_review_beats(spec: dict[str, Any]) -> list[tuple[float, BeatSource]]:
    beats: list[tuple[float, BeatSource]] = []
    composition = spec.get("composition")
    if not isinstance(composition, dict):
        return beats
    timeline = composition.get("timelineScript")
    if isinstance(timeline, str):
        for match in _TIMELINE_NUM_RE.finditer(timeline):
            beats.append((float(match.group(1)), "spec_timeline"))
    body_html = composition.get("bodyHtml")
    if isinstance(body_html, str):
        for match in _DATA_START_RE.finditer(body_html):
            start = float(match.group(1))
            beats.append((start, "spec_html"))
            duration_match = _DATA_DURATION_RE.search(body_html[match.start() : match.start() + 120])
            if duration_match:
                beats.append((start + float(duration_match.group(1)) * 0.5, "spec_html"))
    duration = float(spec.get("durationSec") or 0.0)
    if duration > 0:
        normalized = []
        seen: set[float] = set()
        for value, source in beats:
            clamped = min(max(0.0, value), max(0.0, duration - 0.04))
            key = round(clamped, 2)
            if key in seen:
                continue
            seen.add(key)
            normalized.append((clamped, source))
        return normalized
    return beats


def sample_review_timestamps(
    duration_sec: float,
    spec_beats: list[tuple[float, BeatSource]],
    *,
    max_frames: int | None = None,
) -> list[tuple[float, BeatSource]]:
    cap = max_frames or material_review_max_frames()
    if duration_sec <= 0.5:
        return [(max(0.0, duration_sec * 0.5), "ratio_fill")]
    selected: list[tuple[float, BeatSource]] = list(spec_beats)
    for ratio in _RATIO_FILL:
        if len(selected) >= cap:
            break
        selected.append((min(duration_sec - 0.04, max(0.0, duration_sec * ratio)), "ratio_fill"))
    selected.sort(key=lambda item: item[0])
    merged: list[tuple[float, BeatSource]] = []
    for timestamp, source in selected:
        if merged and abs(timestamp - merged[-1][0]) < 0.3:
            continue
        merged.append((timestamp, source))
        if len(merged) >= cap:
            break
    return merged


def _resolve_material_review_route_with_reason(
    *,
    store: Any | None,
    preview_path: Path,
    size_mb: float,
    duration: float,
) -> tuple[MaterialReviewRoute, str]:
    if store is None:
        return "text_only", "store_missing"

    status = store.get_status()
    providers = status.get("providers") if isinstance(status, dict) else {}
    video = providers.get("videoUnderstanding") if isinstance(providers, dict) else {}
    vision = providers.get("vision") if isinstance(providers, dict) else {}

    video_ready = (
        isinstance(video, dict)
        and video.get("configured")
        and video.get("hasApiKey")
    )
    vision_ready = (
        isinstance(vision, dict)
        and vision.get("configured")
        and vision.get("hasApiKey")
    )

    if (
        video_ready
        and duration > 0
        and duration <= material_review_video_max_sec()
        and size_mb <= material_review_video_max_mb()
    ):
        return "video", "video_understanding_ready"

    if vision_ready:
        if not video_ready:
            if not isinstance(video, dict) or not video.get("configured"):
                return "vision", "video_understanding_not_configured"
            return "vision", "video_understanding_missing_api_key"
        if duration <= 0:
            return "vision", "preview_duration_zero"
        if duration > material_review_video_max_sec():
            return "vision", f"video_duration_exceeds_max:{duration:.1f}s"
        if size_mb > material_review_video_max_mb():
            return "vision", f"video_size_exceeds_max:{size_mb:.1f}mb"
        return "vision", "video_understanding_unavailable"

    if not video_ready and not vision_ready:
        return "text_only", "no_multimodal_provider_configured"
    if not video_ready:
        return "text_only", "video_understanding_not_configured"
    if not video.get("hasApiKey"):
        return "text_only", "video_understanding_missing_api_key"
    if duration <= 0:
        return "text_only", "preview_duration_zero"
    if duration > material_review_video_max_sec():
        return "text_only", f"video_duration_exceeds_max:{duration:.1f}s"
    if size_mb > material_review_video_max_mb():
        return "text_only", f"video_size_exceeds_max:{size_mb:.1f}mb"
    return "text_only", "vision_not_configured"


def resolve_material_review_route(
    *,
    store: Any | None,
    preview_path: Path,
) -> MaterialReviewRoute:
    if not preview_path.is_file():
        logger.info(
            "material_review_route=text_only reason=preview_missing preview=%s",
            preview_path,
        )
        return "text_only"

    size_mb = preview_path.stat().st_size / (1024 * 1024)
    ffmpeg = FFmpegTool()
    probe = ffmpeg.probe(preview_path)
    duration = float(probe.get("durationSec") or 0.0) if isinstance(probe, dict) else 0.0
    route, reason = _resolve_material_review_route_with_reason(
        store=store,
        preview_path=preview_path,
        size_mb=size_mb,
        duration=duration,
    )
    if route == "text_only":
        logger.info(
            "material_review_route=text_only reason=%s preview=%s duration_sec=%.2f size_mb=%.2f",
            reason,
            preview_path,
            duration,
            size_mb,
        )
    return route


def check_preview_hard_gates(
    preview_path: Path,
    *,
    expected_duration_sec: float | None,
) -> list[str]:
    errors: list[str] = []
    if not preview_path.is_file() or preview_path.stat().st_size <= 0:
        errors.append("preview_missing_or_empty")
        return errors
    ffmpeg = FFmpegTool()
    probe = ffmpeg.probe(preview_path)
    if not isinstance(probe, dict) or probe.get("code"):
        errors.append("preview_probe_failed")
        return errors
    duration = float(probe.get("durationSec") or 0.0)
    if expected_duration_sec and expected_duration_sec > 0:
        delta = abs(duration - expected_duration_sec) / expected_duration_sec
        if delta > 0.15:
            errors.append(f"preview_duration_drift:{duration:.2f}s vs {expected_duration_sec:.2f}s")
    return errors


def build_repair_feedback(report: dict[str, Any]) -> str:
    suggestions = [str(item) for item in report.get("suggestions") or [] if str(item).strip()]
    issues = [str(item) for item in report.get("issues") or [] if str(item).strip()]
    parts = []
    if suggestions:
        parts.append("Apply these review fixes: " + "; ".join(suggestions))
    if issues:
        parts.append("Issues: " + "; ".join(issues))
    return " ".join(parts).strip()


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _encode_frame(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "timeSec": 0.0,
        "imageBase64": base64.b64encode(data).decode("ascii"),
        "mimeType": "image/jpeg",
        "path": str(path),
    }


def _build_text_payload(
    *,
    spec: dict[str, Any],
    author_payload: dict[str, Any],
    slot_id: str,
    frame_timestamps: list[float] | None = None,
    beat_sources: list[str] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "slotId": slot_id,
        "locale": str(author_payload.get("locale") or "zh"),
        "materialSpec": spec,
        "finishBrief": author_payload.get("finishBrief"),
        "compositionAuthorBrief": author_payload.get("compositionAuthorBrief"),
        "renderPolicy": author_payload.get("renderPolicy"),
        "slotTiming": author_payload.get("slotTiming"),
        "visualStyleBible": author_payload.get("visualStyleBible"),
    }
    if frame_timestamps:
        payload["frameTimestamps"] = frame_timestamps
    if beat_sources:
        payload["beatSources"] = beat_sources
    diagnostics = author_payload.get("baseVideoDiagnostics")
    if isinstance(diagnostics, dict) and diagnostics:
        payload["baseVideoDiagnostics"] = diagnostics
    return payload


_INFRA_BASE_VIDEO_MARKERS = (
    "底片",
    "基础视频",
    "base video",
    "base-video",
    "base media",
    "pure black",
    "纯黑",
    "不可见",
    "invisible",
    "black screen",
    "黑屏",
    "sparse keyframe",
    "seek",
)


def classify_review_rejection(
    report: dict[str, Any],
    *,
    diagnostics: dict[str, Any] | None,
) -> str:
    if report.get("approved", True):
        return "approved"
    if report.get("hardGateFailed"):
        return "creative"
    issues = [str(item).lower() for item in report.get("issues") or []]
    suggestions = [str(item).lower() for item in report.get("suggestions") or []]
    merged = " ".join(issues + suggestions)
    if not any(marker in merged for marker in _INFRA_BASE_VIDEO_MARKERS):
        return "creative"
    if isinstance(diagnostics, dict):
        interval = diagnostics.get("maxKeyframeIntervalSec")
        reencoded = diagnostics.get("reencoded")
        if reencoded is True:
            return "creative"
        if isinstance(interval, (int, float)) and float(interval) > 2.0:
            return "infrastructure"
    return "unknown"


def apply_infrastructure_review_waiver(
    report: dict[str, Any],
    *,
    author_payload: dict[str, Any],
) -> dict[str, Any]:
    diagnostics = author_payload.get("baseVideoDiagnostics")
    if not isinstance(diagnostics, dict):
        diagnostics = None
    classification = classify_review_rejection(report, diagnostics=diagnostics)
    if classification != "infrastructure":
        return report
    merged = dict(report)
    merged["approved"] = True
    merged["reviewUnavailable"] = True
    warnings = [str(item) for item in merged.get("warnings") or [] if str(item).strip()]
    warnings.append(
        "Review waived infrastructure base-video seek artifact; fix upstream encoding or re-run after normalize."
    )
    merged["warnings"] = warnings
    merged.setdefault("trace", {})
    if isinstance(merged["trace"], dict):
        merged["trace"]["reviewClassification"] = classification
    return merged


def _extract_review_frames(
    preview_path: Path,
    spec: dict[str, Any],
    frames_dir: Path,
    ffmpeg: FFmpegTool,
) -> tuple[list[dict[str, Any]], list[str], list[float], list[str]]:
    probe = ffmpeg.probe(preview_path)
    duration = float(probe.get("durationSec") or spec.get("durationSec") or 1.0)
    spec_beats = extract_spec_review_beats(spec)
    sampled = sample_review_timestamps(duration, spec_beats)
    frames_dir.mkdir(parents=True, exist_ok=True)
    encoded: list[dict[str, Any]] = []
    frame_paths: list[str] = []
    timestamps: list[float] = []
    beat_sources: list[str] = []
    for index, (timestamp, source) in enumerate(sampled):
        output = frames_dir / f"frame-{index}-{int(timestamp * 1000)}.jpg"
        result = ffmpeg.extract_frame_at(preview_path, output, time_sec=timestamp)
        if not isinstance(result, dict) or result.get("code"):
            continue
        encoded_frame = _encode_frame(output)
        encoded_frame["timeSec"] = timestamp
        encoded.append(encoded_frame)
        frame_paths.append(str(output))
        timestamps.append(timestamp)
        beat_sources.append(source)
    return encoded, frame_paths, timestamps, beat_sources


def _merge_reviewer_output(
    *,
    output: dict[str, Any],
    slot_id: str,
    generation_id: str,
    route: MaterialReviewRoute,
    review_inputs: dict[str, Any],
    provider: str,
    agent_review_round: int,
    trace: dict[str, Any] | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "slotId": slot_id,
        "generationId": generation_id,
        "reviewedAt": _utc_now_iso(),
        "approved": bool(output.get("approved")),
        "issues": list(output.get("issues") or []),
        "suggestions": list(output.get("suggestions") or []),
        "reviewInputs": {
            "mode": route if route != "vision" else "frames",
            **review_inputs,
        },
        "agentReviewRound": agent_review_round,
        "provider": provider,
    }
    scores = output.get("scores")
    if isinstance(scores, dict):
        report["scores"] = scores
    if trace:
        report["trace"] = trace
    return report


def run_slot_review(
    *,
    runner: AgentRunner | None,
    context: TaskContext | None,
    gateway: ModelGateway | None,
    store: Any | None,
    preview_path: Path,
    spec: dict[str, Any],
    author_payload: dict[str, Any],
    slot_id: str,
    generation_id: str,
    generation_root: Path | None = None,
    agent_review_round: int = 1,
    provider: str = "hyperframes_material",
    observability_sink: Any | None = None,
) -> dict[str, Any]:
    expected_duration = None
    slot_timing = author_payload.get("slotTiming")
    if isinstance(slot_timing, dict):
        expected_duration = float(slot_timing.get("durationSec") or 0.0) or None
    if expected_duration is None:
        expected_duration = float(spec.get("durationSec") or 0.0) or None

    hard_errors = check_preview_hard_gates(preview_path, expected_duration_sec=expected_duration)
    if hard_errors:
        return {
            "slotId": slot_id,
            "generationId": generation_id,
            "reviewedAt": _utc_now_iso(),
            "approved": False,
            "hardGateFailed": True,
            "issues": hard_errors,
            "suggestions": ["Fix preview render before creative review."],
            "reviewInputs": {"mode": "skipped"},
            "agentReviewRound": agent_review_round,
            "provider": provider,
            "trace": build_material_review_trace(route="hard_gate"),
        }

    set_material_review_slot_context(gateway, slot_id)
    project_id = str(context.project_id if context is not None else author_payload.get("projectId") or "")
    task_id = str(context.task_id if context is not None else author_payload.get("taskId") or "") or None
    if store is None:
        from app.pipelines.material_review_finalize import _resolve_gateway_store

        store = _resolve_gateway_store(
            gateway,
            context,
            generation_root=generation_root,
        )
    route = resolve_material_review_route(store=store, preview_path=preview_path)
    text_payload = _build_text_payload(
        spec=spec,
        author_payload=author_payload,
        slot_id=slot_id,
    )
    review_inputs: dict[str, Any] = {}
    trace: dict[str, Any] | None = None
    llm_session: MaterialReviewLlmSession | None = None
    if observability_sink is not None and route in {"video", "vision"}:
        llm_session = MaterialReviewLlmSession(
            sink=observability_sink,
            gateway=gateway,
            project_id=project_id,
            task_id=task_id,
            generation_id=generation_id,
            slot_id=slot_id,
            route=route,
            agent_review_round=agent_review_round,
            payload_keys=sorted(text_payload.keys()),
        )

    output: dict[str, Any]
    try:
        if route == "video" and gateway is not None:
            review_inputs["videoPath"] = str(preview_path)
            system_prompt = load_prompt()
            messages = ModelGateway.build_video_structure_messages(
                system_prompt=system_prompt,
                text_payload=text_payload,
                text_message={"task": "material_review", "slotId": slot_id},
                video_path=preview_path,
            )
            from app.observability.gateway_context import agent_observability_scope

            with agent_observability_scope(gateway, "material_reviewer"):
                output = gateway.complete_json_messages(messages, profile="video_understanding")
        elif route == "vision" and gateway is not None:
            frames_dir = (
                (generation_root / "material-reviews" / slot_id / "frames")
                if generation_root is not None
                else preview_path.parent / "review-frames"
            )
            encoded, frame_paths, timestamps, beat_sources = _extract_review_frames(
                preview_path,
                spec,
                frames_dir,
                FFmpegTool(),
            )
            review_inputs["framePaths"] = frame_paths
            review_inputs["frameTimestamps"] = timestamps
            review_inputs["beatSources"] = beat_sources
            text_payload = _build_text_payload(
                spec=spec,
                author_payload=author_payload,
                slot_id=slot_id,
                frame_timestamps=timestamps,
                beat_sources=beat_sources,
            )
            if llm_session is not None:
                llm_session.payload_keys = sorted(text_payload.keys())
            system_prompt = load_prompt()
            messages = ModelGateway.build_structure_messages(
                system_prompt=system_prompt,
                text_payload={"reviewPayload": text_payload},
                keyframes=encoded,
            )
            from app.observability.gateway_context import agent_observability_scope

            with agent_observability_scope(gateway, "material_reviewer"):
                output = gateway.complete_json_messages(messages, profile="vision")
        elif runner is not None and context is not None:
            review_inputs["mode"] = "text_only"
            output = run_material_reviewer(
                runner,
                review_payload=text_payload,
                context=context,
                generation_id=generation_id,
            )
            route = "text_only"
            trace = build_material_review_trace(
                route="text_only",
                model_call_id=read_last_model_call_id(gateway),
                agent_run_id=runner.last_agent_run_id,
                prompt_version=resolve_material_reviewer_prompt_version(),
                parent_observability_run_id=acp_parent_observability_run_id(),
            )
        else:
            output = {
                "approved": True,
                "issues": [],
                "suggestions": [],
            }
            route = "text_only"
            review_inputs["mode"] = "text_only"

        validation = validate_contract("material-reviewer-output", output)
        if not validation.valid:
            if llm_session is not None:
                trace = llm_session.fail([str(item) for item in validation.errors])
            raise LLMToolValidationError(
                "material reviewer output failed validation",
                raw_output=json.dumps(output, ensure_ascii=False),
                validation_errors=validation.errors,
            )
        if llm_session is not None:
            trace = llm_session.finish()
    except LLMToolValidationError:
        raise
    except Exception:
        if llm_session is not None:
            trace = llm_session.fail(["material_review_llm_failed"])
        raise

    report = _merge_reviewer_output(
        output=output,
        slot_id=slot_id,
        generation_id=generation_id,
        route=route,
        review_inputs=review_inputs,
        provider=provider,
        agent_review_round=agent_review_round,
        trace=trace,
    )
    report = apply_infrastructure_review_waiver(report, author_payload=author_payload)
    report_validation = validate_contract("material-review-report", report)
    if not report_validation.valid:
        raise LLMToolValidationError(
            "material review report failed validation",
            raw_output=json.dumps(report, ensure_ascii=False),
            validation_errors=report_validation.errors,
        )
    if generation_root is not None:
        report = enrich_material_review_report(report, spec=spec, preview_path=preview_path)
        report_dir = generation_root / "material-reviews" / slot_id
        report_dir.mkdir(parents=True, exist_ok=True)
        report_path = report_dir / "report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def build_skipped_review_report(
    *,
    slot_id: str,
    generation_id: str,
    provider: str,
    approved: bool = True,
) -> dict[str, Any]:
    return {
        "slotId": slot_id,
        "generationId": generation_id,
        "reviewedAt": _utc_now_iso(),
        "approved": approved,
        "issues": [],
        "suggestions": [],
        "reviewInputs": {"mode": "skipped"},
        "provider": provider,
        "trace": build_material_review_trace(route="skipped"),
    }


def build_failed_review_report(
    *,
    slot_id: str,
    generation_id: str,
    provider: str,
    error_message: str,
    route: MaterialReviewRoute = "text_only",
    gateway: ModelGateway | None = None,
    agent_review_round: int = 1,
) -> dict[str, Any]:
    review_mode = "frames" if route == "vision" else route
    if review_mode not in {"video", "frames", "text_only"}:
        review_mode = "text_only"
    review_unavailable = is_review_infrastructure_error(error_message)
    report: dict[str, Any] = {
        "slotId": slot_id,
        "generationId": generation_id,
        "reviewedAt": _utc_now_iso(),
        "approved": False,
        "issues": [error_message],
        "suggestions": [
            "Preview is ready for manual review; retry agent review later if needed."
            if review_unavailable
            else "Retry material review after fixing the underlying error."
        ],
        "reviewInputs": {"mode": review_mode},
        "agentReviewRound": agent_review_round,
        "provider": provider,
        "trace": build_material_review_trace(
            route=route,
            model_call_id=read_last_model_call_id(gateway),
            prompt_version=resolve_material_reviewer_prompt_version(),
            parent_observability_run_id=acp_parent_observability_run_id(),
        ),
    }
    if review_unavailable:
        report["reviewUnavailable"] = True
        report["approved"] = True
        report["issues"] = []
    return report


def is_review_infrastructure_error(error_message: str) -> bool:
    lowered = str(error_message or "").lower()
    markers = (
        "429",
        "503",
        "502",
        "504",
        "setlimitexceeded",
        "toomanyrequests",
        "rate limit",
        "timeout",
        "connection reset",
        "connection closed",
        "llmtoolconfigerror",
        "no modelgateway",
        "gatewayerror",
        "invalid agentrunlog",
        "tokenusage",
    )
    return any(marker in lowered for marker in markers)
