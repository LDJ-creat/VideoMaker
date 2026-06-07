from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from typing import Any, Protocol

from app.db.session import Database
from app.services.artifact_store import ArtifactStore
from app.services.cookie_store import CookieStore
from app.services.project_store import ProjectStore
from app.services.task_events import TaskEventService
from app.services.upload_batch_store import UploadBatchStore

logger = logging.getLogger(__name__)
worker_logger = logging.getLogger("videomaker.worker")


class DemoPipeline(Protocol):
    def analyze_sample(
        self,
        *,
        project_id: str,
        task_id: str,
        sample_id: str,
        video_path: str | Path | None = None,
        source_url: str | None = None,
        cookies_path: str | Path | None = None,
        emit: Any,
        resume: bool = False,
    ) -> dict[str, Any]: ...

    def run_generation(
        self,
        *,
        project_id: str,
        task_id: str,
        generation_id: str,
        structure: dict[str, Any],
        user_brief: dict[str, Any],
        assets: list[dict[str, Any]],
        emit: Any,
        resume: bool = False,
        variant: str = "default",
        sample_selection: dict[str, Any] | None = None,
        generation_run_id: str | None = None,
        human_review_mode: bool | None = None,
    ) -> dict[str, Any]: ...

    def run_revise(
        self,
        *,
        project_id: str,
        task_id: str,
        source_generation_id: str,
        generation_id: str,
        instruction: str,
        structure: dict[str, Any],
        user_brief: dict[str, Any],
        assets: list[dict[str, Any]],
        emit: Any,
        intents: list[dict[str, Any]] | None = None,
        variant: str | None = None,
        resume: bool = False,
    ) -> dict[str, Any]: ...

    def parse_edit_intent(
        self,
        *,
        project_id: str,
        task_id: str,
        instruction: str,
        source_plan: dict[str, Any],
        emit: Any,
    ) -> dict[str, Any]: ...


def _worker_root() -> Path:
    return Path(__file__).resolve().parents[3] / "worker"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _augment_worker_env(env: dict[str, str]) -> dict[str, str]:
    """Ensure worker subprocess can find repo-local HyperFrames CLI and repo paths."""
    repo_root = _repo_root()
    env.setdefault("VIDEOMAKER_REPO_ROOT", str(repo_root))
    env.setdefault("VIDEO_MAX_POLL_SEC", os.environ.get("VIDEO_MAX_POLL_SEC", "600"))
    node_bin = repo_root / "node_modules" / ".bin"
    if node_bin.is_dir():
        path_key = "PATH" if os.name == "nt" else "Path"
        current = env.get(path_key) or env.get("PATH", "")
        prefix = str(node_bin)
        if prefix not in current.split(os.pathsep):
            env[path_key] = os.pathsep.join([prefix, current]) if current else prefix
    return env


def _worker_python(worker_root: Path) -> str:
    for venv_name in (".venv",):
        for base in (worker_root, Path(__file__).resolve().parents[2]):
            candidate = base / venv_name / "Scripts" / "python.exe"
            if candidate.exists():
                return str(candidate)
    return sys.executable


def _default_api_base_url() -> str:
    return os.environ.get("VIDEOMAKER_API_BASE_URL", "http://127.0.0.1:8000")


def _shared_root() -> Path:
    return Path(__file__).resolve().parents[3] / "shared"


class SubprocessDemoPipeline:
    """Run worker pipeline in an isolated process to avoid `app` package name clash."""

    def __init__(
        self,
        *,
        database_path: Path,
        storage_root: Path,
        api_base_url: str | None = None,
    ) -> None:
        self._database_path = database_path
        self._storage_root = storage_root
        self._api_base_url = api_base_url or _default_api_base_url()
        self._worker_root = _worker_root()
        self._python = _worker_python(self._worker_root)

    def _payload_base(self) -> dict[str, str]:
        return {
            "apiBaseUrl": self._api_base_url,
            "storageRoot": str(self._storage_root),
            "databasePath": str(self._database_path),
        }

    def _inject_stock_media_env(self, env: dict[str, str]) -> None:
        if env.get("VIDEOMAKER_PEXELS_API_KEY", "").strip():
            return
        try:
            from stock_media.store import StockMediaStore

            creds = StockMediaStore(self._database_path, self._storage_root).get_credentials()
            if creds is not None and creds.api_key.strip():
                env["VIDEOMAKER_PEXELS_API_KEY"] = creds.api_key.strip()
        except Exception:
            logger.debug("stock media credentials unavailable for worker env", exc_info=True)

    def _log_worker_output(self, payload: dict[str, Any], completed: subprocess.CompletedProcess[str]) -> None:
        task_id = payload.get("taskId", "unknown")
        mode = payload.get("mode", "unknown")
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()

        worker_logger.info(
            "subprocess finished task_id=%s mode=%s returncode=%s",
            task_id,
            mode,
            completed.returncode,
        )
        if stdout:
            worker_logger.debug("stdout (task_id=%s):\n%s", task_id, stdout)
        if stderr:
            log = worker_logger.error if completed.returncode != 0 else worker_logger.warning
            log("stderr (task_id=%s):\n%s", task_id, stderr)

    def _invoke(self, payload: dict[str, Any]) -> dict[str, Any]:
        script = self._worker_root / "run_p0_task.py"
        if not script.exists():
            raise FileNotFoundError(f"Worker runner not found: {script}")

        env = _augment_worker_env(os.environ.copy())
        shared_root = _shared_root()
        env["PYTHONPATH"] = os.pathsep.join([str(self._worker_root), str(shared_root)])
        self._inject_stock_media_env(env)

        logger.info(
            "starting worker subprocess task_id=%s mode=%s python=%s",
            payload.get("taskId"),
            payload.get("mode"),
            self._python,
        )

        completed = subprocess.run(
            [self._python, str(script), json.dumps(payload, ensure_ascii=False)],
            cwd=str(self._worker_root),
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        self._log_worker_output(payload, completed)

        if completed.returncode != 0 and not completed.stdout.strip():
            stderr = (completed.stderr or "").strip()
            raise RuntimeError(stderr or f"Worker exited with code {completed.returncode}")

        stdout = completed.stdout.strip()
        if not stdout:
            stderr = (completed.stderr or "").strip()
            raise RuntimeError(stderr or "Worker produced no output")

        # Use the last line in case libraries print warnings to stdout.
        result = json.loads(stdout.splitlines()[-1])
        if completed.returncode != 0 and result.get("ok") is not True:
            stderr = (completed.stderr or "").strip()
            final_event = result.get("finalEvent")
            error = final_event.get("error") if isinstance(final_event, dict) else None
            if isinstance(error, dict):
                details = error.get("details")
                if details:
                    worker_logger.error(
                        "worker tool error task_id=%s code=%s details=%s",
                        payload.get("taskId"),
                        error.get("code"),
                        details,
                    )
            # Worker subprocess already POSTed failed task events; return result for caller.
            if isinstance(final_event, dict) and final_event.get("status") == "failed":
                return result
            message = error.get("message") if isinstance(error, dict) else stderr or "Worker task failed"
            raise RuntimeError(message)
        return result

    def analyze_sample(
        self,
        *,
        project_id: str,
        task_id: str,
        sample_id: str,
        video_path: str | Path | None = None,
        source_url: str | None = None,
        cookies_path: str | Path | None = None,
        emit: Any,
        resume: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            **self._payload_base(),
            "mode": "analyze_sample",
            "taskId": task_id,
            "projectId": project_id,
            "sampleId": sample_id,
            "resume": resume,
        }
        if video_path is not None:
            payload["videoPath"] = str(video_path)
        if source_url is not None:
            payload["sourceUrl"] = source_url
        if cookies_path is not None:
            payload["cookiesPath"] = str(cookies_path)
        return self._invoke(payload)

    def run_generation(
        self,
        *,
        project_id: str,
        task_id: str,
        generation_id: str,
        structure: dict[str, Any],
        user_brief: dict[str, Any],
        assets: list[dict[str, Any]],
        emit: Any,
        resume: bool = False,
        variant: str = "default",
        sample_selection: dict[str, Any] | None = None,
        generation_run_id: str | None = None,
        human_review_mode: bool | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            **self._payload_base(),
            "mode": "run_generation",
            "taskId": task_id,
            "projectId": project_id,
            "generationId": generation_id,
            "structure": structure,
            "userBrief": user_brief,
            "assets": assets,
            "resume": resume,
            "variant": variant,
        }
        if sample_selection is not None:
            payload["sampleSelection"] = sample_selection
        if generation_run_id is not None:
            payload["generationRunId"] = generation_run_id
        if human_review_mode is not None:
            payload["humanReviewMode"] = human_review_mode
        return self._invoke(payload)

    def run_revise(
        self,
        *,
        project_id: str,
        task_id: str,
        source_generation_id: str,
        generation_id: str,
        instruction: str,
        structure: dict[str, Any],
        user_brief: dict[str, Any],
        assets: list[dict[str, Any]],
        emit: Any,
        intents: list[dict[str, Any]] | None = None,
        variant: str | None = None,
        resume: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            **self._payload_base(),
            "mode": "run_revise",
            "taskId": task_id,
            "projectId": project_id,
            "sourceGenerationId": source_generation_id,
            "generationId": generation_id,
            "instruction": instruction,
            "structure": structure,
            "userBrief": user_brief,
            "assets": assets,
            "resume": resume,
        }
        if intents is not None:
            payload["intents"] = intents
        if variant is not None:
            payload["variant"] = variant
        return self._invoke(payload)

    def parse_edit_intent(
        self,
        *,
        project_id: str,
        task_id: str,
        instruction: str,
        source_plan: dict[str, Any],
        emit: Any,
    ) -> dict[str, Any]:
        return self._invoke(
            {
                **self._payload_base(),
                "mode": "parse_edit_intent",
                "taskId": task_id,
                "projectId": project_id,
                "instruction": instruction,
                "sourcePlan": source_plan,
            }
        )

    def run_knowledge_selector(
        self,
        *,
        project_id: str,
        task_id: str,
        user_brief: dict[str, Any],
        candidates: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return self._invoke(
            {
                **self._payload_base(),
                "mode": "knowledge_selector",
                "taskId": task_id,
                "projectId": project_id,
                "userBrief": user_brief,
                "candidates": candidates,
            }
        )


class PipelineRunner:
    def __init__(
        self,
        *,
        database: Database,
        storage_root: Path,
        task_events: TaskEventService,
        project_store: ProjectStore,
        cookie_store: CookieStore | None = None,
        sync: bool = False,
        pipeline: DemoPipeline | None = None,
        api_base_url: str | None = None,
    ) -> None:
        self.database = database
        self.storage_root = storage_root
        self.task_events = task_events
        self.project_store = project_store
        self.cookie_store = cookie_store or CookieStore(storage_root)
        self.artifact_store = ArtifactStore(storage_root)
        self.sync = sync
        self.api_base_url = api_base_url or _default_api_base_url()
        self._pipeline = pipeline
        self._active_tasks: set[str] = set()
        self._running_lock = threading.Lock()
        self._sample_analysis_active = 0
        self._sample_analysis_queue: list[dict[str, Any]] = []
        self._sample_analysis_lock = threading.Lock()

    def _max_concurrent_sample_analysis(self) -> int:
        raw = os.getenv("VIDEOMAKER_MAX_CONCURRENT_SAMPLE_ANALYSIS", "2")
        try:
            return max(1, int(raw))
        except ValueError:
            return 2

    def _is_task_active(self, task_id: str) -> bool:
        with self._running_lock:
            return task_id in self._active_tasks

    def _mark_task_active(self, task_id: str) -> bool:
        with self._running_lock:
            if task_id in self._active_tasks:
                return False
            self._active_tasks.add(task_id)
            return True

    def _mark_task_inactive(self, task_id: str) -> None:
        with self._running_lock:
            self._active_tasks.discard(task_id)

    def _run_task(self, task_id: str, job: Any) -> None:
        def wrapped() -> None:
            if not self._mark_task_active(task_id):
                worker_logger.warning(
                    "Skipping duplicate in-process job task_id=%s",
                    task_id,
                )
                return
            try:
                job()
            finally:
                self._mark_task_inactive(task_id)

        self._run(wrapped)

    def _get_pipeline(self) -> DemoPipeline:
        if self._pipeline is None:
            self._pipeline = SubprocessDemoPipeline(
                database_path=self.database.path,
                storage_root=self.storage_root,
                api_base_url=self.api_base_url,
            )
        return self._pipeline

    def _emit(self, task_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.task_events.update_task(task_id, **kwargs)

    def _run(self, job: Any) -> None:
        if self.sync:
            job()
            return
        thread = threading.Thread(target=job, daemon=True)
        thread.start()

    def _make_emit(self, task_id: str) -> Any:
        def emit(**kwargs: Any) -> dict[str, Any]:
            return self._emit(task_id, **kwargs)

        return emit

    def _ensure_task_failed(
        self,
        task_id: str,
        *,
        result: dict[str, Any],
        default_stage: str,
        default_code: str,
    ) -> None:
        latest = self.task_events.get_task(task_id)
        if latest is not None and latest.get("status") == "failed":
            return
        final_event = result.get("finalEvent")
        if isinstance(final_event, dict) and final_event.get("status") == "failed":
            self._emit(
                task_id,
                status="failed",
                stage=str(final_event.get("stage", default_stage)),
                progress=int(final_event.get("progress", 0)),
                message=str(final_event.get("message", "Task failed")),
                error=final_event.get("error")
                or {
                    "code": default_code,
                    "message": "Task failed",
                    "retryable": True,
                },
            )
            return
        self._emit(
            task_id,
            status="failed",
            stage=default_stage,
            progress=0,
            message="Task failed",
            error={"code": default_code, "message": "Task failed", "retryable": True},
        )

    def start_url_import(
        self,
        *,
        project_id: str,
        sample_id: str,
        task_id: str,
        url: str,
    ) -> None:
        def job() -> None:
            try:
                self._emit(
                    task_id,
                    status="running",
                    stage="uploading",
                    progress=2,
                    message="Downloading sample from URL",
                )
                cookies_path = self.cookie_store.get_cookies_path()
                result = self._get_pipeline().analyze_sample(
                    project_id=project_id,
                    task_id=task_id,
                    sample_id=sample_id,
                    source_url=url,
                    cookies_path=cookies_path,
                    emit=self._make_emit(task_id),
                    resume=False,
                )
                if result.get("ok"):
                    video_uri = None
                    sample_analysis = result.get("sampleAnalysis")
                    if isinstance(sample_analysis, dict):
                        video_uri = sample_analysis.get("sourcePath")
                    self.project_store.update_sample(
                        sample_id,
                        status="analyzed",
                        video_uri=video_uri,
                        structure=result["structure"],
                    )
                else:
                    self.project_store.update_sample(sample_id, status="failed")
            except Exception as exc:  # pragma: no cover - safety net
                logger.exception("URL import failed task_id=%s project_id=%s", task_id, project_id)
                latest = self.task_events.get_task(task_id)
                if latest is None or latest.get("status") != "failed":
                    self._emit(
                        task_id,
                        status="failed",
                        stage="uploading",
                        progress=0,
                        message="URL import failed",
                        error={
                            "code": "url_import_failed",
                            "message": str(exc),
                            "retryable": True,
                        },
                    )
                self.project_store.update_sample(sample_id, status="failed")

        self._run_task(task_id, job)

    def enqueue_sample_analysis(
        self,
        *,
        project_id: str,
        sample_id: str,
        task_id: str,
        video_uri: str,
        resume: bool = False,
    ) -> None:
        with self._sample_analysis_lock:
            self._sample_analysis_queue.append(
                {
                    "project_id": project_id,
                    "sample_id": sample_id,
                    "task_id": task_id,
                    "video_uri": video_uri,
                    "resume": resume,
                }
            )
        self._drain_sample_analysis_queue()

    def _drain_sample_analysis_queue(self) -> None:
        while True:
            with self._sample_analysis_lock:
                if self._sample_analysis_active >= self._max_concurrent_sample_analysis():
                    return
                if not self._sample_analysis_queue:
                    return
                item = self._sample_analysis_queue.pop(0)
                self._sample_analysis_active += 1
            self._start_sample_analysis_job(
                project_id=item["project_id"],
                sample_id=item["sample_id"],
                task_id=item["task_id"],
                video_uri=item["video_uri"],
                resume=item["resume"],
                from_queue=True,
            )

    def _finish_sample_analysis_slot(self) -> None:
        with self._sample_analysis_lock:
            self._sample_analysis_active = max(0, self._sample_analysis_active - 1)
        self._drain_sample_analysis_queue()

    def start_sample_analysis(
        self,
        *,
        project_id: str,
        sample_id: str,
        task_id: str,
        video_uri: str,
        resume: bool = False,
    ) -> None:
        self._start_sample_analysis_job(
            project_id=project_id,
            sample_id=sample_id,
            task_id=task_id,
            video_uri=video_uri,
            resume=resume,
            from_queue=False,
        )

    def _refresh_upload_batch_for_sample(self, sample_id: str) -> None:
        sample = self.project_store.get_sample(sample_id)
        if sample is None:
            return
        batch_id = sample.get("uploadBatchId")
        if not batch_id:
            return
        batch_store = UploadBatchStore(self.database)
        batch = batch_store.get_batch(str(batch_id))
        if batch is None:
            return
        statuses: dict[str, str] = {}
        for sid in batch["sampleIds"]:
            row = self.project_store.get_sample(str(sid))
            statuses[str(sid)] = str(row.get("status", "unknown")) if row else "unknown"
        batch_store.refresh_batch_status(str(batch_id), statuses)

    def _start_sample_analysis_job(
        self,
        *,
        project_id: str,
        sample_id: str,
        task_id: str,
        video_uri: str,
        resume: bool = False,
        from_queue: bool = False,
    ) -> None:
        def job() -> None:
            try:
                self.project_store.update_sample(sample_id, status="analyzing", task_id=task_id)
                self._refresh_upload_batch_for_sample(sample_id)
                if resume:
                    self._emit(
                        task_id,
                        status="running",
                        stage="extracting_metadata",
                        progress=5,
                        message="Resuming sample analysis from checkpoint",
                    )
                cookies_path = self.cookie_store.get_cookies_path()
                result = self._get_pipeline().analyze_sample(
                    project_id=project_id,
                    task_id=task_id,
                    sample_id=sample_id,
                    video_path=video_uri,
                    cookies_path=cookies_path,
                    emit=self._make_emit(task_id),
                    resume=resume,
                )
                if result.get("ok"):
                    self.project_store.update_sample(
                        sample_id,
                        status="analyzed",
                        structure=result["structure"],
                    )
                else:
                    self.project_store.update_sample(sample_id, status="failed")
                    self._ensure_task_failed(
                        task_id,
                        result=result,
                        default_stage="extracting_metadata",
                        default_code="sample_analysis_failed",
                    )
                self._refresh_upload_batch_for_sample(sample_id)
            except Exception as exc:  # pragma: no cover
                logger.exception("Sample analysis failed task_id=%s sample_id=%s", task_id, sample_id)
                latest = self.task_events.get_task(task_id)
                if latest is None or latest.get("status") != "failed":
                    self._emit(
                        task_id,
                        status="failed",
                        stage="extracting_metadata",
                        progress=0,
                        message="Sample analysis failed",
                        error={
                            "code": "sample_analysis_failed",
                            "message": str(exc),
                            "retryable": True,
                        },
                    )
                self.project_store.update_sample(sample_id, status="failed")
                self._refresh_upload_batch_for_sample(sample_id)
            finally:
                if from_queue:
                    self._finish_sample_analysis_slot()

        self._run_task(task_id, job)

    def start_generation(
        self,
        *,
        project_id: str,
        generation_id: str,
        task_id: str,
        structure: dict[str, Any],
        user_brief: dict[str, Any],
        assets: list[dict[str, Any]],
        resume: bool = False,
        variant: str = "default",
        sample_selection: dict[str, Any] | None = None,
        generation_run_id: str | None = None,
        human_review_mode: bool | None = None,
        on_generation_complete: Any | None = None,
    ) -> None:
        def job() -> None:
            result: dict[str, Any] = {"ok": False}
            try:
                self.project_store.update_generation(generation_id, status="running", task_id=task_id)
                if resume:
                    self._emit(
                        task_id,
                        status="running",
                        stage="analyzing_assets",
                        progress=5,
                        message="Resuming generation from checkpoint",
                    )
                worker_result = self._get_pipeline().run_generation(
                    project_id=project_id,
                    task_id=task_id,
                    generation_id=generation_id,
                    structure=structure,
                    user_brief=user_brief,
                    assets=assets,
                    emit=self._make_emit(task_id),
                    resume=resume,
                    variant=variant,
                    sample_selection=sample_selection,
                    generation_run_id=generation_run_id,
                    human_review_mode=human_review_mode,
                )
                result = worker_result
                if worker_result.get("paused"):
                    self.project_store.update_generation(generation_id, status="awaiting_review")
                    return
                if worker_result.get("ok"):
                    self.project_store.update_generation(
                        generation_id,
                        status="succeeded",
                        structure_id=result.get("plan", {}).get("structureId")
                        or structure.get("id"),
                        inventory_id=result["inventory"]["id"],
                        gap_report=result["gapReport"],
                        plan=result["plan"],
                    )
                else:
                    self.project_store.update_generation(
                        generation_id,
                        status="failed",
                        gap_report=result.get("gapReport"),
                        plan=result.get("plan"),
                    )
            except Exception as exc:  # pragma: no cover
                logger.exception(
                    "Generation failed task_id=%s generation_id=%s",
                    task_id,
                    generation_id,
                )
                result = {"ok": False}
                self._emit(
                    task_id,
                    status="failed",
                    stage="analyzing_assets",
                    progress=0,
                    message="Generation failed",
                    error={
                        "code": "generation_failed",
                        "message": str(exc),
                        "retryable": True,
                    },
                )
                self.project_store.update_generation(generation_id, status="failed")
            finally:
                if on_generation_complete is not None:
                    on_generation_complete(generation_id, result if "result" in locals() else {"ok": False})

        self._run_task(task_id, job)

    def parse_edit_intent(
        self,
        *,
        project_id: str,
        instruction: str,
        source_plan: dict[str, Any],
    ) -> list[dict[str, Any]]:
        task_id = "parse-edit-intent"
        pipeline = self._get_pipeline()
        if hasattr(pipeline, "parse_edit_intent"):
            result = pipeline.parse_edit_intent(
                project_id=project_id,
                task_id=task_id,
                instruction=instruction,
                source_plan=source_plan,
                emit=self._make_emit(task_id),
            )
            intents = result.get("intents")
            if isinstance(intents, list) and intents:
                return intents
        return self._parse_edit_intent_rules(instruction, source_plan)

    @staticmethod
    def _parse_edit_intent_rules(instruction: str, source_plan: dict[str, Any]) -> list[dict[str, Any]]:
        import importlib.util
        import sys

        module_path = _worker_root() / "app" / "pipelines" / "intent_applier.py"
        spec = importlib.util.spec_from_file_location("videomaker_intent_applier", module_path)
        if spec is None or spec.loader is None:
            raise RuntimeError(f"Could not load intent applier from {module_path}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        source_summary = module.build_source_summary(source_plan)
        payload = module.parse_edit_intent_for_api(instruction, source_summary)
        intents = payload.get("intents")
        if not isinstance(intents, list) or not intents:
            raise ValueError("No edit intents parsed from instruction")
        return intents

    @staticmethod
    def _validate_edit_intents(intents: list[dict[str, Any]]) -> None:
        import json

        import jsonschema

        schema_path = (
            _worker_root().parent.parent / "packages" / "contracts" / "schemas" / "edit-intent.schema.json"
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(instance={"intents": intents}, schema=schema)
        except jsonschema.ValidationError as exc:
            raise ValueError(f"Invalid EditIntent payload: {exc.message}") from exc

    def start_revise(
        self,
        *,
        project_id: str,
        source_generation_id: str,
        generation_id: str,
        task_id: str,
        instruction: str,
        intents: list[dict[str, Any]],
        structure: dict[str, Any],
        user_brief: dict[str, Any],
        assets: list[dict[str, Any]],
        variant: str | None = None,
        resume: bool = False,
    ) -> None:
        def job() -> None:
            try:
                self.project_store.update_generation(generation_id, status="running", task_id=task_id)
                if resume:
                    self._emit(
                        task_id,
                        status="running",
                        stage="parsing_edit_intent",
                        progress=5,
                        message="Resuming generation revise from checkpoint",
                    )
                pipeline = self._get_pipeline()
                if not hasattr(pipeline, "run_revise"):
                    raise RuntimeError("Pipeline does not support revise")
                result = pipeline.run_revise(
                    project_id=project_id,
                    task_id=task_id,
                    source_generation_id=source_generation_id,
                    generation_id=generation_id,
                    instruction=instruction,
                    structure=structure,
                    user_brief=user_brief,
                    assets=assets,
                    emit=self._make_emit(task_id),
                    intents=intents,
                    variant=variant,
                    resume=resume,
                )
                if result.get("ok"):
                    self.project_store.update_generation(
                        generation_id,
                        status="succeeded",
                        structure_id=structure.get("id"),
                        inventory_id=result["inventory"]["id"],
                        gap_report=result["gapReport"],
                        plan=result["plan"],
                    )
                else:
                    self.project_store.update_generation(
                        generation_id,
                        status="failed",
                        gap_report=result.get("gapReport"),
                        plan=result.get("plan"),
                    )
                    self._ensure_task_failed(
                        task_id,
                        result=result,
                        default_stage="parsing_edit_intent",
                        default_code="revise_failed",
                    )
            except Exception as exc:  # pragma: no cover
                logger.exception(
                    "Revise failed task_id=%s generation_id=%s",
                    task_id,
                    generation_id,
                )
                self._emit(
                    task_id,
                    status="failed",
                    stage="parsing_edit_intent",
                    progress=0,
                    message="Revise failed",
                    error={
                        "code": "revise_failed",
                        "message": str(exc),
                        "retryable": True,
                    },
                )
                self.project_store.update_generation(generation_id, status="failed")

        self._run_task(task_id, job)

    def _human_review_mode_for_generation(self, generation: dict[str, Any]) -> bool | None:
        generation_root = (
            self.storage_root
            / "projects"
            / str(generation["projectId"])
            / "generations"
            / str(generation["id"])
        )
        checkpoint_path = generation_root / "checkpoint.json"
        if not checkpoint_path.is_file():
            return None
        try:
            data = json.loads(checkpoint_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None
        if isinstance(data, dict) and "humanReviewMode" in data:
            return bool(data["humanReviewMode"])
        return None

    def retry_task(self, task_id: str) -> dict[str, Any]:
        current = self.task_events.get_task(task_id)
        if current is None:
            raise KeyError(task_id)

        status = current.get("status")
        if status not in {"failed", "retrying", "running", "awaiting_review"}:
            raise ValueError(
                f"Task cannot be retried from status '{status}' "
                "(expected failed, retrying, awaiting_review, or stale running)"
            )
        if self._is_task_active(task_id):
            raise ValueError(
                "Task is still running in this API process; wait for it to finish before retrying"
            )

        error = current.get("error")
        if isinstance(error, dict) and error.get("retryable") is False:
            raise ValueError("Task is not retryable")

        updated = self._emit(
            task_id,
            status="retrying",
            stage=current["stage"],
            progress=current["progress"],
            message="Retry requested, resuming from checkpoint",
        )

        sample = self.project_store.get_sample_by_task_id(task_id)
        if sample is not None:
            video_uri = sample.get("videoUri")
            if not video_uri:
                raise ValueError("Sample has no video for retry")
            self.start_sample_analysis(
                project_id=sample["projectId"],
                sample_id=sample["id"],
                task_id=task_id,
                video_uri=video_uri,
                resume=True,
            )
            return updated

        generation = self.project_store.get_generation_by_task_id(task_id)
        if generation is not None:
            structure = self.project_store.get_latest_sample_structure(generation["projectId"])
            if structure is None:
                raise ValueError("No sample structure available for generation retry")
            brief = self.project_store.get_brief(generation["projectId"]) or {
                "topic": "Demo topic",
                "sellingPoints": [],
                "mustMention": [],
                "avoidMention": [],
            }
            assets = self.project_store.list_assets(generation["projectId"])
            variant = str(generation.get("variant") or (generation.get("plan") or {}).get("variant") or "default")
            generation_root = (
                self.storage_root
                / "projects"
                / generation["projectId"]
                / "generations"
                / generation["id"]
            )
            revise_context_path = generation_root / "revise-context.json"
            if revise_context_path.is_file():
                revise_context = json.loads(revise_context_path.read_text(encoding="utf-8"))
                source_generation_id = str(revise_context.get("sourceGenerationId", ""))
                instruction = str(revise_context.get("instruction") or "")
                intents: list[dict[str, Any]] = []
                edit_intent_path = generation_root / "edit-intent.json"
                if edit_intent_path.is_file():
                    payload = json.loads(edit_intent_path.read_text(encoding="utf-8"))
                    if isinstance(payload.get("intents"), list):
                        intents = payload["intents"]
                if not source_generation_id:
                    raise ValueError("Revise generation is missing sourceGenerationId")
                self.start_revise(
                    project_id=generation["projectId"],
                    source_generation_id=source_generation_id,
                    generation_id=generation["id"],
                    task_id=task_id,
                    instruction=instruction,
                    intents=intents,
                    structure=structure,
                    user_brief=brief,
                    assets=assets,
                    variant=variant,
                    resume=True,
                )
                return updated

            self.start_generation(
                project_id=generation["projectId"],
                generation_id=generation["id"],
                task_id=task_id,
                structure=structure,
                user_brief=brief,
                assets=assets,
                resume=True,
                variant=variant,
                human_review_mode=self._human_review_mode_for_generation(generation),
            )
            return updated

        raise ValueError("No sample or generation found for task")
