from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Iterator

from app.observability.capture import resolve_observability_capture

if TYPE_CHECKING:
    from app.gateway.model_gateway import ModelGateway
    from app.observability.sink import ObservabilitySink


@dataclass
class GatewayObservability:
    sink: ObservabilitySink
    project_id: str
    task_id: str | None = None
    generation_id: str | None = None
    agent_name: str | None = None
    slot_id: str | None = None
    turn: int | None = None
    capture: str | None = None
    last_model_call_id: str | None = field(default=None, repr=False)

    @property
    def effective_capture(self) -> str:
        return self.capture or resolve_observability_capture()


def attach_gateway_observability(
    gateway: ModelGateway,
    *,
    sink: ObservabilitySink,
    project_id: str,
    task_id: str | None = None,
    generation_id: str | None = None,
) -> GatewayObservability:
    existing = getattr(gateway, "observability", None)
    if isinstance(existing, GatewayObservability) and existing.sink is sink:
        existing.project_id = project_id
        existing.task_id = task_id
        existing.generation_id = generation_id
        return existing

    ctx = GatewayObservability(
        sink=sink,
        project_id=project_id,
        task_id=task_id,
        generation_id=generation_id,
    )
    gateway.observability = ctx
    return ctx


def resolve_profile_model(gateway: ModelGateway, profile: str) -> str:
    config = gateway.config
    if profile == "vision":
        return config.vision.model
    if profile == "video_understanding":
        return config.video_understanding.model
    if profile == "image":
        return config.image.model
    if profile == "tts":
        return config.tts.model
    if profile == "video":
        return config.video.model
    return config.text.model


@contextmanager
def agent_observability_scope(
    gateway: Any,
    agent_name: str,
) -> Iterator[None]:
    observability = getattr(gateway, "observability", None)
    previous_agent_name = None
    if observability is not None:
        previous_agent_name = observability.agent_name
        observability.agent_name = agent_name
    try:
        yield
    finally:
        if observability is not None:
            observability.agent_name = previous_agent_name
