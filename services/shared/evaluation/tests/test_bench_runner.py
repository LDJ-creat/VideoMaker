from __future__ import annotations

import json
from pathlib import Path

from evaluation.artifacts import slot_match_items, storyboard_scenes
from evaluation.final_video_qa import run_final_video_qa
from evaluation.migration_scorer import score_migration
from evaluation.observability_rollup import rollup_model_calls
from evaluation.plan_quality import score_plan_quality
from evaluation.profile_resolver import resolve_evaluation_profile
from evaluation.report_builder import build_evaluation_report
from evaluation.usage_normalize import normalize_chat_usage


def _fixture_generation_root(tmp_path: Path) -> tuple[Path, str, str]:
    project_id = "proj-bench"
    generation_id = "gen-bench"
    root = tmp_path / "storage" / "projects" / project_id / "generations" / generation_id
    root.mkdir(parents=True, exist_ok=True)
    (root / "generation-plan.json").write_text(
        json.dumps(
            {
                "id": generation_id,
                "projectId": project_id,
                "storyboard": [
                    {"slotId": "hook", "role": "hook_visual", "script": "hello"},
                    {"slotId": "body", "role": "usage_scene", "script": "world"},
                ],
                "timeline": {"durationSec": 30},
            }
        ),
        encoding="utf-8",
    )
    (root / "gap-report.json").write_text(
        json.dumps({"slots": [{"slotId": "hook", "status": "matched"}]}),
        encoding="utf-8",
    )
    (root / "slot-matches.json").write_text(
        json.dumps({"slotMatches": [{"slotId": "hook", "status": "matched"}]}),
        encoding="utf-8",
    )
    (root / "checkpoint.json").write_text(
        json.dumps(
            {
                "generationId": generation_id,
                "stageTimings": [
                    {
                        "stage": "mapping_slots",
                        "durationMs": 1200,
                        "status": "completed",
                    },
                    {
                        "stage": "awaiting_master_review",
                        "durationMs": 5000,
                        "status": "paused",
                        "kind": "human_gate",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return tmp_path / "storage", project_id, generation_id


def _write_model_calls(storage_root: Path, project_id: str, generation_id: str) -> None:
    log_dir = storage_root / "projects" / project_id / "logs" / "model-calls"
    log_dir.mkdir(parents=True, exist_ok=True)
    calls = [
        {
            "id": "c1",
            "callKind": "chat_json",
            "profile": "text",
            "model": "gpt-test",
            "driver": "openai_compatible",
            "outputValid": True,
            "latencyMs": 100,
            "createdAt": "2026-07-04T00:00:00Z",
            "generationId": generation_id,
            "usageUnits": {"kind": "tokens", "prompt": 10, "completion": 20, "total": 30},
        },
        {
            "id": "c2",
            "callKind": "tts",
            "profile": "tts",
            "model": "tts-test",
            "driver": "openai_compatible",
            "outputValid": True,
            "latencyMs": 50,
            "createdAt": "2026-07-04T00:00:01Z",
            "generationId": generation_id,
            "usageUnits": {"kind": "chars", "chars": 120},
        },
    ]
    for call in calls:
        (log_dir / f"{call['id']}.json").write_text(json.dumps(call), encoding="utf-8")


def test_normalize_chat_usage_aliases() -> None:
    usage = normalize_chat_usage({"input_tokens": 5, "output_tokens": 7})
    assert usage["prompt"] == 5
    assert usage["completion"] == 7
    assert usage["total"] == 12


def test_storyboard_scenes_array_shape() -> None:
    plan = {"storyboard": [{"slotId": "hook", "role": "hook_visual"}]}
    scenes = storyboard_scenes(plan)
    assert len(scenes) == 1
    assert scenes[0]["slotId"] == "hook"


def test_slot_match_items_reads_slot_matches_key() -> None:
    payload = {"slotMatches": [{"slotId": "hook"}]}
    items = slot_match_items(payload)
    assert len(items) == 1
    assert items[0]["slotId"] == "hook"


def test_plan_quality_with_array_storyboard(tmp_path: Path) -> None:
    storage_root, project_id, generation_id = _fixture_generation_root(tmp_path)
    root = storage_root / "projects" / project_id / "generations" / generation_id
    result = score_plan_quality(root)
    assert result["sceneCount"] == 2
    assert "missing_storyboard_scenes" not in result["issues"]


def test_migration_scorer_reads_slot_matches(tmp_path: Path) -> None:
    storage_root, project_id, generation_id = _fixture_generation_root(tmp_path)
    root = storage_root / "projects" / project_id / "generations" / generation_id
    structure = {"slots": [{"id": "hook", "role": "hook_visual"}]}
    result = score_migration(root, structure)
    assert result["slotCoverage"] >= 1.0


def _d6_like_structure() -> dict:
    return {
        "slots": [
            {"id": "slot-1", "segmentId": "seg-1", "role": "hook_visual"},
            {"id": "slot-2", "segmentId": "seg-2", "role": "proof"},
            {"id": "slot-3", "segmentId": "seg-3", "role": "proof"},
            {"id": "slot-4", "segmentId": "seg-4", "role": "benefit_card"},
            {"id": "slot-5", "segmentId": "seg-5", "role": "benefit_card"},
            {"id": "slot-6", "segmentId": "seg-6", "role": "cta"},
        ],
        "narrative": {
            "segments": [
                {
                    "id": "seg-1",
                    "role": "hook",
                    "transcriptExcerpt": "这是我看到过最强大的心理暗示，就4句话分享给你。",
                }
            ]
        },
        "verbal": {
            "hookTemplate": "开篇直接抛出高价值标签加数量限定的干货承诺，快速拉满用户期待感，引导用户继续观看。"
        },
        "evidence": [
            {"targetId": "seg-1", "source": "asr", "summary": "hook", "confidence": 0.8},
            {"targetId": "seg-2", "source": "asr", "summary": "proof", "confidence": 0.8},
        ],
    }


def test_migration_role_preservation_resolves_from_slot_id(tmp_path: Path) -> None:
    storage_root, project_id, generation_id = _fixture_generation_root(tmp_path)
    root = storage_root / "projects" / project_id / "generations" / generation_id
    (root / "generation-plan.json").write_text(
        json.dumps(
            {
                "storyboard": [
                    {"slotId": f"slot-{i}", "script": f"scene-{i}"}
                    for i in range(1, 7)
                ]
            }
        ),
        encoding="utf-8",
    )
    result = score_migration(root, _d6_like_structure())
    assert result["rolePreservation"] == 1.0
    assert "low_role_preservation" not in str(result["issues"])


def test_migration_evidence_binding_uses_target_id(tmp_path: Path) -> None:
    storage_root, project_id, generation_id = _fixture_generation_root(tmp_path)
    root = storage_root / "projects" / project_id / "generations" / generation_id
    (root / "generation-plan.json").write_text(
        json.dumps({"storyboard": [{"slotId": "slot-1"}, {"slotId": "slot-2"}]}),
        encoding="utf-8",
    )
    result = score_migration(root, _d6_like_structure())
    assert result["evidenceBinding"] == 1.0


def test_migration_hook_pattern_rewards_structure_not_literal_copy(tmp_path: Path) -> None:
    storage_root, project_id, generation_id = _fixture_generation_root(tmp_path)
    root = storage_root / "projects" / project_id / "generations" / generation_id
    (root / "generation-plan.json").write_text(
        json.dumps(
            {
                "storyboard": [{"slotId": f"slot-{i}"} for i in range(1, 7)],
                "masterNarration": (
                    "想摆脱贫穷思维？4句搞钱认知金句，帮你打破打工固有思维！"
                    "第一句：赚钱拼的不是死时长，是认知与不可替代性。"
                    "第二句：别只靠工资存钱，被动收入才拉开贫富差距。"
                ),
            }
        ),
        encoding="utf-8",
    )
    (root / "script-draft.json").write_text(
        json.dumps(
            {
                "masterNarration": (
                    "想摆脱贫穷思维？4句搞钱认知金句，帮你打破打工固有思维！"
                    "第一句：赚钱拼的不是死时长，是认知与不可替代性。"
                    "第二句：别只靠工资存钱，被动收入才拉开贫富差距。"
                )
            }
        ),
        encoding="utf-8",
    )
    result = score_migration(root, _d6_like_structure())
    assert result["hookPatternPreservation"] >= 0.85
    assert result["contentCopyRisk"] < 0.2
    assert result["weighted"] >= 90.0


def test_migration_content_copy_risk_flags_literal_reuse(tmp_path: Path) -> None:
    storage_root, project_id, generation_id = _fixture_generation_root(tmp_path)
    root = storage_root / "projects" / project_id / "generations" / generation_id
    copied_hook = "这是我看到过最强大的心理暗示，就4句话分享给你。"
    (root / "script-draft.json").write_text(
        json.dumps({"masterNarration": copied_hook}),
        encoding="utf-8",
    )
    (root / "generation-plan.json").write_text(
        json.dumps({"storyboard": [{"slotId": "slot-1", "script": copied_hook}]}),
        encoding="utf-8",
    )
    result = score_migration(root, _d6_like_structure())
    assert result["contentCopyRisk"] >= 0.5
    assert any("high_content_copy_risk" in issue for issue in result["issues"])


def test_rollup_model_calls_categories(tmp_path: Path) -> None:
    storage_root, project_id, generation_id = _fixture_generation_root(tmp_path)
    _write_model_calls(storage_root, project_id, generation_id)
    log_dir = storage_root / "projects" / project_id / "logs" / "model-calls"
    calls = [json.loads(path.read_text(encoding="utf-8")) for path in log_dir.glob("*.json")]
    rollup = rollup_model_calls(calls)
    assert rollup["usageByCategory"]["text_chat"]["totalTokens"] == 30
    assert rollup["usageByCategory"]["tts"]["totalChars"] == 120


def test_build_evaluation_report_partial_technical_null(tmp_path: Path) -> None:
    storage_root, project_id, generation_id = _fixture_generation_root(tmp_path)
    _write_model_calls(storage_root, project_id, generation_id)
    report = build_evaluation_report(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
        partial=True,
    )
    assert report["partial"] is True
    assert report["scores"]["core"]["technical"] is None


def test_build_evaluation_report_greenfield(tmp_path: Path) -> None:
    storage_root, project_id, generation_id = _fixture_generation_root(tmp_path)
    _write_model_calls(storage_root, project_id, generation_id)
    report = build_evaluation_report(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
        partial=False,
    )
    assert report["version"] == "1.0"
    assert report["observability"]["timing"]["wallClock"]["humanWaitMs"] == 5000


def test_final_video_qa_technical_block(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("VIDEOMAKER_EVAL_TECHNICAL_BLOCK", "true")
    mp4 = tmp_path / "tiny.mp4"
    mp4.write_bytes(b"not-a-real-mp4")
    result = run_final_video_qa(mp4, target_duration_sec=30)
    assert result["blockingIssues"]


def test_profile_resolver_greenfield(tmp_path: Path) -> None:
    storage_root, project_id, generation_id = _fixture_generation_root(tmp_path)
    generation_root = storage_root / "projects" / project_id / "generations" / generation_id
    profile = resolve_evaluation_profile(generation_root)
    assert "core" in profile["enabledModules"]
