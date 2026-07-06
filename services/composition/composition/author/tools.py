from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from composition.lint_pipeline import LintContext, lint_material_spec_full, spec_lint_result_to_json
from composition.material_review.preview import (
    render_material_preview_spec,
    review_material_preview_tool,
)
from composition.material_review.session import validate_review_marker, write_review_marker
from composition.registry.installer import load_registry_catalog
from composition.render.hyperframes_cli import HyperFramesCli
from composition.skills.runtime import SkillRuntime
from composition.types import BuildContext


def _material_review_tools_enabled() -> bool:
    raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def material_review_max_rounds() -> int:
    raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_MAX_ROUNDS", "2").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 2


def tool_definitions() -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = [
        {
            "type": "function",
            "function": {
                "name": "skill_view",
                "description": "Read a SKILL.md or references file by location path from available_skills.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string"},
                        "section": {"type": "string"},
                    },
                    "required": ["location"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "registry_list",
                "description": "List curated HyperFrames registry blocks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "role": {"type": "string"},
                    },
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "composition_lint_draft",
                "description": "Build composition from MaterialSpec and run hyperframes lint.",
                "parameters": {
                    "type": "object",
                    "properties": {"spec_json": {"type": "object"}},
                    "required": ["spec_json"],
                },
            },
        },
    ]
    if _material_review_tools_enabled():
        tools.extend(
            [
                {
                    "type": "function",
                    "function": {
                        "name": "render_material_preview",
                        "description": "Render a preview MP4 from MaterialSpec in scratch.",
                        "parameters": {
                            "type": "object",
                            "properties": {"spec_json": {"type": "object"}},
                            "required": ["spec_json"],
                        },
                    },
                },
                {
                    "type": "function",
                    "function": {
                        "name": "review_material_preview",
                        "description": "Review rendered preview against brief; returns MaterialReviewReport.",
                        "parameters": {
                            "type": "object",
                            "properties": {"spec_json": {"type": "object"}},
                            "required": ["spec_json"],
                        },
                    },
                },
            ]
        )
    tools.append(
        {
            "type": "function",
            "function": {
                "name": "submit_material_spec",
                "description": "Submit final MaterialSpec JSON.",
                "parameters": {
                    "type": "object",
                    "properties": {"spec_json": {"type": "object"}},
                    "required": ["spec_json"],
                },
            },
        }
    )
    return tools


class CompositionToolExecutor:
    def __init__(
        self,
        *,
        skill_runtime: SkillRuntime,
        build_ctx: BuildContext,
        lint_root: Path,
        hyperframes_cli: HyperFramesCli | None = None,
        repo_root: Path | None = None,
        author_payload: dict[str, Any] | None = None,
        review_gateway: Any | None = None,
    ) -> None:
        self._runtime = skill_runtime
        self._build_ctx = build_ctx
        self._lint_root = lint_root
        self._repo_root = repo_root
        self._cli = hyperframes_cli or HyperFramesCli(repo_root=repo_root)
        self._author_payload = author_payload or {}
        self._review_gateway = review_gateway
        self._last_review_report: dict[str, Any] | None = None
        self._review_rounds_used = 0

    def execute(self, name: str, arguments: dict[str, Any]) -> str:
        if name == "skill_view":
            try:
                content = self._runtime.skill_view(
                    str(arguments["location"]),
                    section=arguments.get("section"),
                )
                return content
            except (FileNotFoundError, ValueError) as exc:
                return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
        if name == "registry_list":
            catalog = load_registry_catalog()
            blocks = catalog.get("blocks", [])
            category = arguments.get("category")
            role = arguments.get("role")
            filtered = []
            for block in blocks:
                if category and block.get("category") != category:
                    continue
                if role and role not in (block.get("suggestedRoles") or []):
                    continue
                filtered.append(block)
            return json.dumps(filtered, ensure_ascii=False)
        if name == "composition_lint_draft":
            spec = arguments.get("spec_json")
            if not isinstance(spec, dict):
                return json.dumps({"ok": False, "errors": ["spec_json must be object"]})
            schema_only = bool(arguments.get("schema_only"))
            from composition.paths import detect_repo_root

            repo = self._repo_root.resolve() if self._repo_root else detect_repo_root()
            lint_ctx = LintContext(
                scratch_dir=self._lint_root.resolve(),
                repo_root=repo,
                author_payload=self._author_payload,
                aspect_ratio=self._build_ctx.aspect_ratio,
                asset_root=self._build_ctx.asset_root,
            )
            errors, result = lint_material_spec_full(
                spec,
                lint_ctx,
                schema_only=schema_only,
                cli=self._cli,
            )
            if result is None:
                return json.dumps({"ok": False, "errors": errors or ["lint failed"]}, ensure_ascii=False)
            payload = spec_lint_result_to_json(result)
            payload["ok"] = not errors
            if errors:
                payload["errors"] = errors
            return json.dumps(payload, ensure_ascii=False)
        if name == "render_material_preview":
            spec = arguments.get("spec_json")
            if not isinstance(spec, dict):
                return json.dumps({"ok": False, "errors": ["spec_json must be object"]}, ensure_ascii=False)
            from composition.paths import detect_repo_root

            repo = self._repo_root.resolve() if self._repo_root else detect_repo_root()
            payload = render_material_preview_spec(
                spec,
                scratch_dir=self._lint_root.resolve(),
                repo_root=repo,
                aspect_ratio=self._build_ctx.aspect_ratio,
                asset_root=self._build_ctx.asset_root,
            )
            return json.dumps(payload, ensure_ascii=False)
        if name == "review_material_preview":
            spec = arguments.get("spec_json")
            if not isinstance(spec, dict):
                return json.dumps({"ok": False, "errors": ["spec_json must be object"]}, ensure_ascii=False)
            from composition.paths import detect_repo_root

            repo = self._repo_root.resolve() if self._repo_root else detect_repo_root()
            scratch = self._lint_root.resolve()
            if validate_review_marker(scratch, spec) is None:
                observation = review_material_preview_tool(
                    spec_json=spec,
                    scratch_dir=scratch,
                    repo_root=repo,
                    author_payload=self._author_payload,
                    aspect_ratio=self._build_ctx.aspect_ratio,
                    asset_root=self._build_ctx.asset_root,
                    review_gateway=self._review_gateway,
                )
            elif self._review_rounds_used >= material_review_max_rounds():
                return json.dumps(
                    {
                        "ok": False,
                        "error": "review_rounds_exhausted",
                        "reviewRoundsUsed": self._review_rounds_used,
                        "reviewMaxRounds": material_review_max_rounds(),
                    },
                    ensure_ascii=False,
                )
            else:
                observation = review_material_preview_tool(
                    spec_json=spec,
                    scratch_dir=scratch,
                    repo_root=repo,
                    author_payload=self._author_payload,
                    aspect_ratio=self._build_ctx.aspect_ratio,
                    asset_root=self._build_ctx.asset_root,
                    review_gateway=self._review_gateway,
                )
                try:
                    parsed = json.loads(observation)
                    if not parsed.get("cached") and not parsed.get("skipped"):
                        self._review_rounds_used += 1
                except json.JSONDecodeError:
                    self._review_rounds_used += 1
            try:
                parsed = json.loads(observation)
                if isinstance(parsed, dict) and isinstance(parsed.get("report"), dict):
                    self._last_review_report = parsed["report"]
                    if parsed.get("ok"):
                        write_review_marker(
                            self._lint_root.resolve(),
                            spec=spec,
                            report=parsed["report"],
                        )
            except json.JSONDecodeError:
                pass
            return observation
        if name == "submit_material_spec":
            spec = arguments.get("spec_json")
            if not isinstance(spec, dict):
                return json.dumps(
                    {"accepted": False, "error": "spec_json must be object"},
                    ensure_ascii=False,
                )
            if _material_review_tools_enabled():
                review_error = validate_review_marker(self._lint_root.resolve(), spec)
                if review_error:
                    return json.dumps(
                        {
                            "accepted": False,
                            "error": review_error,
                            "reviewReport": self._last_review_report,
                        },
                        ensure_ascii=False,
                    )
            return json.dumps({"accepted": True, "spec": spec})
        return json.dumps({"error": f"unknown tool {name}"})
