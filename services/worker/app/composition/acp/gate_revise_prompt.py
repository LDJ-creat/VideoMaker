from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.pipelines.material_slot_revise import MATERIAL_GATE_REVISE_SOURCE

_REVIEW_SUMMARY_MAX_CHARS = 2048


def is_gate_revise_author_payload(payload: dict[str, Any]) -> bool:
    gate = payload.get("materialGateRevise")
    if isinstance(gate, dict) and gate.get("source") == MATERIAL_GATE_REVISE_SOURCE:
        return True
    contract = payload.get("authorContract")
    return isinstance(contract, dict) and contract.get("mustChangeSpec") is True


def _load_prior_review_summary(generation_root: Path | None, slot_id: str) -> dict[str, Any] | None:
    if generation_root is None or not slot_id:
        return None
    report_path = generation_root / "material-reviews" / slot_id / "report.json"
    if not report_path.is_file():
        return None
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(report, dict):
        return None
    summary: dict[str, Any] = {}
    issues = report.get("issues")
    if isinstance(issues, list) and issues:
        summary["issues"] = [str(item) for item in issues[:8]]
    suggestions = report.get("suggestions")
    if isinstance(suggestions, list) and suggestions:
        summary["suggestions"] = [str(item) for item in suggestions[:6]]
    approved = report.get("approved")
    if approved is not None:
        summary["approved"] = bool(approved)
    if not summary:
        return None
    text = json.dumps(summary, ensure_ascii=False)
    if len(text) > _REVIEW_SUMMARY_MAX_CHARS:
        summary["issues"] = summary.get("issues", [])[:4]
        summary["suggestions"] = summary.get("suggestions", [])[:3]
    return summary or None


def build_gate_revise_prompt_user_payload(
    payload: dict[str, Any],
    *,
    generation_root: Path | None = None,
) -> dict[str, Any]:
    """Slim user prompt for material gate NL revise (no full existingMaterialSpec)."""
    slim: dict[str, Any] = {}
    for key in (
        "slot",
        "slotId",
        "slotTiming",
        "editInstruction",
        "materialEditMode",
        "authorContract",
        "renderPolicy",
        "existingSpecHash",
        "brandColors",
        "renderTarget",
        "finishBrief",
        "compositionAuthorBrief",
    ):
        if key in payload:
            slim[key] = payload[key]
    gate = payload.get("materialGateRevise")
    if isinstance(gate, dict):
        slim["materialGateRevise"] = {
            key: gate[key]
            for key in (
                "source",
                "materialEditMode",
                "editInstruction",
                "affectedSlotIds",
                "authorContract",
            )
            if key in gate
        }
    slot_id = str(payload.get("slotId") or "").strip()
    if not slot_id:
        slot_obj = payload.get("slot")
        if isinstance(slot_obj, dict):
            slot_id = str(slot_obj.get("id") or slot_obj.get("slotId") or "").strip()
    if not slot_id:
        gate = payload.get("materialGateRevise")
        if isinstance(gate, dict):
            affected = gate.get("affectedSlotIds")
            if isinstance(affected, list) and affected:
                slot_id = str(affected[0]).strip()
    review_summary = _load_prior_review_summary(generation_root, slot_id)
    if review_summary:
        slim["priorReviewSummary"] = review_summary
    return slim
