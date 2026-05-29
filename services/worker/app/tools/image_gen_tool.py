from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

from app.gateway.model_gateway import ModelGateway

ProgressEmitter = Callable[[str, str], None]


@dataclass
class ToolError(Exception):
    code: str
    message: str
    retryable: bool = False


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _artifact_ref(artifact_type: str, path: Path) -> dict[str, Any]:
    return {
        "id": path.stem,
        "type": artifact_type,
        "uri": str(path.resolve()),
        "createdAt": _utc_now_iso(),
    }


class ImageGenTool:
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
        options: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if self._emit_progress is not None:
            self._emit_progress("generating_image", "Generating image")
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            image_bytes = self._gateway.generate_image(prompt, options=options)
        except Exception as exc:
            raise ToolError(
                code="image_generation_failed",
                message=str(exc),
                retryable=True,
            ) from exc
        output_path.write_bytes(image_bytes)
        return _artifact_ref("image", output_path)
