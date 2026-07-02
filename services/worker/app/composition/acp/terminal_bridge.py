from __future__ import annotations

import re
import sys
from pathlib import Path


_TERMINAL_ALLOWLIST = (
    re.compile(r"^hyperframes(\.cmd)?$"),
    re.compile(r"^npx(\.cmd)?$"),
    re.compile(r"^node(\.exe)?$"),
    re.compile(r"^npm(\.cmd)?$"),
)


def _auto_approve_enabled() -> bool:
    import os

    raw = os.getenv("VIDEOMAKER_COMPOSITION_ACP_AUTO_APPROVE", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _is_lint_spec_cli_invocation(args: list[str] | None) -> bool:
    if not args or len(args) < 3:
        return False
    if args[0] != "-m":
        return False
    return args[1] == "composition.cli" and args[2] == "lint-spec"


def is_terminal_command_allowed(command: str, args: list[str] | None = None) -> bool:
    if _auto_approve_enabled():
        base = Path(command).name.lower()
        python_names = {Path(sys.executable).name.lower(), "python", "python.exe", "python3", "python3.exe"}
        if base in python_names and _is_lint_spec_cli_invocation(args):
            return True
        if any(pattern.match(base) for pattern in _TERMINAL_ALLOWLIST):
            return True
    _ = args
    return False


class TerminalBridge:
    async def run(
        self,
        *,
        command: str,
        args: list[str] | None = None,
        cwd: str | None = None,
        trace: Any | None = None,
    ) -> tuple[int, str, str]:
        if not is_terminal_command_allowed(command, args):
            if trace is not None and hasattr(trace, "record_tool_call"):
                trace.record_tool_call(
                    {
                        "kind": "terminal_denied",
                        "command": command,
                        "args": list(args or []),
                    }
                )
            raise PermissionError(f"terminal command not allowed: {command}")
        import asyncio

        proc = await asyncio.create_subprocess_exec(
            command,
            *(args or []),
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_bytes, stderr_bytes = await proc.communicate()
        return (
            int(proc.returncode or 0),
            stdout_bytes.decode("utf-8", errors="replace"),
            stderr_bytes.decode("utf-8", errors="replace"),
        )


def resolve_hyperframes_command(repo_root: Path) -> list[str]:
    local = repo_root / "node_modules" / ".bin" / ("hyperframes.cmd" if sys.platform == "win32" else "hyperframes")
    if local.is_file():
        return [str(local)]
    return ["hyperframes"]
