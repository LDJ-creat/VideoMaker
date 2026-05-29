from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any

from app.agents.content_strategist import run_content_strategist
from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext
from app.tools.opencv_tool import OpenCVTool
from app.validation.schema_loader import validate_contract

VISION_AGENT_NAME = "asset_moment_vision"
VISION_TASK_KEY = "asset_moment_vision"
TOP_MOMENT_COUNT = 5
VISION_MOMENT_COUNT = 3
VALID_SEGMENT_ROLES = {"hook", "mid", "cta"}


def normalize_score(value: float, minimum: float, maximum: float) -> float:
    if maximum == minimum:
        return 1.0
    scaled = (value - minimum) / (maximum - minimum)
    return max(0.0, min(1.0, scaled))


def compute_highlight_score(
    *,
    motion_score: float,
    sharpness_score: float,
    center_subject_score: float,
) -> float:
    score = 0.4 * motion_score + 0.3 * sharpness_score + 0.3 * center_subject_score
    return round(max(0.0, min(1.0, score)), 4)


def moment_id(asset_id: str, start_sec: float, end_sec: float) -> str:
    start_ms = int(round(start_sec * 1000))
    end_ms = int(round(end_sec * 1000))
    return f"moment-{asset_id}-{start_ms}-{end_ms}"


def score_shot_moment(
    shot: dict[str, Any],
    *,
    frame_metrics: dict[str, float] | None = None,
) -> float:
    if frame_metrics is not None:
        return compute_highlight_score(
            motion_score=float(frame_metrics.get("motionScore", 0.5)),
            sharpness_score=float(frame_metrics.get("sharpnessScore", 0.5)),
            center_subject_score=float(frame_metrics.get("centerSubjectScore", 0.5)),
        )

    confidence = float(shot.get("confidence", 0.5))
    confidence = max(0.0, min(1.0, confidence))
    return compute_highlight_score(
        motion_score=confidence,
        sharpness_score=0.45 + confidence * 0.1,
        center_subject_score=0.5,
    )


def _resolve_asset_path(storage_root: Path, project_id: str, uri: str) -> Path | None:
    candidate = Path(uri)
    if candidate.is_file():
        return candidate.resolve()

    if uri.startswith("storage://"):
        candidate = storage_root / uri.removeprefix("storage://")
    elif uri.startswith("projects/"):
        candidate = storage_root / uri
    else:
        candidate = storage_root / "projects" / project_id / uri

    return candidate.resolve() if candidate.is_file() else None


def _load_asset_shots(
    storage_root: Path,
    project_id: str,
    asset_id: str,
    *,
    video_path: Path | None,
    duration_sec: float,
    opencv: OpenCVTool,
) -> list[dict[str, Any]]:
    analysis_root = storage_root / "projects" / project_id / "assets" / asset_id / "analysis"
    for filename in ("shots.json", "asset-analysis.json"):
        analysis_path = analysis_root / filename
        if not analysis_path.is_file():
            continue
        payload = json.loads(analysis_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
        shots = payload.get("shots")
        if isinstance(shots, list) and shots:
            return shots

    if video_path is not None:
        result = opencv.detect_shots(video_path, duration_sec=duration_sec)
        shots = result.get("shots", [])
        if shots:
            return shots

    return [
        {
            "startSec": 0.0,
            "endSec": max(0.1, duration_sec),
            "confidence": 0.4,
            "changeReason": "unknown",
        }
    ]


def _load_asset_transcript(
    storage_root: Path,
    project_id: str,
    asset_id: str,
) -> list[dict[str, Any]]:
    analysis_root = storage_root / "projects" / project_id / "assets" / asset_id / "analysis"
    for filename in ("asset-analysis.json", "transcript.json"):
        analysis_path = analysis_root / filename
        if not analysis_path.is_file():
            continue
        payload = json.loads(analysis_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
        transcript = payload.get("transcript")
        if isinstance(transcript, list):
            return transcript
    return []


def _transcript_snippet(
    transcript: list[dict[str, Any]],
    *,
    start_sec: float,
    end_sec: float,
) -> str:
    snippets: list[str] = []
    for segment in transcript:
        if not isinstance(segment, dict):
            continue
        seg_start = float(segment.get("startSec", 0.0))
        seg_end = float(segment.get("endSec", 0.0))
        if seg_end < start_sec or seg_start > end_sec:
            continue
        text = str(segment.get("text", "")).strip()
        if text:
            snippets.append(text)
    return " ".join(snippets)


class _VideoFrameReader:
    def __init__(self, video_path: Path, cv2: Any) -> None:
        self._cv2 = cv2
        self._capture = cv2.VideoCapture(str(video_path))
        self._opened = self._capture.isOpened()

    def read_at(self, time_sec: float) -> Any | None:
        if not self._opened:
            return None
        self._capture.set(self._cv2.CAP_PROP_POS_MSEC, max(0.0, time_sec * 1000.0))
        success, frame = self._capture.read()
        return frame if success else None

    def read_pair(self, time_sec: float, *, delta_sec: float = 0.1) -> tuple[Any | None, Any | None]:
        prev_frame = self.read_at(max(0.0, time_sec - delta_sec))
        current_frame = self.read_at(time_sec)
        return prev_frame, current_frame

    def close(self) -> None:
        if self._opened:
            self._capture.release()

    def __enter__(self) -> _VideoFrameReader:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()


def _analyze_frame_metrics(frame: Any, *, prev_frame: Any | None, cv2: Any) -> dict[str, float]:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
    sharpness = float(laplacian.var())
    sharpness_score = min(1.0, sharpness / 500.0)

    height, width = gray.shape[:2]
    center = gray[height // 4 : 3 * height // 4, width // 4 : 3 * width // 4]
    center_var = float(center.var())
    total_var = float(gray.var()) or 1.0
    center_subject_score = min(1.0, center_var / total_var)

    motion_score = 0.5
    if prev_frame is not None:
        prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
        diff = cv2.absdiff(gray, prev_gray)
        motion_score = min(1.0, float(diff.mean()) / 64.0)

    return {
        "motionScore": round(motion_score, 4),
        "sharpnessScore": round(sharpness_score, 4),
        "centerSubjectScore": round(center_subject_score, 4),
    }


def _frame_metrics_for_shot(
    reader: _VideoFrameReader | None,
    shot: dict[str, Any],
    *,
    opencv: OpenCVTool,
) -> dict[str, float] | None:
    if reader is None or opencv.cv2 is None:
        return None

    start_sec = float(shot.get("startSec", 0.0))
    end_sec = float(shot.get("endSec", start_sec + 0.1))
    midpoint = start_sec + max(0.0, end_sec - start_sec) / 2.0
    prev_frame, frame = reader.read_pair(midpoint)
    if frame is None:
        return None
    return _analyze_frame_metrics(frame, prev_frame=prev_frame, cv2=opencv.cv2)


def _encode_frame_base64(frame: Any, opencv: OpenCVTool) -> str | None:
    if opencv.cv2 is None:
        return None
    ok, encoded = opencv.cv2.imencode(".jpg", frame, [int(opencv.cv2.IMWRITE_JPEG_QUALITY), 85])
    if not ok:
        return None
    return base64.b64encode(encoded.tobytes()).decode("ascii")


def _build_video_candidate_moments(
    *,
    asset: dict[str, Any],
    shots: list[dict[str, Any]],
    video_path: Path | None,
    transcript: list[dict[str, Any]],
    opencv: OpenCVTool,
) -> list[dict[str, Any]]:
    scored: list[dict[str, Any]] = []
    reader: _VideoFrameReader | None = None
    if video_path is not None and opencv.cv2 is not None:
        reader = _VideoFrameReader(video_path, opencv.cv2)

    try:
        for shot in shots:
            start_sec = float(shot.get("startSec", 0.0))
            end_sec = float(shot.get("endSec", start_sec + 0.1))
            frame_metrics = _frame_metrics_for_shot(reader, shot, opencv=opencv)
            highlight_score = score_shot_moment(shot, frame_metrics=frame_metrics)
            scored.append(
                {
                    "id": moment_id(str(asset["id"]), start_sec, end_sec),
                    "assetId": asset["id"],
                    "startSec": start_sec,
                    "endSec": end_sec,
                    "description": asset.get("description", "") or f"shot from {asset['id']}",
                    "tags": list(asset.get("tags", [])),
                    "highlightScore": highlight_score,
                    "transcriptSnippet": _transcript_snippet(
                        transcript,
                        start_sec=start_sec,
                        end_sec=end_sec,
                    ),
                }
            )
    finally:
        if reader is not None:
            reader.close()

    scored.sort(key=lambda item: item["highlightScore"], reverse=True)
    top_moments = scored[:TOP_MOMENT_COUNT]

    if video_path is not None and opencv.cv2 is not None and top_moments:
        with _VideoFrameReader(video_path, opencv.cv2) as encode_reader:
            for moment in top_moments[:VISION_MOMENT_COUNT]:
                midpoint = moment["startSec"] + (moment["endSec"] - moment["startSec"]) / 2.0
                frame = encode_reader.read_at(midpoint)
                if frame is not None:
                    keyframe = _encode_frame_base64(frame, opencv)
                    if keyframe:
                        moment["keyframeBase64"] = keyframe

    return top_moments


def _build_image_candidate_moment(
    *,
    asset: dict[str, Any],
    image_path: Path | None,
    opencv: OpenCVTool,
) -> dict[str, Any]:
    frame_metrics = None
    keyframe: str | None = None
    if image_path is not None and opencv.cv2 is not None:
        frame = opencv.cv2.imread(str(image_path))
        if frame is not None:
            frame_metrics = _analyze_frame_metrics(frame, prev_frame=None, cv2=opencv.cv2)
            keyframe = _encode_frame_base64(frame, opencv)

    moment = {
        "id": moment_id(str(asset["id"]), 0.0, 0.1),
        "assetId": asset["id"],
        "startSec": 0.0,
        "endSec": 0.1,
        "description": asset.get("description", "") or f"image {asset['id']}",
        "tags": list(asset.get("tags", [])),
        "highlightScore": score_shot_moment({"confidence": 0.75}, frame_metrics=frame_metrics),
        "transcriptSnippet": "",
    }
    if keyframe:
        moment["keyframeBase64"] = keyframe
    return moment


def _validate_moment_vision(payload: dict[str, Any]) -> dict[str, Any]:
    analyses = payload.get("analyses")
    if not isinstance(analyses, list):
        raise ValueError("asset_moment_vision output must include analyses array")
    for item in analyses:
        if not isinstance(item, dict):
            raise ValueError("analyses items must be objects")
        if "momentId" not in item:
            raise ValueError("analyses item missing momentId")
        roles = item.get("suggestedSegmentRoles", [])
        if roles is not None:
            if not isinstance(roles, list):
                raise ValueError("suggestedSegmentRoles must be an array")
            invalid = [role for role in roles if str(role) not in VALID_SEGMENT_ROLES]
            if invalid:
                raise ValueError(f"Invalid suggestedSegmentRoles: {invalid}")
    return payload


def _enrich_moments_with_vision(
    runner: AgentRunner,
    *,
    moments: list[dict[str, Any]],
    context: TaskContext,
    generation_id: str | None,
) -> list[dict[str, Any]]:
    if not moments:
        return moments

    vision_targets = [
        {key: value for key, value in moment.items() if key != "keyframeBase64"}
        for moment in moments[:VISION_MOMENT_COUNT]
    ]
    keyframes = {
        moment["id"]: moment.get("keyframeBase64")
        for moment in moments[:VISION_MOMENT_COUNT]
        if moment.get("keyframeBase64")
    }
    vision_inputs = {
        "moments": [
            {
                **target,
                **({"keyframeBase64": keyframes[target["id"]]} if target["id"] in keyframes else {}),
            }
            for target in vision_targets
        ]
    }

    output = runner.run(
        VISION_AGENT_NAME,
        task=VISION_TASK_KEY,
        schema_name=None,
        inputs=vision_inputs,
        context=context,
        progress=20,
        generation_id=generation_id,
        post_validate=_validate_moment_vision,
        profile="vision",
    )

    analysis_by_id = {
        str(item["momentId"]): item
        for item in output.get("analyses", [])
        if isinstance(item, dict) and item.get("momentId")
    }

    enriched: list[dict[str, Any]] = []
    for moment in moments:
        updated = dict(moment)
        analysis = analysis_by_id.get(moment["id"])
        if analysis is None:
            enriched.append(updated)
            continue
        if analysis.get("description"):
            updated["description"] = str(analysis["description"])
        visual_tags = analysis.get("visualTags")
        if isinstance(visual_tags, list):
            updated["visualTags"] = [str(tag) for tag in visual_tags]
        roles = analysis.get("suggestedSegmentRoles")
        if isinstance(roles, list):
            updated["suggestedSegmentRoles"] = [str(role) for role in roles]
        enriched.append(updated)
    return enriched


def _apply_visual_tags_to_assets(
    assets: list[dict[str, Any]],
    moments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    tags_by_asset: dict[str, list[str]] = {}
    for moment in moments:
        asset_id = str(moment.get("assetId", ""))
        visual_tags = moment.get("visualTags")
        if not asset_id or not isinstance(visual_tags, list):
            continue
        bucket = tags_by_asset.setdefault(asset_id, [])
        for tag in visual_tags:
            tag_text = str(tag).strip()
            if tag_text and tag_text not in bucket:
                bucket.append(tag_text)

    updated_assets: list[dict[str, Any]] = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        merged = dict(asset)
        existing = [str(tag) for tag in merged.get("tags", []) if str(tag).strip()]
        for tag in tags_by_asset.get(str(asset.get("id", "")), []):
            if tag not in existing:
                existing.append(tag)
        merged["tags"] = existing
        updated_assets.append(merged)
    return updated_assets


def run_asset_understanding(
    runner: AgentRunner,
    *,
    inventory: dict[str, Any],
    context: TaskContext,
    generation_id: str | None = None,
    opencv: OpenCVTool | None = None,
) -> dict[str, Any]:
    context.emit_event(
        stage="analyzing_assets",
        progress=10,
        message="Analyzing user brief and uploaded assets",
    )

    enriched = run_content_strategist(
        runner,
        inventory=inventory,
        context=context,
        progress=12,
        generation_id=generation_id,
    )

    opencv_tool = opencv or OpenCVTool()
    project_id = str(enriched["projectId"])
    storage_root = Path(context.storage_root)
    candidate_moments: list[dict[str, Any]] = []

    for asset in enriched.get("assets", []):
        if not isinstance(asset, dict):
            continue

        asset_id = str(asset["id"])
        asset_type = asset.get("type")
        asset_uri = str(asset.get("uri", ""))
        media_path = _resolve_asset_path(storage_root, project_id, asset_uri)

        if asset_type == "video":
            duration_sec = float(asset.get("durationSec", 3.0))
            shots = _load_asset_shots(
                storage_root,
                project_id,
                asset_id,
                video_path=media_path,
                duration_sec=duration_sec,
                opencv=opencv_tool,
            )
            transcript = _load_asset_transcript(storage_root, project_id, asset_id)
            candidate_moments.extend(
                _build_video_candidate_moments(
                    asset=asset,
                    shots=shots,
                    video_path=media_path,
                    transcript=transcript,
                    opencv=opencv_tool,
                )
            )
        elif asset_type == "image":
            candidate_moments.append(
                _build_image_candidate_moment(
                    asset=asset,
                    image_path=media_path,
                    opencv=opencv_tool,
                )
            )

    candidate_moments.sort(key=lambda item: item.get("highlightScore", 0.0), reverse=True)
    candidate_moments = candidate_moments[:TOP_MOMENT_COUNT]

    if candidate_moments:
        candidate_moments = _enrich_moments_with_vision(
            runner,
            moments=candidate_moments,
            context=context,
            generation_id=generation_id,
        )

    for moment in candidate_moments:
        moment.pop("keyframeBase64", None)
        moment.pop("transcriptSnippet", None)

    enriched["candidateMoments"] = candidate_moments
    enriched["assets"] = _apply_visual_tags_to_assets(
        list(enriched.get("assets", [])),
        candidate_moments,
    )

    validation = validate_contract("asset-inventory", enriched)
    if not validation.valid:
        raise ValueError(f"Invalid AssetInventory payload: {validation.errors}")
    return enriched
