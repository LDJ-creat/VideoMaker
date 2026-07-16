from __future__ import annotations

import sys

import pytest

from app.composition.acp.terminal_bridge import is_terminal_command_allowed


def test_terminal_denies_python_lint_spec_cli() -> None:
    import sys

    assert not is_terminal_command_allowed(
        sys.executable,
        ["-m", "composition.cli", "lint-spec", "--scratch", "/tmp/scratch"],
    )


def test_terminal_denies_other_python_modules() -> None:
    assert not is_terminal_command_allowed(sys.executable, ["-m", "http.server"])


def test_terminal_allows_hyperframes() -> None:
    assert is_terminal_command_allowed("hyperframes.cmd", ["lint", "."])
