from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from evaluation.usage_normalize import normalize_chat_usage

HUMAN_GATE_STAGES = frozenset({
    "awaiting_master_review",
    "awaiting_storyboard_review",
    "awaiting_material_review",
})

CHAT_PROFILE_TEXT = frozenset({"text"})
CHAT_PROFILE_VISION = frozenset({"vision", "video_understanding"})


def _empty_category(billing_unit: str) -> dict[str, Any]:
    base: dict[str, Any] = {"billingUnit": billing_unit, "calls": 0, "latencyMs": 0.0}
    if billing_unit == "tokens":
        base.update({"promptTokens": 0.0, "completionTokens": 0.0, "totalTokens": 0.0})
    elif billing_unit == "chars":
        base["totalChars"] = 0.0
    elif billing_unit == "images":
        base["successfulImages"] = 0
        base["failedCalls"] = 0
    return base


def _init_usage_by_category() -> dict[str, Any]:
    return {
        "text_chat": _empty_category("tokens"),
        "vision_chat": _empty_category("tokens"),
        "tts": {**_empty_category("chars"), "totalChars": 0.0},
        "image_gen": {**_empty_category("images"), "successfulImages": 0, "failedCalls": 0},
        "video_gen": {
            "billingUnit": "video_seconds",
            "successfulJobs": 0,
            "totalDurationSec": 0.0,
            "requestedDurationSec": 0.0,
            "latencyMs": 0.0,
            "jobs": [],
        },
    }


def _category_key_for_chat(profile: str) -> str:
    if profile in CHAT_PROFILE_VISION:
        return "vision_chat"
    return "text_chat"


def _read_model_calls(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str | None = None,
    task_id: str | None = None,
) -> list[dict[str, Any]]:
    log_dir = storage_root / "projects" / project_id / "logs" / "model-calls"
    if not log_dir.is_dir():
        return []
    calls: list[dict[str, Any]] = []
    for path in log_dir.glob("*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if generation_id is not None and payload.get("generationId") != generation_id:
            continue
        if task_id is not None and payload.get("taskId") != task_id:
            continue
        calls.append(payload)
    return calls


def _usage_from_call(payload: dict[str, Any]) -> dict[str, Any] | None:
    units = payload.get("usageUnits")
    if isinstance(units, dict):
        return units
    token_usage = payload.get("tokenUsage")
    if isinstance(token_usage, dict):
        normalized = normalize_chat_usage(token_usage)
        if normalized:
            return {
                "kind": "tokens",
                "prompt": normalized.get("prompt"),
                "completion": normalized.get("completion"),
                "total": normalized.get("total"),
            }
    output = payload.get("output")
    if isinstance(output, dict):
        kind = payload.get("callKind")
        if kind == "tts" and payload.get("outputValid"):
            chars = output.get("charCount")
            if chars is not None:
                return {"kind": "chars", "chars": float(chars), "calls": 1.0}
        if kind == "image" and payload.get("outputValid"):
            return {"kind": "images", "images": 1.0, "calls": 1.0}
    return None


def _accumulate_chat(category: dict[str, Any], units: dict[str, Any], latency_ms: float) -> None:
    category["calls"] = int(category.get("calls", 0)) + 1
    category["latencyMs"] = float(category.get("latencyMs", 0.0)) + latency_ms
    prompt = float(units.get("prompt") or 0)
    completion = float(units.get("completion") or 0)
    total = float(units.get("total") or (prompt + completion))
    category["promptTokens"] = float(category.get("promptTokens", 0.0)) + prompt
    category["completionTokens"] = float(category.get("completionTokens", 0.0)) + completion
    category["totalTokens"] = float(category.get("totalTokens", 0.0)) + total


def _merge_video_submit_poll(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    submits = [c for c in calls if c.get("callKind") == "video_submit"]
    polls = [c for c in calls if c.get("callKind") == "video_poll"]
    polls_by_job: dict[str, list[dict[str, Any]]] = {}
    for poll in polls:
        job_id = str(poll.get("jobId") or (poll.get("output") or {}).get("jobId") or "")
        if not job_id:
            input_payload = poll.get("input")
            if isinstance(input_payload, dict):
                job_id = str(input_payload.get("jobId") or "")
        if job_id:
            polls_by_job.setdefault(job_id, []).append(poll)

    jobs: list[dict[str, Any]] = []
    for submit in submits:
        output = submit.get("output") if isinstance(submit.get("output"), dict) else {}
        job_id = str(submit.get("jobId") or output.get("jobId") or "")
        if not job_id:
            continue
        input_payload = submit.get("input") if isinstance(submit.get("input"), dict) else {}
        options = input_payload.get("options") if isinstance(input_payload.get("options"), dict) else {}
        requested = options.get("durationSec")
        slot_id = options.get("slotId") or submit.get("slotId")
        poll_list = polls_by_job.get(job_id, [])
        poll_latency = sum(float(p.get("latencyMs") or 0) for p in poll_list)
        submit_latency = float(submit.get("latencyMs") or 0)
        units = _usage_from_call(submit) or {}
        if not units:
            units = submit.get("usageUnits") if isinstance(submit.get("usageUnits"), dict) else {}
        actual = units.get("actualDurationSec")
        for poll in poll_list:
            if poll.get("outputValid"):
                poll_units = poll.get("usageUnits")
                if isinstance(poll_units, dict) and poll_units.get("actualDurationSec") is not None:
                    actual = poll_units.get("actualDurationSec")
                elif isinstance(poll.get("output"), dict) and poll["output"].get("durationSec") is not None:
                    actual = poll["output"].get("durationSec")
        successful = any(p.get("outputValid") for p in poll_list) or bool(submit.get("outputValid"))
        if not successful:
            continue
        job_entry = {
            "jobId": job_id,
            "slotId": str(slot_id) if slot_id else None,
            "model": str(submit.get("model") or ""),
            "requestedDurationSec": float(requested) if requested is not None else None,
            "actualDurationSec": float(actual) if actual is not None else None,
            "outputBytes": None,
            "latencyMs": submit_latency + poll_latency,
        }
        for poll in poll_list:
            out = poll.get("output")
            if isinstance(out, dict) and out.get("bytes") is not None:
                job_entry["outputBytes"] = int(out["bytes"])
        jobs.append(job_entry)
    return jobs


def rollup_model_calls(calls: list[dict[str, Any]]) -> dict[str, Any]:
    usage = _init_usage_by_category()
    model_latency: dict[str, float] = {
        "text_chat": 0.0,
        "vision_chat": 0.0,
        "tts": 0.0,
        "image_gen": 0.0,
        "video_gen": 0.0,
    }

    non_video_calls = [c for c in calls if c.get("callKind") not in {"video_submit", "video_poll"}]
    for call in non_video_calls:
        kind = str(call.get("callKind") or "")
        profile = str(call.get("profile") or "text")
        latency = float(call.get("latencyMs") or 0)
        units = _usage_from_call(call)

        if kind in {"chat_json", "chat_text", "chat_tools"}:
            cat_key = _category_key_for_chat(profile)
            cat = usage[cat_key]
            if units and units.get("kind") == "tokens":
                _accumulate_chat(cat, units, latency)
            else:
                cat["calls"] = int(cat.get("calls", 0)) + 1
                cat["latencyMs"] = float(cat.get("latencyMs", 0.0)) + latency
            model_latency[cat_key] += latency
        elif kind == "tts":
            cat = usage["tts"]
            cat["calls"] = int(cat.get("calls", 0)) + 1
            cat["latencyMs"] = float(cat.get("latencyMs", 0.0)) + latency
            if call.get("outputValid") and units and units.get("chars") is not None:
                cat["totalChars"] = float(cat.get("totalChars", 0.0)) + float(units["chars"])
            model_latency["tts"] += latency
        elif kind == "image":
            cat = usage["image_gen"]
            cat["calls"] = int(cat.get("calls", 0)) + 1
            cat["latencyMs"] = float(cat.get("latencyMs", 0.0)) + latency
            if call.get("outputValid"):
                cat["successfulImages"] = int(cat.get("successfulImages", 0)) + 1
            else:
                cat["failedCalls"] = int(cat.get("failedCalls", 0)) + 1
            model_latency["image_gen"] += latency

    video_jobs = _merge_video_submit_poll(calls)
    video_cat = usage["video_gen"]
    video_cat["jobs"] = video_jobs
    video_cat["successfulJobs"] = len(video_jobs)
    total_sec = 0.0
    requested_sec = 0.0
    for job in video_jobs:
        video_cat["latencyMs"] = float(video_cat.get("latencyMs", 0.0)) + float(job.get("latencyMs") or 0)
        if job.get("actualDurationSec") is not None:
            total_sec += float(job["actualDurationSec"])
        elif job.get("requestedDurationSec") is not None:
            total_sec += float(job["requestedDurationSec"])
        if job.get("requestedDurationSec") is not None:
            requested_sec += float(job["requestedDurationSec"])
    video_cat["totalDurationSec"] = round(total_sec, 3)
    video_cat["requestedDurationSec"] = round(requested_sec, 3)
    model_latency["video_gen"] = float(video_cat["latencyMs"])

    # Drop empty categories for cleaner reports
    cleaned: dict[str, Any] = {}
    for key, value in usage.items():
        if key == "video_gen":
            if value.get("successfulJobs", 0) > 0 or value.get("latencyMs", 0) > 0:
                cleaned[key] = value
            continue
        if int(value.get("calls", 0)) > 0:
            cleaned[key] = value
    return {"usageByCategory": cleaned, "modelLatency": model_latency}


def _parse_iso(value: str | None) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _model_calls_dir_has_files(storage_root: Path, project_id: str) -> bool:
    log_dir = storage_root / "projects" / project_id / "logs" / "model-calls"
    if not log_dir.is_dir():
        return False
    return any(log_dir.glob("*.json"))


def _detect_acp_untracked(storage_root: Path, project_id: str, generation_id: str | None) -> bool:
    tool_dir = storage_root / "projects" / project_id / "logs" / "tool-runs"
    if not tool_dir.is_dir():
        return False
    for path in tool_dir.glob("acp_session_*.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if generation_id is None or payload.get("generationId") == generation_id:
            return True
    return False


def enrich_human_gate_stages_from_events(
    stages: list[dict[str, Any]],
    events: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not events:
        return stages

    parsed: list[tuple[datetime, dict[str, Any]]] = []
    for event in events:
        updated = _parse_iso(str(event.get("updatedAt") or ""))
        if updated is not None:
            parsed.append((updated, event))
    parsed.sort(key=lambda item: item[0])
    if not parsed:
        return stages

    enriched = list(stages)
    for idx in range(len(parsed) - 1):
        event_time, event = parsed[idx]
        next_time, next_event = parsed[idx + 1]
        stage = str(event.get("stage") or "")
        status = str(event.get("status") or "")
        if stage not in HUMAN_GATE_STAGES and status != "awaiting_review":
            continue
        gate_stage = stage if stage in HUMAN_GATE_STAGES else str(next_event.get("stage") or stage)
        duration_ms = max(0.0, (next_time - event_time).total_seconds() * 1000)
        replaced = False
        for entry in enriched:
            if entry.get("stage") == gate_stage and entry.get("endedAt") is None:
                entry["endedAt"] = next_time.isoformat().replace("+00:00", "Z")
                entry["durationMs"] = round(duration_ms, 3)
                entry["kind"] = "human_gate"
                entry["status"] = "paused"
                replaced = True
                break
        if not replaced and gate_stage in HUMAN_GATE_STAGES:
            enriched.append(
                {
                    "stage": gate_stage,
                    "startedAt": event_time.isoformat().replace("+00:00", "Z"),
                    "endedAt": next_time.isoformat().replace("+00:00", "Z"),
                    "durationMs": round(duration_ms, 3),
                    "status": "paused",
                    "kind": "human_gate",
                }
            )
    return enriched


def timing_from_checkpoint(checkpoint: dict[str, Any] | None) -> dict[str, Any]:
    stages: list[dict[str, Any]] = []
    if isinstance(checkpoint, dict):
        raw_stages = checkpoint.get("stageTimings")
        if isinstance(raw_stages, list):
            stages = [item for item in raw_stages if isinstance(item, dict)]

    human_wait_ms = 0.0
    active_ms = 0.0
    for stage in stages:
        duration = float(stage.get("durationMs") or 0)
        name = str(stage.get("stage") or "")
        kind = stage.get("kind")
        if kind == "human_gate" or name in HUMAN_GATE_STAGES:
            human_wait_ms += duration
        else:
            active_ms += duration

    total_ms = human_wait_ms + active_ms
    wall_clock: dict[str, Any] = {
        "totalMs": total_ms,
        "queuedMs": 0.0,
        "activeMs": active_ms,
        "humanWaitMs": human_wait_ms,
    }
    if stages:
        first = stages[0]
        last = stages[-1]
        if first.get("startedAt"):
            wall_clock["startedAt"] = first["startedAt"]
        if last.get("endedAt"):
            wall_clock["endedAt"] = last["endedAt"]
    return {"wallClock": wall_clock, "stages": stages}


def timing_from_task_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    if not events:
        return timing_from_checkpoint(None)

    parsed: list[tuple[datetime, dict[str, Any]]] = []
    for event in events:
        updated = _parse_iso(str(event.get("updatedAt") or ""))
        if updated is not None:
            parsed.append((updated, event))
    parsed.sort(key=lambda item: item[0])
    if not parsed:
        return timing_from_checkpoint(None)

    started_at = parsed[0][0].isoformat().replace("+00:00", "Z")
    ended_at = parsed[-1][0].isoformat().replace("+00:00", "Z")
    total_ms = (parsed[-1][0] - parsed[0][0]).total_seconds() * 1000

    human_wait_ms = 0.0
    queued_ms = 0.0
    for idx in range(1, len(parsed)):
        prev_time, prev_event = parsed[idx - 1]
        cur_time, cur_event = parsed[idx]
        delta = (cur_time - prev_time).total_seconds() * 1000
        prev_stage = str(prev_event.get("stage") or "")
        status = str(cur_event.get("status") or "")
        if prev_stage in HUMAN_GATE_STAGES or status == "awaiting_review":
            human_wait_ms += delta
        elif status == "queued":
            queued_ms += delta

    active_ms = max(0.0, total_ms - human_wait_ms - queued_ms)
    return {
        "wallClock": {
            "totalMs": total_ms,
            "queuedMs": queued_ms,
            "activeMs": active_ms,
            "humanWaitMs": human_wait_ms,
            "startedAt": started_at,
            "endedAt": ended_at,
        },
        "stages": [],
    }


def build_observability_summary(
    storage_root: Path,
    *,
    project_id: str,
    generation_id: str,
    task_id: str | None = None,
    checkpoint: dict[str, Any] | None = None,
    task_events: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    calls = _read_model_calls(
        storage_root,
        project_id=project_id,
        generation_id=generation_id,
        task_id=task_id,
    )
    rollup = rollup_model_calls(calls)
    ck_timing = timing_from_checkpoint(checkpoint)
    if task_events:
        event_timing = timing_from_task_events(task_events)
        if event_timing["wallClock"]["totalMs"] > ck_timing["wallClock"]["totalMs"]:
            ck_timing["wallClock"] = event_timing["wallClock"]
        ck_timing["stages"] = enrich_human_gate_stages_from_events(
            ck_timing.get("stages") or [],
            task_events,
        )
        human_wait_ms = 0.0
        active_ms = 0.0
        for stage in ck_timing["stages"]:
            duration = float(stage.get("durationMs") or 0)
            name = str(stage.get("stage") or "")
            kind = stage.get("kind")
            if kind == "human_gate" or name in HUMAN_GATE_STAGES:
                human_wait_ms += duration
            else:
                active_ms += duration
        ck_timing["wallClock"]["humanWaitMs"] = max(
            float(ck_timing["wallClock"].get("humanWaitMs") or 0),
            human_wait_ms,
        )
        ck_timing["wallClock"]["activeMs"] = active_ms

    warnings: list[str] = []
    notes: list[str] = []
    incomplete = False
    if os.getenv("VIDEOMAKER_OBSERVABILITY_CAPTURE", "full").strip().lower() == "off":
        incomplete = True
        warnings.append("observability_capture_off")
    if not calls:
        incomplete = True
        warnings.append("no_model_calls_found")

    video_cat = rollup["usageByCategory"].get("video_gen")
    if isinstance(video_cat, dict):
        for job in video_cat.get("jobs") or []:
            if job.get("actualDurationSec") is None and job.get("requestedDurationSec") is not None:
                warnings.append("video_duration_estimated")

    if not _model_calls_dir_has_files(storage_root, project_id):
        incomplete = True

    if generation_id and _detect_acp_untracked(storage_root, project_id, generation_id):
        notes.append("acpAuthorUntracked")

    notes.append("rollup_authority=model_calls")

    return {
        "incomplete": incomplete,
        "warnings": warnings,
        "notes": notes,
        "usageByCategory": rollup["usageByCategory"],
        "timing": {
            "wallClock": ck_timing["wallClock"],
            "stages": ck_timing["stages"],
            "modelLatency": rollup["modelLatency"],
        },
    }
