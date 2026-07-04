from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from composition.paths import detect_repo_root


@dataclass(frozen=True)
class McpSessionContext:
    scratch_dir: Path
    repo_root: Path
    author_payload: dict[str, Any]
    aspect_ratio: str
    asset_root: Path | None

    @property
    def material_spec_path(self) -> Path:
        return self.scratch_dir / "material-spec.json"

    @classmethod
    def from_environ(cls) -> McpSessionContext:
        scratch_raw = os.environ.get("VM_ACP_SCRATCH_DIR", "").strip()
        if not scratch_raw:
            raise RuntimeError("VM_ACP_SCRATCH_DIR is required for composition MCP server")
        scratch_dir = Path(scratch_raw).resolve()
        scratch_dir.mkdir(parents=True, exist_ok=True)

        repo_root = detect_repo_root()
        repo_env = os.environ.get("VM_REPO_ROOT", "").strip()
        if repo_env:
            repo_root = Path(repo_env).resolve()

        payload: dict[str, Any] = {}
        payload_path = os.environ.get("VM_AUTHOR_PAYLOAD_PATH", "").strip()
        if payload_path:
            payload = json.loads(Path(payload_path).read_text(encoding="utf-8"))

        aspect_ratio = os.environ.get("VM_ASPECT_RATIO", "9:16").strip() or "9:16"
        asset_root_raw = os.environ.get("VM_ASSET_ROOT", "").strip()
        asset_root = Path(asset_root_raw).resolve() if asset_root_raw else None

        return cls(
            scratch_dir=scratch_dir,
            repo_root=repo_root,
            author_payload=payload,
            aspect_ratio=aspect_ratio,
            asset_root=asset_root,
        )
