from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _read_json(path: Path) -> Any | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def resolve_evaluation_profile(
    generation_root: Path,
    *,
    variant_id: str | None = None,
) -> dict[str, Any]:
    structure = (
        _read_json(generation_root / "structure-scaled.json")
        or _read_json(generation_root / "synthesized-structure.json")
        or _read_json(generation_root / "video-structure.json")
    )

    inventory = _read_json(generation_root / "asset-inventory.json") or {}

    input_mode = "greenfield"
    enabled = ["core"]
    reference_structure_id: str | None = None
    knowledge_entry_id: str | None = None

    source_kind = None
    if isinstance(structure, dict):
        reference_structure_id = str(structure.get("sampleId") or structure.get("id") or "") or None
        meta = structure.get("metadata") if isinstance(structure.get("metadata"), dict) else {}
        source_kind = meta.get("sourceKind") or structure.get("sourceKind")
        source_video = str(structure.get("sourceVideoId") or "")
        if source_kind == "knowledge" or source_video.startswith("knowledge-"):
            input_mode = "knowledge_guided"
            enabled.append("knowledge_fit")
            if source_video.startswith("knowledge-"):
                knowledge_entry_id = source_video.replace("knowledge-", "", 1)
        elif reference_structure_id:
            input_mode = "sample_migration"
            enabled.append("migration")

    if input_mode == "greenfield":
        route = str(inventory.get("assetUnderstandingRoute") or "")
        if route != "baseline_only" and isinstance(structure, dict) and structure.get("slots"):
            input_mode = "knowledge_guided"
            if "knowledge_fit" not in enabled:
                enabled.append("knowledge_fit")

    selection = _read_json(generation_root.parent.parent / "sample-selection.json")
    if isinstance(selection, dict) and input_mode == "greenfield":
        primary = selection.get("primarySampleId")
        if primary:
            input_mode = "sample_migration"
            if "migration" not in enabled:
                enabled.append("migration")
            if "knowledge_fit" in enabled:
                enabled.remove("knowledge_fit")

    profile: dict[str, Any] = {
        "inputMode": input_mode,
        "enabledModules": sorted(set(enabled), key=lambda x: ["core", "migration", "knowledge_fit"].index(x)),
    }
    if reference_structure_id:
        profile["referenceStructureId"] = reference_structure_id
    if knowledge_entry_id:
        profile["knowledgeEntryId"] = knowledge_entry_id
    if variant_id:
        profile["variantId"] = variant_id
    return profile
