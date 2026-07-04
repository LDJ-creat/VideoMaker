from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

from acp import PROTOCOL_VERSION, run_agent, text_block
from acp.schema import (
    AgentCapabilities,
    InitializeResponse,
    Implementation,
    NewSessionResponse,
    PromptResponse,
)


class FakeCompositionAgent:
    def __init__(self) -> None:
        self._client = None

    def on_connect(self, conn) -> None:
        self._client = conn

    async def initialize(
        self,
        protocol_version: int,
        client_capabilities=None,
        client_info=None,
        **kwargs,
    ) -> InitializeResponse:
        _ = protocol_version, client_capabilities, client_info, kwargs
        return InitializeResponse(
            protocol_version=PROTOCOL_VERSION,
            agent_capabilities=AgentCapabilities(),
            agent_info=Implementation(name="fake-composition-agent", version="0.1.0"),
        )

    async def new_session(
        self,
        cwd: str,
        additional_directories=None,
        mcp_servers=None,
        **kwargs,
    ) -> NewSessionResponse:
        _ = cwd, additional_directories, mcp_servers, kwargs
        return NewSessionResponse(session_id="fake-acp-session")

    async def prompt(self, prompt, session_id: str, message_id=None, **kwargs) -> PromptResponse:
        _ = prompt, message_id, kwargs
        scratch = Path(os.environ["VM_ACP_SCRATCH_DIR"]).resolve()
        scratch.mkdir(parents=True, exist_ok=True)
        spec_path = scratch / "material-spec.json"

        fixture = os.environ.get("VM_ACP_FIXTURE_SPEC", "").strip()
        if fixture:
            spec = json.loads(Path(fixture).read_text(encoding="utf-8"))
        else:
            spec = {
                "template": "benefit-card",
                "durationSec": 3,
                "params": {
                    "title": "ACP Test",
                    "bullets": ["One"],
                    "colors": {"primary": "#2563eb", "background": "#0f172a", "text": "#ffffff"},
                },
            }

        assert self._client is not None
        await self._client.write_text_file(
            json.dumps(spec, ensure_ascii=False, indent=2),
            str(spec_path),
            session_id,
        )
        return PromptResponse(stop_reason="end_turn")

    async def cancel(self, session_id: str, **kwargs) -> None:
        _ = session_id, kwargs


async def _main() -> None:
    await run_agent(FakeCompositionAgent())


if __name__ == "__main__":
    asyncio.run(_main())
