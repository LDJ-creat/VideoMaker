from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agents.runner import AgentRunner
from app.agents.scene_script_adaptor import run_scene_script_adaptor
from app.agents.scene_visual_adaptor import run_scene_visual_adaptor
from app.gateway.model_gateway import ModelGateway
from app.pipelines.script_draft import load_script_draft, save_script_draft
from app.runtime.task_context import TaskContext

DRIFT_REPORT_FILENAME = "narration/drift-report.json"
ESTIMATED_SNAPSHOT_FILENAME = "narration/drift-estimated-snapshot.json"
VISUAL_ADAPTATIONS_DIR = "narration/drift-adaptations"
SCRIPT_ADAPTATIONS_DIR = "narration/drift-script-adaptations"
SCRIPT_PASS_COUNTS_FILENAME = "narration/drift-script-pass-counts.json"

WARN_THRESHOLD = float(os.getenv("VIDEOMAKER_DRIFT_WARN_THRESHOLD", "0.15"))
STRONG_THRESHOLD = float(os.getenv("VIDEOMAKER_DRIFT_STRONG_THRESHOLD", "0.30"))
CHARS_PER_SEC_MAX = float(os.getenv("VIDEOMAKER_DRIFT_CHARS_PER_SEC_MAX", "6.0"))
CHARS_PER_SEC_MIN = float(os.getenv("VIDEOMAKER_DRIFT_CHARS_PER_SEC_MIN", "2.0"))
CRITICAL_SLOT_ROLES = frozenset({"hook", "hook_visual", "hook_text", "cta", "proof"})


def save_estimated_snapshot(generation_root: Path, storyboard: list[dict[str, Any]]) -> None:
    snapshot: dict[str, float] = {}
    for scene in storyboard:
        if not isinstance(scene, dict) or not scene.get("slotId"):
            continue
        start = float(scene.get("startSec", 0.0))
        end = float(scene.get("endSec", start))
        snapshot[str(scene["slotId"])] = round(max(0.1, end - start), 3)
    path = generation_root / ESTIMATED_SNAPSHOT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")


def load_estimated_snapshot(generation_root: Path) -> dict[str, float]:
    path = generation_root / ESTIMATED_SNAPSHOT_FILENAME
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return {str(key): float(value) for key, value in payload.items()}


def load_drift_report(generation_root: Path) -> dict[str, Any] | None:
    path = generation_root / DRIFT_REPORT_FILENAME
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _slot_role(structure: dict[str, Any], slot_id: str) -> str:
    for slot in structure.get("slots") or []:
        if isinstance(slot, dict) and str(slot.get("id")) == slot_id:
            return str(slot.get("role") or slot.get("slotRole") or "")
    return ""


def _structure_slot(structure: dict[str, Any], slot_id: str) -> dict[str, Any]:
    for slot in structure.get("slots") or []:
        if isinstance(slot, dict) and str(slot.get("id")) == slot_id:
            return dict(slot)
    return {}


def _wpm_budget(measured_sec: float, *, slot_role: str, vo_directive: dict[str, Any] | None) -> dict[str, int]:
    wpm = 240.0
    if slot_role.startswith("hook") or slot_role == "cta":
        wpm *= 1.15
    elif slot_role in {"proof", "benefit_card"}:
        wpm *= 0.95
    if isinstance(vo_directive, dict):
        pace = str(vo_directive.get("pace") or "").lower()
        if pace == "fast":
            wpm *= 1.2
        elif pace == "slow":
            wpm *= 0.85
    words = round(measured_sec * wpm / 60.0)
    return {"min": max(1, int(words * 0.8)), "max": max(1, int(words * 1.2))}


def _classify_root_cause(
    *,
    drift_ratio: float,
    chars_per_sec: float,
    char_count: int,
    wpm_budget: dict[str, int],
    slot_role: str,
) -> str:
    if char_count > wpm_budget["max"] * 1.25 or chars_per_sec > CHARS_PER_SEC_MAX:
        return "word_count_high"
    if (chars_per_sec < CHARS_PER_SEC_MIN or char_count < wpm_budget["min"]) and slot_role in CRITICAL_SLOT_ROLES:
        return "word_count_low"
    if abs(drift_ratio - 1.0) <= WARN_THRESHOLD:
        return "within_budget"
    return "pace_mismatch"


def _resolution_path(root_cause: str, drift_ratio: float) -> str:
    if root_cause in {"word_count_high", "word_count_low"}:
        auto = os.getenv("VIDEOMAKER_DRIFT_AUTO_SCRIPT", "false").strip().lower() == "true"
        return "script_revise" if auto else "user_pending"
    if abs(drift_ratio - 1.0) > STRONG_THRESHOLD:
        return "visual_adapt"
    if abs(drift_ratio - 1.0) > WARN_THRESHOLD:
        return "rules_only"
    return "rules_only"


def _apply_rules_timing_adaptation(
    scene: dict[str, Any],
    *,
    estimated_sec: float,
    measured_sec: float,
    drift_ratio: float,
) -> dict[str, Any]:
    updated = dict(scene)
    brief = dict(updated.get("compositionAuthorBrief") or {}) if isinstance(updated.get("compositionAuthorBrief"), dict) else {}
    if brief or updated.get("source") == "packaging_completion":
        if not brief:
            brief = {"mode": "hf_native", "authorPrompt": str(updated.get("visual") or "适配实测口播时长")}
        timing_context = {
            "measuredDurationSec": round(measured_sec, 3),
            "estimatedDurationSec": round(estimated_sec, 3),
            "driftRatio": round(drift_ratio, 3),
        }
        if drift_ratio < 0.70:
            timing_context["motionDensity"] = "compact"
            beat_count = 2
        elif drift_ratio > 1.25:
            timing_context["motionDensity"] = "sparse"
            beat_count = max(3, int(round(measured_sec / 2.0)))
        else:
            timing_context["motionDensity"] = "normal"
            beat_count = max(2, int(round(measured_sec / 2.5)))
        timing_context["beatCount"] = beat_count
        brief["timingContext"] = timing_context
        prompt = str(brief.get("authorPrompt") or "")
        if drift_ratio < 0.70:
            suffix = (
                f"【时长适配】实测口播 {measured_sec:.1f}s（原估 {estimated_sec:.1f}s）。"
                f"动画须紧凑：≤{beat_count} 个视觉 beat，快入快出，禁止长 static hold。"
            )
        elif drift_ratio > 1.25:
            suffix = (
                f"【时长适配】实测口播 {measured_sec:.1f}s（原估 {estimated_sec:.1f}s）。"
                f"动画须铺满全程：至少 {beat_count} beat 分段出字/转场，避免大块静止。"
            )
        else:
            suffix = ""
        if suffix and suffix not in prompt:
            brief["authorPrompt"] = f"{prompt.rstrip()} {suffix}".strip()[:600]
        updated["compositionAuthorBrief"] = brief
    return updated


def _timing_payload_from_entry(entry: dict[str, Any], scene: dict[str, Any]) -> dict[str, Any]:
    measured_sec = float(entry.get("measuredSec") or 0.0)
    drift_ratio = float(entry.get("driftRatio") or 1.0)
    vo_directive = scene.get("voDirective") if isinstance(scene.get("voDirective"), dict) else None
    slot_role = str(entry.get("slotRole") or "")
    motion = "normal"
    if drift_ratio < 0.70:
        motion = "compact"
    elif drift_ratio > 1.25:
        motion = "sparse"
    beat_count = max(2, int(round(measured_sec / (2.0 if motion == "sparse" else 2.5))))
    return {
        "estimatedSec": float(entry.get("estimatedSec") or measured_sec),
        "measuredSec": measured_sec,
        "driftRatio": drift_ratio,
        "charsPerSec": float(entry.get("charsPerSec") or 0.0),
        "wpmBudget": entry.get("wpmBudget") or _wpm_budget(measured_sec, slot_role=slot_role, vo_directive=vo_directive),
        "motionDensity": motion,
        "beatCount": beat_count,
    }


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _append_adaptation_index(generation_root: Path, rel_dir: str, meta: dict[str, Any]) -> str:
    adaptation_id = str(meta.get("adaptationId") or uuid.uuid4().hex[:12])
    meta = {**meta, "adaptationId": adaptation_id, "createdAt": _utc_now_iso()}
    root = generation_root / rel_dir / adaptation_id
    root.mkdir(parents=True, exist_ok=True)
    (root / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    index_path = generation_root / rel_dir / "index.jsonl"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(meta, ensure_ascii=False) + "\n")
    return adaptation_id


def _write_adaptation_payload(generation_root: Path, rel_dir: str, adaptation_id: str, **files: Any) -> None:
    root = generation_root / rel_dir / adaptation_id
    for name, payload in files.items():
        path = root / name
        if isinstance(payload, str):
            path.write_text(payload, encoding="utf-8")
        else:
            path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_script_pass_counts(generation_root: Path) -> dict[str, int]:
    path = generation_root / SCRIPT_PASS_COUNTS_FILENAME
    if not path.is_file():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {}
    return {str(key): int(value) for key, value in payload.items()}


def _increment_script_pass_count(generation_root: Path, slot_id: str) -> int:
    counts = _load_script_pass_counts(generation_root)
    counts[slot_id] = counts.get(slot_id, 0) + 1
    path = generation_root / SCRIPT_PASS_COUNTS_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(counts, ensure_ascii=False, indent=2), encoding="utf-8")
    return counts[slot_id]


def _script_pass_allowed(generation_root: Path, slot_id: str) -> bool:
    max_passes = int(os.getenv("VIDEOMAKER_DRIFT_MAX_SCRIPT_PASSES", "1"))
    return _load_script_pass_counts(generation_root).get(slot_id, 0) < max_passes


def _maybe_run_visual_llm_adaptor(
    *,
    generation_root: Path,
    runner: AgentRunner | None,
    structure: dict[str, Any],
    draft: dict[str, Any],
    storyboard: list[dict[str, Any]],
    entry: dict[str, Any],
    context: TaskContext,
    generation_id: str,
) -> None:
    if runner is None:
        return
    if os.getenv("VIDEOMAKER_DRIFT_LLM_VISUAL", "true").strip().lower() != "true":
        return
    if str(entry.get("resolutionPath")) != "visual_adapt":
        return
    if abs(float(entry.get("driftRatio") or 1.0) - 1.0) <= STRONG_THRESHOLD:
        return
    slot_id = str(entry["slotId"])
    scene_index = next(
        (index for index, scene in enumerate(storyboard) if str(scene.get("slotId")) == slot_id),
        None,
    )
    if scene_index is None:
        return
    scene = storyboard[scene_index]
    brief = scene.get("compositionAuthorBrief")
    if not isinstance(brief, dict):
        return
    timing_payload = _timing_payload_from_entry(entry, scene)
    slot_role = str(entry.get("slotRole") or _slot_role(structure, slot_id))
    visual_style_bible = draft.get("visualStyleBible") if isinstance(draft.get("visualStyleBible"), dict) else None
    inputs = {
        "scene": scene,
        "timing": timing_payload,
        "slotRole": slot_role,
        "visualStyleBible": visual_style_bible,
        "structureSlot": _structure_slot(structure, slot_id),
        "driftWarnings": list(entry.get("warnings") or []),
    }
    adaptation_id = _append_adaptation_index(
        generation_root,
        VISUAL_ADAPTATIONS_DIR,
        {"slotId": slot_id, "path": "visual", "agent": "scene_visual_adaptor", "driftRatio": entry.get("driftRatio")},
    )
    _write_adaptation_payload(generation_root, VISUAL_ADAPTATIONS_DIR, adaptation_id, inputs=inputs)
    try:
        output = run_scene_visual_adaptor(
            runner,
            scene=scene,
            timing=timing_payload,
            slot_role=slot_role,
            visual_style_bible=visual_style_bible,
            structure_slot=_structure_slot(structure, slot_id),
            drift_warnings=list(entry.get("warnings") or []),
            context=context,
            generation_id=generation_id,
        )
    except Exception as exc:
        _write_adaptation_payload(
            generation_root,
            VISUAL_ADAPTATIONS_DIR,
            adaptation_id,
            error={"message": str(exc)},
        )
        return
    _write_adaptation_payload(
        generation_root,
        VISUAL_ADAPTATIONS_DIR,
        adaptation_id,
        normalized=output,
        raw_output=getattr(runner.llm, "last_raw_output", None),
    )
    updated = dict(scene)
    updated["compositionAuthorBrief"] = output["compositionAuthorBrief"]
    if isinstance(output.get("visual"), str):
        updated["visual"] = output["visual"]
    storyboard[scene_index] = updated


def build_drift_report(
    *,
    generation_id: str,
    content_hash: str,
    draft: dict[str, Any],
    structure: dict[str, Any],
    timing: dict[str, Any],
    estimated_by_slot: dict[str, float],
) -> dict[str, Any]:
    duration_target = float(draft.get("durationTargetSec") or 0.0)
    total_duration = float(timing.get("durationSec") or 0.0)
    timing_by_slot = {
        str(item.get("slotId")): item
        for item in timing.get("sceneTiming") or []
        if isinstance(item, dict) and item.get("slotId")
    }
    slots: list[dict[str, Any]] = []
    for scene in draft.get("storyboard") or []:
        if not isinstance(scene, dict) or not scene.get("slotId"):
            continue
        slot_id = str(scene["slotId"])
        measured_item = timing_by_slot.get(slot_id, scene)
        measured_sec = max(
            0.1,
            float(measured_item.get("endSec", 0.0)) - float(measured_item.get("startSec", 0.0)),
        )
        estimated_sec = float(estimated_by_slot.get(slot_id) or measured_sec)
        drift_ratio = measured_sec / estimated_sec if estimated_sec > 0 else 1.0
        script = str(scene.get("script") or "")
        char_count = len(script)
        chars_per_sec = char_count / measured_sec if measured_sec > 0 else 0.0
        slot_role = _slot_role(structure, slot_id)
        vo_directive = scene.get("voDirective") if isinstance(scene.get("voDirective"), dict) else None
        wpm_budget = _wpm_budget(measured_sec, slot_role=slot_role, vo_directive=vo_directive)
        root_cause = _classify_root_cause(
            drift_ratio=drift_ratio,
            chars_per_sec=chars_per_sec,
            char_count=char_count,
            wpm_budget=wpm_budget,
            slot_role=slot_role,
        )
        resolution = _resolution_path(root_cause, drift_ratio)
        warnings: list[str] = []
        if abs(drift_ratio - 1.0) > WARN_THRESHOLD:
            warnings.append("drift_warn")
        if abs(drift_ratio - 1.0) > STRONG_THRESHOLD:
            warnings.append("drift_strong")
        slots.append(
            {
                "slotId": slot_id,
                "estimatedSec": round(estimated_sec, 3),
                "measuredSec": round(measured_sec, 3),
                "driftRatio": round(drift_ratio, 3),
                "charCount": char_count,
                "charsPerSec": round(chars_per_sec, 3),
                "wpmBudget": wpm_budget,
                "slotRole": slot_role,
                "rootCause": root_cause,
                "resolutionPath": resolution,
                "warnings": warnings,
            }
        )
    report: dict[str, Any] = {
        "generationId": generation_id,
        "contentHash": content_hash,
        "durationTargetSec": duration_target,
        "totalDurationSec": round(total_duration, 3),
        "slots": slots,
    }
    if duration_target > 0 and total_duration > duration_target * 1.05:
        report["totalDurationOverTarget"] = True
        report["overTargetSec"] = round(total_duration - duration_target, 3)
        candidate = max(slots, key=lambda item: int(item.get("charCount") or 0))
        candidate["rootCause"] = "word_count_high"
        candidate["resolutionPath"] = _resolution_path(
            "word_count_high",
            float(candidate.get("driftRatio") or 1.0),
        )
        warnings = list(candidate.get("warnings") or [])
        if "duration_target_exceeded" not in warnings:
            warnings.append("duration_target_exceeded")
        candidate["warnings"] = warnings
    return report


def run_narration_drift_resolution(
    *,
    generation_root: Path,
    structure: dict[str, Any],
    timing: dict[str, Any],
    context: TaskContext,
    generation_id: str,
    runner: AgentRunner | None = None,
    auto_script: bool = True,
) -> dict[str, Any]:
    draft = load_script_draft(generation_root)
    if draft is None:
        raise ValueError("script-draft.json not found for drift resolution")

    estimated_by_slot = load_estimated_snapshot(generation_root)
    report = build_drift_report(
        generation_id=generation_id,
        content_hash=str(timing.get("contentHash") or ""),
        draft=draft,
        structure=structure,
        timing=timing,
        estimated_by_slot=estimated_by_slot,
    )

    storyboard = [dict(scene) for scene in draft.get("storyboard") or [] if isinstance(scene, dict)]
    script_queue: list[str] = []

    for entry in report["slots"]:
        resolution = str(entry.get("resolutionPath") or "rules_only")
        if resolution in {"rules_only", "visual_adapt"}:
            slot_id = str(entry["slotId"])
            for index, scene in enumerate(storyboard):
                if str(scene.get("slotId")) != slot_id:
                    continue
                storyboard[index] = _apply_rules_timing_adaptation(
                    scene,
                    estimated_sec=float(entry["estimatedSec"]),
                    measured_sec=float(entry["measuredSec"]),
                    drift_ratio=float(entry["driftRatio"]),
                )
                break
            _maybe_run_visual_llm_adaptor(
                generation_root=generation_root,
                runner=runner,
                structure=structure,
                draft=draft,
                storyboard=storyboard,
                entry=entry,
                context=context,
                generation_id=generation_id,
            )
        elif resolution == "script_revise" and auto_script and _script_pass_allowed(generation_root, str(entry["slotId"])):
            script_queue.append(str(entry["slotId"]))
        elif resolution == "user_pending":
            context.emit_event(
                stage="adapting_narration_density",
                progress=55,
                message=f"Slot {entry['slotId']} needs script density fix",
            )

    draft["storyboard"] = storyboard
    save_script_draft(generation_root, draft)

    report_path = generation_root / DRIFT_REPORT_FILENAME
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    plan_path = generation_root / "generation-plan.json"
    if plan_path.is_file():
        try:
            plan_payload = json.loads(plan_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            plan_payload = None
        if isinstance(plan_payload, dict):
            plan_payload["narrationDriftReportUri"] = "narration/drift-report.json"
            plan_path.write_text(json.dumps(plan_payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if script_queue and runner is not None:
        for slot_id in script_queue:
            run_slot_script_revise_and_resync(
                generation_root=generation_root,
                structure=structure,
                context=context,
                generation_id=generation_id,
                runner=runner,
                slot_id=slot_id,
                instruction=None,
                gateway=None,
            )
        report = load_drift_report(generation_root) or report

    return report


def _default_script_instruction(entry: dict[str, Any]) -> str:
    slot_id = str(entry.get("slotId") or "")
    measured = float(entry.get("measuredSec") or 0.0)
    estimated = float(entry.get("estimatedSec") or 0.0)
    char_count = int(entry.get("charCount") or 0)
    chars_per_sec = float(entry.get("charsPerSec") or 0.0)
    wpm_budget = entry.get("wpmBudget") or {"min": 1, "max": 1}
    slot_role = str(entry.get("slotRole") or "")
    return (
        f"镜 {slot_id} 实测口播 {measured:.1f}s，原估 {estimated:.1f}s，当前 {char_count} 字，"
        f"字/秒 {chars_per_sec:.1f}。请将本镜 script 调整至 {wpm_budget.get('min')}–{wpm_budget.get('max')} 字，"
        f"使口播密度与 {slot_role} 角色匹配，并同步更新 masterNarration 对应片段，保持语气一致。"
    )


def run_slot_script_revise_and_resync(
    *,
    generation_root: Path,
    structure: dict[str, Any],
    context: TaskContext,
    generation_id: str,
    runner: AgentRunner,
    slot_id: str,
    instruction: str | None,
    gateway: ModelGateway | None,
) -> dict[str, Any]:
    from app.pipelines.canonical_narration import run_canonical_narration_synthesis
    from app.pipelines.narration_scene_timing import load_narration_timing
    from app.pipelines.tts_synthesis import resolve_synthesis_mode

    if not _script_pass_allowed(generation_root, slot_id):
        raise ValueError("drift_script_pass_limit_reached")

    draft = load_script_draft(generation_root)
    if draft is None:
        raise ValueError("script-draft.json not found")
    report = load_drift_report(generation_root)
    if report is None:
        raise ValueError("drift-report.json not found")

    entry = next((item for item in report.get("slots") or [] if str(item.get("slotId")) == slot_id), None)
    if not isinstance(entry, dict):
        raise ValueError("slot_not_in_drift_report")

    storyboard = [dict(scene) for scene in draft.get("storyboard") or [] if isinstance(scene, dict)]
    scene = next((item for item in storyboard if str(item.get("slotId")) == slot_id), None)
    if scene is None:
        raise ValueError("slot_not_in_storyboard")

    timing_payload = _timing_payload_from_entry(entry, scene)
    resolved_instruction = (instruction or "").strip() or _default_script_instruction(entry)
    visual_style_bible = draft.get("visualStyleBible") if isinstance(draft.get("visualStyleBible"), dict) else None
    adaptation_id = _append_adaptation_index(
        generation_root,
        SCRIPT_ADAPTATIONS_DIR,
        {
            "slotId": slot_id,
            "path": "script",
            "agent": "scene_script_adaptor",
            "driftRatio": entry.get("driftRatio"),
        },
    )
    inputs = {
        "targetSlotId": slot_id,
        "scene": scene,
        "masterNarration": str(draft.get("masterNarration") or ""),
        "timing": timing_payload,
        "instruction": resolved_instruction,
    }
    _write_adaptation_payload(generation_root, SCRIPT_ADAPTATIONS_DIR, adaptation_id, inputs=inputs)

    output = run_scene_script_adaptor(
        runner,
        target_slot_id=slot_id,
        scene=scene,
        master_narration=str(draft.get("masterNarration") or ""),
        timing=timing_payload,
        slot_role=str(entry.get("slotRole") or _slot_role(structure, slot_id)),
        duration_target_sec=float(draft.get("durationTargetSec") or 30.0),
        visual_style_bible=visual_style_bible,
        instruction=resolved_instruction,
        context=context,
        generation_id=generation_id,
    )
    _write_adaptation_payload(
        generation_root,
        SCRIPT_ADAPTATIONS_DIR,
        adaptation_id,
        normalized=output,
        raw_output=getattr(runner.llm, "last_raw_output", None),
    )

    for index, item in enumerate(storyboard):
        if str(item.get("slotId")) != slot_id:
            continue
        updated = dict(item)
        updated["script"] = output["script"]
        if isinstance(output.get("voDirective"), dict):
            updated["voDirective"] = output["voDirective"]
        storyboard[index] = updated
        break

    draft["storyboard"] = storyboard
    draft["masterNarration"] = output["masterNarration"]
    save_script_draft(generation_root, draft)
    _increment_script_pass_count(generation_root, slot_id)

    if gateway is None:
        return {"ok": True, "adaptationId": adaptation_id, "draft": draft, "resynced": False}

    from app.pipelines.canonical_narration import invalidate_narration_timing

    prior_timing = load_narration_timing(generation_root)
    synthesis_mode = ""
    if isinstance(prior_timing, dict):
        synthesis_mode = str(prior_timing.get("synthesisMode") or "")
    if not synthesis_mode:
        synthesis_mode = resolve_synthesis_mode(
            storyboard=storyboard,
            structure=structure,
            workbench_prefs=gateway.config.tts_preferences,
            generation_id=generation_id,
            narration_vo_profile=(
                draft.get("narrationVoProfile") if isinstance(draft.get("narrationVoProfile"), dict) else None
            ),
        )
    invalidate_narration_timing(generation_root)
    changed_slots = {slot_id} if synthesis_mode == "segmented" else None
    timing = run_canonical_narration_synthesis(
        gateway=gateway,
        structure=structure,
        context=context,
        generation_id=generation_id,
        generation_root=generation_root,
        draft=draft,
        changed_slot_ids=changed_slots,
        force=True,
        runner=runner,
    )
    run_narration_drift_resolution(
        generation_root=generation_root,
        structure=structure,
        timing=timing,
        context=context,
        generation_id=generation_id,
        runner=runner,
        auto_script=False,
    )
    return {"ok": True, "adaptationId": adaptation_id, "draft": load_script_draft(generation_root), "resynced": True}
