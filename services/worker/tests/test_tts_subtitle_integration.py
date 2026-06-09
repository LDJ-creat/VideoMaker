from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.pipelines.generation_pipeline import (
    FixtureMaterialGateway,
    assemble_generation_plan,
    build_asset_inventory,
)
from app.providers.completion_registry import (
    MaterialContext,
    apply_material_results_to_plan,
    execute_completion_plan,
    register_default_providers,
)
from app.render.render_timeline_to_hyperframes import write_composition
from app.runtime.video_gen_quota import VideoGenQuota


class _FixtureGatewayWithConfig(FixtureMaterialGateway):
    def __init__(self) -> None:
        self.config = type("Cfg", (), {"tts_preferences": {}})()


def _load_fixture(name: str) -> dict:
    path = Path(__file__).parent / "fixtures" / "agents" / f"{name}.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _load_structure() -> dict:
    path = Path(__file__).parent / "fixtures" / "structures" / "sample-structure.json"
    return json.loads(path.read_text(encoding="utf-8"))


def test_fixture_pipeline_produces_voiceover_and_subtitles_in_composition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("VIDEOMAKER_TTS_MODE", "per_scene")
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

    plan = assemble_generation_plan(
        structure=structure,
        inventory=inventory,
        gap_report=gap_report,
        slot_matches=slot_matches,
        storyboard=storyboard,
        packaging_plan=packaging_plan,
        master_narration="",
    )

    tts_actions = [a for a in plan["completionActions"] if a.get("provider") == "tts"]
    assert tts_actions
    assert plan.get("ttsMode") == "per_scene"

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
    subtitle_clips = [
        c for c in text_track["clips"] if str(c.get("id", "")).startswith("subtitle-")
    ]
    assert subtitle_clips
    vo_by_slot = {
        str(c.get("id", "")).removeprefix("vo-"): c for c in vo_track["clips"]
    }
    for subtitle in subtitle_clips:
        subtitle_id = str(subtitle.get("id", ""))
        slot_id = subtitle_id.removeprefix("subtitle-").split("-")[0]
        vo_clip = vo_by_slot.get(slot_id)
        if vo_clip is None:
            continue
        assert float(subtitle["endSec"]) <= float(vo_clip["endSec"]) + 0.001

    composition_dir = render_root / "composition"
    write_composition(
        timeline=updated_plan["timeline"],
        composition_dir=composition_dir,
        render_root=render_root,
    )
    html = (composition_dir / "index.html").read_text(encoding="utf-8")
    assert "voiceover-clip" in html
    assert "subtitle-clean" in html
    assert html.count("<audio") >= len(tts_actions)
    assert "node.pause()" in html
    assert (render_root / "materials").is_dir()

    from app.render.timeline_compiler.subtitle_ass import collect_subtitle_clips

    subtitle_clips_after = collect_subtitle_clips(updated_plan["timeline"])
    assert subtitle_clips_after
    assert all(float(c["endSec"]) > float(c["startSec"]) for c in subtitle_clips_after)
