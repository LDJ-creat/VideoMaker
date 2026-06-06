from __future__ import annotations

from app.perception.sample_facts import (
    batch_digest_index_entries,
    merge_visual_facts_into_sample_analysis,
    slim_audio_profile,
)


def test_slim_audio_profile_strips_timeline_and_regions() -> None:
    full = {
        "hasVoiceover": True,
        "hasBgm": False,
        "onsetTimes": [0.0, 1.5],
        "metrics": {"voiceoverCoveragePct": 0.8},
        "avgSpeechRate": 4.2,
        "energyTimeline": [{"timeSec": 0.0, "rmsDb": -12.0}],
        "speechRegions": [{"startSec": 0.0, "endSec": 2.0}],
        "silenceRegions": [],
        "bgmCandidateRegions": [],
    }
    slim = slim_audio_profile(full)
    assert slim == {
        "hasVoiceover": True,
        "hasBgm": False,
        "onsetTimes": [0.0, 1.5],
        "metrics": {"voiceoverCoveragePct": 0.8},
        "avgSpeechRate": 4.2,
    }


def test_merge_visual_facts_stores_digest_index_only() -> None:
    sample_analysis = {
        "metadataPath": "/tmp/metadata.json",
        "metadata": {"durationSec": 10.0},
    }
    batch_digests = [
        {
            "batchIndex": 0,
            "startSec": 0.0,
            "endSec": 4.0,
            "visualFacts": "product close-up on table",
            "onScreenTextFacts": [{"timeSec": 1.0, "text": "限时", "confidence": 0.9}],
        }
    ]
    merged = merge_visual_facts_into_sample_analysis(
        sample_analysis,
        batch_digests=batch_digests,
    )
    assert "metadataPath" not in merged
    assert merged["keyframeBatchDigests"] == [
        {
            "batchIndex": 0,
            "startSec": 0.0,
            "endSec": 4.0,
            "digestRef": "batch-digests/batch-0.json",
        }
    ]
    assert merged["onScreenTextFacts"][0]["text"] == "限时"


def test_batch_digest_index_entries_preserves_order() -> None:
    entries = batch_digest_index_entries(
        [
            {"batchIndex": 1, "startSec": 4.0, "endSec": 8.0, "visualFacts": "x"},
            {"batchIndex": 0, "startSec": 0.0, "endSec": 4.0, "visualFacts": "y"},
        ]
    )
    assert entries[0]["digestRef"] == "batch-digests/batch-1.json"
    assert entries[1]["digestRef"] == "batch-digests/batch-0.json"
