from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from app.composition.acp.base_video_normalize import (
    BaseVideoDiagnostics,
    prepare_base_video_for_scratch,
    should_normalize_base_video,
)


def test_should_normalize_base_video_when_interval_exceeds_threshold() -> None:
    assert should_normalize_base_video(8.33, threshold_sec=2.0) is True
    assert should_normalize_base_video(1.5, threshold_sec=2.0) is False


def test_prepare_base_video_skips_reencode_when_dense(tmp_path: Path) -> None:
    src = tmp_path / "dense.mp4"
    src.write_bytes(b"video")
    scratch = tmp_path / "scratch"
    dest, diagnostics = prepare_base_video_for_scratch(
        src,
        scratch,
        ffmpeg=_FakeFfmpeg(interval=1.0),
    )
    assert dest.name == "dense.mp4"
    assert diagnostics.reencoded is False


def test_prepare_base_video_reencodes_sparse(tmp_path: Path) -> None:
    src = tmp_path / "sparse.mp4"
    src.write_bytes(b"video")
    scratch = tmp_path / "scratch"
    dest, diagnostics = prepare_base_video_for_scratch(
        src,
        scratch,
        ffmpeg=_FakeFfmpeg(interval=8.33),
    )
    assert dest.name == "sparse-normalized.mp4"
    assert diagnostics.reencoded is True
    assert dest.is_file()


class _FakeFfmpeg:
    def __init__(self, *, interval: float) -> None:
        self.interval = interval
        self.normalize_called = False

    def probe(self, video_path: str | Path) -> dict[str, object]:
        return {"durationSec": 9.5}

    def _command_runner(self, command: list[str]) -> MagicMock:
        result = MagicMock()
        result.returncode = 0
        if "nokey" in command:
            if self.interval > 2.0:
                result.stdout = "0.0\n8.33\n"
            else:
                result.stdout = "0.0\n1.0\n2.0\n"
        return result

    def normalize_for_composition_preview(self, src: Path, dest: Path) -> dict[str, object]:
        self.normalize_called = True
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"normalized")
        return {"path": str(dest)}

    def probe_keyframe_interval_sec(self, video_path: Path) -> float | None:
        return self.interval


def test_base_video_diagnostics_to_dict() -> None:
    payload = BaseVideoDiagnostics(max_keyframe_interval_sec=8.33, reencoded=True).to_dict()
    assert payload["reencoded"] is True
    assert payload["maxKeyframeIntervalSec"] == 8.33
