from __future__ import annotations

from app.pipelines.sample_analysis_progress import (
    make_sample_pipeline_publisher,
    map_perception_progress,
)


def test_map_perception_progress_direct_route() -> None:
    assert map_perception_progress(15, "direct_multimodal") == 12
    assert map_perception_progress(30, "direct_multimodal") == 19
    assert map_perception_progress(80, "direct_multimodal") == 42
    assert map_perception_progress(100, "direct_multimodal") == 52


def test_sample_pipeline_publisher_maps_completed_to_consolidating() -> None:
    events: list[dict] = []

    def emit(**kwargs):
        events.append(kwargs)
        return kwargs

    publish = make_sample_pipeline_publisher(emit, "direct_multimodal")
    publish(
        {
            "stage": "completed",
            "status": "succeeded",
            "progress": 100,
            "message": "sample analysis completed",
        }
    )

    assert events[-1]["stage"] == "consolidating"
    assert events[-1]["status"] == "running"
    assert events[-1]["progress"] == 52
