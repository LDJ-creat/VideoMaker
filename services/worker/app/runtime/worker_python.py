from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


def worker_root() -> Path:
    return Path(__file__).resolve().parents[2]


def api_root() -> Path:
    return worker_root().parent / "api"


def resolve_worker_python() -> str:
    """Match services/api pipeline_runner._worker_python resolution order."""
    for base in (worker_root(), api_root()):
        candidate = base / ".venv" / "Scripts" / "python.exe"
        if candidate.exists():
            return str(candidate)
    return sys.executable


def worker_python_has_langfuse(python_exe: str | None = None) -> bool:
    exe = python_exe or resolve_worker_python()
    completed = subprocess.run(
        [
            exe,
            "-c",
            "import importlib.util,sys; sys.exit(0 if importlib.util.find_spec('langfuse') else 1)",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.returncode == 0


def describe_worker_python(python_exe: str | None = None) -> str:
    exe = Path(python_exe or resolve_worker_python())
    if exe.name.lower() == "python.exe":
        for label, root in (("worker", worker_root()), ("api", api_root())):
            expected = root / ".venv" / "Scripts" / "python.exe"
            if exe.resolve() == expected.resolve():
                return f"{label} venv ({exe})"
    return str(exe)
