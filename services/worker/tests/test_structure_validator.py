from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.validation.structure_coercer import coerce_video_structure
from app.validation.structure_validator import (
    StructureValidationError,
    validate_video_structure,
)


def _coerce_fixture(raw: dict) -> dict:
    analysis_path = Path(__file__).parent / "fixtures" / "sample_analysis.json"
    analysis = json.loads(analysis_path.read_text(encoding="utf-8"))
    return coerce_video_structure(
        raw,
        project_id=str(raw.get("projectId") or "project-1"),
        source_video_id=str(raw.get("sourceVideoId") or "sample-1"),
        analysis=analysis,
    )


def _minimal_hook_payload(**overrides: object) -> dict:
    base = {
        "confidence": 0.8,
        "metadata": {"durationSec": 10.0},
        "narrative": {
            "summary": "中文摘要足够长用于测试",
            "segments": [
                {
                    "id": "seg-1",
                    "role": "hook",
                    "startSec": 0.0,
                    "endSec": 3.0,
                    "scriptSummary": "反问式痛点开场建立停滑",
                    "visualSummary": "胸景口播快切产品 UI 特写",
                    "transcriptExcerpt": "还在花冤枉钱？",
                    "intent": "停滑",
                }
            ],
        },
        "rhythm": {
            "totalDurationSec": 10.0,
            "shotCount": 1,
            "avgShotDurationSec": 10.0,
            "tempo": "fast",
            "beatPoints": [0.0, 10.0],
            "shotBoundaries": [
                {"startSec": 0.0, "endSec": 10.0, "confidence": 0.8, "changeReason": "scene_change"}
            ],
        },
        "slots": [],
        "evidence": [
            {
                "targetId": "seg-1",
                "source": "asr",
                "summary": "0-2s 反问",
                "excerpt": "还在花冤枉钱？",
                "confidence": 0.8,
            }
        ],
    }
    for key, value in overrides.items():
        base[key] = value
    return _coerce_fixture(base)


def _valid_structure() -> dict:
    path = Path(__file__).parent / "fixtures" / "agents" / "structure_analyst.json"
    return _coerce_fixture(json.loads(path.read_text(encoding="utf-8")))


def test_validate_accepts_fixture_structure() -> None:
    structure = _valid_structure()
    assert validate_video_structure(structure) == structure


def test_validate_requires_evidence_per_segment() -> None:
    structure = _valid_structure()
    structure["evidence"] = [
        item for item in structure["evidence"] if not item["targetId"].startswith("seg-2")
    ]
    with pytest.raises(StructureValidationError, match="segment evidence"):
        validate_video_structure(structure)


def test_validate_requires_valid_slot_segment_ids() -> None:
    structure = _valid_structure()
    structure["slots"][0]["segmentId"] = "missing-segment"
    with pytest.raises(StructureValidationError, match="slot segmentId"):
        validate_video_structure(structure)


def test_validate_rejects_confidence_out_of_range() -> None:
    structure = _valid_structure()
    structure["confidence"] = 1.5
    with pytest.raises(StructureValidationError, match="confidence"):
        validate_video_structure(structure)


def test_validate_cta_must_end_near_video_end() -> None:
    structure = _valid_structure()
    for segment in structure["narrative"]["segments"]:
        if segment["role"] == "cta":
            segment["endSec"] = 10.0
    with pytest.raises(StructureValidationError, match="cta"):
        validate_video_structure(structure)


def test_validate_rejects_asr_evidence_without_time_range() -> None:
    structure = _valid_structure()
    structure["evidence"] = [
        item
        for item in structure["evidence"]
        if item["targetId"] != "seg-hook"
    ]
    structure["evidence"].append(
        {
            "targetId": "seg-hook",
            "source": "asr",
            "summary": "hook text without timestamps",
            "confidence": 0.5,
        }
    )
    with pytest.raises(StructureValidationError, match="segment evidence"):
        validate_video_structure(structure)


def test_validate_rejects_template_blacklist_phrase() -> None:
    structure = _valid_structure()
    structure["narrative"]["segments"][0]["visualSummary"] = "Engaging opening that captures viewer attention"
    with pytest.raises(StructureValidationError, match="blacklist"):
        validate_video_structure(structure)


def test_validate_rejects_duplicate_visual_and_script_summary() -> None:
    structure = _valid_structure()
    structure["narrative"]["segments"][0]["scriptSummary"] = structure["narrative"]["segments"][0][
        "visualSummary"
    ]
    with pytest.raises(StructureValidationError, match="too similar"):
        validate_video_structure(structure)


def test_validate_accepts_asr_evidence_with_excerpt_only() -> None:
    structure = _valid_structure()
    structure["evidence"] = [
        item for item in structure["evidence"] if item["targetId"] != "seg-hook"
    ]
    structure["evidence"].append(
        {
            "targetId": "seg-hook",
            "source": "asr",
            "summary": "hook segment",
            "excerpt": "太贵又麻烦？",
            "confidence": 0.8,
        }
    )
    assert validate_video_structure(structure) == structure


def test_validate_rhythm_shot_boundaries_align_with_reference_shots() -> None:
    import json

    analysis_path = Path(__file__).parent / "fixtures" / "sample_analysis.json"
    shots = json.loads(analysis_path.read_text(encoding="utf-8"))["shots"]
    structure = _valid_structure()
    validate_video_structure(structure, reference_shots=shots)


def test_validate_rhythm_misaligned_shot_boundaries_fail() -> None:
    import json

    analysis_path = Path(__file__).parent / "fixtures" / "sample_analysis.json"
    shots = json.loads(analysis_path.read_text(encoding="utf-8"))["shots"]
    structure = _valid_structure()
    structure["rhythm"]["shotBoundaries"][0]["startSec"] = 99.0
    with pytest.raises(StructureValidationError, match="rhythm.shotBoundaries"):
        validate_video_structure(structure, reference_shots=shots)


def test_validate_skips_shot_alignment_when_reference_shots_none() -> None:
    structure = _valid_structure()
    structure["rhythm"]["shotBoundaries"][0]["startSec"] = 99.0
    assert validate_video_structure(structure, reference_shots=None) == structure


def test_validate_accepts_keyframe_evidence_with_timestamp_without_path() -> None:
    structure = _minimal_hook_payload(
        evidence=[
            {
                "targetId": "seg-1",
                "source": "keyframe",
                "summary": "0.8s 快切至产品 UI 特写，底部黄字关键词",
                "confidence": 0.8,
            }
        ]
    )
    assert validate_video_structure(structure, reference_shots=None, anti_template=False) == structure


def test_validate_accepts_keyframe_evidence_with_time_range_without_path() -> None:
    structure = _minimal_hook_payload(
        evidence=[
            {
                "targetId": "seg-1",
                "source": "keyframe",
                "summary": "胸景口播直视镜头",
                "timeRange": {"startSec": 0.0, "endSec": 0.8},
                "confidence": 0.8,
            }
        ]
    )
    assert validate_video_structure(structure, reference_shots=None, anti_template=False) == structure


def test_validate_rejects_keyframe_evidence_without_path_or_timestamp() -> None:
    structure = _minimal_hook_payload(
        evidence=[
            {
                "targetId": "seg-1",
                "source": "keyframe",
                "summary": "胸景口播",
                "confidence": 0.8,
            }
        ]
    )
    with pytest.raises(StructureValidationError, match="segment evidence"):
        validate_video_structure(structure, reference_shots=None, anti_template=False)


def test_validate_v3_requires_transcript_excerpt() -> None:
    structure = _minimal_hook_payload()
    structure["narrative"]["segments"][0].pop("transcriptExcerpt", None)
    with pytest.raises(StructureValidationError) as exc:
        validate_video_structure(structure, anti_template=False)
    assert any("transcriptExcerpt" in item for item in exc.value.errors)


def test_validate_v3_requires_audio_evidence_when_voiceover_present() -> None:
    structure = _minimal_hook_payload(
        evidence=[
            {
                "targetId": "seg-1",
                "source": "keyframe",
                "summary": "0.5-1.2 sec",
                "confidence": 0.8,
            }
        ]
    )
    analysis = {
        "audioProfile": {
            "hasVoiceover": True,
            "hasBgm": False,
            "onsetTimes": [0.0, 2.5],
            "metrics": {"voiceoverCoveragePct": 0.8},
        }
    }
    with pytest.raises(StructureValidationError) as exc:
        validate_video_structure(structure, analysis=analysis, anti_template=False)
    assert any("audio or asr evidence" in item for item in exc.value.errors)


def test_validate_v3_rejects_misaligned_beat_points() -> None:
    structure = _minimal_hook_payload()
    structure["rhythm"]["beatPoints"] = [1.0, 4.0, 7.0, 9.5]
    analysis = {
        "audioProfile": {
            "hasVoiceover": True,
            "hasBgm": False,
            "onsetTimes": [0.0, 2.5, 5.0],
            "metrics": {"voiceoverCoveragePct": 0.8},
        }
    }
    with pytest.raises(StructureValidationError) as exc:
        validate_video_structure(structure, analysis=analysis, anti_template=False)
    assert any("beatPoints not aligned" in item for item in exc.value.errors)


def test_validate_rejects_duplicate_transcript_and_script_summary() -> None:
    structure = _minimal_hook_payload()
    duplicate = "反问式痛点开场建立停滑，完整口播与摘要相同"
    structure["narrative"]["segments"][0]["scriptSummary"] = duplicate
    structure["narrative"]["segments"][0]["transcriptExcerpt"] = duplicate
    with pytest.raises(StructureValidationError, match="transcriptExcerpt duplicates"):
        validate_video_structure(structure, anti_template=False)
