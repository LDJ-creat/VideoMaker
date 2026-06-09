from __future__ import annotations

import json
import os
import shlex
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from composition.paths import detect_repo_root


@dataclass(slots=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


CommandRunner = Callable[[list[str], Path], CommandResult]


def _default_command_runner(command: list[str], cwd: Path) -> CommandResult:
    completed = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return CommandResult(
        returncode=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
    )


def fixture_command_runner() -> CommandRunner:
    def runner(command: list[str], cwd: Path) -> CommandResult:
        _ = cwd
        if "render" in command:
            output_index = command.index("--output") + 1
            output_path = Path(command[output_index])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"mock-mp4")
        return CommandResult(returncode=0, stdout="ok", stderr="")

    return runner


def resolve_hyperframes_argv(*, repo_root: Path | None = None) -> list[str]:
    custom = os.getenv("VIDEOMAKER_HYPERFRAMES_CMD", "").strip()
    if custom:
        return shlex.split(custom, posix=(os.name != "nt"))
    root = (repo_root or detect_repo_root()).resolve()
    if os.name == "nt":
        local = root / "node_modules" / ".bin" / "hyperframes.cmd"
    else:
        local = root / "node_modules" / ".bin" / "hyperframes"
    if local.is_file():
        return [str(local)]
    return ["npx", "hyperframes"]


class HyperFramesCli:
    def __init__(
        self,
        command_runner: CommandRunner | None = None,
        *,
        repo_root: Path | None = None,
    ) -> None:
        self._command_runner = command_runner or _default_command_runner
        self._argv = resolve_hyperframes_argv(repo_root=repo_root)

    def _cli(self, *args: str) -> list[str]:
        return [*self._argv, *args]

    def lint(self, composition_dir: Path, log_path: Path | None = None) -> dict[str, Any]:
        started = time.perf_counter()
        command = self._cli("lint", str(composition_dir))
        try:
            result = self._command_runner(command, composition_dir)
        except FileNotFoundError:
            payload = {"ok": False, "errors": ["hyperframes cli missing"], "command": command}
            if log_path:
                log_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return payload
        ok = result.returncode == 0
        payload: dict[str, Any] = {
            "ok": ok,
            "command": command,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "durationMs": round((time.perf_counter() - started) * 1000),
            "errors": [] if ok else [result.stderr.strip() or result.stdout.strip() or "lint failed"],
        }
        if log_path:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def render(self, composition_dir: Path, output_path: Path, log_path: Path) -> dict[str, Any]:
        started = time.perf_counter()
        command = self._cli("render", str(composition_dir), "--output", str(output_path))
        log: dict[str, Any] = {"command": command}
        try:
            version_result = self._command_runner(
                self._cli("--version"),
                composition_dir,
            )
        except FileNotFoundError:
            log["status"] = "missing_cli"
            log["ok"] = False
            log["error"] = {"code": "hyperframes_missing", "message": "HyperFrames CLI unavailable", "retryable": True}
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
            return {"ok": False, "error": log["error"]}
        if version_result.returncode != 0:
            log["status"] = "missing_cli"
            log["ok"] = False
            log["error"] = {"code": "hyperframes_missing", "message": "HyperFrames CLI unavailable", "retryable": True}
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
            return {"ok": False, "error": log["error"]}
        try:
            result = self._command_runner(command, composition_dir)
        except FileNotFoundError:
            log["status"] = "missing_cli"
            log["ok"] = False
            log["error"] = {"code": "hyperframes_missing", "message": "HyperFrames CLI unavailable", "retryable": True}
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
            return {"ok": False, "error": log["error"]}
        log["stdout"] = result.stdout
        log["stderr"] = result.stderr
        log["durationMs"] = round((time.perf_counter() - started) * 1000)
        if result.returncode == 0:
            log["ok"] = True
            log["status"] = "succeeded"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
            return {"ok": True}
        log["ok"] = False
        log["status"] = "failed"
        log["error"] = {"code": "hyperframes_render_failed", "message": "HyperFrames render failed", "retryable": False}
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_path.write_text(json.dumps(log, indent=2), encoding="utf-8")
        return {"ok": False, "error": log["error"]}
