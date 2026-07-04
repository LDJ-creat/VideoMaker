from __future__ import annotations

import time
from typing import Any

from app.gateway.providers.base import GatewayError
from app.observability.capture import capture_enabled_for_local, prepare_payload
from app.runtime.model_call_store import ModelCallLog


def record_model_call(
    gateway: Any,
    *,
    call_kind: str,
    profile: str,
    model: str,
    driver: str,
    input_payload: Any,
    started: float,
    output_payload: Any = None,
    output_valid: bool = True,
    error: Exception | None = None,
    token_usage: dict[str, float] | None = None,
    usage_units: dict[str, Any] | None = None,
    job_id: str | None = None,
) -> str | None:
    observability = getattr(gateway, "observability", None)
    if observability is None:
        return None

    capture = observability.effective_capture
    if not capture_enabled_for_local(capture):
        return None

    latency_ms = float(getattr(gateway, "last_latency_ms", None) or ((time.perf_counter() - started) * 1000))
    error_payload: dict[str, Any] | None = None
    if error is not None:
        output_valid = False
        code = getattr(error, "code", None)
        if isinstance(error, GatewayError) or code is not None:
            error_payload = {
                "code": str(code or "gateway_error"),
                "message": str(getattr(error, "message", error)),
                "retryable": bool(getattr(error, "retryable", False)),
            }
        else:
            error_payload = {
                "code": "model_call_failed",
                "message": str(error),
                "retryable": True,
            }

    log = ModelCallLog(
        call_kind=call_kind,
        profile=profile,
        model=model,
        driver=driver,
        output_valid=output_valid,
        latency_ms=latency_ms,
        task_id=observability.task_id,
        generation_id=observability.generation_id,
        slot_id=observability.slot_id,
        agent_name=observability.agent_name,
        turn=observability.turn,
        job_id=job_id,
        input_payload=prepare_payload(input_payload, capture=capture),
        output_payload=prepare_payload(output_payload, capture=capture),
        token_usage=token_usage,
        usage_units=usage_units,
        error=error_payload,
    )
    payload = log.to_payload(project_id=observability.project_id)
    observability.sink.record_model_call(payload)
    observability.last_model_call_id = str(payload["id"])
    return str(payload["id"])


def invalidate_last_model_call(
    gateway: Any,
    *,
    validation_errors: list[str] | None = None,
) -> None:
    observability = getattr(gateway, "observability", None)
    if observability is None or not observability.last_model_call_id:
        return

    message = "; ".join(validation_errors or []) or "post_validation_failed"
    patch = {
        "projectId": observability.project_id,
        "id": observability.last_model_call_id,
        "taskId": observability.task_id,
        "generationId": observability.generation_id,
        "outputValid": False,
        "error": {
            "code": "post_validation_failed",
            "message": message[:2000],
            "retryable": True,
        },
    }
    observability.sink.amend_model_call(patch)


def chat_driver_for_profile(gateway: Any, profile: str) -> str:
    if profile in {"image"}:
        return image_driver(gateway)
    if profile == "tts":
        return tts_driver(gateway)
    if profile == "video":
        return video_driver(gateway)
    config = gateway.config
    base_url = ""
    if profile == "vision":
        base_url = config.vision.base_url.lower()
    elif profile == "video_understanding":
        base_url = config.video_understanding.base_url.lower()
    else:
        base_url = config.text.base_url.lower()
    if "dashscope" in base_url:
        return "dashscope_chat"
    if "volces.com" in base_url or "volcengine" in base_url:
        return "volcengine_ark"
    return "openai_compatible"


def image_driver(gateway: Any) -> str:
    base_url = gateway.config.image.base_url.lower()
    if "dashscope" in base_url:
        return "dashscope_image"
    return "openai_compatible"


def tts_driver(gateway: Any) -> str:
    return gateway.config.tts_driver


def video_driver(gateway: Any) -> str:
    return gateway.config.video_driver
