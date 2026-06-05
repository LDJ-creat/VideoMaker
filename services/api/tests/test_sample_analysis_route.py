from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient


def test_get_sample_analysis_facts_route(client: TestClient, app_paths) -> None:
    project = client.post("/api/projects", json={"name": "Sample Facts Project"}).json()
    project_id = project["id"]
    sample = client.post(
        f"/api/projects/{project_id}/samples/upload",
        files={"file": ("demo.mp4", b"fake", "video/mp4")},
    ).json()
    sample_id = sample["id"]

    analysis_root = (
        app_paths["storage_root"]
        / "projects"
        / project_id
        / "samples"
        / sample_id
        / "analysis"
    )
    analysis_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "metadata": {"durationSec": 12.0},
        "transcript": {"segments": []},
        "shots": [],
        "keyframes": [],
        "locale": "zh",
        "audioProfile": {"hasVoiceover": False, "hasBgm": False, "metrics": {}},
    }
    (analysis_root / "sample-analysis.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    response = client.get(f"/api/samples/{sample_id}/sample-analysis")
    assert response.status_code == 200
    body = response.json()
    assert body["locale"] == "zh"
    assert "audioProfile" in body
