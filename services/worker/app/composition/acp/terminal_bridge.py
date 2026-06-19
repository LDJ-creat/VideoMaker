from __future__ import annotations

import asyncio
import os
import re
import sys
from pathlib import Path


_TERMINAL_ALLOWLIST = (
    re.compile(r"^hyperframes(\.cmd)?$"),
    re.compile(r"^npx$"),
    re.compile(r"^node(\.exe)?$"),
    re.compile(r"^npm(\.cmd)?$"),
)


def _auto_approve_enabled() -> bool:
    raw = os.getenv("VIDEOMAKER_COMPOSITION_ACP_AUTO_APPROVE", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def is_terminal_command_allowed(command: str, args: list[str] | None = None) -> bool:
    if _auto_approve_enabled():
        base = Path(command).name
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
    ) -> tuple[int, str, str]:
        if not is_terminal_command_allowed(command, args):
            raise PermissionError(f"terminal command not allowed: {command}")
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
