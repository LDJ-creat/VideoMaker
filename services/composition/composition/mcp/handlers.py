from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from composition.author.lint_errors import enrich_lint_errors
from composition.author.tools import CompositionToolExecutor
from composition.lint_pipeline import (
    LintContext,
    lint_material_spec_full,
    spec_lint_result_to_json,
    validate_spec_gate,
)
from composition.mcp.context import McpSessionContext
from composition.material_review.preview import (
    render_material_preview_spec,
    review_material_preview_tool,
)
from composition.material_review.session import validate_review_marker, write_review_marker
from composition.render.hyperframes_cli import HyperFramesCli, fixture_command_runner
from composition.schema_loader import validate_contract
from composition.skills.runtime import SkillRuntime
from composition.types import BuildContext


def _hyperframes_cli(repo_root: Path) -> HyperFramesCli:
    if os.getenv("VM_ACP_FIXTURE_LINT", "").strip().lower() in {"1", "true", "yes"}:
        return HyperFramesCli(command_runner=fixture_command_runner(), repo_root=repo_root)
    return HyperFramesCli(repo_root=repo_root)


def _lint_context(ctx: McpSessionContext) -> LintContext:
    return LintContext.from_mcp(ctx)


def create_executor(ctx: McpSessionContext) -> CompositionToolExecutor:
    ctx.scratch_dir.mkdir(parents=True, exist_ok=True)
    runtime = SkillRuntime(repo_root=ctx.repo_root)
    build_ctx = BuildContext(
        project_root=ctx.scratch_dir,
        output_dir=ctx.scratch_dir,
        asset_root=ctx.asset_root,
        aspect_ratio=ctx.aspect_ratio,
    )
    return CompositionToolExecutor(
        skill_runtime=runtime,
        build_ctx=build_ctx,
        lint_root=ctx.scratch_dir,
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


def handle_composition_lint_draft(
    ctx: McpSessionContext,
    *,
    spec_json: dict[str, Any],
    schema_only: bool = False,
) -> str:
    if not isinstance(spec_json, dict):
        return json.dumps({"ok": False, "errors": ["spec_json must be object"]}, ensure_ascii=False)
    lint_ctx = _lint_context(ctx)
    errors, result = lint_material_spec_full(
        spec_json,
        lint_ctx,
        schema_only=schema_only,
        cli=_hyperframes_cli(ctx.repo_root),
    )
    if result is None:
        return json.dumps({"ok": False, "errors": errors or ["lint failed"]}, ensure_ascii=False)
    if errors:
        payload = spec_lint_result_to_json(result)
        payload["ok"] = False
        payload.update(enrich_lint_errors(errors))
        return json.dumps(payload, ensure_ascii=False)
    payload = spec_lint_result_to_json(result)
    payload["ok"] = True
    return json.dumps(payload, ensure_ascii=False)


def lint_material_spec(
    ctx: McpSessionContext,
    *,
    spec_json: dict[str, Any],
    skip_hf_if_cached: bool = False,
) -> list[str]:
    """Run validate + build + hyperframes lint; return error strings (empty when ok)."""
    errors, _ = lint_material_spec_full(
        spec_json,
        _lint_context(ctx),
        skip_hf_if_cached=skip_hf_if_cached,
        cli=_hyperframes_cli(ctx.repo_root),
    )
    return errors


def handle_render_material_preview(ctx: McpSessionContext, *, spec_json: dict[str, Any]) -> str:
    if not isinstance(spec_json, dict):
        return json.dumps({"ok": False, "errors": ["spec_json must be object"]}, ensure_ascii=False)
    payload = render_material_preview_spec(
        spec_json,
        scratch_dir=ctx.scratch_dir,
        repo_root=ctx.repo_root,
        aspect_ratio=ctx.aspect_ratio,
        asset_root=ctx.asset_root,
    )
    return json.dumps(payload, ensure_ascii=False)


def _material_review_gate_enabled() -> bool:
    raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true").strip().lower()
    if raw in {"0", "false", "no", "off"}:
        return False
    in_session = os.getenv("VM_ACP_IN_SESSION_REVIEW", "true").strip().lower()
    return in_session not in {"0", "false", "no", "off"}


def handle_review_material_preview(ctx: McpSessionContext, *, spec_json: dict[str, Any]) -> str:
    if not isinstance(spec_json, dict):
        return json.dumps({"ok": False, "errors": ["spec_json must be object"]}, ensure_ascii=False)
    if not _material_review_gate_enabled():
        return json.dumps(
            {
                "ok": True,
                "skipped": True,
                "reason": "in_session_review_disabled",
                "report": {"approved": True, "issues": [], "suggestions": []},
            },
            ensure_ascii=False,
        )
    observation = review_material_preview_tool(
        spec_json=spec_json,
        scratch_dir=ctx.scratch_dir,
        repo_root=ctx.repo_root,
        author_payload=ctx.author_payload,
        aspect_ratio=ctx.aspect_ratio,
        asset_root=ctx.asset_root,
    )
    if _material_review_gate_enabled():
        try:
            parsed = json.loads(observation)
            if isinstance(parsed, dict) and parsed.get("ok") and isinstance(parsed.get("report"), dict):
                write_review_marker(ctx.scratch_dir, spec=spec_json, report=parsed["report"])
        except json.JSONDecodeError:
            pass
    return observation


def handle_write_material_spec(ctx: McpSessionContext, *, spec_json: dict[str, Any]) -> str:
    if not isinstance(spec_json, dict):
        return json.dumps({"ok": False, "errors": ["spec_json must be object"]}, ensure_ascii=False)

    if _material_review_gate_enabled():
        review_error = validate_review_marker(ctx.scratch_dir, spec_json)
        if review_error:
            return json.dumps({"ok": False, "errors": [review_error]}, ensure_ascii=False)

    gate_errors = validate_spec_gate(spec_json, ctx.author_payload)
    if gate_errors:
        payload = {"ok": False, "errors": gate_errors}
        payload.update(enrich_lint_errors(gate_errors))
        return json.dumps(payload, ensure_ascii=False)

    skip_lint = os.getenv("VIDEOMAKER_MCP_WRITE_SKIP_LINT", "").strip().lower() in {"1", "true", "yes"}
    if not skip_lint:
        lint_errors = lint_material_spec(ctx, spec_json=spec_json)
        if lint_errors:
            payload = {"ok": False, "errors": lint_errors}
            payload.update(enrich_lint_errors(lint_errors))
            return json.dumps(payload, ensure_ascii=False)

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
