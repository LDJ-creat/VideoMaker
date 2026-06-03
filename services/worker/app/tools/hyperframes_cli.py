from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

from app.agents.prompt_loader import detect_repo_root


def resolve_hyperframes_argv(*, repo_root: Path | None = None) -> list[str]:
    """Resolve HyperFrames CLI invocation (local node_modules, env override, or npx)."""
    custom = os.getenv("VIDEOMAKER_HYPERFRAMES_CMD", "").strip()
    if custom:
        return shlex.split(custom, posix=(os.name != "nt"))

    root = (repo_root or detect_repo_root()).resolve()
    if sys.platform == "win32":
        local = root / "node_modules" / ".bin" / "hyperframes.cmd"
    else:
        local = root / "node_modules" / ".bin" / "hyperframes"
    if local.is_file():
        return [str(local)]

    return ["npx", "hyperframes"]
