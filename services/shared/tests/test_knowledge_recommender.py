from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge.recommender import build_recommendation, rank_knowledge_entries


def _entry(entry_id: str, **overrides: object) -> dict:
    base = {
        "id": entry_id,
        "status": "published",
        "title": "快节奏促销带货",
        "category": "电商带货",
        "style": "快节奏促销",
        "hookType": "pain_point",
        "tempo": "fast",
        "durationBucket": "30s",
        "slotPattern": "hook→benefit→proof→cta",
        "summary": "电商快节奏结构",
        "skillMdUri": f"knowledge/ecommerce/{entry_id}/structure-skill.md",
        "structureJsonUri": f"knowledge/ecommerce/{entry_id}/video-structure.json",
        "version": 1,
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
    }
    base.update(overrides)
    return base


def test_rank_knowledge_entries_prefers_topic_overlap() -> None:
    brief = {
        "topic": "电商带货促销",
        "tone": "快节奏",
        "sellingPoints": ["限时优惠", "性价比高", "包邮"],
    }
    candidates = rank_knowledge_entries(
        [
            _entry("a"),
            _entry("b", title="知识科普", category="教育", style="慢节奏", tempo="slow"),
        ],
        brief=brief,
    )
    assert candidates[0]["entryId"] == "a"
    assert candidates[0]["score"] >= candidates[1]["score"]


def test_build_recommendation_has_primary() -> None:
    recommendation = build_recommendation(
        project_id="project-1",
        entries=[_entry("a"), _entry("b", style="其他")],
        brief={"topic": "电商", "sellingPoints": ["优惠"]},
    )
    assert recommendation["suggestedPrimaryId"] == "a"
    assert recommendation["candidates"]
