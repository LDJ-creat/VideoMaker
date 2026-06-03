from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app.gateway.model_gateway import ModelGateway
from app.runtime.video_gen_quota import VideoGenQuota
from app.tools.image_gen_tool import ToolError, _artifact_ref

ProgressEmitter = Callable[[str, str], None]


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
        try:
            job_id = self._gateway.submit_video_job(prompt, options=opts)
            result = self._gateway.poll_video_job(job_id)
        except ToolError:
            raise
        except Exception as exc:
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
        if not quota.consume(slot_id):
            output_path.unlink(missing_ok=True)
            raise ToolError(
                code="video_quota_exceeded",
                message="Video generation quota exceeded for this generation",
                retryable=False,
            )
        return _artifact_ref("video", output_path)
