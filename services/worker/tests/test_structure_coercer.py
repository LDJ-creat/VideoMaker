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


def test_coerce_hoists_evidence_from_narrative() -> None:
    payload = {
        "narrative": {
            "summary": "测试结构",
            "segments": [
                {
                    "id": "seg-1",
                    "role": "hook",
                    "startSec": 0,
                    "endSec": 3,
                    "scriptSummary": "反问开场",
                    "visualSummary": "胸景口播",
                    "intent": "停滑",
                }
            ],
            "evidence": [
                {
                    "targetId": "seg-1",
                    "source": "asr",
                    "summary": "0-3s 反问",
                    "excerpt": "还在花冤枉钱",
                }
            ],
        },
        "rhythm": {"beatPoints": [0, 3], "shotBoundaries": []},
        "packaging": {"visualDensity": "medium"},
        "slots": [],
    }
    coerced = coerce_video_structure(
        payload,
        project_id="project-1",
        source_video_id="sample-1",
        analysis={"metadata": {"durationSec": 30.0}, "shots": []},
    )
    assert "evidence" not in coerced["narrative"]
    assert any(item.get("targetId") == "seg-1" for item in coerced["evidence"])


def test_coerce_fills_transcript_excerpt_from_asr_evidence() -> None:
    payload = {
        "version": "p1-v2",
        "narrative": {
            "summary": "测试",
            "segments": [
                {
                    "id": "seg-1",
                    "role": "hook",
                    "startSec": 0,
                    "endSec": 3,
                    "scriptSummary": "反问式开场建立停滑",
                    "visualSummary": "胸景口播",
                    "intent": "停滑",
                }
            ],
        },
        "evidence": [
            {
                "targetId": "seg-1",
                "source": "asr",
                "summary": "0-3s",
                "excerpt": "还在花冤枉钱？",
            }
        ],
        "rhythm": {"beatPoints": [0, 3], "shotBoundaries": []},
        "packaging": {"visualDensity": "medium"},
        "slots": [],
    }
    coerced = coerce_video_structure(
        payload,
        project_id="project-1",
        source_video_id="sample-1",
        analysis={"metadata": {"durationSec": 30.0}, "shots": []},
    )
    assert coerced["narrative"]["segments"][0]["transcriptExcerpt"] == "还在花冤枉钱？"


def test_coerce_direct_route_ignores_llm_shot_boundaries() -> None:
    shots = [
        {"startSec": 0.0, "endSec": 2.0, "confidence": 0.8, "changeReason": "visual_cut"},
        {"startSec": 2.0, "endSec": 5.0, "confidence": 0.81, "changeReason": "scene_change"},
    ]
    payload = {
        "version": "p1-v2",
        "narrative": {
            "summary": "测试",
            "segments": [
                {
                    "id": "seg-1",
                    "role": "hook",
                    "startSec": 0,
                    "endSec": 5,
                    "scriptSummary": "反问式开场",
                    "visualSummary": "胸景口播",
                    "intent": "停滑",
                    "transcriptExcerpt": "还在花冤枉钱？",
                }
            ],
        },
        "rhythm": {
            "tempo": "fast",
            "beatPoints": [0, 5],
            "shotBoundaries": [
                {
                    "startSec": 99.0,
                    "endSec": 100.0,
                    "confidence": 0.9,
                    "changeReason": "visual_cut",
                }
            ],
        },
        "packaging": {"visualDensity": "medium"},
        "slots": [],
        "evidence": [],
    }
    coerced = coerce_video_structure(
        payload,
        project_id="project-1",
        source_video_id="sample-1",
        analysis={
            "metadata": {"durationSec": 5.0},
            "shots": shots,
            "structureAnalysisRoute": "direct_multimodal",
        },
    )
    boundaries = coerced["rhythm"]["shotBoundaries"]
    assert len(boundaries) == 2
    assert boundaries[0]["startSec"] == 0.0
    assert boundaries[0]["endSec"] == 2.0
    assert boundaries[1]["startSec"] == 2.0
    assert boundaries[1]["endSec"] == 5.0
