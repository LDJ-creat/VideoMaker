from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from video.poster import (
    _build_sample_times,
    _pick_best_candidate,
    extract_video_poster,
)


def test_pick_best_candidate_prefers_highest_sharpness() -> None:
    candidates = [
        (1.0, Path("a.jpg"), 10.0),
        (1.5, Path("b.jpg"), 200.0),
        (2.0, Path("c.jpg"), 30.0),
    ]
    time_sec, path = _pick_best_candidate(candidates)
    assert time_sec == 1.5
    assert path.name == "b.jpg"


def test_pick_best_candidate_falls_back_to_1_5_without_opencv_scores() -> None:
    candidates = [
        (1.0, Path("a.jpg"), None),
        (1.5, Path("b.jpg"), None),
        (2.0, Path("c.jpg"), None),
    ]
    time_sec, path = _pick_best_candidate(candidates)
    assert time_sec == 1.5
    assert path.name == "b.jpg"


def test_build_sample_times_skips_opening_for_normal_videos() -> None:
    assert _build_sample_times(12.0, sample_times_sec=(1.0, 1.5, 2.0)) == (1.0, 1.5, 2.0)


def test_build_sample_times_clamps_for_short_videos() -> None:
    assert _build_sample_times(1.2, sample_times_sec=(1.0, 1.5, 2.0)) == (0.5, 1.0, 1.15)


def test_build_sample_times_uses_early_frames_for_very_short_videos() -> None:
    assert _build_sample_times(0.8, sample_times_sec=(1.0, 1.5, 2.0)) == (0.0, 0.1, 0.5)


def test_extract_video_poster_skips_when_poster_is_fresh(tmp_path: Path) -> None:
    video = tmp_path / "source.mp4"
    poster = tmp_path / "poster.jpg"
    video.write_bytes(b"video")
    poster.write_bytes(b"poster")

    video_mtime = video.stat().st_mtime
    poster.touch()
    assert poster.stat().st_mtime >= video_mtime

    result = extract_video_poster(video, poster)
    assert result["ok"] is True
    assert result.get("skipped") is True


def test_extract_video_poster_uses_ffmpeg_and_opencv(tmp_path: Path) -> None:
    video = tmp_path / "source.mp4"
    poster = tmp_path / "poster.jpg"
    video.write_bytes(b"video")

    def fake_extract(video_path: Path, output_path: Path, time_sec: float) -> bool:
        output_path.write_bytes(f"{time_sec}".encode("utf-8"))
        return True

    def fake_sharpness(image_path: Path) -> float | None:
        time_sec = float(image_path.read_bytes().decode("utf-8"))
        if time_sec == 1.5:
            return 200.0
        if time_sec == 2.0:
            return 30.0
        return 10.0

    with (
        patch("video.poster._probe_duration_sec", return_value=10.0),
        patch("video.poster._ffmpeg_extract_frame", side_effect=fake_extract),
        patch("video.poster._sharpness_score", side_effect=fake_sharpness),
    ):
        result = extract_video_poster(video, poster)

    assert result["ok"] is True
    assert result["sourceTimeSec"] == 1.5
    assert poster.is_file()


def test_extract_video_poster_returns_error_when_ffmpeg_fails(tmp_path: Path) -> None:
    video = tmp_path / "source.mp4"
    poster = tmp_path / "poster.jpg"
    video.write_bytes(b"video")

    with (
        patch("video.poster._probe_duration_sec", return_value=10.0),
        patch("video.poster._ffmpeg_extract_frame", return_value=False),
    ):
        result = extract_video_poster(video, poster)

    assert result["ok"] is False
    assert result["error"] == "ffmpeg_extract_failed"


def test_extract_video_poster_video_not_found(tmp_path: Path) -> None:
    result = extract_video_poster(tmp_path / "missing.mp4", tmp_path / "poster.jpg")
    assert result["ok"] is False
    assert result["error"] == "video_not_found"
