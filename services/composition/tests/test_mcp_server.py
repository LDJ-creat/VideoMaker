from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
COMPOSITION_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = COMPOSITION_ROOT.parents[1]


def _server_env(scratch: Path, payload_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["VM_ACP_SCRATCH_DIR"] = str(scratch)
    env["VM_REPO_ROOT"] = str(REPO_ROOT)
    env["VM_AUTHOR_PAYLOAD_PATH"] = str(payload_path)
    env["VM_ASPECT_RATIO"] = "9:16"
    env["VM_ACP_FIXTURE_LINT"] = "1"
    env["PYTHONPATH"] = os.pathsep.join(
        [str(COMPOSITION_ROOT), str(REPO_ROOT / "services" / "shared"), env.get("PYTHONPATH", "")]
    )
    return env


@pytest.fixture
def mcp_scratch(tmp_path: Path) -> tuple[Path, Path]:
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    payload_path = scratch / "task.json"
    payload_path.write_text(
        json.dumps(
            {
                "slot": {"role": "benefit_card", "scriptIntent": "show benefits", "visualIntent": "cards"},
                "renderPolicy": {"forbidVoiceoverText": True},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return scratch, payload_path


async def _call_tool(params: StdioServerParameters, tool_name: str, arguments: dict) -> str:
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
    return result.content[0].text if result.content else ""


def test_mcp_skill_view(mcp_scratch: tuple[Path, Path]) -> None:
    scratch, payload_path = mcp_scratch
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "composition.mcp.server"],
        env=_server_env(scratch, payload_path),
        cwd=str(REPO_ROOT),
    )
    text = asyncio.run(
        _call_tool(params, "skill_view", {"location": "skills/public/hyperframes/SKILL.md"}),
    )
    assert "HyperFrames" in text or "hyperframes" in text.lower()


def test_mcp_write_material_spec(mcp_scratch: tuple[Path, Path]) -> None:
    scratch, payload_path = mcp_scratch
    spec = {
        "template": "benefit-card",
        "durationSec": 3,
        "params": {
            "title": "Test",
            "bullets": ["One"],
            "colors": {"primary": "#2563eb", "background": "#0f172a", "text": "#ffffff"},
        },
    }
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "composition.mcp.server"],
        env=_server_env(scratch, payload_path),
        cwd=str(REPO_ROOT),
    )
    raw = asyncio.run(_call_tool(params, "write_material_spec", {"spec_json": spec}))
    payload = json.loads(raw)
    assert payload["ok"] is True
    written = json.loads((scratch / "material-spec.json").read_text(encoding="utf-8"))
    assert written["template"] == "benefit-card"
