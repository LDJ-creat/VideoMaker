from __future__ import annotations

from pathlib import Path

from app.services.generation_responses import (
    build_latest_generations_response,
    generation_render_video_url,
)


def test_generation_render_video_url_when_mp4_exists(tmp_path: Path) -> None:
    project_id = "proj-1"
    generation_id = "gen-1"
    mp4 = (
        tmp_path
        / "projects"
        / project_id
        / "renders"
        / generation_id
        / "output.mp4"
    )
    mp4.parent.mkdir(parents=True, exist_ok=True)
    mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    url = generation_render_video_url(tmp_path, project_id, generation_id)
    assert url == f"/api/projects/{project_id}/media/file/renders/{generation_id}/output.mp4"


def test_latest_generations_includes_render_video_url(tmp_path: Path) -> None:
    project_id = "proj-1"
    generation_id = "gen-1"
    mp4 = (
        tmp_path
        / "projects"
        / project_id
        / "renders"
        / generation_id
        / "output.mp4"
    )
    mp4.parent.mkdir(parents=True, exist_ok=True)
    mp4.write_bytes(b"\x00\x00\x00\x18ftypmp42")

    records = [
        {
            "id": generation_id,
            "projectId": project_id,
            "variant": "high_click",
            "plan": {"id": generation_id, "projectId": project_id, "variant": "high_click"},
        }
    ]
    payload = build_latest_generations_response(records, storage_root=tmp_path)
    entry = payload["generations"][0]
    assert "renderVideoUrl" in entry
    assert entry["renderVideoUrl"].endswith("output.mp4")
