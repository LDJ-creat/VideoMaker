from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge.index_builder import build_entry_meta, duration_bucket, extract_slot_pattern


def test_extract_slot_pattern_from_segments() -> None:
    structure = {
        "narrative": {
            "segments": [
                {"role": "hook"},
                {"role": "benefit"},
                {"role": "proof"},
                {"role": "cta"},
            ]
        }
    }
    assert extract_slot_pattern(structure) == "hook→benefit→proof→cta"


def test_duration_bucket() -> None:
    assert duration_bucket(15) == "15s"
    assert duration_bucket(30) == "30s"
    assert duration_bucket(90) == "60s+"


def test_build_entry_meta() -> None:
    structure = json.loads(
        (Path(__file__).parent.parent.parent / "worker" / "tests" / "fixtures" / "structures" / "sample-structure.json").read_text(
            encoding="utf-8"
        )
    )
    meta = build_entry_meta(
        structure,
        title="测试",
        category="电商",
        style="快节奏",
        summary="摘要",
    )
    assert meta["slotPattern"]
    assert meta["durationBucket"] == "30s"
