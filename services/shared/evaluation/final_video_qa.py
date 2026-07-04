from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any

from evaluation.ffprobe_util import probe_media_duration_sec


def run_final_video_qa(
    mp4_path: Path,
    *,
    target_duration_sec: float | None = None,
    duration_drift_max: float | None = None,
) -> dict[str, Any]:
    drift_max = duration_drift_max
    if drift_max is None:
        drift_max = float(os.getenv("VIDEOMAKER_EVAL_DURATION_DRIFT_MAX", "0.25"))

    issues: list[str] = []
    warnings: list[str] = []
    blocking: list[str] = []
    score = 100.0

    technical: dict[str, Any] = {
        "validContainer": False,
        "hasAudio": False,
        "durationSec": None,
        "resolution": None,
    }

    if not mp4_path.is_file():
        blocking.append("output_mp4_missing")
        return _result(score=0.0, technical=technical, blocking=blocking, warnings=warnings, issues=issues)

    duration = probe_media_duration_sec(mp4_path)
    technical["durationSec"] = duration
    technical["validContainer"] = duration is not None and duration > 0

    if duration is None or duration < 1.0:
        blocking.append("suspiciously_short_output")
        score -= 40
    elif target_duration_sec and target_duration_sec > 0:
        drift = abs(duration - target_duration_sec) / target_duration_sec
        if drift > drift_max:
            warnings.append(f"duration_drift:{drift:.0%}")
            score -= min(25.0, drift * 50.0)

    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_streams",
                str(mp4_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.returncode == 0:
            data = json.loads(proc.stdout or "{}")
            streams = data.get("streams") if isinstance(data, dict) else []
            video_stream = next(
                (s for s in streams if isinstance(s, dict) and s.get("codec_type") == "video"),
                {},
            )
            audio_stream = next(
                (s for s in streams if isinstance(s, dict) and s.get("codec_type") == "audio"),
                {},
            )
            width = int(video_stream.get("width") or 0)
            height = int(video_stream.get("height") or 0)
            if width and height:
                technical["resolution"] = f"{width}x{height}"
            technical["hasAudio"] = bool(audio_stream)
            if not audio_stream:
                warnings.append("no_audio_stream")
                score -= 15
    except (OSError, json.JSONDecodeError, subprocess.TimeoutExpired):
        warnings.append("ffprobe_streams_failed")
        score -= 10

    if os.getenv("VIDEOMAKER_EVAL_TECHNICAL_BLOCK", "false").lower() == "true":
        blocking.extend(warnings)
        blocking.extend(
            issue for issue in issues if issue not in blocking and issue not in warnings
        )

    score = max(0.0, min(100.0, score))
    return _result(
        score=score,
        technical=technical,
        blocking=blocking,
        warnings=warnings,
        issues=issues + warnings + blocking,
    )


def _result(
    *,
    score: float,
    technical: dict[str, Any],
    blocking: list[str],
    warnings: list[str],
    issues: list[str],
) -> dict[str, Any]:
    return {
        "score": round(score, 1),
        "technical": technical,
        "blockingIssues": blocking,
        "warnings": warnings,
        "issues": issues,
    }
