"""ReAct author-session vision review (Worker-owned), aligned with ACP in-session policy."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def react_in_session_review_enabled() -> bool:
    raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_REACT_IN_SESSION", "true").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def material_review_max_rounds() -> int:
    raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_MAX_ROUNDS", "1").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 1


def material_review_repair_followup_max() -> int:
    raw = os.getenv("VIDEOMAKER_MATERIAL_REVIEW_REPAIR_FOLLOWUP_MAX", "1").strip()
    try:
        return max(0, int(raw))
    except ValueError:
        return 1


def react_author_scratch_dir(generation_root: Path | None, slot_id: str) -> Path | None:
    if generation_root is None or not str(slot_id).strip():
        return None
    return Path(generation_root) / "react-author" / str(slot_id).strip()


def _preview_profile() -> str:
    raw = os.getenv("VIDEOMAKER_MATERIAL_PREVIEW_PROFILE", "fast").strip().lower()
    return raw if raw in {"full", "fast"} else "fast"


def _build_repair_feedback(report: dict[str, Any]) -> str:
    try:
        from app.pipelines.material_review import build_repair_feedback

        text = build_repair_feedback(report)
        if text.strip():
            return text
    except Exception:
        pass
    suggestions = [str(item) for item in report.get("suggestions") or [] if str(item).strip()]
    issues = [str(item) for item in report.get("issues") or [] if str(item).strip()]
    parts: list[str] = []
    if suggestions:
        parts.append("Apply these review fixes: " + "; ".join(suggestions))
    if issues:
        parts.append("Issues: " + "; ".join(issues))
    return " ".join(parts).strip() or "Fix material preview issues and re-submit."


@dataclass(frozen=True)
class ReactSessionReviewResult:
    approved: bool
    report: dict[str, Any]
    vision_billed: bool
    repair_feedback: str | None = None
    error: str | None = None


def run_react_session_review(
    *,
    spec: dict[str, Any],
    scratch_dir: Path,
    repo_root: Path,
    author_payload: dict[str, Any],
    aspect_ratio: str,
    review_gateway: Any | None,
    agent_review_round: int,
    hyperframes_cli: Any | None = None,
) -> ReactSessionReviewResult:
    """Render preview + Worker vision review; write marker on completion."""
    from composition.material_review.preview import (
        render_material_preview_spec,
        run_review_via_worker,
    )
    from composition.material_review.session import write_review_marker

    scratch_dir.mkdir(parents=True, exist_ok=True)
    preview_path = scratch_dir / "preview.mp4"
    render = render_material_preview_spec(
        spec,
        scratch_dir=scratch_dir,
        repo_root=repo_root,
        aspect_ratio=aspect_ratio,
        asset_root=None,
        preview_profile=_preview_profile(),
    )
    if not render.get("ok"):
        err = render.get("error") if isinstance(render.get("error"), dict) else {}
        message = str(err.get("message") or "preview_render_failed")
        report = {
            "approved": False,
            "hardGateFailed": True,
            "issues": [message],
            "suggestions": ["Fix composition so preview can render, then re-submit."],
            "agentReviewRound": agent_review_round,
            "reviewPhase": "author_session",
            "trace": {"reviewRoute": "author_session_preview_failed"},
        }
        write_review_marker(scratch_dir, spec=spec, report=report)
        return ReactSessionReviewResult(
            approved=False,
            report=report,
            vision_billed=False,
            repair_feedback=_build_repair_feedback(report),
            error=message,
        )

    preview_path = Path(str(render.get("previewPath") or preview_path))
    slot = author_payload.get("slot") if isinstance(author_payload.get("slot"), dict) else {}
    slot_id = str(slot.get("id") or author_payload.get("slotId") or "slot")
    generation_id = str(author_payload.get("generationId") or "generation")
    generation_root_raw = author_payload.get("generationRoot")
    generation_root = Path(generation_root_raw) if generation_root_raw else None

    # Prefer parent generation dir (not generated/) for review paths when available.
    if generation_root is not None and generation_root.name == "generated":
        generation_root = generation_root.parent

    review_result = run_review_via_worker(
        preview_path=preview_path,
        spec=spec,
        author_payload=author_payload,
        slot_id=slot_id,
        generation_id=generation_id,
        generation_root=generation_root,
        agent_review_round=agent_review_round,
        gateway=review_gateway,
    )

    report: dict[str, Any]
    vision_billed = True
    if isinstance(review_result, dict) and isinstance(review_result.get("report"), dict):
        report = dict(review_result["report"])
        if review_result.get("cached") or review_result.get("skipped"):
            vision_billed = False
        if not review_result.get("ok") and not report.get("approved"):
            # infrastructure path may set ok True with waived report
            pass
    elif isinstance(review_result, dict) and review_result.get("ok") is False:
        err = review_result.get("error") if isinstance(review_result.get("error"), dict) else {}
        message = str(err.get("message") or review_result.get("error") or "review_failed")
        report = {
            "approved": False,
            "issues": [message],
            "suggestions": ["Retry review after fixing preview/gateway."],
            "agentReviewRound": agent_review_round,
            "reviewPhase": "author_session",
            "trace": {"reviewRoute": "author_session_error"},
        }
        vision_billed = False
    else:
        report = {
            "approved": False,
            "issues": ["review_result_invalid"],
            "suggestions": ["Re-submit after fixing material author review path."],
            "agentReviewRound": agent_review_round,
            "reviewPhase": "author_session",
        }
        vision_billed = False

    report.setdefault("agentReviewRound", agent_review_round)
    report["reviewPhase"] = "author_session"
    trace = dict(report.get("trace") or {})
    trace.setdefault("reviewRoute", "author_session")
    report["trace"] = trace

    write_review_marker(scratch_dir, spec=spec, report=report)
    approved = bool(report.get("approved")) and not report.get("hardGateFailed")
    feedback = None if approved else _build_repair_feedback(report)
    return ReactSessionReviewResult(
        approved=approved,
        report=report,
        vision_billed=vision_billed,
        repair_feedback=feedback,
    )


def write_exhausted_review_marker(
    scratch_dir: Path,
    *,
    spec: dict[str, Any],
    report: dict[str, Any] | None,
    review_rounds_used: int,
) -> None:
    from composition.material_review.session import write_review_marker

    payload = dict(report or {})
    payload["approved"] = False
    issues = [str(i) for i in payload.get("issues") or [] if str(i).strip()]
    if not any("review_rounds_exhausted" in i for i in issues):
        issues.append(f"review_rounds_exhausted:{review_rounds_used}")
    payload["issues"] = issues
    payload["reviewPhase"] = "author_session"
    payload.setdefault("suggestions", payload.get("suggestions") or [])
    write_review_marker(scratch_dir, spec=spec, report=payload)
