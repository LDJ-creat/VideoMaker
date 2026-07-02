from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


MARKER_FILENAME = "material-review-marker.json"


def material_spec_content_hash(spec: dict[str, Any]) -> str:
    payload = json.dumps(spec, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _spec_hash(spec: dict[str, Any]) -> str:
    return material_spec_content_hash(spec)


def marker_path(scratch_dir: Path) -> Path:
    return scratch_dir / MARKER_FILENAME


def write_review_marker(scratch_dir: Path, *, spec: dict[str, Any], report: dict[str, Any]) -> None:
    scratch_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "specHash": _spec_hash(spec),
        "approved": bool(report.get("approved")),
        "report": report,
    }
    marker_path(scratch_dir).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def validate_review_marker(scratch_dir: Path, spec: dict[str, Any]) -> str | None:
    path = marker_path(scratch_dir)
    if not path.is_file():
        return "Call review_material_preview before write_material_spec."
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return "Material review marker is invalid."
    if not isinstance(payload, dict):
        return "Material review marker is invalid."
    if str(payload.get("specHash") or "") != _spec_hash(spec):
        return "Material review marker does not match current spec_json."
    if not payload.get("approved"):
        return "Preview review not approved."
    return None
