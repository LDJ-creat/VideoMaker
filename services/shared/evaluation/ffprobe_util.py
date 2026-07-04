from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any


def probe_media_duration_sec(path: Path) -> float | None:
    if not path.is_file():
        return None
    try:
        proc = subprocess.run(
            [
                "ffprobe",
                "-v",
                "quiet",
                "-print_format",
                "json",
                "-show_format",
                str(path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        if proc.returncode != 0:
            return None
        data = json.loads(proc.stdout or "{}")
        fmt = data.get("format") if isinstance(data, dict) else {}
        if not isinstance(fmt, dict):
            return None
        duration = fmt.get("duration")
        if duration is None:
            return None
        return float(duration)
    except (OSError, json.JSONDecodeError, ValueError, subprocess.TimeoutExpired):
        return None


def probe_video_bytes_duration_sec(video_bytes: bytes) -> float | None:
    if not video_bytes:
        return None
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(video_bytes)
        tmp_path = Path(tmp.name)
    try:
        return probe_media_duration_sec(tmp_path)
    finally:
        tmp_path.unlink(missing_ok=True)
