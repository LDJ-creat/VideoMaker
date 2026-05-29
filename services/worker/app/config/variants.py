from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from app.agents.prompt_loader import detect_repo_root


@lru_cache(maxsize=1)
def _load_registry() -> dict[str, Any]:
    registry_path = detect_repo_root() / "packages" / "contracts" / "variants" / "registry.yaml"
    if not registry_path.is_file():
        return {}
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    variants = payload.get("variants")
    return variants if isinstance(variants, dict) else {}


def load_agent_overrides(variant: str, agent_name: str) -> dict[str, Any]:
    variants = _load_registry()
    variant_entry = variants.get(variant) or {}
    if not isinstance(variant_entry, dict):
        return {}
    overrides = variant_entry.get("agentOverrides") or {}
    if not isinstance(overrides, dict):
        return {}
    agent_overrides = overrides.get(agent_name) or {}
    return dict(agent_overrides) if isinstance(agent_overrides, dict) else {}


def load_variant_gap_planner_overrides(variant: str) -> dict[str, Any]:
    return load_agent_overrides(variant, "gap_planner")


def clear_registry_cache() -> None:
    _load_registry.cache_clear()
