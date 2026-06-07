from __future__ import annotations

import pytest

from app.stock.stock_segment_planner import build_stock_segments


def test_build_stock_segments_single_for_short_slot() -> None:
    segments = build_stock_segments(
        slot={"id": "slot-1", "role": "hook_visual"},
        scene={"visual": "dinner party", "script": "hello"},
        primary_query="dinner awkward smile",
        target_duration_sec=7.0,
    )
    assert len(segments) == 1
    assert segments[0].query == "dinner awkward smile"
    assert segments[0].duration_sec == 7.0


def test_build_stock_segments_splits_social_scenes_for_long_slot() -> None:
    visual = (
        "多场景快速剪辑串联商务饭局、朋友聚会、家庭聚餐三类场景的正确社交行为示范，"
        "每个场景出现时同步弹出对应规则的大白字字幕"
    )
    segments = build_stock_segments(
        slot={"id": "slot-4", "role": "usage_scene"},
        scene={"visual": visual, "script": "不同场景规则示范"},
        primary_query="social gathering lifestyle b-roll",
        target_duration_sec=47.0,
    )
    assert len(segments) == 3
    assert sum(segment.duration_sec for segment in segments) == pytest.approx(47.0, abs=0.01)
    assert "business dinner" in segments[0].query.lower()
    assert "friends" in segments[1].query.lower()
    assert "family dinner" in segments[2].query.lower()


def test_build_stock_segments_splits_slot6_demo_markers() -> None:
    visual = "近景特写展示手写接话句型的笔记画面、手机备忘录里「话题池」的操作界面"
    segments = build_stock_segments(
        slot={"id": "slot-6", "role": "usage_scene"},
        scene={"visual": visual, "script": "万能接话句型与话题池"},
        primary_query="conversation tips lifestyle",
        target_duration_sec=72.0,
    )
    assert 2 <= len(segments) <= 4
    assert sum(segment.duration_sec for segment in segments) == pytest.approx(72.0, abs=0.01)
