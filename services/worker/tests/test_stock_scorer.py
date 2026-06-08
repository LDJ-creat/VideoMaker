from __future__ import annotations

from app.stock.stock_scorer import pick_best_candidate


def test_pick_best_candidate_rejects_video_shorter_than_target() -> None:
    videos = [
        {"id": 1, "duration": 14, "tags": ["kitchen lifestyle b-roll"]},
        {"id": 2, "duration": 16, "tags": ["kitchen lifestyle b-roll"]},
    ]
    best, media_type, score = pick_best_candidate(
        query="kitchen lifestyle b-roll",
        photos=[],
        videos=videos,
        prefer_video=True,
        target_duration_sec=15.7,
    )
    assert best is not None
    assert media_type == "video"
    assert best["id"] == 2
    assert score > 0


def test_pick_best_candidate_rejects_video_below_target_even_within_old_ninetieth_band() -> None:
    """15s is below 15.7s target; must not pass after removing the 0.9 tolerance."""
    videos = [{"id": 4, "duration": 15, "tags": ["kitchen lifestyle b-roll"]}]
    best, media_type, _score = pick_best_candidate(
        query="kitchen lifestyle b-roll",
        photos=[],
        videos=videos,
        prefer_video=True,
        target_duration_sec=15.7,
    )
    assert best is None
    assert media_type is None


def test_pick_best_candidate_accepts_video_at_least_target_duration() -> None:
    videos = [{"id": 3, "duration": 16, "tags": ["office meeting discussion"]}]
    best, media_type, _score = pick_best_candidate(
        query="office meeting discussion",
        photos=[],
        videos=videos,
        prefer_video=True,
        target_duration_sec=15.7,
    )
    assert best is not None
    assert media_type == "video"
    assert best["id"] == 3
