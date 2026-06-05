from __future__ import annotations

from typing import Any

from app.agents.runner import AgentRunner
from app.runtime.task_context import TaskContext


TASK_KEY = "structure_compiler"
SCHEMA_NAME = "video-structure"


def _slim_batch_digests(digests: Any) -> list[dict[str, Any]]:
    if not isinstance(digests, list):
        return []
    slim: list[dict[str, Any]] = []
    for item in digests:
        if not isinstance(item, dict):
            continue
        slim.append(
            {
                "batchIndex": item.get("batchIndex"),
                "startSec": item.get("startSec"),
                "endSec": item.get("endSec"),
                "visualFacts": list(item.get("visualFacts") or [])[:12],
                "onScreenTextFacts": list(item.get("onScreenTextFacts") or [])[:12],
            }
        )
    return slim


def _slim_segment_analyses(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    slim: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        evidence = []
        for ev in list(item.get("localEvidence") or [])[:5]:
            if not isinstance(ev, dict):
                continue
            evidence.append(
                {
                    key: ev.get(key)
                    for key in ("source", "summary", "timeRange", "excerpt")
                    if ev.get(key) is not None
                }
            )
        slim.append(
            {
                "segmentId": item.get("segmentId"),
                "transcriptExcerpt": item.get("transcriptExcerpt"),
                "emotionTone": item.get("emotionTone"),
                "rhetoricalDevices": item.get("rhetoricalDevices"),
                "voStyle": item.get("voStyle"),
                "visualSpec": item.get("visualSpec"),
                "onScreenTextFacts": list(item.get("onScreenTextFacts") or [])[:8],
                "localEvidence": evidence,
            }
        )
    return slim


def _slim_audio_profile(audio_profile: Any) -> dict[str, Any] | None:
    if not isinstance(audio_profile, dict):
        return None
    return {
        "hasVoiceover": audio_profile.get("hasVoiceover"),
        "hasBgm": audio_profile.get("hasBgm"),
        "onsetTimes": list(audio_profile.get("onsetTimes") or [])[:48],
        "avgSpeechRate": audio_profile.get("avgSpeechRate"),
    }


def _transcript_summary(transcript: Any) -> dict[str, Any]:
    if isinstance(transcript, dict):
        segments = list(transcript.get("segments") or [])
        return {
            "language": transcript.get("language"),
            "segmentCount": len(segments),
            "preview": [
                {
                    "startSec": item.get("startSec"),
                    "endSec": item.get("endSec"),
                    "text": str(item.get("text") or "")[:80],
                }
                for item in segments[:6]
                if isinstance(item, dict)
            ],
        }
    if isinstance(transcript, list):
        return {"segmentCount": len(transcript)}
    return {"segmentCount": 0}


def run_structure_compiler(
    runner: AgentRunner,
    *,
    analysis: dict[str, Any],
    proposal: dict[str, Any],
    segment_analyses: list[dict[str, Any]],
    project_id: str,
    source_video_id: str,
    context: TaskContext,
    progress: int = 93,
    validation_errors: list[str] | None = None,
) -> dict[str, Any]:
    inputs: dict[str, Any] = {
        "projectId": project_id,
        "sourceVideoId": source_video_id,
        "locale": analysis.get("locale", "zh"),
        "metadata": analysis.get("metadata"),
        "transcriptSummary": _transcript_summary(analysis.get("transcript")),
        "shotCount": len(analysis.get("shots") or []),
        "audioProfile": _slim_audio_profile(analysis.get("audioProfile")),
        "keyframeBatchDigests": _slim_batch_digests(analysis.get("keyframeBatchDigests")),
        "onScreenTextFacts": list(analysis.get("onScreenTextFacts") or [])[:24],
        "proposal": proposal,
        "segmentAnalyses": _slim_segment_analyses(segment_analyses),
        "version": "p1-v2",
    }
    if validation_errors:
        inputs["validationErrors"] = validation_errors

    return runner.run(
        "structure_compiler",
        task=TASK_KEY,
        schema_name=None,
        inputs=inputs,
        context=context,
        progress=progress,
    )
