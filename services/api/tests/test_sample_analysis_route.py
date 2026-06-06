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
        "metadataPath": "legacy/metadata.json",
        "metadata": {"durationSec": 12.0},
        "transcript": {"segments": []},
        "shots": [],
        "keyframes": [],
        "locale": "zh",
        "audioProfile": {
            "hasVoiceover": False,
            "hasBgm": False,
            "metrics": {},
            "energyTimeline": [{"timeSec": 0.0, "rmsDb": -10.0}],
        },
        "keyframeBatchDigests": [
            {
                "batchIndex": 0,
                "startSec": 0.0,
                "endSec": 4.0,
                "visualFacts": "full digest body",
                "onScreenTextFacts": [],
            }
        ],
    }
    (analysis_root / "sample-analysis.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    response = client.get(f"/api/samples/{sample_id}/sample-analysis")
    assert response.status_code == 200
    body = response.json()
    assert body["locale"] == "zh"
    assert "metadataPath" not in body
    assert "energyTimeline" not in body["audioProfile"]
    assert body["keyframeBatchDigests"] == [
        {
            "batchIndex": 0,
            "startSec": 0.0,
            "endSec": 4.0,
            "digestRef": "batch-digests/batch-0.json",
        }
    ]


def test_get_sample_analysis_include_expands_sidecars(
    client: TestClient,
    app_paths,
) -> None:
    project = client.post("/api/projects", json={"name": "Include Project"}).json()
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
    (analysis_root / "batch-digests").mkdir(parents=True, exist_ok=True)
    (analysis_root / "batch-digests" / "batch-0.json").write_text(
        json.dumps(
            {
                "visualFacts": "full digest body",
                "onScreenTextFacts": [{"timeSec": 1.0, "text": "限时", "confidence": 0.9}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (analysis_root / "audio-profile-full.json").write_text(
        json.dumps(
            {
                "hasVoiceover": True,
                "hasBgm": True,
                "metrics": {"voiceoverCoveragePct": 0.8},
                "energyTimeline": [{"timeSec": 0.0, "rmsDb": -10.0}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    payload = {
        "metadata": {"durationSec": 12.0},
        "transcript": {"segments": []},
        "shots": [],
        "keyframes": [],
        "locale": "zh",
        "audioProfile": {
            "hasVoiceover": True,
            "hasBgm": True,
            "metrics": {"voiceoverCoveragePct": 0.8},
        },
        "keyframeBatchDigests": [
            {
                "batchIndex": 0,
                "startSec": 0.0,
                "endSec": 4.0,
                "digestRef": "batch-digests/batch-0.json",
            }
        ],
    }
    (analysis_root / "sample-analysis.json").write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )

    response = client.get(
        f"/api/samples/{sample_id}/sample-analysis?include=audioFull,digestFull"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["audioProfile"]["energyTimeline"][0]["rmsDb"] == -10.0
    assert body["keyframeBatchDigests"][0]["visualFacts"] == "full digest body"


def test_get_sample_structure_rejects_legacy_version(client: TestClient) -> None:
    project = client.post("/api/projects", json={"name": "Legacy Structure"}).json()
    project_id = project["id"]
    sample = client.post(
        f"/api/projects/{project_id}/samples/upload",
        files={"file": ("demo.mp4", b"fake", "video/mp4")},
    ).json()
    sample_id = sample["id"]

    from app.services.project_store import ProjectStore

    store = ProjectStore(client.app.state.db)  # type: ignore[attr-defined]
    store.update_sample(
        sample_id,
        structure={"version": "p1-v2", "projectId": project_id, "id": "legacy"},
    )

    response = client.get(f"/api/samples/{sample_id}/structure")
    assert response.status_code == 409
    assert "p1-v3" in response.json()["detail"]


def test_get_sample_structure_hydrates_from_disk_artifact(
    client: TestClient,
    app_paths,
) -> None:
    project = client.post("/api/projects", json={"name": "Disk Structure"}).json()
    project_id = project["id"]
    sample = client.post(
        f"/api/projects/{project_id}/samples/upload",
        files={"file": ("demo.mp4", b"fake", "video/mp4")},
    ).json()
    sample_id = sample["id"]

    structure = {
        "id": f"video-structure-{sample_id}",
        "projectId": project_id,
        "sourceVideoId": sample_id,
        "version": "p1-v3",
        "metadata": {"durationSec": 12.0, "hasAudio": True},
        "narrative": {"summary": "hook → cta", "segments": []},
        "rhythm": {
            "totalDurationSec": 12.0,
            "shotCount": 1,
            "avgShotDurationSec": 12.0,
            "tempo": "slow",
            "beatPoints": [0.0, 12.0],
            "shotBoundaries": [],
        },
        "slots": [],
        "evidence": [],
        "confidence": 0.8,
    }
    analysis_root = (
        app_paths["storage_root"]
        / "projects"
        / project_id
        / "samples"
        / sample_id
        / "analysis"
    )
    analysis_root.mkdir(parents=True, exist_ok=True)
    (analysis_root / "video-structure.json").write_text(
        json.dumps(structure, ensure_ascii=False),
        encoding="utf-8",
    )

    response = client.get(f"/api/samples/{sample_id}/structure")
    assert response.status_code == 200
    assert response.json()["version"] == "p1-v3"

    from app.services.project_store import ProjectStore

    store = ProjectStore(client.app.state.db)  # type: ignore[attr-defined]
    persisted = store.get_sample(sample_id)
    assert persisted is not None
    assert persisted.get("structure", {}).get("version") == "p1-v3"
    assert persisted.get("status") == "analyzed"
