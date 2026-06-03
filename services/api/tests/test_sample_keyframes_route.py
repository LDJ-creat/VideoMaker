from __future__ import annotations

import json


def test_get_sample_keyframes_returns_preview_urls(client, app, app_paths) -> None:
    from app.services.project_store import ProjectStore

    project_id = client.post("/api/projects", json={"name": "Keyframes"}).json()["id"]
    store = ProjectStore(app.state.db)
    sample = store.create_sample(
        project_id,
        source_kind="local",
        file_name="source.mp4",
        video_uri=str(
            app_paths["storage_root"]
            / "projects"
            / project_id
            / "samples"
            / "placeholder"
            / "source.mp4"
        ),
    )
    sample_id = sample["id"]

    analysis_root = (
        app_paths["storage_root"]
        / "projects"
        / project_id
        / "samples"
        / sample_id
        / "analysis"
    )
    keyframes_dir = analysis_root / "keyframes"
    keyframes_dir.mkdir(parents=True)
    image_path = keyframes_dir / "shot-0-1866.jpg"
    image_path.write_bytes(b"jpeg-bytes")
    (analysis_root / "keyframes.json").write_text(
        json.dumps(
            [
                {
                    "shotId": "shot-0",
                    "timeSec": 1.866,
                    "path": str(image_path),
                    "score": 0.82,
                    "width": 720,
                    "height": 960,
                }
            ]
        ),
        encoding="utf-8",
    )

    response = client.get(f"/api/samples/{sample_id}/keyframes")
    assert response.status_code == 200
    payload = response.json()
    assert payload["sampleId"] == sample_id
    assert len(payload["keyframes"]) == 1
    assert payload["keyframes"][0]["previewUrl"].endswith(
        f"samples/{sample_id}/analysis/keyframes/shot-0-1866.jpg"
    )
