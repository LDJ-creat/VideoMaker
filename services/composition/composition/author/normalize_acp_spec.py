from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_MEDIA_NAME_PATTERN = re.compile(
    r"[A-Za-z0-9._-]+\.(?:mp4|webm|mov|mkv|png|jpe?g|webp|gif|bmp)",
    re.IGNORECASE,
)


def is_smoke_empty_spec(spec: dict[str, Any]) -> bool:
    if str(spec.get("template", "")).strip() != "benefit-card":
        return False
    if spec.get("composition"):
        return False
    params = spec.get("params")
    if not isinstance(params, dict):
        return True
    title = str(params.get("title", "")).strip()
    bullets = params.get("bullets")
    bullet_items = [str(item).strip() for item in bullets] if isinstance(bullets, list) else []
    if title or any(bullet_items):
        return False
    return True


def _scratch_basenames(scratch_dir: Path) -> set[str]:
    names: set[str] = set()
    if not scratch_dir.is_dir():
        return names
    for path in scratch_dir.iterdir():
        if path.is_file() and path.stat().st_size > 0:
            names.add(path.name)
    assets_dir = scratch_dir / "assets"
    if assets_dir.is_dir():
        for path in assets_dir.iterdir():
            if path.is_file() and path.stat().st_size > 0:
                names.add(path.name)
    return names


def _replace_path_tokens(value: str, scratch_dir: Path, allowed: set[str]) -> str:
    updated = value.replace("\\", "/")
    if "generated/" in updated.lower() or "/acp-author/" in updated.lower():
        for name in allowed:
            if name in updated:
                return name
        match = _MEDIA_NAME_PATTERN.search(updated)
        if match:
            return match.group(0)
    if updated.startswith("/") or (len(updated) > 1 and updated[1] == ":"):
        basename = Path(updated).name
        if basename in allowed:
            return basename
        match = _MEDIA_NAME_PATTERN.search(updated)
        if match:
            return match.group(0)
    return value


def _normalize_asset_refs(
    refs: list[Any],
    scratch_dir: Path,
    allowed: set[str],
) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for ref in refs:
        if not isinstance(ref, dict):
            continue
        merged = dict(ref)
        uri = str(merged.get("uri", "")).strip()
        if uri:
            merged["uri"] = _replace_path_tokens(uri, scratch_dir, allowed)
        normalized.append(merged)
    return normalized


def _normalize_composition_html(html: str, scratch_dir: Path, allowed: set[str]) -> str:
    def _sub_src(match: re.Match[str]) -> str:
        quote = match.group(1)
        src = match.group(2)
        replacement = _replace_path_tokens(src, scratch_dir, allowed)
        return f"src={quote}{replacement}{quote}"

    return re.sub(r"""src=(["'])([^"']+)\1""", _sub_src, html, flags=re.IGNORECASE)


def normalize_acp_material_spec(
    spec: dict[str, Any],
    scratch_dir: Path,
) -> dict[str, Any]:
    merged = dict(spec)
    allowed = _scratch_basenames(scratch_dir)

    params = merged.get("params")
    if isinstance(params, dict):
        params_copy = dict(params)
        refs = params_copy.get("assetRefs")
        if isinstance(refs, list):
            params_copy["assetRefs"] = _normalize_asset_refs(refs, scratch_dir, allowed)
        merged["params"] = params_copy

    composition = merged.get("composition")
    if isinstance(composition, dict):
        comp_copy = dict(composition)
        body = str(comp_copy.get("bodyHtml", ""))
        if body:
            comp_copy["bodyHtml"] = _normalize_composition_html(body, scratch_dir, allowed)
        merged["composition"] = comp_copy

    return merged
