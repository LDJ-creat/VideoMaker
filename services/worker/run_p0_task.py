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


def _default_stage(mode: str) -> str:
    if mode == "analyze_sample":
        return "extracting_metadata"
    if mode == "parse_edit_intent":
        return "parsing_edit_intent"
    if mode == "run_revise":
        return "parsing_edit_intent"
    return "analyzing_assets"


def _failure_result(mode: str, exc: Exception) -> dict[str, Any]:
    stage = _default_stage(mode)
    error = {
        "code": "worker_unhandled_error",
        "message": str(exc),
        "retryable": True,
    }
    return {
        "ok": False,
        "finalEvent": {
            "status": "failed",
            "stage": stage,
            "progress": 0,
            "message": f"Worker crashed: {exc}",
            "error": error,
        },
    }


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

    emit = None
    result: dict[str, Any] | None = None

    try:
        from app.pipelines.p0_demo_pipeline import P0DemoPipeline

        database_path = payload.get("databasePath")
        pipeline = P0DemoPipeline(
            storage_root,
            database_path=database_path,
        )
        emit = _emit_factory(api_base_url, task_id)

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
                variant=str(payload.get("variant", "default")),
                sample_selection=payload.get("sampleSelection"),
                generation_run_id=payload.get("generationRunId"),
            )
        elif mode == "run_revise":
            result = pipeline.run_revise(
                project_id=project_id,
                task_id=task_id,
                source_generation_id=str(payload["sourceGenerationId"]),
                generation_id=str(payload["generationId"]),
                instruction=str(payload["instruction"]),
                structure=payload["structure"],
                user_brief=payload["userBrief"],
                assets=payload["assets"],
                emit=emit,
                intents=payload.get("intents"),
                variant=payload.get("variant"),
                resume=resume,
            )
        elif mode == "parse_edit_intent":
            from app.agents.edit_intent_parser import build_source_summary, run_edit_intent_parser
            from app.runtime.task_context import TaskContext

            source_plan = payload["sourcePlan"]
            context = TaskContext(
                project_id=project_id,
                task_id=task_id,
                storage_root=storage_root,
            )
            parsed = run_edit_intent_parser(
                pipeline._build_runner(),  # noqa: SLF001
                instruction=str(payload["instruction"]),
                source_summary=build_source_summary(source_plan),
                context=context,
            )
            result = {"ok": True, "intents": parsed.get("intents", [])}
        elif mode == "knowledge_selector":
            from app.agents.knowledge_selector import run_knowledge_selector
            from app.runtime.task_context import TaskContext

            context = TaskContext(
                project_id=project_id,
                task_id=task_id,
                storage_root=storage_root,
            )
            parsed = run_knowledge_selector(
                pipeline._build_runner(),  # noqa: SLF001
                brief=payload["userBrief"],
                candidates=payload["candidates"],
                context=context,
            )
            result = {"ok": True, "selection": parsed}
        else:
            print(f"Unknown mode: {mode}", file=sys.stderr)
            return 2
    except Exception as exc:
        traceback.print_exc()
        failure = _failure_result(mode, exc)
        final_event = failure["finalEvent"]
        if emit is not None:
            emit(
                status="failed",
                stage=str(final_event["stage"]),
                progress=0,
                message=str(final_event["message"]),
                error=final_event["error"],
            )
        else:
            _post_task_event(
                api_base_url,
                task_id,
                status="failed",
                stage=str(final_event["stage"]),
                progress=0,
                message=str(final_event["message"]),
                error=final_event["error"],
            )
        result = failure

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
