from __future__ import annotations

from app.validation.structure_coercer import coerce_video_structure


def test_coerce_defaults_version_to_p0_v1_without_deep_fields() -> None:
    payload = {
        "narrative": {
            "segments": [
                {
                    "role": "hook",
                    "scriptSummary": "反问式痛点开场建立停滑",
                    "visualSummary": "胸景口播快切产品 UI 特写",
                }
            ]
        },
        "rhythm": {"beatPoints": [], "shotBoundaries": []},
        "packaging": {"visualDensity": "medium"},
        "slots": [],
        "evidence": [],
    }
    coerced = coerce_video_structure(
        payload,
        project_id="project-1",
        source_video_id="sample-1",
    )
    assert coerced["version"] == "p0-v1"


def test_coerce_upgrades_to_p1_v2_when_transcript_excerpt_present() -> None:
    payload = {
        "narrative": {
            "segments": [
                {
                    "role": "hook",
                    "transcriptExcerpt": "还在花冤枉钱？",
                    "scriptSummary": "反问式痛点开场建立停滑",
                    "visualSummary": "胸景口播快切产品 UI 特写",
                }
            ]
        },
        "rhythm": {"beatPoints": [], "shotBoundaries": []},
        "packaging": {"visualDensity": "medium"},
        "slots": [],
        "evidence": [],
    }
    coerced = coerce_video_structure(
        payload,
        project_id="project-1",
        source_video_id="sample-1",
    )
    assert coerced["version"] == "p1-v2"
