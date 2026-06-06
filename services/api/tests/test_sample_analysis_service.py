from __future__ import annotations

from app.services.sample_analysis import slim_sample_analysis_response


def test_slim_sample_analysis_response_strips_paths_timeline_and_visual_facts() -> None:
    payload = {
        "metadataPath": "analysis/metadata.json",
        "sourcePath": "samples/demo/source.mp4",
        "metadata": {"durationSec": 12.0},
        "audioProfile": {
            "hasVoiceover": True,
            "hasBgm": False,
            "metrics": {"voiceoverCoveragePct": 0.5},
            "energyTimeline": [{"timeSec": 0.0, "rmsDb": -8.0}],
        },
        "keyframeBatchDigests": [
            {
                "batchIndex": 0,
                "startSec": 0.0,
                "endSec": 4.0,
                "visualFacts": "close-up product",
                "frames": [],
            }
        ],
    }
    slim = slim_sample_analysis_response(payload)
    assert "metadataPath" not in slim
    assert "sourcePath" not in slim
    assert "energyTimeline" not in slim["audioProfile"]
    assert slim["keyframeBatchDigests"] == [
        {
            "batchIndex": 0,
            "startSec": 0.0,
            "endSec": 4.0,
            "digestRef": "batch-digests/batch-0.json",
        }
    ]
