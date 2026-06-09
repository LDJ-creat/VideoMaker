from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from app.composition.gateway_adapter import ModelGatewayToolAdapter
from app.gateway.model_gateway import ModelGateway
from app.tools.hyperframes_tool import HyperFramesTool
from composition.api import CompositionEngine
from composition.render.hyperframes_cli import CommandResult, HyperFramesCli
from composition.types import ProgressEmitter, ToolGateway


def _runner_from_hyperframes_tool(tool: HyperFramesTool):
    def runner(command: list[str], cwd: Path) -> CommandResult:
        result = tool.command_runner(command, cwd)
        return CommandResult(
            returncode=result.returncode,
            stdout=result.stdout,
            stderr=result.stderr,
        )

    return runner


def create_composition_engine(
    *,
    gateway: ModelGateway | ToolGateway | None = None,
    hyperframes_tool: HyperFramesTool | None = None,
    storage_root: Path | None = None,
    emit_progress: ProgressEmitter | None = None,
    fixture_spec: dict[str, Any] | None = None,
    repo_root: Path | None = None,
) -> CompositionEngine:
    tool_gateway: ToolGateway | None = None
    if gateway is not None:
        tool_gateway = (
            ModelGatewayToolAdapter(gateway)
            if isinstance(gateway, ModelGateway)
            else gateway
        )
    cli = None
    if hyperframes_tool is not None:
        cli = HyperFramesCli(
            command_runner=_runner_from_hyperframes_tool(hyperframes_tool),
            repo_root=repo_root,
        )
    return CompositionEngine(
        repo_root=repo_root,
        storage_root=storage_root,
        gateway=tool_gateway,
        hyperframes_cli=cli,
        emit_progress=emit_progress,
        fixture_spec=fixture_spec,
    )
