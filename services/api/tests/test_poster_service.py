from __future__ import annotations

import json
from pathlib import Path

from app.services.poster_service import (
    pick_category_cover_url,
    pick_project_cover_url,
    sample_poster_media_url,
)
from app.services.project_store import ProjectStore
from app.services.sample_selection_store import SampleSelectionStore


def _write_poster(storage_root: Path, project_id: str, sample_id: str) -> None:
    poster = (
        storage_root
        / "projects"
        / project_id
        / "samples"
        / sample_id
        / "poster.jpg"
    )
    poster.parent.mkdir(parents=True, exist_ok=True)
    poster.write_bytes(b"poster")


def _write_keyframe_poster(storage_root: Path, project_id: str, sample_id: str) -> None:
    analysis_root = (
        storage_root
        / "projects"
        / project_id
        / "samples"
        / sample_id
        / "analysis"
    )
    keyframes_dir = analysis_root / "keyframes"
    keyframes_dir.mkdir(parents=True)
    image_path = keyframes_dir / "frame.jpg"
    image_path.write_bytes(b"jpeg")
    (analysis_root / "keyframes.json").write_text(
        json.dumps(
            [
                {
                    "timeSec": 1.0,
                    "path": str(image_path),
                    "score": 0.9,
                    "width": 720,
                    "height": 1280,
                }
            ]
        ),
        encoding="utf-8",
    )


def test_sample_poster_media_url_prefers_poster_jpg(tmp_path: Path) -> None:
    project_id = "proj-1"
    sample_id = "sample-1"
    _write_poster(tmp_path, project_id, sample_id)
    _write_keyframe_poster(tmp_path, project_id, sample_id)

    url = sample_poster_media_url(
        tmp_path,
        project_id=project_id,
        sample_id=sample_id,
    )
    assert url == f"/api/projects/{project_id}/media/file/samples/{sample_id}/poster.jpg"


def test_sample_poster_media_url_falls_back_to_keyframes(tmp_path: Path) -> None:
    project_id = "proj-1"
    sample_id = "sample-1"
    _write_keyframe_poster(tmp_path, project_id, sample_id)

    url = sample_poster_media_url(
        tmp_path,
        project_id=project_id,
        sample_id=sample_id,
    )
    assert url is not None
    assert url.endswith("analysis/keyframes/frame.jpg")


def test_pick_project_cover_url_prefers_generation_poster(app, app_paths) -> None:
    store = ProjectStore(app.state.db)
    selection_store = SampleSelectionStore(app.state.db)
    project = store.create_project("Cover test")
    project_id = project["id"]

    sample = store.create_sample(project_id=project_id, source_kind="local", status="uploaded")
    _write_poster(app_paths["storage_root"], project_id, str(sample["id"]))

    generation = store.create_generation(project_id=project_id, status="completed")
    generation_id = generation["id"]
    render_root = (
        app_paths["storage_root"]
        / "projects"
        / project_id
        / "renders"
        / generation_id
    )
    render_root.mkdir(parents=True)
    (render_root / "output.mp4").write_bytes(b"mp4")
    (render_root / "poster.jpg").write_bytes(b"render-poster")

    cover = pick_project_cover_url(
        app_paths["storage_root"],
        store,
        selection_store,
        project_id,
    )
    assert cover == f"/api/projects/{project_id}/media/file/renders/{generation_id}/poster.jpg"


def test_pick_project_cover_url_uses_primary_sample(app, app_paths) -> None:
    store = ProjectStore(app.state.db)
    selection_store = SampleSelectionStore(app.state.db)
    project = store.create_project("Sample cover")
    project_id = project["id"]

    first = store.create_sample(project_id=project_id, source_kind="local", status="uploaded")
    second = store.create_sample(project_id=project_id, source_kind="local", status="uploaded")
    _write_poster(app_paths["storage_root"], project_id, str(second["id"]))

    selection_store.save_selection(
        {
            "projectId": project_id,
            "primarySampleId": str(first["id"]),
            "referenceSampleIds": [str(second["id"])],
            "mode": "manual",
        }
    )

    cover = pick_project_cover_url(
        app_paths["storage_root"],
        store,
        selection_store,
        project_id,
    )
    assert cover == (
        f"/api/projects/{project_id}/media/file/samples/{second['id']}/poster.jpg"
    )


def test_pick_category_cover_url_uses_first_importable_with_poster(app, app_paths) -> None:
    store = ProjectStore(app.state.db)
    project = store.create_project("Category source")
    project_id = project["id"]
    sample = store.create_sample(project_id=project_id, source_kind="local", status="analyzed")
    sample_id = str(sample["id"])
    _write_poster(app_paths["storage_root"], project_id, sample_id)

    entries = [
        {
            "id": "entry-new",
            "sourceProjectId": project_id,
            "sourceSampleId": sample_id,
            "updatedAt": "2026-06-10T00:00:00Z",
        },
        {
            "id": "entry-old",
            "sourceProjectId": "missing-project",
            "sourceSampleId": "missing-sample",
            "updatedAt": "2026-06-01T00:00:00Z",
        },
    ]

    def assess(entry: dict, project_store: ProjectStore) -> tuple[bool, str | None]:
        if entry["id"] == "entry-new":
            return True, None
        return False, "missing source"

    cover = pick_category_cover_url(
        entries,
        store,
        app_paths["storage_root"],
        assess_importable=assess,
    )
    assert cover == f"/api/projects/{project_id}/media/file/samples/{sample_id}/poster.jpg"
