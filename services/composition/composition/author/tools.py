from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from composition.build.composition_builder import build_composition
from composition.registry.installer import load_registry_catalog
from composition.render.hyperframes_cli import HyperFramesCli
from composition.skills.runtime import SkillRuntime
from composition.types import BuildContext


def tool_definitions() -> list[dict[str, Any]]:
    return [
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
        },
    ]


class CompositionToolExecutor:
    def __init__(
        self,
        *,
        skill_runtime: SkillRuntime,
        build_ctx: BuildContext,
        lint_root: Path,
        hyperframes_cli: HyperFramesCli | None = None,
        repo_root: Path | None = None,
    ) -> None:
        self._runtime = skill_runtime
        self._build_ctx = build_ctx
        self._lint_root = lint_root
        self._cli = hyperframes_cli or HyperFramesCli(repo_root=repo_root)

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
            draft_dir = self._lint_root / "lint-draft"
            draft_dir.mkdir(parents=True, exist_ok=True)
            try:
                build_composition(
                    spec,
                    draft_dir,
                    asset_root=self._build_ctx.asset_root,
                    project_root=self._build_ctx.project_root,
                    aspect_ratio=self._build_ctx.aspect_ratio,
                )
            except Exception as exc:
                return json.dumps({"ok": False, "errors": [str(exc)]})
            lint = self._cli.lint(draft_dir, draft_dir / "lint-log.json")
            return json.dumps(lint, ensure_ascii=False)
        if name == "submit_material_spec":
            return json.dumps({"accepted": True, "spec": arguments.get("spec_json")})
        return json.dumps({"error": f"unknown tool {name}"})
