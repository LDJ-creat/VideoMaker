from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

MaterialScope = str


def material_review_enabled() -> bool:
    raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_ENABLED", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def material_review_on_revise_enabled() -> bool:
    raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_ON_REVISE", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def build_material_review_revise_context_payload(
    *,
    source_generation_id: str,
    material_scope: MaterialScope,
    affected_slot_ids: list[str],
    affected_pipeline_stages: list[str],
) -> dict[str, Any]:
    if not material_review_enabled() or not material_review_on_revise_enabled():
        return {}
    if material_scope == "none" or "generating_material" not in affected_pipeline_stages:
        return {}
    if material_scope == "scoped":
        scope_label = "scoped"
    elif material_scope == "all":
        scope_label = "all"
    else:
        return {}
    payload: dict[str, Any] = {
        "materialReviewScope": scope_label,
        "sourceGenerationId": source_generation_id,
    }
    if affected_slot_ids:
        payload["materialReviewSlotIds"] = affected_slot_ids
    return payload


def parse_material_review_revise_context(payload: dict[str, Any]) -> dict[str, Any] | None:
    scope = payload.get("materialReviewScope")
    if not scope:
        return None
    result: dict[str, Any] = {
        "scope": str(scope),
        "sourceGenerationId": str(payload.get("sourceGenerationId") or ""),
    }
    slot_ids = payload.get("materialReviewSlotIds")
    if isinstance(slot_ids, list):
        result["affectedSlotIds"] = [str(item) for item in slot_ids if str(item).strip()]
    return result


def load_material_review_revise_context(generation_root: Path) -> dict[str, Any] | None:
    path = generation_root / "revise-context.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    return parse_material_review_revise_context(payload)
