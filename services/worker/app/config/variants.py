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
        raise FileNotFoundError(f"Variant registry not found: {registry_path}")
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


def get_variant_entry(variant: str) -> dict[str, Any] | None:
    entry = _load_registry().get(variant)
    return dict(entry) if isinstance(entry, dict) else None


def get_variant_label(variant: str) -> str:
    entry = get_variant_entry(variant)
    if entry is None:
        return variant
    label = entry.get("label")
    return str(label) if label else variant


def get_enabled_variant_ids() -> list[str]:
    enabled: list[str] = []
    for variant_id, entry in sorted(_load_registry().items()):
        if isinstance(entry, dict) and entry.get("enabled") is True:
            enabled.append(variant_id)
    return enabled


def default_variant_ids() -> list[str]:
    defaults = ["high_click", "high_conversion"]
    enabled = set(get_enabled_variant_ids())
    resolved = [variant_id for variant_id in defaults if variant_id in enabled]
    return resolved or get_enabled_variant_ids()


def assert_variants_allowed(variant_ids: list[str]) -> None:
    registry = _load_registry()
    for variant_id in variant_ids:
        entry = registry.get(variant_id)
        if not isinstance(entry, dict):
            raise ValueError(f"Unknown variant: {variant_id}")
        if entry.get("enabled") is not True:
            raise ValueError(f"Variant is disabled: {variant_id}")


def load_all_agent_overrides(variant: str) -> dict[str, dict[str, Any]]:
    entry = get_variant_entry(variant) or {}
    overrides = entry.get("agentOverrides") or {}
    if not isinstance(overrides, dict):
        return {}
    return {
        agent_name: dict(agent_overrides)
        for agent_name, agent_overrides in overrides.items()
        if isinstance(agent_overrides, dict)
    }


def load_variant_material_author_overrides(variant: str) -> dict[str, Any]:
    return load_agent_overrides(variant, "material_author")


def load_variant_packaging_designer_overrides(variant: str) -> dict[str, Any]:
    return load_agent_overrides(variant, "packaging_designer")


def load_variant_material_execution_overrides(variant: str) -> dict[str, Any]:
    """Flat overrides for HF material_author execution (packaging + material hints)."""
    merged: dict[str, Any] = {}
    merged.update(load_variant_packaging_designer_overrides(variant))
    merged.update(load_variant_material_author_overrides(variant))
    return merged


def clear_registry_cache() -> None:
    _load_registry.cache_clear()
