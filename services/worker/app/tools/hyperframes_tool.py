from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

MISSING_CLI_ERROR: dict[str, Any] = {
    "code": "hyperframes_missing",
    "message": "HyperFrames CLI is unavailable",
    "retryable": True,
}

RENDER_FAILED_ERROR: dict[str, Any] = {
    "code": "hyperframes_render_failed",
    "message": "HyperFrames render command failed",
    "retryable": False,
}


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
    """Stub HyperFrames CLI for fixture_mode / CI without npx hyperframes."""

    def runner(command: list[str], cwd: Path) -> CommandResult:
        _ = cwd
        if "render" in command:
            output_index = command.index("--output") + 1
            output_path = Path(command[output_index])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"mock-mp4")
        return CommandResult(returncode=0, stdout="ok", stderr="")

    return runner


def build_fixture_hyperframes_tool() -> HyperFramesTool:
    return HyperFramesTool(command_runner=fixture_command_runner())


class HyperFramesTool:
    def __init__(self, command_runner: CommandRunner | None = None) -> None:
        self._command_runner = command_runner or _default_command_runner

    def _persist_log(self, log_path: Path, log: dict[str, Any]) -> None:
        log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2), encoding="utf-8")

    def _finish(
        self,
        *,
        log_path: Path,
        log: dict[str, Any],
        started: float,
        ok: bool,
        status: str,
        error: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        log["status"] = status
        log["durationMs"] = round((time.perf_counter() - started) * 1000)
        if error is not None:
            log["error"] = error
        self._persist_log(log_path, log)
        if ok:
            return {"ok": True}
        return {"ok": False, "error": error}

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
        log: dict[str, Any] = {"command": command}

        try:
            version_result = self._command_runner(
                ["npx", "hyperframes", "--version"], composition_dir
            )
        except FileNotFoundError:
            return self._finish(
                log_path=log_path,
                log=log,
                started=started,
                ok=False,
                status="missing_cli",
                error=MISSING_CLI_ERROR,
            )

        if version_result.returncode != 0:
            log["versionStdout"] = version_result.stdout
            log["versionStderr"] = version_result.stderr
            return self._finish(
                log_path=log_path,
                log=log,
                started=started,
                ok=False,
                status="missing_cli",
                error=MISSING_CLI_ERROR,
            )

        try:
            result = self._command_runner(command, composition_dir)
        except FileNotFoundError:
            return self._finish(
                log_path=log_path,
                log=log,
                started=started,
                ok=False,
                status="missing_cli",
                error=MISSING_CLI_ERROR,
            )

        log["stdout"] = result.stdout
        log["stderr"] = result.stderr

        if result.returncode == 0:
            return self._finish(
                log_path=log_path,
                log=log,
                started=started,
                ok=True,
                status="succeeded",
            )

        return self._finish(
            log_path=log_path,
            log=log,
            started=started,
            ok=False,
            status="failed",
            error=RENDER_FAILED_ERROR,
        )
