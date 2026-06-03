from __future__ import annotations

import sys
from pathlib import Path

from app.tools.hyperframes_cli import resolve_hyperframes_argv


def test_resolve_hyperframes_prefers_local_node_modules(tmp_path: Path, monkeypatch) -> None:
    bin_dir = tmp_path / "node_modules" / ".bin"
    bin_dir.mkdir(parents=True)
    if sys.platform == "win32":
        cli = bin_dir / "hyperframes.cmd"
    else:
        cli = bin_dir / "hyperframes"
    cli.write_text("@echo off\n", encoding="utf-8")

    monkeypatch.delenv("VIDEOMAKER_HYPERFRAMES_CMD", raising=False)
    argv = resolve_hyperframes_argv(repo_root=tmp_path)
    assert argv[0].endswith("hyperframes") or argv[0].endswith("hyperframes.cmd")


def test_resolve_hyperframes_env_override(monkeypatch) -> None:
    monkeypatch.setenv("VIDEOMAKER_HYPERFRAMES_CMD", "custom-hf --verbose")
    assert resolve_hyperframes_argv(repo_root=Path("/unused")) == [
        "custom-hf",
        "--verbose",
    ]
