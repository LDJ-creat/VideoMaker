from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from composition.aspect_ratio import render_dimensions
from composition.build.composition_shell import write_hyperframes_json, write_index_html
from composition.build.html_safety import HtmlSafetyError, validate_composition_fragment
from composition.build.legacy_scaffold import (
    MaterialScaffoldError,
    build_composition as build_legacy_composition,
    collect_project_sandbox_paths,
    ensure_paths_in_project_sandbox,
    validate_material_spec,
)
from composition.build.media_staging import MediaStagingError, normalize_and_stage_composition_media
from composition.registry.installer import install_registry_blocks
from composition.schema_loader import validate_contract


def _resolve_asset_refs(
    asset_refs: list[dict[str, Any]] | None,
    *,
    asset_root: Path | None,
    composition_dir: Path,
) -> None:
    if not asset_refs:
        return
    assets_dir = composition_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    if asset_root is None:
        return
    root = asset_root.resolve()
    for ref in asset_refs:
        if not isinstance(ref, dict):
            continue
        uri = str(ref.get("uri", "")).strip()
        if not uri:
            continue
        source = (root / uri).resolve() if not Path(uri).is_absolute() else Path(uri).resolve()
        if not source.is_relative_to(root):
            raise MaterialScaffoldError("assetRef uri escapes asset sandbox")
        if source.is_file():
            dest = assets_dir / source.name
            if source.resolve() != dest.resolve():
                shutil.copy2(source, dest)


def _build_composition_template(
    spec: dict[str, Any],
    output_dir: Path,
    *,
    asset_root: Path | None,
    aspect_ratio: str,
) -> Path:
    composition = spec.get("composition")
    if not isinstance(composition, dict):
        raise MaterialScaffoldError("composition template requires composition object")
    body_html = str(composition.get("bodyHtml", "")).strip()
    if not body_html:
        raise MaterialScaffoldError("composition.bodyHtml is required")
    styles = str(composition.get("styles") or "")
    timeline_script = str(composition.get("timelineScript") or "")
    validate_composition_fragment(
        body_html=body_html,
        styles=styles,
        timeline_script=timeline_script,
    )
    canvas_width, canvas_height = render_dimensions(aspect_ratio)
    output_dir.mkdir(parents=True, exist_ok=True)
    refs = spec.get("params", {}).get("assetRefs") if isinstance(spec.get("params"), dict) else None
    if isinstance(refs, list):
        _resolve_asset_refs(refs, asset_root=asset_root, composition_dir=output_dir)
    block_ids = composition.get("registryBlocks")
    if isinstance(block_ids, list) and block_ids:
        rejected = install_registry_blocks(
            output_dir,
            [str(item) for item in block_ids if str(item).strip()],
        )
        if any("not in catalog" in item for item in rejected):
            unknown = [item.split(": ", 1)[-1] for item in rejected if "not in catalog" in item]
            raise MaterialScaffoldError(f"Unknown registryBlocks: {', '.join(unknown)}")
    if not timeline_script.strip():
        timeline_script = 'tl.set("#root", { autoAlpha: 1 }, 0);'
    write_hyperframes_json(output_dir)
    try:
        body_html = normalize_and_stage_composition_media(
            output_dir,
            asset_root=asset_root,
            html=body_html,
        )
    except MediaStagingError as exc:
        raise MaterialScaffoldError(str(exc)) from exc
    write_index_html(
        composition_dir=output_dir,
        body_html=body_html,
        styles=styles,
        timeline_script=timeline_script,
        duration_sec=float(spec["durationSec"]),
        canvas_width=canvas_width,
        canvas_height=canvas_height,
    )
    return output_dir


def build_composition(
    spec: dict[str, Any],
    output_dir: Path,
    *,
    asset_root: Path | None = None,
    project_root: Path | None = None,
    aspect_ratio: str = "9:16",
) -> Path:
    validation = validate_material_spec(spec)
    if not validation.valid:
        messages = "; ".join(error.message for error in validation.errors)
        raise MaterialScaffoldError(f"Invalid MaterialSpec: {messages}")

    output_dir = output_dir.resolve()
    if project_root is not None:
        ensure_paths_in_project_sandbox(
            project_root,
            *collect_project_sandbox_paths(project_root, output_dir, asset_root),
        )

    template = str(spec.get("template", ""))
    if template == "composition":
        try:
            return _build_composition_template(
                spec,
                output_dir,
                asset_root=asset_root,
                aspect_ratio=aspect_ratio,
            )
        except HtmlSafetyError as exc:
            raise MaterialScaffoldError(str(exc)) from exc
    return build_legacy_composition(
        spec,
        output_dir,
        asset_root=asset_root,
        project_root=project_root,
        aspect_ratio=aspect_ratio,
    )


def validate_spec_dict(spec: dict[str, Any]) -> bool:
    return validate_contract("material-spec", spec).valid
