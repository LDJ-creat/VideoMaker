from __future__ import annotations

from app.validation.structure_coercer import coerce_video_structure


def test_coerce_defaults_version_to_p1_v3() -> None:
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
        "slots": [],
        "evidence": [],
    }
    coerced = coerce_video_structure(
        payload,
        project_id="project-1",
        source_video_id="sample-1",
    )
    assert coerced["version"] == "p1-v3"
    assert coerced["context"]["contentCategory"] == "general"
    assert coerced["verbal"]["hookTemplate"]


def test_coerce_enriches_v3_blocks_with_transcript_excerpt() -> None:
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
    assert coerced["version"] == "p1-v3"
    assert coerced["narrative"]["segments"][0]["transcriptExcerpt"] == "还在花冤枉钱？"


def test_coerce_sanitizes_low_value_shot_detection_evidence() -> None:
    payload = {
        "narrative": {
            "summary": "测试",
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
        },
        "evidence": [
            {
                "targetId": "seg-1",
                "source": "shot_detection",
                "summary": "3 overlapping shot boundaries at 0.0-3.0s",
                "confidence": 0.8,
            }
        ],
        "rhythm": {"beatPoints": [0, 3], "shotBoundaries": []},
        "slots": [],
    }
    coerced = coerce_video_structure(
        payload,
        project_id="project-1",
        source_video_id="sample-1",
        analysis={"metadata": {"durationSec": 30.0}, "shots": []},
    )
    shot_evidence = [e for e in coerced["evidence"] if e.get("source") == "shot_detection"]
    assert shot_evidence
    assert "overlapping" not in shot_evidence[0]["summary"].lower()


def test_coerce_maps_problem_slot_role_to_proof() -> None:
    payload = {
        "narrative": {
            "summary": "测试",
            "segments": [
                {
                    "id": "seg-problem",
                    "role": "problem",
                    "startSec": 0,
                    "endSec": 5,
                    "scriptSummary": "痛点描述",
                    "visualSummary": "问题场景",
                    "intent": "痛点",
                }
            ],
        },
        "slots": [
            {
                "id": "slot-problem",
                "segmentId": "seg-problem",
                "role": "problem",
                "visualIntent": "展示痛点",
                "scriptIntent": "说明问题",
            }
        ],
        "rhythm": {"beatPoints": [0, 5], "shotBoundaries": []},
        "evidence": [],
    }
    coerced = coerce_video_structure(
        payload,
        project_id="project-1",
        source_video_id="sample-1",
        analysis={"metadata": {"durationSec": 30.0}, "shots": []},
    )
    assert coerced["slots"][0]["role"] == "proof"


def test_coerce_splits_visual_and_script_slot_intents() -> None:
    payload = {
        "narrative": {
            "summary": "测试",
            "segments": [
                {
                    "id": "seg-1",
                    "role": "hook",
                    "startSec": 0,
                    "endSec": 3,
                    "scriptSummary": "反问式口播建立停滑",
                    "visualSummary": "胸景口播快切产品特写",
                    "intent": "停滑",
                }
            ],
        },
        "slots": [
            {
                "id": "slot-1",
                "segmentId": "seg-1",
                "role": "hook",
            }
        ],
        "rhythm": {"beatPoints": [0, 3], "shotBoundaries": []},
        "evidence": [],
    }
    coerced = coerce_video_structure(
        payload,
        project_id="project-1",
        source_video_id="sample-1",
        analysis={"metadata": {"durationSec": 30.0}, "shots": []},
    )
    slot = coerced["slots"][0]
    assert slot["visualIntent"] == "胸景口播快切产品特写"
    assert slot["scriptIntent"] == "反问式口播建立停滑"
    assert slot["visualIntent"] != slot["scriptIntent"]


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
        "version": "p1-v3",
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
        "version": "p1-v3",
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


def test_coerce_normalizes_direct_route_v3_llm_shapes() -> None:
    payload = {
        "version": "p1-v3",
        "verbal": {
            "hookTemplate": "hook",
            "outlineTimeline": [
                {"phase": "hook", "startSec": 0, "endSec": 17, "sharePct": 10},
                {"phase": "cta", "startSec": 175, "endSec": 181, "sharePct": 5},
            ],
            "ctaMechanism": "关注转化",
        },
        "transfer": {
            "differentiationLever": "第一人称共情",
            "emotionTriggers": [
                {"type": "resonance", "desc": "强共鸣"},
                {"type": "loss_aversion", "desc": "损失危机"},
            ],
        },
        "visual": {
            "cutRateProfile": {
                "avgShotDurationSec": 3.12,
                "rhythmControl": "缓节奏单镜头",
            }
        },
        "audio": {
            "voProfile": {
                "style": "成熟平稳的男性旁白，咬字清晰语速适中",
            }
        },
        "narrative": {
            "summary": "测试结构",
            "segments": [
                {
                    "id": "seg-hook",
                    "role": "hook",
                    "startSec": 0,
                    "endSec": 17,
                    "scriptSummary": "反问开场",
                    "visualSummary": "近景口播",
                    "intent": "共鸣",
                    "transcriptExcerpt": "这不就是",
                },
                {
                    "id": "seg-cta",
                    "role": "cta",
                    "startSec": 175,
                    "endSec": 181,
                    "scriptSummary": "关注引导",
                    "visualSummary": "头像卡片",
                    "intent": "转化",
                    "transcriptExcerpt": "哪里不一样",
                },
            ],
        },
        "rhythm": {"beatPoints": [0, 17, 181], "shotBoundaries": []},
        "slots": [],
        "evidence": [],
    }
    coerced = coerce_video_structure(
        payload,
        project_id="project-1",
        source_video_id="sample-1",
        analysis={
            "metadata": {"durationSec": 181.0},
            "shots": [],
            "structureAnalysisRoute": "direct_multimodal",
        },
    )
    assert coerced["verbal"]["outlineTimeline"][0]["sharePct"] == 0.1
    assert coerced["visual"]["cutRateProfile"]["avgShotSec"] == 3.12
    assert "rhythmControl" not in coerced["visual"]["cutRateProfile"]
    assert coerced["audio"]["voProfile"]["persona"].startswith("成熟平稳")
    assert "style" not in coerced["audio"]["voProfile"]
    trigger = coerced["transfer"]["emotionTriggers"][0]
    assert trigger["triggerType"] == "resonance"
    assert trigger["mechanism"] == "强共鸣"
    assert trigger["segmentId"] == "seg-hook"


def test_coerce_maps_demonstration_alias_to_usage_scene() -> None:
    payload = {
        "narrative": {
            "segments": [
                {
                    "id": "seg-1",
                    "role": "solution",
                    "startSec": 0,
                    "endSec": 5,
                    "scriptSummary": "步骤演示",
                    "visualSummary": "手部操作特写",
                    "intent": "教程",
                }
            ]
        },
        "slots": [
            {
                "id": "slot-1",
                "segmentId": "seg-1",
                "role": "demonstration",
                "visualIntent": "分步操作",
                "scriptIntent": "讲解步骤",
                "importance": "recommended",
            }
        ],
        "evidence": [],
    }
    coerced = coerce_video_structure(
        payload,
        project_id="project-1",
        source_video_id="sample-1",
    )
    assert coerced["slots"][0]["role"] == "usage_scene"


def test_coerce_defaults_packaging_required_asset_type_for_benefit_card() -> None:
    payload = {
        "narrative": {
            "segments": [
                {
                    "id": "seg-1",
                    "role": "benefit",
                    "startSec": 0,
                    "endSec": 3,
                    "scriptSummary": "卖点列举",
                    "visualSummary": "信息卡动效",
                    "intent": "利益点",
                }
            ]
        },
        "slots": [
            {
                "id": "slot-1",
                "segmentId": "seg-1",
                "role": "benefit_card",
                "visualIntent": "三卖点卡片",
                "scriptIntent": "列举卖点",
                "importance": "must_have",
            }
        ],
        "evidence": [],
    }
    coerced = coerce_video_structure(
        payload,
        project_id="project-1",
        source_video_id="sample-1",
    )
    assert coerced["slots"][0]["requiredAssetType"] == ["text", "packaging"]
