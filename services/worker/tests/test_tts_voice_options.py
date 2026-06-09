from __future__ import annotations

from app.pipelines.tts_voice_options import (
    build_tts_synthesis_options,
    normalize_vo_directive,
    report_vo_directive_warnings,
)


def test_build_tts_synthesis_options_maps_vo_profile() -> None:
    structure = {
        "audio": {
            "voProfile": {
                "pace": "fast",
                "energy": "high",
                "persona": "带货主播",
            }
        }
    }
    workbench = {
        "resourceId": "seed-tts-2.0",
        "speaker": "zh_female_vv_uranus_bigtts",
        "modelVariant": "seed-tts-2.0-expressive",
        "speechRate": 0,
        "loudnessRate": 0,
        "emotion": None,
        "emotionScale": 4,
        "contextTexts": "句末收束",
        "explicitLanguage": "zh",
        "format": "pcm",
        "sampleRate": 24000,
        "chunkCharLimit": 400,
    }
    options = build_tts_synthesis_options(
        structure=structure,
        workbench_prefs=workbench,
        generation_id="gen-abc",
    )
    assert options["speechRate"] == 30
    assert "带货主播" in options["contextTexts"]
    assert "更有感染力" in options["contextTexts"]
    assert "句末收束" in options["contextTexts"]
    assert options["generationId"] == "gen-abc"


def test_build_tts_synthesis_options_narration_overrides_sample() -> None:
    structure = {
        "audio": {
            "voProfile": {
                "pace": "medium",
                "persona": "科普博主",
            }
        }
    }
    workbench = {
        "resourceId": "seed-tts-2.0",
        "speaker": "zh_female_vv_uranus_bigtts",
        "modelVariant": "seed-tts-2.0-expressive",
        "speechRate": 0,
        "loudnessRate": 0,
        "emotion": None,
        "emotionScale": 4,
        "contextTexts": "句末收束",
        "explicitLanguage": "zh",
        "format": "pcm",
        "sampleRate": 24000,
        "chunkCharLimit": 400,
    }
    options = build_tts_synthesis_options(
        structure=structure,
        workbench_prefs=workbench,
        generation_id="gen-1",
        narration_vo_profile={"pace": "fast"},
        scene_vo_directive={"pace": "slow", "contextHint": "收束"},
    )
    assert options["speechRate"] == -25
    assert "收束" in options["contextTexts"]
    assert "科普博主" in options["contextTexts"]


def test_build_tts_synthesis_options_includes_structure_context_hint() -> None:
    structure = {
        "audio": {
            "voProfile": {
                "contextHint": "样本层提示",
                "persona": "科普博主",
            }
        }
    }
    workbench = {
        "resourceId": "seed-tts-2.0",
        "speaker": "zh_female_vv_uranus_bigtts",
        "modelVariant": "seed-tts-2.0-expressive",
        "speechRate": 0,
        "loudnessRate": 0,
        "emotion": None,
        "emotionScale": 4,
        "contextTexts": "工作台基线",
        "explicitLanguage": "zh",
        "format": "pcm",
        "sampleRate": 24000,
        "chunkCharLimit": 400,
    }
    options = build_tts_synthesis_options(
        structure=structure,
        workbench_prefs=workbench,
        generation_id="gen-1",
        scene_vo_directive={"contextHint": "分镜提示"},
    )
    parts = options["contextTexts"].split("；")
    assert parts[0] == "工作台基线"
    assert parts.index("样本层提示") < parts.index("分镜提示")
    assert "以科普博主" in options["contextTexts"]


def test_report_vo_directive_warnings_dedupes_messages() -> None:
    emitted: list[tuple[str, str]] = []
    report_vo_directive_warnings(
        ["invalid_vo_directive_pace:turbo", "invalid_vo_directive_pace:turbo"],
        emit_progress=lambda stage, message: emitted.append((stage, message)),
    )
    assert emitted == [("vo_directive_normalized", "invalid_vo_directive_pace:turbo")]


def test_build_tts_synthesis_options_workbench_emotion() -> None:
    options = build_tts_synthesis_options(
        structure={},
        workbench_prefs={
            "resourceId": "seed-tts-2.0",
            "speaker": "zh_female_vv_uranus_bigtts",
            "modelVariant": "seed-tts-2.0-expressive",
            "speechRate": 5,
            "loudnessRate": 0,
            "emotion": "happy",
            "emotionScale": 4,
            "contextTexts": "",
            "explicitLanguage": "zh",
            "format": "pcm",
            "sampleRate": 24000,
            "chunkCharLimit": 400,
        },
        generation_id="gen-1",
    )
    assert options["emotion"] == "happy"
    assert options["speechRate"] == 5
