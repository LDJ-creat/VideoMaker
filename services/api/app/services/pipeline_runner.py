from __future__ import annotations

import sys
import threading
from pathlib import Path
from typing import Any, Protocol

from app.db.session import Database
from app.services.artifact_store import ArtifactStore
from app.services.project_store import ProjectStore
from app.services.task_events import TaskEventService


class DemoPipeline(Protocol):
    def analyze_sample(
        self,
        *,
        project_id: str,
        task_id: str,
        sample_id: str,
        video_path: str | Path | None = None,
        source_url: str | None = None,
        emit: Any,
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
    ) -> dict[str, Any]: ...


def _worker_root() -> Path:
    return Path(__file__).resolve().parents[3] / "worker"


def _load_worker_pipeline(storage_root: Path) -> DemoPipeline:
    worker_root = _worker_root()
    worker_path = str(worker_root)
    if worker_path not in sys.path:
        sys.path.insert(0, worker_path)
    from app.pipelines.p0_demo_pipeline import P0DemoPipeline

    return P0DemoPipeline(storage_root)


class PipelineRunner:
    def __init__(
        self,
        *,
        database: Database,
        storage_root: Path,
        task_events: TaskEventService,
        project_store: ProjectStore,
        sync: bool = False,
        pipeline: DemoPipeline | None = None,
    ) -> None:
        self.database = database
        self.storage_root = storage_root
        self.task_events = task_events
        self.project_store = project_store
        self.artifact_store = ArtifactStore(storage_root)
        self.sync = sync
        self._pipeline = pipeline

    def _get_pipeline(self) -> DemoPipeline:
        if self._pipeline is None:
            self._pipeline = _load_worker_pipeline(self.storage_root)
        return self._pipeline

    def _emit(self, task_id: str, **kwargs: Any) -> dict[str, Any]:
        return self.task_events.update_task(task_id, **kwargs)

    def _run(self, job: Any) -> None:
        if self.sync:
            job()
            return
        thread = threading.Thread(target=job, daemon=True)
        thread.start()

    def start_url_import(
        self,
        *,
        project_id: str,
        sample_id: str,
        task_id: str,
        url: str,
    ) -> None:
        def job() -> None:
            emit = lambda **kwargs: self._emit(task_id, **kwargs)  # noqa: E731
            try:
                self._emit(
                    task_id,
                    status="running",
                    stage="uploading",
                    progress=2,
                    message="Downloading sample from URL",
                )
                result = self._get_pipeline().analyze_sample(
                    project_id=project_id,
                    task_id=task_id,
                    sample_id=sample_id,
                    source_url=url,
                    emit=emit,
                )
                if result.get("ok"):
                    self.project_store.update_sample(
                        sample_id,
                        status="analyzed",
                        structure=result["structure"],
                    )
                else:
                    self.project_store.update_sample(sample_id, status="failed")
            except Exception as exc:  # pragma: no cover - safety net
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

        self._run(job)

    def start_sample_analysis(
        self,
        *,
        project_id: str,
        sample_id: str,
        task_id: str,
        video_uri: str,
    ) -> None:
        def job() -> None:
            emit = lambda **kwargs: self._emit(task_id, **kwargs)  # noqa: E731
            try:
                self.project_store.update_sample(sample_id, status="analyzing", task_id=task_id)
                result = self._get_pipeline().analyze_sample(
                    project_id=project_id,
                    task_id=task_id,
                    sample_id=sample_id,
                    video_path=video_uri,
                    emit=emit,
                )
                if result.get("ok"):
                    self.project_store.update_sample(
                        sample_id,
                        status="analyzed",
                        structure=result["structure"],
                    )
                else:
                    self.project_store.update_sample(sample_id, status="failed")
            except Exception as exc:  # pragma: no cover
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

        self._run(job)

    def start_generation(
        self,
        *,
        project_id: str,
        generation_id: str,
        task_id: str,
        structure: dict[str, Any],
        user_brief: dict[str, Any],
        assets: list[dict[str, Any]],
    ) -> None:
        def job() -> None:
            emit = lambda **kwargs: self._emit(task_id, **kwargs)  # noqa: E731
            try:
                self.project_store.update_generation(generation_id, status="running", task_id=task_id)
                result = self._get_pipeline().run_generation(
                    project_id=project_id,
                    task_id=task_id,
                    generation_id=generation_id,
                    structure=structure,
                    user_brief=user_brief,
                    assets=assets,
                    emit=emit,
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
            except Exception as exc:  # pragma: no cover
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

        self._run(job)
