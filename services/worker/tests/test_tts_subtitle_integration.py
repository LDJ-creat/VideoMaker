from __future__ import annotations

import io
import json
import struct
import wave
from pathlib import Path

import pytest

from app.pipelines.generation_pipeline import (
    FixtureMaterialGateway,
    assemble_generation_plan,
    build_asset_inventory,
)
from app.pipelines.tts_mode import MASTER_TTS_SLOT_ID, VO_MASTER_CLIP_ID
from app.providers.completion_registry import (
    MaterialContext,
    apply_material_results_to_plan,
    execute_completion_plan,
    register_default_providers,
)
from app.render.render_timeline_to_hyperframes import write_composition
from app.runtime.video_gen_quota import VideoGenQuota


class _FixtureGatewayWithConfig(FixtureMaterialGateway):
    def synthesize_speech(self, text: str, *, options: dict | None = None) -> bytes:
        _ = text, options
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as handle:
            handle.setnchannels(1)
            handle.setsampwidth(2)
            handle.setframerate(24000)
            handle.writeframes(struct.pack("<h", 0) * 2400)
        return buffer.getvalue()


def _load_fixture(name: str) -> dict:
    path = Path(__file__).parent / "fixtures" / "agents" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_structure() -> dict:
    path = Path(__file__).parent / "fixtures" / "structures" / "sample-structure.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_fixture_pipeline_produces_voiceover_and_subtitles_in_composition(
    tmp_path: Path,
) -> None:
    structure = _load_structure()
    inventory = build_asset_inventory(
        project_id="project-1",
        user_brief={
            "topic": "便携果汁机",
            "productName": "JuiceGo",
            "sellingPoints": ["便携"],
            "targetAudience": "上班族",
            "mustMention": [],
            "avoidMention": [],
        },
        assets=[],
    )
    gap_report = _load_fixture("gap_planner")
    slot_matches = _load_fixture("slot_mapper")["slotMatches"]
    storyboard = _load_fixture("storyboard_writer")["storyboard"]
    packaging_plan = _load_fixture("packaging_designer")["packagingPlan"]
    master_narration = "全片口播测试文案。"

    plan = assemble_generation_plan(
        structure=structure,
        inventory=inventory,
        gap_report=gap_report,
        slot_matches=slot_matches,
        storyboard=storyboard,
        packaging_plan=packaging_plan,
        master_narration=master_narration,
    )

    tts_actions = [a for a in plan["completionActions"] if a.get("provider") == "tts"]
    assert tts_actions
    assert plan.get("ttsMode") == "global"
    assert tts_actions[0]["slotId"] == MASTER_TTS_SLOT_ID

    generation_root = tmp_path / "generations" / "gen-1"
    render_root = tmp_path / "renders" / "gen-1"
    generated_root = generation_root / "generated"
    generated_root.mkdir(parents=True)
    render_root.mkdir(parents=True)

    ctx = MaterialContext(
        project_id="project-1",
        generation_id="gen-1",
        render_root=render_root,
        generated_root=generated_root,
        gateway=_FixtureGatewayWithConfig(),  # type: ignore[arg-type]
        quota=VideoGenQuota(),
        inventory=inventory,
        slot_matches=slot_matches,
        storyboard=storyboard,
        structure=structure,
        emit_progress=lambda *_args: None,
        register_artifact=lambda artifact_type, path: {
            "id": f"art-{Path(path).name}",
            "type": artifact_type,
            "uri": str(Path(path).resolve()),
            "createdAt": "2026-06-02T00:00:00Z",
        },
        master_narration=master_narration,
    )
    register_default_providers(ctx)
    results = execute_completion_plan(tts_actions, ctx)
    assert results
    assert all(item.get("ok") for item in results)

    updated_plan = apply_material_results_to_plan(plan, results=results, render_root=render_root)

    vo_track = next(
        t for t in updated_plan["timeline"]["tracks"] if t["type"] == "voiceover"
    )
    text_track = next(t for t in updated_plan["timeline"]["tracks"] if t["type"] == "text")
    assert vo_track["clips"]
    assert vo_track["clips"][0]["id"] == VO_MASTER_CLIP_ID
    subtitle_clips = [
        c for c in text_track["clips"] if str(c.get("id", "")).startswith("subtitle-")
    ]
    assert subtitle_clips

    composition_dir = render_root / "composition"
    write_composition(
        timeline=updated_plan["timeline"],
        composition_dir=composition_dir,
        render_root=render_root,
    )
    html = (composition_dir / "index.html").read_text(encoding="utf-8")
    assert "voiceover-clip" in html
    assert "subtitle-clean" in html
    assert html.count("<audio") >= 1
    assert "node.pause()" in html
    assert (render_root / "materials").is_dir()

    from app.render.timeline_compiler.subtitle_ass import collect_subtitle_clips

    subtitle_clips_after = collect_subtitle_clips(updated_plan["timeline"])
    assert subtitle_clips_after
    assert all(float(c["endSec"]) > float(c["startSec"]) for c in subtitle_clips_after)
