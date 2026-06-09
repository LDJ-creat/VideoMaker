from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Protocol


@dataclass
class AuthorRequest:
    slot: dict[str, Any]
    project_id: str = ""
    brand_colors: dict[str, Any] = field(default_factory=dict)
    variant_overrides: dict[str, Any] = field(default_factory=dict)
    asset_refs: list[dict[str, Any]] | None = None
    aspect_ratio: str = "9:16"
    pattern_l0: list[dict[str, Any]] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    task_id: str | None = None
    generation_id: str | None = None
    react_trace: Any | None = None


@dataclass
class BuildContext:
    project_root: Path
    output_dir: Path
    asset_root: Path | None = None
    aspect_ratio: str = "9:16"


@dataclass
class RenderPaths:
    project_root: Path
    output_dir: Path
    output_clip: Path
    log_path: Path
    asset_root: Path | None = None
    aspect_ratio: str = "9:16"
    lint_log_path: Path | None = None


@dataclass
class LintResult:
    ok: bool
    skipped: bool = False
    errors: list[str] = field(default_factory=list)
    composition_dir: Path | None = None
    log_path: Path | None = None


@dataclass
class RenderResult:
    ok: bool
    output_clip: Path | None = None
    composition_dir: Path | None = None
    duration_sec: float = 0.0
    lint_passed: bool = False
    lint_skipped: bool = False
    lint_log_path: Path | None = None
    error: dict[str, Any] | None = None


@dataclass
class PatternDepositContext:
    storage_root: Path
    project_id: str
    generation_id: str
    slot_id: str
    slot_role: str
    spec: dict[str, Any]
    composition_dir: Path
    lint_passed: bool
    render_passed: bool
    lint_log_path: Path | None = None


@dataclass
class PatternPromoteRequest:
    storage_root: Path
    project_id: str
    generation_id: str
    slot_id: str
    title: str | None = None
    category: str | None = None


class ToolGateway(Protocol):
    def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        task: str,
    ) -> dict[str, Any]: ...

    def complete_json(
        self,
        task: str,
        inputs: dict[str, Any],
        schema_name: str | None,
    ) -> dict[str, Any]: ...


ProgressEmitter = Callable[[str, str], None]
