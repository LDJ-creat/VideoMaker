from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


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


class HyperFramesTool:
    def __init__(self, command_runner: CommandRunner | None = None) -> None:
        self._command_runner = command_runner or _default_command_runner

    def render(self, composition_dir: Path, output_path: Path, log_path: Path) -> dict:
        started = time.perf_counter()
        command = [
            "npx",
            "hyperframes",
            "render",
            str(composition_dir),
            "--output",
            str(output_path),
        ]
        log: dict = {"command": command}

        try:
            version_result = self._command_runner(["npx", "hyperframes", "--version"], composition_dir)
        except FileNotFoundError:
            log["status"] = "missing_cli"
            log["durationMs"] = round((time.perf_counter() - started) * 1000)
            log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
            return {
                "ok": False,
                "error": {
                    "code": "hyperframes_missing",
                    "message": "HyperFrames CLI is unavailable",
                    "retryable": True,
                },
            }

        if version_result.returncode != 0:
            log["status"] = "missing_cli"
            log["versionStdout"] = version_result.stdout
            log["versionStderr"] = version_result.stderr
            log["durationMs"] = round((time.perf_counter() - started) * 1000)
            log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
            return {
                "ok": False,
                "error": {
                    "code": "hyperframes_missing",
                    "message": "HyperFrames CLI is unavailable",
                    "retryable": True,
                },
            }

        result = self._command_runner(command, composition_dir)
        log["stdout"] = result.stdout
        log["stderr"] = result.stderr
        log["durationMs"] = round((time.perf_counter() - started) * 1000)

        if result.returncode == 0:
            log["status"] = "succeeded"
            log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
            return {"ok": True}

        log["status"] = "failed"
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")
        return {
            "ok": False,
            "error": {
                "code": "hyperframes_render_failed",
                "message": "HyperFrames render command failed",
                "retryable": False,
            },
        }
