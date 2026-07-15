from __future__ import annotations

from pathlib import Path

import pytest

from app.composition.acp.trace_policy import (
    TracePolicyMonitor,
    detect_forbidden_read_in_session_update,
    detect_forbidden_shell_bypass,
    is_forbidden_repo_read,
)


def test_is_forbidden_repo_read_services_path(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    assert is_forbidden_repo_read(
        r"D:\VideoMaker\services\worker\app\foo.py",
        scratch_dir=scratch,
    )


def test_is_forbidden_repo_read_allows_scratch_brief(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    assert not is_forbidden_repo_read(str(scratch / "AUTHOR_BRIEF.md"), scratch_dir=scratch)


def test_trace_policy_detects_repo_read(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    payload = {
        "update": {
            "tool": "Read",
            "input": {"path": "services/composition/composition/mcp/handlers.py"},
        }
    }
    path = detect_forbidden_read_in_session_update(payload, scratch_dir=scratch)
    assert path is not None
    assert "handlers.py" in path


def test_trace_policy_detects_shell_mcp_bypass() -> None:
    update = {
        "kind": "execute",
        "rawInput": {
            "command": "cd D:\\VideoMaker\\services\\composition; python -c \"from composition.mcp import handlers\""
        },
    }
    assert detect_forbidden_shell_bypass(update) == "python -c"
    payload = {"update": update}
    path = detect_forbidden_read_in_session_update(payload, scratch_dir=Path("/tmp/scratch"))
    assert path == "python -c"


def test_trace_policy_monitor_aborts_on_second_violation(tmp_path: Path) -> None:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monitor = TracePolicyMonitor(scratch_dir=scratch)
    first = {"update": {"input": {"path": "services/worker/app/foo.py"}}}
    second = {"update": {"input": {"path": "tests/test_acp_author.py"}}}
    monitor.inspect_session_update(first)
    assert not monitor.should_abort()
    monitor.inspect_session_update(second)
    assert monitor.should_abort()
