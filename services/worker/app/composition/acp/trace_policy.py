from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

_SCRATCH_ALLOWLIST_BASENAMES = frozenset(
    {
        "author_brief.md",
        "skills_summary.md",
        "task.json",
        "draft.json",
        "material-spec.json",
        "material-spec.lint-passed",
    }
)

_FORBIDDEN_SEGMENTS = (
    "/services/",
    "\\services\\",
    "/tests/",
    "\\tests\\",
    "composition/mcp",
    "composition\\mcp",
)

_TOOL_READ_MARKERS = re.compile(r"\b(read|grep|glob|search)\b", re.IGNORECASE)


def trace_policy_enabled() -> bool:
    raw = os.getenv("VIDEOMAKER_ACP_TRACE_POLICY_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _normalize_path_text(value: str) -> str:
    return value.replace("\\", "/").strip()


def _is_scratch_allowed(path_text: str, scratch_dir: Path) -> bool:
    normalized = _normalize_path_text(path_text)
    if not normalized:
        return False
    basename = Path(normalized).name.lower()
    if basename in _SCRATCH_ALLOWLIST_BASENAMES:
        return True
    scratch_text = _normalize_path_text(str(scratch_dir.resolve()))
    if scratch_text and scratch_text.lower() in normalized.lower():
        return True
    if normalized.lower().startswith("scratch/"):
        return True
    return False


def is_forbidden_repo_read(path_text: str, *, scratch_dir: Path) -> bool:
    normalized = _normalize_path_text(path_text)
    if not normalized or _is_scratch_allowed(normalized, scratch_dir):
        return False
    lowered = normalized.lower()
    if any(segment in lowered for segment in _FORBIDDEN_SEGMENTS):
        return True
    if lowered.endswith(".py"):
        return True
    return False


_SHELL_FORBIDDEN_MARKERS = (
    "python -c",
    "composition.mcp",
    "services/composition",
    "services\\composition",
    "inspect.getsource",
    "_invoke_mcp",
    "composition.cli lint-spec",
    "composition.cli lint_spec",
)


def detect_forbidden_shell_bypass(update: dict[str, Any]) -> str | None:
    if update.get("kind") != "execute":
        return None
    raw_input = update.get("rawInput")
    command = ""
    if isinstance(raw_input, dict):
        command = str(raw_input.get("command") or "")
    if not command.strip():
        return None
    lowered = command.lower()
    for marker in _SHELL_FORBIDDEN_MARKERS:
        if marker.lower() in lowered:
            return marker
    return None


def _collect_path_candidates(node: Any, *, bucket: list[str]) -> None:
    if isinstance(node, str):
        text = node.strip()
        if not text:
            return
        if "/" in text or "\\" in text or text.endswith(".py") or text.endswith(".md"):
            bucket.append(text)
        return
    if isinstance(node, dict):
        for key, value in node.items():
            key_text = str(key).lower()
            if key_text in {"path", "file", "file_path", "filepath", "location", "uri"} and isinstance(value, str):
                bucket.append(value)
            _collect_path_candidates(value, bucket=bucket)
        return
    if isinstance(node, list):
        for item in node:
            _collect_path_candidates(item, bucket=bucket)


def _tool_name_suggests_read(update: dict[str, Any]) -> bool:
    for key in ("tool", "toolName", "name", "kind", "type"):
        value = update.get(key)
        if isinstance(value, str) and _TOOL_READ_MARKERS.search(value):
            return True
    return False


def detect_forbidden_read_in_session_update(
    payload: dict[str, Any],
    *,
    scratch_dir: Path,
) -> str | None:
    update = payload.get("update")
    if not isinstance(update, dict):
        return None

    shell_violation = detect_forbidden_shell_bypass(update)
    if shell_violation:
        return shell_violation

    candidates: list[str] = []
    _collect_path_candidates(update, bucket=candidates)

    text = ""
    content = update.get("content")
    if isinstance(content, dict):
        text = str(content.get("text", ""))
    elif isinstance(content, str):
        text = content
    if text.strip():
        _collect_path_candidates({"text": text}, bucket=candidates)
        for match in re.finditer(r"[`'\"]([^`'\"]+(?:/|\\)[^`'\"]+)[`'\"]", text):
            candidates.append(match.group(1))

    tool_suggests_read = _tool_name_suggests_read(update)
    for candidate in candidates:
        if is_forbidden_repo_read(candidate, scratch_dir=scratch_dir):
            return candidate
    if tool_suggests_read and candidates:
        for candidate in candidates:
            if candidate.endswith(".py") or "services" in candidate.replace("\\", "/").lower():
                return candidate
    return None


@dataclass
class TracePolicyMonitor:
    scratch_dir: Path
    violation_count: int = 0
    last_violation_path: str | None = None
    _seen_hashes: set[str] = field(default_factory=set)

    def inspect_session_update(self, payload: dict[str, Any]) -> str | None:
        if not trace_policy_enabled():
            return None
        path = detect_forbidden_read_in_session_update(payload, scratch_dir=self.scratch_dir)
        if not path:
            return None
        digest = json.dumps({"path": path, "update": payload.get("update")}, sort_keys=True, default=str)
        if digest in self._seen_hashes:
            return path
        self._seen_hashes.add(digest)
        self.violation_count += 1
        self.last_violation_path = path
        return path

    def should_abort(self) -> bool:
        return trace_policy_enabled() and self.violation_count >= 2

    def needs_policy_followup(self) -> bool:
        return trace_policy_enabled() and self.violation_count == 1


def build_policy_violation_followup(
    *,
    dialogue_round: int,
    scratch_dir: Path,
    violation_path: str | None,
) -> str:
    from app.composition.acp.prompt_sanitize import scratch_dir_for_prompt

    payload = {
        "dialogueRound": dialogue_round + 1,
        "policyViolation": "read_repo_source",
        "forbiddenAction": "read_repo_source",
        "violationPath": violation_path,
        "scratchDir": scratch_dir_for_prompt(scratch_dir),
        "nextStep": "Use read_author_brief MCP and composition_validate_draft / composition_lint_scratch_file only.",
        "fixRecipe": "Do not Read/Grep repo .py or services/ paths; do not shell python -c into composition.mcp; stay in scratch + MCP tools.",
    }
    return (
        "IN_SESSION_POLICY_REPAIR: repository source read or MCP shell bypass detected.\n"
        "Use MCP tools only (read_author_brief, skill_view, composition_lint_scratch_file, write_material_spec).\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
    )
