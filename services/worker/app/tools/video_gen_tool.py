from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

from app.gateway.model_gateway import ModelGateway
from app.runtime.video_gen_quota import VideoGenQuota
from app.tools.image_gen_tool import ToolError, _artifact_ref

ProgressEmitter = Callable[[str, str], None]


def _pending_job_path(output_path: Path, slot_id: str) -> Path:
    return output_path.parent / f"{slot_id}.video-job.json"


class VideoGenTool:
    def __init__(
        self,
        *,
        gateway: ModelGateway,
        emit_progress: ProgressEmitter | None = None,
    ) -> None:
        self._gateway = gateway
        self._emit_progress = emit_progress

    def generate(
        self,
        *,
        prompt: str,
        output_path: Path,
        quota: VideoGenQuota,
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        opts = dict(options or {})
        slot_id = str(opts.get("slotId") or "__legacy__")
        if not quota.can_generate_for_slot(slot_id):
            raise ToolError(
                code="video_quota_exceeded",
                message=f"Video generation quota exceeded for slot {slot_id}",
                retryable=False,
            )
        if self._emit_progress is not None:
            self._emit_progress("generating_video", "Generating video")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pending_path = _pending_job_path(output_path, slot_id)
        job_id = _read_pending_job_id(pending_path)
        resumed = job_id is not None
        try:
            if job_id is None:
                job_id = self._gateway.submit_video_job(prompt, options=opts)
                _write_pending_job_id(pending_path, job_id)
            elif self._emit_progress is not None:
                self._emit_progress("generating_video", f"Resuming video job {job_id}")
            result = self._gateway.poll_video_job(job_id)
        except ToolError:
            raise
        except Exception as exc:
            if job_id is None:
                pending_path.unlink(missing_ok=True)
            raise ToolError(
                code="video_generation_failed",
                message=str(exc),
                retryable=True,
            ) from exc
        if not result.video_bytes:
            raise ToolError(
                code="video_generation_failed",
                message="Video job completed without downloadable bytes",
                retryable=True,
            )
        output_path.write_bytes(result.video_bytes)
        pending_path.unlink(missing_ok=True)
        if not quota.consume(slot_id):
            output_path.unlink(missing_ok=True)
            raise ToolError(
                code="video_quota_exceeded",
                message="Video generation quota exceeded for this generation",
                retryable=False,
            )
        return _artifact_ref("video", output_path)


def _read_pending_job_id(path: Path) -> str | None:
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    job_id = payload.get("jobId")
    if isinstance(job_id, str) and job_id.strip():
        return job_id.strip()
    return None


def _write_pending_job_id(path: Path, job_id: str) -> None:
    path.write_text(json.dumps({"jobId": job_id}, ensure_ascii=False), encoding="utf-8")
