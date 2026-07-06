from __future__ import annotations

import re
from pathlib import Path

_INFRA_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"AgentRunLog", re.I), "review_infra_unavailable"),
    (re.compile(r"ValidationErrorItem", re.I), "review_infra_unavailable"),
    (re.compile(r"tokenUsage", re.I), "review_infra_unavailable"),
    (re.compile(r"review_failed", re.I), "material_review_failed"),
    (re.compile(r"preview_render_failed", re.I), "preview_render_failed"),
    (re.compile(r"sandbox|path_escape|generated/", re.I), "lint_sandbox_path"),
    (re.compile(r"missing_material_spec|missing spec", re.I), "missing_material_spec"),
)

_WINDOWS_ABS = re.compile(r"[A-Za-z]:\\[^\s\"']+")
_UNIX_ABS = re.compile(r"/(?:Users|home|VideoMaker|services|projects)[^\s\"']*")
_PY_REF = re.compile(r"[\w./\\-]+\.py\b")


def sanitize_gate_error(message: str) -> str:
    text = str(message or "").strip()
    if not text:
        return "validation_failed"
    for pattern, code in _INFRA_PATTERNS:
        if pattern.search(text):
            return code
    text = _WINDOWS_ABS.sub("<path>", text)
    text = _UNIX_ABS.sub("<path>", text)
    text = _PY_REF.sub("<source>", text)
    if len(text) > 240:
        text = text[:237] + "..."
    return text


def sanitize_gate_errors(errors: list[str]) -> list[str]:
    seen: set[str] = set()
    cleaned: list[str] = []
    for item in errors:
        normalized = sanitize_gate_error(item)
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned or ["validation_failed"]


def scratch_dir_for_prompt(scratch_dir: Path) -> str:
    return scratch_dir.name or "scratch"
