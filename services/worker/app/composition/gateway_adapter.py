from __future__ import annotations

from typing import Any

from app.gateway.model_gateway import ModelGateway


class ModelGatewayToolAdapter:
    """Bridge worker ModelGateway to composition ToolGateway protocol."""

    def __init__(self, gateway: ModelGateway) -> None:
        self._gateway = gateway

    def complete_json(
        self,
        task: str,
        inputs: dict[str, Any],
        schema_name: str | None,
    ) -> dict[str, Any]:
        return self._gateway.complete_json(task, inputs, schema_name or "material-spec")

    def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        task: str,
    ) -> dict[str, Any]:
        return self._gateway.complete_with_tools(messages, tools, task=task)
