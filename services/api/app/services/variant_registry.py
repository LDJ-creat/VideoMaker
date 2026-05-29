from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / "packages" / "contracts" / "variants" / "registry.yaml").is_file():
            return parent
    raise FileNotFoundError("Could not locate packages/contracts/variants/registry.yaml")


@lru_cache(maxsize=1)
def _load_registry() -> dict[str, Any]:
    registry_path = _repo_root() / "packages" / "contracts" / "variants" / "registry.yaml"
    payload = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    variants = payload.get("variants")
    return variants if isinstance(variants, dict) else {}


def get_variant_label(variant_id: str) -> str:
    entry = _load_registry().get(variant_id) or {}
    label = entry.get("label") if isinstance(entry, dict) else None
    return str(label) if label else variant_id


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


def resolve_requested_variants(variants: list[str] | None) -> list[str]:
    requested = list(variants) if variants else default_variant_ids()
    if not requested:
        raise ValueError("No enabled variants configured")
    seen: set[str] = set()
    for variant_id in requested:
        if variant_id in seen:
            raise ValueError(f"Duplicate variant: {variant_id}")
        seen.add(variant_id)
    assert_variants_allowed(requested)
    return requested


def assert_variants_allowed(variant_ids: list[str]) -> None:
    registry = _load_registry()
    for variant_id in variant_ids:
        entry = registry.get(variant_id)
        if not isinstance(entry, dict):
            raise ValueError(f"Unknown variant: {variant_id}")
        if entry.get("enabled") is not True:
            raise ValueError(f"Variant is disabled: {variant_id}")


def clear_registry_cache() -> None:
    _load_registry.cache_clear()
