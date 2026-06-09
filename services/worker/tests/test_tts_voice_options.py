from __future__ import annotations

from app.pipelines.tts_voice_options import build_tts_synthesis_options


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
