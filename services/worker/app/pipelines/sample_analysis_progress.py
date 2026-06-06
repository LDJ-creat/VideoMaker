from __future__ import annotations

from collections.abc import Callable
from typing import Any

EmitFn = Callable[..., dict[str, Any]]

# Direct multimodal: perception 5–52%, structure 55–88%, knowledge 92–98%, done 100%.
DIRECT_PERCEPTION_PROGRESS_END = 52
DIRECT_STRUCTURE_PROGRESS_START = 55
DIRECT_STRUCTURE_PROGRESS_VALIDATE = 72
DIRECT_STRUCTURE_PROGRESS_SAVED = 85
DIRECT_KNOWLEDGE_PROGRESS = 92

MAP_REDUCE_PERCEPTION_PROGRESS_END = 82


def map_perception_progress(internal_progress: int, route: str) -> int:
    capped = max(0, min(int(internal_progress), 100))
    end = (
        DIRECT_PERCEPTION_PROGRESS_END
        if route == "direct_multimodal"
        else MAP_REDUCE_PERCEPTION_PROGRESS_END
    )
    return 5 + int(capped * (end - 5) / 100)


def make_sample_pipeline_publisher(emit: EmitFn, route: str) -> Callable[[dict[str, Any]], None]:
    perception_end = (
        DIRECT_PERCEPTION_PROGRESS_END
        if route == "direct_multimodal"
        else MAP_REDUCE_PERCEPTION_PROGRESS_END
    )

    def publish(event: dict[str, Any]) -> None:
        stage = str(event.get("stage") or "extracting_metadata")
        status = str(event.get("status") or "running")
        message = str(event.get("message") or "")
        progress = int(event.get("progress") or 0)

        if status == "failed":
            emit(
                status="failed",
                stage=stage,
                progress=map_perception_progress(progress, route),
                message=message,
                error=event.get("error"),
            )
            return

        if status == "succeeded" and stage == "completed":
            emit(
                status="running",
                stage="consolidating",
                progress=perception_end,
                message="Perception complete, preparing structure analysis",
            )
            return

        emit(
            status="running",
            stage=stage,
            progress=map_perception_progress(progress, route),
            message=message,
        )

    return publish
