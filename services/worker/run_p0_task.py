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
    if mode == "render_knowledge_draft":
        return "rendering_knowledge_draft"
    if mode == "parse_edit_intent":
        return "parsing_edit_intent"
    if mode == "revise_script_draft":
        return "running_agent"
    if mode == "run_revise":
        return "parsing_edit_intent"
    if mode == "execute_revise_patch":
        return "applying_revise_patch"
    if mode == "plan_revise":
        return "parsing_edit_intent"
    if mode == "composition_pattern_promote":
        return "composition_pattern_promote"
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
    from composition.patterns.deposit import PromoteRejected

    emit = None
    result: dict[str, Any] | None = None

    try:
        from app.pipelines.p0_demo_pipeline import P0DemoPipeline

        database_path = payload.get("databasePath")
        pipeline = P0DemoPipeline(
            storage_root,
            database_path=database_path,
        )
        # Sync helper modes do not register SQLite tasks; skip HTTP task events.
        emit = None if mode in {"plan_revise", "parse_edit_intent"} else _emit_factory(
            api_base_url, task_id
        )

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
        elif mode == "render_knowledge_draft":
            result = pipeline.render_knowledge_draft(
                project_id=project_id,
                task_id=task_id,
                sample_id=str(payload["sampleId"]),
                emit=emit,
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
                human_review_mode=payload.get("humanReviewMode"),
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
        elif mode == "plan_revise":
            result = pipeline.run_plan_revise(
                project_id=project_id,
                task_id=task_id,
                generation_id=str(payload["generationId"]),
                instruction=str(payload["instruction"]),
                source_plan=payload["sourcePlan"],
                session=payload.get("session"),
                emit=emit,
            )
        elif mode == "execute_revise_patch":
            result = pipeline.run_revise_patch(
                project_id=project_id,
                task_id=task_id,
                generation_id=str(payload["generationId"]),
                plan_payload=payload["plan"],
                emit=emit,
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
        elif mode == "revise_script_draft":
            from app.pipelines.script_draft_revise import revise_script_draft
            from app.runtime.task_context import TaskContext

            context = TaskContext(
                project_id=project_id,
                task_id=task_id,
                storage_root=storage_root,
            )
            result = revise_script_draft(
                pipeline._build_runner(),  # noqa: SLF001
                project_id=project_id,
                generation_id=str(payload["generationId"]),
                scope=str(payload["scope"]),
                instruction=str(payload["instruction"]),
                context=context,
                structure=payload.get("structure"),
                database_path=getattr(pipeline, "_database_path", None),
            )
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
        elif mode == "composition_pattern_promote":
            from app.agents.composition_pattern_author import run_composition_pattern_author
            from app.pipelines.p0_demo_pipeline import is_fixture_mode
            from app.runtime.task_context import TaskContext
            from composition.patterns.promote_prepare import PromotePrepareContext, prepare_promoted_pattern_bundle
            from composition.patterns.sanitize import load_generation_plan_context
            from composition.render.hyperframes_cli import HyperFramesCli, fixture_command_runner

            generation_id = str(payload["generationId"])
            slot_id = str(payload["slotId"])
            context = TaskContext(
                project_id=project_id,
                task_id=task_id,
                storage_root=storage_root,
            )
            runner = pipeline._build_runner()  # noqa: SLF001
            loaded = load_generation_plan_context(
                storage_root,
                project_id=project_id,
                generation_id=generation_id,
                slot_id=slot_id,
            )
            cli = HyperFramesCli(
                command_runner=fixture_command_runner() if is_fixture_mode() else None,
            )

            def author_fn(**kwargs: Any) -> dict[str, Any]:
                return run_composition_pattern_author(
                    runner,
                    material_spec=kwargs["material_spec"],
                    instance_spec=kwargs["instance_spec"],
                    slot=kwargs["slot"],
                    context=context,
                    validation_errors=kwargs.get("validation_errors") or None,
                    generation_id=generation_id,
                )

            prepared_dir = prepare_promoted_pattern_bundle(
                PromotePrepareContext(
                    storage_root=storage_root,
                    project_id=project_id,
                    generation_id=generation_id,
                    slot_id=slot_id,
                    slot_role=str(loaded.get("slotRole") or slot_id),
                    storyboard_summary=str(loaded.get("storyboardSummary") or ""),
                    master_narration=str(loaded.get("masterNarration") or ""),
                    scene=loaded.get("scene") if isinstance(loaded.get("scene"), dict) else {},
                ),
                author_fn=author_fn,
                hyperframes_cli=cli,
            )
            result = {"ok": True, "preparedDir": str(prepared_dir)}
        else:
            print(f"Unknown mode: {mode}", file=sys.stderr)
            return 2
    except PromoteRejected as exc:
        code = str(exc)
        failure = {
            "ok": False,
            "error": code,
            "finalEvent": {
                "status": "failed",
                "stage": _default_stage(mode),
                "progress": 0,
                "message": code,
                "error": {"code": code, "message": code, "retryable": True},
            },
        }
        result = failure
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
        result = failure

    print(json.dumps(result, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
