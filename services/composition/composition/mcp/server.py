from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from composition.mcp.context import McpSessionContext
from composition.mcp.handlers import (
    handle_composition_lint_draft,
    handle_composition_lint_scratch_file,
    handle_composition_validate_draft,
    handle_read_author_brief,
    handle_registry_list,
    handle_render_material_preview,
    handle_review_material_preview,
    handle_skill_view,
    handle_write_material_spec,
)

mcp = FastMCP("videomaker-composition")


def _ctx() -> McpSessionContext:
    return McpSessionContext.from_environ()


@mcp.tool()
def skill_view(location: str, section: str | None = None) -> str:
    """Read a SKILL.md or references file by location path from available_skills."""
    return handle_skill_view(_ctx(), location=location, section=section)


@mcp.tool()
def registry_list(category: str | None = None, role: str | None = None) -> str:
    """List curated HyperFrames registry blocks."""
    return handle_registry_list(_ctx(), category=category, role=role)


@mcp.tool()
def read_author_brief() -> str:
    """Return author brief JSON (slot, authorContract, editInstruction) from scratch task payload."""
    return handle_read_author_brief(_ctx())


@mcp.tool()
def composition_validate_draft(spec_json: dict) -> str:
    """Fast schema + copy-guard validation only (no HyperFrames render)."""
    return handle_composition_validate_draft(_ctx(), spec_json=spec_json)


@mcp.tool()
def composition_lint_draft(spec_json: dict) -> str:
    """Build composition from MaterialSpec and run hyperframes lint.

    WHEN: After drafting or editing MaterialSpec JSON.
    NEVER: shell python, Read repo source, VM_ACP_FIXTURE_LINT.
    TIMEOUT: 90s.
    """
    return handle_composition_lint_draft(_ctx(), spec_json=spec_json)


@mcp.tool()
def composition_lint_scratch_file(relative_path: str = "draft.json") -> str:
    """Lint a JSON spec file under scratch (relative path only). NEVER use shell python."""
    return handle_composition_lint_scratch_file(_ctx(), relative_path=relative_path)


@mcp.tool()
def render_material_preview(spec_json: dict) -> str:
    """Render a scratch preview MP4 from MaterialSpec for material review."""
    return handle_render_material_preview(_ctx(), spec_json=spec_json)


@mcp.tool()
def review_material_preview(spec_json: dict) -> str:
    """Run material_reviewer against the scratch preview and return a review report."""
    return handle_review_material_preview(_ctx(), spec_json=spec_json)


@mcp.tool()
def write_material_spec(spec_json: dict) -> str:
    """Validate, lint, and write MaterialSpec JSON to the session scratch directory."""
    return handle_write_material_spec(_ctx(), spec_json=spec_json)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
