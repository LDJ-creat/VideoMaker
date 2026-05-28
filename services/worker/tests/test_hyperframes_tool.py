from __future__ import annotations

import json
from pathlib import Path

from app.tools.hyperframes_tool import CommandResult, HyperFramesTool


def test_render_returns_retryable_error_when_cli_missing(tmp_path: Path) -> None:
    def runner(command: list[str], cwd: Path) -> CommandResult:
        raise FileNotFoundError("npx not found")

    tool = HyperFramesTool(command_runner=runner)
    composition_dir = tmp_path / "composition"
    composition_dir.mkdir(parents=True, exist_ok=True)
    output_path = tmp_path / "output.mp4"
    log_path = tmp_path / "render-log.json"

    result = tool.render(composition_dir=composition_dir, output_path=output_path, log_path=log_path)

    assert result["ok"] is False
    assert result["error"]["code"] == "hyperframes_missing"
    assert result["error"]["retryable"] is True
    log = json.loads(log_path.read_text(encoding="utf-8"))
    assert log["status"] == "missing_cli"
    assert log["error"]["code"] == "hyperframes_missing"
    assert log["error"]["retryable"] is True
    assert "durationMs" in log


def test_render_returns_retryable_error_when_render_command_missing(tmp_path: Path) -> None:
    calls = {"count": 0}

    def runner(command: list[str], cwd: Path) -> CommandResult:
        calls["count"] += 1
        if calls["count"] == 1:
            return CommandResult(returncode=0, stdout="1.0.0", stderr="")
        raise FileNotFoundError("npx not found")

    tool = HyperFramesTool(command_runner=runner)
    composition_dir = tmp_path / "composition"
    composition_dir.mkdir(parents=True, exist_ok=True)
    output_path = tmp_path / "output.mp4"
    log_path = tmp_path / "render-log.json"

    result = tool.render(composition_dir=composition_dir, output_path=output_path, log_path=log_path)

    assert result["ok"] is False
    assert result["error"]["code"] == "hyperframes_missing"
    log = json.loads(log_path.read_text(encoding="utf-8"))
    assert log["status"] == "missing_cli"
    assert log["error"]["retryable"] is True


def test_render_writes_log_on_success(tmp_path: Path) -> None:
    def runner(command: list[str], cwd: Path) -> CommandResult:
        return CommandResult(returncode=0, stdout="ok", stderr="")

    tool = HyperFramesTool(command_runner=runner)
    composition_dir = tmp_path / "composition"
    composition_dir.mkdir(parents=True, exist_ok=True)
    output_path = tmp_path / "output.mp4"
    log_path = tmp_path / "render-log.json"

    result = tool.render(composition_dir=composition_dir, output_path=output_path, log_path=log_path)

    assert result["ok"] is True
    log = json.loads(log_path.read_text(encoding="utf-8"))
    assert log["status"] == "succeeded"
    assert log["command"][0] == "npx"
    assert "durationMs" in log
    assert "error" not in log


def test_render_writes_error_details_when_render_fails(tmp_path: Path) -> None:
    def runner(command: list[str], cwd: Path) -> CommandResult:
        if "render" in command:
            return CommandResult(returncode=1, stdout="", stderr="render failed")
        return CommandResult(returncode=0, stdout="1.0.0", stderr="")

    tool = HyperFramesTool(command_runner=runner)
    composition_dir = tmp_path / "composition"
    composition_dir.mkdir(parents=True, exist_ok=True)
    output_path = tmp_path / "output.mp4"
    log_path = tmp_path / "render-log.json"

    result = tool.render(composition_dir=composition_dir, output_path=output_path, log_path=log_path)

    assert result["ok"] is False
    assert result["error"]["code"] == "hyperframes_render_failed"
    log = json.loads(log_path.read_text(encoding="utf-8"))
    assert log["status"] == "failed"
    assert log["error"]["retryable"] is False
    assert log["stderr"] == "render failed"
