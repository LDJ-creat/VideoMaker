from __future__ import annotations

import json
import subprocess
from pathlib import Path

from composition.paths import detect_repo_root


def _resolve_hyperframes_argv(*, repo_root: Path | None = None) -> list[str]:
    root = (repo_root or detect_repo_root()).resolve()
    if (root / "node_modules" / ".bin" / "hyperframes.cmd").is_file():
        return [str(root / "node_modules" / ".bin" / "hyperframes.cmd")]
    if (root / "node_modules" / ".bin" / "hyperframes").is_file():
        return [str(root / "node_modules" / ".bin" / "hyperframes")]
    return ["npx", "hyperframes"]


def load_registry_catalog(*, repo_root: Path | None = None) -> dict:
    path = (repo_root or detect_repo_root()) / "services" / "composition" / "composition" / "registry" / "catalog.json"
    return json.loads(path.read_text(encoding="utf-8"))


def allowed_registry_block_ids(*, repo_root: Path | None = None) -> frozenset[str]:
    catalog = load_registry_catalog(repo_root=repo_root)
    blocks = catalog.get("blocks", [])
    return frozenset(str(item.get("id", "")).strip() for item in blocks if isinstance(item, dict) and item.get("id"))


def filter_registry_block_ids(block_ids: list[str], *, repo_root: Path | None = None) -> tuple[list[str], list[str]]:
    allowed = allowed_registry_block_ids(repo_root=repo_root)
    accepted: list[str] = []
    rejected: list[str] = []
    for block_id in block_ids:
        normalized = str(block_id).strip()
        if not normalized:
            continue
        if normalized in allowed:
            accepted.append(normalized)
        else:
            rejected.append(normalized)
    return accepted, rejected


def install_registry_blocks(composition_dir: Path, block_ids: list[str], *, repo_root: Path | None = None) -> list[str]:
    accepted, rejected = filter_registry_block_ids(block_ids, repo_root=repo_root)
    warnings: list[str] = [f"registry block not in catalog: {item}" for item in rejected]
    if not accepted:
        return warnings
    argv = _resolve_hyperframes_argv(repo_root=repo_root)
    for block_id in accepted:
        command = [*argv, "add", block_id, "--yes"]
        try:
            result = subprocess.run(
                command,
                cwd=str(composition_dir),
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError:
            warnings.append(f"hyperframes cli missing; skipped block {block_id}")
            continue
        if result.returncode != 0:
            warnings.append(f"hyperframes add {block_id} failed: {result.stderr.strip() or result.stdout.strip()}")
    return warnings
