from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path
from typing import Any
from urllib import request

from app.tools.whisper_tool import configure_whisper_runtime


def _post_task_event(api_base_url: str, task_id: str, **fields: Any) -> None:
    endpoint = api_base_url.rstrip("/") + f"/api/tasks/{task_id}/events"
    payload = json.dumps(fields).encode("utf-8")
    req = request.Request(
        endpoint,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with request.urlopen(req, timeout=10):
        return


def _emit_factory(api_base_url: str, task_id: str):
    def emit(**kwargs: Any) -> dict[str, Any]:
        body = {
            "status": kwargs["status"],
            "stage": kwargs["stage"],
            "progress": kwargs["progress"],
            "message": kwargs["message"],
        }
        if kwargs.get("artifactRefs") is not None:
            body["artifactRefs"] = kwargs["artifactRefs"]
        if kwargs.get("error") is not None:
            body["error"] = kwargs["error"]
        _post_task_event(api_base_url, task_id, **body)
        return body

    return emit


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: run_p0_task.py '<json-payload>'", file=sys.stderr)
        return 2

    payload = json.loads(sys.argv[1])
    configure_whisper_runtime()
    api_base_url = str(payload["apiBaseUrl"])
    storage_root = Path(payload["storageRoot"])
    task_id = str(payload["taskId"])
    project_id = str(payload["projectId"])
    mode = str(payload["mode"])
    resume = bool(payload.get("resume", False))

    from app.pipelines.p0_demo_pipeline import P0DemoPipeline

    pipeline = P0DemoPipeline(storage_root)
    emit = _emit_factory(api_base_url, task_id)

    try:
        if mode == "analyze_sample":
            result = pipeline.analyze_sample(
                project_id=project_id,
                task_id=task_id,
                sample_id=str(payload["sampleId"]),
                video_path=payload.get("videoPath"),
                source_url=payload.get("sourceUrl"),
                cookies_path=payload.get("cookiesPath"),
                emit=emit,
                resume=resume,
            )
        elif mode == "run_generation":
            result = pipeline.run_generation(
                project_id=project_id,
                task_id=task_id,
                generation_id=str(payload["generationId"]),
                structure=payload["structure"],
                user_brief=payload["userBrief"],
                assets=payload["assets"],
                emit=emit,
                resume=resume,
            )
        else:
            print(f"Unknown mode: {mode}", file=sys.stderr)
            return 2
    except Exception as exc:
        traceback.print_exc()
        stage = "extracting_metadata" if mode == "analyze_sample" else "analyzing_assets"
        error = {
            "code": "worker_unhandled_error",
            "message": str(exc),
            "retryable": True,
        }
        emit(
            status="failed",
            stage=stage,
            progress=0,
            message=f"Worker crashed: {exc}",
            error=error,
        )
        result = {"ok": False, "finalEvent": {"status": "failed", "stage": stage, "error": error}}

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
