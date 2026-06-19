from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from composition.author.forbidden_copy_guard import check_forbidden_copy_in_spec
from composition.author.tools import CompositionToolExecutor
from composition.mcp.context import McpSessionContext
from composition.render.hyperframes_cli import HyperFramesCli, fixture_command_runner
from composition.schema_loader import validate_contract
from composition.skills.runtime import SkillRuntime
from composition.types import BuildContext


def _hyperframes_cli(repo_root: Path) -> HyperFramesCli:
    if os.getenv("VM_ACP_FIXTURE_LINT", "").strip().lower() in {"1", "true", "yes"}:
        return HyperFramesCli(command_runner=fixture_command_runner(), repo_root=repo_root)
    return HyperFramesCli(repo_root=repo_root)


def create_executor(ctx: McpSessionContext) -> CompositionToolExecutor:
    lint_root = ctx.scratch_dir / "mcp-session"
    lint_root.mkdir(parents=True, exist_ok=True)
    runtime = SkillRuntime(repo_root=ctx.repo_root)
    build_ctx = BuildContext(
        project_root=ctx.scratch_dir,
        output_dir=lint_root,
        asset_root=ctx.asset_root,
        aspect_ratio=ctx.aspect_ratio,
    )
    return CompositionToolExecutor(
        skill_runtime=runtime,
        build_ctx=build_ctx,
        lint_root=lint_root,
        hyperframes_cli=_hyperframes_cli(ctx.repo_root),
        repo_root=ctx.repo_root,
        author_payload=ctx.author_payload,
    )


def handle_skill_view(ctx: McpSessionContext, *, location: str, section: str | None = None) -> str:
    return create_executor(ctx).execute(
        "skill_view",
        {"location": location, **({"section": section} if section else {})},
    )


def handle_registry_list(
    ctx: McpSessionContext,
    *,
    category: str | None = None,
    role: str | None = None,
) -> str:
    args: dict[str, Any] = {}
    if category:
        args["category"] = category
    if role:
        args["role"] = role
    return create_executor(ctx).execute("registry_list", args)


def handle_composition_lint_draft(ctx: McpSessionContext, *, spec_json: dict[str, Any]) -> str:
    return create_executor(ctx).execute("composition_lint_draft", {"spec_json": spec_json})


def lint_material_spec(ctx: McpSessionContext, *, spec_json: dict[str, Any]) -> list[str]:
    """Run build + hyperframes lint; return error strings (empty when ok)."""
    raw = handle_composition_lint_draft(ctx, spec_json=spec_json)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return [raw]
    if payload.get("ok"):
        return []
    errors = payload.get("errors")
    if isinstance(errors, list):
        return [str(item) for item in errors]
    return [raw]


def handle_write_material_spec(ctx: McpSessionContext, *, spec_json: dict[str, Any]) -> str:
    if not isinstance(spec_json, dict):
        return json.dumps({"ok": False, "errors": ["spec_json must be object"]}, ensure_ascii=False)

    schema_result = validate_contract("material-spec", spec_json)
    if not schema_result.valid:
        errors = [f"{item.path}: {item.message}" for item in schema_result.errors]
        return json.dumps({"ok": False, "errors": errors}, ensure_ascii=False)

    copy_errors = check_forbidden_copy_in_spec(spec_json, ctx.author_payload)
    if copy_errors:
        return json.dumps({"ok": False, "errors": copy_errors}, ensure_ascii=False)

    lint_errors = lint_material_spec(ctx, spec_json=spec_json)
    if lint_errors:
        return json.dumps({"ok": False, "errors": lint_errors}, ensure_ascii=False)

    target = ctx.material_spec_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(spec_json, ensure_ascii=False, indent=2), encoding="utf-8")
    lint_marker = ctx.scratch_dir / "material-spec.lint-passed"
    lint_marker.write_text("ok\n", encoding="utf-8")
    return json.dumps(
        {"ok": True, "path": str(target)},
        ensure_ascii=False,
    )


def read_material_spec(ctx: McpSessionContext) -> dict[str, Any] | None:
    path = ctx.material_spec_path
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None
