from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from app.pipelines.material_review import (
    enrich_material_review_report,
    material_spec_content_hash,
    preview_content_hash,
)

MaterializeMode = Literal["copy_preview", "render", "skip"]
FinalSource = Literal["preview_copy", "render"]

MARKER_FILENAME = "material-review-marker.json"
PREVIEW_FILENAME = "preview.mp4"
PREVIEW_COMPOSITION_DIR = "preview-composition"


def scratch_dir_for_slot(generation_root: Path, slot_id: str) -> Path:
    """Preferred ACP scratch; prefer this when writing ACP artifacts."""
    return generation_root / "acp-author" / slot_id


def author_scratch_dirs_for_slot(generation_root: Path, slot_id: str) -> list[Path]:
    """ACP and ReAct author scratch roots for a slot (order: prefer first hit)."""
    return [
        generation_root / "acp-author" / slot_id,
        generation_root / "react-author" / slot_id,
    ]


def load_scratch_review_marker(generation_root: Path, slot_id: str) -> dict[str, Any] | None:
    """Load in-session review marker from ACP or ReAct scratch (first match wins)."""
    for scratch in author_scratch_dirs_for_slot(generation_root, slot_id):
        path = scratch / MARKER_FILENAME
        if not path.is_file():
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    return None


def resolve_author_scratch_with_marker(generation_root: Path, slot_id: str) -> Path | None:
    for scratch in author_scratch_dirs_for_slot(generation_root, slot_id):
        if (scratch / MARKER_FILENAME).is_file():
            return scratch
    return None


def should_promote_as_passed(marker: dict[str, Any] | None, *, spec: dict[str, Any]) -> bool:
    if not isinstance(marker, dict) or not marker.get("approved"):
        return False
    return str(marker.get("specHash") or "") == material_spec_content_hash(spec)


def should_materialize_final(
    *,
    scratch_dir: Path,
    spec: dict[str, Any] | None,
    force_render: bool = False,
) -> MaterializeMode:
    if force_render:
        return "render" if isinstance(spec, dict) else "skip"
    preview_path = scratch_dir / PREVIEW_FILENAME
    if preview_path.is_file() and preview_path.stat().st_size > 0:
        if isinstance(spec, dict):
            marker = _load_marker_payload(scratch_dir)
            if marker is not None:
                current_hash = material_spec_content_hash(spec)
                marker_hash = str(marker.get("specHash") or "")
                if marker_hash and marker_hash != current_hash:
                    return "render"
                report = marker.get("report")
                if isinstance(report, dict):
                    report_hash = str(report.get("specHash") or "")
                    if report_hash and report_hash != current_hash:
                        return "render"
        return "copy_preview"
    if isinstance(spec, dict):
        return "render"
    return "skip"


def _load_marker_payload(scratch_dir: Path) -> dict[str, Any] | None:
    path = scratch_dir / MARKER_FILENAME
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


@dataclass(frozen=True)
class MaterializeResult:
    ok: bool
    final_path: Path | None
    final_source: FinalSource | None
    error: str | None = None


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _copy_tree_if_exists(source: Path, dest: Path) -> None:
    if not source.is_dir():
        return
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)
    shutil.copytree(source, dest)


def materialize_final_to_generated(
    *,
    scratch_dir: Path,
    generated_root: Path,
    action_id: str,
    spec: dict[str, Any] | None,
    mode: MaterializeMode,
) -> MaterializeResult:
    output_clip = generated_root / f"{action_id}.mp4"
    action_dir = generated_root / action_id
    action_dir.mkdir(parents=True, exist_ok=True)

    if mode == "skip":
        return MaterializeResult(ok=False, final_path=None, final_source=None, error="nothing_to_materialize")

    if mode == "copy_preview":
        preview_path = scratch_dir / PREVIEW_FILENAME
        if not preview_path.is_file() or preview_path.stat().st_size <= 0:
            return MaterializeResult(
                ok=False,
                final_path=None,
                final_source=None,
                error="scratch_preview_missing",
            )
        shutil.copy2(preview_path, output_clip)
        preview_composition = scratch_dir / PREVIEW_COMPOSITION_DIR
        _copy_tree_if_exists(preview_composition, action_dir / "composition")
        scratch_spec = scratch_dir / "material-spec.json"
        if scratch_spec.is_file() and isinstance(spec, dict):
            (action_dir / "material-spec.json").write_text(
                json.dumps(spec, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        elif scratch_spec.is_file():
            shutil.copy2(scratch_spec, action_dir / "material-spec.json")
        return MaterializeResult(ok=True, final_path=output_clip, final_source="preview_copy")

    if not isinstance(spec, dict):
        return MaterializeResult(ok=False, final_path=None, final_source=None, error="spec_missing_for_render")
    return MaterializeResult(ok=True, final_path=output_clip, final_source="render")


def promote_marker_report(
    marker: dict[str, Any],
    *,
    spec: dict[str, Any],
    final_preview_path: Path,
    generation_id: str,
    slot_id: str,
    provider: str,
    final_source: FinalSource,
) -> dict[str, Any]:
    embedded = marker.get("report")
    if isinstance(embedded, dict):
        report = dict(embedded)
    else:
        report = {
            "slotId": slot_id,
            "generationId": generation_id,
            "reviewedAt": _utc_now_iso(),
            "approved": bool(marker.get("approved")),
            "issues": [],
            "suggestions": [],
            "reviewInputs": {"mode": "video"},
            "provider": provider,
        }
    report["slotId"] = slot_id
    report["generationId"] = generation_id
    report["provider"] = provider
    review_inputs = dict(report.get("reviewInputs") or {})
    review_inputs["mode"] = str(review_inputs.get("mode") or "video")
    review_inputs["videoPath"] = str(final_preview_path.resolve())
    review_inputs["reviewReuse"] = "in_session"
    report["reviewInputs"] = review_inputs
    report["reviewPhase"] = "promoted"
    report["finalSource"] = final_source
    trace = dict(report.get("trace") or {})
    trace["reviewRoute"] = "promoted"
    report["trace"] = trace
    return enrich_material_review_report(report, spec=spec, preview_path=final_preview_path)


def build_gate_report_without_marker(
    *,
    slot_id: str,
    generation_id: str,
    provider: str,
    preview_path: Path | None,
    spec: dict[str, Any] | None,
    review_bypass: str,
    final_source: FinalSource = "render",
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "slotId": slot_id,
        "generationId": generation_id,
        "reviewedAt": _utc_now_iso(),
        "approved": False,
        "issues": [f"review_bypass:{review_bypass}"],
        "suggestions": [
            "Preview is ready for manual review."
            if preview_path is not None and preview_path.is_file()
            else "Re-run author session or revise this slot before final assembly."
        ],
        "reviewInputs": {"mode": "skipped"},
        "provider": provider,
        "reviewBypass": review_bypass,
        "reviewPhase": "promoted",
        "finalSource": final_source,
        "trace": {"reviewRoute": "promoted"},
    }
    if preview_path is not None and preview_path.is_file() and isinstance(spec, dict):
        review_inputs = dict(report["reviewInputs"])
        review_inputs["videoPath"] = str(preview_path.resolve())
        report["reviewInputs"] = review_inputs
        return enrich_material_review_report(report, spec=spec, preview_path=preview_path)
    return report


def marker_report_for_finalize(
    *,
    generation_root: Path,
    slot_id: str,
    spec: dict[str, Any],
    final_preview_path: Path,
    generation_id: str,
    provider: str,
    final_source: FinalSource,
    partial_harvest: bool = False,
) -> dict[str, Any]:
    marker = load_scratch_review_marker(generation_root, slot_id)
    if isinstance(marker, dict):
        if should_promote_as_passed(marker, spec=spec):
            return promote_marker_report(
                marker,
                spec=spec,
                final_preview_path=final_preview_path,
                generation_id=generation_id,
                slot_id=slot_id,
                provider=provider,
                final_source=final_source,
            )
        if marker.get("report") or not marker.get("approved"):
            report = promote_marker_report(
                marker,
                spec=spec,
                final_preview_path=final_preview_path,
                generation_id=generation_id,
                slot_id=slot_id,
                provider=provider,
                final_source=final_source,
            )
            if not report.get("reviewUnavailable"):
                report["approved"] = False
            return report
    bypass = "partial_harvest" if partial_harvest else "no_in_session_marker"
    return build_gate_report_without_marker(
        slot_id=slot_id,
        generation_id=generation_id,
        provider=provider,
        preview_path=final_preview_path,
        spec=spec,
        review_bypass=bypass,
        final_source=final_source,
    )
