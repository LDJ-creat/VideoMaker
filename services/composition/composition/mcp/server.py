from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from composition.mcp.context import McpSessionContext
from composition.mcp.handlers import (
    handle_composition_lint_draft,
    handle_registry_list,
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
def composition_lint_draft(spec_json: dict) -> str:
    """Build composition from MaterialSpec and run hyperframes lint."""
    return handle_composition_lint_draft(_ctx(), spec_json=spec_json)


@mcp.tool()
def write_material_spec(spec_json: dict) -> str:
    """Validate, lint, and write MaterialSpec JSON to the session scratch directory."""
    return handle_write_material_spec(_ctx(), spec_json=spec_json)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
